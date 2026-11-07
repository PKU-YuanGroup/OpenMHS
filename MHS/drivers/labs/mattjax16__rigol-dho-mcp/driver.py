"""Rigol DHO800/DHO900 oscilloscope through the pinned rigol-dho-mcp FastMCP server.

A config-only McpClientDriver. The thirteen default tools of rigol_dho_mcp/server.py
become sixteen finite bindings; the optional raw-SCPI tool stays unexposed. The source
file is read as text by the gate and never imported. The fake backend is the controlled
MCP peer in fake.py. Every hardware construction refuses before any import, process
start or connection, so the evidence stays contract_checked.
"""
from mhs.driver import Action, Fact, Field, Limit, McpClientDriver

SOURCE = 'rigol_dho_mcp/server.py'
PIN = 'f9ac7191869845ae46ca714de69a877c388b2530'
SHA = 'c2daec52a875c1eb910606695dab71af6d160d731ac7a14dc1437911e5651190'
OWNER = 'mattjax16'
MEASUREMENTS = ['VMAX', 'VMIN', 'VPP', 'VTOP', 'VBASe', 'VAMP', 'VAVG', 'VRMS', 'OVERshoot', 'PREShoot',
                'MARea', 'MPARea', 'PERiod', 'FREQuency', 'RTIMe', 'FTIMe', 'PWIDth', 'NWIDth', 'PDUTy', 'NDUTy',
                'TVMAX', 'TVMIN', 'PSLewrate', 'NSLewrate', 'VUPPer', 'VMID', 'VLOWer', 'VARiance', 'PVRMS',
                'PPULses', 'NPULses', 'PEDGes', 'NEDGes']
BETWEEN = ['RRDelay', 'RFDelay', 'FRDelay', 'FFDelay', 'RRPHase', 'RFPHase', 'FRPHase', 'FFPHase']
CURSOR_SOURCES = ['CHAN1', 'CHAN2', 'CHAN3', 'CHAN4', 'MATH1', 'MATH2', 'MATH3', 'MATH4']
TRIGGER_SOURCES = ['CHAN1', 'CHAN2', 'CHAN3', 'CHAN4', 'EXT', 'ACL'] + ['D' + str(i) for i in range(16)]
TOOL_NAMES = ('identify', 'get_status', 'run_control', 'configure_channel', 'configure_timebase',
              'configure_trigger_edge', 'configure_acquisition', 'configure_cursors', 'get_cursor_values',
              'get_measurement', 'measure_between', 'get_waveform', 'get_screenshot')
CAPS = {name: 'x-cap.' + OWNER + '.' + name + '.v1' for name in TOOL_NAMES}


def operator_limit():
    return Limit.operator_required('No pinned source line bounds this value; the operator approves a finite range.')


def text(**kwargs):
    return Field('string', max_length=256, **kwargs)


def strings(names):
    return {name: text() for name in names.split()}


def optional_enum(values):
    return Field('string', enum=values, required=False, nullable=True)


def numeric(unit=None, integer=False):
    return Field('integer' if integer else 'number', unit=unit, required=False, nullable=True, limit=operator_limit())


def channel(limit, required=False):
    # The FastMCP signature itself bounds each channel index: Field(ge=1, le=4) on the cited line.
    return Field('integer', unit='1', required=required, limit=limit)


def schema(fields):
    properties = {name: field.to_schema() for name, field in fields.items()}
    for name, field in fields.items():
        if field.nullable and field.enum is not None:
            properties[name]['enum'].append(None)
    return {'type': 'object', 'properties': properties,
            'required': [name for name, field in fields.items() if field.required is not False],
            'additionalProperties': False}


CHANNEL = {'enabled': Field('boolean'), **{name: text(required=False) for name in (
    'scale_V_per_div', 'offset_V', 'coupling', 'probe_ratio', 'bandwidth_limit')}}
STATUS = {**strings('trigger_status sample_rate_Sa_per_s memory_depth acquisition_type '
                    'timebase_scale_s_per_div timebase_offset_s'),
          'trigger': Field('object', properties=strings('mode sweep')),
          'channels': Field('object', properties={'CH' + str(ch): Field('object', properties=CHANNEL, required=False)
                                                  for ch in range(1, 5)})}
