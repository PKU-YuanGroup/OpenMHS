"""Lost resource-creation replies never become evidence of remote retirement."""
from __future__ import annotations

import copy
import threading
import time
import unittest

from mhs.bridge.sila2 import PeerLease, Sila2Bridge
from mhs.bridge.sila2_replay import RecordingSila2Peer
from mhs.driver.sila2_config import compile_sila2
from tests.bridges.test_sila2_races import HookPeer, launch
from tests.driver.sila2_support import bridge, compiled, connect, fixture, until
from tests import test_sila2_stock as stock

RUN = fixture.CAPS['RunAcquisitionProtocol']
ARGS = fixture.EXAMPLES['RunAcquisitionProtocol']
ICON = fixture.CAPS['DisplayIcon']


def damage(reply, defect):
    if defect == 'transport':
        raise ConnectionError('response lost after resource creation')
    if defect == 'missing_payload':
        reply.pop('payload')
    elif defect == 'typed_error':
        reply.pop('payload')
        reply['error'] = {'kind': 'undefined', 'identifier': 'LostResult', 'message': 'controlled response loss'}
    elif defect == 'empty_payload':
        reply['payload'] = {}
    elif defect == 'foreign':
        reply['request_id'] = 'foreign-response'
    return reply


class SilaUnknownResourceTests(unittest.TestCase):
    make = stock.SilaStockTests.make
    invoke = stock.SilaStockTests.invoke

    def assert_uncertain(self, driver):
        self.assertFalse(driver.safe_state()['achieved'])
        self.assertTrue(driver.safety_status()['remote_uncertain'])
        with self.assertRaises(Exception):
            driver.reset()
        self.assertFalse(driver.safety_status()['safe_state']['achieved'])

    def test_both_subscription_positions_keep_lost_response_ownership(self):
        for kind in ('info', 'intermediate'):
            for defect in ('transport', 'missing_payload', 'typed_error', 'empty_payload', 'foreign'):
                with self.subTest(kind=kind, defect=defect):
                    peer = HookPeer()
                    _, driver = bridge(self, peer)
                    connect(driver)
                    def hook(message, reply):
                        if message['operation'] == 'subscribe' and message['payload']['kind'] == kind:
                            return damage(reply, defect)
                        return reply
                    peer.hook = hook
                    with self.assertRaises(Exception):
                        driver.call(RUN, ARGS)
                    owner = driver._latest['RunAcquisitionProtocol']
                    self.assertIn(owner.ident, driver._works)
                    self.assertEqual(len(owner.resource_debts), 1)
                    request_id, debt = next(iter(owner.resource_debts.items()))
                    self.assertTrue(any(r['request_id'] == request_id and r['owner_id'] == owner.ident
                                        for r in peer.requests))
                    self.assertEqual(debt['operation'], 'subscribe')
                    self.assertEqual(len(debt['request_sha256']), 64)
                    self.assert_uncertain(driver)
                    self.assertFalse(peer.active)
                    self.assertTrue(any(not stream['closed'] for stream in peer.streams.values()))
                    self.assertTrue(any(r['operation'] == 'invoke' and r['member'] == 'Stop' for r in peer.requests))

    def test_stock_primary_binary_failure_retains_read_owner_and_no_grant(self):
        for defect in ('transport', 'missing_payload', 'typed_error', 'empty_payload', 'foreign'):
            with self.subTest(defect=defect):
                peer, store, server, client, device = self.make(options={'chunked': True})
                self.assertEqual(self.invoke(client, device, 'Connect')['status'], 'completed')
                original = peer.request
                def request(message, *, timeout_ms):
                    reply = original(message, timeout_ms=timeout_ms)
                    if message['operation'] == 'property' and message['member'] == 'DisplayIcon':
                        return damage(reply, defect)
                    return reply
                peer.request = request
                receipt = client.invoke(ICON, {}, device_id=device)
                self.assertNotEqual(receipt['status'], 'completed')
                self.assertNotIn('artifacts', receipt)
                self.assertEqual(store._grants, {})
                driver = server.devices[device].bridge.inner
                debts = [w for w in driver._works.values() if w.resource_debts]
                self.assertEqual(len(debts), 1)
                self.assertFalse(debts[0].effectful)
                self.assertTrue(peer.binaries)
                self.assert_uncertain(driver)
                self.assertTrue(peer.binaries)

    def test_observable_binary_batch_loss_retains_unknown_transfer_after_stream_cleanup(self):
        for defect in ('transport', 'missing_payload', 'typed_error', 'empty_payload'):
            with self.subTest(defect=defect):
                config = compiled()
                config['members']['DisplayIcon']['kind'] = 'observable_property'
                peer = HookPeer(config=config, chunked=True)
                driver = Sila2Bridge(config, transport=PeerLease(peer=peer))
                self.addCleanup(driver.close)
                connect(driver)
                def hook(message, reply):
                    return damage(reply, defect) if message['operation'] == 'next' else reply
                peer.hook = hook
                context, deadline = driver._context(None, 1000)
                work = driver._start('normal', deadline, lambda w: driver._result(w, 'DisplayIcon', {}),
                                     member='DisplayIcon')
                with self.assertRaises(Exception):
                    driver._wait(work, context)
                self.assertEqual(len(work.resource_debts), 1)
                self.assertTrue(peer.binaries)
                self.assert_uncertain(driver)
                self.assertTrue(all(stream['closed'] for stream in peer.streams.values()))
                self.assertTrue(peer.binaries)

    def test_late_identifiable_subscription_can_retire_only_after_response_and_cleanup(self):
        peer = HookPeer()
        _, driver = bridge(self, peer, request_timeout_ms=20)
        connect(driver)
        entered, release = peer.block('after:subscribe:RunAcquisitionProtocol')
        self.addCleanup(release.set)
        thread, results, errors = launch(lambda: driver.call(RUN, ARGS))
        self.addCleanup(lambda: thread.join(1))
        self.assertTrue(entered.wait(1))
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results, [])
        self.assertTrue(errors)
        owner = driver._latest['RunAcquisitionProtocol']
        self.assertTrue(owner.resource_debts)
        self.assertFalse(driver.safe_state()['achieved'])
        release.set()
        self.assertTrue(owner.event.wait(1))
        self.assertEqual(owner.resource_debts, {})
        self.assertTrue(owner.streams)
        self.assertTrue(driver.safe_state()['achieved'])
        self.assertTrue(all(stream['closed'] for stream in peer.streams.values()))
        self.assertFalse(peer.active)

    def test_recording_failure_after_peer_allocation_retains_original_request(self):
        peer = HookPeer()
        recorder = RecordingSila2Peer(peer)
        driver = Sila2Bridge(compiled(), transport=PeerLease(peer=recorder))
        self.addCleanup(driver.close)
        connect(driver)
        def hook(message, reply):
            if message['operation'] == 'subscribe':
                reply['unrecordable'] = float('nan')
            return reply
        peer.hook = hook
        with self.assertRaises(Exception):
            driver.call(RUN, ARGS)
        incomplete = [row for row in recorder.records if 'response' not in row]
        self.assertEqual(len(incomplete), 1)
        owner = driver._latest['RunAcquisitionProtocol']
        self.assertIn(incomplete[0]['request']['request_id'], owner.resource_debts)
        self.assert_uncertain(driver)
        self.assertTrue(any(not stream['closed'] for stream in peer.streams.values()))

    def test_uncertain_read_resource_budget_is_bounded_before_further_dispatch(self):
        config = compiled(max_operations=3)
        config['members']['DeviceState']['kind'] = 'observable_property'
        peer = HookPeer(config=config)
        driver = Sila2Bridge(config, transport=PeerLease(peer=peer))
        self.addCleanup(driver.close)
        connect(driver)
        def hook(message, reply):
            return damage(reply, 'transport') if message['operation'] == 'subscribe' else reply
        peer.hook = hook
        for _ in range(2):
            with self.assertRaises(Exception):
                driver.read('main', ['DeviceState'])
        self.assertEqual(len(driver._works), 3)
        before = len(peer.requests)
        for _ in range(4):
            with self.assertRaises(Exception):
                driver.read('main', ['DeviceState'])
        self.assertEqual(len(peer.requests), before)
        self.assertEqual(len(peer.streams), 2)
        self.assert_uncertain(driver)
        driver.close()
        until(self, lambda: peer.closed)
        self.assertTrue(all(stream['closed'] for stream in peer.streams.values()))
        self.assertFalse(driver.safety_status()['safe_state']['achieved'])
        self.assertEqual(sum(bool(w.resource_debts) for w in driver._works.values()), 2)

    def test_scalar_observation_failure_does_not_invent_a_resource_or_block_fresh_stop(self):
        peer = HookPeer()
        _, driver = bridge(self, peer)
        connect(driver)
        def hook(message, reply):
            if message['operation'] == 'property' and message['member'] == 'DeviceState':
                raise ConnectionError('scalar observation unavailable')
            return reply
        peer.hook = hook
        with self.assertRaises(Exception):
            driver.read('main', ['DeviceState'])
        self.assertFalse(any(w.resource_debts for w in driver._works.values()))
        self.assertTrue(driver.safe_state()['achieved'])

    def test_unsupported_binary_shapes_refuse_before_peer_factory(self):
        binary = {'type': 'Binary', 'max_bytes': 100}
        shapes = [binary, {'type': 'List', 'items': binary, 'max_items': 2},
                  {'type': 'Structure', 'fields': {'data': binary}},
                  {'type': 'List', 'items': {'type': 'Structure', 'fields': {'data': binary}}, 'max_items': 2}]
        for place in ('input', 'intermediate', 'output', 'metadata'):
            for shape in shapes:
                if place == 'output' and shape['type'] == 'Binary':
                    continue  # Existing complete primary artifact support.
                with self.subTest(place=place, shape=shape):
                    raw = copy.deepcopy(fixture.CONFIG)
                    commands = copy.deepcopy(fixture.Driver.commands)
                    if place == 'metadata':
                        raw['metadata'] = [{'identifier': raw['feature'] + '/Metadata/Transfer',
                                            'type': shape, 'value': []}]
                    elif place == 'output':
                        raw['members']['DisplayIcon']['output']['DisplayIcon'] = shape
                        commands[ICON] = {'member': 'DisplayIcon'}
                    else:
                        raw['members']['RunAcquisitionProtocol'][place]['Transfer'] = shape
                    called = []
                    def factory(lease, **options):
                        called.append(True)
                        raise AssertionError('unsupported declaration reached peer construction')
                    raw['commands'], raw['reads'] = commands, fixture.Driver.reads
                    with self.assertRaises(ValueError):
                        Sila2Bridge(raw, transport=PeerLease(factory=factory))
                    self.assertEqual(called, [])


if __name__ == '__main__':
    unittest.main()
