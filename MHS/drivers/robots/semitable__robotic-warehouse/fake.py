"""Fake backend of the RWARE driver: a pure Python stand-in for the registered ``rware-tiny-1ag-v2``.

Why a fake: the acceptance gate does not install or import the clone (``rware`` needs gymnasium, numpy, networkx and
pyglet), and package code never imports the clone.  This module re-implements the parts of
``rware.warehouse:Warehouse`` that the registered tiny one-agent environment uses: the grid layout, the random
reset, the five discrete actions, the shelf carrying and delivery rules, the per-agent observation vector and the
500-step episode limit.  Every constant and rule cites the line of the clone at the pinned commit
96fbc64e3eae5fee915e0d390f864fa06ddccd47.  The public members are the ones ``Warehouse`` has (``reset``, ``step``,
``close``; gate G7); the space classes duck-type ``gymnasium.spaces.Tuple``, ``Discrete`` and ``Box`` (the bridge
reads ``spaces``, ``n``, ``start``, ``low``, ``high`` and ``shape``).

What this is not, all recorded in the driver's fidelity ``gaps``:

* the initial state comes from Python's ``random.Random(seed)``; upstream draws it from numpy's generator, so one
  seed does not give the same trajectory on the two implementations;
* the bridge contract has one scalar reward, while upstream ``Warehouse.step`` returns a list with one reward per
  agent (``warehouse.py:946``); with the registered one-agent layout this fake returns that single value as a float;
* there is no rendering, no collision graph between several agents and no gymnasium wrapper chain.

Nothing here talks to a device.
"""

import random

# rware/__init__.py:24-39: the registered tiny one-agent layout (column_height, shelf_rows, shelf_columns,
# n_agents, msg_bits, sensor_range, request_queue_size, max_steps and INDIVIDUAL rewards).
COLUMN_HEIGHT = 8
SHELF_ROWS = 1
SHELF_COLUMNS = 3
N_AGENTS = 1
MSG_BITS = 0
SENSOR_RANGE = 1
REQUEST_QUEUE_SIZE = 1
MAX_STEPS = 500
# rware/warehouse.py:46-49: RewardType.INDIVIDUAL is 1.
REWARD_INDIVIDUAL = 1
# rware/warehouse.py:432-443: (4 + len(Direction)) + (1 + 2 * sensor_range) ** 2 * (1 + len(Direction) + msg_bits)
# + (1 + 2 * sensor_range) ** 2 * 2.  With Direction of length 4, sensor_range 1 and msg_bits 0 this is 71.
OBS_LENGTH = 71


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return (isinstance(value, int) and not isinstance(value, bool)
                and self.start <= value < self.start + self.n)


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class Tuple:
    """Duck-typed ``gymnasium.spaces.Tuple``: the bridge reads its ``spaces`` member."""

    def __init__(self, spaces):
        self.spaces = tuple(spaces)


