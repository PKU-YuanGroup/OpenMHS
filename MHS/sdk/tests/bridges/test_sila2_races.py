"""Controlled schedules exercise production helper ownership without native imports."""
import copy
import threading
import time
import unittest
from unittest.mock import patch

from mhs.bridge.base import BridgeContext
from mhs.bridge.sila2 import PeerLease, Sila2Bridge
from mhs.bridge.sila2_replay import RecordingSila2Peer, Sila2ReplayPeer
from tests.driver.sila2_support import PhenixPeer, bridge, compiled, connect, fixture, until

RUN = fixture.CAPS['RunAcquisitionProtocol']
ARGS = fixture.EXAMPLES['RunAcquisitionProtocol']


class HookPeer(PhenixPeer):
    def __init__(self, **options):
        super().__init__(**options)
        self.hook = None
    def request(self, message, *, timeout_ms):
        reply = super().request(message, timeout_ms=timeout_ms)
        return self.hook(message, reply) if self.hook is not None else reply


def launch(function):
    results, errors = [], []
    def run():
        try: results.append(function())
        except BaseException as error: errors.append(error)
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, results, errors


class SilaRaceTests(unittest.TestCase):
    def test_stop_before_late_effect_success_and_error_requires_a_new_stop(self):
        for late_error in (False, True):
            peer = HookPeer(auto_complete=False)
            _, driver = bridge(self, peer, stop_timeout_ms=450)
            connect(driver)
            entered, release = peer.block('before:invoke:RunAcquisitionProtocol')
            if late_error:
                def hook(message, reply):
                    if message['operation'] == 'invoke' and message['member'] == 'RunAcquisitionProtocol':
                        raise RuntimeError('source-shaped effect then lost response')
                    return reply
                peer.hook = hook
            normal, _, failures = launch(lambda: driver.call(RUN, ARGS, BridgeContext(deadline_ms=35)))
            observed, release_observation = peer.block('after:observe')
            stop = None
            try:
                self.assertTrue(entered.wait(1)); normal.join(.2); self.assertTrue(failures)
                stop, results, errors = launch(driver.safe_state)
                self.assertTrue(observed.wait(1))
                self.assertFalse(peer.active, 'first stop observed no effect before delayed invocation')
                release.set(); until(self, lambda: driver._normal is None)
                self.assertTrue(peer.active)
                release_observation.set(); stop.join(1)
                self.assertFalse(errors)
                count = sum(r['operation'] == 'invoke' and r['member'] == 'Stop' for r in peer.requests)
                if results[0]['achieved']:
                    self.assertGreaterEqual(count, 2, 'old pre-effect observation cannot settle the late owner')
                    self.assertFalse(peer.active)
                self.assertTrue(driver.safe_state()['achieved'])
            finally:
                release.set(); release_observation.set(); normal.join(1)
                if stop is not None: stop.join(1)

    def test_unsafe_read_after_stop_observation_prevents_commit_and_reset(self):
        peer, driver = bridge(self); connect(driver)
        entered, release = peer.block('after:observe')
        worker, results, errors = launch(driver.safe_state)
        try:
            self.assertTrue(entered.wait(1))
            peer.device_state, peer.active = 'Operate', True
            self.assertEqual(driver.read('main', ['DeviceState'])['DeviceState'], 'Operate')
            peer.ack_only = True
            release.set(); worker.join(1)
            self.assertFalse(errors); self.assertFalse(results[0]['achieved'])
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            with self.assertRaises(Exception): driver.reset()
        finally: release.set(); worker.join(1)

    def test_reset_has_no_mutation_and_rejects_concurrent_read_or_close(self):
        for close in (False, True):
            peer, driver = bridge(self); connect(driver); self.assertTrue(driver.safe_state()['achieved'])
            entered, release = peer.block('after:observe')
            before = sum(r['operation'] == 'invoke' for r in peer.requests)
            worker, results, errors = launch(driver.reset)
            try:
                self.assertTrue(entered.wait(1))
                if close: driver.close()
                else:
                    peer.active, peer.device_state = True, 'Operate'
                    driver.read('main', ['DeviceState'])
                release.set(); worker.join(1)
                self.assertTrue(errors); self.assertFalse(results)
                self.assertFalse(driver.safety_status()['safe_state']['achieved'])
                self.assertEqual(before, sum(r['operation'] == 'invoke' for r in peer.requests))
            finally: release.set(); worker.join(1)

    def test_stop_timeout_retains_single_protective_owner(self):
        peer, driver = bridge(self, stop_timeout_ms=35); connect(driver)
        entered, release = peer.block('after:invoke:Stop')
        try:
            self.assertFalse(driver.safe_state()['achieved']); self.assertTrue(entered.is_set())
            old = driver._protective
            for _ in range(3): self.assertFalse(driver.safe_state()['achieved'])
            self.assertIs(driver._protective, old)
            self.assertEqual(sum(r['member'] == 'Stop' for r in peer.requests), 1)
            release.set(); until(self, old.event.is_set)
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            self.assertTrue(driver.safe_state()['achieved'])
        finally: release.set()

    def test_duplicate_typed_terminal_controls_and_sticky_fault_allow_protective_retry(self):
        for change in ('same', 'status', 'typed_progress'):
            peer = HookPeer(auto_complete=False)
            _, driver = bridge(self, peer); connect(driver)
            def hook(message, reply):
                if message['operation'] == 'next' and peer.streams[message['payload']['stream_id']]['kind'] == 'info':
                    ident = peer.streams[message['payload']['stream_id']]['execution_uuid']; peer.complete(ident)
                    item = reply['payload']['items'][0]; item.update(status=2, progress=1.0)
                    other = copy.deepcopy(item)
                    if change == 'status': other['status'] = 3
                    if change == 'typed_progress': other['progress'] = 1
                    reply['payload'].update(items=[item, other], end=True)
                return reply
            peer.hook = hook
            if change == 'same':
                self.assertIn('complete', driver.call(RUN, ARGS)['Status'])
                self.assertTrue(driver.safe_state()['achieved'])
            else:
                with self.assertRaises(Exception): driver.call(RUN, ARGS)
                self.assertTrue(driver._fault)
                before = sum(r['member'] == 'Stop' for r in peer.requests)
                self.assertFalse(driver.safe_state()['achieved'])
                self.assertGreater(sum(r['member'] == 'Stop' for r in peer.requests), before)
                with self.assertRaises(Exception): driver.reset()

    def test_foreign_confirmation_and_uuid_reuse_cannot_replace_owned_execution(self):
        peer = HookPeer(); _, driver = bridge(self, peer); connect(driver)
        driver.call(RUN, ARGS); old = next(iter(peer.jobs))
        def reused(message, reply):
            if message['operation'] == 'invoke' and message['member'] == 'RunAcquisitionProtocol':
                reply['payload']['execution_uuid'] = old
            return reply
        peer.hook = reused
        with self.assertRaises(Exception): driver.call(RUN, ARGS)
        self.assertTrue(peer.active); self.assertTrue(driver._fault)
        self.assertFalse(driver.safe_state()['achieved'])
        peer = HookPeer(); _, driver = bridge(self, peer); connect(driver)
        def foreign(message, reply):
            if message['operation'] == 'invoke': reply['owner_id'] = '00000000-0000-0000-0000-000000000000'
            return reply
        peer.hook = foreign
        with self.assertRaises(Exception): driver.call(RUN, ARGS)
        self.assertTrue(driver._fault); self.assertEqual(len(driver._owners), 2)

    def test_full_progress_without_result_and_expired_uuid_stay_unknown(self):
        for failure in ('transport', 'expired'):
            peer = HookPeer(); _, driver = bridge(self, peer); connect(driver)
            def hook(message, reply):
                if message['operation'] == 'result':
                    if failure == 'transport': raise ConnectionError('final response lost')
                    reply.pop('payload'); reply['error'] = {'kind': 'framework', 'identifier': 'INVALID_COMMAND_EXECUTION_UUID', 'message': 'expired'}
                return reply
            peer.hook = hook
            with self.assertRaises(Exception): driver.call(RUN, ARGS)
            owner = driver._latest['RunAcquisitionProtocol']
            self.assertEqual(owner.progress, 1.0); self.assertFalse(owner.retired)
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            self.assertTrue(driver.safe_state()['achieved'])

    def test_observable_property_owns_subscription_and_cannot_become_a_method(self):
        config = compiled(); config['members']['DeviceState']['kind'] = 'observable_property'
        peer = PhenixPeer(config=config)
        driver = Sila2Bridge(config, transport=PeerLease(peer=peer)); self.addCleanup(driver.close)
        connect(driver)
        self.assertEqual(driver.read('main', ['DeviceState']), {'DeviceState': 'Idle'})
        self.assertTrue(all(s['closed'] for s in peer.streams.values()))
        self.assertEqual([r['operation'] for r in peer.requests if r['member'] == 'DeviceState'], ['subscribe', 'next', 'unsubscribe'])

    def test_observation_stream_gap_overflow_and_early_end_retain_execution(self):
        for defect in ('gap', 'overflow', 'early_end'):
            peer = HookPeer(auto_complete=False); _, driver = bridge(self, peer); connect(driver)
            def hook(message, reply):
                if message['operation'] == 'next':
                    batch = reply['payload']
                    if defect == 'gap': batch['sequence'] += 1
                    elif defect == 'overflow': batch['items'] *= 17
                    else: batch['items'], batch['end'] = [], True
                return reply
            peer.hook = hook
            with self.assertRaises(Exception): driver.call(RUN, ARGS)
            self.assertTrue(peer.active)
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            self.assertTrue(driver.safe_state()['achieved'])


