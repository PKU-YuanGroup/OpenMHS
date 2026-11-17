"""OpenMHS driver for gh.unitreerobotics/unitree_rl_gym: the Go2 Isaac Gym training world.

The card's entry symbol is ``legged_gym.envs.base.legged_robot:LeggedRobot``.  It is a concrete
implementation: the ``go2`` task is registered with this exact class
(``legged_gym/envs/__init__.py:14``) and the class implements ``step`` and ``reset_idx`` itself; only
``BaseTask.reset`` is inherited.  The package serves that registered Go2 task, not a hardware robot:
the upstream is a reinforcement-learning simulator (``setup.py:11`` names isaacgym and rsl-rl, not a
serial, USB or DDS transport).

The interface is the rsl_rl vector-environment one, not Gymnasium:

* ``step(actions)`` takes a native tensor shaped ``(num_envs, num_actions)``, clips it, runs
  ``cfg.control.decimation`` physics substeps and returns
  ``(obs_buf, privileged_obs_buf, rew_buf, reset_buf, extras)``
  (``legged_gym/envs/base/legged_robot.py:49-80``);
* ``reset()`` resets every environment and then takes one zero-action step
  (``legged_gym/envs/base/base_task.py:82-86``);
* ``reset_buf`` is the native terminal flag and ``time_out_buf`` the native time-limit flag
  (``legged_gym/envs/base/legged_robot.py:118-124``);
* the observation is the concatenation of base linear velocity, base angular velocity, projected
  gravity, commands, the scaled DOF position difference, DOF velocity and the actions
  (``legged_gym/envs/base/legged_robot.py:182-192``), in the native DOF order.

This is a direct :class:`~mhs.driver.Driver`, not the card's ``PythonObjectDriver``: the
python-object family is configuration only and cannot build the per-agent action tensor, unpack the
five-tuple step result, preserve the separate terminated/truncated flags or convert both fake and
simulator results to JSON.  Those conversions live here, in the production adapter, so the fake and
the sim backend share them.

Two catalogue classes are bound: ``cap.world.step.v1`` (``ticks`` control transitions with one action
per transition) and ``cap.world.reset.v1``.  ``cap.world.seed.v1`` is deliberately not bound: the
seed is applied by ``task_registry.make_env`` before the environment is constructed
(``legged_gym/utils/task_registry.py:64``, ``legged_gym/utils/helpers.py:42-47``), and the
constructed environment has no post-construction integer seed.  The environment exposes no
``get_state``/``set_state`` either, so this package declares no seeded replay claim.

The device is simulated at R0.  The runtime's software e-stop latch stops the world by refusing
further steps and resets; there is no hardware stop to declare.  This package is model-authored and
unreviewed: it is checked on the fake backend only, and no upstream simulator or hardware was run.
"""

from collections.abc import Mapping

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, read

LEGGED_ROBOT = "legged_gym/envs/base/legged_robot.py"
BASE_TASK = "legged_gym/envs/base/base_task.py"
TASK_REGISTRY = "legged_gym/utils/task_registry.py"
HELPERS = "legged_gym/utils/helpers.py"
CONFIG = "legged_gym/envs/base/legged_robot_config.py"
GO2_CONFIG = "legged_gym/envs/go2/go2_config.py"

#: The catalogue's integer input for a step: the runtime carries the class's 1..10000 range.
MAX_TICKS = 10000


