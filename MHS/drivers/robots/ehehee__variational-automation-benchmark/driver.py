"""OpenMHS driver for gh.ehehee/variational-automation-benchmark: the single-arm VAB environment.

The upstream is a robosuite/MuJoCo manipulation benchmark whose task is a YAML file.  The card's ``helper`` is
``MujocoDriver``, but the clone ships no MJCF model (``models`` is empty) and the device class is a robosuite
environment, not a bare MuJoCo model: ``VABEnv`` subclasses ``SingleArmEnv`` and builds its scene at run time
(``libero/libero/vab/env.py:50`` and ``:116-156``).  This package is therefore a direct ``Driver`` over ``VABEnv``,
which is the card's ``decision`` (``direct-driver``); the ``MujocoDriver`` helper is not used (RESULT.json).

The two bound capabilities are ``cap.world.step.v1`` and ``cap.world.reset.v1``.  A step applies the control vector
in ``action.values`` once per tick and calls ``VABEnv.step``; a reset calls ``VABEnv.reset(init_index=seed)`` and
returns the selected initial-state index as the required ``seed`` output.  The README calls the 50 initial states of
a single-arm task "seeds" and calls ``reset(init_index=i)`` (``README.md:42-43``), so the reset input maps the
catalogue's integer ``seed`` to the environment's own initial-state selector.  ``cap.world.seed.v1`` is deliberately
not bound: VABEnv exposes no random-number-generator seed, and the integer would have to pretend to be one.

The device is simulated (R0): there is no hardware backend and no e-stop path to a machine.  The fake backend
(``fake.py``) is the package's own pure Python stand-in; robosuite, MuJoCo and numpy were not installed where the
gate ran, so it was never compared with the upstream environment.  The observation carries the two cameras as
compact placeholder frames; the real task YAMLs request 128 x 128 x 3 (``README.md:93-94``), which is named in the
fidelity gaps.  This package is model-authored and unreviewed, and is checked on the fake backend only.
"""

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, action, read

ENV = "libero/libero/vab/env.py"
BIMANUAL = "libero/libero/vab/bimanual_env.py"
SCHEMA = "libero/libero/vab/schema.py"
LOADER = "libero/libero/vab/loader.py"
README = "README.md"
TASK_YAML = "tasks/libero_object_target_pos_var20x20/pick_up_the_cream_cheese_and_place_it_in_the_basket.yaml"


