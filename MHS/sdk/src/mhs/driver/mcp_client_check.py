"""Source and recorded-wire proof for finite MCP tools; no upstream execution."""
from __future__ import annotations

import ast
import hashlib

from .mcp_client_config import checked, encoded, keys
from .mcp_client_driver import McpClientDriver
from .upstream import parse_ref


def prove_tools(tree, config):
    source = config['source']
    text = tree.read_text(source['path'])
    if not isinstance(text, str) or len(text.encode()) > 1048576:
        raise ValueError('MCP source is absent or exceeds the finite AST bound')
    if hashlib.sha256(text.encode()).hexdigest() != source['sha256']:
        raise ValueError('MCP tool source differs from its reviewed bytes')
    if tree.pinned and tree.commit != source['commit']:
        raise ValueError('MCP source pin differs from its declared reviewed commit')
    module = ast.parse(text)
    proven = []
    for name, spec in config['tools'].items():
        functions = [node for node in module.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.name == name]
        if len(functions) != 1:
            raise ValueError('selected MCP tool is not a unique top-level function: ' + name)
        fn = functions[0]
        decorators = [node for node in fn.decorator_list if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Attribute) and node.func.attr == 'tool'
                      and isinstance(node.func.value, ast.Name) and node.func.value.id == source['receiver']
                      and not node.args and not node.keywords]
        if len(decorators) != 1:
            raise ValueError('selected function is not literally registered on the declared MCP receiver')
        ref = parse_ref(spec['source_ref'])
        if ref is None or ref.path != source['path'] or not fn.lineno <= ref.line <= ref.end <= fn.end_lineno:
            raise ValueError('MCP source reference does not cite its own tool function')
        args = fn.args
        if args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg:
            raise ValueError('MCP source has unsupported dynamic argument shape')
        names = [arg.arg for arg in args.args]
        required = names[:len(names) - len(args.defaults)]
        if (set(names) != set(spec['input']['properties'])
                or set(required) != set(spec['input'].get('required', []))):
            raise ValueError('MCP declared arguments/required defaults differ from source')
        defaults = {name: ast.literal_eval(value) for name, value in zip(names[len(required):], args.defaults)}
        if defaults != spec.get('defaults', {}):
            raise ValueError('MCP optional defaults differ from literal pinned source')
        if spec.get('prerequisite'):
            ref = parse_ref(spec['prerequisite']['source_ref'])
            if ref is None or not fn.lineno <= ref.line <= ref.end <= fn.end_lineno:
                raise ValueError('MCP prerequisite citation must stay inside its selected tool')
        if not spec['effectful'] and any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                                       and node.func.attr == 'write' for node in ast.walk(fn)):
            raise ValueError('MCP source has explicit writes but declaration erases their effects')
        proven.append({'tool': name, 'source_ref': spec['source_ref']})
    for binding in config['commands'].values():
        if 'select' in binding:
            ref=parse_ref(binding['select']['observe']['source_ref'])
            fn=next(node for node in module.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==binding['tool'])
            if ref is None or not fn.lineno<=ref.line<=ref.end<=fn.end_lineno:
                raise ValueError('MCP source-discriminated binding must cite its selected tool body')
    return proven


def prove_wire(config, message, timeout_ms, lane):
    encoded(message, config['max_message_bytes'])
    keys(message, {'jsonrpc', 'id', 'method', 'params'}, {'jsonrpc', 'id', 'method', 'params'}, 'wire')
    if (message['jsonrpc'] != '2.0' or type(message['id']) is not str or len(message['id']) != 32
            or any(c not in '0123456789abcdef' for c in message['id'])
            or type(timeout_ms) is not int or not 0 < timeout_ms <= config['request_timeout_ms']
            or lane not in ('normal', 'protective')):
        raise ValueError('MCP wire identity/deadline/lane differs from the finite contract')
    if message['method'] == 'tools/list' and message['params'] == {} and lane == 'normal':
        return None
    if message['method'] != 'tools/call':
        raise ValueError('undeclared MCP method')
    params = keys(message['params'], {'name', 'arguments'}, {'name', 'arguments'}, 'tool params')
    name = params['name']
    if type(name) is not str or name not in config['tools']:
        raise ValueError('undeclared MCP tool')
    checked(params['arguments'], config['tools'][name]['input'], 'recorded arguments')
    if lane == 'protective':
        safety = config.get('safety')
        if not safety or not ((name == safety['command'] and params['arguments'] == safety['arguments'])
                              or (name == safety['observe'] and params['arguments'] == {})):
            raise ValueError('undeclared protective transaction')
    return name


def check_mcp_client_surface(ctx, gate):
    try:
        config = McpClientDriver.bridge_config.__func__(ctx.cls, ctx.model.resource_id)
        prove_tools(ctx.tree, config)
    except Exception as exc:
        gate.error('MCP_SOURCE_UNPROVEN', str(exc), 'driver.py')
        return
    observed = set()
    for log in ctx.logs:
        seen = set()
        for call in log.calls:
            if call.kind != 'call' or call.name != 'exchange':
                continue
            message = call.args[0] if call.args else call.kwargs.get('message')
            try:
                name = prove_wire(config, message, call.kwargs.get('timeout_ms'), call.kwargs.get('lane'))
                if message['id'] in seen:
                    raise ValueError('MCP request identity was reused')
                seen.add(message['id'])
                if name is not None:
                    observed.add(name)
            except Exception as exc:
                gate.error('MCP_WIRE_UNDECLARED', str(exc), 'exchange')
    missing = set(config['tools']) - observed
    if missing:
        gate.warning('MCP_TOOLS_NOT_EXERCISED', 'Recorded gates did not exercise: ' + ', '.join(sorted(missing)), 'exchange')
    gate.warning('MCP_NATIVE_UNRESOLVED', 'Source registration and finite controlled calls are proven; native transport '
                 'ownership, deployment policy and device stopping remain unresolved. Native admission refuses before I/O.',
                 'driver.py')
