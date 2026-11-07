"""HOST-002: trusted, device-bound emergency stop through the real MCP path.

The ordinary OpenAI4S MCP tool is approval-gated; this test models a *denying*
ordinary approval context and shows the trusted integration helper still reaches
the endpoint, latches the stop and records an audit line.  It also checks that
an arbitrary endpoint/device and a disabled connector are refused.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from openai4s_mhs.config import MHSConfig
from openai4s_mhs.emergency import EmergencyStopError, emergency_stop
from openai4s_mhs.host_evidence import HostLedger
from openai4s_mhs.mcp_invoke import MCPConnector
from openai4s_mhs.operator_route import reset as operator_reset

from .hardware_endpoint import start_endpoint
from .host_remediation_support import write_settings
from .support import sdk_projection_available


class DenyingOrdinaryApproval:
    """Stands in for a PermissionBroker whose human/policy decision is 'deny'."""

    def gate(self, **_kwargs):
        return {"allow": False, "message": "HOST-002 test: ordinary approval denied"}

    def approvals_reviewer_for(self, **_kwargs):
        return "user"


@unittest.skipUnless(sdk_projection_available(), "mhs.mcp / OpenAI4S MCP client not available")
class TrustedEmergencyStopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-host002-")
        self.addCleanup(self.tmp.cleanup)
        self.endpoint = start_endpoint("conveyor", mode="hardware")
        self.addCleanup(self.endpoint.close)
        self.device_id = str(self.endpoint.devices[0]["device_id"])
        directory = Path(self.tmp.name)
        self.allowed_path = write_settings(
            directory / "allowed",
            self.endpoint.url,
            allow_hardware=False,  # e-stop must still work on hardware
            estop_devices=[self.device_id],
        )
        self.denied_device_path = write_settings(
            directory / "denied-device",
            self.endpoint.url,
            allow_hardware=False,
            estop_devices=["mhs://some-other-endpoint/other-device"],
        )
        self.disabled_path = write_settings(
            directory / "disabled",
            self.endpoint.url,
            enabled=False,
            allow_hardware=True,
            estop_devices=[self.device_id],
        )

    def _safety(self, config: MHSConfig) -> dict:
        with MCPConnector("hw", config) as connector:
            response = connector.call("mhs__safety", {"device_id": self.device_id})
            self.assertFalse(response["is_error"], response)
            return dict(response["raw"]["structuredContent"]["safety"])

    def test_denied_ordinary_approval_does_not_block_trusted_stop(self) -> None:
        from openai4s.config import get_config
        from openai4s.host_dispatch import HostDispatcher
        from openai4s.tools.mcp import CallMCPTool

        config = MHSConfig.load(self.allowed_path)
        # The ordinary MCP action is approval-gated and this context denies it.
        self.assertTrue(CallMCPTool.requires_approval)
        denying = DenyingOrdinaryApproval()
        self.assertFalse(denying.gate(method="mcp_call")["allow"])
        with mock.patch("openai4s.permissions.broker", return_value=denying):
            dispatcher = HostDispatcher(
                cfg=get_config(), workspace=Path(self.tmp.name) / "workspace"
            )
            ordinary = dispatcher(
                "mcp_call",
                [
                    {
                        "server": "mhs-hw",
                        "tool": "mhs__estop",
                        "args": {"device_id": self.device_id, "reason": "ordinary"},
                    }
                ],
            )
            self.assertIn("Permission denied", ordinary["error"])
            result = emergency_stop(
                "hw", self.device_id, "HOST-002 denied-approval test", config=config
            )
        self.assertEqual(result["receipt"]["status"], "completed")
        self.assertTrue(result["latched"])
        self.assertTrue(result["receipt"]["output"]["latched"])
        self.assertIsNone(result["audit_error"])
        status = self._safety(config)
        self.assertTrue(status["estop_engaged"])
        self.assertEqual(status["estop"]["engaged"], True)

        # A local audited line exists in the hash-chained host ledger.
        ledger = HostLedger(config.host_ledger_path)
        kinds = [item.get("kind") for item in ledger.records()]
        self.assertIn("emergency_stop_request", kinds)
        self.assertIn("emergency_stop_result", kinds)
        self.assertTrue(ledger.verify()["valid"])

        # The agent connector cannot release the latch...
        with MCPConnector("hw", config) as connector:
            refused = connector.call("mhs__reset", {"device_id": self.device_id})
        self.assertTrue(refused["is_error"], refused)
        self.assertEqual(
            refused["raw"]["structuredContent"]["mhs_error"]["mhs_code"], "MHS.AUTH.FORBIDDEN"
        )
        self.assertTrue(self._safety(config)["estop_engaged"])
        # ...a reset is a separate human decision on the host operator route.
        result = operator_reset(
            "hw", self.device_id, operator="human:test-operator",
            reason="HOST-002 test: area checked", config=config,
        )
        self.assertEqual(result["receipt"]["status"], "completed", result)
        self.assertIsNone(result["audit_error"])
        self.assertFalse(self._safety(config)["estop_engaged"])
        records = HostLedger(config.host_ledger_path).records()
        reset_records = [item for item in records if item.get("kind") == "operator_reset_result"]
        self.assertEqual(len(reset_records), 1)
        self.assertEqual(reset_records[0]["operator"], "human:test-operator")
        self.assertEqual(reset_records[0]["outcome"], "completed")

    def test_unauthorized_device_and_endpoint_are_refused(self) -> None:
        config = MHSConfig.load(self.denied_device_path)
        with self.assertRaises(EmergencyStopError) as caught:
            emergency_stop("hw", self.device_id, "must refuse", config=config)
        self.assertEqual(caught.exception.code, "MHS.HOST.DEVICE_NOT_ALLOWED")

        allowed = MHSConfig.load(self.allowed_path)
        with self.assertRaises(EmergencyStopError) as caught:
            emergency_stop("not-configured", self.device_id, "must refuse", config=allowed)
        self.assertEqual(caught.exception.code, "MHS.HOST.ENDPOINT_NOT_ALLOWED")

        # No endpoint effect from either refusal.
        self.assertFalse(self._safety(allowed)["estop_engaged"])

    def test_disabled_connector_refuses_the_trusted_route(self) -> None:
        config = MHSConfig.load(self.disabled_path)
        with self.assertRaises(EmergencyStopError) as caught:
            emergency_stop("hw", self.device_id, "must refuse", config=config)
        self.assertEqual(caught.exception.code, "MHS.AUTH.FORBIDDEN")
        self.assertFalse(self._safety(MHSConfig.load(self.allowed_path))["estop_engaged"])


if __name__ == "__main__":
    unittest.main()
