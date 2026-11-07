"""Trusted safe-state action routing through the stock server and retained bridge."""
from __future__ import annotations
import copy
import threading
import unittest

from mhs.bridge.base import BridgeContext
from mhs.bridge.python import PythonObjectBridge
from mhs.driver import Action, DriverDefinitionError, Field, PythonObjectDriver, close_server
from tests.bridges.test_python_retention import FIDELITY, Native
from tests.driver.support import serve

OFF='x-cap.retained.off.v1'
RESUME='x-cap.retained.resume.v1'

class Raw(Native):
    def off(self):
        super().off()
        return self.parameter.value
    def resume(self):
        self.events.append('resume')
        self.parameter.value=1.
        return 1.

class Fixture(PythonObjectDriver):
    device_id,device_kind,mode,risk='safe-action','world.sim','simulated','R0'
    fidelity=FIDELITY
    parameters={'value':Field('number',unit='1',writable=True)}
    reads={'value':'parameter.get'}
    writes={'value':{'native':'parameter.set','invoke':'call','timeout_ms':35}}
    commands={OFF:{'native':'off','timeout_ms':40,'concurrency':'exclusive',
                   'result':{'map':{'value':'output.$'}}},
              RESUME:{'native':'resume','timeout_ms':40,'concurrency':'exclusive',
                      'result':{'map':{'value':'output.$'}}}}
    actions={OFF:Action(name='off',safe_state=True,output={'value':Field('number',unit='1')}),
             RESUME:Action(name='resume',output={'value':Field('number',unit='1')})}
    safety_bindings={'estop':{'native':'off','timeout_ms':40},'reset':{'native':'reset_fault','timeout_ms':40}}
    safe_state='Output off after all earlier native work settles'

class SafeActionTests(unittest.TestCase):
    def attach(self, cls=Fixture):
        raw=Raw();raw.parameter.release.set()
        driver=cls(native=raw);server,client=serve(driver)
        self.addCleanup(close_server,server)
        self.addCleanup(raw.parameter.release.set)
        self.addCleanup(raw.off_release.set)
        return raw,driver,client

    def settle(self, driver):
        with driver.inner._activity:
            self.assertTrue(driver.inner._activity.wait_for(lambda:not driver.inner._executions,2))

    def test_stock_estop_dispatches_achieved_by_and_preserves_ack(self):
        raw,driver,client=self.attach()
        receipt=client.estop()
        self.assertTrue(receipt['output']['safe_state_achieved'],receipt)
        self.assertGreaterEqual(raw.events.count('off'),2) # native stop + declared achieved_by
        self.assertTrue(driver.inner.safety_status()['safe_state']['achieved'])
        self.assertEqual(client.command(OFF)['status'],'completed')
        self.assertTrue(driver.inner.safety_status()['safe_state']['achieved'])
        self.assertEqual(client.reset()['result']['status'],'completed')

    def test_unrelated_action_refused_while_latched_even_with_forged_input(self):
        raw,driver,client=self.attach();client.estop()
        for args in ({},{'safe_state':True},{'extra':{'safe_state':True}}):
            self.assertNotEqual(client.command(RESUME,args)['status'],'completed')
        self.assertNotIn('resume',raw.events)

    def test_pending_setter_does_not_block_native_stop_but_prevents_ack(self):
        raw,driver,client=self.attach();raw.parameter.release.clear()
        self.assertEqual(client.write({'value':8.})['status'],'unknown')
        before=raw.events.count('off')
        receipt=client.command(OFF)
        self.assertEqual(raw.events.count('off'),before+1)
        self.assertEqual(receipt['status'],'failed',receipt)
        self.assertFalse(driver.inner.safety_status()['safe_state']['achieved'])
        # Forged context cannot grant the unrelated action reserved safety capacity.
        with self.assertRaises(Exception):
            driver.inner.call(RESUME,{},BridgeContext(extra={'safe_state':True}))
        self.assertNotIn('resume',raw.events)
        self.assertFalse(client.estop()['output']['safe_state_achieved'])
        self.assertNotEqual(client.reset().get('result',{}).get('status'),'completed')
        raw.parameter.release.set();self.settle(driver)
        self.assertEqual(raw.parameter.value,8.)
        self.assertFalse(driver.inner.safety_status()['safe_state']['achieved'])
        self.assertEqual(client.command(OFF)['status'],'completed')
        self.assertEqual(raw.parameter.value,0.)
        self.assertEqual(client.reset()['result']['status'],'completed')

    def test_safe_action_runs_while_ordinary_transaction_lock_is_held(self):
        raw,driver,client=self.attach()
        entered,release=threading.Event(),threading.Event()
        def lock():
            with driver.inner._lock:
                entered.set();release.wait(2)
        thread=threading.Thread(target=lock);thread.start();self.assertTrue(entered.wait(1))
        try:
            # Read receipt snapshots can wait on the ordinary lock; directly
            # exercise the bridge while the stock session remains attached.
            self.assertEqual(driver.inner.call(OFF,{}),{'value':0.})
            self.assertIn('off',raw.events)
        finally:release.set();thread.join(2)

    def test_safe_action_timeout_is_retained_and_late_completion_needs_confirmation(self):
        raw,driver,client=self.attach();raw.off_release.clear()
        result=client.command(OFF)
        self.assertEqual(result['status'],'unknown',result)
        self.assertFalse(driver.inner.safety_status()['safe_state']['achieved'])
        self.assertNotEqual(client.reset().get('result',{}).get('status'),'completed')
        self.assertNotEqual(client.write({'value':9.})['status'],'completed')
        raw.off_release.set();self.settle(driver)
        self.assertFalse(driver.inner.safety_status()['safe_state']['achieved'])
        self.assertEqual(client.command(OFF)['status'],'completed')
        self.assertTrue(driver.inner.safety_status()['safe_state']['achieved'])

    def test_failed_output_mapping_cannot_commit_safe_stamp(self):
        class Bad(Fixture):
            commands=copy.deepcopy(Fixture.commands)
            commands[OFF]['result']={'map':{'value':'output.missing'}}
        raw,driver,client=self.attach(Bad)
        self.assertEqual(client.command(OFF)['status'],'failed')
        self.assertFalse(driver.inner.safety_status()['safe_state']['achieved'])

    def test_safe_action_configuration_requires_no_native_input(self):
        class Bad(Fixture):
            commands=copy.deepcopy(Fixture.commands)
            commands[OFF]['args']={'enabled':{'from':'input.enabled'}}
        with self.assertRaises(DriverDefinitionError):Bad.driver_model()

    def test_request_metadata_cannot_declare_a_safe_role(self):
        config=Fixture.bridge_config('main')
        config['capabilities'][RESUME]['safe_state']=True
        with self.assertRaises(Exception):PythonObjectBridge(config,load=False,strict=True)
        with self.assertRaises(Exception):PythonObjectBridge(Fixture.bridge_config('main'),load=False,
                                                             safe_state_capabilities=['not-bound'])

    def test_direct_declared_action_rejects_caller_arguments(self):
        raw,driver,client=self.attach()
        with self.assertRaises(Exception):driver.inner.call(OFF,{'enabled':True})
        self.assertNotIn('off',raw.events)