class SilaConstructionTests(unittest.TestCase):
    def test_partial_factory_timeout_and_exception_keep_registered_peer_owned(self):
        peer = PhenixPeer(); entered, release = threading.Event(), threading.Event()
        def factory(lease):
            lease.register(peer); entered.set(); release.wait(); raise RuntimeError('partial initialization failed')
        lease = PeerLease(factory)
        driver = Sila2Bridge(compiled(request_timeout_ms=35), transport=lease); self.addCleanup(driver.close)
        try:
            with self.assertRaises(Exception): connect(driver)
            self.assertTrue(entered.is_set()); self.assertIs(lease.peer, peer)
            with self.assertRaises(ValueError): PeerLease(peer=peer)
            start = time.monotonic(); driver.close(); self.assertLess(time.monotonic() - start, .1)
            self.assertFalse(peer.closed)
            release.set(); until(self, lambda: peer.closed)
            self.assertIsNotNone(lease.error)
            self.assertFalse(peer.requests)
        finally: release.set()

    def test_cleanup_error_retains_handle_and_close_stays_bounded(self):
        peer = PhenixPeer()
        def broken_close(): raise RuntimeError('cleanup failed')
        peer.close = broken_close
        lease = PeerLease(peer=peer); driver = Sila2Bridge(compiled(), transport=lease)
        connect(driver); driver.close(); until(self, lambda: driver._cleanup_error is not None)
        with self.assertRaises(ValueError): PeerLease(peer=peer)
        self.assertFalse(driver.safety_status()['safe_state']['achieved'])
        # The test itself owns this fake and explicitly repairs its close to
        # release the test registry entry; production did not discard it.
        peer.close = lambda: None; lease.close()

    def test_request_start_failure_before_and_after_real_start_retains_live_owner(self):
        original = threading.Thread.start
        for partial in (False, True):
            peer = PhenixPeer(); _, driver = bridge(self, peer)
            entered, release = peer.block('before:describe')
            def start(thread):
                if thread.name == 'mhs-sila2-normal':
                    if partial:
                        original(thread)
                        if not entered.wait(1): raise AssertionError('real worker did not enter owned RPC')
                    raise RuntimeError('controlled thread startup failure')
                return original(thread)
            try:
                with patch.object(threading.Thread, 'start', start):
                    with self.assertRaises(Exception): connect(driver)
                if partial:
                    self.assertTrue(entered.wait(1)); self.assertIsNotNone(driver._normal)
                else:
                    self.assertIsNone(driver._normal); self.assertFalse(peer.requests)
                driver.close(); release.set()
                if partial: until(self, lambda: driver._normal is None)
                self.assertFalse(any(r['operation'] == 'invoke' for r in peer.requests))
            finally: release.set(); driver.close()

    def test_close_during_delayed_thread_start_never_joins_unstarted_worker(self):
        original = threading.Thread.start
        peer, driver = bridge(self)
        entered, release = threading.Event(), threading.Event()
        def start(thread):
            if thread.name == 'mhs-sila2-normal': entered.set(); release.wait()
            return original(thread)
        worker = None
        try:
            with patch.object(threading.Thread, 'start', start):
                worker, _, errors = launch(lambda: connect(driver))
                self.assertTrue(entered.wait(1)); start_at = time.monotonic(); driver.close()
                self.assertLess(time.monotonic() - start_at, .1)
                release.set(); worker.join(1)
                self.assertTrue(errors); self.assertFalse(worker.is_alive())
            self.assertFalse(peer.requests)
        finally:
            release.set()
            if worker is not None: worker.join(1)

    def test_cleanup_worker_start_failure_never_constructs_peer(self):
        original = threading.Thread.start
        for partial in (False, True):
            constructed, workers = [], []
            def factory(lease):
                constructed.append(True); peer = PhenixPeer(); lease.register(peer); return peer
            lease = PeerLease(factory)
            def start(thread):
                if thread.name == 'mhs-sila2-close':
                    workers.append(thread)
                    if partial: original(thread)
                    raise RuntimeError('controlled cleanup startup failure')
                return original(thread)
            with patch.object(threading.Thread, 'start', start):
                with self.assertRaises(RuntimeError): Sila2Bridge(compiled(), transport=lease)
            self.assertEqual(constructed, [])
            if partial: until(self, lambda: not workers[0].is_alive())

    def test_close_before_admission_releases_injected_peer_without_describe(self):
        peer, driver = bridge(self)
        driver.close(); until(self, lambda: peer.closed)
        self.assertEqual(peer.requests, [])
        self.assertFalse(driver.safety_status()['safe_state']['achieved'])


