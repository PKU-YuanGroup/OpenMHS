"""2-DOF planar arm: an OpenMHS reference endpoint.

This module is a protocol fixture, not a driver template: its hand-written
bridge and manifest exercise motion classes, seeded determinism, the runtime
safety rules and the conformance suite.  Write a per-repository driver with
:mod:`mhs.driver` (``MHS/sdk/docs/driver-authoring.md``).  The bindings keep
their field names (``joint_positions_deg``, ``x_mm``/``y_mm``/``elbow``) and
MCP tool names; that drift from the catalogue classes, and the ``cap.world.*``
classes bound to a ``robot.arm`` resource, are listed in
``MHS/sdk/docs/reference-endpoints.md`` and realigned after the pilot.

A deterministic simulator of a planar two-link arm (link lengths 250 mm and
200 mm).  Normative state is integer fixed-point: joint angles in millidegrees
(``mdeg``) and the end-effector pose in micrometres (``um``), computed with the
closed-form forward and inverse kinematics of a two-link planar chain.

Capabilities:

* ``cap.motion.joint_position.v1`` -- move to a joint-space target
* ``cap.motion.cartesian_pose.v1`` -- move to a cartesian pose (analytic IK)
* ``cap.motion.home.v1``          -- return to the home pose
* ``cap.motion.stop.v1``          -- stop in the declared safe state
* ``cap.world.state.v1`` / snapshot / restore
* ``cap.world.seed.v1``           -- seeded pose noise (``--noise`` mode)

With ``--noise`` the arm applies a deterministic xorshift32 pose perturbation
seeded by ``cap.world.seed.v1``; the manifest then declares
``determinism.kind = "seeded"`` with ``seed_control: parameter`` and every
receipt echoes the seed.  Without it the endpoint declares ``exact`` precision.

Run::

    python3 -m mhs.reference arm --port 7400
    python3 -m mhs.reference arm --port 7400 --noise --seed 42
"""

from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from mhs.bridge.base import Bridge, BridgeContext, make_mhs_error
from mhs.signals import Cancelled
from mhs.reference._common import (
    INSTANCE_IDS,
    EndpointSpec,
    capability,
    device,
    exact_fidelity,
    resource,
)

__all__ = ["Arm2DOF", "ArmBridge", "build", "device_manifest"]

DEVICE_SLUG = "robot/arm-2dof"
RESOURCE_ID = "arm"

LINK1_UM = 250_000
LINK2_UM = 200_000
Q1_LIMIT_MDEG = 90_000
Q2_LIMIT_MDEG = 135_000
NOISE_AMPLITUDE_UM = 2_000

_MDEG_TO_RAD = math.pi / 180_000.0


def _round(value: float) -> int:
    # Half away from zero, so the fixed-point mapping is symmetric and stable.
    return int(math.floor(value + 0.5)) if value >= 0 else int(math.ceil(value - 0.5))


def _xorshift32(state: int) -> int:
    """Deterministic 32-bit PRNG step (used for seeded noise only)."""

    state &= 0xFFFFFFFF
    if state == 0:
        state = 0x9E3779B9
    state ^= (state << 13) & 0xFFFFFFFF
    state ^= state >> 17
    state ^= (state << 5) & 0xFFFFFFFF
    return state & 0xFFFFFFFF


