"""Finite SiLA declarations and value validation; no upstream imports or I/O.

The controlled peer protocol is not a gRPC/protobuf implementation. Runtime
profile identifiers record reviewed source versions, not native admission.
"""
from __future__ import annotations

import base64
import copy
import datetime
import hashlib
import json
import math
import re

from ..units import convert as convert_unit
from .spec import DriverDefinitionError
from .upstream import parse_ref, safe_relpath

_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,63}\Z')
_FQI = re.compile(r'[a-z][a-z0-9.-]{0,127}/[A-Za-z][A-Za-z0-9_]{0,63}/[A-Za-z][A-Za-z0-9_]{0,63}/v[1-9][0-9]{0,3}\Z')
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_COMMIT = re.compile(r'[0-9a-f]{40}\Z')
_KINDS = frozenset({'command', 'observable_command', 'property', 'observable_property'})
_BASIC = frozenset({'Boolean', 'Integer', 'Real', 'String', 'Binary', 'Duration', 'Timestamp', 'List', 'Structure'})
_PROFILES = frozenset({'sila2-0.1.0', 'sila2-0.10.4', 'sila2-0.14.0', 'unitelabs-sila-0.7.5'})
PEER_FORMAT = 'mhs-sila2-controlled-v1'
MAX_BYTES = 8 * 1024 * 1024


def fail(message):
    raise DriverDefinitionError('SiLA2: ' + message)


def keys(value, allowed, required=(), label='object'):
    if type(value) is not dict or set(value) - set(allowed) or set(required) - set(value):
        fail(label + ' has unknown/missing fields or is not a plain object')
    return value


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        fail(label + f' must be an integer in {low}..{high}')
    return value


def plain(value, depth=0, budget=None, *, binary=False):
    if budget is None:
        budget = [65536, MAX_BYTES]
    budget[0] -= 1
    if depth > 16 or budget[0] < 0:
        fail('value exceeds depth/node bound')
    if value is None or type(value) in (bool, int):
        if type(value) is int and value.bit_length() > 64:
            fail('integer exceeds64bits')
        return
    if type(value) is float:
        if not math.isfinite(value):
            fail('nonfinite value')
        return
    if type(value) is str or binary and type(value) is bytes:
        size = len(value.encode('utf-8')) if type(value) is str else len(value)
        budget[1] -= size
        if budget[1] < 0:
            fail('value exceeds aggregate byte bound')
        return
    if type(value) is dict:
        if len(value) > 256 or any(type(k) is not str or len(k) > 256 for k in value):
            fail('invalid object keys')
        for name, item in value.items():
            plain(name, depth + 1, budget, binary=binary)
            plain(item, depth + 1, budget, binary=binary)
        return
    if type(value) is list:
        if len(value) > 1024:
            fail('list exceeds1024items')
        for item in value:
            plain(item, depth + 1, budget, binary=binary)
        return
    fail('only concrete bounded values are supported')


