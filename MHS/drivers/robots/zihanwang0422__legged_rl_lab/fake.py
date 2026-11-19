"""Fake backend of the legged_rl_lab driver: a pure-Python kinematic stand-in for the cross-embodied env.

Why a fake: the upstream environment is an Isaac Sim 5.1.0 / Isaac Lab 2.3.0 GPU simulation
(``README.md:3-5``) and neither package is installed where the acceptance gate runs, and package code never imports
the clone.  This module re-implements the *interface* of ``CrossEmbodiedG1Go2Env`` (the class the driver names as
``native``): a 29-dimensional unified action, a 98-dimensional policy observation and a 101-dimensional critic
observation (``g1go2_flat_env_cfg.py:15-30``), the command ranges of ``:218-227``, the base-height termination at
0.25 m (``:493-497``) and the 20 s episode at a 20 ms control period (``:533-535``).

What this is not: the upstream environment.  It has no rigid-body dynamics, contacts, actuators, sensors, noise,
rendering or GPU work; it models one G1 environment, not the configured 512 environments (half G1, half Go2).  The
reward is only the shared alive term (weight 0.15, ``:366``); every tracking and penalty term is omitted.  The
base-height transition is a placeholder, marked ``# placeholder`` below; the observation values are analytic.  The
fidelity contract of the driver lists these gaps.

Every non-placeholder constant cites the line of the clone at the pinned commit
386ee24bc62c8033641d65b940dc2cf1dec56545.  The public members are the ones the Gymnasium bridge calls on an
environment (``action_space``, ``observation_space``, ``reset``, ``step``, ``close``); gate G7 checks them against the
upstream class, whose Gymnasium base lies outside the clone.

Nothing here talks to a device.
"""

import math
import random

