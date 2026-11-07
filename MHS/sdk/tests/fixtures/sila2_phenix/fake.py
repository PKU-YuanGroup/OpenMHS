"""Original controlled peer, with explicit unsafe schedules. No SiLA import.

The describe/observe/stream envelopes are the SDK's controlled test contract;
they are not endpoints supplied by the native Phenix server.
"""
import copy
import hashlib
import struct
import threading
import uuid
import zlib

from .declarations import CONFIG


def _png():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 1, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b'\x00\x10\x20\x30\x40\x50\x60')) + chunk(b'IEND', b'')


class PhenixPeer:
    def __init__(self, *, auto_complete=True, ack_only=False, cached_idle=False, chunked=False, config=None):
        self.config = copy.deepcopy(CONFIG if config is None else config)
        self.auto_complete, self.ack_only, self.cached_idle, self.chunked = auto_complete, ack_only, cached_idle, chunked
        self.connected = False
        self.ever_connected = False
        self.device_state = 'Offline'
        self.stage = 'Transfer'
        self.plate = False
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
                                'proto_sha256': self.config['proto']['sha256'], 'members': copy.deepcopy(self.config['members']), 'retirement_contract': 'controlled-only-v1'}}
        if operation == 'observe':
            self.sequence += 1
            return {'payload': {'sequence': self.sequence, 'authoritative': not self.cached_idle,
                                'quiescent': self.ever_connected and not self.active,
                                'retired_owners': sorted(self.retired),
                                'active_executions': [ident for ident, job in self.jobs.items() if job['active']]}}
        if operation == 'invoke':
            values = data['input']
            if member == 'Connect':
                if values['PhenixHost'] != 'controlled-phenix.invalid':
                    return self._error('CommunicationError')
                self.connected, self.device_state = True, 'Idle'
                self.ever_connected = True
                self.retired.add(owner)
                return {'payload': {'DeviceName': 'Controlled Phenix'}}
            if not self.connected:
                return self._error('NotConnected')
            if member == 'RunAcquisitionProtocol':
                if self.active or values['ProtocolName'] != 'controlled_protocol':
                    return self._error('DeviceError')
                self.active, self.stage, self.device_state, self.plate = True, 'Operate', 'Operate', True
                ident = str(uuid.uuid4())
                self.jobs[ident] = {'owner': owner, 'active': True, 'status': 1, 'step': 0, 'input': copy.deepcopy(values)}
                self.started.set()
                return {'payload': {'execution_uuid': ident, 'lifetime': {'seconds': 30, 'nanos': 0}}}
            if member == 'Stop':
                if not self.ack_only:
                    self.active = False
                    self.device_state = 'Idle'
                    for job in self.jobs.values():
                        job['active'], job['status'] = False, 3
                        self.retired.add(job['owner'])
                    self.finished.set()
                return {'payload': {}}
            if self.active:
                return self._error('DeviceError')
            if member == 'StageIn':
                self.stage, self.plate = 'Operate', True
            elif member == 'StageOut':
                self.stage, self.plate = 'Transfer', False
            elif member == 'GoIdle':
                self.device_state = 'Idle'
            elif member == 'GoStandby':
                self.device_state = 'Standby'
            elif member == 'Disconnect':
                self.connected, self.device_state = False, 'Offline'
            else:
                raise ValueError('unknown controlled command')
            self.retired.add(owner)
            return {'payload': {}}
        if operation == 'property':
            values = {'IsConnected': self.connected, 'DeviceState': 'Idle' if self.cached_idle else self.device_state,
                      'StagePosition': self.stage, 'PlateDetected': self.plate,
                      'AvailableProtocols': ['controlled_protocol'], 'DeviceDescription': 'Original controlled test imager; no optics or timing fidelity.'}
            if member == 'DisplayIcon':
                if self.chunked:
                    ident = str(uuid.uuid4()); self.binaries[ident] = {'data': self.icon, 'owner': owner}
                    value = {'binary_uuid': ident, 'size_bytes': len(self.icon), 'sha256': hashlib.sha256(self.icon).hexdigest()}
                else:
                    value = self.icon
            else:
                value = values[member]
            return {'payload': {member: value}}
        if operation == 'subscribe':
            ident = str(uuid.uuid4())
            self.streams[ident] = {'owner': owner, 'kind': data['kind'], 'execution_uuid': data['execution_uuid'], 'sequence': -1, 'closed': False, 'member': member}
            return {'payload': {'stream_id': ident}}
        if operation == 'next':
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
                if self.auto_complete and job['active'] and job['step'] >= 2:
                    self.complete(stream['execution_uuid'])
                progress = 1.0 if not job['active'] else .25
                item = {'execution_uuid': stream['execution_uuid'], 'status': job['status'], 'progress': progress,
                        'remaining': None, 'lifetime': {'seconds': 30, 'nanos': 0}}
            else:
                item = {'ProgressInfo': 'Well R1C1 - ' + ('25%' if job['active'] else '100%')}
            return {'payload': {'sequence': stream['sequence'], 'items': [item], 'end': not job['active']}}
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
                return self._error('DeviceError')
            return {'payload': {'Status': 'Acquisition complete; stage ejected'}}
        if operation in ('binary_info', 'binary_chunk', 'binary_delete'):
            ident = data['binary_uuid']; binary = self.binaries[ident]
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

    def complete(self, ident):
        with self._lock:
            job = self.jobs[ident]
            job['active'], job['status'] = False, 2
            self.active, self.device_state, self.stage, self.plate = False, 'Idle', 'Transfer', False
            self.retired.add(job['owner'])
            self.finished.set()

    def close(self):
        self._barrier('before:close')
        with self._lock:
            self.closed = True
            for stream in self.streams.values():
                stream['closed'] = True
            self.binaries.clear()


def connect(lease, **options):
    peer = PhenixPeer(**options)
    lease.register(peer)
    return peer
