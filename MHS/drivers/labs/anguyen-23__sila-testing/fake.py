"""Controlled Phenix peer for the fake backend; no SiLA, gRPC, COM or upstream import.

The peer answers the SDK's controlled SiLA 2 profile (`mhs-sila2-controlled-v1`): describe, observe, invoke, property,
subscribe/next/unsubscribe, result and the binary transfer operations. Its device behaviour follows the simulation
branch of the pinned PhenixImagerImpl where the package's tests touch it (servers/phenix_imager/phenix_imager/
feature_implementations/pheniximager_impl.py): Connect makes the device Idle at the Transfer position with no plate
(190-198), StageIn moves to Operate with a plate detected (224-229), StageOut moves back to Transfer and leaves the
plate detected (246-250), GoIdle and GoStandby set the state (279-292), Disconnect goes Offline and empties the
protocol list (211-215), an acquisition reports per-well progress text and returns to Transfer when complete
(341-378), and Stop ends a running acquisition and leaves the device Idle (267-270).

Differences from the upstream simulation: the peer reaches one placeholder host (the simulation accepts any), refuses
unknown protocol names (the simulation runs any), completes an acquisition on the second progress poll (the simulation
images 96 wells at 0.1 s each), and refuses every command except Stop while an acquisition runs. The upstream accepts
them, Disconnect included (pheniximager_impl.py:207-215 checks only the connection), after which Stop raises
NotConnected (:263-265, 78-85): a run that another client disconnected cannot be stopped through the feature.
foreign_disconnect() models that path for the tests.

The describe/observe envelopes are the SDK's controlled test contract; the native Phenix offers no equivalent: its
Stop is an acknowledged RCI command and its DeviceState a cached value (facts.md). Every number and string below is
test data, marked `# placeholder`; none is a Phenix fact, range or timing.
"""
import copy
import hashlib
import struct
import threading
import uuid
import zlib

from .declarations import CONFIG

HOST = 'phenix-controlled.invalid'  # placeholder: the one host this peer reaches (RFC 2606 .invalid)
DEVICE_NAME = 'Opera Phenix (Simulated)'  # placeholder: the simulation's Connect reply text (impl :192)
PROTOCOLS = ['BrightField_10x', 'Confocal_40x_3ch']  # placeholder: two names of the simulation list (impl :45-51)
DESCRIPTION = 'PerkinElmer Opera Phenix high-content screening imager (controlled fake; no optics).'  # placeholder
LIFETIME_S = 30  # placeholder: execution lifetime the peer reports


def _png():
    """A 2 x 1 RGB PNG built in memory; a placeholder for the 64 KiB-bounded DisplayIcon, not the upstream icon.png."""
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 1, 8, 2, 0, 0, 0))  # placeholder
            + chunk(b'IDAT', zlib.compress(b'\x00\x10\x20\x30\x40\x50\x60')) + chunk(b'IEND', b''))  # placeholder


