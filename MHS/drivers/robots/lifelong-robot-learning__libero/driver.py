"""OpenMHS driver for gh.lifelong-robot-learning/libero: the LIBERO ``OffScreenRenderEnv`` tabletop world.

The upstream is a robosuite/MuJoCo manipulation benchmark, not a hardware SDK.  The card's entry symbol
``libero.libero.envs.env_wrapper:OffScreenRenderEnv`` is a BDDL-driven *environment object*: the driver is a direct
``Driver`` over that object and serves the two ``cap.world.*`` classes that fit it.  ``cap.world.step.v1`` takes
``{ticks, action: {values: [seven numbers]}}``; one tick is one ``env.step`` (the clone's default ``control_freq`` of
20 means 50 ms of control time).  ``cap.world.reset.v1`` takes an optional ``seed``, calls ``env.seed(seed)`` and then
``env.reset()``.  The world resource publishes the low-dimensional observation the clone uses in
``get_robot_state_vector`` plus the reward, terminal flags, tick, episode and seed.  The device is simulated (R0): there
is no hardware backend, no e-stop path to a machine and no operator-required limit.

DEVIATION FROM THE CARD: the card names the ``MujocoDriver`` helper, but this upstream interface is the environment
object, not a bare MJCF file.  A ``MujocoDriver`` would load a model path and its fake would have to expose the
``mujoco`` module surface (``MjModel``, ``MjData``, ``mj_step``, ...), none of which is an attribute of
``OffScreenRenderEnv``; gate G7 checks the fake against the card's entry symbol.  This package therefore uses a direct
``Driver`` over ``OffScreenRenderEnv`` (the card's decision is already ``direct-driver``).

The gate cannot import the clone (and robosuite, mujoco, bddl and torch are absent where it runs), so ``backends``
names the package's own fake, a pure Python stand-in (see fake.py and the fidelity ``gaps``).  The real MuJoCo/robosuite
environment is not opened here and no trajectory was compared with it.  Every Fact cites a line of the clone at the
pinned commit (8f1084e3132a39270c3a13ebe37270a43ece2a01).  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from collections.abc import Mapping

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, action, read

ENV = "libero/libero/envs/env_wrapper.py"
BDDL = "libero/libero/envs/bddl_base_domain.py"
KITCHEN = "libero/libero/envs/problems/libero_kitchen_tabletop_manipulation.py"
BDDL_FILE = ("libero/libero/bddl_files/libero_10/"
             "KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it.bddl")
README = "README.md"
REQUIREMENTS = "requirements.txt"
#: The low-dimensional observation members of the robosuite observation dict (bddl_base_domain.py:828).
OBS_KEYS = ("robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos")
ACTION_LENGTH = 7


def _action_values(action_value):
    """The seven OSC_POSE values from the action object the capability schema describes."""
    values = action_value.get("values") if isinstance(action_value, Mapping) else action_value
    if not isinstance(values, (list, tuple)) or len(values) != ACTION_LENGTH:
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                           f"action.values must be an array of {ACTION_LENGTH} numbers")
    try:
        return [float(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action.values must contain only numbers",
                           ) from exc


class LiberoOffScreen(Driver):
    device_id = "libero"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "libero.libero.envs.env_wrapper:OffScreenRenderEnv"
    backends = {"fake": ".fake:FakeOffScreenRenderEnv"}
    display_name = "LIBERO OffScreenRenderEnv tabletop manipulation"
    vendor, model = "Lifelong Robot Learning", "LIBERO"
    tags = ["libero", "robosuite", "mujoco", "simulation", "manipulation", "reinforcement-learning"]
    facts = [
        Fact("ControlEnv reads the BDDL problem information and builds the robosuite task class "
             "TASK_MAPPING[problem_name] from the BDDL file", source="upstream_code", ref=f"{ENV}:49-56"),
        Fact("OffScreenRenderEnv forces has_renderer False and has_offscreen_renderer True before it builds the "
             "ControlEnv", source="upstream_code", ref=f"{ENV}:152-159"),
        Fact("ControlEnv.step passes the action straight to the robosuite environment", source="upstream_code",
             ref=f"{ENV}:87-88"),
        Fact("ControlEnv.reset calls env.reset() until it returns and retries when the environment raises "
             "RandomizationError", source="upstream_code", ref=f"{ENV}:90-101"),
        Fact("ControlEnv.seed delegates to env.seed(seed)", source="upstream_code", ref=f"{ENV}:133-134"),
        Fact("BDDLBaseDomain.seed calls np.random.seed(seed)", source="upstream_code", ref=f"{BDDL}:162-163"),
        Fact("ControlEnv.set_init_state loads the supplied state and regenerates the observations through "
             "regenerate_obs_from_state", source="upstream_code", ref=f"{ENV}:136-145"),
        Fact("ControlEnv.get_sim_state returns the flattened MuJoCo simulation state", source="upstream_code",
             ref=f"{ENV}:118-120"),
        Fact("ControlEnv.close closes the robosuite environment", source="upstream_code", ref=f"{ENV}:147-149"),
        Fact("ControlEnv defaults to the OSC_POSE controller", source="upstream_code", ref=f"{ENV}:17"),
        Fact("ControlEnv defaults control_freq to 20 control steps per second, so one control step lasts 50 ms",
             source="upstream_code", ref=f"{ENV}:27"),
        Fact("ControlEnv defaults horizon to 1000", source="upstream_code", ref=f"{ENV}:28"),
        Fact("The default camera names are agentview and robot0_eye_in_hand with camera heights and widths 128",
             source="upstream_code", ref=f"{ENV}:31-36"),
        Fact("BDDLBaseDomain is the robosuite SingleArmEnv task base class", source="upstream_code",
             ref=f"{BDDL}:37"),
        Fact("The task base imports the mujoco Python bindings", source="upstream_code", ref=f"{BDDL}:13"),
        Fact("BDDLBaseDomain.step calls super().step(action) and then reports done as _check_success()",
             source="upstream_code", ref=f"{BDDL}:800-809"),
        Fact("BDDLBaseDomain.reward returns 1.0 when _check_success() and 0.0 otherwise, scaled by reward_scale",
             source="upstream_code", ref=f"{BDDL}:179-189"),
        Fact("BDDLBaseDomain._assert_problem_name requires the parsed problem name to equal the class name in "
             "lower case", source="upstream_code", ref=f"{BDDL}:191-195"),
        Fact("The robosuite observation vector of LIBERO concatenates robot0_gripper_qpos, robot0_eef_pos and "
             "robot0_eef_quat", source="upstream_code", ref=f"{BDDL}:828"),
        Fact("The README example constructs OffScreenRenderEnv from a BDDL file, seeds and resets it, sets an initial "
             "state, and steps a seven-element action that returns (obs, reward, done, info)",
             source="upstream_code", ref=f"{README}:116-130"),
        Fact("The Libero_Kitchen_Tabletop_Manipulation problem class is registered with register_problem and extends "
             "BDDLBaseDomain", source="upstream_code", ref=f"{KITCHEN}:11-12"),
        Fact("The kitchen BDDL file defines the problem LIBERO_Kitchen_Tabletop_Manipulation and its language "
             "instruction", source="upstream_code", ref=f"{BDDL_FILE}:1-3"),
        Fact("The clone pins robosuite 1.4.0 and bddl 1.0.1 as its simulation and BDDL dependencies",
             source="upstream_code", ref=f"{REQUIREMENTS}:10-11"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The upstream is MuJoCo through
    #: robosuite; the fake's gaps are listed below so the contract says what this package does not model.
    fidelity = {
        "engine": "mujoco:libero",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "cap.world.reset.v1 calls env.seed(seed) and then env.reset(); upstream sets numpy's global "
                     "seed and draws the object placements from it, while this package's fake uses Python's "
                     "random.Random, so the same seed does not produce the same trajectory on the two",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a stand-in for the robosuite/MuJoCo environment: it integrates a placeholder "
            "first-order end-effector and gripper motion and models no contact, friction, mass, actuator, object "
            "placement or MuJoCo state",
            "the task predicate, the sparse task reward of bddl_base_domain.py:165-189 and the done flag from "
            "_check_success() are not modelled: the fake always returns reward 0.0 and done false",
            "the clone's default observation also carries the agentview and robot0_eye_in_hand camera images "
            "(128 x 128 x 3 each); the fake and this driver return only the low-dimensional robot0_eef_pos, "
            "robot0_eef_quat and robot0_gripper_qpos members, and the full camera arrays are NOT COVERED",
            "the real MuJoCo qpos/qvel layout is not modelled: the fake's get_sim_state returns nine placeholder "
            "numbers, not the flattened state of the task model",
            "the fake's step is one control step of 50 ms (the clone's default control_freq 20); the physics "
            "substeps MuJoCo performs inside that step are not modelled",
            "no wall-clock pacing and no rendering: realtime_factor 0, clock lockstep, and no "
            "cap.world.render.v1 binding",
            "snapshot and restore are not offered by this driver even though the clone exposes get_sim_state, "
            "set_state and set_init_state; no snapshot capability is bound",
            "no physical device is modelled and nothing was validated against hardware; no upstream simulator "
            "trajectory was compared with the fake",
        ],
    }

    # -- startup -------------------------------------------------------------
    def setup(self):
        """Open the environment at its deterministic start state and keep the first observation."""
        #: placeholder: the seed the driver uses before the first explicit reset
        self._seed = 0
        self._episode = 0
        self._tick = 0
        self._last_observation = None
        self._last_reward = 0.0
        self._terminated = False
        self._truncated = False
        self.native.seed(self._seed)
        self._last_observation = self._compact(self.native.reset())

    def _compact(self, observation):
        """Keep the low-dimensional members of the robosuite observation dict and make them JSON numbers."""
        if not isinstance(observation, Mapping):
            raise DriverFailed("MHS.DEVICE.FAULTED", "the environment returned no observation mapping")
        compact = {}
        for key in OBS_KEYS:
            value = observation.get(key)
            if value is None:
                continue
            try:
                compact[key] = [float(item) for item in value]
            except (TypeError, ValueError) as exc:
                raise DriverFailed("MHS.DEVICE.FAULTED",
                                   f"the environment observation member {key!r} is not numeric") from exc
        if not compact:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the environment observation has none of the members {list(OBS_KEYS)}")
        return compact

    def _state_hash(self):
        """A digest of the state this driver publishes (the receipt's state hash is the server's own)."""
        return canonical.digest({
            "observation": self._last_observation,
            "tick": self._tick,
            "episode": self._episode,
            "terminated": bool(self._terminated),
            "truncated": bool(self._truncated),
        })

    # -- resource state ------------------------------------------------------
    @read("observation", type="object",
          description="Last low-dimensional observation: robot0_eef_pos (3), robot0_eef_quat (4) and "
                      "robot0_gripper_qpos (2); camera images are not returned")
    def observation(self):
        return self._last_observation

    @read("reward", unit="1", description="Reward of the last step")
    def reward(self):
        return self._last_reward

    @read("terminated", type="boolean", description="Whether the task reported done on the last step")
    def terminated(self):
        return bool(self._terminated)

    @read("truncated", type="boolean", description="Whether the last step ended the episode without a task success")
    def truncated(self):
        return bool(self._truncated)

    @read("tick", type="integer", unit="1", description="Control steps since the last reset")
    def tick(self):
        return int(self._tick)

    @read("episode", type="integer", unit="1", description="Reset actions since the driver started")
    def episode(self):
        return int(self._episode)

    @read("seed", type="integer", unit="1", description="Seed used by the last reset")
    def seed(self):
        return int(self._seed)

    # -- capabilities --------------------------------------------------------
    @action(cap="cap.world.reset.v1", action_name="reset",
            description="Reset the environment to its task start state after applying the seed",
            input={"seed": Field("integer", unit="1",
                                 description="Seed passed to env.seed before env.reset; the last seed is reused when "
                                             "omitted")})
    def reset_world(self, seed=None):
        chosen = self._seed if seed is None else int(seed)
        self.check_cancelled()
        self.native.seed(chosen)
        observation = self.native.reset()
        self._seed = chosen
        self._episode += 1
        self._tick = 0
        self._last_reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_observation = self._compact(observation)
        return {"observation": self._last_observation, "seed": chosen}

    @action(cap="cap.world.step.v1", action_name="step",
            description="Advance the environment by a bounded number of control steps with one seven-element "
                        "OSC_POSE action",
            input={
                "ticks": Field("integer", unit="1",
                               description="Control steps to advance; the action is applied at every step"),
                "action": Field("object", description="The OSC_POSE action applied at every step",
                                properties={"values": Field(
                                    "array", items=Field("number", unit="1"), length=ACTION_LENGTH,
                                    description="Seven numbers: end-effector delta x, y, z, rotation x, y, z and "
                                                "gripper command")}),
            })
    def step_world(self, action, ticks=1):
        values = _action_values(action)
        if self._terminated or self._truncated:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the episode has ended; reset the environment before stepping")
        total_reward = 0.0
        for _ in range(int(ticks)):
            self.check_cancelled()
            observation, reward, done, _info = self.native.step(values)
            self._tick += 1
            self._last_observation = self._compact(observation)
            self._last_reward = float(reward)
            self._terminated = bool(done)
            self._truncated = False
            total_reward += self._last_reward
            if self._terminated:
                break
        return {
            "observation": self._last_observation,
            "reward": total_reward,
            "terminated": bool(self._terminated),
            "truncated": bool(self._truncated),
            "tick": int(self._tick),
            "state_hash": self._state_hash(),
        }
