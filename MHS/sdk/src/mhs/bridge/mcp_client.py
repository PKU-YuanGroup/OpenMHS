"""Finite MCP calls over an injected controlled peer, with retained ownership.

No native transport is implemented or constructed here. MCP cancellation and
disconnect are not proof of device stopping. A declared protective transaction
can prove only the controlled peer's state after every older request retires.
"""
from __future__ import annotations

import base64
import copy
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import io
import json
import threading
import time
import uuid

from .base import Bridge, BridgeContext, busy, driver_failed, make_mhs_error, outcome_unknown, unsupported
from .ros_images import _check_png, require_decoder
from .mcp_stdio import OwnedStdioTransport
from .. import signals
from ..artifacts import publisher_from_context
from ..driver.mcp_client_config import compile_mcp_client, checked, encoded, get_path, keys, plain


def native_unavailable(**_options):
    raise RuntimeError('MCP native admission blocked: transport ownership, cancellation and device-state evidence are unresolved')


def _context(ctx, maximum):
    context = BridgeContext.coerce(ctx)
    deadline = min(time.monotonic() + maximum / 1000,
                   context.extra.get('deadline_at', time.monotonic() + context.remaining_ms() / 1000))
    return BridgeContext.coerce({**context.__dict__, 'extra': {**context.extra, 'deadline_at': deadline}})


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate JSON key')
        value[key] = item
    return value


def _constant(_value):
    raise ValueError('nonfinite JSON number')


@dataclass
class _Exchange:
    ident: str
    tool: str | None
    lane: str
    effectful: bool
    event: threading.Event = field(default_factory=threading.Event)
    result: object = None
    error: BaseException | None = None
    abandoned: bool = False


