"""Fake backend of the Mars Explorer driver: a pure Python stand-in for ``mars_explorer.envs:Explorer``.

Why a fake: the upstream package imports legacy ``gym``, ``numpy`` and ``pygame`` and its utilities import
``matplotlib`` (``mars-explorer/setup.py:9-13``, ``mars-explorer/mars_explorer/utils/randomMapGenerator.py:1-2``);
the acceptance gate runs none of them and package code never imports the clone.  This module re-implements the grid
world of ``mars_explorer/envs/explorer.py`` with Python's standard library only.  Every constant below is copied from
the default configuration in ``mars-explorer/mars_explorer/envs/settings.py`` and the rules from
``mars-explorer/mars_explorer/envs/explorer.py`` at the pinned commit, with the line cited next to each one.

The public members are the ones ``Explorer`` has (``reset``, ``step``, ``close``; gate G7); the space classes
duck-type ``gym.spaces.Discrete`` and ``Box`` because the bridge reads ``n``, ``start``, ``low``, ``high`` and
``shape``.  ``reset`` takes no seed, like the upstream method (``explorer.py:38``), so the bridge's legacy fallback
calls it without one.

What this is not: the upstream environment.  Differences, all listed in the driver's fidelity ``gaps``:

* the map and lidar use Python's ``random.Random`` and plain loops, not numpy's global generator and vectorised
  ray casting; a seed does not give the same map as the upstream environment (and upstream has no seed parameter);
* the observation is a flat list of 441 numbers; upstream returns a ``(21, 21, 1)`` float64 array, which the bridge
  also flattens for the JSON observation;
* there is no rendering and no viewer, no ``metadata``-driven pygame loop and no ``PassiveEnvChecker`` wrapper.

Nothing here talks to a device.
"""

import math
import random

# Default configuration: mars-explorer/mars_explorer/envs/settings.py
SIZE = 21                                       # settings.py:5
INITIAL = (0, 0)                                # settings.py:4
MOVEMENT_COST = 0.2                             # settings.py:7
OBSTACLES = 12                                  # settings.py:12
MARGINS = (1, 1)                                # settings.py:21
OBSTACLE_SIZE = (2, 2)                          # settings.py:23
MAX_STEPS = 400                                 # settings.py:25
BONUS_REWARD = 400                              # settings.py:26
COLLISION_REWARD = -400                         # settings.py:27
OUT_OF_BOUNDS_REWARD = -400                     # settings.py:28
LIDAR_RANGE = 6                                 # settings.py:31
LIDAR_CHANNELS = 32                             # settings.py:32
# mars-explorer/mars_explorer/utils/lidarSensor.py:6-7
LIDAR_RESOLUTION = 200
# mars-explorer/mars_explorer/envs/explorer.py:32-33
ACTION_COUNT = 4
CELL_EXPLORED = 0.3                             # explorer.py:50
CELL_OBSTACLE = 1.0                             # explorer.py:49
CELL_ROBOT_AFTER_RESET = 0.6                    # explorer.py:79
CELL_ROBOT_AFTER_STEP = 0.5                     # explorer.py:171


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = tuple(int(value) for value in shape)
        self.dtype = "float64"


