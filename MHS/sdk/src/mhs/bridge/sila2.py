"""Retained SiLA controlled-peer contract, not a native wire adapter.

All real runtime profiles remain refused. A local response deadline, execution
lifetime, cancelled subscription or unary Stop acknowledgement is never a
physical retirement proof. The additional observe operation below belongs to
the explicit controlled peer contract, not to a fabricated SiLA endpoint.
"""
from __future__ import annotations

import copy
import hashlib
import threading
import time
import uuid
from dataclasses import dataclass, field

from .. import signals
from ..artifacts import publisher_from_context
from ..driver.sila2_config import (PEER_FORMAT, compile_sila2, canonical, fingerprint, keys,
                                   integer, plain, validate, validate_fields, input_values)
from .base import Bridge, BridgeContext, busy, driver_failed, make_mhs_error, outcome_unknown, unsupported

_OWNERS_LOCK = threading.Lock()
_OWNERS = {}
_FRAMEWORK_ERRORS = frozenset({'COMMAND_EXECUTION_NOT_ACCEPTED', 'INVALID_COMMAND_EXECUTION_UUID',
                               'COMMAND_EXECUTION_NOT_FINISHED', 'INVALID_METADATA', 'NO_METADATA_ALLOWED'})


def native_unavailable(**_options):
    raise RuntimeError('SiLA native admission refused: runtime, ownership, device retirement and license blockers remain open')


def _uuid(value):
    if type(value) is not str or len(value) != 36 or str(uuid.UUID(value)) != value:
        raise ValueError('canonical UUID required')
    return value


class PeerLease:
    """Own a controlled peer before its factory initializes or returns it.

    A fake factory must call lease.register(peer) before performing setup.
    This does not authorize arbitrary native construction or runtime imports.
    """
    def __init__(self, factory=None, options=None, peer=None):
        self.factory, self.options = factory, copy.deepcopy(options or {})
        self.peer = None
        self.started = False
        self.closed = False
        self.error = None
        if peer is not None:
            self.register(peer)
            self.started = True

    def register(self, peer):
        with _OWNERS_LOCK:
            if self.peer is not None or self.closed or id(peer) in _OWNERS:
                raise ValueError('peer already owned or lease closed')
            self.peer = peer
            _OWNERS[id(peer)] = (peer, self)

    def request(self, message, *, timeout_ms):
        if self.closed:
            raise RuntimeError('controlled peer lease closed')
        if not self.started:
            # One ordinary construction owner exists in Sila2Bridge. The
            # protective lane cannot start a second construction attempt.
            self.started = True
            if self.factory is None:
                raise RuntimeError('explicit controlled factory required')
            try:
                returned = self.factory(self, **copy.deepcopy(self.options))
            except BaseException:
                self.error = 'factory failed after entering construction'
                raise
            if returned is not self.peer or self.peer is None:
                self.error = 'factory did not return its registered peer'
                raise RuntimeError(self.error)
        if self.error is not None or self.peer is None:
            raise RuntimeError('controlled construction remains unresolved')
        return self.peer.request(message, timeout_ms=timeout_ms)

    def close(self):
        self.closed = True
        if self.peer is not None:
            self.peer.close()
            with _OWNERS_LOCK:
                owned = _OWNERS.get(id(self.peer))
                if owned is not None and owned[1] is self:
                    _OWNERS.pop(id(self.peer))


@dataclass
class _Work:
    ident: str
    lane: str
    deadline: float
    effectful: bool = False
    member: str | None = None
    epoch: int = 0
    event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    result: object = None
    error: BaseException | None = None
    abandoned: bool = False
    done_at: float | None = None
    rpc_deadline: float | None = None
    execution_uuid: str | None = None
    terminal: int | None = None
    terminal_packet: bytes | None = None
    retired: bool = False
    dispatched: bool = False
    streams: dict = field(default_factory=dict)
    binaries: set = field(default_factory=set)
    resource_debts: dict = field(default_factory=dict)
    progress: float | None = None
    intermediate: dict = field(default_factory=dict)


class _RemoteError(Exception):
    pass


