"""Fake backend of the itomori driver: a pure Python stand-in for the Navigation2DEnv environment.

Why a fake: the acceptance gate runs without gymnasium, and package code never imports the clone.  This module
re-implements the parts of ``itomori.envs:Navigation2DEnv`` (the class the driver names as ``native``) that the
Gymnasium bridge uses: the two spaces, ``reset``, ``step`` and ``close``.  Every constant and rule below cites the
line of the clone at the pinned commit (0c2da173bf989736f919772d3c6cbc2fea098b72).  The public members of
``FakeNavigation2DEnv`` are members of the upstream class (gate G7); ``Box`` and ``Dict`` duck-type the gymnasium
space classes the bridge reads (``low``, ``high``, ``shape``, ``spaces``).

What this is not: the upstream environment.  It models the default 10x10 no-obstacle map only, with the default
``default_uav_args`` and default reward weights.  It has no obstacles, no chance constraint, no rendering, no GPS
noise draw and no numpy arrays.  These differences are in the fidelity ``gaps`` of the driver and in the package
README.  The fake keeps the upstream's state rule that ``reset`` does not restore ``gps_uncertainty``.

Nothing here talks to a device.
"""

import math

# itomori/envs/navigation2d_configs/maps/10x10/10x10_NoObstacle.json:2-5
SIZE = 10.0
ORIGIN = (1.0, 1.0)
DESTINATION = (9.0, 9.0)

# itomori/envs/configs.py:2-13 (default_uav_args)
VELOCITY_INITIAL = 0.0
VELOCITY_MIN = 0.0
VELOCITY_MAX = 50.0
VELOCITY_CHANGE_MIN = -10.0
VELOCITY_CHANGE_MAX = 100.0
ANGLE_INITIAL = 0.0
ANGLE_CHANGE_MIN = -10.0
ANGLE_CHANGE_MAX = 10.0
DELTA_T = 0.1
GPS_UNCERTAINTY_INITIAL = 0.5
GPS_UNCERTAINTY_INCREMENT = 0.02

# itomori/envs/navigation2d.py:46 and :24-28
DESTINATION_TOLERANCE = 1.5
REWARD_WEIGHTS = {"distance": 0.9, "steps": 0.1, "risk": 0.0}


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element (a flat float array)."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float64"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces`` and recurses into each member."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None


