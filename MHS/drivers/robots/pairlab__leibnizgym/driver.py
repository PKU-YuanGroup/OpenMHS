"""OpenMHS driver for gh.pairlab/leibnizgym: the TriFinger IsaacGym environment.

The card proposes the Gymnasium family, but the upstream entry class is not a Gymnasium environment: ``TrifingerEnv``
derives from the repository's own ``IsaacEnvBase`` and exposes no ``action_space``, no ``observation_space`` and no
``env_id`` (``leibnizgym/envs/trifinger/trifinger_env.py:118``, ``leibnizgym/envs/env_base.py:79``).  A
``GymnasiumDriver`` derives the whole contract from those spaces, so that shape cannot express this interface.  This
package is therefore a direct ``Driver`` over the upstream class (see RESULT.json, "DEVIATION FROM THE CARD").

The bound capabilities are ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1``.  A step takes the
catalogue ``ticks`` count and a nine-value normalized action (the wrapper's action space is Box(-1, 1), and the
environment denormalizes the action from [-1, 1] before computing the joint command).  A reset calls
``TrifingerEnv.reset()`` and returns its observation row.  The seed capability calls the upstream static ``seed``
method, which seeds Python's ``random``, NumPy and PyTorch.  The environment auto-resets an instance when the episode
length is reached, but this driver surfaces that as ``truncated`` and requires an explicit reset, as the other world
drivers do.

The device is simulated (R0): there is no hardware backend and no operator-required limit.  The fake backend
(``fake.py``) is this package's pure Python stand-in; it was not compared with the upstream environment (IsaacGym,
PyTorch and the TriFinger assets were not run where the gate ran).  This package is model-authored and unreviewed, and
is checked on the fake backend only.
"""

from collections.abc import Mapping

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, read

TRIFINGER = "leibnizgym/envs/trifinger/trifinger_env.py"
ENV_BASE = "leibnizgym/envs/env_base.py"
WRAPPER = "leibnizgym/wrappers/vec_task.py"
DIMS = "leibnizgym/envs/trifinger/utils.py"
README = "README.md"
SETUP = "setup.py"

#: The action is a nine-value normalized joint command (``action_dim`` of the default position mode).
ACTION_DIM = 9
#: The observation is robot_q (9), robot_u (9), object_q (7), object_q_des (7) and command (9).
OBSERVATION_DIM = 41
#: ``TRIFINGER_DEFAULT_CONFIG_DICT["episode_length"]``.
EPISODE_LENGTH = 750
#: ``ISAACGYM_DEFAULT_CONFIG_DICT["sim"]["dt"]`` times ``control_decimation``.
TIMESTEP_MS = 20.0


def _plain_scalar(value):
    """One Python scalar from a native reward or done buffer (a tensor, a one-element list or a scalar)."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    if isinstance(value, (list, tuple)):
        value = value[0] if value else 0
    return value


def _observation_row(value) -> dict:
    """The observation of the first environment instance as a JSON object with the flat 41-value row."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
        value = value[0]
    if isinstance(value, Mapping):
        flat = []
        for item in value.values():
            if hasattr(item, "tolist"):
                item = item.tolist()
            if isinstance(item, (list, tuple)):
                flat.extend(float(element) for element in item)
            else:
                flat.append(float(item))
        return {"values": flat}
    if isinstance(value, (list, tuple)):
        return {"values": [float(item) for item in value]}
    return {"values": [float(value)]}


def _action_array(values):
    """The native action: an array of shape [1, action_dim], as ``IsaacEnvBase.step`` expects (env_base.py:360-365)."""
    try:
        import numpy as np
    except ImportError:  # the upstream needs NumPy as well; the fake accepts a plain list
        return [list(values)]
    return np.asarray(list(values), dtype=np.float32).reshape(1, len(values))


def _action_values(action) -> list:
    if not isinstance(action, Mapping):
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action must be an object")
    values = action.get("values")
    if not isinstance(values, (list, tuple)):
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action.values must be an array")
    if len(values) != ACTION_DIM:
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                           f"action.values must have {ACTION_DIM} values, got {len(values)}")
    return [float(value) for value in values]


