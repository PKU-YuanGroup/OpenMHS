"""Deterministic conveyor workcell: an OpenMHS reference endpoint.

This module is a protocol fixture, not a driver template: its hand-written
bridge and manifest exercise the wire protocol, the runtime safety rules and
the conformance suite.  Write a per-repository driver with :mod:`mhs.driver`
(``MHS/sdk/docs/driver-authoring.md``).  Its bindings keep their field names
and MCP tool names; the remaining catalogue drift (the diverter's ``gate``
field, ``cap.actuation.valve.v1`` and ``cap.motion.stop.v1`` bound to a
``world.sim`` resource) is listed in ``MHS/sdk/docs/reference-endpoints.md``.

The model is an integer, fixed-step simulation of a small conveyor with a
diverter, photoelectric sensors, a safety door and a latching emergency stop.
It exists to make MHS *command semantics* executable: revisions, command ids,
interlocks, permits, receipts, evidence and deterministic replay.

The normative state is integer-only (1 tick = 1 ms of simulated time).  Part
positions are tracked in micrometres so that an integer ``velocity_mm_s`` is
exactly ``velocity_mm_s`` micrometres per tick; the manifest's schema-compatible
``position_mm`` field is derived from it.  There is no wall clock, no floating
point and no randomness in normative state, so ``state_hash`` sequences replay
byte-for-byte.

Two capability families are exposed:

* the core classes from ``MHS/schema/examples/device.conveyor-workcell.json``
  (``cap.world.step.v1``, ``cap.world.state.v1``, ``cap.actuation.valve.v1``,
  ``cap.world.snapshot.v1``, ``cap.world.restore.v1``) plus ``cap.motion.stop.v1``
  (the declared safe state);
* reference extension classes under ``x-cap.mhs-reference.*`` (start/feed) and,
  only in the **test profile**, ``x-cap.mhs-test.*`` fault injection (jam,
  sensor fault, lost receipt), door control and a bounded cancellable delay used
  by the conformance suite's negative tests.

Run it with::

    python3 -m mhs.reference conveyor --port 7400
    python3 -m mhs.reference conveyor --stdio
"""

from __future__ import annotations

import copy
import time
from typing import Any, Mapping

from mhs.bridge.base import Bridge, BridgeContext, make_mhs_error
from mhs.signals import Cancelled
from mhs.reference._common import (
    INSTANCE_IDS,
    MHS_VERSION,
    EndpointSpec,
    capability,
    device,
    exact_fidelity,
    resource,
)

__all__ = [
    "ConveyorSim",
    "ConveyorBridge",
    "build",
    "device_manifest",
    "DEVICE_SLUG",
]

DEVICE_SLUG = "lab/conveyor-workcell"
RESOURCE_ID = "workcell"

#: Safety-door latch sources.
LATCH_NONE = None
LATCH_DOOR = "door"
LATCH_ESTOP = "estop"

#: Geometry, in micrometres along the conveyor.
DIVERTER_UM = 600_000
DIVERTED_BIN_UM = 800_000
OUTFEED_UM = 1_000_000
INFEED_CLEAR_UM = 100_000

