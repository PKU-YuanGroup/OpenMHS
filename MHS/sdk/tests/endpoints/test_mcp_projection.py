"""MCP projection tests, including real OpenAI4S MCPConnection interop.

The projection is exercised twice: once over an in-process fake MHS client (fast
protocol unit tests) and once as a real stdio subprocess behind OpenAI4S's own
``MCPConnection`` -- the host class the integration story depends on.
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import unittest

from tests.endpoints import support

from mhs.mcp import (
    MCPProjection,
    PROTOCOL_VERSION,
    _tool_input_schema,
    projection_tool_name,
)


class FakeMCPClient(support.FakeClient):
    """Fake MHS client whose receipt can be rejected to test isError semantics."""

    def __init__(self, manifests, *, reject: bool = False):
        super().__init__(manifests)
        self.reject = reject

    def invoke(self, capability_id, payload=None, **kwargs):
        receipt = super().invoke(capability_id, payload, **kwargs)
        if self.reject:
            receipt["status"] = "rejected"
            receipt["error"] = {"mhs_code": "MHS.SAFETY.INTERLOCK_OPEN", "message": "door open"}
        return receipt


class ToolNamingTests(unittest.TestCase):
    def test_tool_names_are_legal_stable_and_spec_shaped(self) -> None:
        device_id = "mhs://localhost:7400/lab/conveyor-workcell"
        name = projection_tool_name(device_id, "cap.world.step.v1")
        self.assertEqual(name, "mhs__lab_conveyor_workcell__world_step")
        self.assertEqual(name, projection_tool_name(device_id, "cap.world.step.v1"))
        self.assertLessEqual(len(name), 63)
        self.assertTrue(name.startswith("mhs__"))
        long_name = projection_tool_name(
            "mhs://localhost:7400/very/long/device/path/name-with-many-segments-here",
            "x-cap.somevendor.a-very-long-capability-class-name-here.v1",
        )
        self.assertLessEqual(len(long_name), 63)
        self.assertNotIn(" ", long_name)

    def test_input_schema_preserves_capability_fields_and_advertises_optional_controls(self) -> None:
        capability = {
            "capability_id": "cap.world.step.v1",
            "input_schema": {
                "type": "object",
                "required": ["ticks"],
                "properties": {"ticks": {"type": "integer", "x-mhs-unit": "ms"}},
                "additionalProperties": False,
            },
        }
        schema = _tool_input_schema(capability)
        # capability schema is projected without loss: required stays required,
        # units survive, and the closed object stays closed for foreign keys.
        self.assertEqual(schema["required"], ["ticks"])
        self.assertEqual(schema["properties"]["ticks"]["x-mhs-unit"], "ms")
        self.assertFalse(schema.get("additionalProperties", True))
        # MHS control fields are optional additions, never required
        controls = {"session_id", "command_id", "expected_revision", "permit_id", "deadline_ms"}
        self.assertTrue(controls.issubset(schema["properties"]))
        for control in controls:
            self.assertNotIn(control, schema["required"])


class FakeProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = FakeMCPClient([support.simple_manifest()])
        self.projection = MCPProjection(self.client, endpoint="fake")

    def tearDown(self) -> None:
        self.projection.close()

    def _initialize(self) -> dict:
        response = self.projection.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            }
        )
        assert response is not None
        return response["result"]

    def test_handshake_negotiates_protocol_and_identifies_the_shim(self) -> None:
        result = self._initialize()
        self.assertEqual(result["protocolVersion"], PROTOCOL_VERSION)
        self.assertIn("tools", result["capabilities"])
        self.assertIn("resources", result["capabilities"])
        self.assertEqual(result["serverInfo"]["name"], "mhs-mcp:mhs://localhost:7400")
        self.assertIsNone(self.projection.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_requests_before_initialize_are_rejected(self) -> None:
        response = self.projection.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(response["error"]["code"], -32002)

    def test_unknown_method_and_malformed_request(self) -> None:
        self._initialize()
        unknown = self.projection.handle_message({"jsonrpc": "2.0", "id": 3, "method": "no/such/method"})
        self.assertEqual(unknown["error"]["code"], -32601)
        malformed = self.projection.handle_message({"jsonrpc": "2.0", "id": 4})
        self.assertEqual(malformed["error"]["code"], -32600)

    def test_tools_list_contains_capability_and_discovery_tools(self) -> None:
        self._initialize()
        response = self.projection.handle_message({"jsonrpc": "2.0", "id": 5, "method": "tools/list"})
        tools = {tool["name"]: tool for tool in response["result"]["tools"]}
        capability_tool = tools["mhs__lab_conveyor_workcell__world_step"]
        self.assertIn("Mode:", capability_tool["description"])
        self.assertIn("Not a safety-rated channel", capability_tool["description"])
        self.assertEqual(capability_tool["x-mhs"]["risk_class"], "R1")
        self.assertIn("ticks", capability_tool["inputSchema"]["properties"])
        for name in ("mhs__devices", "mhs__inspect", "mhs__read", "mhs__safety", "mhs__operations", "mhs__evidence"):
            self.assertIn(name, tools)

    def test_tools_call_maps_to_one_command_and_returns_a_receipt(self) -> None:
        self._initialize()
        response = self.projection.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "mhs__lab_conveyor_workcell__world_step", "arguments": {"ticks": 5}},
            }
        )
        result = response["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["receipt"]["status"], "completed")
        self.assertEqual(len(self.client.calls), 1)
        self.assertEqual(self.client.calls[0]["capability_id"], "cap.world.step.v1")
        self.assertEqual(self.client.calls[0]["payload"], {"ticks": 5})
        # an explicit MCP command_id becomes the MHS idempotency key (retry token)
        retried = self.projection.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "mhs__lab_conveyor_workcell__world_step",
                    "arguments": {"ticks": 5, "command_id": "01J8ZQ3V6Y7M2N4P6R8S0T2V4W"},
                },
            }
        )
        self.assertFalse(retried["result"]["isError"])
        self.assertEqual(self.client.calls[-1]["command_id"], "01J8ZQ3V6Y7M2N4P6R8S0T2V4W")
        self.assertEqual(self.client.calls[-1]["payload"], {"ticks": 5})

    def test_rejected_receipt_is_a_successful_tool_call(self) -> None:
        client = FakeMCPClient([support.simple_manifest()], reject=True)
        projection = MCPProjection(client, endpoint="fake")
        try:
            projection.handle_message(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "t"}},
                }
            )
            response = projection.handle_message(
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "tools/call",
                    "params": {"name": "mhs__lab_conveyor_workcell__world_step", "arguments": {"ticks": 5}},
                }
            )
            result = response["result"]
            self.assertFalse(result["isError"])  # TPT-038: a rejection is an outcome, not a malfunction
            self.assertEqual(result["structuredContent"]["receipt"]["status"], "rejected")
            self.assertEqual(result["structuredContent"]["mhs_error"]["mhs_code"], "MHS.SAFETY.INTERLOCK_OPEN")
        finally:
            projection.close()

    def test_unknown_tool_is_invalid_params(self) -> None:
        self._initialize()
        response = self.projection.handle_message(
            {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "mhs__nope", "arguments": {}}}
        )
        self.assertEqual(response["error"]["code"], -32602)

    def test_resources_list_and_read_map_to_mhs_uris(self) -> None:
        self._initialize()
        listing = self.projection.handle_message({"jsonrpc": "2.0", "id": 9, "method": "resources/list"})
        resources = listing["result"]["resources"]
        self.assertTrue(any("/devices" in item["uri"] for item in resources))
        self.assertTrue(any(item["uri"].endswith("/resources/workcell") for item in resources))
        uri = next(item["uri"] for item in resources if item["uri"].endswith("/resources/workcell"))
        read = self.projection.handle_message(
            {"jsonrpc": "2.0", "id": 10, "method": "resources/read", "params": {"uri": uri}}
        )
        self.assertEqual(read["result"]["contents"][0]["uri"], uri)
        json.loads(read["result"]["contents"][0]["text"])


class StdioProjectionTests(unittest.TestCase):
    """Drive the real stdio shim process with a bounded raw JSON-RPC client."""

    def _process(self) -> subprocess.Popen:
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = support.SDK_SRC + (os.pathsep + existing if existing else "")
        return subprocess.Popen(
            [sys.executable, "-m", "mhs.mcp", "--reference", "conveyor", "--test-profile"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def _request(self, process: subprocess.Popen, message: dict, *, timeout: float = 20.0) -> dict:
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write((json.dumps(message) + "\n").encode())
        process.stdin.flush()
        ready, _, _ = select.select([process.stdout], [], [], timeout)
        if not ready:
            self.fail("MCP projection did not answer within the deadline")
        line = process.stdout.readline()
        self.assertTrue(line, "MCP projection closed stdout")
        return json.loads(line.decode())

    def test_stdio_handshake_tools_and_call(self) -> None:
        process = self._process()
        try:
            init = self._request(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": "unittest", "version": "1.0"},
                    },
                },
            )
            self.assertTrue(init["result"]["serverInfo"]["name"].startswith("mhs-mcp:"))
            process.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
            process.stdin.flush()
            ping = self._request(process, {"jsonrpc": "2.0", "id": 2, "method": "ping"})
            self.assertEqual(ping["result"], {})
            tools = self._request(process, {"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
            names = [tool["name"] for tool in tools["result"]["tools"]]
            self.assertIn("mhs__lab_conveyor_workcell__world_step", names)
            called = self._request(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {"name": "mhs__lab_conveyor_workcell__world_step", "arguments": {"ticks": 3}},
                },
            )
            result = called["result"]
            self.assertFalse(result["isError"])
            self.assertEqual(result["structuredContent"]["receipt"]["status"], "completed")
            resources = self._request(process, {"jsonrpc": "2.0", "id": 5, "method": "resources/list"})
            self.assertTrue(resources["result"]["resources"])
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover
                process.kill()


class OpenAI4SInteropTests(unittest.TestCase):
    """The proof for the OpenAI4S story: their own MCPConnection drives the shim."""

    def test_openai4s_mcp_connection_lists_and_calls_tools(self) -> None:
        try:
            sys.path.insert(0, support.OPENAI4S_SRC)
            from openai4s.mcp_client import MCPConnection
        except Exception as exc:  # noqa: BLE001
            self.skipTest(f"OpenAI4S source not importable: {exc}")
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = support.SDK_SRC + (os.pathsep + existing if existing else "")
        connection = MCPConnection(
            [sys.executable, "-m", "mhs.mcp", "--reference", "conveyor", "--test-profile"],
            env=env,
        )
        try:
            tools = connection.list_tools()
            names = {tool["name"] for tool in tools}
            self.assertIn("mhs__lab_conveyor_workcell__world_step", names)
            result = connection.call_tool("mhs__lab_conveyor_workcell__world_step", {"ticks": 7})
            self.assertFalse(result["is_error"])
            self.assertIn("completed", result["text"])
            self.assertEqual(result["raw"]["structuredContent"]["receipt"]["status"], "completed")
            receipt = result["raw"]["structuredContent"]["receipt"]
            self.assertEqual(receipt["capability_id"], "cap.world.step.v1")
            self.assertTrue(str(receipt["receipt_id"]))
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
