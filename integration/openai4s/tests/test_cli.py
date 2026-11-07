"""CLI: mcp-config, endpoints and devices without importing OpenAI4S."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from openai4s_mhs.cli import main


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, {"MHS_SKIP_OPENAI4S_DECLARATION": "1"}):
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv)
    return code, out.getvalue(), err.getvalue()


class CLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-cli-test-")
        self.addCleanup(self.tmp.cleanup)
        self.config_path = Path(self.tmp.name) / "mhs.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "endpoints": [
                        {"id": "lab", "url": "http://127.0.0.1:9", "label": "lab"},
                        {
                            "id": "conveyor",
                            "command": ["python3", "-m", "mhs.reference", "conveyor", "--stdio"],
                        },
                    ],
                    "evidence_log": str(Path(self.tmp.name) / "evidence.jsonl"),
                }
            ),
            encoding="utf-8",
        )

    def test_mcp_config_emits_connectors(self) -> None:
        code, out, err = _run(
            ["mcp-config", "--config", str(self.config_path), "--json", "--python", "/usr/bin/python3"]
        )
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertIn("connectors", payload)
        self.assertTrue(payload["enabled"])
        entries = payload["connectors"]
        self.assertEqual([entry["id"] for entry in entries], ["mhs-lab", "mhs-conveyor"])
        self.assertTrue(all(entry["enabled"] for entry in entries))
        self.assertEqual(entries[0]["command"][0], "/usr/bin/python3")
        self.assertEqual(
            entries[0]["command"][entries[0]["command"].index("--endpoint") + 1],
            "http://127.0.0.1:9",
        )
        self.assertEqual(entries[0]["command"][-2], "--config")
        self.assertEqual(entries[0]["command"][-1], str(self.config_path))
        self.assertEqual(entries[0]["transport"], "stdio")

    def test_mcp_config_bare(self) -> None:
        code, out, _err = _run(
            ["mcp-config", "--config", str(self.config_path), "--json", "--bare"]
        )
        self.assertEqual(code, 0)
        self.assertIsInstance(json.loads(out), list)

    def test_mcp_config_connectors_are_disabled_by_default(self) -> None:
        disabled = Path(self.tmp.name) / "mhs-disabled.json"
        disabled.write_text(
            json.dumps(
                {
                    "enabled": False,
                    "endpoints": [{"id": "lab", "url": "http://127.0.0.1:9"}],
                }
            ),
            encoding="utf-8",
        )
        code, out, err = _run(["mcp-config", "--config", str(disabled), "--json"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        # Listed so settings can show it, but the connector itself is off.
        self.assertEqual(len(payload["connectors"]), 1)
        self.assertFalse(payload["connectors"][0]["enabled"])
        self.assertFalse(payload["enabled"])
        self.assertTrue(payload["experimental"])
        self.assertEqual(payload["transport"], "mcp")
        # --write upserts into OpenAI4S's store when one is reachable (skipped
        # here); the payload still reports the attempt.
        code, out, _err = _run(["mcp-config", "--config", str(disabled), "--json", "--write"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)["connectors"]), 1)

    def test_settings_verbs_default_off_then_enable_disable(self) -> None:
        settings = Path(self.tmp.name) / "settings.json"
        code, out, err = _run(["status", "--config", str(settings), "--json"])
        self.assertEqual(code, 0, err)
        status = json.loads(out)
        self.assertFalse(status["enabled"])
        self.assertTrue(status["experimental"])
        self.assertFalse(status["default_enabled"])
        code, out, err = _run(["enable", "--config", str(settings), "--json"])
        self.assertEqual(code, 0, err)
        self.assertTrue(json.loads(out)["enabled"])
        settings_payload = json.loads(settings.read_text(encoding="utf-8"))
        self.assertTrue(settings_payload["enabled"])
        self.assertEqual(oct(settings.stat().st_mode & 0o777), "0o600")
        code, out, _err = _run(["disable", "--config", str(settings), "--json"])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(out)["enabled"])

    def test_endpoints_does_not_connect(self) -> None:
        code, out, err = _run(["endpoints", "--config", str(self.config_path), "--json"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["count"], 2)
        transports = {item["id"]: item["transport"] for item in payload["endpoints"]}
        self.assertEqual(transports, {"lab": "http", "conveyor": "stdio"})

    def test_devices_reports_unreachable_endpoint_instead_of_crashing(self) -> None:
        # Port 9 is closed; the SDK may be absent.  Either way discovery must
        # return per-endpoint errors, not exit non-zero.
        code, out, err = _run(["devices", "--config", str(self.config_path), "--json"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["count"], 2)
        by_endpoint = {item.get("endpoint_id"): item for item in payload["devices"]}
        # The closed port must be reported as a per-endpoint error...
        self.assertIn("error", by_endpoint["lab"])
        self.assertIn("mhs_code", by_endpoint["lab"])
        # ...while the healthy stdio endpoint is still discovered in the same run.
        self.assertEqual(by_endpoint["conveyor"]["mode"], "simulated")
        self.assertTrue(by_endpoint["conveyor"]["device_id"].startswith("mhs://"))

    def test_invalid_input_json_is_a_clean_exit(self) -> None:
        code, _out, err = _run(
            [
                "call",
                "conveyor",
                "cap.world.step.v1",
                "--config",
                str(self.config_path),
                "--input",
                "{not json",
            ]
        )
        self.assertEqual(code, 2)
        self.assertIn("not valid JSON", err)

    def test_unknown_endpoint_id_fails_cleanly(self) -> None:
        code, out, err = _run(
            ["read", "conveyor", "--endpoint", "missing", "--config", str(self.config_path), "--json"]
        )
        self.assertEqual(code, 2, err)
        payload = json.loads(out)
        self.assertEqual(payload["mhs_code"], "MHS.HOST.DEVICE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
