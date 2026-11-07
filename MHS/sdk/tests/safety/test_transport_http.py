"""HTTP transport hardening (WP-04 4a2; findings SDK-04, SDK-05, SDK-08).

Ports of the review repros ``sdk-core-verify/hostcheck.py`` (foreign Host and
Origin accepted), ``sdk-core/e5.py`` / ``sdk-core-verify/v5.py`` (one SSE stream
drained every session's subscriptions; session.open accepted without a
Content-Type), ``sdk-core/e6.py`` / ``v6.py`` (NaN input, an effectful command
sent as a notification) and the SDK-05 schema-route file read.
"""

from __future__ import annotations

import http.client
import json
import re
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import warnings
from pathlib import Path
from typing import Any

from mhs import canonical
from mhs.errors import MHSError
from mhs.reference import build_endpoint, build_server

STEP = "cap.world.step.v1"


def _conveyor(**server_kwargs: Any):
    spec = build_endpoint("conveyor", endpoint_id="mhs://localhost/http-test", test_profile=True)
    server = build_server(spec, log_ready=False)
    for key, value in server_kwargs.items():
        setattr(server, key, value)
    return spec, server


class HttpFixture(unittest.TestCase):
    server_kwargs: dict[str, Any] = {}

    def setUp(self) -> None:
        self.spec, self.server = self.make_server()
        self.handle = self.server.start_http("127.0.0.1", 0)
        self.addCleanup(self.spec.close)
        self.addCleanup(self.handle.shutdown)
        self.port = self.handle.port
        self.url = self.handle.url
        self.rpc("mhs.hello", protocol_versions=["1.0"])

    def make_server(self):
        return _conveyor()

    # -- raw HTTP helpers ------------------------------------------------
    def request(self, method: str, path: str, *, body: bytes | None = None,
                headers: dict[str, str] | None = None, skip_host: bool = False,
                timeout: float = 5.0) -> tuple[int, dict[str, str], bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            merged = {"Host": f"127.0.0.1:{self.port}"}
            if skip_host:
                merged.pop("Host")
            merged.update(headers or {})
            for key, value in merged.items():
                connection.putheader(key, value)
            if body is not None:
                connection.putheader("Content-Length", str(len(body)))
            connection.endheaders(body)
            response = connection.getresponse()
            return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
        finally:
            connection.close()

    def post(self, message: Any, *, headers: dict[str, str] | None = None,
             raw: bytes | None = None, **kwargs: Any) -> tuple[int, dict[str, str], Any]:
        merged = {"Content-Type": "application/json"}
        merged.update(headers or {})
        body = raw if raw is not None else json.dumps(message).encode()
        status, response_headers, data = self.request("POST", "/mhs/v1/rpc", body=body,
                                                      headers=merged, **kwargs)
        try:
            payload = json.loads(data) if data else None
        except json.JSONDecodeError:
            payload = data
        return status, response_headers, payload

    def rpc(self, method: str, **params: Any) -> dict[str, Any]:
        status, _headers, payload = self.post(
            {"jsonrpc": "2.0", "id": canonical.ulid(), "method": method, "params": params})
        self.assertEqual(status, 200, payload)
        if "error" in payload:
            raise MHSError(payload["error"]["data"]["mhs_code"], payload["error"]["message"])
        return payload["result"]


def _sse_open(port: int, path: str, timeout: float = 5.0) -> tuple[int, Any, socket.socket]:
    """Open an SSE stream; return (status, file, socket)."""
    sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    sock.sendall((f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                  "Accept: text/event-stream\r\n\r\n").encode())
    stream = sock.makefile("rb")
    status_line = stream.readline().decode()
    status = int(status_line.split()[1])
    while True:
        line = stream.readline()
        if line in (b"\r\n", b"\n", b""):
            break
    return status, stream, sock


class _SseReader:
    def __init__(self, port: int, path: str) -> None:
        self.status, self._stream, self._sock = _sse_open(port, path)
        self.frames: list[list[str]] = []
        self._lock = threading.Lock()
        if self.status == 200:
            threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        current: list[str] = []
        try:
            for raw in self._stream:
                line = raw.decode().rstrip("\r\n")
                if not line:
                    if current:
                        with self._lock:
                            self.frames.append(current)
                    current = []
                    continue
                current.append(line)
        except (OSError, ValueError):
            return

    def events(self) -> list[dict[str, Any]]:
        out = []
        with self._lock:
            frames = list(self.frames)
        for frame in frames:
            for line in frame:
                if line.startswith("data:"):
                    out.append(json.loads(line[5:].strip()))
        return out

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass


class HostAndOriginTests(HttpFixture):
    def test_hostcheck_foreign_host_is_refused(self) -> None:
        before = len(self.server._sessions)
        status, _headers, payload = self.post(
            {"jsonrpc": "2.0", "id": 1, "method": "mhs.session.open", "params": {"mode": "simulated"}},
            headers={"Host": f"evil.example.com:{self.port}", "Origin": "http://evil.example.com"})
        self.assertEqual(status, 403, payload)
        self.assertNotIn("result", payload or {})
        self.assertEqual(payload["error"]["data"]["mhs_code"], "MHS.AUTH.FORBIDDEN")
        self.assertEqual(len(self.server._sessions), before, "a session was opened")
        status, _headers, _body = self.request("GET", "/.well-known/mhs.json",
                                               headers={"Host": "rebind.attacker.test"})
        self.assertEqual(status, 403)

    def test_missing_host_is_refused(self) -> None:
        status, _headers, _payload = self.post(
            {"jsonrpc": "2.0", "id": 1, "method": "mhs.devices.list", "params": {}}, skip_host=True)
        self.assertEqual(status, 403)

    def test_loopback_hosts_are_accepted(self) -> None:
        for host in (f"127.0.0.1:{self.port}", f"localhost:{self.port}", f"[::1]:{self.port}",
                     "localhost", "LOCALHOST"):
            with self.subTest(host):
                status, _headers, payload = self.post(
                    {"jsonrpc": "2.0", "id": 1, "method": "mhs.devices.list", "params": {}},
                    headers={"Host": host})
                self.assertEqual(status, 200, payload)
                self.assertIn("result", payload)

    def test_foreign_origin_is_refused(self) -> None:
        for origin in ("http://evil.example.com", "null", f"http://evil.example.com:{self.port}",
                       "http://127.0.0.1:1"):
            with self.subTest(origin):
                status, _headers, payload = self.post(
                    {"jsonrpc": "2.0", "id": 1, "method": "mhs.devices.list", "params": {}},
                    headers={"Origin": origin})
                self.assertEqual(status, 403, payload)
                self.assertEqual(payload["error"]["data"]["mhs_code"], "MHS.AUTH.FORBIDDEN")

    def test_same_origin_is_accepted(self) -> None:
        for origin in (f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"):
            with self.subTest(origin):
                status, _headers, payload = self.post(
                    {"jsonrpc": "2.0", "id": 1, "method": "mhs.devices.list", "params": {}},
                    headers={"Origin": origin})
                self.assertEqual(status, 200, payload)


class ConfiguredAllowlistTests(HttpFixture):
    def make_server(self):
        spec = build_endpoint("conveyor", endpoint_id="mhs://localhost/http-test", test_profile=True)
        devices = build_server(spec, log_ready=False)
        from mhs.server import MHSServer

        server = MHSServer(devices.endpoint_id, list(devices.devices.values()), log_ready=False,
                           allowed_hosts=["mhs.lab.internal"],
                           allowed_origins=["https://console.lab.internal"])
        return spec, server

    def test_configured_host_and_origin_are_accepted(self) -> None:
        status, _headers, payload = self.post(
            {"jsonrpc": "2.0", "id": 1, "method": "mhs.devices.list", "params": {}},
            headers={"Host": "mhs.lab.internal:8443", "Origin": "https://console.lab.internal"})
        self.assertEqual(status, 200, payload)
        status, _headers, payload = self.post(
            {"jsonrpc": "2.0", "id": 1, "method": "mhs.devices.list", "params": {}},
            headers={"Host": "other.lab.internal"})
        self.assertEqual(status, 403, payload)


class ContentTypeTests(HttpFixture):
    def test_content_type_must_be_application_json(self) -> None:
        message = {"jsonrpc": "2.0", "id": 1, "method": "mhs.session.open",
                   "params": {"principal": {"id": "human:alice", "kind": "human"}}}
        before = len(self.server._sessions)
        for content_type in (None, "", "application/x-www-form-urlencoded", "text/plain",
                             "multipart/form-data"):
            with self.subTest(content_type):
                headers = {} if content_type is None else {"Content-Type": content_type}
                body = json.dumps(message).encode()
                status, _h, data = self.request("POST", "/mhs/v1/rpc", body=body, headers=headers)
                payload = json.loads(data)
                self.assertEqual(status, 415, payload)
                self.assertEqual(payload["error"]["data"]["mhs_code"], "MHS.PROTOCOL.INVALID_REQUEST")
        self.assertEqual(len(self.server._sessions), before, "e5: a session opened without Content-Type")
        status, _h, payload = self.post(message, headers={"Content-Type": "application/json; charset=utf-8"})
        self.assertEqual(status, 200, payload)
        self.assertIn("session_id", payload["result"])

    def test_get_on_the_rpc_path_is_405(self) -> None:
        status, _headers, _body = self.request("GET", "/mhs/v1/rpc")
        self.assertEqual(status, 405)


class AuthTokenTests(HttpFixture):
    def make_server(self):
        spec = build_endpoint("conveyor", endpoint_id="mhs://localhost/http-test", test_profile=True)
        devices = build_server(spec, log_ready=False)
        from mhs.server import MHSServer

        server = MHSServer(devices.endpoint_id, list(devices.devices.values()), log_ready=False,
                           auth_tokens={"s3cret-token": {"id": "operator:ada", "kind": "operator"}})
        return spec, server

    def setUp(self) -> None:
        self._auth = {"Authorization": "Bearer s3cret-token"}
        super().setUp()

    def post(self, message: Any, *, headers: dict[str, str] | None = None, **kwargs: Any):
        merged = dict(self._auth)
        merged.update(headers or {})
        return super().post(message, headers=merged, **kwargs)

    def test_requests_need_a_valid_bearer_token(self) -> None:
        message = {"jsonrpc": "2.0", "id": 1, "method": "mhs.devices.list", "params": {}}
        for label, auth in (("missing", None), ("wrong", "Bearer nope"), ("scheme", "Basic s3cret-token")):
            with self.subTest(label):
                headers = {"Content-Type": "application/json"}
                if auth:
                    headers["Authorization"] = auth
                status, response_headers, data = self.request(
                    "POST", "/mhs/v1/rpc", body=json.dumps(message).encode(), headers=headers)
                self.assertEqual(status, 401)
                self.assertEqual(response_headers.get("www-authenticate"), "Bearer")
                self.assertNotIn(b"s3cret-token", data)
                self.assertEqual(json.loads(data)["error"]["data"]["mhs_code"], "MHS.AUTH.UNAUTHENTICATED")
        status, _headers, payload = self.post(message)
        self.assertEqual(status, 200, payload)

    def test_well_known_is_public_and_advertises_bearer(self) -> None:
        status, _headers, body = self.request("GET", "/.well-known/mhs.json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["auth"], ["bearer"])
        status, _headers, _body = self.request("GET", "/mhs/v1/schema/device.schema.json")
        self.assertEqual(status, 401)
        status, _headers, _body = self.request("GET", "/mhs/v1/schema/device.schema.json", headers=self._auth)
        self.assertEqual(status, 200)


class BindTests(unittest.TestCase):
    """Non-loopback binds need auth tokens or an explicit insecure_dev opt-in."""

    def _server(self, **kwargs: Any):
        spec = build_endpoint("conveyor", endpoint_id="mhs://localhost/bind-test")
        self.addCleanup(spec.close)
        devices = build_server(spec, log_ready=False)
        from mhs.server import MHSServer

        return MHSServer(devices.endpoint_id, list(devices.devices.values()), log_ready=False, **kwargs)

    def test_non_loopback_bind_is_refused_without_tokens(self) -> None:
        server = self._server()
        for host in ("0.0.0.0", "::", "", "192.168.1.20", "lab-host.example.com"):
            with self.subTest(host):
                with self.assertRaises(MHSError) as ctx:
                    server.start_http(host, 0)
                self.assertEqual(ctx.exception.code, "MHS.AUTH.TRANSPORT_INSECURE")

    def test_loopback_binds_are_allowed(self) -> None:
        server = self._server()
        for host in ("127.0.0.1", "localhost", "127.0.0.2", "::1"):
            with self.subTest(host):
                server._check_bind_host(host, insecure_dev=None)  # noqa: SLF001

    def test_tokens_or_insecure_dev_allow_a_non_loopback_bind(self) -> None:
        self._server(auth_tokens={"t": {"id": "svc", "kind": "service"}})._check_bind_host(  # noqa: SLF001
            "0.0.0.0", insecure_dev=None)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self._server(insecure_dev=True)._check_bind_host("0.0.0.0", insecure_dev=None)  # noqa: SLF001
            self._server()._check_bind_host("0.0.0.0", insecure_dev=True)  # noqa: SLF001
        self.assertTrue(any("insecure" in str(item.message) for item in caught))


class SchemaRouteTests(HttpFixture):
    """SDK-05: no client-supplied ref may read a file outside the shipped schemas."""

    def setUp(self) -> None:
        super().setUp()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.secret = Path(directory.name) / "secret.json"
        self.secret.write_text(json.dumps({"api_token": "DUMMY-SECRET-FOR-REVIEW"}))

    def test_traversal_absolute_and_home_refs_are_refused(self) -> None:
        relative = "../" * 12 + str(self.secret).lstrip("/")
        refs = [str(self.secret), relative, "~/secret.json", "..\\secret.json", "./device.schema.json",
                "schema/../device.schema.json", "C:\\secret.json", "file:///etc/passwd"]
        for ref in refs:
            with self.subTest(ref=ref):
                with self.assertRaises(MHSError) as ctx:
                    self.rpc("mhs.schema.get", ref=ref)
                self.assertEqual(ctx.exception.code, "MHS.PROTOCOL.INVALID_PARAMS")
                quoted = urllib.request.quote(ref, safe="")
                for path in (f"/mhs/v1/schema/{quoted}", f"/mhs/v1/schema?ref={quoted}"):
                    status, _headers, body = self.request("GET", path)
                    self.assertIn(status, (400, 404), path)
                    self.assertNotIn(b"DUMMY-SECRET", body)

    def test_a_previously_loaded_file_is_not_public(self) -> None:
        from mhs.schema import clear_default_store, default_store

        self.addCleanup(clear_default_store)
        default_store().load_path(self.secret)
        with self.assertRaises(MHSError):
            self.rpc("mhs.schema.get", ref="secret.json")
        status, _headers, body = self.request("GET", "/mhs/v1/schema/secret.json")
        self.assertEqual(status, 404)
        self.assertNotIn(b"DUMMY-SECRET", body)

    def test_shipped_schemas_still_resolve(self) -> None:
        from mhs import _ids

        result = self.rpc("mhs.schema.get", ref="device.schema.json")
        self.assertEqual(result["schema"]["$id"], _ids.SCHEMA_BASE + "device.schema.json")
        result = self.rpc("mhs.schema.get", ref=_ids.SCHEMA_BASE + "receipt.schema.json")
        self.assertEqual(result["schema"]["$id"], _ids.SCHEMA_BASE + "receipt.schema.json")
        result = self.rpc("mhs.schema.get", ref=STEP)
        self.assertEqual(result["capability_id"], STEP)


class SseOwnershipTests(HttpFixture):
    """e5/v5: an SSE stream delivers only its own session's subscriptions."""

    def _open(self, principal: str) -> tuple[str, str]:
        session = self.rpc("mhs.session.open", mode="simulated",
                           principal={"id": principal, "kind": "agent"})["session_id"]
        subscription = self.rpc("mhs.subscribe", session_id=session, streams=["state"],
                                deadline_ms=1000)["subscription_id"]
        return session, subscription

    def test_e5_each_stream_gets_only_its_own_events(self) -> None:
        session_a, sub_a = self._open("agent-a")
        session_b, sub_b = self._open("agent-b")
        reader_a = _SseReader(self.port, f"/mhs/v1/events?session_id={session_a}")
        reader_b = _SseReader(self.port, f"/mhs/v1/events?session_id={session_b}")
        self.addCleanup(reader_a.close)
        self.addCleanup(reader_b.close)
        self.assertEqual((reader_a.status, reader_b.status), (200, 200))
        for _ in range(10):
            receipt = self.rpc("mhs.command", session_id=session_a, capability_id=STEP,
                               input={"ticks": 1}, deadline_ms=2000)
            self.assertEqual(receipt["status"], "completed", receipt)
        end = time.monotonic() + 5
        while time.monotonic() < end and (len(reader_a.events()) < 10 or len(reader_b.events()) < 10):
            time.sleep(0.05)
        ids_a = [event["params"]["subscription_id"] for event in reader_a.events()]
        ids_b = [event["params"]["subscription_id"] for event in reader_b.events()]
        self.assertEqual(ids_a, [sub_a] * 10)
        self.assertEqual(ids_b, [sub_b] * 10)
        frame = next(frame for frame in reader_a.frames if any(line.startswith("id:") for line in frame))
        self.assertIn("event: mhs.event", frame)
        self.assertTrue(any(line == f"id: {sub_a}:1" for line in frame), frame)

    def test_sse_requires_the_owning_session(self) -> None:
        session_a, sub_a = self._open("agent-a")
        session_b, _sub_b = self._open("agent-b")
        cases = {
            "no session": ("/mhs/v1/events", 400),
            "subscription only": (f"/mhs/v1/events?subscription_id={sub_a}", 400),
            "unknown session": ("/mhs/v1/events?session_id=mhs_s_" + canonical.ulid(), 403),
            "foreign subscription": (f"/mhs/v1/events?session_id={session_b}&subscription_id={sub_a}", 404),
        }
        for label, (path, expected) in cases.items():
            with self.subTest(label):
                status, stream, sock = _sse_open(self.port, path)
                sock.close()
                self.assertEqual(status, expected)
        reader = _SseReader(self.port, f"/mhs/v1/events?session_id={session_a}&subscription_id={sub_a}")
        self.addCleanup(reader.close)
        self.assertEqual(reader.status, 200)

    def test_unsubscribe_needs_the_owning_session(self) -> None:
        _session_a, sub_a = self._open("agent-a")
        session_b, _sub_b = self._open("agent-b")
        with self.assertRaises(MHSError):
            self.rpc("mhs.unsubscribe", session_id=session_b, subscription_id=sub_a)
        self.assertIn(sub_a, self.server._subscriptions)

    def test_subscription_ids_are_unguessable(self) -> None:
        session, first = self._open("agent-a")
        second = self.rpc("mhs.subscribe", session_id=session, streams=["state"],
                          deadline_ms=1000)["subscription_id"]
        for subscription in (first, second):
            self.assertRegex(subscription, r"^sub_[0-9a-f]{32}$")
        self.assertNotEqual(first[:-4], second[:-4], "subscription ids differ only in a counter")

    def test_per_principal_sse_cap(self) -> None:
        from mhs.server import _MAX_SSE_STREAMS_PER_PRINCIPAL

        session, _subscription = self._open("agent-a")
        readers = []
        for _ in range(_MAX_SSE_STREAMS_PER_PRINCIPAL):
            reader = _SseReader(self.port, f"/mhs/v1/events?session_id={session}")
            readers.append(reader)
            self.addCleanup(reader.close)
            self.assertEqual(reader.status, 200)
        status, _stream, sock = _sse_open(self.port, f"/mhs/v1/events?session_id={session}")
        sock.close()
        self.assertEqual(status, 429)
        other, _ = self._open("agent-b")
        reader = _SseReader(self.port, f"/mhs/v1/events?session_id={other}")
        self.addCleanup(reader.close)
        self.assertEqual(reader.status, 200, "the cap is per principal")


class SocketTimeoutTests(HttpFixture):
    def make_server(self):
        spec, server = _conveyor()
        server.http_timeout_s = 0.3
        return spec, server

    def test_a_stalled_client_is_disconnected(self) -> None:
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        self.addCleanup(sock.close)
        sock.sendall(b"POST /mhs/v1/rpc HTTP/1.1\r\nHost: 127.0.0.1\r\n")  # never finishes
        started = time.monotonic()
        data = sock.recv(4096)
        self.assertEqual(data, b"", "the server kept a stalled connection open")
        self.assertLess(time.monotonic() - started, 3.0)


class HttpWireHygieneTests(HttpFixture):
    def test_e6_nan_input_is_a_parse_error(self) -> None:
        session = self.rpc("mhs.session.open", mode="simulated")["session_id"]
        before = self.rpc("mhs.resource.read", session_id=session, deadline_ms=2000)["revision"]
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant):
                raw = ('{"jsonrpc":"2.0","id":3,"method":"mhs.command","params":{"session_id":"%s",'
                       '"capability_id":"x-cap.mhs-reference.start.v1","input":{"speed_mm_s":%s},'
                       '"deadline_ms":2000}}' % (session, constant)).encode()
                status, _headers, payload = self.post(None, raw=raw)
                self.assertEqual(status, 400, payload)
                self.assertEqual(payload["error"]["data"]["mhs_code"], "MHS.PROTOCOL.PARSE_ERROR")
        after = self.rpc("mhs.resource.read", session_id=session, deadline_ms=2000)["revision"]
        self.assertEqual(before, after)

    def test_e6_effectful_notification_is_dropped_and_logged(self) -> None:
        session = self.rpc("mhs.session.open", mode="simulated")["session_id"]
        before = self.rpc("mhs.resource.read", session_id=session, deadline_ms=2000)["revision"]
        with self.assertLogs("mhs.server", level="WARNING") as logs:
            status, _headers, _payload = self.post(
                {"jsonrpc": "2.0", "method": "mhs.command",
                 "params": {"session_id": session, "capability_id": STEP, "input": {"ticks": 5},
                            "deadline_ms": 2000}})
        self.assertEqual(status, 204)
        self.assertTrue(any("mhs.command" in line for line in logs.output))
        after = self.rpc("mhs.resource.read", session_id=session, deadline_ms=2000)["revision"]
        self.assertEqual(before, after, "a command sent as a notification was executed")

    def test_estop_with_a_non_finite_deadline_latches(self) -> None:
        """Verifier probe estop_inf.py over HTTP (plan 3.6: never refused)."""
        device_id = next(iter(self.server.devices))
        for literal in ("1e999", "NaN", "-Infinity"):
            with self.subTest(literal):
                raw = ('{"jsonrpc":"2.0","id":7,"method":"mhs.safety.estop","params":'
                       '{"device_id":"%s","reason":"x","deadline_ms":%s}}' % (device_id, literal)).encode()
                with self.assertLogs("mhs.server", level="WARNING"):
                    status, _headers, payload = self.post(None, raw=raw)
                self.assertEqual(status, 200, payload)
                self.assertIn("result", payload, payload)
                self.assertEqual(payload["result"]["status"], "completed", payload)
                self.assertTrue(payload["result"]["output"]["latched"], payload)
                self.assertTrue(self.server._latched[device_id])  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
