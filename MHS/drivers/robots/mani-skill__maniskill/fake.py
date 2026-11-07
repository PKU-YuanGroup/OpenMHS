"""Fake backend of the ManiSkill driver: a pure-Python kinematic stand-in for TriFingerRotateCubeLevel0-v1.

Why a fake: the acceptance gate never installs or imports the clone (it needs SAPIEN, PhysX, torch and a GPU-capable
stack), and package code never imports the clone.  This module models the public surface that
``mani_skill.envs.tasks.rotate_cube:RotateCubeEnvLevel0`` has -- ``reset(seed, options)``, ``step(action)``,
``close()``, ``action_space`` and ``observation_space`` (gate G7) -- and the step limit that ``gym.make`` adds as the
``MSTimeLimit`` wrapper.  The two space classes duck-type ``gymnasium.spaces.Box`` (the bridge reads ``low``, ``high``,
``shape`` and ``dtype``).

The model is kinematic (fidelity F0): the nine joint positions integrate the normalised joint deltas directly, the cube
is moved by a small placeholder drift, and there are no contacts, friction, actuators or constraints.  Every constant
that is a property of the upstream environment cites its line at the pinned commit
62ff3a5896b4d5b4cf0ac4c8d79afe600c9404a3; every invented number is marked ``# placeholder``.  The fake was never
compared with a run of the upstream SAPIEN environment (see the driver's fidelity gaps and facts.md).

Nothing here talks to a device.
"""

import math
import random

# RotateCubeEnv / TriFingerPro properties (mani_skill/envs/tasks/rotate_cube.py unless noted).
N_JOINTS = 9                                    # three three-joint fingers, trifingerpro.py:42-56
N_OBS = 32                                      # 9 qpos + 9 qvel + 3 goal_pos + 4 goal_q + 3 obj_p + 4 obj_q
CONTROL_DELTA = 0.1                             # per-joint delta bound, trifingerpro.py:105-106
QPOS_INIT_NOISE = 0.02                          # robot_init_qpos_noise, rotate_cube.py:58
CUBE_SIZE = 0.065                               # self.size, rotate_cube.py:44
CUBE_START_Z = CUBE_SIZE / 2.0 + 0.005          # rotate_cube.py:125
GOAL_Z = CUBE_SIZE / 2.0                        # difficulty 0 goal height, rotate_cube.py:179
GOAL_RADIUS = 0.02                              # rotate_cube.py:39
ARENA_RADIUS = 0.195                            # rotate_cube.py:43
RADIUS_3D = CUBE_SIZE * math.sqrt(3.0) / 2.0    # rotate_cube.py:47
MAX_COM_DISTANCE = ARENA_RADIUS - RADIUS_3D     # rotate_cube.py:49
MAX_EPISODE_STEPS = 250                         # max_episode_steps, rotate_cube.py:351
NORMALISED_MAX_REWARD = 15.0                    # max_reward, rotate_cube.py:345

# Placeholder dynamics of this fake, not facts about the environment.
CUBE_DRIFT = 0.002                              # placeholder
REWARD_DISTANCE = 0.2                           # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, values):
        return len(values) == len(self.low) and all(
            low <= float(value) <= high for value, low, high in zip(values, self.low, self.high))


class FakeRotateCubeEnv:
    """A kinematic TriFinger cube-rotation environment without SAPIEN: the same reset/step/close surface."""

    def __init__(self, num_envs=1, obs_mode=None, reward_mode=None, control_mode=None, **options):
        if num_envs != 1:
            raise ValueError("the fake serves one environment")
        self.action_space = Box([-1.0] * N_JOINTS, [1.0] * N_JOINTS)        # gym_utils.py:110-112
        self.observation_space = Box([-math.inf] * N_OBS, [math.inf] * N_OBS)
        self._rng = random.Random()
        self._closed = False
        self._qpos = [0.0] * N_JOINTS
        self._qvel = [0.0] * N_JOINTS
        self._obj_p = [0.0, 0.0, CUBE_START_Z]
        self._obj_q = [1.0, 0.0, 0.0, 0.0]
        self._goal_p = [0.0, 0.0, GOAL_Z]
        self._goal_q = [1.0, 0.0, 0.0, 0.0]
        self._steps = 0

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._qpos = [self._rng.gauss(0.0, QPOS_INIT_NOISE) for _ in range(N_JOINTS)]   # rotate_cube.py:243-244
        self._qvel = [0.0] * N_JOINTS
        self._obj_p = [0.0, 0.0, CUBE_START_Z]                                          # rotate_cube.py:124-127
        self._obj_q = [1.0, 0.0, 0.0, 0.0]
        radius = math.sqrt(self._rng.random()) * MAX_COM_DISTANCE                       # rotate_cube.py:159-161
        theta = 2.0 * math.pi * self._rng.random()                                      # rotate_cube.py:163
        self._goal_p = [radius * math.cos(theta), radius * math.sin(theta), GOAL_Z]     # rotate_cube.py:165-166
        self._goal_q = [1.0, 0.0, 0.0, 0.0]                                             # rotate_cube.py:153-155
        self._steps = 0
        return self._observation(), {}

    def step(self, action):
        values = [float(value) for value in action]
        if len(values) != N_JOINTS:
            raise ValueError(f"the action must have {N_JOINTS} values")
        # The controller clips to [-1, 1] and scales by the [-0.1, 0.1] delta range (gym_utils.py:104-107).
        values = [max(-1.0, min(1.0, value)) for value in values]
        self._qvel = [value * CONTROL_DELTA for value in values]
        self._qpos = [position + delta for position, delta in zip(self._qpos, self._qvel)]
        # Placeholder kinematic drift of the cube: finger 0/1 move x, finger 2 moves y.
        left = (sum(values[0:6]) / 6.0) * CUBE_DRIFT
        right = (sum(values[6:9]) / 3.0) * CUBE_DRIFT
        self._obj_p[0] = max(-MAX_COM_DISTANCE, min(MAX_COM_DISTANCE, self._obj_p[0] + left))
        self._obj_p[1] = max(-MAX_COM_DISTANCE, min(MAX_COM_DISTANCE, self._obj_p[1] + right))
        self._steps += 1
        distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(self._obj_p, self._goal_p)))
        success = distance < GOAL_RADIUS
        angle = 2.0 * math.acos(min(1.0, abs(sum(a * b for a, b in zip(self._obj_q, self._goal_q)))))
        success = success and angle < 0.1
        if success:
            dense = NORMALISED_MAX_REWARD                                              # rotate_cube.py:341
        else:
            dense = NORMALISED_MAX_REWARD * max(0.0, 1.0 - distance / REWARD_DISTANCE)
        reward = dense / (2.0 * NORMALISED_MAX_REWARD) + 0.5                           # rotate_cube.py:345-347
        truncated = self._steps >= MAX_EPISODE_STEPS
        return self._observation(), reward, success, truncated, {"success": success, "elapsed_steps": self._steps}

    def close(self):
        self._closed = True

    def _observation(self):
        return list(self._qpos) + list(self._qvel) + list(self._goal_p) + list(self._goal_q) \
            + list(self._obj_p) + list(self._obj_q)
