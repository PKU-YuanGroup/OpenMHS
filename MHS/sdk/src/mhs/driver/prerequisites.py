"""Finite fake-only gate prerequisites, executed as visible stock commands.

The first profile is one explicit Connect for the complete controlled Phenix
fixture. This is test preparation, never driver initialization or safety proof.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import json
import time

from .behaviour import Session
from .build import hardware_device_id
from .sila2 import Sila2Driver
from .sila2_check import SOURCE_COMMIT, prove_profile
from .sila2_config import canonical, plain, validate_fields

FILE = 'fixtures/gate-prerequisites.json'
PROFILE = 'sila2-controlled-phenix-connect-v1'
# Public immutable integers are covered by the existing gate fingerprint;
# private integers are reserved for runtime counters in that mechanism.
MAX_FILE_BYTES = 16384
MAX_INPUT_BYTES = 1024
COMMAND_TIMEOUT_MS = 500
TOTAL_TIMEOUT_MS = 1000


@dataclass(frozen=True)
class Prerequisite:
    capability_id: str
    host: str
    cases: frozenset[str]
    hardware_id: str
    setup_rule: str


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate prerequisite JSON key')
        result[key] = value
    return result


def load(ctx):
    path = ctx.dir / FILE
    if not path.is_file():
        return None
    with path.open('rb') as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError('prerequisite document exceeds the gate budget')
    document = json.loads(data, object_pairs_hook=_object)
    plain(document)
    if type(document) is not dict or set(document) != {'profile', 'connect', 'cases'} or document['profile'] != PROFILE:
        raise ValueError('only the finite reviewed controlled Phenix prerequisite profile is supported')
    if ctx.backend != 'fake' or not isinstance(ctx.cls, type) or not issubclass(ctx.cls, Sila2Driver):
        raise ValueError('prerequisites require the controlled fake SiLA family; native/other profiles are refused')
    config = Sila2Driver.bridge_config.__func__(ctx.cls, ctx.model.resource_id)
    prove_profile(ctx.tree, ctx.cls.native, config)
    if not ctx.synthetic and ctx.commit != SOURCE_COMMIT:
        raise ValueError('prerequisite task pin differs from the complete source profile')
    members = config['members']
    mapped = {}
    for capability, binding in config['commands'].items():
        member = binding['member']
        if member in mapped:
            raise ValueError('prerequisite profile forbids duplicate command routes')
        mapped[member] = capability
    expected = {name for name, spec in members.items() if spec['kind'].endswith('command')} | {'DisplayIcon'}
    reads = {item['member'] for item in config['reads'].values() if 'member' in item}
    if set(mapped) != expected or reads != {name for name, spec in members.items() if spec['kind'].endswith('property')} - {'DisplayIcon'}:
        raise ValueError('prerequisite profile must retain all eight commands and seven primary properties')
    command = document['connect']
    if type(command) is not dict or set(command) != {'capability_id', 'input'} or command['capability_id'] != mapped['Connect']:
        raise ValueError('only the declared Connect command may prepare this profile')
    payload = command['input']
    if len(canonical(payload)) > MAX_INPUT_BYTES:
        raise ValueError('prerequisite input exceeds the gate budget')
    validate_fields(members['Connect']['input'], payload, profile=config['runtime_profile'])
    action = ctx.cls.actions[mapped['Connect']]
    if not action.requires_permit or action.long_running or action.cancellable or action.safe_state:
        raise ValueError('Connect must remain a permit-bound finite ordinary action')
    cases = document['cases']
    required = set(mapped.values()) - {mapped['Connect']} | {'safety'}
    if type(cases) is not list or any(type(item) is not str for item in cases) or len(cases) != len(set(cases)) or set(cases) != required:
        raise ValueError('prerequisite cases must be the complete finite non-Connect surface plus safety')
    overlay = ctx.example_overlay
    device = hardware_device_id(ctx.model)
    try:
        rule = overlay['devices'][device][mapped['Connect']]
    except (KeyError, TypeError):
        raise ValueError('the explicit Connect prerequisite requires its narrow example overlay') from None
    plain(rule)
    if type(rule) is not dict or set(rule) != {'PhenixHost'}:
        raise ValueError('prerequisite overlay must name only the original Connect host input')
    return Prerequisite(mapped['Connect'], payload['PhenixHost'], frozenset(cases), device,
                        json.dumps(rule, sort_keys=True, separators=(',', ':')))


def overlay(plan, existing):
    """Add only Connect's declared rule; never fill a dependent negative input."""
    result = copy.deepcopy(existing) if existing is not None else {
        'openmhs': '0.9', 'site': 'explicit controlled gate prerequisite', 'devices': {}}
    plain(result)
    if type(result) is not dict or type(result.get('devices')) is not dict:
        raise ValueError('prerequisite overlay requires the normal closed site-limits shape')
    device = result['devices'].setdefault(plan.hardware_id, {})
    rule = json.loads(plan.setup_rule)
    if plan.capability_id in device and canonical(device[plan.capability_id]) != canonical(rule):
        raise ValueError('prerequisite overlay conflicts with the supplied Connect limits')
    device[plan.capability_id] = rule
    return result


def execute(server, plan):
    """Prepare one already-owned simulated server; never own/close its Driver.

    The separate session is always ended. A pending/unknown command is a
    failure, including when normal session cleanup requests cancellation.
    No ready readback is used as a stop, reset or retirement proof.
    """
    if len(server.devices) != 1 or server.strict is not True:
        raise ValueError('prerequisites require one strict controlled endpoint')
    device = next(iter(server.devices.values()))
    if device.mode != 'simulated':
        raise ValueError('prerequisites never issue approvals on a hardware-view session')
    start = time.monotonic()
    session = Session(server, device.device_id)
    record = {'profile': PROFILE, 'session_id': session.session_id}
    primary_error = None
    try:
        receipt = session.command(plan.capability_id, {'PhenixHost': plan.host},
                                  deadline_ms=COMMAND_TIMEOUT_MS, wait=False, test_permit=True)
        record['receipt'] = copy.deepcopy(receipt)
        if receipt.get('status') != 'completed':
            raise ValueError('Connect prerequisite did not complete; later gate cases are refused')
        if time.monotonic() - start >= TOTAL_TIMEOUT_MS / 1000:
            raise ValueError('Connect prerequisite exhausted its total gate budget')
        state = session.rpc('mhs.resource.read', {'session_id': session.session_id, 'device_id': device.device_id,
            'resource_id': session.resource_id, 'fields': ['IsConnected'], 'deadline_ms': COMMAND_TIMEOUT_MS})
        record['readback'] = copy.deepcopy(state)
        if (state.get('state') or {}).get('IsConnected') is not True:
            raise ValueError('Connect prerequisite did not establish its declared connected state')
        if time.monotonic() - start >= TOTAL_TIMEOUT_MS / 1000:
            raise ValueError('Connect prerequisite exhausted its total gate budget')
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        try:
            closed = session.rpc('mhs.session.close', {'session_id': session.session_id})
            record['session_close'] = copy.deepcopy(closed)
            if not primary_error and (closed.get('summary') or {}).get('cancellation_pending'):
                raise ValueError('Connect prerequisite retained a pending operation at session close')
        except BaseException:
            if primary_error is None:
                raise
    record['elapsed_ms'] = (time.monotonic() - start) * 1000
    if record['elapsed_ms'] >= TOTAL_TIMEOUT_MS:
        raise ValueError('Connect prerequisite exhausted its total gate budget during session close')
    return record
