"""Complete controlled Rigol workflow over owned pipes and stock public paths."""
import base64
import copy
import hashlib
import io
import json
import math
import threading
import time
from unittest.mock import patch

from mhs import canonical
from mhs.adapter import load_driver
from mhs.artifacts import ArtifactPublisher, LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import build_server, close_server
from mhs.errors import MHSError
from mhs.mcp import serve_stdio, projection_tool_name
from tests.bridges.test_mcp_stdio import OwnedPeerCase, wait_for
from tests.driver.test_mcp_client import FIXTURE, fixture
from tests import test_mcp_client_artifacts as prior


class StdioStockContractTests(OwnedPeerCase):
    invoke=prior.McpStockTests.invoke
    result=prior.McpStockTests.result
    request=prior.McpStockTests.request
    projection=prior.McpStockTests.projection

    def assert_no_effects(self,directory):
        self.assertFalse(any(e.get('tool') and fixture.CONFIG['tools'][e['tool']]['effectful'] for e in self.events(directory)))

    def make(self,plan=None,*,limits=True,store_options=None,tokens=None,permit=False):
        peer,directory=self.peer(plan)
        if permit:
            class Variant(fixture.Driver):pass
            Variant.actions=copy.deepcopy(fixture.Driver.actions)
            Variant.actions[fixture.CAPS['run_control']].requires_permit=True
            driver=Variant(backend='fake',base_dir=FIXTURE,native=peer)
        else:
            driver=load_driver(FIXTURE,backend='fake',native=peer)
        self.assertIsNone(peer.status()['pid'])
        store=LocalArtifactStore(**(store_options or {}))
        server=build_server(driver,site_limits=fixture.overlay() if limits else None,artifact_store=store,auth_tokens=tokens)
        self.addCleanup(close_server,server)
        client=MHSClient(InProcessTransport(server,auth_token='a' if tokens else None));client.hello()
        device=next(iter(server.devices));client.open_session([device],mode=server.devices[device].mode)
        return peer,directory,driver,store,server,client,device

    def test_all_thirteen_tools_sixteen_bindings_and_complete_optional_flow(self):
        peer,directory,driver,store,server,client,device=self.make({'channel_count':2})
        self.assertEqual(len(fixture.Driver.driver_model().bindings),16)
        self.assertEqual(self.result(client,self.invoke(client,device,'identify'))['text'],'RIGOL TECHNOLOGIES,CONTROLLED-DHO,SDK-FAKE,0')
        value=self.result(client,self.invoke(client,device,'get_status'))
        self.assertEqual(set(value['channels']),{'CH1','CH2'});self.assertEqual(value['channels']['CH2'],{'enabled':False})
        channel={'channel':2,'enabled':True,'scale':.2,'offset':-.1,'coupling':'AC','probe_ratio':10,'bandwidth_limit':'20M','invert':True}
        result=self.result(client,self.invoke(client,device,'configure_channel',channel))
        expected={'channel':2,'enabled':True,'scale_V_per_div':'0.2','offset_V':'-0.1','coupling':'AC','probe_ratio':'10','bandwidth_limit':'20M'}
        self.assertEqual(result,expected);self.assertNotIn('invert',result)
        state=json.loads((directory/'state.json').read_text());self.assertIs(state['invert']['2'],True)
        self.assertEqual(self.result(client,self.invoke(client,device,'configure_channel',{'channel':2,'enabled':None,'scale':None,'offset':None,'coupling':None,'probe_ratio':None,'bandwidth_limit':None,'invert':None})),expected)
        self.assertEqual(self.result(client,self.invoke(client,device,'configure_timebase',{'scale':.002,'offset':-.01})),{'scale_s_per_div':'0.002','offset_s':'-0.01'})
        self.assertEqual(self.result(client,self.invoke(client,device,'configure_timebase',{'scale':None,'offset':None})),{'scale_s_per_div':'0.002','offset_s':'-0.01'})
        trigger={'source':'D15','slope':'RFALl','level':.25,'sweep':'SINGle'}
        expected={'mode':'EDGE','source':'D15','slope':'RFALl','level_V':'0.25','sweep':'SINGle','status':'STOP'}
        self.assertEqual(self.result(client,self.invoke(client,device,'configure_trigger_edge',trigger)),expected)
        self.assertEqual(self.result(client,self.invoke(client,device,'configure_trigger_edge',dict.fromkeys(trigger))),expected)
        acq={'memory_depth':'50M','acq_type':'AVERages','averages':8}
        expected={'memory_depth':'50M','type':'AVERages','averages':'8','sample_rate_Sa_per_s':'1000000'}
        self.assertEqual(self.result(client,self.invoke(client,device,'configure_acquisition',acq)),expected)
        self.assertEqual(self.result(client,self.invoke(client,device,'configure_acquisition',dict.fromkeys(acq))),expected)
        for action,command,status in [('run',':RUN','RUN'),('single',':SINGle','WAIT'),('autoset',':AUToset','RUN'),('clear',':CLEar','RUN'),('force_trigger',':TFORce','RUN'),('stop',':STOP','STOP')]:
            self.assertEqual(self.result(client,self.invoke(client,device,'run_control',{'action':action})),{'text':'Sent '+command+'. Trigger status: '+status})
        for name,args in [('configure_cursors',{'mode':'TRACk','track_source_a':'CHAN2','track_source_b':'MATH3'}),('get_cursor_values',{}),('configure_cursors',{'mode':'OFF'}),('get_cursor_values',{}),('get_measurement',{'item':'VPP'}),('measure_between',{'item':'RRDelay'}),('get_waveform',{}),('get_screenshot',{})]:
            self.assertEqual(self.invoke(client,device,name,args)['status'],'completed',name)
        called={e['tool'] for e in self.events(directory) if e['method']=='tools/call'}
        self.assertEqual(called,set(fixture.CAPS))
        self.assertFalse(peer.status()['fenced'])

    def test_explicit_and_omitted_cursor_branches_keep_seconds_and_volts(self):
        for axis,cap,field,number in [('TIME',fixture.CURSOR_TIME,'ax',.000002),('AMPLitude',fixture.CURSOR_AMPLITUDE,'ay',.75)]:
            peer,directory,driver,store,server,client,device=self.make()
            self.assertEqual(self.result(client,self.invoke(client,device,cap,{'source':'MATH4','position_a':0.,'position_b':number*2})),{'mode':'MANual'})
            self.assertEqual(self.result(client,self.invoke(client,device,'get_cursor_values'))['type'],axis)
            self.assertEqual(self.result(client,self.invoke(client,device,'configure_cursors',{'mode':'OFF'})),{'mode':'OFF'})
            self.assertEqual(set(self.result(client,self.invoke(client,device,'get_cursor_values'))),{'mode','note'})
            before=len(self.events(directory))
            self.assertEqual(self.result(client,self.invoke(client,device,fixture.CURSOR_CURRENT,{'time_position_a':.000002,'voltage_position_a':.75})),{'mode':'MANual'})
            calls=[e for e in self.events(directory)[before:] if e.get('tool')=='configure_cursors']
            self.assertEqual(len(calls),2);self.assertNotIn('cursor_type',calls[-1]['arguments'])
            self.assertEqual(calls[-1]['arguments']['position_a'],number)
            self.assertEqual(json.loads((directory/'state.json').read_text())['cursor'][field],str(number))
            for name in ('time_position_a','time_position_b','voltage_position_a','voltage_position_b'):
                binding=next(b for b in driver._model.bindings if b.capability_id==fixture.CURSOR_CURRENT)
                self.assertEqual(binding.input_schema['properties'][name]['x-mhs-unit'],'s' if name.startswith('time') else 'V')
            self.result(client,self.invoke(client,device,'configure_cursors',{'mode':'TRACk','track_source_a':'CHAN2','track_source_b':'MATH3'}))
            values=self.result(client,self.invoke(client,device,'get_cursor_values'))
            self.assertEqual((values['source_a'],values['source_b']),('CHAN2','MATH3'))
            self.assertTrue({'ax','ay','bx','by','delta_x','delta_y','inverse_delta_x'}<=values.keys())

    def test_all_measurements_units_selector_effects_and_invalid_flag(self):
        peer,directory,driver,store,server,client,device=self.make()
        for name,items,arguments in [('get_measurement',fixture.MEASUREMENTS,{'channel':4}),('measure_between',fixture.BETWEEN,{'source_a':2,'source_b':3})]:
            for item in items:
                expected={'item':item,**arguments,'value':1.25,'invalid':False}
                self.assertEqual(self.result(client,self.invoke(client,device,name,{'item':item,**arguments})),expected)
                self.assertEqual(json.loads((directory/'state.json').read_text())['last_selector'],{'item':item,**arguments})
        peer,directory,driver,store,server,client,device=self.make({'measurement_value':1e38})
        result=self.result(client,self.invoke(client,device,'get_measurement',{'item':'VPP'}))
        self.assertEqual(result,{'channel':1,'item':'VPP','value':1e38,'invalid':True})
        peer,directory,driver,store,server,client,device=self.make({'measurement_value':'not numeric'})
        result=self.invoke(client,device,'get_measurement',{'item':'VPP'})
        self.assertNotEqual(result['status'],'completed');self.assertEqual(store._grants,{})
        self.assertTrue(driver.safety_status()['remote_uncertain']);self.assertTrue(peer.wait_retired(2))

    def test_real_pipe_mcp_all_full_waveforms_png_and_resource_stdio(self):
        peer,directory,driver,store,server,client,device=self.make()
        projection,tools=self.projection(client,device)
        for name in fixture.CAPS:
            called=self.request(projection,'tools/call',{'name':tools[name],'arguments':fixture.EXAMPLES[name]})
            self.assertEqual(called['result']['structuredContent']['receipt']['status'],'completed',called)
        for capability in (fixture.CURSOR_TIME,fixture.CURSOR_AMPLITUDE,fixture.CURSOR_CURRENT):
            called=self.request(projection,'tools/call',{'name':projection_tool_name(device,capability),'arguments':{}})
            self.assertEqual(called['result']['structuredContent']['receipt']['status'],'completed',called)
        artifacts=[]
        for mode,length,multiplier,offset in [('screen',1031,37,11),('memory',20001,53,7)]:
            stopped=self.request(projection,'tools/call',{'name':tools['run_control'],'arguments':{'action':'stop'}})
            self.assertEqual(stopped['result']['structuredContent']['receipt']['status'],'completed')
            raw=bytes((i*multiplier+offset)%256 for i in range(length))
            volts=[(v-127)*.02 for v in raw];step=max(1,length//10000);indices=list(range(0,length,step))
            expected_stats={'vmin_V':round(min(volts),6),'vmax_V':round(max(volts),6),'vpp_V':round(max(volts)-min(volts),6),'vavg_V':round(sum(volts)/length,6),'vrms_V':round(math.sqrt(sum(v*v for v in volts)/length),6)}
            for include in (True,False):
                response=self.request(projection,'tools/call',{'name':tools['get_waveform'],'arguments':{'mode':mode,'max_points':10000,'include_data':include}})
                receipt=response['result']['structuredContent']['receipt'];value=self.result(client,receipt)
                expected={'channel':1,'mode':mode,'points_captured':length,'dt_s':1e-6,'t0_s':-.001,'sample_rate_Sa_per_s':1e6,'stats':expected_stats}
                if include:expected.update(decimation_factor=step,points_returned=len(indices),time_s=[round(-.001+i*1e-6,12) for i in indices],voltage_V=[round(volts[i],6) for i in indices])
                self.assertEqual(value,expected)
                if mode=='memory' and include:self.assertEqual(value['points_returned'],10001)
                data=client.read_artifact(receipt['output']['artifact_ref'],session_id=receipt['session_id'])['data']
                desc=receipt['artifacts'][0]
                self.assertEqual((desc['size_bytes'],desc['digest']),(len(data),'sha256:'+hashlib.sha256(data).hexdigest()))
                self.assertEqual(desc['x-vendor']['openmhs.mcp_result']['coverage'],'complete_returned_result')
                artifacts.append((desc['uri'],data))
        response=self.request(projection,'tools/call',{'name':tools['get_screenshot'],'arguments':{}})
        receipt=response['result']['structuredContent']['receipt'];self.assertEqual(receipt['status'],'completed')
        self.assertEqual((receipt['output']['width'],receipt['output']['height']),(3,2))
        data=client.read_artifact(receipt['output']['image_ref'],session_id=receipt['session_id'])['data']
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(list(image.getdata()),[(255,0,0),(0,255,0),(0,0,255),(17,34,51),(68,85,102),(119,136,153)])
        self.assertEqual(receipt['artifacts'][0]['digest'],'sha256:'+hashlib.sha256(data).hexdigest())
        artifacts.append((receipt['output']['image_ref'],data))
        output=io.BytesIO();requests=[{'jsonrpc':'2.0','id':i,'method':'resources/read','params':{'uri':uri}} for i,(uri,_) in enumerate(artifacts)]
        serve_stdio(projection,stdin=io.BytesIO(('\n'.join(map(json.dumps,requests))+'\n').encode()),stdout=output)
        rows=[json.loads(row) for row in output.getvalue().splitlines()]
        self.assertEqual([base64.b64decode(row['result']['contents'][0]['blob']) for row in rows],[data for _,data in artifacts])

    def test_no_implicit_stop_for_memory_and_no_unpermitted_effect(self):
        peer,directory,driver,store,server,client,device=self.make(permit=True)
        receipt=self.invoke(client,device,'run_control',{'action':'run'})
        self.assertEqual(receipt['status'],'rejected');self.assertEqual(receipt['error']['mhs_code'],'MHS.SAFETY.PERMIT_INVALID')
        self.assert_no_effects(directory)
        permit=client.permit(fixture.CAPS['run_control'],{'action':'run'},device_id=device)
        self.assertEqual(self.invoke(client,device,'run_control',{'action':'run'},permit_id=permit['permit_id'])['status'],'completed')
        before=len(self.events(directory));receipt=self.invoke(client,device,'get_waveform',{'mode':'memory'})
        self.assertEqual(receipt['error']['mhs_code'],'MHS.DEVICE.PRECONDITION_UNMET')
        calls=[e.get('tool') for e in self.events(directory)[before:] if e['method']=='tools/call']
        self.assertTrue(calls);self.assertEqual(set(calls),{'get_status'});self.assertEqual(json.loads((directory/'state.json').read_text())['trigger_status'],'RUN')
        peer,directory,driver,store,server,client,device=self.make(limits=False)
        receipt=self.invoke(client,device,'configure_timebase',{'scale':.01})
        self.assertEqual(receipt['error']['mhs_code'],'MHS.SAFETY.LIMITS_UNSET')
        for name,args in [('identify',{'url':'http://not-used.invalid'}),('configure_channel',{'channel':5}),('get_waveform',{'max_points':10001}),('configure_timebase',{'scale':True})]:
            self.assertEqual(self.invoke(client,device,name,args)['status'],'rejected')
        self.assert_no_effects(directory)

    def test_full_receipt_replay_mutation_principal_session_and_ttl(self):
        clock=[0.];tokens={'a':{'id':'alice','kind':'agent'},'b':{'id':'bob','kind':'agent'}}
        peer,directory,driver,store,server,client,device=self.make(store_options={'ttl_s':1,'clock':lambda:clock[0]},tokens=tokens)
        command=canonical.ulid();receipt=self.invoke(client,device,'get_screenshot',command_id=command)
        self.assertEqual(receipt['status'],'completed');original=copy.deepcopy(dict(receipt));count=len(self.events(directory))
        uri=receipt['output']['image_ref'];sid=receipt['session_id']
        data=client.read_artifact(uri,session_id=sid)['data']
        receipt['artifacts'][0]['x-vendor']['openmhs.mcp_result']['tool']='caller mutation'
        replay=self.invoke(client,device,'get_screenshot',command_id=command)
        self.assertTrue(replay['replayed']);self.assertEqual({k:v for k,v in replay.items() if k!='replayed'},{k:v for k,v in original.items() if k!='replayed'})
        self.assertEqual(client.read_artifact(uri,session_id=sid)['data'],data);self.assertEqual(len(self.events(directory)),count)
        for token in (None,'b','wrong'):
            other=MHSClient(InProcessTransport(server,auth_token=token))
            with self.assertRaises(MHSError):other.read_artifact(uri,session_id=sid)
        projection,tools=self.projection(client,device)
        self.assertIn('error',self.request(projection,'resources/read',{'uri':uri}))
        response=self.request(projection,'tools/call',{'name':tools['get_screenshot'],'arguments':{}})
        own=response['result']['structuredContent']['receipt'];own_uri=own['output']['image_ref']
        own['artifacts'][0]['x-vendor']['openmhs.mcp_result']['tool']='projected mutation'
        self.assertEqual(projection._artifact_routes[own_uri]['descriptor']['x-vendor']['openmhs.mcp_result']['tool'],'get_screenshot')
        self.assertIn('result',self.request(projection,'resources/read',{'uri':own_uri}))
        client.open_session([device])
        with self.assertRaises(MHSError):client.read_artifact(uri,session_id=client.session_id)
        clock[0]=2
        with self.assertRaises(MHSError):client.read_artifact(uri,session_id=sid)
        count=len(self.events(directory));expired=self.invoke(client,device,'get_screenshot',command_id=command,session_id=sid)
        self.assertEqual(expired['artifacts'],original['artifacts']);self.assertEqual(len(self.events(directory)),count)

    def test_bad_primary_results_preflight_and_failed_commit_have_no_grants(self):
        for plan,name in [({'fault':'bad_png','fault_tool':'get_screenshot'},'get_screenshot'),({'fault':'text_error','fault_tool':'get_waveform'},'get_waveform'),({'empty_waveform':True},'get_waveform')]:
            peer,directory,driver,store,server,client,device=self.make(plan)
            receipt=self.invoke(client,device,name)
            self.assertNotEqual(receipt['status'],'completed');self.assertNotIn('artifacts',receipt);self.assertEqual(store._grants,{})
            self.assertTrue(peer.wait_retired(2))
        peer,directory,driver,store,server,client,device=self.make(store_options={'max_artifact_bytes':4096})
        self.assertNotEqual(self.invoke(client,device,'get_waveform')['status'],'completed');self.assert_no_effects(directory)
        peer,directory,driver,store,server,client,device=self.make(store_options={'max_artifacts':1})
        self.assertEqual(self.invoke(client,device,'get_screenshot')['status'],'completed')
        before=[e for e in self.events(directory) if e.get('tool')=='get_waveform']
        self.assertNotEqual(self.invoke(client,device,'get_waveform')['status'],'completed')
        self.assertEqual([e for e in self.events(directory) if e.get('tool')=='get_waveform'],before)
        peer,directory,driver,store,server,client,device=self.make()
        with patch.object(ArtifactPublisher,'commit',side_effect=RuntimeError('controlled commit failure')):
            self.assertNotEqual(self.invoke(client,device,'get_screenshot')['status'],'completed')
        self.assertEqual(store._grants,{})
        receipt=self.invoke(client,device,'get_screenshot');desc=receipt['artifacts'][0]
        (store._root/desc['digest'][7:]).write_bytes(b'corrupted controlled bytes')
        with self.assertRaises(MHSError):client.read_artifact(desc['uri'],session_id=receipt['session_id'])
        root=store._root;close_server(server);self.assertFalse(root.exists());self.assertTrue(peer.wait_retired(3))

    def test_stock_cancel_retains_owner_and_never_publishes_late_output(self):
        peer,directory,driver,store,server,client,device=self.make({'hold_tool':'get_waveform','ignore_eof':True,'ignore_term':True})
        # Warm start makes the stock request deadline about the actual tool.
        self.assertEqual(self.invoke(client,device,'identify')['status'],'completed')
        release=threading.Event();observed=peer._retirement_observed
        with patch.object(peer,'_retirement_observed',lambda:release.is_set() and observed()):
            running=client.invoke(fixture.CAPS['get_waveform'],{},device_id=device,deadline_ms=20)
            self.assertIn(running['status'],('accepted','running'))
            self.assertTrue(wait_for(lambda:(directory/'held-get_waveform').exists()))
            def release_after_notification():
                if not wait_for(lambda:(directory/'cancel-seen').exists()):raise AssertionError('notification not delivered')
                (directory/'release-get_waveform').touch()
            releaser,released=self.spawn(release_after_notification)
            client.cancel(running['operation_id'],deadline_ms=100)
            self.assertTrue(wait_for(lambda:client.get_operation(running['operation_id']).get('status')=='unknown'))
            self.assertTrue(driver.inner._pending);self.assertEqual(store._grants,{})
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            releaser.join(2);self.assertNotIn('error',released)
            self.assertTrue((directory/'late-effect').exists())
            self.assertEqual(store._grants,{})
            release.set()
        self.assertTrue(peer.wait_retired(3));self.assertTrue(wait_for(lambda:not driver.inner._pending))
        self.assertTrue(driver.safety_status()['remote_uncertain']);self.assertFalse(driver.inner.estop()['safe_state_achieved'])

    def test_stop_close_and_terminal_loss_during_publication_never_grant(self):
        for action in ('stop','close','terminal'):
            peer,directory,driver,store,server,client,device=self.make()
            entered,release=threading.Event(),threading.Event();original=ArtifactPublisher.publish
            def hold(publisher,*args,**kwargs):
                result=original(publisher,*args,**kwargs);entered.set();release.wait(3);return result
            with patch.object(ArtifactPublisher,'publish',hold):
                worker,result=self.spawn(lambda:self.invoke(client,device,'get_screenshot'))
                self.assertTrue(entered.wait(2));before=time.monotonic()
                try:
                    if action=='stop':self.assertTrue(driver.inner.estop()['safe_state_achieved'])
                    elif action=='close':driver.close()
                    else:(directory/'exit-now').touch();self.assertTrue(peer.wait_retired(2))
                    self.assertLess(time.monotonic()-before,.5)
                finally:release.set();worker.join(3)
            self.assertNotEqual(result['value']['status'],'completed');self.assertNotIn('artifacts',result['value']);self.assertEqual(store._grants,{})
