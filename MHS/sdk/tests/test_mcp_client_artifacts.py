"""Stock loader/server/MCP complete Rigol outputs and scoped byte ownership."""
import base64
import copy
import hashlib
import io
import json
import math
import threading
import time
import unittest
from unittest.mock import patch

from mhs import canonical
from mhs.adapter import load_driver
from mhs.artifacts import ArtifactPublisher
from mhs.client import InProcessTransport,MHSClient
from mhs.driver import build_server,close_server
from mhs.errors import MHSError
from mhs.mcp import MCPPolicy,MCPProjection,serve_stdio,projection_tool_name
from mhs.schema.store import default_store
from tests.driver.test_mcp_client import FIXTURE,fixture,ControlledPeer


class McpStockTests(unittest.TestCase):
    def make(self,*,limits=True,store_options=None,tokens=None,permit=False):
        from mhs.artifacts import LocalArtifactStore
        if permit:
            class Variant(fixture.Driver):pass
            Variant.actions=copy.deepcopy(fixture.Driver.actions)
            Variant.actions[fixture.CAPS['run_control']].requires_permit=True
            driver=Variant(backend='fake',base_dir=FIXTURE,native=ControlledPeer())
        else:
            driver=load_driver(FIXTURE,backend='fake')
        peer=driver.native
        store=LocalArtifactStore(**(store_options or {}))
        server=build_server(driver,site_limits=fixture.overlay() if limits else None,artifact_store=store,auth_tokens=tokens)
        self.addCleanup(close_server,server)
        client=MHSClient(InProcessTransport(server,auth_token='a' if tokens else None));client.hello()
        device=next(iter(server.devices));client.open_session([device],mode=server.devices[device].mode)
        return peer,driver,store,server,client,device

    def invoke(self,client,device,name,args=None,**kwargs):
        receipt=client.invoke(fixture.CAPS.get(name,name),args or {},device_id=device,**kwargs)
        if receipt['status'] in ('accepted','running'):
            receipt=client.wait(receipt['operation_id'],timeout=3)
        return receipt

    def result(self,client,receipt):
        self.assertEqual(receipt['status'],'completed',receipt)
        self.assertEqual(default_store().validate(dict(receipt),'receipt.schema.json'),[])
        if 'artifact_ref' in receipt['output']:
            data=client.read_artifact(receipt['output']['artifact_ref'],session_id=receipt['session_id'])['data']
            return json.loads(data)
        return receipt['output']

    def assert_no_effects(self,peer):
        self.assertFalse(any(call['message']['method']=='tools/call' and
            fixture.CONFIG['tools'][call['message']['params']['name']]['effectful'] for call in peer.calls))

    def request(self,projection,method,params=None):
        return projection.handle_message({'jsonrpc':'2.0','id':canonical.ulid(),'method':method,'params':params or {}})

    def projection(self,client,device):
        projection=MCPProjection(client,policy=MCPPolicy(enabled=True,allow_hardware=False));self.addCleanup(projection.close)
        self.assertIn('result',self.request(projection,'initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'controlled-rigol','version':'1'}}))
        names=self.request(projection,'tools/list')['result']['tools']
        tools={key:projection_tool_name(device,cap) for key,cap in fixture.CAPS.items()}
        self.assertTrue(set(tools.values()) <= {row['name'] for row in names})
        return projection,tools

    def test_complete_thirteen_tools_all_optional_fields_actions_and_partial_status(self):
        peer,driver,store,server,client,device=self.make()
        self.assertEqual(self.result(client,self.invoke(client,device,'identify'))['text'],'RIGOL TECHNOLOGIES,CONTROLLED-DHO,SDK-FAKE,0')
        peer.channel_count=2
        status=self.result(client,self.invoke(client,device,'get_status'))
        self.assertEqual(set(status['channels']),{'CH1','CH2'});self.assertEqual(status['channels']['CH2'],{'enabled':False})
        channel=self.result(client,self.invoke(client,device,'configure_channel',{'channel':2,'enabled':True,'scale':.2,'offset':-.1,
            'coupling':'AC','probe_ratio':10,'bandwidth_limit':'20M','invert':True}))
        self.assertEqual(channel,{'channel':2,'enabled':True,'scale_V_per_div':'0.2','offset_V':'-0.1','coupling':'AC','probe_ratio':'10','bandwidth_limit':'20M'})
        self.assertTrue(peer.invert[2]);self.assertNotIn('invert',channel)
        self.assertEqual(self.result(client,self.invoke(client,device,'configure_timebase',{'scale':.002,'offset':-.01})),{'scale_s_per_div':'0.002','offset_s':'-0.01'})
        trig=self.result(client,self.invoke(client,device,'configure_trigger_edge',{'source':'D15','slope':'RFALl','level':.25,'sweep':'SINGle'}))
        self.assertEqual(trig,{'mode':'EDGE','source':'D15','slope':'RFALl','level_V':'0.25','sweep':'SINGle','status':'STOP'})
        acq=self.result(client,self.invoke(client,device,'configure_acquisition',{'memory_depth':'50M','acq_type':'AVERages','averages':8}))
        self.assertEqual(acq,{'memory_depth':'50M','type':'AVERages','averages':'8','sample_rate_Sa_per_s':'1000000'})
        for action,command in [('run',':RUN'),('single',':SINGle'),('autoset',':AUToset'),('clear',':CLEar'),('force_trigger',':TFORce'),('stop',':STOP')]:
            self.assertTrue(self.result(client,self.invoke(client,device,'run_control',{'action':action}))['text'].startswith('Sent '+command+'.'))
        for mode,options in [('MANual',{'cursor_type':'AMPLitude','source':'MATH4','position_a':.2,'position_b':.8}),
                             ('MANual',{'cursor_type':'TIME','position_a':1e-6,'position_b':4e-6}),
                             ('TRACk',{'track_source_a':'CHAN2','track_source_b':'MATH3'}),('OFF',{})]:
            if mode=='MANual':
                cap=fixture.CURSOR_TIME if options['cursor_type']=='TIME' else fixture.CURSOR_AMPLITUDE
                arguments={k:v for k,v in options.items() if k!='cursor_type'}
            else:cap='configure_cursors';arguments={'mode':mode,**options}
            self.assertEqual(self.result(client,self.invoke(client,device,cap,arguments)),{'mode':mode})
            values=self.result(client,self.invoke(client,device,'get_cursor_values'));self.assertEqual(values['mode'],mode)
            if mode=='MANual':
                self.assertEqual(values['type'],options['cursor_type']);self.assertIn('inverse_delta_x',values)
                if options['cursor_type']=='AMPLitude':self.assertAlmostEqual(float(values['delta_y']),.6)
                else:self.assertAlmostEqual(float(values['delta_x']),3e-6)
            elif mode=='TRACk':self.assertEqual((values['source_a'],values['source_b']),('CHAN2','MATH3'))
            else:self.assertEqual(set(values),{'mode','note'})
        for item in fixture.MEASUREMENTS:
            value=self.result(client,self.invoke(client,device,'get_measurement',{'item':item,'channel':4}))
            self.assertEqual(value,{'item':item,'channel':4,'value':1.25,'invalid':False})
        for item in fixture.BETWEEN:
            value=self.result(client,self.invoke(client,device,'measure_between',{'item':item,'source_a':2,'source_b':3}))
            self.assertEqual(value,{'item':item,'source_a':2,'source_b':3,'value':1.25,'invalid':False})
        self.result(client,self.invoke(client,device,'get_waveform',{'mode':'screen'}))
        self.result(client,self.invoke(client,device,'get_waveform',{'mode':'memory','include_data':False}))
        self.assertEqual(self.invoke(client,device,'get_screenshot')['status'],'completed')
        called={c['message']['params'].get('name') for c in peer.calls if c['message']['method']=='tools/call'}
        self.assertEqual(called,set(fixture.CAPS))

    def test_nullable_optional_no_change_and_stock_limits_permits_zero_effect_refusal(self):
        peer,_,_,_,client,device=self.make(permit=True)
        before=copy.deepcopy(peer.calls)
        denied=self.invoke(client,device,'run_control',{'action':'run'})
        self.assertEqual(denied['status'],'rejected');self.assertEqual(denied['error']['mhs_code'],'MHS.SAFETY.PERMIT_INVALID')
        self.assert_no_effects(peer)

        permit=client.permit(fixture.CAPS['run_control'],{'action':'run'},device_id=device)
        self.assertEqual(self.invoke(client,device,'run_control',{'action':'run'},permit_id=permit['permit_id'])['status'],'completed')
        self.result(client,self.invoke(client,device,'configure_channel',{'channel':1,'coupling':None,'invert':None,'scale':None}))
        peer,_,_,_,client,device=self.make(limits=False)
        before=copy.deepcopy(peer.calls)
        missing=self.invoke(client,device,'configure_timebase',{'scale':.01})
        self.assertEqual(missing['status'],'rejected');self.assertEqual(missing['error']['mhs_code'],'MHS.SAFETY.LIMITS_UNSET')
        self.assert_no_effects(peer)
        for name,args in [('configure_channel',{'channel':5}),('get_waveform',{'max_points':10001}),
                          ('configure_timebase',{'scale':True}),('identify',{'endpoint':'http://other.invalid'}),
                          ('identify',{'code':'print(1)'}),('identify',{'tool':'scpi_command'})]:
            result=self.invoke(client,device,name,args);self.assertEqual(result['status'],'rejected',result)
        self.assert_no_effects(peer)

    def test_current_cursor_type_branch_preserves_omission_and_both_physical_units(self):
        for axis,cap,prefix,value in [('TIME',fixture.CURSOR_TIME,'time_',.000002),
                                      ('AMPLitude',fixture.CURSOR_AMPLITUDE,'voltage_',.75)]:
            peer,_,_,_,client,device=self.make()
            self.result(client,self.invoke(client,device,cap,{'position_a':0.0}))
            self.result(client,self.invoke(client,device,'configure_cursors',{'mode':'OFF'}))
            before=len(peer.calls)
            receipt=self.invoke(client,device,fixture.CURSOR_CURRENT,{'time_position_a':.000002,'voltage_position_a':.75})
            self.assertEqual(self.result(client,receipt),{'mode':'MANual'})
            selected=[c['message']['params'] for c in peer.calls[before:] if c['message']['params'].get('name')=='configure_cursors']
            self.assertEqual(len(selected),2);self.assertNotIn('cursor_type',selected[-1]['arguments'])
            self.assertEqual(selected[-1]['arguments']['position_a'],value)
            self.assertEqual(peer.cursor['a'+('x' if axis=='TIME' else 'y')],str(value))
            model=fixture.Driver.driver_model()
            binding=next(b for b in model.bindings if b.capability_id==fixture.CURSOR_CURRENT)
            self.assertEqual(binding.input_schema['properties'][prefix+'position_a']['x-mhs-unit'],'s' if axis=='TIME' else 'V')
        peer,driver,_,_,client,device=self.make()
        before=copy.deepcopy(peer.cursor)
        peer.cursor['type']='unrecognized'
        wrong=self.invoke(client,device,fixture.CURSOR_CURRENT,{'voltage_position_a':2.0})
        self.assertEqual(wrong['status'],'unknown',wrong)
        self.assertEqual(peer.cursor['mode'],'MANual');self.assertEqual(peer.cursor['ay'],before['ay'])
        self.assertTrue(driver.safety_status()['remote_uncertain'])

    def test_source_memory_prerequisite_uses_fresh_readback_without_implicit_stop(self):
        peer,_,_,_,client,device=self.make()
        self.result(client,self.invoke(client,device,'run_control',{'action':'run'}))
        before=len([c for c in peer.calls if c['message']['params'].get('name')=='get_waveform'])
        refused=self.invoke(client,device,'get_waveform',{'mode':'memory'})
        self.assertNotEqual(refused['status'],'completed')
        self.assertEqual(refused['error']['mhs_code'],'MHS.DEVICE.PRECONDITION_UNMET')
        self.assertEqual(peer.trigger_status,'RUN')
        self.assertEqual(before,len([c for c in peer.calls if c['message']['params'].get('name')=='get_waveform']))
        self.result(client,self.invoke(client,device,'run_control',{'action':'stop'}))
        self.assertEqual(self.result(client,self.invoke(client,device,'get_waveform',{'mode':'memory'}))['mode'],'memory')

    def test_mcp_full_screen_memory_arrays_png_bytes_and_stdio_retrieval(self):
        peer,_,_,_,client,device=self.make();projection,tools=self.projection(client,device)
        retrievals=[]
        for name in fixture.CAPS:
            response=self.request(projection,'tools/call',{'name':tools[name],'arguments':fixture.EXAMPLES[name]})
            self.assertEqual(response['result']['structuredContent']['receipt']['status'],'completed',response)
        for mode,raw in [('screen',peer.raw_screen),('memory',peer.raw_memory)]:
            stopped=self.request(projection,'tools/call',{'name':tools['run_control'],'arguments':{'action':'stop'}})
            self.assertEqual(stopped['result']['structuredContent']['receipt']['status'],'completed',stopped)
            wire=self.request(projection,'tools/call',{'name':tools['get_waveform'],'arguments':{'mode':mode,'max_points':10000}})
            receipt=wire['result']['structuredContent']['receipt'];document=self.result(client,receipt)
            indices=list(range(0,len(raw),max(1,len(raw)//10000)))
            self.assertEqual(document['points_returned'],len(indices))
            self.assertEqual(document['time_s'],[round(-.001+i/1000000,12) for i in indices])
            self.assertEqual(document['voltage_V'],[round((raw[i]-127)*.02,6) for i in indices])
            if mode=='memory':self.assertGreater(document['points_returned'],10000)
            volts=[(v-127)*.02 for v in raw]
            self.assertEqual(document['stats']['vrms_V'],round(math.sqrt(sum(v*v for v in volts)/len(volts)),6))
            self.assertEqual(document['points_captured'],len(raw));self.assertEqual(document['decimation_factor'],max(1,len(raw)//10000))
            descriptor=receipt['artifacts'][0];uri=descriptor['uri'];data=client.read_artifact(uri,session_id=receipt['session_id'])['data']
            self.assertEqual(descriptor['digest'],'sha256:'+hashlib.sha256(data).hexdigest());self.assertEqual(descriptor['size_bytes'],len(data))
            self.assertEqual(descriptor['x-vendor']['openmhs.mcp_result']['coverage'],'complete_returned_result')
            retrievals.append((uri,data))
        wire=self.request(projection,'tools/call',{'name':tools['get_screenshot'],'arguments':{}})
        receipt=wire['result']['structuredContent']['receipt'];self.assertEqual(receipt['status'],'completed',receipt)
        self.assertEqual((receipt['output']['width'],receipt['output']['height']),(3,2))
        self.assertEqual(client.read_artifact(receipt['output']['image_ref'],session_id=receipt['session_id'])['data'],peer.screenshot)
        from PIL import Image
        with Image.open(io.BytesIO(peer.screenshot)) as image:
            self.assertEqual(list(image.getdata()),[(255,0,0),(0,255,0),(0,0,255),(17,34,51),(68,85,102),(119,136,153)])
        output=io.BytesIO();requests=[{'jsonrpc':'2.0','id':i,'method':'resources/read','params':{'uri':uri}}
                                     for i,(uri,data) in enumerate(retrievals)]
        serve_stdio(projection,stdin=io.BytesIO(('\n'.join(map(json.dumps,requests))+'\n').encode()),stdout=output)
        responses=[json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([base64.b64decode(row['result']['contents'][0]['blob']) for row in responses],
                         [data for uri,data in retrievals])

    def test_scoped_replay_ttl_principal_session_and_metadata_projection_copy(self):
        clock=[0.0];tokens={'a':{'id':'alice','kind':'agent'},'b':{'id':'bob','kind':'agent'}}
        peer,_,_,server,client,device=self.make(store_options={'ttl_s':1,'clock':lambda:clock[0]},tokens=tokens)
        key=canonical.ulid();first=self.invoke(client,device,'get_screenshot',command_id=key)
        self.assertEqual(first['status'],'completed',first);count=len(peer.calls)
        replay=self.invoke(client,device,'get_screenshot',command_id=key)
        self.assertTrue(replay['replayed']);self.assertEqual(replay['artifacts'],first['artifacts']);self.assertEqual(len(peer.calls),count)
        uri=first['output']['image_ref'];sid=first['session_id']
        for token in (None,'b','wrong'):
            other=MHSClient(InProcessTransport(server,auth_token=token))
            with self.assertRaises(MHSError):other.read_artifact(uri,session_id=sid)
        projection,_=self.projection(client,device)
        isolated=copy.deepcopy(first);projection._register_artifacts(isolated)
        isolated['artifacts'][0]['x-vendor']['openmhs.mcp_result']['tool']='changed'
        read=self.request(projection,'resources/read',{'uri':uri})
        self.assertIn('error',read,'a new projection cannot acquire another session artifact')
        response=self.request(projection,'tools/call',{'name':projection_tool_name(device,fixture.CAPS['get_screenshot']),'arguments':{}})
        owned=response['result']['structuredContent']['receipt'];owned_uri=owned['output']['image_ref']
        owned['artifacts'][0]['x-vendor']['openmhs.mcp_result']['tool']='external mutation'
        self.assertEqual(projection._artifact_routes[owned_uri]['descriptor']['x-vendor']['openmhs.mcp_result']['tool'],'get_screenshot')
        self.assertIn('result',self.request(projection,'resources/read',{'uri':owned_uri}))
        count=len(peer.calls)
        client.open_session([device]);self.assertNotEqual(client.session_id,sid)
        with self.assertRaises(MHSError):client.read_artifact(uri,session_id=client.session_id)
        clock[0]=2
        with self.assertRaises(MHSError):client.read_artifact(uri,session_id=sid)
        expired=self.invoke(client,device,'get_screenshot',command_id=key,session_id=sid)
        self.assertEqual(expired['artifacts'],first['artifacts']);self.assertEqual(len(peer.calls),count)

    def test_invalid_primary_results_and_unfollowed_local_paths_have_no_partial_grants(self):
        mutations=[lambda r:r['result'].update(content=[{'type':'resource_link','uri':'file:///private/remote.png'}]),
            lambda r:r['result']['content'][0].update(data='%%'),
            lambda r:r['result']['content'][0].update(data=base64.b64encode(b'not png').decode()),
            lambda r:r['result']['content'][0].update(mimeType='image/jpeg'),
            lambda r:r['result']['content'][0].update(data=base64.b64encode(base64.b64decode(r['result']['content'][0]['data'])[:-4]).decode()),
            lambda r:r['result']['content'][0].update(data=r['result']['content'][0]['data']+'AAAA'),
            lambda r:r['result']['content'].append({'type':'text','text':'/tmp/full.png'})]
        for mutate in mutations:
            peer,_,store,_,client,device=self.make()
            def after(m,r,l):
                if m['params'].get('name')=='get_screenshot':mutate(r)
                return r
            peer.after=after
            receipt=self.invoke(client,device,'get_screenshot')
            self.assertNotEqual(receipt['status'],'completed');self.assertNotIn('artifacts',receipt);self.assertEqual(store._grants,{})

    def test_independent_primary_output_budget_and_node_bounds(self):
        for mode in ('text_budget','nodes','summary'):
            peer,_,store,_,client,device=self.make()
            def after(m,r,l):
                if m['params'].get('name')=='get_waveform':
                    if mode=='text_budget':r['result']['content'][0]['text']+=' '*(1024*1024)
                    elif mode=='nodes':r['result']['structuredContent']=[[0]*65536]*5
                    else:r['result']['content'][0]['text']=json.dumps({'points_captured':20001,'first_10':[1]*10,'last_10':[2]*10})
                return r
            peer.after=after
            receipt=self.invoke(client,device,'get_waveform',{'max_points':10})
            self.assertNotEqual(receipt['status'],'completed');self.assertEqual(store._grants,{})
        peer,_,store,_,client,device=self.make(store_options={'max_artifacts':1})
        self.assertEqual(self.invoke(client,device,'get_screenshot')['status'],'completed')
        count=len([c for c in peer.calls if c['message']['params'].get('name')=='get_waveform'])
        self.assertNotEqual(self.invoke(client,device,'get_waveform')['status'],'completed')
        self.assertEqual(len(store._grants),1)
        self.assertEqual(count,len([c for c in peer.calls if c['message']['params'].get('name')=='get_waveform']))
        for mutate in (lambda v:v['time_s'].pop(),lambda v:v.update(channel=4),lambda v:v.update(points_returned=True),
                       lambda v:v.update(first_10_samples=[1,2]),lambda v:v.clear()):
            peer,_,store,_,client,device=self.make()
            def after(m,r,l):
                if m['params'].get('name')=='get_waveform':
                    value=json.loads(r['result']['content'][0]['text']);mutate(value)
                    r['result']['content'][0]['text']=json.dumps(value)
                return r
            peer.after=after
            receipt=self.invoke(client,device,'get_waveform')
            self.assertNotEqual(receipt['status'],'completed');self.assertNotIn('artifacts',receipt);self.assertEqual(store._grants,{})

    def test_prior_global_result_cannot_settle_a_new_stock_request(self):
        peer,_,store,_,client,device=self.make();saved=[]
        def remember(message,response,lane):
            if message['params'].get('name')=='get_status':saved.append(copy.deepcopy(response))
            return response
        peer.after=remember
        self.assertEqual(self.result(client,self.invoke(client,device,'get_status'))['trigger_status'],'STOP')
        stale=saved[-1];peer.trigger_status='RUN'
        def replay_old(message,response,lane):
            return copy.deepcopy(stale) if message['params'].get('name')=='get_status' else response
        peer.after=replay_old
        rejected=self.invoke(client,device,'get_status')
        self.assertEqual(rejected['status'],'failed');self.assertIsNone(rejected['output'])
        self.assertEqual(rejected['error']['mhs_code'],'MHS.CAPABILITY.OUTPUT_INVALID')
        self.assertEqual(store._grants,{})
        peer.after=None
        self.assertEqual(self.result(client,self.invoke(client,device,'get_status'))['trigger_status'],'RUN')

    def test_preflight_size_digest_and_failed_publication_cleanup(self):
        peer,_,store,_,client,device=self.make(store_options={'max_artifact_bytes':4096})
        receipt=self.invoke(client,device,'get_waveform')
        self.assertNotEqual(receipt['status'],'completed');self.assertEqual(store._grants,{})
        self.assertFalse(any(c['message']['params'].get('name')=='get_waveform' for c in peer.calls))
        _,_,store,server,client,device=self.make()
        with patch.object(ArtifactPublisher,'commit',side_effect=RuntimeError('commit refused')):
            receipt=self.invoke(client,device,'get_screenshot')
        self.assertNotEqual(receipt['status'],'completed');self.assertEqual(store._grants,{})
        receipt=self.invoke(client,device,'get_screenshot');desc=receipt['artifacts'][0]
        (store._root/desc['digest'][7:]).write_bytes(b'corrupted')
        with self.assertRaises(MHSError):client.read_artifact(desc['uri'],session_id=receipt['session_id'])
        root=store._root;close_server(server);self.assertFalse(root.exists())

    def test_stock_cancel_retains_unknown_owner_until_real_retirement(self):
        peer,driver,store,server,client,device=self.make();entered,release=threading.Event(),threading.Event()
        def before(m,l):
            if l=='normal' and m['params'].get('name')=='get_waveform':entered.set();release.wait(3)
        peer.before=before
        try:
            running=client.invoke(fixture.CAPS['get_waveform'],{},device_id=device,deadline_ms=20)
            self.assertIn(running['status'],('running','accepted'),running);self.assertTrue(entered.wait(1))
            cancelled=client.cancel(running['operation_id'],deadline_ms=100);self.assertIsNotNone(cancelled)
            deadline=time.monotonic()+1
            while time.monotonic()<deadline:
                operation=client.get_operation(running['operation_id'])
                if operation.get('status')=='unknown':break
                time.sleep(.01)
            self.assertEqual(operation['status'],'unknown',operation)
            self.assertTrue(driver.inner._pending);self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            self.assertEqual(store._grants,{})
            release.set()
            with driver.inner._condition:self.assertTrue(driver.inner._condition.wait_for(lambda:not driver.inner._pending,timeout=1))
            self.assertEqual(store._grants,{});self.assertTrue(driver.inner.estop()['safe_state_achieved'])
        finally:
            release.set()
            with driver.inner._condition:driver.inner._condition.wait_for(lambda:not driver.inner._pending,timeout=1)

    def test_stop_and_close_do_not_wait_for_publication_or_allow_late_grants(self):
        for closing in (False,True):
            peer,driver,store,server,client,device=self.make();entered,release=threading.Event(),threading.Event();results=[]
            original=ArtifactPublisher.publish
            def held(pub,*args,**kwargs):
                result=original(pub,*args,**kwargs);entered.set();release.wait(3);return result
            worker=threading.Thread(target=lambda:results.append(self.invoke(client,device,'get_screenshot')))
            try:
                with patch.object(ArtifactPublisher,'publish',held):
                    worker.start();self.assertTrue(entered.wait(1));start=time.monotonic()
                    if closing:driver.close()
                    else:self.assertTrue(driver.inner.estop()['safe_state_achieved'])
                    self.assertLess(time.monotonic()-start,.4);self.assertFalse(release.is_set())
                    release.set();worker.join(2)
                self.assertFalse(worker.is_alive());self.assertNotEqual(results[0]['status'],'completed')
                self.assertNotIn('artifacts',results[0]);self.assertEqual(store._grants,{})
            finally:release.set();worker.join(2)


if __name__=='__main__':unittest.main()
