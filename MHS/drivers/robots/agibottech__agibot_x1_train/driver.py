"""OpenMHS driver for gh.agibottech/agibot_x1_train: the X1DHStandEnv Isaac Gym training environment.

The upstream is the reinforcement-learning training code for the AgiBot X1 humanoid (README.md:5).  The card's
entry class ``humanoid.envs.x1.x1_dh_stand_env:X1DHStandEnv`` is a concrete ``LeggedRobot`` subclass
(x1_dh_stand_env.py:79) registered as ``x1_dh_stand`` through the repository's own ``task_registry``
(humanoid/envs/__init__.py:43), not through ``gym.register``.  It is therefore not a Gymnasium environment: it has no
``action_space`` or ``observation_space``, ``reset()`` takes no seed and returns ``(obs, privileged_obs)``
(legged_robot.py:157-162), and ``step(actions)`` takes a ``(num_envs, num_actions)`` tensor and returns
``(obs_buf, privileged_obs_buf, rew_buf, reset_buf, extras)`` (legged_robot.py:111-155).  A ``GymnasiumDriver``
would have to invent the spaces and the reset/step signature, so this package is a direct ``Driver`` over the
upstream class.  See RESULT.json, "DEVIATION FROM THE CARD".

The package serves the shipped ``X1DHStandCfg`` for one environment (the training config uses 4096,
x1_dh_stand_config.py:50; MHS serves one world).  The bound capabilities are ``cap.world.step.v1`` and
``cap.world.reset.v1``.  A step takes the catalogue ``ticks`` plus an ``action`` object with 12 ``values`` (the
number of actions of the config, x1_dh_stand_config.py:49); the driver applies the same action at every tick and
calls the fake's ``step`` once per tick. The upstream clips actions using ``clip_actions=100``; the package
requires an operator action envelope because the cited configuration alone does not state both endpoints.
A reset calls ``X1DHStandEnv.reset``; the environment has no integer seed or state snapshot, so the reset output's
required ``seed`` is 0 and ``cap.world.seed.v1`` is deliberately not bound.

The environment needs Isaac Gym, torch and a GPU (x1_dh_stand_env.py:35-40; setup.py:44-50).  Package code never
imports the clone, and this package has only the fake backend; no upstream or hardware backend was run.  The fake
is a pure-Python stand-in whose values are placeholders, not a physics simulation.  This package is model-authored
and unreviewed.
"""

from collections.abc import Mapping
import math

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, read

ENV = "humanoid/envs/x1/x1_dh_stand_env.py"
BASE = "humanoid/envs/base/legged_robot.py"
CONFIG = "humanoid/envs/x1/x1_dh_stand_config.py"
SETUP = "setup.py"
README = "README.md"

#: The shipped configuration's observation and action sizes (x1_dh_stand_config.py:41-49).
OBSERVATION_SIZE = 66 * 47          # frame_stack * num_single_obs = 3102
PRIVILEGED_OBSERVATION_SIZE = 3 * 73  # c_frame_stack * single_num_privileged_obs = 219
ACTION_SIZE = 12                    # num_actions

def _flatten(value) -> list:
    """A flat list of floats from a torch tensor, a nested sequence or a scalar sequence."""
    if hasattr(value, "detach"):
        value = value.detach().cpu().reshape(-1).tolist()
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
        value = [item for row in value for item in row]
    return [float(item) for item in value]


def _scalar(value) -> float:
    """The first value of a tensor or sequence (each upstream buffer has one entry per environment)."""
    if hasattr(value, "detach"):
        value = value.detach().cpu().reshape(-1).tolist()
    if isinstance(value, (list, tuple)):
        value = value[0]
    scalar = float(value)
    if not math.isfinite(scalar):
        raise ValueError("the native scalar is not finite")
    return scalar


