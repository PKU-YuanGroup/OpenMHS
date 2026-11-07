"""Analytic fake backend for GazeboCircuitTurtlebotLidar-v0.

Why a fake: package code never imports the pinned clone, and the acceptance
gate runs without ROS Melodic, Gazebo 9 or legacy ``gym``.  This module
re-implements the public surface of
``gym_gazebo.envs.turtlebot.gazebo_circuit_turtlebot_lidar:GazeboCircuitTurtlebotLidarEnv``:
``action_space``, ``reset()``, ``step(action)`` and ``discretize_observation``.
The five-sector distances and the per-tick closings are placeholder test data,
not device measurements, and every one is marked below.  The action meanings,
the discretization rule, the minimum range and the reward values come from the
cited upstream lines.

What this is not: the upstream environment.  It starts no ROS launch file,
talks to no Gazebo server, publishes no Twist and reads no LaserScan.  It
models no pose, velocity, collision geometry or wall-clock timing.  Its
``reset(seed=...)`` accepts the bridge's seed keyword as an extension; the
upstream ``reset()`` takes no argument.  All differences are listed in the
driver's fidelity ``gaps``.
"""

import math
import random

#: The upstream collision threshold (gazebo_circuit_turtlebot_lidar.py:33).
MIN_RANGE = 0.2
#: The upstream discrete buckets for an infinite and a NaN beam (lines 38-41).
INFINITY_BUCKET = 6
NAN_BUCKET = 0

#: Test data, not a fact: the five sector distances the fake starts with.
START_RANGES = [4.0, 3.0, 2.0, 3.0, 4.0]  # placeholder
#: Test data, not a fact: how much a placeholder sector closes per tick.
FORWARD_CLOSURE = 0.5  # placeholder
TURN_CLOSURE = 0.35  # placeholder
#: Test data, not a fact: the lowest placeholder distance, so the next tick is terminal.
DISTANCE_FLOOR = 0.1  # placeholder

#: The upstream action meanings (#F,L,R; lines 60-74) and the placeholder sectors they close.
_FORWARD_SECTORS = (1, 2, 3)  # placeholder: front, centre and rear-facing sectors
_LEFT_SECTORS = (0, 1)  # placeholder: left sectors
_RIGHT_SECTORS = (3, 4)  # placeholder: right sectors


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class _Scan:
    """The part of a sensor_msgs/LaserScan message ``discretize_observation`` reads."""

    def __init__(self, ranges):
        self.ranges = list(ranges)


class FakeGazeboCircuitTurtlebotLidarEnv:
    """The upstream environment without ROS or Gazebo."""

    def __init__(self, **_options):
        self.action_space = Discrete(3)  # gazebo_circuit_turtlebot_lidar.py:26
        self.reward_range = (-math.inf, math.inf)  # line 27
        self.np_random = None
        self._ranges = list(START_RANGES)  # placeholder
        self._last_state = None
        self._seed()  # line 29

    def _seed(self, seed=None):
        """Upstream ``_seed`` replacement: keep a seeded Python generator (line 48-50)."""
        self.np_random = random.Random(seed)
        return [seed]

    def discretize_observation(self, data, new_ranges):
        """The upstream five-sector discretization and collision rule (lines 31-46)."""
        discretized_ranges = []
        done = False
        mod = len(data.ranges) / new_ranges
        for i, item in enumerate(data.ranges):
            if i % mod == 0:
                if item == float("inf"):
                    discretized_ranges.append(INFINITY_BUCKET)
                elif item != item:  # NaN
                    discretized_ranges.append(NAN_BUCKET)
                else:
                    discretized_ranges.append(int(item))
            if MIN_RANGE > item > 0:
                done = True
        return discretized_ranges, done

    def reset(self, seed=None, options=None):
        """Reset to the placeholder start state and return ``(state, done)`` like upstream.

        The seed keyword is a bridge extension; ``options`` is accepted and ignored because the
        upstream reset defines none (gazebo_circuit_turtlebot_lidar.py:102-137).
        """
        if seed is not None:
            self._seed(int(seed))
        self._ranges = list(START_RANGES)  # placeholder
        state, done = self.discretize_observation(_Scan(self._ranges), 5)
        self._last_state = state
        return state, done

    def step(self, action):
        """Apply one of the three upstream actions and return the four-value legacy result (line 100)."""
        if self._last_state is None:
            raise RuntimeError("reset() must be called before step()")
        if action == 0:
            sectors, closure = _FORWARD_SECTORS, FORWARD_CLOSURE
        elif action == 1:
            sectors, closure = _LEFT_SECTORS, TURN_CLOSURE
        elif action == 2:
            sectors, closure = _RIGHT_SECTORS, TURN_CLOSURE
        else:
            # The upstream code publishes nothing for an unknown action but still reads and returns a scan.
            sectors, closure = (), 0.0
        for index in sectors:
            self._ranges[index] = max(DISTANCE_FLOOR, self._ranges[index] - closure)  # placeholder
        state, done = self.discretize_observation(_Scan(self._ranges), 5)
        if done:
            reward = -200  # line 98
        elif action == 0:
            reward = 5  # line 94
        else:
            reward = 1  # line 96
        self._last_state = state
        return state, reward, done, {}
