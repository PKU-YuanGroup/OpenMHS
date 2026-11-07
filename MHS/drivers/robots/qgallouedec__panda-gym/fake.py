"""Fake backend of the panda-gym driver: a pure Python stand-in for ``gym.make("PandaReach-v3")``.

Why a fake: the acceptance gate runs without panda-gym (it needs gymnasium, pybullet, numpy and scipy, setup.py:23),
and package code never imports the clone.  This module re-implements the Reach task of
``panda_gym.envs.panda_tasks:PandaReachEnv`` (the class the driver names as ``native``) at the level of the
end-effector: the Panda's arm, the inverse kinematics and the PyBullet contacts are replaced by moving the
end-effector by the clipped action times 0.05, and the 50-step time limit that ``gymnasium.make`` adds to
PandaReach-v3 is applied here.  Every constant below cites the line of the clone at the pinned commit
(10c4d8adaab07d8a29b2f8dc0aa85f8edd8532ae).  The public members are the ones RobotTaskEnv has (``reset``,
``step``, ``close``; gate G7), and the two space classes duck-type ``gymnasium.spaces.Box`` and ``Dict`` (the bridge
reads ``low``, ``high``, ``shape`` and ``spaces``).

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* the goal comes from Python's ``random.Random(seed)``, upstream draws it from numpy's generator, so a seed does not
  give the same goal on both;
* the end-effector moves directly instead of through inverse kinematics and 20 physics substeps, so there are no
  contacts, friction, actuator or sensor dynamics;
* observations are Python float lists; upstream returns float32 numpy arrays;
* there is no rendering.

Nothing here talks to a device.
"""

import math
import random

# panda_gym/pybullet.py:53-64: timestep 1/500 s, n_substeps 20 (pybullet.py:28), dt = timestep * n_substeps.
DT = (1.0 / 500.0) * 20
# panda_gym/envs/robots/panda.py:31-33: the action space is Box(-1.0, 1.0) with 3 values for end-effector control.
ACTION_LOW, ACTION_HIGH = -1.0, 1.0
N_ACTION = 3
# panda_gym/envs/robots/panda.py:81: one action moves the target by at most 0.05.
STEP_DISPLACEMENT = 0.05
# panda_gym/envs/tasks/reach.py:15-16,22-23: goal_range 0.3 gives these bounds (goal_range_low/high).
GOAL_LOW = [-0.15, -0.15, 0.0]
GOAL_HIGH = [0.15, 0.15, 0.3]
# panda_gym/envs/tasks/reach.py:15: the default distance_threshold.
DISTANCE_THRESHOLD = 0.05
# panda_gym/envs/core.py:237-243: every observation member is bounded by -10.0 and 10.0.
OBSERVATION_BOUND = 10.0
# panda_gym/__init__.py:21: PandaReach-v3 is registered with max_episode_steps=50 (100 only for Stack).
MAX_EPISODE_STEPS = 50
# Test data, not a fact: the first end-effector position after Panda.reset() needs the URDF forward kinematics.
START_POSITION = [0.0, 0.0, 0.2]  # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: one bounded array per observation member."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: named member spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _goal_distance(a, b):
    """``panda_gym.utils.distance``: the Euclidean norm rounded to 6 decimals (utils.py:15-17)."""
    return round(math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b))), 6)


class FakePandaReachEnv:
    """PandaReach-v3 without PyBullet: ``reset(seed, options)`` and ``step(action)`` return what the env returns."""

    def __init__(
        self,
        render_mode="rgb_array",
        reward_type="sparse",
        control_type="ee",
        renderer="Tiny",
        render_width=720,
        render_height=480,
        render_target_position=None,
        render_distance=1.4,
        render_yaw=45,
        render_pitch=-30,
        render_roll=0,
    ):
        if control_type != "ee":
            raise ValueError("the fake models the default end-effector control (control_type='ee') only")
        if render_mode not in ("rgb_array", "human"):
            raise ValueError("render_mode must be 'rgb_array' or 'human'")
        self.render_mode = render_mode
        self._reward_type = reward_type
        # core.py:237-243: Box(-10.0, 10.0) for observation, achieved_goal and desired_goal.
        # The sizes are the PandaReach-v3 shapes: 6 robot values (position and velocity, no finger width because
        # the gripper is blocked, panda.py:109-119) and 3 goal values (reach.py:39-44).
        self.observation_space = Dict(
            {
                "observation": Box([-OBSERVATION_BOUND] * 6, [OBSERVATION_BOUND] * 6, (6,)),
                "achieved_goal": Box([-OBSERVATION_BOUND] * 3, [OBSERVATION_BOUND] * 3, (3,)),
                "desired_goal": Box([-OBSERVATION_BOUND] * 3, [OBSERVATION_BOUND] * 3, (3,)),
            }
        )
        self.action_space = Box([ACTION_LOW] * N_ACTION, [ACTION_HIGH] * N_ACTION, (N_ACTION,))
        self._rng = random.Random()
        self._ee_position = list(START_POSITION)  # placeholder
        self._ee_velocity = [0.0, 0.0, 0.0]  # placeholder
        self._goal = None
        self._steps = 0
        self._closed = False

    def reset(self, *, seed=None, options=None):
        """Reseed (when a seed is given), sample a goal (reach.py:50-53) and reset the arm (panda.py:121-126)."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._goal = [self._rng.uniform(GOAL_LOW[i], GOAL_HIGH[i]) for i in range(3)]
        self._ee_position = list(START_POSITION)  # placeholder
        self._ee_velocity = [0.0, 0.0, 0.0]  # placeholder
        self._steps = 0
        return self._observation(), {"is_success": False}

    def step(self, action):
        """Move the end-effector, then apply the Reach success rule and the sparse reward (reach.py:55-64)."""
        if self._goal is None:
            raise RuntimeError("reset() must be called before step()")
        values = [float(value) for value in action]
        if len(values) != N_ACTION:
            raise ValueError(f"the PandaReach-v3 action has {N_ACTION} values, got {len(values)}")
        # panda.py:54 clips the action to the action space; panda.py:81-86 scales it by 0.05 and clips the height.
        clipped = [min(ACTION_HIGH, max(ACTION_LOW, value)) for value in values]
        delta = [value * STEP_DISPLACEMENT for value in clipped]
        position = [self._ee_position[i] + delta[i] for i in range(3)]
        position[2] = max(0.0, position[2])
        self._ee_position = position
        self._ee_velocity = [delta[i] / DT for i in range(3)]
        self._steps += 1

        distance = _goal_distance(self._ee_position, self._goal)
        terminated = distance < DISTANCE_THRESHOLD
        truncated = self._steps >= MAX_EPISODE_STEPS
        if self._reward_type == "sparse":
            reward = -1.0 if distance > DISTANCE_THRESHOLD else 0.0
        else:
            reward = -distance
        return self._observation(), float(reward), bool(terminated), bool(truncated), {"is_success": bool(terminated)}

    def close(self):
        self._closed = True

    def _observation(self):
        """The RobotTaskEnv observation dict (core.py:265-274) for PandaReach-v3."""
        return {
            "observation": list(self._ee_position) + list(self._ee_velocity),
            "achieved_goal": list(self._ee_position),
            "desired_goal": list(self._goal),
        }