class UnitreeGo2(Driver):
    device_id = "unitree-go2"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "legged_gym.envs.base.legged_robot:LeggedRobot"
    backends = {"fake": ".fake:FakeLeggedRobot", "sim": ".driver:make_env"}
    vendor, model = "Unitree Robotics", "unitree_rl_gym go2 (Isaac Gym)"
    display_name = "Unitree RL Gym Go2 training world"
    tags = ["unitree", "go2", "quadruped", "reinforcement-learning", "isaac-gym", "simulation"]
    facts = [
        Fact("The README describes the repository as a reinforcement learning implementation based on "
             "Unitree robots, supporting Go2, H1, H1_2 and G1", source="vendor_doc", ref="README.md:9"),
        Fact("The go2 task is registered with the LeggedRobot class and the GO2RoughCfg and GO2RoughCfgPPO "
             "configs", source="upstream_code", ref="legged_gym/envs/__init__.py:14"),
        Fact("task_registry.make_env constructs the registered task class with cfg, sim_params, "
             "physics_engine, sim_device and headless", source="upstream_code", ref=f"{TASK_REGISTRY}:68-72"),
        Fact("task_registry.make_env applies the config seed with set_seed before it constructs the "
             "environment", source="upstream_code", ref=f"{TASK_REGISTRY}:64"),
        Fact("set_seed seeds Python random, numpy, torch and PYTHONHASHSEED and also the CUDA generators",
             source="upstream_code", ref=f"{HELPERS}:42-47"),
        Fact("BaseTask.reset resets every environment and then calls step with a zero action, returning the "
             "observation and the privileged observation", source="upstream_code", ref=f"{BASE_TASK}:82-86"),
        Fact("BaseTask takes num_envs, num_obs, num_privileged_obs and num_actions from the config and "
             "allocates observation, reward, reset, episode-length and timeout buffers for num_envs "
             "environments", source="upstream_code", ref=f"{BASE_TASK}:31-49"),
        Fact("LeggedRobot.step clips the actions to plus or minus cfg.normalization.clip_actions, runs "
             "cfg.control.decimation physics substeps and then calls post_physics_step",
             source="upstream_code", ref=f"{LEGGED_ROBOT}:49-73"),
        Fact("LeggedRobot.step returns obs_buf, privileged_obs_buf, rew_buf, reset_buf and extras after "
             "clipping the observations", source="upstream_code", ref=f"{LEGGED_ROBOT}:75-80"),
        Fact("post_physics_step increments episode_length_buf and common_step_counter, checks terminations, "
             "computes rewards, resets the environments in reset_buf and computes the observations",
             source="upstream_code", ref=f"{LEGGED_ROBOT}:90-112"),
        Fact("check_termination sets reset_buf from termination contacts and base orientation, sets "
             "time_out_buf when episode_length_buf exceeds max_episode_length and ORs the timeout into "
             "reset_buf", source="upstream_code", ref=f"{LEGGED_ROBOT}:118-124"),
        Fact("reset_idx resets the DOFs and root states, resamples commands, clears action and episode-length "
             "buffers and sets reset_buf to 1 for the selected environments", source="upstream_code",
             ref=f"{LEGGED_ROBOT}:139-151"),
        Fact("compute_observations concatenates base linear velocity, base angular velocity, projected "
             "gravity, commands, the scaled DOF position difference, DOF velocity and the actions",
             source="upstream_code", ref=f"{LEGGED_ROBOT}:182-192"),
        Fact("_compute_torques scales actions by cfg.control.action_scale and interprets them according to "
             "control_type P, V or T, clipping the torques to torque_limits", source="upstream_code",
             ref=f"{LEGGED_ROBOT}:308-330"),
        Fact("The DOF count and names come from the loaded asset", source="upstream_code",
             ref=f"{LEGGED_ROBOT}:548-558"),
        Fact("Default joint angles and PD gains are looked up by DOF name", source="upstream_code",
             ref=f"{LEGGED_ROBOT}:466-476"),
        Fact("LeggedRobot sets self.dt to cfg.control.decimation multiplied by sim_params.dt",
             source="upstream_code", ref=f"{LEGGED_ROBOT}:624"),
        Fact("The maximum episode length is ceil(episode_length_s / self.dt)", source="upstream_code",
             ref=f"{LEGGED_ROBOT}:630-631"),
        Fact("The base env config defaults to 4096 environments, 48 observations and 12 actions",
             source="upstream_code", ref=f"{CONFIG}:5-8"),
        Fact("The base control config defaults to decimation 4", source="upstream_code", ref=f"{CONFIG}:60-68"),
        Fact("The base normalization config clips actions to 100.0", source="upstream_code", ref=f"{CONFIG}:135"),
        Fact("The base sim config uses a 0.005 s timestep", source="upstream_code", ref=f"{CONFIG}:154-155"),
        Fact("The PPO config default seed is 1", source="upstream_code", ref=f"{CONFIG}:173-174"),
        Fact("GO2RoughCfg extends LeggedRobotCfg and its control section sets control_type P, action_scale "
             "0.25 and decimation 4", source="upstream_code", ref=f"{GO2_CONFIG}:3-31"),
        Fact("GO2RoughCfg lists twelve default joint angles, four for each of the hip, thigh and calf "
             "groups", source="upstream_code", ref=f"{GO2_CONFIG}:6-21"),
        Fact("GO2RoughCfg loads the Go2 URDF from resources/robots/go2/urdf/go2.urdf",
             source="upstream_code", ref=f"{GO2_CONFIG}:33-35"),
        Fact("setup.py install_requires lists isaacgym, rsl-rl, matplotlib, numpy, tensorboard, mujoco and "
             "pyyaml; it names no serial, USB or DDS hardware transport", source="upstream_code",
             ref="setup.py:11"),
    ]
    safe_state = ("the software e-stop latch refuses further step and reset calls; an in-flight native control "
                  "transition may finish, and the last observation, tick and episode counters stay readable")
    #: The deployed fake is an analytic F0 stand-in, not the upstream Isaac Gym simulator.
    fidelity = {
        "engine": "analytic:unitree_rl_gym-go2-stand-in",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "the fake applies one closed-form transition per tick and is repeatable for a fixed action "
                     "sequence, but the upstream environment has no post-construction integer seed and no "
                     "get_state/set_state, so this package makes no seeded replay claim and does not bind "
                     "cap.world.seed.v1",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a pure-Python analytic stand-in for the go2 training environment, not the upstream Isaac "
            "Gym simulator: it runs no PhysX, contact, terrain, URDF or reward computation, and its observation, "
            "reward and termination values are placeholders",
            "the base config defaults to 4096 parallel environments, 48 observations and 12 actions "
            "(legged_gym/envs/base/legged_robot_config.py:5-8); the fake returns 1 environment by default "
            "(a caller may ask for 2 through the fake option num_envs) and its 48-value observation and 12-action "
            "vector are placeholder shapes, so a receipt is smaller than the upstream default",
            "the upstream step runs cfg.control.decimation physics substeps per control action "
            "(legged_gym/envs/base/legged_robot.py:60; go2 decimation 4, sim dt 0.005 s, "
            "legged_gym/envs/go2/go2_config.py:31 and legged_gym/envs/base/legged_robot_config.py:155), a 20 ms "
            "control period; the fake advances one closed-form transition per tick without integrating those "
            "substeps",
            "the fake does not model the Go2 URDF, joint limits, PD gains, torques, commands, contacts, terrain, "
            "domain randomization or the reward functions; it only carries the action into a placeholder "
            "observation, and it clips the action to a placeholder 100.0 rather than the environment's configured "
            "cfg.normalization.clip_actions",
            "no seed control or snapshot/restore: the upstream seed is applied before construction "
            "(legged_gym/utils/task_registry.py:64 and legged_gym/utils/helpers.py:42-47), the environment exposes "
            "no post-construction integer seed and no get_state/set_state, so the package declares no seeded replay "
            "claim",
            "no rendering: the Isaac Gym viewer is not exposed, and no cap.world.render.v1 is bound",
            "the sim backend factory (.driver:make_env) was not run: it needs the installed upstream package, "
            "isaacgym and torch (setup.py:11), and the gate and these tests use the fake only",
            "policy action bounds are operator_required; site-limits.example.json contains illustrative fake-scale "
            "bounds, not joint travel limits or an approved live deployment envelope",
        ],
    }
    fidelity_by_backend = {
        "sim": {
            "engine": "isaacgym:unitree_rl_gym-go2",
            "fidelity_level": "F1",
            "gaps": [
                "the live Isaac Gym backend was not run or compared with hardware; only Go2 is served",
                "the factory enforces headless=True because BaseTask.render can call sys.exit with a viewer; "
                "construction acquires Isaac Gym, changes process-wide torch JIT flags and creates a simulator "
                "(base_task.py:12,36-56); the package provides no simulator teardown",
                "native physics and reset calls can block, with cancellation checked only between control transitions; "
                "a transition already in flight may finish after the e-stop latch engages",
                "the upstream may print to stdout during construction; stdio hosting requires isolation of that output",
                "policy action bounds must be supplied for the selected deployment; the example overlay is fake-scale",
                "the separate deploy/deploy_real DDS robot runner and the H1, H1_2 and G1 tasks are not served",
            ],
        },
    }

    # -- lifecycle ------------------------------------------------------------------------------------------
    def setup(self):
        """Initialise the driver-side counters and the observation from the backend's current buffers."""
        task = str(self.options.get("task", "go2"))
        if task != "go2":
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"this package serves the go2 task; the backend was asked for {task!r}")
        self._tick = 0
        self._episode = 0
        self._last_observation = self._observation_from(self.native.obs_buf, self.native.privileged_obs_buf,
                                                        self.native.rew_buf, self.native.reset_buf,
                                                        self.native.time_out_buf, self.native.episode_length_buf,
                                                        self.native.extras)

    # -- reads ----------------------------------------------------------------------------------------------
    @read("tick", type="integer", unit="1", description="Control transitions applied since the last reset")
    def get_tick(self):
        return int(getattr(self, "_tick", 0))

    @read("episode", type="integer", unit="1", description="Resets performed since the backend opened")
    def get_episode(self):
        return int(getattr(self, "_episode", 0))

    @read("scenario", type="string", description="Registered task this world serves: go2")
    def get_scenario(self):
        return "go2"

    @read("num_envs", type="integer", unit="1",
          description="Number of parallel environments in the native action and observation tensors")
    def get_num_envs(self):
        return int(self.native.num_envs)

    @read("num_actions", type="integer", unit="1", description="Action values per environment, in native DOF order")
    def get_num_actions(self):
        return int(self.native.num_actions)

    @read("num_observations", type="integer", unit="1", description="Observation values per environment")
    def get_num_observations(self):
        return int(self.native.num_obs)

    @read("observation", type="object",
          description="Last observation snapshot: per-environment observations, rewards, terminal flags and "
                      "episode lengths, in native environment order")
    def get_observation(self):
        return getattr(self, "_last_observation", None)

    # -- actions --------------------------------------------------------------------------------------------
    @action(cap="cap.world.step.v1",
            description="Apply one policy action per control transition and return the resulting per-environment "
                        "observation, rewards and native terminal flags",
            input={
                "ticks": Field("integer", unit="1",
                               description="Control transitions to advance; the same action is applied at every "
                                           "tick"),
                "action": Field("object",
                                description="Native policy action: values holds one vector per environment in "
                                            "native environment order, each with num_actions values; a flat "
                                            "vector of num_actions values is broadcast to every environment; "
                                            "an explicit action is required so the envelope always checks it",
                                required=True,
                                properties={
                                    "values": Field("array", items=Field(), unit="1",
                                                    description="One policy vector per environment, or one flat "
                                                                "vector broadcast to every environment",
                                                    required=True,
                                                    limit=Limit.operator_required(
                                                        "the action clip is a configurable policy setting, not a "
                                                        "device travel bound; the operator supplies the policy "
                                                        "envelope for the selected simulation deployment")),
                                }),
            })
    def advance(self, action, ticks=1):
        rows = self._native_actions(action)
        # The real step calls torch.clip on a Tensor (legged_robot.py:53-57).
        # Its observation buffer supplies the floating dtype and device (base_task.py:41).
        new_tensor = getattr(self.native.obs_buf, "new_tensor", None)
        native_actions = new_tensor(rows) if callable(new_tensor) else rows
        count = int(ticks)
        if count < 1 or count > MAX_TICKS:
            # The class schema normally refuses this before the driver; keep a direct call honest.
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               f"ticks must be between 1 and {MAX_TICKS}, got {count}")
        for _ in range(count):
            self.check_cancelled()
            result = self.native.step(native_actions)
            if not isinstance(result, (tuple, list)) or len(result) < 5:
                raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID",
                                   "LeggedRobot.step did not return the five-tuple "
                                   "(obs_buf, privileged_obs_buf, rew_buf, reset_buf, extras)")
            obs, privileged, rewards, reset_buf, extras = result[:5]
            self._tick += 1
            self._last_observation = self._observation_from(obs, privileged, rewards, reset_buf,
                                                            self.native.time_out_buf, self.native.episode_length_buf,
                                                            extras)
        observation = self._last_observation
        output = {
            "observation": observation,
            "tick": self._tick,
            "state_hash": canonical.digest({"observation": observation, "tick": self._tick,
                                            "episode": self._episode}),
        }
        if int(self.native.num_envs) == 1:
            output["reward"] = float(observation["rewards"][0])
            output["terminated"] = bool(observation["terminated"][0])
            output["truncated"] = bool(observation["truncated"][0])
        return output

    @action(cap="cap.world.reset.v1",
            description="Reset every simulated environment to the go2 start state and return the initial "
                        "observation",
            input={
                "options": Field("object",
                                 description="Environment-specific reset options; the upstream reset takes none, "
                                             "so this object is accepted and ignored"),
            })
    def reset_world(self, options=None):
        if options is not None and not isinstance(options, Mapping):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "options must be an object")
        result = self.native.reset()
        if not isinstance(result, (tuple, list)) or len(result) < 2:
            raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID",
                               "LeggedRobot.reset did not return (observation, privileged_observation)")
        obs, privileged = result[:2]
        self._tick = 0
        self._episode += 1
        self._last_observation = self._observation_from(obs, privileged, self.native.rew_buf,
                                                        self.native.reset_buf, self.native.time_out_buf,
                                                        self.native.episode_length_buf, self.native.extras)
        return {"observation": self._last_observation, "seed": 0}

    # -- shared conversion (fake and sim backends) ----------------------------------------------------------
    def _native_actions(self, action):
        """Convert the JSON action object to the native ``(num_envs, num_actions)`` row-major list."""
        num_envs, num_actions = int(self.native.num_envs), int(self.native.num_actions)
        if not isinstance(action, Mapping):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "action must be an object with a values member")
        if set(action) != {"values"}:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               f"action accepts only the values member, got {sorted(map(str, action))}")
        values = action["values"]
        if not isinstance(values, (list, tuple)) or isinstance(values, (str, bytes)):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action.values must be an array")
        rows = list(values)
        if not rows:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action.values must not be empty")
        nested = isinstance(rows[0], (list, tuple))
        if nested:
            if len(rows) != num_envs:
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                                   f"action.values has {len(rows)} rows but the world has {num_envs} "
                                   f"environments")
            converted = [self._action_row(row, index, num_actions) for index, row in enumerate(rows)]
        else:
            vector = self._action_row(rows, 0, num_actions)
            converted = [list(vector) for _ in range(num_envs)]
        return converted

    @staticmethod
    def _action_row(row, index, num_actions):
        if not isinstance(row, (list, tuple)) or isinstance(row, (str, bytes)):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               f"action.values[{index}] must be an array of {num_actions} numbers")
        if len(row) != num_actions:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               f"action.values[{index}] has {len(row)} values but the world has {num_actions} "
                               f"actions")
        out = []
        for position, value in enumerate(row):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                                   f"action.values[{index}][{position}] is not a number")
            number = float(value)
            if number != number or number in (float("inf"), float("-inf")):
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                                   f"action.values[{index}][{position}] is not finite")
            out.append(number)
        return out

    def _observation_from(self, obs, privileged, rewards, reset_buf, time_out_buf, episode_length_buf, extras):
        """Convert native tensors/lists of the five-tuple into the per-agent observation document."""
        num_envs = int(self.native.num_envs)
        num_actions = int(self.native.num_actions)
        num_obs = int(self.native.num_obs)
        observations = self._matrix(obs, num_envs, num_obs, "obs_buf")
        if privileged is None:
            privileged_obs = None
        else:
            privileged_obs = self._matrix(privileged, num_envs, int(self.native.num_privileged_obs),
                                          "privileged_obs_buf")
        reward_values = self._vector(rewards, num_envs, "rew_buf")
        terminal = self._flags(reset_buf, num_envs, "reset_buf")
        timeout = self._flags(time_out_buf, num_envs, "time_out_buf")
        episodes = [int(value) for value in self._vector(episode_length_buf, num_envs, "episode_length_buf")]
        terminated = [bool(done and not timed_out) for done, timed_out in zip(terminal, timeout)]
        truncated = [bool(timed_out) for timed_out in timeout]
        return {
            "num_envs": num_envs,
            "num_actions": num_actions,
            "num_observations": num_obs,
            "obs": observations,
            "privileged_obs": privileged_obs,
            "rewards": [float(value) for value in reward_values],
            "terminated": terminated,
            "truncated": truncated,
            "episode_lengths": episodes,
            "extras": _jsonable(extras, "extras"),
        }

    @staticmethod
    def _matrix(value, rows, columns, label):
        data = _jsonable(value, label)
        if rows == 1 and isinstance(data, list) and len(data) == columns and \
                all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in data):
            data = [data]
        if not isinstance(data, list) or len(data) != rows:
            raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID",
                               f"{label} does not have {rows} rows")
        out = []
        for index, row in enumerate(data):
            if not isinstance(row, list) or len(row) != columns:
                raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID",
                                   f"{label}[{index}] does not have {columns} values")
            out.append([_number(item, f"{label}[{index}]") for item in row])
        return out

    @staticmethod
    def _vector(value, length, label):
        data = _jsonable(value, label)
        if length == 1 and isinstance(data, (int, float)) and not isinstance(data, bool):
            data = [data]
        if not isinstance(data, list) or len(data) != length:
            raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID",
                               f"{label} does not have {length} values")
        return data

    @staticmethod
    def _flags(value, length, label):
        values = UnitreeGo2._vector(value, length, label)
        if any(type(item) not in (bool, int) or item not in (0, 1) for item in values):
            raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", f"{label} contains a missing or invalid flag")
        return [bool(item) for item in values]


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", f"{label} contains a non-numeric value")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", f"{label} contains a non-finite value")
    return number


