"""Finite compiler, immutable projection and exact client-source boundaries."""
import copy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mhs.driver import DriverDefinitionError, HttpDriver
from mhs.driver.http_config import compile_http, plain
from mhs.driver.http_check import prove_routes, SOURCE_PATH
from mhs.driver.loader import import_driver_module

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures' / 'http_ot2'
fixture = import_driver_module(FIXTURE)


def compiled(config=None):
    return compile_http(config if config is not None else fixture.CONFIG, fixture.Driver.commands, fixture.Driver.reads)


class Tree:
    def __init__(self, text=None):
        self.text = (FIXTURE / 'upstream/ot2_driver_http.py.txt').read_text() if text is None else text
    def read_text(self, name):
        return self.text if name == SOURCE_PATH else None


class ConfigurationTests(unittest.TestCase):
    def test_complete_profile_is_detached(self):
        raw = copy.deepcopy(fixture.CONFIG)
        got = compiled(raw)
        raw['routes']['play']['json']['data']['actionType'] = 'stop'
        self.assertEqual(got['routes']['play']['json']['data']['actionType'], 'play')
        self.assertEqual(len(got['workflow']), 9)

    def test_origin_and_unbounded_values_refused(self):
        for key, value in [('origin', 'http://user:password@host'), ('origin', 'http://host/path'),
                           ('origin', 'http://host/#part'), ('origin', 'http://host/?q=1'),
                           ('origin', '//host'), ('origin', 'file:///tmp/x'), ('origin', 'http://host\\other'),
                           ('origin', 'http://%68ost'), ('origin', 'http://host:0'),
                           ('headers', {'Authorization': 'test'}), ('request_timeout_ms', 0),
                           ('request_timeout_ms', True), ('workflow_timeout_ms', 600001),
                           ('max_polls', 10001), ('owned_transport', 1), ('auth_ref', '../policy'),
                           ('unknown', {}), ('profile', 'autodiscover')]:
            raw = copy.deepcopy(fixture.CONFIG); raw[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(DriverDefinitionError): compiled(raw)

    def test_unsafe_route_or_template_refused(self):
        for role, key, value in [('play','path','/runs/{input.url}/actions'), ('play','path','https://host/run'),
                ('play','path','/runs/../actions'), ('play','path','/runs/%2f/actions'),
                ('play','method',[]), ('play','json',{'data':{'actionType':'stop'}}),
                ('create','json',{'data':{'protocolId':{'$job':'unknown'}}}),
                ('commands','query',{'cursor':0,'pageLength':1000000}), ('status','source_ref','../a.py:3'),
                ('status','source_ref',SOURCE_PATH+':1-999'), ('status','source_method','__getattr__')]:
            raw=copy.deepcopy(fixture.CONFIG); raw['routes'][role][key]=value
            with self.subTest(role=role,key=key), self.assertRaises(DriverDefinitionError): compiled(raw)

    def test_weakened_response_ownership_or_schema_refused(self):
        for role, patch_ in [('status', {'correlation':{}}), ('status', {'required':{'data.status':'string'}}),
                             ('upload', {'required':{}}), ('list', {'required':{'data':'object'}}),
                             ('play', {'status':[302]}), ('play', {'status':[True]}), ('play', {'status':[{}]})]:
            raw=copy.deepcopy(fixture.CONFIG);raw['routes'][role]['response'].update(patch_)
            with self.subTest(role=role,patch=patch_), self.assertRaises(DriverDefinitionError): compiled(raw)

    def test_bounded_json_rejects_hooks_cycles_and_aggregate_inputs(self):
        class String(str): pass
        circular=[];circular.append(circular)
        for value in (String('x'), {'x': float('nan')}, circular, ['x' * 8192] * 1025, [[0] * 4096] * 17):
            with self.subTest(kind=type(value).__name__), self.assertRaises(DriverDefinitionError): plain(value)

    def test_no_arbitrary_maps_or_artifact_paths(self):
        for field, value in [('path','../outside'), ('sha256','0'*63), ('max_bytes',False), ('filename','../outside.py')]:
            raw=copy.deepcopy(fixture.CONFIG);raw['artifacts']['controlled_protocol'][field]=value
            with self.subTest(field=field), self.assertRaises(DriverDefinitionError): compiled(raw)
        for commands, reads, writes in [({'bad':{'operation':[]}}, {}, {}), ({},{'bad':{'state':[]}},{}),
                                        ({},{},{'speed':{}})]:
            with self.assertRaises(DriverDefinitionError): compile_http(fixture.CONFIG,commands,reads,writes)


class ClassBoundaryTests(unittest.TestCase):
    def make(self):
        driver=fixture.Driver(backend='fake',base_dir=FIXTURE)
        self.addCleanup(driver.close)
        return driver

    def test_model_copy_and_runtime_mutation_rejection(self):
        driver=self.make(); model=driver._driver_model(); model.risk='R0'
        self.assertEqual(driver._driver_model().risk,'R2')
        for mutate in [lambda d:setattr(d._model,'risk','R0'),
                       lambda d:d._http_config['workflow'].update(play='stop'),
                       lambda d:d.options.update(origin='http://elsewhere.invalid')]:
            driver=self.make();mutate(driver)
            with self.assertRaises(DriverDefinitionError): HttpDriver._verified_model(driver)

    def test_config_only_methods_cannot_override_trusted_paths(self):
        for name in ('driver_model','_driver_model','bridge_config','make_bridge','_fill_model','call','close'):
            bad=type('Override', (fixture.Driver,), {name:lambda *args:None})
            with self.subTest(name=name), self.assertRaises(DriverDefinitionError): bad(backend='fake')
        class Descriptor:
            def __get__(self,instance,owner): return lambda *args:None
        for value in (None,Descriptor()):
            bad=type('Override',(fixture.Driver,),{'_fill_model':value})
            with self.assertRaises(DriverDefinitionError):bad(backend='fake')

    def test_profile_cannot_erase_permit_envelope_or_relabel_motion_as_safe(self):
        for key,member,value in [(fixture.RUN,'requires_permit',False),(fixture.RESUME,'requires_permit',False),
                                 (fixture.RESUME,'safe_state',True),(fixture.RUN,'risk','R0'),
                                 (fixture.RUN,'cancellable',False),(fixture.RUN,'long_running',False)]:
            class Variant(fixture.Driver):pass
            Variant.actions=copy.deepcopy(fixture.Driver.actions);setattr(Variant.actions[key],member,value)
            with self.subTest(key=key,member=member),self.assertRaises(DriverDefinitionError):Variant(backend='fake')
        for member,value in [('risk','R0'),('mode','simulated'),('estop_physical_ref','unproved.txt:1')]:
            Variant=type('Variant',(fixture.Driver,),{member:value})
            with self.subTest(member=member),self.assertRaises(DriverDefinitionError):Variant(backend='fake')
        class Variant(fixture.Driver):pass
        Variant.actions=copy.deepcopy(fixture.Driver.actions);Variant.actions[fixture.RUN].input['protocol'].limits=()
        with self.assertRaises(DriverDefinitionError):Variant(backend='fake')

    def test_hardware_projection_retains_limits_permits_and_stop_without_factory(self):
        from mhs.driver.check import _hardware_view_subject
        from mhs.driver.build import build_manifest
        driver=self.make();ctx=SimpleNamespace(cls=type(driver),instance=driver)
        shell=_hardware_view_subject(ctx)
        self.assertFalse(driver._native_ready)
        self.assertEqual(shell._model.risk,'R2')
        self.assertTrue(next(b for b in shell._model.bindings if b.capability_id==fixture.RUN).requires_permit)
        self.assertEqual(next(b for b in shell._model.bindings if b.capability_id==fixture.RUN).limits['protocol'],'operator_required')
        self.assertEqual(build_manifest(shell,backend='hardware')['mode'],'hardware')
        driver._model.estop=None
        with self.assertRaises(DriverDefinitionError): _hardware_view_subject(ctx)

    def test_native_helper_and_direct_factory_refuse_before_any_upstream_import(self):
        from importlib import import_module
        native=import_module('.native',fixture.__package__)
        before={name for name in sys.modules if name.split('.')[0] in ('requests','opentrons','ot2_interface')}
        with patch('importlib.import_module', side_effect=AssertionError('no upstream import')):
            with self.assertRaisesRegex(RuntimeError,'native admission blocked'): fixture.Driver(backend='hardware')
            with self.assertRaisesRegex(RuntimeError,'native admission blocked'): native.connect()
        self.assertEqual(before,{name for name in sys.modules if name.split('.')[0] in ('requests','opentrons','ot2_interface')})

    def test_stock_unsigned_loader_refuses_before_native_factory(self):
        from importlib import import_module
        from mhs.adapter import load_driver, LoadError
        native=import_module('.native',fixture.__package__)
        with tempfile.TemporaryDirectory() as state, patch.object(native,'connect',side_effect=AssertionError('sentinel')) as factory:
            with self.assertRaises(LoadError) as error:
                load_driver(FIXTURE,backend='hardware',allow_hardware=True,state_dir=state)
            self.assertEqual(error.exception.reason,'review_required')
            factory.assert_not_called()


class SourceProofTests(unittest.TestCase):
    def test_exact_bundled_pinned_client_proves_all_selected_requests(self):
        self.assertEqual(len(prove_routes(Tree(),fixture.Driver.native,compiled())),9)

    def test_edited_wrong_class_or_unrelated_reference_is_refused(self):
        for tree,symbol in [(Tree(Tree().text.replace('"pause"','"stop"')),fixture.Driver.native),
                            (Tree(),'other:OT2_Driver')]:
            with self.assertRaises(ValueError): prove_routes(tree,symbol,compiled())
        for patch_ in ({'source_method':'execute'}, {'source_ref':SOURCE_PATH+':214'},
                       {'source_ref':SOURCE_PATH+':231-234'}, {'source_ref':'other.py:231'}):
            config=compiled(); config['routes']['pause'].update(patch_)
            with self.assertRaises(ValueError): prove_routes(Tree(),fixture.Driver.native,config)

    def test_gate_preloads_checker_and_guards_policy_tables_and_regex(self):
        import importlib
        from mhs.driver import check
        for name in check._GATE_MODULES: importlib.import_module(name)
        from mhs.driver import http_check,http_config
        before=check._integrity_snapshot()
        original=http_check._METHOD_CALLS.copy()
        try:
            http_check._METHOD_CALLS.clear()
            self.assertIn('mhs.driver.http_check._METHOD_CALLS',check._integrity_changes(before,check._integrity_snapshot()))
        finally: http_check._METHOD_CALLS.update(original)
        import re
        with patch.object(http_config,'_SEGMENT',re.compile('.*')):
            self.assertIn('mhs.driver.http_config._SEGMENT',check._integrity_changes(before,check._integrity_snapshot()))

    def test_recorded_wire_matches_complete_declared_profile(self):
        from mhs.driver.http_check import prove_wire
        from tests.bridges.test_http import FakeOT2
        from mhs.bridge.http import HttpBridge
        peer=FakeOT2();driver=HttpBridge(compiled(),transport=peer,base_dir=FIXTURE)
        try:driver.call(fixture.RUN,{'protocol':'controlled_protocol'})
        finally:driver.close()
        self.assertEqual([prove_wire(compiled(),message,50)[0] for message in peer.requests],['upload','create','play','status'])
        for field,value in [('origin','http://foreign.invalid'),('headers',{'Opentrons-Version':'99'}),
                            ('path','/runs/../../actions'),('json',{'data':{'actionType':'undeclared'}})]:
            message=copy.deepcopy(peer.requests[2]);message[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):prove_wire(compiled(),message,50)
        message=copy.deepcopy(peer.requests[0]);message['multipart']['sha256']='0'*64
        with self.assertRaises(ValueError):prove_wire(compiled(),message,50)


class HttpFreshGateIntegrityTests(unittest.TestCase):
    def test_fresh_stock_g3_detects_computed_checker_table_compiler_and_regex_changes(self):
        from tests.driver.test_qcodes_integrity import QcodesGateIntegrityTests
        runner=QcodesGateIntegrityTests()
        clean=runner.stock('')
        self.assertEqual(clean['gate']['status'],'pass')
        for leaf,mutation,member in [('http_check','module.prove_routes = lambda *args: []','prove_routes'),
                ('http_check','module._METHOD_CALLS.clear()','_METHOD_CALLS'),
                ('http_config','module.compile_http = lambda *args: {}','compile_http'),
                ('http_config',"import re\nmodule._SEGMENT = re.compile('.*')",'_SEGMENT')]:
            source='from importlib import import_module\nmodule = import_module(".".join(["mhs", "driver", '+repr(leaf)+']))\n'+mutation+'\n'
            result=runner.stock(source)
            with self.subTest(member=member):
                self.assertEqual(result['static'],[])
                self.assertEqual(result['gate']['status'],'fail')
                self.assertTrue(any(item['code']=='G3.GATE_TAMPERED' and member in item['message'] for item in result['gate']['findings']))
        from mhs.driver.check import static_findings
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'driver.py').write_text('from mhs.driver.http_check import prove_routes\n')
            self.assertIn('G3.FORBIDDEN',[item[0] for item in static_findings(directory)])


if __name__ == '__main__': unittest.main()