# Tool inputs exactly as the pinned FastMCP signatures declare them (server.py:148-593).
INPUTS = {
    'identify': {}, 'get_status': {},
    'run_control': {'action': Field('string', enum=['run', 'stop', 'single', 'autoset', 'clear', 'force_trigger'])},
    'configure_channel': {'channel': channel(Limit(1, 4, source='upstream_code', ref=f'{SOURCE}:230'), True),
                          'enabled': Field('boolean', required=False, nullable=True),
                          'scale': numeric('V'), 'offset': numeric('V'), 'coupling': optional_enum(['AC', 'DC', 'GND']),
                          'probe_ratio': numeric(), 'bandwidth_limit': optional_enum(['OFF', '20M']),
                          'invert': Field('boolean', required=False, nullable=True)},
    'configure_timebase': {'scale': numeric('s'), 'offset': numeric('s')},
    'configure_trigger_edge': {'source': optional_enum(TRIGGER_SOURCES),
                               'slope': optional_enum(['POSitive', 'NEGative', 'RFALl']),
                               'level': numeric('V'), 'sweep': optional_enum(['AUTO', 'NORMal', 'SINGle'])},
    'configure_acquisition': {'memory_depth': optional_enum(['AUTO', '1k', '10k', '100k', '1M', '5M', '10M', '25M', '50M']),
                              'acq_type': optional_enum(['NORMal', 'AVERages', 'PEAK', 'ULTRa']),
                              'averages': numeric(integer=True)},
    'configure_cursors': {'mode': Field('string', enum=['OFF', 'MANual', 'TRACk'], required=False),
                          'cursor_type': optional_enum(['TIME', 'AMPLitude']), 'source': optional_enum(CURSOR_SOURCES),
                          'position_a': numeric(), 'position_b': numeric(),
                          'track_source_a': optional_enum(CURSOR_SOURCES), 'track_source_b': optional_enum(CURSOR_SOURCES)},
    'get_cursor_values': {},
    'get_measurement': {'item': Field('string', enum=MEASUREMENTS),
                        'channel': channel(Limit(1, 4, source='upstream_code', ref=f'{SOURCE}:443'))},
    'measure_between': {'item': Field('string', enum=BETWEEN),
                        'source_a': channel(Limit(1, 4, source='upstream_code', ref=f'{SOURCE}:478')),
                        'source_b': channel(Limit(1, 4, source='upstream_code', ref=f'{SOURCE}:479'))},
    'get_waveform': {'channel': channel(Limit(1, 4, source='upstream_code', ref=f'{SOURCE}:512')),
                     'mode': Field('string', enum=['screen', 'memory'], required=False),
                     'max_points': Field('integer', required=False,
                                         limit=Limit(10, 10000, source='upstream_code', ref=f'{SOURCE}:517')),
                     'include_data': Field('boolean', required=False)},
    'get_screenshot': {},
}
INPUT_DESCRIPTIONS = {
    'action': 'Acquisition control: run, stop, single, autoset, clear or force_trigger.',
    'channel': 'Analog channel index, 1 through 4.', 'enabled': 'Show or hide this analog channel.',
    'scale': 'Scale per display division in the stated unit (V or s).', 'offset': 'Offset in the stated unit (V or s).',
    'coupling': 'Analog input coupling.', 'probe_ratio': 'Dimensionless probe attenuation ratio.',
    'bandwidth_limit': 'Bandwidth limit token, OFF or 20M.', 'invert': 'Set channel inversion; the tool returns no inversion readback.',
    'source': 'Trigger or cursor source token.', 'slope': 'Edge trigger slope token.',
    'level': 'Trigger level in volts.', 'sweep': 'Trigger sweep token.',
    'memory_depth': 'Acquisition memory depth token.', 'acq_type': 'Acquisition type token.',
    'averages': 'Average count for AVERages mode; the operator overlay bounds it.',
    'mode': 'Cursor mode or waveform mode, as the enum lists.',
    'cursor_type': 'Manual cursor axis: TIME (seconds) or AMPLitude (volts); omitted keeps the current type.',
    'position_a': 'Cursor A coordinate; seconds for TIME, volts for AMPLitude.',
    'position_b': 'Cursor B coordinate; seconds for TIME, volts for AMPLitude.',
    'track_source_a': 'Waveform that track cursor A follows.', 'track_source_b': 'Waveform that track cursor B follows.',
    'item': 'Measurement item; values in SI units, phases in degrees.',
    'source_a': 'First analog channel index, 1 through 4.', 'source_b': 'Second analog channel index, 1 through 4.',
    'max_points': 'Decimation target 10 to 10000; floor decimation can return more points.',
    'include_data': 'Return every decimated time/voltage sample; false returns statistics only.',
}
for _fields in INPUTS.values():
    for _key, _field in _fields.items():
        _field.description = INPUT_DESCRIPTIONS[_key]
        if _key in ('probe_ratio', 'averages', 'max_points'):
            _field.unit = '1'
