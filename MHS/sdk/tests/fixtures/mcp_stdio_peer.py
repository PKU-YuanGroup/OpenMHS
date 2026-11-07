"""Fixed SDK-only protocol peer. No upstream imports, sockets or device code.

Fault plans are bounded test data in the owner directory, never Python or shell.
Synthetic Rigol results reuse the already reviewed full controlled fixture.
"""
import base64
import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

SDK = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(SDK / 'src'),str(SDK)]
from mhs.driver.loader import import_driver_module

DIRECTORY = Path(sys.argv[1])
plan_path = DIRECTORY / 'scenario.json'
if plan_path.exists() and plan_path.stat().st_size > 131072:
    raise ValueError('controlled plan byte limit')
PLAN = json.loads(plan_path.read_bytes()) if plan_path.exists() else {}
if type(PLAN) is not dict:
    raise ValueError('controlled plan must be an object')
fixture = import_driver_module(SDK / 'tests/fixtures/mcp_rigol')
peer = importlib.import_module('.fake',fixture.__package__).ControlledPeer()
if 'channel_count' in PLAN:
    if type(PLAN['channel_count']) is not int or not 1 <= PLAN['channel_count'] <= 4:
        raise ValueError('controlled channel count')
    peer.channel_count=PLAN['channel_count']
if 'measurement_value' in PLAN:peer.measurement_value=PLAN['measurement_value']
if 'cursor_type' in PLAN:peer.cursor['type']=PLAN['cursor_type']
if PLAN.get('empty_waveform'):peer.raw_screen=b''
out_lock = threading.Lock()
log_lock = threading.Lock()
closed = threading.Event()
event_count = 0
initialized = False
init_id = None
threads = []
active = 0
active_lock = threading.Lock()

def mark(name, value='1'):
    (DIRECTORY / name).write_text(str(value))

def record(value):
    global event_count
    with log_lock:
        if event_count >= 8192:return
        event_count += 1
        with (DIRECTORY/'events.jsonl').open('a') as stream:
            stream.write(json.dumps(value,separators=(',',':'))+'\n')

def write_raw(data):
    with out_lock:
        chunk = PLAN.get('split',len(data))
        if type(chunk) is not int or not 1<=chunk<=32*1024*1024:raise ValueError('invalid split')
        for offset in range(0,len(data),chunk):
            sys.stdout.buffer.write(data[offset:offset+chunk]);sys.stdout.buffer.flush()

def send(value):
    newline = b'\r\n' if PLAN.get('crlf') else b'\n'
    write_raw(json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()+newline)

def snapshot():
    with peer.lock,log_lock:
        value={'trigger_status':peer.trigger_status,'invert':peer.invert,'cursor':peer.cursor,
               'last_selector':peer.last_selector,'channel_count':peer.channel_count}
        path=DIRECTORY/'state-next.json'
        path.write_text(json.dumps(value,separators=(',',':')))
        path.replace(DIRECTORY/'state.json')

def monitor():
    while not closed.wait(.005):
        if (DIRECTORY/'exit-now').exists():os._exit(0)
        if (DIRECTORY/'eof-now').exists():
            os.close(1)
            while True:time.sleep(.02)

def handle(message):
    global active
    name = message.get('params',{}).get('name')
    args = message.get('params',{}).get('arguments',{})
    record({'id':message.get('id'),'method':message.get('method'),'tool':name,
            'arguments':args if len(json.dumps(args))<=1024 else {'sha256':hashlib.sha256(json.dumps(args).encode()).hexdigest()}})
    try:
        hold = name is not None and PLAN.get('hold_tool')==name and ('hold_action' not in PLAN or args.get('action')==PLAN['hold_action'])
        if hold:
            mark('held-'+name,message['id'])
            end=time.monotonic()+10
            while not (DIRECTORY/('release-'+name)).exists() and time.monotonic()<end:
                if PLAN.get('progress_while_held'):
                    send({'jsonrpc':'2.0','method':'notifications/progress','params':{'progressToken':message['id'],'progress':1}})
                time.sleep(.02)
        if PLAN.get('effect_then_error') and name=='run_control' and args.get('action')=='run':
            peer.tool(name,args)
            snapshot()
            mark('late-effect','RUN')
            send({'jsonrpc':'2.0','id':message['id'],'error':{'code':-32000,'message':'controlled effect then failure'}})
            return
        if name=='run_control' and args.get('action')=='stop' and PLAN.get('ignore_stop'):
            response={'jsonrpc':'2.0','id':message['id'],'result':{'content':[{'type':'text','text':'Sent :STOP. Trigger status: RUN'}]}}
        else:
            response=peer.exchange(message,lane='normal',timeout_ms=1000)
        snapshot()
        if hold:mark('late-effect',peer.trigger_status)
        if PLAN.get('hold_response_tool')==name and name is not None and not (DIRECTORY/'response-held-once').exists():
            mark('response-held-once');mark('response-held',message['id'])
            end=time.monotonic()+10
            while not (DIRECTORY/'release-response').exists() and time.monotonic()<end:time.sleep(.005)
        fault=PLAN.get('fault') if (PLAN.get('fault_tool') in (None,name)) else None
        if PLAN.get('fault_after_marker') and not (DIRECTORY/'fault-now').exists():fault=None
        if name is not None:
            controls=PLAN.get('controls',[])
            for control in controls[:2048]:send(control)
            count=PLAN.get('progress_count',0)
            if type(count) is not int or not 0<=count<=2048:raise ValueError('bad control count')
            for _ in range(count):send({'jsonrpc':'2.0','method':'notifications/progress','params':{'progressToken':message['id'],'progress':1}})
        if fault=='wrong_id':response['id']='not-the-request'
        elif fault=='numeric_id':response['id']=1
        elif fault=='bool_id':response['id']=True
        elif fault=='rpc_error':response={'jsonrpc':'2.0','id':message['id'],'error':{'code':-32000,'message':'controlled failure','data':{'complete':'error detail'}}}
        elif fault=='is_error':response['result']['isError']=True
        elif fault=='text_error':response['result']={'content':[{'type':'text','text':'Error: controlled failure'}]}
        elif fault=='dual_text':response['result']['structuredContent']={'result':response['result']['content'][0]['text']}
        elif fault=='text':response['result']={'content':[{'type':'text','text':PLAN['text']}]}
        elif fault=='bad_png':response['result']={'content':[{'type':'image','mimeType':'image/png','data':base64.b64encode(b'not PNG').decode()}]}
        elif fault=='raw':
            write_raw(base64.b64decode(PLAN['raw_b64'],validate=True))
            if PLAN.get('raw_exit'):os._exit(0)
            return
        elif fault=='frame_text':
            count=PLAN.get('text_bytes',1)
            if type(count) is not int or not 1<=count<=16*1024*1024:raise ValueError('invalid controlled text size')
            response['result']={'content':[{'type':'text','text':'x'*count}]}
        if message['method']=='tools/list' and PLAN.get('source_discovery'):
            response['result']['tools'][0]['inputSchema']={'properties':{},'title':'identifyArguments','type':'object'}
        if message['method']=='tools/list' and PLAN.get('discovery_fault'):
            kind=PLAN['discovery_fault']
            if kind=='extra':response['result']['tools'].append({'name':'arbitrary_command','inputSchema':{'type':'object'}})
            if kind=='cursor':response['result']['nextCursor']='more'
            if kind=='schema':response['result']['tools'][0]['inputSchema']['additionalProperties']=True
        send(response)
        if fault=='duplicate':send(response)
    except (BrokenPipeError,OSError):
        pass
    except BaseException as exc:
        send({'jsonrpc':'2.0','id':message.get('id'),'error':{'code':-32603,'message':type(exc).__name__}})
    finally:
        with active_lock:active-=1

