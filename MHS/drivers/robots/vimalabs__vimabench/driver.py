"""OpenMHS driver for gh.vimalabs/vimabench: VIMA-Bench, a PyBullet tabletop manipulation simulator.

VIMA-Bench is a legacy ``gym.Env`` (``vima_bench/env/base.py:25``) built by its own factory ``vima_bench.make``
(``vima_bench/__init__.py:14``), not by a registered Gymnasium id.  A ``GymnasiumDriver`` derives its whole contract
from ``gymnasium.make(env_id)`` and its spaces; it cannot call ``vima_bench.make(task_name=...)``, and the clone
registers no Gymnasium id (no ``gym.register`` call exists in it).  This package is therefore a direct ``Driver`` over
the clone's entry class ``vima_bench.env.base:VIMAEnvBase`` (see RESULT.json, "DEVIATION FROM THE CARD"), with the
``sim`` backend naming the clone's own factory and a package fake for the gate.

The bound capabilities are ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1``.  A step applies
the pick-and-place action object (the four Box fields of ``VIMAEnvBase.action_space``, ``base.py:181-196`` and
``:402-408``) once per tick and returns the four-tuple ``(obs, reward, done, info)`` (``base.py:455``); a reset seeds
the environment through ``VIMAEnvBase.seed`` (``base.py:224-229``) and reloads the scene (``base.py:248-389``); the
seed capability sets the same seed without resetting.  ``VIMAEnvBase.seed`` seeds numpy's generator and the task
generator (``base.py:224-229``, ``tasks/task_suite/base.py:141-143``).

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The gate runs the package fake only; the ``sim`` backend (``vima_bench:make``) needs
pybullet, gym==0.21.0 and the clone's assets (``requirements.txt:1-2``) and was not run here.  This package is
model-authored and unreviewed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mhs import canonical
from mhs.bridge.base import MappingError, jsonable
from mhs.driver import Driver, Fact, Field, Limit, action, read

BASE = "vima_bench/env/base.py"
TASK = "vima_bench/tasks/task_suite/base.py"
INIT = "vima_bench/__init__.py"
README = "README.md"

#: The four action-space members, in the order ``VIMAEnvBase.step`` reads them (base.py:402-408).
POSE_FIELDS = ("pose0_position", "pose0_rotation", "pose1_position", "pose1_rotation")


def _json(value: Any) -> Any:
    """JSON data from a native observation/info value (numpy arrays become lists)."""
    try:
        return jsonable(value)
    except MappingError as exc:
        raise ValueError(f"VIMA-Bench returned a value that is not JSON data: {exc}") from exc


class VIMAEnv(Driver):
    device_id = "vima-bench"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "vima_bench.env.base:VIMAEnvBase"
    backends = {"fake": ".fake:FakeVIMAEnv", "sim": "vima_bench:make"}
    display_name = "VIMA-Bench multimodal robot manipulation benchmark (PyBullet)"
    vendor, model = "vimalabs", "VIMA-Bench"
    tags = ["vima", "robot-manipulation", "pybullet", "tabletop", "multimodal-prompt", "reinforcement-learning",
            "simulation", "gym"]
    facts = [
        Fact("The public factory is vima_bench.make, which returns a VIMAEnvBase", source="upstream_code",
             ref=f"{INIT}:14-42"),
        Fact("VIMAEnvBase is a gym.Env subclass", source="upstream_code", ref=f"{BASE}:25"),
        Fact("The README calls the interface Gym-style and shows make(task_name=...), env.reset()",
             source="vendor_doc", ref=f"{README}:30-40"),
        Fact("VIMA-Bench is a PyBullet simulation of a UR5 workspace: reset loads the plane, workspace and UR5 URDFs "
             "and sets gravity to -9.8 m/s^2", source="upstream_code", ref=f"{BASE}:248-287"),
        Fact("The constructor defaults are hz=240 and max_sim_steps_to_static=1000", source="upstream_code",
             ref=f"{BASE}:36-37"),
        Fact("VIMAEnvBase sets p.setTimeStep(1.0 / hz), the physics integration step", source="upstream_code",
             ref=f"{BASE}:131"),
        Fact("One VIMAEnvBase.step with an action executes one pick-and-place primitive and then steps the "
             "simulation until the rigid bodies are static, for at most max_sim_steps_to_static steps",
             source="upstream_code", ref=f"{BASE}:391-433"),
        Fact("The action space is a Dict of four Boxes: pose0_position and pose1_position are [0.25, -0.5] to "
             "[0.75, 0.50], and pose0_rotation and pose1_rotation are -1.0 to 1.0 with four elements",
             source="upstream_code", ref=f"{BASE}:181-196"),
        Fact("step reads the four action keys pose0_position, pose0_rotation, pose1_position and pose1_rotation",
             source="upstream_code", ref=f"{BASE}:402-408"),
        Fact("step returns the legacy four-tuple (obs, reward, done, info)", source="upstream_code",
             ref=f"{BASE}:455"),
        Fact("The reward is always 0 in VIMA-Bench", source="upstream_code", ref=f"{BASE}:437-438"),
        Fact("done is the task's success or failure flag", source="upstream_code", ref=f"{BASE}:452-455"),
        Fact("The info dict carries the prompt, success and failure", source="upstream_code",
             ref=f"{BASE}:675-682"),
        Fact("The default observation modalities are rgb and segm, each a Dict over the camera views, plus an "
             "ee Discrete(2) indicator", source="upstream_code", ref=f"{BASE}:69-106"),
        Fact("A task's default observation image size is (128, 256) and its default views are front and top",
             source="upstream_code", ref=f"{TASK}:67-114"),
        Fact("The observations are rendered per view; ee is 0 for the Suction end effector and 1 for Spatula",
             source="upstream_code", ref=f"{BASE}:663-671"),
        Fact("reset reloads the scene, resets the task, generates the prompt and returns the first observation",
             source="upstream_code", ref=f"{BASE}:248-389"),
        Fact("reset generates the prompt with Task.generate_prompt, which returns the prompt string and an assets "
             "dict", source="upstream_code", ref=f"{BASE}:330"),
        Fact("seed creates a numpy default_rng, stores the seed and seeds the task generator", source="upstream_code",
             ref=f"{BASE}:224-229"),
        Fact("Task.set_seed creates the task's numpy default_rng and stores the seed", source="upstream_code",
             ref=f"{TASK}:141-143"),
        Fact("Some task code draws from Python's global random and numpy's global generator, which "
             "VIMAEnvBase.seed does not set", source="upstream_code", ref=f"{TASK}:560-599"),
        Fact("close disconnects the PyBullet client", source="upstream_code", ref=f"{BASE}:221-222"),
        Fact("The install requirements are pybullet and gym==0.21.0", source="vendor_doc",
             ref="requirements.txt:1-2"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the stored observation, tick and prompt stay readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  ``timestep_ms`` names the
    #: PyBullet physics step; one cap.world.step tick is one env.step primitive, which runs a variable number of
    #: those steps until the objects settle (base.py:391-433), so the control period is not fixed (a gap below).
    fidelity = {
        "engine": "pybullet:vima_bench/VIMAEnvBase",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) and cap.world.seed.v1 call VIMAEnvBase.seed, which makes a numpy default_rng and "
                     "seeds the task generator (base.py:224-229, task_suite/base.py:141-143); not every upstream "
                     "draw is controlled by that seed (a gap below). The package fake uses Python's random.Random "
                     "instead, so one seed does not give the same trajectory on the fake and upstream",
        },
        "timestep_ms": 4.166666666666667,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "one cap.world.step.v1 tick is one VIMAEnvBase.step primitive, not one physics step: the primitive "
            "moves the arm and then integrates until the rigid bodies are static (at most max_sim_steps_to_static "
            "= 1000 steps, base.py:36-37 and :425-433), so the simulated duration of one tick is not fixed; "
            "timestep_ms names the PyBullet physics step (1/hz, hz default 240)",
            "the package fake is a pure Python kinematic stand-in: it moves one placeholder object to the place "
            "position and never uses PyBullet, contact dynamics, the UR5, the assets or the task success/failure "
            "logic; its object, target and prompt are placeholders",
            "the fake observation arrays are 3 x 2 x 2 rgb and 2 x 2 segm placeholders for the front and top views; "
            "the real arrays are 3 x 128 x 256 and 128 x 256 by the task defaults (task_suite/base.py:67), so the "
            "fake returns much smaller arrays than the device",
            "the fake draws with Python's random.Random, upstream with numpy's default_rng; the fake was never "
            "compared with the upstream PyBullet environment (pybullet and gym are not installed where the gate "
            "runs) and the model was never validated against a physical robot",
            "the upstream path is not fully reproducible from the seed alone: some task code also draws from "
            "Python's global random (tasks/task_suite/base.py:560) and numpy's global generator "
            "(tasks/task_suite/base.py:599), which VIMAEnvBase.seed does not set; the fake is reproducible from "
            "its own seed but does not model those draws",
            "no wall-clock pacing (realtime_factor 0); the fake does not model the physics step or the settle loop",
            "rendering is not served: the clone renders rgb/segm/depth through render_camera and cap.world.render.v1 "
            "needs an artifact store; depth is also rejected by the clone's modality assertion (base.py:67)",
            "snapshot and restore are not offered: VIMAEnvBase exposes no get_state/set_state",
            "prompt_assets (the images the prompt refers to) is not exposed; the prompt string is readable through "
            "the info read after a reset or a step",
        ],
    }

    # ------------------------------------------------------------------ state
    def _tick_value(self) -> int:
        return int(getattr(self, "_tick", 0))

    def _episode_value(self) -> int:
        return int(getattr(self, "_episode", 0))

    def _observation_json(self) -> dict[str, Any]:
        return _json(getattr(self, "_observation", {})) or {}

    @read("observation", type="object",
          description="Current observation dict from VIMAEnvBase: rgb and segm per view plus the ee indicator")
    def observation(self) -> dict[str, Any]:
        return self._observation_json()

    @read("reward", type="number", unit="1", description="Reward of the last step; VIMA-Bench always returns 0")
    def reward(self) -> float:
        return float(getattr(self, "_reward", 0.0))

    @read("terminated", type="boolean", description="True when the task reported success or failure")
    def terminated(self) -> bool:
        return bool(getattr(self, "_terminated", False))

    @read("truncated", type="boolean", description="True when a time limit ended the episode; VIMA-Bench has none")
    def truncated(self) -> bool:
        return bool(getattr(self, "_truncated", False))

    @read("tick", type="integer", unit="1", description="Primitives applied since the last reset")
    def tick(self) -> int:
        return self._tick_value()

    @read("episode", type="integer", unit="1", description="Resets performed since the backend opened")
    def episode(self) -> int:
        return self._episode_value()

    @read("info", type="object",
          description="Info dict of the last step: prompt, success and failure, as VIMAEnvBase._get_info builds it")
    def info(self) -> dict[str, Any]:
        return _json(getattr(self, "_info", {})) or {}

    # ---------------------------------------------------------------- actions
    @action(cap="cap.world.step.v1",
            description="Apply one VIMA-Bench pick-and-place action per tick and return the environment step result",
            input={
                "ticks": Field("integer", unit="1",
                               description="Primitives to apply; the action is used at every tick"),
                "action": Field("object", description="Pick-and-place action (the four Box fields)",
                                properties={
                                    "pose0_position": Field(
                                        "array", items="number", unit="m", length=2,
                                        description="Pick xy in metres",
                                        limit=Limit(min=[0.25, -0.5], max=[0.75, 0.50], names=["x", "y"],
                                                    source="upstream_code", ref=f"{BASE}:181-196")),
                                    "pose0_rotation": Field(
                                        "array", items="number", unit="1", length=4,
                                        description="Pick quaternion (x, y, z, w)",
                                        limit=Limit(min=-1.0, max=1.0, source="upstream_code",
                                                    ref=f"{BASE}:190-196")),
                                    "pose1_position": Field(
                                        "array", items="number", unit="m", length=2,
                                        description="Place xy in metres",
                                        limit=Limit(min=[0.25, -0.5], max=[0.75, 0.50], names=["x", "y"],
                                                    source="upstream_code", ref=f"{BASE}:181-196")),
                                    "pose1_rotation": Field(
                                        "array", items="number", unit="1", length=4,
                                        description="Place quaternion (x, y, z, w)",
                                        limit=Limit(min=-1.0, max=1.0, source="upstream_code",
                                                    ref=f"{BASE}:193-196")),
                                }),
            })
    def step(self, ticks: int, action: dict[str, Any]) -> dict[str, Any]:
        native_action = {name: list(action[name]) for name in POSE_FIELDS}
        for _ in range(int(ticks)):
            try:
                observation, reward, done, info = self.native.step(native_action)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"VIMAEnvBase.step did not return (obs, reward, done, info): {exc}") from exc
            self._observation = observation
            self._reward = float(reward)
            self._terminated = bool(done)
            self._truncated = False
            self._info = dict(info or {}) if isinstance(info, Mapping) else {"info": info}
            self._tick = self._tick_value() + 1
            if self._terminated:
                break
        observation_json = self._observation_json()
        return {
            "observation": observation_json,
            "reward": float(getattr(self, "_reward", 0.0)),
            "terminated": bool(getattr(self, "_terminated", False)),
            "truncated": bool(getattr(self, "_truncated", False)),
            "tick": self._tick_value(),
            "state_hash": canonical.digest({
                "observation": observation_json,
                "tick": self._tick_value(),
                "episode": self._episode_value(),
                "terminated": bool(getattr(self, "_terminated", False)),
                "truncated": bool(getattr(self, "_truncated", False)),
            }),
        }

    @action(cap="cap.world.reset.v1",
            description="Seed VIMAEnvBase, reload its scene and task, and return the first observation",
            input={"seed": Field("integer", unit="1",
                                 description="Seed for VIMAEnvBase.seed and the task generator (non-negative)")})
    def reset_world(self, seed: int) -> dict[str, Any]:
        self.native.seed(int(seed))
        observation = self.native.reset()
        self._observation = observation
        self._reward = 0.0
        self._terminated = False
        self._truncated = False
        self._tick = 0
        self._episode = self._episode_value() + 1
        self._seed = int(seed)
        self._info = self.native._get_info()
        return {"observation": self._observation_json(), "seed": int(seed)}

    @action(cap="cap.world.seed.v1",
            description="Seed VIMAEnvBase's random generators for the subsequent reset and steps, without resetting",
            input={"seed": Field("integer", unit="1",
                                 description="Seed passed to VIMAEnvBase.seed (non-negative)")})
    def seed_world(self, seed: int) -> dict[str, Any]:
        self.native.seed(int(seed))
        self._seed = int(seed)
        return {"seed": int(seed), "accepted": True}

    def teardown(self) -> None:
        self.native.close()