class SafeActionOutputTests(unittest.TestCase):
    attach = SafeActionTests.attach
    settle = SafeActionTests.settle
    def test_wrong_type_does_not_confirm_command_or_achieved_by(self):
        raw,driver,client=self.attach()
        raw.off=lambda: "not-a-number"
        result=client.command(OFF)
        self.assertEqual(result['status'],'failed',result)
        self.assertEqual(result['error']['mhs_code'],'MHS.CAPABILITY.OUTPUT_INVALID')
        self.assertFalse(driver.inner.safety_status()['safe_state']['achieved'])
        result=client.estop()
        self.assertFalse(result['output']['safe_state_achieved'],result)
        self.assertFalse(driver.inner.safety_status()['safe_state']['achieved'])

    def test_nested_required_field_must_exist_before_safety_commit(self):
        class Nested(Fixture):
            actions=copy.deepcopy(Fixture.actions)
            actions[OFF]=Action(name='off',safe_state=True,output={'value':Field('object',properties={
                'confirmed':Field('boolean',required=True)})})
        raw,driver,client=self.attach(Nested)
        raw.off=lambda: {}
        self.assertEqual(client.command(OFF)['status'],'failed')
        self.assertFalse(driver.inner.safety_status()['safe_state']['achieved'])
        self.assertFalse(client.estop()['output']['safe_state_achieved'])

    def test_missing_output_contract_cannot_confirm_safe_action(self):
        config=Fixture.bridge_config('main')
        bridge=PythonObjectBridge(config,load=False,safe_state_capabilities=[OFF])
        bridge._target=Raw();bridge._loaded=True
        self.addCleanup(bridge.close)
        with self.assertRaises(Exception):bridge.call(OFF,{})
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])

    def test_output_contract_is_copied(self):
        schemas={OFF:{'output_schema':{'type':'object','properties':{'value':{'type':'number'}},
                                     'required':['value'],'additionalProperties':False}}}
        bridge=PythonObjectBridge(Fixture.bridge_config('main'),load=False,safe_state_capabilities=[OFF],
                                  capability_schemas=schemas)
        bridge._target=Raw();bridge._target.off=lambda: 'not-a-number';bridge._loaded=True
        self.addCleanup(bridge.close)
        schemas[OFF]['output_schema']['properties']['value']['type']='string'
        with self.assertRaises(Exception):bridge.call(OFF,{})
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])

if __name__=='__main__':unittest.main()