class Arm2DOF:
    """Integer fixed-point two-link planar arm model."""

    def __init__(self, *, noise: bool = False, seed: int = 0) -> None:
        self.noise_enabled = bool(noise)
        self.reset(seed)

    # -- lifecycle ---------------------------------------------------------
    def reset(self, seed: int = 0) -> None:
        self.q1_mdeg = 0
        self.q2_mdeg = 0
        self.pose_um = self.forward(0, 0)
        self.mode = "idle"
        self.estop_state = "released"
        self.latched = False
        self.moves = 0
        self.seed = int(seed) & 0xFFFFFFFF
        self.rng_state = self.seed or 0x12345678
        self.noise_dx_um = 0
        self.noise_dy_um = 0

    # -- kinematics --------------------------------------------------------
    @staticmethod
    def forward(q1_mdeg: int, q2_mdeg: int) -> tuple[int, int]:
        angle1 = q1_mdeg * _MDEG_TO_RAD
        angle12 = (q1_mdeg + q2_mdeg) * _MDEG_TO_RAD
        x_um = LINK1_UM * math.cos(angle1) + LINK2_UM * math.cos(angle12)
        y_um = LINK1_UM * math.sin(angle1) + LINK2_UM * math.sin(angle12)
        return _round(x_um), _round(y_um)

    @staticmethod
    def reachable(x_um: int, y_um: int) -> bool:
        radius = math.hypot(x_um, y_um)
        return abs(LINK1_UM - LINK2_UM) <= radius <= (LINK1_UM + LINK2_UM)

    @staticmethod
    def inverse(x_um: float, y_um: float, elbow: str = "down") -> tuple[int, int]:
        """Closed-form two-link IK; returns joint angles in millidegrees."""

        radius_sq = float(x_um) * float(x_um) + float(y_um) * float(y_um)
        cos_q2 = (radius_sq - LINK1_UM * LINK1_UM - LINK2_UM * LINK2_UM) / (2.0 * LINK1_UM * LINK2_UM)
        cos_q2 = max(-1.0, min(1.0, cos_q2))
        q2_rad = math.acos(cos_q2)
        if elbow == "down":
            q2_rad = -q2_rad
        q1_rad = math.atan2(y_um, x_um) - math.atan2(
            LINK2_UM * math.sin(q2_rad), LINK1_UM + LINK2_UM * math.cos(q2_rad)
        )
        return _round(q1_rad / _MDEG_TO_RAD), _round(q2_rad / _MDEG_TO_RAD)

    # -- state -------------------------------------------------------------
    def state_doc(self) -> dict[str, Any]:
        return {
            "joint_mdeg": [self.q1_mdeg, self.q2_mdeg],
            "joint_deg": [self.q1_mdeg / 1000.0, self.q2_mdeg / 1000.0],
            "pose_um": [self.pose_um[0], self.pose_um[1]],
            "pose_mm": [self.pose_um[0] / 1000.0, self.pose_um[1] / 1000.0],
            "mode": self.mode,
            "estop": self.estop_state,
            "latched": self.latched,
            "moves": self.moves,
            "seed": self.seed,
            "noise_enabled": self.noise_enabled,
            "noise_delta_um": [self.noise_dx_um, self.noise_dy_um],
            "rng_state": self.rng_state,
        }

    def snapshot(self) -> dict[str, Any]:
        return {RESOURCE_ID: copy.deepcopy(self.state_doc())}

    def restore(self, snapshot: Any) -> None:
        if not isinstance(snapshot, Mapping):
            raise make_mhs_error("MHS.SCHEMA.INVALID_INPUT", "snapshot must be an object")
        envelope = snapshot.get("snapshot")
        if isinstance(envelope, Mapping):
            snapshot = envelope
        state = snapshot.get(RESOURCE_ID)
        if not isinstance(state, Mapping):
            state = snapshot.get("state") if isinstance(snapshot.get("state"), Mapping) else snapshot
        self.q1_mdeg = int(state.get("joint_mdeg", [0, 0])[0])
        self.q2_mdeg = int(state.get("joint_mdeg", [0, 0])[1])
        self.pose_um = self.forward(self.q1_mdeg, self.q2_mdeg)
        self.mode = str(state.get("mode", "idle"))
        self.estop_state = str(state.get("estop", "released"))
        self.latched = bool(state.get("latched", False))
        self.moves = int(state.get("moves", 0))
        self.seed = int(state.get("seed", 0)) & 0xFFFFFFFF
        self.rng_state = int(state.get("rng_state", self.seed)) & 0xFFFFFFFF
        delta = state.get("noise_delta_um") or [0, 0]
        self.noise_dx_um = int(delta[0])
        self.noise_dy_um = int(delta[1])
        if self.noise_dx_um or self.noise_dy_um:
            self.pose_um = (self.pose_um[0] + self.noise_dx_um, self.pose_um[1] + self.noise_dy_um)

    # -- safety ------------------------------------------------------------
    def interlocks(self) -> list[dict[str, str]]:
        # The e-stop latch is server-owned safety state, not a hard interlock:
        # reporting it open here would make mhs.safety.reset impossible.
        return []

    def safety_status(self) -> dict[str, Any]:
        return {
            "risk_class": "R1",
            "estop": {"engaged": self.estop_state == "engaged", "latching": True},
            "interlocks": self.interlocks(),
            "permits": [],
            "safe_state": {"description": "Arm stationary at its current pose", "achieved": self.mode in ("stopped", "idle")},
        }

    def estop(self, reason: str = "") -> dict[str, Any]:
        self.estop_state = "engaged"
        self.latched = True
        self.mode = "stopped"
        return {"estop": "engaged", "latched": True, "reason": reason, "safe_state_achieved": True}

    def reset_interlocks(self) -> dict[str, Any]:
        self.estop_state = "released"
        self.latched = False
        self.mode = "idle"
        return {"reset": True, "estop": self.estop_state, "latched": False}

    def _check_motion(self) -> None:
        if self.estop_state == "engaged" or self.latched:
            raise make_mhs_error(
                "MHS.SAFETY.ESTOP_ENGAGED",
                "arm is latched; reset before commanding motion",
                {"retryable": False, "interlocks": self.interlocks()},
            )

    # -- commands ----------------------------------------------------------
    def _apply_pose(self, q1_mdeg: int, q2_mdeg: int) -> tuple[int, int]:
        base = self.forward(q1_mdeg, q2_mdeg)
        self.q1_mdeg, self.q2_mdeg = q1_mdeg, q2_mdeg
        if self.noise_enabled:
            self.rng_state = _xorshift32(self.rng_state)
            self.noise_dx_um = (self.rng_state % (2 * NOISE_AMPLITUDE_UM + 1)) - NOISE_AMPLITUDE_UM
            self.rng_state = _xorshift32(self.rng_state)
            self.noise_dy_um = (self.rng_state % (2 * NOISE_AMPLITUDE_UM + 1)) - NOISE_AMPLITUDE_UM
            self.pose_um = (base[0] + self.noise_dx_um, base[1] + self.noise_dy_um)
        else:
            self.noise_dx_um = 0
            self.noise_dy_um = 0
            self.pose_um = base
        self.moves += 1
        self.mode = "moving"
        return base

    def joint_position(self, joint_positions_deg: Any) -> dict[str, Any]:
        self._check_motion()
        if not isinstance(joint_positions_deg, (list, tuple)) or len(joint_positions_deg) != 2:
            raise make_mhs_error(
                "MHS.SCHEMA.INVALID_INPUT", "joint_positions_deg must be an array of two numbers"
            )
        q1 = _round(float(joint_positions_deg[0]) * 1000.0)
        q2 = _round(float(joint_positions_deg[1]) * 1000.0)
        if abs(q1) > Q1_LIMIT_MDEG or abs(q2) > Q2_LIMIT_MDEG:
            raise make_mhs_error(
                "MHS.SAFETY.ENVELOPE_VIOLATION",
                "joint target is outside the declared joint limits",
                {
                    "retryable": False,
                    "details": {
                        "limits_mdeg": {"q1": [-Q1_LIMIT_MDEG, Q1_LIMIT_MDEG], "q2": [-Q2_LIMIT_MDEG, Q2_LIMIT_MDEG]},
                        "requested_mdeg": [q1, q2],
                    },
                },
            )
        self._apply_pose(q1, q2)
        return {
            "reached": True,
            "joint_mdeg": [self.q1_mdeg, self.q2_mdeg],
            "pose_um": list(self.pose_um),
            "seed": self.seed,
            "determinism": "seeded" if self.noise_enabled else "exact",
        }

    def cartesian_pose(self, x_mm: float, y_mm: float, elbow: str = "down") -> dict[str, Any]:
        self._check_motion()
        x_um = _round(float(x_mm) * 1000.0)
        y_um = _round(float(y_mm) * 1000.0)
        if elbow not in ("down", "up"):
            raise make_mhs_error("MHS.SCHEMA.INVALID_INPUT", "elbow must be 'down' or 'up'")
        if not self.reachable(x_um, y_um):
            raise make_mhs_error(
                "MHS.SAFETY.ENVELOPE_VIOLATION",
                f"target ({x_mm}, {y_mm}) mm is outside the 2-DOF workspace",
                {
                    "retryable": False,
                    "details": {
                        "requested_um": [x_um, y_um],
                        "reach_um": {"min": abs(LINK1_UM - LINK2_UM), "max": LINK1_UM + LINK2_UM},
                    },
                },
            )
        q1, q2 = self.inverse(x_um, y_um, elbow=elbow)
        if abs(q1) > Q1_LIMIT_MDEG or abs(q2) > Q2_LIMIT_MDEG:
            raise make_mhs_error(
                "MHS.SAFETY.ENVELOPE_VIOLATION",
                "inverse kinematics solution is outside the declared joint limits",
                {"retryable": False, "details": {"requested_mdeg": [q1, q2]}},
            )
        base = self._apply_pose(q1, q2)
        residual_x = base[0] - x_um
        residual_y = base[1] - y_um
        return {
            "reached": True,
            "joint_mdeg": [self.q1_mdeg, self.q2_mdeg],
            "pose_um": list(self.pose_um),
            "target_um": [x_um, y_um],
            "residual_um": [residual_x, residual_y],
            "seed": self.seed,
            "determinism": "seeded" if self.noise_enabled else "exact",
        }

    def home(self) -> dict[str, Any]:
        self._check_motion()
        self._apply_pose(0, 0)
        self.mode = "homed"
        return {
            "reached": True,
            "joint_mdeg": [0, 0],
            "pose_um": list(self.pose_um),
            "seed": self.seed,
        }

    def stop(self) -> dict[str, Any]:
        self.mode = "stopped"
        return {
            "mode": "stopped",
            "joint_mdeg": [self.q1_mdeg, self.q2_mdeg],
            "pose_um": list(self.pose_um),
            "safe_state_achieved": True,
        }

    def seed_rng(self, seed: int) -> dict[str, Any]:
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise make_mhs_error("MHS.SCHEMA.INVALID_INPUT", "seed must be an integer")
        if seed < 0 or seed > 0xFFFFFFFF:
            raise make_mhs_error("MHS.SCHEMA.INVALID_INPUT", "seed must be a uint32")
        self.seed = seed
        self.rng_state = seed or 0x12345678
        self.noise_dx_um = 0
        self.noise_dy_um = 0
        self.pose_um = self.forward(self.q1_mdeg, self.q2_mdeg)
        return {"seed": self.seed, "noise_enabled": self.noise_enabled}


