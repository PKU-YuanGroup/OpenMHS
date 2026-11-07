"""OpenMHS driver for gh.huggingface/lerobot-libero: the LIBERO coffee-table manipulation environment.

DEVIATION FROM THE CARD: the card proposes the ``MujocoDriver`` family helper and lists the five LIBERO problem
classes as entry symbols, but the card has no ``models`` entry and the entry classes are not raw MJCF models: they
parse a BDDL task file and build a robosuite/MuJoCo scene at construction time (``bddl_base_domain.py:42-160``,
``:297``).  A ``MujocoDriver`` serves one MJCF file through ``model_path``/``mj_step``; it cannot carry a task suite,
a BDDL file or the environment's ``step(action)`` interface, and there is no model file in the card.  This package is
therefore a direct ``Driver`` over the first card entry symbol,
``libero.libero.envs.problems.libero_coffee_table_manipulation:Libero_Coffee_Table_Manipulation``, with a package fake
whose methods mirror that class and its base.  It still binds the card's ``cap.world.reset.v1`` and
``cap.world.step.v1``.

``cap.world.reset.v1`` calls ``seed(seed)`` then ``reset()`` (the README's order, ``README.md:125-126``) and returns
the observation dictionary and the seed.  ``cap.world.step.v1`` calls ``step(action)`` once per tick with the
``values`` vector of the action object; the upstream step returns ``(obs, reward, done, info)`` and replaces
``done`` with its success predicate (``bddl_base_domain.py:800-809``).  The driver forwards exactly those values.

The device is simulated (R0): there is no hardware backend, no physical stop path and no operator-required limit.
MuJoCo, robosuite and bddl are not installed where the gate runs (checked with importlib.util.find_spec), the
upstream package was never installed or run, and the clone was never imported.  The fake backend (``fake.py``) is a
physics-free F0 stand-in with placeholder arrays; the real observation also carries the camera images the constructor
enables by default (``bddl_base_domain.py:51`` and ``:67-69``), which this package does not serve (see RESULT.json
notes).  Every Fact cites a line of the clone at commit 14fd6f022ff6647defc24e73563b95aa36670f43.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from mhs.driver import Driver, DriverFailed, Fact, Field, action, read

ENTRY = "libero/libero/envs/problems/libero_coffee_table_manipulation.py"
BASE = "libero/libero/envs/bddl_base_domain.py"


def _jsonable(value: Any) -> Any:
    """Turn numpy-like arrays, tuples and mappings into JSON values, recursively."""

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


class LiberoCoffeeTable(Driver):
    """The LIBERO coffee-table environment served through the world reset/step capabilities."""

    device_id = "libero-coffee-table"
    device_kind = "world.sim"
    resource_id = "world"
    mode, risk = "simulated", "R0"
    native = ("libero.libero.envs.problems.libero_coffee_table_manipulation:"
              "Libero_Coffee_Table_Manipulation")
    backends = {"fake": ".fake:FakeLiberoCoffeeTableManipulation"}
    display_name = "LIBERO coffee-table manipulation environment"
    vendor, model = "Hugging Face", "LIBERO Coffee Table Manipulation"
    tags = ["libero", "robosuite", "mujoco", "manipulation", "simulation", "benchmark"]
    seed = 0
    facts = [
        Fact("LIBERO is designed for studying knowledge transfer in multitask and lifelong robot learning",
             source="vendor_doc", ref="README.md:26"),
        Fact("LIBERO provides 130 tasks grouped into four task suites: LIBERO-Spatial, LIBERO-Object, LIBERO-Goal "
             "and LIBERO-100", source="vendor_doc", ref="README.md:32"),
        Fact("The README creates OffScreenRenderEnv with a 128x128 camera, calls env.seed(0) and then env.reset()",
             source="vendor_doc", ref="README.md:119-126"),
        Fact("The README steps the environment with a seven-element zero action and unpacks obs, reward, done, info",
             source="vendor_doc", ref="README.md:131-133"),
        Fact("The README says only a sparse reward is supported: +1 when the task is finished", source="vendor_doc",
             ref="README.md:136"),
        Fact("The package is published as libero and requires Python >=3.8", source="upstream_code",
             ref="pyproject.toml:6-14"),
        Fact("The runtime pins robosuite==1.4.0 and bddl==1.0.1", source="upstream_code",
             ref="pyproject.toml:23-24"),
        Fact("The entry class is registered with @register_problem and subclasses BDDLBaseDomain",
             source="upstream_code", ref=f"{ENTRY}:11-12"),
        Fact("BDDLBaseDomain subclasses robosuite's SingleArmEnv", source="upstream_code", ref=f"{BASE}:37"),
        Fact("The constructor requires bddl_file_name and robots and parses the BDDL problem from that file",
             source="upstream_code", ref=f"{BASE}:42-45"),
        Fact("The constructor parses the BDDL problem file into parsed_problem", source="upstream_code",
             ref=f"{BASE}:124-125"),
        Fact("seed calls np.random.seed(seed)", source="upstream_code", ref=f"{BASE}:162-163"),
        Fact("reward is 0.0, or 1.0 when _check_success returns true", source="upstream_code",
             ref=f"{BASE}:179-189"),
        Fact("step calls the robosuite step and then replaces done with _check_success", source="upstream_code",
             ref=f"{BASE}:800-809"),
        Fact("The coffee-table success check ANDs every predicate of the parsed goal_state", source="upstream_code",
             ref=f"{ENTRY}:133-141"),
        Fact("The base constructor defaults to camera observations (use_camera_obs=True)", source="upstream_code",
             ref=f"{BASE}:51"),
        Fact("The default camera is agentview at 256x256 pixels", source="upstream_code", ref=f"{BASE}:67-69"),
        Fact("get_robot_state_vector concatenates robot0_gripper_qpos, robot0_eef_pos and robot0_eef_quat",
             source="upstream_code", ref=f"{BASE}:826-829"),
        Fact("language_instruction returns the parsed problem's language string", source="upstream_code",
             ref=f"{BASE}:840-842"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch, and the last observation stays readable")
    fidelity = {
        "engine": "libero:coffee_table_manipulation",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the upstream seed calls np.random.seed(seed) (bddl_base_domain.py:162-163) and the placement "
                     "samplers draw from numpy's generator; the fake reseeds Python's random.Random, so a seed "
                     "repeats the fake's state hashes but the fake and upstream do not share a random stream or a "
                     "physics model",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a physics-free stand-in: it keeps three end-effector coordinates and a tick count, "
            "moves them by a placeholder gain, and integrates no rigid-body dynamics, contacts, actuators, "
            "sensors, cameras or noise; the upstream environment builds a robosuite/MuJoCo world",
            "the observation is a placeholder dictionary with the three robot keys the clone's "
            "get_robot_state_vector names (bddl_base_domain.py:826-829); the real observation also carries object "
            "observations and the agentview/robot0_eye_in_hand camera images that the constructor enables by "
            "default (bddl_base_domain.py:51 and :67-69), and its array lengths depend on the BDDL task and the "
            "camera configuration",
            "there is no fixed timestep in the clone: control_freq is a constructor option with default 20 "
            "(bddl_base_domain.py:63) and the physics step comes from the robosuite model, so timestep_ms is 0 "
            "and ticks count control steps, not physics steps",
            "the action vector's shape is a constructor option (the wrapper's default controller is OSC_POSE, "
            "env_wrapper.py:17); the fake accepts any non-empty numeric vector and the README example uses seven "
            "zeros (README.md:131)",
            "the BDDL file selects the objects, placements and goal predicates; the fake parses no BDDL file and "
            "never reports success (done is always false and reward is always 0.0)",
            "snapshot and restore are not offered by this package",
            "MuJoCo, robosuite and bddl were not installed and the upstream environment was never run, so no "
            "trajectory or observation of this package was compared with it",
            "no physical device is modelled and nothing was validated against hardware",
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

        self.native.seed(self._seed)
        self._store_observation(self.native.reset())
        self._tick = 0
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
          description="Last observation returned by the upstream environment's reset or step")
    def observation(self) -> dict[str, Any]:
        return self._observation_value

    @read("tick", type="integer", unit="1", description="Control steps applied since the last reset")
    def tick(self) -> int:
        return self._tick

    @read("seed", type="integer", unit="1", description="Seed supplied to the last reset")
    def seed_value(self) -> int:
        return self._seed

    @read("reward", type="number", unit="1", description="Reward of the last step (summed over its ticks)")
    def reward(self) -> float:
        return self._reward

    @read("terminated", type="boolean", description="Whether the last step reported the task as done")
    def terminated(self) -> bool:
        return self._terminated

    @action(cap="cap.world.reset.v1",
            description="Seed the environment and reset it to a fresh task start state",
            input={
                "seed": Field("integer", unit="1",
                              description="Seed passed to the environment's seed(); omit it to use the driver seed"),
                "options": Field("object",
                                 description="Accepted for the class contract; the upstream reset takes no options"),
            })
    def reset_world(self, seed: int | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        del options
        applied = self._seed if seed is None else int(seed)
        self.native.seed(applied)
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
                               description="Control steps to advance; the action is applied at every tick"),
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
            return [float(value) for value in values]
        except (TypeError, ValueError) as exc:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "action.values must be a non-empty numeric array") from exc