class ConveyorSim:
    """Integer fixed-step conveyor model.  Pure, deterministic, snapshotable."""

    tick_ms = 1

    def __init__(self) -> None:
        self.reset()

    # -- lifecycle ---------------------------------------------------------
    def reset(self) -> None:
        self.tick = 0
        self.mono_ms = 0
        self.door = "closed"
        self.estop_state = "released"
        self.latched = False
        self.latch_reason: str | None = LATCH_NONE
        self.gate = "main"
        self.velocity_mm_s = 0
        self.drive = "stopped"
        self.parts: list[dict[str, Any]] = []
        self.part_seq = 0
        self.parts_delivered = 0
        self.faults: set[str] = set()
        self.lost_receipt_pending = False

    # -- state -------------------------------------------------------------
    def _sync_part(self, part: dict[str, Any]) -> None:
        part["position_mm"] = int(part["position_um"]) // 1000

    def sensors(self) -> dict[str, str]:
        if "sensor_fault" in self.faults:
            return {"infeed": "unknown", "diverter": "unknown"}
        infeed = "part" if any(int(p["position_um"]) < INFEED_CLEAR_UM for p in self.parts) else "clear"
        diverter = "part" if any(0 < int(p["position_um"]) < DIVERTER_UM for p in self.parts) else "clear"
        return {"infeed": infeed, "diverter": diverter}

    def state_doc(self) -> dict[str, Any]:
        parts = []
        for part in self.parts:
            item = {
                "id": part["id"],
                "position_mm": int(part["position_um"]) // 1000,
                "position_um": int(part["position_um"]),
                "route": part["route"],
            }
            parts.append(item)
        return {
            "tick": self.tick,
            "door": self.door,
            "estop": self.estop_state,
            "parts": parts,
            "velocity_mm_s": self.velocity_mm_s,
            "mono_ms": self.mono_ms,
            "gate": self.gate,
            "drive": self.drive,
            "latched": self.latched,
            "latch_reason": self.latch_reason,
            "part_seq": self.part_seq,
            "parts_delivered": self.parts_delivered,
            "faults": sorted(self.faults),
            "sensors": self.sensors(),
        }

    def snapshot(self) -> dict[str, Any]:
        return {RESOURCE_ID: copy.deepcopy(self.state_doc())}

    def restore(self, snapshot: Any) -> None:
        state = _extract_state(snapshot)
        self.reset()
        self.tick = int(state.get("tick", 0))
        self.mono_ms = int(state.get("mono_ms", 0))
        self.door = str(state.get("door", "closed"))
        self.estop_state = str(state.get("estop", "released"))
        self.latched = bool(state.get("latched", False))
        self.latch_reason = state.get("latch_reason")
        self.gate = str(state.get("gate", "main"))
        self.velocity_mm_s = int(state.get("velocity_mm_s", 0))
        self.drive = str(state.get("drive", "stopped"))
        self.part_seq = int(state.get("part_seq", 0))
        self.parts_delivered = int(state.get("parts_delivered", 0))
        self.faults = set(state.get("faults") or [])
        self.parts = []
        for raw in state.get("parts") or []:
            part = {
                "id": str(raw.get("id")),
                "position_um": int(raw.get("position_um", int(raw.get("position_mm", 0)) * 1000)),
                "route": str(raw.get("route", "main")),
            }
            self._sync_part(part)
            self.parts.append(part)

    # -- safety ------------------------------------------------------------
    def latch(self, reason: str) -> None:
        self.latched = True
        self.latch_reason = reason
        self.velocity_mm_s = 0
        self.drive = "stopped"
        self.gate = "main"

    def interlocks(self) -> list[dict[str, str]]:
        # Only *controllable* hard interlocks are reported here.  The e-stop and
        # workcell latch are server-owned safety state (reported as
        # ``estop.engaged``), not interlocks: reporting them open would make
        # ``mhs.safety.reset`` impossible, because reset is what releases them.
        return [
            {
                "id": "door_closed",
                "state": "closed" if self.door == "closed" else "open",
                "description": "Safety door is closed",
            }
        ]

    def safety_status(self) -> dict[str, Any]:
        return {
            "risk_class": "R1",
            "estop": {"engaged": self.estop_state == "engaged", "latching": True},
            "interlocks": self.interlocks(),
            "permits": [],
            "safe_state": {
                "description": "Conveyor stopped, diverter gate in main position",
                "achieved": self.velocity_mm_s == 0 and self.gate == "main",
            },
        }

    def estop(self, reason: str = "") -> dict[str, Any]:
        self.estop_state = "engaged"
        self.latch(LATCH_ESTOP)
        return {"estop": "engaged", "latched": True, "reason": reason}

    def reset_interlocks(self) -> dict[str, Any]:
        if self.door != "closed":
            raise make_mhs_error(
                "MHS.SAFETY.INTERLOCK_OPEN",
                "Safety door is open; close it before reset",
                {"retryable": False, "interlocks": [{"id": "door_closed", "state": "open"}]},
            )
        self.estop_state = "released"
        self.latched = False
        self.latch_reason = LATCH_NONE
        self.velocity_mm_s = 0
        self.drive = "stopped"
        self.gate = "main"
        return {"reset": True, "latched": False, "estop": "released"}

    # -- commands ----------------------------------------------------------
    def _require_ready(self, *, need_drive: bool = False) -> None:
        if self.door != "closed":
            raise make_mhs_error(
                "MHS.SAFETY.INTERLOCK_OPEN",
                "Safety door is open",
                {"retryable": False, "interlocks": [{"id": "door_closed", "state": "open"}]},
            )
        if self.estop_state == "engaged" or self.latched:
            raise make_mhs_error(
                "MHS.SAFETY.ESTOP_ENGAGED",
                "Workcell is latched; reset and clear interlocks first",
                {
                    "retryable": False,
                    "interlocks": [
                        {"id": "estop_released", "state": "open"},
                        {"id": "workcell_latched", "state": "open"},
                    ],
                },
            )
        if need_drive and self.drive != "running":
            raise make_mhs_error(
                "MHS.CONFLICT.PRECONDITION",
                "Conveyor drive is not running; start it first",
                {"retryable": False},
            )

    def step(self, ticks: int) -> dict[str, Any]:
        if ticks < 0:
            raise make_mhs_error(
                "MHS.SCHEMA.INVALID_INPUT",
                "ticks must be >= 0",
                {"retryable": False, "details": {"field": "ticks"}},
            )
        # An e-stop or latch holds the drive at zero but time still advances.
        for _ in range(ticks):
            self.tick += 1
            self.mono_ms += 1
            if self.latched or self.estop_state == "engaged":
                continue
            if "jam" in self.faults or self.velocity_mm_s <= 0:
                continue
            advance = self.velocity_mm_s  # micrometres per tick == mm/s
            delivered = []
            for part in self.parts:
                part["position_um"] = int(part["position_um"]) + advance
                if part["route"] == "main":
                    if self.gate == "divert" and part["position_um"] >= DIVERTER_UM:
                        part["route"] = "diverted"
                    if part["position_um"] >= OUTFEED_UM:
                        delivered.append(part)
                elif part["route"] == "diverted":
                    if part["position_um"] >= DIVERTED_BIN_UM:
                        part["position_um"] = DIVERTED_BIN_UM
                        part["route"] = "stopped"
                elif part["route"] == "stopped":
                    part["position_um"] = min(int(part["position_um"]), DIVERTED_BIN_UM)
                self._sync_part(part)
            for part in delivered:
                self.parts.remove(part)
                self.parts_delivered += 1
        return {"tick": self.tick, "state_hash": None, "sensors": self.sensors()}

    def set_gate(self, gate: str) -> dict[str, Any]:
        self.gate = gate
        return {"gate": self.gate}

    def start(self, speed_mm_s: int = 50) -> dict[str, Any]:
        self._require_ready()
        self.velocity_mm_s = int(speed_mm_s)
        self.drive = "running" if self.velocity_mm_s > 0 else "stopped"
        return {"drive": self.drive, "velocity_mm_s": self.velocity_mm_s}

    def stop(self) -> dict[str, Any]:
        self.velocity_mm_s = 0
        self.drive = "stopped"
        self.gate = "main"
        return {"drive": "stopped", "velocity_mm_s": 0, "gate": "main", "safe_state_achieved": True}

    def feed(self, count: int = 1) -> dict[str, Any]:
        self._require_ready()
        fed: list[str] = []
        for _ in range(int(count)):
            if any(int(part["position_um"]) < INFEED_CLEAR_UM for part in self.parts):
                raise make_mhs_error(
                    "MHS.CONFLICT.PRECONDITION",
                    "Infeed is occupied; clear it before feeding another part",
                    {"retryable": True, "details": {"infeed_clear_um": INFEED_CLEAR_UM}},
                )
            part_id = f"P{self.part_seq:04d}"
            self.part_seq += 1
            part = {"id": part_id, "position_um": 0, "position_mm": 0, "route": "main"}
            self.parts.append(part)
            fed.append(part_id)
        return {"fed": fed, "part_count": len(self.parts)}

    def set_door(self, door: str) -> dict[str, Any]:
        self.door = door
        if door == "open":
            self.latch(LATCH_DOOR)
        return {"door": self.door, "latched": self.latched}

    def set_fault(self, fault: str, enabled: bool) -> dict[str, Any]:
        if enabled:
            self.faults.add(fault)
            if fault == "jam":
                self.velocity_mm_s = 0
                self.drive = "stopped"
            if fault == "lost_receipt":
                self.lost_receipt_pending = True
        else:
            self.faults.discard(fault)
            if fault == "lost_receipt":
                self.lost_receipt_pending = False
        return {"fault": fault, "enabled": bool(enabled), "faults": sorted(self.faults)}


