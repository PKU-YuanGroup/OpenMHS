"""Owned stdio for one fixed SDK-controlled POSIX peer; native admission stays off.

This is not a command runner or a native MCP transport factory. Process cleanup
is software ownership only, never instrument quiescence. Abrupt host death is
outside the in-process ownership contract.
"""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
import copy
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import threading
import time

from ..driver.mcp_client_config import encoded, plain

_PEER_PATH = str(Path(__file__).resolve().parents[3] / 'tests/fixtures/mcp_stdio_peer.py')
_EXECUTABLE = str(Path(sys.executable).resolve())
_PEER_SHA256 = '88bd047fed28fc52966cbdfd01e92e29ff8e968296770e70378728ef6ab6d6af'
_INIT_ID = 'mhs-owned-stdio-initialize'
_VERSION = '2025-11-25'


class StdioFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class StdioBudget:
    frame_bytes: int = 16 * 1024 * 1024
    aggregate_bytes: int = 32 * 1024 * 1024
    outgoing_bytes: int = 64 * 1024
    handshake_bytes: int = 64 * 1024
    control_bytes: int = 4096
    handshake_ms: int = 2000
    write_ms: int = 100
    grace_ms: int = 250
    terminate_ms: int = 250
    kill_ms: int = 500
    ledger_ids: int = 4096
    stderr_bytes: int = 65536
    control_rate: int = 64
    controls_per_request: int = 1024

    def __post_init__(self):
        maximum = (('frame_bytes',16*1024*1024),('aggregate_bytes',32*1024*1024),
                   ('outgoing_bytes',65536),('handshake_bytes',65536),('control_bytes',4096),
                   ('handshake_ms',2000),('write_ms',100),('grace_ms',250),('terminate_ms',250),
                   ('kill_ms',500),('ledger_ids',4096),('stderr_bytes',65536),
                   ('control_rate',64),('controls_per_request',1024))
        for name, limit in maximum:
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= limit:
                raise ValueError('invalid finite stdio budget: ' + name)
        if self.ledger_ids < 8 or self.aggregate_bytes < self.frame_bytes:
            raise ValueError('stdio budget lacks identity reserve or one complete frame')


@dataclass
class _Request:
    ident: str
    lane: str
    message: dict
    deadline: float
    issued: bool = False
    sent: bool = False
    writing: bool = False
    cancel_queued: bool = False
    controls: int = 0
    queued: bool = False
    done: bool = False
    abandoned: bool = False
    response: dict | None = None
    wire_bytes: int = 0


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate JSON key')
        value[key] = item
    return value


def _constant(value):
    raise ValueError('nonfinite JSON constant: ' + value)