class LeibnizTrifinger(Driver):
    device_id = "trifinger"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "leibnizgym.envs.trifinger.trifinger_env:TrifingerEnv"
    backends = {"fake": ".fake:FakeTrifingerEnv"}
    display_name = "LeibnizGym TriFinger IsaacGym environment"
    vendor, model = "PAIR Lab", "leibnizgym TriFinger"
    tags = ["trifinger", "isaacgym", "robot", "simulation", "reinforcement-learning"]
    facts = [
        Fact("TrifingerEnv is the concrete IsaacGym environment for the three-finger TriFinger robot",
             source="upstream_code", ref=f"{TRIFINGER}:118"),
        Fact("TrifingerEnv derives from IsaacEnvBase, the repository's own base class, not from gym.Env or "
             "gymnasium.Env", source="upstream_code", ref=f"{ENV_BASE}:79"),
        Fact("The default configuration sets episode_length to 750, command_mode to position, normalize_action to "
             "true and the object initial state to random", source="upstream_code", ref=f"{TRIFINGER}:30-66"),
        Fact("The robot has three fingers with three joints each, so the joint position, joint velocity and joint "
             "torque dimensions are 9", source="upstream_code", ref=f"{DIMS}:35-39"),
        Fact("The joint position limits are [-0.33, 0.0, -2.7] to [1.0, 1.57, 0.0] per finger, the joint velocity "
             "limit is 10 rad/s and the maximum joint torque is 0.36 N m", source="upstream_code",
             ref=f"{TRIFINGER}:149-167"),
        Fact("The comment on normalize_action says the action is denormalized from [-1, 1], and the default value "
             "is true", source="upstream_code", ref=f"{TRIFINGER}:45-46"),
        Fact("The VecTask wrapper builds the action space as Box(-clip_actions, clip_actions) with clip_actions "
             "1.0", source="upstream_code", ref=f"{WRAPPER}:34-56"),
        Fact("step takes an action tensor of shape [num_instances, action_dim] and returns observation, reward, "
             "termination and info buffers", source="upstream_code", ref=f"{ENV_BASE}:345-400"),
        Fact("step resets the instances whose reset flag is set before applying the action, and sets that flag when "
             "the step count reaches episode_length", source="upstream_code", ref=f"{ENV_BASE}:373-395"),
        Fact("reset returns the observation tensor [num_instances, obs_dim]", source="upstream_code",
             ref=f"{ENV_BASE}:322-343"),
        Fact("The observation spec is robot_q 9, robot_u 9, object_q 7, object_q_des 7 and command 9, 41 values in "
             "total for the default action dimension", source="upstream_code", ref=f"{TRIFINGER}:280-286"),
        Fact("seed sets Python's random, NumPy and PyTorch seeds", source="upstream_code", ref=f"{ENV_BASE}:312-320"),
        Fact("The constructor seeds the environment from its config, whose default seed is 0", source="upstream_code",
             ref=f"{ENV_BASE}:169"),
        Fact("The default physics timestep is 0.02 s and control_decimation is 1, so one environment step advances "
             "0.02 s", source="upstream_code", ref=f"{ENV_BASE}:38-49"),
        Fact("TrifingerEnv.__init__ takes config, device, verbose and visualize", source="upstream_code",
             ref=f"{TRIFINGER}:258"),
        Fact("The README states that the repository provides an IsaacGym environment for the TriFinger robot and "
             "that it supports IsaacGym Preview Release 2", source="vendor_doc", ref=f"{README}:7-17"),
        Fact("The install requirements list numpy, scipy, gym, torch, hydra-core and rl_games, with no serial, VISA, "
             "USB or vendor hardware package", source="upstream_code", ref=f"{SETUP}:12-28"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation and tick stay readable")
    #: The model as deployed: an IsaacGym rigid-body simulation at the default configuration.
    fidelity = {
        "engine": "isaacgym:TrifingerEnv",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "TrifingerEnv.seed(seed) seeds Python's random, NumPy and PyTorch (env_base.py:312-320), and "
                     "the default reset draws the object pose and goal from those generators (trifinger_env.py:66); "
                     "the fake uses Python's random.Random and was never compared with the upstream environment",
        },
        "timestep_ms": TIMESTEP_MS,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a pure Python stand-in: it models the tick, a placeholder nine-value joint offset "
            "and a placeholder 41-value observation row, but no IsaacGym, PhysX, rigid-body dynamics, contacts, "
            "actuators or sensors, and it was never compared with the upstream environment",
            "one cap.world.step.v1 tick is one TrifingerEnv.step call, which runs control_decimation physics steps "
            "(env_base.py:382-384); with the default control_decimation 1 and dt 0.02 s that is 20 ms per tick",
            "the upstream is vectorized ([num_instances, obs_dim]); the fake models one instance and the driver "
            "returns its first observation row, so a configured num_instances above 1 is not exposed",
            "only the default configuration is modelled (position command mode, normalized action, episode length "
            "750); torque and position_impedance modes, asymmetric observations, force-torque sensors and rendering "
            "are not modelled",
            "the upstream environment auto-resets an instance at episode_length (env_base.py:392-395); the driver "
            "reports truncated at 750 ticks and requires an explicit reset instead of continuing",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
            "the real environment needs IsaacGym Preview Release 2, PyTorch and a config dict (README.md:7-17, "
            "trifinger_env.py:258-277); it was not installed or run where the gate ran",
            "no physical device is modelled and nothing was validated against one",
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

    def teardown(self) -> None:
        self.native.close()

    # ------------------------------------------------------------------ state
    @read("observation", type="object",
          description="Last observation of the simulation (the first instance's 41-value row)")
    def observation(self) -> dict:
        return dict(getattr(self, "_last_observation", {}))

    @read("reward", type="number", unit="1", description="Reward of the last step")
    def reward(self) -> float:
        return float(getattr(self, "_reward", 0.0))

    @read("terminated", type="boolean", description="Whether the last step reached a terminal state")
    def terminated(self) -> bool:
        return bool(getattr(self, "_terminated", False))

    @read("truncated", type="boolean", description="Whether the last step reached the episode length")
    def truncated(self) -> bool:
        return bool(getattr(self, "_truncated", False))

    @read("tick", type="integer", unit="1", description="Environment steps applied since the last reset")
    def tick(self) -> int:
        return int(getattr(self, "_tick", 0))

    @read("episode", type="integer", unit="1", description="Resets served by this backend")
    def episode(self) -> int:
        return int(getattr(self, "_episode", 0))

    @read("seed", type="integer", unit="1", description="Seed applied by the last seed or reset")
    def seed(self) -> int:
        value = getattr(self, "_seed", None)
        return int(value) if value is not None else 0

    @read("info", type="object", description="Task information returned by the last step")
    def info(self) -> dict:
        return dict(getattr(self, "_info", {}))

    # ---------------------------------------------------------------- actions
    @action(cap="cap.world.step.v1",
            description="Advance the TriFinger simulation by bounded steps with one normalized joint command",
            input={
                "ticks": Field("integer", unit="1",
                               description="Environment steps to advance; the action is applied at every step"),
                "action": Field("object", description="Normalized nine-value joint command",
                                properties={
                                    "values": Field("array", items="number", length=ACTION_DIM, unit="1",
                                                    description="Normalized joint command, one value per joint",
                                                    limit=Limit(min=-1.0, max=1.0, unit="1",
                                                                source="upstream_code",
                                                                ref=f"{TRIFINGER}:654-659")),
                                }),
            })
    def step(self, ticks: int, action: dict) -> dict:
        if self._terminated or self._truncated:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the episode has ended; reset the environment before stepping")
        if not isinstance(ticks, int) or isinstance(ticks, bool) or ticks < 1:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "ticks must be a positive integer")
        values = _action_values(action)
        total_reward = 0.0
        for _ in range(ticks):
            self.check_cancelled()
            result = self.native.step(_action_array(values))
            try:
                observation, reward, terminated, truncated, info = result
            except (TypeError, ValueError):
                observation, reward, done, info = result
                terminated, truncated = done, False
            self._tick += 1
            self._last_observation = _observation_row(observation)
            self._reward = float(_plain_scalar(reward))
            total_reward += self._reward
            self._terminated = bool(_plain_scalar(terminated))
            self._truncated = bool(_plain_scalar(truncated)) or self._tick >= EPISODE_LENGTH
            self._info = dict(info or {}) if isinstance(info, Mapping) else {"info": info}
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
            description="Reset the TriFinger scene and return its initial observation",
            input={
                "seed": Field("integer", unit="1", required=False,
                              description="Seed applied before the reset; the pending or last seed is used when "
                                          "omitted"),
                "scenario": Field("string", required=False,
                                  description="Named scenario; only 'default' is served"),
                "options": Field("object", required=False,
                                 description="Reset options; the upstream reset takes none and they are ignored"),
            })
    def reset_world(self, seed=None, scenario=None, options=None) -> dict:
        if scenario not in (None, "default"):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "only the 'default' scenario is served")
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "seed must be a non-negative integer")
        chosen = seed if seed is not None else self._pending_seed
        self._pending_seed = None
        if chosen is not None:
            self.native.seed(int(chosen))
            self._seed = int(chosen)
        observation = self.native.reset()
        self._tick = 0
        self._episode += 1
        self._reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_observation = _observation_row(observation)
        self._info = {}
        return {"observation": dict(self._last_observation),
                "seed": int(self._seed) if self._seed is not None else 0}

    @action(cap="cap.world.seed.v1",
            description="Seed the environment generators without resetting it",
            input={"seed": Field("integer", unit="1", description="Seed used by the next reset")})
    def set_seed(self, seed: int) -> dict:
        chosen = int(seed)
        if chosen < 0:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "seed must be a non-negative integer")
        self.native.seed(chosen)
        self._seed = chosen
        self._pending_seed = chosen
        return {"seed": chosen, "accepted": True}
