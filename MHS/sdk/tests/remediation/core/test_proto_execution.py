"""Regression tests for PROTO-002..006 (review counterexamples)."""

from __future__ import annotations

import json
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mhs import canonical, connect
from mhs.errors import MHSError
from mhs.protocol import Method
from mhs.reference import build_endpoint, build_server

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE / "core"))
import _device_server  # noqa: E402


def _server_client():
    server = _device_server.build_server()
    handle = server.start_http("127.0.0.1", 0)
    client = connect(handle.url)
    manifest = client.devices()[0]
    device_id = manifest["device_id"]
    return server, handle, client, device_id


class CommandIdentityTests(unittest.TestCase):
    """PROTO-002/OP-004/OP-006: command identity is device+capability+input."""

    def setUp(self):
        self.server, self.handle, self.client, self.device_id = _server_client()
        self.session = self.client.open_session(
            [self.device_id], capabilities=None, mode="simulated", ttl_s=300
        )["session_id"]

    def tearDown(self):
        self.client.close()
        self.handle.shutdown()

    def test_same_command_id_other_capability_is_not_replayed(self):
        first = self.client.invoke(
            "cap.world.step.v1", {"ticks": 1}, device_id=self.device_id,
            session_id=self.session, command_id=canonical.ulid(),
        )
        self.assertEqual(first["status"], "completed")
        # Same command_id, different capability and empty input: the old SDK
        # replayed the first receipt; the action digest must now differ.
        second = self.client.invoke(
            "cap.motion.stop.v1", {}, device_id=self.device_id,
            session_id=self.session, command_id=first["command_id"],
        )
        self.assertEqual(second["status"], "rejected")
        self.assertEqual(second["error"]["mhs_code"], "MHS.CONFLICT.COMMAND_ID_REUSE")

    def test_action_digest_is_capability_and_resource_scoped(self):
        receipt = self.client.invoke(
            "cap.world.step.v1", {"ticks": 1}, device_id=self.device_id,
            session_id=self.session,
        )
        expected = canonical.digest(
            {"capability_id": "cap.world.step.v1", "resource": "world",
             "input": {"ticks": 1}}
        )
        self.assertEqual(receipt["input_digest"], expected)


class CancellationTests(unittest.TestCase):
    """PROTO-003: cancellation is acknowledged, never a claimed physical stop."""

    def setUp(self):
        self.server, self.handle, self.client, self.device_id = _server_client()
        self.session = self.client.open_session(
            [self.device_id], capabilities=None, mode="simulated", ttl_s=300
        )["session_id"]

    def tearDown(self):
        self.client.close()
        self.handle.shutdown()

    def _wait_final(self, operation_id: str, timeout: float = 5.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ops = self.client.operations(device_id=self.device_id)["operations"]
            entry = next((op for op in ops if op["operation_id"] == operation_id), None)
            if entry is not None and entry.get("status") in (
                "completed", "failed", "cancelled", "unknown"
            ):
                return entry
            time.sleep(0.02)
        raise AssertionError(f"operation {operation_id} did not finish")

    def test_cancel_does_not_claim_safe_state_before_worker_ack(self):
        before = self.client.read("world", device_id=self.device_id)["state"]["tick"]
        running = self.client.invoke(
            "x-cap.test.long.v1", {"ms": 400}, device_id=self.device_id,
            session_id=self.session, deadline_ms=80,
        )
        self.assertIn(running["status"], ("unknown", "running", "accepted"))
        op_id = running.get("operation_id")
        self.assertTrue(op_id)
        cancel = self.client.request(
            Method.OPERATIONS_CANCEL,
            {"session_id": self.session, "operation_id": op_id, "deadline_ms": 10},
        )
        self.assertIn(cancel["status"], ("running", "cancelled", "completed"))
        if cancel["status"] == "running":
            self.assertFalse(cancel.get("cancellation", {}).get("safe_state_achieved", False))
            self.assertTrue(cancel.get("x-vendor", {}).get("cancellation_pending", False))
        final = self._wait_final(op_id)
        after = self.client.read("world", device_id=self.device_id)["state"]["tick"]
        if final.get("status") == "cancelled":
            self.assertEqual(after, before, "cancelled worker must not apply its effect")
        else:
            self.assertEqual(final.get("status"), "completed")
            self.assertEqual(after, before + 1, "completed worker's effect must be visible")

    def test_non_cooperative_cancel_reports_pending_running(self):
        # This case exercises an admitted cancellation that the worker ignores.
        # Declare that contract before admission; omitted/false is a refusal.
        binding = self.server.devices[self.device_id].capability("cap.test.block.v1", "world")
        binding.constraints = {**(binding.constraints or {}), "cancellable": True}
        self.assertTrue(binding.cancellable)
        running = self.client.invoke(
            "cap.test.block.v1", {"ms": 350}, device_id=self.device_id,
            session_id=self.session, deadline_ms=80,
        )
        op_id = running.get("operation_id")
        self.assertTrue(op_id)
        cancel = self.client.request(
            Method.OPERATIONS_CANCEL,
            {"session_id": self.session, "operation_id": op_id, "deadline_ms": 10},
        )
        self.assertEqual(cancel["status"], "running")
        self.assertFalse(cancel["cancellation"]["safe_state_achieved"])
        self.assertTrue(cancel["x-vendor"]["cancellation_pending"])
        final = self._wait_final(op_id)
        self.assertEqual(final["status"], "completed")


class DeadlineTests(unittest.TestCase):
    """PROTO-010/011: deadlines are mandatory and enforced for every blocking call."""

    def setUp(self):
        self.server, self.handle, self.client, self.device_id = _server_client()
        self.session = self.client.open_session(
            [self.device_id], capabilities=None, mode="simulated", ttl_s=300
        )["session_id"]

    def tearDown(self):
        self.client.close()
        self.handle.shutdown()

    def test_missing_deadline_is_rejected(self):
        with self.assertRaises(MHSError) as ctx:
            self.client.request(
                Method.COMMAND,
                {"session_id": self.session, "device_id": self.device_id,
                 "capability_id": "cap.world.step.v1", "input": {"ticks": 1},
                 "command_id": canonical.ulid()},
            )
        self.assertEqual(ctx.exception.code, "MHS.PROTOCOL.DEADLINE_INVALID")

    def test_over_budget_command_returns_unknown_not_late_completion(self):
        started = time.monotonic()
        receipt = self.client.invoke(
            "cap.test.block.v1", {"ms": 900}, device_id=self.device_id,
            session_id=self.session, deadline_ms=50,
        )
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 0.6, "request must not wait for the full command")
        self.assertEqual(receipt["status"], "unknown")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.OUTCOME.TIMEOUT")
        self.assertIn("operation_id", receipt)


