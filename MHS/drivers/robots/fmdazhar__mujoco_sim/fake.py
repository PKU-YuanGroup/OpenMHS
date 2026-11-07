"""Fake backend for gh.fmdazhar/mujoco_sim: a pure-Python stand-in for ``ur5ePegInHoleGymEnv_easy-v0``.

The gate cannot import the upstream package (it needs MuJoCo 3.2.5, gymnasium 1.0.0, glfw and PyOpenGL, and
package code never imports the clone).  This module therefore models the contract of one registered
environment, ``ur5ePegInHoleGymEnv_easy-v0``, without MuJoCo:

* the easy variant applies ``XYZGripperCloseEnv``, so the action is the first three elements of the base
  seven-element Box, i.e. x, y and z in [-1, 1] (mujoco_sim/envs/wrappers.py:134-138);
* the easy variant applies ``CustomObsWrapper`` and ``FlattenObservation``, so the observation is one flat
  array of the six kept members: controller_pose (6), ur5e/tcp_pose (6), ur5e/tcp_vel (3),
  ur5e/wrist_force (3), ur5e/wrist_torque (3) and connector_pose (6), 27 values in total
  (mujoco_sim/__init__.py:27-42);
* ``reset(seed, options)`` accepts the Gymnasium reset signature and returns ``(observation, info)``;
* ``step(action)`` returns ``(observation, reward, terminated, truncated, info)`` like the upstream step
  (mujoco_sim/envs/ur5e_pick_gym_connector.py:406-476);
* the episode truncates at the upstream ``_max_episode_steps`` of 1000 (mujoco_sim/config/config.py:15).

What this is not: the MuJoCo model.  The motion here is a deliberately simple kinematic stand-in, every
numeric start value and scale below is test data marked ``# placeholder``, and the fake was never compared
with the upstream environment.  Contacts, actuator forces, sensors, the peg-in-hole reward and task-success
termination are not modelled; the driver's fidelity ``gaps`` list these omissions.

The public methods are limited to ``reset`` and ``step`` (gate G7 checks them against the AST surface of the
upstream class, which defines both at
mujoco_sim/envs/ur5e_pick_gym_connector.py:257 and :406).  Nothing here talks to a device.
"""

import random

#: The easy variant's action is x, y and z only (mujoco_sim/envs/wrappers.py:138).
ACTION_SIZE = 3
#: Six kept observation members: 6 + 6 + 3 + 3 + 3 + 6 (mujoco_sim/__init__.py:27-36).
OBSERVATION_SIZE = 27
#: The upstream episode limit (mujoco_sim/config/config.py:15).
MAX_EPISODE_STEPS = 1000
#: The upstream observation Box bound (mujoco_sim/envs/ur5e_pick_gym_connector.py:172).
OBSERVATION_BOUND = 1e6

#: Test data of this stand-in, never a sourced fact.
STEP_SCALE = 0.001          # placeholder
RESET_NOISE = 0.001         # placeholder
START_HEIGHT = 0.05         # placeholder
CONNECTOR_POSE = [0.35, 0.0, 0.05, 0.0, 0.0, 0.0]  # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None, dtype=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = dtype or "float64"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != self.shape[0]:
            return False
        return all(float(low) <= float(item) <= float(high)
                   for item, low, high in zip(value, self.low, self.high))


class FakeUR5ePegInHoleEnv:
    """A deterministic kinematic world with the action and observation contract of the easy variant."""

    def __init__(self, **_options):
        # The action space XYZGripperCloseEnv installs and the observation space FlattenObservation
        # produces (mujoco_sim/envs/wrappers.py:134-138 and mujoco_sim/__init__.py:38-42).
        self.action_space = Box([-1.0, -1.0, -1.0], [1.0, 1.0, 1.0], (ACTION_SIZE,), "float32")
        self.observation_space = Box([-OBSERVATION_BOUND] * OBSERVATION_SIZE,
                                     [OBSERVATION_BOUND] * OBSERVATION_SIZE,
                                     (OBSERVATION_SIZE,), "float32")
        self._rng = random.Random(0)                                     # placeholder
        self._position = [0.0, 0.0, 0.0]                                 # placeholder
        self._velocity = [0.0, 0.0, 0.0]                                 # placeholder
        self._tick = 0
        self._reset(None)

    def _reset(self, seed):
        """Set the stand-in's start state; ``seed`` fixes the pseudo-random draw."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        noise = [self._rng.uniform(-RESET_NOISE, RESET_NOISE) for _ in range(ACTION_SIZE)]  # placeholder
        self._position = [noise[0], noise[1], START_HEIGHT + noise[2]]   # placeholder
        self._velocity = [0.0, 0.0, 0.0]                                 # placeholder
        self._tick = 0

    def _observation(self):
        """The flattened easy-variant observation: six members in the upstream Dict order."""
        controller_pose = [self._position[0], self._position[1], self._position[2],
                           0.0, 0.0, 0.0]                                 # placeholder
        tcp_pose = [self._position[0], self._position[1], self._position[2],
                    0.0, 0.0, 0.0]                                        # placeholder
        tcp_vel = list(self._velocity)                                   # placeholder
        wrist_force = [0.0, 0.0, 0.0]                                    # placeholder
        wrist_torque = [0.0, 0.0, 0.0]                                   # placeholder
        return controller_pose + tcp_pose + tcp_vel + wrist_force + wrist_torque + list(CONNECTOR_POSE)

    def reset(self, seed=None, options=None):
        """Gymnasium reset: return the initial observation and an empty info object."""
        self._reset(seed)
        return self._observation(), {}

    def step(self, action):
        """Apply one action and return the next observation, reward, flags and info."""
        values = [float(value) for value in action]
        if len(values) != ACTION_SIZE:
            raise ValueError(f"ur5ePegInHoleGymEnv_easy-v0 takes {ACTION_SIZE} action values, got {len(values)}")
        self._velocity = [STEP_SCALE * value for value in values]        # placeholder
        self._position = [position + velocity
                          for position, velocity in zip(self._position, self._velocity)]  # placeholder
        self._tick += 1
        # The sparse reward is -1 until task completion and 0 on completion
        # (mujoco_sim/config/config.py:92-93 and mujoco_sim/envs/ur5e_pick_gym_connector.py:721-723).
        reward = -1.0
        truncated = self._tick >= MAX_EPISODE_STEPS
        return self._observation(), reward, False, truncated, {"is_success": False}
