"""Stock cancellation, binary ownership and session-scoped artifact controls."""
import copy
import threading
import time
import unittest
from unittest.mock import patch

from mhs import canonical
from mhs.artifacts import ArtifactPublisher
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import close_server
from mhs.errors import MHSError
from tests.driver.sila2_support import fixture, until
from tests.bridges.test_sila2_races import launch
from tests import test_sila2_stock as stock_support

ICON = fixture.CAPS['DisplayIcon']


class SilaStockOwnershipTests(unittest.TestCase):
    make = stock_support.SilaStockTests.make
    invoke = stock_support.SilaStockTests.invoke

    def test_progress_read_and_supported_cancel_keep_distinct_remote_result(self):
        peer, _, server, client, device = self.make(options={'auto_complete': False})
        self.assertEqual(self.invoke(client, device, 'Connect')['status'], 'completed')
        started = self.invoke(client, device, 'RunAcquisitionProtocol', deadline_ms=15)
        self.assertIn(started['status'], ('accepted', 'running')); self.assertTrue(peer.started.wait(1))
        resource = server.devices[device].resources[0].resource_id
        progress = client.read(resource, device_id=device, fields=['acquisition_progress', 'execution_known', 'last_progress_info'])
        self.assertIn('0.25', str(progress)); self.assertIn('25%', str(progress))
        cancelled = client.cancel(started['operation_id'])
        final = client.wait(started['operation_id'], timeout=2)
        self.assertEqual(final['status'], 'cancelled', (cancelled, final))
        self.assertFalse(peer.active)
        self.assertTrue(any(r['member'] == 'Stop' for r in peer.requests))
        self.assertTrue(all(s['closed'] for s in peer.streams.values()))

    def test_unsafe_cancel_and_estop_remain_failed_unknown_never_achieved(self):
        peer, _, server, client, device = self.make(options={'auto_complete': False, 'ack_only': True})
        self.assertEqual(self.invoke(client, device, 'Connect')['status'], 'completed')
        started = self.invoke(client, device, 'RunAcquisitionProtocol', deadline_ms=15)
        self.assertTrue(peer.started.wait(1)); peer.cached_idle = True
        client.cancel(started['operation_id'])
        until(self, lambda: client.get_operation(started['operation_id'])['status'] == 'unknown')
        final = client.get_operation(started['operation_id'])
        self.assertNotIn(final['status'], ('completed', 'cancelled'))
        stop = client.estop('source-shaped ack only', device_id=device)
        self.assertFalse((stop.get('output') or {}).get('safe_state_achieved', False), stop)
        self.assertTrue(peer.active)
        self.assertNotEqual(client.reset(device_id=device)['status'], 'completed')

    def test_foreign_principal_cannot_read_or_cancel_owned_operation(self):
        tokens = {'fixture-a': {'id': 'alice', 'kind': 'agent'}, 'fixture-b': {'id': 'bob', 'kind': 'agent'}}
        peer, _, server, client, device = self.make(options={'auto_complete': False}, tokens=tokens)
        self.invoke(client, device, 'Connect')
        started = self.invoke(client, device, 'RunAcquisitionProtocol', deadline_ms=15)
        self.assertTrue(peer.started.wait(1))
        other = MHSClient(InProcessTransport(server, auth_token='fixture-b')); other.hello(); other.open_session([device])
        before = sum(r['member'] == 'Stop' for r in peer.requests)
        for method in (other.get_operation, other.cancel):
            with self.assertRaises(MHSError) as error: method(started['operation_id'])
            self.assertEqual(error.exception.code, 'MHS.OPERATION.UNKNOWN')
        self.assertEqual(before, sum(r['member'] == 'Stop' for r in peer.requests))
        client.cancel(started['operation_id'])
        self.assertEqual(client.wait(started['operation_id'], timeout=2)['status'], 'cancelled')

    def test_full_binary_grant_session_principal_replay_and_expiry(self):
        now = [0.0]
        tokens = {'fixture-a': {'id': 'alice', 'kind': 'agent'}, 'fixture-b': {'id': 'bob', 'kind': 'agent'}}
        peer, _, server, client, device = self.make(options={'chunked': True}, tokens=tokens,
                                                   store_options={'ttl_s': 1, 'clock': lambda: now[0]})
        self.invoke(client, device, 'Connect')
        command = canonical.ulid(); result = client.invoke(ICON, {}, device_id=device, command_id=command)
        self.assertEqual(result['status'], 'completed', result)
        count = len(peer.requests); uri = result['output']['artifact_ref']; session = result['session_id']
        self.assertEqual(client.read_artifact(uri, session_id=session)['data'], peer.icon)
        replay = client.invoke(ICON, {}, device_id=device, command_id=command)
        self.assertTrue(replay['replayed']); self.assertEqual(replay['artifacts'], result['artifacts'])
        self.assertEqual(len(peer.requests), count)
        for token in (None, 'fixture-b'):
            other = MHSClient(InProcessTransport(server, auth_token=token))
            with self.assertRaises(MHSError): other.read_artifact(uri, session_id=session)
        client.open_session([device])
        with self.assertRaises(MHSError): client.read_artifact(uri, session_id=client.session_id)
        now[0] = 2
        with self.assertRaises(MHSError): client.read_artifact(uri, session_id=session)
        replay = client.invoke(ICON, {}, device_id=device, command_id=command, session_id=session)
        self.assertEqual(replay['artifacts'], result['artifacts']); self.assertEqual(len(peer.requests), count)

    def test_preflight_limit_rejects_before_binary_property_and_session_close_revokes(self):
        peer, store, _, client, device = self.make(store_options={'max_artifact_bytes': 32})
        self.invoke(client, device, 'Connect'); count = len(peer.requests)
        result = client.invoke(ICON, {}, device_id=device)
        self.assertNotEqual(result['status'], 'completed'); self.assertEqual(store._grants, {})
        self.assertFalse(any(r['member'] == 'DisplayIcon' for r in peer.requests[count:]))
        peer, store, _, client, device = self.make()
        self.invoke(client, device, 'Connect'); result = client.invoke(ICON, {}, device_id=device)
        uri = result['output']['artifact_ref']; client.close_session(result['session_id'])
        with self.assertRaises(MHSError): client.read_artifact(uri, session_id=result['session_id'])

    def test_transfer_gap_digest_overflow_and_delete_failure_never_publish(self):
        for defect in ('gap', 'digest', 'overflow', 'delete'):
            peer, store, server, client, device = self.make(options={'chunked': True})
            self.invoke(client, device, 'Connect')
            original = peer.request
            def request(message, *, timeout_ms):
                response = original(message, timeout_ms=timeout_ms)
                operation = message['operation']
                if defect == 'gap' and operation == 'binary_chunk': response['payload']['offset'] += 1
                if defect == 'digest' and operation == 'binary_chunk': response['payload']['data'] = b'0' * len(response['payload']['data'])
                if defect == 'overflow' and operation == 'property' and message['member'] == 'DisplayIcon': response['payload']['DisplayIcon']['size_bytes'] = 2**40
                if defect == 'delete' and operation == 'binary_delete': response['payload']['deleted'] = False
                return response
            peer.request = request
            receipt = client.invoke(ICON, {}, device_id=device)
            self.assertNotEqual(receipt['status'], 'completed', (defect, receipt)); self.assertNotIn('artifacts', receipt)
            self.assertEqual(store._grants, {})
            if defect in ('gap', 'digest', 'overflow', 'delete'):
                self.assertTrue(any(w.binaries for w in server.devices[device].bridge.inner._works.values()))
            close_server(server)
            until(self, lambda: peer.closed)
            self.assertFalse(peer.binaries)

    def test_late_binary_subscription_handle_is_owned_until_explicit_cleanup(self):
        peer, store, server, client, device = self.make(options={'chunked': True})
        self.invoke(client, device, 'Connect')
        entered, release = peer.block('after:property:DisplayIcon')
        sid = client.session_id
        worker, receipts, errors = launch(lambda: client.invoke(ICON, {}, device_id=device, deadline_ms=25, session_id=sid))
        try:
            self.assertTrue(entered.wait(1)); worker.join(.2)
            self.assertTrue(peer.binaries); self.assertEqual(store._grants, {})
            release.set(); until(self, lambda: server.devices[device].bridge.inner._normal is None)
            self.assertEqual(store._grants, {})
            self.assertFalse(any(r['operation'] == 'binary_chunk' for r in peer.requests))
            self.assertTrue(server.devices[device].bridge.inner.safe_state()['achieved'])
            self.assertFalse(peer.binaries)
        finally: release.set(); worker.join(1)

    def test_publication_and_store_lock_do_not_hold_stop_or_leak_late_artifact(self):
        peer, store, server, client, device = self.make()
        self.invoke(client, device, 'Connect')
        entered, release = threading.Event(), threading.Event()
        original = ArtifactPublisher.publish
        def held(publisher, *args, **kwargs):
            result = original(publisher, *args, **kwargs)
            entered.set(); release.wait(2); return result
        worker = None
        try:
            with patch.object(ArtifactPublisher, 'publish', held):
                worker, receipts, errors = launch(lambda: client.invoke(ICON, {}, device_id=device, deadline_ms=1000))
                self.assertTrue(entered.wait(1)); start = time.monotonic()
                stopped = server.devices[device].bridge.inner.safe_state()
                self.assertLess(time.monotonic() - start, .3); self.assertFalse(stopped['achieved'])
                self.assertTrue(any(r['member'] == 'Stop' for r in peer.requests))
                release.set(); worker.join(2)
            self.assertFalse(errors); self.assertNotEqual(receipts[0]['status'], 'completed')
            self.assertNotIn('artifacts', receipts[0]); self.assertEqual(store._grants, {})
            self.assertTrue(server.devices[device].bridge.inner.safe_state()['achieved'])
        finally:
            release.set()
            if worker is not None: worker.join(2)

    def test_output_commit_failure_and_close_never_leave_grants(self):
        peer, store, server, client, device = self.make(); self.invoke(client, device, 'Connect')
        for method in ('prepare', 'commit'):
            with patch.object(ArtifactPublisher, method, side_effect=RuntimeError('controlled stock publication failure')):
                result = client.invoke(ICON, {}, device_id=device)
            self.assertNotEqual(result['status'], 'completed'); self.assertNotIn('artifacts', result); self.assertEqual(store._grants, {})
        result = client.invoke(ICON, {}, device_id=device)
        self.assertEqual(result['status'], 'completed')
        root = store._root; close_server(server); self.assertFalse(root.exists())
        with self.assertRaises(MHSError): client.read_artifact(result['output']['artifact_ref'], session_id=result['session_id'])


if __name__ == '__main__': unittest.main()
