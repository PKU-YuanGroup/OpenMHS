"""Typed, bounded, source-checked contract and unconditionally refused native path."""
import copy
from importlib import import_module
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

from mhs.driver import DriverDefinitionError, Sila2Driver
from mhs.driver.sila2_config import canonical, compile_sila2, input_values, plain, type_spec, validate, validate_fields
from mhs.driver.sila2_check import prove_declarations, prove_profile, prove_wire
from tests.driver.sila2_support import FIXTURE, bridge, compiled, connect, fixture


class SilaTypeTests(unittest.TestCase):
    def test_deterministic_detached_complete_descriptor(self):
        raw = copy.deepcopy(fixture.CONFIG)
        left = compile_sila2(raw, fixture.Driver.commands, fixture.Driver.reads)
        self.assertEqual(canonical(left), canonical(compiled()))
        raw['members']['StageOut']['effect'] = 'read'
        self.assertEqual(left['members']['StageOut']['effect'], 'effectful')
        self.assertEqual(len(left['members']), 15)

    def test_only_finite_concrete_data_no_callback_expression_or_unbounded_payload(self):
        class Str(str): pass
        cycle = []; cycle.append(cycle)
        for value in (Str('x'), lambda: None, {'f': float('nan')}, cycle, ['x'] * 1025, 1 << 65,
                      {'a' * 257: 1}, 'x' * (8 * 1024 * 1024 + 1)):
            with self.subTest(kind=type(value).__name__), self.assertRaises(DriverDefinitionError): plain(value)
        for kind in ('Any', 'Date', 'Time', 'eval', '__dict__'):
            with self.subTest(kind=kind), self.assertRaises(DriverDefinitionError): type_spec({'type': kind})

    def test_bool_integer_real_and_enum_identity(self):
        for spec, good, bad in [({'type': 'Integer', 'min': -2, 'max': 3}, 2, [True, 1.0, 4, 2**63]),
                                ({'type': 'Boolean'}, False, [0, 1, 'false']),
                                ({'type': 'Real', 'min': 0, 'max': 1}, .5, [True, float('nan'), float('inf'), -1]),
                                ({'type': 'Integer', 'enum': [1, 2]}, 1, [True, 3])]:
            self.assertEqual(validate(spec, good), good)
            for item in bad:
                with self.subTest(spec=spec, item=item), self.assertRaises((DriverDefinitionError, ValueError)): validate(spec, item)
        self.assertNotEqual(canonical(True), canonical(1))
        self.assertNotEqual(canonical(1), canonical(1.0))

    def test_nested_optional_structure_list_and_binary_bounds(self):
        spec = {'type': 'Structure', 'fields': {'values': {'type': 'List', 'items': {'type': 'Integer'}, 'max_items': 2},
                'label': {'type': 'String', 'max_length': 4, 'optional': True}}}
        self.assertEqual(validate(spec, {'values': [1, 2]}), {'values': [1, 2]})
        for value in ({}, {'values': [1, 2, 3]}, {'values': [True]}, {'values': [], 'extra': 1}, {'values': [], 'label': 'ééé'}):
            with self.subTest(value=value), self.assertRaises(DriverDefinitionError): validate(spec, value)
        self.assertEqual(validate({'type': 'Binary', 'max_bytes': 3}, b'abc'), b'abc')
        for data in (b'abcd', 'abc', {'size_bytes': 2**30, 'binary_uuid': 'a'*36, 'sha256': '0'*64}):
            with self.assertRaises(DriverDefinitionError): validate({'type': 'Binary', 'max_bytes': 3}, data)

    def test_duration_and_versioned_calendar_semantics(self):
        self.assertEqual(validate({'type': 'Duration'}, {'seconds': 2, 'nanos': 9}), {'seconds': 2, 'nanos': 9})
        for data in ({'seconds': True, 'nanos': 0}, {'seconds': -1, 'nanos': 0}, {'seconds': 1, 'nanos': 10**9}, 2):
            with self.assertRaises((DriverDefinitionError, ValueError)): validate({'type': 'Duration'}, data)
        stamp = {'year': 2024, 'month': 2, 'day': 29, 'hour': 23, 'minute': 59, 'second': 59,
                 'timezone': {'hours': -7, 'minutes': 30}, 'millisecond': 321}
        self.assertEqual(validate({'type': 'Timestamp'}, stamp), stamp)
        with self.assertRaises(DriverDefinitionError): validate({'type': 'Timestamp'}, stamp, profile='sila2-0.1.0')
        for bad in ({**stamp, 'year': 2023}, {**stamp, 'second': 60}, {**stamp, 'millisecond': 1000}):
            with self.assertRaises((DriverDefinitionError, ValueError)): validate({'type': 'Timestamp'}, bad)

    def test_nontrivial_unit_conversion_and_no_integer_rounding(self):
        config = compiled(); binding = dict(config['commands'][fixture.CAPS['RunAcquisitionProtocol']], input_units={'TimeoutMinutes': 's'})
        values = {**fixture.EXAMPLES['RunAcquisitionProtocol'], 'TimeoutMinutes': 120}
        self.assertEqual(input_values(config, binding, values)['TimeoutMinutes'], 2)
        values['TimeoutMinutes'] = 61
        with self.assertRaises(DriverDefinitionError): input_values(config, binding, values)
        for unit in ('Cel', '/min', 'unknown'):
            commands = copy.deepcopy(fixture.Driver.commands)
            commands[fixture.CAPS['RunAcquisitionProtocol']]['input_units'] = {'TimeoutMinutes': unit}
            with self.assertRaises((DriverDefinitionError, ValueError)): compile_sila2(fixture.CONFIG, commands, fixture.Driver.reads)

    def test_source_profile_endpoints_and_unbounded_declarations_are_refused(self):
        for key, value in [('endpoint', 'http://user@host'), ('endpoint', '../peer'), ('peer_format', 'grpc'),
                           ('runtime_profile', 'latest'), ('feature', 'arbitrary'), ('commit', 'a'*39),
                           ('request_timeout_ms', False), ('stop_timeout_ms', 30001), ('max_operations', 0),
                           ('call', 'python:eval')]:
            with self.subTest(key=key), self.assertRaises((DriverDefinitionError, ValueError)): compiled(**{key: value})
        raw = copy.deepcopy(fixture.CONFIG); raw['members']['Stop']['completion'] = 'returned'
        with self.assertRaises(DriverDefinitionError): compile_sila2(raw)
        raw = copy.deepcopy(fixture.CONFIG); raw['members']['RunAcquisitionProtocol']['effect'] = 'read'
        with self.assertRaises(DriverDefinitionError): compile_sila2(raw)

    def test_typed_static_metadata_cannot_smuggle_arbitrary_headers(self):
        item = {'identifier': fixture.CONFIG['feature'] + '/Metadata/Operator', 'type': {'type': 'String', 'max_length': 20}, 'value': 'controlled'}
        config = compiled(metadata=[item]); self.assertEqual(config['metadata'], [item])
        for bad in ([item, item], [{**item, 'identifier': 'Authorization'}], [{**item, 'value': 'x'*21}],
                    [{**item, 'headers': {'Authorization': 'x'}}], [{**item, 'identifier': 'other/Metadata/X'}]):
            with self.assertRaises(DriverDefinitionError): compiled(metadata=bad)


