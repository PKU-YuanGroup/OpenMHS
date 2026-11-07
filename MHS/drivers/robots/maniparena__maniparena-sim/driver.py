"""OpenMHS driver for gh.maniparena/maniparena-sim: the ManipArena simulated robot environment.

The card proposes a ``GymnasiumDriver`` family-config, but the clone has no registered Gymnasium id and no environment
class of its own: ``build_sdk_ros2_gym_env`` is a builder function that returns a ``(gym_env, embodiment)`` pair
(src/maniparena_sim/environment/sdk_builder.py:106-107), and the only in-tree environment wrapper is
``AssembledEnvironment``, whose ``build_gym_environment`` calls ``gym.make`` on a name that
``IsaacLabArenaEnvironment`` registers at composition time (assembled_environment.py:17 and :103).  A GymnasiumDriver
is configuration only and derives the whole contract from ``env_id`` and the spaces, so it cannot name this
environment from configuration alone.  This package is therefore a direct ``Driver`` over the clone's
``AssembledEnvironment`` class (the card's second entry symbol) with the package fake backend; see RESULT.json,
"DEVIATION FROM THE CARD".

The world contract is the catalogue's: ``cap.world.step.v1`` takes ``ticks`` and an action object whose ``values`` is
the flat action vector of the configured embodiment, ``cap.world.reset.v1`` takes an optional seed/scenario/options,
and ``cap.world.seed.v1`` records the seed used by the next reset.  The action width is not fixed by the clone: the
SDK selects one of quanta_x1, quanta_x2 and artixon_arm_6a (sdk_builder.py:11) and either Cartesian or joint arm
control (README.md:91), so the driver validates the vector against the live environment's action space instead of
inventing a catalogue bound.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The fake is a pure Python kinematic stand-in because the real stack needs Isaac Sim 6.x wheels, Isaac Lab,
IsaacLab-Arena, Linux and an NVIDIA GPU (README.md:36-44; docs/install.md:13), none of which was installed or run here.
This package is model-authored and unreviewed and is checked on the fake backend only; its evidence is
``contract_checked``, never an MHS-Device level and never a hardware run.
"""

from collections.abc import Mapping

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, action, read

SDK_BUILDER = "src/maniparena_sim/environment/sdk_builder.py"
ASSEMBLED = "src/maniparena_sim/environment/assembled_environment.py"
SDK_LAUNCHER = "scripts/sdk_ros2.py"
EVAL_LOOP = "scripts/eval.py"
README = "README.md"
DOCS_INSTALL = "docs/install.md"
DOCS_QUANTA_X2 = "docs/quanta_x2_sdk.md"
DOCS_ARTIXON = "docs/artixon_arm_6a_sdk.md"
PYPROJECT = "pyproject.toml"


def _plain(value):
    """A JSON value from a native observation element (a tensor, an array, a scalar or a nested list)."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return value
    return str(value)


def _scalar(value):
    """One scalar from a native reward or flag (a one-element tensor, list or scalar)."""
    value = _plain(value)
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    if isinstance(value, list):
        value = value[0] if value else 0
    return value


def _observation_row(value) -> dict:
    """The environment observation as a JSON object; a group of the upstream observation Dict stays a list."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    return {"values": _plain(value)}


def _action_values(action) -> list:
    """The flat action vector from the catalogue action object ``{values: [...]}``."""
    if not isinstance(action, Mapping):
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action must be an object with a values array")
    values = action.get("values")
    if not isinstance(values, (list, tuple)):
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action.values must be an array")
    out = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action.values must contain only numbers")
        out.append(float(value))
    return out


def _action_shape(env) -> int | None:
    """The flat width of the environment's action space, when it publishes one."""
    space = getattr(env, "action_space", None)
    shape = getattr(space, "shape", None)
    if not isinstance(shape, (tuple, list)) or not shape:
        return None
    width = 1
    for part in shape:
        if isinstance(part, bool) or not isinstance(part, int) or part < 1:
            return None
        width *= part
    return width


def _native_action(env, values: list):
    """The native step argument: a batched tensor for an Isaac Lab environment, a plain list for the fake."""
    if getattr(env, "device", None) is not None and getattr(env, "num_envs", None) is not None:
        try:
            import torch
        except ImportError:  # the fake and the gate never need torch
            return [list(values)]
        return torch.tensor([list(values)], dtype=torch.float32, device=env.device)
    return [list(values)]


