"""Finite controlled execution, exact late ownership and protective retirement."""
import copy
import threading
import time
import unittest

from mhs.bridge.base import BridgeContext
from mhs.bridge.sila2 import PeerLease, Sila2Bridge
from tests.driver.sila2_support import PhenixPeer, bridge, compiled, connect, fixture, until

RUN = fixture.CAPS['RunAcquisitionProtocol']
ARGS = fixture.EXAMPLES['RunAcquisitionProtocol']


class SilaLifecycleTests(unittest.TestCase):
    def test_complete_eight_command_seven_property_contract(self):
        peer, driver = bridge(self)
        self.assertEqual(connect(driver), {'DeviceName': 'Controlled Phenix'})
        for name in ('StageIn', 'StageOut', 'GoIdle', 'GoStandby'):
            self.assertEqual(driver.call(fixture.CAPS[name], fixture.EXAMPLES.get(name, {})), {})
        self.assertIn('stage ejected', driver.call(RUN, ARGS)['Status'])
        values = driver.read('main')
        self.assertEqual(values['acquisition_progress'], 1.0)
        self.assertEqual(values['last_progress_info'], 'Well R1C1 - 100%')
        self.assertTrue(values['execution_known'])
        self.assertFalse(values['PlateDetected'])
        self.assertEqual(values['StagePosition'], 'Transfer')
        self.assertTrue(driver.call(fixture.CAPS['Stop'])['stopped'])
        count = len(peer.requests)
        self.assertEqual(driver.reset(), {'reset': True})
        self.assertEqual([r['operation'] for r in peer.requests[count:]], ['observe'])
        self.assertEqual(driver.call(fixture.CAPS['Disconnect']), {})
        self.assertFalse(driver.read('main', ['IsConnected'])['IsConnected'])
        self.assertEqual(set(r['member'] for r in peer.requests if r['operation'] == 'invoke'),
                         {name for name, spec in fixture.CONFIG['members'].items() if spec['kind'].endswith('command')})

    def test_request_timeout_retains_late_confirmation_without_followup(self):
        peer = PhenixPeer(auto_complete=False)
        entered, release = peer.block('after:invoke:RunAcquisitionProtocol')
        _, driver = bridge(self, peer, request_timeout_ms=35)
        connect(driver)
        start = time.monotonic()
        try:
            with self.assertRaises(Exception): driver.call(RUN, ARGS)
            self.assertLess(time.monotonic() - start, .3)
            self.assertTrue(entered.is_set())
            owner = driver._normal
            self.assertIsNotNone(owner)
            self.assertIsNone(owner.execution_uuid)
            with self.assertRaises(Exception): driver.call(RUN, ARGS)
            release.set()
            until(self, owner.event.is_set)
            self.assertIn(owner.execution_uuid, peer.jobs)
            self.assertTrue(peer.active)
            self.assertFalse(any(r['operation'] == 'subscribe' for r in peer.requests))
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            self.assertTrue(driver.safe_state()['achieved'])
            self.assertFalse(peer.active)
        finally: release.set()

    def test_held_normal_rpc_does_not_hold_protective_stop(self):
        peer = PhenixPeer(auto_complete=False)
        entered, release = peer.block('before:next:RunAcquisitionProtocol')
        _, driver = bridge(self, peer, request_timeout_ms=40, stop_timeout_ms=100)
        connect(driver)
        errors = []
        def run():
            try: driver.call(RUN, ARGS)
            except Exception as exc: errors.append(exc)
        worker = threading.Thread(target=run, daemon=True)
        try:
            worker.start(); self.assertTrue(entered.wait(1))
            start = time.monotonic(); stopped = driver.safe_state()
            self.assertLess(time.monotonic() - start, .25)
            self.assertFalse(stopped['achieved'])
            self.assertFalse(peer.active)
            self.assertIsNotNone(driver._normal)
            with self.assertRaises(Exception): driver.reset()
            release.set(); worker.join(1)
            until(self, lambda: driver._normal is None)
            self.assertTrue(driver.safe_state()['achieved'])
            self.assertTrue(all(item['closed'] for item in peer.streams.values()))
            self.assertTrue(errors)
        finally: release.set(); worker.join(1)

    def test_ack_only_cached_idle_and_expiry_do_not_retire_active_work(self):
        for options in ({'ack_only': True}, {'ack_only': True, 'cached_idle': True}):
            peer = PhenixPeer(auto_complete=False, ack_only=True)
            _, driver = bridge(self, peer, execution_timeout_ms=35)
            connect(driver)
            peer.cached_idle = options.get('cached_idle', False)
            with self.assertRaises(Exception): driver.call(RUN, ARGS)
            until(self, lambda: driver._normal is None)
            self.assertFalse(driver.safe_state()['achieved'])
            self.assertTrue(peer.active)
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            with self.assertRaises(Exception): driver.reset()
            with self.assertRaises(Exception): driver.call(fixture.CAPS['StageOut'], fixture.EXAMPLES['StageOut'])

    def test_fresh_endpoint_never_invents_retirement(self):
        peer, driver = bridge(self)
        self.assertFalse(driver.safe_state()['achieved'])
        self.assertEqual(peer.requests, [])

    def test_invalid_protocol_input_and_precancelled_call_have_zero_dispatches(self):
        from mhs.errors import MHSError
        from mhs import signals
        peer, driver = bridge(self)
        for value in (0, 1441, True, float('nan')):
            with self.assertRaises(MHSError) as error:
                driver.call(RUN, {**ARGS, 'TimeoutMinutes': value})
            self.assertEqual(error.exception.code, 'MHS.CAPABILITY.INPUT_INVALID')
        cancelled = threading.Event(); cancelled.set()
        with self.assertRaises(signals.Cancelled):
            driver.call(RUN, ARGS, BridgeContext(cancel_event=cancelled))
        self.assertEqual(peer.requests, [])

    def test_full_owner_history_refuses_new_work_but_protective_stop_remains_available(self):
        peer, driver = bridge(self, max_operations=2)
        connect(driver); driver.call(fixture.CAPS['GoIdle'])
        before = len(peer.requests)
        with self.assertRaises(Exception): driver.call(fixture.CAPS['GoIdle'])
        self.assertEqual(len(peer.requests), before)
        self.assertTrue(driver.safe_state()['achieved'])
        self.assertEqual(len(driver._owners), 2, 'bounded history must never silently evict identities')

    def test_close_is_bounded_and_never_implies_remote_stop(self):
        peer = PhenixPeer(auto_complete=False)
        entered, release = peer.block('after:invoke:RunAcquisitionProtocol')
        _, driver = bridge(self, peer, request_timeout_ms=30)
        connect(driver)
        try:
            with self.assertRaises(Exception): driver.call(RUN, ARGS)
            count = len(peer.requests); start = time.monotonic()
            driver.close(); driver.close()
            self.assertLess(time.monotonic() - start, .1)
            self.assertFalse(peer.closed)
            self.assertFalse(driver.safety_status()['safe_state']['achieved'])
            release.set(); until(self, lambda: peer.closed)
            self.assertTrue(peer.active)
            self.assertEqual(len(peer.requests), count)
        finally: release.set()


if __name__ == '__main__': unittest.main()
