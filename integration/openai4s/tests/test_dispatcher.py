"""The native path end to end: HostDispatcher -> Tool -> MHSHost -> endpoint."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openai4s.config import get_config
from openai4s.host_dispatch import HostDispatcher
from openai4s.tools.registry import execute_tool_call, get_tool

from openai4s_mhs import install
from openai4s_mhs.config import EndpointSpec, MHSConfig
from openai4s_mhs.host import MHSHost

from .fake_endpoint import FakeMHSServer, fake_connect


class DispatcherNativePathTests(unittest.TestCase):
    def setUp(self) -> None:
        install(MHSConfig(enabled=True, sync_openai4s=False))
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-dispatch-test-")
        self.addCleanup(self.tmp.cleanup)
        self.dispatcher = HostDispatcher(
            cfg=get_config(), workspace=Path(self.tmp.name) / "workspace"
        )
        self.server = FakeMHSServer()
        self._inject(self.server)

    def _inject(self, server: FakeMHSServer) -> None:
        config = MHSConfig(
            endpoints=[EndpointSpec(id="fake", url="http://127.0.0.1:1")],
            evidence_log=str(Path(self.tmp.name) / "evidence.jsonl"),
        )
        host = MHSHost(config, sdk_connect=fake_connect(server))
        self.addCleanup(host.close)
        # The lazy property reads this instance attribute; no monkeypatching of
        # the property itself, so a second dispatcher still gets its own host.
        self.dispatcher._openai4s_mhs_host = host

    # -- direct dispatcher calls ------------------------------------------
    def test_devices_through_dispatcher(self) -> None:
        result = self.dispatcher("mhs_devices", [{}])
        self.assertEqual(result["count"], 1)
        device = result["devices"][0]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["fidelity"]["level"], "F0")
        self.assertIn("fidelity", result["note"].lower())

    def test_read_through_dispatcher(self) -> None:
        result = self.dispatcher("mhs_read", [{"device_id": "conveyor"}])
        self.assertEqual(result["revision"], 0)
        self.assertEqual(result["state"]["tick"], 0)

    def test_command_through_dispatcher_returns_receipt_and_ledger_entry(self) -> None:
        result = self.dispatcher(
            "mhs_command",
            [
                {
                    "device_id": "conveyor",
                    "capability_id": "cap.world.step.v1",
                    "input": {"ticks": 7},
                }
            ],
        )
        self.assertEqual(result["status"], "completed")
        self.assertIn("command_id", result)
        self.assertIn("evidence", result)
        self.assertEqual(result["state_revision_after"], 1)
        self.assertEqual(self.server.tick, 7)
        ledger = self.dispatcher.openai4s_mhs_host.ledger()
        self.assertEqual(ledger[-1]["command_id"], result["command_id"])

    def test_unknown_outcome_teaches_the_model_to_re_read(self) -> None:
        server = FakeMHSServer(risk_class="R0", unknown_once=True)
        self._inject(server)
        result = self.dispatcher(
            "mhs_command",
            [
                {
                    "device_id": "conveyor",
                    "capability_id": "cap.world.step.v1",
                    "input": {"ticks": 3},
                }
            ],
        )
        self.assertEqual(result["status"], "unknown")
        self.assertTrue(result["outcome_unknown"])
        self.assertIn("Do not retry blindly", result["agent_guidance"])
        self.assertEqual(server.tick, 0)

    def test_mhs_code_is_propagated_for_a_host_refusal(self) -> None:
        server = FakeMHSServer(mode="hardware")
        self._inject(server)
        result = self.dispatcher("mhs_read", [{"device_id": "conveyor"}])
        self.assertEqual(result["mhs_code"], "MHS.HOST.HARDWARE_GATED")
        self.assertIn("allow_hardware", result["error"])
        self.assertEqual(server.sessions, {})

    def test_safety_estop_and_rejection_receipt(self) -> None:
        stopped = self.dispatcher(
            "mhs_safety", [{"action": "estop", "device_id": "conveyor", "reason": "test"}]
        )
        self.assertEqual(stopped["status"], "completed")
        rejected = self.dispatcher(
            "mhs_command",
            [
                {
                    "device_id": "conveyor",
                    "capability_id": "cap.world.step.v1",
                    "input": {"ticks": 1},
                }
            ],
        )
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["error"]["code"], "MHS.SAFETY.INTERLOCK_OPEN")
        self.assertEqual(self.server.tick, 0)
        status = self.dispatcher(
            "mhs_safety", [{"action": "status", "device_id": "conveyor"}]
        )
        self.assertEqual(status["estop"], "engaged")

        # Releasing the latch is the operator's decision: the model-facing tool
        # refuses it before the endpoint is contacted and the latch holds.
        reset = self.dispatcher("mhs_safety", [{"action": "reset", "device_id": "conveyor"}])
        self.assertEqual(reset["mhs_code"], "MHS.AUTH.FORBIDDEN")
        self.assertEqual(reset["details"]["policy"], "operator_route_only")
        self.assertEqual(self.server.estop_state, "engaged")
        self.assertEqual(
            get_tool("mhs_safety").parameters["properties"]["action"]["enum"], ["status", "estop"]
        )

    def test_evidence_and_operations_through_dispatcher(self) -> None:
        self.dispatcher(
            "mhs_command",
            [
                {
                    "device_id": "conveyor",
                    "capability_id": "cap.world.step.v1",
                    "input": {"ticks": 1},
                }
            ],
        )
        export = self.dispatcher("mhs_evidence", [{"action": "export"}])
        self.assertGreaterEqual(export["count"], 1)
        report = self.dispatcher("mhs_evidence", [{"action": "verify"}])
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["checked"], export["count"])
        ledger = self.dispatcher("mhs_evidence", [{"action": "ledger"}])
        self.assertEqual(ledger["count"], 1)
        operations = self.dispatcher(
            "mhs_operations", [{"action": "list", "device_id": "conveyor"}]
        )
        self.assertEqual(operations["operations"], [])

    def test_connect_actions(self) -> None:
        endpoints = self.dispatcher("mhs_connect", [{"action": "endpoints"}])
        self.assertEqual(endpoints["count"], 1)
        self.assertEqual(endpoints["endpoints"][0]["id"], "fake")
        discovered = self.dispatcher("mhs_connect", [{"action": "discover"}])
        self.assertEqual(len(discovered["devices"]), 1)

    # -- execute_tool_call (the model-facing path) ------------------------
    def test_execute_tool_call_devices_and_command(self) -> None:
        text, ok = execute_tool_call(
            self.dispatcher, {"name": "mhs_devices", "arguments": {}}
        )
        self.assertTrue(ok, text)
        self.assertIn("[Tool: mhs_devices]", text)
        self.assertIn("simulated", text)

        text, ok = execute_tool_call(
            self.dispatcher,
            {
                "name": "mhs_command",
                "arguments": {
                    "device_id": "conveyor",
                    "capability_id": "cap.world.step.v1",
                    "input": {"ticks": 4},
                },
            },
        )
        self.assertTrue(ok, text)
        self.assertIn("completed", text)
        self.assertEqual(self.server.tick, 4)

    def test_execute_tool_call_rejects_extra_arguments(self) -> None:
        text, ok = execute_tool_call(
            self.dispatcher,
            {
                "name": "mhs_read",
                "arguments": {"device_id": "conveyor", "unexpected": 1},
            },
        )
        self.assertFalse(ok)
        self.assertIn("invalid arguments", text.lower())

    def test_tool_schemas_reject_missing_required_arguments(self) -> None:
        tool = get_tool("mhs_command")
        self.assertIsNotNone(tool)
        self.assertIsNotNone(tool.validation_error({"device_id": "conveyor"}))
        text, ok = execute_tool_call(
            self.dispatcher,
            {"name": "mhs_command", "arguments": {"device_id": "conveyor"}},
        )
        self.assertFalse(ok)
        self.assertIn("invalid arguments", text.lower())


if __name__ == "__main__":
    unittest.main()