OUTPUTS = {
    'identify': {'text': text()}, 'get_status': STATUS, 'run_control': {'text': text()},
    'configure_channel': {'channel': Field('integer'), 'enabled': Field('boolean'),
                          **strings('scale_V_per_div offset_V coupling probe_ratio bandwidth_limit')},
    'configure_timebase': strings('scale_s_per_div offset_s'),
    'configure_trigger_edge': strings('mode source slope level_V sweep status'),
    'configure_acquisition': strings('memory_depth type averages sample_rate_Sa_per_s'),
    'configure_cursors': strings('mode'),
    'get_cursor_values': {'artifact_ref': text(), 'media_type': Field('string', enum=['application/json'])},
    'get_measurement': {'item': Field('string', enum=MEASUREMENTS), 'channel': Field('integer'),
                        'value': Field('number'), 'invalid': Field('boolean')},
    'measure_between': {'item': Field('string', enum=BETWEEN), 'source_a': Field('integer'), 'source_b': Field('integer'),
                        'value': Field('number'), 'invalid': Field('boolean')},
    'get_waveform': {'artifact_ref': text(), 'media_type': Field('string', enum=['application/json'])},
    'get_screenshot': {'image_ref': text(), 'media_type': Field('string', enum=['image/png']),
                       'width': Field('integer'), 'height': Field('integer')},
}
CURSOR_VALUES = strings('ax ay bx by delta_x delta_y inverse_delta_x')
# get_cursor_values returns one of three shapes, chosen by the active cursor mode (server.py:404-432).
CURSOR_SCHEMA = {'anyOf': [
    schema({'mode': Field('string', enum=['MANual']), **strings('type source'), **CURSOR_VALUES}),
    schema({'mode': Field('string', enum=['TRACk']), **strings('source_a source_b'), **CURSOR_VALUES}),
    schema({'mode': Field('string', enum=['OFF']), 'note': text()}),
]}
# get_waveform returns statistics only, or statistics plus the decimated arrays (server.py:560-584).
WAVE_BASE = {'channel': Field('integer'), 'mode': Field('string', enum=['screen', 'memory']),
             'points_captured': Field('integer'), 'dt_s': Field('number'), 't0_s': Field('number'),
             'sample_rate_Sa_per_s': Field('number', nullable=True),
             'stats': Field('object', properties={key: Field('number')
                                                  for key in ['vmin_V', 'vmax_V', 'vpp_V', 'vavg_V', 'vrms_V']})}
WAVE_ARRAYS = {'decimation_factor': Field('integer'), 'points_returned': Field('integer'),
               'time_s': Field('array', items=Field('number'), max_items=20000),
               'voltage_V': Field('array', items=Field('number'), max_items=20000)}
WAVE_SCHEMA = {'anyOf': [schema(WAVE_BASE), schema({**WAVE_BASE, **WAVE_ARRAYS})]}
# The def line of each registered tool function (each follows its @mcp.tool() decorator).
LINES = dict(zip(TOOL_NAMES, [148, 158, 199, 229, 269, 287, 316, 345, 396, 441, 476, 511, 593]))
# Tools that write to the instrument. get_measurement and measure_between select the item with a
# write before they query it (server.py:454, 493); get_waveform writes its source and mode (527-529).
EFFECTS = set(TOOL_NAMES) - {'identify', 'get_status', 'get_cursor_values', 'get_screenshot'}
# The literal defaults of every optional argument, as the source signatures write them.
DEFAULTS = {name: {key: None for key, field in fields.items() if field.required is False}
            for name, fields in INPUTS.items()}
DEFAULTS['configure_cursors']['mode'] = 'MANual'
DEFAULTS['get_measurement'] = {'channel': 1}
DEFAULTS['measure_between'] = {'source_a': 1, 'source_b': 2}
DEFAULTS['get_waveform'] = {'channel': 1, 'mode': 'screen', 'max_points': 1000, 'include_data': True}
EXAMPLES = {name: {} for name in TOOL_NAMES}
EXAMPLES.update(run_control={'action': 'stop'}, configure_channel={'channel': 1},
                get_measurement={'item': 'VPP'}, measure_between={'item': 'RRDelay'})
