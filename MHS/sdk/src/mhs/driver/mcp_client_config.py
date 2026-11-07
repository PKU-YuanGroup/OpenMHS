"""Finite MCP client declarations; discovery is compatibility, never authority."""
from __future__ import annotations

import copy
import json
import math
import re

from .spec import DriverDefinitionError
from .upstream import parse_ref, safe_relpath
from ..schema.validator import validate

_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,63}\Z')
_PATH = re.compile(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*){0,7}\Z')
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_COMMIT = re.compile(r'[0-9a-f]{40}\Z')
_TYPES = frozenset({'object', 'array', 'string', 'integer', 'number', 'boolean', 'null'})
_SCHEMA_KEYS = frozenset({'type', 'properties', 'required', 'additionalProperties', 'items',
                        'minItems', 'maxItems', 'maxLength', 'enum', 'minimum', 'maximum',
                        'anyOf', 'oneOf', 'description', 'x-mhs-unit', 'x-mhs-delta'})
MAX_BYTES = 16 * 1024 * 1024
MAX_NODES = 262144
MAX_ARRAY = 65536


def fail(message):
    raise DriverDefinitionError('MCP client: ' + message)


def integer(value, label, maximum, minimum=1):
    if type(value) is not int or not minimum <= value <= maximum:
        fail(f'{label} must be an integer in {minimum}..{maximum}')
    return value


def plain(value, *, depth=0, budget=None):
    """Bound concrete JSON before copying, invoking hooks, or encoding."""
    if budget is None:
        budget = [MAX_NODES, MAX_BYTES]
    budget[0] -= 1
    if depth > 16 or budget[0] < 0:
        fail('JSON nesting/node budget exceeded')
    kind = type(value)
    if value is None or kind is bool:
        return
    if kind in (int, float):
        if not math.isfinite(value) or (kind is int and abs(value) > 9007199254740991):
            fail('JSON number is nonfinite or outside exact integer range')
        return
    if kind is str:
        budget[1] -= len(value)
    elif kind is dict:
        if len(value) > 128 or any(type(k) is not str or len(k) > 128 for k in value):
            fail('JSON object keys exceed finite bounds')
        budget[1] -= sum(map(len, value))
        for child in value.values():
            plain(child, depth=depth + 1, budget=budget)
    elif kind is list:
        if len(value) > MAX_ARRAY:
            fail('JSON array exceeds finite bound')
        for child in value:
            plain(child, depth=depth + 1, budget=budget)
    else:
        fail('only concrete JSON is permitted')
    if budget[1] < 0:
        fail('JSON text exceeds byte budget')


