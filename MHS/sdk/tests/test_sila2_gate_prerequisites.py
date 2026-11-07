"""No automatic Connect or stop proof to make the generic gate succeed."""
import unittest

from tests import test_sila2_stock as stock_support
from tests.driver.sila2_support import fixture


class SilaExplicitPrerequisiteTests(unittest.TestCase):
    make = stock_support.SilaStockTests.make
    invoke = stock_support.SilaStockTests.invoke

    def test_fresh_stock_endpoint_and_authorized_stage_call_do_not_invent_connect_or_safety(self):
        peer, _, _, client, device = self.make()
        receipt = self.invoke(client, device, 'StageIn')
        self.assertEqual(receipt['status'], 'unknown', receipt)
        self.assertEqual(receipt['error']['mhs_code'], 'MHS.OUTCOME.UNKNOWN')
        self.assertFalse(peer.connected)
        self.assertFalse(peer.ever_connected)
        self.assertFalse(any(r['member'] == 'Connect' for r in peer.requests))
        stop = client.estop('fresh disconnected endpoint', device_id=device)
        self.assertEqual(stop['status'], 'failed', stop)
        self.assertFalse((stop.get('output') or {}).get('safe_state_achieved', False), stop)
        self.assertNotEqual(client.reset(device_id=device)['status'], 'completed')
        self.assertFalse(any(r['member'] == 'Connect' for r in peer.requests))

    def test_all_six_read_properties_follow_explicit_state_changes_and_reset_does_not_connect(self):
        peer, _, server, client, device = self.make()
        resource = server.devices[device].resources[0].resource_id
        fields = [name for name, spec in fixture.CONFIG['members'].items()
                  if spec['kind'].endswith('property') and name != 'DisplayIcon']
        def state():
            return client.read(resource, device_id=device, fields=fields)['state']
        before = state()
        self.assertEqual(set(before), set(fields))
        self.assertEqual(before['DeviceState'], 'Offline')
        self.assertFalse(before['IsConnected'])
        self.assertFalse(peer.ever_connected)
        self.assertEqual(self.invoke(client, device, 'Connect')['status'], 'completed')
        connected = state()
        self.assertTrue(connected['IsConnected'])
        self.assertEqual(connected['DeviceState'], 'Idle')
        self.assertEqual(connected['AvailableProtocols'], ['controlled_protocol'])
        self.assertEqual(connected['DeviceDescription'], 'Original controlled test imager; no optics or timing fidelity.')
        self.assertEqual(self.invoke(client, device, 'StageIn')['status'], 'completed')
        self.assertEqual((state()['StagePosition'], state()['PlateDetected']), ('Operate', True))
        self.assertEqual(self.invoke(client, device, 'StageOut')['status'], 'completed')
        self.assertEqual((state()['StagePosition'], state()['PlateDetected']), ('Transfer', False))
        self.assertEqual(self.invoke(client, device, 'GoStandby')['status'], 'completed')
        self.assertEqual(state()['DeviceState'], 'Standby')
        self.assertEqual(self.invoke(client, device, 'GoIdle')['status'], 'completed')
        self.assertEqual(state()['DeviceState'], 'Idle')
        self.assertEqual(client.estop('controlled stop after Connect', device_id=device)['status'], 'completed')
        mark = len(peer.requests)
        self.assertEqual(client.reset(device_id=device)['status'], 'completed')
        self.assertFalse(any(r['operation'] == 'invoke' for r in peer.requests[mark:]))
        self.assertEqual(self.invoke(client, device, 'Disconnect')['status'], 'completed')
        self.assertEqual((state()['IsConnected'], state()['DeviceState']), (False, 'Offline'))
        observed = {r['member'] for r in peer.requests if r['operation'] == 'property'}
        self.assertTrue(set(fields) <= observed)


if __name__ == '__main__':
    unittest.main()
