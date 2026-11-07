"""Fake backend of the OceanScale driver: a pure Python stand-in for ``oceanscale.rov_env:ROVEnv``.

Why a fake: the acceptance gate runs without the upstream stack (the clone needs an NVIDIA GPU with CUDA 12.8+ and
pulls CUDA-enabled wheels, README.md:10-11 and :20; pyproject.toml:27-43), and package code never imports the clone.
This module re-implements only the parts of ``ROVEnv`` the Gymnasium bridge uses: the flat 26-element observation,
the 6-element action mapping, the reset noise, the exponential station-keeping reward, the 5 m out-of-bounds
termination and the ``max_episode_steps`` truncation.  Every constant taken from the clone cites its line at the
pinned commit (84f6cc4ce3dcf7cb4a53e2e9d2e81f541b0c63f2).

What this is not, all restated in the driver's fidelity ``gaps``:

* no Newton, Warp, Torch, thruster allocation or Tier-1 Fossen hydrodynamics: the fake integrates the action as a
  kinematic acceleration with a linear drag, so forces and trajectories are not the upstream ones;
* one environment only (``n_envs=1``): the fake returns a flat 26-vector and scalar reward, while upstream's
  ``step`` always returns batched ``(n_envs, 26)`` arrays (rov_env.py:346-347);
* no sensor noise: upstream adds Gaussian noise of ``sensor_noise_std`` to every observation entry
  (rov_env.py:768-769), the fake leaves the observation deterministic;
* no rendering, no exact state get/set and no partial reset of individual environments.

Nothing here talks to a device.
"""

import math
import random

# oceanscale/hydro/tier1.py:43: the default physics step, copied into ROVEnv's dt argument (rov_env.py:89).
DEFAULT_DT = 1.0 / 240.0
# rov_env.py:90: constructor default of max_episode_steps (a configuration default, not a device bound).
DEFAULT_MAX_EPISODE_STEPS = 1000
# rov_env.py:137-139: default target position.
DEFAULT_TARGET = (0.0, 0.0, -1.5)
# rov_env.py:101-102: default reset-noise half-ranges.
DEFAULT_INIT_POS_NOISE_STD = 0.5
DEFAULT_INIT_YAW_NOISE_STD = 0.5
# rov_env.py:163-164: observation and action space shapes and the action bounds.
OBS_DIM = 26
ACT_DIM = 6
ACTION_LOW = -1.0
ACTION_HIGH = 1.0
# rov_env.py:785-789: reward scales and weights.
POSITION_SCALE = 1.0
VELOCITY_SCALE = 0.5
ACTION_SCALE = 1.0
W_POSITION = 0.5
W_VELOCITY = 0.3
W_ACTION = 0.2
# rov_env.py:420: out-of-bounds termination distance.
OUT_OF_BOUNDS_M = 5.0
# placeholder: the fake's kinematic coefficients are test data, not the upstream dynamics.
FAKE_LINEAR_ACCEL = 1.0
FAKE_ANGULAR_ACCEL = 1.0
FAKE_DRAG_PER_S = 0.1


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: ``low``, ``high``, ``shape`` and ``dtype`` are what the bridge reads."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.low):
            return False
        return all(isinstance(item, (int, float)) and not isinstance(item, bool)
                   and self.low[index] <= float(item) <= self.high[index]
                   for index, item in enumerate(value))


