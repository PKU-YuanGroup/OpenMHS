"""Stock MCP/stop/reset cannot retire an unidentified Binary sample.

This controlled observable-property declaration exercises the generic helper.
It does not change Phenix's pinned unary source or claim a native device profile.
"""
import base64
import copy
import hashlib
import unittest

from mhs import canonical
from mhs.artifacts import LocalArtifactStore
from mhs.bridge.sila2 import PeerLease
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import build_server, close_server
from mhs.mcp import MCPPolicy, MCPProjection
from tests.bridges.test_sila2_races import HookPeer
from tests.driver.sila2_support import FIXTURE, fixture


CONFIG = copy.deepcopy(fixture.CONFIG)
CONFIG['members']['DisplayIcon']['kind'] = 'observable_property'


class ObservableBinaryDriver(fixture.Driver):
    sila2_config = CONFIG


class SilaEmptyBinaryBatchTests(unittest.TestCase):
    def exercise(self, defect, *, end=True):
        config = ObservableBinaryDriver.bridge_config('main')
        peer = HookPeer(config=config, chunked=True)
        driver = ObservableBinaryDriver(backend='fake', native=PeerLease(peer=peer), base_dir=FIXTURE)
        store = LocalArtifactStore()
        server = build_server(driver, site_limits=fixture.overlay(), artifact_store=store)
        projection = None
        try:
            client = MHSClient(InProcessTransport(server))
            client.hello()
            device = next(iter(server.devices))
            client.open_session([device], mode='simulated')
            original_session = client.session_id
            cap, args = fixture.CAPS['Connect'], fixture.EXAMPLES['Connect']
            permit = client.permit(cap, args, device_id=device)
            connected = client.invoke(cap, args, device_id=device, permit_id=permit['permit_id'])
            self.assertEqual(connected['status'], 'completed')

            def hook(message, reply):
                if message['operation'] == 'next':
                    if defect == 'missing_items':
                        reply['payload'].pop('items')
                    elif defect == 'empty_items':
                        reply['payload']['items'] = []
                        reply['payload']['end'] = end
                    elif defect == 'missing_sample':
                        reply['payload']['items'] = [{}]
                return reply

            peer.hook = hook
            projection = MCPProjection(client, policy=MCPPolicy(enabled=True, allow_hardware=False))

            def request(method, params):
                return projection.handle_message({'jsonrpc': '2.0', 'id': canonical.ulid(),
                                                   'method': method, 'params': params})

            response = request('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                               'clientInfo': {'name': 'controlled-binary-retention', 'version': '1'}})
            self.assertIn('result', response)
            tool = next(item['name'] for item in request('tools/list', {})['result']['tools']
                        if item['name'].endswith('phenix_displayicon'))
            receipt = request('tools/call', {'name': tool, 'arguments': {}})['result']['structuredContent']['receipt']
            downloaded = None
            if receipt['status'] == 'completed':
                artifact = receipt['artifacts'][0]
                content = request('resources/read', {'uri': artifact['uri']})['result']['contents'][0]
                downloaded = base64.b64decode(content['blob'], validate=True)
                self.assertEqual(downloaded, peer.icon)
                self.assertEqual(artifact['digest'], 'sha256:' + hashlib.sha256(downloaded).hexdigest())
            before = {'remote': len(peer.binaries), 'known': sum(len(work.binaries) for work in driver.inner._works.values()),
                      'debts': sum(len(work.resource_debts) for work in driver.inner._works.values()),
                      'grants': len(store._grants)}
            stopped = client.estop('controlled resource-retirement check', device_id=device, session_id=original_session)
            reset = client.reset(device_id=device, session_id=original_session)
            return {'capture': receipt, 'downloaded': downloaded, 'before': before,
                    'stopped': stopped, 'reset': reset, 'status': driver.safety_status(),
                    'remaining_remote': len(peer.binaries),
                    'remaining_debts': sum(len(work.resource_debts) for work in driver.inner._works.values()),
                    'streams_closed': all(stream['closed'] for stream in peer.streams.values())}
        finally:
            if projection is not None:
                projection.close()
            close_server(server)
            store.close()
            if driver.inner is not None and driver.inner._cleanup is not None:
                driver.inner._cleanup.join(1)
                self.assertFalse(driver.inner._cleanup.is_alive())
            self.assertTrue(peer.closed)
            self.assertFalse(peer.binaries)

    def assert_unknown(self, row):
        self.assertNotEqual(row['capture']['status'], 'completed')
        self.assertFalse(row['capture'].get('artifacts'))
        self.assertEqual(row['before']['grants'], 0)
        self.assertNotEqual(row['stopped']['status'], 'completed')
        self.assertIsNot((row['stopped'].get('output') or {}).get('safe_state_achieved'), True)
        self.assertNotEqual(row['reset']['status'], 'completed')
        self.assertEqual(row['before']['remote'], 1)
        self.assertEqual(row['before']['known'], 0)
        self.assertEqual(row['before']['debts'], 1)
        self.assertEqual(row['remaining_remote'], 1)
        self.assertEqual(row['remaining_debts'], 1)
        self.assertTrue(row['streams_closed'])
        self.assertTrue(row['status']['remote_uncertain'])
        self.assertFalse(row['status']['safe_state']['achieved'])

    def test_empty_sample_keeps_unknown_debt_for_both_end_flags_through_stock_stop_and_reset(self):
        for end in (False, True):
            with self.subTest(end=end):
                self.assert_unknown(self.exercise('empty_items', end=end))

    def test_missing_batch_and_missing_binary_sample_remain_unresolved(self):
        for defect in ('missing_items', 'missing_sample'):
            with self.subTest(defect=defect):
                self.assert_unknown(self.exercise(defect))

    def test_complete_sample_keeps_all_png_bytes_and_allows_fresh_stop_reset(self):
        row = self.exercise('complete')
        self.assertEqual(row['capture']['status'], 'completed')
        self.assertEqual(len(row['downloaded']), 72)
        self.assertEqual(row['before']['debts'], 0)
        self.assertEqual(row['before']['remote'], 0)
        self.assertEqual(row['stopped']['status'], 'completed')
        self.assertTrue(row['stopped']['output']['safe_state_achieved'])
        self.assertEqual(row['reset']['status'], 'completed')
        self.assertEqual(row['remaining_remote'], 0)


if __name__ == '__main__':
    unittest.main()
