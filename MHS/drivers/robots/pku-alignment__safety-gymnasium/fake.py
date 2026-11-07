"""Fake backend of the Safety-Gymnasium driver: a pure Python stand-in for the Point Goal1 task.

Why a fake: the acceptance gate runs without ``safety_gymnasium``, ``gymnasium``, ``mujoco`` or numpy, and package
code never imports the read-only clone.  This module therefore re-implements the small part of the standard
Gymnasium view of ``SafetyPointGoal1Gymnasium-v0`` that the bridge drives: a two-value continuous action in
[-1, 1], a flattened observation with the upstream sensor and lidar layout, a goal, eight hazards and one vase, and
the 1000-environment-step episode limit.  The class it stands in for is
``safety_gymnasium.builder:Builder`` (the driver's ``native``); the standard five-item step is the one the upstream
``SafetyGymnasium2Gymnasium`` wrapper returns (``safety_gymnasium/wrappers/gymnasium_conversion.py:26-34``).

Every constant below is test data of this fake, marked ``# placeholder``.  The comments name the upstream lines
that describe the shape (two actuators, a 16-bin lidar, a goal radius, a hazard radius, a 1000-step episode), but
none of these values is a device fact or a declared limit: the action bounds are the only limit, and the bridge
derives that limit from the fake's ``action_space``.

What this is not: MuJoCo.  The motion is a kinematic point model (forward speed and turn rate), there are no
contacts, friction, actuator forces, gravity, meshes or rendered frames, and the layout is drawn with Python's
``random.Random`` rather than the upstream numpy generator.  All of that is listed in the driver's fidelity
``gaps``.  Nothing here talks to a device.
"""

import math
import random

# placeholder: one fake tick is one environment step of 20 ms (10 MuJoCo steps of 2 ms; point.xml:19,
# underlying.py:95-96)
DT_S = 0.02
# placeholder: forward speed in m/s at action value 1
SPEED_MPS = 0.5
# placeholder: turn rate in rad/s at action value 1
TURN_RATE_RAD_S = 1.5
# placeholder: goal radius of the Goal asset (goal.py:31)
GOAL_RADIUS_M = 0.3
# placeholder: sparse goal reward and dense distance reward (goal.py:36-40)
GOAL_REWARD = 1.0
DISTANCE_REWARD = 1.0
# placeholder: hazard radius and cost coefficient (hazards.py:32,37)
HAZARD_RADIUS_M = 0.2
HAZARD_COST = 1.0
# placeholder: GoalLevel1 adds 8 hazards and one vase (goal_level1.py:33-34)
NUM_HAZARDS = 8
NUM_VASES = 1
# placeholder: episode limit of BaseTask.num_steps (base_task.py:181)
EPISODE_STEPS = 1000
# placeholder: LidarConf.num_bins (base_task.py:47)
LIDAR_BINS = 16
# placeholder: the range at which the fake lidar reading reaches zero
LIDAR_RANGE_M = 2.0
# placeholder: half-width of the goal placement square (goal_level0.py:27)
GOAL_EXTENT_M = 1.0
# placeholder: half-width of the hazard and vase placement square (goal_level1.py:31)
OBJECT_EXTENT_M = 1.5
# placeholder: minimum distance of the initial goal from the agent
GOAL_MIN_DISTANCE_M = 0.5


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: one lower and one upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float64"


def _wrap_angle(value):
    """An angle in (-pi, pi]."""
    return (value + math.pi) % (2.0 * math.pi) - math.pi


