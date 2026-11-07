"""Fixtures for the strict-mode tests (WP-04 step 4b).

A small arm whose bindings are faithful to their catalogue classes, so a test
starts from a device strict mode accepts and changes exactly one thing.
"""

from __future__ import annotations

import copy
import threading
import warnings
from typing import Any, Iterable, Mapping

from mhs.bridge.base import Bridge
from mhs.server import Capability, Device, MHSServer, MHSStrictWarning, Resource, SafetyEnvelope

from ._support import FIDELITY, Rpc

ARM_ID = "mhs://localhost/strict/arm"
JOINTS = "cap.motion.joint_position.v1"
STOP = "cap.motion.stop.v1"
TORQUE = "cap.motion.joint_torque.v1"
DESCRIBE = "cap.device.describe.v1"
EXT = "x-cap.test.ping.v1"

TOKENS = {
    "operator-token": {"id": "operator:ada", "kind": "operator"},
    "agent-token": {"id": "agent:model", "kind": "agent"},
    "human-token": {"id": "human:bob", "kind": "human"},
}


class TokenRpc(Rpc):
    """:class:`Rpc` that presents a bearer token on every call (``handle(auth_token=...)``)."""

    def __init__(self, server: MHSServer, auth_token: str | None = None) -> None:
        super().__init__(server)
        self.auth_token = auth_token

    def raw(self, method: str, **params: Any) -> dict[str, Any]:
        with self._lock:
            self._n += 1
            request_id = self._n
        response = self.server.handle(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
            auth_token=self.auth_token,
        )
        return response.to_dict() if hasattr(response, "to_dict") else dict(response)


class ArmBridge(Bridge):
    """Records native calls; ``outputs[cid]`` overrides what a call returns."""

    bridge_id = "tests.safety.strict_arm"

    def __init__(self, device_id: str = ARM_ID) -> None:
        super().__init__(device_id=device_id)
        self.state: dict[str, Any] = {"joint_positions": [0.0, 0.0], "stopped": True}
        self.calls: list[str] = []
        self.outputs: dict[str, Any] = {}
        self.interlock_states: dict[str, str] = {}
        self._calls_lock = threading.Lock()

    def count(self, name: str) -> int:
        with self._calls_lock:
            return sum(1 for item in self.calls if item == name)

    def _record(self, name: str) -> None:
        with self._calls_lock:
            self.calls.append(name)

    def read(self, resource_id: str, fields=None, ctx=None):  # noqa: ANN001
        return copy.deepcopy(self.state)

    def call(self, capability_id: str, args=None, ctx=None):  # noqa: ANN001
        self._record(capability_id)
        args = dict(args or {})
        if capability_id in self.outputs:
            return copy.deepcopy(self.outputs[capability_id])
        if capability_id == JOINTS:
            self.state["joint_positions"] = [float(v) for v in args.get("joint_positions") or []]
            self.state["stopped"] = False
            return {"reached": True, "joint_positions": list(self.state["joint_positions"])}
        if capability_id == STOP:
            self.state["stopped"] = True
            return {"stopped": True}
        if capability_id == TORQUE:
            return {"applied": True}
        if capability_id == DESCRIBE:
            return {"device_id": self.device_id, "mode": "simulated",
                    "manifest_digest": "sha256:" + "0" * 64, "capabilities": [JOINTS, STOP]}
        if capability_id == EXT:
            return {"pong": True}
        if capability_id == "cap.optics.set_power.v1":
            return {"set_power_mw": float(args.get("power", 0))}
        if capability_id == "cap.thermal.setpoint.v1":
            return {"setpoint": args.get("target_temperature")}
        return {"ok": True}

    def interlocks(self):
        return [{"id": key, "state": value} for key, value in self.interlock_states.items()]

    def reset(self, ctx=None):  # noqa: ANN001
        self._record("reset")
        return {"reset": True}


