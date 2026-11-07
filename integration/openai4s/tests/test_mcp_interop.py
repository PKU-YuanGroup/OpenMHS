"""Path A interop: OpenAI4S's real MCPManager against ``mhs.mcp``.

Skipped unless the SDK ships the MCP projection and the OpenAI4S source tree is
importable.  The second test is the two-path agreement check: a native
``MHSHost`` command is replayed through MCP with the same ``command_id``; the
endpoint's idempotency store must return the retained receipt.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from openai4s_mhs.config import EndpointSpec, MHSConfig
from openai4s_mhs.host import MHSHost

from .support import launch_http_reference, sdk_projection_available, stop_process

_SDK_READY = sdk_projection_available()
_SDK_SRC = Path(__file__).resolve().parents[3] / "MHS" / "sdk" / "src"

PIPETTE_SHORT = "liquid-handler"
PAYLOAD = {"source_well": "A1", "destination_well": "B1", "volume_ul": 25}


def _connector_config(url: str, config_path: str | os.PathLike[str]) -> dict:
    return {
        "id": "mhs-lab",
        "command": [
            sys.executable,
            "-m",
            "mhs.mcp",
            "--endpoint",
            url,
            "--config",
            str(config_path),
        ],
        "transport": "stdio",
        "timeout": 30,
        "env": {
            "PYTHONPATH": os.pathsep.join(
                part for part in (str(_SDK_SRC), os.environ.get("PYTHONPATH")) if part
            ),
            # OpenAI4S gives connectors a least-privilege environment.
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    }


def _receipt(response: dict) -> dict:
    """The MHS receipt from an MCP result: structuredContent or the JSON line."""
    structured = (response.get("raw") or {}).get("structuredContent")
    if isinstance(structured, dict) and structured.get("receipt_id"):
        return structured
    for line in reversed(str(response.get("text") or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    raise AssertionError(f"MCP result carried no JSON receipt: {response.get('text')!r}")



def _invoke_with_command_id(
    manager: Any, config: dict, tool: dict, payload: dict, command_id: str
) -> dict:
    """Call a projected tool so the receipt can be reconciled by command_id.

    The projection reads the retry token from ``params._meta``; OpenAI4S's
    public ``call_tool(name, arguments)`` cannot carry ``_meta``, so the test
    uses the manager's live connection when the schema does not declare
    ``command_id`` as an argument.
    """
    name = str(tool.get("name"))
    props = (tool.get("inputSchema") or {}).get("properties") or {}
    if "command_id" in props:
        return manager.call_tool("mhs-lab", config, name, {**payload, "command_id": command_id})
    connection = manager.get("mhs-lab", config)
    result = connection._request(  # noqa: SLF001 - deliberate, see docstring
        "tools/call",
        {"name": name, "arguments": dict(payload), "_meta": {"command_id": command_id}},
    )
    parts = [
        str(block.get("text") or "")
        for block in result.get("content") or []
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return {"is_error": bool(result.get("isError")), "text": "\n".join(parts), "raw": result}



@unittest.skipUnless(_SDK_READY, "mhs.mcp / mhs.server / OpenAI4S MCP client not available")
class MCPProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.proc, self.url, self.ready = launch_http_reference("lab", timeout=20)
        self.addCleanup(stop_process, self.proc)
        self.settings = tempfile.TemporaryDirectory(prefix="mhs-mcp-policy-")
        self.addCleanup(self.settings.cleanup)
        policy = Path(self.settings.name) / "mhs.json"
        policy.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "allow_hardware": False,
                    "endpoints": [{"id": "lab", "url": self.url}],
                }
            ),
            encoding="utf-8",
        )
        self.policy_path = policy

    def test_tools_list_and_read_call(self) -> None:
        from openai4s.mcp_client import MCPManager

        manager = MCPManager()
        self.addCleanup(manager.shutdown)
        config = _connector_config(self.url, self.policy_path)
        tools = manager.list_tools("mhs-lab", config)
        names = {str(tool.get("name")) for tool in tools}
        self.assertIn("mhs__lab_liquid_handler__fluid_transfer", names)
        self.assertIn("mhs__lab_plate_reader__measure_spectrum", names)
        for tool in tools:
            self.assertEqual(tool.get("inputSchema", {}).get("type"), "object")
        # A read-domain capability is a safe MCP call: it must return JSON text.
        response = manager.call_tool(
            "mhs-lab",
            config,
            "mhs__lab_liquid_handler__fluid_level",
            {"well_ids": ["A1", "B1"]},
        )
        self.assertFalse(response["is_error"], response)
        payload = _receipt(response)
        self.assertEqual(payload.get("status"), "completed")
        self.assertTrue(payload.get("receipt_id"))

    def test_native_receipt_is_replayed_by_command_id(self) -> None:
        from openai4s.mcp_client import MCPManager

        tmp = tempfile.TemporaryDirectory(prefix="mhs-mcp-test-")
        self.addCleanup(tmp.cleanup)
        host = MHSHost(
            MHSConfig(
                endpoints=[EndpointSpec(id="lab", url=self.url)],
                evidence_log=str(Path(tmp.name) / "evidence.jsonl"),
                command_timeout_ms=15_000,
            )
        )
        self.addCleanup(host.close)
        devices = host.devices()
        pipette = next(
            item
            for item in devices
            if str(item.get("device_id", "")).endswith("/" + PIPETTE_SHORT)
        )
        native = host.command(str(pipette["device_id"]), "cap.fluid.transfer.v1", PAYLOAD)
        self.assertEqual(native["status"], "completed")

        manager = MCPManager()
        self.addCleanup(manager.shutdown)
        config = _connector_config(self.url, self.policy_path)
        tools = manager.list_tools("mhs-lab", config)
        tool = next(
            item
            for item in tools
            if item.get("name") == "mhs__lab_liquid_handler__fluid_transfer"
        )
        response = _invoke_with_command_id(
            manager, config, tool, PAYLOAD, native["command_id"]
        )
        self.assertFalse(response["is_error"], response)
        replayed = _receipt(response)
        self.assertEqual(replayed["command_id"], native["command_id"])
        self.assertEqual(replayed["receipt_id"], native["receipt_id"])
        self.assertEqual(replayed["status"], "completed")
        self.assertTrue(replayed.get("replayed"))


if __name__ == "__main__":
    unittest.main()
