"""HTTP binding, SSE notifications, well-known discovery and the ``mhs`` CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mhs import canonical, connect
from mhs.errors import MHSError
from mhs.reference import build_endpoint, build_server
from mhs.schema import SchemaStore
from mhs.server import SessionManager, SubscriptionHub

REPO = Path(__file__).resolve().parents[4]
PYTHONPATH = str(REPO / "MHS" / "sdk" / "src")


class HttpBindingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = build_endpoint(
            "conveyor", endpoint_id="mhs://127.0.0.1:7400", test_profile=True
        )
        cls.server = build_server(cls.spec, log_ready=False)
        cls.handle = cls.server.start_http("127.0.0.1", 0)
        cls.url = cls.handle.url
        cls.store = SchemaStore()
        cls.client = connect(cls.url)
        cls.hello = cls.client.hello()
        cls.device_id = cls.client.devices()[0]["device_id"]
        cls.session = cls.client.open_session(
            [cls.device_id], capabilities=None, mode="simulated", ttl_s=300
        )

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.close()
        finally:
            cls.handle.shutdown()
            cls.spec.close()

    def _step(self, ticks=1, **kwargs):
        return self.client.invoke("cap.world.step.v1", {"ticks": ticks},
                                  device_id=self.device_id, **kwargs)

    def test_well_known_descriptor(self):
        with urllib.request.urlopen(self.url + "/.well-known/mhs.json", timeout=5) as response:
            descriptor = json.loads(response.read())
        self.assertEqual(self.store.validate(descriptor, "endpoint-descriptor.schema.json"), [])
        self.assertEqual(descriptor["mhs_version"], "1.0")
        self.assertIn(self.device_id, descriptor["devices"])
        self.assertEqual(descriptor["transports"]["http"], "/mhs/v1/rpc")
        self.assertIn("MHS.SAFETY.NOT_CERTIFIED", descriptor["features"])

    def test_schema_http_route(self):
        with urllib.request.urlopen(self.url + "/mhs/v1/schema/device.schema.json", timeout=5) as response:
            schema = json.loads(response.read())
        from mhs import _ids

        self.assertEqual(schema["$id"], _ids.SCHEMA_BASE + "device.schema.json")
        self.assertEqual(schema["title"], "OpenMHS device manifest")
        # Unknown schema refs are a 404 with a JSON error body.
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.url + "/mhs/v1/schema/no-such.schema.json", timeout=5)
        self.assertEqual(ctx.exception.code, 404)
        ctx.exception.close()

    def test_http_roundtrip_read_and_invoke(self):
        self.assertEqual(self.hello["mhs_version"], "1.0")
        self.assertEqual(self.client.read("workcell", device_id=self.device_id)["revision"],
                         self.client.read("workcell", device_id=self.device_id)["revision"])
        receipt = self._step(2)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(
            receipt["state_hash_after"],
            self.client.read("workcell", device_id=self.device_id)["state_hash"],
        )

    def test_sse_two_subscriptions_are_independent(self):
        first = self.client.subscribe(["state"], device_id=self.device_id)
        second = self.client.subscribe(["state"], device_id=self.device_id)
        try:
            self._step(1)
            events_first = self.client.events(first, timeout=3.0)
            events_second = self.client.events(second, timeout=3.0)
            first_ids = {(event.get("params") or {}).get("subscription_id")
                         for event in events_first if event.get("method") == "mhs.event"}
            second_ids = {(event.get("params") or {}).get("subscription_id")
                          for event in events_second if event.get("method") == "mhs.event"}
            self.assertIn(first, first_ids)
            self.assertIn(second, second_ids)
            self.assertNotIn(second, first_ids)
            self.assertNotIn(first, second_ids)
        finally:
            self.client.unsubscribe(first)
            self.client.unsubscribe(second)

    def test_subscription_gap_event_is_explicit(self):
        subscription = self.client.subscribe(["state"], device_id=self.device_id)
        try:
            # Force the server's bounded per-subscription buffer to overflow.
            self.server._subscriptions[subscription]["max_buffer"] = 2  # noqa: SLF001
            for _ in range(4):
                self._step(1)
            events = self.client.events(subscription, timeout=3.0)
            gaps = [
                event for event in events
                if (event.get("params") or {}).get("stream") == "control"
                and (event.get("params") or {}).get("type") == "gap"
            ]
            self.assertTrue(gaps, "a dropped sample must produce an explicit gap event")
            sequences = [(event.get("params") or {}).get("seq") for event in events]
            self.assertEqual(sequences, sorted(sequences))
            self.assertIn("from", gaps[0]["params"])
            self.assertIn("to", gaps[0]["params"])
        finally:
            self.client.unsubscribe(subscription)

    def test_http_batch(self):
        results = self.client.batch([
            {"method": "mhs.devices.list", "params": {"detail": "summary"}},
            {"method": "mhs.safety.status",
             "params": {"device_id": self.device_id, "deadline_ms": 1000}},
        ])
        self.assertTrue(all(item["ok"] for item in results))
        self.assertEqual(results[0]["result"]["count"], 1)

    def test_session_and_subscription_facades(self):
        manager = SessionManager(self.server)
        self.assertGreaterEqual(len(manager), 1)
        session = manager.require(self.session["session_id"])
        self.assertEqual(session.mode, "simulated")
        heartbeat = manager.heartbeat(self.session["session_id"])
        self.assertIn("expires_at", heartbeat)
        hub = SubscriptionHub(self.server)
        subscription = hub.subscribe(session, ["state"], device_id=self.device_id)
        self.assertTrue(subscription["subscription_id"].startswith("sub_"))
        self.assertIn("seq_start", subscription)
        hub.unsubscribe(session, subscription["subscription_id"])

    def test_evidence_over_http(self):
        bundle = self.client.export_evidence()
        report = self.client.verify_evidence(bundle)
        self.assertTrue(report["valid"], report.get("errors"))
        for receipt in bundle["receipts"]:
            self.assertEqual(self.store.validate(receipt, "receipt.schema.json"), [])


class CliSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = build_endpoint("conveyor", endpoint_id="mhs://127.0.0.1:7400", test_profile=True)
        cls.server = build_server(cls.spec, log_ready=False)
        cls.handle = cls.server.start_http("127.0.0.1", 0)
        cls.url = cls.handle.url
        env = dict(os.environ)
        env["PYTHONPATH"] = PYTHONPATH + os.pathsep + env.get("PYTHONPATH", "")
        cls.env = env

    @classmethod
    def tearDownClass(cls):
        cls.handle.shutdown()
        cls.spec.close()

    def _cli(self, *args, timeout=30):
        return subprocess.run(
            [sys.executable, "-m", "mhs.cli", *args],
            cwd=str(REPO),
            env=self.env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def test_devices_json(self):
        result = self._cli("devices", "--endpoint", self.url, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        devices = payload.get("devices") or []
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["mode"], "simulated")
        self.assertTrue(devices[0]["capabilities"])

    def test_read_and_call(self):
        read = self._cli("read", "workcell", "--endpoint", self.url, "--json")
        self.assertEqual(read.returncode, 0, read.stderr)
        state = json.loads(read.stdout)
        self.assertIn("state_hash", state)
        call = self._cli(
            "call", "--endpoint", self.url, "--capability", "cap.world.step.v1",
            "--input", '{"ticks": 1}', "--json",
        )
        self.assertEqual(call.returncode, 0, call.stderr)
        receipt = json.loads(call.stdout)
        self.assertEqual(receipt["status"], "completed")

    def test_evidence_and_version(self):
        evidence = self._cli("evidence", "--endpoint", self.url, "--verify")
        self.assertEqual(evidence.returncode, 0, evidence.stderr)
        report = json.loads(evidence.stdout)
        self.assertTrue(report["valid"])
        version = self._cli("version")
        self.assertEqual(version.returncode, 0)
        self.assertIn("protocol 1.0", version.stdout)

    def test_stdio_endpoint_target(self):
        # The CLI can launch a local stdio endpoint from a comma-separated argv.
        target = "stdio:" + ",".join([sys.executable, "-m", "mhs.reference", "conveyor", "--stdio"])
        result = self._cli("hello", "--endpoint", target, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["mhs_version"], "1.0")


class HttpErrorTest(unittest.TestCase):
    """A dead endpoint must surface a bounded timeout, never hang."""

    def test_client_timeout(self):
        class SlowHandler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                time.sleep(1.5)
                body = b'{"jsonrpc":"2.0","id":null,"result":{}}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
        port = server.server_address[1]
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            started = time.monotonic()
            # PROTO-013: connect() negotiates hello, so the timeout surfaces at
            # connect time; it must not hang and must be a transport/outcome code.
            with self.assertRaises(MHSError) as ctx:
                connect(f"http://127.0.0.1:{port}", timeout=0.2)
            elapsed = time.monotonic() - started
            self.assertLess(elapsed, 1.2)
            self.assertIn(ctx.exception.code, ("MHS.OUTCOME.TIMEOUT", "MHS.TRANSPORT.TIMEOUT"))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