#: Sourced binding limits for every numeric input of the arm's actuation
#: classes, so strict hardware never refuses them with MHS.SAFETY.LIMITS_UNSET.
JOINT_LIMITS = {
    "joint_positions": {"min": -3.2, "max": 3.2, "unit": "rad", "reason": "joint travel of the test arm"},
    "duration_s": {"min": 0, "max": 60, "unit": "s", "reason": "bounded test motion"},
}
TORQUE_LIMITS = {
    "joint_torques": {"min": -20, "max": 20, "unit": "N.m", "reason": "test arm torque rating"},
    "duration_s": {"min": 0, "max": 10, "unit": "s", "reason": "bounded test motion"},
}


def arm_capabilities(*, extra: Iterable[Capability] = (), torque: bool = False) -> list[Capability]:
    caps = [
        Capability(JOINTS, "arm", exclusive=True, limits=copy.deepcopy(JOINT_LIMITS)),
        Capability(STOP, "arm"),
        Capability(DESCRIBE, "arm"),
        Capability(EXT, "arm", input_schema={"type": "object", "properties": {}},
                   output_schema={"type": "object", "properties": {"pong": {"type": "boolean"}},
                                  "required": ["pong"]}),
    ]
    if torque:
        caps.append(Capability(TORQUE, "arm", exclusive=True, limits=copy.deepcopy(TORQUE_LIMITS)))
    caps.extend(extra)
    return caps


def arm_safety(*, risk: str = "R1", achieved_by: Iterable[str] = (STOP,), **fields: Any) -> SafetyEnvelope:
    estop = fields.pop("estop", {"kind": "software", "latching": True, "latency_ms": 50})
    return SafetyEnvelope(risk_class=risk, estop=estop,
                          safe_state={"description": "arm stopped", "achieved_by": list(achieved_by)},
                          **fields)


def arm_device(
    *,
    mode: str = "simulated",
    risk: str = "R1",
    capabilities: list[Capability] | None = None,
    safety: SafetyEnvelope | None = None,
    fidelity: Any = "default",
    resources: list[Resource] | None = None,
    bridge: ArmBridge | None = None,
    torque: bool = False,
    strict: bool | None = None,
    device_id: str = ARM_ID,
) -> Device:
    if fidelity == "default":
        fidelity = dict(FIDELITY) if mode in ("simulated", "hybrid") else None
    if mode == "hybrid" and isinstance(fidelity, Mapping) and "authority" not in fidelity:
        fidelity = {**fidelity, "authority": {"arm": "hardware"}}
    return Device(
        device_id,
        "Strict arm",
        mode=mode,
        resources=resources if resources is not None else [
            Resource("arm", "robot.arm", state_schema={
                "type": "object",
                "properties": {"joint_positions": {"type": "array", "items": {"type": "number"}},
                               "stopped": {"type": "boolean"}},
            })
        ],
        capabilities=capabilities if capabilities is not None else arm_capabilities(torque=torque),
        safety=safety if safety is not None else arm_safety(risk=risk),
        fidelity=fidelity,
        bridge=bridge if bridge is not None else ArmBridge(device_id),
        strict=strict,
    )


def arm_server(device: Device | None = None, *, strict: bool | None = True, auth_token: str | None = None,
               **server_kwargs: Any) -> tuple[MHSServer, TokenRpc, Device, ArmBridge]:
    device = device if device is not None else arm_device()
    server = MHSServer("mhs://localhost/strict", [device], log_ready=False, strict=strict, **server_kwargs)
    rpc = TokenRpc(server, auth_token)
    rpc("mhs.hello", protocol_versions=["1.0"])
    return server, rpc, device, device.bridge


def strict_warnings(record: list[warnings.WarningMessage]) -> list[str]:
    return [str(item.message) for item in record if issubclass(item.category, MHSStrictWarning)]


class RecordWarnings:
    """``with RecordWarnings() as caught:`` -- every warning, never deduplicated."""

    def __enter__(self) -> list[warnings.WarningMessage]:
        self._context = warnings.catch_warnings(record=True)
        record = self._context.__enter__()
        warnings.simplefilter("always")
        return record

    def __exit__(self, *exc: Any) -> None:
        self._context.__exit__(*exc)
