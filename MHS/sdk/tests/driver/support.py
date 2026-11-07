"""Fakes, sample drivers and an in-process JSON-RPC client for the Driver API tests (stdlib only)."""

from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Mapping

from mhs import canonical
from mhs.driver import (
    Driver,
    DriverFailed,
    Fact,
    Field,
    Limit,
    action,
    build_server,
    estop,
    interlock,
    read,
    reset,
    write,
)

JOINTS = ["j1", "j2", "j3", "j4", "j5", "j6"]


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------


class FakeBath:
    """An asyncio thermal bath (julabo-like); ``actuations`` records every effectful native call."""

    def __init__(self, **options: Any) -> None:
        self.options = dict(options)
        self.actuations: list[tuple[Any, ...]] = []
        self.reads = 0
        self.temperature = 21.5
        self.setpoint = 20.0
        self.pump_speed = 0.0
        self.lid_closed: Any = True
        self.ramp_started = threading.Event()
        self.ramp_cancelled = threading.Event()
        self.loops: set[int] = set()
        self.reset_calls = 0

    async def get_temperature(self) -> float:
        self.loops.add(id(asyncio.get_running_loop()))
        self.reads += 1
        await asyncio.sleep(0)
        return self.temperature

    async def set_setpoint(self, value: float) -> None:
        self.loops.add(id(asyncio.get_running_loop()))
        self.actuations.append(("set_setpoint", value))
        self.setpoint = float(value)

    def set_pump(self, value: float) -> float:
        self.actuations.append(("set_pump", value))
        self.pump_speed = round(float(value), 1)
        return self.pump_speed

    async def ramp(self, target: float, seconds: float) -> dict[str, Any]:
        self.actuations.append(("ramp", target))
        self.ramp_started.set()
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            self.ramp_cancelled.set()
            raise
        self.setpoint = float(target)
        return {"setpoint": self.setpoint, "reached": True}

    async def stop(self) -> None:
        self.actuations.append(("stop",))

    def heater_off(self) -> bool:
        self.actuations.append(("heater_off",))
        return True

    def clear_error(self) -> None:
        self.reset_calls += 1

    def explode(self) -> None:
        self.actuations.append(("explode",))
        raise RuntimeError("controller at /home/lab/secret.cfg failed")


def connect_bath(**options: Any) -> FakeBath:
    """The hardware entry point of :class:`Bath` (a fake here; a fake backend may not reuse it)."""
    return FakeBath(**options)


def marking_bath(marker: str, **options: Any) -> FakeBath:
    """A backend factory that leaves the file ``marker`` behind (a refused load never calls it)."""
    Path(marker).write_text("constructed", encoding="utf-8")
    return FakeBath(**options)


class FakeArm:
    """A 6-axis arm with joint and cartesian moves (xArm-like return codes)."""

    def __init__(self, **_options: Any) -> None:
        self.actuations: list[tuple[Any, ...]] = []
        self.joints = [0.0] * 6
        self.code = 0

    def set_servo_angle(self, angles: list[float]) -> int:
        self.actuations.append(("set_servo_angle", list(angles)))
        if self.code:
            return self.code
        self.joints = list(angles)
        return 0

    def set_position(self, x: float, y: float, z: float) -> int:
        self.actuations.append(("set_position", x, y, z))
        return 0

    def emergency_stop(self) -> None:
        self.actuations.append(("emergency_stop",))

    def get_servo_angle(self) -> list[float]:
        return list(self.joints)


# ---------------------------------------------------------------------------
# sample drivers
# ---------------------------------------------------------------------------


