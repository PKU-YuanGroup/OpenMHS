"""The MCP tool surface: stable names, bounded descriptions with limits and facts, annotations.

Findings: SURF-06 (annotations, parameter descriptions, bounded output),
DRV-10 and MISSED anthropic-fidelity (the enforced limits, interlocks and
facts reach the model in the tool description).
"""

from __future__ import annotations

import contextlib
import copy
import io
import re
import unittest
from typing import Any, Iterator

from mhs.mcp import META_KEY, OPERATOR_TOOLS, TOOL_DESCRIPTION_LIMIT, MCPProjection

from tests.endpoints import support as endpoint_support
from tests.surfaces import _support as s

DISCOVERY = ["mhs__devices", "mhs__estop", "mhs__evidence", "mhs__inspect", "mhs__operations", "mhs__read",
             "mhs__safety"]
#: tools/list names under the default policy: discovery tools plus the capability
#: tools, whose names never change (tests/endpoints/test_reference_models.py
#: TOOL_NAMES holds the same capability names).
SNAPSHOT = {
    "conveyor": DISCOVERY + [
        "mhs__lab_conveyor_workcell__actuation_valve", "mhs__lab_conveyor_workcell__mhs_reference_feed",
        "mhs__lab_conveyor_workcell__mhs_reference_start", "mhs__lab_conveyor_workcell__motion_stop",
        "mhs__lab_conveyor_workcell__world_restore", "mhs__lab_conveyor_workcell__world_snapshot",
        "mhs__lab_conveyor_workcell__world_state", "mhs__lab_conveyor_workcell__world_step",
    ],
    "lab": DISCOVERY + [
        "mhs__lab_liquid_handler__fluid_aspirate", "mhs__lab_liquid_handler__fluid_dispense",
        "mhs__lab_liquid_handler__fluid_level", "mhs__lab_liquid_handler__fluid_transfer",
        "mhs__lab_liquid_handler__motion_stop", "mhs__lab_plate_reader__measure_spectrum",
        "mhs__lab_sample_mover__motion_stop", "mhs__lab_sample_mover__sample_move",
    ],
    "arm": DISCOVERY + [
        "mhs__robot_arm_2dof__motion_cartesian_pos_529c54", "mhs__robot_arm_2dof__motion_home",
        "mhs__robot_arm_2dof__motion_joint_positio_288cd9", "mhs__robot_arm_2dof__motion_stop",
        "mhs__robot_arm_2dof__world_restore", "mhs__robot_arm_2dof__world_seed",
        "mhs__robot_arm_2dof__world_snapshot", "mhs__robot_arm_2dof__world_state",
    ],
}


def _properties(schema: Any, path: str = "") -> Iterator[tuple[str, dict]]:
    """Every input property of a tool schema, nested ones included."""
    if not isinstance(schema, dict):
        return
    target = schema.get("items") if isinstance(schema.get("items"), dict) else schema
    for key, prop in (target.get("properties") or {}).items():
        if isinstance(prop, dict):
            yield f"{path}{key}", prop
            yield from _properties(prop, f"{path}{key}.")


def _numeric(prop: dict) -> bool:
    kinds = prop.get("type")
    kinds = [kinds] if isinstance(kinds, str) else list(kinds or [])
    if "array" in kinds and isinstance(prop.get("items"), dict):
        return _numeric(prop["items"])
    return "number" in kinds or "integer" in kinds


