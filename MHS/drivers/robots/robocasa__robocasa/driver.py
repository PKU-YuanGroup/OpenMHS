"""OpenMHS driver for gh.robocasa/robocasa: the PickPlaceCounterToCabinet kitchen simulation.

``RoboCasaGymEnv`` is a ``gymnasium.Env`` wrapper around a robosuite/MuJoCo kitchen task (gym_wrapper.py:143).  The
documented entry point is ``gym.make("robocasa/PickPlaceCounterToCabinet")`` (README.md:78-82); the wrapper registers
every environment as ``robocasa/<class>`` (gym_wrapper.py:400-420).  One package serves one task: the card's other
entry class, ``Kitchen``, is the base class of this task, not a second device.

DEVIATION FROM THE CARD: the card proposes the ``GymnasiumDriver`` helper, but that bridge cannot serve this
environment.  The wrapper's action space is a ``Dict`` whose keys already start with ``action.`` (gym_wrapper.py:95-98)
and ``unmap_action`` reads those exact keys (gym_wrapper.py:121-140).  The gymnasium bridge prefixes every Dict action
key with ``action.`` when it derives limits, so it builds the unresolvable limit path ``action.action.gripper_close``
and refuses to publish the contract (``python3 -m mhs.driver reference`` fails with ``limit path
'action.action.gripper_close' does not resolve``).  The package is therefore a direct ``Driver`` over the wrapper, with
an input schema that names the five fields without the upstream prefix and a driver-side translation that restores
``action.<field>`` before the native call.  The wire syntax of the Python interface is not changed; the mapping is
documented in facts.md.

The three bound capabilities are ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1``.  A step
repeats ``gym.Env.step`` for ``ticks`` transitions with one action, a reset calls ``gym.Env.reset(seed, options)`` and
a seed is recorded for the next reset (the wrapper has no separate seed method).  The device is simulated and has no
hardware backend.  The risk is R1, not R0, because every step advances a simulated robot arm and mobile base, which
the safety spec classifies as simulation stepping (MHS/spec/04-safety.md section 2.1) and which has no physical
effect outside the process.  With no hardware path there is no independent hardware e-stop to cite, and none is
claimed; the runtime's software e-stop latch stops the simulation, the driver's ``@estop`` closes the wrapper and
the observation and tick stay readable, and ``mhs.safety.reset`` reopens it at the recorded seed.

The gate does not install robosuite, MuJoCo, gymnasium or the roughly 10 GB kitchen assets (README.md:65), and package
code never imports the clone.  The ``fake`` backend is therefore this package's pure Python stand-in (fake.py) for the
wrapper's public surface; it models no contacts, task success or camera, and was never compared with the upstream
environment.  No sim or hardware backend is declared: that path would need robocasa imported, robosuite, MuJoCo 3.3.1
and the kitchen assets, and it was not run here.

Every Fact cites a line of the clone at commit 456174f62b89b8fca99eaaf33949c29fec9cfc2a.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs import canonical
from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, reset

WRAPPER = "robocasa/wrappers/gym_wrapper.py"
KITCHEN = "robocasa/environments/kitchen/kitchen.py"
ACTION_BOUND = f"{WRAPPER}:97-98"


def _action_limit():
    # gym_wrapper.py:97-98: every action Box is low=-1, high=1.
    return Limit(min=-1, max=1, unit="1", source="upstream_code", ref=ACTION_BOUND)


class RoboCasaPickPlace(Driver):
    device_id = "robocasa_pick_place"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R1"
    native = "robocasa.wrappers.gym_wrapper:RoboCasaGymEnv"
    backends = {"fake": ".fake:FakeRoboCasaEnv"}
    display_name = "RoboCasa PickPlaceCounterToCabinet (kitchen simulation)"
    vendor, model = "RoboCasa", "RoboCasa365 1.0.1"
    tags = ["robocasa", "kitchen", "manipulation", "mobile-base", "mujoco", "robosuite", "gymnasium",
            "simulation", "reinforcement-learning"]
    facts = [
        Fact("RoboCasa is a large-scale simulation framework for training robots to perform everyday tasks, not a "
             "hardware SDK", source="vendor_doc", ref="README.md:5"),
        Fact("The documented entry point creates an environment with "
             "gym.make('robocasa/PickPlaceCounterToCabinet', split='pretrain', seed=0)", source="vendor_doc",
             ref="README.md:78-82"),
        Fact("The wrapper registers every environment as 'robocasa/<class>' with the wrapper class as the entry "
             "point", source="upstream_code", ref=f"{WRAPPER}:400-420"),
        Fact("RoboCasaGymEnv is a gymnasium.Env subclass", source="upstream_code", ref=f"{WRAPPER}:143"),
        Fact("RoboCasaGymEnv forwards unknown attributes to the inner robosuite environment through __getattr__",
             source="upstream_code", ref=f"{WRAPPER}:395-397"),
        Fact("The wrapper's action space is a Dict of five Box fields with low -1 and high 1: action.gripper_close "
             "(1 element), action.end_effector_position (3), action.end_effector_rotation (3), action.base_motion "
             "(4) and action.control_mode (1)", source="upstream_code", ref=f"{WRAPPER}:83-102"),
        Fact("The final action_space is PandaOmronKeyConverter.deduce_action_space(env), not the space built from "
             "the composite controller", source="upstream_code", ref=f"{WRAPPER}:268"),
        Fact("unmap_action reads the five fields as input_action['action.gripper_close'], "
             "['action.end_effector_position'], ['action.end_effector_rotation'], ['action.base_motion'] and "
             "['action.control_mode'] before calling the inner environment", source="upstream_code",
             ref=f"{WRAPPER}:121-140"),
        Fact("The wrapper maps the robot observation to state.gripper_qpos, state.base_position, state.base_rotation, "
             "state.end_effector_position_relative and state.end_effector_rotation_relative", source="upstream_code",
             ref=f"{WRAPPER}:303-311"),
        Fact("The mapped state observations are Box(-1, 1)", source="upstream_code", ref=f"{WRAPPER}:72-76"),
        Fact("The camera configuration is three views named robot0_agentview_left, robot0_agentview_right and "
             "robot0_eye_in_hand, all 256 by 256 pixels", source="upstream_code", ref=f"{WRAPPER}:35-47"),
        Fact("The observation space adds one Box(0, 255) of shape (height, width, 3) per video.* camera and a "
             "Text(max_length=256) annotation.human.task_description", source="upstream_code",
             ref=f"{WRAPPER}:244-267"),
        Fact("reset(seed) replaces the inner environment RNG with numpy.random.default_rng(seed); options is accepted "
             "but not used", source="upstream_code", ref=f"{WRAPPER}:342-346"),
        Fact("step calls the inner environment, reports reward 1.0 when _check_success() is true and 0.0 otherwise, "
             "always sets truncated False and returns the inner environment's done flag", source="upstream_code",
             ref=f"{WRAPPER}:374-385"),
        Fact("Kitchen passes control_freq 20, horizon 1000 and ignore_done True to robosuite; one control signal "
             "therefore advances the simulation by 50 ms", source="upstream_code", ref=f"{KITCHEN}:381-383"),
        Fact("Kitchen._check_success returns False by default and the task subclasses implement the success test",
             source="upstream_code", ref=f"{KITCHEN}:1542-1551"),
        Fact("The package pins MuJoCo 3.3.1 and asserts that version at import", source="upstream_code",
             ref="robocasa/__init__.py:1005-1007"),
        Fact("Each environment is built with robosuite.make, the MuJoCo-backed engine", source="upstream_code",
             ref="robocasa/utils/env_utils.py:138"),
        Fact("The kitchen assets downloaded by the setup script are around 10GB", source="vendor_doc",
             ref="README.md:65"),
        Fact("render returns the cached camera frame and refuses before a reset or step; close delegates to the inner "
             "environment", source="upstream_code", ref=f"{WRAPPER}:387-393"),
    ]
    safe_state = ("the simulation stops advancing: the e-stop closes the wrapper and no step or reset is accepted "
                  "until mhs.safety.reset clears the latch and reopens it at the recorded seed; the observation and "
                  "tick stay readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The only served backend is the
    #: package fake, so the package claims F0: kinematic placeholder transitions with no contacts, no MuJoCo and no
    #: camera.  The upstream wrapper would be an F1 MuJoCo model, but it is not installed or run in this package.
    fidelity = {
        "engine": "custom:robocasa/PickPlaceCounterToCabinet (kinematic fake stand-in)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the driver records a seed and passes it to reset(seed), which replaces the wrapper's inner numpy "
                     "generator (gym_wrapper.py:342-344); the fake draws its placeholder state with Python's "
                     "random.Random, so one seed repeats on the fake but gives a different trajectory than the "
                     "upstream numpy stream, and no trajectory of the two was compared",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics: the fake integrates a placeholder linear motion of the robot state and has no MuJoCo, "
            "robosuite, rigid-body, contact, friction, actuator, sensor or noise model; the upstream wrapper would "
            "be an F1 MuJoCo model (robocasa/__init__.py:1005-1007, robocasa/utils/env_utils.py:138), not this",
            "the fake keeps reward 0.0 and done False for the base Kitchen success test (kitchen.py:1542-1551); the "
            "concrete task's success test, reward and horizon behaviour are not modelled",
            "the fake returns 2x2x3 placeholder camera frames whereas the upstream observation space declares "
            "256x256x3 frames (gym_wrapper.py:244-250), and its state lengths are placeholders",
            "task scenes and objects need the roughly 10GB kitchen assets downloaded by the setup script (README.md:65), "
            "which were not installed or downloaded here",
            "snapshot and restore are not offered: RoboCasaGymEnv exposes no get_state/set_state pair",
            "no sim or hardware backend is declared; the real wrapper path needs robocasa imported to register the "
            "id, robosuite, MuJoCo 3.3.1 (setup.py:21) and the kitchen assets, and was not run",
            "no physical device is modelled and the simulator was never validated against one",
        ],
    }

    # ------------------------------------------------------------------ state
    def setup(self):
        observation, info = self.native.reset(seed=0)
        self._last_observation = observation
        self._last_reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_info = dict(info or {})
        self._tick = 0
        self._episode = 1
        self._seed = 0
        self._pending_seed = None

    def _state_hash(self):
        return canonical.digest({
            "observation": self._last_observation,
            "tick": self._tick,
            "episode": self._episode,
            "terminated": bool(self._terminated),
            "truncated": bool(self._truncated),
        })

    @read("observation", type="object", description="Last observation returned by the wrapper")
    def observation(self):
        return dict(self._last_observation)

    @read("reward", type="number", unit="1", description="Reward of the last step")
    def reward(self):
        return float(self._last_reward)

    @read("terminated", type="boolean", description="Whether the last step reported the task as done")
    def terminated(self):
        return bool(self._terminated)

    @read("truncated", type="boolean", description="Whether the last step reported a truncation")
    def truncated(self):
        return bool(self._truncated)

    @read("tick", type="integer", unit="1", description="Transitions applied since the last reset")
    def tick(self):
        return int(self._tick)

    @read("episode", type="integer", unit="1", description="Resets performed since the backend opened")
    def episode(self):
        return int(self._episode)

    @read("seed", type="integer", unit="1", description="Seed recorded for the last or next reset")
    def seed(self):
        return int(self._seed)

    @read("info", type="object", description="Info dictionary returned by the last reset or step")
    def info(self):
        return dict(self._last_info)

    # --------------------------------------------------------------- stopping
    @estop
    def stop(self):
        self.native.close()

    @reset
    def recover(self):
        observation, info = self.native.reset(seed=int(self._seed))
        self._last_observation = observation
        self._last_reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_info = dict(info or {})
        self._tick = 0
        self._episode += 1

    # ---------------------------------------------------------------- actions
    @action(cap="cap.world.step.v1",
            description="Advance the simulation",
            input={
                "action": Field("object", description="Action fields",
                                properties={
                                    "gripper_close": Field("array", items="number", length=1, unit="1",
                                                           description="Gripper close",
                                                           limit=_action_limit()),
                                    "end_effector_position": Field("array", items="number", length=3, unit="1",
                                                                   description="End-effector position",
                                                                   limit=_action_limit()),
                                    "end_effector_rotation": Field("array", items="number", length=3, unit="1",
                                                                   description="End-effector rotation",
                                                                   limit=_action_limit()),
                                    "base_motion": Field("array", items="number", length=4, unit="1",
                                                         description="Base motion",
                                                         limit=_action_limit()),
                                    "control_mode": Field("array", items="number", length=1, unit="1",
                                                          description="Base control mode",
                                                          limit=_action_limit()),
                                }),
                "ticks": Field("integer", unit="1", description="Control steps"),
            })
    def step(self, action, ticks=1):
        native_action = {
            "action.gripper_close": list(action["gripper_close"]),
            "action.end_effector_position": list(action["end_effector_position"]),
            "action.end_effector_rotation": list(action["end_effector_rotation"]),
            "action.base_motion": list(action["base_motion"]),
            "action.control_mode": list(action["control_mode"]),
        }
        reward_total = 0.0
        for _ in range(int(ticks)):
            self.check_cancelled()
            observation, reward, done, truncated, info = self.native.step(native_action)
            self._last_observation = observation
            self._last_reward = float(reward)
            self._terminated = bool(done)
            self._truncated = bool(truncated)
            self._last_info = dict(info or {})
            reward_total += float(reward)
            self._tick += 1
            if self._terminated or self._truncated:
                break
        observation = dict(self._last_observation)
        return {
            "observation": observation,
            "reward": reward_total,
            "terminated": bool(self._terminated),
            "truncated": bool(self._truncated),
            "tick": int(self._tick),
            "state_hash": self._state_hash(),
        }

    @action(cap="cap.world.reset.v1",
            description="Reset the simulation",
            input={
                "seed": Field("integer", unit="1", description="Reset seed"),
                "options": Field("object", description="Reset options"),
            })
    def reset_world(self, seed=None, options=None):
        chosen = seed if seed is not None else self._pending_seed
        self._pending_seed = None
        kwargs = {}
        if chosen is not None:
            kwargs["seed"] = int(chosen)
        if options is not None:
            kwargs["options"] = dict(options)
        result = self.native.reset(**kwargs)
        observation, info = result
        self._last_observation = observation
        self._last_reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_info = dict(info or {})
        self._tick = 0
        self._episode += 1
        self._seed = int(chosen) if chosen is not None else 0
        return {"observation": dict(observation), "seed": int(self._seed)}

    @action(cap="cap.world.seed.v1",
            description="Record the next reset seed",
            input={"seed": Field("integer", unit="1", description="Next reset seed")})
    def set_seed(self, seed):
        self._seed = int(seed)
        self._pending_seed = int(seed)
        return {"seed": int(seed), "accepted": True}