class SilaClassTests(unittest.TestCase):
    def test_native_refusal_and_unsigned_loader_are_separate_before_import(self):
        from mhs.adapter import load_driver, LoadError
        from mhs.bridge.sila2 import native_unavailable
        native = import_module('.native', fixture.__package__)
        before = {name for name in sys.modules if name.split('.')[0] in {'sila2', 'unitelabs', 'grpc', 'google'}}
        with patch('importlib.import_module', side_effect=AssertionError('native import forbidden')):
            with self.assertRaisesRegex(RuntimeError, 'admission refused'): fixture.Driver(backend='hardware')
            with self.assertRaisesRegex(RuntimeError, 'admission refused'): native_unavailable()
        with tempfile.TemporaryDirectory() as state, patch.object(native, 'connect', side_effect=AssertionError('native factory')) as factory:
            with self.assertRaises(LoadError) as error: load_driver(FIXTURE, backend='hardware', allow_hardware=True, state_dir=state)
            self.assertEqual(error.exception.reason, 'review_required'); factory.assert_not_called()
        self.assertEqual(before, {name for name in sys.modules if name.split('.')[0] in {'sila2', 'unitelabs', 'grpc', 'google'}})

    def test_class_hooks_authority_and_effect_envelope_cannot_be_weakened(self):
        for name in ('call', 'close', '_verify', 'make_bridge', 'bridge_config', '_fill_model'):
            bad = type('Bad', (fixture.Driver,), {name: lambda *args: None})
            with self.subTest(name=name), self.assertRaises(DriverDefinitionError): bad(backend='fake')
        for key, attribute, value in [(fixture.CAPS['StageOut'], 'safe_state', True),
                (fixture.CAPS['Connect'], 'requires_permit', False), (fixture.CAPS['Connect'], 'risk', 'R0'),
                (fixture.CAPS['Connect'], 'cancellable', True), (fixture.CAPS['RunAcquisitionProtocol'], 'long_running', False)]:
            class Bad(fixture.Driver): pass
            Bad.actions = copy.deepcopy(fixture.Driver.actions); setattr(Bad.actions[key], attribute, value)
            with self.assertRaises(DriverDefinitionError): Bad(backend='fake')
        for mutate in (lambda d: d._sila_config['members']['Stop'].update(effect='read'),
                       lambda d: setattr(d._model, 'risk', 'R0'), lambda d: d.options.update(endpoint='foreign')):
            driver = fixture.Driver(backend='fake', base_dir=FIXTURE); self.addCleanup(driver.close)
            mutate(driver)
            with self.assertRaises(DriverDefinitionError): driver.call(fixture.CAPS['Connect'], fixture.EXAMPLES['Connect'])
            self.assertFalse(driver._native_ready)

    def test_binary_property_cannot_be_downgraded_to_read_metadata_or_arbitrary_projection(self):
        for bindings, reads in [({fixture.CAPS['DisplayIcon']: {'member': 'DisplayIcon'}}, {}),
                ({}, {'icon': {'member': 'DisplayIcon', 'field': 'DisplayIcon'}}),
                ({fixture.CAPS['DisplayIcon']: {'member': 'DisplayIcon', 'artifact': 'DisplayIcon', 'media_type': 'text/html'}}, {})]:
            with self.assertRaises(DriverDefinitionError): compile_sila2(fixture.CONFIG, bindings, reads)
        class Bad(fixture.Driver): pass
        Bad.actions = copy.deepcopy(fixture.Driver.actions)
        Bad.actions[fixture.CAPS['Connect']].input['PhenixHost'].limits = ()
        with self.assertRaises(DriverDefinitionError): Bad(backend='fake')