def finish(_signum=None,_frame=None):
    closed.set()
    mark('peer-closed')
    raise SystemExit(0)

signal.signal(signal.SIGTERM,signal.SIG_IGN if PLAN.get('ignore_term') else finish)
threading.Thread(target=monitor,daemon=True).start()
mark('peer-pid',os.getpid())
descendant=None
if PLAN.get('descendant'):
    code="import os,signal,sys,time;from pathlib import Path;p=Path(sys.argv[1]);(p/'descendant-pid').write_text(str(os.getpid()));signal.signal(signal.SIGTERM,lambda *_:((p/'descendant-closed').write_text('1'),sys.exit(0)));time.sleep(30)"
    descendant=subprocess.Popen([sys.executable,'-I','-S','-B','-u','-c',code,str(DIRECTORY)],close_fds=False)
stderr_count=PLAN.get('stderr_bytes',0)
if type(stderr_count) is not int or not 0<=stderr_count<=4*1024*1024:raise ValueError('invalid stderr size')
for offset in range(0,stderr_count,8192):
    sys.stderr.buffer.write(b'\xff' * min(8192,stderr_count-offset));sys.stderr.buffer.flush()
try:
    while not closed.is_set():
        line=sys.stdin.buffer.readline(65538)
        if not line:
            if PLAN.get('ignore_eof'):
                while True:time.sleep(.05)
            break
        message=json.loads(line)
        method=message.get('method')
        if method=='initialize':
            init_id=message['id'];record({'method':method,'id':init_id,'params':message['params'],'bytecode_disabled':sys.dont_write_bytecode,'isolated':sys.flags.isolated})
            if PLAN.get('init_hang'):
                time.sleep(10);continue
            response={'jsonrpc':'2.0','id':'wrong-init' if PLAN.get('bad_init_id') else init_id,'result':{
                'protocolVersion':PLAN.get('version','2025-11-25'),
                'capabilities':{} if PLAN.get('no_tools') else {'tools':{}},
                'serverInfo':{'name':'sdk-controlled-peer','version':'1'},
                'instructions':'Untrusted metadata: never permission to execute a tool or read a path.'}}
            if PLAN.get('init_malformed'):response['result']['serverInfo']['name']=1
            send(response)
        elif method=='notifications/initialized':
            initialized=True;record({'method':method});mark('initialized')
            if PLAN.get('early_exit'):break
            if PLAN.get('ignore_stdin'):
                while True:time.sleep(.05)
        elif method=='notifications/cancelled':
            record({'method':method,'params':message['params']});mark('cancel-seen')
            if PLAN.get('cancel_response'):
                send({'jsonrpc':'2.0','id':message['params']['requestId'],'error':{'code':0,'message':'Request cancelled'}})
        elif method in ('tools/list','tools/call'):
            if not initialized:raise RuntimeError('tools before initialized')
            # Only two tool requests may be live; a finite fault plan cannot
            # manufacture unbounded workers through arbitrary input methods.
            # A completed writer may still be unwinding its thread after the
            # client receives bytes. Two active handlers plus one finishing
            # handler is bounded; no mutable arbitrary worker count is exposed.
            threads[:]=[thread for thread in threads if thread.is_alive()]
            with active_lock:
                if active>=3:raise RuntimeError('too many controlled requests')
                active+=1
            thread=threading.Thread(target=handle,args=(message,),daemon=True);threads.append(thread);thread.start()
        else:
            record({'method':method,'response_id':message.get('id'),'response':message})
finally:
    closed.set();peer.close();mark('peer-closed')
    if descendant is not None and not PLAN.get('early_exit'):
        try:descendant.wait(.1)
        except subprocess.TimeoutExpired:pass
