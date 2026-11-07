"""Fake backend of the multiworld GoalGridworld driver: the upstream grid world in pure Python.

Why a fake: the acceptance gate never installs or imports the clone, and ``multiworld`` needs the legacy ``gym``
package plus numpy.  This module re-implements ``multiworld.envs.gridworlds.goal_gridworld:GoalGridworld`` (the
class the driver names as ``native``) with the same public members: ``reset``, ``step``, ``move_agent``,
``from_s``, ``to_s``, ``get_obs``, ``imagine_obs`` and ``compute_reward``.  Every constant and rule below cites
the line of the clone at the pinned commit (12a05bfa4139f90741608ba409edebb95d7ef9ab).  The duck-typed space
classes (``Discrete``, ``Box`` and ``Dict``) carry the members the Gymnasium bridge reads.

What this is not: the upstream environment.  Differences, all in the driver's fidelity ``gaps``:

* the reset uses Python's ``random.Random(seed)``; upstream's ``reset()`` has no seed argument and draws from the
  unseeded global numpy generator (``goal_gridworld.py:71``);
* there is no rendering: upstream's ``render()`` needs OpenCV and writes a PNG to a hard-coded directory;
* the episode counter uses ``random.Random.randrange`` where upstream uses ``numpy.random.randint``.

Nothing here talks to a device.
"""

import copy
import random

# goal_gridworld.py:13 -- five discrete actions as row/column offsets
ACTIONS = [(-1, 0), (0, 1), (1, 0), (0, -1), (0, 0)]
# goal_gridworld.py:35 -- the constructor's default grid
DEFAULT_SIZE = (10, 10)
# goal_gridworld.py:53 -- the observation resolution used by get_obs and imagine_obs
RES = 1
# goal_gridworld.py:114 -- done once the step count is greater than this
STEP_LIMIT = 40
# goal_gridworld.py:83 -- the episode number is drawn from this range
EPISODE_MODULUS = 20
# goal_gridworld.py:133 and :137/:149 -- the cell weights of the two observation images
AGENT_WEIGHT = 1.0
NEIGHBOUR_WEIGHT = 0.2


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
    """Duck-typed ``gym.spaces.Box``: a low/high bound and the shape it flattens from."""

    def __init__(self, low, high, shape):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = "float64"

    def contains(self, value):
        flat = list(value)
        count = 1
        for item in self.shape:
            count *= item
        return len(flat) == count and all(self.low <= item <= self.high for item in flat)


class Dict:
    """Duck-typed ``gym.spaces.Dict``: a named mapping of the member spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = None


class FakeGoalGridworld:
    """``GoalGridworld`` without gym or numpy: the same members and the same grid rules."""

    def __init__(self, size=DEFAULT_SIZE, concatenated=False, seed=None, **_options):
        self.nrow, self.ncol = size
        self.concatenated = concatenated
        self.ACTIONS = ACTIONS
        self.nS = self.nrow * self.ncol
        self.nA = len(ACTIONS)
        self.lastaction = None
        self.action_space = Discrete(self.nA)
        observation_space = Box(low=0, high=1.0, shape=(self.nrow, self.ncol, 1))
        self.observation_space = Dict({
            "observation": observation_space,
            "achieved_goal": observation_space,
            "desired_goal": observation_space,
        })
        if self.concatenated:
            self.observation_space = Box(low=0, high=1.0, shape=(self.nrow * 2, self.ncol, 1))
        self.res = RES
        self.renderres = 10
        self._rng = random.Random(seed)
        self.state = {"count": 0, "agent": (0, 0)}
        self.goal_state = {"agent": (0, 0)}
        self.init_state = copy.deepcopy(self.state)
        self.episode = 0

    def from_s(self, s):
        row = int(s / self.ncol)
        return (row, s - row * self.ncol)

    def to_s(self, row, col):
        return row * self.ncol + col

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        self.state = {"count": 0}
        positions = self._rng.sample(range(self.nS), 2)
        agent_pos = self.from_s(positions[0])
        goal_pos = self.from_s(positions[1])
        self.state["agent"] = agent_pos
        self.goal_state = {"agent": goal_pos}
        self.lastaction = None
        self.init_state = copy.deepcopy(self.state)
        obs = self.get_obs()
        goal_obs = self.imagine_obs(self.goal_state)
        self.episode = self._rng.randrange(EPISODE_MODULUS)
        if self.concatenated:
            return obs + goal_obs
        return {"observation": obs, "desired_goal": goal_obs, "achieved_goal": obs}

    def move_agent(self, a):
        act = ACTIONS[a]
        pos = self.state["agent"]
        row, col = pos[0] + act[0], pos[1] + act[1]
        if row in range(self.nrow) and col in range(self.ncol):
            self.state["agent"] = (row, col)
            return (row, col)
        return pos

    def step(self, a):
        self.state["count"] += 1
        self.move_agent(a)
        self.lastaction = a
        success = 0
        done = self.state["count"] > STEP_LIMIT
        obs = self.get_obs()
        goal_obs = self.imagine_obs(self.goal_state)
        reward = self.compute_reward(obs, goal_obs, None)
        info = {"success": success, "count": self.state["count"], "done": done}
        if self.concatenated:
            return obs + goal_obs, reward, done, info
        return ({"observation": obs, "desired_goal": goal_obs, "achieved_goal": obs},
                reward, done, info)

    def _empty(self):
        return [0.0] * (self.nrow * self.ncol)

    def get_obs(self, mode="rgb"):
        if mode == "rgb":
            img = self._empty()
            row, col = self.state["agent"]
            img[self.to_s(row, col)] += AGENT_WEIGHT
            for x in (-1, 1):
                for y in (-1, 1):
                    if row + x in range(self.nrow) and col + y in range(self.ncol):
                        img[self.to_s(row + x, col + y)] += NEIGHBOUR_WEIGHT
            return img
        return None

    def imagine_obs(self, state, mode="rgb"):
        if mode == "rgb":
            img = self._empty()
            row, col = state["agent"]
            for x in (-1, 0, 1):
                for y in (-1, 0, 1):
                    if row + x in range(self.nrow) and col + y in range(self.ncol):
                        img[self.to_s(row + x, col + y)] += NEIGHBOUR_WEIGHT
            img[self.to_s(row, col)] = AGENT_WEIGHT
            return img
        return None

    def compute_reward(self, achieved_goal, desired_goal, info):
        error = sum((float(a) - float(d)) ** 2 for a, d in zip(achieved_goal, desired_goal))
        return -error