# Budgets of the controlled MCP peer in fake.py (placeholders), not Rigol timings. The pinned server waits up to
# 30 s per deep-memory chunk, 15 s per screen read and 20 s for a screenshot (server.py:544, 547, 599), its socket
# timeout defaults to 10 s (server.py:61), and one tool issues several SCPI calls, so a real server could not meet
# them. A native profile would need its own reviewed budgets; native admission is refused anyway.
CONTROLLED_REQUEST_TIMEOUT_MS = 500  # placeholder (controlled-peer budget)
CONTROLLED_STOP_TIMEOUT_MS = 500  # placeholder (controlled-peer budget)
CONTROLLED_OPERATION_MS = 1000  # placeholder (controlled-peer budget of get_waveform and get_screenshot)
# Output size bounds of this package (a larger real result is refused, never truncated); not device sizes.
TOOLS = {}
for _name in TOOL_NAMES:
    _output = {'kind': 'json', 'schema': schema(OUTPUTS[_name]), 'max_bytes': 65536}
    if _name in ('identify', 'run_control'):
        _output = {'kind': 'text', 'max_bytes': 4096}
        if _name == 'run_control':
            _output['success_prefixes'] = ['Sent :']
    elif _name == 'get_cursor_values':
        _output.update(schema=CURSOR_SCHEMA, artifact=True)
    elif _name == 'get_waveform':
        _output.update(schema=WAVE_SCHEMA, artifact=True, max_bytes=1024 * 1024,
                       array_counts={'time_s': 'points_returned', 'voltage_V': 'points_returned'}, arrays_if='include_data')
    elif _name == 'get_screenshot':
        _output = {'kind': 'png', 'max_bytes': 1024 * 1024, 'max_pixels': 2097152}
    TOOLS[_name] = {'input': schema(INPUTS[_name]), 'output': _output, 'effectful': _name in EFFECTS,
                    'source_ref': SOURCE + ':' + str(LINES[_name]), 'defaults': DEFAULTS[_name],
                    'error_prefixes': ['ERROR', 'Error:']}
for _name, _fields in {'configure_channel': ['channel'], 'get_measurement': ['item', 'channel'],
                       'measure_between': ['item', 'source_a', 'source_b'], 'get_waveform': ['channel', 'mode']}.items():
    TOOLS[_name]['result_matches'] = {field: field for field in _fields}
# Memory mode needs a stopped scope (server.py:515, 523-524); the handler does not check it, so the
# binding reads a fresh trigger status first and refuses unless it is STOP.
TOOLS['get_waveform']['prerequisite'] = {'when': {'argument': 'mode', 'equals': 'memory'}, 'observe': 'get_status',
                                         'path': 'trigger_status', 'equals': 'STOP', 'source_ref': SOURCE + ':518-525'}
CONFIG = {'tools': TOOLS, 'source': {'path': SOURCE, 'sha256': SHA, 'commit': PIN, 'receiver': 'mcp'},
          'safety': {'command': 'run_control', 'arguments': {'action': 'stop'}, 'observe': 'get_status',
                     'path': 'trigger_status', 'equals': 'STOP'},
          'request_timeout_ms': CONTROLLED_REQUEST_TIMEOUT_MS, 'stop_timeout_ms': CONTROLLED_STOP_TIMEOUT_MS,
          'max_message_bytes': 4 * 1024 * 1024, 'owned_transport': True}

# Three more bindings of configure_cursors give the cursor coordinates an explicit unit.
CURSOR_TIME = 'x-cap.' + OWNER + '.configure_cursors_time.v1'
CURSOR_AMPLITUDE = 'x-cap.' + OWNER + '.configure_cursors_amplitude.v1'
CURSOR_CURRENT = 'x-cap.' + OWNER + '.configure_cursors_current.v1'
CURSOR_BASE = {key: field for key, field in INPUTS['configure_cursors'].items() if key not in ('position_a', 'position_b')}


def coordinates(unit):
    return {key: Field('number', unit=unit, required=False, nullable=True, limit=operator_limit(),
                       description='Manual cursor ' + letter + ' coordinate in ' + ('seconds.' if unit == 's' else 'volts.'))
            for key, letter in [('position_a', 'A'), ('position_b', 'B')]}


TIME_FIELDS = {'source': INPUTS['configure_cursors']['source'], **coordinates('s')}
AMPLITUDE_FIELDS = {'source': INPUTS['configure_cursors']['source'], **coordinates('V')}
CURRENT_FIELDS = {'source': INPUTS['configure_cursors']['source'],
                  **{'time_' + key: field for key, field in coordinates('s').items()},
                  **{'voltage_' + key: field for key, field in coordinates('V').items()}}
