"""Fake backend of the SharpaWave in-hand rotation package: an analytic stand-in for the Isaac Lab environment.

The upstream entry ``rl_isaaclab.tasks.inhand_rotate.sharpa_wave_env:SharpaWaveInhandRotateEnv`` subclasses Isaac
Lab's ``DirectRLEnv`` and needs Isaac Sim, a GPU and the 16,384-environment scene of
``sharpa_wave_env_cfg.py:259``.  None of that can run where the gate runs, and package code never imports the clone.
This module therefore reproduces the environment's public Gymnasium surface (``reset``, ``step`` and ``close``) and
the configured dimensions with a small, purely kinematic model.  It is an analytic stand-in, not a recording and not
the upstream simulator: the driver's fidelity ``gaps`` list every difference.

Shape of the model (all numbers below are the upstream configuration, cited in the driver's facts):

* 22 joint targets (``sharpa_wave_env_cfg.py:42``); ``step`` clips each action to ``[-1, 1]`` and advances the
  previous target by ``action_scale = 1/24`` (``sharpa_wave_env_cfg.py:51-52``, ``sharpa_wave_env.py:177-185``);
* one control step is ``decimation = 12`` physics steps of ``dt = 1/240`` s, i.e. 0.05 s
  (``sharpa_wave_env_cfg.py:49`` and ``:56``);
* the configured maximum is 400 control steps; the fake compares its counter to maximum minus one, matching the
  threshold in ``sharpa_wave_env.py:255`` (it does not reproduce the external base's automatic reset lifecycle);
* the policy observation is the last three 64-value frames of the history buffer, 192 values in total
  (``sharpa_wave_env_cfg.py:43`` and ``sharpa_wave_env.py:421-445``);
* the reward combines the six source terms with the configured scales (``sharpa_wave_env.py:217-233``,
  ``sharpa_wave_env_cfg.py:267-276``).

The joint motion, object rotation and PD torques are kinematic proxies.  Their internal constants are fake test
data, marked ``# placeholder``: they are not Facts, Limits or device values.  The tactile channels are held at zero
because there is no contact model.  The action space is published unbounded: the clone states the internal
saturation ``clip_actions = 1.0`` but the space itself is built by the Isaac Lab ``DirectRLEnv`` base outside the
clone, so the fake clips each action in ``step`` rather than inventing a space bound.

Gate G7 checks every public method of this class against the native class; only ``reset``, ``step`` and ``close``
are public, and all helpers are private.
"""

from __future__ import annotations

import math
import random

# The configured dimensions (upstream code, not device values).
NUM_JOINTS = 22                              # sharpa_wave_env_cfg.py:42
OBSERVATION_SIZE = 192                       # sharpa_wave_env_cfg.py:43
FRAME_SIZE = OBSERVATION_SIZE // 3           # sharpa_wave_env.py:445 packs three frames
LAG_FRAMES = 3
CLIP_ACTIONS = 1.0                           # sharpa_wave_env_cfg.py:51
ACTION_SCALE = 1.0 / 24.0                    # sharpa_wave_env_cfg.py:52
DECIMATION = 12                              # sharpa_wave_env_cfg.py:49
PHYSICS_DT = 1.0 / 240.0                     # sharpa_wave_env_cfg.py:56
STEP_DT = DECIMATION * PHYSICS_DT            # 12 * (1/240) s = 0.05 s
EPISODE_LENGTH_S = 20.0                      # sharpa_wave_env_cfg.py:41
MAX_EPISODE_STEPS = int(round(EPISODE_LENGTH_S / STEP_DT))
# Reset height band of the object (sharpa_wave_env_cfg.py:263-264).
RESET_HEIGHT_LOWER = 0.59906
RESET_HEIGHT_UPPER = 0.63906
OBJECT_HEIGHT = 0.61906                      # sharpa_wave_env_cfg.py:256 (the object's initial z)
# Reward scales and clip (sharpa_wave_env_cfg.py:269-276).
ANGVEL_CLIP_MIN = -0.5
ANGVEL_CLIP_MAX = 0.5
ROTATE_REWARD_SCALE = 2.5
OBJECT_LINVEL_PENALTY_SCALE = -0.3
POS_DIFF_PENALTY_SCALE = -0.4
TORQUE_PENALTY_SCALE = -0.1
WORK_PENALTY_SCALE = -0.5
OBJECT_POS_REWARD_SCALE = 0.003
# Fake model constants (test data only).
JOINT_LIMIT = math.pi                        # placeholder: the per-joint limits come from the USD asset upstream
POSITION_LAG = 0.4                           # placeholder: first-order joint tracking per control step
P_GAIN = 1.0                                 # placeholder: the upstream gains come from the articulation data
D_GAIN = 0.1                                 # placeholder
OBJECT_YAW_PER_ACTION = 0.02                 # placeholder: radians of object yaw per unit of mean action
START_SPREAD = 0.15                          # placeholder: reset joint-position spread (rad)
OBJECT_POSITION_EPS = 0.001                  # sharpa_wave_env.py:224


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: ``low``, ``high``, ``shape`` and ``dtype`` are what the bridge reads."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = None