def _extract_state(snapshot: Any) -> Mapping[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise make_mhs_error("MHS.BRIDGE.MAPPING_ERROR", "snapshot must be an object", {"retryable": False})
    # mhs.snapshot wraps the bridge state under "snapshot"; accept both shapes.
    envelope = snapshot.get("snapshot")
    if isinstance(envelope, Mapping):
        snapshot = envelope
    if RESOURCE_ID in snapshot and isinstance(snapshot[RESOURCE_ID], Mapping):
        return snapshot[RESOURCE_ID]
    state = snapshot.get("state")
    if isinstance(state, Mapping):
        if RESOURCE_ID in state and isinstance(state[RESOURCE_ID], Mapping):
            return state[RESOURCE_ID]
        return state
    return snapshot


# ---------------------------------------------------------------------------
# bridge
# ---------------------------------------------------------------------------

_BINDINGS: list[dict[str, Any]] = [
    {
        "capability_id": "cap.world.step.v1",
        "resource": RESOURCE_ID,
        "native": "ConveyorSim::advance(ticks)",
        "description": "Advance the deterministic integer simulation by whole ticks (1 tick = 1 ms).",
    },
    {
        "capability_id": "cap.world.state.v1",
        "resource": RESOURCE_ID,
        "native": "ConveyorSim::state()",
        "description": "Read the complete world state without mutating it.",
    },
    {
        "capability_id": "cap.actuation.valve.v1",
        "resource": RESOURCE_ID,
        "native": "ConveyorSim::set_diverter(gate)",
        "description": "Move the diverter gate between main and divert positions (permit-gated).",
    },
    {
        "capability_id": "cap.motion.stop.v1",
        "resource": RESOURCE_ID,
        "native": "ConveyorSim::stop()",
        "description": "Bring the conveyor to its declared safe state (drive stopped, gate main).",
    },
    {
        "capability_id": "cap.world.snapshot.v1",
        "resource": RESOURCE_ID,
        "native": "ConveyorSim::snapshot()",
        "description": "Return a deterministic snapshot of the normative world state.",
    },
    {
        "capability_id": "cap.world.restore.v1",
        "resource": RESOURCE_ID,
        "native": "ConveyorSim::restore(snapshot)",
        "description": "Restore a previously taken snapshot (simulated/replay only).",
    },
    {
        "capability_id": "x-cap.mhs-reference.start.v1",
        "resource": RESOURCE_ID,
        "native": "ConveyorSim::start(speed_mm_s)",
        "description": "Start the conveyor drive at a bounded integer speed.",
    },
    {
        "capability_id": "x-cap.mhs-reference.feed.v1",
        "resource": RESOURCE_ID,
        "native": "ConveyorSim::feed(count)",
        "description": "Place parts on the infeed when the infeed zone is clear.",
    },
]

_TEST_BINDINGS: list[dict[str, Any]] = [
    {
        "capability_id": "x-cap.mhs-test.fault_inject.v1",
        "resource": RESOURCE_ID,
        "native": "ConveyorSim::set_fault(fault, enabled)",
        "description": "TEST PROFILE ONLY: inject jam / sensor_fault / lost_receipt faults.",
    },
    {
        "capability_id": "x-cap.mhs-test.set_door.v1",
        "resource": RESOURCE_ID,
        "native": "ConveyorSim::set_door(state)",
        "description": "TEST PROFILE ONLY: open or close the simulated safety door.",
    },
    {
        "capability_id": "x-cap.mhs-test.delay.v1",
        "resource": RESOURCE_ID,
        "native": "ConveyorSim::delay(ms)",
        "description": "TEST PROFILE ONLY: bounded, cancellable delay for cancellation/deadline tests.",
    },
]


class ConveyorBridge(Bridge):
    """Map the conveyor workcell onto MHS capabilities."""

    bridge_kind = "python-object"
    bridge_id = "mhs.bridge.reference.conveyor"

    def __init__(self, *, device_id: str | None = None, test_profile: bool = False):
        super().__init__(device_id=device_id)
        self.test_profile = bool(test_profile)
        self.sim = ConveyorSim()
        self._bindings = list(_BINDINGS) + (list(_TEST_BINDINGS) if test_profile else [])

    # -- adapter surface ---------------------------------------------------
    def capabilities(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._bindings)

    def resources(self) -> list[dict[str, Any]]:
        return [{"resource_id": RESOURCE_ID, "kind": "world.sim", "hash_exclusions": ["/mono_ms"]}]

    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> dict[str, Any]:
        self.ensure_open()
        if resource_id != RESOURCE_ID:
            raise make_mhs_error(
                "MHS.BRIDGE.CAPABILITY_NOT_SUPPORTED",
                f"unknown resource {resource_id!r}",
                {"retryable": False},
            )
        state = self.sim.state_doc()
        if fields:
            return {name: state.get(name) for name in fields if name in state}
        return state

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        self.ensure_open()
        return self.sim.snapshot()

    def restore(self, snapshot: Any) -> dict[str, Any]:
        self.ensure_open()
        self.sim.restore(snapshot)
        return {RESOURCE_ID: self.sim.state_doc()}

    def interlocks(self) -> list[dict[str, str]]:
        return self.sim.interlocks()

    def safety_status(self) -> dict[str, Any]:
        return self.sim.safety_status()

    def estop(self, reason: str = "", ctx: Any = None) -> dict[str, Any]:
        return self.sim.estop(reason)

    def reset(self, ctx: Any = None) -> dict[str, Any]:
        return self.sim.reset_interlocks()

    # -- contract-plane calls ----------------------------------------------
    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        self.ensure_open()
        args = dict(args or {})
        context = BridgeContext.coerce(ctx)
        output = self._dispatch(capability_id, args, context)
        if context.cancelled():
            raise Cancelled(f"{capability_id} stopped: cancellation was requested")
        if self.sim.lost_receipt_pending and capability_id != "x-cap.mhs-test.fault_inject.v1":
            # Simulated "unknown outcome": the effect happened, the receipt did not
            # make it back. The host must treat this as unknown, not as a rejection.
            self.sim.lost_receipt_pending = False
            self.sim.faults.discard("lost_receipt")
            raise make_mhs_error(
                "MHS.OUTCOME.UNKNOWN",
                "Simulated lost receipt: the command may have taken effect; do not retry blindly",
                {
                    "retryable": False,
                    "effect_applied": True,
                    "details": {"fault": "lost_receipt", "capability_id": capability_id},
                },
            )
        return output

    # -- internals ---------------------------------------------------------
    def _dispatch(self, capability_id: str, args: Mapping[str, Any], ctx: BridgeContext) -> Any:
        sim = self.sim
        if capability_id == "cap.world.step.v1":
            ticks = args.get("ticks")
            if not isinstance(ticks, int) or isinstance(ticks, bool):
                raise make_mhs_error(
                    "MHS.SCHEMA.INVALID_INPUT",
                    "ticks must be an integer",
                    {"retryable": False, "details": {"field": "ticks"}},
                )
            if ticks < 1 or ticks > 10000:
                raise make_mhs_error(
                    "MHS.SAFETY.ENVELOPE_VIOLATION",
                    f"ticks={ticks} is outside the declared envelope 1..10000",
                    {"retryable": False, "details": {"field": "ticks", "min": 1, "max": 10000}},
                )
            return sim.step(ticks)
        if capability_id == "cap.world.state.v1":
            return sim.state_doc()
        if capability_id == "cap.actuation.valve.v1":
            gate = args.get("gate")
            if gate not in ("main", "divert"):
                raise make_mhs_error(
                    "MHS.SCHEMA.INVALID_INPUT",
                    "gate must be 'main' or 'divert'",
                    {"retryable": False, "details": {"field": "gate"}},
                )
            sim._require_ready()
            return sim.set_gate(str(gate))
        if capability_id == "cap.motion.stop.v1":
            return sim.stop()
        if capability_id == "cap.world.snapshot.v1":
            return sim.snapshot()
        if capability_id == "cap.world.restore.v1":
            snapshot = args.get("snapshot")
            if not isinstance(snapshot, Mapping):
                raise make_mhs_error(
                    "MHS.SCHEMA.INVALID_INPUT",
                    "snapshot must be an object",
                    {"retryable": False},
                )
            sim.restore(snapshot)
            return {RESOURCE_ID: sim.state_doc()}
        if capability_id == "x-cap.mhs-reference.start.v1":
            speed = args.get("speed_mm_s", 50)
            if not isinstance(speed, int) or isinstance(speed, bool):
                raise make_mhs_error(
                    "MHS.SCHEMA.INVALID_INPUT",
                    "speed_mm_s must be an integer",
                    {"retryable": False},
                )
            if speed < 0 or speed > 200:
                raise make_mhs_error(
                    "MHS.SAFETY.ENVELOPE_VIOLATION",
                    f"speed_mm_s={speed} is outside the declared envelope 0..200",
                    {"retryable": False, "details": {"field": "speed_mm_s", "min": 0, "max": 200}},
                )
            return sim.start(speed)
        if capability_id == "x-cap.mhs-reference.feed.v1":
            count = args.get("count", 1)
            if not isinstance(count, int) or isinstance(count, bool):
                raise make_mhs_error(
                    "MHS.SCHEMA.INVALID_INPUT", "count must be an integer", {"retryable": False}
                )
            if count < 1 or count > 32:
                raise make_mhs_error(
                    "MHS.SAFETY.ENVELOPE_VIOLATION",
                    f"count={count} is outside the declared envelope 1..32",
                    {"retryable": False},
                )
            return sim.feed(count)
        if not self.test_profile:
            raise make_mhs_error(
                "MHS.BRIDGE.CAPABILITY_NOT_SUPPORTED",
                f"capability {capability_id!r} is not part of this endpoint profile",
                {"retryable": False},
            )
        if capability_id == "x-cap.mhs-test.set_door.v1":
            state = args.get("state")
            if state not in ("open", "closed"):
                raise make_mhs_error(
                    "MHS.SCHEMA.INVALID_INPUT",
                    "state must be 'open' or 'closed'",
                    {"retryable": False},
                )
            return sim.set_door(str(state))
        if capability_id == "x-cap.mhs-test.fault_inject.v1":
            fault = args.get("fault")
            if fault not in ("jam", "sensor_fault", "lost_receipt"):
                raise make_mhs_error(
                    "MHS.SCHEMA.INVALID_INPUT",
                    "fault must be jam, sensor_fault or lost_receipt",
                    {"retryable": False},
                )
            return sim.set_fault(str(fault), bool(args.get("enabled", True)))
        if capability_id == "x-cap.mhs-test.delay.v1":
            ms = int(args.get("ms", 10))
            if ms < 10 or ms > 2000:
                raise make_mhs_error(
                    "MHS.SAFETY.ENVELOPE_VIOLATION",
                    f"ms={ms} is outside the declared envelope 10..2000",
                    {"retryable": False},
                )
            slept = 0
            while slept < ms:
                if ctx.cancelled():
                    raise Cancelled(f"delay cancelled after {slept} ms")
                time.sleep(0.005)
                slept += 5
            return {"slept_ms": slept, "cancelled": False}
        raise make_mhs_error(
            "MHS.BRIDGE.CAPABILITY_NOT_SUPPORTED",
            f"capability {capability_id!r} is not declared by the conveyor bridge",
            {"retryable": False},
        )


def _effects() -> dict[str, list[dict[str, Any]]]:
    return {
        "cap.actuation.valve.v1": [
            {"kind": "actuation.valve", "summary": "diverter gate moved", "reversible": True, "severity": "R1"}
        ],
        "cap.motion.stop.v1": [
            {"kind": "motion.stop", "summary": "conveyor stopped in safe state", "reversible": True, "severity": "R1"}
        ],
        "x-cap.mhs-reference.start.v1": [
            {"kind": "motion.start", "summary": "conveyor drive started", "reversible": True, "severity": "R1"}
        ],
        "x-cap.mhs-reference.feed.v1": [
            {"kind": "material.feed", "summary": "parts placed on the infeed", "reversible": True, "severity": "R1"}
        ],
        "x-cap.mhs-test.set_door.v1": [
            {"kind": "safety.interlock", "summary": "safety door moved", "reversible": True, "severity": "R1"}
        ],
        "x-cap.mhs-test.fault_inject.v1": [
            {"kind": "test.fault", "summary": "test fault flag toggled", "reversible": True, "severity": "R0"}
        ],
    }


_EFFECTS = _effects()


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------


def _state_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["tick", "door", "estop", "parts"],
        "properties": {
            "tick": {"type": "integer", "minimum": 0, "x-mhs-unit": "ms"},
            "door": {"type": "string", "enum": ["closed", "open"]},
            "estop": {"type": "string", "enum": ["released", "engaged"]},
            "parts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "position_mm", "route"],
                    "properties": {
                        "id": {"type": "string"},
                        "position_mm": {"type": "integer", "x-mhs-unit": "mm"},
                        "position_um": {"type": "integer", "x-mhs-unit": "um"},
                        "route": {"type": "string", "enum": ["main", "diverted", "stopped"]},
                    },
                },
            },
            "velocity_mm_s": {"type": "integer", "x-mhs-unit": "mm/s"},
            "mono_ms": {"type": "integer", "x-mhs-unit": "ms"},
            "gate": {"type": "string", "enum": ["main", "divert"]},
            "drive": {"type": "string", "enum": ["stopped", "running"]},
            "latched": {"type": "boolean"},
            "latch_reason": {"type": ["string", "null"], "enum": ["door", "estop", None]},
            "part_seq": {"type": "integer", "minimum": 0},
            "parts_delivered": {"type": "integer", "minimum": 0},
            "faults": {"type": "array", "items": {"type": "string"}},
            "sensors": {"type": "object"},
        },
    }


