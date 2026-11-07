"""Fake backend of the Habitat-Lab driver: a pure Python stand-in for ``gym.make("Habitat-v0")``.

Why a fake: habitat-lab needs habitat-sim, the legacy ``gym`` 0.22 package and a dataset
(``habitat-lab/requirements.txt:1-3``), and package code never imports the clone.  This module re-implements the
small part of the Gym contract that ``habitat.core.environments:GymHabitatEnv`` exposes for the point-navigation
test configuration: ``reset`` returns an observation, ``step`` returns ``(observation, reward, done, info)``
(``habitat-lab/habitat/gym/gym_wrapper.py:254-281``), and the action space is ``Discrete(4)`` for the four
navigation actions (``test/test_gym_wrapper.py:89-93``, ``habitat-lab/habitat/config/habitat/task/pointnav.yaml:3-7``).

What this is not: the upstream environment or habitat-sim.  The fake is kinematic; it moves and turns the agent by
the configured step size and angle and computes the point-goal vector.  Differences, all listed in the fidelity
``gaps`` of the driver:

* no rigid-body dynamics, contacts, articulated arm or rendering;
* the rgb and depth observations are small flat stand-ins (the point-nav test config declares 256 x 256 sensors,
  ``habitat-lab/habitat/config/benchmark/nav/pointnav/pointnav_habitat_test.yaml:14-20``);
* the reward models only the distance-to-goal decrease, not the slack and success rewards of ``RLTaskEnv.get_reward``
  (``habitat-lab/habitat/core/environments.py:73-84``).

The public members are the ones the Gym interface of the upstream environment has (``reset``, ``step``, ``close``;
gate G7).  Numbers marked ``# placeholder`` are test data and are never used as a fact or a limit.
"""

import math
import random

# habitat-lab/habitat/config/default_structured_configs.py:1791: forward_step_size in metres
FORWARD_STEP_SIZE = 0.25
# habitat-lab/habitat/config/default_structured_configs.py:1792: turn_angle in degrees
TURN_ANGLE_RAD = math.radians(10)
# habitat-lab/habitat/config/benchmark/nav/pointnav/pointnav_habitat_test.yaml:10: max_episode_steps
MAX_EPISODE_STEPS = 500
# habitat-lab/habitat/config/default_structured_configs.py:405-406: the point goal is polar, dimensionality 2
POINT_GOAL_DIM = 2
# habitat-lab/habitat/config/default_structured_configs.py:1573: the depth sensor's max_depth is 10.0
DEPTH_MAX = 10.0
# habitat-lab/habitat/config/benchmark/nav/pointnav/pointnav_habitat_test.yaml:16-20: the real sensors are 256 x 256
REAL_RGB_SHAPE = (256, 256, 3)
REAL_DEPTH_SHAPE = (256, 256, 1)
# placeholder: the goal is drawn uniformly from this square, the agent starts at the origin facing -z
GOAL_RANGE_M = 2.0
GOAL_LOW, GOAL_HIGH = -GOAL_RANGE_M, GOAL_RANGE_M

#: The four action ids of the point-nav task, in the order of habitat-lab/habitat/config/habitat/task/pointnav.yaml:3-7.
ACTION_STOP, ACTION_FORWARD, ACTION_TURN_LEFT, ACTION_TURN_RIGHT = 0, 1, 2, 3


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1`` (the bridge reads ``n``)."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"