class FakeWarehouse:
    """The registered ``rware-tiny-1ag-v2`` without numpy, gymnasium or networkx."""

    # rware/warehouse.py:141-143
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 10}

    def __init__(self, **_options):
        self.column_height = COLUMN_HEIGHT                      # placeholder, rware/__init__.py:27
        self.shelf_rows = SHELF_ROWS                            # placeholder, rware/__init__.py:28
        self.shelf_columns = SHELF_COLUMNS                      # placeholder, rware/__init__.py:29
        self.n_agents = N_AGENTS                                # placeholder, rware/__init__.py:30
        self.msg_bits = MSG_BITS                                # placeholder, rware/__init__.py:31
        self.sensor_range = SENSOR_RANGE                        # placeholder, rware/__init__.py:32
        self.request_queue_size = REQUEST_QUEUE_SIZE            # placeholder, rware/__init__.py:33
        self.max_inactivity_steps = None                        # placeholder, rware/__init__.py:34
        self.max_steps = MAX_STEPS                              # placeholder, rware/__init__.py:36
        self.reward_type = REWARD_INDIVIDUAL                    # placeholder, rware/__init__.py:37
        self._make_layout_from_params()
        # rware/warehouse.py:255-260: one Discrete(len(Action)) per agent, wrapped in a Tuple.
        self.action_space = Tuple(tuple(self.n_agents * [Discrete(5)]))
        # rware/warehouse.py:282-289 and 432-443: a Tuple of one flattened Box per agent.
        bounds = [-float("inf")] * OBS_LENGTH
        self.observation_space = Tuple(
            tuple(self.n_agents * [Box(bounds, [-value for value in bounds], (OBS_LENGTH,))]))
        self.shelfs = []
        self.agents = []
        self.request_queue = []
        self.renderer = None
        self._cur_inactive_steps = 0
        self._cur_steps = 0
        self._shelf_grid = []
        self._agent_grid = []
        self._rng = random.Random()

    # -- layout -----------------------------------------------------------------
    def _make_layout_from_params(self):
        """``Warehouse._make_layout_from_params`` (rware/warehouse.py:294-306)."""
        self.grid_size = (
            (self.column_height + 1) * self.shelf_rows + 2,
            (2 + 1) * self.shelf_columns + 1,
        )
        self.goals = [
            (self.grid_size[1] // 2 - 1, self.grid_size[0] - 1),
            (self.grid_size[1] // 2, self.grid_size[0] - 1),
        ]
        self.highways = [
            [0 for _ in range(self.grid_size[1])] for _ in range(self.grid_size[0])
        ]
        for x in range(self.grid_size[1]):
            for y in range(self.grid_size[0]):
                self.highways[y][x] = int(self._highway_func(x, y))

    def _highway_func(self, x, y):
        """The predicate of ``Warehouse._make_layout_from_params`` (rware/warehouse.py:310-320)."""
        is_on_vertical_highway = x % 3 == 0
        is_on_horizontal_highway = y % (self.column_height + 1) == 0
        is_on_delivery_row = y == self.grid_size[0] - 1
        is_on_queue = (y > self.grid_size[0] - (self.column_height + 3)) and (
            x == self.grid_size[1] // 2 - 1 or x == self.grid_size[1] // 2
        )
        return is_on_vertical_highway or is_on_horizontal_highway or is_on_delivery_row or is_on_queue

    def _is_highway(self, x, y):
        return bool(self.highways[y][x])

    def _recalc_grid(self):
        """``Warehouse._recalc_grid`` (rware/warehouse.py:748-755)."""
        self._shelf_grid = [[0 for _ in range(self.grid_size[1])] for _ in range(self.grid_size[0])]
        self._agent_grid = [[0 for _ in range(self.grid_size[1])] for _ in range(self.grid_size[0])]
        for shelf in self.shelfs:
            self._shelf_grid[shelf["y"]][shelf["x"]] = shelf["id"]
        for agent in self.agents:
            self._agent_grid[agent["y"]][agent["x"]] = agent["id"]

    # -- reset ------------------------------------------------------------------
    def reset(self, seed=None, options=None):
        """``Warehouse.reset`` (rware/warehouse.py:757-802) with Python's generator instead of numpy's."""
        if seed is not None:
            self._rng = random.Random(seed)                     # rware/warehouse.py:758-760
        self._cur_inactive_steps = 0
        self._cur_steps = 0
        self.shelfs = []
        shelf_id = 0
        for y in range(self.grid_size[0]):
            for x in range(self.grid_size[1]):
                if not self._is_highway(x, y):
                    shelf_id += 1
                    self.shelfs.append({"id": shelf_id, "x": x, "y": y})
        location = self._rng.randrange(self.grid_size[0] * self.grid_size[1])
        agent_x = location % self.grid_size[1]
        agent_y = location // self.grid_size[1]
        self.agents = [{
            "id": 1,
            "x": agent_x,
            "y": agent_y,
            "dir": self._rng.randrange(4),
            "carrying_shelf": None,
            "has_delivered": False,
        }]
        self._recalc_grid()
        self.request_queue = self._rng.sample(self.shelfs, self.request_queue_size)
        return tuple([self._make_obs()]), {}

    # -- step -------------------------------------------------------------------
    def step(self, actions):
        """``Warehouse.step`` for the one-agent layout (rware/warehouse.py:804-946)."""
        if len(actions) != len(self.agents):
            raise AssertionError("the number of actions must match the number of agents")
        action = int(actions[0])
        if action not in (0, 1, 2, 3, 4):
            raise ValueError(f"{action} is not a valid Action")
        agent = self.agents[0]
        requested = action
        start = (agent["x"], agent["y"])
        target = self._req_location(agent, action)
        if (agent["carrying_shelf"] is not None and start != target
                and self._shelf_grid[target[1]][target[0]]
                and not (self._agent_grid[target[1]][target[0]]
                         and self.agents[self._agent_grid[target[1]][target[0]] - 1]["carrying_shelf"])):
            requested = 0                                      # rware/warehouse.py:836-844
        rewards = [0.0]
        if requested == 1:                                     # rware/warehouse.py:883-887
            agent["x"], agent["y"] = target
            if agent["carrying_shelf"] is not None:
                agent["carrying_shelf"]["x"], agent["carrying_shelf"]["y"] = target
        elif requested in (2, 3):                              # rware/warehouse.py:889-891
            agent["dir"] = self._req_direction(agent["dir"], requested)
        elif requested == 4 and agent["carrying_shelf"] is None:
            shelf_id = self._shelf_grid[agent["y"]][agent["x"]]
            if shelf_id:
                agent["carrying_shelf"] = self.shelfs[shelf_id - 1]
        elif requested == 4 and agent["carrying_shelf"] is not None:
            if not self._is_highway(agent["x"], agent["y"]):
                agent["carrying_shelf"] = None
                if agent["has_delivered"] and self.reward_type == 2:
                    rewards[0] += 0.5
                agent["has_delivered"] = False
        self._recalc_grid()

        shelf_delivered = False
        for goal_x, goal_y in self.goals:                       # rware/warehouse.py:905-931
            shelf_id = self._shelf_grid[goal_y][goal_x]
            if not shelf_id:
                continue
            shelf = self.shelfs[shelf_id - 1]
            if shelf not in self.request_queue:
                continue
            shelf_delivered = True
            candidates = [item for item in self.shelfs if item not in self.request_queue]
            new_request = self._rng.choice(candidates)
            self.request_queue[self.request_queue.index(shelf)] = new_request
            if self.reward_type == 0:
                for index in range(len(rewards)):
                    rewards[index] += 1
            elif self.reward_type == 1:
                agent_id = self._agent_grid[goal_y][goal_x]
                rewards[agent_id - 1] += 1
            elif self.reward_type == 2:
                agent_id = self._agent_grid[goal_y][goal_x]
                self.agents[agent_id - 1]["has_delivered"] = True
                rewards[agent_id - 1] += 0.5

        if shelf_delivered:
            self._cur_inactive_steps = 0
        else:
            self._cur_inactive_steps += 1
        self._cur_steps += 1
        done = bool(
            (self.max_inactivity_steps and self._cur_inactive_steps >= self.max_inactivity_steps)
            or (self.max_steps and self._cur_steps >= self.max_steps)
        )
        truncated = False
        # The Gymnasium bridge carries one scalar reward; upstream returns list(rewards) at warehouse.py:946.
        return tuple([self._make_obs()]), float(sum(rewards)), done, truncated, {}

    # -- actions ----------------------------------------------------------------
    def _req_location(self, agent, action):
        """``Agent.req_location`` (rware/warehouse.py:84-101)."""
        if action != 1:
            return agent["x"], agent["y"]
        if agent["dir"] == 0:
            return agent["x"], max(0, agent["y"] - 1)
        if agent["dir"] == 1:
            return agent["x"], min(self.grid_size[0] - 1, agent["y"] + 1)
        if agent["dir"] == 2:
            return max(0, agent["x"] - 1), agent["y"]
        return min(self.grid_size[1] - 1, agent["x"] + 1), agent["y"]

    @staticmethod
    def _req_direction(direction, action):
        """``Agent.req_direction`` (rware/warehouse.py:103-112)."""
        wraplist = [0, 3, 1, 2]
        if action == 3:
            return wraplist[(wraplist.index(direction) + 1) % len(wraplist)]
        if action == 2:
            return wraplist[(wraplist.index(direction) - 1) % len(wraplist)]
        return direction

    # -- observation ------------------------------------------------------------
    def _window(self, grid, center_x, center_y):
        """The sensor square of ``Warehouse._get_default_obs`` (rware/warehouse.py:611-642)."""
        radius = self.sensor_range
        out = []
        for y in range(center_y - radius, center_y + radius + 1):
            for x in range(center_x - radius, center_x + radius + 1):
                if 0 <= x < self.grid_size[1] and 0 <= y < self.grid_size[0]:
                    out.append(grid[y][x])
                else:
                    out.append(0)
        return out

    def _make_obs(self):
        """The flattened observation of ``Warehouse._get_default_obs`` (rware/warehouse.py:660-738)."""
        agent = self.agents[0]
        agents = self._window(self._agent_grid, agent["x"], agent["y"])
        shelfs = self._window(self._shelf_grid, agent["x"], agent["y"])
        requested = {shelf["id"] for shelf in self.request_queue}
        obs = [float(agent["x"]), float(agent["y"]), float(agent["carrying_shelf"] is not None)]
        direction = [0.0, 0.0, 0.0, 0.0]
        direction[agent["dir"]] = 1.0
        obs.extend(direction)
        obs.append(float(self._is_highway(agent["x"], agent["y"])))
        for agent_id, shelf_id in zip(agents, shelfs):
            if agent_id == 0:
                obs.extend([0.0, 1.0, 0.0, 0.0, 0.0])
            else:
                obs.append(1.0)
                other = [0.0, 0.0, 0.0, 0.0]
                other[self.agents[agent_id - 1]["dir"]] = 1.0
                obs.extend(other)
            if shelf_id == 0:
                obs.extend([0.0, 0.0])
            else:
                obs.extend([1.0, float(shelf_id in requested)])
        return obs

    # -- lifecycle --------------------------------------------------------------
    def close(self):
        """``Warehouse.close`` (rware/warehouse.py:952-954); there is no renderer in the fake."""
        self.renderer = None
