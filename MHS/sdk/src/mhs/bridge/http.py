"""Finite HTTP run workflows over an injected, bounded response interface.

There is deliberately no native network factory in this version. The pinned
OT2 client proves request shapes, not remote retirement or protocol safety.
The controlled fake can settle its own requests; physical stopping is never
inferred from a response, socket close, local flag or expired caller deadline.
"""
from __future__ import annotations

import base64
import copy
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
import time
import uuid

from .base import Bridge, BridgeContext, busy, driver_failed, make_mhs_error, outcome_unknown, unsupported
from .. import signals
from ..artifacts import publisher_from_context
from ..driver.http_config import (compile_http, encoded, plain, MAX_HEADERS, _SEGMENT,
                                  OT2_CLIENT_PATH, OT2_CLIENT_SHA256, OT2_CLIENT_COMMIT)

_TERMINAL = frozenset({'succeeded', 'failed', 'stopped'})
_STATES = frozenset({'idle', 'running', 'finishing', 'succeeded', 'failed', 'paused', 'stop-requested', 'stopped'})
_EFFECTS = frozenset({'upload', 'create', 'play', 'pause', 'resume', 'stop'})


def native_unavailable(**_options):
    raise RuntimeError('HTTP native admission blocked: server retirement and protocol effect-envelope evidence are unresolved')


def _context(ctx, maximum):
    context = BridgeContext.coerce(ctx)
    deadline = min(time.monotonic() + maximum / 1000,
                   (context.extra or {}).get('deadline_at', time.monotonic() + context.remaining_ms() / 1000))
    return BridgeContext.coerce({**context.__dict__, 'extra': {**context.extra, 'deadline_at': deadline}})


def _get(value, path):
    for part in path.split('.'):
        if type(value) is not dict or part not in value:
            raise ValueError('required response field is missing')
        value = value[part]
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _bad_number(value):
    raise ValueError('non-finite JSON number')


@dataclass
class _Exchange:
    ident: str
    role: str
    lane: str
    job: dict | None
    effectful: bool
    event: threading.Event = field(default_factory=threading.Event)
    result: dict | None = None
    error: BaseException | None = None
    abandoned: bool = False