def canonical(value):
    plain(value, binary=True)
    def tagged(item):
        if type(item) is bytes:
            return ['bytes', base64.b64encode(item).decode('ascii')]
        if type(item) is dict:
            return ['object', [[key, tagged(item[key])] for key in sorted(item)]]
        if type(item) is list:
            return ['array', [tagged(child) for child in item]]
        return [type(item).__name__, item]
    return json.dumps(tagged(value), ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode()


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def type_spec(spec, depth=0):
    keys(spec, {'type', 'fields', 'items', 'min', 'max', 'enum', 'max_length', 'max_items', 'max_bytes', 'optional', 'unit'}, {'type'}, 'type')
    if depth > 16 or type(spec['type']) is not str or spec['type'] not in _BASIC:
        fail('unsupported type or nesting')
    kind = spec['type']
    if 'optional' in spec and type(spec['optional']) is not bool:
        fail('optional must be boolean')
    if 'unit' in spec and (type(spec['unit']) is not str or kind not in ('Integer', 'Real')):
        fail('unit requires a numeric type')
    if kind == 'Structure':
        fields(spec.get('fields'), depth + 1)
    elif 'fields' in spec:
        fail('fields requires Structure')
    if kind == 'List':
        type_spec(spec.get('items'), depth + 1)
        integer(spec.get('max_items'), 1, 1024, 'max_items')
    elif 'items' in spec or 'max_items' in spec:
        fail('items requires List')
    for key in ('min', 'max'):
        if key in spec:
            if kind not in ('Integer', 'Real') or type(spec[key]) not in (int, float) or not math.isfinite(spec[key]):
                fail('numeric constraint is invalid')
    if 'min' in spec and 'max' in spec and spec['min'] > spec['max']:
        fail('reversed numeric constraint')
    if kind == 'String':
        integer(spec.get('max_length'), 1, 65536, 'max_length')
    elif 'max_length' in spec:
        fail('max_length requires String')
    if kind == 'Binary':
        integer(spec.get('max_bytes'), 1, MAX_BYTES, 'max_bytes')
    elif 'max_bytes' in spec:
        fail('max_bytes requires Binary')
    if 'enum' in spec:
        if type(spec['enum']) is not list or not 1 <= len(spec['enum']) <= 1024:
            fail('enum needs finite values')
        base = {k: v for k, v in spec.items() if k != 'enum'}
        seen = set()
        for item in spec['enum']:
            validate(base, item)
            digest = fingerprint(item)
            if digest in seen:
                fail('duplicate enum value')
            seen.add(digest)


def fields(value, depth=0):
    if type(value) is not dict or len(value) > 128:
        fail('fields must be a finite plain object')
    for name, spec in value.items():
        if not _NAME.fullmatch(name):
            fail('invalid field identifier')
        type_spec(spec, depth)


def validate(spec, value, *, profile='sila2-0.14.0'):
    plain(value, binary=True)
    kind = spec['type']
    if kind == 'Boolean':
        okay = type(value) is bool
    elif kind == 'Integer':
        okay = type(value) is int and -(2**63) <= value < 2**63
    elif kind == 'Real':
        okay = type(value) in (int, float) and math.isfinite(value)
    elif kind == 'String':
        okay = type(value) is str and len(value.encode('utf-8')) <= spec['max_length']
    elif kind == 'Binary':
        okay = type(value) is bytes and len(value) <= spec['max_bytes']
        if type(value) is dict:
            keys(value, {'binary_uuid', 'size_bytes', 'sha256'}, {'binary_uuid', 'size_bytes', 'sha256'}, 'binary transfer')
            okay = (type(value['binary_uuid']) is str and len(value['binary_uuid']) == 36
                    and type(value['size_bytes']) is int and 0 <= value['size_bytes'] <= spec['max_bytes']
                    and type(value['sha256']) is str and _HEX.fullmatch(value['sha256']) is not None)
    elif kind == 'List':
        okay = type(value) is list and len(value) <= spec['max_items']
        if okay:
            for item in value:
                validate(spec['items'], item, profile=profile)
    elif kind == 'Structure':
        validate_fields(spec['fields'], value, profile=profile)
        okay = True
    elif kind == 'Duration':
        keys(value, {'seconds', 'nanos'}, {'seconds', 'nanos'}, 'duration')
        integer(value['seconds'], 0, 2**63 - 1, 'duration seconds')
        integer(value['nanos'], 0, 999999999, 'duration nanos')
        okay = True
    elif kind == 'Timestamp':
        required = {'year', 'month', 'day', 'hour', 'minute', 'second', 'timezone'}
        allowed = required | ({'millisecond'} if profile in ('sila2-0.14.0', 'unitelabs-sila-0.7.5') else set())
        keys(value, allowed, required, 'timestamp')
        for name in required - {'timezone'}:
            integer(value[name], 0, 9999, name)
        datetime.datetime(value['year'], value['month'], value['day'], value['hour'], value['minute'], value['second'])
        if 'millisecond' in value:
            integer(value['millisecond'], 0, 999, 'millisecond')
        keys(value['timezone'], {'hours', 'minutes'}, {'hours', 'minutes'}, 'timezone')
        integer(value['timezone']['hours'], -23, 23, 'timezone hours')
        integer(value['timezone']['minutes'], 0, 59, 'timezone minutes')
        okay = True
    else:
        fail('unsupported value type')
    if not okay:
        fail('value does not match ' + kind)
    if kind in ('Integer', 'Real'):
        if 'min' in spec and value < spec['min'] or 'max' in spec and value > spec['max']:
            fail('value violates protocol constraint')
    if 'enum' in spec and not any(canonical(value) == canonical(item) for item in spec['enum']):
        fail('value is outside declared enum')
    return copy.deepcopy(value)


def validate_fields(schema, value, *, profile='sila2-0.14.0'):
    keys(value, schema, [name for name, spec in schema.items() if not spec.get('optional', False)], 'typed fields')
    return {name: validate(schema[name], item, profile=profile) for name, item in value.items()}


def diagnostic_type(config, binding):
    member = config['members'].get(binding['execution'])
    if member is None or member['kind'] != 'observable_command':
        fail('diagnostics require a declared observable execution')
    state = binding['state']
    if state == 'known': return {'type': 'Boolean'}
    if state == 'uuid': return {'type': 'String', 'max_length': 36}
    if state == 'progress': return {'type': 'Real', 'min': 0, 'max': 1}
    if type(state) is str and state.startswith('intermediate:'):
        result = member.get('intermediate', {}).get(state.split(':', 1)[1])
        if result is not None and result['type'] != 'Binary': return result
    fail('unsupported finite execution diagnostic')


def input_schema(config, binding):
    result = copy.deepcopy(config['members'][binding['member']]['input'])
    for name, unit in binding.get('input_units', {}).items():
        spec = result[name]
        for bound in ('min', 'max'):
            if bound in spec:
                spec[bound] = convert_unit(spec[bound], spec['unit'], unit)
        spec['unit'] = unit
    return result


def input_values(config, binding, values):
    values = validate_fields(input_schema(config, binding), values, profile=config['runtime_profile'])
    native = config['members'][binding['member']]['input']
    for name, unit in binding.get('input_units', {}).items():
        if name not in values: continue
        value = values[name]
        if native[name]['type'] == 'Integer' and abs(value) > 2**53:
            fail('integer conversion exceeds the exact numeric budget')
        value = convert_unit(value, unit, native[name]['unit'])
        if native[name]['type'] == 'Integer':
            if not value.is_integer(): fail('unit conversion cannot round an integer argument')
            value = int(value)
        values[name] = value
    return validate_fields(native, values, profile=config['runtime_profile'])


def source(spec):
    keys(spec, {'path', 'sha256', 'ref'}, {'path', 'sha256', 'ref'}, 'source')
    ref = parse_ref(spec['ref'])
    if (type(spec['path']) is not str or safe_relpath(spec['path']) != spec['path']
            or ref is None or ref.path != spec['path'] or ref.end - ref.line > 400
            or type(spec['sha256']) is not str or not _HEX.fullmatch(spec['sha256'])):
        fail('source requires an exact digest and bounded matching citation')


def _contains_binary(spec):
    if spec['type'] == 'Binary':
        return True
    if spec['type'] == 'List':
        return _contains_binary(spec['items'])
    if spec['type'] == 'Structure':
        return any(_contains_binary(item) for item in spec['fields'].values())
    return False


def compile_sila2(raw, commands=None, reads=None, writes=None):
    plain(raw)
    keys(raw, {'peer_format', 'runtime_profile', 'endpoint', 'feature', 'commit', 'fdl', 'proto', 'implementation',
               'members', 'stop', 'request_timeout_ms', 'execution_timeout_ms', 'stop_timeout_ms',
               'max_events', 'max_operations', 'unsafe_properties', 'metadata'},
         {'peer_format', 'runtime_profile', 'endpoint', 'feature', 'commit', 'fdl', 'proto', 'implementation', 'members', 'stop'})
    if raw['peer_format'] != PEER_FORMAT or raw['runtime_profile'] not in _PROFILES:
        fail('unknown controlled contract or source profile')
    if type(raw['endpoint']) is not str or not _NAME.fullmatch(raw['endpoint']):
        fail('endpoint is a fixed opaque controlled-peer identity')
    if type(raw['feature']) is not str or not _FQI.fullmatch(raw['feature']):
        fail('invalid fully qualified feature identity')
    if type(raw['commit']) is not str or not _COMMIT.fullmatch(raw['commit']):
        fail('exact source commit required')
    source(raw['fdl']); source(raw['proto']); source(raw['implementation'])
    members = raw['members']
    if type(members) is not dict or not 1 <= len(members) <= 256:
        fail('finite member declarations required')
    for name, member in members.items():
        if not _NAME.fullmatch(name):
            fail('invalid member identifier')
        keys(member, {'kind', 'input', 'output', 'intermediate', 'errors', 'effect', 'completion', 'source_ref'},
             {'kind', 'input', 'output', 'errors', 'effect', 'completion', 'source_ref'}, 'member')
        if member['kind'] not in _KINDS or member['effect'] not in ('read', 'effectful'):
            fail('invalid member kind/effect')
        if member['completion'] not in ('returned', 'acknowledgement', 'observable'):
            fail('invalid completion interpretation')
        if (member['kind'] == 'observable_command') != (member['completion'] == 'observable'):
            fail('observable kind and completion disagree')
        fields(member['input']); fields(member['output']); fields(member.get('intermediate', {}))
        if any(_contains_binary(item) for item in member['input'].values()):
            fail('Binary input transfer is unsupported')
        if any(_contains_binary(item) for item in member.get('intermediate', {}).values()):
            fail('Binary intermediate transfer is unsupported')
        if any(item['type'] != 'Binary' and _contains_binary(item) for item in member['output'].values()):
            fail('nested primary Binary output needs an owned artifact implementation')
        if member['kind'].endswith('property') and member['input']:
            fail('property inputs are not supported')
        if member['kind'].endswith('command') and member['effect'] != 'effectful':
            fail('selected actuator commands require retained effect ownership')
        if member.get('intermediate') and member['kind'] != 'observable_command':
            fail('intermediates require observable command')
        if type(member['errors']) is not list or len(member['errors']) > 32 or any(type(e) is not str or not _NAME.fullmatch(e) for e in member['errors']):
            fail('invalid finite defined-error list')
        ref = parse_ref(member['source_ref'])
        if ref is None or ref.path != raw['fdl']['path'] or ref.end - ref.line > 200:
            fail('member source must cite its finite FDL declaration')
    stop = members.get(raw['stop'])
    if stop is None or stop['kind'] != 'command' or stop['effect'] != 'effectful' or stop['input'] or stop['completion'] != 'acknowledgement':
        fail('stop must explicitly be an input-free unary acknowledgement')
    if writes:
        fail('implicit property mutation is unsupported; declare effectful commands')
    commands, reads = {} if commands is None else commands, {} if reads is None else reads
    plain(commands); plain(reads)
    if type(commands) is not dict or type(reads) is not dict or len(commands) + len(reads) > 256:
        fail('finite command/read maps required')
    for cap, binding in commands.items():
        keys(binding, {'member', 'artifact', 'media_type', 'input_units'}, {'member'}, 'binding')
        if binding['member'] not in members:
            fail('binding selects undeclared member')
        member = members[binding['member']]
        conversions = binding.get('input_units', {})
        if type(conversions) is not dict: fail('input_units requires a finite map')
        for name, unit in conversions.items():
            spec = member['input'].get(name)
            if spec is None or spec['type'] not in ('Integer', 'Real') or 'unit' not in spec or type(unit) is not str:
                fail('conversion must select an explicitly unit-bearing numeric input')
            try: convert_unit(1, unit, spec['unit'])
            except (ValueError, TypeError): fail('incompatible unit conversion')
        if 'artifact' in binding:
            field = binding['artifact']
            if set(member['output']) != {field} or member['output'][field]['type'] != 'Binary':
                fail('artifact binding needs one complete primary Binary output')
            if binding.get('media_type') not in ('image/png', 'application/octet-stream', 'video/mp4', 'text/plain'):
                fail('explicit supported artifact media type required')
        elif any(spec['type'] == 'Binary' for spec in member['output'].values()):
            fail('primary Binary output requires stock artifact publication')
    for name, binding in reads.items():
        if 'execution' in binding:
            keys(binding, {'execution', 'state', 'default'}, {'execution', 'state', 'default'}, 'execution diagnostic')
            validate(diagnostic_type(raw, binding), binding['default'], profile=raw['runtime_profile'])
            continue
        keys(binding, {'member', 'field'}, {'member', 'field'}, 'read')
        member = members.get(binding['member'])
        if (member is None or not member['kind'].endswith('property') or member['effect'] != 'read'
                or binding['field'] not in member['output'] or member['output'][binding['field']]['type'] == 'Binary'):
            fail('reads require a non-effectful typed property; Binary uses artifact command')
    result = copy.deepcopy(raw)
    for key, default, high in [('request_timeout_ms', 500, 30000), ('execution_timeout_ms', 4000, 600000),
                              ('stop_timeout_ms', 500, 30000), ('max_events', 64, 1024), ('max_operations', 256, 1024)]:
        result[key] = integer(raw.get(key, default), 1, high, key)
    unsafe = raw.get('unsafe_properties', {})
    if type(unsafe) is not dict:
        fail('unsafe properties must be finite')
    for member_name, expected in unsafe.items():
        member = members.get(member_name)
        if member is None or not member['kind'].endswith('property'):
            fail('unknown safety observation')
        validate_fields(member['output'], expected, profile=raw['runtime_profile'])
    result['unsafe_properties'] = copy.deepcopy(unsafe)
    metadata = raw.get('metadata', [])
    if type(metadata) is not list or len(metadata) > 16:
        fail('metadata must be a finite declaration')
    headers = set()
    for item in metadata:
        keys(item, {'identifier', 'type', 'value'}, {'identifier', 'type', 'value'}, 'metadata')
        if type(item['identifier']) is not str or not item['identifier'].startswith(raw['feature'] + '/Metadata/') or not _NAME.fullmatch(item['identifier'].rsplit('/', 1)[-1]):
            fail('metadata must identify the exact selected feature')
        type_spec(item['type'])
        if _contains_binary(item['type']):
            fail('Binary metadata transfer is unsupported')
        validate(item['type'], item['value'], profile=raw['runtime_profile'])
        header = 'sila-' + item['identifier'].lower().replace('/', '-') + '-bin'
        if header in headers:
            fail('duplicate metadata header')
        headers.add(header)
    result['metadata'] = copy.deepcopy(metadata)
    result['commands'], result['reads'] = copy.deepcopy(commands), copy.deepcopy(reads)
    return result
