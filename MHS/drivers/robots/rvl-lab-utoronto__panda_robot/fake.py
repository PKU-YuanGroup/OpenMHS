"""Fake backend of the panda_robot driver: a pure-Python stand-in for PandaReacherEnv.

The upstream environment is an old Gym class that commands a real Franka Emika Panda through
ROS.  The acceptance gate cannot import it: the clone is Python 2 source, its ``envs`` package
imports a missing module, and a live run needs rospy, MoveIt, franka_ros, a Franka control computer
and a real arm.  This module therefore reproduces the interface and the source-coded semantics that
the environment itself owns:

* ``step(action)`` returns the old Gym four-tuple ``(observation, reward, done, info)``;
* ``observation`` is the six values of end-effector position followed by end-effector velocity;
* ``reward`` is minus the Euclidean distance to the goal (dense default), and ``done`` is
  ``distance < threshold``;
* ``reset()`` returns the start observation, and ``close()`` stops the fake's velocity.

The upstream calls ``PandaClient.set_ee_velocity`` and sleeps one 10 Hz period inside ``step``; the
fake instead integrates its placeholder velocity for one step.  It does not import or execute any
upstream code, does not use ROS and never talks to a robot.  All numbers below are test data, not
device facts, and are marked ``# placeholder``.  The action space is the one exception the SDK
allows a Gymnasium fake: the bridge derives the step bounds from it, and this package does not set
``action_space_ref`` because the upstream class defines no action space and no bound.
"""

import math

# Test data only: the upstream environment defines no action space and does not bound or scale the
# three Twist values (panda_reacher_env.py:38-43,60-61).
ACTION_LOW, ACTION_HIGH = -1.0, 1.0  # placeholder
N_ACTION = 3  # placeholder: three Twist linear components in apply_velocity_action
# Test data only: one integration step stands in for the upstream 10 Hz rate.sleep().
DT = 0.1  # placeholder
# Test data only: the upstream starts from PandaClient.go_home(), whose position needs the arm/URDF.
START_POSITION = [0.30, 0.0, 0.25]  # placeholder
# Test data only: the upstream hole_goal and threshold are different values cited in driver.py.
GOAL = [0.20, 0.0, 0.25]  # placeholder
THRESHOLD = 0.04  # placeholder
# Test data only: a broad observation envelope for the placeholder state.
OBSERVATION_BOUND = 10.0  # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads low, high, shape and dtype."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class FakePandaReacherEnv:
    """PandaReacherEnv without ROS: the old Gym four-tuple interface over a placeholder point mass."""

    def __init__(self, **_options):
        self.action_space = Box([ACTION_LOW] * N_ACTION, [ACTION_HIGH] * N_ACTION, (N_ACTION,))
        self.observation_space = Box([-OBSERVATION_BOUND] * 6, [OBSERVATION_BOUND] * 6, (6,))
        self._seed = 0  # placeholder
        self._position = list(START_POSITION)  # placeholder
        self._velocity = [0.0, 0.0, 0.0]  # placeholder
        self._goal = list(GOAL)  # placeholder
        self.threshold = THRESHOLD  # placeholder
        self.sparse = False
        self._closed = False

    def reset(self, seed=None, options=None):
        """Start a new episode at the placeholder start pose and return the observation."""
        if seed is not None:
            self._seed = int(seed)
        self._position = list(START_POSITION)  # placeholder
        self._velocity = [0.0, 0.0, 0.0]  # placeholder
        self._closed = False
        return self.get_obs()

    def apply_velocity_action(self, action):
        """Store the three Twist linear components for the next integration step."""
        values = [float(value) for value in action]
        if len(values) != N_ACTION:
            raise ValueError(f"the action has {N_ACTION} linear components, got {len(values)}")
        self._velocity = values

    def compute_distance(self, achieved_goal, desired_goal):
        """Euclidean distance between the first three values of two goals (placeholder arithmetic)."""
        return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(achieved_goal[:3], desired_goal[:3])))

    def compute_reward(self, achieved_goal, desired_goal, info=0):
        """Dense reward minus distance; the sparse branch returns -1 outside the threshold."""
        distance = self.compute_distance(achieved_goal, desired_goal)
        if not self.sparse:
            return -distance
        return -int(distance >= self.threshold)

    def preprocess_action(self, action):
        """The upstream returns the action unchanged."""
        return action

    def step(self, action):
        """Apply one placeholder velocity step and return the old Gym four-tuple."""
        action = self.preprocess_action(action)
        self.apply_velocity_action(action)
        self._position = [self._position[i] + self._velocity[i] * DT for i in range(3)]
        obs = self.get_obs()
        achieved_goal = obs[:3]
        reward = self.compute_reward(achieved_goal, self._goal)
        distance = self.compute_distance(achieved_goal, self._goal)
        done = bool(distance < self.threshold)
        info = {"shaped_reward": -distance}
        return (obs, reward, done, info)

    def get_obs(self):
        """End-effector position followed by velocity, six placeholder values."""
        return list(self._position) + list(self._velocity)

    def close(self):
        """Stop the placeholder velocity; the fake owns no ROS resources."""
        self._velocity = [0.0, 0.0, 0.0]  # placeholder
        self._closed = True