class SilaReplayTests(unittest.TestCase):
    def recording(self):
        peer = PhenixPeer(); recorder = RecordingSila2Peer(peer)
        driver = Sila2Bridge(compiled(), transport=PeerLease(peer=recorder)); self.addCleanup(driver.close)
        connect(driver); driver.call(RUN, ARGS); driver.safe_state(); driver.reset()
        return recorder.records

    def test_exact_complete_workflow_rebinds_local_only(self):
        records = self.recording(); peer = Sila2ReplayPeer(records)
        driver = Sila2Bridge(compiled(), transport=PeerLease(peer=peer)); self.addCleanup(driver.close)
        connect(driver); driver.call(RUN, ARGS); self.assertTrue(driver.safe_state()['achieved']); driver.reset()
        self.assertTrue(peer.consumed)
        recorded = next(row['response']['payload']['execution_uuid'] for row in records
                        if row['request']['operation'] == 'invoke' and row['request']['member'] == 'RunAcquisitionProtocol')
        self.assertEqual(driver._latest['RunAcquisitionProtocol'].execution_uuid, recorded)

    def test_incomplete_replay_and_changed_request_are_refused(self):
        records = self.recording(); incomplete = copy.deepcopy(records); incomplete[-1].pop('response')
        with self.assertRaises(ValueError): Sila2ReplayPeer(incomplete)
        peer = Sila2ReplayPeer(records)
        driver = Sila2Bridge(compiled(), transport=PeerLease(peer=peer)); self.addCleanup(driver.close)
        with self.assertRaises(Exception): driver.call(fixture.CAPS['Connect'], {'PhenixHost': 'different.invalid'})
        self.assertFalse(peer.consumed)


if __name__ == '__main__': unittest.main()
