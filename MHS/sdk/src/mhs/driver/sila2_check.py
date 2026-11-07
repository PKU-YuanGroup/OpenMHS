"""Exact, static Phenix declaration proof. Never a native retirement proof.

No upstream module, generated protobuf, compiler, network or simulator runs.
Only this reviewed device pin has a source profile. Other finite controlled
contracts remain usable in SDK tests but have no accepted native source proof.
"""
from __future__ import annotations

import ast
import hashlib
import re
import uuid
import xml.etree.ElementTree as ET

from .sila2 import Sila2Driver
from .sila2_config import PEER_FORMAT, canonical, integer, keys, plain, validate_fields
from .upstream import parse_ref

SOURCE_COMMIT = '0b572380e06977c1920510773b4bfee7bcd0eec5'
SOURCE_SYMBOL = 'phenix_imager.feature_implementations.pheniximager_impl:PhenixImagerImpl'
SOURCE_FEATURE = 'calico.automation/extended/PhenixImager/v1'
_SOURCES = {
    'fdl': ('servers/phenix_imager/PhenixImager.sila.xml', '0a1553a5f453d6e38b0aa80be5cb5b569e84cc3a69e3f6bbdf91036ebd8cfbea'),
    'proto': ('servers/phenix_imager/phenix_imager/generated/pheniximager/PhenixImager.proto', '4e54068064164d5df4b99f810b68f8416622326a5cead8379f0a57df5559f3dd'),
    'implementation': ('servers/phenix_imager/phenix_imager/feature_implementations/pheniximager_impl.py', 'a84f91786e0da27e5e22ed25b21432b9b5e3abff781bb540fe1938c2e8abefd0'),
}
_METHOD_LINES = {'Connect': 187, 'Disconnect': 207, 'StageIn': 220, 'StageOut': 242,
                 'Stop': 263, 'GoIdle': 275, 'GoStandby': 286, 'RunAcquisitionProtocol': 301,
                 'get_IsConnected': 153, 'get_DeviceState': 158, 'get_StagePosition': 164,
                 'get_PlateDetected': 170, 'get_AvailableProtocols': 178,
                 'get_DisplayIcon': 102, 'get_DeviceDescription': 106}
_UNITS = {('GoStandby', 'DurationSeconds'): 's', ('RunAcquisitionProtocol', 'TimeoutMinutes'): 'min'}
_BLOCK = re.compile(r'<(Command|Property)>.*?</\1>', re.DOTALL)
_IDENTIFIER = re.compile(r'<Identifier>([^<]+)</Identifier>')
_RPC = re.compile(r'\brpc\s+(\w+)\s*\(([^)]+)\)\s*returns\s*\(([^)]+)\)')
_OPERATIONS = frozenset({'describe', 'observe', 'invoke', 'property', 'subscribe', 'next',
                         'unsubscribe', 'result', 'binary_info', 'binary_chunk', 'binary_delete'})


def _xml(text):
    if type(text) is not str or len(text.encode()) > 1024 * 1024 or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('FDL must be bounded plain XML without entities or DTD')
    root = ET.fromstring(text)
    nodes = list(root.iter())
    if len(nodes) > 4096:
        raise ValueError('FDL exceeds the finite element bound')
    for node in nodes:
        node.tag = node.tag.rsplit('}', 1)[-1]
    return root


def _dtype(node):
    if node is None or len(node) != 1:
        raise ValueError('unsupported or ambiguous FDL DataType')
    item = node[0]
    if item.tag == 'Basic' and item.text in ('Boolean', 'Integer', 'Real', 'String', 'Binary'):
        return {'type': item.text}
    if item.tag == 'List':
        return {'type': 'List', 'items': _dtype(item.find('DataType'))}
    if item.tag == 'Constrained':
        result = _dtype(item.find('DataType'))
        constraints = item.find('Constraints')
        if constraints is None: raise ValueError('missing constrained datatype predicates')
        for predicate in constraints:
            key = {'MinimalInclusive': 'min', 'MaximalInclusive': 'max'}.get(predicate.tag)
            if key is None or key in result: raise ValueError('unsupported or duplicate FDL predicate')
            result[key] = int(predicate.text) if result['type'] == 'Integer' else float(predicate.text)
        return result
    raise ValueError('FDL type needs an explicitly reviewed finite parser')