def _jsonable(value, label):
    """Convert a native tensor, numpy array or JSON-shaped value to JSON-shaped Python data."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item, f"{label}.{key}") for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item, f"{label}[{index}]") for index, item in enumerate(value)]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            return _jsonable(tolist(), label)
        except Exception as exc:  # noqa: BLE001 - a native array that cannot be converted is an output failure
            raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID",
                               f"{label} cannot be converted from its native array ({type(exc).__name__})") from exc
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _jsonable(item(), label)
        except Exception as exc:  # noqa: BLE001 - a native scalar that cannot be converted is an output failure
            raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID",
                               f"{label} cannot be converted from its native scalar ({type(exc).__name__})") from exc
    raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID",
                       f"{label} contains a {type(value).__name__}, which is not JSON")


# ---------------------------------------------------------------------------
# sim backend factory (not run by the gate)
# ---------------------------------------------------------------------------

def make_env(task="go2", num_envs=1, seed=1, sim_device="cuda:0", headless=True, **options):
    """Build the registered Go2 ``LeggedRobot`` environment through the clone's task registry.

    This is the production simulator factory named by ``backends["sim"]``.  It mirrors
    ``task_registry.make_env`` (``legged_gym/utils/task_registry.py:54-73``) without its ``get_args()``
    call: it fetches the registered Go2 config, overrides only the number of parallel environments,
    applies the config seed with the upstream ``set_seed`` before construction, builds the Isaac Gym
    ``SimParams`` from the config's ``sim`` section, and instantiates the card's ``LeggedRobot`` class
    directly.  It was not run in this acceptance run: it needs the installed upstream package,
    isaacgym and torch (``setup.py:11``).

    Options: ``task`` (only ``"go2"`` is served), ``num_envs`` (upstream base default 4096; the MHS
    default is 1 so a receipt is small), ``seed``, ``sim_device`` (``"cuda:0"`` or ``"cpu"``),
    ``headless`` (must be True), and ``use_gpu`` / ``use_gpu_pipeline`` / ``subscenes`` for ``SimParams``.  Any other
    option is ignored.
    """
    if task != "go2":
        raise ValueError(f"this package serves the go2 task; got {task!r}")
    if int(num_envs) < 1:
        raise ValueError("num_envs must be at least 1")
    if headless is not True:
        raise ValueError("this in-process backend requires headless=True; the upstream viewer can exit the host")

    import isaacgym  # noqa: F401 - the upstream package imports it before its envs
    from isaacgym import gymapi, gymutil

    import legged_gym.envs  # noqa: F401 - imports and registers the go2, h1, h1_2 and g1 tasks
    from legged_gym.envs.base.legged_robot import LeggedRobot
    from legged_gym.utils.helpers import class_to_dict, set_seed
    from legged_gym.utils.task_registry import task_registry

    env_cfg, _train_cfg = task_registry.get_cfgs("go2")
    env_cfg.env.num_envs = int(num_envs)
    set_seed(int(seed))

    gpu = bool(options.get("use_gpu", str(sim_device).startswith("cuda")))
    sim_params = gymapi.SimParams()
    sim_params.physx.use_gpu = gpu
    sim_params.physx.num_subscenes = int(options.get("subscenes", 0))
    sim_params.use_gpu_pipeline = bool(options.get("use_gpu_pipeline", gpu))
    gymutil.parse_sim_config(class_to_dict(env_cfg.sim), sim_params)
    return LeggedRobot(cfg=env_cfg, sim_params=sim_params, physics_engine=gymapi.SIM_PHYSX,
                       sim_device=str(sim_device), headless=bool(headless))
