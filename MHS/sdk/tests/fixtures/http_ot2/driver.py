"""SDK-contained full controlled OT2 workflow; not a native acceptance fixture."""
from mhs.driver import Action, Field, HttpDriver, Limit

RUN = 'x-cap.ot2.run_protocol.v1'
PAUSE = 'x-cap.ot2.pause.v1'
RESUME = 'x-cap.ot2.resume.v1'
CANCEL = 'x-cap.ot2.cancel.v1'
LOGS = 'x-cap.ot2.logs.v1'
INSPECT = 'x-cap.ot2.inspect_run.v1'
LIST = 'x-cap.ot2.list_runs.v1'
SOURCE = 'src/ot2_interface/ot2_driver_http.py'
PROTOCOL_SHA256 = 'b583ec89a9fe55dc488d3957df025b93db454703ea5c6a53ad12bdb285983527'
ENVELOPE = Limit.operator_required('Operator must approve this exact immutable protocol and its complete effects; a digest alone is not a safety proof')


def route(method, path, source_method, line, *, required=None, json=None, multipart=None, query=None, correlation=None):
    result = {'method': method, 'path': path, 'source_method': source_method,
              'source_ref': SOURCE + ':' + str(line),
              'response': {'status': [200 if method == 'GET' else 201], 'required': required or {'data': 'object'}}}
    if json is not None: result['json'] = json
    if multipart is not None: result['multipart'] = multipart
    if query is not None: result['query'] = query
    if correlation is not None: result['response']['correlation'] = correlation
    return result


CONFIG = {'profile': 'ot2-run-v1', 'origin': 'http://controlled-ot2.invalid:31950',
    'headers': {'Opentrons-Version': '2'}, 'request_timeout_ms': 500, 'workflow_timeout_ms': 4000,
    'poll_ms': 10, 'max_polls': 500, 'max_body_bytes': 2 * 1024 * 1024, 'owned_transport': True,
    'routes': {
        'upload': route('POST', '/protocols', 'transfer', 152, multipart='files', required={'data.id': 'string'}),
        'create': route('POST', '/runs', 'transfer', 163, json={'data': {'protocolId': {'$job': 'protocol_id'}}}, required={'data.id': 'string'}),
        'play': route('POST', '/runs/{run_id}/actions', 'execute', 188, json={'data': {'actionType': 'play'}}),
        'pause': route('POST', '/runs/{run_id}/actions', 'pause', 231, json={'data': {'actionType': 'pause'}}),
        'resume': route('POST', '/runs/{run_id}/actions', 'resume', 253, json={'data': {'actionType': 'play'}}),
        'stop': route('POST', '/runs/{run_id}/actions', 'cancel', 275, json={'data': {'actionType': 'stop'}}),
        'status': route('GET', '/runs/{run_id}', 'check_run_status', 295,
                        required={'data.id': 'string', 'data.status': 'string'}, correlation={'data.id': 'run_id'}),
        'list': route('GET', '/runs', 'get_runs', 370, required={'data': 'array'}),
        'commands': route('GET', '/runs/{run_id}/commands', 'get_run_log', 347,
                          query={'cursor': 0, 'pageLength': 1000}, required={'data': 'array'}),
    }, 'workflow': {name: name for name in ('upload', 'create', 'play', 'pause', 'resume', 'stop', 'status', 'list', 'commands')},
    'artifacts': {'controlled_protocol': {'path': 'protocol.json', 'sha256': PROTOCOL_SHA256, 'max_bytes': 4096}}}


class Driver(HttpDriver):
    device_id = 'controlled_ot2'
    device_kind = 'generic'
    mode, risk = 'hardware', 'R2'
    native = 'ot2_interface.ot2_driver_http:OT2_Driver'
    backends = {'fake': '.fake:connect', 'hardware': '.native:connect'}
    safe_state = 'Only the controlled peer confirms an owned run stopped after all requests retire; native stopping is unresolved.'
    http_config = CONFIG
    parameters = {'status': Field('string'), 'run_id': Field('string'), 'protocol_id': Field('string'),
                  'pending': Field('integer'), 'safe': Field('boolean')}
    reads = {name: {'state': name} for name in parameters}
    commands = {cap: {'operation': operation} for cap, operation in
                ((RUN, 'run'), (PAUSE, 'pause'), (RESUME, 'resume'), (CANCEL, 'cancel'),
                 (LOGS, 'logs'), (INSPECT, 'inspect'), (LIST, 'list'))}
    actions = {
        RUN: Action(name='run_protocol', description='Upload a fixed protocol, create and play its owned run, and poll to completion.',
                    risk='R2', requires_permit=True, exclusive=False, long_running=True, cancellable=True, max_duration_ms=4000,
                    input={'protocol': Field('string', enum=['controlled_protocol'], limit=ENVELOPE)},
                    output={'run_id': Field('string'), 'protocol_id': Field('string'), 'status': Field('string', enum=['succeeded'])},
                    examples=[{'protocol': 'controlled_protocol'}]),
        PAUSE: Action(name='pause', risk='R2', exclusive=False, output={'run_id': Field('string'), 'status': Field('string', enum=['paused'])}),
        RESUME: Action(name='resume', risk='R2', requires_permit=True, exclusive=False, output={'run_id': Field('string'), 'status': Field('string', enum=['running'])}),
        CANCEL: Action(name='cancel', risk='R2', exclusive=False, safe_state=True, output={'stopped': Field('boolean'), 'run_id': Field('string')}),
        LOGS: Action(name='logs', risk='R0', exclusive=False, output={'artifact_ref': Field('string'), 'run_id': Field('string'),
                    'media_type': Field('string', enum=['application/json']), 'complete': Field('boolean')}),
        INSPECT: Action(name='inspect_run', risk='R0', exclusive=False, output={'run_id': Field('string'), 'status': Field('string')}),
        LIST: Action(name='list_runs', risk='R0', exclusive=False, output={'runs': Field('array', items=Field('object', properties={
                    'id': Field('string'), 'protocolId': Field('string'), 'status': Field('string'), 'current': Field('boolean')}), max_items=4096)}),
    }
    safety_bindings = {'estop': {'operation': 'cancel'}}


def overlay():
    return {'openmhs': '0.9', 'site': 'controlled-fixture', 'issued_by': {'id': 'operator:fixture'},
            'issued_at': '2026-11-04T00:00:00Z', 'devices': {'mhs://localhost/controlled_ot2': {
                RUN: {'protocol': {'allowed': ['controlled_protocol'], 'source': 'operator'}}}}}
