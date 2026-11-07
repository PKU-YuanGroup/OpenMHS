"""Fake backend of the gym-simplegrid driver: a pure-Python stand-in for ``gym_simplegrid.envs:SimpleGridEnv``.

Why a fake: the upstream package imports gymnasium, numpy and matplotlib (``requirements.txt:1-3`` and
``setup.py:15-19``) and builds a ``GridRenderer`` even when nothing is rendered (``gym_simplegrid/envs/simple_grid.py:
45-47``), and package code never imports the clone.  This module re-implements the discrete state machine of
``SimpleGridEnv`` and the 200-step ``TimeLimit`` that ``gymnasium.make("SimpleGrid-4x4-v0")`` adds from the
registration's ``max_episode_steps`` (``gym_simplegrid/__init__.py:28-33``).  Every rule and constant below cites the
line of the clone at the pinned commit (6ded2fcf684727b27b5569688cad6f92bc3bc52b).

The public members are the ones ``SimpleGridEnv`` has (``reset``, ``step``, ``close`` and ``get_reward``; gate G7),
and the space class duck-types ``gymnasium.spaces.Discrete`` (the bridge reads ``n`` and ``start``).

What this is not: the upstream environment.  It draws the sampled start and goal with Python's ``random.Random``
while upstream draws them from numpy's generator (``simple_grid.py:68`` and ``:167-168``), so one seed gives
different positions on the two.  It has no renderer (``simple_grid.py:116-131``) and no ``OrderEnforcing`` or
``PassiveEnvChecker`` wrapper.  The driver's fidelity ``gaps`` say all of this.  Nothing here talks to a device.
"""

import random

