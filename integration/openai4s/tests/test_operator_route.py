"""The host operator route: resets and permits are human decisions.

``mhs.mcp`` lists ``mhs__reset``/``mhs__permit`` only with ``--operator-tools``.
Agent connector rows never carry the flag and the governed host route refuses
both tools on an agent row; the operator route (``OperatorRoute``, CLI
``safety reset``) launches its own ``--operator-tools`` connection, needs a
named operator (and, on the CLI, an interactive terminal) and records every
step in the host ledger.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from openai4s_mhs import status as settings_status
from openai4s_mhs.cli import main
from openai4s_mhs.config import EndpointSpec, MHSConfig
from openai4s_mhs.host_evidence import HostLedger
from openai4s_mhs.hostroute import governed_call
from openai4s_mhs.mcp_invoke import MCPConnector, MCPInvokeError
from openai4s_mhs.mcpconfig import connector_entry, operator_argv
from openai4s_mhs.operator_route import OperatorRoute, OperatorRouteError
from openai4s_mhs.operator_route import reset as operator_reset

from .hardware_endpoint import start_endpoint
from .host_remediation_support import write_settings
from .long_running_endpoint import start_job_endpoint
from .support import sdk_projection_available


class _Terminal(io.StringIO):
    """stdin of an operator at a terminal who types ``answer``."""

    def isatty(self) -> bool:
        return True


def _run_cli(argv: list[str], stdin: Any) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "stdin", stdin), contextlib.redirect_stdout(out), \
            contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class OperatorRouteUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-operator-unit-")
        self.addCleanup(self.tmp.cleanup)

    def test_operator_argv_adds_the_flag_and_the_operator_token(self) -> None:
        token = Path(self.tmp.name) / "operator.token"
        path = write_settings(Path(self.tmp.name), "http://127.0.0.1:9", endpoint_id="lab",
                              extra={"operator_token_file": str(token)})
        config = MHSConfig.load(path)
        spec = config.endpoints[0]
        agent = connector_entry(spec, python="py", config_path=config.config_path)["command"]
        operator = operator_argv(spec, config, python="py")
        self.assertNotIn("--operator-tools", agent)
        self.assertNotIn("--token-file", agent)
        self.assertEqual(operator, agent + ["--operator-tools", "--token-file", str(token)])
        # A stdio endpoint has no bearer token to carry.
        stdio = EndpointSpec(id="arm", command=["python3", "-m", "mhs.reference", "arm", "--stdio"])
        self.assertEqual(operator_argv(stdio, config, python="py")[-1], "--operator-tools")

    def test_a_missing_operator_token_file_is_a_settings_error(self) -> None:
        # Verifier finding: the child exited on the missing file and the CLI reported an unreachable endpoint (3).
        path = write_settings(Path(self.tmp.name), "http://127.0.0.1:9", endpoint_id="lab",
                              extra={"operator_token_file": str(Path(self.tmp.name) / "missing.token")})
        config = MHSConfig.load(path)
        with self.assertRaises(OperatorRouteError) as ctx:
            OperatorRoute("lab", config, operator="human:alice")
        self.assertEqual(ctx.exception.code, "MHS.HOST.CONFIG_REQUIRED")
        code, out, _err = _run_cli(["safety", "reset", "dev", "--config", str(path), "--endpoint", "lab",
                                    "--operator", "human:alice", "--json"], _Terminal("reset\n"))
        self.assertEqual((code, json.loads(out)["mhs_code"]), (2, "MHS.HOST.CONFIG_REQUIRED"))

    def test_operator_name_and_enabled_integration_are_required(self) -> None:
        enabled = MHSConfig.load(write_settings(Path(self.tmp.name) / "on", "http://127.0.0.1:9",
                                                endpoint_id="lab"))
        with self.assertRaises(OperatorRouteError) as caught:
            OperatorRoute("lab", enabled, operator="  ")
        self.assertEqual(caught.exception.code, "MHS.AUTH.FORBIDDEN")
        disabled = MHSConfig.load(write_settings(Path(self.tmp.name) / "off", "http://127.0.0.1:9",
                                                 endpoint_id="lab", enabled=False))
        with self.assertRaises(MCPInvokeError) as caught:
            OperatorRoute("lab", disabled, operator="human:alice")
        self.assertEqual(caught.exception.code, "MHS.AUTH.FORBIDDEN")

    def test_host_route_refuses_operator_tools_before_any_endpoint_call(self) -> None:
        path = write_settings(Path(self.tmp.name), "http://127.0.0.1:9", endpoint_id="lab")
        config = MHSConfig.load(path)
        row = connector_entry(config.endpoints[0], python="py", config_path=str(path), enabled=True)
        row["connector_id"] = row["id"]
        calls: list[tuple] = []

        def call_tool(*args: Any) -> dict:
            calls.append(("call", args))
            return {"is_error": False, "text": "", "raw": {}}

        def list_tools(*args: Any) -> list:
            calls.append(("list", args))
            return []

        for tool in ("mhs__reset", "mhs__permit"):
            result = governed_call(row, row, {"server": row["id"], "tool": tool, "args": {}},
                                   call_tool=call_tool, list_tools=list_tools)
            self.assertTrue(result["is_error"], result)
            error = result["raw"]["structuredContent"]["mhs_error"]
            self.assertEqual(error["mhs_code"], "MHS.AUTH.FORBIDDEN")
            self.assertEqual(error["policy"], "operator_route_only")
        self.assertEqual(calls, [])

    def test_operator_tools_in_the_settings_document_is_reported(self) -> None:
        path = write_settings(Path(self.tmp.name), "http://127.0.0.1:9", endpoint_id="lab",
                              extra={"operator_tools": True})
        config = MHSConfig.load(path)
        self.assertEqual(len(config.warnings), 1)
        self.assertIn("operator_tools", config.warnings[0])
        with mock.patch.dict("os.environ", {"MHS_SKIP_OPENAI4S_SYNC": "1"}):
            report = settings_status(str(path))
        self.assertIn("operator_tools", report["warnings"][0])

    def test_unsafe_shared_settings_refuse_enabled_agent_rows(self) -> None:
        # Verifier finding: operator_tools=true only warned, yet every agent row passes the document to mhs.mcp,
        # so on stock OpenAI4S the model would see mhs__reset/mhs__permit.
        from openai4s_mhs import enable
        from openai4s_mhs.mcp_register import sync_connectors
        from openai4s_mhs.mcpconfig import UnsafeAgentSettings

        for flag in ("operator_tools", "allow_external_sessions"):
            with self.subTest(flag):
                path = write_settings(Path(self.tmp.name) / flag, "http://127.0.0.1:9", endpoint_id="lab",
                                      enabled=False, extra={flag: True})
                with mock.patch.dict("os.environ", {"MHS_SKIP_OPENAI4S_SYNC": "1"}):
                    with self.assertRaises(UnsafeAgentSettings) as ctx:
                        enable(str(path))
                    self.assertEqual(ctx.exception.code, "MHS.HOST.CONFIG_REQUIRED")
                    self.assertFalse(json.loads(path.read_text(encoding="utf-8"))["enabled"], "nothing changed")
                    with self.assertRaises(UnsafeAgentSettings):
                        sync_connectors(MHSConfig.load(path), enabled=True)
                    code, _out, err = _run_cli(["mcp-config", "--config", str(path), "--write"], io.StringIO())
                    self.assertEqual(code, 2)
                    self.assertIn("MHS.HOST.CONFIG_REQUIRED", err)
                    # disabled rows (the listing an operator reviews) are still produced
                    self.assertEqual(_run_cli(["mcp-config", "--config", str(path)], io.StringIO())[0], 0)

    def test_cli_reset_needs_an_operator_name_and_a_terminal(self) -> None:
        path = write_settings(Path(self.tmp.name), "http://127.0.0.1:9", endpoint_id="lab")
        code, out, err = _run_cli(["safety", "reset", "dev", "--config", str(path)], _Terminal("reset\n"))
        self.assertEqual(code, 2, err)
        self.assertIn("--operator", err)
        code, out, err = _run_cli(
            ["safety", "reset", "dev", "--config", str(path), "--operator", "human:alice", "--json"],
            io.StringIO("reset\n"),
        )
        self.assertEqual(code, 4)
        self.assertEqual(json.loads(out)["mhs_code"], "MHS.AUTH.FORBIDDEN")


@unittest.skipUnless(sdk_projection_available(), "mhs.mcp / OpenAI4S MCP client not available")
class OperatorRouteEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-operator-route-")
        self.addCleanup(self.tmp.cleanup)
        self.endpoint = start_endpoint("conveyor", mode="hardware")
        self.addCleanup(self.endpoint.close)
        self.device_id = str(self.endpoint.devices[0]["device_id"])
        # allow_hardware stays false: the software safety envelope is not actuation.
        self.path = write_settings(Path(self.tmp.name), self.endpoint.url)
        self.config = MHSConfig.load(self.path)

    def _safety(self) -> dict:
        with MCPConnector("hw", self.config) as connector:
            response = connector.call("mhs__safety", {"device_id": self.device_id})
        self.assertFalse(response["is_error"], response)
        return dict(response["raw"]["structuredContent"]["safety"])

    def _estop(self) -> None:
        with MCPConnector("hw", self.config) as connector:
            stopped = connector.call("mhs__estop", {"device_id": self.device_id, "reason": "test"})
        self.assertFalse(stopped["is_error"], stopped)
        self.assertTrue(self._safety()["estop_engaged"])

    def test_operator_reset_releases_the_latch_and_is_audited(self) -> None:
        self._estop()
        result = operator_reset("hw", self.device_id, operator="human:alice",
                                reason="conveyor cleared", config=self.config)
        self.assertEqual(result["receipt"]["status"], "completed", result)
        self.assertEqual(result["operator"], "human:alice")
        self.assertIsNone(result["audit_error"])
        self.assertFalse(self._safety()["estop_engaged"])
        ledger = HostLedger(self.config.host_ledger_path)
        records = [item for item in ledger.records() if str(item.get("kind")).startswith("operator_")]
        self.assertEqual([item["kind"] for item in records],
                         ["operator_reset_request", "operator_reset_result"])
        self.assertTrue(all(item["operator"] == "human:alice" for item in records))
        self.assertEqual(records[1]["receipt_digest"].split(":")[0], "sha256")
        self.assertTrue(ledger.verify()["valid"])

    def test_a_refused_reset_is_returned_as_its_receipt(self) -> None:
        with OperatorRoute("hw", self.config, operator="human:alice") as route:
            self.assertTrue({"mhs__reset", "mhs__permit"} <= route.tool_names())
            result = route.reset(self.device_id, reason="nothing is latched")
        self.assertNotEqual(result["receipt"]["status"], "completed", result)
        outcome = [item for item in HostLedger(self.config.host_ledger_path).records()
                   if item.get("kind") == "operator_reset_result"]
        self.assertEqual(outcome[-1]["outcome"], result["receipt"]["status"])

    def test_cli_reset_with_an_operator_at_the_terminal(self) -> None:
        self._estop()
        argv = ["safety", "reset", self.device_id, "--config", str(self.path), "--endpoint", "hw",
                "--operator", "human:bob", "--reason", "jam cleared", "--json"]
        code, out, err = _run_cli(argv, _Terminal("no\n"))
        self.assertEqual(code, 1, err)
        self.assertIn("not confirmed", err)
        self.assertTrue(self._safety()["estop_engaged"], "an unconfirmed reset sends nothing")
        code, out, err = _run_cli(argv, _Terminal("reset\n"))
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["receipt"]["status"], "completed")
        self.assertIn("Type 'reset' to confirm", err)
        self.assertFalse(self._safety()["estop_engaged"])

    def test_cli_reset_finds_the_endpoint_of_the_device_like_estop(self) -> None:
        # Verifier finding: with two endpoints configured, `safety reset <device>` without --endpoint exited 2
        # (MHS.HOST.ENDPOINT_NOT_ALLOWED) while `safety estop <device>` found the device.
        other = start_endpoint("lab")
        self.addCleanup(other.close)
        document = json.loads(self.path.read_text(encoding="utf-8"))
        document["endpoints"].append({"id": "lab", "url": other.url, "label": "lab"})
        two = Path(self.tmp.name) / "two-endpoints.json"
        two.write_text(json.dumps(document), encoding="utf-8")
        self._estop()
        argv = ["safety", "reset", self.device_id, "--config", str(two), "--operator", "human:bob", "--json"]
        code, out, err = _run_cli(argv, _Terminal("reset\n"))
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["receipt"]["status"], "completed")
        self.assertFalse(self._safety()["estop_engaged"])
        code, out, err = _run_cli(["safety", "reset", "no-such-device", "--config", str(two),
                                   "--operator", "human:bob", "--json"], _Terminal("reset\n"))
        self.assertEqual((code, json.loads(out)["mhs_code"]), (1, "MHS.HOST.DEVICE_NOT_FOUND"))

    def test_cli_reset_without_a_terminal_sends_nothing(self) -> None:
        self._estop()
        code, out, err = _run_cli(
            ["safety", "reset", self.device_id, "--config", str(self.path), "--operator", "human:bob"],
            io.StringIO("reset\n"),
        )
        self.assertEqual(code, 4)
        self.assertIn("MHS.AUTH.FORBIDDEN", err)
        self.assertTrue(self._safety()["estop_engaged"])


@unittest.skipUnless(sdk_projection_available(), "mhs.mcp / OpenAI4S MCP client not available")
class OperatorTokenTests(unittest.TestCase):
    """``operator_token_file``: the endpoint sees the operator, not the agent."""

    def test_operator_route_authenticates_with_the_operator_token(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="mhs-operator-token-")
        self.addCleanup(tmp.cleanup)
        token = "op-" + "7" * 32
        endpoint = start_job_endpoint(auth_tokens={token: {"id": "human:carol", "kind": "operator"}})
        self.addCleanup(endpoint.close)
        token_file = Path(tmp.name) / "operator.token"
        token_file.write_text(token + "\n", encoding="utf-8")
        config = MHSConfig.load(write_settings(Path(tmp.name), endpoint.url, endpoint_id="job",
                                               extra={"operator_token_file": str(token_file)}))
        # The agent row carries no token: an authenticated endpoint does not answer it.
        with self.assertRaises(Exception):
            with MCPConnector("job", config):
                pass
        with OperatorRoute("job", config, operator="human:carol") as route:
            stopped = route.call("mhs__estop", {"device_id": endpoint.device_id, "reason": "test"})
            self.assertFalse(stopped["is_error"], stopped)
            result = route.reset(endpoint.device_id, reason="checked")
        receipt = result["receipt"]
        self.assertEqual(receipt["status"], "completed", receipt)
        # The endpoint attributes the reset to the token's operator, not to the
        # projection's self-declared agent principal.
        principal = receipt.get("principal") or {}
        meta = principal.get("x-meta") or {}
        self.assertEqual(principal.get("id"), "human:carol", receipt)
        self.assertEqual((meta.get("authenticated"), meta.get("role")), (True, "operator"), receipt)


if __name__ == "__main__":
    unittest.main()
