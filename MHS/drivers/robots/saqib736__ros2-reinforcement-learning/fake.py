"""Analytic fake backend for the RacingBotEnv-v0 driver.

This is a pure Python stand-in for ``rl_racing.gazebo_env:GazeboEnv``.  The
gate cannot import the upstream environment because it needs ``rclpy``, ROS 2,
Gazebo, ``numpy`` and ``gymnasium`` (gazebo_env.py:3-9), and package code never
imports or runs the clone.

The fake keeps the upstream public environment surface (``reset``, ``step``,
``seed``, ``render`` and ``close``) and the two spaces, so the Gymnasium bridge
sees the same action shape and observation shape.  It follows the upstream
action-to-velocity conversion (gazebo_env.py:95-103), the 60-value laser
observation scaled by 10 (gazebo_env.py:29,105-110), the crash test against
``min_obstacle_dist`` (gazebo_env.py:112-119) and the reward terms
(gazebo_env.py:121-145).  It does not model Gazebo physics, rays, contacts or
odometry, and it returns immediately instead of waiting for ROS messages.

Every number that is not copied from the upstream source above is placeholder
test data and is marked ``# placeholder``.  It is not a device fact, limit or
safety bound.
"""

import random

# gazebo_env.py:25-27: the upstream action space is Box([-1, -1], [1, 1]).
ACTION_LOW = [-1.0, -1.0]
ACTION_HIGH = [1.0, 1.0]
# gazebo_env.py:29: the upstream observation space is Box(0, 1, shape=(60,)).
OBSERVATION_LOW = 0.0
OBSERVATION_HIGH = 1.0
OBSERVATION_SIZE = 60
# gazebo_env.py:20-23: the upstream environment constants.
MAX_LINEAR_VEL = 1.0
MIN_LINEAR_VEL = 0.0
ANGULAR_VEL = 1.0
MIN_OBSTACLE_DIST = 0.2
# gazebo_connections.py:55: infinite laser readings are replaced with 10 m.
MAX_LASER_RANGE = 10.0
# Test data, not a device fact: nominal forward travel and turn-away effect
# per fake control transition.  The upstream has no fixed transition time in
# the clone; these numbers only make the analytic stand-in move.
FORWARD_TRAVEL = 0.2  # placeholder
TURN_AWAY = 0.05  # placeholder
START_CLEARANCE = 8.0  # placeholder
START_JITTER = 0.25  # placeholder
BEAM_SPREAD = 0.01  # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads low, high, shape and dtype."""

    def __init__(self, low, high, shape):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = "float32"


