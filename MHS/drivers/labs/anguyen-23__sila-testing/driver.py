"""PerkinElmer Opera Phenix through the PhenixImager SiLA 2 feature of gh.anguyen-23/sila-testing (Sila2Driver).

The sila2 family exemplar. The declaration is the complete feature of servers/phenix_imager/PhenixImager.sila.xml at
commit 0b572380 (declarations.py): eight commands and seven properties. Sila2Driver is configuration only and serves
a controlled peer (fake.py); every native backend refuses (native.py), so the evidence is `contract_checked` and no
SiLA server, RCI connection or Phenix is ever reached.
"""
from mhs.driver import Action, Fact, Field, Limit, Sila2Driver

from .declarations import CONFIG

FDL = 'servers/phenix_imager/PhenixImager.sila.xml'
IMPL = 'servers/phenix_imager/phenix_imager/feature_implementations/pheniximager_impl.py'
RCI = 'servers/phenix_imager/phenix_imager/rci_transport.py'

#: One extension capability per command, plus the DisplayIcon artifact (no catalogue class has these contracts).
CAPS = {name: 'x-cap.anguyen-23.' + name.lower() + '.v1' for name, spec in CONFIG['members'].items()
        if spec['kind'].endswith('command') or name == 'DisplayIcon'}
ENVELOPE = Limit.operator_required('The operator approves the exact host, plate, protocol and duration for each '
                                   'effect; no source states a deployable value.')
#: Example inputs; every value is a placeholder that the example overlay (site-limits.example.json) allows.
EXAMPLES = {'Connect': {'PhenixHost': 'phenix-controlled.invalid'}, 'StageIn': {'PlateBarcode': 'PLATE-0001'},
            'StageOut': {'PlateBarcode': 'PLATE-0001'}, 'GoStandby': {'DurationSeconds': 60},
            'RunAcquisitionProtocol': {'ProtocolName': 'BrightField_10x', 'PlateBarcode': 'PLATE-0001',
                                       'TimeoutMinutes': 1}}
DESCRIPTIONS = {
    'Connect': 'Open the RCI connection to the named Phenix host and return the device name.',
    'Disconnect': 'Close the RCI connection.',
    'StageIn': 'Move the stage from Transfer to Operate (RCI LOAD); a plate must already be on the stage.',
    'StageOut': 'Move the stage from Operate to Transfer (RCI EJECT) so the plate can be removed.',
    'Stop': 'Stop the running acquisition protocol (RCI STOP); the e-stop of this package.',
    'GoIdle': 'Return the device to Idle (RCI IDLE).',
    'GoStandby': 'Put the device into Standby for DurationSeconds before it wakes up (RCI STANDBY).',
    'RunAcquisitionProtocol': 'Run a named acquisition protocol on the plate; progress per well; ejects when done.',
    'DisplayIcon': 'Publish the instrument icon PNG as an artifact (a UI icon, not an acquired image).',
}


def field(spec, *, effectful=False):
    types = {'Boolean': 'boolean', 'Integer': 'integer', 'Real': 'number', 'String': 'string', 'List': 'array'}
    kwargs = {'description': 'Typed PhenixImager value as the FDL declares it.'}
    for name in ('unit', 'max_length', 'max_items', 'enum'):
        if name in spec:
            kwargs[name] = spec[name]
    if spec['type'] == 'List':
        kwargs['items'] = field(spec['items'])
    return Field(types[spec['type']], limit=ENVELOPE if effectful else None, **kwargs)


def actions():
    result = {}
    for name, cap in CAPS.items():
        spec = CONFIG['members'][name]
        effectful = spec['effect'] == 'effectful'
        if name == 'DisplayIcon':
            output = {'artifact_ref': Field('string', max_length=4096), 'media_type': Field('string', max_length=128),
                      'size_bytes': Field('integer')}
        elif name == 'Stop':
            output = {'stopped': Field('boolean')}
        else:
            output = {key: field(item) for key, item in spec['output'].items()}
        result[cap] = Action(name='phenix_' + name.lower(), description=DESCRIPTIONS[name],
                             risk='R2' if effectful else 'R0', exclusive=False,
                             requires_permit=effectful and name != 'Stop', safe_state=name == 'Stop',
                             long_running=name == 'RunAcquisitionProtocol',
                             cancellable=name == 'RunAcquisitionProtocol',
                             max_duration_ms=4000 if name == 'RunAcquisitionProtocol' else None,
                             input={key: field(item, effectful=effectful) for key, item in spec['input'].items()},
                             output=output, examples=[EXAMPLES[name]] if name in EXAMPLES else None)
    return result