class HttpBridge(Bridge):
    bridge_kind = 'http'
    bridge_id = 'mhs.bridge.http'

    def __init__(self, config, *, transport=None, device_id=None, resource_id='main', base_dir=None, validation=False):
        super().__init__(device_id=device_id)
        config = copy.deepcopy(config)
        commands, reads = config.pop('commands', {}), config.pop('reads', {})
        self.config = compile_http(config, commands, reads)
        if transport is None and not validation:
            native_unavailable()
        if self.config.get('auth_ref') is not None and not validation:
            raise ValueError('HTTP credential policy resolution is not implemented; no request is admitted')
        self._config = copy.deepcopy(self.config)
        self._transport = transport
        self._resource_id = resource_id
        self._base_dir = Path(base_dir or '.').resolve()
        self._condition = threading.Condition(threading.RLock())
        self._safety_lane = threading.Lock()
        self._pending = {}
        self._job = None
        self._running = False
        self._latched = False
        self._debt = False
        self._safe = False
        self._safe_epoch = -1
        self._close_started = False
        self._close_done = threading.Event()
        self._close_error = None
        self._close_start_error = None
        self.trace = []
        self._sequence = 0
        # A stop proof cannot retire a normal request that was pending when
        # its observations began, or that completed while they were in flight.
        # Completion increments this even when a response is lost or invalid.
        self._normal_generation = 0

    @property
    def estop_native(self):
        return 'POST /runs/{run_id}/actions:stop'

    def _route(self, role):
        return self._config['routes'][self._config['workflow'][role]]

    def _template(self, value, job):
        if type(value) is dict:
            if set(value) == {'$job'}:
                result = (job or {}).get(value['$job'])
                if type(result) is not str or not _SEGMENT.fullmatch(result) or result in ('.', '..'):
                    raise ValueError('owned job has no valid remote identifier')
                return result
            return {key: self._template(item, job) for key, item in value.items()}
        if type(value) is list:
            return [self._template(item, job) for item in value]
        return value

    def _artifact(self, name):
        if type(name) is not str or name not in self._config['artifacts']:
            raise make_mhs_error('MHS.RESOURCE.SCHEMA_INVALID', 'unknown explicit protocol artifact')
        spec = self._config['artifacts'][name]
        path = self._base_dir / spec['path']
        handles = []
        try:
            if not all(hasattr(os, name) for name in ('O_NOFOLLOW', 'O_DIRECTORY', 'O_NONBLOCK')):
                raise ValueError('confined artifact reads require no-follow directory handles')
            directory = os.open(self._base_dir, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY)
            handles.append(directory)
            for part in Path(spec['path']).parts[:-1]:
                directory = os.open(part, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY, dir_fd=directory)
                handles.append(directory)
            # Check the opened object, not a raceable pre-open pathname. A FIFO
            # or device must not block on open before fstat can reject it.
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= spec['max_bytes']:
                    raise ValueError('artifact is not a bounded regular file')
                data = stream.read(spec['max_bytes'] + 1)
            if len(data) > spec['max_bytes'] or hashlib.sha256(data).hexdigest() != spec['sha256']:
                raise ValueError('artifact digest/size mismatch')
        except (OSError, ValueError) as exc:
            raise make_mhs_error('MHS.RESOURCE.SCHEMA_INVALID', 'protocol artifact integrity check failed') from exc
        finally:
            for handle in reversed(handles):
                os.close(handle)
        return {'field': 'files', 'filename': spec.get('filename', path.name), 'sha256': spec['sha256'],
                'size_bytes': len(data), 'data_base64': base64.b64encode(data).decode('ascii')}

    def _response(self, raw, message, spec, job):
        if type(raw) is not dict or set(raw) != {'request_id', 'status', 'headers', 'body'}:
            raise ValueError('invalid HTTP response envelope')
        if raw['request_id'] != message['request_id'] or type(raw['request_id']) is not str:
            raise ValueError('response request identity mismatch')
        if type(raw['status']) is not int or raw['status'] not in spec['response']['status']:
            raise ValueError('unaccepted HTTP response status; redirects are never followed')
        headers = raw['headers']
        if (type(headers) is not dict or any(type(k) is not str or type(v) is not str for k, v in headers.items())
                or len(encoded(headers)) > MAX_HEADERS or len({k.lower() for k in headers}) != len(headers)
                or any('\r' in k + v or '\n' in k + v for k, v in headers.items())):
            raise ValueError('invalid or excessive HTTP response headers')
        lowered = {key.lower(): value for key, value in headers.items()}
        if lowered.get('content-type', '').lower() not in ('application/json', 'application/json; charset=utf-8'):
            raise ValueError('unsupported response content type')
        if lowered.get('content-encoding', 'identity') != 'identity':
            raise ValueError('compressed responses are outside this finite profile')
        body = raw['body']
        if type(body) is not str or not 0 < len(body) <= self._config['max_body_bytes']:
            raise ValueError('invalid response body')
        data = body.encode('utf-8')
        if len(data) > self._config['max_body_bytes']:
            raise ValueError('response body exceeds byte limit')
        result = json.loads(body, object_pairs_hook=_pairs, parse_constant=_bad_number)
        plain(result)
        if type(result) is not dict or result.get('errors') or result.get('error'):
            raise ValueError('response reports an application error or is not an object')
        types = {'string': str, 'boolean': bool, 'integer': int, 'object': dict, 'array': list}
        for path, kind in spec['response']['required'].items():
            value = _get(result, path)
            if (kind == 'number' and type(value) not in (int, float)) or (kind != 'number' and type(value) is not types[kind]):
                raise ValueError('response field type mismatch')
        for path, key in spec['response'].get('correlation', {}).items():
            value = _get(result, path)
            if type(value) is not str or value != (job or {}).get(key):
                raise ValueError('response does not identify the owned job')
        return result, hashlib.sha256(data).hexdigest()

    def _accept(self, exchange, result):
        job = exchange.job
        if job is None:
            return
        if self._job is not job:
            raise ValueError('response belongs to a retired local job')
        if exchange.role in ('upload', 'create'):
            value = _get(result, 'data.id')
            if type(value) is not str or not _SEGMENT.fullmatch(value) or value in ('.', '..'):
                raise ValueError('invalid returned job identifier')
            key = 'protocol_id' if exchange.role == 'upload' else 'run_id'
            if job.get(key) not in (None, value):
                raise ValueError('remote identifier changed within a job')
            job[key] = value
        elif exchange.role == 'status':
            value = _get(result, 'data.status')
            if value not in _STATES:
                raise ValueError('unknown run state')
            if job['settled'] and value not in _TERMINAL:
                # A fresh active observation revokes the earlier retirement,
                # including after reset released the local latch. Keep that
                # owned run; a new workflow must not replace it.
                job['settled'] = False
                self._debt = True
            job['status'] = value
            if value != 'stopped':
                self._safe = False
                if self._latched:
                    self._debt = True

    def _exchange(self, role, context, epoch, *, protective=False, artifact=None, job=None, workflow_poll=False):
        deadline = min(context.extra['deadline_at'], time.monotonic() + self._config['request_timeout_ms'] / 1000)
        spec = self._route(role)
        lane = 'protective' if protective else 'normal'
        with self._condition:
            self.ensure_open()
            if workflow_poll and self._latched:
                # A run observer yields to the independent stop transaction.
                # It cannot enqueue a new normal poll while settlement is being
                # checked, or call itself cancelled before settlement is known.
                while job is not None and not job['settled'] and time.monotonic() < deadline and not self.closed:
                    self._condition.wait(min(.01, max(0, deadline - time.monotonic())))
                if job is not None and job['settled'] and job['status'] == 'stopped':
                    raise signals.Cancelled('controlled HTTP run settled after stop')
                raise outcome_unknown('HTTP stop has not settled the owned run')
            if time.monotonic() >= deadline:
                raise outcome_unknown('HTTP request has no remaining time budget')
            if not protective and context.cancelled():
                raise signals.Cancelled('HTTP operation cancelled before request dispatch')
            if not protective and role in _EFFECTS and (self._latched or epoch != self.estop_epoch):
                raise make_mhs_error('MHS.SAFETY.ESTOP_ENGAGED', 'HTTP effect admission is latched')
            while any(item.lane == lane for item in self._pending.values()):
                if any(item.lane == lane and item.abandoned for item in self._pending.values()):
                    raise busy('HTTP request lane retains an abandoned operation')
                if time.monotonic() >= deadline:
                    raise busy('HTTP request lane did not become available within its budget')
                if not protective and (context.cancelled() or self._latched or epoch != self.estop_epoch):
                    raise signals.Cancelled('HTTP request cancelled while waiting for its lane')
                self._condition.wait(min(.01, max(0, deadline - time.monotonic())))
                self.ensure_open()
            job = self._job if job is None else job
            if job is not self._job:
                raise busy('HTTP request belongs to a retired local job')
            if not protective and role in _EFFECTS and (self._latched or epoch != self.estop_epoch):
                raise make_mhs_error('MHS.SAFETY.ESTOP_ENGAGED', 'HTTP effect admission is latched')
            path = spec['path']
            for name in ('run_id', 'protocol_id'):
                if '{' + name + '}' in path:
                    path = path.replace('{' + name + '}', self._template({'$job': name}, job))
            ident = uuid.uuid4().hex
            message = {'format': 'mhs-http-request-v1', 'request_id': ident, 'origin': self._config['origin'],
                       'method': spec['method'], 'path': path, 'headers': copy.deepcopy(self._config['headers']),
                       'query': self._template(spec.get('query', {}), job)}
            if 'json' in spec:
                message['json'] = self._template(spec['json'], job)
            if 'multipart' in spec:
                if artifact is None:
                    raise ValueError('upload requires a prevalidated artifact')
                message['multipart'] = artifact
            if len(encoded(message)) > self._config['max_body_bytes']:
                raise make_mhs_error('MHS.RESOURCE.SCHEMA_INVALID', 'request exceeds configured size')
            exchange = _Exchange(ident, role, lane, job, role in _EFFECTS)
            self._sequence += 1
            sequence, started_ns = self._sequence, time.monotonic_ns()
            self._pending[ident] = exchange
            if lane == 'normal':
                self._normal_generation += 1
            if exchange.effectful:
                self._safe = False

            def execute():
                try:
                    raw = self._transport.request(copy.deepcopy(message), timeout_ms=max(1, int((deadline - time.monotonic()) * 1000)))
                    result, digest = self._response(raw, message, spec, job)
                    with self._condition:
                        self._accept(exchange, result)
                        exchange.result = result
                        # Bounded, content-addressed evidence; no protocol bytes,
                        # body text, opaque auth references or errors are logged.
                        self.trace.append({'request_id': ident, 'role': role, 'method': spec['method'], 'path': path,
                                           'profile': self._config['profile'], 'origin': self._config['origin'],
                                           'source_ref': spec['source_ref'], 'sequence': sequence,
                                           'started_monotonic_ns': started_ns, 'ended_monotonic_ns': time.monotonic_ns(),
                                           'generation': (job or {}).get('generation'),
                                           'request_sha256': hashlib.sha256(encoded(message)).hexdigest(),
                                           'response_sha256': digest, 'status': raw['status']})
                        self.trace[:] = self.trace[-128:]
                except BaseException as exc:
                    with self._condition:
                        exchange.error = exc
                        if exchange.effectful:
                            self._debt = True
                finally:
                    with self._condition:
                        self._pending.pop(ident, None)
                        if lane == 'normal':
                            self._normal_generation += 1
                        exchange.event.set()
                        self._condition.notify_all()
                        self._maybe_close_locked()

            # Registration is the dispatch linearization point. An already
            # registered request stays owned across e-stop, even if its worker
            # has not yet reached the transport. It prevents early settlement.
            worker = threading.Thread(target=execute, name='mhs-http-' + lane, daemon=True)
            try:
                worker.start()
            except BaseException as exc:
                if worker.ident is None:
                    # The standard Thread never started: no worker can retire
                    # this registration and no request was handed to the peer.
                    self._pending.pop(ident, None)
                    if lane == 'normal':
                        self._normal_generation += 1
                    exchange.error = exc
                    exchange.event.set()
                    self._condition.notify_all()
                    self._maybe_close_locked()
                    raise driver_failed('MHS.DEVICE.NOT_READY', 'HTTP worker could not start') from exc
                # start() may raise after a real start (for example an injected
                # wrapper failure). Preserve that worker's ownership until its
                # finally block returns the request, including after close.
                exchange.abandoned = True
                self._debt = True
                self._safe = False
                raise outcome_unknown('HTTP worker started but startup acknowledgement failed') from exc
        while not exchange.event.wait(min(.01, max(0, deadline - time.monotonic()))):
            if time.monotonic() >= deadline or (not protective and context.cancelled()):
                with self._condition:
                    exchange.abandoned = True
                    if exchange.effectful or (job is not None and not job.get('settled')):
                        self._debt = True
                    self._safe = False
                raise outcome_unknown('HTTP request is retained after caller timeout/cancellation')
        if exchange.error is not None:
            if exchange.effectful:
                raise outcome_unknown('HTTP effect response is unconfirmed') from exchange.error
            raise driver_failed('MHS.CAPABILITY.OUTPUT_INVALID', 'HTTP observation response is invalid') from exchange.error
        return exchange.result

    def _fresh(self, context, epoch, *, protective=False, job=None, workflow_poll=False):
        with self._condition:
            job = self._job if job is None else job
        if job is None or job.get('run_id') is None:
            return None
        return self._exchange('status', context, epoch, protective=protective, job=job, workflow_poll=workflow_poll)

    def _run(self, args, context):
        if set(args) != {'protocol'}:
            raise make_mhs_error('MHS.RESOURCE.SCHEMA_INVALID', 'run requires only the explicit protocol artifact name')
        artifact = self._artifact(args['protocol'])
        with self._condition:
            if self._latched or self._debt:
                raise make_mhs_error('MHS.SAFETY.ESTOP_ENGAGED', 'unresolved HTTP ownership blocks a new run')
            if self._running or self._pending or (self._job is not None and not self._job['settled']):
                raise busy('an earlier HTTP job still owns the device')
            epoch = self.estop_epoch
            job = {'run_id': None, 'protocol_id': None, 'status': 'idle', 'settled': False,
                   'artifact_sha256': artifact['sha256'], 'generation': uuid.uuid4().hex}
            self._job = job
            self._running = True
        try:
            self._exchange('upload', context, epoch, artifact=artifact, job=job)
            self._exchange('create', context, epoch, job=job)
            self._exchange('play', context, epoch, job=job)
            for _ in range(self._config['max_polls']):
                with self._condition:
                    if job['settled'] and job['status'] == 'stopped':
                        raise signals.Cancelled('controlled HTTP run is remotely settled after stop')
                if context.cancelled() or context.remaining_ms() <= 0:
                    raise outcome_unknown('HTTP run wait ended before remote retirement')
                result = self._fresh(context, epoch, job=job, workflow_poll=True)
                status = _get(result, 'data.status')
                if status in _TERMINAL:
                    with self._condition:
                        if self._latched:
                            stop_deadline = min(context.extra['deadline_at'], time.monotonic() + self._config['request_timeout_ms']/1000)
                            while not job['settled'] and time.monotonic() < stop_deadline and not self.closed:
                                self._condition.wait(min(.01,max(0,stop_deadline-time.monotonic())))
                            if job['settled'] and job['status'] == 'stopped':
                                raise signals.Cancelled('controlled HTTP run settled after stop')
                        if self._debt or self._pending or self._latched or epoch != self.estop_epoch:
                            raise outcome_unknown('HTTP terminal observation cannot retire earlier uncertain effects')
                        job['settled'] = True
                    if status == 'succeeded':
                        return {'run_id': job['run_id'], 'protocol_id': job['protocol_id'], 'status': status}
                    if status == 'stopped':
                        raise signals.Cancelled('controlled HTTP run stopped')
                    raise driver_failed('MHS.DEVICE.FAULT', 'HTTP run failed')
                with self._condition:
                    self._condition.wait(min(self._config['poll_ms'] / 1000, max(0, context.remaining_ms() / 1000)))
            raise outcome_unknown('HTTP run exceeded its finite poll budget')
        except BaseException as exc:
            if context.cancelled():
                # operations.cancel only sets the caller's cancellation event.
                # Retire the owned run through the same independent stop lane;
                # the event is not itself evidence of remote cancellation.
                with self._condition:
                    retired = (self._job is job and job['settled'] and job['status'] == 'stopped'
                               and self._safe and not self._debt and not self._pending and not self.closed)
                if not retired:
                    stopped = self._stop(_context(context, self._config['request_timeout_ms'] * 2), engage=True)
                    retired = bool(stopped['safe_state_achieved'])
                if retired:
                    raise signals.Cancelled('controlled HTTP run retired after operation cancellation') from exc
                with self._condition:
                    self._debt = True
                    self._safe = False
                raise outcome_unknown('HTTP operation cancellation did not retire the owned run') from exc
            with self._condition:
                if not job['settled']:
                    self._debt = True
                    self._safe = False
            raise
        finally:
            with self._condition:
                self._running = False
                self._condition.notify_all()

    def call(self, capability_id, args=None, ctx=None):
        self.ensure_open()
        spec = self._config['commands'].get(capability_id)
        if spec is None:
            raise unsupported(capability_id)
        args = {} if args is None else args
        if type(args) is not dict:
            raise make_mhs_error('MHS.RESOURCE.SCHEMA_INVALID', 'HTTP input must be an object')
        context = _context(ctx, self._config['workflow_timeout_ms'])
        operation = spec['operation']
        if operation == 'run':
            return self._run(args, context)
        if args:
            raise make_mhs_error('MHS.RESOURCE.SCHEMA_INVALID', 'this HTTP control accepts no arbitrary input')
        if operation == 'cancel':
            result = self._stop(context, engage=True)
            if not result['safe_state_achieved']:
                raise driver_failed('MHS.SAFETY.SAFE_STATE_UNREACHED', 'HTTP stop is not settled')
            return {'stopped': True, 'run_id': (self._job or {}).get('run_id') or ''}
        with self._condition:
            epoch = self.estop_epoch
            job = self._job
        if operation in ('pause', 'resume'):
            with self._condition:
                if self._debt or self._job is None or self._job['settled']:
                    raise busy('there is no confirmed active run to control')
            self._exchange(operation, context, epoch, job=job)
            result = self._fresh(context, epoch, job=job)
            expected = 'paused' if operation == 'pause' else 'running'
            if _get(result, 'data.status') != expected:
                with self._condition:
                    self._debt = True
                raise outcome_unknown('HTTP control acknowledgement did not reach its expected run state')
            return {'run_id': job['run_id'], 'status': expected}
        if operation == 'list':
            return {'runs': _get(self._exchange('list', context, epoch), 'data')}
        if operation in ('inspect', 'logs'):
            result = self._fresh(context, epoch, job=job)
            if result is None:
                raise driver_failed('MHS.DEVICE.NOT_READY', 'there is no owned run')
            if operation == 'inspect':
                return {'run_id': job['run_id'], 'status': _get(result, 'data.status')}
            publisher = publisher_from_context(context)
            if publisher is None:
                raise driver_failed('MHS.CAPABILITY.NOT_BOUND', 'HTTP logs require the endpoint artifact store')
            commands = self._exchange('commands', context, epoch, job=job)
            document = {'profile': self._config['profile'], 'run_id': job['run_id'],
                        'protocol_id': job['protocol_id'], 'protocol_sha256': job['artifact_sha256'],
                        'coverage': 'first_command_page', 'complete': False, 'run': result, 'commands': commands}
            with self._condition:
                document['evidence'] = copy.deepcopy([item for item in self.trace if item['generation'] == job['generation']])
            document['evidence_coverage'] = 'most_recent_128_validated_responses'
            document['request_profile_source'] = {'commit': OT2_CLIENT_COMMIT, 'path': OT2_CLIENT_PATH,
                                                  'sha256': OT2_CLIENT_SHA256, 'executed': False}
            data = encoded(document)
            if len(data) > publisher.max_bytes:
                raise driver_failed('MHS.CAPABILITY.OUTPUT_INVALID', 'HTTP log exceeds artifact limit')
            self._refuse_if_estopped(epoch, 'HTTP log publication')
            with self._condition:
                if self._job is not job:
                    raise busy('HTTP job changed before log publication')
                self.ensure_open()
            descriptor = publisher.publish(data, 'application/json', output_field='artifact_ref')
            try:
                self.ensure_open()
                self._refuse_if_estopped(epoch, 'HTTP log publication')
                with self._condition:
                    if self._job is not job:
                        raise busy('HTTP job changed during log publication')
            except BaseException:
                publisher.abort()
                raise
            return {'artifact_ref': descriptor['uri'], 'run_id': job['run_id'],
                    'media_type': 'application/json', 'complete': False}
        raise unsupported(capability_id)

    def read(self, resource_id, fields=None, ctx=None):
        self.ensure_open()
        if resource_id != self._resource_id:
            raise unsupported(resource_id, 'resource')
        declared = self._config['reads']
        selected = list(declared) if fields is None else list(fields)
        if any(name not in declared for name in selected):
            raise unsupported(resource_id, 'field')
        if any(declared[name]['state'] == 'status' for name in selected):
            self._fresh(_context(ctx, self._config['request_timeout_ms']), self.estop_epoch)
        with self._condition:
            job = self._job or {}
            state = {'status': job.get('status', 'idle'), 'run_id': job.get('run_id') or '',
                     'protocol_id': job.get('protocol_id') or '', 'pending': len(self._pending),
                     'safe': self._safe and not self._debt and not self._pending and not self.closed}
            return {name: state[declared[name]['state']] for name in selected}

    def _stop(self, context, *, engage):
        with self._condition:
            if engage:
                self._engage_estop()
                self._latched = True
            epoch = self.estop_epoch
            self._safe = False
            self._condition.notify_all()
        performed = False
        achieved = False
        if not self._safety_lane.acquire(timeout=max(0, context.remaining_ms() / 1000)):
            return {'performed': False, 'native': self.estop_native, 'safe_state_achieved': False}
        try:
            with self._condition:
                job = self._job
                if job is None:
                    # An empty local owner record is not evidence that the
                    # remote device is idle, and supplies no native stop ID.
                    return {'performed': False, 'native': self.estop_native, 'safe_state_achieved': False}
                elif job.get('run_id') is None:
                    return {'performed': False, 'native': self.estop_native, 'safe_state_achieved': False}
            # At most one protective retry. Upload/create/play/resume are
            # never replayed. A changed generation or an older pending normal
            # request makes the entire observation pair obsolete, even if its
            # worker returns before final delivery of a stopped list response.
            for _attempt in range(2):
                with self._condition:
                    normal_pending = any(item.lane == 'normal' for item in self._pending.values())
                    generation = self._normal_generation
                performed = True
                self._exchange('stop', context, epoch, protective=True, job=job)
                with self._condition:
                    # Allow an already completing observation to release its
                    # slot, with a small fixed bound. A retained effect never
                    # becomes settled just because this wait expires.
                    self._condition.wait_for(lambda:not self._pending,
                                             timeout=min(.02, max(0, context.remaining_ms()/1000)))
                result = self._fresh(context, epoch, protective=True)
                listed = self._exchange('list', context, epoch, protective=True, job=job)
                rows = _get(listed, 'data')
                ids = set()
                scope_clear = type(rows) is list
                for row in rows:
                    if (type(row) is not dict or type(row.get('id')) is not str or row['id'] in ids
                            or row.get('status') not in _TERMINAL):
                        scope_clear = False
                        break
                    ids.add(row['id'])
                    if row['id'] == job['run_id'] and row['status'] != 'stopped':
                        scope_clear = False
                # This additional finite negative check detects foreign active
                # jobs in the controlled peer. It is not proof of complete
                # pagination, exclusive deployment control or physical quiet.
                scope_clear = scope_clear and job['run_id'] in ids
                with self._condition:
                    achieved = (self._job is job and _get(result, 'data.status') == 'stopped'
                                and scope_clear and not normal_pending and generation == self._normal_generation
                                and not self._pending and epoch == self.estop_epoch and not self.closed)
                    if achieved:
                        # Proof validation and commitment share one critical
                        # section. Any observation after its release revokes
                        # this state normally and is never overwritten later.
                        self._debt = False
                        self._safe = True
                        self._safe_epoch = epoch
                        job['settled'] = True
                        self._condition.notify_all()
                    if achieved or self.closed or epoch != self.estop_epoch or context.remaining_ms() <= 0:
                        break
                    # An unresolved worker cannot be retried away. If it is
                    # still pending, keep the attempted stop and return false.
                    # If it retired during this attempt, the one retry issues
                    # a new stop and new observations after its settlement.
                    if self._pending:
                        break
        except Exception:
            with self._condition:
                self._debt = True
        finally:
            self._safety_lane.release()
        return {'performed': performed, 'native': self.estop_native, 'safe_state_achieved': achieved}

    def estop(self, reason='', ctx=None):
        result = self._stop(_context(ctx, self._config['request_timeout_ms'] * 2), engage=True)
        if result['performed']:
            result['estop'] = 'engaged'
        return result

    def safe_state(self, ctx=None):
        result = self.estop(ctx=ctx)
        return {'achieved': result['safe_state_achieved'], 'native': result['native']}

    def reset(self, ctx=None):
        with self._condition:
            job = self._job
            if (self.closed or self._pending or self._running or self._debt or not self._safe
                    or job is None or not job['settled'] or job['status'] != 'stopped'
                    or self._safe_epoch != self.estop_epoch):
                raise make_mhs_error('MHS.SAFETY.SAFE_STATE_UNREACHED', 'HTTP ownership is not settled')
            epoch = self.estop_epoch
        result = self._stop(_context(ctx, self._config['request_timeout_ms'] * 2), engage=False)
        with self._condition:
            if (not result['safe_state_achieved'] or epoch != self.estop_epoch or self._safe_epoch != epoch
                    or self._job is not job or not job['settled'] or job['status'] != 'stopped'
                    or self.closed or self._pending or self._running or self._debt or not self._safe):
                raise make_mhs_error('MHS.SAFETY.SAFE_STATE_UNREACHED', 'HTTP reset lost its fresh settlement')
            self._latched = False
        return {'reset': True}

    def safety_status(self):
        with self._condition:
            achieved = (self._safe and not self._debt and not self._pending and not self.closed
                        and self._safe_epoch == self.estop_epoch)
            return {'estop': {'native': self.estop_native}, 'safe_state': {'achieved': achieved},
                    'pending_http': len(self._pending), 'remote_uncertain': self._debt}

    def _maybe_close_locked(self):
        if not self.closed or self._pending or self._close_started:
            return
        self._close_started = True
        if not self._config['owned_transport'] or self._transport is None:
            self._close_done.set()
            return
        def cleanup():
            try:
                close = getattr(self._transport, 'close', None)
                if callable(close):
                    close()
            except BaseException as exc:
                self._close_error = type(exc).__name__
            finally:
                self._close_done.set()
        worker = threading.Thread(target=cleanup, name='mhs-http-close', daemon=True)
        try:
            worker.start()
        except BaseException as exc:
            self._close_start_error = type(exc).__name__
            # A later explicit close may retry only if no thread ever started.
            # A partially acknowledged real start still owns the one cleanup
            # attempt, even if peer.close has not returned yet.
            if worker.ident is None:
                self._close_started = False

    def close(self):
        with self._condition:
            self._closed = True
            self._latched = True
            self._safe = False
            if self._job is not None and not self._job['settled']:
                self._debt = True
            self._condition.notify_all()
            self._maybe_close_locked()