class Box:
    """Duck-typed ``gym.spaces.Box``: flat low/high bounds and a shape (the bridge reads ``low``/``high``)."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gym.spaces.Dict``: named sub-spaces (the bridge reads ``spaces``)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None
        self.dtype = None


def _wrap_angle(angle):
    """Normalise an angle to ``[-pi, pi]`` (the point-goal azimuth)."""

    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


class FakeHabitatEnv:
    """The Gym surface of ``GymHabitatEnv`` for the point-navigation test config, without habitat-sim."""

    def __init__(self, **_options):
        self.action_space = Discrete(4)
        # The observation keys and order are those of the point-nav configuration: two simulator sensors and the
        # goal sensor (``pointnav.yaml:13-14``, ``rgbd_agent.yaml:4-5``).  The flat shapes are placeholders.
        self.observation_space = Dict(
            {
                "rgb": Box([0.0] * 12, [255.0] * 12, (12,)),         # placeholder flat stand-in for (256, 256, 3)
                "depth": Box([0.0] * 4, [DEPTH_MAX] * 4, (4,)),      # placeholder flat stand-in for (256, 256, 1)
                "pointgoal_with_gps_compass": Box(
                    [0.0, -math.pi], [1.0e3, math.pi], (POINT_GOAL_DIM,)
                ),
            }
        )
        self._rng = random.Random()
        self._seed = None
        self._agent = [0.0, 0.0]                 # placeholder: x, z in metres
        self._heading = 0.0                      # placeholder: radians, zero along -z
        self._goal = [0.0, 0.0]
        self._previous_distance = 0.0
        self._elapsed_steps = 0
        self._done = False
        self._started = False

    # -- Gym surface -------------------------------------------------------------------------------------------
    def reset(self, *, seed=None, options=None):
        """Start a new episode and return its first observation.

        ``seed`` is the modern Gym keyword; the upstream legacy ``gym`` 0.22 wrapper seeds through ``env.seed()``
        instead (``habitat-lab/habitat/core/env.py:481-482``), so the bridge's fallback is what a real run takes.
        The fake accepts the keyword so the seeded path is exercised here.
        """
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        self._agent = [0.0, 0.0]                                      # placeholder
        self._heading = 0.0                                           # placeholder
        self._goal = [self._rng.uniform(GOAL_LOW, GOAL_HIGH) for _ in range(2)]  # placeholder
        self._previous_distance = self._distance()
        self._elapsed_steps = 0
        self._done = False
        self._started = True
        return self._observation()

    def step(self, action):
        """Apply one discrete navigation action; return ``(observation, reward, done, info)``."""
        if not self._started:
            raise AssertionError("Call reset before using step method.")
        if self._done:
            raise AssertionError("Episode over, call reset before using step method.")
        if action not in (ACTION_STOP, ACTION_FORWARD, ACTION_TURN_LEFT, ACTION_TURN_RIGHT):
            raise AssertionError(f"{action!r} is not a point-nav action")

        if action == ACTION_FORWARD:
            self._agent[0] += FORWARD_STEP_SIZE * math.sin(self._heading)
            self._agent[1] -= FORWARD_STEP_SIZE * math.cos(self._heading)
        elif action == ACTION_TURN_LEFT:
            self._heading += TURN_ANGLE_RAD
        elif action == ACTION_TURN_RIGHT:
            self._heading -= TURN_ANGLE_RAD

        self._elapsed_steps += 1
        distance = self._distance()
        # The distance-to-goal reward is -(new_distance - previous_distance) (habitat-lab/habitat/tasks/nav/nav.py:1004-1006).
        reward = self._previous_distance - distance
        self._previous_distance = distance
        if action == ACTION_STOP or self._elapsed_steps >= MAX_EPISODE_STEPS:
            self._done = True
        info = {"distance_to_goal": distance}                        # placeholder metric, test data
        return self._observation(), reward, self._done, info

    def close(self):
        """Stop the episode; the environment is not reused after close."""
        self._started = False
        self._done = True

    # -- internals ---------------------------------------------------------------------------------------------
    def _distance(self):
        dx = self._goal[0] - self._agent[0]
        dz = self._goal[1] - self._agent[1]
        return math.hypot(dx, dz)

    def _observation(self):
        dx = self._goal[0] - self._agent[0]
        dz = self._goal[1] - self._agent[1]
        distance = math.hypot(dx, dz)
        azimuth = _wrap_angle(math.atan2(dx, -dz) - self._heading)
        return {
            # placeholder: a 12-number flat stand-in for the real 256 x 256 x 3 rgb sensor
            "rgb": [float(self._elapsed_steps % 256)] + [0.0] * 11,
            # placeholder: a 4-number flat stand-in for the real 256 x 256 x 1 depth sensor
            "depth": [0.5, 1.5, 2.5, 3.5],
            "pointgoal_with_gps_compass": [distance, azimuth],
        }