class Driver(Sila2Driver):
    device_id = 'phenix_imager'
    device_kind = 'instrument.microscope'
    vendor = 'PerkinElmer'
    model = 'Opera Phenix (PhenixImager SiLA 2 feature)'
    mode, risk = 'hardware', 'R2'
    native = 'phenix_imager.feature_implementations.pheniximager_impl:PhenixImagerImpl'
    backends = {'fake': '.fake:connect', 'hardware': '.native:connect'}
    safe_state = ('No acquisition running, proven only by the controlled peer: after Stop, a fresh authoritative '
                  'observation must show no active execution. A native Phenix gives no such proof: its Stop is an '
                  'acknowledged RCI STOP, DeviceState is a cached status, and the stage is ejected only after a '
                  'completed run (facts.md); the stage position and the plate are left where they were.')
    sila2_config = CONFIG
    parameters = {name: field(spec['output'][name]) for name, spec in CONFIG['members'].items()
                  if spec['kind'].endswith('property') and name != 'DisplayIcon'}
    reads = {name: {'member': name, 'field': name} for name in parameters}
    parameters.update({'execution_known': Field('boolean'), 'execution_uuid': Field('string', max_length=36),
                       'acquisition_progress': Field('number'), 'last_progress_info': Field('string', max_length=4096)})
    reads.update({name: {'execution': 'RunAcquisitionProtocol', 'state': state, 'default': default}
                  for name, state, default in [('execution_known', 'known', False), ('execution_uuid', 'uuid', ''),
                                              ('acquisition_progress', 'progress', 0.0),
                                              ('last_progress_info', 'intermediate:ProgressInfo', '')]})
    commands = {cap: {'member': name} for name, cap in CAPS.items()}
    commands[CAPS['DisplayIcon']].update({'artifact': 'DisplayIcon', 'media_type': 'image/png'})
    actions = actions()
    safety_bindings = {'estop': {'member': 'Stop'}}
    facts = [
        Fact('The PhenixImager feature controls a PerkinElmer Opera Phenix high-content screening imager through its '
             'RCI (Remote Control Interface) protocol.', source='upstream_code', ref=f'{FDL}:12-18'),
        Fact('Stop is an unobservable command that stops the currently running acquisition protocol.',
             source='upstream_code', ref=f'{FDL}:103-114'),
        Fact('GoStandby takes DurationSeconds, an Integer with MinimalInclusive 60.', source='upstream_code',
             ref=f'{FDL}:136-147'),
        Fact('RunAcquisitionProtocol is observable; TimeoutMinutes is an Integer from 1 to 1440 (default 600 in its '
             'description) and ProgressInfo is its intermediate response.', source='upstream_code', ref=f'{FDL}:159-212'),
        Fact('DeviceState is a String property: Operate, Idle, Standby, Offline or Service.', source='upstream_code',
             ref=f'{FDL}:226-232'),
        Fact('StagePosition is a String property: Transfer, Operate, Service or Home.', source='upstream_code',
             ref=f'{FDL}:234-240'),
        Fact('StageMotionTimeout means that stage movement did not complete within 2 minutes.', source='upstream_code',
             ref=f'{FDL}:309-315'),
        Fact('PhenixImagerImpl starts with _simulation_mode set to True.', source='upstream_code', ref=f'{IMPL}:66'),
        Fact('In real mode, get_DeviceState returns the device_state name of the transport status, or Offline when '
             'there is no status.', source='upstream_code', ref=f'{IMPL}:158-162'),
        Fact('The RCI receive callback stores the status of every PROGRESS and STATUS reply in _status.',
             source='upstream_code', ref=f'{RCI}:287-301'),
        Fact('_require_connected raises NotConnected when the instrument is not connected.', source='upstream_code',
             ref=f'{IMPL}:78-85'),
        Fact('Disconnect requires only a connection; in simulation mode it clears the connection, sets Offline and '
             'empties the protocol list.', source='upstream_code', ref=f'{IMPL}:207-215'),
        Fact('Stop first requires a connection; in real mode it then calls the transport send_stop without an argument '
             'and returns.', source='upstream_code', ref=f'{IMPL}:263-273'),
        Fact('send_stop sends the RCI STOP command with a barcode that defaults to an empty string.',
             source='upstream_code', ref=f'{RCI}:241-243'),
        Fact('_send_command waits up to COMMAND_RESPONSE_TIMEOUT_S for a response and raises TimeoutError when none '
             'arrives.', source='upstream_code', ref=f'{RCI}:261-276'),
        Fact('_send_command_expect_ack checks only whether the reply is a REJECT; any other reply passes.',
             source='upstream_code', ref=f'{RCI}:278-285'),
        Fact('A real acquisition waits for a completion event that only a progress of 100 or more sets, for up to '
             'TimeoutMinutes, and sends EJECT only afterwards.', source='upstream_code', ref=f'{IMPL}:401-435'),
        Fact('The transport reaches the instrument on port 8213 and listens for callbacks on port 8300.',
             source='upstream_code', ref=f'{RCI}:26-27'),
        Fact('COMMAND_RESPONSE_TIMEOUT_S is 20.0 and STAGE_MOTION_TIMEOUT_S is 120.0.', source='upstream_code',
             ref=f'{RCI}:32-33'),
        Fact('connect creates the COM object RCI_DEVICELib.RCIDeviceClass through comtypes.client.',
             source='upstream_code', ref=f'{RCI}:175-178'),
        Fact('The phenix_imager server is the PerkinElmer Opera Phenix RCI wrapper (comtypes) on port 50058.',
             source='vendor_doc', ref='README.md:48'),
        Fact('All servers start in simulation mode by default; the SimulationController feature switches to real '
             'mode.', source='vendor_doc', ref='README.md:72'),
    ]
