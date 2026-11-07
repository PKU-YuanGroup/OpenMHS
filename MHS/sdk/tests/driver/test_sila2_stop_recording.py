"""Only the finite Stop call is native-stop evidence, never proof or cleanup."""
import threading
import unittest
from unittest.mock import patch

from mhs.driver.check import _Context
from tests.driver.sila2_support import FIXTURE, fixture


def capture(*, resource='none', concurrent=False, noop=False):
    """Stock endpoint with peer-only resource faults and explicit no-op injection.

    The concurrent control holds the recorder's real act window on another
    thread. The existing stock G6 test separately runs a real pending command.
    """
    ctx = _Context(FIXTURE, 'fake', None, None, False)
    ep = None
    window_entered, window_release = threading.Event(), threading.Event()
    worker = None
    try:
        ep = ctx.endpoint(gate_case='safety', site_limits=ctx.example_overlay)
        driver = ep.server.devices[ep.device_id].bridge
        peer = object.__getattribute__(driver.inner._transport, '_mhs_target').peer
        dispatch = peer._dispatch
        initial = None
        if resource == 'binary':
            peer.chunked = True
            def interrupted(message):
                if message['operation'] == 'binary_chunk':
                    raise RuntimeError('controlled interrupted transfer')
                return dispatch(message)
            with patch.object(peer, '_dispatch', side_effect=interrupted):
                initial = ep.session.command(fixture.CAPS['DisplayIcon'], {})
            assert initial['status'] != 'completed', initial
            assert peer.binaries and any(w.binaries for w in driver.inner._works.values())
        elif resource == 'stream':
            def interrupted(message):
                reply = dispatch(message)
                if message['operation'] == 'next' and reply.get('payload', {}).get('end'):
                    reply['payload']['extra'] = 'controlled malformed terminal batch'
                return reply
            with patch.object(peer, '_dispatch', side_effect=interrupted):
                initial = ep.session.command(fixture.CAPS['RunAcquisitionProtocol'],
                                             fixture.EXAMPLES['RunAcquisitionProtocol'], test_permit=True)
            assert initial['status'] != 'completed', initial
            assert not peer.active and any(not s['closed'] for s in peer.streams.values())
        else:
            assert resource == 'none'
        assert driver.inner._normal is None
        retained_before = {'binaries': len(peer.binaries),
                           'streams': sum(not s['closed'] for s in peer.streams.values())}
        if noop:
            # A deliberately broken implementation is the negative control,
            # never production configuration or a changed gate oracle.
            driver.inner._invoke_stop = lambda work: None
        if concurrent:
            def hold_window():
                with ep.log.window('act'):
                    window_entered.set()
                    window_release.wait(2)
            worker = threading.Thread(target=hold_window, name='controlled-other-act-window')
            worker.start()
            assert window_entered.wait(1)
        mark = ep.log.mark()
        receipt = ep.session.estop()
        calls = [{'phase': c.phase, 'operation': c.args[0]['operation'], 'member': c.args[0]['member']}
                 for c in ep.log.since(mark) if c.kind == 'call' and c.name == 'request']
        reset_calls = []
        if not noop and receipt['status'] == 'completed':
            mark = ep.log.mark()
            reset = ep.session.reset()
            assert reset['result']['status'] == 'completed', reset
            reset_calls = [{'phase': c.phase, 'operation': c.args[0]['operation'], 'member': c.args[0]['member']}
                           for c in ep.log.since(mark) if c.kind == 'call' and c.name == 'request']
        return {'resource': resource, 'concurrent_act_window': concurrent, 'noop_stop': noop,
                'initial_status': initial['status'] if initial else None, 'retained_before': retained_before,
                'retained_after': {'binaries': len(peer.binaries),
                                   'streams': sum(not s['closed'] for s in peer.streams.values())},
                'receipt': receipt, 'calls': calls, 'reset_calls': reset_calls}
    finally:
        window_release.set()
        if worker is not None:
            worker.join(1)
            assert not worker.is_alive()
        if ep is not None:
            ep.close()
        ctx.close()


