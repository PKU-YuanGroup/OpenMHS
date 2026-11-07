"""Finite HTTP declarations. No discovery, networking, imports or executable maps."""
from __future__ import annotations

import copy
import json
import math
import re
from urllib.parse import urlsplit

from .spec import DriverDefinitionError
from .upstream import parse_ref, safe_relpath

_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,63}\Z')
_PATH = re.compile(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*){0,7}\Z')
_SEGMENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')
_DIGEST = re.compile(r'[0-9a-f]{64}\Z')
_ROLES = ('upload', 'create', 'play', 'pause', 'resume', 'stop', 'status', 'list', 'commands')
_OPERATIONS = frozenset({'run', 'pause', 'resume', 'cancel', 'logs', 'inspect', 'list'})
_STATE = frozenset({'status', 'run_id', 'protocol_id', 'pending', 'safe'})
_METHODS = frozenset({'GET', 'POST', 'PUT', 'PATCH', 'DELETE'})
MAX_BODY = 8 * 1024 * 1024
MAX_HEADERS = 32 * 1024
OT2_CLIENT_PATH = 'src/ot2_interface/ot2_driver_http.py'
OT2_CLIENT_SHA256 = '1f7ef567e83a33c11b6f4fc5411eec307192bdbc24235c9926c6a125f9a4fed6'
OT2_CLIENT_COMMIT = '39ffdfdb73c3bc08bb988c5140cfc1af3cecbd0c'


def fail(message):
    raise DriverDefinitionError('HTTP: ' + message)


def integer(value, label, maximum, minimum=1):
    if type(value) is not int or not minimum <= value <= maximum:
        fail(f'{label} must be an integer in {minimum}..{maximum}')
    return value