class ArmBridge(Bridge):
    """Map the 2-DOF arm model onto MHS motion/world capabilities."""

    bridge_kind = "python-object"
    bridge_id = "mhs.bridge.reference.arm-2dof"

    def __init__(self, *, device_noise: bool = False, seed: int = 0, device_id: str | None = None):
        super().__init__(device_id=device_id)
        self.arm = Arm2DOF(noise=device_noise, seed=seed)

    # -- adapter surface ---------------------------------------------------
    def capabilities(self) -> list[dict[str, Any]]:
        return [
            {"capability_id": "cap.motion.joint_position.v1", "resource": RESOURCE_ID, "native": "Arm2DOF::move_joints"},
            {"capability_id": "cap.motion.cartesian_pose.v1", "resource": RESOURCE_ID, "native": "Arm2DOF::move_cartesian"},
            {"capability_id": "cap.motion.home.v1", "resource": RESOURCE_ID, "native": "Arm2DOF::home"},
            {"capability_id": "cap.motion.stop.v1", "resource": RESOURCE_ID, "native": "Arm2DOF::stop"},
            {"capability_id": "cap.world.state.v1", "resource": RESOURCE_ID, "native": "Arm2DOF::state"},
            {"capability_id": "cap.world.snapshot.v1", "resource": RESOURCE_ID, "native": "Arm2DOF::snapshot"},
            {"capability_id": "cap.world.restore.v1", "resource": RESOURCE_ID, "native": "Arm2DOF::restore"},
            {"capability_id": "cap.world.seed.v1", "resource": RESOURCE_ID, "native": "Arm2DOF::seed"},
        ]

    def resources(self) -> list[dict[str, Any]]:
        return [{"resource_id": RESOURCE_ID, "kind": "robot.arm"}]

    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> dict[str, Any]:
        self.ensure_open()
        if resource_id != RESOURCE_ID:
            raise make_mhs_error("MHS.DEVICE.UNSUPPORTED", f"unknown resource {resource_id!r}")
        state = self.arm.state_doc()
        if fields:
            return {name: state.get(name) for name in fields if name in state}
        return state

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        self.ensure_open()
        return self.arm.snapshot()

    def restore(self, snapshot: Any) -> dict[str, Any]:
        self.ensure_open()
        self.arm.restore(snapshot)
        return self.arm.snapshot()

    def interlocks(self) -> list[dict[str, str]]:
        return self.arm.interlocks()

    def safety_status(self) -> dict[str, Any]:
        return self.arm.safety_status()

    def estop(self, reason: str = "", ctx: Any = None) -> dict[str, Any]:
        return self.arm.estop(reason)

    def reset(self, ctx: Any = None) -> dict[str, Any]:
        return self.arm.reset_interlocks()

    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        self.ensure_open()
        args = dict(args or {})
        if BridgeContext.coerce(ctx).cancelled():
            raise Cancelled(f"{capability_id} not started: cancellation was requested")
        arm = self.arm
        if capability_id == "cap.motion.joint_position.v1":
            return arm.joint_position(args.get("joint_positions_deg"))
        if capability_id == "cap.motion.cartesian_pose.v1":
            return arm.cartesian_pose(
                args.get("x_mm", 0), args.get("y_mm", 0), str(args.get("elbow", "down"))
            )
        if capability_id == "cap.motion.home.v1":
            return arm.home()
        if capability_id == "cap.motion.stop.v1":
            return arm.stop()
        if capability_id == "cap.world.state.v1":
            return arm.state_doc()
        if capability_id == "cap.world.snapshot.v1":
            return arm.snapshot()
        if capability_id == "cap.world.restore.v1":
            snapshot = args.get("snapshot")
            if not isinstance(snapshot, Mapping):
                raise make_mhs_error("MHS.SCHEMA.INVALID_INPUT", "snapshot must be an object")
            arm.restore(snapshot)
            return arm.snapshot()
        if capability_id == "cap.world.seed.v1":
            return arm.seed_rng(args.get("seed"))
        raise make_mhs_error(
            "MHS.DEVICE.UNSUPPORTED", f"arm bridge does not expose {capability_id!r}", {"retryable": False}
        )


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------


