"""Controlled remote lifecycle, no network or upstream package execution."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from mhs import signals
from mhs.artifacts import ArtifactScope, LocalArtifactStore, CONTEXT_KEY, ArtifactPublisher
from mhs.bridge.http import HttpBridge
from mhs.bridge.base import BridgeOutcomeUnknown, BridgeBusy
from mhs.errors import MHSError
from tests.driver.test_http import FIXTURE, fixture, compiled
from importlib import import_module

FakeOT2=import_module('.fake',fixture.__package__).FakeOT2


class HttpBridgeTests(unittest.TestCase):
    def make(self, peer=None, **settings):
        config=copy.deepcopy(fixture.CONFIG);config.update(settings)
        peer=peer or FakeOT2()
        bridge=HttpBridge(compiled(config),transport=peer,base_dir=FIXTURE)
        self.addCleanup(bridge.close)
        self.addCleanup(lambda:[release.set() for _,release in peer.blocks.values()])
        return bridge,peer

    def background(self, function):
        result={};done=threading.Event()
        def execute():
            try: result['value']=function()
            except BaseException as exc: result['error']=exc
            finally: done.set()
        thread=threading.Thread(target=execute,daemon=True);thread.start()
        self.addCleanup(lambda:thread.join(2))
        return result,done

    def settled(self, bridge):
        with bridge._condition:
            self.assertTrue(bridge._condition.wait_for(lambda:not bridge._pending,timeout=2))

    def test_full_upload_create_play_poll_and_exact_requests(self):
        bridge,peer=self.make()
        value=bridge.call(fixture.RUN,{'protocol':'controlled_protocol'})
        self.assertEqual(value,{'run_id':'run-1','protocol_id':'protocol-1','status':'succeeded'})
        self.assertEqual([peer.role(r) for r in peer.requests],['upload','create','play','status'])
        self.assertEqual(peer.uploads['protocol-1'],(FIXTURE/'protocol.json').read_bytes())
        self.assertEqual(peer.requests[1]['json'],{'data':{'protocolId':'protocol-1'}})
        self.assertEqual(peer.requests[2]['path'],'/runs/run-1/actions')
        self.assertEqual(peer.requests[2]['headers'],{'Opentrons-Version':'2'})
        self.assertEqual(bridge.call(fixture.INSPECT)['status'],'succeeded')
        self.assertEqual(len(bridge.call(fixture.LIST)['runs']),1)
        self.assertTrue(bridge._job['settled'])

    def test_pause_resume_and_cancel_keep_full_effectful_surface(self):
        bridge,peer=self.make(FakeOT2(auto_complete=False))
        result,done=self.background(lambda:bridge.call(fixture.RUN,{'protocol':'controlled_protocol'}))
        self.assertTrue(peer.started.wait(1))
        self.assertEqual(bridge.call(fixture.PAUSE)['status'],'paused')
        self.assertEqual(bridge.call(fixture.RESUME)['status'],'running')
        self.assertTrue(bridge.call(fixture.CANCEL)['stopped'])
        self.assertTrue(done.wait(1));self.assertIsInstance(result.get('error'),signals.Cancelled)
        self.assertEqual(peer.runs['run-1']['status'],'stopped')
        self.assertTrue(bridge.safety_status()['safe_state']['achieved'])
        self.assertTrue(bridge.reset()['reset'])

    def test_stalled_play_does_not_block_stop_or_get_mistaken_for_retirement(self):
        peer=FakeOT2(auto_complete=False);peer.late_play_after_stop=True
        entered,release=peer.block('play')
        bridge,_=self.make(peer,request_timeout_ms=100)
        result,done=self.background(lambda:bridge.call(fixture.RUN,{'protocol':'controlled_protocol'}))
        self.assertTrue(entered.wait(1));start=time.monotonic()
        self.assertFalse(bridge.estop()['safe_state_achieved'])
        self.assertLess(time.monotonic()-start,.2)
        self.assertEqual(peer.runs['run-1']['status'],'stopped')
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        with self.assertRaises(MHSError): bridge.reset()
        self.assertTrue(done.wait(1));self.assertIsInstance(result.get('error'),BridgeOutcomeUnknown)
        with self.assertRaises(MHSError): bridge.call(fixture.RUN,{'protocol':'controlled_protocol'})
        release.set();self.settled(bridge)
        self.assertEqual(peer.runs['run-1']['status'],'running','adversarial late play really occurred')
        self.assertTrue(bridge.estop()['safe_state_achieved'])
        self.assertTrue(bridge.reset()['reset'])

    def test_terminal_poll_waits_for_complete_stop_scope_check(self):
        peer=FakeOT2(auto_complete=False)
        status_entered,status_release=peer.block('status')
        scope_entered,scope_release=peer.block('list')
        bridge,_=self.make(peer,request_timeout_ms=1000)
        run,done=self.background(lambda:bridge.call(fixture.RUN,{'protocol':'controlled_protocol'}))
        self.assertTrue(status_entered.wait(1))
        stopped,stop_done=self.background(bridge.estop)
        with bridge._condition:
            self.assertTrue(bridge._condition.wait_for(lambda:bridge._latched,timeout=1))
        status_release.set();self.assertTrue(scope_entered.wait(1))
        self.assertFalse(stop_done.is_set());self.assertFalse(done.is_set())
        scope_release.set();self.assertTrue(stop_done.wait(1));self.assertTrue(done.wait(1))
        self.assertTrue(stopped['value']['safe_state_achieved']);self.assertIsInstance(run.get('error'),signals.Cancelled)

    def test_late_create_is_retained_and_becomes_addressable_for_stop(self):
        peer=FakeOT2();entered,release=peer.block('create')
        bridge,_=self.make(peer,request_timeout_ms=50)
        result,done=self.background(lambda:bridge.call(fixture.RUN,{'protocol':'controlled_protocol'}))
        self.assertTrue(entered.wait(1));self.assertTrue(done.wait(1))
        self.assertIsInstance(result.get('error'),BridgeOutcomeUnknown)
        self.assertFalse(bridge.estop()['safe_state_achieved'])
        release.set();self.settled(bridge)
        self.assertEqual(bridge._job['run_id'],'run-1')
        self.assertNotIn('play',[peer.role(r) for r in peer.requests])
        self.assertTrue(bridge.estop()['safe_state_achieved'])

    def test_unknown_upload_outcome_cannot_be_discarded_by_reset_or_new_run(self):
        peer=FakeOT2();entered,release=peer.block('upload')
        bridge,_=self.make(peer,request_timeout_ms=50)
        _,done=self.background(lambda:bridge.call(fixture.RUN,{'protocol':'controlled_protocol'}))
        self.assertTrue(entered.wait(1));self.assertTrue(done.wait(1));release.set();self.settled(bridge)
        self.assertEqual(bridge._job['protocol_id'],'protocol-1')
        self.assertFalse(bridge.estop()['safe_state_achieved'])
        with self.assertRaises(MHSError): bridge.reset()
        with self.assertRaises(MHSError): bridge.call(fixture.RUN,{'protocol':'controlled_protocol'})
        self.assertEqual(len(peer.requests),1)

    def test_http_success_or_stopping_state_is_not_stop_settlement(self):
        for status in ['running','stop-requested','paused']:
            bridge,peer=self.make();bridge.call(fixture.RUN,{'protocol':'controlled_protocol'});peer.stop_state=status
            with self.subTest(status=status):
                self.assertFalse(bridge.estop()['safe_state_achieved'])
                with self.assertRaises(MHSError): bridge.reset()

    def test_empty_local_ownership_and_foreign_active_jobs_are_not_safe(self):
        bridge,peer=self.make()
        self.assertFalse(bridge.estop()['safe_state_achieved']);self.assertEqual(peer.requests,[])
        bridge,peer=self.make();bridge.call(fixture.RUN,{'protocol':'controlled_protocol'})
        peer.runs['foreign']={'id':'foreign','status':'running','protocolId':'outside','current':True}
        self.assertFalse(bridge.estop()['safe_state_achieved'])
        self.assertEqual(peer.runs['foreign']['status'],'running','foreign work must not be stopped by guessing ownership')
        with self.assertRaises(MHSError):bridge.reset()

    def test_fresh_unsafe_observation_revokes_prior_safe_status(self):
        bridge,peer=self.make();bridge.call(fixture.RUN,{'protocol':'controlled_protocol'});bridge.estop()
        self.assertTrue(bridge.safety_status()['safe_state']['achieved'])
        peer.auto_complete=False;peer.runs['run-1']['status']='running'
        self.assertEqual(bridge.read('main',['status'])['status'],'running')
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        with self.assertRaises(MHSError):bridge.reset()

    def test_invalid_effect_responses_preserve_uncertainty(self):
        mutations=[lambda r,m:{**r,'status':302},lambda r,m:{**r,'request_id':'other'},
                   lambda r,m:{**r,'body':'{"data":{"id":"a"},"data":{"id":"b"}}'},
                   lambda r,m:{**r,'body':'{"data":{"id":"x"},"errors":[{"detail":"bad"}]}'},
                   lambda r,m:{**r,'headers':{'Content-Type':'application/xml'}},
                   lambda r,m:{**r,'headers':{'Content-Type':'application/json','Content-Encoding':'gzip'}},
                   lambda r,m:{**r,'body':'{"data":{"id":"../other"}}'},
                   lambda r,m:{**r,'body':'{"data":{"id":NaN}}'}]
        for mutate in mutations:
            peer=FakeOT2();peer.mutators['upload']=mutate;bridge,_=self.make(peer)
            with self.subTest(mutate=mutate),self.assertRaises(BridgeOutcomeUnknown):bridge.call(fixture.RUN,{'protocol':'controlled_protocol'})
            self.assertTrue(bridge.safety_status()['remote_uncertain'])
            self.assertEqual(len(peer.requests),1)

    def test_fresh_response_must_identify_owned_job(self):
        peer=FakeOT2();peer.mutators['status']=lambda r,m:{**r,'body':'{"data":{"id":"foreign","status":"succeeded"}}'}
        bridge,_=self.make(peer)
        with self.assertRaises(MHSError):bridge.call(fixture.RUN,{'protocol':'controlled_protocol'})
        self.assertFalse(bridge._job['settled']);self.assertTrue(bridge._debt)

    def test_response_byte_header_depth_and_encoding_bounds(self):
        changes=[{'body':'x'*(2*1024*1024+1)},
                 {'headers':{'Content-Type':'application/json','X-Extra':'x'*33000}},
                 {'headers':{'Content-Type':'application/json','content-type':'application/json'}},
                 {'headers':{'Content-Type':'application/json','X-Extra':'one\r\ntwo'}},
                 {'body':'{"data":{"id":"ok"},"nested":'+('['*20)+'0'+(']'*20)+'}'}]
        for change in changes:
            peer=FakeOT2();peer.mutators['upload']=lambda raw,msg,change=change:{**raw,**change}
            bridge,_=self.make(peer)
            with self.subTest(change=list(change)),self.assertRaises(BridgeOutcomeUnknown):bridge.call(fixture.RUN,{'protocol':'controlled_protocol'})
            self.assertEqual(len(peer.requests),1);self.assertFalse(bridge.safety_status()['safe_state']['achieved'])

    def test_bounded_polling_retains_ownership_and_confirmed_cancellation_retires_it(self):
        bridge,peer=self.make(FakeOT2(auto_complete=False),max_polls=2)
        with self.assertRaises(BridgeOutcomeUnknown):bridge.call(fixture.RUN,{'protocol':'controlled_protocol'})
        self.assertEqual(peer.runs['run-1']['status'],'running');self.assertTrue(bridge._debt)
        self.assertTrue(bridge.estop()['safe_state_achieved'])
        bridge,peer=self.make(FakeOT2(auto_complete=False));cancel=threading.Event()
        result,done=self.background(lambda:bridge.call(fixture.RUN,{'protocol':'controlled_protocol'},ctx={'cancel_event':cancel}))
        self.assertTrue(peer.started.wait(1));cancel.set();self.assertTrue(done.wait(1))
        self.assertIsInstance(result.get('error'),signals.Cancelled)
        self.assertEqual(peer.runs['run-1']['status'],'stopped')
        self.assertIn('stop',[peer.role(item) for item in peer.requests])
        self.assertFalse(bridge._debt)
        self.assertTrue(bridge.safety_status()['safe_state']['achieved'])

    def test_integrity_and_no_follow_artifact_read_before_any_effect(self):
        for case in ('changed','leaf_link','parent_link'):
            with tempfile.TemporaryDirectory() as root:
                root=Path(root);target=root/'protocol.json'
                if case=='changed':target.write_bytes(b'other')
                elif case=='leaf_link':target.symlink_to(FIXTURE/'protocol.json')
                else:
                    (root/'subdir').symlink_to(FIXTURE,target_is_directory=True)
                config=compiled()
                if case=='parent_link':config['artifacts']['controlled_protocol']['path']='subdir/protocol.json'
                peer=FakeOT2();bridge=HttpBridge(config,transport=peer,base_dir=root)
                try:
                    with self.subTest(case=case),self.assertRaises(MHSError):bridge.call(fixture.RUN,{'protocol':'controlled_protocol'})
                    self.assertEqual(peer.requests,[])
                finally:bridge.close()

    def test_explicit_auth_reference_is_unresolved_before_requests(self):
        config=compiled();config['auth_ref']='deployment_policy';peer=FakeOT2()
        with self.assertRaisesRegex(ValueError,'credential policy'):HttpBridge(config,transport=peer)
        self.assertEqual(peer.requests,[])

    def test_owned_close_deferred_until_retained_request_returns_exactly_once(self):
        peer=FakeOT2();entered,release=peer.block('upload');bridge,_=self.make(peer,request_timeout_ms=50)
        _,done=self.background(lambda:bridge.call(fixture.RUN,{'protocol':'controlled_protocol'}))
        self.assertTrue(entered.wait(1));self.assertTrue(done.wait(1));bridge.close();bridge.close()
        self.assertEqual(peer.close_calls,0);self.assertTrue(bridge._pending)
        release.set();self.assertTrue(bridge._close_done.wait(1));self.assertEqual(peer.close_calls,1)
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])

    def test_borrowed_or_failed_blocking_close_stays_local_and_bounded(self):
        bridge,peer=self.make(owned_transport=False);bridge.close();self.assertTrue(bridge._close_done.wait(1));self.assertEqual(peer.close_calls,0)
        peer=FakeOT2();peer.close_error=True;peer.close_release=threading.Event();self.addCleanup(peer.close_release.set)
        bridge,_=self.make(peer);start=time.monotonic();bridge.close();self.assertLess(time.monotonic()-start,.1)
        self.assertTrue(peer.close_entered.wait(1));self.assertFalse(bridge._close_done.is_set())
        peer.close_release.set();self.assertTrue(bridge._close_done.wait(1));self.assertEqual(bridge._close_error,'RuntimeError')

    def test_log_response_failure_never_creates_grant(self):
        bridge,peer=self.make();bridge.call(fixture.RUN,{'protocol':'controlled_protocol'})
        peer.mutators['commands']=lambda r,m:{**r,'body':'{"data": "wrong"}'}
        store=LocalArtifactStore();store.bind('mhs://localhost');self.addCleanup(store.close)
        publisher=store.publisher(ArtifactScope('s','d','main',fixture.LOGS,'c'),lambda:None)
        with self.assertRaises(MHSError):bridge.call(fixture.LOGS,ctx={'extra':{CONTEXT_KEY:publisher}})
        self.assertEqual(store._grants,{})

    def test_log_publication_does_not_hold_stop_lane_and_aborts_after_stop(self):
        bridge,peer=self.make();bridge.call(fixture.RUN,{'protocol':'controlled_protocol'})
        store=LocalArtifactStore();store.bind('mhs://localhost');self.addCleanup(store.close)
        publisher=store.publisher(ArtifactScope('s','d','main',fixture.LOGS,'c'),lambda:None)
        entered,release=threading.Event(),threading.Event();self.addCleanup(release.set)
        original=ArtifactPublisher.publish
        def blocked(pub,*args,**kwargs):
            descriptor=original(pub,*args,**kwargs);entered.set();release.wait(2);return descriptor
        with patch.object(ArtifactPublisher,'publish',blocked):
            result,done=self.background(lambda:bridge.call(fixture.LOGS,ctx={'extra':{CONTEXT_KEY:publisher}}))
            self.assertTrue(entered.wait(1));start=time.monotonic()
            self.assertTrue(bridge.estop()['safe_state_achieved']);self.assertLess(time.monotonic()-start,.2)
            release.set();self.assertTrue(done.wait(1))
        self.assertIn('error',result);self.assertEqual(store._grants,{})

    def test_close_during_staged_publication_aborts_uncommitted_log(self):
        bridge,peer=self.make();bridge.call(fixture.RUN,{'protocol':'controlled_protocol'})
        store=LocalArtifactStore();store.bind('mhs://localhost');self.addCleanup(store.close)
        publisher=store.publisher(ArtifactScope('s','d','main',fixture.LOGS,'c'),lambda:None)
        entered,release=threading.Event(),threading.Event();self.addCleanup(release.set)
        original=ArtifactPublisher.publish
        def blocked(pub,*args,**kwargs):
            value=original(pub,*args,**kwargs);entered.set();release.wait(2);return value
        with patch.object(ArtifactPublisher,'publish',blocked):
            result,done=self.background(lambda:bridge.call(fixture.LOGS,ctx={'extra':{CONTEXT_KEY:publisher}}))
            self.assertTrue(entered.wait(1));bridge.close();release.set();self.assertTrue(done.wait(1))
        self.assertIn('error',result);self.assertEqual(store._grants,{})


class HttpExchangeReplayTests(unittest.TestCase):
    def record(self):
        from mhs.bridge.http_replay import exchange_record
        records=[];peer=FakeOT2()
        for role in ('upload','create','play','status'):
            peer.mutators[role]=lambda raw,message:(records.append(exchange_record(message,raw)) or raw)
        bridge=HttpBridge(compiled(),transport=peer,base_dir=FIXTURE)
        try: result=bridge.call(fixture.RUN,{'protocol':'controlled_protocol'})
        finally: bridge.close()
        return records,result

    def test_full_workflow_replays_complete_exchange_and_fresh_local_identity(self):
        from mhs.bridge.http_replay import ReplayHttpExchange
        records,expected=self.record();replay=ReplayHttpExchange(records)
        bridge=HttpBridge(compiled(),transport=replay,base_dir=FIXTURE)
        try:
            self.assertEqual(bridge.call(fixture.RUN,{'protocol':'controlled_protocol'}),expected)
            self.assertEqual(replay._position,4)
            self.assertTrue(all(item['request']['request_id'] not in replay._seen for item in records))
        finally:bridge.close()

    def test_method_origin_header_query_body_or_reused_id_cannot_match(self):
        from mhs.bridge.http_replay import ReplayHttpExchange
        records,_=self.record()
        for field,value in [('method','DELETE'),('origin','http://foreign.invalid'),('headers',{'Opentrons-Version':'3'}),
                            ('query',{'redirect':'elsewhere'}),('multipart',{'sha256':'0'*64})]:
            replay=ReplayHttpExchange(records);message=copy.deepcopy(records[0]['request']);message[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):replay.request(message,timeout_ms=50)
            self.assertEqual(replay._position,0)
        replay=ReplayHttpExchange(records);message=copy.deepcopy(records[0]['request']);replay.request(message,timeout_ms=50)
        following=copy.deepcopy(records[1]['request']);following['request_id']=message['request_id']
        with self.assertRaises(ValueError):replay.request(following,timeout_ms=50)

    def test_legacy_incomplete_and_mismatched_record_identity_refuse(self):
        from mhs.bridge.http_replay import ReplayHttpExchange
        records,_=self.record()
        changed=copy.deepcopy(records);changed[0]['response']['request_id']='f'*32
        missing=copy.deepcopy(records);del missing[0]['request']['headers']
        for data in [changed,missing,[{'method':'POST','path':'/protocols','response':{}}],records[:1]*2]:
            with self.assertRaises(ValueError):ReplayHttpExchange(data)


if __name__ == '__main__':unittest.main()