class Bath(Driver):
    """An R2 hardware bath: async read/write, limits, an operator_required bound, a long ramp, e-stop."""

    device_id, device_kind = "lab/bath", "thermal.zone"
    mode, risk = "hardware", "R2"
    native = "julabo.julabo:JulaboCF"
    backends = {"fake": FakeBath, "hardware": connect_bath}
    tags = ["circulator", "thermal bath"]
    facts = [Fact("Bath fluid range -20..150 Cel", source="vendor_doc", ref="manual.pdf:41")]
    safe_state = "heater off, pump stopped"
    vendor, model = "Julabo", "CF41"

    @read("temperature", unit="Cel", description="Bath temperature")
    async def temperature(self):
        return await self.native.get_temperature()

    @read("setpoint", unit="Cel")
    def current_setpoint(self):
        return self.native.setpoint

    @write("setpoint", unit="Cel", description="Temperature setpoint",
           limit=Limit(min=-20, max=150, source="upstream_code", ref="julabo/julabo.py:88"))
    async def set_setpoint(self, value):
        await self.native.set_setpoint(value)

    @write("pump_speed", unit="/min", limit=Limit.operator_required("the manual gives no pump range"))
    def set_pump(self, value):
        return self.native.set_pump(value)

    @action(cap="cap.thermal.setpoint.v1", long_running=True, cancellable=True,
            input={"target_temperature": Field(limit=Limit(min=-20, max=150, source="vendor_doc", ref="manual.pdf:42"))})
    async def ramp_to(self, target_temperature, rate=None):
        seconds = float(self.options_seconds())
        return await self.native.ramp(target_temperature, seconds)

    @action(name="x-cap.julabo.heater_off.v1", safe_state=True, description="Switch the heater off",
            output={"heater_off": Field("boolean")})
    def heater_off(self):
        return self.native.heater_off()

    @action(name="x-cap.julabo.explode.v1", description="Always fails natively")
    def explode(self):
        self.native.explode()

    @estop(latency_ms=200)
    async def stop(self):
        await self.native.stop()

    @interlock("lid_closed", description="Bath lid closed", blocks=["cap.thermal.setpoint.v1"])
    def lid(self):
        return self.native.lid_closed

    @reset
    def recover(self):
        self.native.clear_error()

    def options_seconds(self) -> float:
        return float(self.options.get("ramp_s", 0.01))


class Arm(Driver):
    """A 6-joint arm: per-element joint limits, nested cartesian limits, return-code failures."""

    device_id, device_kind = "robot/arm", "robot.arm"
    mode, risk = "hardware", "R2"
    native = "xarm.wrapper.xarm_api:XArmAPI"
    backends = {"fake": FakeArm}
    safe_state = "motion stopped"
    estop_physical_ref = "red mushroom button on the control box"

    @read("joints", type="array", items="number", length=6, unit="rad")
    def joints(self):
        return self.native.get_servo_angle()

    @action(cap="cap.motion.joint_position.v1", input={"joint_positions": Field(
        unit="rad", length=6,
        limit=Limit(min=[-6.28, -2.0, -0.1, -6.28, -1.7, -6.28], max=[6.28, 2.0, 3.8, 6.28, 3.1, 6.28],
                    names=JOINTS, source="upstream_code", ref="xarm/x3/parameter.py:12"))})
    def move_joints(self, joint_positions):
        code = self.native.set_servo_angle(joint_positions)
        if code:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"set_servo_angle returned {code}", native_code=code)
        return {"joint_positions": joint_positions, "reached": True}

    @action(cap="cap.motion.cartesian_pose.v1",
            limits={"position.x": Limit(min=-700, max=700, source="vendor_doc", ref="xarm-manual.pdf:20"),
                    "position.y": Limit(min=-700, max=700, source="vendor_doc", ref="xarm-manual.pdf:20"),
                    "position.z": Limit(min=-100, max=900, source="vendor_doc", ref="xarm-manual.pdf:20")})
    def move_pose(self, position, orientation=None, frame=None, duration_s=None):
        self.native.set_position(position["x"], position["y"], position["z"])
        return {"reached": True}

    @estop(native="emergency_stop")
    def stop(self):
        self.native.emergency_stop()


# ---------------------------------------------------------------------------
# in-process client
# ---------------------------------------------------------------------------


