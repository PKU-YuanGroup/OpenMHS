"""Fake backend of the SocialGym-v0 driver: a small, self-contained social navigation environment.

Why a fake: the upstream package needs gymnasium, pygame, scipy and torch (requirements.txt), none of which is
importable where the gate runs, and package code never imports the clone.  This module implements the two public
members the bridge calls, ``reset`` and ``step`` (the same names as ``SocialNavGym.reset`` and ``.step``; gate G7),
and duck-types the environment's action and observation spaces with a ``Box`` (the bridge reads ``low``, ``high``
and ``shape``).  The dynamics follow the clone's interfaces:

* the action is the robot's ``ActionRot(v, r)`` (``crowd_nav/utils/action.py:4``): move by ``v`` in the direction
  ``yaw + r`` and then add ``r`` to ``yaw`` (``social_gym/src/robot_agent.py:116-136``);
* one environment step applies the action for ``time_step_factor`` sub-steps of ``time_step`` each
  (``social_gym/social_nav_gym.py:240-245``);
* the observation is the human's ``ObservableState`` (px, py, vx, vy, radius;
  ``crowd_nav/utils/state.py:24-30``);
* the reward and terminal flags follow ``compute_reward_and_infos`` (``social_gym/social_nav_sim.py:1004-1028``)
  with the values of the repository's example configuration (``crowd_nav/configs/env.config:2-4,11-14``).

What this is not: the upstream environment.  It has one human, constant human velocity, no social force, headed
social force or ORCA model, no walls and no rendering; the upstream action and observation spaces are dummy
``Discrete(1)`` values (``social_nav_gym.py:55-57``), while the Box here carries the two-number robot action and the
five-number observation the step and observable-state code actually use.  The upstream reset also needs
``configure(config)`` and ``set_robot(robot)`` first (``social_nav_gym.py:59-98,125``).  These differences are the
driver's fidelity ``gaps``.  The start positions, the seed offset and the human speed below are test data, marked
``# placeholder``; never read them as facts about the device.
"""

import math
import random

# crowd_nav/configs/env.config:2-4 (the repository's example configuration, not a device bound)
TIME_LIMIT = 50.0
ENV_TIME_STEP = 0.0125
ROBOT_TIME_STEP = 0.25
# social_gym/social_nav_gym.py:65: time_step_factor = int(robot_time_step / time_step)
SUBSTEPS = int(round(ROBOT_TIME_STEP / ENV_TIME_STEP))
# crowd_nav/configs/env.config:11-14
SUCCESS_REWARD = 1.0
COLLISION_PENALTY = -0.25
DISCOMFORT_DIST = 0.2
DISCOMFORT_PENALTY_FACTOR = 0.5
# crowd_nav/configs/env.config:29,37
HUMAN_RADIUS = 0.3
ROBOT_RADIUS = 0.3


