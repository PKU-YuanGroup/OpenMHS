"""Fake backend of the Planning Multi-Robot Gym driver: a pure Python stand-in for the upstream environment.

Why a fake: package code never imports the clone, the upstream package is not installed, and gymnasium and pygame are
not importable where the gate runs (the upstream environment imports them at planning_multi_robot_env.py:4-8).  This
module re-implements the simulation of ``planning_multi_robot_gym:PlanningMultiRobotEnv`` (the class the driver names
as ``native``) with the standard library only.  The public members of the backend class are the ones
PlanningMultiRobotEnv has (``reset``, ``step`` and ``close``; gate G7), and the two space classes duck-type
``gymnasium.spaces.Dict`` and ``Box`` (the bridge reads ``spaces``, ``low``, ``high`` and ``shape``).

Every constant and rule below cites the line of the clone at the pinned commit
dbb4eb5ab82e4143d1d567095eacae7bdb390b0b.  What this is not, all listed in the fidelity ``gaps`` of driver.py:

* the initial state comes from Python's ``random.Random``; upstream draws it from numpy's generator through
  ``gym.Env.np_random``, so one seed gives a different trajectory on the two;
* the simulation uses Python floats and lists; upstream uses numpy arrays;
* the info dictionary omits ``predict_position`` because a Python callable is not JSON data;
* there is no pygame rendering and no human window.

Nothing here talks to a device.
"""

import math
import random