class Sila2Bridge(Bridge):
    bridge_kind = 'sila2'
    bridge_id = 'mhs.bridge.sila2'

    def __init__(self, config, *, transport=None, device_id=None, resource_id='main', validation=False):
        super().__init__(device_id=device_id)
        raw = copy.deepcopy(config)
        commands, reads = raw.pop('commands', {}), raw.pop('reads', {})
        self._config = compile_sila2(raw, commands, reads)
        self._authority = fingerprint(self._config)
        if transport is None and not validation:
            native_unavailable()
        self._transport = transport
        self._resource_id = resource_id
        self._condition = threading.Condition(threading.RLock())
        self._normal = None
        self._protective = None
        self._owners = {}
        self._works = {}
        self._latest = {}
        self._uuids = set()
        self._stream_ids = set()
        self._binary_ids = set()
        self._generation = str(uuid.uuid4())
        self._ordinary_generation = 0
        self._observation_sequence = -1
        self._stop_request_revision = 0
        self._admitted = False
        self._latched = False
        self._uncertain = False
        self._fault = False
        self._safe = False
        self._safe_epoch = -1
        self._cleanup = None
        self._cleanup_error = None
        self.trace = []
        if transport is not None and not validation:
            try:
                self._prepare_cleanup()
            except BaseException:
                # No factory can have run yet. A partially started cleanup
                # worker remains owned and is signalled before construction
                # propagates its failure. Injected peers remain caller-owned
                # if construction fails before a worker can start.
                with self._condition:
                    self._closed = True
                    self._condition.notify_all()
                raise

    @property
    def estop_native(self):
        return self._config['feature'] + '/Command/' + self._config['stop']

    def _check(self):
        if fingerprint(self._config) != self._authority:
            raise ValueError('SiLA compiled authority changed')

    def _context(self, ctx, maximum):
        context = BridgeContext.coerce(ctx)
        deadline = min(time.monotonic() + maximum / 1000,
                       (context.extra or {}).get('deadline_at', time.monotonic() + context.remaining_ms() / 1000))
        return context, deadline

    def _start(self, lane, deadline, function, *, effectful=False, member=None, context=None):
        self._check()
        with self._condition:
            self.ensure_open()
            if lane == 'protective':
                # Retain the earlier owner and its epoch. A later caller only
                # owns a new Stop after that work ends; no stale result is
                # reused and the original caller deadline never moves.
                while self._protective is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or context is not None and context.cancelled():
                        raise busy('protective lane remains owned within this caller budget')
                    self._condition.wait(min(.01, remaining))
                    self.ensure_open()
                if context is not None and context.cancelled():
                    raise busy('protective caller ended before admission')
            if time.monotonic() >= deadline:
                raise busy('no time remains to start a controlled request')
            if lane == 'protective' and effectful:
                self._engage_estop()
                self._latched = True
            work = _Work(str(uuid.uuid4()), lane, deadline, effectful, member, self.estop_epoch)
            slot = '_normal' if lane == 'normal' else '_protective'
            if getattr(self, slot) is not None:
                raise busy('SiLA lane retains its earlier owner')
            if lane == 'normal' and (len(self._works) >= self._config['max_operations'] or len(self._uuids) >= self._config['max_operations'] or len(self._stream_ids) >= self._config['max_operations'] * 4 or len(self._binary_ids) >= self._config['max_operations']):
                raise busy('bounded retained resource history is full')
            if lane == 'normal' and effectful and (self._latched or self._uncertain or self._fault):
                raise busy('SiLA effect admission awaits fresh retirement')
            if effectful and lane == 'normal':
                if len(self._owners) >= self._config['max_operations']:
                    raise busy('bounded execution history is full; no owner is discarded')
                self._owners[work.ident] = work
                if member is not None:
                    self._latest[member] = work
            setattr(self, slot, work)
            self._works[work.ident] = work
            if lane == 'normal':
                self._ordinary_generation += 1
            self._safe = False if effectful or lane == 'protective' else self._safe

        def execute():
            try:
                with self._condition:
                    self.ensure_open()
                    if effectful and lane == 'normal' and (self._latched or work.epoch != self.estop_epoch):
                        raise RuntimeError('effect start was fenced by stop')
                work.result = function(work)
            except BaseException as exc:
                work.error = exc
                with self._condition:
                    self._safe = False
                    if work.dispatched and effectful or lane == 'normal' and self._safe_epoch >= 0:
                        self._uncertain = True
            finally:
                # Even a failed acknowledgement is a relevant settlement for
                # proof freshness. No stale stopped observation can overwrite it.
                with self._condition:
                    if lane == 'normal':
                        self._ordinary_generation += 1
                    if not work.dispatched and effectful:
                        work.retired = True
                    if getattr(self, slot) is work:
                        setattr(self, slot, None)
                    work.done_at = time.monotonic()
                    work.event.set()
                    if work.resource_debts:
                        self._uncertain = True
                        self._safe = False
                    if (work.ident not in self._owners and not work.binaries and not work.resource_debts
                            and all(s['closed'] for s in work.streams.values())):
                        self._works.pop(work.ident, None)
                    self._condition.notify_all()

        work.thread = threading.Thread(target=execute, name='mhs-sila2-' + lane, daemon=True)
        try:
            # Publication precedes start; start never holds the lifecycle lock.
            # Close remains bounded even if Thread.start itself is delayed.
            work.thread.start()
        except BaseException as exc:
            with self._condition:
                if work.thread.ident is None:
                    if getattr(self, slot) is work:
                        setattr(self, slot, None)
                    work.retired = True
                    work.error = exc
                    work.done_at = time.monotonic()
                    work.event.set()
                    if lane == 'normal':
                        self._ordinary_generation += 1
                    self._works.pop(work.ident, None)
                    self._condition.notify_all()
                else:
                    work.abandoned = True
                    self._uncertain = True
                    self._safe = False
            raise outcome_unknown('SiLA worker startup failed; any started owner remains retained') from exc
        return work

    def _wait(self, work, context, *, cancellation=False):
        while True:
            if work.event.is_set() and work.done_at <= work.deadline and not work.abandoned:
                if work.error is not None:
                    if work.dispatched and work.effectful:
                        raise outcome_unknown('SiLA effect has no confirmed complete outcome') from work.error
                    raise driver_failed('MHS.CAPABILITY.OUTPUT_INVALID', 'SiLA controlled response is invalid') from work.error
                return work.result
            if (context.cancelled() or work.abandoned or time.monotonic() >= work.deadline
                    or work.rpc_deadline is not None and time.monotonic() >= work.rpc_deadline):
                with self._condition:
                    work.abandoned = True
                    self._safe = False
                    if work.effectful and not work.retired:
                        self._uncertain = True
                if context.cancelled() and cancellation:
                    stopped = self._stop(None)
                    if stopped['safe_state_achieved']:
                        raise signals.Cancelled('controlled SiLA operation retired after independent stop')
                raise outcome_unknown('SiLA caller ended; local and remote ownership remain retained')
            work.event.wait(min(.01, max(0, work.deadline - time.monotonic())))

    def _rpc(self, work, operation, member=None, **payload):
        self._check()
        with self._condition:
            if self.closed or work.abandoned or time.monotonic() >= work.deadline:
                raise TimeoutError('owned RPC has no remaining budget')
            if operation == 'invoke' and work.lane == 'normal' and (self._latched or work.epoch != self.estop_epoch):
                raise RuntimeError('ordinary mutation fenced by stop')
            request = {'format': PEER_FORMAT, 'request_id': str(uuid.uuid4()), 'owner_id': work.ident,
                       'generation': self._generation, 'endpoint': self._config['endpoint'],
                       'feature': self._config['feature'], 'runtime_profile': self._config['runtime_profile'],
                       'descriptor_sha256': self._config['fdl']['sha256'], 'operation': operation,
                       'member': member, 'payload': copy.deepcopy(payload)}
            if operation == 'invoke' or work.effectful and operation in ('property', 'subscribe'):
                work.dispatched = True
        plain(request, binary=True)
        with self._condition:
            rpc_deadline = min(work.deadline, time.monotonic() + self._config['request_timeout_ms'] / 1000)
            work.rpc_deadline = rpc_deadline
            # Keep the request and its owning peer/work before crossing the
            # allocation boundary. A transport/error envelope can arrive after
            # a stream or transfer exists, without exposing its identifier.
            spec = self._config['members'].get(member, {})
            binary_output = any(item['type'] == 'Binary' for item in spec.get('output', {}).values())
            creates_resource = (operation == 'subscribe' or binary_output and (
                operation in ('invoke', 'property', 'result') or operation == 'next'
                and work.streams.get(payload.get('stream_id'), {}).get('kind') == 'property'))
            if creates_resource:
                work.resource_debts[request['request_id']] = {
                    'operation': operation, 'member': member,
                    'request_sha256': fingerprint(request), 'generation': self._generation}
        try:
            raw = self._transport.request(request, timeout_ms=max(1, int((rpc_deadline - time.monotonic()) * 1000)))
        finally:
            with self._condition:
                if time.monotonic() >= rpc_deadline:
                    work.abandoned = True
                    self._safe = False
                    self._uncertain = self._uncertain or work.effectful
                work.rpc_deadline = None
        # Interpret a late confirmation/stream/transfer handle so that its
        # ownership is retained. The next RPC is forbidden once abandoned.
        for key in ('request_id', 'owner_id', 'generation', 'feature', 'member', 'operation'):
            # Identity fields are bounded scalar values from our request. Do
            # not adopt handles from an uncorrelated response, but do not let
            # malformed later fields erase handles in a correlated response.
            if (type(raw) is not dict or key not in raw
                    or type(raw[key]) is not type(request[key]) or raw[key] != request[key]):
                with self._condition:
                    self._fault = True
                raise ValueError('peer identity or operation mismatch')
        if 'payload' in raw:
            identified = self._own_response_resources(work, operation, member, payload, raw['payload'])
            if identified:
                with self._condition:
                    work.resource_debts.pop(request['request_id'], None)
        plain(raw, binary=True)
        reply = copy.deepcopy(raw)
        keys(reply, {'request_id', 'owner_id', 'generation', 'feature', 'member', 'operation', 'payload', 'error'},
             {'request_id', 'owner_id', 'generation', 'feature', 'member', 'operation'}, 'peer response')
        if ('payload' in reply) == ('error' in reply):
            raise ValueError('exactly one typed response or error is required')
        with self._condition:
            self.trace.append({'request_id': request['request_id'], 'owner_id': work.ident, 'operation': operation,
                               'member': member, 'request_sha256': fingerprint(request), 'response_sha256': fingerprint(reply)})
            self.trace[:] = self.trace[-128:]
        if 'error' in reply:
            error = reply['error']
            keys(error, {'kind', 'identifier', 'message'}, {'kind', 'identifier', 'message'}, 'error')
            if error['kind'] not in ('validation', 'defined', 'undefined', 'framework') or type(error['message']) is not str or len(error['message'].encode()) > 4096:
                raise ValueError('unsupported error')
            if type(error['identifier']) is not str or len(error['identifier']) > 512:
                raise ValueError('invalid bounded error identifier')
            if error['kind'] == 'framework' and error['identifier'] not in _FRAMEWORK_ERRORS:
                raise ValueError('undeclared framework error')
            if error['kind'] == 'defined' and error['identifier'] not in self._config['members'].get(member, {}).get('errors', []):
                raise ValueError('undeclared defined error')
            raise _RemoteError(error['kind'])
        return reply['payload']

    def _own_response_resources(self, work, operation, member, request_payload, value):
        """Retain identified remote resources before validating their bodies.

        This is ownership, never successful completion. Missing, reused or
        malformed identifiers leave a sticky fault; closing an observation or
        timing out cannot then certify retirement of an unknown resource.
        """
        spec = self._config['members'].get(member, {})
        identified = True
        try:
            if operation == 'invoke' and spec.get('kind') == 'observable_command':
                remote = _uuid(value.get('execution_uuid') if type(value) is dict else None)
                with self._condition:
                    if remote in self._uuids or work.execution_uuid is not None:
                        raise ValueError('execution UUID reused')
                    self._uuids.add(remote)
                    work.execution_uuid = remote
            elif operation == 'subscribe':
                ident = _uuid(value.get('stream_id') if type(value) is dict else None)
                with self._condition:
                    if ident in self._stream_ids:
                        raise ValueError('stream identity reused')
                    self._stream_ids.add(ident)
                    work.streams[ident] = {'kind': request_payload['kind'], 'member': member,
                                           'sequence': -1, 'closed': False}
            elif operation in ('invoke', 'property', 'result'):
                identified = self._capture_binaries(work, member, value)
            elif operation == 'next':
                identified = False
                stream = work.streams.get(request_payload.get('stream_id'))
                if stream is not None and stream['kind'] == 'property' and type(value) is dict:
                    items = value.get('items')
                    if type(items) is list:
                        # A property capture admits exactly one sample; retain
                        # every bounded batch handle even when cardinality is
                        # invalid. Oversized batches remain a sticky fault.
                        # An empty batch identifies no allocation. Retain the
                        # request debt even if the stream claims it has ended.
                        identified = bool(items)
                        for item in items[:16]:
                            complete = self._capture_binaries(work, member, item)
                            identified = complete and identified
                        if len(items) > 16:
                            raise ValueError('unbounded property resource batch')
        except (TypeError, ValueError, AttributeError, KeyError):
            with self._condition:
                self._fault = True
                self._safe = False
            raise ValueError('unidentified or reused response resource remains unresolved')
        return identified

    def _capture_binaries(self, work, member, value):
        if type(value) is not dict:
            return False
        identified = True
        for name, spec in self._config['members'].get(member, {}).get('output', {}).items():
            item = value.get(name)
            if spec['type'] != 'Binary':
                continue
            if type(item) is bytes:
                continue  # Complete inline value; no remote transfer handle.
            if type(item) is not dict:
                identified = False
                continue
            try:
                ident = _uuid(item.get('binary_uuid'))
                with self._condition:
                    if ident in self._binary_ids:
                        raise ValueError('binary identity reused')
                    self._binary_ids.add(ident)
                    work.binaries.add(ident)
            except (TypeError, ValueError, AttributeError):
                with self._condition:
                    self._fault = True
                raise ValueError('unidentified or reused binary remains unresolved')
        return identified

    def _admit(self, work):
        with self._condition:
            if self._admitted:
                return
            if work.lane != 'normal':
                raise RuntimeError('protective path cannot construct an unadmitted peer')
        self._prepare_cleanup()
        reply = self._rpc(work, 'describe')
        expected = {'runtime_profile': self._config['runtime_profile'], 'descriptor_sha256': self._config['fdl']['sha256'],
                    'proto_sha256': self._config['proto']['sha256'], 'members': self._config['members'], 'retirement_contract': 'controlled-only-v1'}
        if canonical(reply) != canonical(expected):
            raise ValueError('declared feature/descriptor contract mismatch')
        with self._condition:
            if self.closed:
                raise RuntimeError('closed during controlled admission')
            self._admitted = True

    def _observation(self, work):
        proof = self._rpc(work, 'observe')
        keys(proof, {'sequence', 'authoritative', 'quiescent', 'retired_owners', 'active_executions'},
             {'sequence', 'authoritative', 'quiescent', 'retired_owners', 'active_executions'}, 'retirement proof')
        integer(proof['sequence'], 0, 2**63 - 1, 'observation sequence')
        if type(proof['authoritative']) is not bool or type(proof['quiescent']) is not bool:
            raise ValueError('invalid retirement predicate')
        for key in ('retired_owners', 'active_executions'):
            if type(proof[key]) is not list or len(proof[key]) > self._config['max_operations']:
                raise ValueError('invalid ownership list')
            if len(set(_uuid(item) for item in proof[key])) != len(proof[key]):
                raise ValueError('duplicate ownership record')
        with self._condition:
            fresh = proof['sequence'] > self._observation_sequence
            self._observation_sequence = max(self._observation_sequence, proof['sequence'])
            if not fresh or not proof['authoritative'] or not proof['quiescent'] or proof['active_executions']:
                self._safe = False
                if self._latched:
                    self._uncertain = True
            return proof, fresh

    def _stream(self, work, member, kind):
        result = self._rpc(work, 'subscribe', member, kind=kind, execution_uuid=work.execution_uuid)
        keys(result, {'stream_id'}, {'stream_id'}, 'stream')
        ident = _uuid(result['stream_id'])
        if ident not in work.streams:
            raise ValueError('stream was not retained with its response')
        return ident

    def _next(self, work, member, stream):
        result = self._rpc(work, 'next', member, stream_id=stream)
        keys(result, {'sequence', 'items', 'end'}, {'sequence', 'items', 'end'}, 'stream batch')
        state = work.streams[stream]
        integer(result['sequence'], 0, 2**63 - 1, 'stream sequence')
        if result['sequence'] != state['sequence'] + 1 or type(result['end']) is not bool or type(result['items']) is not list or len(result['items']) > 16:
            raise ValueError('stream gap, overflow or malformed batch')
        state['sequence'] = result['sequence']
        return result

    def _close_streams(self, work, member, owner=None):
        owner = work if owner is None else owner
        for ident, state in owner.streams.items():
            if state['closed']:
                continue
            result = self._rpc(work, 'unsubscribe', state['member'], stream_id=ident, stream_owner=owner.ident)
            if result != {'closed': True} or type(result.get('closed')) is not bool:
                raise ValueError('stream closure unconfirmed')
            state['closed'] = True

    def _release_resources(self, work):
        with self._condition:
            if self._normal is not None:
                return
            owners = list(self._works.values())
        for owner in owners:
            if owner is work:
                continue
            self._close_streams(work, owner.member, owner)
            for ident in list(owner.binaries):
                result = self._rpc(work, 'binary_delete', owner.member, binary_uuid=ident, binary_owner=owner.ident)
                if canonical(result) != canonical({'deleted': True}):
                    raise ValueError('binary cleanup remains unconfirmed')
                owner.binaries.remove(ident)
            with self._condition:
                if owner.ident not in self._owners and owner.event.is_set() and not owner.resource_debts:
                    self._works.pop(owner.ident, None)

    def _result(self, work, member, args):
        spec = self._config['members'][member]
        if spec['kind'] in ('property', 'observable_property'):
            if spec['kind'] == 'property':
                value = self._rpc(work, 'property', member)
            else:
                stream = self._stream(work, member, 'property')
                batch = self._next(work, member, stream)
                if len(batch['items']) != 1:
                    raise ValueError('property needs exactly one captured sample')
                value = batch['items'][0]
                self._close_streams(work, member)
            output = validate_fields(spec['output'], value, profile=self._config['runtime_profile'])
            expected = self._config['unsafe_properties'].get(member)
            if expected is not None and canonical(output) != canonical(expected):
                with self._condition:
                    self._safe = False
                    if self._latched or self._safe_epoch >= 0:
                        self._uncertain = True
            return output
        value = self._rpc(work, 'invoke', member, input=args, metadata=self._config['metadata'])
        if spec['kind'] != 'observable_command':
            output = validate_fields(spec['output'], value, profile=self._config['runtime_profile'])
            if spec['completion'] == 'acknowledgement':
                raise _RemoteError('unary acknowledgement is not completion')
            return output
        keys(value, {'execution_uuid', 'lifetime'}, {'execution_uuid', 'lifetime'}, 'confirmation')
        remote = _uuid(value['execution_uuid'])
        if value['lifetime'] is not None:
            validate({'type': 'Duration'}, value['lifetime'])
        if remote != work.execution_uuid:
            raise ValueError('execution was not retained with its response')
        info = self._stream(work, member, 'info')
        intermediate = self._stream(work, member, 'intermediate') if spec.get('intermediate') else None
        events = 0
        ended = False
        while not ended:
            if self._latched or self.closed or work.abandoned:
                raise _RemoteError('observation ended without remote retirement')
            batch = self._next(work, member, info)
            for event in batch['items']:
                if work.terminal_packet is not None and canonical(event) != work.terminal_packet:
                    with self._condition:
                        self._fault = True
                    raise ValueError('contradictory terminal execution info')
                keys(event, {'execution_uuid', 'status', 'progress', 'remaining', 'lifetime'},
                     {'execution_uuid', 'status', 'progress', 'remaining', 'lifetime'}, 'execution info')
                if event['execution_uuid'] != work.execution_uuid:
                    raise ValueError('foreign execution info')
                integer(event['status'], 0, 3, 'execution status')
                if event['progress'] is not None:
                    validate({'type': 'Real', 'min': 0, 'max': 1}, event['progress'])
                for name in ('remaining', 'lifetime'):
                    if event[name] is not None:
                        validate({'type': 'Duration'}, event[name])
                events += 1
                if events > self._config['max_events']:
                    raise ValueError('bounded stream event budget exceeded')
                if work.terminal is not None and (event['status'] != work.terminal or canonical(event) != work.terminal_packet):
                    with self._condition:
                        self._fault = True
                    raise ValueError('contradictory terminal execution info')
                if event['status'] in (2, 3):
                    work.terminal, work.terminal_packet = event['status'], canonical(event)
                work.progress = event['progress']
            if intermediate:
                inter = self._next(work, member, intermediate)
                for item in inter['items']:
                    work.intermediate = validate_fields(spec['intermediate'], item, profile=self._config['runtime_profile'])
            ended = batch['end']
            if not ended:
                time.sleep(.001)
        if work.terminal is None:
            raise ValueError('stream ended without terminal info')
        value = self._rpc(work, 'result', member, execution_uuid=work.execution_uuid)
        output = validate_fields(spec['output'], value, profile=self._config['runtime_profile'])
        self._close_streams(work, member)
        if work.terminal != 2:
            raise _RemoteError('execution finished with error')
        return output

    def _binary(self, work, member, value, spec):
        validate(spec, value, profile=self._config['runtime_profile'])
        if type(value) is bytes:
            return value
        ident = _uuid(value['binary_uuid'])
        if ident not in work.binaries:
            raise ValueError('binary handle was not retained with its response')
        info = self._rpc(work, 'binary_info', member, binary_uuid=ident)
        if canonical(info) != canonical(value):
            raise ValueError('binary identity/size/digest changed')
        chunks = []
        offset = 0
        while offset < value['size_bytes']:
            count = min(65536, value['size_bytes'] - offset)
            chunk = self._rpc(work, 'binary_chunk', member, binary_uuid=ident, offset=offset, length=count)
            keys(chunk, {'offset', 'data'}, {'offset', 'data'}, 'binary chunk')
            if type(chunk['offset']) is not int or chunk['offset'] != offset or type(chunk['data']) is not bytes or len(chunk['data']) != count:
                raise ValueError('binary chunk has gap, overlap or truncation')
            chunks.append(chunk['data']); offset += count
        data = b''.join(chunks)
        if hashlib.sha256(data).hexdigest() != value['sha256']:
            raise ValueError('complete binary digest mismatch')
        result = self._rpc(work, 'binary_delete', member, binary_uuid=ident, binary_owner=work.ident)
        if canonical(result) != canonical({'deleted': True}):
            raise ValueError('binary deletion remains owned')
        work.binaries.remove(ident)
        return data

    def call(self, capability_id, args=None, ctx=None):
        binding = self._config['commands'].get(capability_id)
        if binding is None:
            raise unsupported(capability_id)
        member = binding['member']
        if member == self._config['stop']:
            if args:
                raise make_mhs_error('MHS.CAPABILITY.INPUT_INVALID', 'Stop accepts no inputs')
            result = self._stop(ctx)
            if not result['safe_state_achieved']:
                raise driver_failed('MHS.SAFETY.SAFE_STATE_UNREACHED', 'SiLA Stop is not freshly retired')
            return {'stopped': True}
        spec = self._config['members'][member]
        try:
            values = input_values(self._config, binding, {} if args is None else args)
        except (TypeError, ValueError) as exc:
            raise make_mhs_error('MHS.CAPABILITY.INPUT_INVALID', 'SiLA typed protocol input was refused before dispatch') from exc
        context, deadline = self._context(ctx, self._config['execution_timeout_ms'])
        if context.cancelled():
            raise signals.Cancelled('SiLA request was cancelled before dispatch')
        publisher = publisher_from_context(context) if 'artifact' in binding else None
        if 'artifact' in binding:
            if publisher is None:
                raise make_mhs_error('MHS.CAPABILITY.NOT_BOUND', 'stock artifact store is required')
            publisher.preflight(spec['output'][binding['artifact']]['max_bytes'])
        def execute(work):
            self._admit(work)
            output = self._result(work, member, values)
            if spec['effect'] == 'effectful':
                proof, fresh = self._observation(work)
                with self._condition:
                    if (fresh and proof['authoritative'] and proof['quiescent'] and not proof['active_executions']
                            and work.ident in proof['retired_owners'] and not self._fault
                            and not self.closed and work.epoch == self.estop_epoch):
                        work.retired = True
                    else:
                        raise _RemoteError('returned result lacks current controlled retirement')
            if 'artifact' in binding:
                data = self._binary(work, member, output[binding['artifact']], spec['output'][binding['artifact']])
                if len(data) > publisher.max_bytes:
                    raise ValueError('artifact exceeds grant budget')
                with self._condition:
                    if work.abandoned or self.closed or work.epoch != self.estop_epoch:
                        raise RuntimeError('artifact owner is no longer admitted')
                descriptor = publisher.publish(data, binding['media_type'], output_field='artifact_ref')
                try:
                    with self._condition:
                        if work.abandoned or self.closed or work.epoch != self.estop_epoch:
                            raise RuntimeError('artifact commit lost its owner')
                except BaseException:
                    publisher.abort()
                    raise
                return {'artifact_ref': descriptor['uri'], 'media_type': binding['media_type'], 'size_bytes': len(data)}
            return output
        work = self._start('normal', deadline, lambda work: self._ordinary_action(execute, work),
                           effectful=spec['effect'] == 'effectful', member=member)
        return self._wait(work, context, cancellation=spec['kind'] == 'observable_command')

    def read(self, resource_id, fields=None, ctx=None):
        if resource_id != self._resource_id:
            raise unsupported(resource_id, 'resource')
        selected = list(self._config['reads']) if fields is None else list(fields)
        if any(name not in self._config['reads'] for name in selected):
            raise unsupported(resource_id, 'field')
        diagnostics = {}
        with self._condition:
            self._check()
            self.ensure_open()
            for name in selected:
                binding = self._config['reads'][name]
                if 'execution' not in binding:
                    continue
                work = self._latest.get(binding['execution'])
                state = binding['state']
                value = binding['default']
                if work is not None:
                    if state == 'known': value = work.execution_uuid is not None
                    elif state == 'uuid': value = work.execution_uuid or value
                    elif state == 'progress': value = work.progress if work.progress is not None else value
                    elif state.startswith('intermediate:'):
                        value = work.intermediate.get(state.split(':', 1)[1], value)
                diagnostics[name] = copy.deepcopy(value)
        if len(diagnostics) == len(selected):
            return diagnostics
        context, deadline = self._context(ctx, self._config['execution_timeout_ms'])
        def execute(work):
            self._admit(work)
            output = dict(diagnostics)
            for name in selected:
                if name in diagnostics:
                    continue
                binding = self._config['reads'][name]
                values = self._result(work, binding['member'], {})
                output[name] = values[binding['field']]
            return output
        return self._wait(self._start('normal', deadline, lambda work: self._ordinary_read(execute, work)), context)

    def _ordinary_action(self, function, work):
        """Keep the ordinary command's recording phase on its owned worker."""
        return function(work)

    def _ordinary_read(self, function, work):
        """A concurrent protective caller cannot relabel this worker's read."""
        return function(work)

    def _invoke_stop(self, work):
        """The finite native-shaped Stop request, distinct from ordinary work."""
        result = self._rpc(work, 'invoke', self._config['stop'], input={}, metadata=self._config['metadata'])
        validate_fields(self._config['members'][self._config['stop']]['output'], result)

    def _stop(self, ctx, *, reset=False):
        context, deadline = self._context(ctx, self._config['stop_timeout_ms'])
        with self._condition:
            if not reset:
                # Fence fresh ordinary effects immediately. Advance the proof
                # epoch only when this caller owns the protective slot.
                self._stop_request_revision += 1
                self._latched = True
            reset_revision = self._stop_request_revision
            previous_safe = self._safe
            if self.closed or not self._admitted or reset and (not previous_safe or self._uncertain or self._fault):
                return {'performed': False, 'native': self.estop_native, 'safe_state_achieved': False}

        def execute(work):
            attempt = 0
            while True:
                with self._condition:
                    generation = self._ordinary_generation
                    pending = self._normal is not None
                if not reset:
                    self._invoke_stop(work)
                    with self._condition:
                        self._condition.wait_for(lambda: self._normal is None,
                                                 timeout=min(.05, max(0, deadline - time.monotonic())))
                self._release_resources(work)
                proof, fresh = self._observation(work)
                with self._condition:
                    unresolved_resources = any(owner.resource_debts or owner.binaries or
                                               any(not s['closed'] for s in owner.streams.values())
                                               for owner in self._works.values())
                    achieved = (not pending and self._normal is None and generation == self._ordinary_generation
                                and not unresolved_resources and fresh and proof['authoritative'] and proof['quiescent']
                                and not proof['active_executions'] and not self._fault and not self.closed
                                and not work.abandoned and work.epoch == self.estop_epoch and time.monotonic() < deadline
                                and (not reset or reset_revision == self._stop_request_revision)
                                and all(owner.retired or ident in proof['retired_owners'] for ident, owner in self._owners.items()))
                    if achieved:
                        for owner in self._owners.values():
                            owner.retired = True
                        self._safe, self._safe_epoch, self._uncertain = True, work.epoch, False
                        if reset:
                            self._latched = False
                        return {'performed': not reset, 'native': self.estop_native, 'safe_state_achieved': True}
                    if self.closed or reset or work.abandoned or time.monotonic() >= deadline:
                        break
                    # Keep the first observation even while ordinary work is
                    # pending. A cooperative receipt read may settle later in
                    # this caller's original budget; its proof still needs a
                    # new Stop after retirement. Only read() admits member=None
                    # non-effectful work. Command/publication owners keep the
                    # prompt unsafe result. Close/abandon ends the wait.
                    while (self._normal is not None and self._normal.member is None
                           and not self._normal.effectful and not self.closed and not work.abandoned):
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        self._condition.wait(min(.01, remaining))
                    if (self._normal is not None or self.closed or work.abandoned
                            or time.monotonic() >= deadline):
                        break
                    # Keep the two stable negative-proof attempts. Ordinary
                    # settlement invalidates that observation, so a fresh Stop
                    # and proof may retry within the same unextended deadline.
                    if (attempt >= 1 and not pending and self._normal is None
                            and generation == self._ordinary_generation):
                        break
                    attempt += 1
            return {'performed': not reset, 'native': self.estop_native, 'safe_state_achieved': False}
        try:
            work = self._start('protective', deadline, execute, effectful=not reset,
                               member=self._config['stop'], context=context)
            return self._wait(work, context)
        except Exception:
            # Admission-only timeout/cancellation did not dispatch another
            # effect. Owned request failures already retain their uncertainty
            # in _start/_wait; do not invalidate an earlier owner's proof.
            return {'performed': False, 'native': self.estop_native, 'safe_state_achieved': False}

    def estop(self, reason='', ctx=None):
        return self._stop(ctx)

    def safe_state(self, ctx=None):
        result = self._stop(ctx)
        return {'achieved': result['safe_state_achieved'], 'native': result['native']}

    def reset(self, ctx=None):
        result = self._stop(ctx, reset=True)
        if not result['safe_state_achieved']:
            raise make_mhs_error('MHS.SAFETY.SAFE_STATE_UNREACHED', 'fresh controlled retirement is required for reset')
        return {'reset': True}

    def safety_status(self):
        with self._condition:
            # A stock cancellation receipt can start a non-effectful state
            # read just after Stop committed. Wait briefly for already-owned
            # work; never exclude it from the final safety predicate. The
            # condition releases its lock so retirement/close can proceed.
            pending = [work for work in (self._normal, self._protective) if work is not None]
            if (pending and (self._safe or self._protective is not None)
                    and all(work.thread is not threading.current_thread() for work in pending)):
                deadline = min(time.monotonic() + .05, *(work.deadline for work in pending))
                self._condition.wait_for(lambda: self.closed or self._uncertain or self._fault or
                                        self._normal is None and self._protective is None,
                                        timeout=max(0, deadline - time.monotonic()))
            achieved = (self._safe and not self._uncertain and not self._fault and not self.closed
                        and self._normal is None and self._protective is None and self._safe_epoch == self.estop_epoch)
            return {'estop': {'native': self.estop_native}, 'safe_state': {'achieved': achieved},
                    'remote_uncertain': self._uncertain or self._fault,
                    'pending_sila': int(self._normal is not None) + int(self._protective is not None)}

    def _prepare_cleanup(self):
        with self._condition:
            if self._cleanup is not None:
                return
            self.ensure_open()
            # Establish cleanup ownership before constructing the peer. Close
            # only signals this already-owned worker and never starts a thread.
            worker = threading.Thread(target=self._cleanup_run, name='mhs-sila2-close', daemon=True)
            self._cleanup = worker
        try:
            worker.start()
        except BaseException as exc:
            with self._condition:
                self._cleanup_error = type(exc).__name__
                if worker.ident is None:
                    self._cleanup = None
                else:
                    self._fault = True
            raise

    def _cleanup_run(self):
        with self._condition:
            self._condition.wait_for(lambda: self.closed and self._normal is None and self._protective is None)
        # Closing the local peer never retires the remote owners. Failed close
        # remains visible and the lease retains its registered handle.
        if self._transport is not None:
            try:
                self._transport.close()
            except BaseException as exc:
                self._cleanup_error = type(exc).__name__

    def close(self):
        with self._condition:
            self._closed = True
            self._latched = True
            self._safe = False
            if (any(not owner.retired for owner in self._owners.values())
                    or any(owner.resource_debts for owner in self._works.values())):
                self._uncertain = True
            self._condition.notify_all()