def _state_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["joint_mdeg", "pose_um", "mode"],
        "properties": {
            "joint_mdeg": {
                "type": "array",
                "items": {"type": "integer", "x-mhs-unit": "mdeg"},
                "minItems": 2,
                "maxItems": 2,
            },
            "joint_deg": {"type": "array", "items": {"type": "number", "x-mhs-unit": "deg"}, "minItems": 2, "maxItems": 2},
            "pose_um": {
                "type": "array",
                "items": {"type": "integer", "x-mhs-unit": "um"},
                "minItems": 2,
                "maxItems": 2,
            },
            "pose_mm": {"type": "array", "items": {"type": "number", "x-mhs-unit": "mm"}, "minItems": 2, "maxItems": 2},
            "mode": {"type": "string", "enum": ["idle", "moving", "homed", "stopped"]},
            "estop": {"type": "string", "enum": ["released", "engaged"]},
            "latched": {"type": "boolean"},
            "moves": {"type": "integer", "minimum": 0},
            "seed": {"type": "integer", "minimum": 0},
            "noise_enabled": {"type": "boolean"},
            "noise_delta_um": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
            "rng_state": {"type": "integer", "minimum": 0},
        },
    }


def _initial_state(seed: int) -> dict[str, Any]:
    import math as _math

    x = _round((LINK1_UM + LINK2_UM) * _math.cos(0.0))
    y = _round((LINK1_UM + LINK2_UM) * _math.sin(0.0))
    return {
        "joint_mdeg": [0, 0],
        "joint_deg": [0.0, 0.0],
        "pose_um": [x, y],
        "pose_mm": [x / 1000.0, y / 1000.0],
        "mode": "idle",
        "estop": "released",
        "latched": False,
        "moves": 0,
        "seed": int(seed) & 0xFFFFFFFF,
        "noise_enabled": False,
        "noise_delta_um": [0, 0],
        "rng_state": int(seed) & 0xFFFFFFFF or 0x12345678,
    }


