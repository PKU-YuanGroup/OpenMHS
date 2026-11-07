"""Bounded source proof for the first HTTP request-shape profile.

This profile is deliberately tied to the reviewed OT2 client bytes. It proves
the selected requests in that client, not a deployed server, a schema or stop
retirement. A new pin/profile needs explicit source review, not fuzzy matching.
No upstream code is imported or executed.
"""
from __future__ import annotations

import ast
import base64
import hashlib

from .families import HttpDriver
from .http_config import _SEGMENT, encoded, OT2_CLIENT_PATH, OT2_CLIENT_SHA256, OT2_CLIENT_COMMIT
from .upstream import parse_ref

SOURCE_PATH = OT2_CLIENT_PATH
SOURCE_SHA256 = OT2_CLIENT_SHA256
SOURCE_SYMBOL = 'ot2_interface.ot2_driver_http:OT2_Driver'
SOURCE_COMMIT = OT2_CLIENT_COMMIT
_METHOD_CALLS = {
    'upload': ('transfer', 152, 'post'), 'create': ('transfer', 163, 'post'),
    'play': ('execute', 188, 'post'), 'pause': ('pause', 231, 'post'),
    'resume': ('resume', 253, 'post'), 'stop': ('cancel', 275, 'post'),
    'status': ('check_run_status', 295, 'get'), 'list': ('get_runs', 370, 'get'),
    'commands': ('get_run_log', 347, 'get'),
}


def prove_routes(tree, symbol, config):
    if symbol != SOURCE_SYMBOL or config['profile'] != 'ot2-run-v1':
        raise ValueError('no reviewed HTTP request-shape profile for this native symbol')
    text = tree.read_text(SOURCE_PATH)
    if not isinstance(text, str) or len(text.encode('utf-8')) > 1048576:
        raise ValueError('pinned HTTP client source is absent or exceeds the AST bound')
    if hashlib.sha256(text.encode('utf-8')).hexdigest() != SOURCE_SHA256:
        raise ValueError('HTTP request profile does not match the reviewed pinned client bytes')
    module = ast.parse(text)
    classes = [item for item in module.body if isinstance(item, ast.ClassDef) and item.name == 'OT2_Driver']
    if len(classes) != 1:
        raise ValueError('the exact native class is absent or ambiguous')
    functions = {item.name: item for item in classes[0].body if isinstance(item, ast.FunctionDef)}
    proven = []
    for role, name in config['workflow'].items():
        route = config['routes'][name]
        method, line, verb = _METHOD_CALLS[role]
        ref = parse_ref(route['source_ref'])
        if route['source_method'] != method or ref is None or ref.path != SOURCE_PATH:
            raise ValueError('route source reference must identify its exact native method')
        calls = [node for node in ast.walk(functions[method]) if isinstance(node, ast.Call)
                 and node.lineno == line and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Name) and node.func.value.id == 'requests'
                 and node.func.attr == verb]
        if len(calls) != 1 or not calls[0].lineno <= ref.line <= ref.end <= calls[0].end_lineno:
            raise ValueError('route reference must fall inside its exact source request call')
        if route['method'].lower() != verb:
            raise ValueError('route method differs from the pinned request')
        proven.append({'role': role, 'source_ref': route['source_ref'], 'method': method})
    return proven


def _matches(template, value):
    if type(template) is dict and set(template) == {'$job'}:
        return type(value) is str and _SEGMENT.fullmatch(value) is not None and value not in ('.', '..')
    if type(template) is dict:
        return type(value) is dict and set(value) == set(template) and all(_matches(item, value[key]) for key,item in template.items())
    if type(template) is list:
        return type(value) is list and len(value) == len(template) and all(_matches(a,b) for a,b in zip(template,value))
    return type(value) is type(template) and value == template


def prove_wire(config, message, timeout_ms):
    """Match one recorded request to the exact finite declared wire surface."""
    from ..bridge.http_replay import _request
    _request(message)
    if (message['origin'] != config['origin'] or message['headers'] != config['headers']
            or type(timeout_ms) is not int or not 0 < timeout_ms <= config['request_timeout_ms']
            or len(encoded(message)) > config['max_body_bytes'] or type(message['path']) is not str):
        raise ValueError('recorded HTTP origin, policy header, deadline or body bound differs from the declaration')
    matches=[]
    for role,name in config['workflow'].items():
        route=config['routes'][name]
        left,right=route['path'].split('/'),message['path'].split('/')
        if route['method'] != message['method'] or len(left) != len(right): continue
        if any(not (type(b) is str and _SEGMENT.fullmatch(b) and b not in ('.','..'))
               if a in ('{run_id}','{protocol_id}') else a != b for a,b in zip(left,right)): continue
        expected={'format','request_id','origin','method','path','headers','query'} | ({'json'} if 'json' in route else set()) | ({'multipart'} if 'multipart' in route else set())
        if set(message) != expected or not _matches(route.get('query',{}),message['query']): continue
        if 'json' in route and not _matches(route['json'],message['json']): continue
        if 'multipart' in route:
            part=message['multipart']
            if type(part) is not dict or set(part)!={'field','filename','sha256','size_bytes','data_base64'} or part['field']!='files': continue
            try: data=base64.b64decode(part['data_base64'],validate=True)
            except (TypeError,ValueError): continue
            if type(part['size_bytes']) is not int or len(data)!=part['size_bytes'] or hashlib.sha256(data).hexdigest()!=part['sha256']: continue
            if not any(part['sha256']==item['sha256'] and 0<len(data)<=item['max_bytes']
                       and part['filename']==item.get('filename',item['path'].split('/')[-1]) for item in config['artifacts'].values()): continue
        matches.append(role)
    if not matches: raise ValueError('recorded HTTP request has no exact declared method/route/query/body/artifact mapping')
    return matches


def check_http_surface(ctx, gate):
    try:
        config = HttpDriver.bridge_config.__func__(ctx.cls, ctx.model.resource_id)
        prove_routes(ctx.tree, ctx.cls.native, config)
    except Exception as exc:
        gate.error('HTTP_SOURCE_UNPROVEN', str(exc), 'driver.py')
        return
    observed=set()
    for log in ctx.logs:
        seen=set()
        for call in log.calls:
            if call.kind != 'call' or call.name != 'request': continue
            message=call.args[0] if call.args else call.kwargs.get('message')
            try:
                roles=prove_wire(config,message,call.kwargs.get('timeout_ms'))
                if message['request_id'] in seen: raise ValueError('recorded HTTP request identity was reused')
                seen.add(message['request_id']);observed.update(roles)
            except Exception as exc:
                gate.error('HTTP_WIRE_UNDECLARED',str(exc),'request')
    missing=set(config['workflow'])-observed
    if missing:
        gate.warning('HTTP_ROLES_NOT_EXERCISED','Recorded gate calls did not exercise these roles: '+', '.join(sorted(missing)),'request')
    gate.warning('HTTP_NATIVE_UNRESOLVED',
                 'Pinned client request shapes are proven; server schemas, remote retirement, '
                 'protocol effect envelope and deployment policy remain unresolved. Native admission is refused.',
                 'driver.py', SOURCE_PATH + ':132-386')