class PhenixPeer:
    """Fake Phenix server. Options select the negative controls the tests use:

    ack_only    Stop is acknowledged but changes nothing (the native RCI STOP is acknowledgement-only);
    cached_idle DeviceState always reads Idle and observe is not authoritative (the native cached status);
    stale_idle  DeviceState always reads Idle while observe stays authoritative;
    auto_complete False keeps an acquisition running until Stop; chunked serves the icon as a binary transfer.
    """

    def __init__(self, *, auto_complete=True, ack_only=False, cached_idle=False, stale_idle=False, chunked=False,
                 config=None):
        self.config = copy.deepcopy(CONFIG if config is None else config)
        self.auto_complete, self.ack_only, self.cached_idle, self.chunked = auto_complete, ack_only, cached_idle, chunked
        self.stale_idle = stale_idle
        self.connected = False
        self.ever_connected = False
        self.device_state = 'Offline'
        self.stage = 'Transfer'
        self.plate = False
        self.protocols = []
        self.active = False
        self.closed = False
        self.requests = []
        self.jobs = {}
        self.streams = {}
        self.binaries = {}
        self.retired = set()
        self.blocks = {}
        self.sequence = 0
        self.icon = _png()
        self.started = threading.Event()
        self.finished = threading.Event()
        self._lock = threading.RLock()

    def block(self, point):
        events = threading.Event(), threading.Event()
        self.blocks[point] = events
        return events

    def _barrier(self, point):
        pair = self.blocks.get(point)
        if pair:
            pair[0].set()
            pair[1].wait()

    def _error(self, name):
        return {'error': {'kind': 'defined', 'identifier': name, 'message': 'controlled device error'}}

    def request(self, message, *, timeout_ms):
        operation, member = message['operation'], message['member']
        key = operation + (':' + member if member else '')
        self._barrier('before:' + key)
        with self._lock:
            if self.closed:
                raise RuntimeError('peer is closed')
            self.requests.append(copy.deepcopy(message))
            reply = {key: message[key] for key in ('request_id', 'owner_id', 'generation', 'feature', 'member', 'operation')}
            result = self._dispatch(message)
            reply.update(result)
        self._barrier('after:' + key)
        return reply

    def _dispatch(self, message):
        operation, member, data, owner = message['operation'], message['member'], message['payload'], message['owner_id']
        if operation == 'describe':
            return {'payload': {'runtime_profile': self.config['runtime_profile'], 'descriptor_sha256': self.config['fdl']['sha256'],
                                'proto_sha256': self.config['proto']['sha256'], 'members': copy.deepcopy(self.config['members']),
                                'retirement_contract': 'controlled-only-v1'}}
        if operation == 'observe':
            self.sequence += 1
            return {'payload': {'sequence': self.sequence, 'authoritative': not self.cached_idle,
                                'quiescent': self.ever_connected and not self.active,
                                'retired_owners': sorted(self.retired),
                                'active_executions': [ident for ident, job in self.jobs.items() if job['active']]}}
        if operation == 'invoke':
            return self._invoke(member, data['input'], owner)
        if operation == 'property':
            stale = self.cached_idle or self.stale_idle
            values = {'IsConnected': self.connected, 'DeviceState': 'Idle' if stale else self.device_state,
                      'StagePosition': self.stage, 'PlateDetected': self.plate,
                      'AvailableProtocols': list(self.protocols), 'DeviceDescription': DESCRIPTION}
            if member == 'DisplayIcon':
                if self.chunked:
                    ident = str(uuid.uuid4())
                    self.binaries[ident] = {'data': self.icon, 'owner': owner}
                    value = {'binary_uuid': ident, 'size_bytes': len(self.icon), 'sha256': hashlib.sha256(self.icon).hexdigest()}
                else:
                    value = self.icon
            else:
                value = values[member]
            return {'payload': {member: value}}
        if operation == 'subscribe':
            ident = str(uuid.uuid4())
            self.streams[ident] = {'owner': owner, 'kind': data['kind'], 'execution_uuid': data['execution_uuid'],
                                   'sequence': -1, 'closed': False, 'member': member}
            return {'payload': {'stream_id': ident}}
        if operation == 'next':
            return self._next(message, data, owner)
        if operation == 'unsubscribe':
            stream = self.streams[data['stream_id']]
            if data['stream_owner'] != stream['owner']:
                raise ValueError('wrong stream closure owner')
            stream['closed'] = True
            return {'payload': {'closed': True}}
        if operation == 'result':
            job = self.jobs[data['execution_uuid']]
            if job['owner'] != owner:
                raise ValueError('foreign result')
            if job['active']:
                return {'error': {'kind': 'framework', 'identifier': 'COMMAND_EXECUTION_NOT_FINISHED', 'message': 'still active'}}
            if job['status'] != 2:
                return self._error('DeviceError')  # the simulation raises DeviceError when stopped (impl :355-357)
            return {'payload': {'Status': "Acquisition '" + job['input']['ProtocolName'] + "' completed successfully"}}
        if operation in ('binary_info', 'binary_chunk', 'binary_delete'):
            ident = data['binary_uuid']
            binary = self.binaries[ident]
            if binary['owner'] != data.get('binary_owner', owner):
                raise ValueError('foreign binary')
            value = binary['data']
            if operation == 'binary_info':
                return {'payload': {'binary_uuid': ident, 'size_bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}}
            if operation == 'binary_chunk':
                return {'payload': {'offset': data['offset'], 'data': value[data['offset']:data['offset'] + data['length']]}}
            self.binaries.pop(ident)
            return {'payload': {'deleted': True}}
        raise ValueError('unknown controlled operation')

    def _invoke(self, member, values, owner):
        if member == 'Connect':
            if values['PhenixHost'] != HOST:
                return self._error('CommunicationError')  # an unreachable host (impl :200-203)
            self.connected, self.device_state, self.stage, self.plate = True, 'Idle', 'Transfer', False
            self.protocols = list(PROTOCOLS)
            self.ever_connected = True
            self.retired.add(owner)
            return {'payload': {'DeviceName': DEVICE_NAME}}
        if not self.connected:
            return self._error('NotConnected')  # every other command needs a connection (impl :78-85)
        if member == 'RunAcquisitionProtocol':
            if self.active or values['ProtocolName'] not in self.protocols:
                return self._error('DeviceError')  # placeholder: a busy device or an unknown protocol is refused
            self.active, self.stage, self.device_state, self.plate = True, 'Operate', 'Operate', True
            ident = str(uuid.uuid4())
            self.jobs[ident] = {'owner': owner, 'active': True, 'status': 1, 'step': 0, 'input': copy.deepcopy(values)}
            self.started.set()
            return {'payload': {'execution_uuid': ident, 'lifetime': {'seconds': LIFETIME_S, 'nanos': 0}}}
        if member == 'Stop':
            if not self.ack_only:
                self.active = False
                self.device_state = 'Idle'
                for job in self.jobs.values():
                    if job['active']:
                        job['active'], job['status'] = False, 3
                        self.retired.add(job['owner'])
                self.finished.set()
            return {'payload': {}}
        if self.active:
            return self._error('DeviceError')  # placeholder: no other command while an acquisition runs
        if member == 'StageIn':
            self.stage, self.plate, self.device_state = 'Operate', True, 'Idle'
        elif member == 'StageOut':
            self.stage, self.device_state = 'Transfer', 'Idle'  # the plate stays detected until it is removed
        elif member == 'GoIdle':
            self.device_state = 'Idle'
        elif member == 'GoStandby':
            self.device_state = 'Standby'
        elif member == 'Disconnect':
            self.connected, self.device_state, self.protocols = False, 'Offline', []
        else:
            raise ValueError('unknown controlled command')
        self.retired.add(owner)
        return {'payload': {}}

    def _next(self, message, data, owner):
        stream = self.streams[data['stream_id']]
        if stream['owner'] != owner or stream['closed']:
            raise ValueError('stream owner mismatch or closed')
        stream['sequence'] += 1
        if stream['kind'] == 'property':
            prop = self._dispatch({**message, 'operation': 'property'})['payload']
            return {'payload': {'sequence': stream['sequence'], 'items': [prop], 'end': False}}
        job = self.jobs[stream['execution_uuid']]
        if stream['kind'] == 'info':
            job['step'] += 1
            if self.auto_complete and job['active'] and job['step'] >= 2:  # placeholder: completes on the second poll
                self.complete(stream['execution_uuid'])
            progress = 1.0 if not job['active'] else .25  # placeholder
            item = {'execution_uuid': stream['execution_uuid'], 'status': job['status'], 'progress': progress,
                    'remaining': None, 'lifetime': {'seconds': LIFETIME_S, 'nanos': 0}}
        else:
            item = {'ProgressInfo': 'Well R1C1 - ' + ('25%' if job['active'] else '100%')}  # placeholder text
        return {'payload': {'sequence': stream['sequence'], 'items': [item], 'end': not job['active']}}

    def complete(self, ident):
        with self._lock:
            job = self.jobs[ident]
            job['active'], job['status'] = False, 2
            self.active, self.device_state, self.stage = False, 'Idle', 'Transfer'
            self.retired.add(job['owner'])
            self.finished.set()

    def foreign_disconnect(self):
        """Another client of the same server disconnects; the upstream accepts it even while an acquisition runs."""
        with self._lock:
            self.connected, self.device_state, self.protocols = False, 'Offline', []

    def close(self):
        self._barrier('before:close')
        with self._lock:
            self.closed = True
            for stream in self.streams.values():
                stream['closed'] = True
            self.binaries.clear()


def connect(lease, **options):
    """Fake backend factory: register the peer with its PeerLease before any setup, then return it."""
    peer = PhenixPeer(**options)
    lease.register(peer)
    return peer