def _caps() -> list[dict[str, Any]]:
    return [
        capability(
            "cap.motion.joint_position.v1",
            RESOURCE_ID,
            "Move the arm to a joint-space target",
            "Arm2DOF::move_joints(joint_positions_deg)",
            {
                "type": "object",
                "required": ["joint_positions_deg"],
                "properties": {
                    "joint_positions_deg": {
                        "type": "array",
                        "items": {"type": "number", "minimum": -135, "maximum": 135, "x-mhs-unit": "deg"},
                        "minItems": 2,
                        "maxItems": 2,
                        "default": [0, 0],
                        "x-mhs-unit": "deg",
                    }
                },
            },
            {"type": "object"},
            summary="Move both joints to an absolute joint-space target (degrees); bounds are enforced as a safety envelope.",
            tags=["robot arm", "joint motion", "2-dof", "kinematics", "deterministic simulation"],
            units={"joint_positions_deg": "deg"},
            effects=["motion.joint"],
            hazards=["collision", "joint limit violation"],
            preconditions=["estop released", "arm not latched"],
            constraints={"max_duration_ms": 5000},
            limits={"joint_positions_deg": {"min": -135, "max": 135, "unit": "deg", "reason": "joint travel limits"}},
        ),
        capability(
            "cap.motion.cartesian_pose.v1",
            RESOURCE_ID,
            "Move the end effector to a cartesian pose",
            "Arm2DOF::move_cartesian(x_mm, y_mm, elbow)",
            {
                "type": "object",
                "required": ["x_mm", "y_mm"],
                "properties": {
                    "x_mm": {"type": "number", "default": 300, "x-mhs-unit": "mm"},
                    "y_mm": {"type": "number", "default": 0, "x-mhs-unit": "mm"},
                    "elbow": {"type": "string", "enum": ["down", "up"], "default": "down"},
                },
            },
            {"type": "object"},
            summary="Move the end effector to a planar cartesian target using closed-form inverse kinematics.",
            tags=["robot arm", "cartesian motion", "inverse kinematics", "2-dof"],
            units={"x_mm": "mm", "y_mm": "mm"},
            effects=["motion.cartesian"],
            hazards=["collision", "unreachable target"],
            preconditions=["target inside the 2-link workspace", "estop released", "arm not latched"],
            constraints={"max_duration_ms": 5000},
            limits={"x_mm": {"min": -450, "max": 450, "unit": "mm", "reason": "workspace"}, "y_mm": {"min": -450, "max": 450, "unit": "mm", "reason": "workspace"}},
        ),
        capability(
            "cap.motion.home.v1",
            RESOURCE_ID,
            "Return the arm to its home pose",
            "Arm2DOF::home()",
            {"type": "object", "properties": {}},
            {"type": "object"},
            summary="Move the arm to the declared home pose (both joints at zero).",
            tags=["robot arm", "home", "motion"],
            effects=["motion.home"],
            preconditions=["estop released", "arm not latched"],
            constraints={"max_duration_ms": 5000},
        ),
        capability(
            "cap.motion.stop.v1",
            RESOURCE_ID,
            "Stop the arm in its safe state",
            "Arm2DOF::stop()",
            {"type": "object", "properties": {}},
            {"type": "object"},
            summary="Stop the arm at its current pose (declared safe state); no motion follows.",
            tags=["robot arm", "stop", "safe state", "motion"],
            effects=["motion.stop"],
            postconditions=["arm stationary"],
            constraints={"max_duration_ms": 1000},
            determinism="exact",
            exclusive=False,
        ),
        capability(
            "cap.world.state.v1",
            RESOURCE_ID,
            "Read the arm state",
            "Arm2DOF::state()",
            {"type": "object", "properties": {}},
            {"type": "object"},
            summary="Read joint positions, end-effector pose, mode and determinism counters.",
            tags=["robot arm", "state", "observation"],
            determinism="exact",
            exclusive=False,
        ),
        capability(
            "cap.world.snapshot.v1",
            RESOURCE_ID,
            "Take a deterministic arm snapshot",
            "Arm2DOF::snapshot()",
            {"type": "object", "properties": {}},
            {"type": "object"},
            summary="Snapshot the exact integer joint/pose state for deterministic restore.",
            tags=["robot arm", "snapshot", "determinism", "replay"],
            determinism="exact",
            exclusive=False,
        ),
        capability(
            "cap.world.restore.v1",
            RESOURCE_ID,
            "Restore a deterministic arm snapshot",
            "Arm2DOF::restore(snapshot)",
            {"type": "object", "required": ["snapshot"], "properties": {"snapshot": {"type": "object"}}},
            {"type": "object"},
            summary="Restore a previously taken arm snapshot; simulated/replay only.",
            tags=["robot arm", "restore", "determinism", "replay"],
            constraints={"max_duration_ms": 5000},
        ),
        capability(
            "cap.world.seed.v1",
            RESOURCE_ID,
            "Seed the deterministic noise source",
            "Arm2DOF::seed(seed)",
            {
                "type": "object",
                "required": ["seed"],
                "properties": {"seed": {"type": "integer", "minimum": 0, "maximum": 4294967295}},
            },
            {"type": "object"},
            summary="Set the xorshift32 seed used by the seeded-noise pose perturbation; receipts echo the seed.",
            tags=["robot arm", "seed", "determinism", "seeded noise"],
            constraints={"max_duration_ms": 1000},
            determinism="seeded",
            exclusive=False,
        ),
    ]


