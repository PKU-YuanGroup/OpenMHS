"""Complete controlled Phenix through stock one-class loading, permits and MCP."""
import base64
import hashlib
from types import SimpleNamespace
import unittest

from mhs import canonical
from mhs.adapter import load
from mhs.artifacts import LocalArtifactStore
from mhs.bridge.sila2 import PeerLease
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import close_server
from mhs.driver.build import build_manifest, device_from_manifest
from mhs.driver.check import _hardware_view_subject
from mhs.mcp import MCPPolicy, MCPProjection
from mhs.server import MHSServer
from tests.driver.sila2_support import FIXTURE, PhenixPeer, fixture


class SilaStockTests(unittest.TestCase):
    def make(self, *, hardware=False, overlay=True, options=None, store_options=None, tokens=None):
        peer = PhenixPeer(**(options or {}))
        store = LocalArtifactStore(**(store_options or {}))
        self.addCleanup(store.close)
        if hardware:
            driver = fixture.Driver(backend='fake', native=PeerLease(peer=peer), base_dir=FIXTURE)
            subject = _hardware_view_subject(SimpleNamespace(cls=type(driver), instance=driver))
            # Synthetic test authority; never a human signature or native grant.
            verifier = lambda request: {'verified': True, 'approvals': [{'principal': 'test:controlled-sila',
                'method': 'human_click', 'evidence_ref': 'SDK local controlled fixture; no person or hardware'}]}
            server = MHSServer('mhs://localhost', [device_from_manifest(build_manifest(subject, backend='hardware'), driver)],
                strict=True, armed=True, site_limits=fixture.overlay() if overlay else None,
                artifact_store=store, auth_tokens=tokens, approval_verifier=verifier)
        else:
            server = load(FIXTURE, backend='fake', native=PeerLease(peer=peer), artifact_store=store,
                          auth_tokens=tokens, site_limits=fixture.overlay() if overlay else None)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server, auth_token='fixture-a' if tokens else None))
        client.hello(); device = next(iter(server.devices))
        client.open_session([device], mode=server.devices[device].mode)
        return peer, store, server, client, device

    def invoke(self, client, device, name, *, permit=True, **kwargs):
        args = fixture.EXAMPLES.get(name, {})
        cap = fixture.CAPS[name]
        if permit and fixture.Driver.actions[cap].requires_permit:
            grant = client.permit(cap, args, device_id=device, session_id=kwargs.get('session_id'))
            kwargs['permit_id'] = grant['permit_id']
        return client.invoke(cap, args, device_id=device, **kwargs)

    def test_full_native_shaped_workflow_with_exact_icon_and_stock_loader(self):
        peer, store, server, client, device = self.make(options={'chunked': True})
        for name in ('Connect', 'StageIn', 'StageOut', 'GoIdle', 'GoStandby', 'RunAcquisitionProtocol'):
            receipt = self.invoke(client, device, name)
            self.assertEqual(receipt['status'], 'completed', (name, receipt))
        resource = server.devices[device].resources[0].resource_id
        observed = client.read(resource, device_id=device)
        self.assertIn('last_progress_info', str(observed))
        original_session = client.session_id
        projection = MCPProjection(client, policy=MCPPolicy(enabled=True, allow_hardware=False))
        self.addCleanup(projection.close)
        def request(method, params):
            return projection.handle_message({'jsonrpc': '2.0', 'id': canonical.ulid(), 'method': method, 'params': params})
        self.assertIn('result', request('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
            'clientInfo': {'name': 'sila-controlled', 'version': '1'}}))
        tools = request('tools/list', {})['result']['tools']
        tool = next(item['name'] for item in tools if item['name'].endswith('phenix_displayicon'))
        response = request('tools/call', {'name': tool, 'arguments': {}})['result']
        receipt = response['structuredContent']['receipt']
        self.assertEqual(receipt['status'], 'completed', receipt)
        self.assertNotIn('image_ref', receipt['output'])
        descriptor = receipt['artifacts'][0]
        blob = base64.b64decode(request('resources/read', {'uri': descriptor['uri']})['result']['contents'][0]['blob'])
        self.assertEqual(blob, peer.icon)
        self.assertEqual(descriptor['digest'], 'sha256:' + hashlib.sha256(blob).hexdigest())
        self.assertFalse(peer.binaries)
        self.assertEqual(self.invoke(client, device, 'Stop', session_id=original_session)['status'], 'completed')
        self.assertEqual(client.estop('controlled latch', device_id=device, session_id=original_session)['status'], 'completed')
        self.assertEqual(client.reset(device_id=device, session_id=original_session)['status'], 'completed')
        self.assertEqual(self.invoke(client, device, 'Disconnect', session_id=original_session)['status'], 'completed')
        self.assertFalse(peer.connected)

    def test_hardware_view_requires_real_stock_permit_and_operator_envelope(self):
        peer, _, _, client, device = self.make(hardware=True)
        denied = self.invoke(client, device, 'Connect', permit=False)
        self.assertEqual(denied['status'], 'rejected')
        self.assertTrue(all(r['operation'] in ('describe', 'property') for r in peer.requests))
        permitted = self.invoke(client, device, 'Connect')
        self.assertEqual(permitted['status'], 'completed', permitted)
        peer, _, _, client, device = self.make(hardware=True, overlay=False)
        denied = self.invoke(client, device, 'Connect')
        self.assertEqual(denied['status'], 'rejected')
        self.assertEqual(denied['error']['mhs_code'], 'MHS.SAFETY.LIMITS_UNSET')
        self.assertFalse(any(r['operation'] == 'invoke' for r in peer.requests))


if __name__ == '__main__': unittest.main()