def _initial_state() -> dict[str, Any]:
    return {
        "tick": 0,
        "door": "closed",
        "estop": "released",
        "parts": [],
        "velocity_mm_s": 0,
        "mono_ms": 0,
        "gate": "main",
        "drive": "stopped",
        "latched": False,
        "latch_reason": None,
        "part_seq": 0,
        "parts_delivered": 0,
        "faults": [],
        "sensors": {"infeed": "clear", "diverter": "clear"},
    }


def _capabilities(test_profile: bool) -> list[dict[str, Any]]:
    caps = [
        capability(
            "cap.world.step.v1",
            RESOURCE_ID,
            "Advance the simulated workcell",
            "ConveyorSim::advance(ticks)",
            {
                "type": "object",
                "required": ["ticks"],
                "properties": {"ticks": {"type": "integer", "minimum": 1, "maximum": 10000}},
            },
            {"type": "object"},
            summary="Advance the deterministic integer workcell simulation by whole 1 ms ticks.",
            tags=["conveyor", "simulation", "deterministic", "fixed step", "world step"],
            units={"ticks": "ms"},
            effects=["world.time", "motion.transport"],
            preconditions=["workcell not latched", "estop released", "safety door closed"],
            postconditions=["tick advanced by ticks", "parts advanced by velocity"],
            constraints={"cancellable": False, "max_duration_ms": 5000},
            limits={"ticks": {"min": 1, "max": 10000, "reason": "bounded step to keep calls bounded"}},
        ),
        capability(
            "cap.world.state.v1",
            RESOURCE_ID,
            "Read the complete world state",
            "ConveyorSim::state()",
            {"type": "object", "properties": {}},
            {"type": "object"},
            summary="Read the complete conveyor workcell state document without mutating it.",
            tags=["conveyor", "world state", "read only", "observation"],
            determinism="exact",
            exclusive=False,
        ),
        capability(
            "cap.actuation.valve.v1",
            RESOURCE_ID,
            "Set the diverter gate",
            "ConveyorSim::set_diverter(gate)",
            {
                "type": "object",
                "required": ["gate"],
                "properties": {"gate": {"type": "string", "enum": ["main", "divert"]}},
            },
            {"type": "object"},
            summary="Move the diverter gate so parts route to the main line or the divert bin.",
            tags=["conveyor", "diverter", "routing", "valve", "actuation"],
            units={},
            effects=["actuation.valve"],
            hazards=["part misrouting", "jam"],
            preconditions=["safety door closed", "workcell not latched"],
            constraints={"max_duration_ms": 2000},
            requires_permit=True,
        ),
        capability(
            "cap.motion.stop.v1",
            RESOURCE_ID,
            "Stop the conveyor in its safe state",
            "ConveyorSim::stop()",
            {"type": "object", "properties": {}},
            {"type": "object"},
            summary="Stop the conveyor drive and return the diverter gate to the main position (declared safe state).",
            tags=["conveyor", "stop", "safe state", "motion"],
            effects=["motion.stop"],
            postconditions=["velocity is zero", "gate is main"],
            constraints={"max_duration_ms": 1000},
            determinism="exact",
            exclusive=False,
        ),
        capability(
            "cap.world.snapshot.v1",
            RESOURCE_ID,
            "Take a deterministic snapshot",
            "ConveyorSim::snapshot()",
            {"type": "object", "properties": {}},
            {"type": "object"},
            summary="Return a snapshot of the normative workcell state for later exact restore.",
            tags=["simulation", "snapshot", "determinism", "replay"],
            determinism="exact",
            exclusive=False,
        ),
        capability(
            "cap.world.restore.v1",
            RESOURCE_ID,
            "Restore a deterministic snapshot",
            "ConveyorSim::restore(snapshot)",
            {
                "type": "object",
                "required": ["snapshot"],
                "properties": {"snapshot": {"type": "object"}},
            },
            {"type": "object"},
            summary="Restore a previously taken snapshot; only valid on simulated/replay endpoints.",
            tags=["simulation", "restore", "determinism", "replay"],
            preconditions=["snapshot was taken by this device", "mode is simulated or replay"],
            constraints={"max_duration_ms": 5000},
        ),
        capability(
            "x-cap.mhs-reference.start.v1",
            RESOURCE_ID,
            "Start the conveyor drive (reference extension)",
            "ConveyorSim::start(speed_mm_s)",
            {
                "type": "object",
                "properties": {"speed_mm_s": {"type": "integer", "minimum": 0, "maximum": 200}},
            },
            {"type": "object"},
            summary="Start the conveyor drive at a bounded integer speed in mm/s.",
            tags=["conveyor", "start", "drive", "reference extension"],
            units={"speed_mm_s": "mm/s"},
            effects=["motion.start"],
            preconditions=["workcell not latched", "estop released", "safety door closed"],
            constraints={"max_duration_ms": 1000},
            limits={"speed_mm_s": {"min": 0, "max": 200, "reason": "bounded reference speed"}},
        ),
        capability(
            "x-cap.mhs-reference.feed.v1",
            RESOURCE_ID,
            "Feed parts onto the conveyor infeed (reference extension)",
            "ConveyorSim::feed(count)",
            {
                "type": "object",
                "properties": {"count": {"type": "integer", "minimum": 1, "maximum": 32}},
            },
            {"type": "object"},
            summary="Place parts on the infeed when the infeed zone is clear, up to a bounded count.",
            tags=["conveyor", "infeed", "material feed", "reference extension"],
            effects=["material.feed"],
            preconditions=["infeed zone clear", "workcell not latched"],
            constraints={"max_duration_ms": 1000},
            limits={"count": {"min": 1, "max": 32, "reason": "bounded feed batch"}},
        ),
    ]
    if test_profile:
        caps.extend(
            [
                capability(
                    "x-cap.mhs-test.fault_inject.v1",
                    RESOURCE_ID,
                    "Inject a test fault (test profile only)",
                    "ConveyorSim::set_fault(fault, enabled)",
                    {
                        "type": "object",
                        "required": ["fault"],
                        "properties": {
                            "fault": {
                                "type": "string",
                                "enum": ["jam", "sensor_fault", "lost_receipt"],
                            },
                            "enabled": {"type": "boolean"},
                        },
                    },
                    {"type": "object"},
                    summary="TEST PROFILE ONLY. Inject a deterministic fault: conveyor jam, sensor fault, or a lost receipt.",
                    tags=["test only", "fault injection", "jam", "sensor fault", "unknown outcome"],
                    effects=["test.fault"],
                    constraints={"max_duration_ms": 1000},
                    determinism="exact",
                    exclusive=False,
                ),
                capability(
                    "x-cap.mhs-test.set_door.v1",
                    RESOURCE_ID,
                    "Open or close the simulated safety door (test profile only)",
                    "ConveyorSim::set_door(state)",
                    {
                        "type": "object",
                        "required": ["state"],
                        "properties": {"state": {"type": "string", "enum": ["open", "closed"]}},
                    },
                    {"type": "object"},
                    summary="TEST PROFILE ONLY. Open or close the simulated safety door to exercise interlock rejection.",
                    tags=["test only", "safety door", "interlock", "negative test"],
                    effects=["safety.interlock"],
                    constraints={"max_duration_ms": 1000},
                ),
                capability(
                    "x-cap.mhs-test.delay.v1",
                    RESOURCE_ID,
                    "Bounded cancellable delay (test profile only)",
                    "ConveyorSim::delay(ms)",
                    {
                        "type": "object",
                        "required": ["ms"],
                        "properties": {"ms": {"type": "integer", "minimum": 10, "maximum": 2000}},
                    },
                    {"type": "object"},
                    summary="TEST PROFILE ONLY. Sleep for a bounded time so cancellation and deadline behaviour can be exercised.",
                    tags=["test only", "delay", "cancellation", "deadline"],
                    constraints={"cancellable": True, "max_duration_ms": 2000},
                    exclusive=False,
                    determinism="exact",
                ),
            ]
        )
    return caps


