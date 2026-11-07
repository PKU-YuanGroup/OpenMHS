"""Fake backend of the DroneGymGazeboEnv-v0 driver: an analytic kinematic stand-in.

Why a fake: the upstream environment imports rospy, cv_bridge, OpenCV and the external
``mavros_px4_vehicle`` package, constructs ``PX4Vehicle(auto_connect=True)`` and waits for
Gazebo services and MAVROS topics (step1/new_drone_gym_gazebo_env.py:12-24, :36, :73-80).
Package code never imports or runs the clone, and the acceptance gate has no ROS, Gazebo,
PX4 SITL or MAVROS.  This module re-implements the public Gymnasium surface the bridge uses
(``reset``, ``step`` and ``close``; gate G7) plus the two duck-typed space attributes the
bridge reads (``action_space``, ``observation_space``).

What is modelled: the three discrete actions forward/left/right of the upstream environment
(step1/new_drone_gym_gazebo_env.py:39, :253-273), the 0.5 m position change per action
(:67-68, :233-251), the workspace and goal-termination rules (:307-348, :371-386), the
reward of :388-410 and the 225-step episode limit of the registration (:26-31).  One
``step`` is one setpoint transition, not one Gazebo physics step.

What is not modelled: no ROS, Gazebo, PX4 SITL, MAVROS, depth camera, CvBridge/OpenCV
preprocessing, physics, contacts, attitude or noise.  The observation the fake returns is
much smaller than the real ``(3, 80, 106)`` array and its image channels are zeros; the
real size and that gap are recorded in the driver notes and RESULT.json.  All numbers
below are either copied from the cited upstream line (the comment names it) or marked
``# placeholder`` test data; none is a Fact or a Limit.
"""

import random

