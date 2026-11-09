"""Actual SDK-owned pipes, finite parser controls and terminal owner races.

No upstream MCP SDK/server/device is imported. Test fault plans are bounded
data consumed by the one fixed SDK peer. Process exit proves software cleanup.
"""
import base64
import copy
import json
import os
from pathlib import Path
import signal
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from mhs import signals
from mhs.bridge.mcp_client import McpClientBridge
from mhs.bridge.mcp_stdio import OwnedStdioTransport, StdioBudget, StdioFailure, _Request
from tests.driver.test_mcp_client import compiled, fixture


def wait_for(predicate, seconds=2):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if predicate():return True
        time.sleep(.005)
    return bool(predicate())


def wire(ident='wire', name='identify', args=None):
    return {'jsonrpc':'2.0','id':ident,'method':'tools/call',
            'params':{'name':name,'arguments':args or {}}}


def line(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()+b'\n'


class OwnedPeerCase(unittest.TestCase):
    def peer(self, plan=None, budget=None):
        temporary=tempfile.TemporaryDirectory(prefix='mhs-controlled-stdio-')
        self.addCleanup(temporary.cleanup)
        directory=Path(temporary.name)
        if plan is not None:(directory/'scenario.json').write_text(json.dumps(plan,allow_nan=False))
        peer=OwnedStdioTransport(str(directory),budget=budget)
        def cleanup():
            peer.close()
            self.assertTrue(peer.wait_retired(4),peer.status())
        self.addCleanup(cleanup)
        return peer,directory

    def bridge(self, plan=None, timeout=1500, budget=None):
        peer,directory=self.peer(plan,budget)
        config=compiled();config['request_timeout_ms']=timeout;config['stop_timeout_ms']=1200
        bridge=McpClientBridge(config,transport=peer)
        self.addCleanup(lambda:self.assertTrue(bridge._close_done.wait(4)))
        self.addCleanup(bridge.close)
        return bridge,peer,directory

    def call(self, bridge, name='identify', args=None, **context):
        return bridge.call(fixture.CAPS[name],args or {},context)

    def events(self,directory):
        path=directory/'events.jsonl'
        return [json.loads(row) for row in path.read_text().splitlines()] if path.exists() else []

    def spawn(self, function):
        result={}
        def work():
            try:result['value']=function()
            except BaseException as exc:result['error']=exc
        worker=threading.Thread(target=work)
        worker.start()
        self.addCleanup(worker.join,4)
        return worker,result


class StdioProtocolTests(OwnedPeerCase):
    def test_lazy_fixed_peer_handshake_and_concurrent_first_lanes(self):
        peer,directory=self.peer({'hold_tool':'identify'})
        self.assertIsNone(peer.status()['pid']);self.assertFalse((directory/'peer-pid').exists())
        one,a=self.spawn(lambda:peer.exchange(wire('ordinary'),lane='normal',timeout_ms=1500))
        self.assertTrue(wait_for(lambda:(directory/'held-identify').exists()))
        b=peer.exchange(wire('protect','get_status'),lane='protective',timeout_ms=1000)
        self.assertEqual(b['id'],'protect');self.assertTrue(one.is_alive())
        (directory/'release-identify').touch();one.join(2)
        self.assertEqual(a['value']['id'],'ordinary')
        events=self.events(directory)
        self.assertEqual([e['method'] for e in events[:2]],['initialize','notifications/initialized'])
        self.assertEqual(sum(e['method']=='initialize' for e in events),1)
        self.assertEqual(events[0]['params']['protocolVersion'],'2025-11-25')
        self.assertEqual(events[0]['params']['capabilities'],{})
        self.assertTrue(events[0]['bytecode_disabled']);self.assertEqual(events[0]['isolated'],1)
        self.assertIn('Untrusted',peer.status()['initialization']['instructions'])
        a['value']['result']['content'][0]['text']='external mutation'
        self.assertNotIn('external mutation',json.dumps(b))

    def test_bad_initialization_never_dispatches_tool_or_reconnects(self):
        for plan in ({'version':'wrong'},{'bad_init_id':True},{'no_tools':True},{'init_malformed':True}):
            peer,directory=self.peer(plan)
            with self.subTest(plan=plan),self.assertRaises(StdioFailure):
                peer.exchange(wire(),lane='normal',timeout_ms=1000)
            self.assertEqual([e['method'] for e in self.events(directory)],['initialize'])
            pid=peer.status()['pid']
            with self.assertRaises(StdioFailure):peer.exchange(wire('again'),lane='normal',timeout_ms=20)
            self.assertEqual(peer.status()['pid'],pid);self.assertTrue(peer.status()['retired'])
            self.assertEqual(peer.status()['pending'],[])

    def test_hung_init_and_close_during_startup_keep_no_cancel_for_init(self):
        for close in (False,True):
            peer,directory=self.peer({'init_hang':True})
            worker,result=self.spawn(lambda:peer.exchange(wire(),lane='normal',timeout_ms=1500))
            self.assertTrue(wait_for(lambda:any(e['method']=='initialize' for e in self.events(directory))))
            if close:peer.close()
            worker.join(2)
            self.assertIsInstance(result['error'],StdioFailure)
            self.assertFalse(any(e['method'] in ('tools/call','notifications/cancelled') for e in self.events(directory)))
            self.assertTrue(peer.status()['retired'])

    def test_split_utf8_crlf_coalesced_controls_and_escaped_newline(self):
        expected='Unicode \u03bb / \u4e2d\u6587 / escaped\nline'
        for split,crlf in ((1,False),(7,True),(65536,False)):
            response={'jsonrpc':'2.0','id':'wire','result':{'content':[{'type':'text','text':expected}]}}
            frames=line({'jsonrpc':'2.0','method':'notifications/progress','params':{'progress':1}})+line(response)
            if crlf:frames=frames.replace(b'\n',b'\r\n')
            peer,_=self.peer({'fault':'raw','fault_tool':'identify','raw_b64':base64.b64encode(frames).decode(),'split':split,'crlf':crlf})
            self.assertEqual(peer.exchange(wire(),lane='normal',timeout_ms=2000),response)

    def test_invalid_framing_and_ambiguous_json_poison_without_partial_success(self):
        values=[b'\xff\n',b'\xef\xbb\xbf{}\n',b'hello\n',b'\n',b'Content-Length: 2\r\n\r\n{}',
                b'{"jsonrpc":"2.0","id":"wire","result":"literal\nline"}\n',
                b'{"jsonrpc":"2.0","id":"wire","result":1,"result":2}\n',
                b'{"jsonrpc":"2.0","id":"wire","result":NaN}\n',
                b'{"jsonrpc":"2.0","id":"wire","result":Infinity}\n',b'[]\n',b'1\n',
                b'{"jsonrpc":"2.0","id":"wire","result":{},"error":{}}\n',
                b'{"id":"wire","result":{}}\n',b'{}{}\n',b'{"jsonrpc":']
        for raw in values:
            peer,_=self.peer({'fault':'raw','fault_tool':'identify','raw_b64':base64.b64encode(raw).decode(),'raw_exit':True})
            with self.subTest(raw=raw[:80]),self.assertRaises(StdioFailure):peer.exchange(wire(),lane='normal',timeout_ms=800)
            self.assertTrue(peer.status()['fenced']);self.assertTrue(peer.status()['retired'])

    def test_exact_frame_cap_and_cap_plus_one(self):
        response={'jsonrpc':'2.0','id':'wire','result':{'value':'x'*400}}
        raw=line(response);cap=len(raw)-1
        for limit,success in ((cap,True),(cap-1,False)):
            peer,_=self.peer({'fault':'raw','fault_tool':'identify','raw_b64':base64.b64encode(raw).decode()},
                             StdioBudget(frame_bytes=limit,aggregate_bytes=4096))
            if success:self.assertEqual(peer.exchange(wire(),lane='normal',timeout_ms=1000),response)
            else:
                with self.assertRaises(StdioFailure):peer.exchange(wire(),lane='normal',timeout_ms=1000)
                self.assertIn('frame byte budget',peer.status()['reason'])

    def parser(self, frames, *, frame=1024*1024, aggregate=2*1024*1024, drip=False):
        # Actual pipe decoder with two deliberately unconsumed response owners.
        # No transport exchange consumes them; this exposes aggregate pressure.
        peer,_=self.peer(budget=StdioBudget(frame_bytes=frame,aggregate_bytes=aggregate))
        peer._state='READY'
        for ident in ('one','two'):
            peer._requests[ident]=_Request(ident,'normal',{},time.monotonic()+2,sent=True)
        read_fd,write_fd=os.pipe();stream=os.fdopen(read_fd,'rb',buffering=0);os.set_blocking(read_fd,False)
        def reader():
            try:peer._reader(stream)
            finally:stream.close()
        worker,result=self.spawn(reader)
        try:
            for index,frame_data in enumerate(frames):
                offset=0
                while offset<len(frame_data):offset+=os.write(write_fd,frame_data[offset:])
                if drip and index<2:self.assertTrue(wait_for(lambda:peer._requests[('one','two')[index]].done))
        finally:os.close(write_fd)
        worker.join(2);self.assertFalse(worker.is_alive())
        return peer,result

    def test_aggregate_two_completed_responses_plus_partial_share_one_budget(self):
        a=line({'jsonrpc':'2.0','id':'one','result':{'text':'a'*300}})
        b=line({'jsonrpc':'2.0','id':'two','result':{'text':'b'*300}})
        peer,result=self.parser([a+b],frame=512,aggregate=1024)
        self.assertTrue(peer._requests['one'].done and peer._requests['two'].done)
        self.assertEqual(peer._requests['two'].response['result']['text'],'b'*300)
        self.assertIn('EOF',str(result['error']))
        peer,result=self.parser([a,b,b' '*400],frame=512,aggregate=1024,drip=True)
        self.assertIn('aggregate',str(result['error']))
        self.assertLessEqual(peer.status()['peak_bytes'],1024)

    def test_decoded_shape_limits_independent_of_frame_size(self):
        for value in ([0]*65537,[[0]*65536]*5,[[[[[[[[[[[[[[[[[0]]]]]]]]]]]]]]]]],9007199254740992):
            peer,result=self.parser([line({'jsonrpc':'2.0','id':'one','result':value})])
            self.assertFalse(peer._requests['one'].done)
            self.assertNotIn('EOF',str(result['error']))
        peer,result=self.parser([line({'jsonrpc':'2.0','id':'one','result':{'array':[0]*65536,'exact':9007199254740991}})])
        self.assertTrue(peer._requests['one'].done)

    def test_typed_unknown_duplicate_ids_and_nonreuse(self):
        for fault in ('wrong_id','numeric_id','bool_id','duplicate'):
            peer,_=self.peer({'fault':fault,'fault_tool':'identify'})
            try:result=peer.exchange(wire(),lane='normal',timeout_ms=1000)
            except StdioFailure:result=None
            self.assertTrue(wait_for(lambda:peer.status()['fenced']),fault)
            self.assertTrue(peer.wait_retired(2))
            # A first valid response may be historical success before duplicate
            # delivery. It never completes a second ID or preserves live health.
            if result is not None:self.assertEqual(result['id'],'wire')
        peer,_=self.peer();peer.exchange(wire(),lane='normal',timeout_ms=1000)
        with self.assertRaisesRegex(StdioFailure,'identity'):peer.exchange(wire(),lane='normal',timeout_ms=1000)

    def test_lifetime_ledger_reserves_final_protective_work(self):
        peer,_=self.peer(budget=StdioBudget(ledger_ids=8))
        peer.exchange(wire('first'),lane='normal',timeout_ms=1000)
        peer.exchange(wire('second'),lane='normal',timeout_ms=1000)
        with self.assertRaisesRegex(StdioFailure,'identity budget'):peer.exchange(wire('third'),lane='normal',timeout_ms=1000)
        for number in range(4):
            self.assertEqual(peer.exchange(wire('protect'+str(number),'run_control',{'action':'stop'}),lane='protective',timeout_ms=1000)['id'],'protect'+str(number))
        self.assertEqual(peer.status()['issued_ids'],7)
        with self.assertRaises(StdioFailure):peer.exchange(wire('exhausted'),lane='protective',timeout_ms=1000)

    def test_protocol_and_tool_errors_retain_complete_bounded_evidence(self):
        for fault in ('rpc_error','is_error'):
            peer,_=self.peer({'fault':fault,'fault_tool':'identify'})
            with self.assertRaises(StdioFailure):peer.exchange(wire(),lane='normal',timeout_ms=1000)
            error=peer.status()['failure_response'];self.assertEqual(error['id'],'wire')
            if fault=='rpc_error':self.assertEqual(error['error'],{'code':-32000,'message':'controlled failure','data':{'complete':'error detail'}})
            else:self.assertIs(error['result']['isError'],True)
            error.clear();self.assertEqual(peer.status()['failure_response']['id'],'wire')
            self.assertTrue(peer.status()['fenced'])

    def test_stderr_flood_is_drained_bounded_and_not_protocol(self):
        peer,_=self.peer({'stderr_bytes':1024*1024})
        self.assertEqual(peer.exchange(wire(),lane='normal',timeout_ms=1500)['id'],'wire')
        self.assertTrue(wait_for(lambda:peer.status()['stderr_retained']+peer.status()['stderr_discarded']==1024*1024))
        self.assertEqual(peer.status()['stderr_retained'],65536)
        self.assertEqual(peer.status()['stderr_discarded'],1024*1024-65536)
        self.assertFalse(peer.status()['fenced'])

    def test_control_authority_ping_and_list_changed(self):
        controls=[{'jsonrpc':'2.0','id':'server-ping','method':'ping'},
                  {'jsonrpc':'2.0','id':2,'method':'sampling/createMessage','params':{'path':'/not/read','url':'http://not-used.invalid'}},
                  {'jsonrpc':'2.0','method':'notifications/progress','params':{'progress':1}}]
        peer,directory=self.peer({'controls':controls})
        self.assertEqual(peer.exchange(wire(),lane='normal',timeout_ms=1000)['id'],'wire')
        self.assertTrue(wait_for(lambda:len([e for e in self.events(directory) if 'response_id' in e])==2))
        self.assertEqual([e['response_id'] for e in self.events(directory) if 'response_id' in e],['server-ping',2])
        replies=[e['response'] for e in self.events(directory) if 'response_id' in e]
        self.assertEqual(replies[0],{'jsonrpc':'2.0','id':'server-ping','result':{}})
        self.assertEqual(replies[1]['error']['code'],-32601)
        peer,_=self.peer({'controls':[{'jsonrpc':'2.0','method':'notifications/tools/list_changed'}]})
        with self.assertRaises(StdioFailure):peer.exchange(wire(),lane='normal',timeout_ms=1000)
        self.assertIn('discovery changed',peer.status()['reason'])

    def test_progress_limits_and_fixed_deadline(self):
        peer,_=self.peer({'progress_count':8})
        self.assertEqual(peer.exchange(wire(),lane='normal',timeout_ms=1000)['id'],'wire')
        for budget in (StdioBudget(control_rate=4),StdioBudget(controls_per_request=4)):
            peer,_=self.peer({'progress_count':10},budget)
            with self.assertRaises(StdioFailure):peer.exchange(wire(),lane='normal',timeout_ms=1000)
            self.assertIn('control',peer.status()['reason'])
        peer,directory=self.peer({'hold_tool':'identify','progress_while_held':True})
        peer.exchange(wire('warm','get_status'),lane='normal',timeout_ms=2000)
        self.assertTrue((directory/'initialized').exists())
        started=time.monotonic()
        with self.assertRaises(StdioFailure):peer.exchange(wire(),lane='normal',timeout_ms=180)
        self.assertLess(time.monotonic()-started,1.5)
        self.assertIn('deadline',peer.status()['reason'])
        self.assertTrue((directory/'held-identify').exists())

    def test_partial_write_fences_without_inserting_cancellation_into_frame(self):
        peer,directory=self.peer({'ignore_stdin':True})
        # Warm initialize only: a tool then fills a blocked pipe. Large bounded
        # input is transport test data, not a declared Rigol tool argument.
        data=wire('large','identify',{'padding':'x'*60000})
        original=os.write;partial=[False]
        def blocked(fd,data):
            if threading.current_thread().name=='mhs-owned-stdio-writer':
                if partial[0]:raise BlockingIOError('controlled pipe pressure')
                if b'"id":"large"' in data:
                    partial[0]=True;return original(fd,data[:128])
            return original(fd,data)
        with patch('os.write',blocked),self.assertRaises(StdioFailure):peer.exchange(data,lane='normal',timeout_ms=1000)
        self.assertTrue(partial[0])
        self.assertIn('partial frame write',peer.status()['reason'])
        trace=peer.status()['trace']
        self.assertFalse(any(e.get('kind')=='cancel' for e in trace))
        self.assertFalse(any(e.get('method')=='tools/call' for e in self.events(directory)))

    def test_large_result_parse_does_not_own_protective_writer(self):
        peer,directory=self.peer({'fault':'frame_text','fault_tool':'identify','text_bytes':500000,'stderr_bytes':200000})
        entered,release=threading.Event(),threading.Event()
        from mhs.bridge import mcp_stdio
        original=mcp_stdio.plain
        def pause(value,*args,**kwargs):
            if threading.current_thread().name=='mhs-owned-stdio-stdout' and isinstance(value,dict) and value.get('id')=='large':
                entered.set();release.wait(2)
            return original(value,*args,**kwargs)
        with patch.object(mcp_stdio,'plain',pause):
            one,result=self.spawn(lambda:peer.exchange(wire('large'),lane='normal',timeout_ms=1500))
            self.assertTrue(entered.wait(1))
            two,stopped=self.spawn(lambda:peer.exchange(wire('protect','run_control',{'action':'stop'}),lane='protective',timeout_ms=1200))
            try:self.assertTrue(wait_for(lambda:any(e.get('id')=='protect' for e in self.events(directory)),.4))
            finally:release.set();one.join(2);two.join(2)
        self.assertEqual(len(result['value']['result']['content'][0]['text']),500000)
        self.assertEqual(stopped['value']['id'],'protect')


class StdioOwnershipTests(OwnedPeerCase):
    def healthy(self,plan=None,timeout=1500,budget=None):
        bridge,peer,directory=self.bridge(plan,timeout,budget)
        self.assertTrue(self.call(bridge)['text'])
        return bridge,peer,directory

    def test_cancelled_before_issue_and_cancel_once_after_issue(self):
        bridge,peer,directory=self.bridge()
        cancel=threading.Event();cancel.set()
        with self.assertRaises(Exception):self.call(bridge,cancel_event=cancel)
        self.assertIsNone(peer.status()['pid'])
        bridge,peer,directory=self.healthy({'hold_tool':'run_control','hold_action':'run','cancel_response':True,'ignore_term':True})
        # Explicit observation fault keeps software ownership after the process
        # has been killed, so the caller cannot conflate notification with exit.
        release=threading.Event();original=peer._retirement_observed
        with patch.object(peer,'_retirement_observed',lambda:release.is_set() and original()):
            cancel=threading.Event()
            worker,result=self.spawn(lambda:self.call(bridge,'run_control',{'action':'run'},cancel_event=cancel))
            self.assertTrue(wait_for(lambda:(directory/'held-run_control').exists()))
            ident=(directory/'held-run_control').read_text();cancel.set();worker.join(2)
            try:
                self.assertIsInstance(result['error'],signals.OutcomeUnknown)
                self.assertIn(ident,bridge._pending)
                self.assertIn(ident,peer.status()['pending'])
                self.assertFalse(peer.status()['retired'])
                self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
                self.assertTrue(wait_for(lambda:peer.status()['state']=='RETIREMENT_UNCONFIRMED'))
                notifications=[e for e in self.events(directory) if e['method']=='notifications/cancelled']
                self.assertEqual(len(notifications),1);self.assertEqual(notifications[0]['params']['requestId'],ident)
            finally:release.set()
        self.assertTrue(peer.wait_retired(2));self.assertTrue(wait_for(lambda:not bridge._pending))
        self.assertTrue(bridge.safety_status()['remote_uncertain'])
        with self.assertRaises(Exception):bridge.reset()

    def test_local_deadline_retains_owner_then_terminal_cleanup_never_replays(self):
        bridge,peer,directory=self.healthy({'hold_tool':'run_control','hold_action':'run'})
        self.assertTrue((directory/'initialized').exists())
        release=threading.Event();original=peer._retirement_observed
        with patch.object(peer,'_retirement_observed',lambda:release.is_set() and original()):
            with self.assertRaises(signals.OutcomeUnknown):self.call(bridge,'run_control',{'action':'run'},deadline_ms=180)
            self.assertTrue((directory/'held-run_control').exists())
            self.assertEqual(len(bridge._pending),1)
            before=len(self.events(directory))
            with self.assertRaises(Exception):self.call(bridge,'run_control',{'action':'run'})
            self.assertFalse(bridge.estop()['safe_state_achieved'])
            self.assertGreaterEqual(len(self.events(directory)),before)
            release.set()
        self.assertTrue(peer.wait_retired(2));self.assertTrue(wait_for(lambda:not bridge._pending))
        runs=[e for e in self.events(directory) if e.get('tool')=='run_control' and e.get('arguments',{}).get('action')=='run']
        self.assertEqual(len(runs),1);self.assertTrue(bridge.safety_status()['remote_uncertain'])

    def test_idle_exit_and_eof_revoke_cached_proof(self):
        for marker in ('exit-now','eof-now'):
            bridge,peer,directory=self.healthy()
            self.assertTrue(bridge.estop()['safe_state_achieved'])
            self.assertTrue(bridge.safety_status()['safe_state']['achieved'])
            (directory/marker).touch()
            self.assertTrue(peer.wait_retired(2))
            status=bridge.safety_status();self.assertFalse(status['safe_state']['achieved']);self.assertTrue(status['remote_uncertain'])
            with self.assertRaises(Exception):bridge.reset()
            self.assertTrue(bridge._latched)

    def test_noneffectful_failure_and_native_envelope_do_not_preserve_proof(self):
        for fault in ('rpc_error','text_error','dual_text'):
            bridge,peer,directory=self.healthy({'fault':fault,'fault_tool':'identify','fault_after_marker':True})
            self.assertTrue(bridge.estop()['safe_state_achieved'])
            self.assertTrue(self.call(bridge)['text'])
            self.assertTrue(bridge.safety_status()['safe_state']['achieved'])
            (directory/'fault-now').touch()
            with self.assertRaises(Exception):self.call(bridge)
            self.assertTrue(peer.wait_retired(2));self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
            self.assertTrue(bridge.safety_status()['remote_uncertain'])

    def test_discovery_native_mismatch_and_pagination_are_still_refused(self):
        for plan in ({'source_discovery':True},{'discovery_fault':'extra'},{'discovery_fault':'cursor'},{'discovery_fault':'schema'}):
            bridge,peer,directory=self.bridge(plan)
            with self.subTest(plan=plan),self.assertRaises(Exception):self.call(bridge,'run_control',{'action':'run'})
            self.assertTrue(peer.wait_retired(2))
            self.assertFalse(any(e.get('method')=='tools/call' for e in self.events(directory)))

    def test_stop_commit_and_reset_commit_revalidate_owner_epoch(self):
        bridge,peer,directory=self.healthy()
        original=bridge._exchange
        def terminal_before_commit(tool,*args,**kwargs):
            result=original(tool,*args,**kwargs)
            if tool=='get_status' and kwargs.get('protective'):
                (directory/'exit-now').touch();self.assertTrue(peer.wait_retired(2))
            return result
        with patch.object(bridge,'_exchange',terminal_before_commit):
            self.assertFalse(bridge.estop()['safe_state_achieved'])
        bridge,peer,directory=self.healthy();self.assertTrue(bridge.estop()['safe_state_achieved'])
        original_stop=bridge._stop
        def terminal_after_proof(*args,**kwargs):
            result=original_stop(*args,**kwargs)
            self.assertTrue(result['safe_state_achieved'])
            (directory/'exit-now').touch();self.assertTrue(peer.wait_retired(2));return result
        with patch.object(bridge,'_stop',terminal_after_proof):
            with self.assertRaises(Exception):bridge.reset()
        self.assertTrue(bridge._latched);self.assertFalse(bridge.safety_status()['safe_state']['achieved'])

    def test_older_effect_fresh_stop_and_later_observation_are_truthful(self):
        bridge,peer,directory=self.healthy({'hold_tool':'run_control','hold_action':'run','hold_response_tool':'get_status'})
        worker,normal=self.spawn(lambda:self.call(bridge,'run_control',{'action':'run'}))
        self.assertTrue(wait_for(lambda:(directory/'held-run_control').exists()))
        stopper,stopped=self.spawn(bridge.estop)
        self.assertTrue(wait_for(lambda:(directory/'response-held').exists()))
        self.assertTrue(any(e.get('tool')=='run_control' and e.get('arguments',{}).get('action')=='stop' for e in self.events(directory)))
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        (directory/'release-run_control').touch();worker.join(2)
        self.assertEqual(json.loads((directory/'state.json').read_text())['trigger_status'],'RUN')
        (directory/'release-response').touch();stopper.join(2)
        self.assertTrue(stopped['value']['safe_state_achieved'],stopped)
        self.assertIsInstance(normal['error'],signals.Cancelled)
        stops=[e for e in self.events(directory) if e.get('tool')=='run_control' and e.get('arguments',{}).get('action')=='stop']
        self.assertEqual(len(stops),2)
        history=copy.deepcopy(stopped['value']);self.assertTrue(bridge.reset()['reset'])
        (directory/'exit-now').touch();self.assertTrue(peer.wait_retired(2))
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        self.assertEqual(stopped['value'],history)

    def test_close_pending_is_nonblocking_and_autonomous(self):
        bridge,peer,directory=self.healthy({'hold_tool':'run_control','hold_action':'run'})
        worker,result=self.spawn(lambda:self.call(bridge,'run_control',{'action':'run'}))
        self.assertTrue(wait_for(lambda:(directory/'held-run_control').exists()))
        before=time.monotonic();bridge.close();self.assertLess(time.monotonic()-before,.15)
        self.assertTrue(bridge._close_done.wait(3));worker.join(2)
        self.assertTrue(peer.status()['retired']);self.assertTrue(result.get('error'))
        self.assertFalse(bridge.safety_status()['safe_state']['achieved']);bridge.close()

    def test_startup_and_cleanup_thread_failures_keep_real_owner(self):
        original=threading.Thread.start
        for target in ('mhs-mcp-normal','mhs-owned-stdio-supervisor','mhs-owned-stdio-stdout','mhs-mcp-close'):
            for after in (False,True):
                bridge,peer,directory=self.bridge()
                if target=='mhs-mcp-close':self.assertTrue(self.call(bridge)['text'])
                def broken(worker):
                    if worker.name==target:
                        if after:original(worker)
                        raise RuntimeError('injected startup boundary')
                    return original(worker)
                with self.subTest(target=target,after=after),patch.object(threading.Thread,'start',broken):
                    if target=='mhs-mcp-close':bridge.close()
                    else:
                        with self.assertRaises(Exception):self.call(bridge)
                bridge.close()
                self.assertTrue(peer.wait_retired(3),peer.status())
                self.assertTrue(bridge._close_done.wait(3))
                self.assertEqual(bridge._pending,{})
                self.assertFalse(bridge.safety_status()['safe_state']['achieved'])

    def test_spawn_descriptor_failure_and_close_race(self):
        from mhs.bridge import mcp_stdio
        for kind in ('popen','descriptor'):
            peer,_=self.peer()
            target=patch.object(mcp_stdio.subprocess,'Popen',side_effect=OSError('spawn refused')) if kind=='popen' else patch.object(mcp_stdio.os,'set_blocking',side_effect=OSError('descriptor setup refused'))
            with target,self.assertRaises(StdioFailure):peer.exchange(wire(),lane='normal',timeout_ms=1000)
            self.assertTrue(peer.status()['retired'])
            if peer._process is not None:self.assertIsNotNone(peer._process.poll())
        peer,_=self.peer();entered,release=threading.Event(),threading.Event();original=peer._peer_source
        def held():entered.set();release.wait(2);return original()
        with patch.object(peer,'_peer_source',held):
            worker,result=self.spawn(lambda:peer.exchange(wire(),lane='normal',timeout_ms=1000))
            self.assertTrue(entered.wait(1));peer.close();release.set();worker.join(2)
        self.assertIsNone(peer.status()['pid']);self.assertTrue(peer.status()['retired'])

    def test_start_ack_failure_before_transport_registration_still_retires(self):
        bridge,peer,directory=self.bridge()
        entered,release=threading.Event(),threading.Event()
        real_exchange=peer.exchange;start=threading.Thread.start
        def delayed(*args,**kwargs):
            entered.set();release.wait(2);return real_exchange(*args,**kwargs)
        def partial(worker):
            result=start(worker)
            if worker.name=='mhs-mcp-normal':
                self.assertTrue(entered.wait(1));raise RuntimeError('after actual start before peer registration')
            return result
        try:
            with patch.object(peer,'exchange',delayed),patch.object(threading.Thread,'start',partial):
                with self.assertRaises(signals.OutcomeUnknown):self.call(bridge)
                self.assertTrue(peer.status()['retired']);self.assertIsNone(peer.status()['pid'])
                self.assertEqual(len(bridge._pending),1)
                release.set();self.assertTrue(wait_for(lambda:not bridge._pending))
        finally:release.set()
        self.assertFalse((directory/'peer-pid').exists());self.assertFalse(bridge.safety_status()['safe_state']['achieved'])

    def test_health_notification_exception_does_not_strand_retirement(self):
        peer,directory=self.peer()
        peer.attach(lambda:(_ for _ in ()).throw(RuntimeError('injected listener failure')))
        self.assertEqual(peer.exchange(wire(),lane='normal',timeout_ms=1500)['id'],'wire')
        (directory/'exit-now').touch();self.assertTrue(peer.wait_retired(2))
        self.assertTrue(any(e['direction']=='health_callback_error' for e in peer.status()['trace']))
        with peer.ownership_guard() as token:self.assertIsNone(token)

    def test_handshake_budget_and_abandon_before_process_issue(self):
        peer,directory=self.peer(budget=StdioBudget(handshake_bytes=100))
        with self.assertRaises(StdioFailure):peer.exchange(wire(),lane='normal',timeout_ms=1500)
        self.assertFalse(any(e['method']=='tools/call' for e in self.events(directory)))
        peer,directory=self.peer();peer.abandon('unissued')
        self.assertTrue(peer.wait_retired(.1));self.assertIsNone(peer.status()['pid'])
        with self.assertRaises(StdioFailure):peer.exchange(wire(),lane='normal',timeout_ms=100)
        self.assertEqual(self.events(directory),[])

    def test_early_leader_exit_retires_real_descendant_and_pipe_owners(self):
        peer,directory=self.peer({'descendant':True})
        self.assertEqual(peer.exchange(wire(),lane='normal',timeout_ms=1000)['id'],'wire')
        self.assertTrue(wait_for(lambda:(directory/'descendant-pid').exists()))
        descendant=int((directory/'descendant-pid').read_text());parent=peer.status()['pid']
        (directory/'exit-now').touch();self.assertTrue(peer.wait_retired(3),peer.status())
        self.assertTrue((directory/'descendant-closed').exists())
        for pid in (parent,descendant):
            with self.assertRaises(ProcessLookupError):os.kill(pid,0)
        self.assertTrue(all(done.is_set() and stream.closed for _,done,stream in peer._workers))

    def test_caller_managed_signal_deferral_while_host_remains_alive(self):
        # Deliberately NOT default SIGTERM/SIGKILL/crash survival. This caller
        # installs and owns the deferring policy; the transport changes none.
        for signum in (signal.SIGINT,signal.SIGTERM):
            for stage in ('active','term','kill'):
                received=[];previous=signal.getsignal(signum)
                handler=lambda number,_frame:received.append(number)
                signal.signal(signum,handler)
                peer,directory=self.peer({'hold_tool':'identify','ignore_term':True,'ignore_eof':True})
                original=os.killpg;sent=[False]
                def interrupt_group(pid,number):
                    if not sent[0] and ((stage=='term' and number==signal.SIGTERM) or (stage=='kill' and number==signal.SIGKILL)):
                        sent[0]=True;os.kill(os.getpid(),signum)
                    return original(pid,number)
                try:
                    worker,result=self.spawn(lambda:peer.exchange(wire(),lane='normal',timeout_ms=1500))
                    self.assertTrue(wait_for(lambda:(directory/'held-identify').exists()))
                    with patch('os.killpg',interrupt_group):
                        if stage=='active':os.kill(os.getpid(),signum)
                        peer.close();self.assertTrue(peer.wait_retired(3))
                    worker.join(2);self.assertEqual(received,[signum])
                    self.assertIs(signal.getsignal(signum),handler)
                    self.assertTrue(all(stream.closed for _,_,stream in peer._workers))
                    self.assertTrue(peer.status()['fenced'])
                finally:signal.signal(signum,previous)
                self.assertIs(signal.getsignal(signum),previous)


if __name__=='__main__':unittest.main()
