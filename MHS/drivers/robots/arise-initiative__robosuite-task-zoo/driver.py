"""OpenMHS driver for gh.arise-initiative/robosuite-task-zoo: the HammerPlace robosuite environment.

DEVIATION FROM THE CARD: the card proposes the ``MujocoDriver`` family helper and lists five robosuite
environment classes as entry symbols, but it lists no model: the entry classes are not raw MJCF models.
``HammerPlaceEnv`` subclasses robosuite's ``SingleArmEnv`` and builds its MuJoCo scene, objects, placement
samplers and observables in its constructor and ``_load_model`` (hammer_place.py:19, :138-303).  A
``MujocoDriver`` serves one MJCF file through ``model_path``/``mj_step`` and cannot carry the environment's
``reset()``/``step(action)`` interface or the absent model.  This package is therefore a direct ``Driver`` over
the card's first entry symbol, ``robosuite_task_zoo.environments.manipulation.hammer_place:HammerPlaceEnv``, with
a package fake whose methods mirror that class and its robosuite base.  It still binds the card's
``cap.world.reset.v1`` and ``cap.world.step.v1``.  The other four entry symbols are real classes of the clone but
are not served (one device per package).

``cap.world.reset.v1`` calls ``reset()`` and returns the observation dictionary and the recorded seed.  The
robosuite reset takes no seed argument and the clone exposes no seed method, so the MHS seed is recorded for the
receipt and does not steer the upstream reset; the placement sampler draws from numpy's process-wide generator
(hammer_place.py:443-456).  ``cap.world.step.v1`` calls ``step(action)`` once per tick with the ``values`` vector
of the action object; the upstream step returns ``(obs, reward, done, info)`` and replaces ``done`` with its success
predicate (hammer_place.py:489-499).  The driver forwards exactly those values and never invents a reward.

The device is simulated (R1: the world advances a simulated robot arm; MHS/spec/04-safety.md lists simulation
stepping as R1).  There is no hardware backend, no physical stop path and no operator-required limit.  robosuite,
mujoco-py, numpy, numba and scipy are not installed where the gate runs, the upstream package was never installed
or run, and the clone was never imported.  The ``fake`` backend (fake.py) is a physics-free F0 stand-in with
placeholder arrays; the real observation also carries the camera images the constructor enables by default
(hammer_place.py:28, :43-45), which this package does not serve (see RESULT.json notes).  Every Fact cites a line
of the clone at commit 74eab7f88214c21ca1ae8617c2b2f8d19718a9ed.  This package is model-authored and unreviewed:
it is checked on the fake backend only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, action, estop, read, reset

ENTRY = "robosuite_task_zoo/environments/manipulation/hammer_place.py"
KITCHEN = "robosuite_task_zoo/environments/manipulation/kitchen.py"
MULTITASK = "robosuite_task_zoo/environments/manipulation/multitask_kitchen.py"
TOOL_USE = "robosuite_task_zoo/environments/manipulation/tool_use.py"


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


class HammerPlace(Driver):
    """The HammerPlace environment served through the world reset/step capabilities."""

    device_id = "robosuite-hammer-place"
    device_kind = "world.sim"
    resource_id = "world"
    mode, risk = "simulated", "R1"
    native = "robosuite_task_zoo.environments.manipulation.hammer_place:HammerPlaceEnv"
    backends = {"fake": ".fake:FakeHammerPlaceEnv"}
    display_name = "robosuite Task Zoo HammerPlace environment"
    vendor, model = "ARISE-Initiative", "HammerPlaceEnv"
    tags = ["robosuite", "mujoco", "manipulation", "hammer", "cabinet", "simulation", "benchmark"]
    seed = 0
    facts = [
        Fact("The repository hosts a collection of robosuite tasks designed by community users and is intended to "
             "standardize experimental validation of simulated tasks", source="vendor_doc", ref="README.md:3-6"),
        Fact("Using the repository requires installing robosuite first, and the clone is then installed with pip "
             "install -e .", source="vendor_doc", ref="README.md:8-13"),
        Fact("The environments are based on robosuite and refer to the robosuite documentation for how to create an "
             "environment", source="vendor_doc", ref="environments.md:3-5"),
        Fact("The HammerPlace task is a single-arm tabletop domain in which the operator places a hammer into the "
             "cabinet and closes the cabinet", source="vendor_doc", ref="environments.md:28-31"),
        Fact("The documented task action space is OSC_POSITION (3) plus Gripper (1)", source="vendor_doc",
             ref="environments.md:39"),
        Fact("The documented HammerPlace observations are workspace images, eye-in-hand images and proprioception",
             source="vendor_doc", ref="environments.md:40"),
        Fact("The hammer_place module imports robosuite's SingleArmEnv as the base environment", source="upstream_code",
             ref=f"{ENTRY}:4"),
        Fact("HammerPlaceEnv is defined as a single-arm robosuite environment", source="upstream_code",
             ref=f"{ENTRY}:19"),
        Fact("The HammerPlaceEnv constructor takes robots, an optional controller_configs, control_freq 20, horizon "
             "1000 and camera defaults use_camera_obs=True, use_object_obs=True, camera_names agentview, "
             "camera_heights 256 and camera_widths 256", source="upstream_code", ref=f"{ENTRY}:20-48"),
        Fact("The constructor forwards robots, controller_configs, control_freq, horizon, camera options and the rest "
             "to SingleArmEnv", source="upstream_code", ref=f"{ENTRY}:76-98"),
        Fact("_load_model builds the TableArena, the HammerObject named hammer and the CabinetObject, registers them "
             "with the ManipulationTask and stores hammer and CabinetObject in self.objects", source="upstream_code",
             ref=f"{ENTRY}:138-303"),
        Fact("The placement sampler draws the hammer pose from x_range [0.10, 0.18] and y_range [-0.20, -0.13] on "
             "the table during a reset that is not deterministic", source="upstream_code", ref=f"{ENTRY}:443-456"),
        Fact("The success predicate is true when the hammer is inside the drawer (1.0 > z > 0.94 and y > 0.22) and "
             "the cabinet is closed (qpos > -0.01)", source="upstream_code", ref=f"{ENTRY}:463-475"),
        Fact("The sparse reward is 0.0, or 1.0 when _check_success is true, scaled by reward_scale",
             source="upstream_code", ref=f"{ENTRY}:100-136"),
        Fact("HammerPlaceEnv.step maps a four-element action to action[:3] plus the gripper, calls the robosuite "
             "parent step and returns obs, reward, done and info", source="upstream_code", ref=f"{ENTRY}:489-499"),
        Fact("step replaces the parent's done with the environment's _check_success result", source="upstream_code",
             ref=f"{ENTRY}:495-499"),
        Fact("The custom observables include robot0_joint_pos (activated), the object pose/relative-pose sensors, "
             "robot0_contact and robot0_eef_force_norm", source="upstream_code", ref=f"{ENTRY}:323-395"),
        Fact("get_state_vector reads the observation keys robot0_gripper_qpos, robot0_eef_pos and robot0_eef_quat",
             source="upstream_code", ref=f"{ENTRY}:530-533"),
        Fact("The clone's demo creates the environment, calls env.reset(), reads env.action_spec and unpacks "
             "obs, reward, done, _ from env.step(action)", source="upstream_code", ref="demo.py:6-24"),
        Fact("The clone's example creates MultitaskKitchenDomain with the OSC_POSITION controller, calls env.reset() "
             "and steps a four-element action", source="upstream_code", ref="examples/demo_env.py:15-35"),
        Fact("The clone also defines KitchenEnv in kitchen.py", source="upstream_code", ref=f"{KITCHEN}:18"),
        Fact("The clone also defines MultitaskKitchenDomain in multitask_kitchen.py", source="upstream_code",
             ref=f"{MULTITASK}:17"),
        Fact("The clone also defines ToolUseEnvBase in tool_use.py", source="upstream_code", ref=f"{TOOL_USE}:17"),
        Fact("The clone defines the hardest tool-use variant ToolUseEnv with its own cube and tool ranges",
             source="upstream_code", ref=f"{TOOL_USE}:545-552"),
        Fact("The package declares numpy, numba, scipy and mujoco-py as install dependencies; robosuite itself is "
             "installed separately", source="upstream_code", ref="setup.py:19-24"),
    ]
    safe_state = ("the simulation stops advancing: the e-stop closes the environment and no step or reset is accepted "
                  "until mhs.safety.reset clears the latch and resets the environment; the last observation and tick "
                  "stay readable")
    fidelity = {
        "engine": "robosuite:HammerPlaceEnv",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "the clone exposes no seed method and the robosuite reset takes no seed: the placement sampler "
                     "draws the object pose from numpy's process-wide generator (hammer_place.py:443-456), so the "
                     "MHS seed is recorded for the receipt only and does not select a state.  The package's fake is "
                     "deterministic from its own fixed placeholder start state but is not the upstream environment",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a physics-free stand-in: it keeps a placeholder end-effector position and a tick "
            "count, moves it by a placeholder gain, and integrates no rigid-body dynamics, contacts, friction, "
            "actuators, sensors, cameras or noise; the upstream environment builds a robosuite/MuJoCo world",
            "the observation is a placeholder dictionary with the robot keys the clone's get_state_vector names "
            "(hammer_place.py:530-533) and the activated robot0_joint_pos observable (hammer_place.py:332); the real "
            "observation also carries the object observations, robot0_contact, robot0_eef_force_norm and the "
            "agentview and robot0_eye_in_hand camera images that the constructor enables by default "
            "(hammer_place.py:28 and :43-45), and its array lengths depend on the robot and camera configuration. "
            "NOT COVERED: the camera image arrays",
            "the fake reports reward 0.0 and done false and never reaches the cabinet success predicate "
            "(hammer_place.py:463-475): the task success, reward scaling and placement sampling are not modelled",
            "there is no fixed timestep in the clone: control_freq is a constructor option with default 20 "
            "(hammer_place.py:39) and the physics step comes from the robosuite model, so timestep_ms is 0 and ticks "
            "count control steps, not physics steps",
            "the action vector's shape is a constructor option: the documented benchmark action space is "
            "OSC_POSITION (3) plus Gripper (1) (environments.md:39) and the clone special-cases action_dim 4 "
            "(hammer_place.py:489-492), but controller_configs can select another controller, so the driver declares "
            "no action bound and accepts any non-empty numeric vector",
            "the clone exposes no seed method and the reset takes no seed, so cap.world.reset.v1 records the seed "
            "without passing it to the environment; determinism.kind is none",
            "the clone's step replaces done with _check_success and the returned info only adds history_ft and "
            "recent_ft (hammer_place.py:495-499), so a horizon timeout is not reported and truncated is false",
            "only the first card entry symbol, HammerPlaceEnv, is served; the other four declared classes are other "
            "single-arm tasks and are not this driver",
            "snapshot and restore are not offered by this package",
            "robosuite, mujoco-py, numpy, numba and scipy were not installed and the upstream environment was never "
            "run, so no trajectory or observation of this package was compared with it",
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
        self._closed = False

    def setup(self) -> None:
        """Start a fresh episode so the first read has a defined observation."""

        self._store_observation(self.native.reset())
        self._tick = 0
        self._reward = 0.0
        self._terminated = False
        self._closed = False

    def teardown(self) -> None:
        close = getattr(self.native, "close", None)
        if callable(close):
            close()

    def _store_observation(self, observation: Any) -> None:
        value = _jsonable(observation)
        self._observation_value = value if isinstance(value, dict) else {"value": value}

    def _state_hash(self) -> str:
        return canonical.digest({
            "observation": self._observation_value,
            "tick": self._tick,
            "episode": self._episode,
            "reward": self._reward,
            "terminated": bool(self._terminated),
        })

    @read("observation", type="object",
          description="Last observation returned by the upstream environment's reset or step")
    def observation(self) -> dict[str, Any]:
        return self._observation_value

    @read("tick", type="integer", unit="1", description="Control steps applied since the last reset")
    def tick(self) -> int:
        return self._tick

    @read("episode", type="integer", unit="1", description="Resets performed since the backend opened")
    def episode(self) -> int:
        return self._episode

    @read("seed", type="integer", unit="1", description="Seed recorded for the last or next reset")
    def seed_value(self) -> int:
        return self._seed

    @read("reward", type="number", unit="1", description="Reward of the last step (summed over its ticks)")
    def reward(self) -> float:
        return self._reward

    @read("terminated", type="boolean", description="Whether the last step reported the task as done")
    def terminated(self) -> bool:
        return self._terminated

    @estop
    def stop(self) -> None:
        """Stop the simulation by closing the upstream environment."""

        self._closed = True
        self.native.close()

    @reset
    def recover(self) -> None:
        """Reset the environment after the operator clears the e-stop latch."""

        self._store_observation(self.native.reset())
        self._tick = 0
        self._episode += 1
        self._reward = 0.0
        self._terminated = False
        self._closed = False

    @action(cap="cap.world.reset.v1",
            description="Reset the environment to a fresh task start state",
            input={
                "seed": Field("integer", unit="1",
                              description="Seed recorded for the receipt; the upstream reset takes no seed"),
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
        self._closed = False
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
        info: Mapping[str, Any] = {}
        for _ in range(int(ticks)):
            self.check_cancelled()
            observation, step_reward, done, info = self.native.step(values)
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
            "state_hash": self._state_hash(),
            "reward": self._reward,
            "terminated": self._terminated,
            "truncated": bool(info.get("timed_out", False)) if isinstance(info, Mapping) else False,
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
