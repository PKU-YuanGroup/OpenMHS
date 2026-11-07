"""Finite SDK-only axis fixture, not an upstream driver or accepted package.

The peer supplies immediate Status completion and explicit fixture units. It
tests the stock contract, bridge and admission paths; it makes no claim about
EPICS, physical stopping or the blocked BEC package. There is no live backend.
"""
from mhs import canonical, units
from mhs.driver import Action, Field, Limit, OphydDriver

MOVE = 'x-cap.sdk-fixture.axis_move.v1'
STOP = 'x-cap.sdk-fixture.axis_stop.v1'
LIMIT = Limit.operator_required('SDK fixture envelope, never a hardware limit')
native_connect_calls = []


class Status:
    done = True
    success = True

    def wait(self, timeout=None):
        return None

    def add_callback(self, callback):
        callback(self)


class Signal:
    def __init__(self, owner, name, value):
        self.owner, self.name, self.value = owner, name, value

    def get(self, *, use_monitor=False):
        if use_monitor is not False:
            raise ValueError('fixture requires a fresh read')
        self.owner.calls.append((self.name + '.get', use_monitor))
        return self.value

    def set(self, value):
        self.owner.calls.append((self.name + '.set', value))
        self.value = value
        return Status()


class Axis:
    def __init__(self, engineering_unit):
        self.egu = engineering_unit
        self.calls = []
        self.user_readback = Signal(self, 'user_readback', 0.0)
        self.user_setpoint = Signal(self, 'user_setpoint', 0.0)
        self.velocity = Signal(self, 'velocity', 0.1)
        self.motor_done_move = Signal(self, 'motor_done_move', 1)

    def move(self, position, *, wait=False, timeout=1.0):
        if wait is not False or timeout != 1.0:
            raise ValueError('unexpected fixture invocation')
        self.calls.append(('move', position, wait, timeout))
        self.user_setpoint.value = self.user_readback.value = position
        return Status()

    def stop(self):
        self.calls.append(('stop',))
        return {'stopped': True, 'done': 1, 'position': self.user_readback.value}

    def destroy(self):
        self.calls.append(('destroy',))


def connect_fake(*, engineering_unit='mm', velocity_unit='mm/s'):
    return Axis(engineering_unit)


def connect_native(*, engineering_unit, velocity_unit, prefix):
    native_connect_calls.append((engineering_unit, velocity_unit, prefix))
    if not units.is_known(engineering_unit) or not units.is_known(velocity_unit):
        raise ValueError('explicit supported units are required')
    if not isinstance(prefix, str) or not prefix:
        raise ValueError('an explicit prefix is required')
    raise RuntimeError('SDK fixture has no live backend')


class Driver(OphydDriver):
    _needs_instance = True
    device_id = 'sdk_fixture_axis'
    device_kind = 'motion.axis'
    mode = 'hardware'
    risk = 'R2'
    native = 'sdk_fixture:Axis'
    backends = {'hardware': '.driver:connect_native', 'fake': '.driver:connect_fake'}
    safe_state = 'The controlled fixture is idle; no hardware stop is claimed.'
    native_close = 'destroy'
    parameters = {
        'position': Field('number'),
        'setpoint': Field('number'),
        'velocity': Field('number', writable=True, limit=LIMIT),
        'done': Field('integer', enum=[0, 1]),
        'engineering_unit': Field('string'),
    }
    signal_bindings = {
        name: {'signal': signal, 'get': True, 'set': name == 'velocity',
               'profile': 'classic_epics_v1', 'get_kwargs': {'use_monitor': False},
               'timeout_ms': 1000, 'source_ref': 'fixture_source.py:4'}
        for name, signal in (('position', 'user_readback'), ('setpoint', 'user_setpoint'),
                             ('velocity', 'velocity'), ('done', 'motor_done_move'))
    }
    reads = {'engineering_unit': 'egu'}
    commands = {
        MOVE: {'concurrency': 'exclusive', 'native': 'move', 'invoke': 'status', 'timeout_ms': 1000,
               'args': {'position': {'from': 'input.position'}, 'wait': {'value': False},
                        'timeout': {'value': 1.0}}, 'result': {'map': {'completed': 'output.success'}}},
        STOP: {'concurrency': 'exclusive', 'native': 'stop', 'invoke': 'call', 'timeout_ms': 1000,
               'result': {'map': {'stopped': 'output.stopped', 'done': 'output.done',
                                  'position': 'output.position'}}},
    }
    actions = {
        MOVE: Action(name='move_absolute', verb='invoke', long_running=True, cancellable=True,
                     max_duration_ms=1000, input={'position': Field('number', limit=LIMIT)},
                     output={'completed': Field('boolean')}),
        STOP: Action(name='stop_and_confirm_idle', verb='invoke', safe_state=True,
                     output={'stopped': Field('boolean'), 'done': Field('integer', enum=[1]),
                             'position': Field('number')}),
    }
    safety_bindings = {'estop': {'native': 'stop', 'invoke': 'call', 'timeout_ms': 1000}}
    unit_bindings = {
        'parameters.position': 'engineering_unit',
        'parameters.setpoint': 'engineering_unit',
        'parameters.velocity': 'velocity_unit',
        f'actions.{MOVE}.input.position': 'engineering_unit',
        f'actions.{STOP}.output.position': 'engineering_unit',
    }
    fake_unit_defaults = {'engineering_unit': 'mm', 'velocity_unit': 'mm/s'}


def overlay():
    return {'openmhs': '0.9', 'site': 'sdk-fixture', 'issued_by': {'id': 'operator:fixture'},
            'issued_at': '2026-11-04T00:00:00Z', 'devices': {
                'mhs://localhost/sdk_fixture_axis': {
                    'velocity': {'min': 0.01, 'max': 1.0, 'unit': 'mm/s', 'source': 'operator'},
                    MOVE: {'position': {'min': -1.0, 'max': 1.0, 'unit': 'mm', 'source': 'operator'}}}}}


class Client:
    """Small stock JSON-RPC client; there is no transport or native service."""
    def __init__(self, server):
        self.server, self.counter = server, 0
        self.device = next(iter(server.devices))
        self.rpc('mhs.hello', {'protocol_versions': ['1.0'],
                             'client': {'name': 'sdk-fixture', 'version': '1'}})
        self.session = self.rpc('mhs.session.open', {
            'device_ids': [self.device], 'mode': server.devices[self.device].mode, 'ttl_s': 120,
            'principal': {'id': 'sdk-fixture', 'kind': 'agent'}})['session_id']
        self.resource = server.devices[self.device].resources[0].resource_id

    def rpc(self, method, params):
        self.counter += 1
        response = self.server.handle({'jsonrpc': '2.0', 'id': self.counter,
                                       'method': method, 'params': params})
        response = response.to_dict() if hasattr(response, 'to_dict') else response
        if 'error' in response:
            raise AssertionError(response)
        return response['result']

    def command(self, capability, args=None):
        return self.rpc('mhs.command', {'session_id': self.session, 'device_id': self.device,
            'capability_id': capability, 'input': args or {}, 'command_id': canonical.ulid(),
            'deadline_ms': 2000})

    def read(self):
        return self.rpc('mhs.resource.read', {'session_id': self.session, 'device_id': self.device,
            'resource_id': self.resource, 'deadline_ms': 2000})

    def write(self, velocity):
        return self.rpc('mhs.resource.write', {'session_id': self.session, 'device_id': self.device,
            'resource_id': self.resource, 'patch': {'velocity': velocity},
            'command_id': canonical.ulid(), 'deadline_ms': 2000})
