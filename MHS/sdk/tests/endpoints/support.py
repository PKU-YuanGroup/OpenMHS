"""Shared fixtures for the MHS endpoint/bridge/MCP tests (stdlib only).

Paths: ``SDK_ROOT`` is ``MHS/sdk`` (the ``tests`` package is importable from
it), ``SDK_SRC`` is ``MHS/sdk/src`` (what a child process needs on
``PYTHONPATH`` to import ``mhs``), ``REPO_ROOT`` the project root and
``OPENAI4S_SRC`` the OpenAI4S checkout used by the interop test:
``$MHS_OPENAI4S_SRC``, else ``<project root>/work/openai4s-src`` (the test
skips when it is not importable).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from typing import Any, Mapping

SDK_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SDK_SRC = os.path.join(SDK_ROOT, "src")
for _path in (SDK_SRC, SDK_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

REPO_ROOT = os.path.dirname(os.path.dirname(SDK_ROOT))
WORKSPACE = REPO_ROOT
OPENAI4S_SRC = os.environ.get("MHS_OPENAI4S_SRC") or os.path.join(REPO_ROOT, "work", "openai4s-src")


class Thermo:
    """A tiny native object used by the python-object bridge tests."""

    def __init__(self, *, temperature_c: int = 21, name: str = "thermo"):
        self.temperature_c = temperature_c
        self.name = name
        self.closed = False
        self._serial = 0

    def measure(self, channel: int = 0) -> dict[str, Any]:
        self._serial += 1
        return {"temperature_c": self.temperature_c + channel, "serial": self._serial}

    def set_point(self, celsius: int) -> dict[str, Any]:
        if celsius > 80:
            raise ValueError("setpoint above the declared maximum")
        self.temperature_c = celsius
        return {"temperature_c": self.temperature_c}

    def state(self) -> dict[str, Any]:
        return {"temperature_c": self.temperature_c, "serial": self._serial}

    def snapshot(self) -> dict[str, Any]:
        return {"temperature_c": self.temperature_c, "serial": self._serial}

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        self.temperature_c = int(snapshot["temperature_c"])
        self._serial = int(snapshot.get("serial", 0))

    def close(self) -> None:
        self.closed = True


THERMO_CONFIG: dict[str, Any] = {
    "target": "tests.endpoints.support:Thermo",
    "factory": {"kind": "class", "kwargs": {"temperature_c": 21}},
    "close": "close",
    "capabilities": {
        "cap.measure.temperature.v1": {
            "resource": "thermo",
            "native": "measure",
            "description": "Read the temperature of one channel.",
            "args": {"channel": {"from": "input.channel", "default": 0}},
            "result": {"temperature_c": {"from": "temperature_c"}, "serial": {"from": "serial"}},
            "errors": {"ValueError": "MHS.CAPABILITY.INPUT_INVALID", "*": "MHS.DEVICE.FAULTED"},
        },
        "cap.thermal.setpoint.v1": {
            "resource": "thermo",
            "native": "set_point",
            "args": {"celsius": {"from": "input.target_c"}},
            "errors": {"ValueError": "MHS.SAFETY.ENVELOPE_VIOLATION"},
            "advertise": {"input_schema": {"type": "object", "required": ["target_mK"]}},
        },
    },
    "reads": {"thermo": {"method": "state"}},
    "snapshot": {"method": "snapshot"},
    "restore": {"method": "restore", "args": {"snapshot": {"from": "snapshot"}}},
}


class FakeClient:
    """Minimal duck-typed MHS client used by MCP projection unit tests."""

    def __init__(self, manifests: list[Mapping[str, Any]]):
        self.manifests = [dict(item) for item in manifests]
        self.calls: list[dict[str, Any]] = []
        self.sessions = 0
        self.closed = False

    def hello(self) -> dict[str, Any]:
        return {
            "mhs_version": "1.0",
            "endpoint_id": "mhs://localhost:7400",
            "devices": self.manifests,
            "features": ["MHS.SAFETY.NOT_CERTIFIED"],
        }

    def devices(self) -> list[dict[str, Any]]:
        return self.manifests

    def inspect(self, device_id: str | None = None) -> dict[str, Any]:
        for manifest in self.manifests:
            if device_id is None or manifest.get("device_id") == device_id:
                return manifest
        raise AssertionError("unknown device")

    def open_session(self, device_ids=None, capabilities=None, mode=None, ttl_s=600, **kwargs: Any) -> dict[str, Any]:
        self.sessions += 1
        return {"session_id": f"mhs_s_fake{self.sessions}", "granted": [], "mode": "simulated", "expires_at": "2026-01-01T00:00:00Z"}

    def close_session(self, session_id: str | None = None) -> dict[str, Any]:
        return {"closed_at": "2026-01-01T00:00:00Z"}

    def invoke(self, capability_id: str, payload: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"capability_id": capability_id, "payload": dict(payload or {}), **kwargs})
        return {
            "receipt_id": "01J8ZQ3V6Y7M2N4P6R8S0T2V4W",
            "command_id": kwargs.get("command_id") or "01J8ZQ3V6Y7M2N4P6R8S0T2V4X",
            "capability_id": capability_id,
            "device_id": kwargs.get("device_id"),
            "status": "completed",
            "state_revision_after": 1,
            "state_hash_after": "sha256:" + "0" * 64,
            "output": {"ok": True},
        }

    def read(self, resource_id: str, **kwargs: Any) -> dict[str, Any]:
        return {"revision": 1, "state": {}, "state_hash": "sha256:" + "0" * 64}

    def safety_status(self, device_id: str | None = None) -> dict[str, Any]:
        return {"risk_class": "R1", "estop": {"engaged": False, "latching": True}, "interlocks": []}

    def operations(self, device_id: str | None = None) -> dict[str, Any]:
        return {"operations": []}

    def cancel(self, operation_id: str, **kwargs: Any) -> dict[str, Any]:
        return {"status": "cancelled", "safe_state_achieved": True, "operation_id": operation_id}

    def export_evidence(self, **kwargs: Any) -> dict[str, Any]:
        return {"receipts": [], "head_digest": "sha256:" + "0" * 64}

    def verify_evidence(self, bundle: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return {"valid": True}

    def close(self) -> None:
        self.closed = True


def simple_manifest() -> dict[str, Any]:
    return {
        "mhs_version": "1.0",
        "device_id": "mhs://localhost:7400/lab/conveyor-workcell",
        "instance_id": "01J8ZQ3V6Y7M2N4P6R8S0T2V4W",
        "display_name": "Fake conveyor",
        "mode": "simulated",
        "resources": [{"resource_id": "workcell", "kind": "world.sim", "state_schema": {"type": "object"}}],
        "capabilities": [
            {
                "capability_id": "cap.world.step.v1",
                "resource": "workcell",
                "title": "Advance",
                "input_schema": {
                    "type": "object",
                    "required": ["ticks"],
                    "properties": {"ticks": {"type": "integer", "minimum": 0, "maximum": 10000}},
                },
                "output_schema": {"type": "object"},
                "semantics": {"summary": "Advance the simulation.", "tags": ["simulation"]},
            }
        ],
        "safety": {
            "risk_class": "R1",
            "estop": {"kind": "software", "latching": True},
            "safe_state": {"description": "stopped", "achieved_by": []},
        },
        "fidelity": {
            "engine": "custom-integer",
            "fidelity_level": "F0",
            "determinism": {"kind": "exact"},
            "snapshot_restore": True,
            "gaps": [],
        },
    }


class EndpointHandle:
    """Boot a reference endpoint in-process over loopback HTTP."""

    def __init__(self, name: str, *, test_profile: bool = False, noise: bool = False, seed: int = 0, bundle: str | None = None):
        from mhs.reference import build_endpoint, build_server

        self.spec = build_endpoint(
            name,
            endpoint_id="mhs://localhost:0",
            test_profile=test_profile,
            noise=noise,
            seed=seed,
            bundle=bundle,
        )
        self.server = build_server(self.spec, log_ready=False)
        self.http = self.server.start_http("127.0.0.1", 0)
        self.url = self.http.url

    def __enter__(self) -> "EndpointHandle":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def close(self) -> None:
        try:
            self.http.shutdown()
        finally:
            self.spec.close()


def wait_for_http(url: str, *, timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/.well-known/mhs.json", timeout=0.5) as response:
                json.loads(response.read().decode("utf-8"))
                return
        except Exception:  # noqa: BLE001 - retry until ready
            time.sleep(0.02)
    raise AssertionError(f"endpoint at {url} did not become ready")