class _Box:
    """Duck-typed one-dimensional space: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float64"


def _segment_distance(px, py, qx, qy):
    """Distance from the origin to the segment ``(px, py)``-``(qx, qy)`` (``point_to_segment_dist``)."""
    dx, dy = qx - px, qy - py
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return math.hypot(px, py)
    t = -(px * dx + py * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return math.hypot(px + t * dx, py + t * dy)


class FakeSocialNavGym:
    """One robot and one constant-velocity human: ``reset(phase, test_case, seed, options)`` and ``step(action)``."""

    def __init__(self):
        # social_nav_gym.py:55-57: the upstream spaces are dummy Discrete(1); the fake carries what the code uses.
        self.action_space = _Box([-math.inf, -math.inf], [math.inf, math.inf])
        self.observation_space = _Box([-math.inf] * 5, [math.inf] * 5)
        self._rng = random.Random(0)
        self._robot = [0.0, 0.0, math.pi / 2]          # placeholder: x, y, yaw
        self._goal = [0.0, 1.0]                        # placeholder
        self._human = [2.0, 0.0, 0.5, 0.0, HUMAN_RADIUS]   # placeholder: px, py, vx, vy, radius
        self._time = 0.0

    def reset(self, phase="test", test_case=None, *, seed=None, options=None):
        """Start a new episode; ``phase`` and ``test_case`` mirror the upstream signature, ``seed`` drives the fake."""
        self._rng = random.Random(0 if seed is None else int(seed))
        offset = self._rng.uniform(-0.05, 0.05)        # placeholder: seed-controlled start offset
        self._robot = [0.0, 0.0, math.pi / 2]          # placeholder
        self._goal = [0.0, 1.0]                        # placeholder
        self._human = [2.0 + offset, offset, 0.5, 0.0, HUMAN_RADIUS]   # placeholder
        self._time = 0.0
        return self._observation(), {}

    def step(self, action):
        """Apply a robot action for one robot time step and return ``(observation, reward, terminated, truncated, info)``."""
        v, r = self._unpack_action(action)
        collision, dmin, reaching_goal = self._check(v, r)
        reward, terminated, truncated = self._reward(collision, dmin, reaching_goal)
        self._advance(v, r)
        return self._observation(), reward, terminated, truncated, {}

    # -- internals -------------------------------------------------------------------------------------------------
    def _unpack_action(self, action):
        if isinstance(action, (list, tuple)) and len(action) == 2:
            return float(action[0]), float(action[1])
        v = getattr(action, "v", None)
        r = getattr(action, "r", None)
        if v is None or r is None:
            raise ValueError("the robot action must be ActionRot(v, r) or a two-number [v, r] sequence")
        return float(v), float(r)

    def _observation(self):
        return list(self._human)

    def _check(self, v, r):
        """The collision and goal test of ``collision_detection_and_reaching_goal`` (social_nav_sim.py:949-984)."""
        x, y, yaw = self._robot
        hx, hy, hvx, hvy, hradius = self._human
        rvx = v * math.cos(yaw + r)
        rvy = v * math.sin(yaw + r)
        difference_x, difference_y = hx - x, hy - y
        end_x = difference_x + (hvx - rvx) * ROBOT_TIME_STEP
        end_y = difference_y + (hvy - rvy) * ROBOT_TIME_STEP
        dmin = _segment_distance(difference_x, difference_y, end_x, end_y) - hradius - ROBOT_RADIUS
        collision = dmin < 0.0
        goal_distance = math.hypot((x + rvx * ROBOT_TIME_STEP) - self._goal[0],
                                   (y + rvy * ROBOT_TIME_STEP) - self._goal[1])
        return collision, dmin, goal_distance < ROBOT_RADIUS

    def _reward(self, collision, dmin, reaching_goal):
        """The reward and flags of ``compute_reward_and_infos`` (social_nav_sim.py:1004-1028)."""
        if self._time >= TIME_LIMIT - 1.0:
            return 0.0, False, True
        if collision:
            return COLLISION_PENALTY, True, False
        if reaching_goal:
            return SUCCESS_REWARD, True, False
        if dmin < DISCOMFORT_DIST:
            return (dmin - DISCOMFORT_DIST) * DISCOMFORT_PENALTY_FACTOR * ROBOT_TIME_STEP, False, False
        return 0.0, False, False

    def _advance(self, v, r):
        """One robot time step, integrated as the sub-step loop of ``SocialNavGym.step`` (social_nav_gym.py:240-245)."""
        x, y, yaw = self._robot
        hx, hy, hvx, hvy, hradius = self._human
        for _ in range(SUBSTEPS):
            x += math.cos(yaw + r) * v * ENV_TIME_STEP
            y += math.sin(yaw + r) * v * ENV_TIME_STEP
            yaw = (yaw + r) % (2.0 * math.pi)
            hx += hvx * ENV_TIME_STEP
            hy += hvy * ENV_TIME_STEP
            self._time += ENV_TIME_STEP
        self._robot = [x, y, yaw]
        self._human = [hx, hy, hvx, hvy, hradius]