class Client:
    """A JSON-RPC session on one device of an in-process :class:`mhs.server.MHSServer`."""

    def __init__(self, server: Any, device_id: str | None = None, *, token: str | None = None,
                 principal: Mapping[str, Any] | None = None) -> None:
        self.server = server
        self.device_id = device_id or next(iter(server.devices))
        self.token = token
        self._ids = 0
        self.rpc("mhs.hello", {"protocol_versions": ["1.0"], "client": {"name": "driver-tests", "version": "0"}})
        device = server.devices[self.device_id]
        opened = self.rpc("mhs.session.open", {
            "device_ids": [self.device_id], "mode": device.mode, "ttl_s": 120,
            "principal": dict(principal or {"id": "driver-tests", "kind": "agent"})})
        self.session_id = opened["session_id"]
        self.resource_id = device.resources[0].resource_id

    def call(self, method: str, params: Mapping[str, Any]) -> dict[str, Any]:
        """The raw JSON-RPC response (``result`` or ``error``)."""
        self._ids += 1
        kwargs = {"auth_token": self.token} if self.token else {}
        response = self.server.handle({"jsonrpc": "2.0", "id": self._ids, "method": method, "params": dict(params)},
                                      **kwargs)
        return response.to_dict() if hasattr(response, "to_dict") else response

    def rpc(self, method: str, params: Mapping[str, Any]) -> Any:
        response = self.call(method, params)
        if "error" in response:
            raise AssertionError(f"{method} failed: {response['error']}")
        return response["result"]

    def command(self, capability_id: str, payload: Mapping[str, Any] | None = None, *,
                deadline_ms: int = 5000) -> dict[str, Any]:
        return self.rpc("mhs.command", {"session_id": self.session_id, "device_id": self.device_id,
                                        "capability_id": capability_id, "input": dict(payload or {}),
                                        "command_id": canonical.ulid(), "deadline_ms": deadline_ms})

    def write(self, patch: Mapping[str, Any]) -> dict[str, Any]:
        return self.rpc("mhs.resource.write", {"session_id": self.session_id, "device_id": self.device_id,
                                               "resource_id": self.resource_id, "patch": dict(patch),
                                               "command_id": canonical.ulid(), "deadline_ms": 5000})

    def read(self) -> dict[str, Any]:
        return self.rpc("mhs.resource.read", {"session_id": self.session_id, "device_id": self.device_id,
                                              "resource_id": self.resource_id, "deadline_ms": 5000})

    def estop(self, reason: str = "test") -> dict[str, Any]:
        return self.rpc("mhs.safety.estop", {"session_id": self.session_id, "device_id": self.device_id,
                                             "reason": reason, "deadline_ms": 5000})

    def reset(self) -> dict[str, Any]:
        return self.call("mhs.safety.reset", {"session_id": self.session_id, "device_id": self.device_id,
                                              "deadline_ms": 5000})

    def device(self) -> dict[str, Any]:
        return self.rpc("mhs.devices.get", {"device_id": self.device_id})

    def operations(self) -> list[dict[str, Any]]:
        return self.rpc("mhs.operations.list", {"session_id": self.session_id,
                                                "device_id": self.device_id})["operations"]

    def wait_running(self, timeout_s: float = 3.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            for item in self.operations():
                if item.get("state") in ("accepted", "running"):
                    return item
            time.sleep(0.005)
        raise AssertionError("no running operation appeared")

    def operation(self, operation_id: str) -> dict[str, Any]:
        return self.rpc("mhs.operations.get", {"session_id": self.session_id, "operation_id": operation_id,
                                               "deadline_ms": 5000})


def code(receipt: Mapping[str, Any]) -> str | None:
    return (receipt.get("error") or {}).get("mhs_code")


def serve(driver: Any, **options: Any) -> tuple[Any, Client]:
    server = build_server(driver, **options)
    return server, Client(server)


def write_package(directory: Path, files: Mapping[str, str]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return directory


def lock_document(*, kind: str = "model", reviewed: bool = False, commit: str = "a" * 40) -> dict[str, Any]:
    authored: dict[str, Any] = {"kind": kind}
    if kind == "model":
        authored.update({"model_id": "example-model", "run_id": "run-1", "date": "2026-10-22"})
    else:
        authored["name"] = "A. Person"
    return {
        "openmhs": "0.9",
        "package_id": "gh.example/bath",
        "upstream": {"repo_url": "https://github.com/example/bath", "commit": commit, "license_spdx": "MIT"},
        "backends": {"hardware": ".native:connect", "fake": ".fake:FakeBath"},
        "sdk_version": "0.9.0.dev0",
        "authored_by": authored,
        "reviewed_by": ({"reviewer": "R. Viewer", "date": "2026-10-22", "scope": "hardware"} if reviewed else None),
    }


def temp_dir(test: Any) -> Path:
    holder = tempfile.TemporaryDirectory(prefix="mhs-driver-test-")
    test.addCleanup(holder.cleanup)
    return Path(holder.name)


def dumps(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)