for _key, _field in CURRENT_FIELDS.items():
    if _field.type == 'number':
        _field.description = ('Cursor ' + _key[-1].upper() + (' seconds; applied only when the retained type is TIME.'
                              if _key.startswith('time_') else ' volts; applied only when the retained type is AMPLitude.'))


def projected(axis, prefix=''):
    arguments = {'mode': {'const': 'MANual'}, 'source': {'input': 'source'},
                 'position_a': {'input': prefix + 'position_a'}, 'position_b': {'input': prefix + 'position_b'}}
    if not prefix:
        arguments['cursor_type'] = {'const': axis}
    return arguments


# With no cursor_type the handler reads the retained type (server.py:375-389): enter MANual, read
# get_cursor_values.type, then apply only the candidates of that axis and omit cursor_type.
CURRENT_SELECT = {'observe': {'prepare': {'tool': 'configure_cursors', 'arguments': {'mode': 'MANual'}},
                              'tool': 'get_cursor_values', 'path': 'type', 'source_ref': SOURCE + ':375-389'},
                  'cases': {axis: {'arguments': projected(axis, prefix)}
                            for axis, prefix in [('TIME', 'time_'), ('AMPLitude', 'voltage_')]}}
DESCRIPTIONS = {
    'identify': 'Query the *IDN? identity string through the identify tool.',
    'get_status': 'Read trigger status, sample rate, memory depth, acquisition type, timebase and enabled-channel '
                  'settings, as the strings the scope returns.',
    'run_control': 'Send one acquisition control (run, stop, single, autoset, clear, force_trigger); the reply '
                   'carries the queried trigger status.',
    'configure_channel': 'Change only the supplied analog-channel settings; returns the queried channel settings '
                         '(no inversion readback).',
    'configure_timebase': 'Set the main timebase scale and/or offset; returns the queried values.',
    'configure_trigger_edge': 'Set EDGE trigger mode, then the supplied source, slope, level and sweep; returns the '
                              'queried trigger settings and status.',
    'configure_acquisition': 'Set memory depth, acquisition type and average count; returns the queried values and '
                             'sample rate.',
    'configure_cursors': 'Set the cursor mode (OFF, MANual, TRACk) with type and source or track sources; returns the '
                         'queried mode. Coordinates use the typed cursor bindings.',
    'get_cursor_values': 'Read cursor positions and deltas of the active mode; the complete result is a JSON artifact.',
    'get_measurement': 'Select and read one automatic measurement item on one channel (SI units); selecting is a '
                       'scope write.',
    'measure_between': 'Select and read a delay (s) or phase (degrees) item between two channels; selecting is a '
                       'scope write.',
    'get_waveform': 'Capture the screen or deep-memory waveform: statistics plus every returned decimated '
                    'time/voltage sample, as a JSON artifact. Memory mode needs a fresh STOP status first.',
    'get_screenshot': 'Capture the scope display as a PNG image artifact.',
}