# g1go2_flat_env_cfg.py:15-30: actor 98 dims, critic 101 dims, actions 29 dims.
POLICY_DIM = 98
CRITIC_DIM = 101
N_JOINTS = 29
N_GO2_JOINTS = 12
# g1go2_flat_env_cfg.py:197-198: scale_g1=0.5, scale_go2=0.25.
G1_SCALE = 0.5
GO2_SCALE = 0.25
# g1go2_flat_env_cfg.py:218-227: x, y and yaw commands are sampled uniformly from (-1.0, 1.0).
COMMAND_LOW = -1.0
COMMAND_HIGH = 1.0
# g1go2_flat_env_cfg.py:218: the command is resampled every 10 s.
COMMAND_RESAMPLE_S = 10.0
# g1go2_flat_env_cfg.py:533-535: decimation 4 and sim.dt 0.005 s give a 20 ms control period; the episode is 20 s.
CONTROL_DT_S = 0.02
COMMAND_RESAMPLE_STEPS = int(COMMAND_RESAMPLE_S / CONTROL_DT_S)
EPISODE_STEPS = 1000
# source/legged_rl_lab/legged_rl_lab/assets/unitree.py:333: the G1 initial base position is 0.8 m.
INITIAL_BASE_HEIGHT_M = 0.8
# g1go2_flat_env_cfg.py:493-497: the base-fall termination threshold is 0.25 m.
FALL_HEIGHT_M = 0.25
# g1go2_flat_env_cfg.py:150-155, :176-178: both joint velocity observations have scale 0.05.
JOINT_VEL_OBS_SCALE = 0.05
# g1go2_flat_env_cfg.py:366: the shared alive reward term has weight 0.15.
# Its use below as a per-step score is a placeholder, not the external reward manager's integration.
ALIVE_REWARD = 0.15
# placeholder: the fake's kinematic base-height loss per unit of |scaled action|; the upstream height is a
# rigid-body quantity and this coefficient is test data, not a measurement or a bound.
HEIGHT_LOSS_PER_ACTION = 1e-4


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeCrossEmbodiedG1Go2Env:
    """A kinematic G1 slice of ``CrossEmbodiedG1Go2Env`` with the same spaces and step interface."""

    def __init__(self, cfg=None, render_mode=None, **kwargs):
        # The upstream constructor also accepts the registered cfg (g1go2_flat_env_cfg.py:571) and discards the
        # gymnasium keyword arguments (g1go2_flat_env_cfg.py:585-587); rendering is not modelled.
        if render_mode is not None:
            raise ValueError("the fake cross-embodied environment cannot render; use render_mode=None")
        self.action_space = Box([-math.inf] * N_JOINTS, [math.inf] * N_JOINTS, (N_JOINTS,))
        self.observation_space = Dict({
            "policy": Box([-math.inf] * POLICY_DIM, [math.inf] * POLICY_DIM, (POLICY_DIM,)),
            "critic": Box([-math.inf] * CRITIC_DIM, [math.inf] * CRITIC_DIM, (CRITIC_DIM,)),
        })
        self._rng = random.Random(0)
        self._seed = 0
        self._command = [0.0, 0.0, 0.0]
        self._joint_pos = [0.0] * N_JOINTS
        self._joint_vel = [0.0] * N_JOINTS
        self._last_action = [0.0] * N_JOINTS
        self._base_height = INITIAL_BASE_HEIGHT_M
        self._steps = 0
        self._terminated = False
        self._truncated = False

    # -- Gymnasium environment interface ---------------------------------
    def reset(self, *, seed=None, options=None):
        """Start an episode: sample the velocity command and zero the joint state (``g1go2_flat_env_cfg.py:15-30``)."""
        if options is not None and not isinstance(options, dict):
            raise ValueError("reset options must be a mapping")
        if seed is not None:
            self._rng = random.Random(int(seed))
            self._seed = int(seed)
        # g1go2_flat_env_cfg.py:218-227: the command is resampled from the three uniform ranges.
        self._command = [self._rng.uniform(COMMAND_LOW, COMMAND_HIGH) for _ in range(3)]
        self._joint_pos = [0.0] * N_JOINTS
        self._joint_vel = [0.0] * N_JOINTS
        self._last_action = [0.0] * N_JOINTS
        self._base_height = INITIAL_BASE_HEIGHT_M
        self._steps = 0
        self._terminated = False
        self._truncated = False
        return self._observation(), {}

    def step(self, action):
        """Apply one scaled joint-position action and return the next observation and terminal flags."""
        if self._terminated or self._truncated:
            raise RuntimeError("the episode has ended; reset the environment first")
        if isinstance(action, (str, bytes)) or not hasattr(action, "__len__"):
            raise ValueError("the action must be a sequence of 29 numbers")
        values = [float(value) for value in action]
        if len(values) != N_JOINTS:
            raise ValueError(f"the action must have {N_JOINTS} values, got {len(values)}")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("the action values must be finite")
        # g1go2_flat_env_cfg.py:197-198 and cross_embodied_mdp.py:707: the G1 scale is 0.5; a G1 environment keeps
        # all 29 dims, so no Go2 zero padding (cross_embodied_mdp.py:645-653) is applied here.
        scaled = [G1_SCALE * value for value in values]
        old = self._joint_pos
        self._joint_pos = scaled
        self._joint_vel = [(new - before) / CONTROL_DT_S for new, before in zip(scaled, old)]
        # last_action_cross reads action_manager.action, not the term's _last_scaled buffer
        # (cross_embodied_mdp.py:117-127); joint targets alone use the G1 scale.
        self._last_action = list(values)
        # placeholder: a kinematic height response, not the upstream rigid-body height.  Zero actions hold the G1
        # initial 0.8 m; a large action lowers it and can cross the 0.25 m termination threshold of
        # g1go2_flat_env_cfg.py:493-497.
        self._base_height -= HEIGHT_LOSS_PER_ACTION * sum(abs(value) for value in scaled)
        self._steps += 1
        if self._steps % COMMAND_RESAMPLE_STEPS == 0:
            # g1go2_flat_env_cfg.py:218: the command is resampled on the configured 10 s interval.
            self._command = [self._rng.uniform(COMMAND_LOW, COMMAND_HIGH) for _ in range(3)]
        self._terminated = self._base_height < FALL_HEIGHT_M
        self._truncated = self._steps >= EPISODE_STEPS
        # is_alive_cross is zero when terminated (cross_embodied_mdp.py:187-193).
        # Placeholder per-step reward magnitude: external reward integration and other terms are omitted.
        reward = 0.0 if self._terminated else ALIVE_REWARD
        return self._observation(), reward, self._terminated, self._truncated, {}

    def close(self):
        """Release nothing: the fake owns no simulator, GPU or external resource."""
        return None

    # -- observation layout ----------------------------------------------
    def _observation(self):
        # g1go2_flat_env_cfg.py:15-30: [robot_id(2) | ang_vel(3) | proj_grav(3) | cmd(3) |
        # joint_pos(29) | joint_vel(29) | last_action(29)] for the actor, and the same plus base_lin_vel(3) for the
        # critic.  The fake models a G1 environment, so robot_id is [1, 0] and no Go2 padding is applied.
        robot_id = [1.0, 0.0]
        ang_vel = [0.0, 0.0, 0.0]
        projected_gravity = [0.0, 0.0, -1.0]
        command = list(self._command)
        joint_vel = [value * JOINT_VEL_OBS_SCALE for value in self._joint_vel]
        policy = robot_id + ang_vel + projected_gravity + command + list(self._joint_pos) + joint_vel \
            + list(self._last_action)
        critic = robot_id + [0.0, 0.0, 0.0] + ang_vel + projected_gravity + command + list(self._joint_pos) \
            + joint_vel + list(self._last_action)
        return {"policy": policy, "critic": critic}
