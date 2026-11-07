"""SURF-01: under the default policy the model can neither self-permit nor reset.

Ports of ``integration-surfaces/hw_mcp.py`` and
``verify-integration-surfaces/reset_noallow.py`` (the R2 conveyor declared
``mode: "hardware"``), plus the ``mcp_drive.py`` self-permit steps.  The
endpoint side of these repros is WP-04's (``tests/safety``); these tests cover
the MCP projection: ``mhs__reset`` and ``mhs__permit`` are operator tools that
are neither listed nor callable unless the host policy sets ``operator_tools``.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

from mhs.mcp import OPERATOR_TOOLS, MCPPolicy

from tests.surfaces import _support as s

VALVE = "cap.actuation.valve.v1"


class DefaultPolicyTests(unittest.TestCase):
    def test_operator_tools_are_not_listed_by_default(self) -> None:
        spec, server = s.reference("conveyor")
        self.addCleanup(spec.close)
        for policy in (None, s.policy(), s.policy(allow_hardware=True)):
            with self.subTest(policy=policy and policy.to_dict()):
                mcp = s.Mcp(server, policy=policy)
                names = {tool["name"] for tool in mcp.tools()}
                self.assertFalse(OPERATOR_TOOLS & names, names)
                self.assertIn("mhs__estop", names)
                mcp.close()

    def test_hidden_operator_tools_refuse_without_an_endpoint_call(self) -> None:
        spec, server = s.reference("conveyor")
        self.addCleanup(spec.close)
        mcp = s.Mcp(server)
        mark = mcp.mark()
        for name, arguments in (
            ("mhs__permit", {"capability_id": VALVE, "input": {"gate": "divert"}}),
            ("mhs__permit", {"capability_id": VALVE, "input": {"gate": "divert"},
                             "approvals": [{"principal": "human:operator", "method": "human_click"}]}),
            ("mhs__reset", {"device_id": s.CONVEYOR}),
        ):
            with self.subTest(tool=name, arguments=arguments):
                result = mcp.call(name, arguments)
                self.assertTrue(result["isError"], result)
                self.assertEqual(s.mhs_error(result)["mhs_code"], "MHS.AUTH.FORBIDDEN")
                self.assertEqual(s.mhs_error(result)["policy"], "operator_tools=false")
                self.assertIsNone(result["structuredContent"]["receipt"])
        self.assertNotIn("mhs.safety.permit", mcp.sent_since(mark))
        self.assertNotIn("mhs.safety.reset", mcp.sent_since(mark))
        self.assertNotIn("mhs.session.open", mcp.sent_since(mark))

    def test_hw_mcp_model_cannot_self_permit_or_reset_hardware(self) -> None:
        # hw_mcp.py: allow_hardware=true, R2 hardware conveyor.
        spec, server = s.reference("conveyor", hardware=True)
        self.addCleanup(spec.close)
        mcp = s.Mcp(server, policy=s.policy(allow_hardware=True))
        valve = mcp.tool("__actuation_valve")
        tool = next(item for item in mcp.tools() if item["name"] == valve)
        self.assertEqual(tool["x-mhs"]["mode"], "hardware")

        no_permit = mcp.call(valve, {"gate": "divert"})
        self.assertFalse(no_permit["isError"], no_permit)
        self.assertEqual(s.receipt(no_permit)["status"], "rejected")
        self.assertEqual(s.mhs_error(no_permit)["mhs_code"], "MHS.SAFETY.PERMIT_INVALID")

        self_permit = mcp.call("mhs__permit", {"capability_id": VALVE, "input": {"gate": "divert"}})
        self.assertTrue(self_permit["isError"], self_permit)
        self.assertNotIn("permit", self_permit["structuredContent"])

        stopped = mcp.call("mhs__estop", {"device_id": s.CONVEYOR, "reason": "operator stop"})
        self.assertFalse(stopped["isError"], stopped)
        self.assertEqual(stopped["structuredContent"]["estop"]["status"], "completed")

        reset = mcp.call("mhs__reset", {"device_id": s.CONVEYOR})
        self.assertTrue(reset["isError"], reset)
        self.assertEqual(s.mhs_error(reset)["mhs_code"], "MHS.AUTH.FORBIDDEN")
        safety = mcp.call("mhs__safety", {"device_id": s.CONVEYOR})["structuredContent"]["safety"]
        self.assertTrue(safety["estop"]["engaged"], safety)

        restart = mcp.call(mcp.tool("__mhs_reference_start"), {"speed_mm_s": 100})
        self.assertFalse(restart["isError"], restart)
        self.assertEqual(s.receipt(restart)["status"], "rejected")
        self.assertEqual(s.mhs_error(restart)["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_reset_noallow_operator_latch_survives_the_model(self) -> None:
        # reset_noallow.py: the operator latches the e-stop; allow_hardware=false.
        spec, server = s.reference("conveyor", hardware=True)
        self.addCleanup(spec.close)
        operator = s.client(server)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # compat mode warns about the unauthenticated human claim
            operator.open_session([s.CONVEYOR], mode="hardware", principal={"id": "operator", "kind": "human"})
        self.assertEqual(operator.estop("operator panic", device_id=s.CONVEYOR)["status"], "completed")

        mcp = s.Mcp(server, policy=s.policy(allow_hardware=False))
        start = mcp.tool("__mhs_reference_start")
        actuation = mcp.call(start, {"speed_mm_s": 100})
        self.assertTrue(actuation["isError"])
        self.assertEqual(s.mhs_error(actuation)["mhs_code"], "MHS.AUTH.HARDWARE_DISABLED")
        reset = mcp.call("mhs__reset", {"device_id": s.CONVEYOR})
        self.assertTrue(reset["isError"])
        self.assertEqual(s.mhs_error(reset)["mhs_code"], "MHS.AUTH.FORBIDDEN")
        self.assertTrue(operator.safety_status(s.CONVEYOR)["estop"]["engaged"])
        resumed = operator.invoke("x-cap.mhs-reference.start.v1", {"speed_mm_s": 100}, device_id=s.CONVEYOR)
        self.assertEqual(resumed["status"], "rejected")
        self.assertEqual(resumed["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")


class OperatorToolsTests(unittest.TestCase):
    def test_operator_connector_lists_and_uses_reset_and_permit(self) -> None:
        spec, server = s.reference("conveyor")
        self.addCleanup(spec.close)
        mcp = s.Mcp(server, policy=s.policy(operator_tools=True))
        names = {tool["name"] for tool in mcp.tools()}
        self.assertTrue(OPERATOR_TOOLS <= names, names)
        permit = mcp.call("mhs__permit", {"capability_id": VALVE, "input": {"gate": "divert"}})
        self.assertFalse(permit["isError"], permit)
        permit_id = permit["structuredContent"]["permit"]["permit_id"]
        valve = mcp.call(mcp.tool("__actuation_valve"), {"gate": "divert", "permit_id": permit_id})
        self.assertEqual(s.receipt(valve)["status"], "completed")
        mcp.call("mhs__estop", {"device_id": s.CONVEYOR, "reason": "operator test"})
        reset = mcp.call("mhs__reset", {"device_id": s.CONVEYOR})
        self.assertFalse(reset["isError"], reset)
        self.assertEqual(reset["structuredContent"]["reset"]["status"], "completed")

    def test_policy_document_flags_default_to_false(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mhs-surfaces-policy-") as tmp:
            path = Path(tmp) / "mhs.json"
            path.write_text(json.dumps({"enabled": True}), encoding="utf-8")
            loaded = MCPPolicy.load(path)
            self.assertEqual((loaded.enabled, loaded.allow_hardware, loaded.operator_tools,
                              loaded.allow_external_sessions), (True, False, False, False))
            # Only a JSON true enables a flag: the string "true" does not.
            path.write_text(json.dumps({"enabled": True, "operator_tools": "true",
                                        "allow_external_sessions": 1, "allow_hardware": "yes"}), encoding="utf-8")
            loaded = MCPPolicy.load(path)
            self.assertEqual((loaded.allow_hardware, loaded.operator_tools, loaded.allow_external_sessions),
                             (False, False, False))
            # enabled follows the same rule: {"enabled": "false"} (a string) leaves the projection off
            for value in ("false", "true", 1):
                path.write_text(json.dumps({"enabled": value}), encoding="utf-8")
                with mock.patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("MHS_ENABLED", None)
                    self.assertFalse(MCPPolicy.load(path).enabled, value)
            path.write_text(json.dumps({"enabled": True, "operator_tools": True,
                                        "allow_external_sessions": True}), encoding="utf-8")
            loaded = MCPPolicy.load(path)
            self.assertTrue(loaded.operator_tools and loaded.allow_external_sessions)
            self.assertEqual(loaded.to_dict()["operator_tools"], True)
        direct = MCPPolicy.direct_launch()
        self.assertEqual((direct.enabled, direct.allow_hardware, direct.operator_tools,
                          direct.allow_external_sessions), (True, False, False, False))


if __name__ == "__main__":
    unittest.main()
