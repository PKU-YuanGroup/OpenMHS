"""Fake backend for gh.psvl/doorgym: a pure Python stand-in for ``doorenv2.envs:DoorEnvBlueV1``.

Why a fake: the acceptance gate cannot install the upstream stack (gym 0.14, mujoco-py, mjremote, torch and
MuJoCo itself are not available where the gate runs), and package code never imports the clone.  This module
models the contract of one generated world, ``world_generator/world/pull_blue_right_v2_gripper_motor``, without
MuJoCo:

* the action space is the ``Box`` that ``DoorEnv.__init__`` builds from ``model.actuator_ctrlrange`` with the
  last ``gripper_space`` bounds removed (``doorenv2/doorenv2/envs/doorenv.py:76-83``).  For the gripper-motor
  robot that is seven motor values in [-1, 1] (``world_generator/robot/blue_right_v2_gripper_motor.xml:4-10``)
  and the right gripper value in [0, 1.05] (``...:18``); ``DoorEnv`` starts ``gripper_action`` with four zeros
  (``doorenv2/doorenv2/envs/doorenv.py:35``), so the last four actuator bounds are removed;
* ``nn`` is 8 for a world whose file name contains ``gripper`` (``doorenv2/doorenv2/envs/doorenv.py:58-62``),
  and the observation is the first ``nn`` qpos and qvel values followed by the three-value finger-to-knob
  distance (``doorenv2/doorenv2/envs/doorenv.py:256-273,404-405``; ``doorenv2/doorenv2/envs/doorenv_blue.py:
  133-143``), i.e. ``2 * 8 + 3 = 19`` values;
* ``reset(seed)`` returns only the observation, and ``step(action)`` returns the legacy four-tuple
  ``(observation, reward, done, info)`` that ``DoorEnv.step`` returns (``doorenv2/doorenv2/envs/doorenv.py:
  130-135``).  ``done`` becomes True at the 512th step because the registration wraps the env in a gym
  ``TimeLimit`` with ``max_episode_steps=512`` (``doorenv2/doorenv2/__init__.py:3-7``); the environment itself
  never sets it.

What this is not: MuJoCo or the upstream environment.  The dynamics here are a deliberately simple analytic
stand-in, every numeric constant of that stand-in is test data marked ``# placeholder``, and the fake was never
compared with the upstream environment.  The driver's fidelity ``gaps`` list the omissions.  The public methods
are limited to ``reset``, ``step`` and ``close`` (gate G7); ``reset`` is inherited from gym's ``MujocoEnv`` in
the upstream class, which the clone's AST cannot follow, so G7 may report ``MAYBE_ABSENT`` for it.  Nothing here
talks to a device.
"""

import random

#: The action Box of the gripper-motor world: sourced from the actuator ranges of the robot, not invented.
ACTION_LOW = [-1.0] * 7 + [0.0]
ACTION_HIGH = [1.0] * 7 + [1.05]
N_JOINTS = 8                                     # doorenv2/doorenv2/envs/doorenv.py:58-62
N_DISTANCE = 3                                   # get_dist_vec is a 3-vector
OBSERVATION_SIZE = 2 * N_JOINTS + N_DISTANCE     # 19, the size of util.py:61
MAX_EPISODE_STEPS = 512                          # doorenv2/doorenv2/__init__.py:6

#: Test data of the stand-in, not values of the MuJoCo model.
VELOCITY_DECAY = 0.5          # placeholder
ACTION_GAIN = 0.1             # placeholder
QPOS_FRACTION = 0.02          # placeholder: one environment step is 20 frames of 0.001 s
RESET_JOINT_NOISE = 0.1       # placeholder
GOAL_HALF_RANGE = 0.15        # placeholder
FINGER_BASE = [0.75, 0.35, 0.70]   # placeholder
KNOB_BASE = [0.80, 0.35, 0.70]     # placeholder


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, dtype=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype or "float32"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != self.shape[0]:
            return False
        return all(float(low) <= float(item) <= float(high)
                   for item, low, high in zip(value, self.low, self.high))


class FakeDoorEnvBlueV1:
    """A deterministic analytic world with the action and observation contract of ``DoorEnvBlueV1``."""

    def __init__(self, **_options):
        # DoorEnv sets action_space from actuator_ctrlrange (doorenv2/doorenv2/envs/doorenv.py:76-83).
        self.action_space = Box(ACTION_LOW, ACTION_HIGH, "float32")
        self._rng = random.Random(0)                                     # placeholder
        self._qpos = [0.0] * N_JOINTS                                    # placeholder
        self._qvel = [0.0] * N_JOINTS                                    # placeholder
        self._goal = [0.0, 0.0]                                          # placeholder
        self._tick = 0
        self._closed = False
        self._reset(None)

    def _observation(self):
        """qpos and qvel of the first nn joints plus the finger-to-knob distance (a 3-vector)."""
        finger = [base + self._qpos[index] for index, base in enumerate(FINGER_BASE)]   # placeholder
        knob = [base + (self._goal[index] if index < len(self._goal) else 0.0)
                for index, base in enumerate(KNOB_BASE)]                                # placeholder
        distance = [finger[index] - knob[index] for index in range(N_DISTANCE)]         # placeholder
        return list(self._qpos) + list(self._qvel) + distance

    def _reset(self, seed):
        """Set the stand-in's start state; ``seed`` fixes the pseudo-random draw."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        # The reset of a pull world: seven joint values from uniform(-0.1, 0.1) and a two-value goal from
        # uniform(-0.15, 0.15) (doorenv2/doorenv2/envs/doorenv_blue.py:57-74); the values are placeholders.
        self._qpos = [self._rng.uniform(-RESET_JOINT_NOISE, RESET_JOINT_NOISE) for _ in range(7)]  # placeholder
        self._qpos.append(0.0)                                                     # placeholder
        self._qvel = [0.0] * N_JOINTS
        self._goal = [self._rng.uniform(-GOAL_HALF_RANGE, GOAL_HALF_RANGE) for _ in range(2)]  # placeholder
        self._tick = 0

    def reset(self, seed=None, options=None):
        """Reset the world and return its observation (the legacy gym API, as DoorEnv inherits it)."""
        self._reset(seed)
        return self._observation()

    def step(self, action):
        """Apply one action, advance one environment step and return the legacy four-tuple result."""
        values = list(action)
        if len(values) != len(ACTION_LOW):
            raise ValueError(f"blue-doorenv-v1 takes {len(ACTION_LOW)} action values, got {len(values)}")
        for index in range(7):
            self._qvel[index] = (VELOCITY_DECAY * self._qvel[index]
                                 + ACTION_GAIN * float(values[index]))              # placeholder
            self._qpos[index] = (self._qpos[index]
                                 + QPOS_FRACTION * self._qvel[index])               # placeholder
        # The right gripper joint is the position actuator of the model (robot XML:18); the command is its
        # position target.
        self._qpos[7] = float(values[7])
        self._tick += 1
        # The upstream control penalty for a gripper world is -mean(square(a[:-2])).
        controls = values[:-2]
        reward = -sum(float(value) * float(value) for value in controls) / max(1, len(controls))  # placeholder
        reward -= abs(self._qpos[0])                                              # placeholder
        done = self._tick >= MAX_EPISODE_STEPS
        return self._observation(), reward, done, {"reward_ctrl": reward, "tick": self._tick}  # placeholder info

    def close(self):
        self._closed = True