class FakeExplorer:
    """The grid world of ``mars_explorer.envs:Explorer`` without gym, numpy, pygame or matplotlib."""

    def __init__(self):
        # explorer.py:17-35: the default configuration, the two spaces and the viewer flag.
        self.sizeX, self.sizeY = SIZE, SIZE
        self.SIZE = (SIZE, SIZE)
        self.movementCost = MOVEMENT_COST
        self.action_space = Discrete(ACTION_COUNT)
        self.observation_space = Box([0.0] * (SIZE * SIZE), [1.0] * (SIZE * SIZE), (SIZE, SIZE, 1))
        self.viewerActive = False
        self._rng = random.Random()

    # -- episodes ---------------------------------------------------------
    def reset(self):
        """Draw a map and return the first observation, as ``Explorer.reset`` does (explorer.py:38-92)."""
        self.maxSteps = MAX_STEPS
        self._grid = self._generate_map()
        self._ground_truth = [[CELL_OBSTACLE if cell else CELL_EXPLORED for cell in row] for row in self._grid]
        self._explored = [[0.0] * SIZE for _ in range(SIZE)]
        self.x, self.y = INITIAL
        self.state_trajectory = []
        self.reward_trajectory = []
        self.drone_trajectory = []
        self._activate_lidar()
        self._update_maps()
        self._output_map = [row[:] for row in self._explored]
        self._output_map[self.x][self.y] = CELL_ROBOT_AFTER_RESET
        self._new_state = self._flatten(self._output_map)
        self.reward = 0
        self.done = False
        self.timeStep = 0
        self.out_of_bounds = False
        self.collision = False
        self.action = 0
        return self._new_state

    def step(self, action):
        """Apply one move and return the legacy four-tuple of ``Explorer.step`` (explorer.py:207-216)."""
        if not self.action_space.contains(action):
            raise ValueError(f"{action!r} is not a valid action")
        self.action = action
        self._choice(action)
        self._activate_lidar()
        self._update_maps()
        self._output_map = [row[:] for row in self._explored]
        self._output_map[self.x][self.y] = CELL_ROBOT_AFTER_STEP
        self._new_state = self._flatten(self._output_map)
        self.timeStep += 1
        self._compute_reward()
        self._check_done()
        self.state_trajectory.append(self._new_state)
        self.reward_trajectory.append(self.reward)
        self.drone_trajectory.append([self.x, self.y])
        return self._new_state, self.reward, self.done, {}

    def close(self):
        """``Explorer.close`` only quits a viewer; the fake has none (explorer.py:219-221)."""
        self.viewerActive = False

    # -- map --------------------------------------------------------------
    def _generate_map(self):
        """Place the default obstacles at random, with the bounds of randomMapGenerator.py:71-72."""
        grid = [[0] * SIZE for _ in range(SIZE)]
        for _ in range(OBSTACLES):
            row = self._rng.randint(MARGINS[0], SIZE - 1 - MARGINS[0])
            column = self._rng.randint(MARGINS[1], SIZE - 1 - MARGINS[1])
            height = self._rng.randint(OBSTACLE_SIZE[0], OBSTACLE_SIZE[1] + 1)
            width = self._rng.randint(OBSTACLE_SIZE[0], OBSTACLE_SIZE[1] + 1)
            for dh in range(height):
                for dw in range(width):
                    grid[min(row + dh, SIZE - 1)][min(column + dw, SIZE - 1)] = 1
        return grid

    # -- movement ---------------------------------------------------------
    def _choice(self, choice):
        """``Explorer._choice``: 0/1 move on the first axis, 2/3 on the second (explorer.py:111-120)."""
        if choice == 0:
            self._move(1, 0)
        elif choice == 1:
            self._move(-1, 0)
        elif choice == 2:
            self._move(0, 1)
        elif choice == 3:
            self._move(0, -1)

    def _move(self, x, y):
        """Move unless a bound or an obstacle blocks it (explorer.py:123-141)."""
        candidate_x = self.x + x
        candidate_y = self.y + y
        in_x_axis = 0 <= candidate_x <= self.sizeX - 1
        in_y_axis = 0 <= candidate_y <= self.sizeY - 1
        in_obstacle = bool(self._grid[candidate_x][candidate_y]) if in_x_axis and in_y_axis else False
        if in_x_axis and in_y_axis and not in_obstacle:
            self.x += x
            self.y += y
        elif not in_x_axis or not in_y_axis:
            self.out_of_bounds = True
        elif in_obstacle:
            self.collision = True

    # -- lidar and maps ---------------------------------------------------
    def _activate_lidar(self):
        """Cast the 32 rays and collect the visible cells (lidarSensor.py:20-100)."""
        ranges = []
        for channel in range(LIDAR_CHANNELS):
            theta = 2.0 * math.pi * channel / LIDAR_CHANNELS
            dx, dy = math.cos(theta), math.sin(theta)
            nearest = LIDAR_RANGE
            for sample in range(LIDAR_RESOLUTION):
                distance = LIDAR_RANGE * sample / (LIDAR_RESOLUTION - 1)
                row = self._clip(round(self.x + distance * dx))
                column = self._clip(round(self.y + distance * dy))
                if self._grid[row][column]:
                    hit = math.hypot(row - self.x, column - self.y)
                    if hit < nearest:
                        nearest = hit
            ranges.append(nearest)
        indexes = []
        for channel in range(LIDAR_CHANNELS):
            theta = 2.0 * math.pi * channel / LIDAR_CHANNELS
            distance = min(ranges[channel] + 0.5, LIDAR_RANGE)
            dx, dy = math.cos(theta), math.sin(theta)
            for sample in range(LIDAR_RESOLUTION):
                reach = distance * sample / (LIDAR_RESOLUTION - 1)
                indexes.append((self._clip(round(self.x + reach * dx)),
                                self._clip(round(self.y + reach * dy))))
        self._lidar_indexes = indexes

    def _update_maps(self):
        """Mark the lidar cells with the ground truth and the robot cell (explorer.py:144-152)."""
        self._past_explored = [row[:] for row in self._explored]
        for row, column in self._lidar_indexes:
            self._explored[row][column] = self._ground_truth[row][column]
        self._explored[self.x][self.y] = CELL_ROBOT_AFTER_RESET

    # -- reward and terminal flags ---------------------------------------
    def _compute_reward(self):
        """Newly explored cells minus the movement cost (explorer.py:176-182)."""
        past = sum(1 for row in self._past_explored for cell in row if cell)
        current = sum(1 for row in self._explored for cell in row if cell)
        self.reward = current - past - self.movementCost

    def _check_done(self):
        """The four terminal rules of explorer.py:185-197, in the same order."""
        explored = sum(1 for row in self._explored for cell in row if cell)
        if self.timeStep > self.maxSteps:
            self.done = True
        elif explored > 0.95 * (self.sizeX * self.sizeY):
            self.done = True
            self.reward = BONUS_REWARD
        elif self.collision:
            self.done = True
            self.reward = COLLISION_REWARD
        elif self.out_of_bounds:
            self.done = True
            self.reward = OUT_OF_BOUNDS_REWARD

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _clip(value):
        return min(max(int(value), 0), SIZE - 1)

    @staticmethod
    def _flatten(matrix):
        return [float(cell) for row in matrix for cell in row]
