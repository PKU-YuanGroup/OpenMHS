"""OpenMHS driver for gh.stanfordvl/lasersuite: the Surreal Robotics Suite DoorOpen environment.

DEVIATION FROM THE CARD: the card proposes the ``MujocoDriver`` family helper and lists the robosuite environment
classes as entry symbols.  A ``MujocoDriver`` serves one MJCF file through ``model_path`` and ``mj_step``; the entry
class ``DoorOpen`` is an environment that builds a MuJoCo scene from a table arena, a door object and a robot at
construction time (``robosuite/environments/door_open.py:131-142``) and exposes the environment interface
``reset()``/``step(action)``/``close()`` (``robosuite/environments/base.py:137-142``, ``:180-201``, ``:344``).  The
three card models are the robot MJCF documents that the environment embeds, not standalone scenes.  This package is
therefore a direct ``Driver`` over the first card entry symbol,
``robosuite.environments.door_open:DoorOpen``, with a package fake.  It binds ``cap.world.reset.v1`` and
``cap.world.step.v1``.

``cap.world.reset.v1`` calls the environment's ``reset()`` and returns the observation dictionary plus the recorded
seed.  ``cap.world.step.v1`` calls ``step(action)`` once per tick with the ``values`` vector and forwards the
environment's ``(observation, reward, done, info)`` result.  ``done`` is reported as ``terminated``.

The device is simulated (R0): there is no hardware backend and no physical robot is driven.  MuJoCo, mujoco-py and
robosuite are not installed where the acceptance gate runs, the upstream package was never installed or run, and the
clone was never imported.  The fake backend (``fake.py``) is a physics-free stand-in whose numbers are placeholders;
the fidelity ``gaps`` below state every difference.  This package is model-authored and unreviewed: it is checked on
the fake backend only, and no hardware run is claimed.  Every Fact cites a line of the clone at commit
8b78c3d202f2a4b8712c5f228feaf5fae61f16e9.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any

from mhs.driver import Driver, DriverFailed, Fact, Field, action, read

ENV = "robosuite/environments/door_open.py"
BASE = "robosuite/environments/base.py"
ROBOT_ENV = "robosuite/environments/robot_env.py"
README = "README.md"
SETUP = "setup.py"


def _jsonable(value: Any) -> Any:
    """Turn array-like values, tuples and mappings into JSON values, recursively."""

    if hasattr(value, "tolist"):
        return _jsonable(value.tolist())
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    return str(value)


def _state_hash(observation: Any, tick: int, reward: float, terminated: bool) -> str:
    body = json.dumps({"observation": observation, "tick": tick, "reward": reward, "terminated": terminated},
                      sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


class DoorOpen(Driver):
    """The robosuite DoorOpen environment served through the world reset/step capabilities."""

    device_id = "robosuite-door-open"
    device_kind = "world.sim"
    resource_id = "world"
    mode, risk = "simulated", "R0"
    native = "robosuite.environments.door_open:DoorOpen"
    backends = {"fake": ".fake:FakeDoorOpen"}
    display_name = "Surreal Robotics Suite DoorOpen environment"
    vendor, model = "Stanford Vision and Learning Lab", "Surreal Robotics Suite DoorOpen"
    tags = ["door-open", "manipulation", "mujoco", "robosuite", "simulation", "robot"]
    seed = 0
    facts = [
        Fact("The entry class DoorOpen subclasses RobotEnv", source="upstream_code", ref=f"{ENV}:19"),
        Fact("RobotEnv subclasses MujocoEnv", source="upstream_code", ref=f"{ROBOT_ENV}:8"),
        Fact("The project describes itself as a simulation benchmark powered by the MuJoCo physics engine",
             source="vendor_doc", ref=f"{README}:11"),
        Fact("The package install requires numpy, scipy and mujoco-py==2.0.2.9", source="upstream_code",
             ref=f"{SETUP}:19-22"),
        Fact("The environment reset method calls _reset_internal, forwards the simulation and returns "
             "_get_observation()", source="upstream_code", ref=f"{BASE}:137-142"),
        Fact("The environment step method advances the simulation, collects the next observation and returns "
             "(next_state, reward, done, info)", source="upstream_code", ref=f"{BASE}:180-201"),
        Fact("The environment close method exists on the environment base class", source="upstream_code",
             ref=f"{BASE}:344"),
        Fact("The DoorOpen constructor default control_freq is 25 and its default horizon is 250",
             source="upstream_code", ref=f"{ENV}:43-44"),
        Fact("The DoorOpen constructor default initialization_noise is 0.02", source="upstream_code",
             ref=f"{ENV}:29"),
        Fact("The DoorOpen constructor defaults enable camera observations and name the agentview camera",
             source="upstream_code", ref=f"{ENV}:32-46"),
        Fact("The camera observation default is 256 pixels high and 256 pixels wide", source="upstream_code",
             ref=f"{ENV}:47-48"),
        Fact("The observation dictionary carries robot state and, when camera observations are enabled, one image "
             "per camera", source="upstream_code", ref=f"{ROBOT_ENV}:247-273"),
        Fact("DoorOpen builds a TableArena, a DoorObject and a DoorTask from the robot models",
             source="upstream_code", ref=f"{ENV}:131-142"),
        Fact("The card's baxter model is an MJCF document whose root element is '<mujoco model=\"baxter\">'",
             source="upstream_code", ref="robosuite/models/assets/robots/baxter/robot.xml:1"),
        Fact("The card's panda model is an MJCF document whose root element is '<mujoco model=\"panda\">'",
             source="upstream_code", ref="robosuite/models/assets/robots/panda/robot.xml:1"),
        Fact("The card's sawyer model is an MJCF document whose root element is '<mujoco model=\"sawyer\">'",
             source="upstream_code", ref="robosuite/models/assets/robots/sawyer/robot.xml:1"),
        Fact("The panda robot wrapper loads robots/panda/robot.xml as its model", source="upstream_code",
             ref="robosuite/models/robots/panda_robot.py:15"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch, and the last observation stays readable")
    fidelity = {
        "engine": "robosuite:DoorOpen",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "the upstream reset applies initialization_noise by default (door_open.py:29) and the "
                     "constructor exposes no seed; the package's fake is deterministic but makes no replay claim "
                     "for the upstream environment",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a physics-free stand-in: it keeps a short placeholder state, moves it toward the "
            "action values and integrates no rigid-body dynamics, contacts, actuators, sensors, cameras or noise; "
            "the upstream environment builds a robosuite/MuJoCo model",
            "the real observation carries the robot state and the agentview camera image (robot_env.py:247-273); "
            "the fake returns a small placeholder dictionary without images or depth maps",
            "the action vector is selected by controller_configs, a constructor option (door_open.py:21), and "
            "the clone states no controller action bound; the fake accepts any non-empty numeric vector and "
            "invents no limit",
            "the control step length is a constructor option (control_freq defaults to 25 at door_open.py:43), so "
            "timestep_ms is 0 and a tick counts one environment step, not a stated physical duration",
            "the fake has no seed input and the upstream environment exposes no seed method: a seed is recorded "
            "for the class contract but does not select a trajectory",
            "only the first card entry symbol, DoorOpen, is served; Lift and the three NutAssembly variants are "
            "not exposed",
            "MuJoCo, mujoco-py and robosuite were not installed and the upstream environment was never run, so no "
            "trajectory or observation of this package was compared with it",
            "no physical robot is modelled and nothing was validated against hardware",
        ],
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tick = 0
        self._episode = 0
        self._seed = int(type(self).seed)
        self._observation_value: dict[str, Any] = {}
        self._reward = 0.0
        self._terminated = False

    def setup(self) -> None:
        """Start a fresh episode so the first read has a defined observation."""

        self._store_observation(self.native.reset())
        self._tick = 0
        self._episode = 0
        self._reward = 0.0
        self._terminated = False

    def teardown(self) -> None:
        close = getattr(self.native, "close", None)
        if callable(close):
            close()

    def _store_observation(self, observation: Any) -> None:
        value = _jsonable(observation)
        self._observation_value = value if isinstance(value, dict) else {"value": value}

    @read("observation", type="object",
          description="Last observation returned by the environment's reset or step")
    def observation(self) -> dict[str, Any]:
        return self._observation_value

    @read("tick", type="integer", unit="1", description="Environment steps applied since the last reset")
    def tick(self) -> int:
        return self._tick

    @read("seed", type="integer", unit="1", description="Seed recorded for the last reset")
    def seed_value(self) -> int:
        return self._seed

    @read("reward", type="number", unit="1", description="Reward of the last step (summed over its ticks)")
    def reward(self) -> float:
        return self._reward

    @read("terminated", type="boolean", description="Whether the last step reported the task as done")
    def terminated(self) -> bool:
        return self._terminated

    @action(cap="cap.world.reset.v1",
            description="Reset the environment to a fresh task start state",
            input={
                "seed": Field("integer", unit="1",
                              description="Seed recorded for this reset; the upstream reset exposes no seed"),
                "options": Field("object",
                                 description="Accepted for the class contract; the upstream reset takes no options"),
            })
    def reset_world(self, seed: int | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        del options
        applied = self._seed if seed is None else int(seed)
        self._store_observation(self.native.reset())
        self._seed = applied
        self._tick = 0
        self._episode += 1
        self._reward = 0.0
        self._terminated = False
        return {"observation": self._observation_value, "seed": applied}

    @action(cap="cap.world.step.v1",
            description="Apply one action vector per tick to the environment's step()",
            input={
                "ticks": Field("integer", unit="1",
                               description="Environment steps to advance; the action is applied at every tick"),
                "action": Field("object", description="The action vector passed to the environment's step()",
                                properties={
                                    "values": Field("array", items=Field("number", unit="1"),
                                                    description="Numeric action vector of the configured controller"),
                                }),
            })
    def step(self, ticks: int, action: Mapping[str, Any]) -> dict[str, Any]:
        values = self._action_values(action)
        total = 0.0
        terminated = False
        observation: Any = self._observation_value
        for _ in range(int(ticks)):
            observation, step_reward, done, _info = self.native.step(values)
            total += float(step_reward)
            self._tick += 1
            terminated = bool(done)
            if terminated:
                break
        self._store_observation(observation)
        self._reward = total
        self._terminated = terminated
        return {
            "observation": self._observation_value,
            "tick": self._tick,
            "state_hash": _state_hash(self._observation_value, self._tick, self._reward, self._terminated),
            "reward": self._reward,
            "terminated": self._terminated,
            "truncated": False,
        }

    @staticmethod
    def _action_values(action: Mapping[str, Any]) -> list[float]:
        values = action.get("values") if isinstance(action, Mapping) else None
        if not isinstance(values, (list, tuple)) or not values:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "action.values must be a non-empty numeric array")
        try:
            numbers = [float(value) for value in values]
        except (TypeError, ValueError) as exc:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "action.values must be a non-empty numeric array") from exc
        if not all(math.isfinite(value) for value in numbers):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "action.values must be finite numbers")
        return numbers
