"""HOST-001: host policy reaches mhs.mcp through the real MCP path.

Every call in this module goes through OpenAI4S's real ``MCPManager`` /
``MCPConnection`` to a real ``mhs.mcp`` subprocess fronting an in-process
``mhs.server`` endpoint whose manifest declares ``mode: "hardware"``.  No SDK
client method is called directly.  The agent rows never list or run the
operator tools (``mhs__reset``, ``mhs__permit``); the operator route's command
line (``--operator-tools``) does, under the same ``allow_hardware`` policy.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openai4s.mcp_client import MCPManager

from openai4s_mhs.config import MHSConfig

from .hardware_endpoint import start_endpoint
from .host_remediation_support import (
    connector_config,
    find_capability_tool,
    result_code,
    result_receipt,
    write_settings,
)
from .support import sdk_projection_available

CAPABILITY = "cap.world.step.v1"
RESOURCE = "workcell"


@unittest.skipUnless(sdk_projection_available(), "mhs.mcp / OpenAI4S MCP client not available")
class HostPolicyMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-host001-")
        self.addCleanup(self.tmp.cleanup)
        self.endpoint = start_endpoint("conveyor", mode="hardware")
        self.addCleanup(self.endpoint.close)
        self.device_id = str(self.endpoint.devices[0]["device_id"])
        self.manager = MCPManager()
        self.addCleanup(self.manager.shutdown)

        directory = Path(self.tmp.name)
        self.allowed_path = write_settings(
            directory / "allowed", self.endpoint.url, allow_hardware=True
        )
        self.denied_path = write_settings(
            directory / "denied", self.endpoint.url, allow_hardware=False
        )
        self.disabled_path = write_settings(
            directory / "disabled",
            self.endpoint.url,
            enabled=False,
            allow_hardware=True,
        )
        self.allowed = connector_config(
            self.endpoint.url, self.allowed_path, connector_id="mhs-hw-allowed"
        )
        self.denied = connector_config(
            self.endpoint.url, self.denied_path, connector_id="mhs-hw-denied"
        )
        self.disabled = connector_config(
            self.endpoint.url, self.disabled_path, connector_id="mhs-hw-disabled"
        )
        # The host operator route: same settings document, --operator-tools.
        self.operator = connector_config(
            self.endpoint.url,
            self.denied_path,
            connector_id="mhs-hw-operator",
            operator_tools=True,
        )

    # -- helpers -----------------------------------------------------------
    def _read_revision(self) -> int:
        response = self.manager.call_tool(
            "mhs-hw-allowed",
            self.allowed,
            "mhs__read",
            {"device_id": self.device_id, "resource_id": RESOURCE},
        )
        self.assertFalse(response["is_error"], response)
        structured = response["raw"]["structuredContent"]
        return int(structured["read"]["revision"])

    def _call_capability(self, connector, config) -> dict:
        return self.manager.call_tool(
            connector,
            config,
            self._capability_name(),
            {"ticks": 2},
        )

    def _capability_name(self) -> str:
        tools = self.manager.list_tools("mhs-hw-denied", self.denied)
        return str(find_capability_tool(tools, CAPABILITY)["name"])

    # -- tests -------------------------------------------------------------
    def test_hardware_disabled_capability_read_operations_and_permit_refuse(self) -> None:
        tools = self.manager.list_tools("mhs-hw-denied", self.denied)
        tool = find_capability_tool(tools, CAPABILITY)
        self.assertTrue(tool["x-mhs"]["hardware_disabled"])
        before = self._read_revision()

        response = self._call_capability("mhs-hw-denied", self.denied)
        self.assertTrue(response["is_error"], response)
        self.assertEqual(result_code(response), "MHS.AUTH.HARDWARE_DISABLED")
        self.assertIsNone(result_receipt(response))

        for name, arguments in (
            ("mhs__read", {"device_id": self.device_id, "resource_id": RESOURCE}),
            ("mhs__operations", {"device_id": self.device_id}),
        ):
            denied = self.manager.call_tool("mhs-hw-denied", self.denied, name, arguments)
            self.assertTrue(denied["is_error"], (name, denied))
            self.assertEqual(result_code(denied), "MHS.AUTH.HARDWARE_DISABLED", name)
        permit_arguments = {"device_id": self.device_id, "capability_id": CAPABILITY,
                            "input_digest": "sha256:" + "0" * 64}
        # The agent row does not even have the permit tool...
        agent_permit = self.manager.call_tool(
            "mhs-hw-denied", self.denied, "mhs__permit", permit_arguments
        )
        self.assertTrue(agent_permit["is_error"], agent_permit)
        self.assertEqual(result_code(agent_permit), "MHS.AUTH.FORBIDDEN")
        # ...and the operator route still may not permit hardware actuation
        # while allow_hardware is false.
        operator_permit = self.manager.call_tool(
            "mhs-hw-operator", self.operator, "mhs__permit", permit_arguments
        )
        self.assertTrue(operator_permit["is_error"], operator_permit)
        self.assertEqual(result_code(operator_permit), "MHS.AUTH.HARDWARE_DISABLED")

        # No effect from the refused capability/read/operations/permit calls.
        self.assertEqual(self._read_revision(), before)

        # Discovery, safety status and the software safety envelope remain
        # available to the authorized connector.
        self.assertFalse(
            self.manager.call_tool(
                "mhs-hw-denied", self.denied, "mhs__inspect", {"device_id": self.device_id}
            )["is_error"]
        )
        self.assertFalse(
            self.manager.call_tool(
                "mhs-hw-denied", self.denied, "mhs__safety", {"device_id": self.device_id}
            )["is_error"]
        )
        stopped = self.manager.call_tool(
            "mhs-hw-denied",
            self.denied,
            "mhs__estop",
            {"device_id": self.device_id, "reason": "HOST-001 safety-path test"},
        )
        self.assertFalse(stopped["is_error"], stopped)
        receipt = result_receipt(stopped)
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(receipt["output"]["latched"])
        # The agent row cannot release the latch; the operator route can.
        agent_reset = self.manager.call_tool(
            "mhs-hw-denied", self.denied, "mhs__reset", {"device_id": self.device_id}
        )
        self.assertTrue(agent_reset["is_error"], agent_reset)
        self.assertEqual(result_code(agent_reset), "MHS.AUTH.FORBIDDEN")
        reset = self.manager.call_tool(
            "mhs-hw-operator", self.operator, "mhs__reset", {"device_id": self.device_id}
        )
        self.assertFalse(reset["is_error"], reset)
        self.assertEqual(result_receipt(reset)["status"], "completed")

    def test_operator_tools_are_listed_only_on_the_operator_route(self) -> None:
        agent = {item["name"] for item in self.manager.list_tools("mhs-hw-denied", self.denied)}
        operator = {
            item["name"] for item in self.manager.list_tools("mhs-hw-operator", self.operator)
        }
        self.assertTrue({"mhs__estop", "mhs__safety", "mhs__inspect"} <= agent, agent)
        self.assertFalse({"mhs__reset", "mhs__permit"} & agent, agent)
        self.assertTrue({"mhs__reset", "mhs__permit"} <= operator, operator)

    def test_allow_hardware_true_permits_capability_and_read(self) -> None:
        before = self._read_revision()
        response = self._call_capability("mhs-hw-allowed", self.allowed)
        self.assertFalse(response["is_error"], response)
        receipt = result_receipt(response)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["state_revision_after"], before + 1)
        read = self.manager.call_tool(
            "mhs-hw-allowed",
            self.allowed,
            "mhs__read",
            {"device_id": self.device_id, "resource_id": RESOURCE},
        )
        self.assertFalse(read["is_error"], read)
        self.assertEqual(read["raw"]["structuredContent"]["read"]["revision"], before + 1)

    def test_enabled_false_refuses_every_tool_without_an_endpoint_call(self) -> None:
        before = self._read_revision()
        tools = self.manager.list_tools("mhs-hw-disabled", self.disabled)
        self.assertEqual(tools, [])
        calls = (
            ("mhs__devices", {}),
            ("mhs__estop", {"device_id": self.device_id, "reason": "must refuse"}),
            (self._capability_name(), {"ticks": 1}),
        )
        for name, arguments in calls:
            response = self.manager.call_tool(
                "mhs-hw-disabled", self.disabled, name, arguments
            )
            self.assertTrue(response["is_error"], (name, response))
            self.assertEqual(result_code(response), "MHS.AUTH.FORBIDDEN", name)
        # The still-authorized reader sees no revision change.
        self.assertEqual(self._read_revision(), before)

    def test_connector_entry_carries_the_policy_path(self) -> None:
        from openai4s_mhs.mcpconfig import connector_entry

        config = MHSConfig.load(self.denied_path)
        entry = connector_entry(
            config.endpoints[0],
            python="/usr/bin/python3",
            config_path=config.config_path,
        )
        self.assertIn("--config", entry["command"])
        self.assertEqual(entry["command"][entry["command"].index("--config") + 1], str(self.denied_path))
        self.assertFalse(entry["enabled"])
        # An agent row never carries the operator flag; the operator route adds it.
        self.assertNotIn("--operator-tools", entry["command"])
        from openai4s_mhs.mcpconfig import operator_argv

        argv = operator_argv(config.endpoints[0], config, python="/usr/bin/python3")
        self.assertEqual(argv[: len(entry["command"])], entry["command"])
        self.assertEqual(argv[len(entry["command"]):], ["--operator-tools"])


if __name__ == "__main__":
    unittest.main()