class OwnedStdioTransport:
    """Lazy concrete SDK peer owner, injected only through controlled fake tests.

    ``directory`` is a caller-owned private directory. The executable and peer
    source are fixed by the SDK; no options select a command, endpoint or code.
    The fixed peer may read bounded test data there, but never executes it.
    """
    def __init_subclass__(cls, **kwargs):
        raise TypeError('owned stdio transport is concrete, not extensible')

    def __init__(self, directory, *, budget=None):
        if os.name != 'posix':
            raise RuntimeError('controlled stdio currently requires POSIX')
        if budget is not None and type(budget) is not StdioBudget:
            raise TypeError('stdio requires a concrete immutable budget')
        path = Path(directory)
        if not path.is_absolute() or path.is_symlink():
            raise ValueError('stdio needs an absolute owned directory')
        info = path.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('stdio directory must be private and owned by this caller')
        self._directory = str(path.resolve())
        # Detach caller state and revalidate even a concrete frozen dataclass:
        # Python callers can bypass frozen assignment with object.__setattr__.
        self._budget = StdioBudget(**vars(budget)) if budget is not None else StdioBudget()
        self._condition = threading.Condition(threading.RLock())
        self._state = 'NEW'
        self._epoch = 0
        self._fenced = False
        self._reason = None
        self._failure_response = None
        self._initialization = None
        self._process = None
        self._supervisor = None
        self._workers = []
        self._requests = {}
        self._ledger = set()
        self._queue = []
        self._sequence = 0
        self._wire_bytes = 0
        self._partial_bytes = 0
        self._decoding_bytes = 0
        self._peak_bytes = 0
        self._stderr = bytearray()
        self._stderr_discarded = 0
        self._controls = deque()
        self._control_count = 0
        self._listener = None
        self._health_delivered = False
        self._retired = threading.Event()
        self._startup_deadline = None
        self._trace = deque(maxlen=128)

    def attach(self, listener):
        with self._condition:
            if self._listener is not None:
                raise RuntimeError('owned stdio peer already attached')
            self._listener = listener
        self._notify_health()

    def _notify_health(self):
        with self._condition:
            callback = self._listener if self._fenced and not self._health_delivered else None
            if callback is not None:
                self._health_delivered = True
        if callback is not None:
            try:
                callback()
            except BaseException as exc:
                # Health notification failure must not strand process cleanup.
                # The owner epoch is already terminal; guarded commits refuse.
                with self._condition:
                    self._trace.append({'direction':'health_callback_error','type':type(exc).__name__})

    @contextmanager
    def ownership_guard(self):
        # Bridge condition -> ownership lock. No callback or I/O under this lock.
        with self._condition:
            live = (self._state == 'READY' and not self._fenced and self._process is not None
                    and self._process.poll() is None)
            yield self._epoch if live else None

    def status(self):
        with self._condition:
            return {'state':self._state,'epoch':self._epoch,'fenced':self._fenced,'reason':self._reason,
                    'retired':self._retired.is_set(),'pending':list(self._requests),
                    'pid':self._process.pid if self._process is not None else None,
                    'retained_bytes':self._wire_bytes+self._partial_bytes+self._decoding_bytes,'peak_bytes':self._peak_bytes,
                    'stderr_retained':len(self._stderr),'stderr_discarded':self._stderr_discarded,
                    'failure_response':copy.deepcopy(self._failure_response),
                    'initialization':copy.deepcopy(self._initialization),
                    'issued_ids':len(self._ledger),'trace':copy.deepcopy(list(self._trace))}

    def _fence_locked(self, reason):
        if not self._fenced:
            self._fenced = True
            self._epoch += 1
            self._reason = str(reason)[:256]
            self._state = 'FENCED'
        self._condition.notify_all()

    def request_close(self, reason='closed'):
        with self._condition:
            self._fence_locked(reason)
            if self._supervisor is None and self._process is None:
                self._state = 'CLOSED'
                self._retired.set()
        self._notify_health()

    def abandon(self, ident, reason='caller abandoned'):
        with self._condition:
            request = self._requests.get(ident)
            if request is not None and not request.abandoned:
                request.abandoned = True
                if request.sent and not request.cancel_queued and ident != _INIT_ID:
                    request.cancel_queued=True
                    self._enqueue_locked({'jsonrpc':'2.0','method':'notifications/cancelled',
                        'params':{'requestId':ident,'reason':'controlled client abandoned request'}},
                        priority=0, kind='cancel', deadline=time.monotonic()+self._budget.write_ms/1000)
            self._fence_locked(reason)
            if self._supervisor is None and self._process is None:
                self._state='CLOSED'
                self._retired.set()
        self._notify_health()

    def wait_retired(self, timeout=None):
        return self._retired.wait(timeout)

    def close(self):
        self.request_close()

    def _enqueue_locked(self, message, *, priority, kind, deadline, request=None):
        maximum = self._budget.control_bytes if kind in ('cancel','initialized','control') else self._budget.outgoing_bytes
        data = encoded(message, maximum) + b'\n'
        # Reserve control/protective capacity instead of an unbounded queue.
        if len(self._queue) >= (4 if priority >= 2 else 8):
            self._fence_locked('writer queue budget exceeded')
            return
        self._sequence += 1
        self._queue.append((priority,self._sequence,data,kind,deadline,request))
        self._queue.sort(key=lambda entry:entry[:2])
        self._condition.notify_all()

    def _start_locked(self, deadline):
        if self._state != 'NEW':
            return
        self._state = 'STARTING'
        self._startup_deadline = min(deadline,time.monotonic()+self._budget.handshake_ms/1000)
        worker = threading.Thread(target=self._supervise,name='mhs-owned-stdio-supervisor',daemon=True)
        self._supervisor = worker
        try:
            worker.start()
        except BaseException:
            self._fence_locked('supervisor startup failure')
            if worker.ident is None:
                self._supervisor = None
                self._state = 'CLOSED'
                self._retired.set()

    def exchange(self, message, *, lane, timeout_ms):
        # Validation and registration precede every possible spawn or write.
        data = encoded(message,self._budget.outgoing_bytes)
        if (type(message) is not dict or set(message) != {'jsonrpc','id','method','params'}
                or message['jsonrpc'] != '2.0' or type(message['id']) is not str
                or not 1 <= len(message['id']) <= 128 or message['id'] == _INIT_ID
                or message['method'] not in ('tools/list','tools/call') or lane not in ('normal','protective')
                or type(timeout_ms) is not int or not 1 <= timeout_ms <= 60000):
            raise ValueError('invalid controlled exchange')
        ident = message['id']
        request = _Request(ident,lane,copy.deepcopy(message),time.monotonic()+timeout_ms/1000)
        rejected = False
        with self._condition:
            if self._fenced:
                rejected = True
            elif ident in self._ledger or any(item.lane == lane for item in self._requests.values()):
                raise StdioFailure('request identity/lane is already owned')
            elif len(self._ledger) >= self._budget.ledger_ids - (5 if lane == 'normal' else 1):
                raise StdioFailure('finite lifetime identity budget exhausted')
            else:
                self._ledger.add(ident)
                self._requests[ident] = request
                self._start_locked(request.deadline)
        if rejected:
            self.wait_retired()
            raise StdioFailure('stdio owner is permanently fenced')
        self._notify_health()
        try:
            while True:
                with self._condition:
                    if not self._fenced and self._state == 'READY' and not request.queued:
                        request.queued = True
                        self._enqueue_locked(request.message,priority=1 if lane=='protective' else 2,
                            kind='tool',deadline=request.deadline,request=request)
                    if request.done and not request.abandoned and not self._fenced:
                        result = request.response
                        request.response = None
                        self._wire_bytes -= request.wire_bytes
                        request.wire_bytes = 0
                        return result
                    expired = time.monotonic() >= request.deadline
                    fenced = self._fenced
                    if not expired and not fenced:
                        self._condition.wait(min(.02,max(0,request.deadline-time.monotonic())))
                        continue
                if expired and not fenced:
                    self.abandon(ident,'request deadline expired')
                # The caller's bridge deadline remains finite; its worker stays
                # here through definitive software retirement, not an RPC wait.
                self.wait_retired()
                raise StdioFailure(self._reason or 'stdio request failed')
        finally:
            with self._condition:
                self._requests.pop(ident,None)
                self._wire_bytes -= request.wire_bytes
                request.response = None
                self._condition.notify_all()

    def _peer_source(self):
        flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os,'O_NOFOLLOW',0)
        fd = os.open(_PEER_PATH,flags)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 128*1024:
                raise ValueError('invalid fixed SDK peer source')
            data = bytearray()
            while len(data) <= 128*1024:
                part = os.read(fd,16384)
                if not part:break
                data.extend(part)
            if hashlib.sha256(data).hexdigest() != _PEER_SHA256:
                raise ValueError('fixed SDK peer source digest differs')
            # Execute these exact already-verified bytes, avoiding a subsequent
            # script-path reopen. Neither code nor executable is caller selected.
            return '__file__ = '+repr(_PEER_PATH)+'\n'+bytes(data).decode('utf-8')
        finally:
            os.close(fd)

    def _supervise(self):
        try:
            source = self._peer_source()
            with self._condition:
                if self._fenced:return
            process = subprocess.Popen([_EXECUTABLE,'-I','-S','-B','-u','-c',source,self._directory],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                cwd=self._directory,env={'PYTHONOPTIMIZE':'0','PYTHONDONTWRITEBYTECODE':'1'},
                start_new_session=True,close_fds=True,bufsize=0)
            with self._condition:
                self._process = process
                self._state = 'FENCED' if self._fenced else 'INITIALIZING'
                self._ledger.add(_INIT_ID)
                self._requests[_INIT_ID] = _Request(_INIT_ID,'init',{},self._startup_deadline)
            for name,stream,target in [('writer',process.stdin,self._writer),('stdout',process.stdout,self._reader),('stderr',process.stderr,self._drain_stderr)]:
                os.set_blocking(stream.fileno(),False)
                done = threading.Event()
                def run(stream=stream,target=target,done=done):
                    try:target(stream)
                    except BaseException as exc:self.request_close(type(exc).__name__+': '+str(exc))
                    finally:
                        stream.close()
                        done.set()
                        with self._condition:self._condition.notify_all()
                worker = threading.Thread(target=run,name='mhs-owned-stdio-'+name,daemon=True)
                self._workers.append((worker,done,stream))
                try:worker.start()
                except BaseException:
                    if worker.ident is None:
                        stream.close();done.set()
                    raise
            with self._condition:
                self._enqueue_locked({'jsonrpc':'2.0','id':_INIT_ID,'method':'initialize','params':{
                    'protocolVersion':_VERSION,'capabilities':{},'clientInfo':{'name':'openmhs-controlled','version':'1'}}},
                    priority=0,kind='init',deadline=self._startup_deadline,request=self._requests[_INIT_ID])
            while True:
                with self._condition:
                    if self._fenced:break
                    expired = next((r.ident for r in self._requests.values() if not r.done and time.monotonic()>=r.deadline),None)
                    if process.poll() is not None:
                        self._fence_locked('owned child exited')
                    elif expired is None:
                        self._condition.wait(.02)
                if expired is not None:self.abandon(expired,'request deadline expired')
            self._notify_health()
        except BaseException as exc:
            self.request_close(type(exc).__name__+': '+str(exc))
        finally:
            with self._condition:
                self._fence_locked(self._reason or 'owner closing')
            self._notify_health()
            self._retire()

    def _writer(self, stream):
        fd = stream.fileno()
        while True:
            with self._condition:
                while not self._queue and not self._fenced:self._condition.wait(.02)
                if self._fenced:
                    self._queue[:] = [entry for entry in self._queue if entry[3]=='cancel']
                if not self._queue:return
                _priority,_sequence,data,kind,deadline,request = self._queue.pop(0)
                if request is not None and (request.abandoned or self._fenced):continue
            deadline = min(deadline,time.monotonic()+self._budget.write_ms/1000)
            offset = 0
            if request is not None:
                with self._condition:request.writing=True
            while offset < len(data):
                with self._condition:
                    if self._fenced and kind!='cancel':return
                if time.monotonic()>=deadline:raise StdioFailure('partial frame write deadline')
                if not select.select([], [fd], [], min(.02,max(0,deadline-time.monotonic())))[1]:continue
                try:
                    count = os.write(fd,data[offset:offset+16384])
                except BlockingIOError:continue
                if count<=0:raise StdioFailure('empty pipe write')
                if request is not None:
                    with self._condition:request.issued=True
                offset += count
            with self._condition:
                if request is not None:
                    request.sent=True;request.writing=False
                    if request.abandoned and not request.cancel_queued and request.ident!=_INIT_ID:
                        request.cancel_queued=True
                        self._enqueue_locked({'jsonrpc':'2.0','method':'notifications/cancelled','params':{'requestId':request.ident,'reason':'controlled client abandoned request'}},priority=0,kind='cancel',deadline=time.monotonic()+self._budget.write_ms/1000)
                self._trace.append({'direction':'out','id':request.ident if request else None,'kind':kind,'bytes':len(data)-1})
                if kind=='initialized' and not self._fenced:
                    self._state='READY'
                self._condition.notify_all()

    def _set_partial(self, size):
        with self._condition:
            if size+self._wire_bytes+self._decoding_bytes > self._budget.aggregate_bytes:
                raise StdioFailure('aggregate incoming byte budget')
            self._partial_bytes=size
            self._peak_bytes=max(self._peak_bytes,size+self._wire_bytes+self._decoding_bytes)

    def _reader(self, stream):
        fd=stream.fileno();buffer=bytearray()
        try:
            while True:
                if not select.select([fd],[],[],.02)[0]:continue
                try:chunk=os.read(fd,16384)
                except BlockingIOError:continue
                if not chunk:
                    raise StdioFailure('unterminated EOF' if buffer else 'stdio EOF')
                self._set_partial(len(buffer)+len(chunk))
                buffer.extend(chunk)
                while b'\n' in buffer:
                    end=buffer.index(b'\n')
                    limit=min(self._budget.frame_bytes,self._budget.handshake_bytes) if self._state=='INITIALIZING' else self._budget.frame_bytes
                    if end>limit:raise StdioFailure('incoming frame byte budget')
                    line=bytes(buffer[:end]);del buffer[:end+1]
                    if line.endswith(b'\r'):line=line[:-1]
                    if not line:raise StdioFailure('blank stdout frame')
                    with self._condition:
                        self._partial_bytes=len(buffer);self._decoding_bytes=len(line)
                    try:self._receive(line)
                    finally:
                        with self._condition:self._decoding_bytes=0
                    self._set_partial(len(buffer))
                limit=min(self._budget.frame_bytes,self._budget.handshake_bytes) if self._state=='INITIALIZING' else self._budget.frame_bytes
                if len(buffer)>limit:raise StdioFailure('unterminated frame byte budget')
        finally:
            self._set_partial(0)

    def _receive(self, line):
        value=json.loads(line.decode('utf-8'),object_pairs_hook=_pairs,parse_constant=_constant)
        plain(value)
        if type(value) is not dict or value.get('jsonrpc')!='2.0':
            raise StdioFailure('invalid JSON-RPC object')
        with self._condition:
            if self._fenced:return
            if 'method' in value:
                self._control_locked(value,len(line))
                return
            if set(value) not in ({'jsonrpc','id','result'},{'jsonrpc','id','error'}) or type(value.get('id')) is not str:
                raise StdioFailure('ambiguous or mistyped response')
            ident=value['id'];request=self._requests.get(ident)
            while request is not None and request.writing and not request.sent and not self._fenced:
                self._condition.wait(.01)
            if self._fenced:return
            if request is None or request.done or not request.sent:
                raise StdioFailure('unknown, duplicate or unissued response ID')
            if 'error' in value or (type(value.get('result')) is dict and value['result'].get('isError') is True):
                if len(line)+self._wire_bytes+self._partial_bytes>self._budget.aggregate_bytes:
                    raise StdioFailure('aggregate error evidence budget')
                self._failure_response=value
                self._wire_bytes+=len(line)
                self._decoding_bytes=0
                self._trace.append({'direction':'error','id':ident,'sha256':hashlib.sha256(line).hexdigest()})
                raise StdioFailure('peer reports protocol/tool failure')
            if ident==_INIT_ID:
                result=value['result']
                if (len(line)>self._budget.handshake_bytes or type(result) is not dict
                        or set(result)-{'protocolVersion','capabilities','serverInfo','instructions'}
                        or result.get('protocolVersion')!=_VERSION or type(result.get('capabilities')) is not dict
                        or type(result['capabilities'].get('tools')) is not dict
                        or type(result.get('serverInfo')) is not dict
                        or type(result['serverInfo'].get('name')) is not str
                        or type(result['serverInfo'].get('version')) is not str):
                    raise StdioFailure('unsupported initialization result')
                self._initialization=copy.deepcopy(result)
                self._requests.pop(ident)
                self._enqueue_locked({'jsonrpc':'2.0','method':'notifications/initialized'},priority=0,
                    kind='initialized',deadline=self._startup_deadline)
            else:
                if len(line)+self._wire_bytes+self._partial_bytes>self._budget.aggregate_bytes:
                    raise StdioFailure('aggregate response budget')
                request.done=True;request.response=value;request.wire_bytes=len(line)
                self._wire_bytes+=len(line)
                self._decoding_bytes=0
            self._trace.append({'direction':'in','id':ident,'bytes':len(line),'sha256':hashlib.sha256(line).hexdigest()})
            self._condition.notify_all()

    def _control_locked(self, value, size):
        now=time.monotonic()
        while self._controls and self._controls[0]<now-1:self._controls.popleft()
        self._controls.append(now);self._control_count+=1
        for request in self._requests.values():
            if not request.done:
                request.controls+=1
                if request.controls>self._budget.controls_per_request:raise StdioFailure('request control budget')
        if (size>self._budget.control_bytes or len(self._controls)>self._budget.control_rate
                or self._control_count>self._budget.controls_per_request*max(1,len(self._ledger))):
            raise StdioFailure('control traffic budget')
        if type(value['method']) is not str or set(value)-{'jsonrpc','id','method','params'}:
            raise StdioFailure('malformed inbound control')
        if value['method']=='notifications/tools/list_changed':raise StdioFailure('fixed discovery changed')
        if 'id' in value:
            if type(value['id']) not in (str,int) or type(value['id']) is str and len(value['id'])>128:
                raise StdioFailure('invalid server request ID')
            response={'jsonrpc':'2.0','id':value['id']}
            response.update({'result':{}} if value['method']=='ping' else {'error':{'code':-32601,'message':'unsupported client method'}})
            self._enqueue_locked(response,priority=0,kind='control',deadline=now+self._budget.write_ms/1000)

    def _drain_stderr(self, stream):
        fd=stream.fileno()
        while True:
            if not select.select([fd],[],[],.02)[0]:continue
            try:part=os.read(fd,16384)
            except BlockingIOError:continue
            if not part:return
            with self._condition:
                self._stderr.extend(part)
                overflow=max(0,len(self._stderr)-self._budget.stderr_bytes)
                if overflow:del self._stderr[:overflow]
                self._stderr_discarded+=overflow

    def _group_exists(self):
        if self._process is None:return False
        try:os.killpg(self._process.pid,0)
        except ProcessLookupError:return False
        return True

    def _retirement_observed(self):
        try:
            self._process.poll()
            return not self._group_exists() and all(done.is_set() for _worker,done,_stream in self._workers)
        except Exception:
            # Observation failure is not evidence of retirement. Keep ownership.
            return False

    def _retire(self):
        process=self._process
        if process is None:
            with self._condition:self._state='CLOSED';self._retired.set();self._condition.notify_all()
            return
        # Close streams whose worker never acquired ownership.
        owned={id(stream) for _thread,_done,stream in self._workers}
        for stream in (process.stdin,process.stdout,process.stderr):
            if id(stream) not in owned:stream.close()
        with self._condition:self._state='CLOSING';self._condition.notify_all()
        for signum,budget in ((None,self._budget.grace_ms),(signal.SIGTERM,self._budget.terminate_ms),(signal.SIGKILL,self._budget.kill_ms)):
            if signum is not None:
                try:os.killpg(process.pid,signum)
                except OSError:pass
            end=time.monotonic()+budget/1000
            while time.monotonic()<end:
                if self._retirement_observed():
                    break
                time.sleep(.01)
            if self._retirement_observed():break
        while not self._retirement_observed():
            with self._condition:self._state='RETIREMENT_UNCONFIRMED';self._condition.notify_all()
            time.sleep(.05)
        for worker,_done,_stream in self._workers:
            if worker.ident is not None:worker.join(.05)
        with self._condition:
            self._queue.clear()
            self._requests.pop(_INIT_ID,None)
            self._state='CLOSED'
            self._retired.set()
            self._condition.notify_all()