class RigolDhoMcp(McpClientDriver):
    device_id = 'rigol_dho'
    device_kind = 'instrument'
    mode, risk = 'hardware', 'R0'
    native = 'rigol_dho_mcp.scpi:ScpiClient'
    backends = {'fake': '.fake:connect', 'hardware': '.native:connect'}
    vendor = 'RIGOL'
    model = 'DHO800/DHO900 series'
    display_name = 'Rigol DHO oscilloscope through rigol-dho-mcp (controlled MCP contract)'
    tags = ('mcp', 'oscilloscope', 'scpi', 'controlled-peer', 'native-blocked')
    safe_state = ('Acquisition stopped: run_control stop on the protective lane, then a fresh get_status reads '
                  'trigger_status STOP after all older requests retired; shown for the controlled peer only.')
    facts = [
        Fact('The server creates one FastMCP instance named rigol-dho800 with DNS-rebinding transport security '
             'settings.', source='upstream_code', ref=f'{SOURCE}:79-88'),
        Fact('RIGOL_ENABLE_SCPI_RAW defaults to 0 (off).', source='upstream_code', ref=f'{SOURCE}:62'),
        Fact('The raw scpi_command tool is registered only when RIGOL_ENABLE_SCPI_RAW is true.',
             source='upstream_code', ref=f'{SOURCE}:608-611'),
        Fact('run_control writes one SCPI command (stop is :STOP) and returns the queried :TRIGger:STATus? text.',
             source='upstream_code', ref=f'{SOURCE}:211-220'),
        Fact('get_status returns trigger status, acquisition and timebase strings and stops listing channels at the '
             'first channel query error.', source='upstream_code', ref=f'{SOURCE}:161-190'),
        Fact('configure_channel writes only the supplied settings and returns no inversion readback.',
             source='upstream_code', ref=f'{SOURCE}:243-265'),
        Fact('Manual cursor positions are seconds for TIME and volts for AMPLitude; with no cursor_type the handler '
             'queries the retained type.', source='upstream_code', ref=f'{SOURCE}:378-385'),
        Fact('get_measurement writes :MEASure:ITEM before it queries the value; a nonfinite value or one above 9e37 in '
             'magnitude is flagged invalid.',
             source='upstream_code', ref=f'{SOURCE}:452-461'),
        Fact('measure_between returns the time offset between edges for Delay items and the phase deviation in '
             'degrees for PHase items.',
             source='upstream_code', ref=f'{SOURCE}:483-487'),
        Fact('Memory mode reads deep memory in RAW chunks of 250000 points; the docstring requires a stopped scope '
             'but the handler does not check it.', source='upstream_code', ref=f'{SOURCE}:507-545'),
        Fact('The returned arrays are decimated with step max(1, n // max_points); time is rounded to 12 and voltage '
             'to 6 decimals.', source='upstream_code', ref=f'{SOURCE}:576-582'),
        Fact('get_screenshot returns the :DISPlay:DATA? PNG block as an MCP image.',
             source='upstream_code', ref=f'{SOURCE}:592-600'),
        Fact('ScpiClient holds one lock for each single write, query or binary query.',
             source='upstream_code', ref='rigol_dho_mcp/scpi.py:156-174'),
    ]
    mcp_config = CONFIG
    parameters = {'trigger_status': text(description='Trigger status string returned by get_status.')}
    reads = {'trigger_status': {'tool': 'get_status', 'path': 'trigger_status'}}
    commands = {cap: {'tool': name} for name, cap in CAPS.items()}
    commands[CAPS['configure_cursors']] = {'tool': 'configure_cursors',
                                           'arguments': {key: {'input': key} for key in CURSOR_BASE}}
    commands[CURSOR_TIME] = {'tool': 'configure_cursors', 'arguments': projected('TIME')}
    commands[CURSOR_AMPLITUDE] = {'tool': 'configure_cursors', 'arguments': projected('AMPLitude')}
    commands[CURSOR_CURRENT] = {'tool': 'configure_cursors', 'select': CURRENT_SELECT}
    actions = {CAPS[name]: Action(name=name, risk='R0', exclusive=False,
                                  long_running=name in ('get_waveform', 'get_screenshot'),
                                  cancellable=name in ('get_waveform', 'get_screenshot'),
                                  max_duration_ms=CONTROLLED_OPERATION_MS if name in ('get_waveform', 'get_screenshot')
                                  else None,
                                  input=INPUTS[name], output=OUTPUTS[name], examples=[EXAMPLES[name]],
                                  description=DESCRIPTIONS[name]) for name in TOOL_NAMES}
    actions[CAPS['configure_cursors']] = Action(
        name='configure_cursors', risk='R0', exclusive=False, input=CURSOR_BASE, output=OUTPUTS['configure_cursors'],
        examples=[{}], description=DESCRIPTIONS['configure_cursors'])
    actions[CURSOR_TIME] = Action(
        name='configure_cursors_time', risk='R0', exclusive=False, input=TIME_FIELDS, output=OUTPUTS['configure_cursors'],
        examples=[{}], description='Manual TIME cursors: sets type TIME and cursor A/B coordinates in seconds.')
    actions[CURSOR_AMPLITUDE] = Action(
        name='configure_cursors_amplitude', risk='R0', exclusive=False, input=AMPLITUDE_FIELDS,
        output=OUTPUTS['configure_cursors'], examples=[{}],
        description='Manual AMPLitude cursors: sets type AMPLitude and cursor A/B coordinates in volts.')
    actions[CURSOR_CURRENT] = Action(
        name='configure_cursors_current', risk='R0', exclusive=False, input=CURRENT_FIELDS,
        output=OUTPUTS['configure_cursors'], examples=[{}],
        description=('Manual cursors on the retained type: enters MANual, reads the type, applies only that axis\'s '
                     'candidates and omits cursor_type. An unreadable type leaves the mode change unresolved.'))
