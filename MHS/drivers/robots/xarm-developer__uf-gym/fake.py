"""Fake backend of the uf-gym driver: a pure Python kinematic stand-in for ``XArm6ReachEnv``.

Why a fake: the acceptance gate runs without gymnasium, pybullet or panda-gym, and package code never imports the
clone.  ``uf_gym.envs.uf_tasks.xarm6_tasks:XArm6ReachEnv`` builds a PyBullet simulation (xarm6_tasks.py:201) and
takes its observation, reward and step limit from the external panda-gym ``RobotTaskEnv`` and ``Reach`` classes,
which are not part of the clone (README.md:11-12, test_xarm6_reach.py:3).  This module therefore reproduces only
the interface the bridge uses and the action handling that the clone states.

What is modelled, and what is not:

* the action space of the Reach environment: ``Box(-1, 1, shape=(3,), float32)``, because ``XArm6ReachEnv`` builds
  ``XArm6(block_gripper=True, control_type="ee")`` (xarm6_tasks.py:202) and that robot has three end-effector
  action dimensions and no gripper dimension (xarm6.py:32-34);
* the 0.05 m end-effector displacement per action unit and the target-height clip at z=0 (xarm6.py:85, xarm6.py:90);
* the 50-step time limit of ``XArm6Reach-v3`` (uf_gym/__init__.py:19, ``max_episode_steps=50`` for Reach);
* an observation, a goal, a reward and a success radius that are placeholders (marked ``# placeholder``), because
  the upstream values come from panda-gym and are not stated in the clone.

The public members are the ones the environment has in the clone: ``reset`` (xarm6.py:125), ``step`` (test scripts,
test_xarm6_reach.py:31) and ``close`` (test_xarm6_reach.py:40), plus the ``action_space`` attribute (xarm6.py:34).
There is deliberately no ``observation_space``: the upstream class inherits it from the external ``RobotTaskEnv``,
which the clone does not define, so no observation bounds are claimed.  Nothing here talks to a device.
"""

import math
import random

# uf_gym/envs/uf_robots/xarm6.py:32-34: with control_type "ee" the action has 3 arm dimensions, and the Reach
# environment blocks the gripper, so no gripper dimension is added.
ACTION_DIM = 3
# uf_gym/envs/uf_robots/xarm6.py:34: spaces.Box(-1.0, 1.0, shape=(n_action,), dtype=np.float32)
ACTION_LOW = -1.0
ACTION_HIGH = 1.0
# uf_gym/envs/uf_robots/xarm6.py:85: ee_displacement = ee_displacement[:3] * 0.05
EE_STEP = 0.05
# uf_gym/__init__.py:19: max_episode_steps=100 if task == "Stack" else 50; XArm6Reach-v3 is a Reach task.
MAX_EPISODE_STEPS = 50

# The values below are test data of this stand-in, not facts about xArm6 or the upstream environment.
START_POSITION = [0.0, 0.0, 0.0]                  # placeholder: end-effector position after reset
VELOCITY_GAIN = 1.0                               # placeholder: observation velocity per action unit
SUCCESS_RADIUS = 0.05                             # placeholder: distance at which the reach succeeds
STEP_REWARD = -1.0                                # placeholder: reward before the goal is reached
SUCCESS_REWARD = 0.0                              # placeholder: reward at the goal
GOAL_LOW = [0.20, -0.20, 0.10]                    # placeholder: lower bound of the sampled goal
GOAL_HIGH = [0.40, 0.20, 0.30]                     # placeholder: upper bound of the sampled goal


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound for each element.

    The bridge reads ``low``, ``high``, ``shape`` and ``dtype`` and classifies the space by its class name.
    """

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        if len(value) != len(self.low):
            return False
        return all(float(low) <= float(item) <= float(high)
                   for low, high, item in zip(self.low, self.high, value))


def _values(action):
    """A plain list of floats from the action the bridge passes (a list for a non-numpy Box)."""
    if hasattr(action, "tolist"):
        action = action.tolist()
    if not isinstance(action, (list, tuple)):
        raise TypeError("the action must be a sequence of numbers")
    out = []
    for item in action:
        value = float(item)
        if not math.isfinite(value):
            raise ValueError("the action contains a non-finite value")
        out.append(value)
    return out


class FakeXArm6ReachEnv:
    """A deterministic kinematic stand-in with the interface of ``XArm6ReachEnv``.

    ``reset(seed=...)`` fixes the sampled goal and ``step(action)`` advances the end-effector by the clip of the
    action scaled by the clone's 0.05 m step.  The nine-number observation is
    ``[end-effector position, end-effector velocity, goal]``; its values, the goal range, the success radius and
    the reward are placeholders.
    """

    def __init__(self, reward_type="sparse", control_type="ee", render_mode=None, **_options):
        if control_type != "ee":
            raise ValueError("the fake stand-in models only the end-effector control type")
        if render_mode is not None:
            raise ValueError("the fake stand-in cannot render; use render_mode=None")
        self.reward_type = reward_type                              # placeholder: accepted, not modelled
        self.control_type = control_type                            # xarm6_tasks.py:202
        self.action_space = Box([ACTION_LOW] * ACTION_DIM, [ACTION_HIGH] * ACTION_DIM)  # xarm6.py:34
        self._rng = random.Random()
        self._steps = 0
        self._position = list(START_POSITION)                       # placeholder
        self._velocity = [0.0] * ACTION_DIM                         # placeholder
        self._goal = list(GOAL_HIGH)                                # placeholder, replaced by reset()
        self._reset_state()

    def _reset_state(self):
        self._steps = 0
        self._position = list(START_POSITION)                       # placeholder
        self._velocity = [0.0] * ACTION_DIM                         # placeholder
        self._goal = [self._rng.uniform(low, high) for low, high in zip(GOAL_LOW, GOAL_HIGH)]  # placeholder

    def _observation(self):
        # placeholder: a flat vector, not the panda-gym RobotTaskEnv observation structure
        return list(self._position) + list(self._velocity) + list(self._goal)

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._reset_state()
        return self._observation(), {}

    def step(self, action):
        values = _values(action)
        if len(values) != ACTION_DIM:
            raise ValueError(f"the action needs {ACTION_DIM} values, got {len(values)}")
        clipped = [min(ACTION_HIGH, max(ACTION_LOW, value)) for value in values]  # xarm6.py:56
        self._position = [position + delta * EE_STEP                # xarm6.py:85
                          for position, delta in zip(self._position, clipped)]
        self._position[2] = max(0.0, self._position[2])             # xarm6.py:90
        self._velocity = [delta * VELOCITY_GAIN for delta in clipped]  # placeholder
        self._steps += 1
        distance = math.sqrt(sum((position - goal) ** 2
                                 for position, goal in zip(self._position, self._goal)))
        terminated = bool(distance <= SUCCESS_RADIUS)               # placeholder
        truncated = bool(self._steps >= MAX_EPISODE_STEPS)          # uf_gym/__init__.py:19
        reward = SUCCESS_REWARD if terminated else STEP_REWARD      # placeholder
        return self._observation(), reward, terminated, truncated, {"is_success": terminated}

    def close(self):
        self._steps = 0