class ToolListSnapshotTests(unittest.TestCase):
    def test_tool_names_are_unchanged_for_conveyor_lab_and_arm(self) -> None:
        for name, expected in SNAPSHOT.items():
            with self.subTest(endpoint=name):
                spec, server = s.reference(name)
                try:
                    for describe in (False, True):
                        mcp = s.Mcp(server, describe_inputs=describe)
                        self.assertEqual(sorted(tool["name"] for tool in mcp.tools()), sorted(expected))
                    operator = s.Mcp(server, policy=s.policy(operator_tools=True))
                    self.assertEqual(sorted(tool["name"] for tool in operator.tools()),
                                     sorted(expected + sorted(OPERATOR_TOOLS)))
                finally:
                    spec.close()

    def test_descriptions_are_bounded_and_every_input_property_is_described_with_its_unit(self) -> None:
        for name in SNAPSHOT:
            spec, server = s.reference(name)
            try:
                mcp = s.Mcp(server, describe_inputs=True, policy=s.policy(operator_tools=True))
                for tool in mcp.tools():
                    with self.subTest(endpoint=name, tool=tool["name"]):
                        self.assertLessEqual(len(tool["description"].encode("utf-8")), TOOL_DESCRIPTION_LIMIT)
                        self.assertIn("annotations", tool)
                        for path, prop in _properties(tool["inputSchema"]):
                            description = str(prop.get("description") or "")
                            self.assertTrue(description.strip(), f"{path} has no description")
                            if _numeric(prop):
                                unit = prop.get("x-mhs-unit") or (prop.get("items") or {}).get("x-mhs-unit")
                                if unit:
                                    self.assertRegex(description, r"[Uu]nit:? " + re.escape(unit) + r"\b", path)
                                else:
                                    # no schema unit: the enforced limit's unit, else "none declared"
                                    self.assertRegex(description, r"[Uu]nit:? \S", path)
                                    match = re.search(r"Endpoint-enforced limit: \S+ (\S+?) \(", description)
                                    if match and re.match(r"[A-Za-z%/]", match.group(1)):
                                        self.assertIn(f"Unit: {match.group(1)}.", description, path)
            finally:
                spec.close()

    def test_in_process_default_keeps_the_authored_schema(self) -> None:
        # MCPProjection(describe_inputs=False) is what the driver gate (G8) lints.
        spec, server = s.reference("conveyor")
        self.addCleanup(spec.close)
        mcp = s.Mcp(server)
        step = next(tool for tool in mcp.tools() if tool["name"].endswith("__world_step"))
        self.assertNotIn("description", step["inputSchema"]["properties"]["ticks"])


