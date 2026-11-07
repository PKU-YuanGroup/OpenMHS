"""Binary handles survive malformed responses through stock artifact paths."""
import unittest

from mhs.bridge.sila2 import PeerLease, Sila2Bridge
from tests.bridges.test_sila2_races import HookPeer
from tests.driver.sila2_support import compiled, connect, fixture
from tests import test_sila2_stock as stock_support

ICON = fixture.CAPS['DisplayIcon']


class SilaResourceArtifactTests(unittest.TestCase):
    make = stock_support.SilaStockTests.make
    invoke = stock_support.SilaStockTests.invoke

    def test_malformed_binary_envelope_keeps_transfer_until_protective_cleanup(self):
        for defect in ('envelope', 'both', 'invalid_id'):
            with self.subTest(defect=defect):
                peer, store, server, client, device = self.make(options={'chunked': True})
                self.invoke(client, device, 'Connect')
                original = peer.request
                def request(message, *, timeout_ms):
                    reply = original(message, timeout_ms=timeout_ms)
                    if message['operation'] == 'property' and message['member'] == 'DisplayIcon':
                        if defect == 'envelope': reply['extra'] = True
                        if defect == 'both': reply['error'] = {'kind': 'undefined', 'identifier': 'lost', 'message': 'ambiguous'}
                        if defect == 'invalid_id': reply['payload']['DisplayIcon']['binary_uuid'] = 'unknown'
                    return reply
                peer.request = request
                receipt = client.invoke(ICON, {}, device_id=device)
                self.assertNotEqual(receipt['status'], 'completed')
                self.assertNotIn('artifacts', receipt); self.assertEqual(store._grants, {})
                driver = server.devices[device].bridge.inner
                self.assertTrue(peer.binaries)
                owned = set().union(*(work.binaries for work in driver._works.values()))
                if defect == 'invalid_id':
                    self.assertTrue(driver._fault); self.assertFalse(driver.safe_state()['achieved'])
                    with self.assertRaises(Exception): driver.reset()
                else:
                    self.assertEqual(owned, set(peer.binaries))
                    self.assertTrue(driver.safe_state()['achieved'])
                    self.assertFalse(peer.binaries)

    def test_observable_binary_property_retains_sample_transfer_before_batch_validation(self):
        for malformed in (False, True):
            with self.subTest(malformed=malformed):
                config = compiled(); config['members']['DisplayIcon']['kind'] = 'observable_property'
                peer = HookPeer(config=config, chunked=True)
                driver = Sila2Bridge(config, transport=PeerLease(peer=peer)); self.addCleanup(driver.close)
                connect(driver)
                def hook(message, reply):
                    if malformed and message['operation'] == 'next': reply['payload']['extra'] = True
                    return reply
                peer.hook = hook
                # A real server-provided publisher is used by the stock tests
                # above. Here the failure occurs before publication, and the
                # successful control uses the same retained result worker.
                def capture(work): return driver._result(work, 'DisplayIcon', {})
                context, deadline = driver._context(None, 1000)
                work = driver._start('normal', deadline, capture, member='DisplayIcon')
                if malformed:
                    with self.assertRaises(Exception): driver._wait(work, context)
                else:
                    self.assertIn('DisplayIcon', driver._wait(work, context))
                self.assertTrue(peer.binaries)
                self.assertEqual(work.binaries, set(peer.binaries))
                self.assertTrue(driver.safe_state()['achieved'])
                self.assertFalse(peer.binaries)
                self.assertTrue(all(stream['closed'] for stream in peer.streams.values()))


if __name__ == '__main__': unittest.main()