# gym_simplegrid/__init__.py:5: the rows of MAP_4x4, the map SimpleGrid-4x4-v0 is registered with.
MAP_4X4 = ["0000", "0101", "0001", "1000"]                     # placeholder
# gym_simplegrid/__init__.py:31: max_episode_steps of SimpleGrid-4x4-v0, applied by the TimeLimit wrapper that
# gymnasium.make adds.  The bridge drives a pre-built environment object, so this fake applies the limit itself.
REGISTERED_MAX_EPISODE_STEPS = 200                              # placeholder
# gym_simplegrid/envs/simple_grid.py:22-27 and :42: one action per direction.
MOVES = {0: (-1, 0), 1: (1, 0), 2: (0, -1), 3: (0, 1)}
# gym_simplegrid/envs/simple_grid.py:140-144: the default reward map.
GOAL_REWARD = 1.0                                               # placeholder
STEP_REWARD = -0.1                                              # placeholder
INVALID_REWARD = -1.0                                           # placeholder


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class FakeSimpleGridEnv:
    """``SimpleGridEnv`` without gymnasium, numpy or matplotlib: ``reset``, ``step`` and ``close``."""

    metadata = {"render_modes": ["human", "rgb_array", "ansi"], "render_fps": 8}   # simple_grid.py:20

    def __init__(self, obstacle_map=None, render_mode=None, render_fps=8, max_steps=None):
        # The upstream constructor requires obstacle_map (simple_grid.py:29-35).  The driver's backend factory
        # passes no options, so the default carries the map of the registered SimpleGrid-4x4-v0 environment
        # (gym_simplegrid/__init__.py:5 and :32); a supplied map is parsed like MapParser.parse (parser.py:33-65).
        if obstacle_map is None:
            obstacle_map = MAP_4X4
        self._grid = self._parse_map(obstacle_map)
        self.nrow = len(self._grid)
        self.ncol = len(self._grid[0])
        self.max_steps = max_steps
        # The pre-registered 4x4 environment carries a 200-step TimeLimit; a max_steps argument would be the
        # environment's own bound instead.
        self._time_limit = REGISTERED_MAX_EPISODE_STEPS if max_steps is None else max_steps
        self.action_space = Discrete(len(MOVES))                    # simple_grid.py:42
        self.observation_space = Discrete(self.nrow * self.ncol)    # simple_grid.py:43
        self.render_mode = render_mode
        self.agent_xy = (0, 0)                                      # simple_grid.py:50
        self.start_xy = (0, 0)
        self.goal_xy = (0, 0)
        self.step_count = 0
        self.last_reward = 0.0
        self.last_action = None
        self._rng = random.Random()
        self._closed = False

    # -- parsing and grid logic (the GridModel methods of gym_simplegrid/grid.py) -----------------------------
    @staticmethod
    def _parse_map(obstacle_map):
        """``MapParser.parse`` (parser.py:33-65): four validation rules, then 0/1 cells."""
        if not obstacle_map:
            raise ValueError("The provided obstacle map is empty.")
        n_cols = len(obstacle_map[0])
        if not all(len(row) == n_cols for row in obstacle_map):
            raise ValueError("Inconsistent column lengths detected in obstacle_map.")
        grid = []
        for row in obstacle_map:
            cells = []
            for char in row:
                if char not in ("0", "1"):
                    raise ValueError("Invalid characters detected. Only '0' and '1' are allowed.")
                cells.append(int(char))
            grid.append(cells)
        return grid

    def _is_in_bounds(self, row, col):
        """grid.py:51."""
        return 0 <= row < self.nrow and 0 <= col < self.ncol

    def _is_free(self, row, col):
        """grid.py:69-71: an out-of-bounds cell is not free; 0 is free and 1 is an obstacle (grid.py:28-29)."""
        if not self._is_in_bounds(row, col):
            return False
        return self._grid[row][col] == 0

    def _to_index(self, row, col):
        """grid.py:89."""
        return row * self.ncol + col

    def _to_xy(self, index):
        """grid.py:105."""
        return (index // self.ncol, index % self.ncol)

    def _get_next_xy(self, row, col, d_row, d_col):
        """grid.py:136-138."""
        return (row + d_row, col + d_col)

    def _sample_valid_xy(self):
        """grid.py:157-169: a uniform draw over the free cells, in row-major order."""
        free = [(row, col) for row in range(self.nrow) for col in range(self.ncol)
                if self._grid[row][col] == 0]
        if not free:
            raise RuntimeError("The grid contains no free cells to sample from.")
        return free[self._rng.randrange(len(free))]

    def _is_valid_xy(self, xy):
        """simple_grid.py:156."""
        return self._is_in_bounds(*xy) and self._is_free(*xy)

    def _parse_loc_option(self, loc):
        """simple_grid.py:158-169: None samples a free cell, an int is a flat index, anything else passes through."""
        if loc is None:
            return self._sample_valid_xy()
        return self._to_xy(loc) if isinstance(loc, int) and not isinstance(loc, bool) else loc

    def _check_integrity(self):
        """simple_grid.py:171-174."""
        for name, pos in (("Start", self.start_xy), ("Goal", self.goal_xy)):
            if not self._is_valid_xy(pos):
                raise ValueError(f"Invalid {name} position: {pos}")

    def _get_obs(self):
        """simple_grid.py:146-147."""
        return self._to_index(*self.agent_xy)

    def _get_info(self):
        """simple_grid.py:149-150."""
        return {"agent_xy": self.agent_xy, "step_count": self.step_count}

    # -- gymnasium.Env surface (simple_grid.py:57-131) ------------------------------------------------------
    def reset(self, seed=None, options=None):
        """``simple_grid.py:57-80``: reseed, parse the location options, check them, start the episode."""
        if seed is not None:
            # upstream: super().reset(seed=seed) replaces np_random with a seeded numpy Generator
            # (simple_grid.py:68); this fake uses Python's random.Random instead.
            self._rng = random.Random(seed)
        options = options or {}
        self.start_xy = self._parse_loc_option(options.get("start_loc"))
        self.goal_xy = self._parse_loc_option(options.get("goal_loc"))
        self._check_integrity()
        self.agent_xy = self.start_xy
        self.step_count = 0
        self.last_reward = 0.0
        self.last_action = None
        self._closed = False
        return self._get_obs(), self._get_info()

    def step(self, action):
        """``simple_grid.py:82-114`` and the 200-step TimeLimit of the registration."""
        if self._closed:
            raise RuntimeError("the environment is closed")
        self.last_action = action
        row, col = self.agent_xy
        dr, dc = MOVES[action]
        target_xy = self._get_next_xy(row, col, dr, dc)
        is_valid = self._is_in_bounds(*target_xy) and self._is_free(*target_xy)
        self.agent_xy = target_xy if is_valid else self.agent_xy
        self.last_reward = self.get_reward(target_xy)
        self.step_count += 1
        terminated = self.agent_xy == self.goal_xy
        truncated = False
        if self._time_limit is not None and self.step_count >= self._time_limit:
            if not terminated:
                truncated = True
        return self._get_obs(), self.last_reward, terminated, truncated, self._get_info()

    def get_reward(self, xy):
        """``simple_grid.py:133-144``: the default reward map."""
        if not self._is_valid_xy(xy):
            return INVALID_REWARD
        if xy == self.goal_xy:
            return GOAL_REWARD
        return STEP_REWARD

    def close(self):
        """``simple_grid.py:130-131``: the upstream close releases the renderer; this fake has none."""
        self._closed = True