class FakeROVEnv:
    """A single-environment stand-in for ``ROVEnv``: ``reset``, ``step`` and ``close`` behave like the upstream ones."""

    def __init__(
        self,
        n_envs: int = 1,
        dt: float = DEFAULT_DT,
        max_episode_steps: int = DEFAULT_MAX_EPISODE_STEPS,
        target_pos=None,
        init_pos_noise_std: float = DEFAULT_INIT_POS_NOISE_STD,
        init_yaw_noise_std: float = DEFAULT_INIT_YAW_NOISE_STD,
    ):
        if n_envs != 1:
            raise ValueError("the fake models one environment (n_envs=1); the upstream default is 64")
        self.n_envs = n_envs                                             # placeholder: one environment, not 64
        self.dt = float(dt)                                              # rov_env.py:113 and :89
        self.max_episode_steps = int(max_episode_steps)                  # rov_env.py:114
        target = DEFAULT_TARGET if target_pos is None else tuple(target_pos)
        self.target_pos = [float(value) for value in target]             # rov_env.py:137-139
        self.init_pos_noise_std = float(init_pos_noise_std)              # rov_env.py:132
        self.init_yaw_noise_std = float(init_yaw_noise_std)              # rov_env.py:133
        self.observation_space = Box([-math.inf] * OBS_DIM, [math.inf] * OBS_DIM)   # rov_env.py:163
        self.action_space = Box([ACTION_LOW] * ACT_DIM, [ACTION_HIGH] * ACT_DIM)    # rov_env.py:164
        self._rng = random.Random()                                      # placeholder: state of the reset noise
        self._position = list(self.target_pos)
        self._velocity = [0.0] * ACT_DIM
        self._yaw = 0.0
        self._steps = 0
        self._last_action = [0.0] * ACT_DIM

    def reset(self, *, seed=None, options=None):
        """Reset the environment; ``options={"target_position": [...]}`` replaces the target (rov_env.py:299-303)."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        if options is not None and "target_position" in options:
            self.target_pos = [float(value) for value in options["target_position"]]
        self._position = [
            self.target_pos[axis] + self._rng.uniform(-self.init_pos_noise_std, self.init_pos_noise_std)
            for axis in range(3)
        ]                                                                # rov_env.py:806-812
        self._yaw = self._rng.uniform(-self.init_yaw_noise_std, self.init_yaw_noise_std)   # rov_env.py:810-812
        self._velocity = [0.0] * ACT_DIM                                 # rov_env.py:835-839
        self._last_action = [0.0] * ACT_DIM
        self._steps = 0
        return self._observation(), {"target_position": list(self.target_pos)}

    def step(self, action):
        """Advance one tick and return ``(observation, reward, terminated, truncated, info)`` as flat values."""
        values = [float(item) for item in action]
        if not self.action_space.contains(values):                       # rov_env.py:355 clamps; the space bounds it
            raise AssertionError(f"action {action!r} is outside the action space")
        self._last_action = values
        drag = max(0.0, 1.0 - FAKE_DRAG_PER_S * self.dt)                 # placeholder
        for axis in range(3):
            self._velocity[axis] = self._velocity[axis] * drag + values[axis] * FAKE_LINEAR_ACCEL * self.dt
            self._position[axis] += self._velocity[axis] * self.dt
        for axis in range(3, ACT_DIM):
            self._velocity[axis] = self._velocity[axis] * drag + values[axis] * FAKE_ANGULAR_ACCEL * self.dt
        self._yaw += self._velocity[5] * self.dt
        self._steps += 1

        reward = (
            W_POSITION * math.exp(-self._position_error() / POSITION_SCALE)
            + W_VELOCITY * math.exp(-self._velocity_norm() / VELOCITY_SCALE)
            + W_ACTION * math.exp(-self._action_norm() / ACTION_SCALE)
        )                                                                # rov_env.py:785-789
        terminated = self._distance_to_target() > OUT_OF_BOUNDS_M        # rov_env.py:420
        truncated = self._steps >= self.max_episode_steps                # rov_env.py:414-416
        info = {
            "reward_distance": math.exp(-self._position_error() / POSITION_SCALE),
            "reward_velocity": math.exp(-self._velocity_norm() / VELOCITY_SCALE),
            "reward_action": math.exp(-self._action_norm() / ACTION_SCALE),
        }                                                                # rov_env.py:791-795
        return self._observation(), float(reward), bool(terminated), bool(truncated), info

    def close(self):
        """Release the fake state (the upstream method releases GPU resources, rov_env.py:277-279)."""
        self._velocity = [0.0] * ACT_DIM

    def _distance_to_target(self):
        return math.sqrt(sum((self._position[axis] - self.target_pos[axis]) ** 2 for axis in range(3)))

    def _position_error(self):
        return self._distance_to_target()

    def _velocity_norm(self):
        return math.sqrt(sum(value * value for value in self._velocity))

    def _action_norm(self):
        return math.sqrt(sum(value * value for value in self._last_action))

    def _observation(self):
        """The 26 entries of rov_env.py:62-70, in the same order."""
        observation = [
            self.target_pos[axis] - self._position[axis] for axis in range(3)
        ]                                                                # position error
        observation.extend([0.0, 0.0, math.sin(self._yaw * 0.5), math.cos(self._yaw * 0.5)])  # quaternion xyzw
        observation.extend(self._velocity[0:3])                          # linear velocity
        observation.extend(self._velocity[3:6])                          # angular velocity
        observation.append(self.target_pos[2] - self._position[2])       # depth error
        observation.extend([0.0, 0.0])                                   # heading error (roll, pitch)
        observation.extend(self._last_action)                            # previous action
        observation.extend([0.0, 0.0, 0.0, 0.0])                         # placeholder: no hydro wrench
        return observation
