"""Fake backend of the gym-navigation driver: a pure Python stand-in for ``NavigationTrack-v0``.

Why a fake: the acceptance gate runs without gymnasium, numpy or pygame, and the pinned ``requirements.txt`` lines
1-3 name exactly those libraries, so package code never imports the clone.  This module restates the track-1
geometry, the five-ray scan, the Gaussian noise, the rewards and the spawn of
``gym_navigation.envs.navigation_track:NavigationTrack`` (the class the driver names as ``native``).  Every constant
and rule below cites the line of the clone at the pinned commit
(98be757c6aa2b2834cecbb7dde3c2c05e5f1b57b).

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* the random stream is Python's ``random.Random(seed)``; upstream draws from numpy's generator, so one seed gives
  different trajectories on the two;
* only track 1 is modelled (the default of the class); the fake refuses another track id;
* no rendering (upstream renders only with ``render_mode="human"``);
* observations are Python floats; upstream returns a numpy float64 array.

The public members are the ones NavigationTrack has (``reset``, ``step``, ``close``; gate G7).  A reset and a step
return the same tuple shapes as the upstream methods.  Nothing here talks to a device.
"""

import math
import random

# gym_navigation/envs/navigation_track.py:21-24
SHIFT_STANDARD_DEVIATION = 0.02
SENSOR_STANDARD_DEVIATION = 0.02
COLLISION_THRESHOLD = 0.4
# gym_navigation/envs/navigation_track.py:26-28
COLLISION_REWARD = -200.0
FORWARD_REWARD = 5.0
ROTATION_REWARD = -0.5
# gym_navigation/envs/navigation_track.py:30-33
SCAN_ANGLES = (-math.pi / 2, -math.pi / 4, 0.0, math.pi / 4, math.pi / 2)
SCAN_RANGE_MAX = 30.0                            # navigation_track.py:31
SCAN_RANGE_MIN = 0.2                             # navigation_track.py:32
N_MEASUREMENTS = len(SCAN_ANGLES)                # navigation_track.py:33
# gym_navigation/enums/action.py:21-23 (value -> linear_shift, angular_shift)
ACTIONS = {
    0: (0.2, 0.0),                               # FORWARD
    1: (0.04, 0.2),                              # ROTATE_RIGHT
    2: (0.04, -0.2),                             # ROTATE_LEFT
}
FORWARD = 0

