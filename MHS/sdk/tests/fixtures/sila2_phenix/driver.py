"""Full source-shaped Phenix controlled fixture, never native acceptance."""
from mhs.driver import Action, Field, Limit, Sila2Driver
from .declarations import CONFIG

CAPS = {name: 'x-cap.phenix.' + name.lower() + '.v1' for name, spec in CONFIG['members'].items()
        if spec['kind'].endswith('command') or name == 'DisplayIcon'}
ENVELOPE = Limit.operator_required('Operator must approve the exact host, plate, protocol and duration with complete motion/optical effects.')
EXAMPLES = {'Connect': {'PhenixHost': 'controlled-phenix.invalid'}, 'StageIn': {'PlateBarcode': 'plate1'},
            'StageOut': {'PlateBarcode': 'plate1'}, 'GoStandby': {'DurationSeconds': 60},
            'RunAcquisitionProtocol': {'ProtocolName': 'controlled_protocol', 'PlateBarcode': 'plate1', 'TimeoutMinutes': 1}}


def field(spec, *, effectful=False):
    types = {'Boolean': 'boolean', 'Integer': 'integer', 'Real': 'number', 'String': 'string', 'List': 'array'}
    kwargs = {'description': 'Complete declared controlled Phenix value; native device admission remains refused.'}
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
        output = {key: field(item) for key, item in spec['output'].items()} if name != 'DisplayIcon' else {
            'artifact_ref': Field('string', max_length=4096), 'media_type': Field('string', max_length=128), 'size_bytes': Field('integer')}
        if name == 'Stop':
            output = {'stopped': Field('boolean')}
        result[cap] = Action(name='phenix_' + name.lower(), description='Controlled complete ' + name + ' route; native profile refused.',
            risk='R2' if spec['effect'] == 'effectful' else 'R0', exclusive=False,
            requires_permit=spec['effect'] == 'effectful' and name != 'Stop', safe_state=name == 'Stop',
            long_running=name == 'RunAcquisitionProtocol', cancellable=name == 'RunAcquisitionProtocol',
            max_duration_ms=4000 if name == 'RunAcquisitionProtocol' else None,
            input={key: field(item, effectful=spec['effect'] == 'effectful') for key, item in spec['input'].items()},
            output=output, examples=[EXAMPLES[name]] if name in EXAMPLES else None)
    return result


class Driver(Sila2Driver):
    device_id = 'controlled_phenix'
    device_kind = 'instrument.microscope'
    mode, risk = 'hardware', 'R2'
    native = 'phenix_imager.feature_implementations.pheniximager_impl:PhenixImagerImpl'
    backends = {'fake': '.fake:connect', 'hardware': '.native:connect'}
    safe_state = 'Only the controlled peer proves fresh complete retirement; native Stop acknowledgement and cached Idle cannot certify safety.'
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


def overlay():
    limits = {}
    for name, values in EXAMPLES.items():
        limits[CAPS[name]] = {}
        for key, value in values.items():
            if type(value) is str:
                limits[CAPS[name]][key] = {'allowed': [value], 'source': 'operator'}
            else:
                limits[CAPS[name]][key] = {'min': value, 'max': value, 'source': 'operator', 'unit': CONFIG['members'][name]['input'][key]['unit']}
    return {'openmhs': '0.9', 'site': 'controlled-fixture', 'issued_by': {'id': 'operator:fixture'},
            'issued_at': '2026-11-04T00:00:00Z', 'devices': {'mhs://localhost/controlled_phenix': limits}}
