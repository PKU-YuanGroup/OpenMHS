"""Correlated malformed responses retain resources without becoming success."""
import unittest

from mhs.bridge.sila2 import PeerLease, Sila2Bridge
from tests.bridges.test_sila2_races import HookPeer
from tests.driver.sila2_support import bridge, compiled, connect, fixture

RUN = fixture.CAPS['RunAcquisitionProtocol']
ARGS = fixture.EXAMPLES['RunAcquisitionProtocol']


class SilaResourceRetentionTests(unittest.TestCase):
    def test_malformed_confirmation_retains_uuid_before_body_and_envelope_validation(self):
        for defect in ('extra', 'lifetime', 'envelope', 'both', 'nonfinite'):
            with self.subTest(defect=defect):
                peer = HookPeer(); _, driver = bridge(self, peer); connect(driver)
                def hook(message, reply):
                    if message['operation'] == 'invoke' and message['member'] == 'RunAcquisitionProtocol':
                        if defect == 'extra': reply['payload']['extra'] = 'unexpected'
                        if defect == 'lifetime': reply['payload']['lifetime'] = {'seconds': True, 'nanos': 0}
                        if defect == 'envelope': reply['extra'] = True
                        if defect == 'both': reply['error'] = {'kind': 'undefined', 'identifier': 'lost', 'message': 'ambiguous'}
                        if defect == 'nonfinite': reply['payload']['lifetime'] = {'seconds': float('nan'), 'nanos': 0}
                    return reply
                peer.hook = hook
                with self.assertRaises(Exception): driver.call(RUN, ARGS)
                owner = driver._latest['RunAcquisitionProtocol']
                self.assertIn(owner.execution_uuid, peer.jobs)
                self.assertFalse(owner.retired); self.assertTrue(peer.active)
                self.assertFalse(driver.safety_status()['safe_state']['achieved'])
                self.assertTrue(driver.safe_state()['achieved'])
                self.assertFalse(peer.active); self.assertTrue(owner.retired)

    def test_malformed_subscription_retains_handle_until_confirmed_unsubscribe(self):
        for defect in ('extra', 'envelope', 'both'):
            with self.subTest(defect=defect):
                peer = HookPeer(); _, driver = bridge(self, peer); connect(driver)
                def hook(message, reply):
                    if message['operation'] == 'subscribe':
                        if defect == 'extra': reply['payload']['extra'] = True
                        if defect == 'envelope': reply['extra'] = True
                        if defect == 'both': reply['error'] = {'kind': 'undefined', 'identifier': 'lost', 'message': 'ambiguous'}
                    return reply
                peer.hook = hook
                with self.assertRaises(Exception): driver.call(RUN, ARGS)
                owner = driver._latest['RunAcquisitionProtocol']
                self.assertEqual(set(owner.streams), set(peer.streams))
                self.assertEqual(len(owner.streams), 1)
                self.assertTrue(all(not value['closed'] for value in peer.streams.values()))
                self.assertTrue(driver.safe_state()['achieved'])
                self.assertTrue(all(value['closed'] for value in peer.streams.values()))
                self.assertTrue(any(r['operation'] == 'unsubscribe' for r in peer.requests))

    def test_unidentifiable_execution_or_subscription_never_clears_the_fault(self):
        for kind in ('execution', 'stream'):
            for malformed in (None, True, 'not-a-uuid'):
                with self.subTest(kind=kind, malformed=malformed):
                    peer = HookPeer(); _, driver = bridge(self, peer); connect(driver)
                    def hook(message, reply):
                        if kind == 'execution' and message['operation'] == 'invoke' and message['member'] == 'RunAcquisitionProtocol':
                            reply['payload']['execution_uuid'] = malformed
                        if kind == 'stream' and message['operation'] == 'subscribe':
                            reply['payload']['stream_id'] = malformed
                        return reply
                    peer.hook = hook
                    with self.assertRaises(Exception): driver.call(RUN, ARGS)
                    self.assertTrue(driver._fault)
                    before = sum(r['member'] == 'Stop' for r in peer.requests)
                    self.assertFalse(driver.safe_state()['achieved'])
                    self.assertGreater(sum(r['member'] == 'Stop' for r in peer.requests), before)
                    with self.assertRaises(Exception): driver.reset()
                    self.assertFalse(driver.safety_status()['safe_state']['achieved'])

    def test_foreign_response_cannot_adopt_a_valid_resource_handle(self):
        for identity in ('owner_id', 'request_id', 'generation', 'feature', 'member', 'operation'):
            with self.subTest(identity=identity):
                peer = HookPeer(); _, driver = bridge(self, peer); connect(driver)
                def hook(message, reply):
                    if message['operation'] == 'invoke' and message['member'] == 'RunAcquisitionProtocol':
                        reply[identity] = 'foreign'
                    return reply
                peer.hook = hook
                with self.assertRaises(Exception): driver.call(RUN, ARGS)
                self.assertIsNone(driver._latest['RunAcquisitionProtocol'].execution_uuid)
                self.assertTrue(driver._fault); self.assertFalse(driver.safe_state()['achieved'])


if __name__ == '__main__': unittest.main()