class X1DHStand(Driver):
    device_id = "x1-dh-stand"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "humanoid.envs.x1.x1_dh_stand_env:X1DHStandEnv"
    backends = {"fake": ".fake:FakeX1DHStandEnv"}
    display_name = "AgiBot X1 DH stand training environment (X1DHStandEnv)"
    vendor, model = "agibottech", "agibot_x1_train (x1_dh_stand)"
    tags = ["humanoid", "x1", "isaac-gym", "reinforcement-learning", "simulation", "locomotion", "stand"]
    facts = [
        Fact("X1DHStandEnv is a LeggedRobot subclass", source="upstream_code",
             ref=f"{ENV}:79"),
        Fact("X1DHStandEnv.step adds the reference action when cfg.env.use_ref_actions is set, then calls "
             "LeggedRobot.step", source="upstream_code", ref=f"{ENV}:353-356"),
        Fact("LeggedRobot.step clips actions to +-cfg.normalization.clip_actions, simulates "
             "cfg.control.decimation physics substeps and returns (obs_buf, privileged_obs_buf, rew_buf, "
             "reset_buf, extras)", source="upstream_code", ref=f"{BASE}:111-155"),
        Fact("LeggedRobot.reset takes no arguments, resets every environment, steps zero actions and returns "
             "(obs, privileged_obs)", source="upstream_code", ref=f"{BASE}:157-162"),
        Fact("LeggedRobot.check_termination combines termination contacts, the episode time-out and the roll and "
             "pitch cutoffs of 1.5 rad into one reset flag", source="upstream_code", ref=f"{BASE}:206-217"),
        Fact("X1DHStandCfg.env sets frame_stack=66, num_single_obs=47 and num_observations=3102",
             source="upstream_code", ref=f"{CONFIG}:41-45"),
        Fact("X1DHStandCfg.env sets c_frame_stack=3, single_num_privileged_obs=73 and num_privileged_obs=219",
             source="upstream_code", ref=f"{CONFIG}:43-48"),
        Fact("X1DHStandCfg.env sets num_actions=12", source="upstream_code", ref=f"{CONFIG}:49"),
        Fact("X1DHStandCfg.env sets num_envs=4096 for training", source="upstream_code", ref=f"{CONFIG}:50"),
        Fact("X1DHStandCfg.control sets action_scale=0.5 and decimation=10, and X1DHStandCfg.sim sets dt=0.001 s",
             source="upstream_code", ref=f"{CONFIG}:153-158"),
        Fact("X1DHStandCfg.init_state lists the 12 default joint angles in radians", source="upstream_code",
             ref=f"{CONFIG}:128-141"),
        Fact("X1DHStandCfg.asset selects the MuJoCo scene resources/robots/x1/mjcf/xyber_x1_flat.xml",
             source="upstream_code", ref=f"{CONFIG}:64"),
        Fact("X1DHStandCfg.normalization sets clip_actions=100 and clip_observations=100",
             source="upstream_code", ref=f"{CONFIG}:366-367"),
        Fact("X1DHStandCfgPPO sets the PPO training seed to 5", source="upstream_code",
             ref=f"{CONFIG}:370-371"),
        Fact("The environment imports isaacgym and torch", source="upstream_code", ref=f"{ENV}:35-40"),
        Fact("setup.py install_requires lists isaacgym, mujoco==2.3.6 and mujoco-python-viewer",
             source="upstream_code", ref=f"{SETUP}:44-50"),
        Fact("The README says the repository is the reinforcement-learning training code for AgiBot X1, used with "
             "separate inference software for real-robot and simulated walking", source="vendor_doc",
             ref=f"{README}:5"),
        Fact("The README documents MuJoCo sim2sim validation with scripts/sim2sim.py --task=x1_dh_stand",
             source="vendor_doc", ref=f"{README}:60-64"),
        Fact("The environment is registered as x1_dh_stand through the in-tree task_registry, not gym.register",
             source="upstream_code", ref="humanoid/envs/__init__.py:39-43"),
    ]
    safe_state = ("the fake world has no autonomous simulation loop; the latch refuses new step and reset calls, "
                  "and an in-flight step checks cancellation before each further tick; cached state stays readable")
    fidelity = {
        "engine": "isaacgym:X1DHStandEnv",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "the upstream resets and steps draw from torch's global RNG for domain randomization and "
                     "command sampling; reset takes no seed and the environment exposes no get_state/set_state, so "
                     "this package makes no replay claim",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a pure-Python stand-in, not Isaac Gym: it models no rigid bodies, contacts, "
            "terrain, PD torques or MuJoCo model, and its joint, reward and termination values are placeholders",
            "the real observation is a 3102-value history of 66 frames of 47 values and the privileged observation "
            "is 219 values; the fake returns arrays of those sizes but fills them from a 12-joint stand-in, so the "
            "layout and values are not the upstream observation",
            "the fake does not model the upstream domain randomization, command resampling, push events, noise, "
            "reward terms or the contact/roll/pitch/time-out termination rules; it reports terminated only after "
            "its own placeholder episode length and truncation is always false",
            "the action envelope is operator_required; site-limits.example.json supplies illustrative fake-scale "
            "bounds only, not a joint-angle or torque envelope; the fake does not model the PD controller",
            "no integer RNG seed is exposed by the environment: reset takes no seed, the fake ignores seeds, and "
            "cap.world.seed.v1 is not bound",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
            "the upstream requires Isaac Gym, torch and a GPU (x1_dh_stand_env.py:35-40; setup.py:44-50), and "
            "neither the upstream simulator nor a real robot was run for this package",
            "one environment is served; the shipped training config runs 4096 environments (x1_dh_stand_config"
            ".py:50), so vectorized training is not covered",
            "only a fake backend exists: step passes Python lists, while LeggedRobot.step requires a torch.Tensor "
            "on the simulator device (legged_robot.py:115-118); a live factory must supply that adapter",
            "live construction acquires Isaac Gym, changes process-wide torch JIT flags and creates the simulator "
            "and optional viewer (base_task.py:44-110); viewer close/QUIT calls sys.exit and render can block in "
            "fetch_results or sync_frame_time (base_task.py:155-177); no such live route is enabled",
        ],
    }

    # ------------------------------------------------------------------ state
    def setup(self) -> None:
        """Open the world in the upstream reset state so a state read works before the first action."""
        self._episode = 0
        self._tick = 0
        self._reward = 0.0
        self._terminated = False
        self._truncated = False
        observation, privileged = self.native.reset()
        self._last_observation = self._observation(observation, privileged)

    def _observation(self, observation, privileged) -> dict:
        """The upstream step/reset observation tuple as the served state object."""
        return {
            "obs": _flatten(observation),
            "privileged_obs": _flatten(privileged),
        }

    @read("observation", type="object",
          description="Latest observation: the 66-frame history and the 3-frame privileged history",
          properties={
              "obs": Field("array", items="number", unit="1", length=OBSERVATION_SIZE,
                           description="66 frames of 47 observation values (x1_dh_stand_config.py:41-45)"),
              "privileged_obs": Field("array", items="number", unit="1", length=PRIVILEGED_OBSERVATION_SIZE,
                                      description="3 frames of 73 privileged values (x1_dh_stand_config.py:43-48)"),
          })
    def observation(self) -> dict:
        return self._last_observation

    @read("tick", type="integer", unit="1", description="Environment steps applied since the last reset")
    def tick(self) -> int:
        return int(self._tick)

    @read("episode", type="integer", unit="1", description="Resets performed since the backend opened")
    def episode(self) -> int:
        return int(self._episode)

    @read("reward", type="number", unit="1", description="Reward of the last step")
    def reward(self) -> float:
        return float(self._reward)

    @read("terminated", type="boolean",
          description="The upstream reset flag of the last step (contacts, roll/pitch cutoff or time-out)")
    def terminated(self) -> bool:
        return bool(self._terminated)

    @read("truncated", type="boolean",
          description="Always false: the upstream returns one reset flag and no separate truncation flag")
    def truncated(self) -> bool:
        return bool(self._truncated)

    # ---------------------------------------------------------------- actions
    @action(cap="cap.world.step.v1",
            description="Apply the 12-value action at every tick and advance the environment",
            input={
                "ticks": Field("integer", unit="1",
                               description="Policy steps to advance; the action is applied at every tick"),
                "action": Field("object", description="The upstream continuous action for one environment",
                                properties={
                                    "values": Field(
                                        "array", items="number", unit="1", length=ACTION_SIZE,
                                        description="12 action values, one per joint (x1_dh_stand_config.py:49)",
                                        limit=Limit.operator_required(
                                            "the cited configuration states clip_actions=100, while the symmetric "
                                            "clip is implemented in another file; the operator supplies the "
                                            "action envelope; the example overlay is fake-scale only"),
                                    ),
                                }),
            })
    def step(self, ticks: int, action: dict) -> dict:
        values = action.get("values") if isinstance(action, Mapping) else None
        if not isinstance(values, (list, tuple)) or len(values) != ACTION_SIZE:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               f"action.values must be an array of {ACTION_SIZE} numbers")
        action_batch = [[float(value) for value in values]]
        steps = int(ticks)
        if steps < 1:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "ticks must be at least 1")
        observation = privileged = reward = done = None
        for _ in range(steps):
            self.check_cancelled()
            observation, privileged, reward, done, _extras = self.native.step(action_batch)
            self._tick = int(self._tick) + 1
            self._last_observation = self._observation(observation, privileged)
            self._reward = _scalar(reward)
            self._terminated = bool(_scalar(done))
            self._truncated = False
        return {
            "observation": self._last_observation,
            "reward": self._reward,
            "terminated": self._terminated,
            "truncated": self._truncated,
            "tick": self._tick,
            "state_hash": canonical.digest({"observation": self._last_observation, "tick": self._tick}),
        }

    @action(cap="cap.world.reset.v1",
            description="Reset all environments to the upstream start state and return the initial observation",
            input={"options": Field(
                "object", properties={},
                description="Accepted for the catalogue reset contract; the upstream reset takes no options and "
                            "refuses a non-empty object")})
    def reset_world(self, options=None) -> dict:
        if options not in (None, {}):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "the upstream reset takes no options")
        observation, privileged = self.native.reset()
        self._tick = 0
        self._episode = int(self._episode) + 1
        self._reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_observation = self._observation(observation, privileged)
        return {
            "observation": self._last_observation,
            "seed": 0,
            "revision": self._episode,
        }
