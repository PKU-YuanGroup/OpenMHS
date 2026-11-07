"""A newer Stop request dominates reset without preempting an owned Stop."""
import threading
import time
import unittest

from mhs.bridge.base import BridgeContext
from tests.bridges.test_sila2_races import launch
from tests.bridges.test_sila2_protective_admission import ObservedCancellation, stops
from tests.driver.sila2_support import bridge, connect, fixture


class SilaResetStopOrderTests(unittest.TestCase):
    def held_reset(self):
        peer, driver = bridge(self, stop_timeout_ms=1000, request_timeout_ms=500)
        connect(driver)
        self.assertTrue(driver.safe_state()['achieved'])
        entered, release = peer.block('before:observe')
        worker, results, errors = launch(driver.reset)
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(1))
        self.assertTrue(driver._latched)
        return peer, driver, release, worker, results, errors

    def assert_effect_fenced(self, peer, driver):
        mark = len(peer.requests)
        with self.assertRaises(Exception):
            driver.call(fixture.CAPS['StageIn'], fixture.EXAMPLES['StageIn'])
        self.assertEqual([r for r in peer.requests[mark:] if r['operation'] == 'invoke'], [])
        self.assertTrue(driver._latched)

    def assert_reset_refused(self, peer, driver, release, worker, results, errors):
        release.set(); worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [])
        self.assertEqual(len(errors), 1)
        self.assert_effect_fenced(peer, driver)

    def test_timed_out_newer_stop_blocks_old_reset_without_new_send_or_epoch(self):
        peer, driver, release, worker, results, errors = self.held_reset()
        epoch, owner, count = driver.estop_epoch, driver._protective, len(stops(peer))
        try:
            began = time.monotonic()
            stopped = driver.estop(ctx=BridgeContext(deadline_ms=35))
            self.assertLess(time.monotonic() - began, .2)
            self.assertFalse(stopped['safe_state_achieved'])
            self.assertIs(driver._protective, owner)
            self.assertEqual(driver.estop_epoch, epoch)
            self.assertEqual(len(stops(peer)), count)
            self.assert_reset_refused(peer, driver, release, worker, results, errors)
            self.assertEqual(len(stops(peer)), count, 'no implicit recovery Stop')
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            self.assertTrue(driver.safe_state()['achieved'])
            self.assertEqual(driver.reset(), {'reset': True})
            self.assertEqual(len(stops(peer)), count + 1)
        finally: release.set(); worker.join(1)

    def test_cancelled_waiter_blocks_old_reset_without_invalidating_its_owner(self):
        peer, driver, release, worker, results, errors = self.held_reset()
        epoch, owner, count = driver.estop_epoch, driver._protective, len(stops(peer))
        cancel = ObservedCancellation()
        waiting, stopped, failures = launch(lambda: driver.estop(ctx=BridgeContext(cancel_event=cancel)))
        try:
            self.assertTrue(cancel.observed.wait(1)); cancel.set(); waiting.join(.2)
            self.assertFalse(waiting.is_alive()); self.assertEqual(failures, [])
            self.assertFalse(stopped[0]['safe_state_achieved'])
            self.assertIs(driver._protective, owner)
            self.assertEqual(driver.estop_epoch, epoch)
            self.assertEqual(len(stops(peer)), count)
            self.assert_reset_refused(peer, driver, release, worker, results, errors)
            self.assertEqual(len(stops(peer)), count)
        finally: cancel.set(); release.set(); waiting.join(1); worker.join(1)

    def test_already_cancelled_stop_request_cannot_be_erased_by_old_reset(self):
        peer, driver, release, worker, results, errors = self.held_reset()
        epoch, count = driver.estop_epoch, len(stops(peer))
        cancel = threading.Event(); cancel.set()
        try:
            stopped = driver.estop(ctx=BridgeContext(cancel_event=cancel))
            self.assertFalse(stopped['safe_state_achieved'])
            self.assertEqual(driver.estop_epoch, epoch)
            self.assertEqual(len(stops(peer)), count)
            self.assert_reset_refused(peer, driver, release, worker, results, errors)
        finally: release.set(); worker.join(1)

    def test_queued_stop_stays_latched_between_old_reset_and_fresh_stop_proof(self):
        peer, driver, release, worker, results, errors = self.held_reset()
        epoch, count = driver.estop_epoch, len(stops(peer))
        entered_stop, release_stop = peer.block('before:invoke:Stop')
        cancel = ObservedCancellation()
        waiting, stopped, failures = launch(lambda: driver.estop(ctx=BridgeContext(cancel_event=cancel)))
        try:
            self.assertTrue(cancel.observed.wait(1))
            self.assertEqual(driver.estop_epoch, epoch)
            release.set(); worker.join(1)
            self.assertEqual(results, []); self.assertEqual(len(errors), 1)
            self.assertTrue(entered_stop.wait(1))
            self.assert_effect_fenced(peer, driver)
            self.assertEqual(driver.estop_epoch, epoch + 1)
            self.assertEqual(len(stops(peer)), count, 'new peer request remains held')
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            release_stop.set(); waiting.join(1)
            self.assertFalse(waiting.is_alive()); self.assertEqual(failures, [])
            self.assertTrue(stopped[0]['safe_state_achieved'])
            self.assertTrue(driver._latched)
            self.assertEqual(len(stops(peer)), count + 1)
            self.assertEqual(driver.reset(), {'reset': True})
            self.assertFalse(driver._latched)
        finally: release.set(); release_stop.set(); worker.join(1); waiting.join(1)

    def test_fresh_reset_without_new_stop_remains_pure_and_admits_one_later_effect(self):
        peer, driver, release, worker, results, errors = self.held_reset()
        count = len(stops(peer))
        try:
            release.set(); worker.join(1)
            self.assertFalse(worker.is_alive()); self.assertEqual(errors, [])
            self.assertEqual(results, [{'reset': True}])
            self.assertFalse(driver._latched)
            self.assertEqual(len(stops(peer)), count, 'reset sends no Stop')
            mark = len(peer.requests)
            driver.call(fixture.CAPS['StageIn'], fixture.EXAMPLES['StageIn'])
            self.assertEqual(len([r for r in peer.requests[mark:]
                                  if r['operation'] == 'invoke' and r['member'] == 'StageIn']), 1)
        finally: release.set(); worker.join(1)

    def test_safe_state_and_declared_stop_requests_also_dominate_old_reset(self):
        for surface in ('safe_state', 'declared_stop'):
            with self.subTest(surface=surface):
                peer, driver, release, worker, results, errors = self.held_reset()
                epoch, count = driver.estop_epoch, len(stops(peer))
                try:
                    context = BridgeContext(deadline_ms=35)
                    if surface == 'safe_state':
                        self.assertFalse(driver.safe_state(context)['achieved'])
                    else:
                        with self.assertRaises(Exception): driver.call(fixture.CAPS['Stop'], {}, context)
                    self.assertEqual(driver.estop_epoch, epoch)
                    self.assertEqual(len(stops(peer)), count)
                    self.assert_reset_refused(peer, driver, release, worker, results, errors)
                finally: release.set(); worker.join(1)


if __name__ == '__main__': unittest.main()