#: step1/new_drone_gym_gazebo_env.py:39: the action space is Discrete(3), forward/left/right.
ACTION_COUNT = 3
#: step1/new_drone_gym_gazebo_env.py:45: the real observation space is Box(-1.0, 8.0, (3, 80, 106)).
OBSERVATION_LOW = -1.0
OBSERVATION_HIGH = 8.0
# placeholder: the fake returns a smaller image than the real 80 x 106 depth frame.
OBSERVATION_HEIGHT = 8
OBSERVATION_WIDTH = 8
#: step1/new_drone_gym_gazebo_env.py:51,53,55: start and desired point z is 1.5 m, desired x is 7.0 m.
START_Z = 1.5
DESIRED_X = 7.0
#: step1/new_drone_gym_gazebo_env.py:58-63: workspace bounds; the y bounds are local to start_point.y.
WORKSPACE_X_MIN = -0.5
WORKSPACE_X_MAX = 7.5
WORKSPACE_Y_MIN = -1.7
WORKSPACE_Y_MAX = 1.7
WORKSPACE_Z_MIN = 0.5
WORKSPACE_Z_MAX = 3.2
#: step1/new_drone_gym_gazebo_env.py:67-68: speed is 0.5 m/s for an action duration of 0.5 s.
SPEED = 0.5
#: step1/new_drone_gym_gazebo_env.py:69: the candidate y starting/desired points on later resets.
POSSIBLE_Y_START_DESIRED_POINTS = (0.0, -5.0, -10.0, -15.0)
#: step1/new_drone_gym_gazebo_env.py:307: the goal radius is 0.5 m.
GOAL_EPSILON = 0.5
#: step1/new_drone_gym_gazebo_env.py:66: the terminal goal reward.
GOAL_REWARD = 100.0
#: step1/new_drone_gym_gazebo_env.py:26-31: the registration's max_episode_steps is 225.
MAX_EPISODE_STEPS = 225


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: numeric bounds, a shape and a dtype name."""

    def __init__(self, low, high, shape, dtype="float32"):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = dtype


class FakeDroneGymGazeboEnv:
    """A kinematic stand-in for ``new_drone_gym_gazebo_env:DroneGymGazeboEnv``.

    ``reset(options=None, seed=None)`` follows the upstream keyword names (step1:94) and
    returns ``(observation, {})``; ``step(action)`` returns the upstream five-tuple
    ``(observation, reward, terminated, truncated, {})`` (step1:92).  The bridge supplies
    the seed and options as keywords, so the unusual upstream order (options before seed)
    is preserved without depending on it.
    """

    def __init__(self, **options):
        self._options = dict(options)
        self.action_space = Discrete(ACTION_COUNT)
        # The real shape is (3, 80, 106); the smaller placeholder shape keeps receipts bounded.
        self.observation_space = Box(OBSERVATION_LOW, OBSERVATION_HIGH,
                                     (3, OBSERVATION_HEIGHT, OBSERVATION_WIDTH))
        self._rng = random.Random(0)
        self._resets = 0
        self._start_y = 0.0
        self.closed = False
        self._terminated = False
        self._truncated = False
        self._tick = 0
        self._reset_state()

    # -- native Gymnasium surface -----------------------------------------
    def reset(self, options=None, seed=None):
        """Move to the episode start; the first reset keeps y=0, later ones choose a candidate lane.

        The seeded local RNG is fake-only: the upstream reset calls random.seed(seed) but draws the
        lane with np.random.choice (step1:103-104, :120), which that seed does not reach.
        """
        if seed is not None:
            self._rng.seed(int(seed))
        self._resets += 1
        if self._resets == 1:
            # step1:106-118: the first reset arms the drone at its initial y=0 position.
            self._start_y = 0.0
        else:
            # step1:120-121: later resets choose one of the candidate y points.
            self._start_y = self._rng.choice(POSSIBLE_Y_START_DESIRED_POINTS)
        self._reset_state()
        return self._observation(), {}

    def step(self, action):
        """Apply one forward/left/right setpoint and return the upstream five-tuple."""
        # step1:253-273: 0 is forward, 1 is left, 2 is right; any other value does not move.
        if action == 0:
            self._x += SPEED
        elif action == 1:
            self._y += SPEED
        elif action == 2:
            self._y -= SPEED
        self._z = START_Z
        self._tick += 1

        observation = self._observation()
        distance = self._distance()
        goal = self._in_desired_position()
        outside = not self._inside_workspace()
        # step1:350-369: the upstream detects collisions from roll/pitch/yaw; the fake has no
        # attitude or contact model, so it never reports a collision.
        self._terminated = outside or goal
        self._truncated = self._tick >= MAX_EPISODE_STEPS
        if not self._terminated:
            # step1:396-397: -1 plus the reduction in distance from the desired point.
            reward = -1.0 + (self._previous_distance - distance)
        elif goal:
            # step1:400-401: the terminal goal reward.
            reward = GOAL_REWARD
        else:
            # step1:405-406: the terminal failure reward.
            reward = -GOAL_REWARD
        self._previous_distance = distance
        return observation, reward, self._terminated, self._truncated, {}

    def close(self):
        """The upstream close shuts down the ROS node (step1:162-164); the fake only marks itself closed."""
        self.closed = True

    # -- model -------------------------------------------------------------
    def _reset_state(self):
        # step1:144-149: a later reset flies the drone to (start_point.x, start_point.y) and then to the
        # takeoff height, so the episode starts at the chosen lane's y, not at y=0 (model review).
        self._x = 0.0
        self._y = self._start_y
        self._z = START_Z
        self._desired_y = self._start_y
        self._tick = 0
        self._terminated = False
        self._truncated = False
        self._previous_distance = self._distance()

    def _distance(self):
        # step1:329-335: planar distance from the desired point; z is not compared.
        return ((self._x - DESIRED_X) ** 2 + (self._y - self._desired_y) ** 2) ** 0.5

    def _in_desired_position(self):
        # step1:307-325: within GOAL_EPSILON below and at most GOAL_EPSILON above, strictly.
        x_close = (self._x <= DESIRED_X + GOAL_EPSILON) and (self._x > DESIRED_X - GOAL_EPSILON)
        y_close = ((self._y <= self._desired_y + GOAL_EPSILON)
                   and (self._y > self._desired_y - GOAL_EPSILON))
        return x_close and y_close

    def _inside_workspace(self):
        # step1:337-348: x and z are absolute; y is relative to the episode's start point.
        return (WORKSPACE_X_MIN < self._x <= WORKSPACE_X_MAX
                and (WORKSPACE_Y_MIN + self._start_y) < self._y <= (WORKSPACE_Y_MAX + self._start_y)
                and WORKSPACE_Z_MIN < self._z <= WORKSPACE_Z_MAX)

    def _observation(self):
        """A small observation with the two position deltas in the last channel (step1:294-305)."""
        channels = [[[0.0 for _ in range(OBSERVATION_WIDTH)] for _ in range(OBSERVATION_HEIGHT)]
                    for _ in range(3)]
        # step1:296-297: the position map holds desired.x - x and desired.y - y.
        channels[2][0][0] = round(DESIRED_X - self._x, 2)
        channels[2][0][1] = round(self._desired_y - self._y, 2)
        return channels