class McpClientBridge(Bridge):
    bridge_kind = 'mcp-client'
    bridge_id = 'mhs.bridge.mcp_client'

    def __init__(self, config, *, transport=None, device_id=None, resource_id='main', validation=False):
        super().__init__(device_id=device_id)
        raw = copy.deepcopy(config)
        commands, reads = raw.pop('commands', {}), raw.pop('reads', {})
        self.config = compile_mcp_client(raw, commands, reads)
        self._config = copy.deepcopy(self.config)
        if transport is None and not validation:
            native_unavailable()
        self._transport, self._resource_id = transport, resource_id
        self._condition = threading.Condition(threading.RLock())
        self._safety_lane = threading.Lock()
        self._ordinary_lane = threading.Lock()
        self._pending = {}
        self._normal_generation = 0
        self._observation_revision = 0
        self._discovered = False
        self._latched = self._debt = self._safe = False
        self._safe_epoch = -1
        self._proof = None
        self._close_started = False
        self._close_done = threading.Event()
        self._close_error = self._close_start_error = None
        self.trace = []
        self._owned_peer = transport if type(transport) is OwnedStdioTransport else None
        if self._owned_peer is not None:
            self._owned_peer.attach(self._owned_terminal)

    def _owned_terminal(self):
        with self._condition:
            self._debt = self._latched = True
            self._safe = False
            self._proof = None
            self._condition.notify_all()

    @contextmanager
    def _owner_guard(self):
        # The caller holds the bridge condition. Transport callbacks never hold
        # its ownership lock while acquiring this condition.
        if self._owned_peer is None:
            yield None
        else:
            with self._owned_peer.ownership_guard() as token:
                if token is None and self._safe:
                    self._debt = self._latched = True
                    self._safe = False
                    self._proof = None
                yield token

    def _proof_value(self, epoch, generation, owner_token):
        value = (epoch,generation,self._observation_revision)
        return value if self._owned_peer is None else (*value,owner_token)

    @property
    def estop_native(self):
        safety = self._config.get('safety')
        return ('tools/call:' + safety['command']) if safety else None

    def _response(self, raw, message, tool):
        encoded(raw, self._config['max_message_bytes'])
        keys(raw, {'jsonrpc', 'id', 'result'}, {'jsonrpc', 'id', 'result'}, 'response')
        if raw['jsonrpc'] != '2.0' or type(raw['id']) is not str or raw['id'] != message['id']:
            raise ValueError('response identity/protocol mismatch')
        result = raw['result']
        if tool is None:
            keys(result, {'tools'}, {'tools'}, 'discovery')
            rows = result['tools']
            if type(rows) is not list or len(rows) != len(self._config['tools']):
                raise ValueError('remote tools differ from local authority')
            seen = set()
            for row in rows:
                keys(row, {'name', 'inputSchema', 'description', 'annotations', 'title', 'outputSchema'},
                     {'name', 'inputSchema'}, 'remote tool')
                name = row['name']
                if (type(name) is not str or name in seen or name not in self._config['tools']
                        or row['inputSchema'] != self._config['tools'][name]['input']):
                    raise ValueError('remote tool/schema drift')
                seen.add(name)
            return None
        spec = self._config['tools'][tool]
        output = spec['output']
        keys(result, {'content', 'structuredContent', 'isError'}, {'content'}, 'tool result')
        if type(result.get('isError', False)) is not bool or result.get('isError', False):
            raise ValueError('remote tool reports an error')
        blocks = result['content']
        if type(blocks) is not list or len(blocks) != 1:
            raise ValueError('one complete primary content block is required')
        block = blocks[0]
        if output['kind'] == 'png':
            keys(block, {'type', 'mimeType', 'data'}, {'type', 'mimeType', 'data'}, 'PNG content')
            if block['type'] != 'image' or block['mimeType'] != 'image/png' or type(block['data']) is not str:
                raise ValueError('expected an inline PNG; resource links and paths are not followed')
            if 'structuredContent' in result or len(block['data']) > (output['max_bytes'] + 2) // 3 * 4:
                raise ValueError('PNG exceeds its bound or has conflicting primary content')
            data = base64.b64decode(block['data'], validate=True)
            if not data or len(data) > output['max_bytes']:
                raise ValueError('PNG exceeds decoded byte budget')
            _check_png(data, output['max_pixels'])
            image = require_decoder()
            with image.open(io.BytesIO(data)) as decoded:
                decoded.verify()
            with image.open(io.BytesIO(data)) as decoded:
                decoded.load()
                width, height = decoded.size
            return {'bytes': data, 'width': width, 'height': height}
        keys(block, {'type', 'text'}, {'type', 'text'}, 'text content')
        if block['type'] != 'text' or type(block['text']) is not str:
            raise ValueError('expected complete inline text')
        text = block['text']
        if len(text.encode('utf-8')) > output['max_bytes']:
            raise ValueError('primary text exceeds output budget')
        if any(text.lstrip().startswith(prefix) for prefix in spec.get('error_prefixes', [])):
            raise ValueError('remote normal-text error')
        if output['kind'] == 'text':
            if 'structuredContent' in result:
                raise ValueError('unexpected second primary text representation')
            prefixes = output.get('success_prefixes', [])
            if prefixes and not any(text.startswith(prefix) for prefix in prefixes):
                raise ValueError('missing declared success text')
            return {'text': text}
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
        checked(value, output['schema'], 'tool result')
        arguments = {**spec.get('defaults', {}), **message['params']['arguments']}
        for path, argument in spec.get('result_matches', {}).items():
            if encoded(get_path(value, path)) != encoded(arguments[argument]):
                raise ValueError('primary result does not match its request arguments')
        for path, count_path in output.get('array_counts', {}).items():
            present = True
            try:
                array, count = get_path(value, path), get_path(value, count_path)
            except ValueError:
                present = False
            conditional = output.get('arrays_if')
            expected = arguments[conditional] if conditional else True
            if present != expected or (present and (type(array) is not list or type(count) is not int or len(array) != count)):
                raise ValueError('complete primary array presence/count differs from its contract')
        if 'structuredContent' in result and encoded(result['structuredContent']) != encoded(value):
            raise ValueError('structured and textual primary results conflict')
        return value

    def _observe_locked(self, tool, result):
        safety = self._config.get('safety')
        if safety and tool == safety['observe']:
            self._observation_revision += 1
            if get_path(result, safety['path']) != safety['equals']:
                if self._safe or self._latched:
                    self._debt = True
                self._safe = False
                self._proof = None

    def _exchange(self, tool, arguments, context, epoch, *, protective=False):
        deadline = min(context.extra['deadline_at'], time.monotonic() + self._config['request_timeout_ms'] / 1000)
        lane = 'protective' if protective else 'normal'
        spec = self._config['tools'].get(tool) if tool is not None else None
        effectful = bool(spec and spec['effectful'])
        if spec:
            checked(arguments, spec['input'], 'tool input')
        with self._condition:
            self.ensure_open()
            while any(item.lane == lane for item in self._pending.values()):
                if any(item.lane == lane and item.abandoned for item in self._pending.values()):
                    raise busy('MCP lane retains an abandoned request')
                if time.monotonic() >= deadline:
                    raise busy('MCP lane did not retire within its finite budget')
                if not protective and context.cancelled():
                    raise signals.Cancelled('MCP call cancelled before dispatch')
                self._condition.wait(min(.01, max(0, deadline - time.monotonic())))
                self.ensure_open()
            if time.monotonic() >= deadline:
                raise busy('MCP call has no dispatch budget')
            if not protective and context.cancelled():
                raise signals.Cancelled('MCP call cancelled before dispatch')
            if effectful and not protective and (self._latched or self._debt or epoch != self.estop_epoch):
                raise make_mhs_error('MHS.SAFETY.ESTOP_ENGAGED', 'unsettled MCP effects block new effects')
            ident = uuid.uuid4().hex
            message = {'jsonrpc': '2.0', 'id': ident, 'method': 'tools/call' if spec else 'tools/list',
                       'params': {'name': tool, 'arguments': copy.deepcopy(arguments)} if spec else {}}
            encoded(message, self._config['max_message_bytes'])
            exchange = _Exchange(ident, tool, lane, effectful)
            self._pending[ident] = exchange
            if lane == 'normal':
                self._normal_generation += 1
            if effectful:
                self._safe = False
                self._proof = None

            def execute():
                try:
                    raw = self._transport.exchange(copy.deepcopy(message), lane=lane,
                        timeout_ms=max(1, int((deadline - time.monotonic()) * 1000)))
                    result = self._response(raw, message, tool)
                    with self._condition:
                        self._observe_locked(tool, result)
                        exchange.result = result
                        self.trace.append({'id': ident, 'tool': tool, 'lane': lane,
                            'request_sha256': hashlib.sha256(encoded(message)).hexdigest(),
                            'response_sha256': hashlib.sha256(encoded(raw)).hexdigest()})
                        self.trace[:] = self.trace[-128:]
                except BaseException as exc:
                    if self._owned_peer is not None:
                        self._owned_peer.request_close('MCP exchange or result validation failed')
                        self._owned_peer.wait_retired()
                    with self._condition:
                        exchange.error = exc
                        if effectful or self._owned_peer is not None:
                            self._debt = True
                            self._safe = False
                            self._proof = None
                finally:
                    with self._condition:
                        self._pending.pop(ident, None)
                        if lane == 'normal':
                            self._normal_generation += 1
                        exchange.event.set()
                        self._condition.notify_all()
                        self._maybe_close_locked()

            worker = threading.Thread(target=execute, name='mhs-mcp-' + lane, daemon=True)
            try:
                worker.start()
            except BaseException as exc:
                if worker.ident is None:
                    self._pending.pop(ident, None)
                    if lane == 'normal':
                        self._normal_generation += 1
                    exchange.error = exc
                    exchange.event.set()
                    self._condition.notify_all()
                    self._maybe_close_locked()
                    raise driver_failed('MHS.DEVICE.NOT_READY', 'MCP request worker could not start') from exc
                exchange.abandoned = True
                self._debt = True
                if self._owned_peer is not None:
                    self._owned_peer.abandon(ident,'request worker startup acknowledgement failed')
                raise outcome_unknown('MCP worker started without startup acknowledgement') from exc
        while not exchange.event.wait(min(.01, max(0, deadline - time.monotonic()))):
            if time.monotonic() >= deadline or (not protective and context.cancelled()):
                with self._condition:
                    exchange.abandoned = True
                    if effectful:
                        self._debt = True
                    self._safe = False
                    self._proof = None
                if self._owned_peer is not None:
                    self._owned_peer.abandon(ident,'MCP caller deadline or cancellation')
                raise outcome_unknown('MCP request remains owned after timeout/cancellation')
        if exchange.error is not None:
            if effectful:
                raise outcome_unknown('MCP effect response is unconfirmed') from exchange.error
            raise driver_failed('MHS.CAPABILITY.OUTPUT_INVALID', 'MCP result is invalid') from exchange.error
        return exchange.result, ident

    def _discover(self, context, epoch):
        with self._condition:
            if self._discovered:
                return
        self._exchange(None, {}, context, epoch)
        with self._condition:
            self.ensure_open()
            self._discovered = True

    def _publication_guard(self, context, epoch):
        with self._condition, self._owner_guard() as owner:
            self.ensure_open()
            if (epoch != self.estop_epoch or context.cancelled() or context.remaining_ms() <= 0
                    or (self._owned_peer is not None and owner is None)):
                raise signals.Cancelled('MCP output publication was superseded')

    @contextmanager
    def _ordinary(self, context):
        # Keep a source-declared prerequisite and its subsequent request in
        # one bounded ordinary transaction. Protective calls never take it.
        if not self._ordinary_lane.acquire(timeout=max(0, context.remaining_ms() / 1000)):
            raise busy('MCP ordinary transaction is still owned')
        try:
            self.ensure_open()
            if context.cancelled():
                raise signals.Cancelled('MCP transaction cancelled before dispatch')
            yield
        finally:
            self._ordinary_lane.release()

    def call(self, capability_id, args=None, ctx=None):
        self.ensure_open()
        command = self._config['commands'].get(capability_id)
        if command is None:
            raise unsupported(capability_id)
        tool = command['tool']
        spec = self._config['tools'][tool]
        supplied = {} if args is None else args
        checked(supplied, command.get('input_schema',spec['input']), 'command input')
        context = _context(ctx, self._config['request_timeout_ms'] * 2)
        if self._owned_peer is not None and context.cancelled():
            # No transaction has been admitted. Do not start a fresh process
            # merely to stop a request that has never been issued.
            raise signals.Cancelled('MCP controlled request cancelled before admission')
        epoch = self.estop_epoch
        output = spec['output']
        artifact = output['kind'] == 'png' or output.get('artifact', False)
        publisher = publisher_from_context(context) if artifact else None
        if artifact:
            if publisher is None:
                raise driver_failed('MHS.CAPABILITY.NOT_BOUND', 'complete MCP output requires an artifact store')
            publisher.preflight(output['max_bytes'])
        try:
            with self._ordinary(context):
                self._discover(context, epoch)
                case=command
                if 'select' in command:
                    observation=command['select']['observe'];preparation=observation['prepare']
                    self._exchange(preparation['tool'],preparation['arguments'],context,epoch)
                    try:
                        observed,_ident=self._exchange(observation['tool'],{},context,epoch)
                        selected=get_path(observed,observation['path'])
                        if type(selected) is not str or selected not in command['select']['cases']:
                            raise ValueError('retained native selector has no declared typed branch')
                        case=command['select']['cases'][selected]
                    except Exception as exc:
                        with self._condition:
                            self._debt=True;self._safe=False;self._proof=None
                        raise outcome_unknown('MCP preparation changed state but the typed readback did not confirm continuation') from exc
                if 'arguments' in case:
                    arguments={name:(rule['const'] if 'const' in rule else supplied[rule['input']])
                               for name,rule in case['arguments'].items() if 'const' in rule or rule['input'] in supplied}
                else:
                    arguments=supplied
                checked(arguments,spec['input'],'wire arguments')
                prerequisite = spec.get('prerequisite')
                effective = {**spec.get('defaults', {}), **arguments}
                if prerequisite and effective[prerequisite['when']['argument']] == prerequisite['when']['equals']:
                    observation, _ident = self._exchange(prerequisite['observe'], {}, context, epoch)
                    if get_path(observation, prerequisite['path']) != prerequisite['equals']:
                        raise make_mhs_error('MHS.DEVICE.PRECONDITION_UNMET', 'MCP source-declared prerequisite is not observed')
                value, ident = self._exchange(tool, arguments, context, epoch)
        except Exception as exc:
            if context.cancelled():
                result = self._stop(_context(None, self._config['stop_timeout_ms']), engage=True)
                with self._condition:
                    settled = result['safe_state_achieved'] and self._safe and not self._pending and not self._debt
                if settled:
                    raise signals.Cancelled('controlled MCP endpoint settled after cancellation') from exc
                raise outcome_unknown('MCP cancellation did not settle earlier requests') from exc
            raise
        self._publication_guard(context, epoch)
        if not artifact:
            return copy.deepcopy(value)
        data = value['bytes'] if output['kind'] == 'png' else encoded(value, output['max_bytes'])
        field_name = 'image_ref' if output['kind'] == 'png' else 'artifact_ref'
        media = 'image/png' if output['kind'] == 'png' else 'application/json'
        descriptor = publisher.publish(data, media_type=media, output_field=field_name,
            x_vendor={'openmhs.mcp_result': {'tool': tool, 'request_id': ident,
                      'source_sha256': self._config['source']['sha256'], 'coverage': 'complete_returned_result'}})
        try:
            self._publication_guard(context, epoch)
        except BaseException:
            publisher.abort()
            raise
        result = {field_name: descriptor['uri'], 'media_type': media}
        if output['kind'] == 'png':
            result.update(width=value['width'], height=value['height'])
        return result

    def read(self, resource_id, fields=None, ctx=None):
        if resource_id != self._resource_id:
            raise unsupported(resource_id, 'resource')
        names = list(self._config['reads']) if fields is None else list(fields)
        if any(name not in self._config['reads'] for name in names):
            raise unsupported('read field', 'resource')
        context = _context(ctx, self._config['request_timeout_ms'] * 2)
        epoch = self.estop_epoch
        results = {}
        with self._ordinary(context):
            self._discover(context, epoch)
            for name in names:
                spec = self._config['reads'][name]
                if spec['tool'] not in results:
                    results[spec['tool']] = self._exchange(spec['tool'], {}, context, epoch)[0]
        return {name: copy.deepcopy(get_path(results[self._config['reads'][name]['tool']],
                                          self._config['reads'][name]['path'])) for name in names}

    def _stop(self, context, *, engage):
        with self._condition:
            if engage:
                self._engage_estop()
                self._latched = True
            epoch = self.estop_epoch
            self._safe = False
            self._proof = None
        result = {'performed': False, 'native': self.estop_native, 'safe_state_achieved': False}
        safety = self._config.get('safety')
        if not safety or not self._safety_lane.acquire(timeout=max(0, context.remaining_ms() / 1000)):
            return result
        try:
            # No automatic retry of ordinary effects. One protective retry is
            # allowed only after all requests that invalidated a proof retire.
            for _attempt in range(2):
                with self._condition:
                    normal_pending = any(item.lane == 'normal' for item in self._pending.values())
                    generation = self._normal_generation
                result['performed'] = True
                self._exchange(safety['command'], safety['arguments'], context, epoch, protective=True)
                value, _ident = self._exchange(safety['observe'], {}, context, epoch, protective=True)
                with self._condition, self._owner_guard() as owner:
                    achieved = ((self._owned_peer is None or owner is not None)
                                and not normal_pending and generation == self._normal_generation
                                and not self._pending and not self.closed and epoch == self.estop_epoch
                                and get_path(value, safety['path']) == safety['equals'])
                    if achieved:
                        self._debt = False
                        self._safe = True
                        self._safe_epoch = epoch
                        self._proof = self._proof_value(epoch,generation,owner)
                        result['safe_state_achieved'] = True
                        result['_proof'] = self._proof
                    if achieved or self.closed or self._pending or epoch != self.estop_epoch:
                        break
        except Exception:
            with self._condition:
                self._debt = True
                self._safe = False
                self._proof = None
        finally:
            self._safety_lane.release()
        return result

    def estop(self, reason='', ctx=None):
        result = self._stop(_context(ctx, self._config['stop_timeout_ms']), engage=True)
        result.pop('_proof', None)
        if result['performed']:
            result['estop'] = 'engaged'
        return result

    def safe_state(self, ctx=None):
        result = self.estop(ctx=ctx)
        return {'achieved': result['safe_state_achieved'], 'native': result['native']}

    def reset(self, ctx=None):
        with self._condition, self._owner_guard() as owner:
            if (self.closed or self._pending or self._debt or not self._safe
                    or (self._owned_peer is not None and owner is None)):
                raise make_mhs_error('MHS.SAFETY.SAFE_STATE_UNREACHED', 'MCP effects are not settled')
            epoch = self.estop_epoch
        result = self._stop(_context(ctx, self._config['stop_timeout_ms']), engage=False)
        with self._condition, self._owner_guard() as owner:
            if (not result['safe_state_achieved'] or result.get('_proof') != self._proof or not self._safe
                    or self._debt or self._pending or self.closed or epoch != self.estop_epoch
                    or (self._owned_peer is not None and owner is None)
                    or self._proof != self._proof_value(epoch,self._normal_generation,owner)):
                raise make_mhs_error('MHS.SAFETY.SAFE_STATE_UNREACHED', 'MCP reset lost its current proof')
            self._latched = False
        return {'reset': True}

    def safety_status(self):
        with self._condition, self._owner_guard() as owner:
            achieved = ((self._owned_peer is None or owner is not None) and self._safe and not self._debt and not self._pending and not self.closed
                        and self._safe_epoch == self.estop_epoch)
            return {'estop': {'native': self.estop_native}, 'safe_state': {'achieved': achieved},
                    'pending_mcp': len(self._pending), 'remote_uncertain': self._debt}

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
                if self._owned_peer is not None:
                    self._owned_peer.wait_retired()
            except BaseException as exc:
                self._close_error = type(exc).__name__
            finally:
                self._close_done.set()
        worker = threading.Thread(target=cleanup, name='mhs-mcp-close', daemon=True)
        try:
            worker.start()
        except BaseException as exc:
            self._close_start_error = type(exc).__name__
            if worker.ident is None:
                self._close_started = False

    def close(self):
        with self._condition:
            self._closed = True
            self._latched = True
            self._safe = False
            self._proof = None
            self._condition.notify_all()
            self._maybe_close_locked()
        if self._owned_peer is not None:
            self._owned_peer.request_close('MCP bridge closed')
