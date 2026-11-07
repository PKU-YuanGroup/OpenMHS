"""Protective confirmation uses its existing budget without discarding ordinary owners."""
import threading
import time
import unittest

from mhs.bridge.base import BridgeContext
from tests.bridges.test_sila2_races import HookPeer, launch
from tests.driver.sila2_support import bridge, connect, until


def stops(peer):
    return [row for row in peer.requests if row['operation'] == 'invoke' and row['member'] == 'Stop']


class SilaStopSettlementTests(unittest.TestCase):
    def held_read(self, **config):
        peer = HookPeer()
        _, driver = bridge(self, peer, **config)
        connect(driver)
        entered, release = peer.block('after:property:DeviceState')
        reader, values, errors = launch(lambda: driver.read('main', ['DeviceState']))
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(1))
        invoked = threading.Event()

        def observe_stop(message, reply):
            if message['operation'] == 'invoke' and message['member'] == 'Stop':
                invoked.set()
            return reply

        peer.hook = observe_stop
        return peer, driver, reader, values, errors, release, invoked

    def test_multiple_cooperative_reads_require_a_fresh_post_settlement_stop(self):
        for count in (0, 1, 2, 4):
            with self.subTest(reads=count):
                peer = HookPeer()
                _, driver = bridge(self, peer)
                connect(driver)
                reads, deadlines = [], []

                def hook(message, reply):
                    if message['operation'] == 'observe' and driver._protective is not None:
                        deadlines.append(driver._protective.deadline)
                        if len(reads) < count:
                            reads.append(driver.read('main', ['DeviceState']))
                    return reply

                peer.hook = hook
                self.assertTrue(driver.safe_state()['achieved'])
                self.assertEqual(reads, [{'DeviceState': 'Idle'}] * count)
                self.assertEqual(len(stops(peer)), count + 1)
                self.assertEqual(len(set(deadlines)), 1, 'retry never renews the original deadline')
                self.assertIsNone(driver._normal)
                self.assertIsNone(driver._protective)
                self.assertTrue(driver.safety_status()['safe_state']['achieved'])
                driver.close()
                driver._cleanup.join(1)
                self.assertFalse(driver._cleanup.is_alive())
                self.assertTrue(peer.closed)

    def test_receipt_read_can_settle_after_fifty_ms_within_original_stop_budget(self):
        peer, driver, reader, values, errors, release, invoked = self.held_read()
        stopper, results, failures = launch(driver.safe_state)
        timer = threading.Timer(.12, release.set)
        try:
            self.assertTrue(invoked.wait(1))
            timer.start()
            stopper.join(1)
            reader.join(1)
            self.assertFalse(stopper.is_alive())
            self.assertFalse(reader.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(failures, [])
            self.assertEqual(values, [{'DeviceState': 'Idle'}])
            self.assertTrue(results[0]['achieved'])
            self.assertEqual(len(stops(peer)), 2)
            self.assertTrue(driver.safety_status()['safe_state']['achieved'])
        finally:
            release.set()
            if timer.ident is not None:
                timer.join(1)
            reader.join(1)
            stopper.join(1)

    def test_never_settling_read_keeps_owner_and_stays_unsafe_at_original_deadline(self):
        peer, driver, reader, _, errors, release, _ = self.held_read(stop_timeout_ms=60)
        owner = driver._normal
        try:
            began = time.monotonic()
            self.assertFalse(driver.safe_state()['achieved'])
            self.assertLess(time.monotonic() - began, .3)
            self.assertIs(driver._normal, owner)
            self.assertTrue(reader.is_alive())
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            with self.assertRaises(Exception):
                driver.reset()
            release.set()
            reader.join(1)
            self.assertEqual(errors, [])
            until(self, lambda: driver._protective is None)
            self.assertTrue(driver.safe_state()['achieved'])
            self.assertGreaterEqual(len(stops(peer)), 2)
        finally:
            release.set()
            reader.join(1)

    def test_continuous_read_churn_cannot_extend_deadline_or_claim_safety(self):
        peer = HookPeer()
        _, driver = bridge(self, peer)
        connect(driver)
        reads, deadlines = [], []

        def hook(message, reply):
            if message['operation'] == 'observe' and driver._protective is not None:
                deadlines.append(driver._protective.deadline)
                reads.append(driver.read('main', ['DeviceState']))
            return reply

        peer.hook = hook
        began = time.monotonic()
        result = driver.safe_state(BridgeContext(deadline_ms=45))
        self.assertFalse(result['achieved'])
        self.assertLess(time.monotonic() - began, .3)
        until(self, lambda: driver._normal is None and driver._protective is None)
        self.assertGreater(len(reads), 2)
        self.assertEqual(len(set(deadlines)), 1)
        self.assertFalse(driver.safety_status()['safe_state']['achieved'])
        with self.assertRaises(Exception):
            driver.reset()
        peer.hook = None
        self.assertTrue(driver.safe_state()['achieved'])

    def test_close_wakes_settlement_wait_without_retiring_the_held_read(self):
        peer, driver, reader, _, _, release, invoked = self.held_read()
        owner = driver._normal
        stopper, results, errors = launch(driver.safe_state)
        try:
            self.assertTrue(invoked.wait(1))
            began = time.monotonic()
            driver.close()
            stopper.join(.2)
            self.assertLess(time.monotonic() - began, .25)
            self.assertFalse(stopper.is_alive())
            self.assertEqual(errors, [])
            self.assertFalse(results[0]['achieved'])
            self.assertIs(driver._normal, owner)
            self.assertFalse(peer.closed)
            release.set()
            reader.join(1)
            driver._cleanup.join(1)
            self.assertFalse(driver._cleanup.is_alive())
            self.assertTrue(peer.closed)
        finally:
            release.set()
            reader.join(1)
            stopper.join(1)

    def test_cancellation_releases_only_the_protective_waiter(self):
        peer, driver, reader, _, _, release, invoked = self.held_read()
        owner = driver._normal
        cancellation = threading.Event()
        stopper, results, errors = launch(lambda: driver.safe_state(BridgeContext(cancel_event=cancellation)))
        try:
            self.assertTrue(invoked.wait(1))
            cancellation.set()
            stopper.join(.2)
            self.assertFalse(stopper.is_alive())
            self.assertEqual(errors, [])
            self.assertFalse(results[0]['achieved'])
            self.assertIs(driver._normal, owner)
            until(self, lambda: driver._protective is None)
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            release.set()
            reader.join(1)
            self.assertTrue(driver.safe_state()['achieved'])
        finally:
            cancellation.set()
            release.set()
            reader.join(1)
            stopper.join(1)

    def test_stable_negative_proof_keeps_original_two_attempt_bound(self):
        peer = HookPeer()
        _, driver = bridge(self, peer)
        connect(driver)
        peer.cached_idle = True
        self.assertFalse(driver.safe_state()['achieved'])
        self.assertEqual(len(stops(peer)), 2)
        self.assertFalse(driver.safety_status()['safe_state']['achieved'])
        with self.assertRaises(Exception):
            driver.reset()


if __name__ == '__main__':
    unittest.main()