# gym_navigation/enums/track.py:26-39: the twelve walls of TRACK1
TRACK1_WALLS = (
    (0.0, 0.0, 0.0, 20.0),
    (0.0, 20.0, 20.0, 20.0),
    (20.0, 20.0, 20.0, 8.5),
    (20.0, 8.5, 11.5, 8.5),
    (11.5, 8.5, 11.5, 0.0),
    (11.5, 0.0, 0.0, 0.0),
    (3.0, 3.0, 3.0, 17.0),
    (3.0, 17.0, 17.0, 17.0),
    (17.0, 17.0, 17.0, 11.5),
    (17.0, 11.5, 8.5, 11.5),
    (8.5, 11.5, 8.5, 3.0),
    (8.5, 3.0, 3.0, 3.0),
)
# gym_navigation/enums/track.py:41-48: the six spawn areas of TRACK1 as (x range, y range)
TRACK1_SPAWN_AREAS = (
    ((1.5, 1.5), (1.5, 18.5)),
    ((1.5, 18.5), (18.5, 18.5)),
    ((18.5, 18.5), (10.0, 18.5)),
    ((10.0, 18.5), (10.0, 10.0)),
    ((10.0, 10.0), (1.5, 10.0)),
    ((1.5, 10.0), (1.5, 1.5)),
)


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: one lower and one upper bound per element."""

    def __init__(self, low, high, shape, dtype="float64"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype


class _NoIntersection(Exception):
    """``gym_navigation.geometry.line``: the scan line does not meet the wall."""


class _Point:
    """``gym_navigation.geometry.point.Point`` (point.py:8-18)."""

    def __init__(self, x_coordinate, y_coordinate):
        self.x_coordinate = x_coordinate
        self.y_coordinate = y_coordinate

    def calculate_distance(self, other):
        return math.sqrt((self.x_coordinate - other.x_coordinate) ** 2
                         + (self.y_coordinate - other.y_coordinate) ** 2)


class _Line:
    """``gym_navigation.geometry.line.Line`` (line.py:14-82), including its slope-0 quirk for both axes."""

    def __init__(self, start, end):
        self.start = start
        self.end = end
        if start.x_coordinate == end.x_coordinate:        # vertical (line.py:28-30)
            self.slope = 0
            self.y_intercept = math.inf
        elif start.y_coordinate == end.y_coordinate:      # horizontal (line.py:31-33)
            self.slope = 0
            self.y_intercept = start.y_coordinate
        else:                                             # line.py:34-38
            self.slope = ((start.y_coordinate - end.y_coordinate)
                          / (start.x_coordinate - end.x_coordinate))
            self.y_intercept = start.y_coordinate - self.slope * start.x_coordinate

    def get_intersection(self, other):
        """``Line.get_intersection`` (line.py:40-70): raises ``_NoIntersection`` when the segments miss."""
        if self.slope == other.slope:
            raise _NoIntersection("Parallel lines")
        if self.start.x_coordinate == self.end.x_coordinate:
            x_coordinate = self.start.x_coordinate
            y_coordinate = other.slope * x_coordinate + other.y_intercept
        elif other.start.x_coordinate == other.end.x_coordinate:
            x_coordinate = other.start.x_coordinate
            y_coordinate = self.slope * x_coordinate + self.y_intercept
        elif self.start.y_coordinate == self.end.y_coordinate:
            y_coordinate = self.start.y_coordinate
            x_coordinate = (y_coordinate - other.y_intercept) / other.slope
        elif other.start.y_coordinate == other.end.y_coordinate:
            y_coordinate = other.start.y_coordinate
            x_coordinate = (y_coordinate - self.y_intercept) / self.slope
        else:
            x_coordinate = ((self.y_intercept - other.y_intercept)
                            / (other.slope - self.slope))
            y_coordinate = self.slope * x_coordinate + self.y_intercept
        intersection = _Point(x_coordinate, y_coordinate)
        if self.contains(intersection) and other.contains(intersection):
            return intersection
        raise _NoIntersection("No intersection")

    def contains(self, point):
        contains_x = (min(self.start.x_coordinate, self.end.x_coordinate)
                      <= point.x_coordinate
                      <= max(self.start.x_coordinate, self.end.x_coordinate))
        contains_y = (min(self.start.y_coordinate, self.end.y_coordinate)
                      <= point.y_coordinate
                      <= max(self.start.y_coordinate, self.end.y_coordinate))
        return contains_x and contains_y


class _Pose:
    """``gym_navigation.geometry.pose.Pose`` (pose.py:8-91)."""

    def __init__(self, position, yaw):
        self.position = position
        self.yaw = yaw

    def move(self, distance):
        if self.yaw == 0:
            self.position.y_coordinate += distance
        elif abs(self.yaw) == math.pi:
            self.position.y_coordinate -= distance
        else:
            slope = math.tan(math.pi / 2 - self.yaw)
            starting_x = self.position.x_coordinate
            if self.yaw < 0:
                self.position.x_coordinate -= math.sqrt(
                    distance ** 2 / (slope ** 2 + 1))
            else:
                self.position.x_coordinate += math.sqrt(
                    distance ** 2 / (slope ** 2 + 1))
            self.position.y_coordinate -= (
                slope * (starting_x - self.position.x_coordinate))

    def rotate(self, theta):
        self.yaw = self._bounded_yaw(self.yaw + theta)

    @staticmethod
    def _bounded_yaw(yaw):
        while yaw < -math.pi:
            yaw += 2 * math.pi
        while yaw > math.pi:
            yaw -= 2 * math.pi
        return yaw

    def shift(self, distance, theta):
        self.move(distance)
        self.rotate(theta)


class FakeNavigationTrack:
    """NavigationTrack on track 1 without gymnasium, numpy or pygame (gate G7 compares it with the upstream class)."""

    def __init__(self, render_mode=None, track_id=1):
        if render_mode is not None:
            raise ValueError("the fake NavigationTrack cannot render; use render_mode=None")
        if track_id != 1:
            raise ValueError("the fake NavigationTrack models track 1 only")
        self._rng = random.Random()
        self._pose = None
        self._ranges = []
        self._world = ()
        # navigation_track.py:46-51
        self.action_space = Discrete(len(ACTIONS))
        self.observation_space = Box(
            [SCAN_RANGE_MIN] * N_MEASUREMENTS,
            [SCAN_RANGE_MAX] * N_MEASUREMENTS,
            (N_MEASUREMENTS,),
            dtype="float64",
        )

    def reset(self, *, seed=None, options=None):
        """``Navigation.reset`` (navigation.py:89-102): reseed if asked, restore the walls, spawn and scan."""
        if seed is not None:
            self._rng = random.Random(seed)
        self._world = tuple(_Line(_Point(x1, y1), _Point(x2, y2))
                            for x1, y1, x2, y2 in TRACK1_WALLS)
        self._init_pose()                             # navigation_track.py:125-131
        self._update_scan()                           # navigation_track.py:62-77
        return list(self._ranges), {}

    def step(self, action):
        """``Navigation.step`` (navigation.py:53-67) on NavigationTrack (navigation_track.py:53-116)."""
        if not self.action_space.contains(action):
            raise ValueError(f"Invalid action {action} ({type(action)})")
        if self._pose is None:
            raise RuntimeError("Call reset before using step method.")
        theta = (self._rng.gauss(0, SHIFT_STANDARD_DEVIATION)
                 + ACTIONS[action][1])                # navigation_track.py:55-56
        distance = (self._rng.gauss(0, SHIFT_STANDARD_DEVIATION)
                    + ACTIONS[action][0])             # navigation_track.py:57-58
        self._pose.shift(distance, theta)             # navigation_track.py:59
        self._update_scan()                           # navigation_track.py:60
        observation = list(self._ranges)              # navigation_track.py:99-100
        terminated = self._collision_occurred()       # navigation_track.py:102-106
        truncated = False                             # navigation.py:60
        reward = self._calculate_reward(action)       # navigation_track.py:108-116
        return observation, reward, terminated, truncated, {}   # navigation_track.py:122-123

    def close(self):
        """``Navigation.close`` (navigation.py:129-132): nothing is open in a headless fake."""

    # -- internals -------------------------------------------------------------
    def _init_pose(self):
        # navigation_track.py:125-131
        area = self._rng.choice(TRACK1_SPAWN_AREAS)
        x_coordinate = self._rng.uniform(area[0][0], area[0][1])
        y_coordinate = self._rng.uniform(area[1][0], area[1][1])
        yaw = self._rng.uniform(-math.pi, math.pi)
        self._pose = _Pose(_Point(x_coordinate, y_coordinate), yaw)

    def _update_scan(self):
        # navigation_track.py:62-77
        ranges = []
        for scan_angle in SCAN_ANGLES:
            scan_pose = _Pose(_Point(self._pose.position.x_coordinate,
                                     self._pose.position.y_coordinate),
                              self._pose.yaw + scan_angle)
            scan_pose.move(SCAN_RANGE_MAX)
            scan_line = _Line(_Point(self._pose.position.x_coordinate,
                                     self._pose.position.y_coordinate),
                              scan_pose.position)
            min_distance = SCAN_RANGE_MAX
            for wall in self._world:
                try:
                    intersection = scan_line.get_intersection(wall)
                except _NoIntersection:
                    continue
                distance = self._pose.position.calculate_distance(intersection)
                min_distance = min(min_distance, distance)
            ranges.append(min_distance
                          + self._rng.gauss(0, SENSOR_STANDARD_DEVIATION))
        self._ranges = ranges

    def _collision_occurred(self):
        # navigation_track.py:105-106
        return any(value < COLLISION_THRESHOLD for value in self._ranges)

    def _calculate_reward(self, action):
        # navigation_track.py:108-116
        if self._collision_occurred():
            return COLLISION_REWARD
        if action == FORWARD:
            return FORWARD_REWARD
        return ROTATION_REWARD