def _step_tuple(value):
    """Unpack the Gymnasium five-tuple (or a legacy four-tuple) of ``env.step``."""
    try:
        observation, reward, terminated, truncated, info = value
    except (TypeError, ValueError):
        observation, reward, terminated, info = value
        truncated = False
    return observation, reward, terminated, truncated, info


class ManipArenaAssembly(Driver):
    """Direct driver over the clone's ``AssembledEnvironment`` (the card's confirmed class entry symbol)."""

    device_id = "maniparena-sim"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "maniparena_sim.environment.assembled_environment:AssembledEnvironment"
    backends = {"fake": ".fake:FakeAssembledEnvironment"}
    display_name = "ManipArena-Sim (Isaac Lab / IsaacLab-Arena bimanual simulation)"
    vendor, model = "ManipArena", "maniparena-sim"
    tags = ["bimanual", "manipulation", "isaac-sim", "isaac-lab", "isaaclab-arena", "simulation", "gymnasium"]
    facts = [
        Fact("ManipArena-Sim is the simulation environment for the ManipArena bimanual manipulation benchmark, "
             "built on Isaac Lab and IsaacLab-Arena", source="vendor_doc", ref=f"{README}:3"),
        Fact("SUPPORTED_SDK_ROBOTS lists quanta_x1, quanta_x2 and artixon_arm_6a", source="upstream_code",
             ref=f"{SDK_BUILDER}:11"),
        Fact("build_sdk_ros2_gym_env is documented to return (gym_env, embodiment) for the selected public SDK "
             "robot", source="upstream_code", ref=f"{SDK_BUILDER}:106-107"),
        Fact("The SDK ROS2 builder supports exactly one environment and raises when num_envs is not 1",
             source="upstream_code", ref=f"{SDK_BUILDER}:118-119"),
        Fact("sdk_simulation_timing defaults physics_dt to 1/120 s, decimation to 6 and render_interval to 2",
             source="upstream_code", ref=f"{SDK_BUILDER}:45-49"),
        Fact("The SDK builder assigns env_cfg.decimation = decimation before it makes the gym environment",
             source="upstream_code", ref=f"{SDK_BUILDER}:173"),
        Fact("AssembledEnvironment is documented to wrap a scene, an embodiment and a task into a lazily built gym "
             "environment", source="upstream_code", ref=f"{ASSEMBLED}:17-18"),
        Fact("build_gym_environment calls gym.make(env_name, cfg=env_cfg, **env_kwargs).unwrapped and returns that "
             "environment", source="upstream_code", ref=f"{ASSEMBLED}:103-109"),
        Fact("get_env builds the gym environment with build_gym_environment when it is not built yet and returns it",
             source="upstream_code", ref=f"{ASSEMBLED}:180-183"),
        Fact("The builder configuration defaults the seed to 42 when the caller supplies none",
             source="upstream_code", ref=f"{ASSEMBLED}:170"),
        Fact("The SDK launcher calls build_sdk_ros2_gym_env and then gym_env.reset()", source="upstream_code",
             ref=f"{SDK_LAUNCHER}:135-140"),
        Fact("The evaluation loop unpacks obs, _, terminated, truncated, _ = gym_env.step(actions), the Gymnasium "
             "five-tuple", source="upstream_code", ref=f"{EVAL_LOOP}:369-371"),
        Fact("The SDK runtime exposes robot state and either Cartesian or joint commands, without recording",
             source="vendor_doc", ref=f"{README}:91"),
        Fact("The desktop SDK uses the fruit tabletop scene with an empty task and has no automatic timeout or "
             "success reset", source="vendor_doc", ref=f"{README}:100-101"),
        Fact("The prerequisites are Ubuntu 22.04 or 24.04 with an NVIDIA GPU, Python 3.12, CUDA 12.8 and Isaac Sim "
             "6.x binary wheels", source="vendor_doc", ref=f"{README}:36-44"),
        Fact("The installer pins Isaac Sim to the wheels isaacsim[all,extscache]==6.0.1.0", source="vendor_doc",
             ref=f"{DOCS_INSTALL}:13"),
        Fact("The project dependencies are numpy, PyYAML, av, pyarrow, msgpack, msgpack-numpy and websockets, with "
             "no serial, VISA, USB or vendor hardware package", source="upstream_code", ref=f"{PYPROJECT}:11-19"),
        Fact("The quanta_x2 SDK guide states that ee is the default arm_control mode and that joint mode subscribes "
             "to joint commands instead", source="vendor_doc", ref=f"{DOCS_QUANTA_X2}:35"),
        Fact("The artixon SDK guide gives the per-arm joint order as left_arm_joint1..6 and right_arm_joint1..6 and "
             "the angle unit as radians", source="vendor_doc", ref=f"{DOCS_ARTIXON}:29"),
        Fact("The README states Apache License 2.0", source="vendor_doc", ref=f"{README}:258"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation and tick stay readable")
    #: The model as deployed (spec 05-fidelity section 2): a kinematic F0 stand-in, not the Isaac Sim physics.
    fidelity = {
        "engine": "maniparena_sim:AssembledEnvironment/gymnasium",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed=...) is forwarded to the Gymnasium environment and the fake seeds Python's "
                     "random.Random; the upstream builder passes the seed to IsaacLab-Arena and Isaac Lab, which "
                     "was not run, so a seed was never compared between the fake and the real simulator",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic F0 stand-in: no Isaac Sim physics, rigid bodies, contacts, actuators, sensors, noise or "
            "rendering; the fake advances one placeholder state coordinate per tick and claims no dynamics",
            "the real action space is the batched Box of the configured embodiment and arm_control mode (the SDK "
            "supports quanta_x1, quanta_x2 and artixon_arm_6a, Cartesian or joint control), so its width and bounds "
            "depend on the payload; the fake uses a twelve-value placeholder Box and the conformance fixture uses "
            "that width, while the driver validates the live environment's shape at run time and invents no bound",
            "the real observation is a Gymnasium Dict of observation-manager groups and camera images; the fake "
            "returns a four-value policy group only, so its arrays are smaller than the device's",
            "the upstream environment is vectorized over num_envs (the SDK builder accepts exactly one) while this "
            "driver exposes one environment; the real stack was not executed",
            "the upstream builder needs Isaac Sim 6.x wheels, Isaac Lab, IsaacLab-Arena, Linux and an NVIDIA GPU "
            "(README.md:36-44; docs/install.md:13); this package ships no sim backend and only the fake was run",
            "timestep_ms 50.0 is physics_dt 1/120 s times the default decimation 6 (src/maniparena_sim/environment/"
            "sdk_builder.py:45-49 and :173); a different simulation payload changes it",
            "snapshot and restore are not offered: the driver exposes no get_state/set_state",
            "no wall-clock pacing: realtime_factor 0 and clock lockstep",
        ],
    }

    # ------------------------------------------------------------------ hooks
    def setup(self) -> None:
        self._tick = 0
        self._episode = 0
        self._seed = None
        self._pending_seed = None
        self._reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_observation = {}
        self._info = {}
        self._env = self._require_env()

    def teardown(self) -> None:
        env = getattr(self, "_env", None)
        if env is not None and callable(getattr(env, "close", None)):
            env.close()

    def _require_env(self):
        """The built gym environment through the upstream ``get_env`` (which builds it lazily)."""
        env = self.native.get_env()
        if env is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "AssembledEnvironment.get_env() returned no environment")
        self._env = env
        return env

    # ------------------------------------------------------------------ state
    @read("observation", type="object", description="Observation returned by the last step or reset")
    def observation(self) -> dict:
        return dict(getattr(self, "_last_observation", {}))

    @read("reward", type="number", unit="1", description="Reward returned by the last step")
    def reward(self) -> float:
        return float(getattr(self, "_reward", 0.0))

    @read("terminated", type="boolean", description="Whether the last step reached a terminal state")
    def terminated(self) -> bool:
        return bool(getattr(self, "_terminated", False))

    @read("truncated", type="boolean", description="Whether the last step reached a truncation condition")
    def truncated(self) -> bool:
        return bool(getattr(self, "_truncated", False))

    @read("tick", type="integer", unit="1", description="Environment steps applied since the last reset")
    def tick(self) -> int:
        return int(getattr(self, "_tick", 0))

    @read("episode", type="integer", unit="1", description="Resets served by this backend")
    def episode(self) -> int:
        return int(getattr(self, "_episode", 0))

    @read("seed", type="integer", unit="1", description="Seed applied by the last reset (0 when none was applied)")
    def seed(self) -> int:
        value = getattr(self, "_seed", None)
        return int(value) if value is not None else 0

    @read("info", type="object", description="Information returned by the last step")
    def info(self) -> dict:
        return dict(getattr(self, "_info", {}))

    # ---------------------------------------------------------------- actions
    @action(cap="cap.world.step.v1",
            description="Advance the ManipArena simulation by bounded steps with one flat action vector",
            input={
                "ticks": Field("integer", unit="1",
                               description="Environment steps to advance; the action is applied at every step"),
                "action": Field("object",
                                description="Action object passed to the environment's action space",
                                properties={
                                    "values": Field("array", items="number", unit="1",
                                                    description="Flat action vector in the order of the live "
                                                                "environment's action space; its width is checked "
                                                                "against that space at run time"),
                                }),
            })
    def step(self, ticks: int, action: dict) -> dict:
        if not isinstance(ticks, int) or isinstance(ticks, bool) or ticks < 1:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "ticks must be a positive integer")
        if self._terminated or self._truncated:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the episode has ended; reset the environment before stepping")
        env = self._require_env()
        values = _action_values(action)
        width = _action_shape(env)
        if width is not None and len(values) != width:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               f"action.values has {len(values)} values but the environment action space has "
                               f"{width}; the payload selects the embodiment and control mode")
        total_reward = 0.0
        for _ in range(ticks):
            self.check_cancelled()
            observation, reward, terminated, truncated, info = _step_tuple(env.step(_native_action(env, values)))
            self._tick += 1
            self._last_observation = _observation_row(observation)
            self._reward = float(_scalar(reward) or 0.0)
            total_reward += self._reward
            self._terminated = bool(_scalar(terminated))
            self._truncated = bool(_scalar(truncated))
            self._info = dict(info or {}) if isinstance(info, Mapping) else {}
            if self._terminated or self._truncated:
                break
        return {
            "observation": dict(self._last_observation),
            "reward": total_reward,
            "terminated": bool(self._terminated),
            "truncated": bool(self._truncated),
            "tick": int(self._tick),
            "state_hash": canonical.digest({
                "observation": self._last_observation,
                "tick": int(self._tick),
                "episode": int(self._episode),
                "terminated": bool(self._terminated),
                "truncated": bool(self._truncated),
                "seed": int(self._seed) if self._seed is not None else None,
            }),
        }

    @action(cap="cap.world.reset.v1",
            description="Reset the ManipArena environment and return its initial observation",
            input={
                "seed": Field("integer", unit="1", required=False,
                              description="Seed forwarded to the environment's reset; the pending seed is used "
                                          "when omitted"),
                "scenario": Field("string", required=False,
                                  description="Named scenario; only 'default' is served"),
                "options": Field("object", required=False,
                                 description="Reset options forwarded to the environment's reset"),
            })
    def reset_world(self, seed=None, scenario=None, options=None) -> dict:
        if scenario not in (None, "default"):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "only the 'default' scenario is served")
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "seed must be a non-negative integer")
        env = self._require_env()
        chosen = seed
        if chosen is None:
            chosen = self._pending_seed
            self._pending_seed = None
        kwargs = {}
        if chosen is not None:
            kwargs["seed"] = int(chosen)
        if options is not None:
            if not isinstance(options, Mapping):
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "options must be an object")
            kwargs["options"] = dict(options)
        result = env.reset(**kwargs)
        if isinstance(result, tuple) and len(result) == 2:
            observation, _info = result
        else:
            observation, _info = result, {}
        self._tick = 0
        self._episode += 1
        self._reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_observation = _observation_row(observation)
        self._info = dict(_info or {}) if isinstance(_info, Mapping) else {}
        if chosen is not None:
            self._seed = int(chosen)
        return {"observation": dict(self._last_observation),
                "seed": int(self._seed) if self._seed is not None else 0}

    @action(cap="cap.world.seed.v1",
            description="Record the seed that the next reset applies",
            input={"seed": Field("integer", unit="1", description="Seed used by the next reset")})
    def set_seed(self, seed: int) -> dict:
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "seed must be a non-negative integer")
        self._require_env()
        self._pending_seed = int(seed)
        return {"seed": int(seed), "accepted": True}