def _safety() -> dict[str, Any]:
    return {
        "risk_class": "R1",
        "envelope": {
            "cap.motion.joint_position.v1": {
                "joint_positions_deg": {"min": -135, "max": 135, "unit": "deg", "reason": "joint travel limits"}
            },
            "cap.motion.cartesian_pose.v1": {
                "x_mm": {"min": -450, "max": 450, "unit": "mm", "reason": "2-link workspace"},
                "y_mm": {"min": -450, "max": 450, "unit": "mm", "reason": "2-link workspace"},
            },
        },
        "interlocks": [],
        "requires_permit": [],
        "estop": {
            "kind": "software",
            "latching": True,
            "latency_ms": 50,
            "reset": "mhs.safety.reset",
            "physical_ref": "No physical e-stop exists on a simulated arm; MHS never replaces one.",
        },
        "safe_state": {
            "description": "Arm stationary at its current pose; no further motion",
            "achieved_by": ["cap.motion.stop.v1"],
        },
    }


#: A seeded-noise arm is a different fidelity instance from the exact arm even
#: though it serves the same model; snapshots and conformance claims must never
#: cross the two configurations (FID-004).
ARM_NOISE_INSTANCE_ID = "01J8ZQ3V6Y7M2N4P6R8S0T2V55"


def device_manifest(endpoint_id: str, *, noise: bool = False, seed: int = 0) -> dict[str, Any]:
    fidelity = exact_fidelity(
        "analytic",
        timestep_ms=0,
        gaps=[
            "Planar 2-DOF rigid-link kinematics only: no dynamics, inertia, gravity or contact",
            "Cartesian targets that need an elbow flip may be rejected by joint limits",
        ],
    )
    if noise:
        fidelity = dict(fidelity)
        fidelity["determinism"] = {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "xorshift32 pose noise; the seed is set by cap.world.seed.v1 and echoed in every receipt.",
        }
        fidelity["gaps"] = list(fidelity.get("gaps") or []) + [
            "Conformance reports of the exact configuration do not apply to this seeded-noise "
            "configuration; it cites its own report (FID-004).",
        ]
    return device(
        endpoint_id=endpoint_id,
        slug=DEVICE_SLUG,
        display_name="2-DOF planar arm (simulated)" + (" with seeded noise" if noise else ""),
        instance_id=ARM_NOISE_INSTANCE_ID if noise else INSTANCE_IDS["arm"],
        mode="simulated",
        model="planar-arm-2dof-sim",
        resources=[resource(RESOURCE_ID, "robot.arm", "Planar arm state", _state_schema(), _initial_state(seed))],
        capabilities=_caps(),
        safety=_safety(),
        fidelity=fidelity,
        profile={
            "title": "2-DOF planar arm",
            "summary": "Analytic two-link planar arm with integer fixed-point kinematics and exact or seeded deterministic replay.",
            "tags": ["robot arm", "planar", "2-dof", "kinematics", "deterministic simulation"],
            "operating_notes": [
                "Normative state is integer millidegrees and micrometres; no floating point is stored.",
                "With --noise, cap.world.seed.v1 selects a deterministic pose perturbation sequence.",
                "Snapshot/restore reproduces the exact joint, pose and PRNG state.",
            ],
        },
        conformance_level="CL4",
        # The published arm report is bound to the exact configuration; a
        # seeded-noise instance must not advertise it (FID-004).
        endpoint_name="arm-seeded" if noise else "arm",
        provenance_sources=["MHS/sdk/src/mhs/reference/arm.py"],
    )


def build(endpoint_id: str, *, noise: bool = False, seed: int = 0) -> EndpointSpec:
    manifest = device_manifest(endpoint_id, noise=noise, seed=seed)
    bridge = ArmBridge(device_noise=noise, seed=seed, device_id=manifest["device_id"])
    return EndpointSpec(
        name="arm",
        endpoint_id=endpoint_id,
        profile="MHS-Sim",
        devices=[manifest],
        bridges={manifest["device_id"]: bridge},
        features=[
            "MHS.SAFETY.NOT_CERTIFIED",
            "deterministic-simulation",
            "seeded-noise" if noise else "exact-determinism",
            "mcp-projection-v1",
        ],
        notes="Analytic 2-DOF planar arm" + (" with seeded noise" if noise else ""),
        conformance_level="CL4",
    )