class SilaSourceAndGateTests(unittest.TestCase):
    def test_unpinned_or_missing_primary_profile_cannot_pass(self):
        class Tree:
            def read_text(self, path): return ''
        for symbol, config in [('other:Class', compiled()), (fixture.Driver.native, compiled()),
                               (fixture.Driver.native, compiled(commit='0'*40))]:
            with self.assertRaises(ValueError): prove_profile(Tree(), symbol, config)

    def test_xml_external_entities_duplicate_members_and_wrong_types_refused(self):
        raw = '<Feature xmlns="http://www.sila-standard.org" SiLA2Version="1.1" FeatureVersion="1.0" Originator="calico.automation" Category="extended"><Identifier>PhenixImager</Identifier></Feature>'
        for text in (raw, '<!DOCTYPE a SYSTEM "file:///etc/passwd">' + raw,
                     '<!ENTITY x SYSTEM "https://example.invalid">' + raw, 'x'*(1024*1024+1)):
            with self.assertRaises(ValueError): prove_declarations(text, compiled())

    def test_recorded_wire_matches_every_observed_finite_control(self):
        peer, driver = bridge(self); connect(driver)
        driver.call(fixture.CAPS['RunAcquisitionProtocol'], fixture.EXAMPLES['RunAcquisitionProtocol'])
        driver.read('main'); driver.safe_state(); driver.reset()
        config = compiled()
        roles = {prove_wire(config, request, 1) for request in peer.requests}
        self.assertIn('invoke:RunAcquisitionProtocol', roles); self.assertIn('result:RunAcquisitionProtocol', roles)
        for key, value in [('endpoint', 'foreign'), ('operation', 'exec'), ('member', '__getattr__'),
                            ('runtime_profile', 'latest'), ('descriptor_sha256', '0'*64)]:
            request = copy.deepcopy(peer.requests[1]); request[key] = value
            with self.subTest(key=key), self.assertRaises((DriverDefinitionError, ValueError)): prove_wire(config, request, 1)
        request = copy.deepcopy(peer.requests[1]); request['payload']['input']['PhenixHost'] = ['wrong']
        with self.assertRaises(DriverDefinitionError): prove_wire(config, request, 1)

    def test_stock_g3_covers_lazy_compiler_checker_bridge_replay_and_policy(self):
        from tests.driver.test_qcodes_integrity import QcodesGateIntegrityTests
        runner = QcodesGateIntegrityTests()
        self.assertEqual(runner.stock('')['gate']['status'], 'pass')
        for module, mutation, member in [('driver.sila2_config', 'module.compile_sila2=lambda *args: {}', 'compile_sila2'),
                ('driver.sila2_check', 'module._METHOD_LINES.clear()', '_METHOD_LINES'),
                ('driver.sila2_check', 'module._SOURCES=dict(module._SOURCES)', '_SOURCES'),
                ('driver.sila2_config', "import re\nmodule._NAME=re.compile('.*')", '_NAME'),
                ('bridge.sila2', 'module.Sila2Bridge._observation=lambda *args: ({},True)', 'Sila2Bridge'),
                ('bridge.sila2_replay', 'module.Sila2ReplayPeer.request=lambda *args: {}', 'Sila2ReplayPeer')]:
            source = 'from importlib import import_module\nmodule=import_module(".".join(["mhs",'+repr(module)+']))\n' + mutation + '\n'
            with self.subTest(module=module, member=member):
                result = runner.stock(source); self.assertEqual(result['static'], [])
                self.assertEqual(result['gate']['status'], 'fail', result)
                self.assertTrue(any(f['code'] == 'G3.GATE_TAMPERED' and member in f['message'] for f in result['gate']['findings']), result)


if __name__ == '__main__': unittest.main()