def _safety(test_profile: bool) -> dict[str, Any]:
    required_for_actuation = ["cap.actuation.*"]
    required_for_motion = [
        "cap.actuation.*",
        "cap.world.step.v1",
        "x-cap.mhs-reference.start.v1",
        "x-cap.mhs-reference.feed.v1",
    ]
    envelope: dict[str, Any] = {
        "cap.world.step.v1": {"ticks": {"min": 1, "max": 10000, "reason": "bounded simulation step"}},
        "cap.actuation.valve.v1": {
            "gate": {"allowed": ["main", "divert"], "reason": "two-position gate"}
        },
        "x-cap.mhs-reference.start.v1": {
            "speed_mm_s": {"min": 0, "max": 200, "unit": "mm/s", "reason": "bounded drive speed"}
        },
        "x-cap.mhs-reference.feed.v1": {
            "count": {"min": 1, "max": 32, "reason": "bounded feed batch"}
        },
    }
    if test_profile:
        required_for_motion.append("x-cap.mhs-test.delay.v1")
        # Only the test profile binds the delay, so only it declares the delay's envelope.
        envelope["x-cap.mhs-test.delay.v1"] = {
            "ms": {"min": 10, "max": 2000, "unit": "ms", "reason": "bounded test delay"}
        }
    return {
        "risk_class": "R1",
        "envelope": envelope,
        "interlocks": [
            {
                "id": "door_closed",
                "description": "Safety door is closed",
                "source": "simulated",
                "required_for": required_for_actuation
                + required_for_motion
                + ["cap.world.step.v1", "cap.actuation.valve.v1", "x-cap.mhs-reference.feed.v1"],
            },
        ],
        "requires_permit": ["cap.actuation.*"],
        "estop": {
            "kind": "software",
            "latching": True,
            "latency_ms": 50,
            "reset": "mhs.safety.reset",
            "physical_ref": "No physical e-stop exists on a simulated workcell; MHS never replaces one.",
        },
        "safe_state": {
            "description": "Conveyor stopped, diverter gate in main position, no parts moving",
            "achieved_by": ["cap.motion.stop.v1"],
        },
    }


