"""Correlated action terminals must precede the safety acknowledgement they justify."""
import copy
import threading
import unittest
from mhs import signals
from mhs.bridge.base import BridgeContext
from tests.bridges import test_ros_actions as action_cases
from tests.bridges.test_ros_actions import (config, CAP, RESUME, PROFILES,
                                          is_goal, is_cancel, ident, result, service_response)

SAFE='x-cap.test.safe.v1'

class SafetyFreshnessTests(unittest.TestCase):
    bridge=action_cases.RosActionTests.bridge
    server=action_cases.RosActionTests.server
    worker=action_cases.RosActionTests.worker

    def test_stock_estop_never_acknowledges_before_cancellation_rearm_terminal(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                started,cancelled,rearmed,release,terminal= [threading.Event() for _ in range(5)]
                state={'value':'On'};trace=[];goals=[];threads=[]
                def handler(message):
                    if is_goal(message):goals.append(ident(message));trace.append('goal');started.set()
                    elif message['op']=='call_service':
                        state['value']='Off';trace.append('stop');return service_response(message)
                    elif is_cancel(message):
                        self.assertEqual(message['id'],goals[0]);cancelled.set();trace.append('cancel')
                        def finish():
                            if not release.wait(2):return
                            state['value']='On';trace.append('rearm');rearmed.set()
                            if not terminal.wait(2):return
                            transport.feed(result(profile,goals[0],2 if profile=='ros1-actionlib' else 5))
                            trace.append('terminal')
                        thread=threading.Thread(target=finish);threads.append(thread);thread.start()
                driver,client,transport=self.server(profile,handler)
                self.addCleanup(terminal.set);self.addCleanup(release.set)
                running=client.command(CAP,{'target':'home'},deadline_ms=10)
                # A running receipt does not prove that its worker has sent the goal.
                self.assertTrue(started.wait(1))
                stop=client.estop()
                self.assertTrue(cancelled.wait(1))
                self.assertFalse(stop['output']['safe_state_achieved'],stop)
                self.assertFalse(driver.inner.safety_status()['safe_state']['achieved'])
                self.assertNotEqual(client.reset().get('result',{}).get('status'),'completed')
                release.set();self.assertTrue(rearmed.wait(1))
                self.assertEqual(state['value'],'On')
                self.assertFalse(driver.inner.safety_status()['safe_state']['achieved'])
                self.assertFalse(client.server._operations[running['operation_id']].done.is_set())
                terminal.set()
                for thread in threads:thread.join(1)
                operation=client.server._operations[running['operation_id']]
                operation.thread.join(2)
                self.assertFalse(operation.thread.is_alive())
                self.assertEqual(state['value'],'Off')
                self.assertTrue(driver.inner.safety_status()['safe_state']['achieved'])
                self.assertIn('stop',trace[trace.index('terminal')+1:])
                self.assertEqual(client.operation(running['operation_id'])['status'],'cancelled')

    def test_safe_state_action_dispatches_but_cannot_confirm_an_active_goal(self):
        cfg=config();cfg['commands'][SAFE]={'service':'/stop','type':'std_srvs/srv/Trigger',
            'safe_state':True,'success':{'path':'success','equals':True}}
        goal=[];started=threading.Event()
        def handler(message):
            if is_goal(message):goal.append(ident(message));started.set()
            elif message['op']=='call_service':return service_response(message)
        bridge,transport=self.bridge(cfg=cfg,handler=handler,
            capability_schemas={SAFE:{"output_schema":{"type":"object","additionalProperties":False}}})
        thread,outcome=self.worker(lambda:bridge.call(CAP,{'target':'home'}))
        self.assertTrue(started.wait(1))
        with self.assertRaises(signals.DriverFailed):bridge.call(SAFE,{})
        self.assertTrue(any(m.get('service')=='/stop' for m in transport.sent))
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        transport.feed(result('ros2-native',goal[0]));thread.join(1)
        self.assertEqual(bridge.call(SAFE,{}),{})
        self.assertTrue(bridge.safety_status()['safe_state']['achieved'])

    def test_post_terminal_stop_failure_retains_goal_and_requires_explicit_reset(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                cancelled=threading.Event();goals=[];state={'rearmed':False,'allow':False}
                def handler(message):
                    if is_goal(message):goals.append(ident(message));cancelled.set()
                    elif is_cancel(message):
                        state['rearmed']=True
                        return result(profile,goals[0],2 if profile=='ros1-actionlib' else 5)
                    elif message['op']=='call_service':
                        return service_response(message,not state['rearmed'] or state['allow'])
                bridge,transport=self.bridge(profile,handler)
                with self.assertRaises(signals.OutcomeUnknown):
                    bridge.call(CAP,{'target':'home'},BridgeContext(cancel_event=cancelled))
                self.assertTrue(next(iter(bridge._actions.values())).abandoned)
                self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
                with self.assertRaises(Exception):bridge.call(RESUME,{})
                with self.assertRaises(Exception):bridge.reset()
                state['allow']=True;bridge.reset()
                self.assertFalse(bridge._actions)
                self.assertEqual(len([m for m in transport.sent if is_goal(m)]),1)

    def test_terminal_during_stop_request_invalidates_that_acknowledgement(self):
        goals=[];started=threading.Event();race={'armed':True}
        def handler(message):
            if is_goal(message):goals.append(ident(message));started.set()
            elif message['op']=='call_service':
                if race['armed']:
                    race['armed']=False
                    # Native callback finishes/re-arms after the stop took effect,
                    # but before its acknowledgement is received.
                    return [result('ros2-native',goals[0]),service_response(message)]
                return service_response(message)
        bridge,transport=self.bridge(handler=handler)
        thread,outcome=self.worker(lambda:bridge.call(CAP,{'target':'home'}))
        self.assertTrue(started.wait(1))
        self.assertFalse(bridge.safe_state()['achieved'])
        thread.join(1)
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        self.assertTrue(bridge.safe_state()['achieved'])

    def test_ordinary_halt_like_service_invalidates_old_safe_state(self):
        state={'enabled':True}
        def handler(message):
            if message['op']=='call_service':
                if message['service']=='/stop':state['enabled']=False
                elif message['service']=='/resume':state['enabled']=True
                return service_response(message)
        bridge,transport=self.bridge(handler=handler)
        self.assertTrue(bridge.safe_state()['achieved'])
        self.assertFalse(state['enabled'])
        bridge.call(RESUME,{})
        self.assertTrue(state['enabled'])
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        self.assertTrue(bridge.safe_state()['achieved'])
        bridge.call(action_cases.READ,{})
        self.assertTrue(bridge.safety_status()['safe_state']['achieved'])

    def test_stock_timed_out_service_late_reply_requires_fresh_stop_and_reset(self):
        from mhs.driver import Action, RosDriver, close_server
        from tests.driver.support import serve
        from mhs.bridge.ros_transport import RecordingRosTransport
        cfg=config();cfg['commands'][RESUME]['timeout_ms']=20
        state={'value':'On'};pending=[]
        def handler(message):
            if message['op']!='call_service':return None
            if message['service']=='/resume':pending.append(copy.deepcopy(message));return None
            if message['service']=='/stop':state['value']='Off'
            return service_response(message)
        transport=RecordingRosTransport(handler)
        cls=type('LateService',(RosDriver,),{
            'device_id':'late-service','device_kind':'instrument','risk':'R0','ros_version':2,
            'commands':{RESUME:cfg['commands'][RESUME]},'safety_bindings':cfg['safety_bindings'],
            'backends':{'fake':lambda:transport},'actions':{RESUME:Action(name='resume')},
        })
        driver=cls(backend='fake');server,client=serve(driver);self.addCleanup(close_server,server)
        receipt=client.command(RESUME,{})
        self.assertEqual(receipt['status'],'unknown',receipt)
        self.assertEqual(len(pending),1)
        stop=client.estop()
        self.assertEqual(state['value'],'Off')
        self.assertFalse(stop['output']['safe_state_achieved'])
        self.assertNotEqual(client.reset().get('result',{}).get('status'),'completed')
        self.assertNotEqual(client.command(RESUME,{})['status'],'completed')
        request=pending[0]
        # Correlated service completion is emitted only after this source-shaped
        # callback's late re-arm. A timeout does not imply its work stopped.
        state['value']='On'
        transport.feed(service_response(request))
        with driver.inner._condition:
            self.assertTrue(driver.inner._condition.wait_for(
                lambda:driver.inner._pending[request['id']].event.is_set(),1))
        self.assertFalse(driver.inner.safety_status()['safe_state']['achieved'])
        self.assertTrue(client.estop()['output']['safe_state_achieved'])
        self.assertEqual(state['value'],'Off')
        self.assertEqual(client.reset()['result']['status'],'completed')
        self.assertNotIn(request['id'],driver.inner._pending)
        self.assertEqual(len(pending),1)

    def test_late_wrong_service_id_never_reconciles_effectful_callback(self):
        held=[]
        def handler(message):
            if message.get('service')=='/resume':held.append(copy.deepcopy(message));return None
            if message['op']=='call_service':return service_response(message)
        cfg=config();cfg['commands'][RESUME]['timeout_ms']=10
        bridge,transport=self.bridge(cfg=cfg,handler=handler)
        with self.assertRaises(signals.OutcomeUnknown):bridge.call(RESUME,{})
        transport.feed({**service_response(held[0]),'id':'another-request'})
        bridge.call(action_cases.READ,{})  # receiver drains prior wrong-id frame
        self.assertFalse(bridge._pending[held[0]['id']].event.is_set())
        self.assertFalse(bridge.safe_state()['achieved'])
        with self.assertRaises(Exception):bridge.reset()

    def test_native_reset_timeout_retains_callback_and_refuses_further_reset(self):
        held=[]
        def handler(message):
            if message.get('service')=='/reset':held.append(copy.deepcopy(message));return None
            if message['op']=='call_service':return service_response(message)
        cfg=config();cfg['safety_bindings']['reset']={
            'service':'/reset','timeout_ms':10,'success':{'path':'success','equals':True}}
        bridge,transport=self.bridge(cfg=cfg,handler=handler)
        with self.assertRaises(signals.OutcomeUnknown):bridge.reset()
        self.assertEqual(len(held),1)
        self.assertFalse(bridge.safe_state()['achieved'])
        with self.assertRaises(Exception):bridge.reset()
        self.assertEqual(len(held),1)
        transport.feed(service_response(held[0]))
        with bridge._condition:
            self.assertTrue(bridge._condition.wait_for(
                lambda:bridge._pending[held[0]['id']].event.is_set(),1))
        self.assertTrue(bridge.safe_state()['achieved'])
        # Reconciliation is explicit; a successfully confirmed second reset
        # may clear the retained first callback only after its terminal reply.
        transport.handler=lambda message: service_response(message) if message['op']=='call_service' else None
        self.assertEqual(bridge.reset(),{'reset':True})
        self.assertFalse(bridge._pending)

    def test_stock_safe_action_validates_complete_output_before_achieved(self):
        from mhs.driver import Action, Field, RosDriver, close_server
        from tests.driver.support import serve
        from mhs.bridge.ros_transport import RecordingRosTransport
        for value in ({'stopped':'wrong'},{}, {'stopped':True}):
            with self.subTest(value=value):
                def handler(message):
                    return {**service_response(message),'values':{'success':True,'status':value}}
                transport=RecordingRosTransport(handler)
                spec={'service':'/stop','success':{'path':'success','equals':True}}
                cls=type('SafeSchema',(RosDriver,),{
                    'device_id':'ros-safe-schema','device_kind':'instrument','risk':'R0',
                    'backends':{'fake':lambda:transport},
                    'commands':{SAFE:{**spec,'result':{'map':{'status':'output.status'}}}},
                    'actions':{SAFE:Action(name='stop',safe_state=True,output={
                        'status':Field('object',properties={'stopped':Field('boolean')})})},
                    'safety_bindings':{'estop':spec},
                })
                driver=cls(backend='fake');server,client=serve(driver);self.addCleanup(close_server,server)
                valid=value=={'stopped':True}
                receipt=client.command(SAFE,{})
                self.assertEqual(receipt['status'],'completed' if valid else 'failed',receipt)
                self.assertEqual(driver.inner.safety_status()['safe_state']['achieved'],valid)
                stop=client.estop()
                self.assertEqual(stop['output']['safe_state_achieved'],valid,stop)
                self.assertEqual(driver.inner.safety_status()['safe_state']['achieved'],valid)

    def test_safe_action_schema_is_copied_and_context_cannot_supply_missing_contract(self):
        from mhs.bridge.ros import RosBridge
        from mhs.bridge.ros_transport import RecordingRosTransport
        cfg=config();cfg['commands'][SAFE]={**cfg['safety_bindings']['estop'],
            'safe_state':True,'result':{'map':{'stopped':'output.stopped'}}}
        schema={'type':'object','required':['stopped'],'properties':{'stopped':{'type':'boolean'}}}
        contracts={SAFE:{'output_schema':schema}}
        def handler(message):return {**service_response(message),'values':{'success':True,'stopped':'wrong'}}
        bridge=RosBridge(cfg,transport=RecordingRosTransport(handler),capability_schemas=contracts)
        self.addCleanup(bridge.close)
        schema['properties']['stopped']['type']='string'
        with self.assertRaises(signals.DriverFailed):bridge.call(SAFE,{})
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        absent=RosBridge(cfg,transport=RecordingRosTransport(handler));self.addCleanup(absent.close)
        with self.assertRaises(signals.DriverFailed):
            absent.call(SAFE,{},BridgeContext(extra={'capability_schemas':contracts,'output_schema':schema}))
        self.assertFalse(absent.safety_status()['safe_state']['achieved'])

    def test_malformed_nested_output_contract_cannot_commit_safe_stamp(self):
        from mhs.bridge.ros import RosBridge
        from mhs.bridge.ros_transport import RecordingRosTransport
        cfg=config();cfg['commands'][SAFE]={**cfg['safety_bindings']['estop'],
            'safe_state':True,'result':{'map':{'stopped':'output.stopped'}}}
        def handler(message):return {**service_response(message),'values':{'success':True,'stopped':True}}
        for schema in (None,{}, {'type':'object','properties':{'stopped':{'type':17}}}):
            bridge=RosBridge(cfg,transport=RecordingRosTransport(handler),
                             capability_schemas={SAFE:{'output_schema':schema}})
            self.addCleanup(bridge.close)
            with self.assertRaises(signals.DriverFailed):bridge.call(SAFE,{})
            self.assertFalse(bridge.safety_status()['safe_state']['achieved'])

if __name__=='__main__':unittest.main()