class SilaStopRecordingTests(unittest.TestCase):
    def assert_classified(self, row):
        stops = [c for c in row['calls'] if c['phase'] == 'estop']
        if row['noop_stop']:
            self.assertEqual(stops, [], row)
            self.assertFalse(any(c['operation'] == 'invoke' and c['member'] == 'Stop' for c in row['calls']))
        else:
            self.assertTrue(stops, row)
            self.assertTrue(all(c['operation'] == 'invoke' and c['member'] == 'Stop' for c in stops), row)
            self.assertEqual(row['receipt']['status'], 'completed', row)
        observations = [c for c in row['calls'] if c['operation'] == 'observe']
        self.assertTrue(observations, row)
        self.assertTrue(all(c['phase'] == 'read' for c in observations), row)
        cleanup = [c for c in row['calls'] if c['operation'] in ('binary_delete', 'unsubscribe')]
        if row['resource'] != 'none':
            self.assertTrue(cleanup, row)
            self.assertTrue(all(c['phase'] == 'act' for c in cleanup), row)
            self.assertEqual(row['retained_after'], {'binaries': 0, 'streams': 0}, row)
        self.assertFalse(any(c['phase'] == 'estop' for c in row['reset_calls']), row)

    def test_noop_quiescent_observation_is_not_stop_evidence(self):
        self.assert_classified(capture(noop=True))

    def test_noop_concurrent_window_observation_is_not_stop_evidence(self):
        self.assert_classified(capture(noop=True, concurrent=True))

    def test_noop_binary_cleanup_is_not_stop_evidence_in_both_schedules(self):
        for concurrent in (False, True):
            with self.subTest(concurrent=concurrent):
                self.assert_classified(capture(resource='binary', noop=True, concurrent=concurrent))

    def test_noop_stream_cleanup_is_not_stop_evidence_in_both_schedules(self):
        for concurrent in (False, True):
            with self.subTest(concurrent=concurrent):
                self.assert_classified(capture(resource='stream', noop=True, concurrent=concurrent))

    def test_real_stop_only_and_reset_read_remain_distinct_in_all_schedules(self):
        for resource in ('none', 'binary', 'stream'):
            for concurrent in (False, True):
                with self.subTest(resource=resource, concurrent=concurrent):
                    self.assert_classified(capture(resource=resource, concurrent=concurrent))

    def test_real_concurrent_stock_read_during_noop_stop_is_never_stop_evidence(self):
        ctx = _Context(FIXTURE, 'fake', None, None, False)
        self.addCleanup(ctx.close)
        ep = ctx.endpoint(gate_case='safety')
        self.addCleanup(ep.close)
        driver = ep.server.devices[ep.device_id].bridge
        peer = object.__getattribute__(driver.inner._transport, '_mhs_target').peer
        driver.inner._invoke_stop = lambda work: None
        entered, release = peer.block('before:observe')
        self.addCleanup(release.set)
        outcome = {}
        worker = threading.Thread(target=lambda: outcome.update(receipt=ep.session.estop()))
        mark = ep.log.mark()
        try:
            worker.start(); self.assertTrue(entered.wait(1))
            self.assertIsNotNone(driver.inner._protective)
            observed = ep.session.read()
            self.assertNotIn('error', observed)
            calls = [c for c in ep.log.since(mark) if c.kind == 'call' and c.name == 'request']
            self.assertTrue(any(c.args[0]['operation'] == 'property' for c in calls))
            self.assertTrue(all(c.phase == 'read' for c in calls), calls)
            self.assertEqual(ep.log.in_phase('estop', mark), [])
        finally:
            release.set(); worker.join(1)
        self.assertFalse(worker.is_alive())

    def test_ordinary_command_and_reset_cannot_inherit_another_stop_window(self):
        ctx = _Context(FIXTURE, 'fake', None, None, False)
        self.addCleanup(ctx.close)
        ep = ctx.endpoint(gate_case='safety', site_limits=ctx.example_overlay)
        self.addCleanup(ep.close)
        mark = ep.log.mark()
        with ep.log.window('estop'):
            receipt = ep.session.command(fixture.CAPS['GoIdle'], {}, test_permit=True)
        self.assertEqual(receipt['status'], 'completed', receipt)
        calls = [c for c in ep.log.since(mark) if c.kind == 'call' and c.name == 'request']
        invoked = [c for c in calls if c.args[0]['operation'] == 'invoke']
        self.assertTrue(invoked)
        self.assertTrue(all(c.phase == 'act' and c.args[0]['member'] == 'GoIdle' for c in invoked))
        self.assertEqual(ep.log.in_phase('estop', mark), [])
        self.assertEqual(ep.session.estop()['status'], 'completed')
        mark = ep.log.mark()
        with ep.log.window('estop'):
            self.assertEqual(ep.session.reset()['result']['status'], 'completed')
        self.assertEqual(ep.log.in_phase('estop', mark), [])


if __name__ == '__main__': unittest.main()
