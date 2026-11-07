"""Discovery (WP-08 08b, AF-08): MHS_ENDPOINTS, ~/.mhs/endpoints.json, /.well-known/mhs.json.

Discovered does not mean trusted: every endpoint is reported ``trusted: false``,
stdio endpoints are never launched by discovery, and the descriptor is the
endpoint's own claim.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from mhs.discovery import (
    EndpointsFileError,
    discover,
    endpoints_from_env,
    parse_target,
    probe,
    read_endpoints_file,
)

from . import _support as s


class _Fixed(BaseHTTPRequestHandler):
    """Answers every GET with ``self.server.reply`` (status, body)."""

    def do_GET(self):  # noqa: N802 - stdlib handler API
        status, body = self.server.reply  # type: ignore[attr-defined]
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        return


def _fixed_server(status: int, body: str) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Fixed)
    server.reply = (status, body)  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


class ParseTest(unittest.TestCase):
    def test_targets(self):
        self.assertEqual(parse_target("http://127.0.0.1:7400/"), ("http", "http://127.0.0.1:7400", None))
        self.assertEqual(parse_target("mhs://lab-pc"), ("http", "http://lab-pc:7400", None))
        self.assertEqual(parse_target("mhs://lab-pc:7401/lab/x"), ("http", "http://lab-pc:7401", None))
        self.assertEqual(parse_target("stdio:python3 -m mhs serve 'my dir' --stdio"),
                         ("stdio", None, ["python3", "-m", "mhs", "serve", "my dir", "--stdio"]))
        self.assertEqual(parse_target("stdio:python3,-m,mhs.reference,lab,--stdio"),
                         ("stdio", None, ["python3", "-m", "mhs.reference", "lab", "--stdio"]))
        self.assertEqual(parse_target("mhs+stdio://python3,-m,mhs.reference,lab,--stdio"),
                         ("stdio", None, ["python3", "-m", "mhs.reference", "lab", "--stdio"]))
        for bad in ("ftp://x", "lab-pc:7400", "stdio:", "mhs://", "mhs+stdio://"):
            with self.subTest(bad), self.assertRaises(ValueError):
                parse_target(bad)

    def test_env_entries(self):
        found = endpoints_from_env(" http://a:1 , stdio:python3 -m mhs.reference arm --stdio,mhs://h ,")
        self.assertEqual([(item.transport, item.key) for item in found],
                         [("http", "http://a:1"), ("stdio", "python3 -m mhs.reference arm --stdio"),
                          ("http", "http://h:7400")])
        self.assertTrue(all(item.sources == ["env"] and item.trusted is False for item in found))
        with self.assertRaises(ValueError):
            endpoints_from_env("not-an-endpoint")
        # MHS_ENDPOINTS is split at commas first, so the comma form of a stdio command (accepted by -e and
        # targets=) is not available there: its words are separated by spaces (module docstring).
        with self.assertRaises(ValueError) as ctx:
            endpoints_from_env("stdio:python3,-m,mhs.reference,lab,--stdio")
        self.assertIn("'-m' is not an endpoint", str(ctx.exception))
        self.assertEqual(discover(targets=["stdio:python3,-m,mhs.reference,lab,--stdio"], use_env=False,
                                  use_file=False)[0].command, ["python3", "-m", "mhs.reference", "lab", "--stdio"])


class EndpointsFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-endpoints-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, document) -> Path:
        path = self.dir / "endpoints.json"
        path.write_text(json.dumps(document) if not isinstance(document, str) else document, encoding="utf-8")
        return path

    def test_valid_file(self):
        path = self._write({"openmhs": "0.9", "endpoints": [
            {"name": "bath", "transport": "http", "url": "http://10.0.0.5:7400", "token_file": "bath.token",
             "devices": ["mhs://10.0.0.5:7400/lab/bath"], "tags": ["lab"]},
            {"transport": "stdio", "command": ["python3", "-m", "mhs", "serve", "drivers/x", "--stdio"],
             "cwd": "work"},
        ]})
        found = read_endpoints_file(path)
        self.assertEqual([item.key for item in found],
                         ["http://10.0.0.5:7400", "python3 -m mhs serve drivers/x --stdio"])
        self.assertEqual(found[0].token_file, str(self.dir / "bath.token"))
        self.assertEqual(found[1].cwd, str(self.dir / "work"))
        self.assertEqual(found[0].devices, ["mhs://10.0.0.5:7400/lab/bath"])

    def test_missing_file_is_empty(self):
        self.assertEqual(read_endpoints_file(self.dir / "nothing.json"), [])

    def test_invalid_file_is_refused_whole(self):
        for document in ({"endpoints": [{"transport": "http"}]},  # http needs url
                         {"endpoints": [{"transport": "http", "url": "http://a:1", "token": "inline"}]},
                         {"servers": []},
                         "{not json"):
            with self.subTest(document=document):
                with self.assertRaises(EndpointsFileError) as ctx:
                    read_endpoints_file(self._write(document))
                self.assertTrue(ctx.exception.problems)

    def test_env_file_override_and_dedupe(self):
        spec, server = s.reference("conveyor")
        try:
            with s.Http(server) as http:
                path = self._write({"endpoints": [{"transport": "http", "url": http.url, "name": "conveyor",
                                                   "endpoint_id": "mhs://elsewhere:1"}]})
                with mock.patch.dict(os.environ, {"MHS_ENDPOINTS": http.url, "MHS_ENDPOINTS_FILE": str(path)}):
                    found = discover()
        finally:
            spec.close()
        self.assertEqual(len(found), 1)
        endpoint = found[0]
        self.assertEqual(endpoint.sources, ["env", "file"])
        self.assertEqual(endpoint.name, "conveyor")
        self.assertEqual(endpoint.status, "reachable")
        self.assertEqual(endpoint.endpoint_id, s.ENDPOINT_ID)
        self.assertTrue(any("differs" in warning for warning in endpoint.warnings))


class ProbeTest(unittest.TestCase):
    def test_reachable_endpoint(self):
        spec, server = s.reference("lab")
        try:
            with s.Http(server) as http:
                found = discover(targets=[http.url], use_env=False, use_file=False)
        finally:
            spec.close()
        endpoint = found[0]
        self.assertEqual(endpoint.status, "reachable")
        self.assertEqual(len(endpoint.devices), 3)
        self.assertEqual(endpoint.descriptor["endpoint_id"], s.ENDPOINT_ID)
        self.assertFalse(endpoint.trusted)
        self.assertFalse(endpoint.to_dict()["trusted"])

    def test_unreachable_endpoint(self):
        endpoint = discover(targets=[s.closed_port_url()], use_env=False, use_file=False)[0]
        self.assertEqual(endpoint.status, "unreachable")
        self.assertEqual(endpoint.error["mhs_code"], "MHS.TRANSPORT.UNAVAILABLE")

    def test_invalid_descriptors(self):
        for status, body in ((200, "{}"), (200, "not json"), (404, '{"error": "nope"}')):
            server, url = _fixed_server(status, body)
            try:
                with self.subTest(status=status, body=body):
                    endpoint = discover(targets=[url], use_env=False, use_file=False)[0]
                    self.assertEqual(endpoint.status, "invalid_descriptor")
                    self.assertEqual(endpoint.error["mhs_code"], "MHS.TRANSPORT.PROTOCOL_ERROR")
            finally:
                server.shutdown()
                server.server_close()

    def test_stdio_endpoint_is_never_launched(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "launched"
            command = f"stdio:{sys.executable} -c open({str(marker)!r},'w')"
            endpoint = discover(targets=[command], use_env=False, use_file=False)[0]
            self.assertEqual(endpoint.status, "not_probed")
            self.assertFalse(marker.exists())
            self.assertEqual(probe(endpoint).status, "not_probed")


class DiscoverCliTest(unittest.TestCase):
    def test_discover_json_and_human(self):
        spec, server = s.reference("conveyor")
        try:
            with s.Http(server) as http, mock.patch.dict(os.environ, {"MHS_ENDPOINTS": http.url}):
                code, out, _err = s.run_cli("discover", "--no-file", "--json")
                self.assertEqual(code, 0)
                payload = json.loads(out)
                self.assertFalse(payload["trusted"])
                self.assertIn("does not mean trusted", payload["note"])
                self.assertEqual(payload["endpoints"][0]["status"], "reachable")
                code, out, _err = s.run_cli("discover", "--no-file")
                self.assertEqual(code, 0)
                self.assertTrue(out.startswith("reachable"))
                self.assertIn("discovered does not mean trusted", out)
        finally:
            spec.close()

    def test_invalid_file_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "endpoints.json"
            path.write_text('{"endpoints": [{"transport": "carrier-pigeon"}]}', encoding="utf-8")
            code, _out, err = s.run_cli("discover", "--no-env", "--file", str(path))
        self.assertEqual(code, 2)
        self.assertIn("invalid endpoints file", err)

    def test_nothing_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _err = s.run_cli("discover", "--no-env", "--file", str(Path(tmp) / "none.json"))
        self.assertEqual(code, 0)
        self.assertIn("no endpoints configured", out)


if __name__ == "__main__":
    unittest.main()
