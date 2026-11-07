"""HOST-001 policy on the bare mhs.mcp projection (no OpenAI4S needed).

These tests launch the real projection as a stdio subprocess and speak JSON-RPC,
so the policy is exercised on the transport boundary rather than by importing
``MCPProjection`` and calling its methods.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _request(process: subprocess.Popen, payload: dict) -> dict:
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()
    line = process.stdout.readline()
    if not line:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise AssertionError(f"mhs.mcp produced no reply; stderr={stderr[-800:]}")
    return json.loads(line)


class ProjectionPolicyTests(unittest.TestCase):
    def _launch(self, enabled: bool) -> tuple[subprocess.Popen, Path]:
        tmp = tempfile.TemporaryDirectory(prefix="mhs-sdk-policy-")
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "mhs.json"
        path.write_text(
            json.dumps({"enabled": enabled, "allow_hardware": False}), encoding="utf-8"
        )
        env = os.environ.copy()
        parts = [str(Path(__file__).resolve().parents[3] / "src")]
        if env.get("PYTHONPATH"):
            parts.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(parts)
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "mhs.mcp",
                "--reference",
                "conveyor",
                "--test-profile",
                "--config",
                str(path),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        self.addCleanup(self._stop, process)
        reply = _request(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "test"}},
            },
        )
        self.assertIn("result", reply)
        return process, path

    @staticmethod
    def _stop(process: subprocess.Popen) -> None:
        try:
            if process.stdin is not None:
                process.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:  # noqa: BLE001
            try:
                process.kill()
            except Exception:  # noqa: BLE001
                pass
        for stream in (process.stdout, process.stderr):
            try:
                if stream is not None:
                    stream.close()
            except Exception:  # noqa: BLE001
                pass

    def test_disabled_policy_refuses_tools_and_resources(self) -> None:
        process, _path = self._launch(enabled=False)
        tools = _request(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(tools["result"]["tools"], [])
        call = _request(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "mhs__devices", "arguments": {}},
            },
        )
        result = call["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(
            result["structuredContent"]["mhs_error"]["mhs_code"], "MHS.AUTH.FORBIDDEN"
        )
        resources = _request(
            process, {"jsonrpc": "2.0", "id": 4, "method": "resources/list"}
        )
        self.assertEqual(resources["result"]["resources"], [])

    def test_enabled_policy_allows_simulated_discovery(self) -> None:
        process, _path = self._launch(enabled=True)
        tools = _request(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {tool["name"] for tool in tools["result"]["tools"]}
        self.assertIn("mhs__devices", names)
        self.assertTrue(any(name.startswith("mhs__") and "world_step" in name for name in names))
        call = _request(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "mhs__devices", "arguments": {}},
            },
        )
        self.assertFalse(call["result"]["isError"])
        self.assertTrue(call["result"]["structuredContent"].get("devices"))


if __name__ == "__main__":
    unittest.main()
