"""Source-domain, paired validity and observed JSON wire regressions."""
import copy,json,math,unittest
from pathlib import Path
from mhs.adapter import load_driver
from mhs.driver import build_server,close_server,DriverFailed
from mhs.client import MHSClient,InProcessTransport
from mhs.bridge.ros_transport import _json_copy
HERE=Path(__file__).resolve().parent
MOVE='x-cap.frankarobotics.spine_move.v1';BATTERY='x-cap.frankarobotics.battery_state.v1'
INPUT={'position':0.2,'velocity':0.1,'acceleration':0.2,'deceleration':0.2}

class SourceContractCases(unittest.TestCase):
    def driver(self):
        driver=load_driver(HERE,'fake');self.addCleanup(driver.close);return driver

    def endpoint(self):
        driver=self.driver()
        overlay=json.loads((HERE/'site-limits.example.json').read_text())
        for field in ('velocity','acceleration','deceleration'):
            overlay['devices']['mhs://localhost/franka_tmr'][MOVE][field]['min']=-1
        server=build_server(driver,site_limits=overlay);self.addCleanup(close_server,server)
        client=MHSClient(InProcessTransport(server));client.hello()
        device=next(iter(server.devices));client.open_session([device],mode='simulated')
        return driver,client,device

    def test_source_positive_domain_rejects_zero_and_negative_before_goal_send(self):
        driver,client,device=self.endpoint()
        schema=next(b for b in driver._model.bindings if b.capability_id==MOVE).input_schema
        for field in ('velocity','acceleration','deceleration'):
            self.assertEqual(schema['properties'][field]['exclusiveMinimum'],0)
            for bad in (0,-0.1):
                with self.subTest(field=field,value=bad):
                    before=list(driver.native.sent)
                    receipt=client.invoke(MOVE,{**INPUT,field:bad},device_id=device)
                    self.assertEqual(receipt['status'],'rejected',receipt)
                    self.assertTrue(all(message['op'] in ('subscribe','unsubscribe')
                                        for message in driver.native.sent[len(before):]))
        self.assertEqual(client.invoke(MOVE,INPUT,device_id=device)['status'],'completed')

    def test_direct_family_call_enforces_same_positive_domain(self):
        driver=self.driver()
        for field in ('velocity','acceleration','deceleration'):
            for value in (0,-0.1,True,float('inf'),float('nan')):
                with self.subTest(field=field,value=value):
                    before=list(driver.native.sent)
                    with self.assertRaises(DriverFailed):driver.call(MOVE,{**INPUT,field:value})
                    self.assertEqual(driver.native.sent,before)

    def test_stock_read_pairs_conflicting_successive_samples_and_invalid_is_null(self):
        driver,client,device=self.endpoint();peer=driver.native;original=peer.handler
        counts={'position':0,'state':0}
        def handler(message):
            topic=message.get('topic','')
            if message.get('op')=='subscribe' and topic in ('/franka_spine_node/position','/franka_spine_node/state'):
                base=topic.rsplit('/',1)[1];counts[base]+=1
                valid=counts[base]%2==1
                payload={'valid':valid,'position':0.1 if valid else 999,
                         'state':'SwitchedOn' if valid else 'INVALID-CACHED',
                         'error_code':'' if valid else 'E42',
                         'error_description':'' if valid else 'read failed'}
                return peer._topic(message,payload)
            return original(message)
        peer.handler=handler
        first=client.read('main',device_id=device)['state']
        self.assertEqual(counts,{'position':1,'state':1})
        self.assertEqual(first['position'],0.1);self.assertTrue(first['position_valid'])
        self.assertEqual(first['state'],'SwitchedOn');self.assertTrue(first['state_valid'])
        second=client.read('main',device_id=device)['state']
        self.assertEqual(counts,{'position':2,'state':2})
        self.assertIsNone(second['position']);self.assertFalse(second['position_valid'])
        self.assertIsNone(second['state']);self.assertFalse(second['state_valid'])
        self.assertEqual(second['state_error_code'],'E42')
        self.assertEqual(second['state_error_description'],'read failed')

    def test_missing_validity_is_not_invented(self):
        driver=self.driver();peer=driver.native
        peer.handler=lambda message: peer._topic(message,{'position':0.2}) if message['op']=='subscribe' else None
        with self.assertRaises(DriverFailed):driver.read('main',['position','position_valid'])

    def test_full_battery_json_null_wire_and_source_nan_are_distinct(self):
        driver,client,device=self.endpoint();peer=driver.native
        fixture=json.loads((HERE/'fixtures/battery-wire.json').read_text())
        frame=json.loads(fixture['raw_frame']);message=frame['msg']
        names=('voltage','current','charge','capacity','design_capacity')
        for name in names:self.assertIsNone(message[name])
        source=peer.source_battery_message()
        for name in names:self.assertTrue(math.isnan(source[name]))
        with self.assertRaises(ValueError):_json_copy({'op':'publish','msg':source},max_bytes=10000)
        ordinary=peer.handler
        def handler(request):
            if request.get('op')=='subscribe' and request.get('topic')=='/franka_battery_node/battery_state':
                return peer._topic(request,copy.deepcopy(message))
            return ordinary(request)
        peer.handler=handler
        receipt=client.invoke(BATTERY,{},device_id=device)
        self.assertEqual(receipt['status'],'completed',receipt)
        self.assertEqual(receipt['output'],{'percentage':message['percentage'],'temperature':30.0,
                                          'power_supply_status':1,'location':'wireless'})
        self.assertIsNone(driver.inner._fatal)

if __name__=='__main__':unittest.main()