class DescriptionContentTests(unittest.TestCase):
    @staticmethod
    def _capability_tool(client: Any) -> dict:
        projection = MCPProjection(client)
        with contextlib.redirect_stderr(io.StringIO()):
            projection.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        listed = projection.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        return next(item for item in listed["result"]["tools"] if "x-mhs" in item)

    def test_conveyor_step_states_the_enforced_limit_and_interlock(self) -> None:
        spec, server = s.reference("conveyor")
        self.addCleanup(spec.close)
        mcp = s.Mcp(server, describe_inputs=True)
        tools = {tool["name"]: tool for tool in mcp.tools()}
        step = tools["mhs__lab_conveyor_workcell__world_step"]
        self.assertIn("Mode: simulated. Risk: R1.", step["description"])
        self.assertIn("ticks 1..10000", step["description"])
        self.assertIn("door_closed", step["description"])
        self.assertIn("Not a safety-rated channel", step["description"])
        self.assertIn("1..10000", step["inputSchema"]["properties"]["ticks"]["description"])
        valve = tools["mhs__lab_conveyor_workcell__actuation_valve"]
        self.assertIn("gate one of main, divert", valve["description"])
        self.assertIn("permit", valve["description"])

    def test_arm_joint_limits_carry_their_unit(self) -> None:
        spec, server = s.reference("arm")
        self.addCleanup(spec.close)
        mcp = s.Mcp(server, describe_inputs=True)
        joint = next(tool for tool in mcp.tools() if "joint_positio" in tool["name"])
        self.assertIn("joint_positions_deg -135..135 deg", joint["description"])
        self.assertIn("Unit: deg.", joint["inputSchema"]["properties"]["joint_positions_deg"]["description"])

    def test_a_limit_unit_fills_a_missing_schema_unit(self) -> None:
        # the schema declares no x-mhs-unit, the enforced limit does: never "Unit: none declared ... mm/s"
        manifest = endpoint_support.simple_manifest()
        detail = copy.deepcopy(manifest)
        detail["capabilities"][0]["x-mhs-effective-limits"] = {
            "limits": {"ticks": {"min": 1, "max": 50, "unit": "1", "reason": "short steps"}}}

        class Client(endpoint_support.FakeClient):
            def inspect(self, device_id=None):
                return copy.deepcopy(detail)

        projection = MCPProjection(Client([manifest]), describe_inputs=True)
        projection.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                   "params": {"clientInfo": {"name": "t"}}})
        listed = projection.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tool = next(item for item in listed["result"]["tools"] if "x-mhs" in item)
        text = tool["inputSchema"]["properties"]["ticks"]["description"]
        self.assertIn("Unit: 1.", text)
        self.assertNotIn("none declared", text)

    def test_reference_facts_reach_the_description_and_long_ones_are_cut_to_the_limit(self) -> None:
        manifest = endpoint_support.simple_manifest()
        reference = {"facts": [{"text": "The workcell belt slips above 180 mm/s.", "source": "vendor_doc",
                                "ref": "README.md:41"}],
                     "safety": {"interlocks": [{"id": "door_closed", "description": "Door closed",
                                                "required_for": ["cap.world.*"]}]}}
        detail = dict(copy.deepcopy(manifest), reference=reference)
        detail["capabilities"][0]["x-mhs-effective-limits"] = {
            "limits": {"ticks": {"min": 1, "max": 50, "reason": "short steps"}}}

        class Client(endpoint_support.FakeClient):
            def inspect(self, device_id=None):
                return copy.deepcopy(detail)

        tool = self._capability_tool(Client([manifest]))
        self.assertIn("The workcell belt slips above 180 mm/s. [vendor_doc README.md:41]", tool["description"])
        self.assertIn("ticks 1..50 (short steps)", tool["description"])
        self.assertIn("door_closed (Door closed)", tool["description"])

        reference["facts"] = [{"text": "fact %d " % index + "x" * 150, "source": "upstream_code",
                               "ref": f"pkg/mod.py:{index}"} for index in range(40)]
        manifest["capabilities"][0]["semantics"]["summary"] = "s" * 3000
        tool = self._capability_tool(Client([manifest]))
        self.assertLessEqual(len(tool["description"].encode("utf-8")), TOOL_DESCRIPTION_LIMIT)
        self.assertIn("ticks 1..50", tool["description"])
        self.assertIn("Not a safety-rated channel", tool["description"])


class AnnotationTests(unittest.TestCase):
    def test_read_tools_are_read_only_and_hardware_actuation_is_destructive(self) -> None:
        spec, server = s.reference("conveyor")
        self.addCleanup(spec.close)
        tools = {tool["name"]: tool for tool in s.Mcp(server).tools()}
        state = tools["mhs__lab_conveyor_workcell__world_state"]
        self.assertTrue(state["annotations"]["readOnlyHint"])
        self.assertEqual(state["x-mhs"]["verb"], "read")
        step = tools["mhs__lab_conveyor_workcell__world_step"]
        self.assertEqual((step["annotations"]["readOnlyHint"], step["annotations"]["destructiveHint"],
                          step["annotations"]["openWorldHint"]), (False, False, False))
        self.assertEqual(step["_meta"][META_KEY], step["x-mhs"])
        self.assertTrue(tools["mhs__devices"]["annotations"]["readOnlyHint"])
        self.assertNotIn("x-mhs", tools["mhs__devices"])

        hw_spec, hw_server = s.reference("conveyor", hardware=True)
        self.addCleanup(hw_spec.close)
        hw_tools = {tool["name"]: tool for tool in s.Mcp(hw_server, policy=s.policy(allow_hardware=True)).tools()}
        valve = hw_tools["mhs__lab_conveyor_workcell__actuation_valve"]
        self.assertEqual((valve["annotations"]["destructiveHint"], valve["annotations"]["openWorldHint"]),
                         (True, True))
        self.assertFalse(hw_tools["mhs__lab_conveyor_workcell__world_state"]["annotations"]["destructiveHint"])


if __name__ == "__main__":
    unittest.main()
