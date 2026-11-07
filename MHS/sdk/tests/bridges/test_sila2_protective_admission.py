"""Bounded protective admission never preempts or borrows a previous proof."""
import threading
import time
import unittest

from mhs.bridge.base import BridgeContext
from tests.bridges.test_sila2_races import HookPeer, launch
from tests.driver.sila2_support import bridge, connect, fixture, until
from mhs.driver.behaviour import BehaviourRun
from mhs.driver.check import _Context
from tests.driver.sila2_support import FIXTURE


class ObservedCancellation(threading.Event):
    def __init__(self):
        super().__init__()
        self.observed = threading.Event()
    def is_set(self):
        self.observed.set()
        return super().is_set()


def stops(peer):
    return [r for r in peer.requests if r['operation'] == 'invoke' and r['member'] == 'Stop']


class SilaProtectiveAdmissionTests(unittest.TestCase):
    def held(self, peer=None):
        peer, driver = bridge(self, peer)
        connect(driver)
        entered, release = peer.block('after:invoke:Stop')
        worker, result, errors = launch(driver.safe_state)
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(1))
        return peer, driver, release, worker, result, errors

    def test_each_waiter_keeps_old_epoch_then_owns_a_fresh_stop_and_typed_proof(self):
        peer, driver, release, first, first_result, first_errors = self.held()
        owner, epoch = driver._protective, driver.estop_epoch
        waiters = []
        try:
            for _ in range(2):
                cancel = ObservedCancellation()
                worker, result, errors = launch(lambda event=cancel: driver.safe_state(BridgeContext(cancel_event=event)))
                waiters.append((worker, result, errors))
                self.assertTrue(cancel.observed.wait(1))
            self.assertIs(driver._protective, owner)
            self.assertEqual(driver.estop_epoch, epoch)
            self.assertEqual(len(stops(peer)), 1)
            self.assertTrue(all(w.is_alive() for w, _, _ in waiters))
            release.set(); first.join(1)
            for worker, _, _ in waiters: worker.join(1)
            self.assertEqual(first_errors, [])
            self.assertTrue(first_result[0]['achieved'])
            for worker, result, errors in waiters:
                self.assertFalse(worker.is_alive()); self.assertEqual(errors, [])
                self.assertTrue(result[0]['achieved'])
            requests = stops(peer)
            self.assertEqual(len(requests), 3)
            self.assertEqual(len({r['owner_id'] for r in requests}), 3)
            self.assertEqual(driver.estop_epoch, epoch + 2)
        finally:
            release.set(); first.join(1)
            for worker, _, _ in waiters: worker.join(1)

    def test_occupied_timeout_keeps_owner_epoch_and_no_new_send(self):
        peer, driver, release, first, result, errors = self.held()
        owner, epoch = driver._protective, driver.estop_epoch
        try:
            began = time.monotonic()
            rejected = driver.safe_state(BridgeContext(deadline_ms=35))
            self.assertFalse(rejected['achieved'])
            self.assertLess(time.monotonic() - began, .2)
            self.assertIs(driver._protective, owner)
            self.assertEqual(driver.estop_epoch, epoch)
            self.assertEqual(len(stops(peer)), 1)
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            with self.assertRaises(Exception): driver.reset()
            release.set(); first.join(1)
            self.assertFalse(errors); self.assertTrue(result[0]['achieved'])
            self.assertTrue(driver.safe_state()['achieved'])
            self.assertEqual(len(stops(peer)), 2)
        finally: release.set(); first.join(1)

    def test_cancel_during_wait_sends_nothing_and_does_not_invalidate_the_owned_stop(self):
        peer, driver, release, first, result, errors = self.held()
        cancel = ObservedCancellation(); epoch = driver.estop_epoch
        waiting, values, failures = launch(lambda: driver.safe_state(BridgeContext(cancel_event=cancel)))
        try:
            self.assertTrue(cancel.observed.wait(1)); cancel.set(); waiting.join(.2)
            self.assertFalse(waiting.is_alive()); self.assertFalse(failures)
            self.assertFalse(values[0]['achieved'])
            self.assertEqual(driver.estop_epoch, epoch)
            self.assertEqual(len(stops(peer)), 1)
            self.assertTrue(first.is_alive())
            release.set(); first.join(1)
            self.assertFalse(errors); self.assertTrue(result[0]['achieved'])
        finally: cancel.set(); release.set(); waiting.join(1); first.join(1)

    def test_close_during_wait_is_bounded_and_retains_cleanup_of_the_only_request(self):
        peer, driver, release, first, result, errors = self.held()
        cancel = ObservedCancellation(); epoch = driver.estop_epoch; owner = driver._protective
        waiting, values, failures = launch(lambda: driver.safe_state(BridgeContext(cancel_event=cancel)))
        try:
            self.assertTrue(cancel.observed.wait(1))
            began = time.monotonic(); driver.close()
            self.assertLess(time.monotonic() - began, .1)
            waiting.join(.2)
            self.assertFalse(waiting.is_alive()); self.assertFalse(failures)
            self.assertFalse(values[0]['achieved'])
            self.assertIs(driver._protective, owner); self.assertEqual(driver.estop_epoch, epoch)
            self.assertFalse(peer.closed)
            release.set(); first.join(1); driver._cleanup.join(1)
            self.assertFalse(driver._cleanup.is_alive()); self.assertTrue(peer.closed)
            self.assertEqual(len(stops(peer)), 1)
            self.assertFalse(result[0]['achieved']); self.assertFalse(errors)
        finally: release.set(); waiting.join(1); first.join(1)

    def test_waiter_cannot_reuse_preceding_success_after_its_own_bad_typed_confirmation(self):
        peer = HookPeer()
        count = [0]
        def malformed_second(message, reply):
            if message['operation'] == 'invoke' and message['member'] == 'Stop':
                count[0] += 1
                if count[0] == 2: reply['payload'] = {'unexpected': 1}
            return reply
        peer.hook = malformed_second
        peer, driver, release, first, result, errors = self.held(peer)
        cancel = ObservedCancellation()
        waiting, values, failures = launch(lambda: driver.safe_state(BridgeContext(cancel_event=cancel)))
        try:
            self.assertTrue(cancel.observed.wait(1)); release.set()
            first.join(1); waiting.join(1)
            self.assertFalse(errors); self.assertTrue(result[0]['achieved'])
            self.assertFalse(failures); self.assertFalse(values[0]['achieved'])
            self.assertEqual(len(stops(peer)), 2)
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            with self.assertRaises(Exception): driver.reset()
        finally: release.set(); waiting.join(1); first.join(1)

    def test_unknown_ordinary_owner_survives_waiters_and_requires_a_post_settlement_stop(self):
        peer = HookPeer(auto_complete=False)
        _, driver = bridge(self, peer, stop_timeout_ms=200)
        connect(driver)
        entered, release_normal = peer.block('before:invoke:RunAcquisitionProtocol')
        normal, _, normal_errors = launch(lambda: driver.call(fixture.CAPS['RunAcquisitionProtocol'],
            fixture.EXAMPLES['RunAcquisitionProtocol'], BridgeContext(deadline_ms=25)))
        self.assertTrue(entered.wait(1)); normal.join(.2); self.assertTrue(normal_errors)
        owner = driver._normal
        held, release_stop = peer.block('after:invoke:Stop')
        first, result, errors = launch(driver.safe_state)
        self.assertTrue(held.wait(1))
        cancel = ObservedCancellation()
        waiting, values, failures = launch(lambda: driver.safe_state(BridgeContext(cancel_event=cancel)))
        try:
            self.assertTrue(cancel.observed.wait(1)); release_stop.set(); first.join(1); waiting.join(1)
            self.assertFalse(errors); self.assertFalse(failures)
            self.assertFalse(result[0]['achieved']); self.assertFalse(values[0]['achieved'])
            self.assertIs(driver._normal, owner)
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            with self.assertRaises(Exception): driver.reset()
            before = len(stops(peer)); release_normal.set(); until(self, owner.event.is_set)
            self.assertTrue(peer.active)
            self.assertTrue(driver.safe_state()['achieved'])
            self.assertGreater(len(stops(peer)), before)
            self.assertFalse(peer.active)
        finally:
            release_normal.set(); release_stop.set(); normal.join(1); first.join(1); waiting.join(1)

    def test_stock_cancelled_icon_and_concurrent_estop_paths_pass_repeated_fresh_endpoints(self):
        # The original combined-gate failure uses these unmodified stock paths.
        for _ in range(12):
            ctx = _Context(FIXTURE, 'fake', None, None, False)
            try:
                run = BehaviourRun(endpoint=ctx.endpoint, model=ctx.model, hardware_view=None,
                                   fixtures=ctx.fixtures, has_prerequisites=True)
                published, bindings = run._with(run._discover)
                safety = published['safety']
                run._estop(bindings, safety['safe_state']['achieved_by'], safety['estop']['native'])
                self.assertEqual([r for r in run.findings if r[2] == 'error'], [])
            finally: ctx.close()

    def test_status_waits_for_owned_safe_read_without_any_new_stop_or_reset(self):
        peer, driver = bridge(self); connect(driver)
        self.assertTrue(driver.safe_state()['achieved'])
        entered, release = peer.block('after:property:DeviceState')
        normal, values, errors = launch(lambda: driver.read('main', ['DeviceState']))
        self.assertTrue(entered.wait(1)); mark = len(stops(peer))
        # The existing cleanup worker already waits on this condition. A new
        # waiter proves the status call has released the retirement lock.
        with driver._condition: count = len(driver._condition._waiters)
        status, results, failures = launch(driver.safety_status)
        try:
            until(self, lambda: len(driver._condition._waiters) > count, timeout=.04)
            self.assertFalse(results, 'no true status before the read retires')
            release.set(); normal.join(1); status.join(1)
            self.assertFalse(errors); self.assertFalse(failures)
            self.assertEqual(values, [{'DeviceState': 'Idle'}])
            self.assertTrue(results[0]['safe_state']['achieved'])
            self.assertEqual(len(stops(peer)), mark)
        finally: release.set(); normal.join(1); status.join(1)

    def test_status_wait_is_bounded_for_never_settling_read_and_late_contrary_value_stays_unsafe(self):
        peer = HookPeer(); _, driver = bridge(self, peer); connect(driver)
        self.assertTrue(driver.safe_state()['achieved'])
        entered, release = peer.block('after:property:DeviceState')
        def contrary(message, reply):
            if message['operation'] == 'property' and message['member'] == 'DeviceState':
                reply['payload']['DeviceState'] = 'Operate'
            return reply
        peer.hook = contrary
        normal, _, errors = launch(lambda: driver.read('main', ['DeviceState']))
        try:
            self.assertTrue(entered.wait(1)); mark = len(stops(peer))
            start = time.monotonic(); status = driver.safety_status()
            self.assertLess(time.monotonic() - start, .2)
            self.assertFalse(status['safe_state']['achieved'])
            self.assertTrue(normal.is_alive())
            release.set(); normal.join(1)
            self.assertFalse(errors)
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            with self.assertRaises(Exception): driver.reset()
            self.assertEqual(len(stops(peer)), mark)
        finally: release.set(); normal.join(1)

    def test_status_does_not_wait_for_its_own_native_shaped_worker(self):
        peer = HookPeer(); _, driver = bridge(self, peer); connect(driver)
        self.assertTrue(driver.safe_state()['achieved'])
        seen = []
        def reentrant(message, reply):
            if message['operation'] == 'property' and message['member'] == 'DeviceState':
                start = time.monotonic(); value = driver.safety_status()
                seen.append((value, time.monotonic() - start))
            return reply
        peer.hook = reentrant
        self.assertEqual(driver.read('main', ['DeviceState']), {'DeviceState': 'Idle'})
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0][0]['safe_state']['achieved'])
        self.assertLess(seen[0][1], .025)

    def test_close_wakes_status_wait_without_releasing_the_pending_owner(self):
        peer, driver = bridge(self); connect(driver); self.assertTrue(driver.safe_state()['achieved'])
        entered, release = peer.block('after:property:DeviceState')
        normal, _, _ = launch(lambda: driver.read('main', ['DeviceState']))
        self.assertTrue(entered.wait(1))
        with driver._condition: count = len(driver._condition._waiters)
        status, results, errors = launch(driver.safety_status)
        try:
            until(self, lambda: len(driver._condition._waiters) > count, timeout=.04)
            owner = driver._normal; driver.close(); status.join(.2)
            self.assertFalse(status.is_alive()); self.assertFalse(errors)
            self.assertFalse(results[0]['safe_state']['achieved'])
            self.assertIs(driver._normal, owner)
            self.assertFalse(peer.closed)
            release.set(); normal.join(1); driver._cleanup.join(1)
            self.assertTrue(peer.closed)
        finally: release.set(); normal.join(1); status.join(1)


if __name__ == '__main__': unittest.main()
