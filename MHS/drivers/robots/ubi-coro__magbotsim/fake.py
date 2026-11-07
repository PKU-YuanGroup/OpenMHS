"""Fake backend of the MagBotSim driver: a pure Python stand-in for ``StateBasedPushBoxEnv``.

Why a fake: the upstream environment needs Gymnasium, numpy, MuJoCo and shapely
(pyproject.toml:9 and :22-30), and package code never imports the clone.  This module mirrors the public surface
the bridge uses (``reset``, ``step`` and ``close``; gate G7) and the two space shapes of
``StateBasedPushBoxEnv``: a two-value Box action and a Dict observation with ``observation``, ``achieved_goal`` and
``desired_goal``.  Every number below is test data of this stand-in (marked ``# placeholder``), not a fact about the
upstream model; the facts of the package are in driver.py.  Nothing here talks to a device.

The stand-in is a kinematic model, not MuJoCo: it integrates the commanded (x,y) acceleration for the 40 control
cycles of one step and pushes the object while the mover is in contact.  The differences from the upstream
environment are listed in the driver's fidelity ``gaps``.
"""

import math
import random

# The fake model's constants are test data (placeholders); they mirror the defaults of the upstream environment.
CYCLE_TIME_S = 0.001          # placeholder: default MuJoCo timestep (basic_magbot_env.py:1340)
CYCLES_PER_STEP = 40          # placeholder: default num_cycles (state_based_global_pushing_env.py:124)
MAX_EPISODE_STEPS = 25        # placeholder: max_episode_steps of StateBasedPushBoxEnv-v0 (magbotsim/__init__.py:61)
A_MAX = 10.0                  # placeholder: default a_max_xy (state_based_global_pushing_env.py:129)
GOAL_TOLERANCE = 0.05         # placeholder: default max_position_err (state_based_global_pushing_env.py:142)
PER_STEP_PENALTY = -0.01      # placeholder: default per_step_penalty (state_based_global_pushing_env.py:145)
COLLISION_PENALTY = -10.0     # placeholder: default collision_penalty (state_based_global_pushing_env.py:144)
AT_GOAL_REWARD = 1.0          # placeholder: default object_at_goal_reward (state_based_global_pushing_env.py:146)
X_MIN, X_MAX = 0.0, 0.48      # placeholder: a 4x3 tile workspace
Y_MIN, Y_MAX = 0.0, 0.36      # placeholder: a 4x3 tile workspace
CONTACT_RADIUS = 0.08         # placeholder: mover-object contact distance
PUSH_GAIN = 0.5               # placeholder: fraction of the mover displacement transferred to the object
START_LOW, START_HIGH = 0.05, 0.15  # placeholder: initial mover position range


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float64"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads the ``spaces`` mapping."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()


class FakeStateBasedPushBoxEnv:
    """A kinematic stand-in for one mover pushing one box.

    ``reset(seed=..., options=...)`` returns ``(observation, {})`` and ``step(action)`` returns
    ``(observation, reward, terminated, truncated, info)``; the observation is the Dict of the upstream observation
    space.  The public members are the ones the upstream class has (``reset``, ``step`` and ``close``; gate G7).
    """

    def __init__(self, **_options):
        self.action_space = Box([-A_MAX, -A_MAX], [A_MAX, A_MAX])
        self.observation_space = Dict({
            "observation": Box([-math.inf] * 4, [math.inf] * 4),
            "achieved_goal": Box([0.0, 0.0], [1.0, 1.0]),        # placeholder: goal-space bounds
            "desired_goal": Box([0.0, 0.0], [1.0, 1.0]),         # placeholder: goal-space bounds
        })
        self._rng = random.Random()
        self._mover = [0.10, 0.10]        # placeholder: initial mover (x,y)
        self._velocity = [0.0, 0.0]
        self._object = [0.24, 0.18]       # placeholder: initial object (x,y)
        self._goal = [0.36, 0.18]         # placeholder: desired object (x,y)
        self._steps = 0
        self._steps_at_goal = 0
        self._closed = False

    @staticmethod
    def _pair(value):
        """A finite (x,y) pair, or None when the reset option is not one."""
        try:
            x, y = (float(item) for item in value)
        except (TypeError, ValueError):
            return None
        return [x, y] if math.isfinite(x) and math.isfinite(y) else None

    def _observation(self):
        return {
            "observation": [self._mover[0], self._mover[1], self._velocity[0], self._velocity[1]],
            "achieved_goal": list(self._object),
            "desired_goal": list(self._goal),
        }

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        options = options if isinstance(options, dict) else {}
        self._mover = self._pair(options.get("mover_xy_start_pos")) or [
            self._rng.uniform(START_LOW, START_HIGH), self._rng.uniform(START_LOW, START_HIGH)]
        self._velocity = [0.0, 0.0]
        self._object = self._pair(options.get("object_xy_start_pos")) or [0.24, 0.18]   # placeholder
        self._goal = self._pair(options.get("object_xy_goal_pos")) or [0.36, 0.18]      # placeholder
        self._steps = 0
        self._steps_at_goal = 0
        return self._observation(), {}

    def step(self, action):
        if len(action) != 2:
            raise ValueError("the PushBox action has two values (num_movers*2)")
        dt = CYCLE_TIME_S * CYCLES_PER_STEP
        old_x, old_y = self._mover
        self._velocity[0] += float(action[0]) * dt
        self._velocity[1] += float(action[1]) * dt
        self._mover[0] += self._velocity[0] * dt
        self._mover[1] += self._velocity[1] * dt
        moved_x, moved_y = self._mover[0] - old_x, self._mover[1] - old_y

        wall_collision = not (X_MIN <= self._mover[0] <= X_MAX and Y_MIN <= self._mover[1] <= Y_MAX)
        if not wall_collision:
            distance = math.hypot(self._object[0] - self._mover[0], self._object[1] - self._mover[1])
            if distance <= CONTACT_RADIUS:
                self._object[0] = min(max(self._object[0] + moved_x * PUSH_GAIN, X_MIN), X_MAX)
                self._object[1] = min(max(self._object[1] + moved_y * PUSH_GAIN, Y_MIN), Y_MAX)

        goal_reached = math.hypot(self._object[0] - self._goal[0],
                                  self._object[1] - self._goal[1]) <= GOAL_TOLERANCE
        self._steps_at_goal = self._steps_at_goal + 1 if goal_reached else 0
        terminated = bool(wall_collision)
        if terminated:
            reward = COLLISION_PENALTY
        elif goal_reached:
            reward = AT_GOAL_REWARD
        else:
            reward = PER_STEP_PENALTY
        self._steps += 1
        truncated = self._steps >= MAX_EPISODE_STEPS
        info = {
            "mover_collision": False,
            "wall_collision": wall_collision,
            "is_success": bool(goal_reached and not terminated),
            "steps_at_goal": self._steps_at_goal,
        }
        return self._observation(), reward, terminated, truncated, info

    def close(self):
        self._closed = True