# planning_multi_robot_env.py:80 -- the play field is (-4.0, -3.0, 4.0, 3.0).
PLAY_FIELD_CORNERS = (-4.0, -3.0, 4.0, 3.0)


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element and a shape."""

    def __init__(self, low, high, shape):
        self.shape = tuple(int(size) for size in shape)
        count = 1
        for size in self.shape:
            count *= size
        self.low = list(low) if isinstance(low, (list, tuple)) else [float(low)] * count
        self.high = list(high) if isinstance(high, (list, tuple)) else [float(high)] * count
        self.dtype = "float64"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.low):
            return False
        return all(low <= float(item) <= high for low, high, item in zip(self.low, self.high, value))


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the mapping the bridge reads through ``.spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = None

    def contains(self, value):
        if not isinstance(value, dict) or set(value) != set(self.spaces):
            return False
        return all(self.spaces[key].contains(value[key]) for key in self.spaces)


class _Robot:
    """The state the upstream ``Robot`` class carries (robot.py:7-15)."""

    def __init__(self, x, y, theta):
        self.x = x
        self.y = y
        self.theta = theta
        self.vL = 0.0
        self.vR = 0.0
        self.path = None
        self.location_history = []


class FakePlanningMultiRobotEnv:
    """PlanningMultiRobot-v0 without numpy or pygame; the constructor parameters are the upstream ones."""

    def __init__(
        self,
        n_robots=5,
        n_barriers=20,
        render_mode=None,
        barrier_radius=0.1,
        robot_radius=0.1,
        wheel_blob=0.04,
        max_velocity=0.5,
        max_acceleration=0.4,
        barrier_velocity_range=0.2,
        dt=0.1,
        steps_ahead_to_plan=10,
        reach_target_reward=1000.0,
        collision_penalty=-500.0,
        reset_when_target_reached=False,
    ):
        # The parameters and their defaults are planning_multi_robot_env.py:26-42; they configure the fake, they are
        # not published as Facts or Limits.
        if render_mode is not None:
            raise ValueError("the fake PlanningMultiRobot environment cannot render; use render_mode=None")
        self.n_robots = n_robots
        self.n_barriers = n_barriers
        self.barrier_radius = barrier_radius
        self.robot_radius = robot_radius
        self.robot_width = robot_radius * 2
        self.dt = dt
        self.steps_ahead_to_plan = steps_ahead_to_plan
        self.tau = dt * steps_ahead_to_plan
        self.reach_target_reward = reach_target_reward
        self.collision_penalty = collision_penalty
        self.reset_when_target_reached = reset_when_target_reached
        self.wheel_blob = wheel_blob
        self.max_velocity = max_velocity
        self.max_acceleration = max_acceleration
        self.barrier_velocity_range = barrier_velocity_range
        self.play_field_corners = PLAY_FIELD_CORNERS
        self.window = None
        self.clock = None
        # planning_multi_robot_env.py:85-90: the action is one Box of two arrays, one value per robot.
        self.action_space = Dict({
            "vR": Box(-max_velocity, max_velocity, (n_robots,)),
            "vL": Box(-max_velocity, max_velocity, (n_robots,)),
        })
        # planning_multi_robot_env.py:92-113: the observation keys and shapes.
        self.observation_space = Dict({
            "vR": Box(-math.inf, math.inf, (n_robots,)),
            "vL": Box(-math.inf, math.inf, (n_robots,)),
            "theta": Box(-math.inf, math.inf, (n_robots,)),
            "robot_positions": Box(-math.inf, math.inf, (n_robots, 2)),
            "future_target_position": Box(-math.inf, math.inf, (2,)),
            "future_obstacle_positions": Box(-math.inf, math.inf, (n_barriers - 1, 2)),
        })
        # planning_multi_robot_env.py:115-124: the info dictionary (predict_position is a callable, not JSON data).
        self._info = {
            "n_robots": self.n_robots,
            "max_acceleration": self.max_acceleration,
            "max_velocity": self.max_velocity,
            "barrier_radius": self.barrier_radius,
            "robot_radius": self.robot_radius,
            "dt": self.dt,
            "tau": self.tau,
        }
        self.barriers = None
        self.target_index = None
        self.robots = []
        self._rng = random.Random()

    def reset(self, *, seed=None, options=None):
        # planning_multi_robot_env.py:146-168.  options are accepted and ignored, as upstream does.
        if seed is not None:
            self._rng = random.Random(seed)
        self.barriers = []
        for _ in range(self.n_barriers):
            self.barriers.append([
                self._rng.uniform(self.play_field_corners[0], self.play_field_corners[2]),
                self._rng.uniform(self.play_field_corners[1], self.play_field_corners[3]),
                self._rng.normalvariate(0.0, self.barrier_velocity_range),
                self._rng.normalvariate(0.0, self.barrier_velocity_range),
            ])
        self.target_index = self._rng.randrange(self.n_barriers)
        self.robots = [
            _Robot(self.play_field_corners[0] - 0.5, -2.0 + 0.8 * index, 0.0)
            for index in range(self.n_robots)
        ]
        return self._get_obs(), dict(self._info)

    def _get_obs(self):
        # planning_multi_robot_env.py:129-144: predict the barriers without moving the simulation state.
        barriers = [[barrier[0], barrier[1], barrier[2], barrier[3]] for barrier in self.barriers]
        for _ in range(self.steps_ahead_to_plan):
            self._move_barriers(barriers)
        return {
            "vR": [robot.vR for robot in self.robots],
            "vL": [robot.vL for robot in self.robots],
            "theta": [robot.theta for robot in self.robots],
            "robot_positions": [[robot.x, robot.y] for robot in self.robots],
            "future_target_position": [barriers[self.target_index][0], barriers[self.target_index][1]],
            "future_obstacle_positions": [
                [barrier[0], barrier[1]]
                for index, barrier in enumerate(barriers)
                if index != self.target_index
            ],
        }

    def _move_barriers(self, barriers):
        # planning_multi_robot_env.py:170-181.
        for barrier in barriers:
            barrier[0] += barrier[2] * self.dt
            if barrier[0] < self.play_field_corners[0]:
                barrier[2] = -barrier[2]
            if barrier[0] > self.play_field_corners[2]:
                barrier[2] = -barrier[2]
            barrier[1] += barrier[3] * self.dt
            if barrier[1] < self.play_field_corners[1]:
                barrier[3] = -barrier[3]
            if barrier[1] > self.play_field_corners[3]:
                barrier[3] = -barrier[3]

    def _predict_position(self, vL, vR, x, y, theta, deltat):
        # planning_multi_robot_env.py:183-212: differential-drive kinematics, without the drawing path.
        if round(vL, 3) == round(vR, 3):
            xnew = x + vL * deltat * math.cos(theta)
            ynew = y + vL * deltat * math.sin(theta)
            thetanew = theta
        elif round(vL, 3) == -round(vR, 3):
            xnew = x
            ynew = y
            thetanew = theta + ((vR - vL) * deltat / self.robot_width)
        else:
            radius = self.robot_width / 2.0 * (vR + vL) / (vR - vL)
            deltatheta = (vR - vL) * deltat / self.robot_width
            xnew = x + radius * (math.sin(deltatheta + theta) - math.sin(theta))
            ynew = y - radius * (math.cos(deltatheta + theta) - math.cos(theta))
            thetanew = theta + deltatheta
        return xnew, ynew, thetanew

    def step(self, action):
        # planning_multi_robot_env.py:214-269.
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} is not in the action space")
        self._move_barriers(self.barriers)
        reward = 0
        for index, robot in enumerate(self.robots):
            robot.location_history.append((robot.x, robot.y))
            vL = min(
                max(robot.vL - self.max_acceleration * self.dt, action["vL"][index]),
                robot.vL + self.max_acceleration * self.dt,
            )
            vR = min(
                max(robot.vR - self.max_acceleration * self.dt, action["vR"][index]),
                robot.vR + self.max_acceleration * self.dt,
            )
            robot.x, robot.y, robot.theta = self._predict_position(
                vL, vR, robot.x, robot.y, robot.theta, self.dt
            )
            robot.vL = vL
            robot.vR = vR

        robot_has_reached_target = False
        for robot in self.robots:
            others = [(other.x, other.y) for other in self.robots if other is not robot]
            for index, barrier in enumerate(self.barriers + others):
                distance = math.sqrt((robot.x - barrier[0]) ** 2 + (robot.y - barrier[1]) ** 2)
                if distance < (self.barrier_radius + self.robot_radius):
                    if index == self.target_index:
                        robot_has_reached_target = True
                        reward += self.reach_target_reward
                    else:
                        reward += self.collision_penalty
        if robot_has_reached_target:
            self.target_index = self._rng.randrange(self.n_barriers)
            for robot in self.robots:
                robot.location_history = []

        terminated = self.reset_when_target_reached and robot_has_reached_target
        return self._get_obs(), reward, terminated, False, dict(self._info)

    def close(self):
        # planning_multi_robot_env.py:312-314: with no pygame window there is nothing to quit.
        self.window = None
        self.clock = None