def encoded(value, maximum=MAX_BYTES):
    plain(value)
    try:
        result = json.dumps(value, allow_nan=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    except (ValueError, UnicodeError) as exc:
        fail('JSON encoding failed')
    if len(result) > maximum:
        fail('encoded JSON exceeds byte budget')
    return result


def keys(value, allowed, required=(), label='object'):
    if type(value) is not dict or set(value) - set(allowed) or set(required) - set(value):
        fail(label + ' has unknown/missing keys or is not a plain object')
    return value


def schema(value, depth=0):
    keys(value, _SCHEMA_KEYS, label='schema')
    if depth > 12:
        fail('schema nesting exceeds 12')
    for union in ('oneOf', 'anyOf'):
        if union in value:
            if set(value) != {union} or type(value[union]) is not list or not 1 <= len(value[union]) <= 8:
                fail('schema union must contain 1..8 finite alternatives')
            for child in value[union]:
                schema(child, depth + 1)
            return
    kind = value.get('type')
    if type(kind) is list:
        if len(kind) != 2 or kind[1] != 'null' or kind[0] == 'null':
            fail('only a concrete type plus null is supported')
        kind = kind[0]
    if type(kind) is not str or kind not in _TYPES:
        fail('schema needs an explicit supported type')
    if kind == 'object':
        props = value.get('properties')
        if type(props) is not dict or len(props) > 64 or value.get('additionalProperties') is not False:
            fail('object schemas must be finite and closed')
        required = value.get('required', [])
        if (type(required) is not list or any(type(k) is not str or k not in props for k in required)
                or len(required) != len(set(required))):
            fail('invalid required schema fields')
        for name, child in props.items():
            if not _NAME.fullmatch(name):
                fail('schema property is not a public field name')
            schema(child, depth + 1)
    elif any(k in value for k in ('properties', 'required', 'additionalProperties')):
        fail('object constraints require an object')
    if kind == 'array':
        integer(value.get('maxItems'), 'maxItems', MAX_ARRAY, 0)
        integer(value.get('minItems', 0), 'minItems', value['maxItems'], 0)
        schema(value.get('items'), depth + 1)
    elif any(k in value for k in ('items', 'minItems', 'maxItems')):
        fail('array constraints require an array')
    if kind == 'string':
        if 'enum' not in value:
            integer(value.get('maxLength'), 'maxLength', MAX_BYTES, 0)
    elif 'maxLength' in value:
        fail('maxLength requires a string')
    if 'enum' in value:
        if type(value['enum']) is not list or not 1 <= len(value['enum']) <= 64:
            fail('enum must be finite')
        for item in value['enum']:
            if type(item) not in (str, bool, int, float) and item is not None:
                fail('enum values must be scalars')
            if validate(item, {k: v for k, v in value.items() if k != 'enum'}):
                fail('enum member does not match its type')
    for bound in ('minimum', 'maximum'):
        if bound in value and (kind not in ('integer', 'number') or type(value[bound]) not in (int, float)):
            fail('numeric schema bound requires a number')
    if value.get('minimum', -math.inf) > value.get('maximum', math.inf):
        fail('reversed schema bounds')


def checked(value, contract, label):
    plain(value)
    if validate(value, contract):
        fail(label + ' does not match the finite schema')
    return value


def get_path(value, path):
    for part in path.split('.'):
        if type(value) is not dict or part not in value:
            fail('required result path is missing')
        value = value[part]
    return value


def _shape(value):
    if type(value) is dict:
        return {k:_shape(v) for k,v in value.items() if k not in ('description','x-mhs-unit','x-mhs-delta')}
    if type(value) is list:
        return [_shape(v) for v in value]
    return value


def _projection(binding, tools, source):
    """Finite constant/field bindings; no expressions or remote dispatch names."""
    keys(binding, {'tool','input_schema','arguments','select'}, {'tool'}, 'command')
    tool = tools.get(binding['tool'])
    if tool is None:
        fail('command names an undeclared tool')
    input_schema = binding.get('input_schema', tool['input'])
    schema(input_schema)
    if input_schema.get('type') != 'object':
        fail('command input must be a closed object')
    if 'arguments' in binding and 'select' in binding:
        fail('command has two argument projections')
    if 'select' in binding:
        selector = keys(binding['select'], {'observe','cases'}, {'observe','cases'}, 'selector')
        cases = selector['cases']
        if type(cases) is not dict or not 1 <= len(cases) <= 8 or any(not _NAME.fullmatch(k) for k in cases):
            fail('source selector needs 1..8 literal cases')
        observation=keys(selector['observe'], {'prepare','tool','path','source_ref'},
                         {'prepare','tool','path','source_ref'}, 'source selector observation')
        preparation=keys(observation['prepare'], {'tool','arguments'}, {'tool','arguments'}, 'preparation')
        preparation_tool=tools.get(preparation['tool']);observation_tool=tools.get(observation['tool'])
        ref=parse_ref(observation['source_ref'])
        if (preparation_tool is None or observation_tool is None or observation_tool['effectful']
                or observation_tool['output']['kind']!='json' or observation_tool['input'].get('required')
                or not _PATH.fullmatch(observation['path']) or ref is None or ref.path!=source['path']
                or ref.end-ref.line>200):
            fail('source selector needs a finite source-cited preparation/readback')
        checked(preparation['arguments'],preparation_tool['input'],'preparation arguments')
        branches = list(cases.values())
    elif 'arguments' in binding:
        branches = [{'arguments':binding['arguments']}]
    else:
        if input_schema != tool['input']:
            fail('unprojected command input differs from its tool')
        return
    all_used=set()
    for case in branches:
        keys(case, {'arguments'}, {'arguments'}, 'projection case')
        mapping = case['arguments']
        if type(mapping) is not dict or set(mapping)-set(tool['input']['properties']):
            fail('projection contains undeclared wire arguments')
        if set(tool['input'].get('required',[]))-set(mapping):
            fail('projection omits required wire arguments')
        used = set()
        for target, rule in mapping.items():
            if type(rule) is not dict or len(rule)!=1 or not set(rule) <= {'input','const'}:
                fail('projection leaves must be literal input/const objects')
            if 'const' in rule:
                checked(rule['const'], tool['input']['properties'][target], 'constant wire argument')
            else:
                name=rule['input']
                if type(name) is not str or name not in input_schema['properties'] or name in used:
                    fail('projection inputs must be declared and used once')
                used.add(name)
                if _shape(input_schema['properties'][name]) != _shape(tool['input']['properties'][target]):
                    fail('projection may change declared units/names, not the concrete value schema')
                source_unit=tool['input']['properties'][target].get('x-mhs-unit')
                if source_unit is not None and input_schema['properties'][name].get('x-mhs-unit')!=source_unit:
                    fail('projection cannot reinterpret a source-declared unit')
                if target in tool['input'].get('required',[]) and name not in input_schema.get('required',[]):
                    fail('projection makes a required wire argument optional')
        all_used.update(used)
    if all_used!=set(input_schema['properties']):
        fail('every declared input must belong to a finite argument branch')


def compile_mcp_client(raw, commands=None, reads=None, writes=None):
    encoded(raw)
    keys(raw, {'tools', 'source', 'safety', 'request_timeout_ms', 'stop_timeout_ms',
               'max_message_bytes', 'owned_transport'}, {'tools', 'source'})
    source = keys(raw['source'], {'path', 'sha256', 'commit', 'receiver'},
                  {'path', 'sha256', 'commit', 'receiver'}, 'source')
    if (type(source['path']) is not str or safe_relpath(source['path']) != source['path']
            or not _SHA.fullmatch(source['sha256']) or not _COMMIT.fullmatch(source['commit'])
            or not _NAME.fullmatch(source['receiver'])):
        fail('source needs a relative path, exact SHA/commit and literal decorator receiver')
    tools = raw['tools']
    if type(tools) is not dict or not 1 <= len(tools) <= 64:
        fail('tools must contain 1..64 explicit entries')
    for name, spec in tools.items():
        if not _NAME.fullmatch(name):
            fail('tool name must be a literal public name')
        keys(spec, {'input', 'output', 'effectful', 'source_ref', 'error_prefixes', 'defaults', 'result_matches', 'prerequisite'},
             {'input', 'output', 'effectful', 'source_ref'}, 'tool')
        schema(spec['input'])
        if spec['input'].get('type') != 'object' or type(spec['effectful']) is not bool:
            fail('tool input must be an object and effects must be explicit')
        defaults = spec.get('defaults', {})
        if (type(defaults) is not dict or set(defaults) !=
                set(spec['input']['properties']) - set(spec['input'].get('required', []))):
            fail('every optional argument needs its literal reviewed default')
        for argument, default in defaults.items():
            checked(default, spec['input']['properties'][argument], 'default argument')
        matches = spec.get('result_matches', {})
        if type(matches) is not dict or any(not _PATH.fullmatch(path) or argument not in spec['input']['properties']
                                          for path, argument in matches.items()):
            fail('result correlations must name finite paths and declared arguments')
        ref = parse_ref(spec['source_ref'])
        if ref is None or ref.path != source['path'] or ref.end - ref.line > 200:
            fail('tool source_ref must be a bounded citation in its exact source')
        output = keys(spec['output'], {'kind', 'schema', 'max_bytes', 'artifact', 'max_pixels', 'success_prefixes', 'array_counts', 'arrays_if'},
                      {'kind', 'max_bytes'}, 'output')
        integer(output['max_bytes'], 'output max_bytes', MAX_BYTES)
        if output['kind'] == 'json':
            schema(output.get('schema'))
            if output['schema'].get('type') != 'object' and not any(k in output['schema'] for k in ('oneOf', 'anyOf')):
                fail('JSON tool results must be objects')
            if type(output.get('artifact', False)) is not bool or any(k in output for k in ('max_pixels', 'success_prefixes')):
                fail('invalid JSON output mode')
            counts = output.get('array_counts', {})
            if type(counts) is not dict or any(not _PATH.fullmatch(k) or not _PATH.fullmatch(v) for k, v in counts.items()):
                fail('array counts must name finite result paths')
            conditional = output.get('arrays_if')
            if conditional is not None and (conditional not in spec['input']['properties'] or not counts
                    or spec['input']['properties'][conditional].get('type') != 'boolean'):
                fail('array presence must follow a declared boolean argument')
        elif output['kind'] == 'png':
            integer(output.get('max_pixels'), 'max_pixels', 16777216)
            if any(k in output for k in ('schema', 'artifact', 'success_prefixes')):
                fail('PNG output cannot redefine its primary representation')
        elif output['kind'] == 'text':
            if any(k in output for k in ('schema', 'artifact', 'max_pixels')):
                fail('text output cannot redefine its representation')
        else:
            fail('only complete JSON, text and PNG results are supported')
        if output['kind'] != 'json' and (matches or any(k in output for k in ('array_counts', 'arrays_if'))):
            fail('result checks require JSON output')
        for prefixes in (spec.get('error_prefixes', []), output.get('success_prefixes', [])):
            if (type(prefixes) is not list or len(prefixes) > 16
                    or any(type(p) is not str or not 1 <= len(p) <= 128 for p in prefixes)):
                fail('text prefixes must be finite literal strings')
    safety = raw.get('safety')
    for spec in tools.values():
        prerequisite = spec.get('prerequisite')
        if prerequisite is None:
            continue
        keys(prerequisite, {'when', 'observe', 'path', 'equals', 'source_ref'},
             {'when', 'observe', 'path', 'equals', 'source_ref'}, 'prerequisite')
        when = keys(prerequisite['when'], {'argument', 'equals'}, {'argument', 'equals'}, 'prerequisite selector')
        if when['argument'] not in spec['input']['properties']:
            fail('prerequisite selector must name a declared argument')
        checked(when['equals'], spec['input']['properties'][when['argument']], 'prerequisite selector')
        observer = tools.get(prerequisite['observe'])
        ref = parse_ref(prerequisite['source_ref'])
        if (observer is None or observer['effectful'] or observer['output']['kind'] != 'json'
                or observer['input'].get('required') or not _PATH.fullmatch(prerequisite['path'])
                or type(prerequisite['equals']) not in (str, bool, int, float)
                or ref is None or ref.path != source['path'] or ref.end - ref.line > 200):
            fail('prerequisite needs source-cited readonly observation and finite equality')
    if safety is not None:
        keys(safety, {'command', 'arguments', 'observe', 'path', 'equals'},
             {'command', 'arguments', 'observe', 'path', 'equals'}, 'safety')
        if (safety['command'] not in tools or safety['observe'] not in tools
                or not tools[safety['command']]['effectful'] or tools[safety['observe']]['effectful']
                or tools[safety['observe']]['output']['kind'] != 'json'
                or not _PATH.fullmatch(safety['path'])
                or type(safety['equals']) not in (str, bool, int, float)):
            fail('safety needs declared effectful command and readonly JSON observation')
        checked(safety['arguments'], tools[safety['command']]['input'], 'protective arguments')
    commands, reads, writes = commands or {}, reads or {}, writes or {}
    encoded({'commands': commands, 'reads': reads, 'writes': writes})
    if writes:
        fail('parameter writes are not supported; declare finite tools')
    for spec in commands.values():
        _projection(spec,tools,source)
    if set(tools) != {spec['tool'] for spec in commands.values()}:
        fail('every selected tool must have a primary command; observations cannot replace tools')
    for name, spec in reads.items():
        keys(spec, {'tool', 'path'}, {'tool', 'path'}, 'read')
        if (not _NAME.fullmatch(name) or spec['tool'] not in tools or tools[spec['tool']]['effectful']
                or tools[spec['tool']]['output']['kind'] != 'json' or not _PATH.fullmatch(spec['path'])
                or tools[spec['tool']]['input'].get('required')):
            fail('reads require an argument-free readonly JSON tool and a public path')
    result = copy.deepcopy(raw)
    result['request_timeout_ms'] = integer(raw.get('request_timeout_ms', 1000), 'request timeout', 60000)
    result['stop_timeout_ms'] = integer(raw.get('stop_timeout_ms', 1000), 'stop timeout', 10000)
    result['max_message_bytes'] = integer(raw.get('max_message_bytes', MAX_BYTES), 'message budget', MAX_BYTES)
    if type(raw.get('owned_transport', True)) is not bool:
        fail('owned_transport must be boolean')
    result['owned_transport'] = raw.get('owned_transport', True)
    result['commands'], result['reads'] = copy.deepcopy(commands), copy.deepcopy(reads)
    return result