def _profile() -> dict[str, Any]:
    return {
        "title": "Conveyor workcell",
        "summary": (
            "A small conveyor with a diverter, photoelectric eyes, a safety door and an emergency stop. "
            "Deterministic integer simulation intended for testing agent command semantics: revisions, "
            "command ids, interlocks, permits and receipts."
        ),
        "tags": [
            "conveyor",
            "lab automation",
            "workcell",
            "deterministic simulation",
            "safety interlock",
            "command semantics",
        ],
        "operating_notes": [
            "Advance the model with cap.world.step.v1; each tick is 1 ms of simulated time.",
            "Every mutation returns a receipt with a new revision and state hash.",
            "Opening the safety door or engaging the e-stop latches the workcell; reset after clearing interlocks.",
        ],
        "docs": ["MHS/sdk/docs/reference-endpoints.md"],
    }


def device_manifest(endpoint_id: str, *, test_profile: bool = False) -> dict[str, Any]:
    """The conveyor device manifest (validates against device.schema.json)."""

    caps = _capabilities(test_profile)
    return device(
        endpoint_id=endpoint_id,
        slug=DEVICE_SLUG,
        display_name="Deterministic conveyor workcell (simulated)",
        instance_id=INSTANCE_IDS["conveyor"],
        mode="simulated",
        model="conveyor-workcell-sim",
        resources=[
            resource(
                RESOURCE_ID,
                "world.sim",
                "Workcell world state",
                _state_schema(),
                _initial_state(),
                hash_exclusions=["/mono_ms"],
            )
        ],
        capabilities=caps,
        safety=_safety(test_profile),
        fidelity=exact_fidelity(
            "custom-integer",
            timestep_ms=1,
            gaps=[
                "No contact physics",
                "No sensor noise model",
                "Parts are points, not rigid bodies",
                "The safety door and e-stop are simulated, not a safety-rated channel",
            ],
        ),
        profile=_profile(),
        conformance_level="CL4",
        endpoint_name="conveyor",
        provenance_sources=["MHS/sdk/src/mhs/reference/conveyor.py"],
    )


def build(endpoint_id: str, *, test_profile: bool = False) -> EndpointSpec:
    """Build the conveyor endpoint specification (manifest + bridge)."""

    manifest = device_manifest(endpoint_id, test_profile=test_profile)
    bridge = ConveyorBridge(device_id=manifest["device_id"], test_profile=test_profile)
    return EndpointSpec(
        name="conveyor",
        endpoint_id=endpoint_id,
        profile="MHS-Sim",
        devices=[manifest],
        bridges={manifest["device_id"]: bridge},
        features=[
            "MHS.SAFETY.NOT_CERTIFIED",
            "deterministic-simulation",
            "mcp-projection-v1",
            "evidence-chain",
        ]
        + (["test-profile", "fault-injection"] if test_profile else []),
        notes="Reference deterministic conveyor workcell; test profile adds x-cap fault injection.",
        conformance_level="CL4",
    )