class VABEnvDriver(Driver):
    device_id = "vab"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "libero.vab.env:VABEnv"
    backends = {"fake": ".fake:FakeVABEnv"}
    display_name = "Variational Automation Benchmark single-arm environment"
    vendor, model = "ehehee", "Variational Automation Benchmark"
    tags = ["simulation", "robosuite", "mujoco", "manipulation", "robot", "benchmark", "reinforcement-learning"]
    facts = [
        Fact("VAB is a self-contained-YAML manipulation benchmark: one file per task supplies arena, robot, objects, "
             "initial states, success predicate and language", source="vendor_doc", ref=f"{README}:3-5"),
        Fact("The documented quick start loads a task YAML with load_task, builds the environment with task.make_env(), "
             "calls reset(init_index=i), then step(action) and unpacks a four-tuple", source="vendor_doc",
             ref=f"{README}:39-46"),
        Fact("The README calls the 50 initial states of a single-arm task seeds and loops over task.n_inits",
             source="vendor_doc", ref=f"{README}:42-43"),
        Fact("The README states the observation contract: images are uint8[H,W,3] per camera, proprio is joint_pos[7], "
             "joint_vel[7], eef_pos[3], eef_quat[4] (xyzw) and gripper_qpos[2]", source="vendor_doc",
             ref=f"{README}:54-63"),
        Fact("Success is returned only as info['success']; a multi-target predicate also surfaces completion_rate in "
             "0..1 and delivery_progress()", source="vendor_doc", ref=f"{README}:69-73"),
        Fact("The README example sets cameras agentview and robot0_eye_in_hand at camera_height 128 and camera_width "
             "128", source="vendor_doc", ref=f"{README}:92-94"),
        Fact("The README lists 62 tasks across 8 suites under tasks/", source="vendor_doc", ref=f"{README}:9"),
        Fact("load_task resolves the YAML path, parses it with yaml.safe_load and validates it into a Task",
             source="upstream_code", ref=f"{LOADER}:11-24"),
        Fact("Task.make_env dispatches to VABBimanualEnv when the YAML lists two robots and to VABEnv otherwise",
             source="upstream_code", ref=f"{SCHEMA}:87-94"),
        Fact("VABEnv subclasses robosuite's SingleArmEnv", source="upstream_code", ref=f"{ENV}:50"),
        Fact("VABEnv selects renderer='mujoco' and passes the task's control frequency, horizon and camera names to "
             "robosuite", source="upstream_code", ref=f"{ENV}:103-112"),
        Fact("reset(init_index) defaults to task.default_init_index, applies that initial state and returns the "
             "filtered observation", source="upstream_code", ref=f"{ENV}:200-212"),
        Fact("reset raises IndexError when init_index is not below len(task.inits)", source="upstream_code",
             ref=f"{ENV}:189-193"),
        Fact("step unwraps robosuite's (obs, reward, done, info), adds success, language and completion_rate to info, "
             "and returns the filtered observation", source="upstream_code", ref=f"{ENV}:214-228"),
        Fact("The filtered observation has exactly the images and proprio keys; images are keyed by the task camera "
             "names and proprio holds joint_pos, joint_vel, eef_pos, eef_quat and gripper_qpos", source="upstream_code",
             ref=f"{ENV}:255-275"),
        Fact("language_instruction returns task.language and action_dim returns robots[0].action_dim",
             source="upstream_code", ref=f"{ENV}:277-283"),
        Fact("delivery_progress returns a (delivered, total) pair or None, and reward is 1.0 on success and 0.0 "
             "otherwise", source="upstream_code", ref=f"{ENV}:239-253"),
        Fact("The bimanual class is VABBimanualEnv, a TwoArmEnv subclass", source="upstream_code",
             ref=f"{BIMANUAL}:38"),
        Fact("VABBimanualEnv.action_dim is the sum of both robots' action dimensions", source="upstream_code",
             ref=f"{BIMANUAL}:215-217"),
        Fact("The task YAML example names robot panda with controller OSC_POSE and the two cameras at 128 x 128",
             source="upstream_code", ref=f"{TASK_YAML}:4-7"),
        Fact("The smoke test asserts the observation keys are exactly images and proprio, asserts the agentview shape "
             "from the task's camera height and width, and asserts success and language in info", source="upstream_code",
             ref="tests/test_smoke.py:32-44"),
        Fact("requirements.txt pins robosuite 1.4.0 with numpy, opencv-python, matplotlib, pyyaml and pydantic",
             source="vendor_doc", ref="requirements.txt:1-6"),
        Fact("setup.py declares python_requires >=3.8 and name libero", source="upstream_code", ref="setup.py:12-18"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the observation, reward and tick stay readable")
    #: The model as deployed (spec 05-fidelity section 2).  The bridge derives the engine, the determinism kind and
    #: the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "robosuite:libero.vab.env/VABEnv",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "reset_required",
            "notes": "the reset input is the initial-state index (the README calls the initial states seeds), and "
                     "VABEnv applies the matching YAML pose, so one init index and one action sequence repeat on the "
                     "same environment; the environment exposes no random-number seed, so cap.world.seed.v1 is not "
                     "bound and the package makes no claim about robosuite's internal physics randomness",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is not robosuite/MuJoCo: it keeps a placeholder joint vector, applies a first-order "
            "motion of it and resolves no contact, controller, actuator or free-joint dynamics; it never evaluates "
            "the YAML success predicate and always reports success False",
            "the fake returns 2 x 2 x 3 pixel frames per camera, while the real task YAMLs set camera_height 128 and "
            "camera_width 128 (README.md:93-94); the fake's proprio arrays use the documented lengths but Python "
            "floats instead of float32 numpy arrays",
            "the fake was never compared with the upstream environment: robosuite 1.4.0, MuJoCo, numpy and pyyaml "
            "were not installed where the gate ran",
            "only one single-arm VABEnv is served; the card's VABBimanualEnv and load_task entry symbols are not "
            "bound, and no task YAML is loaded (the environment's task is not configured)",
            "the environment's control step is the default control_freq 20 Hz (env.py:56), i.e. 50 ms; there is no "
            "wall-clock pacing (realtime_factor 0)",
            "rendering is not served as a capability: images arrive inside the observation, but cap.world.* binds no "
            "render class and no artifact store",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
            "no physical robot is modelled and nothing was validated against hardware",
        ],
    }

    # ------------------------------------------------------------------ state
    def _observation_value(self) -> dict:
        return getattr(self, "_observation", {"images": {}, "proprio": {}})

    def _language_value(self) -> str:
        return str(getattr(self, "_language", ""))

    def _tick_value(self) -> int:
        return int(getattr(self, "_tick", 0))

    def _episode_value(self) -> int:
        return int(getattr(self, "_episode", 0))

    def _init_index_value(self) -> int:
        return int(getattr(self, "_init_index", 0))

    def _reward_value(self) -> float:
        return float(getattr(self, "_reward", 0.0))

    def _success_value(self) -> bool:
        return bool(getattr(self, "_success", False))

    def _completion_value(self) -> float:
        return float(getattr(self, "_completion_rate", 0.0))

    @read("observation", type="object",
          description="Latest filtered observation: camera frames under images and robot proprioception under proprio",
          properties={
              "images": Field("object", description="Camera name to a uint8 H x W x 3 frame (the fake returns a "
                                                    "compact placeholder frame)"),
              "proprio": Field("object", description="Robot proprioception: joint_pos, joint_vel, eef_pos, eef_quat "
                                                     "and gripper_qpos"),
          })
    def observation(self) -> dict:
        return self._observation_value()

    @read("reward", unit="1", description="Reward of the last step, as VABEnv.step returned it")
    def reward(self) -> float:
        return self._reward_value()

    @read("success", type="boolean", description="Success verdict of the last step, as info['success'] carried it")
    def success(self) -> bool:
        return self._success_value()

    @read("completion_rate", unit="1", description="Partial-credit completion rate of the last step, as info carried it")
    def completion_rate(self) -> float:
        return self._completion_value()

    @read("language", type="string", description="Language instruction of the configured task")
    def language(self) -> str:
        return self._language_value()

    @read("tick", type="integer", unit="1", description="Control steps applied since the last reset")
    def tick(self) -> int:
        return self._tick_value()

    @read("episode", type="integer", unit="1", description="Resets performed since the backend opened")
    def episode(self) -> int:
        return self._episode_value()

    @read("init_index", type="integer", unit="1", description="Initial-state index selected by the last reset")
    def init_index(self) -> int:
        return self._init_index_value()

    @read("action_dim", type="integer", unit="1", description="Control width of the configured robot")
    def action_dim(self) -> int:
        return int(self.native.action_dim)

    # ---------------------------------------------------------------- actions
    @action(cap="cap.world.step.v1",
            description="Apply the control vector once per tick through VABEnv.step and return the last transition",
            input={
                "ticks": Field("integer", unit="1",
                               description="Control steps to advance; the values are applied at every step"),
                "action": Field("object", description="The control vector, shaped like VABEnv.step's action",
                                properties={
                                    "values": Field("array", items=Field("number"),
                                                    description="Controller action values, one per robot control "
                                                                "dimension; the fake pads or trims to its width"),
                                }),
            })
    def step(self, ticks: int, action: dict) -> dict:
        values = action.get("values") if isinstance(action, dict) else None
        if values is None:
            vector = [0.0] * int(self.native.action_dim)
        else:
            try:
                vector = [float(item) for item in values]
            except (TypeError, ValueError) as exc:
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                                   f"action.values must be a list of numbers: {exc}") from exc
        observation = self._observation_value()
        reward = self._reward_value()
        done = bool(getattr(self, "_done", False))
        for _ in range(int(ticks)):
            observation, reward, done, info = self.native.step(vector)
            info = dict(info) if info else {}
            self._tick = self._tick_value() + 1
            self._observation = observation
            self._reward = float(reward)
            self._done = bool(done)
            self._success = bool(info.get("success", False))
            self._language = str(info.get("language", self.native.language_instruction))
            self._completion_rate = float(info.get("completion_rate", 0.0))
        state_hash = canonical.digest({"observation": observation, "tick": self._tick_value(),
                                       "success": self._success_value()})
        return {
            "observation": observation,
            "reward": float(reward),
            "terminated": bool(done),
            "truncated": False,
            "tick": self._tick_value(),
            "state_hash": state_hash,
        }

    @action(cap="cap.world.reset.v1",
            description="Reset VABEnv to the task's initial state selected by the seed (the init index)",
            input={
                "seed": Field("integer", unit="1",
                              description="Index of the initial state, as reset(init_index=seed) reads it"),
            })
    def reset_world(self, seed: int) -> dict:
        index = int(seed)
        try:
            observation = self.native.reset(init_index=index)
        except IndexError as exc:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", str(exc), native_code="IndexError") from exc
        self._observation = observation
        self._tick = 0
        self._episode = self._episode_value() + 1
        self._init_index = index
        self._reward = 0.0
        self._success = False
        self._completion_rate = 0.0
        self._done = False
        self._language = str(self.native.language_instruction)
        return {"observation": observation, "seed": index}
