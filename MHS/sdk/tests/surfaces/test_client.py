"""Client receipts, transport errors, device handles and close (WP-08 item 2).

Findings: SDK-14 (silent rejected receipts, lost command_id on timeout, no
keepalive, one session per client), TESTS-09 (close() stalls ~15 s after a
subscription), TESTS-10 (connection refused reported as OUTCOME.TIMEOUT),
SURF-03 / codefile.py (a second device overwrites the client's session).
"""

from __future__ import annotations

import json
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mhs import canonical, connect
from mhs.client import DeviceHandle, MHSClient, MHSRejected, Receipt, StdioTransport
from mhs.errors import MHSError

from tests.surfaces import _support as s


class ReceiptTests(unittest.TestCase):
    def test_ok_and_raise_for_status(self) -> None:
        completed = Receipt({"status": "completed", "receipt_id": "r1"})
        self.assertTrue(completed.ok)
        self.assertIs(completed.raise_for_status(), completed)
        running = Receipt({"status": "running", "operation_id": "op_1"})
        self.assertFalse(running.ok)
        self.assertIs(running.raise_for_status(), running)
        rejected = Receipt({"status": "rejected", "command_id": "c1", "capability_id": "cap.world.step.v1",
                            "error": {"mhs_code": "MHS.SAFETY.ENVELOPE_VIOLATION", "message": "ticks too large",
                                      "retryable": False, "details": {"path": "ticks"}}})
        with self.assertRaises(MHSRejected) as caught:
            rejected.raise_for_status()
        self.assertEqual(caught.exception.code, "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertIs(caught.exception.receipt, rejected)
        self.assertEqual(caught.exception.status, "rejected")
        self.assertEqual(caught.exception.data["command_id"], "c1")
        self.assertEqual(caught.exception.data["details"], {"path": "ticks"})
        self.assertIsInstance(caught.exception, MHSError)
        with self.assertRaises(MHSRejected) as unknown:
            Receipt({"status": "unknown"}).raise_for_status()
        self.assertEqual(unknown.exception.code, "MHS.OUTCOME.UNKNOWN")
        self.assertEqual(json.loads(json.dumps(rejected)), dict(rejected))

    def test_invoke_check_is_opt_in(self) -> None:
        spec, server = s.reference("conveyor")
        self.addCleanup(spec.close)
        client = s.client(server)
        client.open_session([s.CONVEYOR])
        receipt = client.invoke("cap.world.step.v1", {"ticks": 999999}, device_id=s.CONVEYOR)
        self.assertIsInstance(receipt, Receipt)
        self.assertFalse(receipt.ok)
        self.assertEqual(receipt.code, "MHS.SAFETY.ENVELOPE_VIOLATION")
        with self.assertRaises(MHSRejected) as caught:
            client.invoke("cap.world.step.v1", {"ticks": 999999}, device_id=s.CONVEYOR, check=True)
        self.assertEqual(caught.exception.receipt["status"], "rejected")
        self.assertTrue(client.invoke("cap.world.step.v1", {"ticks": 1}, device_id=s.CONVEYOR, check=True).ok)

    def test_wait_follows_an_unknown_receipt_to_its_final_one(self) -> None:
        spec, server = s.reference("conveyor", test_profile=True)
        self.addCleanup(spec.close)
        client = s.client(server)
        client.open_session([s.CONVEYOR])
        unknown = client.invoke("x-cap.mhs-test.delay.v1", {"ms": 400}, device_id=s.CONVEYOR, deadline_ms=50)
        self.assertEqual(unknown["status"], "unknown")
        final = client.wait(unknown["operation_id"], timeout=5)
        self.assertEqual(final.status, "completed")
        waited = client.invoke("x-cap.mhs-test.delay.v1", {"ms": 200}, device_id=s.CONVEYOR, deadline_ms=20,
                               wait=True)
        self.assertEqual(waited.status, "completed")
        with self.assertRaises(MHSError) as caught:
            pending = client.invoke("x-cap.mhs-test.delay.v1", {"ms": 1500}, device_id=s.CONVEYOR, deadline_ms=20)
            client.wait(pending["operation_id"], timeout=0.1)
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.TIMEOUT")
        self.assertTrue(caught.exception.data["may_have_effect"])


class _HelloOnly(BaseHTTPRequestHandler):
    """Answers mhs.hello; every other request gets no answer before the client gives up."""

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        message = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
        if message.get("method") != "mhs.hello":
            time.sleep(2.0)
            return
        body = json.dumps({"jsonrpc": "2.0", "id": message["id"],
                           "result": {"endpoint_id": "mhs://slow", "mhs_version": "1.0"}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        return


class TransportErrorTests(unittest.TestCase):
    def test_connection_refused_is_unavailable_and_retryable(self) -> None:
        port = s.free_port()
        started = time.monotonic()
        with self.assertRaises(MHSError) as caught:
            connect(f"http://127.0.0.1:{port}")
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(caught.exception.code, "MHS.TRANSPORT.UNAVAILABLE")
        self.assertTrue(caught.exception.retryable)
        self.assertFalse(caught.exception.data["may_have_effect"])

    def test_dns_failure_is_unavailable(self) -> None:
        with self.assertRaises(MHSError) as caught:
            connect("http://openmhs-no-such-host.invalid:7400", timeout=5)
        self.assertEqual(caught.exception.code, "MHS.TRANSPORT.UNAVAILABLE")

    def test_a_stdio_command_that_does_not_start_is_unavailable(self) -> None:
        with self.assertRaises(MHSError) as caught:
            StdioTransport(["/nonexistent/openmhs-endpoint"])
        self.assertEqual(caught.exception.code, "MHS.TRANSPORT.UNAVAILABLE")

    def test_post_send_timeout_carries_the_command_id(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _HelloOnly)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        client = connect(f"http://127.0.0.1:{server.server_address[1]}")
        command_id = canonical.ulid()
        with self.assertRaises(MHSError) as caught:
            client.invoke("cap.world.step.v1", {"ticks": 1}, session_id="mhs_s_x", command_id=command_id,
                          deadline_ms=100)
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.TIMEOUT")
        self.assertEqual(caught.exception.data["command_id"], command_id)
        self.assertTrue(caught.exception.data["may_have_effect"])
        self.assertFalse(caught.exception.retryable)
        with self.assertRaises(MHSError) as generated:
            client.invoke("cap.world.step.v1", {"ticks": 1}, session_id="mhs_s_x", deadline_ms=100)
        self.assertTrue(canonical.is_ulid(generated.exception.data["command_id"]))
        with self.assertRaises(MHSError) as read:
            client.request("mhs.devices.list", {}, timeout_s=0.3)
        self.assertEqual(read.exception.code, "MHS.OUTCOME.TIMEOUT")
        self.assertFalse(read.exception.data["may_have_effect"])

    def test_stdio_timeout_carries_the_command_id(self) -> None:
        silent = [sys.executable, "-c", "import sys\nfor _ in sys.stdin: pass"]
        client = MHSClient(StdioTransport(silent, timeout=0.3))
        self.addCleanup(client.transport.close)
        with self.assertRaises(MHSError) as caught:
            client.invoke("cap.world.step.v1", {"ticks": 1}, session_id="mhs_s_x", command_id=canonical.ulid(),
                          deadline_ms=10)
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.TIMEOUT")
        self.assertTrue(canonical.is_ulid(caught.exception.data["command_id"]))
        self.assertTrue(caught.exception.data["may_have_effect"])


class DeviceHandleTests(unittest.TestCase):
    def test_each_handle_owns_its_session(self) -> None:
        spec, server = s.reference("lab")
        self.addCleanup(spec.close)
        client = s.client(server)
        ids = [device["device_id"] for device in client.devices()]
        handles = [client.device(device_id) for device_id in ids]
        for handle in handles:
            self.assertIsInstance(handle, DeviceHandle)
            handle.read()
        sessions = [handle.session_id for handle in handles]
        self.assertEqual(len(set(sessions)), len(ids))
        self.assertIsNone(client.session_id)
        for handle, device_id in zip(handles, ids):
            self.assertEqual(server._sessions[handle.session_id].device_ids, [device_id])
        handles[0].close()
        self.assertNotIn(sessions[0], server._sessions)
        self.assertIsNotNone(server._sessions.get(sessions[1]))

    def test_handle_invoke_check_heartbeat_and_lapse(self) -> None:
        spec, server = s.reference("conveyor")
        self.addCleanup(spec.close)
        client = s.client(server)
        with client.device(s.CONVEYOR, check=True) as conveyor:
            self.assertEqual(conveyor.invoke("cap.world.step.v1", {"ticks": 1}).status, "completed")
            with self.assertRaises(MHSRejected):
                conveyor.invoke("cap.world.step.v1", {"ticks": 999999})
            self.assertEqual(len(conveyor.receipts), 2)
            conveyor._renew_at = 0.0
            mark = len(client.transport.methods)
            conveyor.invoke("cap.world.step.v1", {"ticks": 1})
            self.assertEqual(client.transport.methods[mark:], ["mhs.session.heartbeat", "mhs.command"])
            old = conveyor.session_id
            s.age_sessions(server)
            conveyor._renew_at = 0.0
            with self.assertRaises(MHSError) as caught:
                conveyor.invoke("cap.world.step.v1", {"ticks": 1})
            self.assertEqual(caught.exception.code, "MHS.SESSION.EXPIRED")
            self.assertIsNone(conveyor.session_id)
            self.assertEqual(conveyor.invoke("cap.world.step.v1", {"ticks": 1}).status, "completed")
            self.assertNotEqual(conveyor.session_id, old)
            self.assertEqual(conveyor.estop("handle stop").status, "completed")

    def test_estop_needs_no_session(self) -> None:
        spec, server = s.reference("conveyor")
        self.addCleanup(spec.close)
        client = s.client(server)
        self.assertIsNone(client.session_id)
        receipt = client.estop("no session", device_id=s.CONVEYOR)
        self.assertEqual(receipt.status, "completed")
        self.assertTrue(receipt["output"]["latched"])


class CloseTests(unittest.TestCase):
    def test_close_after_a_subscription_does_not_stall(self) -> None:
        spec, server = s.reference("conveyor")
        self.addCleanup(spec.close)
        handle = server.start_http("127.0.0.1", 0)
        self.addCleanup(handle.shutdown)
        client = connect(handle.url)
        client.open_session([s.CONVEYOR], ttl_s=60)
        subscription = client.subscribe(["state"], device_id=s.CONVEYOR)
        client.invoke("cap.world.step.v1", {"ticks": 1}, device_id=s.CONVEYOR)
        events = client.events(subscription, timeout=3.0)
        self.assertTrue(events, "the SSE stream carries the session's events")
        started = time.monotonic()
        client.close()
        self.assertLess(time.monotonic() - started, 1.0)

    def test_transport_close_with_a_live_session_does_not_stall(self) -> None:
        # client.close() closes the session first, and the endpoint then ends the SSE stream by itself; here the
        # session stays open, so only the transport's socket shutdown can unblock the stream reader at once
        spec, server = s.reference("conveyor")
        self.addCleanup(spec.close)
        handle = server.start_http("127.0.0.1", 0)
        self.addCleanup(handle.shutdown)
        client = connect(handle.url)
        session = client.open_session([s.CONVEYOR], ttl_s=60)
        self.addCleanup(lambda: connect(handle.url).close_session(session["session_id"]))
        subscription = client.subscribe(["state"], device_id=s.CONVEYOR)
        client.invoke("cap.world.step.v1", {"ticks": 1}, device_id=s.CONVEYOR)
        self.assertTrue(client.events(subscription, timeout=3.0), "the SSE stream carries the session's events")
        started = time.monotonic()
        client.transport.close()
        self.assertLess(time.monotonic() - started, 1.0)


if __name__ == "__main__":
    unittest.main()
