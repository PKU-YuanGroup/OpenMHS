"""Fixtures for the REG-002 canonical-binding contract tests.

The documents deliberately copy the *shape* of the MHS-006 §4.1 normative
example (``enum_map``, ``result.map``, ``constants``, ``units``, ``clamp``,
ordered ``errors[]``).  ``NORMATIVE_EXAMPLE`` is the published example verbatim
except for the document wrapper; ``LIFT_BINDINGS`` binds the same primitives to
the local :class:`FakeLift` so the mapping can actually be executed.
"""

from __future__ import annotations

import time
from typing import Any


class FakeLift:
    """Tiny native object with precise symbols used by the contract tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.target = 0
        self.joints: list[float] = []

    # -- native symbols ----------------------------------------------------
    def step(self, action: int, expected_revision: str | None = None) -> dict[str, Any]:
        self.calls.append(("step", action))
        if expected_revision != "ignore":
            raise AssertionError("expected_revision constant was not injected")
        if action < 0:
            raise AssertionError("lift is not ready")
        return {
            "observation": [action, action + 1],
            "reward": 1.0,
            "terminated": False,
            "truncated": False,
        }

    def set_target(self, target: int) -> dict[str, Any]:
        self.calls.append(("set_target", target))
        if target == -1:
            raise AssertionError("precondition unmet: lift is not homed")
        if target == -2:
            raise RuntimeError("device busy: actuator is moving")
        if target == -3:
            raise OSError("vendor SDK returned an unknown status")
        self.target = target
        return {"target": target}

    def set_joints(self, joints: list[float]) -> dict[str, Any]:
        self.calls.append(("set_joints", list(joints)))
        self.joints = list(joints)
        return {"joints": list(joints)}

    def slow(self, seconds: float) -> dict[str, Any]:
        self.calls.append(("slow", seconds))
        time.sleep(float(seconds))
        return {"slept": True}


#: The normative MHS-006 §4.1 example, unchanged in shape.
NORMATIVE_EXAMPLE: dict[str, Any] = {
    "mhs_bindings": "1.0",
    "adapter_id": "org.example.robosuite-lift",
    "bindings": [
        {
            "device_id": "mhs://localhost:7401/robosuite/Lift",
            "capability_id": "cap.world.step.v1",
            "resource": "world",
            "binding": {
                "bridge": "gymnasium",
                "kind": "declarative",
                "native": "gymnasium.Env.step",
                "args": {
                    "action": {
                        "from": "input.action",
                        "type": "integer",
                        "enum_map": {"left": 0, "right": 1},
                    }
                },
                "result": {
                    "map": {
                        "observation": "output.observation",
                        "reward": "output.reward",
                        "terminated": "output.terminated",
                        "truncated": "output.truncated",
                    }
                },
                "constants": {"expected_revision": "ignore"},
                "units": {"input.action": {"from": "1", "to": "1", "factor": 1}},
                "clamp": {"input.action": {"min": 0, "max": 1}},
                "errors": [
                    {
                        "native": "^AssertionError$",
                        "mhs_code": "MHS.DEVICE.PRECONDITION_UNMET",
                        "retryable": False,
                    }
                ],
                "concurrency": "exclusive",
                "timeout_ms": 5000,
            },
        }
    ],
}


#: Executable bindings for :class:`FakeLift` using the same canonical primitives.
LIFT_BINDINGS: dict[str, Any] = {
    "mhs_bindings": "1.0",
    "adapter_id": "org.example.fake-lift",
    "bindings": [
        {
            "device_id": "mhs://localhost:7400/lab/lift",
            "capability_id": "cap.world.step.v1",
            "resource": "world",
            "binding": {
                "bridge": "python-object",
                "kind": "declarative",
                "native": "step",
                "args": {
                    "action": {
                        "from": "input.action",
                        "type": "integer",
                        "enum_map": {"left": 0, "right": 1},
                    }
                },
                "result": {
                    "map": {
                        "observation": "output.observation",
                        "reward": "output.reward",
                        "terminated": "output.terminated",
                        "truncated": "output.truncated",
                    }
                },
                "constants": {"expected_revision": "ignore"},
                "units": {"input.action": {"from": "1", "to": "1", "factor": 1}},
                "clamp": {"input.action": {"min": 0, "max": 1}},
                "errors": [
                    {
                        "native": "^AssertionError$",
                        "mhs_code": "MHS.DEVICE.PRECONDITION_UNMET",
                        "retryable": False,
                    }
                ],
                "concurrency": "exclusive",
                "timeout_ms": 5000,
            },
        },
        {
            "device_id": "mhs://localhost:7400/lab/lift",
            "capability_id": "cap.motion.set-target.v1",
            "resource": "lift",
            "binding": {
                "bridge": "python-object",
                "kind": "declarative",
                "native": "set_target",
                "args": {"target": {"from": "input.target", "type": "integer"}},
                "result": {"map": {"target": "output.target"}},
                "errors": [
                    {
                        "native": "^AssertionError$",
                        "mhs_code": "MHS.DEVICE.PRECONDITION_UNMET",
                        "retryable": False,
                    },
                    {
                        "native": "busy",
                        "mhs_code": "MHS.DEVICE.BUSY",
                        "retryable": True,
                    },
                ],
                "concurrency": "exclusive",
                "timeout_ms": 2000,
            },
        },
        {
            "device_id": "mhs://localhost:7400/lab/lift",
            "capability_id": "cap.motion.joints.v1",
            "resource": "lift",
            "binding": {
                "bridge": "python-object",
                "kind": "declarative",
                "native": "set_joints",
                "args": {
                    "joints": {
                        "from": "input.joints[*]",
                        "type": "number",
                        "unit": {"from": "deg", "to": "rad"},
                    }
                },
                "result": {"map": {"joints": "output.joints"}},
                "clamp": {
                    "input.joints[*]": {
                        "min": -3.141592653589793,
                        "max": 3.141592653589793,
                        "envelope": {"min": -6.283185307179586, "max": 6.283185307179586},
                    }
                },
                "concurrency": "shared",
                "timeout_ms": 2000,
            },
        },
        {
            "device_id": "mhs://localhost:7400/lab/lift",
            "capability_id": "cap.test.slow.v1",
            "resource": "lift",
            "binding": {
                "bridge": "python-object",
                "kind": "declarative",
                "native": "slow",
                "args": {"seconds": {"from": "input.seconds", "type": "number"}},
                "result": {"map": {"slept": "output.slept"}},
                "concurrency": "shared",
                "timeout_ms": 50,
            },
        },
    ],
}

#: Binding target for :class:`FakeLift`.
LIFT_TARGET = "tests.remediation.bridge.support:FakeLift"
