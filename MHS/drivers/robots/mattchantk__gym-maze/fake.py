"""Fake backend of the gym-maze driver: a pure Python stand-in for ``gym_maze.envs:MazeEnvSample5x5``.

Why a fake: the upstream environment imports ``gym``, ``pygame`` and ``numpy`` (``setup.py:12``), and
its constructor opens a pygame display by default (``maze_env.py:18-25``, ``maze_view_2d.py:14-16``).
Package code never imports the clone, so this module re-implements the grid rules of the upstream
``MazeEnv`` (``maze_env.py``) and of ``MazeView2D.move_robot``/``Maze.is_open``
(``maze_view_2d.py``).  The public members are the ones ``MazeEnv`` has that the bridge uses
(``reset``, ``step``, ``seed``; gate G7), plus the ``action_space`` and ``observation_space`` objects
whose fields the Gymnasium bridge reads.

What this is not: the upstream environment.  It has no pygame viewer, no rendering and no numpy
arrays, and is only the fixed 5x5 sample family member named by the driver.  The wall bitmask table
below is the content of ``maze_samples/maze2d_5x5.npy`` at the pinned commit; it is test data of this
fake and is not copied into a Fact, a Limit or the reference.  The driver's fidelity ``gaps`` list
these differences.

Nothing here talks to a device.
"""

import random

# maze_env.py:14: ACTION = ["N", "S", "E", "W"]
ACTION = ("N", "S", "E", "W")
# maze_view_2d.py:286-291: the compass offsets
COMPASS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
# placeholder: the wall bitmasks of the shipped 5x5 sample maze
# (gym_maze/envs/maze_samples/maze2d_5x5.npy).  Test data, never a Fact or a Limit.
MAZE_CELLS = (
    (2, 4, 1, 2, 1),   # placeholder
    (4, 4, 8, 4, 2),   # placeholder
    (8, 1, 1, 1, 1),   # placeholder
    (2, 4, 4, 4, 8),   # placeholder
    (4, 8, 1, 1, 1),   # placeholder
)
# maze_view_2d.py:40-43: entrance at zeros(2), goal at maze_size - (1, 1)
MAZE_SIZE = (5, 5)
ENTRANCE = (0, 0)
GOAL = (MAZE_SIZE[0] - 1, MAZE_SIZE[1] - 1)
# gym_maze/__init__.py:7: max_episode_steps of maze-v0, applied by the TimeLimit wrapper gym.make adds
MAX_EPISODE_STEPS = 2000


def _walls(cell):
    """``Maze.get_walls_status`` (maze_view_2d.py:486-494); a set bit means that wall is open."""
    return {
        "N": (cell & 0x1) >> 0,
        "E": (cell & 0x2) >> 1,
        "S": (cell & 0x4) >> 2,
        "W": (cell & 0x8) >> 3,
    }


def _is_open(robot, direction):
    """``Maze.is_open`` (maze_view_2d.py:442-453): in bounds and either side of the wall is open."""
    dx, dy = COMPASS[direction]
    x, y = robot[0] + dx, robot[1] + dy
    if not (0 <= x < MAZE_SIZE[0] and 0 <= y < MAZE_SIZE[1]):
        return False
    this_wall = bool(_walls(MAZE_CELLS[robot[0]][robot[1]])[direction])
    other_wall = bool(_walls(MAZE_CELLS[x][y])[OPPOSITE[direction]])
    return this_wall or other_wall


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"


class Box:
    """Duck-typed two-element ``gym.spaces.Box``; the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high, dtype="int64"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype


class FakeMazeEnvSample5x5:
    """The 5x5 sample maze without gym, pygame or numpy: ``reset()``, ``step(action)``, ``seed(seed)``.

    ``reset`` returns the observation only, as the upstream class does (``maze_env.py:97``).  The raw
    ``MazeEnv.step`` returns the legacy four-tuple (``maze_env.py:90``); the registered ``maze-v0``
    environment is wrapped by ``gym.make`` with ``max_episode_steps=2000`` (``gym_maze/__init__.py:7``),
    and this fake follows the registered environment: it applies that limit and returns the five-tuple
    ``(observation, reward, terminated, truncated, info)`` the Gymnasium bridge consumes.
    """

    metadata = {"render.modes": ["human", "rgb_array"]}   # maze_env.py:10-12

    def __init__(self, **_options):
        # maze_env.py:44: spaces.Discrete(2*len(maze_size)); a 5x5 world therefore has four actions
        self.action_space = Discrete(2 * len(MAZE_SIZE))
        # maze_env.py:46-49: Box(low=zeros(2), high=maze_size - ones(2), dtype=int64)
        self.observation_space = Box([0, 0], [MAZE_SIZE[0] - 1, MAZE_SIZE[1] - 1])
        self.state = None
        self.steps_beyond_done = None
        self.done = False
        self._robot = list(ENTRANCE)
        self._elapsed_steps = 0
        self._random = random.Random()
        self.seed()                                        # maze_env.py:56
        self.reset()                                       # maze_env.py:57

    def seed(self, seed=None):
        """``MazeEnv.seed`` (maze_env.py:69-71): seed the generator and return ``[seed]``."""
        self._random = random.Random(seed)
        return [seed]

    def reset(self):
        """``MazeEnv.reset`` (maze_env.py:92-97): back to the entrance, fixed zero state, no seed use."""
        self._robot = list(ENTRANCE)
        self.state = [0.0, 0.0]                            # np.zeros(2) upstream
        self.steps_beyond_done = None
        self.done = False
        self._elapsed_steps = 0
        return list(self.state)

    def step(self, action):
        """``MazeEnv.step`` (maze_env.py:73-90) plus the registered TimeLimit of 2000 steps."""
        if isinstance(action, int):
            direction = ACTION[action]                     # maze_env.py:74-75
        else:
            direction = action
        if direction not in COMPASS:
            raise ValueError(f"dir cannot be {direction}. The only valid dirs are {list(COMPASS)}.")
        if _is_open(self._robot, direction):               # maze_view_2d.py:97-103
            dx, dy = COMPASS[direction]
            self._robot = [self._robot[0] + dx, self._robot[1] + dy]
        if tuple(self._robot) == GOAL:                     # maze_env.py:79-82
            reward = 1
            done = True
        else:
            reward = -0.1 / (MAZE_SIZE[0] * MAZE_SIZE[1])
            done = False
        self.state = list(self._robot)                     # maze_env.py:86
        self._elapsed_steps += 1
        # gym_maze/__init__.py:7: max_episode_steps=2000, applied by the TimeLimit wrapper of gym.make
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        return list(self.state), reward, done, truncated, {}

