"""OpenMHS driver for gh.robo-eval/roboeval: the LiftPotPosition manipulation environment.

DEVIATION FROM THE CARD: the card proposes the ``MujocoDriver`` family helper, but this upstream entry
symbol is not a raw MuJoCo model: it is a Gymnasium environment (``RoboEvalEnv``) that builds its Mojo/MuJoCo
world in ``__init__``, needs an ``ActionMode`` argument before it can exist, and is only meaningful as an
object with ``reset(seed, options)`` and ``step(action, fast)``.  A ``MujocoDriver`` would have to expose
``MjModel``/``MjData``/``mj_step`` on the fake, none of which are attributes of the card's entry class, and
G7 checks the fake against exactly that class.  This package therefore uses a direct ``Driver`` over
``roboeval.envs.lift_pot:LiftPotPosition`` with a package fake that has the same public methods; the
capabilities are still the card's ``cap.world.reset.v1`` and ``cap.world.step.v1``.

The device is simulated (R0): there is no hardware backend, no physical stop path and no operator-required
limit.  ``cap.world.step.v1`` forwards ``ticks`` environment control steps (``step`` in
``roboeval/roboeval_env.py``) and an optional action object with a ``values`` vector.  The fake backend is a
kinematic stand-in, so the fidelity contract is F0 (see ``fidelity`` below); the upstream environment itself
delegates physics to MuJoCo but was not installed or run here, and the clone is never imported by package code.

Every fact cites a line of the clone at commit 7199e5c4851bbf8eaf185d486735cbcb233f608a.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from mhs.driver import Driver, Fact, Field, action, read

try:  # the upstream environment requires numpy (pyproject.toml:15); a missing copy only weakens the action type
    import numpy as _numpy
except ImportError:  # pragma: no cover - the gate and the upstream install both provide numpy
    _numpy = None

ENV = "roboeval/roboeval_env.py"
LIFT_POT = "roboeval/envs/lift_pot.py"
OBSERVATION = "roboeval/utils/observation_config.py"


def _jsonable(value: Any) -> Any:
    """Turn numpy arrays and scalars into JSON values, recursively."""

    if hasattr(value, "tolist"):
        return _jsonable(value.tolist())
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _state_hash(observation: Any, tick: int) -> str:
    body = json.dumps({"observation": _jsonable(observation), "tick": tick}, sort_keys=True,
                      separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


class LiftPotPosition(Driver):
    """The LiftPotPosition environment served through the world reset/step capabilities."""

    device_id = "roboeval-lift-pot-position"
    device_kind = "world.sim"
    resource_id = "world"
    mode, risk = "simulated", "R0"
    native = "roboeval.envs.lift_pot:LiftPotPosition"
    backends = {"fake": ".fake:FakeLiftPotPosition"}
    display_name = "RoboEval LiftPotPosition (MuJoCo bimanual manipulation)"
    vendor, model = "RoboEval", "LiftPotPosition"
    tags = ["roboeval", "mujoco", "manipulation", "lift-pot", "simulation", "bimanual"]
    facts = [
        Fact("reset takes keyword-only seed and options and returns (observation, info)",
             source="upstream_code", ref=f"{ENV}:560-577"),
        Fact("step takes an optional action vector and fast flag and returns "
             "(observation, reward, terminated, truncated, info)",
             source="upstream_code", ref=f"{ENV}:603-616"),
        Fact("the physics timestep PHYSICS_DT is 0.002 s", source="upstream_code", ref=f"{ENV}:36"),
        Fact("the control frequency must be between 20 and 500 Hz",
             source="upstream_code", ref=f"{ENV}:33-34"),
        Fact("one control step is round(500/control_frequency) physics steps",
             source="upstream_code", ref=f"{ENV}:112-113"),
        Fact("the Mojo physics wrapper is created with timestep=PHYSICS_DT",
             source="upstream_code", ref=f"{ENV}:141"),
        Fact("a reset calls np.random.seed with the current episode seed",
             source="upstream_code", ref=f"{ENV}:558"),
        Fact("get_observation returns the enabled observation components: proprioception by default",
             source="upstream_code", ref=f"{ENV}:449-462"),
        Fact("the default ObservationConfig enables proprioception and no cameras",
             source="upstream_code", ref=f"{OBSERVATION}:53-54"),
        Fact("proprioception concatenates robot qpos and qvel and adds gripper and floating-base fields",
             source="upstream_code", ref=f"{ENV}:490-504"),
        Fact("get_info adds task_success as a float of the current success flag",
             source="upstream_code", ref=f"{ENV}:480-482"),
        Fact("LiftPotPosition clears and samples the workspace spawn boundary with min_distance 0.1 on reset",
             source="upstream_code", ref=f"{LIFT_POT}:125-132"),
        Fact("INITIAL_HEIGHT is 0.996 m and SUCCESS_HEIGHT is 0.1 m above it",
             source="upstream_code", ref=f"{LIFT_POT}:14-16"),
        Fact("the success rotation tolerance SUCCESS_ROT is 20 degrees",
             source="upstream_code", ref=f"{LIFT_POT}:15"),
        Fact("the base LiftPot reset places the pot at x=0.7, y=0.0 and z=INITIAL_HEIGHT",
             source="upstream_code", ref=f"{LIFT_POT}:45"),
        Fact("close closes the environment's renderers",
             source="upstream_code", ref=f"{ENV}:719-721"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the observation stays readable")
    fidelity = {
        "engine": "roboeval:LiftPotPosition",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the upstream reset(seed) calls np.random.seed with the episode seed (roboeval_env.py:558) "
                     "and the fake draws its placeholder observation from random.Random(seed); a seed repeats the "
                     "fake's state hashes, but the fake and upstream do not share a random stream or a physics "
                     "model",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a kinematic stand-in: it advances a step counter and a placeholder "
            "observation and integrates no rigid-body dynamics, contacts, actuators, sensors or noise; the "
            "upstream environment delegates physics to MuJoCo, which was not installed or run here",
            "no wall-clock pacing: realtime_factor 0 and ticks advance the lockstep counter only",
            "the physics timestep is 2 ms (PHYSICS_DT) and the control period is round(500/control_frequency) "
            "physics steps (20 to 500 Hz); the fake advances neither, and the control frequency is a "
            "constructor option rather than a fixed model parameter",
            "the observation is a placeholder: the real default observation concatenates the robot qpos and "
            "qvel plus gripper and floating-base fields (roboeval_env.py:490-504), and its array length depends "
            "on the BimanualPanda model and was not computed here",
            "the action object is forwarded as a values vector; the fake does not map it through an action "
            "mode or inverse kinematics",
            "snapshot and restore are not offered by the environment",
            "no run of, or comparison with, the upstream environment was made",
        ],
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tick = 0

    def setup(self) -> None:
        """Start a fresh episode so the first read has a defined observation and seed."""

        self._tick = 0
        self.native.reset()

    def teardown(self) -> None:
        close = getattr(self.native, "close", None)
        if callable(close):
            close()

    @read("observation", type="object",
          description="Current environment observation (proprioception by default)")
    def observation(self) -> dict[str, Any]:
        return _jsonable(self.native.get_observation())

    @read("tick", type="integer", unit="1", description="Control steps since the last reset")
    def tick(self) -> int:
        return self._tick

    @action(cap="cap.world.reset.v1",
            description="Reset the environment to a task start state and return the initial observation",
            input={
                "seed": Field("integer", unit="1",
                              description="Seed passed to reset(seed=...); omit it to use the environment's next seed"),
                "options": Field("object",
                                 description="Options dictionary forwarded to the environment's reset()"),
            })
    def reset_world(self, seed: int | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        observation, _info = self.native.reset(seed=seed, options=options)
        self._tick = 0
        return {"observation": _jsonable(observation), "seed": int(self.native.seed)}

    @action(cap="cap.world.step.v1",
            description="Advance the environment by a bounded number of control steps",
            input={
                "ticks": Field("integer", unit="1",
                               description="Control steps to advance; each is one environment step"),
                "action": Field("object",
                                description="Action object with an optional values vector; omit it for a "
                                            "physics-only step",
                                properties={
                                    "values": Field("array", items="number", unit="1", required=False,
                                                    description="Action vector forwarded to the environment"),
                                }),
            })
    def step(self, ticks: int = 1, action: Mapping[str, Any] | None = None) -> dict[str, Any]:
        observation: Any = None
        reward = 0.0
        terminated = False
        truncated = False
        vector = self._action_vector(action)
        for _ in range(ticks):
            observation, step_reward, step_terminated, step_truncated, _info = self.native.step(vector)
            reward += float(step_reward)
            terminated = terminated or bool(step_terminated)
            truncated = truncated or bool(step_truncated)
            self._tick += 1
            if terminated or truncated:
                break
        if observation is None:
            observation = self.native.get_observation()
        observation = _jsonable(observation)
        return {
            "observation": observation,
            "tick": self._tick,
            "state_hash": _state_hash(observation, self._tick),
            "reward": reward,
            "terminated": terminated,
            "truncated": truncated,
        }

    @staticmethod
    def _action_vector(action: Mapping[str, Any] | None) -> Any:
        if action is None:
            return None
        values = action.get("values") if isinstance(action, Mapping) else action
        if values is None:
            return None
        values = [float(value) for value in values]
        if _numpy is None:  # pragma: no cover - numpy is an upstream requirement
            return values
        return _numpy.asarray(values, dtype=_numpy.float32)
