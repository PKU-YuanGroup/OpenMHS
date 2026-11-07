"""Finite declarations, literal source proof and stock integrity boundaries."""
import copy
import importlib
from pathlib import Path
import sys
import tempfile
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mhs.driver import DriverDefinitionError, McpClientDriver
from mhs.driver.loader import import_driver_module
from mhs.driver.mcp_client_config import compile_mcp_client, plain
from mhs.driver.mcp_client_check import prove_tools, prove_wire

FIXTURE=Path(__file__).resolve().parents[1]/'fixtures/mcp_rigol'
fixture=import_driver_module(FIXTURE)
ControlledPeer=importlib.import_module('.fake',fixture.__package__).ControlledPeer


def compiled(config=None):
    from mhs.driver.mcp_client_driver import _command_maps
    return compile_mcp_client(config or fixture.CONFIG,_command_maps(fixture.Driver),fixture.Driver.reads)


class Tree:
    pinned=True
    commit=fixture.PIN
    def __init__(self,text=None):self.text=text if text is not None else (FIXTURE/'upstream/server.py.txt').read_text()
    def read_text(self,path):return self.text if path==fixture.SOURCE else None


class ConfigurationTests(unittest.TestCase):
    def test_complete_declared_authority_detached_with_effects_and_defaults(self):
        raw=copy.deepcopy(fixture.CONFIG);got=compiled(raw)
        self.assertEqual(len(got['tools']),13)
        self.assertTrue(got['tools']['get_waveform']['effectful'])
        self.assertTrue(got['tools']['get_measurement']['effectful'])
        raw['tools'].clear();self.assertEqual(len(got['tools']),13)
        self.assertEqual(got['tools']['get_waveform']['defaults']['max_points'],1000)

    def test_no_caller_code_endpoint_name_or_unbounded_schema(self):
        for key,value in [('endpoint','http://example.invalid'),('command',['python','-c','code']),
                          ('auth','secret'),('request_timeout_ms',False),('max_message_bytes',0),('owned_transport',1)]:
            raw=copy.deepcopy(fixture.CONFIG);raw[key]=value
            with self.subTest(key=key),self.assertRaises(DriverDefinitionError):compiled(raw)
        for bad in ({'type':'object','additionalProperties':True}, {'$ref':'https://example.invalid/schema'},
                    {'type':'array','items':{'type':'number'}},{'type':'string','pattern':'.*'},{}):
            raw=copy.deepcopy(fixture.CONFIG);raw['tools']['identify']['input']=bad
            with self.assertRaises(DriverDefinitionError):compiled(raw)

    def test_custom_objects_cycles_and_independent_node_text_budgets(self):
        class Text(str):pass
        cycle=[];cycle.append(cycle)
        values=[Text('x'),cycle,float('nan'),float('inf'),2**60,{'x':[0]*65537},[[0]*65536]*5,'a'*(16*1024*1024+1)]
        for value in values:
            with self.subTest(kind=type(value).__name__),self.assertRaises(DriverDefinitionError):plain(value)

    def test_all_selected_tools_need_primary_commands_and_protective_is_readonly_observation(self):
        commands=copy.deepcopy(fixture.Driver.commands);commands.pop(fixture.CAPS['get_waveform'])
        with self.assertRaises(DriverDefinitionError):compile_mcp_client(fixture.CONFIG,commands)
        for member,value in [('observe','get_waveform'),('path','_hidden'),('arguments',{'action':'arbitrary'})]:
            raw=copy.deepcopy(fixture.CONFIG);raw['safety'][member]=value
            with self.assertRaises(DriverDefinitionError):compiled(raw)

    def test_numeric_limits_schema_contract_and_methods_cannot_be_erased(self):
        for name in ('call','read','driver_model','_driver_model','_fill_model','make_bridge','close'):
            bad=type('Bad',(fixture.Driver,),{name:lambda *args:None})
            with self.subTest(name=name),self.assertRaises(DriverDefinitionError):bad()
        class Bad(fixture.Driver):pass
        Bad.actions=copy.deepcopy(fixture.Driver.actions)
        Bad.actions[fixture.CAPS['configure_channel']].input['scale'].limits=()
        with self.assertRaises(DriverDefinitionError):Bad()
        class Changed(fixture.Driver):pass
        Changed.mcp_config=copy.deepcopy(fixture.CONFIG)
        Changed.mcp_config['tools']['identify']['input']['properties']['url']={'type':'string','maxLength':100}
        Changed.mcp_config['tools']['identify']['defaults']={'url':'local'}
        with self.assertRaises(DriverDefinitionError):Changed()

    def test_runtime_hardware_projection_preserves_declared_risk_and_limits(self):
        from mhs.driver.check import _hardware_view_subject
        driver=fixture.Driver(backend='fake',base_dir=FIXTURE);self.addCleanup(driver.close)
        shell=_hardware_view_subject(SimpleNamespace(cls=type(driver),instance=driver))
        self.assertEqual(shell._model.risk,'R0');self.assertFalse(driver._native_ready)
        binding=next(b for b in shell._model.bindings if b.capability_id==fixture.CAPS['configure_channel'])
        self.assertEqual(binding.limits['scale'],'operator_required')
        driver._mcp_config['tools']['get_waveform']['effectful']=False
        with self.assertRaises(DriverDefinitionError):driver.call(fixture.CAPS['identify'],{})

    def test_exact_source_proves_thirteen_and_rejects_changed_pin_reference_and_defaults(self):
        self.assertEqual(len(prove_tools(Tree(),compiled())),13)
        with self.assertRaises(ValueError):prove_tools(Tree(Tree().text+'\n'),compiled())
        tree=Tree();tree.commit='0'*40
        with self.assertRaises(ValueError):prove_tools(tree,compiled())
        for patch_ in ({'source_ref':fixture.SOURCE+':158'},{'defaults':{'channel':2,'mode':'screen','max_points':1000,'include_data':True}}):
            config=compiled();config['tools']['get_waveform'].update(patch_)
            with self.assertRaises(ValueError):prove_tools(Tree(),config)

    def test_wire_proof_refuses_raw_scpi_and_arbitrary_protective_effects(self):
        msg={'jsonrpc':'2.0','id':'a'*32,'method':'tools/call','params':{'name':'run_control','arguments':{'action':'stop'}}}
        self.assertEqual(prove_wire(compiled(),msg,20,'protective'),'run_control')
        for mutate in (lambda m:m['params'].update(name='scpi_command'),lambda m:m['params']['arguments'].update(action='run'),
                       lambda m:m.update(method='resources/read'),lambda m:m.update(id=True)):
            bad=copy.deepcopy(msg);mutate(bad)
            with self.assertRaises((ValueError,DriverDefinitionError)):prove_wire(compiled(),bad,20,'protective')

    def test_native_refuses_before_import_spawn_connect_and_unsigned_loader_still_enforces(self):
        from mhs.adapter import load_driver,LoadError
        native=importlib.import_module('.native',fixture.__package__)
        before={name for name in sys.modules if name.split('.')[0] in {'mcp','rigol_dho_mcp','socket'}}
        with patch('importlib.import_module',side_effect=AssertionError('upstream import forbidden')):
            with self.assertRaisesRegex(RuntimeError,'native admission blocked'):fixture.Driver(backend='hardware')
            with self.assertRaisesRegex(RuntimeError,'native admission blocked'):native.connect()
        self.assertEqual(before,{name for name in sys.modules if name.split('.')[0] in {'mcp','rigol_dho_mcp','socket'}})
        with tempfile.TemporaryDirectory() as state,patch.object(native,'connect',side_effect=AssertionError('native sentinel')) as factory:
            # R0 does not require the R2/R3 review signature. The finite native
            # implementation still refuses its own unresolved transport first.
            with self.assertRaisesRegex(RuntimeError,'native admission blocked'):
                load_driver(FIXTURE,backend='hardware',allow_hardware=True,state_dir=state)
            factory.assert_not_called()
        with tempfile.TemporaryDirectory() as temp:
            package=Path(temp)/'higher_risk';shutil.copytree(FIXTURE,package)
            path=package/'driver.py';source=path.read_text();needle="mode,risk='hardware','R0'"
            self.assertEqual(source.count(needle),1);path.write_text(source.replace(needle,"mode,risk='hardware','R2'"))
            with self.assertRaises(LoadError) as caught:
                load_driver(package,backend='hardware',allow_hardware=True,state_dir=Path(temp)/'state')
            self.assertEqual(caught.exception.reason,'review_required')

    def test_stock_gate_detects_computed_checker_compiler_and_regex_mutations(self):
        from tests.driver.test_qcodes_integrity import QcodesGateIntegrityTests
        runner=QcodesGateIntegrityTests()
        for module,statement in [('mcp_client_check','module.prove_tools = lambda *args: []'),
                ('mcp_client_config','module.compile_mcp_client = lambda *args: {}'),
                ('mcp_client_config',"module._PATH = __import__('re').compile('.*')"),
                ('mcp_client_driver','module._numeric_limits = lambda *args: None')]:
            source='from importlib import import_module\nmodule=import_module(".".join(["mhs","driver",'+repr(module)+']))\n'+statement+'\n'
            got=runner.stock(source)
            self.assertEqual(got['gate']['status'],'fail',got)
            self.assertTrue(any(f['code']=='G3.GATE_TAMPERED' for f in got['gate']['findings']),got)
        self.assertEqual(runner.stock('')['gate']['status'],'pass')


if __name__=='__main__':unittest.main()
