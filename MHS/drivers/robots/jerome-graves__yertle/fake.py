"""Fake backend of the Yertle driver: a pure Python stand-in for ``learning.yertle_env:YertleEnv``.

Why a fake: the upstream environment needs gymnasium and pybullet (``learning/requirements-rl.txt:8-9``) and numpy
(``requirements.txt:7``), and constructing it imports and runs the read-only clone, which package code must not do.  This module implements the
public environment interface that the gate checks (``reset``, ``step`` and ``close``; gate G7) plus duck-typed
``Box`` spaces (the bridge reads ``low``, ``high`` and ``shape``) and the same observation layout and reward rules as
``learning/yertle_env.py``.  The constants taken from the upstream configuration cite its lines at the pinned commit
9d04e2d2c1da07d5845807bd36b242b1d0eff843.

What this is not: the upstream environment, and no physical device.  The fake does not run PyBullet, so contact,
friction, the servo, the URDF inertia override and falling are not modelled; base velocity is a first-order stand-in
for the sampled command, joint motion is a first-order approach to the clipped targets and ``terminated`` is always
false.  The driver's fidelity ``gaps`` say all of this.  Numbers marked ``# placeholder`` are test data of the fake,
not facts about the device.

The only public methods are the ones YertleEnv has; helper methods start with an underscore so gate G7 does not read
them as part of the upstream interface.  Nothing here talks to a device.
"""

import math
import random

# learning/yertle_env.py:47-51: four legs times three segments.
N_JOINTS = 12
# learning/yertle_env.py:56-63: soft joint limits in radians.
_DEG = math.pi / 180.0
SHOULDER = (-45.0 * _DEG, 45.0 * _DEG)
THIGH = (-90.0 * _DEG, 20.0 * _DEG)
SHIN = (13.0 * _DEG, 90.0 * _DEG)
JOINT_LIMITS = (SHOULDER, THIGH, SHIN) * 4
# learning/yertle_env.py:65-71
DEFAULT_STANCE = (0.0, -0.6, 0.9) * 4
# learning/yertle_env.py:78-84
SIM_TIMESTEP = 1.0 / 240.0
CONTROL_DECIMATION = 4
EPISODE_SECONDS = 12.0
ACTION_SCALE = 0.4
# learning/yertle_env.py:140: the default step limit of one episode.
MAX_STEPS = int(EPISODE_SECONDS / (SIM_TIMESTEP * CONTROL_DECIMATION))
# learning/yertle_env.py:91-95: command ranges in m/s and rad/s.
COMMAND_X_RANGE = (0.15, 0.35)
COMMAND_Y_RANGE = (-0.1, 0.1)
COMMAND_YAW_RANGE = (-0.4, 0.4)
# learning/yertle_env.py:97-99
MIN_BASE_HEIGHT = 0.08
MAX_TILT = 0.7
TARGET_HEIGHT = 0.18
# learning/yertle_env.py:101-112: reward weights.
W_LIN_VEL = 1.0
W_PROGRESS = 2.0
TRACKING_SIGMA = 0.1
W_YAW_VEL = 0.25
W_ALIVE = 0.0
W_ENERGY = 5e-4
W_ACTION_RATE = 0.01
W_ORIENTATION = 0.5
W_HEIGHT = 0.25
# learning/yertle_env.py:114-120: randomisation is on by default.
RANDOMIZE = True
OBS_NOISE = 0.02
# learning/yertle_env.py:355-381: the yaw kernel width and the progress clip are literals in the reward method.
YAW_SIGMA = 0.25
PROGRESS_CLIP = 0.5
FALL_PENALTY = 5.0
#: placeholder: the fake has no physics, so it approaches the target at this fraction per step and the base follows
#: the command at this fraction per step.
JOINT_FOLLOW = 0.5
TRACK_GAIN = 0.1


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        values = list(value)
        return len(values) == len(self.low) and all(
            low <= float(item) <= high for item, low, high in zip(values, self.low, self.high)
        )


