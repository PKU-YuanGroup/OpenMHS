"""Controlled wire tests of bounded rosbridge text-fragment reconstruction."""
from __future__ import annotations

import base64
import hashlib
import json
import socket
import threading
import unittest
from unittest.mock import patch

from mhs.bridge.ros_transport import WebSocketTransport


def fragments(value, *, ident="0", size=100, raw=None):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False) if raw is None else raw
    parts = [raw[i:i + size] for i in range(0, len(raw), size)]
    return [json.dumps({"op": "fragment", "id": ident, "num": i, "total": len(parts), "data": part})
            for i, part in enumerate(parts)]


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


class Peer:
    def __init__(self, frames=(), clock=None, step=0.0):
        self.frames = list(frames)
        self.clock, self.step = clock, step
        self.closed = False
        self.sent = []

    def settimeout(self, value):
        pass

    def recv(self):
        if self.clock is not None:
            self.clock.now += self.step
        if not self.frames:
            raise socket.timeout()
        return self.frames.pop(0)

    def send(self, message):
        self.sent.append(json.loads(message))

    def close(self, timeout=0):
        self.closed = True


class RosFragmentTests(unittest.TestCase):
    def make(self, frames=(), *, budget=1048576, timeout=2.0, peer=None):
        peer = peer or Peer(frames)
        transport = WebSocketTransport("ws://localhost", connector=lambda *a, **kw: peer,
                                       max_message_bytes=budget, timeout_s=timeout)
        self.addCleanup(transport.close)
        return transport, peer

    def assert_closed(self, transport, peer):
        self.assertTrue(peer.closed)
        self.assertEqual(transport._fragments, {})
        self.assertEqual(transport._fragment_bytes, 0)
        with self.assertRaises(ConnectionError):
            transport.recv()
        with self.assertRaises(ConnectionError):
            transport.send({"op": "subscribe"})

    def test_full_controlled_pointcloud_bytes_reassemble_two_ten_megabyte_parts(self):
        raw = hashlib.shake_256(b"openmhs-controlled-pointcloud-20261104").digest(12582912)
        value = {"op": "publish", "topic": "/points", "msg": {"data": base64.b64encode(raw).decode(),
                 "width": 2048, "height": 128, "point_step": 48, "row_step": 98304}}
        frames = fragments(value, size=10000000)
        self.assertEqual(len(frames), 2)
        transport, _ = self.make(frames, budget=24 * 1024 * 1024)
        result = transport.recv(timeout_s=2.0)
        self.assertEqual(result, value)
        self.assertEqual(base64.b64decode(result["msg"]["data"]), raw)
        self.assertEqual(transport._fragment_bytes, 0)

    def test_unicode_escape_boundaries_and_completed_id_reuse(self):
        first = {"op": "publish", "msg": {"text": "snowman \u2603, supplementary \U0001f30d, quote \" and slash \\"}}
        second = {"op": "status", "level": "info"}
        transport, _ = self.make(fragments(first, size=7) + fragments(second, size=6))
        self.assertEqual(transport.recv(), first)
        self.assertEqual(transport.recv(), second)

    def test_interleaved_ids_and_unfragmented_protective_response(self):
        a, b = {"msg": "a" * 80}, {"msg": "b" * 90}
        af, bf = fragments(a, ident="a", size=50), fragments(b, ident="b", size=60)
        protective = {"op": "service_response", "id": "stop", "result": True, "values": {}}
        transport, _ = self.make([af[0], bf[0], json.dumps(protective), af[1], bf[1]])
        self.assertEqual(transport.recv(), protective)
        self.assertEqual(transport.recv(), a)
        self.assertEqual(transport.recv(), b)

    def test_partial_message_survives_receive_slice_timeout(self):
        value = {"msg": "x" * 100}
        clock = Clock()
        peer = Peer(fragments(value, size=60), clock, 0.03)
        with patch("mhs.bridge.ros_transport.time.monotonic", clock):
            transport, _ = self.make(peer=peer)
            with self.assertRaises(TimeoutError):
                transport.recv(timeout_s=0.02)
            self.assertFalse(peer.closed)
            self.assertEqual(transport.recv(timeout_s=0.02), value)

    def test_expiry_is_total_assembly_time_and_poisoned_not_a_slice_timeout(self):
        value = {"msg": "x" * 100}
        clock = Clock()
        peer = Peer(fragments(value, size=30), clock, 0.03)
        with patch("mhs.bridge.ros_transport.time.monotonic", clock):
            transport, _ = self.make(peer=peer, timeout=0.05)
            for _ in range(2):
                with self.assertRaises(TimeoutError):
                    transport.recv(timeout_s=0.02)
            with self.assertRaisesRegex(ValueError, "expired"):
                transport.recv(timeout_s=0.02)
            self.assert_closed(transport, peer)

    def test_expired_incomplete_message_blocks_unrelated_response(self):
        clock = Clock()
        peer = Peer([fragments({"x": "x" * 50}, size=20)[0]], clock, 0.03)
        with patch("mhs.bridge.ros_transport.time.monotonic", clock):
            transport, _ = self.make(peer=peer, timeout=0.1)
            with self.assertRaises(TimeoutError):
                transport.recv(timeout_s=0.02)
            clock.now = 0.2
            peer.frames.append('{"op":"status"}')
            with self.assertRaisesRegex(ValueError, "expired"):
                transport.recv(timeout_s=0.02)
            self.assert_closed(transport, peer)

    def test_aggregate_budget_counts_all_ids(self):
        frames = []
        for ident in ("a", "b", "c"):
            frames.extend(fragments({"x": "x" * 200}, ident=ident, size=100)[:1])
        transport, peer = self.make(frames, budget=256)
        with self.assertRaisesRegex(ValueError, "aggregate"):
            transport.recv()
        self.assert_closed(transport, peer)

    def test_complete_message_cannot_exceed_budget_using_small_fragments(self):
        transport, peer = self.make(fragments({"x": "x" * 400}, size=100), budget=256)
        with self.assertRaisesRegex(ValueError, "aggregate"):
            transport.recv()
        self.assert_closed(transport, peer)

    def test_active_assembly_count_is_bounded(self):
        frames = [fragments({"x": "x" * 50}, ident=str(i), size=20)[0] for i in range(9)]
        transport, peer = self.make(frames)
        with self.assertRaisesRegex(ValueError, "assembly count"):
            transport.recv()
        self.assert_closed(transport, peer)

    def test_malformed_metadata_is_closed_before_acceptance(self):
        normal = {"op": "fragment", "id": "0", "data": "{}", "num": 0, "total": 1}
        cases = [{**normal, key: value} for key, values in (
            ("id", (None, 1, "", "x" * 257)), ("data", (None, 1, "")),
            ("num", (-1, True, 1.0, 1)), ("total", (0, True, 1.0, 1025))) for value in values]
        cases += [{key: value for key, value in normal.items() if key != "total"}, {**normal, "extra": 1}]
        for case in cases:
            with self.subTest(case=case):
                transport, peer = self.make([json.dumps(case)])
                with self.assertRaises(ValueError):
                    transport.recv()
                self.assert_closed(transport, peer)

    def test_duplicate_out_of_order_and_conflicting_total_fail_closed(self):
        frames = fragments({"x": "x" * 100}, size=40)
        changed = json.loads(frames[1])
        changed["total"] += 1
        for sequence in ([frames[1]], [frames[0], frames[0]], [frames[0], frames[2]],
                         [frames[0], json.dumps(changed)]):
            with self.subTest(sequence=sequence):
                transport, peer = self.make(sequence)
                with self.assertRaises(ValueError):
                    transport.recv()
                self.assert_closed(transport, peer)

    def test_invalid_completed_json_and_nested_or_compressed_payload_fail_closed(self):
        for raw in ("{bad}", "[]", '{"x":NaN}', '{"op":"fragment"}', '{"op":"png"}'):
            with self.subTest(raw=raw):
                transport, peer = self.make(fragments(None, raw=raw, size=4))
                with self.assertRaises(ValueError):
                    transport.recv()
                self.assert_closed(transport, peer)

    def test_frame_budget_remains_enforced_before_fragment_processing(self):
        transport, peer = self.make(fragments({"x": "x" * 300}, size=400), budget=256)
        with self.assertRaisesRegex(ValueError, "max_message_bytes"):
            transport.recv()
        self.assert_closed(transport, peer)

    def test_close_releases_partial_messages(self):
        clock = Clock()
        peer = Peer(fragments({"x": "x" * 50}, size=30), clock, 0.03)
        with patch("mhs.bridge.ros_transport.time.monotonic", clock):
            transport, _ = self.make(peer=peer)
            with self.assertRaises(TimeoutError):
                transport.recv(timeout_s=0.02)
            self.assertGreater(transport._fragment_bytes, 0)
            transport.close()
            self.assert_closed(transport, peer)

    def test_invalid_frame_discards_already_retained_fragments(self):
        for invalid in ('{"x":NaN}', b"binary", "", "[]"):
            with self.subTest(invalid=invalid):
                transport, peer = self.make([fragments({"x": "x" * 40}, size=20)[0], invalid])
                with self.assertRaises((ValueError, ConnectionError)):
                    transport.recv()
                self.assert_closed(transport, peer)

    def test_completed_json_processing_cannot_outlive_assembly_deadline(self):
        from mhs.bridge import ros_transport
        clock = Clock()
        original = ros_transport._json_copy
        def delayed_copy(value, *, max_bytes):
            result = original(value, max_bytes=max_bytes)
            clock.now = 3.0
            return result
        with patch("mhs.bridge.ros_transport.time.monotonic", clock):
            transport, peer = self.make(fragments({"x": "x" * 40}, size=20))
            with patch("mhs.bridge.ros_transport._json_copy", side_effect=delayed_copy):
                with self.assertRaisesRegex(ValueError, "expired"):
                    transport.recv()
            self.assert_closed(transport, peer)

    def test_utf8_aggregate_and_normalized_json_keep_existing_budget(self):
        # Each envelope fits 256 bytes. The decoded Unicode payload does not
        # fit the aggregate byte budget, even though its character count does.
        value = {"x": "\u2603" * 100}
        transport, peer = self.make(fragments(value, size=20), budget=256)
        with self.assertRaisesRegex(ValueError, "aggregate"):
            transport.recv()
        self.assert_closed(transport, peer)
        # A smaller raw UTF-8 payload still cannot evade the existing ASCII
        # normalized JSON bound used throughout the bridge.
        value = {"x": "\u2603" * 50}
        transport, peer = self.make(fragments(value, size=20), budget=256)
        with self.assertRaisesRegex(ValueError, "max_message_bytes"):
            transport.recv()
        self.assert_closed(transport, peer)

    def test_receive_does_not_block_send_and_close_does_not_accept_late_frame(self):
        entered, release = threading.Event(), threading.Event()
        peer = Peer()
        def receive():
            entered.set()
            self.assertTrue(release.wait(1))
            return '{"op":"status"}'
        peer.recv = receive
        transport, _ = self.make(peer=peer)
        errors = []
        def run():
            try:
                transport.recv()
            except BaseException as exc:
                errors.append(exc)
        worker = threading.Thread(target=run)
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            transport.send({"op": "call_service", "service": "/stop"})
            self.assertEqual(peer.sent, [{"op": "call_service", "service": "/stop"}])
            with self.assertRaises(TimeoutError):
                transport.recv(timeout_s=0.01)
            transport.close()
        finally:
            release.set()
            worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ConnectionError)
        self.assert_closed(transport, peer)


if __name__ == "__main__":
    unittest.main()