class FakeGazeboEnv:
    """Kinematic stand-in with the public attributes the Gymnasium bridge reads."""

    def __init__(self, **_options):
        self.action_space = Box(ACTION_LOW, ACTION_HIGH, (2,))
        self.observation_space = Box(OBSERVATION_LOW, OBSERVATION_HIGH, (OBSERVATION_SIZE,))
        self.max_linear_vel = MAX_LINEAR_VEL
        self.min_linear_vel = MIN_LINEAR_VEL
        self.angular_vel = ANGULAR_VEL
        self.min_obstacle_dist = MIN_OBSTACLE_DIST
        self.np_random = random.Random(0)  # placeholder seed for the stand-in
        self.episode_num = 0
        self.cumulated_episode_reward = 0.0
        self.last_action = [0.0, 0.0]
        self._clearance = START_CLEARANCE  # placeholder
        self.current_linear_vel_ = 0.0
        self._current_angular_vel = 0.0
        self.laser_data_ = []
        self.done_laser_ = True
        self.done_odom_ = True
        self.resetSim_done_ = True
        self._closed = False
        self.resetSim()

    def seed(self, seed=None):
        """Create the fake generator; matches the upstream seed() return shape."""
        self.np_random = random.Random(seed)
        return [seed]

    def resetSim(self):
        """Reset the analytic world; the upstream version calls the Gazebo reset service."""
        self._clearance = min(
            MAX_LASER_RANGE,
            max(MIN_OBSTACLE_DIST, START_CLEARANCE + self.np_random.uniform(-START_JITTER, START_JITTER)),
        )  # placeholder start clearance
        self.current_linear_vel_ = 0.0
        self._current_angular_vel = 0.0
        self.laser_data_ = self._scan()
        self.done_laser_ = True
        self.done_odom_ = True
        self.resetSim_done_ = True

    def spin(self):
        """The fake has no ROS graph to wait on; both callbacks are already satisfied."""
        self.done_laser_ = True
        self.done_odom_ = True

    def step(self, action):
        """Apply one action and return the upstream five-tuple."""
        self._set_action(action)
        self._advance()
        self.spin()
        obs = self._get_obs()
        done = self._is_done()
        reward = self._compute_reward(obs, done, action)
        self.cumulated_episode_reward += reward
        self.last_action = [float(action[0]), float(action[1])]
        return obs, float(reward), bool(done), False, {}

    def reset(self, seed=None, options=None):
        """Reset the fake world and return ``(observation, info)`` like GazeboEnv.reset."""
        if seed is not None:
            self.seed(seed)
        self.resetSim()
        self._update_episode()
        self.spin()
        obs = self._get_obs()
        self.last_action = [0.0, 0.0]
        return obs, {}

    def render(self):
        """The upstream render() is a no-op."""
        return None

    def close(self):
        """Mark the fake closed; there is no rclpy node to destroy."""
        self._closed = True

    def publish_velocity(self, velocity):
        """Store the velocity the upstream would publish as geometry_msgs/Twist."""
        self.current_linear_vel_ = float(velocity[0])
        self._current_angular_vel = float(velocity[1])

    def get_laser_scan(self):
        return self.laser_data_

    def get_current_linear_vel(self):
        # placeholder: the upstream returns the odometry twist.linear.x (gazebo_connections.py:61-66);
        # the fake has no odometry and returns the last commanded linear velocity instead.
        return self.current_linear_vel_

    def _update_episode(self):
        self.episode_num += 1
        self.cumulated_episode_reward = 0.0

    def _set_action(self, action):
        """The upstream normalized-action conversion (gazebo_env.py:95-103)."""
        action_linear = (
            (self.max_linear_vel * (action[0] + 1))
            + (self.min_linear_vel * (1 - action[0]))
        ) / 2
        action_angular = (
            (self.angular_vel * (action[1] + 1))
            + (-self.angular_vel * (1 - action[1]))
        ) / 2
        self.publish_velocity([action_linear, action_angular])

    def _advance(self):
        """Move the placeholder scalar clearance; this replaces the Gazebo physics step."""
        delta = (-self.current_linear_vel_ * FORWARD_TRAVEL) + (abs(self._current_angular_vel) * TURN_AWAY)
        self._clearance = min(MAX_LASER_RANGE, max(0.0, self._clearance + delta))
        self.laser_data_ = self._scan()

    def _scan(self):
        """A 60-beam placeholder profile whose minimum is the current clearance."""
        middle = (OBSERVATION_SIZE - 1) / 2.0
        return [
            min(MAX_LASER_RANGE, max(0.0, self._clearance + abs(index - middle) * BEAM_SPREAD))
            for index in range(OBSERVATION_SIZE)
        ]

    def _get_obs(self):
        """The upstream divides every laser reading by 10 (gazebo_env.py:105-110)."""
        return [distance / MAX_LASER_RANGE for distance in self.laser_data_]

    def _is_done(self):
        """The upstream crash test (gazebo_env.py:112-119)."""
        return any(distance < self.min_obstacle_dist for distance in self.laser_data_)

    def _compute_reward(self, obs, done, action):
        """The upstream reward terms (gazebo_env.py:121-145)."""
        linear_velocity = self.get_current_linear_vel()
        progress_reward = linear_velocity * 5

        min_distance = min(obs)
        safety_penalty = (
            -1.0 * (self.min_obstacle_dist - min_distance)
            if min_distance < self.min_obstacle_dist
            else 0.0
        )
        crash_penalty = -20.0 if done else 0.0
        alive_reward = 0.1
        repeat_action_penalty = (
            -2.0
            if [float(action[0]), float(action[1])] == self.last_action
            else 0.0
        )
        return progress_reward + safety_penalty + crash_penalty + alive_reward + repeat_action_penalty
