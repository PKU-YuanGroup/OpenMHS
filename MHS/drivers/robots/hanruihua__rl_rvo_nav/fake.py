"""Fake backend of the rl_rvo_nav driver: a pure Python stand-in for ``gym_env.envs:mrnav``.

The gate never installs or imports the upstream package: the clone needs gym 0.20.0, torch, numpy and the external
ir-sim v2.5 (``README.md:17-27``), and package code never imports the clone.  This module mirrors the public surface
the driver uses: ``mrnav.reset(mode=...)``, ``mrnav.step_ir(action, vel_type='omni', stop=True)``,
``mrnav.reset_one(id)``, ``mrnav.render(...)`` and ``mrnav.show()``, plus the ``ir_gym`` attribute whose
``env_observation()`` the driver reads.  The upstream class does not define ``step``; neither does this fake.

The fake is a two-robot kinematic model: each ``step_ir`` moves every robot by its commanded velocity for the world
step time, a collision between robots sets ``done``, and an arrival sets the robot's arrival flag and is returned as
``info``.  The observation has the upstream shape: current velocity, desired velocity, heading, collision radius and
eight zero RVO neighbour features, rounded to two decimals.  Every start position, radius, threshold, reward and time
constant below is test data, not a fact about the device; each is marked ``# placeholder``.  The fake was not compared
with ir-sim and does not claim to be the upstream simulator (the fidelity gaps in driver.py say so).
"""

import math

# placeholder: the fake's simulated step, robot count, start and goal positions, radius and rewards
DT_S = 0.1
ROBOT_RADIUS = 0.2
GOAL_THRESHOLD = 0.1
ARRIVAL_REWARD = 20.0
COLLISION_REWARD = -20.0
DESIRED_SPEED = 1.0
RVO_STATE_DIM = 8


class _Box:
    """A minimal duck-typed space so the fake exposes the two upstream space attributes."""

    def __init__(self, low, high):
        self.low = low
        self.high = high
        self.shape = (len(low),) if isinstance(low, list) else ()
        self.dtype = "float32"


class _FakeIrGym:
    """The nested simulator object of the fake; ``env_observation`` exists in the upstream ir_gym (ir_gym.py:184)."""

    def __init__(self, parent):
        self._parent = parent

    def env_observation(self):
        return self._parent._observe()


class FakeMrnav:
    """A kinematic stand-in for ``gym_env.envs:mrnav`` with two robots and no obstacles."""

    def __init__(self, **_options):
        self.ir_gym = _FakeIrGym(self)
        # placeholder: the upstream space attributes, with test-data bounds
        self.observation_space = _Box([-math.inf] * 5, [math.inf] * 5)
        self.action_space = _Box([-1.0, -1.0], [1.0, 1.0])
        self.neighbors_region = 5                     # placeholder
        self.circular = [5, 5, 4]                     # placeholder
        self.square = [0, 0, 10, 10]                  # placeholder
        self.interval = 1                             # placeholder
        # placeholder: two robots that start on opposite sides of a 10 x 10 world
        self._start = [(-1.0, 0.0, 1.0, 0.0), (1.0, 0.0, -1.0, 0.0)]
        self._robots = []
        self._reset_robots()

    # -- native surface used by the driver ---------------------------------
    def reset(self, mode=0, **kwargs):
        """Reset every robot (upstream: ir_gym.env_reset -> robots_reset, ir_gym.py:173-179)."""
        self._reset_robots()
        return self._observe()

    def step_ir(self, action, vel_type="omni", stop=True, **kwargs):
        """One transition for every robot, returning the four per-robot lists of mrnav.py:18-30."""
        if not isinstance(action, list):
            action = [action]                         # mrnav.py:20-22
        for index, robot in enumerate(self._robots):
            if index < len(action):
                pair = action[index]
                robot["vx"] = float(pair[0])
                robot["vy"] = float(pair[1])
            robot["x"] += robot["vx"] * DT_S
            robot["y"] += robot["vy"] * DT_S
        obs_list = self._observe()
        reward_list = []
        done_list = []
        info_list = []
        for index, robot in enumerate(self._robots):
            collision = self._collides(index)
            arrived_now = (not robot["arrived"]) and self._goal_distance(robot) < GOAL_THRESHOLD
            if arrived_now:
                robot["arrived"] = True
            reward_list.append((COLLISION_REWARD if collision else 0.0)
                               + (ARRIVAL_REWARD if arrived_now else 0.0))
            done_list.append(bool(collision))         # ir_gym.py:116
            info_list.append(bool(robot["arrived"]))  # ir_gym.py:117
        return obs_list, reward_list, done_list, info_list

    def reset_one(self, id):
        """Reset one robot by index (mrnav.py:42-43)."""
        index = int(id)
        if 0 <= index < len(self._robots):
            self._robots[index] = self._new_robot(index)
        return None

    def render(self, mode="human", save=False, path=None, i=0, **kwargs):
        """The fake draws nothing; the upstream render call is accepted (mrnav.py:32-36)."""
        return None

    def show(self):
        """The fake has no window to show (mrnav.py:45-46)."""
        return None

    # -- fake internals ----------------------------------------------------
    def _new_robot(self, index):
        x, y, gx, gy = self._start[index]
        return {"x": x, "y": y, "goal_x": gx, "goal_y": gy, "vx": 0.0, "vy": 0.0,
                "theta": 0.0, "radius": ROBOT_RADIUS, "arrived": False}

    def _reset_robots(self):
        self._robots = [self._new_robot(index) for index in range(len(self._start))]

    def _goal_distance(self, robot):
        return math.hypot(robot["goal_x"] - robot["x"], robot["goal_y"] - robot["y"])

    def _collides(self, index):
        robot = self._robots[index]
        for other_index, other in enumerate(self._robots):
            if other_index == index:
                continue
            if math.hypot(other["x"] - robot["x"], other["y"] - robot["y"]) < robot["radius"] + other["radius"]:
                return True
        return False

    def _observe(self):
        observations = []
        for robot in self._robots:
            distance = self._goal_distance(robot)
            if distance > 0.0:
                desired = [DESIRED_SPEED * (robot["goal_x"] - robot["x"]) / distance,
                           DESIRED_SPEED * (robot["goal_y"] - robot["y"]) / distance]
            else:
                desired = [0.0, 0.0]
            value = [robot["vx"], robot["vy"], desired[0], desired[1], robot["theta"], robot["radius"]]
            value.extend([0.0] * RVO_STATE_DIM)
            observations.append([round(item, 2) for item in value])
        return observations
