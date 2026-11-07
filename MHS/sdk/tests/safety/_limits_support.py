"""Fixtures for the limits-engine tests (WP-04 step 4c).

Ports of the reviewer repros (``mhs-review-scratch/{sdk-core,schema-catalog,
driver-authoring,fit-lab-instruments,fit-robots-ros,fit-robots-sim,
fit-robots-sim-verifier,verify-schema-catalog}``) build small devices whose
bridge records every native call, so a test can prove that an out-of-range
command never reached the device.
"""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any, Mapping

from mhs.bridge.base import Bridge
from mhs.reference import build_endpoint, build_server
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope

from ._support import FIDELITY, Rpc

_HERE = Path(__file__).resolve()
_MHS = _HERE.parents[3]
CATALOGUE = {item["capability_id"]: item
             for item in json.loads((_MHS / "spec" / "capabilities.json").read_text())["capabilities"]}
EXAMPLES = _MHS / "schema" / "examples"

JOINTS = "cap.motion.joint_position.v1"
POSE = "cap.motion.cartesian_pose.v1"
STOP = "cap.motion.stop.v1"
SETPOINT = "cap.thermal.setpoint.v1"
CONFIGURE = "cap.device.configure.v1"


def class_schema(capability_id: str, which: str = "input_schema") -> dict[str, Any]:
    return copy.deepcopy(CATALOGUE[capability_id][which])


class RecordingBridge(Bridge):
    """Applies inputs to a state document and records every native call."""

    bridge_id = "tests.safety.limits"

    def __init__(self, device_id: str, state: Mapping[str, Any] | None = None) -> None:
        super().__init__(device_id=device_id)
        self.state: dict[str, Any] = copy.deepcopy(dict(state or {}))
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.interlock_reads = 0
        self.interlock_states: dict[str, str] = {}
        self._calls_lock = threading.Lock()

    def native(self, capability_id: str | None = None) -> list[tuple[str, dict[str, Any]]]:
        with self._calls_lock:
            return [item for item in self.calls if capability_id is None or item[0] == capability_id]

    def read(self, resource_id: str, fields=None, ctx=None):  # noqa: ANN001
        return copy.deepcopy(self.state)

    def call(self, capability_id: str, args=None, ctx=None):  # noqa: ANN001
        args = copy.deepcopy(dict(args or {}))
        with self._calls_lock:
            self.calls.append((capability_id, args))
        if capability_id == STOP:
            return {"stopped": True}
        if capability_id == JOINTS:
            self.state["q"] = list(args.get("joint_positions") or [])
            return {"reached": True, "joint_positions": list(self.state["q"])}
        if capability_id == POSE:
            self.state["pos"] = dict(args.get("position") or {})
            return {"reached": True}
        if capability_id == SETPOINT:
            return {"setpoint": args.get("target_temperature")}
        for key, value in args.items():
            if isinstance(value, Mapping) and isinstance(self.state.get(key), dict):
                self.state[key].update(value)
            else:
                self.state[key] = value
        if capability_id == CONFIGURE:
            return {"applied": args}
        return {"applied": True}

    def interlocks(self):
        self.interlock_reads += 1
        return [{"id": key, "state": value} for key, value in self.interlock_states.items()]

    def reset(self, ctx=None):  # noqa: ANN001
        return {"reset": True}


def device(
    device_id: str,
    capabilities: list[Capability],
    *,
    mode: str = "simulated",
    risk: str = "R1",
    envelope: Mapping[str, Any] | None = None,
    resources: list[Resource] | None = None,
    state: Mapping[str, Any] | None = None,
    achieved_by: tuple[str, ...] = (),
    interlocks: list[dict[str, Any]] | None = None,
    requires_permit: list[str] | None = None,
    strict: bool | None = None,
) -> Device:
    return Device(
        device_id,
        "Limits test device",
        mode=mode,
        resources=resources if resources is not None else [Resource("arm", "robot.arm")],
        capabilities=capabilities,
        safety=SafetyEnvelope(
            risk_class=risk,
            envelope=dict(envelope or {}),
            interlocks=list(interlocks or []),
            requires_permit=list(requires_permit or []),
            estop={"kind": "software", "latching": True, "latency_ms": 50},
            safe_state={"description": "stopped", "achieved_by": list(achieved_by)},
        ),
        fidelity=dict(FIDELITY) if mode in ("simulated", "hybrid") else None,
        bridge=RecordingBridge(device_id, state),
        strict=strict,
    )


def serve(dev: Device, **server_kwargs: Any) -> tuple[MHSServer, Rpc, str]:
    server_kwargs.setdefault("log_ready", False)
    server = MHSServer("mhs://localhost/limits", [dev], **server_kwargs)
    rpc = Rpc(server)
    rpc("mhs.hello", protocol_versions=["1.0"])
    session = rpc("mhs.session.open", device_ids=[dev.device_id], mode=dev.mode)["session_id"]
    return server, rpc, session


def reference_arm(envelope_override: Mapping[str, Mapping[str, Any]] | None = None):
    """The reference 2-DOF arm (sdk-core e8.py), with native calls counted."""
    spec = build_endpoint("arm", endpoint_id="mhs://localhost/x")
    for manifest in spec.devices:
        for capability_id, rules in (envelope_override or {}).items():
            manifest["safety"]["envelope"].setdefault(capability_id, {}).update(copy.deepcopy(dict(rules)))
    server = build_server(spec, log_ready=False)
    dev = next(iter(server.devices.values()))
    calls: list[str] = []
    original = dev.bridge.call

    def counted(capability_id, args=None, ctx=None):  # noqa: ANN001
        calls.append(capability_id)
        return original(capability_id, args, ctx)

    dev.bridge.call = counted
    rpc = Rpc(server)
    rpc("mhs.hello", protocol_versions=["1.0"])
    session = rpc("mhs.session.open", mode="simulated")["session_id"]
    return server, rpc, session, dev, calls


def details(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return dict((receipt.get("error") or {}).get("details") or {})
