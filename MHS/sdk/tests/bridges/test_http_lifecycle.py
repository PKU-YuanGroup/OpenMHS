"""Adversarial retirement, cooperative cancellation and local admission failures."""
import inspect
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from mhs.bridge.http import HttpBridge
from mhs.bridge.base import BridgeOutcomeUnknown
from mhs.errors import MHSError
from tests.bridges.test_http import FakeOT2
from tests.driver.test_http import FIXTURE, compiled, fixture
from tests import test_http_artifacts as http_artifact_tests


class ProofBoundary:
    """Pause only after a real successful proof releases its condition lock."""
    def __init__(self, condition):
        self.condition = condition
        self.entered = threading.Event()
        self.release = threading.Event()
        self.used = False

    def __getattr__(self, name):
        return getattr(self.condition, name)

    def __enter__(self):
        return self.condition.__enter__()

    def __exit__(self, *args):
        frame = inspect.currentframe().f_back
        selected = (frame.f_code is HttpBridge._stop.__code__
                    and frame.f_locals.get('achieved') is True and not self.used)
        del frame
        result = self.condition.__exit__(*args)
        if selected:
            self.used = True
            self.entered.set()
            if not self.release.wait(2):
                raise AssertionError('controlled proof-boundary deadline')
        return result


class HttpLifecycleTests(unittest.TestCase):
    def bridge(self, peer, **settings):
        config = compiled()
        config.update(settings)
        bridge = HttpBridge(config, transport=peer, base_dir=FIXTURE)
        self.addCleanup(bridge.close)
        return bridge

    def background(self, call):
        result = {}
        done = threading.Event()

        def execute():
            try:
                result['value'] = call()
            except BaseException as error:
                result['error'] = error
            finally:
                done.set()

        worker = threading.Thread(target=execute, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 2)
        return result, done

    def stale_stop(self, late_error):
        peer = FakeOT2(auto_complete=False)
        peer.late_play_after_stop = True
        play_entered, play_release = peer.block('play')
        list_entered, list_release = threading.Event(), threading.Event()
        list_calls = []

        def hold_first_list(raw, message):
            list_calls.append(raw)
            if len(list_calls) == 1:
                list_entered.set()
                self.assertTrue(list_release.wait(2))
            return raw

        peer.mutators['list'] = hold_first_list
        if late_error:
            def lost_response(raw, message):
                raise RuntimeError('controlled response loss after late play')
            peer.mutators['play'] = lost_response
        bridge = self.bridge(peer, request_timeout_ms=1500, workflow_timeout_ms=5000)
        run, run_done = self.background(lambda: bridge.call(fixture.RUN, {'protocol': 'controlled_protocol'}))
        self.addCleanup(play_release.set)
        self.addCleanup(list_release.set)
        self.assertTrue(play_entered.wait(1))
        stop, stop_done = self.background(bridge.estop)
        self.assertTrue(list_entered.wait(1))
        self.assertEqual(peer.runs['run-1']['status'], 'stopped')
        play_release.set()
        with bridge._condition:
            self.assertTrue(bridge._condition.wait_for(
                lambda: not any(item.lane == 'normal' for item in bridge._pending.values()), timeout=1))
        self.assertEqual(peer.runs['run-1']['status'], 'running')
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        list_release.set()
        self.assertTrue(stop_done.wait(1), stop)
        self.assertTrue(run_done.wait(1), run)
        self.assertTrue(stop['value']['safe_state_achieved'], stop)
        self.assertEqual(peer.runs['run-1']['status'], 'stopped')
        self.assertTrue(bridge.safety_status()['safe_state']['achieved'])
        self.assertFalse(bridge.safety_status()['remote_uncertain'])
        roles = [peer.role(item) for item in peer.requests]
        self.assertEqual(roles.count('stop'), 2, roles)
        self.assertEqual(roles.count('list'), 2, roles)
        self.assertEqual([role for role in roles if role in ('upload', 'create', 'play')],
                         ['upload', 'create', 'play'], 'normal effects must never be replayed')

    def test_late_success_invalidates_stale_stopped_status_and_list(self):
        self.stale_stop(False)

    def test_late_effect_then_error_cannot_have_debt_erased_by_stale_stop(self):
        self.stale_stop(True)

    def test_operation_cancel_retires_owned_run_before_cancelled_receipt(self):
        control = http_artifact_tests.HttpStockTests()
        self.addCleanup(control.doCleanups)
        peer, driver, _, _, client, device = control.make(options={'auto_complete': False})
        running = control.run_protocol(client, device, deadline_ms=20)
        self.assertIn(running['status'], ('accepted', 'running'))
        self.assertTrue(peer.started.wait(1))
        receipt = client.cancel(running['operation_id'], deadline_ms=1000)
        self.assertEqual(receipt['status'], 'cancelled', receipt)
        self.assertEqual(client.get_operation(running['operation_id'])['status'], 'cancelled')
        self.assertEqual(peer.runs['run-1']['status'], 'stopped')
        self.assertTrue(driver.safety_status()['safe_state']['achieved'])
        self.assertIn('stop', [peer.role(item) for item in peer.requests])

    def test_cancel_during_retained_play_stays_unknown_until_later_stop(self):
        peer = FakeOT2(auto_complete=False)
        peer.late_play_after_stop = True
        entered, release = peer.block('play')
        cancelled = threading.Event()
        bridge = self.bridge(peer, request_timeout_ms=100, workflow_timeout_ms=2000)
        run, done = self.background(lambda: bridge.call(
            fixture.RUN, {'protocol': 'controlled_protocol'}, ctx={'cancel_event': cancelled, 'deadline_ms': 2000}))
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(1))
        started = time.monotonic()
        cancelled.set()
        self.assertTrue(done.wait(.5), run)
        self.assertLess(time.monotonic() - started, .5)
        self.assertIsInstance(run.get('error'), BridgeOutcomeUnknown)
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        self.assertTrue(bridge.safety_status()['remote_uncertain'])
        self.assertIn('stop', [peer.role(item) for item in peer.requests])
        release.set()
        with bridge._condition:
            self.assertTrue(bridge._condition.wait_for(lambda: not bridge._pending, timeout=1))
        self.assertEqual(peer.runs['run-1']['status'], 'running')
        self.assertTrue(bridge.estop()['safe_state_achieved'])
        self.assertEqual(peer.runs['run-1']['status'], 'stopped')

    def test_cancel_before_known_run_id_does_not_invent_a_stop_target(self):
        peer = FakeOT2(auto_complete=False)
        entered, release = peer.block('upload')
        cancelled = threading.Event()
        bridge = self.bridge(peer, request_timeout_ms=100, workflow_timeout_ms=2000)
        run, done = self.background(lambda: bridge.call(
            fixture.RUN, {'protocol': 'controlled_protocol'}, ctx={'cancel_event': cancelled, 'deadline_ms': 2000}))
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(1))
        cancelled.set()
        self.assertTrue(done.wait(.5))
        self.assertIsInstance(run.get('error'), BridgeOutcomeUnknown)
        self.assertEqual([peer.role(item) for item in peer.requests], ['upload'])
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        release.set()
        with bridge._condition:
            self.assertTrue(bridge._condition.wait_for(lambda: not bridge._pending, timeout=1))
        self.assertIsNotNone(bridge._job['protocol_id'])
        self.assertIsNone(bridge._job['run_id'])
        with self.assertRaises(MHSError):
            bridge.reset()

    @unittest.skipUnless(hasattr(os, 'mkfifo') and hasattr(os, 'O_NONBLOCK'), 'POSIX FIFO control')
    def test_declared_fifo_is_rejected_without_a_writer_or_transport_request(self):
        with tempfile.TemporaryDirectory() as root:
            config = compiled()
            protocol = Path(root) / config['artifacts']['controlled_protocol']['path']
            protocol.parent.mkdir(parents=True, exist_ok=True)
            os.mkfifo(protocol)
            peer = FakeOT2()
            bridge = HttpBridge(config, transport=peer, base_dir=root)
            try:
                result, done = self.background(lambda: bridge.call(
                    fixture.RUN, {'protocol': 'controlled_protocol'}, ctx={'deadline_ms': 20}))
                if not done.wait(.2):
                    # Release only this test's FIFO to avoid a leaked reader
                    # when the negative baseline is intentionally exercised.
                    writer = os.open(protocol, os.O_WRONLY | os.O_NONBLOCK)
                    os.close(writer)
                    self.assertTrue(done.wait(1))
                    self.fail('FIFO input blocked before regular-file admission')
                self.assertIsInstance(result.get('error'), MHSError)
                self.assertEqual(peer.requests, [])
            finally:
                bridge.close()
                self.assertTrue(bridge._close_done.wait(1))

    def test_thread_failure_before_start_releases_request_and_owned_cleanup(self):
        peer = FakeOT2()
        bridge = self.bridge(peer)
        start = threading.Thread.start

        def fail(thread):
            if thread.name == 'mhs-http-normal':
                raise RuntimeError('controlled failure before worker start')
            return start(thread)

        with patch.object(threading.Thread, 'start', fail):
            with self.assertRaises(Exception):
                bridge.call(fixture.RUN, {'protocol': 'controlled_protocol'})
        self.assertEqual(peer.requests, [])
        self.assertEqual(bridge.safety_status()['pending_http'], 0)
        bridge.close()
        self.assertTrue(bridge._close_done.wait(1))
        self.assertEqual(peer.close_calls, 1)

    def test_thread_failure_after_real_start_retains_request_until_return(self):
        peer = FakeOT2()
        entered, release = peer.block('upload')
        bridge = self.bridge(peer)
        start = threading.Thread.start

        def fail(thread):
            result = start(thread)
            if thread.name == 'mhs-http-normal':
                raise RuntimeError('controlled failure after real worker start')
            return result

        with patch.object(threading.Thread, 'start', fail):
            with self.assertRaises(BridgeOutcomeUnknown):
                bridge.call(fixture.RUN, {'protocol': 'controlled_protocol'})
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(1))
        bridge.close()
        self.assertEqual(bridge.safety_status()['pending_http'], 1)
        self.assertFalse(bridge._close_done.is_set())
        self.assertEqual(peer.close_calls, 0)
        release.set()
        self.assertTrue(bridge._close_done.wait(1))
        self.assertEqual(bridge.safety_status()['pending_http'], 0)
        self.assertEqual(peer.close_calls, 1)
        self.assertEqual(bridge._job['protocol_id'], 'protocol-1')
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])

    def test_cleanup_failure_before_start_is_recorded_and_explicitly_retryable(self):
        peer = FakeOT2()
        bridge = self.bridge(peer)
        start = threading.Thread.start

        def fail(thread):
            if thread.name == 'mhs-http-close':
                raise RuntimeError('controlled cleanup failure before start')
            return start(thread)

        with patch.object(threading.Thread, 'start', fail):
            bridge.close()
        self.assertFalse(bridge._close_started)
        self.assertEqual(bridge._close_start_error, 'RuntimeError')
        self.assertFalse(bridge._close_done.is_set())
        self.assertEqual(peer.close_calls, 0)
        bridge.close()
        self.assertTrue(bridge._close_done.wait(1))
        bridge.close()
        self.assertEqual(peer.close_calls, 1)

    def test_cleanup_failure_after_start_retains_single_inflight_close(self):
        peer = FakeOT2()
        peer.close_release = threading.Event()
        self.addCleanup(peer.close_release.set)
        bridge = self.bridge(peer)
        start = threading.Thread.start

        def fail(thread):
            result = start(thread)
            if thread.name == 'mhs-http-close':
                raise RuntimeError('controlled cleanup acknowledgement failure')
            return result

        with patch.object(threading.Thread, 'start', fail):
            bridge.close()
        self.assertTrue(peer.close_entered.wait(1))
        self.assertTrue(bridge._close_started)
        self.assertEqual(bridge._close_start_error, 'RuntimeError')
        self.assertFalse(bridge._close_done.is_set())
        bridge.close()
        self.assertEqual(peer.close_calls, 0)
        peer.close_release.set()
        self.assertTrue(bridge._close_done.wait(1))
        bridge.close()
        self.assertEqual(peer.close_calls, 1)

    def test_stop_commit_does_not_erase_a_later_unsafe_observation(self):
        peer = FakeOT2()
        bridge = self.bridge(peer)
        bridge.call(fixture.RUN, {'protocol': 'controlled_protocol'})
        boundary = ProofBoundary(bridge._condition)
        bridge._condition = boundary
        result, done = self.background(bridge.estop)
        self.addCleanup(boundary.release.set)
        self.assertTrue(boundary.entered.wait(1))
        peer.auto_complete = False
        with peer._lock:
            peer.runs['run-1']['status'] = 'running'
        self.assertEqual(bridge.read('main', ['status']), {'status': 'running'})
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        boundary.release.set()
        self.assertTrue(done.wait(1), result)
        self.assertNotIn('error', result)
        # The stop receipt describes its earlier successful commit. The newer
        # observation must remain authoritative in current safety/ownership.
        self.assertTrue(result['value']['safe_state_achieved'])
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        self.assertTrue(bridge.safety_status()['remote_uncertain'])
        self.assertFalse(bridge._job['settled'])

    def test_reset_revalidates_a_new_unsafe_observation_before_latch_release(self):
        peer = FakeOT2()
        bridge = self.bridge(peer)
        bridge.call(fixture.RUN, {'protocol': 'controlled_protocol'})
        self.assertTrue(bridge.estop()['safe_state_achieved'])
        entered, release = threading.Event(), threading.Event()
        real_stop = bridge._stop

        def boundary(context, *, engage):
            result = real_stop(context, engage=engage)
            if not engage:
                entered.set()
                self.assertTrue(release.wait(2))
            return result

        bridge._stop = boundary
        result, done = self.background(bridge.reset)
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(1))
        peer.auto_complete = False
        with peer._lock:
            peer.runs['run-1']['status'] = 'running'
        self.assertEqual(bridge.read('main', ['status']), {'status': 'running'})
        release.set()
        self.assertTrue(done.wait(1), result)
        self.assertIsInstance(result.get('error'), MHSError)
        self.assertTrue(bridge._latched)
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        self.assertTrue(bridge.safety_status()['remote_uncertain'])

    def test_later_active_read_after_reset_retains_the_owned_run_without_new_effects(self):
        peer = FakeOT2()
        bridge = self.bridge(peer)
        bridge.call(fixture.RUN, {'protocol': 'controlled_protocol'})
        self.assertTrue(bridge.estop()['safe_state_achieved'])
        self.assertEqual(bridge.reset(), {'reset': True})
        self.assertFalse(bridge._latched)
        peer.auto_complete = False
        with peer._lock:
            peer.runs['run-1']['status'] = 'running'
        self.assertEqual(bridge.read('main', ['status']), {'status': 'running'})
        before = list(peer.requests)
        with self.assertRaises(MHSError):
            bridge.call(fixture.RUN, {'protocol': 'controlled_protocol'})
        self.assertEqual(peer.requests, before)
        self.assertEqual(bridge._job['run_id'], 'run-1')
        self.assertFalse(bridge._job['settled'])
        self.assertTrue(bridge.safety_status()['remote_uncertain'])
        self.assertTrue(bridge.estop()['safe_state_achieved'])
        self.assertEqual(bridge.reset(), {'reset': True})

    def test_reset_does_not_rearm_after_close_at_its_commit_boundary(self):
        peer = FakeOT2()
        bridge = self.bridge(peer)
        bridge.call(fixture.RUN, {'protocol': 'controlled_protocol'})
        self.assertTrue(bridge.estop()['safe_state_achieved'])
        real_stop = bridge._stop

        def boundary(context, *, engage):
            result = real_stop(context, engage=engage)
            if not engage:
                bridge.close()
            return result

        bridge._stop = boundary
        with self.assertRaises(MHSError):
            bridge.reset()
        self.assertTrue(bridge.closed)
        self.assertTrue(bridge._latched)
        self.assertFalse(bridge.safety_status()['safe_state']['achieved'])
        self.assertTrue(bridge._close_done.wait(1))
        self.assertEqual(peer.close_calls, 1)


if __name__ == '__main__':
    unittest.main()