class SubscriptionBoundTests(unittest.TestCase):
    """PROTO-005: queues and subscription counts are bounded."""

    def setUp(self):
        self.server, self.handle, self.client, self.device_id = _server_client()
        self.session = self.client.open_session(
            [self.device_id], capabilities=None, mode="simulated", ttl_s=300
        )["session_id"]

    def tearDown(self):
        self.client.close()
        self.handle.shutdown()

    def test_queue_is_bounded_and_gaps_are_coalesced(self):
        subscription_id = self.client.subscribe(
            ["state"], device_id=self.device_id, session_id=self.session
        )
        self.server._subscriptions[subscription_id]["max_buffer"] = 16
        for _ in range(200):
            self.server._notify("state", self.device_id, {"revision": 1})
        events = self.server._subscriptions[subscription_id]["events"]
        self.assertLessEqual(len(events), 16)
        self.assertGreater(self.server._subscriptions[subscription_id]["dropped"], 0)
        gap_events = [
            event for event in events
            if getattr(event, "params", {}).get("type") == "gap"
        ]
        self.assertLessEqual(len(gap_events), 1, "gap ranges must coalesce")

    def test_per_session_subscription_limit(self):
        for _ in range(64):
            self.client.subscribe(["state"], device_id=self.device_id, session_id=self.session)
        with self.assertRaises(MHSError) as ctx:
            self.client.subscribe(["state"], device_id=self.device_id, session_id=self.session)
        self.assertEqual(ctx.exception.code, "MHS.LIMIT.SUBSCRIPTION_LIMIT")


class ResponseCorrelationTests(unittest.TestCase):
    """PROTO-006: a client must not accept a response for another request."""

    def _serve(self, body):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 - stdlib handler API
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(length)
                payload = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, f"http://127.0.0.1:{server.server_address[1]}"

    def test_wrong_id_or_version_is_rejected(self):
        for body in (
            {"jsonrpc": "2.0", "id": "other-request", "result": {}},
            {"jsonrpc": "1.0", "id": 0, "result": {}},
        ):
            server, url = self._serve(body)
            try:
                # connect() negotiates hello through the same request path, so a
                # foreign response must already be rejected there.
                with self.assertRaises(MHSError) as ctx:
                    connect(url)
                self.assertEqual(ctx.exception.code, "MHS.TRANSPORT.PROTOCOL_ERROR")
            finally:
                server.shutdown()


class EnvelopeTests(unittest.TestCase):
    """PROTO-006: strict JSON-RPC envelope, ids, notifications and versions."""

    def setUp(self):
        self.server, self.handle, self.client, self.device_id = _server_client()

    def tearDown(self):
        self.client.close()
        self.handle.shutdown()

    def test_bad_envelopes_are_rejected(self):
        for payload in (
            {"id": "1", "method": "mhs.hello", "params": {}},
            {"jsonrpc": "1.0", "id": "1", "method": "mhs.hello", "params": {}},
            {"jsonrpc": "2.0", "id": True, "method": "mhs.hello", "params": {}},
        ):
            response = self.server.handle(payload)
            if hasattr(response, "to_dict"):
                response = response.to_dict()
            self.assertIsNotNone(response)
            self.assertEqual(
                (response.get("error") or {}).get("code"), -32600,
                f"expected INVALID_REQUEST for {payload!r}: {response}",
            )

    def test_notification_errors_have_no_response(self):
        response = self.server.handle({"jsonrpc": "1.0", "method": "mhs.command", "params": {}})
        self.assertIsNone(response)

    def test_version_negotiation_requires_a_common_version(self):
        with self.assertRaises(MHSError) as ctx:
            self.client.request(
                Method.HELLO, {"client": {"name": "t", "version": "1"},
                               "protocol_versions": ["99.0"]}
            )
        self.assertEqual(ctx.exception.code, "MHS.PROTOCOL.VERSION_UNSUPPORTED")

    def test_operations_require_hello_first(self):
        server = _device_server.build_server()
        try:
            response = server.handle({
                "jsonrpc": "2.0", "id": "1", "method": "mhs.devices.list", "params": {},
            })
            if hasattr(response, "to_dict"):
                response = response.to_dict()
            self.assertEqual(
                (response.get("error") or {}).get("code"), -32600, str(response)
            )
        finally:
            close = getattr(server, "close", None)
            if callable(close):
                close()


if __name__ == "__main__":
    unittest.main()