class FakeNavigation2DEnv:
    """Navigation2DEnv without numpy: ``reset(seed, options)`` and ``step(action)`` return what the upstream does."""

    def __init__(self):
        # navigation2d.py:100-111: the Box order is [angle change, velocity change]
        self.action_space = Box(
            [ANGLE_CHANGE_MIN, VELOCITY_CHANGE_MIN],
            [ANGLE_CHANGE_MAX, VELOCITY_CHANGE_MAX],
        )
        # navigation2d.py:79-98
        self.observation_space = Dict({
            "origin": Box([0.0, 0.0], [50.0, 50.0]),
            "destination": Box([0.0, 0.0], [SIZE, SIZE]),
            "agent_location": Box(
                [0.0, 0.0, VELOCITY_MIN, -math.inf, 0.0, 0.0],
                [SIZE, SIZE, VELOCITY_MAX, math.inf, math.inf, math.inf],
            ),
        })
        # navigation2d.py:143-154: the uav args are read once; reset does not restore gps_uncertainty
        self.gps_uncertainty = GPS_UNCERTAINTY_INITIAL
        self.gps_uncertainty_initial = GPS_UNCERTAINTY_INITIAL
        self.gps_uncertainty_increment = GPS_UNCERTAINTY_INCREMENT
        self.delta_T = DELTA_T
        self.velocity_min = VELOCITY_MIN
        self.velocity_max = VELOCITY_MAX
        self.velocity_change_min = VELOCITY_CHANGE_MIN
        self.velocity_change_max = VELOCITY_CHANGE_MAX
        self.velocity_initial = VELOCITY_INITIAL
        self.angle_initial = ANGLE_INITIAL
        self.angle_change_min = ANGLE_CHANGE_MIN
        self.angle_change_max = ANGLE_CHANGE_MAX
        self.destination_tolerance = DESTINATION_TOLERANCE
        self.reward_weights = dict(REWARD_WEIGHTS)
        self.size = SIZE
        self.origin = list(ORIGIN)
        self.destination = list(DESTINATION)
        self.obstacles = []
        self.starting_agent_location = [ORIGIN[0], ORIGIN[1], VELOCITY_INITIAL, ANGLE_INITIAL]
        self.timestep = 0
        self.previous_agent_location = None
        self._agent_location = None
        self.agent_location_history = []
        self.risk = 0.0
        self.window = None

    def reset(self, seed=None, options=None):
        """navigation2d.py:217-235: the start is fixed, so seed and options change nothing here."""
        self.timestep = 0
        self.previous_agent_location = None
        self.risk = self.chance_constraint(self.starting_agent_location[:2])
        self._agent_location = list(self.starting_agent_location) + [self.risk, self.gps_uncertainty]
        self.agent_location_history = [list(self._agent_location)]
        return self._get_obs(), self._get_info()

    def step(self, action):
        """navigation2d.py:237-261."""
        self.timestep += 1
        self.gps_uncertainty += self.gps_uncertainty_increment
        self.previous_agent_location = list(self._agent_location)
        location = self._move(action)
        self.risk = self.chance_constraint(location[:2])
        self._agent_location = list(location) + [self.risk, self.gps_uncertainty]
        self.agent_location_history.append(list(self._agent_location))
        observation = self._get_obs()
        reward = self.reward()
        terminated = self.is_done()
        truncated = False
        info = self._get_info()
        return observation, reward, terminated, truncated, info

    def close(self):
        """navigation2d.py:561-564: there is no window in the fake."""
        self.window = None

    def _get_obs(self):
        """navigation2d.py:178-183."""
        return {
            "origin": list(self.origin),
            "destination": list(self.destination),
            "agent_location": list(self._agent_location),
        }

    def _get_info(self):
        """navigation2d.py:185-192."""
        return {
            "risk": self.risk,
            "failed": self.is_failed(),
            "destination_tolerance": self.destination_tolerance,
            "agent_location_history": [list(entry) for entry in self.agent_location_history],
            "obstacles": list(self.obstacles),
        }

    def is_failed(self):
        """navigation2d.py:194-200: the fake has no obstacles, so only the bounds can fail."""
        return self.is_outofbounds(self._agent_location[:2])

    def is_done(self):
        """navigation2d.py:202-212."""
        distance = math.hypot(self._agent_location[0] - self.destination[0],
                              self._agent_location[1] - self.destination[1])
        if distance < self.destination_tolerance:
            return True
        return self.is_failed()

    def is_outofbounds(self, location):
        """navigation2d.py:214-215."""
        return any(value <= 0 for value in location) or any(value >= self.size for value in location)

    def chance_constraint(self, point, obstacles=None):
        """navigation2d.py:601-659: no obstacles in the default map, so the chance is exactly 0."""
        obstacles = self.obstacles if obstacles is None else obstacles
        if obstacles:
            raise NotImplementedError("the fake models the no-obstacle map only")
        return 0.0

    def reward(self):
        """navigation2d.py:349-369."""
        if self.is_failed():
            return math.inf
        distance = math.hypot(self._agent_location[0] - self.destination[0],
                              self._agent_location[1] - self.destination[1])
        steps = len(self.agent_location_history)
        risk = self._agent_location[4]
        return (self.reward_weights["distance"] * distance
                + self.reward_weights["steps"] * steps
                + self.reward_weights["risk"] * risk)

    def _move(self, action):
        """navigation2d.py:325-345: the Box order is [angle change, velocity change]."""
        angle_change, velocity_change = action
        x, y, velocity, angle = self._agent_location[:4]
        delta_t = self.delta_T
        next_velocity = min(max(velocity + velocity_change * delta_t, self.velocity_min), self.velocity_max)
        next_angle = min(max(angle + angle_change * delta_t, self.angle_change_min), self.angle_change_max)
        next_x = x + next_velocity * math.cos(next_angle) * delta_t \
            + velocity_change * math.cos(next_angle) * ((delta_t ** 2) / 2)
        next_x = min(max(next_x, 0.0), self.size)
        next_y = y + next_velocity * math.sin(next_angle) * delta_t \
            + velocity_change * math.sin(next_angle) * ((delta_t ** 2) / 2)
        next_y = min(max(next_y, 0.0), self.size)
        return [next_x, next_y, next_velocity, next_angle]
