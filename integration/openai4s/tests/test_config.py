"""MHSConfig parsing (explicit config, env fallbacks, endpoint selection)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from openai4s_mhs.config import EndpointSpec, MHSConfig, endpoints_from_env
from openai4s_mhs.mcpconfig import (
    connector_argv,
    connector_config,
    connector_entry,
    endpoint_target,
)


class ConfigTests(unittest.TestCase):
    def test_explicit_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mhs.json"
            path.write_text(
                json.dumps(
                    {
                        "endpoints": [
                            {"id": "lab", "url": "http://127.0.0.1:7401", "label": "lab"},
                            {
                                "id": "conveyor",
                                "command": ["python3", "-m", "mhs.reference", "conveyor", "--stdio"],
                            },
                        ],
                        "evidence_log": str(Path(tmp) / "evidence.jsonl"),
                        "allow_hardware": True,
                        "auto_permit_risk": ["R0"],
                        "session_ttl_s": 42,
                        "command_timeout_ms": 1234,
                    }
                ),
                encoding="utf-8",
            )
            config = MHSConfig.load(path)
        self.assertEqual([ep.id for ep in config.endpoints], ["lab", "conveyor"])
        self.assertEqual(config.endpoints[0].url, "http://127.0.0.1:7401")
        self.assertEqual(
            config.endpoints[1].to_mhs_target(),
            ["python3", "-m", "mhs.reference", "conveyor", "--stdio"],
        )
        self.assertTrue(config.allow_hardware)
        self.assertEqual(config.auto_permit_risk, ("R0",))
        self.assertEqual(config.session_ttl_s, 42)
        self.assertEqual(config.command_timeout_ms, 1234)
        self.assertEqual(config.endpoint("lab").id, "lab")
        self.assertEqual(config.evidence_path.suffix, ".jsonl")

    def test_missing_file_is_not_fatal(self) -> None:
        with mock.patch.dict(os.environ, {"MHS_ENDPOINTS": ""}, clear=False):
            config = MHSConfig.load("/nonexistent/definitely/mhs.json")
        self.assertEqual(config.endpoints, [])
        self.assertFalse(config.allow_hardware)

    def test_env_endpoint_fallback(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "MHS_ENDPOINTS": "http://127.0.0.1:7401,http://127.0.0.1:7402",
                "MHS_CONFIG": "",
            },
            clear=False,
        ):
            config = MHSConfig.load("/nonexistent/mhs.json")
        self.assertEqual(len(config.endpoints), 2)
        self.assertEqual(config.endpoints[0].url, "http://127.0.0.1:7401")

    def test_endpoints_from_env_parses_stdio(self) -> None:
        specs = endpoints_from_env("http://h:1,stdio:python3 -m mhs.reference arm --stdio")
        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0].url, "http://h:1")
        self.assertEqual(specs[1].command[:3], ["python3", "-m", "mhs.reference"])
        self.assertEqual(specs[1].to_mhs_target()[-1], "--stdio")

    def test_endpoint_selection_errors(self) -> None:
        with self.assertRaises(LookupError):
            MHSConfig().endpoint(None)
        config = MHSConfig(
            endpoints=[EndpointSpec(id="a", url="http://a"), EndpointSpec(id="b", url="http://b")]
        )
        with self.assertRaises(LookupError):
            config.endpoint(None)
        with self.assertRaises(LookupError):
            config.endpoint("missing")
        self.assertEqual(config.endpoint("b").id, "b")


class MCPConfigTests(unittest.TestCase):
    def test_connector_entry_shape(self) -> None:
        spec = EndpointSpec(id="lab-1", url="http://127.0.0.1:7401", label="lab")
        entry = connector_entry(spec, python="/usr/bin/python3", config_path="/tmp/mhs.json")
        self.assertEqual(entry["id"], "mhs-lab-1")
        self.assertEqual(entry["transport"], "stdio")
        self.assertEqual(
            entry["command"],
            [
                "/usr/bin/python3",
                "-m",
                "mhs.mcp",
                "--endpoint",
                "http://127.0.0.1:7401",
                "--config",
                "/tmp/mhs.json",
            ],
        )
        self.assertFalse(entry["enabled"])  # experimental MCP integration: off by default
        self.assertTrue(connector_entry(spec, enabled=True)["enabled"])
        # The settings path is always carried so mhs.mcp enforces the policy.
        self.assertEqual(connector_entry(spec)["command"][-2], "--config")

    def test_stdio_endpoint_is_encoded(self) -> None:
        spec = EndpointSpec(id="arm", command=["python3", "-m", "mhs.reference", "arm"])
        self.assertEqual(endpoint_target(spec), "mhs+stdio://python3,-m,mhs.reference,arm")
        argv = connector_argv(spec, python="/usr/bin/python3")
        self.assertEqual(argv[:4], ["/usr/bin/python3", "-m", "mhs.mcp", "--command"])
        self.assertEqual(argv[4], "python3 -m mhs.reference arm")

    def test_connector_config_for_config(self) -> None:
        config = MHSConfig(
            enabled=True,
            endpoints=[
                EndpointSpec(id="lab", url="http://127.0.0.1:7401"),
                EndpointSpec(id="arm", command=["python3", "-m", "mhs.reference", "arm"]),
            ]
        )
        payload = connector_config(config, python="/usr/bin/python3")
        self.assertIn("connectors", payload)
        self.assertTrue(payload["enabled"])
        self.assertTrue(payload["experimental"])
        ids = [entry["id"] for entry in payload["connectors"]]
        self.assertEqual(ids, ["mhs-lab", "mhs-arm"])
        for entry in payload["connectors"]:
            self.assertEqual(entry["command"][:3], ["/usr/bin/python3", "-m", "mhs.mcp"])
            self.assertIn(entry["command"][3], ("--endpoint", "--command"))
        by_id = {entry["id"]: entry for entry in payload["connectors"]}
        self.assertEqual(by_id["mhs-lab"]["command"][3], "--endpoint")
        self.assertEqual(by_id["mhs-lab"]["command"][4], "http://127.0.0.1:7401")
        self.assertEqual(by_id["mhs-arm"]["command"][3], "--command")

    def test_disabled_config_emits_connectors_that_are_disabled(self) -> None:
        config = MHSConfig(
            enabled=False,
            endpoints=[EndpointSpec(id="lab", url="http://127.0.0.1:7401")],
        )
        payload = connector_config(config)
        # The row is listed (so the operator can enable it in settings) but off.
        self.assertEqual(len(payload["connectors"]), 1)
        self.assertFalse(payload["connectors"][0]["enabled"])
        self.assertFalse(payload["enabled"])
        self.assertTrue(payload["experimental"])
        self.assertEqual(payload["transport"], "mcp")
        enabled = connector_config(config, enabled=True)
        self.assertTrue(enabled["connectors"][0]["enabled"])
        self.assertTrue(enabled["enabled"])

    def test_enabled_defaults_false_and_env_override(self) -> None:
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"MHS_ENABLED": "1"}, clear=False):
            self.assertTrue(MHSConfig.load().enabled)
        with mock.patch.dict(os.environ, {"MHS_ENABLED": "0"}, clear=False):
            self.assertFalse(MHSConfig.load().enabled)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MHS_ENABLED", None)
            os.environ.pop("MHS_CONFIG", None)
            if not Path.home().joinpath(".openai4s", "mhs.json").exists():
                self.assertFalse(MHSConfig.load().enabled)
        self.assertTrue(MHSConfig(enabled=True).experimental)

    def test_only_a_json_true_enables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MHS_ENABLED", None)
            path = Path(tmp) / "mhs.json"
            for value, expected in (("false", False), ("true", False), (1, False), (True, True)):
                path.write_text(json.dumps({"enabled": value}), encoding="utf-8")
                self.assertEqual(MHSConfig.load(path).enabled, expected, value)

    def test_only_a_json_true_allows_hardware(self) -> None:
        # Verifier finding (MERGE-C2): bool("false") is True opened the MHSHost hardware gate while
        # mhs.mcp's MCPPolicy, reading the same document, kept it shut.
        from mhs.mcp import MCPPolicy
        from openai4s_mhs.host import MHSHost, MHSHostError

        hardware = {"mode": "hardware", "device_id": "mhs://lab.local/arm"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mhs.json"
            for value in ("false", "true", 1, "1", "yes", [True], {"on": True}):
                with self.subTest(value=value):
                    path.write_text(
                        json.dumps({"enabled": True, "allow_hardware": value, "endpoints": []}),
                        encoding="utf-8",
                    )
                    config = MHSConfig.load(path)
                    self.assertFalse(config.allow_hardware)
                    self.assertEqual(MCPPolicy.load(path).allow_hardware, config.allow_hardware)
                    self.assertEqual(config.warnings, ())  # ignored, not weakening: agent rows stay allowed
                    self.assertEqual(len(config.notices), 1, config.notices)
                    self.assertIn("allow_hardware", config.notices[0])
                    self.assertIn("allow_hardware", config.to_settings()["notices"][0])
                    with self.assertRaises(MHSHostError) as caught:
                        MHSHost(config)._hardware_gate(hardware)
                    self.assertEqual(caught.exception.code, "MHS.HOST.HARDWARE_GATED")
            path.write_text(json.dumps({"allow_hardware": True, "endpoints": []}), encoding="utf-8")
            config = MHSConfig.load(path)
            self.assertTrue(config.allow_hardware)
            self.assertTrue(MCPPolicy.load(path).allow_hardware)
            self.assertEqual(config.notices, ())
            MHSHost(config)._hardware_gate(hardware)  # open: no exception

    def test_settings_document_must_be_an_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mhs.json"
            path.write_text(json.dumps([{"allow_hardware": True}]), encoding="utf-8")
            with self.assertRaises(ValueError):
                MHSConfig.load(path)

    def test_ids_are_provider_portable(self) -> None:
        import re

        spec = EndpointSpec(id="mhs://127.0.0.1:7401", url="http://127.0.0.1:7401")
        self.assertRegex(
            connector_entry(spec)["id"], re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")
        )


if __name__ == "__main__":
    unittest.main()
