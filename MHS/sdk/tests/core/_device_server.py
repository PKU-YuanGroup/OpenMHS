"""A tiny in-test MHS device, served over stdio.

Run by ``test_custom_device.py`` to exercise the server/client contract with a
device and bridge that are not part of the reference endpoints::

    python3 _device_server.py --stdio
"""

from __future__ import annotations

import copy
import sys
import time

from mhs.bridge.base import Bridge, make_mhs_error
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope


class TinyBridge(Bridge):
    bridge_id = "tests.tiny"

    def __init__(self) -> None:
        super().__init__(device_id="mhs://localhost/tests/tiny")
        self.state = {
            "tick": 0,
            "door": "closed",
            "gate": "main",
            "stopped": True,
            "latched": False,
            "mono_ms": 0,
        }

    # -- adapter surface ------------------------------------------------
    def read(self, resource_id: str, fields=None, ctx=None):
        self.ensure_open()
        if resource_id != "world":
            raise make_mhs_error("MHS.RESOURCE.UNKNOWN", f"no resource {resource_id!r}")
        state = copy.deepcopy(self.state)
        if fields:
            return {name: state.get(name) for name in fields if name in state}
        return state

    def call(self, capability_id: str, args=None, ctx=None):
        self.ensure_open()
        args = dict(args or {})
        if capability_id == "cap.world.step.v1":
            ticks = int(args.get("ticks", 0))
            self.state["tick"] += ticks
            self.state["mono_ms"] += ticks
            self.state["stopped"] = self.state["tick"] == 0
            return {"output": {"tick": self.state["tick"]}, "state": {"world": copy.deepcopy(self.state)}}
        if capability_id == "cap.device.configure.v1":  # mhs.resource.write (WP-04 4d)
            for key, value in args.items():
                if key not in self.state:
                    raise make_mhs_error("MHS.RESOURCE.FIELD_UNKNOWN", f"unknown field {key!r}")
                self.state[key] = value
            return {"applied": {key: copy.deepcopy(self.state[key]) for key in args}}
        if capability_id == "cap.world.state.v1":
            return {"output": copy.deepcopy(self.state)}
        if capability_id == "cap.motion.stop.v1":
            self.state["stopped"] = True
            self.state["gate"] = "main"
            return {"output": {"stopped": True}, "state": {"world": copy.deepcopy(self.state)}}
        if capability_id == "cap.test.set_door.v1":
            door = str(args.get("state"))
            if door not in ("open", "closed"):
                raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "state must be open or closed")
            self.state["door"] = door
            if door == "open":
                self.state["latched"] = True
                self.state["stopped"] = True
            return {"output": {"door": door}, "state": {"world": copy.deepcopy(self.state)}}
        if capability_id == "cap.actuation.valve.v1":
            gate = str(args.get("gate"))
            if gate not in ("main", "divert"):
                raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "gate must be main or divert")
            if self.state["latched"] or self.state["door"] != "closed":
                raise make_mhs_error("MHS.SAFETY.INTERLOCK_OPEN", "door/latch blocks the valve")
            self.state["gate"] = gate
            return {"output": {"gate": gate}, "state": {"world": copy.deepcopy(self.state)}}
        if capability_id == "cap.test.block.v1":
            time.sleep(float(args.get("ms", 300)) / 1000.0)
            return {"output": {"blocked_ms": int(args.get("ms", 300))},
                    "state": {"world": copy.deepcopy(self.state)}}
        if capability_id == "x-cap.test.long.v1":
            duration = int(args.get("ms", 500))
            slept = 0
            while slept < duration:
                if getattr(ctx, "cancel_event", None) is not None and ctx.cancel_event.is_set():
                    return {"output": {"cancelled": True}, "status": "cancelled",
                            "state": {"world": copy.deepcopy(self.state)}}
                time.sleep(0.005)
                slept += 5
            self.state["tick"] += 1
            return {"output": {"slept_ms": slept}, "state": {"world": copy.deepcopy(self.state)}}
        raise make_mhs_error("MHS.CAPABILITY.UNKNOWN", f"unknown capability {capability_id!r}")

    def write(self, resource_id, patch, ctx=None):
        self.ensure_open()
        if resource_id != "world":
            raise make_mhs_error("MHS.RESOURCE.UNKNOWN", f"no resource {resource_id!r}")
        for key, value in dict(patch or {}).items():
            self.state[key] = value
        return {"world": copy.deepcopy(self.state)}

    def snapshot(self, device_id=None):
        self.ensure_open()
        return {"world": copy.deepcopy(self.state)}

    def restore(self, snapshot):
        self.ensure_open()
        raw = snapshot
        if isinstance(raw, dict) and "state" in raw and isinstance(raw["state"], dict):
            raw = raw["state"]
        if isinstance(raw, dict) and "world" in raw and isinstance(raw["world"], dict):
            raw = raw["world"]
        if not isinstance(raw, dict):
            raise make_mhs_error("MHS.RESOURCE.STATE_INVALID", "snapshot must be an object")
        for key, default in (
            ("tick", 0), ("door", "closed"), ("gate", "main"),
            ("stopped", True), ("latched", False), ("mono_ms", 0),
        ):
            self.state[key] = raw.get(key, default)
        return {"world": copy.deepcopy(self.state)}

    def interlocks(self):
        return [
            {"id": "door_closed", "state": "closed" if self.state["door"] == "closed" else "open",
             "description": "Safety door closed"},
            {"id": "workcell_latched", "state": "open" if self.state["latched"] else "closed",
             "description": "Workcell latch clear"},
        ]

    def safety_status(self):
        return {
            "risk_class": "R1",
            "estop": {"engaged": self.state["latched"], "latching": True},
            "interlocks": self.interlocks(),
            "permits": [],
            "safe_state": {"description": "stopped", "achieved": self.state["stopped"] and self.state["gate"] == "main"},
        }

    def estop(self, reason="", ctx=None):
        self.state["latched"] = True
        self.state["stopped"] = True
        self.state["gate"] = "main"
        return {"estop": "engaged", "latched": True, "reason": reason}

    def reset(self, ctx=None):
        if self.state["door"] != "closed":
            raise make_mhs_error("MHS.SAFETY.INTERLOCK_OPEN", "close the door before reset")
        self.state["latched"] = False
        self.state["stopped"] = True
        self.state["gate"] = "main"
        return {"reset": True, "latched": False}