class FakeYertleEnv:
    """YertleEnv without pybullet: ``reset(seed, options)`` and ``step(action)`` return what gymnasium's do."""

    def __init__(self, config=None, render_mode=None):
        self.cfg = config
        self.render_mode = render_mode
        # learning/yertle_env.py:150-156
        self.action_space = Box([-1.0] * N_JOINTS, [1.0] * N_JOINTS)
        self.observation_space = Box([-math.inf] * 48, [math.inf] * 48)
        self._rng = random.Random()
        self._seed = None
        self._command = [0.0, 0.0, 0.0]
        self._q = list(DEFAULT_STANCE)
        self._dq = [0.0] * N_JOINTS
        self._prev_action = [0.0] * N_JOINTS
        self._base_lin = [0.0, 0.0, 0.0]
        self._base_ang = [0.0, 0.0, 0.0]
        self._gravity = [0.0, 0.0, -1.0]
        self._height = TARGET_HEIGHT
        self._step_count = 0
        self._closed = False

    def reset(self, *, seed=None, options=None):
        # learning/yertle_env.py:247-268
        if seed is not None:
            self._rng = random.Random(int(seed))
            self._seed = int(seed)
        self._command = [
            self._rng.uniform(*COMMAND_X_RANGE),
            self._rng.uniform(*COMMAND_Y_RANGE),
            self._rng.uniform(*COMMAND_YAW_RANGE),
        ]
        self._q = list(DEFAULT_STANCE)
        self._dq = [0.0] * N_JOINTS
        self._prev_action = [0.0] * N_JOINTS
        self._base_lin = [0.0, 0.0, 0.0]
        self._base_ang = [0.0, 0.0, 0.0]
        self._gravity = [0.0, 0.0, -1.0]
        self._height = TARGET_HEIGHT
        self._step_count = 0
        self._closed = False
        return self._obs(), {}

    def step(self, action):
        # learning/yertle_env.py:278-299
        values = [float(item) for item in action]
        if len(values) != N_JOINTS:
            raise ValueError(f"action must have {N_JOINTS} values, got {len(values)}")
        values = [min(1.0, max(-1.0, item)) for item in values]  # placeholder: clip before the native call is never reached
        targets = []
        for index, residual in enumerate(values):
            target = DEFAULT_STANCE[index] + residual * ACTION_SCALE
            low, high = JOINT_LIMITS[index]
            targets.append(min(high, max(low, target)))
        previous = list(self._q)
        self._q = [value + JOINT_FOLLOW * (target - value) for value, target in zip(previous, targets)]
        dt = SIM_TIMESTEP * CONTROL_DECIMATION
        self._dq = [(value - old) / dt for value, old in zip(self._q, previous)]
        for axis in (0, 1):
            self._base_lin[axis] += TRACK_GAIN * (self._command[axis] - self._base_lin[axis])
        self._base_ang[2] += TRACK_GAIN * (self._command[2] - self._base_ang[2])
        observation = self._obs()
        reward, terminated = self._reward_and_done(values)
        self._prev_action = values
        self._step_count += 1
        truncated = self._step_count >= MAX_STEPS
        return observation, reward, terminated, truncated, {"command": list(self._command)}

    def close(self):
        self._closed = True

    def _obs(self):
        # learning/yertle_env.py:332-347
        observation = (
            list(self._base_lin)
            + list(self._base_ang)
            + list(self._gravity)
            + list(self._command)
            + [value - stance for value, stance in zip(self._q, DEFAULT_STANCE)]
            + [value * 0.1 for value in self._dq]
            + list(self._prev_action)
        )
        if RANDOMIZE and OBS_NOISE > 0:
            observation = [value + self._rng.gauss(0.0, OBS_NOISE) for value in observation]
        return observation

    def _reward_and_done(self, action):
        # learning/yertle_env.py:350-382
        lin_err = sum((self._command[axis] - self._base_lin[axis]) ** 2 for axis in (0, 1))
        yaw_err = (self._command[2] - self._base_ang[2]) ** 2
        r_lin = W_LIN_VEL * math.exp(-lin_err / TRACKING_SIGMA)
        r_yaw = W_YAW_VEL * math.exp(-yaw_err / YAW_SIGMA)
        cmd_norm = math.sqrt(self._command[0] ** 2 + self._command[1] ** 2) + 1e-6
        vel_along = (self._base_lin[0] * self._command[0] + self._base_lin[1] * self._command[1]) / cmd_norm
        r_progress = W_PROGRESS * min(PROGRESS_CLIP, max(-PROGRESS_CLIP, vel_along))
        r_energy = -W_ENERGY * sum(abs(value * residual) for value, residual in zip(self._dq, action))
        r_action_rate = -W_ACTION_RATE * sum(
            (residual - previous) ** 2 for residual, previous in zip(action, self._prev_action)
        )
        r_orient = -W_ORIENTATION * (self._gravity[0] ** 2 + self._gravity[1] ** 2)
        r_height = -W_HEIGHT * (self._height - TARGET_HEIGHT) ** 2
        reward = r_lin + r_progress + r_yaw + W_ALIVE + r_energy + r_action_rate + r_orient + r_height
        tilt = math.acos(min(1.0, max(-1.0, -self._gravity[2])))
        fell = self._height < MIN_BASE_HEIGHT or tilt > MAX_TILT
        if fell:
            reward -= FALL_PENALTY
        return float(reward), bool(fell)
