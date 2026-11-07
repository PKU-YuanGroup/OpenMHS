"""Shared fixtures for the agent-surface tests (WP-08): the MCP projection and the client.

The projection is driven in process over :class:`mhs.conformance.inprocess.Loopback`,
which records every endpoint method it sends, so a test can show that a refused
tool call never reached the endpoint.  The reviewer repros these tests port
(``mhs-review-scratch/integration-surfaces`` and ``verify-integration-surfaces``)
used port 7713; nothing here binds a fixed port.
"""

from __future__ import annotations

import contextlib
import io
import os
import socket
import warnings
from pathlib import Path
from typing import Any, Mapping

from mhs.client import MHSClient
from mhs.conformance.inprocess import Loopback
from mhs.mcp import MCPPolicy, MCPProjection
from mhs.reference import build_endpoint, build_server

SDK_SRC = Path(__file__).resolve().parents[2] / "src"
ENDPOINT_ID = "mhs://localhost:7400"
CONVEYOR = "mhs://localhost:7400/lab/conveyor-workcell"
CLIENT_NAME = "surface-tests"


def reference(name: str = "conveyor", *, test_profile: bool = False, hardware: bool = False,
              risk: str = "R2") -> tuple[Any, Any]:
    """``(spec, server)`` of a reference endpoint; ``hardware`` makes every device an R2 hardware device.

    ``hardware`` is the reviewer's ``hw_endpoint.py``: the same simulator declared
    ``mode: "hardware"`` so the hardware rules apply.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        spec = build_endpoint(name, endpoint_id=ENDPOINT_ID, test_profile=test_profile)
        if hardware:
            for device in spec.devices:
                device["mode"] = "hardware"
                device.setdefault("safety", {})["risk_class"] = risk
        server = build_server(spec, log_ready=False)
    return spec, server


def client(server: Any) -> MHSClient:
    """A connected client over a recording loopback (``client.transport.methods``)."""
    result = MHSClient(Loopback(server))
    result.hello()
    return result


def tick(spec: Any, device_id: str = CONVEYOR) -> int:
    return int(spec.bridges[device_id].sim.tick)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def child_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SDK_SRC) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


class Mcp:
    """An initialized in-process MCP projection in front of ``server``."""

    def __init__(self, server: Any, *, policy: MCPPolicy | None = None, describe_inputs: bool = False,
                 client_name: str = CLIENT_NAME, protocol_version: str = "2025-06-18") -> None:
        self.server = server
        self.client = client(server)
        self.transport: Loopback = self.client.transport
        self.projection = MCPProjection(self.client, policy=policy, describe_inputs=describe_inputs)
        self._id = 0
        self.initialized = self.request("initialize", {
            "protocolVersion": protocol_version, "capabilities": {},
            "clientInfo": {"name": client_name, "version": "0"}})

    def request(self, method: str, params: Mapping[str, Any] | None = None, *, mid: Any = None) -> dict[str, Any]:
        self._id += 1
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": self._id if mid is None else mid, "method": method}
        if params is not None:
            message["params"] = dict(params)
        with contextlib.redirect_stderr(io.StringIO()):
            return self.projection.handle_message(message)

    def notify(self, method: str, params: Mapping[str, Any]) -> None:
        self.projection.handle_message({"jsonrpc": "2.0", "method": method, "params": dict(params)})

    def call(self, name: str, arguments: Mapping[str, Any] | None = None, *, meta: Mapping[str, Any] | None = None,
             mid: Any = None) -> dict[str, Any]:
        params: dict[str, Any] = {"name": name, "arguments": dict(arguments or {})}
        if meta is not None:
            params["_meta"] = dict(meta)
        response = self.request("tools/call", params, mid=mid)
        assert "result" in response, response
        return response["result"]

    def tools(self) -> list[dict[str, Any]]:
        return self.request("tools/list")["result"]["tools"]

    def tool(self, suffix: str) -> str:
        names = [tool["name"] for tool in self.tools() if tool["name"].endswith(suffix)]
        assert len(names) == 1, (suffix, names)
        return names[0]

    def mark(self) -> int:
        return len(self.transport.methods)

    def sent_since(self, mark: int) -> list[str]:
        return list(self.transport.methods[mark:])

    def close(self) -> None:
        self.projection.close()


def receipt(result: Mapping[str, Any]) -> dict[str, Any]:
    value = (result.get("structuredContent") or {}).get("receipt")
    assert isinstance(value, Mapping), result
    return dict(value)


def mhs_error(result: Mapping[str, Any]) -> dict[str, Any]:
    return dict((result.get("structuredContent") or {}).get("mhs_error") or {})


def policy(**flags: bool) -> MCPPolicy:
    values = {"enabled": True, "allow_hardware": False}
    values.update(flags)
    return MCPPolicy(**values)


def age_sessions(server: Any, seconds: float = 3700.0) -> None:
    """The reviewer's ttl_test: make every endpoint session older than its TTL."""
    for session in list(server._sessions.values()):
        session.expires_at -= seconds


# ---------------------------------------------------------------------------
# CLI and code-file helpers (WP-08 08b)
# ---------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[4]
THERMOSTAT = REPO / "MHS" / "sdk" / "examples" / "thermostat"


def run_cli(*argv: str) -> tuple[int, str, str]:
    """``mhs <argv>`` in process: ``(exit code, stdout, stderr)``; warnings are silenced."""
    from mhs.cli import main

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Http:
    """``server`` on loopback HTTP for the duration of a ``with`` block (``.url``)."""

    def __init__(self, server: Any) -> None:
        self.server = server
        self.handle = None
        self.url = ""

    def __enter__(self) -> "Http":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.handle = self.server.start_http("127.0.0.1", 0)
        self.url = self.handle.url
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.handle.shutdown()


def closed_port_url() -> str:
    """An http URL on a loopback port nothing listens on."""
    return f"http://127.0.0.1:{free_port()}"