def build_server() -> MHSServer:
    bridge = TinyBridge()
    capabilities = [
        Capability(
            "cap.world.step.v1", "world", title="Advance the world",
            input_schema={"type": "object", "required": ["ticks"],
                          "properties": {"ticks": {"type": "integer", "minimum": 0, "maximum": 100}}},
            constraints={"max_duration_ms": 2000}, exclusive=True, determinism="exact",
        ),
        Capability(
            "cap.world.state.v1", "world", title="Read the world",
            input_schema={"type": "object", "properties": {}},
            exclusive=False, verb="read", determinism="exact",
        ),
        # mhs.resource.write: the configure class takes a patch of the
        # writable state_schema properties of "world" (WP-04 4d).
        Capability(
            "cap.device.configure.v1", "world", title="Write declared world fields",
            exclusive=True, determinism="exact", verb="write",
        ),
        Capability(
            "cap.motion.stop.v1", "world", title="Stop in the safe state",
            input_schema={"type": "object", "properties": {}},
            exclusive=False, determinism="exact",
        ),
        Capability(
            "cap.actuation.valve.v1", "world", title="Move the gate",
            input_schema={"type": "object", "required": ["gate"],
                          "properties": {"gate": {"type": "string", "enum": ["main", "divert"]}}},
            exclusive=True, requires_permit=True, constraints={"max_duration_ms": 1000},
        ),
        Capability(
            "cap.test.set_door.v1", "world", title="Set the test door",
            input_schema={"type": "object", "required": ["state"],
                          "properties": {"state": {"type": "string", "enum": ["open", "closed"]}}},
            exclusive=True,
        ),
        Capability(
            "cap.test.block.v1", "world", title="Slow exclusive action",
            input_schema={"type": "object", "properties": {"ms": {"type": "integer"}}},
            exclusive=True, constraints={"max_duration_ms": 2000},
        ),
        Capability(
            "x-cap.test.long.v1", "world", title="Long cancellable exclusive action",
            input_schema={"type": "object", "required": ["ms"],
                          "properties": {"ms": {"type": "integer", "minimum": 10, "maximum": 2000}}},
            exclusive=True,
            constraints={"max_duration_ms": 2000, "cancellable": True},
        ),
    ]
    safety = SafetyEnvelope(
        risk_class="R1",
        envelope={
            "cap.world.step.v1": {"ticks": {"min": 0, "max": 100, "reason": "bounded step"}},
            "x-cap.test.long.v1": {"ms": {"min": 10, "max": 2000}},
        },
        interlocks=[
            {"id": "door_closed", "description": "Safety door closed", "source": "simulated",
             "required_for": ["cap.actuation.valve.v1"]},
            # The latch itself reads open until mhs.safety.reset releases it, so
            # it gates motion but not recovery (SAFE-041: reset_exempt).
            {"id": "workcell_latched", "description": "Latch clear", "source": "simulated",
             "required_for": ["cap.actuation.valve.v1", "cap.world.step.v1", "x-cap.test.long.v1"],
             "reset_exempt": True},
        ],
        requires_permit=["cap.actuation.valve.v1"],
        estop={"kind": "software", "latching": True, "latency_ms": 50},
        safe_state={"description": "stopped with the gate in main", "achieved_by": ["cap.motion.stop.v1"]},
    )
    device = Device(
        "mhs://localhost/tests/tiny",
        "Tiny in-test device",
        mode="simulated",
        resources=[Resource(
            "world", "world.sim",
            state_schema={
                "type": "object",
                "properties": {
                    "tick": {"type": "integer", "minimum": 0},
                    "door": {"type": "string", "enum": ["open", "closed"]},
                    "gate": {"type": "string", "enum": ["main", "divert"]},
                    "stopped": {"type": "boolean"},
                    "latched": {"type": "boolean"},
                    "mono_ms": {"type": "integer", "minimum": 0},
                },
            },
            state=copy.deepcopy(bridge.state),
            hash_exclusions=["/mono_ms"],
        )],
        capabilities=capabilities,
        safety=safety,
        fidelity={
            "engine": "tests.tiny",
            "fidelity_level": "F0",
            "determinism": {"kind": "exact"},
            "timestep_ms": 1,
            "realtime_factor": 0,
            "reset": "full",
            "snapshot_restore": True,
            "gaps": ["synthetic test model"],
        },
        bridge=bridge,
        instance_id="01J8ZQ3V6Y7M2N4P6R8S0T2V4W",
    )
    return MHSServer(endpoint_id="mhs://localhost/tests", devices=[device],
                      features=["MHS.SAFETY.NOT_CERTIFIED", "test-device"],
                      log_ready=False)


def main() -> int:
    build_server().run_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