class FakeSafetyPointGoal1:
    """The standard Gymnasium view of the Safety-Gymnasium Point Goal1 task, without MuJoCo or numpy."""

    def __init__(self, **_options):
        # placeholder: point.xml:24-25 gives the two actuators the default ctrlrange -1 1
        self.action_space = Box([-1.0, -1.0], [1.0, 1.0])
        # placeholder: 12 sensor values and a 16-bin lidar for the goal, the hazards and the vase
        self.observation_space = Box(
            [-math.inf] * 12 + [0.0] * (LIDAR_BINS * 3),
            [math.inf] * 12 + [1.0] * (LIDAR_BINS * 3),
        )
        self._rng = random.Random(0)
        self._pose = None
        self._speed = 0.0
        self._omega = 0.0
        self._steps = 0
        self._goal = (0.0, 0.0)
        self._hazards = []
        self._vases = []
        self._last_distance = 0.0

    # -- layout and observation -------------------------------------------------
    def _sample_uniform(self, extent):
        return self._rng.uniform(-extent, extent), self._rng.uniform(-extent, extent)

    def _new_goal(self):
        for _ in range(100):
            x, y = self._sample_uniform(GOAL_EXTENT_M)
            if math.hypot(x, y) >= GOAL_MIN_DISTANCE_M:
                return x, y
        return GOAL_EXTENT_M, 0.0

    def _goal_distance(self):
        x, y, _theta = self._pose
        return math.hypot(self._goal[0] - x, self._goal[1] - y)

    def _lidar(self, positions):
        """One 16-bin closeness reading in [0, 1] per direction, as BaseTask._obs_lidar builds it."""
        bins = [0.0] * LIDAR_BINS
        x, y, theta = self._pose
        for px, py in positions:
            dx, dy = px - x, py - y
            distance = math.hypot(dx, dy)
            if distance >= LIDAR_RANGE_M:
                continue
            bearing = _wrap_angle(math.atan2(dy, dx) - theta)
            index = int((bearing + math.pi) / (2.0 * math.pi) * LIDAR_BINS) % LIDAR_BINS
            bins[index] = max(bins[index], 1.0 - distance / LIDAR_RANGE_M)
        return bins

    def _observation(self):
        _x, _y, theta = self._pose
        vx = self._speed * math.cos(theta)
        vy = self._speed * math.sin(theta)
        # The upstream sensors are accelerometer, velocimeter, gyro and magnetometer, three values each
        # (base_agent.py:49).  The values here are analytic placeholders.
        observation = [
            0.0, 0.0, 0.0,                    # placeholder: accelerometer
            vx, vy, 0.0,                      # placeholder: velocimeter
            0.0, 0.0, self._omega,            # placeholder: gyro
            math.cos(theta), math.sin(theta), 0.0,  # placeholder: magnetometer
        ]
        observation.extend(self._lidar([self._goal]))
        observation.extend(self._lidar(self._hazards))
        observation.extend(self._lidar(self._vases))
        return observation

    # -- gymnasium interface ----------------------------------------------------
    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._pose = [0.0, 0.0, 0.0]
        self._speed = 0.0
        self._omega = 0.0
        self._steps = 0
        self._goal = self._new_goal()
        self._hazards = [self._sample_uniform(OBJECT_EXTENT_M) for _ in range(NUM_HAZARDS)]
        self._vases = [self._sample_uniform(OBJECT_EXTENT_M) for _ in range(NUM_VASES)]
        self._last_distance = self._goal_distance()
        return self._observation(), {}

    def step(self, action):
        if self._pose is None:
            raise RuntimeError("reset() must be called before step()")
        values = [float(item) for item in action]
        if len(values) != 2:
            raise ValueError("the Point action has two values")
        if any(item < -1.0 or item > 1.0 for item in values):
            raise ValueError("the Point action is bounded by [-1, 1]")
        self._speed = SPEED_MPS * values[0]
        self._omega = TURN_RATE_RAD_S * values[1]
        self._pose[2] = _wrap_angle(self._pose[2] + self._omega * DT_S)
        self._pose[0] += self._speed * math.cos(self._pose[2]) * DT_S
        self._pose[1] += self._speed * math.sin(self._pose[2]) * DT_S
        self._steps += 1

        distance = self._goal_distance()
        reward = (self._last_distance - distance) * DISTANCE_REWARD
        self._last_distance = distance
        terminated = distance <= GOAL_RADIUS_M
        if terminated:
            reward += GOAL_REWARD
        truncated = self._steps >= EPISODE_STEPS

        cost = 0.0
        x, y, _theta = self._pose
        for hx, hy in self._hazards:
            penetration = HAZARD_RADIUS_M - math.hypot(hx - x, hy - y)
            if penetration > 0.0:
                cost += HAZARD_COST * penetration
        info = {"cost": cost, "goal_met": bool(terminated)}
        return self._observation(), reward, terminated, truncated, info
