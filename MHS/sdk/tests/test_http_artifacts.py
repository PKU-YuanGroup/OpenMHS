"""Full HTTP workflow on stock server plus generic scoped MCP log artifacts."""
import base64
import copy
import hashlib
import io
import json
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mhs import canonical
from mhs.artifacts import ArtifactPublisher, ArtifactScope, LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import build_server,close_server
from mhs.driver.build import build_manifest,device_from_manifest
from mhs.driver.check import _hardware_view_subject
from mhs.errors import MHSError
from mhs.evidence import verify_bundle
from mhs.mcp import MAX_FRAME_BYTES,MAX_ARTIFACT_RESPONSE_BYTES,MCPPolicy,MCPProjection,serve_stdio
from mhs.schema.store import default_store
from mhs.server import MHSServer
from tests.driver.test_http import FIXTURE,fixture
from tests.bridges.test_http import FakeOT2


class HttpStockTests(unittest.TestCase):
    def make(self, *, hardware_view=False, overlay=True, options=None, store_options=None, tokens=None):
        peer=FakeOT2(**(options or {}))
        class Variant(fixture.Driver): pass
        Variant.http_config=copy.deepcopy(fixture.CONFIG)
        if (options or {}).get('log_padding',0)>1024*1024:
            Variant.http_config['max_body_bytes']=8*1024*1024
        driver=Variant(backend='fake',native=peer,base_dir=FIXTURE)
        store=LocalArtifactStore(**(store_options or {}))
        if hardware_view:
            model=_hardware_view_subject(SimpleNamespace(cls=type(driver),instance=driver))
            manifest=build_manifest(model,backend='hardware')
            # Synthetic authority of this in-process fake test, never a human
            # signature or a production/native approval authority.
            verifier=lambda request:{'verified':True,'approvals':[{'principal':'test:http-controlled-peer',
                'method':'human_click','evidence_ref':'SDK fake admission test; no person or hardware'}]}
            server=MHSServer('mhs://localhost',[device_from_manifest(manifest,driver)],strict=True,armed=True,
                site_limits=fixture.overlay() if overlay else None,artifact_store=store,auth_tokens=tokens,
                approval_verifier=verifier)
        else:
            server=build_server(driver,site_limits=fixture.overlay() if overlay else None,artifact_store=store,auth_tokens=tokens)
        self.addCleanup(close_server,server)
        client=MHSClient(InProcessTransport(server,auth_token='fixture-a' if tokens else None));client.hello()
        device=next(iter(server.devices));client.open_session([device],mode=server.devices[device].mode)
        return peer,driver,store,server,client,device

    def run_protocol(self, client, device, **options):
        args={'protocol':'controlled_protocol'}
        permit=client.permit(fixture.RUN,args,device_id=device)
        return client.invoke(fixture.RUN,args,device_id=device,permit_id=permit['permit_id'],**options)

    def request(self,projection,method,params=None):
        return projection.handle_message({'jsonrpc':'2.0','id':canonical.ulid(),'method':method,'params':params or {}})

    def projection(self,client):
        result=MCPProjection(client,policy=MCPPolicy(enabled=True,allow_hardware=False));self.addCleanup(result.close)
        self.assertIn('result',self.request(result,'initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'http-fixture','version':'1'}}))
        tools=self.request(result,'tools/list')['result']['tools']
        name=next(item['name'] for item in tools if item['name'].endswith('ot2_logs'))
        return result,name

    def test_stock_hardware_view_preserves_permit_and_operator_envelope(self):
        peer,driver,store,server,client,device=self.make(hardware_view=True)
        denied=client.invoke(fixture.RUN,{'protocol':'controlled_protocol'},device_id=device)
        self.assertEqual(denied['status'],'rejected');self.assertEqual(denied['error']['mhs_code'],'MHS.SAFETY.PERMIT_INVALID')
        self.assertEqual(peer.requests,[])
        allowed=self.run_protocol(client,device)
        self.assertEqual(allowed['status'],'completed',allowed)
        self.assertEqual([peer.role(r) for r in peer.requests if r['method']=='POST'],['upload','create','play'])
        self.assertEqual(default_store().validate(dict(allowed),'receipt.schema.json'),[])
        self.assertEqual(allowed['mode'],'hardware','hardware contract is served by controlled fake only')

    def test_missing_operator_envelope_and_unapproved_input_have_zero_effects(self):
        peer,_,_,_,client,device=self.make(hardware_view=True,overlay=False)
        missing=self.run_protocol(client,device)
        self.assertEqual(missing['status'],'rejected')
        self.assertEqual(missing['error']['mhs_code'],'MHS.SAFETY.LIMITS_UNSET')
        self.assertEqual(peer.requests,[])
        peer,_,_,_,client,device=self.make(hardware_view=True)
        result=client.invoke(fixture.RUN,{'protocol':'arbitrary_path.py'},device_id=device)
        self.assertEqual(result['status'],'rejected');self.assertEqual(peer.requests,[])

    def test_stock_full_active_pause_resume_cancel(self):
        peer,driver,store,server,client,device=self.make(options={'auto_complete':False})
        running=self.run_protocol(client,device,deadline_ms=20)
        self.assertIn(running['status'],('running','accepted'));self.assertTrue(peer.started.wait(1))
        paused=client.invoke(fixture.PAUSE,{},device_id=device)
        self.assertEqual(paused['status'],'completed',paused);self.assertEqual(paused['output']['status'],'paused')
        denied=client.invoke(fixture.RESUME,{},device_id=device);self.assertEqual(denied['status'],'rejected')
        permit=client.permit(fixture.RESUME,{},device_id=device)
        resumed=client.invoke(fixture.RESUME,{},device_id=device,permit_id=permit['permit_id'])
        self.assertEqual(resumed['status'],'completed',resumed)
        stopped=client.invoke(fixture.CANCEL,{},device_id=device)
        self.assertEqual(stopped['status'],'completed',stopped);self.assertTrue(stopped['output']['stopped'])
        final=client.wait(running['operation_id'],timeout=2)
        self.assertEqual(final['status'],'cancelled',final)
        self.assertEqual(peer.runs['run-1']['status'],'stopped')

    def test_exact_large_log_bytes_schema_provenance_and_mcp_stdio(self):
        size=4*1024*1024
        peer,driver,store,server,client,device=self.make(options={'log_padding':size},store_options={'max_artifact_bytes':8*1024*1024})
        self.assertEqual(self.run_protocol(client,device)['status'],'completed')
        projection,tool=self.projection(client)
        response=self.request(projection,'tools/call',{'name':tool,'arguments':{}})['result']
        receipt=response['structuredContent']['receipt'];self.assertEqual(receipt['status'],'completed',receipt)
        self.assertEqual(default_store().validate(dict(receipt),'receipt.schema.json'),[])
        self.assertNotIn('image_ref',receipt['output']);self.assertFalse(receipt['output']['complete'])
        descriptor=receipt['artifacts'][0];uri=receipt['output']['artifact_ref']
        links=[item for item in response['content'] if item['type']=='resource_link']
        self.assertEqual([(x['uri'],x['name'],x['mimeType']) for x in links],[(uri,'Command artifact','application/json')])
        data=client.read_artifact(uri,session_id=receipt['session_id'])['data'];document=json.loads(data)
        self.assertEqual(document['run_id'],'run-1');self.assertEqual(document['protocol_sha256'],fixture.PROTOCOL_SHA256)
        from mhs.driver.http_check import SOURCE_SHA256,SOURCE_COMMIT
        self.assertEqual(document['request_profile_source']['sha256'],SOURCE_SHA256)
        self.assertEqual(document['request_profile_source']['commit'],SOURCE_COMMIT)
        self.assertFalse(document['request_profile_source']['executed'])
        self.assertEqual(document['commands']['data'][0]['fixture_payload'],'x'*size)
        self.assertEqual(document['coverage'],'first_command_page');self.assertFalse(document['complete'])
        evidence=document['evidence'];self.assertTrue(all(len(item['response_sha256'])==64 for item in evidence))
        self.assertTrue(all(item['ended_monotonic_ns']>=item['started_monotonic_ns'] for item in evidence))
        self.assertEqual(hashlib.sha256(data).hexdigest(),descriptor['digest'][7:]);self.assertEqual(len(data),descriptor['size_bytes'])
        self.assertTrue(verify_bundle(client.export_evidence(session_id=receipt['session_id'])).valid)
        output=io.BytesIO();request={'jsonrpc':'2.0','id':'large-log','method':'resources/read','params':{'uri':uri}}
        serve_stdio(projection,stdin=io.BytesIO((json.dumps(request)+'\n').encode()),stdout=output)
        wire=output.getvalue();self.assertGreater(len(wire),MAX_FRAME_BYTES);self.assertLessEqual(len(wire),MAX_ARTIFACT_RESPONSE_BYTES)
        self.assertEqual(base64.b64decode(json.loads(wire)['result']['contents'][0]['blob']),data)

    def test_owner_session_isolation_and_projection_cannot_steal_existing_grant(self):
        tokens={'fixture-a':{'id':'alice','kind':'agent'},'fixture-b':{'id':'bob','kind':'agent'}}
        _,_,_,server,client,device=self.make(tokens=tokens);self.run_protocol(client,device)
        receipt=client.invoke(fixture.LOGS,{},device_id=device);uri=receipt['output']['artifact_ref'];sid=client.session_id
        for token in (None,'fixture-b','invalid'):
            other=MHSClient(InProcessTransport(server,auth_token=token))
            with self.subTest(token=token),self.assertRaises(MHSError):other.read_artifact(uri,session_id=sid)
        client.open_session([device])
        with self.assertRaises(MHSError):client.read_artifact(uri,session_id=client.session_id)
        projection,_=self.projection(client)
        self.assertEqual(projection._register_artifacts(receipt),[])
        self.assertIn('error',self.request(projection,'resources/read',{'uri':uri}))
        self.assertTrue(client.read_artifact(uri,session_id=sid)['data']);client.close_session(sid)
        with self.assertRaises(MHSError):client.read_artifact(uri,session_id=sid)

    def test_replay_reuses_exact_scoped_grant_without_new_log_requests_or_ttl(self):
        now=[0.0];peer,_,_,_,client,device=self.make(store_options={'ttl_s':1,'clock':lambda:now[0]});self.run_protocol(client,device)
        key=canonical.ulid();first=client.invoke(fixture.LOGS,{},device_id=device,command_id=key)
        count=sum(peer.role(item)=='commands' for item in peer.requests)
        replay=client.invoke(fixture.LOGS,{},device_id=device,command_id=key)
        self.assertTrue(replay['replayed']);self.assertEqual(replay['artifacts'],first['artifacts'])
        now[0]=2
        with self.assertRaises(MHSError):client.read_artifact(first['output']['artifact_ref'],session_id=client.session_id)
        replay=client.invoke(fixture.LOGS,{},device_id=device,command_id=key)
        self.assertEqual(replay['artifacts'],first['artifacts'])
        self.assertEqual(sum(peer.role(item)=='commands' for item in peer.requests),count)

    def test_size_capacity_and_changed_digest_refused(self):
        peer,_,store,_,client,device=self.make(store_options={'max_artifact_bytes':4096});self.run_protocol(client,device)
        receipt=client.invoke(fixture.LOGS,{},device_id=device)
        self.assertEqual(receipt['status'],'failed');self.assertEqual(store._grants,{})
        _,_,store,_,client,device=self.make();self.run_protocol(client,device)
        receipt=client.invoke(fixture.LOGS,{},device_id=device);desc=receipt['artifacts'][0]
        path=store._root/desc['digest'][7:];path.write_bytes(b'changed')
        with self.assertRaises(MHSError):client.read_artifact(desc['uri'],session_id=client.session_id)

    def test_invalid_output_failed_commit_and_close_cleanup(self):
        _,_,store,server,client,device=self.make();self.run_protocol(client,device)
        original=ArtifactPublisher.prepare
        def invalid(pub,output):
            return original(pub,{**output,'artifact_ref':'foreign'})
        with patch.object(ArtifactPublisher,'prepare',invalid):
            failed=client.invoke(fixture.LOGS,{},device_id=device)
        self.assertEqual(failed['status'],'failed',failed);self.assertNotIn('artifacts',failed);self.assertEqual(store._grants,{})
        with patch.object(ArtifactPublisher,'commit',side_effect=RuntimeError('controlled failure')):
            failed=client.invoke(fixture.LOGS,{},device_id=device)
        self.assertNotEqual(failed['status'],'completed');self.assertNotIn('artifacts',failed);self.assertEqual(store._grants,{})
        receipt=client.invoke(fixture.LOGS,{},device_id=device);uri=receipt['output']['artifact_ref']
        root=store._root;close_server(server);self.assertFalse(root.exists())
        with self.assertRaises(MHSError):client.read_artifact(uri,session_id=receipt['session_id'])

    def test_generic_publisher_does_not_allow_ambiguous_image_reference(self):
        store=LocalArtifactStore();store.bind('mhs://localhost');self.addCleanup(store.close)
        pub=store.publisher(ArtifactScope('s','d','r',fixture.LOGS,'c'),lambda:None)
        desc=pub.publish(b'{}','application/json',output_field='artifact_ref')
        with self.assertRaises(MHSError):pub.prepare({'artifact_ref':desc['uri'],'image_ref':desc['uri']})
        self.assertEqual(store._grants,{})

    def test_stock_safe_cancel_finishes_while_generic_publication_is_held(self):
        _,driver,store,server,client,device=self.make();self.run_protocol(client,device)
        entered,release=threading.Event(),threading.Event();sid=client.session_id;results=[]
        original=ArtifactPublisher.publish
        def block(pub,*args,**kwargs):
            result=original(pub,*args,**kwargs);entered.set();release.wait(3);return result
        def logs():results.append(client.invoke(fixture.LOGS,{},device_id=device,session_id=sid,deadline_ms=2000))
        worker=threading.Thread(target=logs,daemon=True)
        try:
            with patch.object(ArtifactPublisher,'publish',block):
                worker.start();self.assertTrue(entered.wait(1))
                other=MHSClient(server);other.hello();start=time.monotonic()
                cancelled=other.invoke(fixture.CANCEL,{},device_id=device,session_id=sid,deadline_ms=200)
                self.assertEqual(cancelled['status'],'completed',cancelled)
                self.assertLess(time.monotonic()-start,.4);self.assertFalse(release.is_set())
                release.set();worker.join(2)
            self.assertFalse(worker.is_alive());self.assertNotEqual(results[0]['status'],'completed')
            self.assertNotIn('artifacts',results[0]);self.assertEqual(store._grants,{})
        finally:release.set();worker.join(2)


if __name__=='__main__':unittest.main()