def _wire_type(spec):
    # SDK allocation limits and explicitly reviewed semantic units are not
    # asserted to be FDL physical constraints.
    result = {key: value for key, value in spec.items() if key not in ('max_length', 'max_items', 'max_bytes', 'unit')}
    if 'items' in result: result['items'] = _wire_type(result['items'])
    return result


def prove_declarations(text, config):
    """Compare all selected fields with primary FDL; no generated self-proof."""
    root = _xml(text)
    expected = '/'.join([root.get('Originator', ''), root.get('Category', ''),
                         root.findtext('Identifier', ''), 'v' + root.get('FeatureVersion', '').split('.')[0]])
    if root.tag != 'Feature' or expected != config['feature'] or root.get('SiLA2Version') != '1.1':
        raise ValueError('feature FQI/version differs from primary FDL')
    members = {}
    for node in root:
        if node.tag not in ('Command', 'Property'): continue
        name = node.findtext('Identifier')
        if not name or name in members: raise ValueError('missing or duplicate FDL member')
        observation = node.findtext('Observable')
        if observation not in ('Yes', 'No'): raise ValueError('missing exact observable declaration')
        kind = ('observable_' if observation == 'Yes' else '') + node.tag.lower()
        shape = {'kind': kind, 'input': {}, 'output': {}, 'intermediate': {}, 'errors': []}
        for tag, key in (('Parameter', 'input'), ('Response', 'output'), ('IntermediateResponse', 'intermediate')):
            for item in node.findall(tag):
                ident = item.findtext('Identifier')
                if not ident or ident in shape[key]: raise ValueError('duplicate FDL field')
                shape[key][ident] = _dtype(item.find('DataType'))
        if node.tag == 'Property': shape['output'] = {name: _dtype(node.find('DataType'))}
        errors = node.find('DefinedExecutionErrors')
        if errors is not None: shape['errors'] = [item.text for item in errors]
        members[name] = shape
    if set(members) != set(config['members']):
        raise ValueError('complete selected feature members differ from primary FDL')
    blocks = {}
    for match in _BLOCK.finditer(text):
        ident = _IDENTIFIER.search(match.group())
        if ident:
            name = ident[1]
            if name in blocks: raise ValueError('ambiguous member source range')
            blocks[name] = (text.count('\n', 0, match.start()) + 1,
                            text.count('\n', 0, match.start() + ident.start()) + 1,
                            text.count('\n', 0, match.end()) + 1)
    proven = []
    for name, source in members.items():
        member = config['members'][name]
        actual = {key: member[key] for key in ('kind', 'errors')}
        actual.update({key: {n: _wire_type(t) for n, t in member.get(key, {}).items()}
                       for key in ('input', 'output', 'intermediate')})
        if canonical(actual) != canonical(source): raise ValueError('FDL type/kind/constraint/error mismatch: ' + name)
        if member['effect'] != ('read' if member['kind'].endswith('property') else 'effectful'):
            raise ValueError('selected Phenix command effects cannot be relabeled read-only')
        for key in ('input', 'output', 'intermediate'):
            for field, spec in member.get(key, {}).items():
                if spec.get('unit') != _UNITS.get((name, field)):
                    raise ValueError('semantic unit differs from the reviewed primary description')
        ref = parse_ref(member['source_ref']); start, ident, end = blocks[name]
        if ref is None or ref.path != config['fdl']['path'] or not start <= ref.line <= ident or ref.end != end:
            raise ValueError('member citation must cover its exact FDL identifier through closing declaration')
        proven.append({'member': name, 'kind': member['kind'], 'ref': member['source_ref']})
    return proven