def _clip(value, lower, upper):
    return lower if value < lower else upper if value > upper else value


class FakeSharpaWaveInhandRotateEnv:
    """Kinematic stand-in for one SharpaWave in-hand rotation environment.

    ``__init__`` mirrors the native signature ``(cfg, render_mode=None, **kwargs)``; the bridge builds it with no
    arguments, so ``cfg`` defaults to the registered configuration modelled here.  The upstream class is registered
    at ``rl_isaaclab/tasks/inhand_rotate/__init__.py:9-17``.
    """

    def __init__(self, cfg=None, render_mode=None, **kwargs):
        self.cfg = cfg
        self.render_mode = render_mode
        self.num_envs = 1
        self.device = "cpu"
        self.step_dt = STEP_DT
        self.max_episode_length = MAX_EPISODE_STEPS
        self.observation_space = Dict({"policy": Box(
            [-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE,
            (OBSERVATION_SIZE,))})
        # The space is owned by the external DirectRLEnv base; the clone only states the internal saturation.
        self.action_space = Box(
            [-math.inf] * NUM_JOINTS, [math.inf] * NUM_JOINTS, (NUM_JOINTS,))
        self._rng = random.Random(0)
        self._closed = False
        self._tick = 0
        self._joint_pos = [0.0] * NUM_JOINTS
        self._prev_targets = [0.0] * NUM_JOINTS
        self._cur_targets = [0.0] * NUM_JOINTS
        self._joint_vel = [0.0] * NUM_JOINTS
        self._default_joint_pos = [0.0] * NUM_JOINTS
        self._object_pos = [0.0, 0.0, OBJECT_HEIGHT]
        self._object_default_pos = [0.0, 0.0, OBJECT_HEIGHT]
        self._object_yaw = 0.0
        self._object_yaw_prev = 0.0
        self._history = []
        self._reset_buffers()

    # -- the native Gymnasium surface ------------------------------------------------
    def reset(self, seed=None, options=None):
        """Reset the fake; options are ignored. The upstream public reset is inherited outside the clone."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._joint_pos = [self._rng.uniform(-START_SPREAD, START_SPREAD) for _ in range(NUM_JOINTS)]
        self._prev_targets = list(self._joint_pos)
        self._cur_targets = list(self._joint_pos)
        self._joint_vel = [0.0] * NUM_JOINTS
        self._object_pos = list(self._object_default_pos)
        self._object_yaw = 0.0
        self._object_yaw_prev = 0.0
        self._tick = 0
        self._reset_buffers()
        return {"policy": self._observation()}, {}

    def step(self, action):
        """Advance one control step of 12 physics ticks and return the Gymnasium five-tuple."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        action = [float(value) for value in action]
        if len(action) != NUM_JOINTS:
            raise ValueError(f"expected {NUM_JOINTS} action values, got {len(action)}")
        if not all(math.isfinite(value) for value in action):
            raise ValueError("action values must be finite")
        clipped = [_clip(value, -CLIP_ACTIONS, CLIP_ACTIONS) for value in action]
        # sharpa_wave_env.py:177-185: targets advance by action_scale from the previous target and are saturated
        # by the joint limits.  The fake uses a symmetric placeholder limit because the USD limits are not modelled.
        targets = [self._prev_targets[i] + ACTION_SCALE * clipped[i] for i in range(NUM_JOINTS)]
        self._cur_targets = [_clip(value, -JOINT_LIMIT, JOINT_LIMIT) for value in targets]
        previous = list(self._joint_pos)
        self._joint_pos = [previous[i] + POSITION_LAG * (self._cur_targets[i] - previous[i])
                           for i in range(NUM_JOINTS)]
        self._joint_vel = [(self._joint_pos[i] - previous[i]) / STEP_DT for i in range(NUM_JOINTS)]
        self._prev_targets = list(self._cur_targets)
        self._object_yaw_prev = self._object_yaw
        mean_action = sum(clipped) / NUM_JOINTS
        self._object_yaw += OBJECT_YAW_PER_ACTION * mean_action      # placeholder kinematic rotation proxy
        self._tick += 1
        self._append_frame()
        terminated = not (RESET_HEIGHT_LOWER <= self._object_pos[2] <= RESET_HEIGHT_UPPER)
        truncated = self._tick >= MAX_EPISODE_STEPS - 1
        reward, terms = self._reward()
        info = dict(terms)
        info["height_reset_upper"] = float(self._object_pos[2] > RESET_HEIGHT_UPPER)
        info["height_reset_lower"] = float(self._object_pos[2] < RESET_HEIGHT_LOWER)
        info["time_out"] = 1.0 if truncated else 0.0
        info["total_reward"] = reward
        return {"policy": self._observation()}, reward, terminated, truncated, info

    def close(self):
        self._closed = True

    # -- private model helpers ---------------------------------------------------------
    def _reset_buffers(self):
        frame = self._frame()
        self._history = [list(frame) for _ in range(80)]

    def _append_frame(self):
        self._history = self._history[1:] + [self._frame()]

    def _frame(self):
        scaled = [_clip(value / JOINT_LIMIT, -1.0, 1.0) for value in self._joint_pos]
        contacts = [0.0] * 5                                     # no tactile model in the fake
        contact_positions = [0.0] * 15                           # enable_contact_pos is False upstream
        return scaled + list(self._cur_targets) + contacts + contact_positions

    def _observation(self):
        frames = self._history[-LAG_FRAMES:]
        return [value for frame in frames for value in frame]

    def _reward(self):
        object_angvel = (self._object_yaw - self._object_yaw_prev) / STEP_DT
        rotate_reward = _clip(object_angvel, ANGVEL_CLIP_MIN, ANGVEL_CLIP_MAX)
        object_linvel_penalty = 0.0                              # the object position is fixed in the fake
        pos_diff_penalty = sum((value - self._default_joint_pos[i]) ** 2
                               for i, value in enumerate(self._joint_pos))
        torques = [P_GAIN * (self._cur_targets[i] - self._joint_pos[i]) - D_GAIN * self._joint_vel[i]
                   for i in range(NUM_JOINTS)]
        torque_penalty = sum(value * value for value in torques)
        work_penalty = (sum(torques[i] * self._joint_vel[i] for i in range(NUM_JOINTS))) ** 2
        object_pos_diff = 1.0 / (math.dist(self._object_pos, self._object_default_pos) + OBJECT_POSITION_EPS)
        total = (rotate_reward * ROTATE_REWARD_SCALE
                 + object_linvel_penalty * OBJECT_LINVEL_PENALTY_SCALE
                 + pos_diff_penalty * POS_DIFF_PENALTY_SCALE
                 + torque_penalty * TORQUE_PENALTY_SCALE
                 + work_penalty * WORK_PENALTY_SCALE
                 + object_pos_diff * OBJECT_POS_REWARD_SCALE)
        terms = {
            "rotate_reward": rotate_reward,
            "object_linvel_penalty": object_linvel_penalty,
            "pos_diff_penalty": pos_diff_penalty,
            "torque_penalty": torque_penalty,
            "work_penalty": work_penalty,
            "object_pos_diff": object_pos_diff,
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": object_angvel,
            "gravity_x": 0.0,
            "gravity_y": 0.0,
            "gravity_z": -0.05,                                  # sharpa_wave_env_cfg.py:58
        }
        return total, terms