def plain(value, *, depth=0, _budget=None):
    """Reject executable/custom objects before copying or serializing them."""
    if _budget is None:
        _budget = [65536, MAX_BODY]
    _budget[0] -= 1
    if depth > 16 or _budget[0] < 0:
        fail('JSON nesting exceeds 16')
    if value is None or type(value) in (bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            fail('non-finite JSON number')
        return
    if type(value) is str:
        _budget[1] -= len(value)
        if _budget[1] < 0:
            fail('JSON string exceeds body bound')
        return
    if type(value) is dict:
        if len(value) > 128 or any(type(k) is not str or len(k) > 128 for k in value):
            fail('JSON object has too many or invalid keys')
        _budget[1] -= sum(map(len, value))
        if _budget[1] < 0:
            fail('JSON object keys exceed body bound')
        for item in value.values():
            plain(item, depth=depth + 1, _budget=_budget)
        return
    if type(value) is list:
        if len(value) > 4096:
            fail('JSON array exceeds 4096 entries')
        for item in value:
            plain(item, depth=depth + 1, _budget=_budget)
        return
    fail('only concrete JSON values are supported')


def encoded(value):
    plain(value)
    try:
        data = json.dumps(value, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()
    except (UnicodeError, ValueError) as exc:
        fail('JSON cannot be encoded within the finite profile')
    if len(data) > MAX_BODY:
        fail('JSON body exceeds SDK limit')
    return data


def object_keys(value, allowed, required=(), label='object'):
    if type(value) is not dict or set(value) - set(allowed) or set(required) - set(value):
        fail(label + ' has missing/unknown keys or is not a plain object')
    return value


def reference(value):
    ref = parse_ref(value)
    if ref is None or safe_relpath(ref.path) != ref.path or ref.end - ref.line > 200:
        fail('source_ref must cite a bounded relative file:line[-end]')


def field_path(value):
    if type(value) is not str or not _PATH.fullmatch(value):
        fail('response path must be a finite public field path')
    return value


def template(value):
    if type(value) is dict:
        if any(key.startswith('$') for key in value):
            if set(value) != {'$job'} or value['$job'] not in ('protocol_id', 'run_id'):
                fail('only exact $job protocol_id/run_id template leaves are supported')
        else:
            for child in value.values():
                template(child)
    elif type(value) is list:
        for child in value:
            template(child)


def compile_http(raw, commands=None, reads=None, writes=None):
    """Return detached JSON configuration; the current native profile is blocked."""
    encoded(raw)
    object_keys(raw, {'profile', 'origin', 'headers', 'auth_ref', 'routes', 'workflow', 'artifacts',
                     'request_timeout_ms', 'workflow_timeout_ms', 'poll_ms', 'max_polls', 'max_body_bytes',
                     'owned_transport'}, {'profile', 'origin', 'headers', 'routes', 'workflow', 'artifacts'})
    if raw['profile'] != 'ot2-run-v1':
        fail('only the explicit ot2-run-v1 request-shape profile is supported')
    origin = raw['origin']
    if type(origin) is not str or len(origin) > 512:
        fail('origin must be an explicit bounded URL')
    try:
        url = urlsplit(origin)
        port = url.port
    except ValueError:
        fail('invalid origin')
    if (url.scheme not in ('http', 'https') or not url.hostname or url.username is not None
            or url.password is not None or url.path not in ('', '/') or url.query or url.fragment
            or any(c.isspace() for c in origin) or '\\' in origin or '%' in url.netloc):
        fail('origin must contain only explicit scheme, host and optional port')
    if port is not None and not 1 <= port <= 65535:
        fail('invalid port')
    headers = object_keys(raw['headers'], {'Opentrons-Version'}, {'Opentrons-Version'}, 'headers')
    if headers['Opentrons-Version'] != '2':
        fail('ot2-run-v1 requires its exact non-secret version header')
    if raw.get('auth_ref') is not None and (type(raw['auth_ref']) is not str or not _NAME.fullmatch(raw['auth_ref'])):
        fail('auth_ref must be an opaque bounded policy name; no secret values are accepted')
    routes = raw['routes']
    if type(routes) is not dict or not 1 <= len(routes) <= 64:
        fail('routes needs 1..64 entries')
    for name, route in routes.items():
        if not _NAME.fullmatch(name):
            fail('invalid route name')
        object_keys(route, {'method', 'path', 'query', 'json', 'multipart', 'response', 'source_ref', 'source_method'},
                    {'method', 'path', 'response', 'source_ref', 'source_method'}, 'route')
        if type(route['method']) is not str or route['method'] not in _METHODS:
            fail('route method must be literal and supported')
        path = route['path']
        if type(path) is not str or not path.startswith('/') or len(path) > 512:
            fail('route needs a literal relative absolute-path')
        parts = path[1:].split('/')
        if not 1 <= len(parts) <= 8 or any(p not in ('{run_id}', '{protocol_id}') and
                (not _SEGMENT.fullmatch(p) or p in ('.', '..')) for p in parts):
            fail('route contains an unsupported segment or substitution')
        for member in ('query', 'json'):
            if member in route:
                if type(route[member]) is not dict:
                    fail(member + ' must be a finite object')
                template(route[member])
        if 'multipart' in route:
            if route['multipart'] != 'files' or 'json' in route or route['method'] != 'POST':
                fail('multipart supports one explicit files artifact, without a JSON body')
        response = object_keys(route['response'], {'status', 'required', 'correlation'}, {'status', 'required'}, 'response')
        if (type(response['status']) is not list or not 1 <= len(response['status']) <= 4
                or any(type(v) is not int or not 200 <= v <= 299 for v in response['status'])
                or len(set(response['status'])) != len(response['status'])):
            fail('response status needs 1..4 explicit successful codes')
        required = response['required']
        if type(required) is not dict or len(required) > 64:
            fail('response required fields must be a bounded object')
        for path, kind in required.items():
            field_path(path)
            if kind not in ('string', 'boolean', 'number', 'integer', 'object', 'array'):
                fail('unsupported response field type')
        correlation = response.get('correlation', {})
        if type(correlation) is not dict or len(correlation) > 2:
            fail('correlation must contain at most two exact ID fields')
        for path, member in correlation.items():
            field_path(path)
            if member not in ('run_id', 'protocol_id'):
                fail('correlation must name the owned job ID')
        reference(route['source_ref'])
        if type(route['source_method']) is not str or not _NAME.fullmatch(route['source_method']):
            fail('source_method must be a public method name')
    workflow = object_keys(raw['workflow'], _ROLES, _ROLES, 'workflow')
    if any(type(name) is not str or name not in routes for name in workflow.values()):
        fail('workflow roles must name declared routes')
    # Fixed request-shape semantics; response values are fake contract choices,
    # never claimed to prove the absent robot-server retirement implementation.
    expected = {'upload': ('POST', '/protocols'), 'create': ('POST', '/runs'),
                'status': ('GET', '/runs/{run_id}'), 'list': ('GET', '/runs'),
                'commands': ('GET', '/runs/{run_id}/commands')}
    for role in ('play', 'pause', 'resume', 'stop'):
        expected[role] = ('POST', '/runs/{run_id}/actions')
    for role, (method, path) in expected.items():
        spec = routes[workflow[role]]
        if (spec['method'], spec['path']) != (method, path):
            fail('workflow role disagrees with the supported OT2 request shape')
    if routes[workflow['upload']].get('multipart') != 'files':
        fail('upload requires the explicit files artifact')
    if routes[workflow['create']].get('json') != {'data': {'protocolId': {'$job': 'protocol_id'}}}:
        fail('create must bind the exact returned protocol ID')
    for role, action in [('play', 'play'), ('pause', 'pause'), ('resume', 'play'), ('stop', 'stop')]:
        if routes[workflow[role]].get('json') != {'data': {'actionType': action}}:
            fail('control route must use its exact actionType')
    if routes[workflow['status']]['response'].get('correlation') != {'data.id': 'run_id'}:
        fail('fresh status must be tied to the owned run ID')
    for role, required in [('upload', {'data.id': 'string'}), ('create', {'data.id': 'string'}),
                           ('status', {'data.id': 'string', 'data.status': 'string'}),
                           ('list', {'data': 'array'}), ('commands', {'data': 'array'})]:
        fields = routes[workflow[role]]['response']['required']
        if any(fields.get(name) != kind for name, kind in required.items()):
            fail('response must retain the required workflow fields')
    if routes[workflow['commands']].get('query') != {'cursor': 0, 'pageLength': 1000}:
        fail('commands must use the pinned explicit first-page request')
    if any(route.get('query', {}) for name, route in routes.items() if name != workflow['commands']):
        fail('only the commands role supports the pinned first-page query')
    if set(routes) != set(workflow.values()):
        fail('unused routes are unsupported')
    artifacts = raw['artifacts']
    if type(artifacts) is not dict or not 1 <= len(artifacts) <= 32:
        fail('artifacts needs 1..32 explicit immutable fixture inputs')
    for name, item in artifacts.items():
        if not _NAME.fullmatch(name):
            fail('invalid artifact name')
        object_keys(item, {'path', 'sha256', 'max_bytes', 'filename'}, {'path', 'sha256', 'max_bytes'}, 'artifact')
        if safe_relpath(item['path']) != item['path'] or type(item['sha256']) is not str or not _DIGEST.fullmatch(item['sha256']):
            fail('artifact needs a confined relative path and exact SHA-256')
        integer(item['max_bytes'], 'artifact max_bytes', MAX_BODY)
        if 'filename' in item and (type(item['filename']) is not str or not _SEGMENT.fullmatch(item['filename'])
                                   or item['filename'] in ('.', '..')):
            fail('artifact filename must be one literal bounded file name')
    out = copy.deepcopy(raw)
    for name, default, maximum in [('request_timeout_ms', 1000, 60000), ('workflow_timeout_ms', 5000, 600000),
                                  ('poll_ms', 10, 1000), ('max_polls', 1000, 10000),
                                  ('max_body_bytes', MAX_BODY, MAX_BODY)]:
        out[name] = integer(raw.get(name, default), name, maximum)
    if type(raw.get('owned_transport', True)) is not bool:
        fail('owned_transport must be an explicit boolean')
    out['owned_transport'] = raw.get('owned_transport', True)
    commands = {} if commands is None else commands
    reads = {} if reads is None else reads
    writes = {} if writes is None else writes
    encoded(commands); encoded(reads); encoded(writes)
    if type(commands) is not dict or len(commands) > 64 or type(reads) is not dict or len(reads) > 64 or writes:
        fail('commands/reads must be finite; OT2 workflow has no arbitrary setting writes')
    for spec in commands.values():
        object_keys(spec, {'operation'}, {'operation'}, 'command')
        if type(spec['operation']) is not str or spec['operation'] not in _OPERATIONS:
            fail('unsupported workflow operation')
    for spec in reads.values():
        object_keys(spec, {'state'}, {'state'}, 'read')
        if type(spec['state']) is not str or spec['state'] not in _STATE:
            fail('unsupported workflow state field')
    out['commands'], out['reads'] = copy.deepcopy(commands), copy.deepcopy(reads)
    return out