def prove_profile(tree, symbol, config):
    if (symbol != SOURCE_SYMBOL or config['commit'] != SOURCE_COMMIT or config['feature'] != SOURCE_FEATURE
            or config['runtime_profile'] != 'sila2-0.14.0' or config['stop'] != 'Stop'):
        raise ValueError('no reviewed static device profile for this symbol/pin')
    texts = {}
    for role, (path, digest) in _SOURCES.items():
        if config[role]['path'] != path or config[role]['sha256'] != digest:
            raise ValueError('source selector does not name the reviewed exact bytes')
        text = tree.read_text(path)
        if type(text) is not str or len(text.encode()) > 1024 * 1024 or hashlib.sha256(text.encode()).hexdigest() != digest:
            raise ValueError('missing, changed or unbounded primary source: ' + role)
        texts[role] = text
    proven = prove_declarations(texts['fdl'], config)
    classes = [node for node in ast.parse(texts['implementation']).body if isinstance(node, ast.ClassDef) and node.name == 'PhenixImagerImpl']
    if len(classes) != 1: raise ValueError('exact implementation class missing')
    methods = {node.name: node for node in classes[0].body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for name, line in _METHOD_LINES.items():
        if name not in methods or methods[name].lineno != line or all(isinstance(n, (ast.Expr, ast.Pass)) for n in methods[name].body):
            raise ValueError('generated annotation or missing implementation is not a native method proof')
    rpcs = {name: (left.strip(), right.strip()) for name, left, right in _RPC.findall(texts['proto'])}
    expected = {}
    namespace = 'sila2.calico.automation.extended.pheniximager.v1.'
    for name, member in config['members'].items():
        if member['kind'] == 'property':
            expected['Get_' + name] = (namespace + 'Get_' + name + '_Parameters', namespace + 'Get_' + name + '_Responses')
        elif member['kind'] == 'command':
            expected[name] = (namespace + name + '_Parameters', namespace + name + '_Responses')
        else:
            expected[name] = (namespace + name + '_Parameters', 'sila2.org.silastandard.CommandConfirmation')
            expected[name + '_Info'] = ('sila2.org.silastandard.CommandExecutionUUID', 'stream sila2.org.silastandard.ExecutionInfo')
            expected[name + '_Intermediate'] = ('sila2.org.silastandard.CommandExecutionUUID', 'stream ' + namespace + name + '_IntermediateResponses')
            expected[name + '_Result'] = ('sila2.org.silastandard.CommandExecutionUUID', namespace + name + '_Responses')
    if rpcs != expected or 'import "SiLAFramework.proto";' not in texts['proto']:
        raise ValueError('generated protocol differs from reviewed FDL/RPC distinctions')
    return proven


def _uuid(value):
    if type(value) is not str or str(uuid.UUID(value)) != value: raise ValueError('canonical correlation UUID required')


def prove_wire(config, message, timeout_ms):
    plain(message, binary=True)
    keys(message, {'format', 'request_id', 'owner_id', 'generation', 'endpoint', 'feature', 'runtime_profile',
                   'descriptor_sha256', 'operation', 'member', 'payload'},
         {'format', 'request_id', 'owner_id', 'generation', 'endpoint', 'feature', 'runtime_profile',
          'descriptor_sha256', 'operation', 'member', 'payload'})
    for key in ('request_id', 'owner_id', 'generation'): _uuid(message[key])
    integer(timeout_ms, 1, config['request_timeout_ms'], 'request timeout')
    for key, value in [('format', PEER_FORMAT), ('endpoint', config['endpoint']), ('feature', config['feature']),
                       ('runtime_profile', config['runtime_profile']), ('descriptor_sha256', config['fdl']['sha256'])]:
        if canonical(message[key]) != canonical(value): raise ValueError('request identity/profile differs')
    operation, name, payload = message['operation'], message['member'], message['payload']
    if type(operation) is not str or operation not in _OPERATIONS: raise ValueError('unknown operation')
    if operation in ('describe', 'observe'):
        if name is not None or payload != {}: raise ValueError('controlled metadata/proof takes no dynamic selectors')
        return operation
    member = config['members'].get(name)
    if member is None: raise ValueError('undeclared member')
    if operation == 'invoke':
        keys(payload, {'input', 'metadata'}, {'input', 'metadata'})
        if not member['kind'].endswith('command'): raise ValueError('cannot invoke a property')
        validate_fields(member['input'], payload['input'], profile=config['runtime_profile'])
        if canonical(payload['metadata']) != canonical(config['metadata']): raise ValueError('static typed metadata changed')
    elif operation == 'property':
        if member['kind'] != 'property' or payload != {}: raise ValueError('wrong property interface')
    elif operation == 'subscribe':
        keys(payload, {'kind', 'execution_uuid'}, {'kind', 'execution_uuid'})
        expected = ('info', 'intermediate') if member['kind'] == 'observable_command' else ('property',) if member['kind'] == 'observable_property' else ()
        if payload['kind'] not in expected: raise ValueError('wrong streaming interface')
        if payload['kind'] == 'property':
            if payload['execution_uuid'] is not None: raise ValueError('property has no execution UUID')
        else: _uuid(payload['execution_uuid'])
    elif operation in ('next', 'unsubscribe'):
        required = {'stream_id'} | ({'stream_owner'} if operation == 'unsubscribe' else set())
        keys(payload, required, required)
        for value in payload.values(): _uuid(value)
    elif operation == 'result':
        keys(payload, {'execution_uuid'}, {'execution_uuid'}); _uuid(payload['execution_uuid'])
        if member['kind'] != 'observable_command': raise ValueError('result requires observable command')
    else:
        extra = {'offset', 'length'} if operation == 'binary_chunk' else {'binary_owner'} if operation == 'binary_delete' else set()
        keys(payload, {'binary_uuid'} | extra, {'binary_uuid'} | extra); _uuid(payload['binary_uuid'])
        if not any(item['type'] == 'Binary' for item in member['output'].values()): raise ValueError('member has no primary binary')
        if operation == 'binary_chunk':
            integer(payload['offset'], 0, 8 * 1024 * 1024, 'offset'); integer(payload['length'], 1, 65536, 'chunk length')
        if operation == 'binary_delete': _uuid(payload['binary_owner'])
    return operation + ':' + name


def check_sila2_surface(ctx, gate):
    # G7 tests the selected declared source and recorded controlled requests.
    # A synthetic SDK fixture pins its primary text through prove_profile's
    # exact hashes; it has no registry/upstream task pin to impersonate.
    try:
        config = Sila2Driver.bridge_config.__func__(ctx.cls, ctx.model.resource_id)
        prove_profile(ctx.tree, ctx.cls.native, config)
        if not ctx.synthetic and ctx.commit != SOURCE_COMMIT:
            raise ValueError('task pin differs from static device profile')
    except Exception as exc:
        gate.error('SILA_SOURCE_UNPROVEN', str(exc), 'driver.py')
    else:
        for log in ctx.logs:
            seen = set()
            for call in log.calls:
                if call.kind != 'call' or call.name != 'request': continue
                message = call.args[0] if call.args else call.kwargs.get('message')
                try:
                    prove_wire(config, message, call.kwargs.get('timeout_ms'))
                    if message['request_id'] in seen: raise ValueError('duplicate dispatch identity')
                    seen.add(message['request_id'])
                except Exception as exc: gate.error('SILA_WIRE_UNDECLARED', str(exc), 'request')
    # The unconditional Sila2Driver/bridge admission refusal stays independent
    # of this fake contract proof, including for a signed or direct constructor.
    if ctx.backend != 'fake':
        gate.error('SILA_NATIVE_UNRESOLVED',
                   'Only the controlled fake contract is checked. Native gRPC/protobuf, bounded remote retirement, '
                   'deployed runtime, device effects/limits and license acceptance remain unresolved; '
                   'all native factories remain refused.', 'driver.py')
