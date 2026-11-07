"""Fake backend of the skill-aware Panda-gym driver: a pure Python stand-in for ``PandaPushEnv``.

Why a fake: the acceptance gate cannot install the upstream stack (panda-gym, gymnasium, pybullet, numpy and scipy,
``setup.py:23``) and package code never imports the clone.  This module re-implements the contract of the registered
environment ``PandaSkillAware-v3`` (``gymnasium.make`` adds a 50-step ``TimeLimit``,
``skill_aware_panda_gym/__init__.py:10``) without a physics engine:

* ``step(action)`` returns the five values of ``PandaPushEnv.step`` (``skill_aware_panda_gym/envs/__init__.py:155-166``)
  and puts the skill label in ``info["state"]``, using the thresholds of ``get_state``
  (``skill_aware_panda_gym/envs/__init__.py:141-153``);
* the object and goal are drawn with the wrapper's ranges, ``goal_xy_range`` 0.3 and ``obj_xy_range`` 0.3
  (``skill_aware_panda_gym/envs/__init__.py:25,27``), and success is the ``distance_threshold`` 0.05
  (``skill_aware_panda_gym/envs/__init__.py:24``) between the object position and the goal;
* the observation is the dict that panda-gym's ``RobotTaskEnv`` builds: the robot block, the task's object pose and
  velocity block, and the achieved and desired goals.  That base class is an external dependency and is not in this
  clone, so the sizes here are stand-in test data.

What this is not: the upstream environment or PyBullet.  There is no rigid-body dynamics, contact, friction, mass,
actuator or sensor model; the skill label comes from the stand-in's own geometric flags, not from contact points.
The public methods are limited to ``__init__``, ``reset``, ``step`` and ``close`` (gate G7).  ``reset``, ``close``
and the action space are inherited from panda-gym's ``RobotTaskEnv``/``Panda`` upstream, which the clone's AST
cannot follow, so G7 reports ``MAYBE_ABSENT`` for the names that occur somewhere in the clone.  Nothing here talks
to a device.
"""

import math
import random

#: Sourced from the clone: the task wrapper's defaults and its success threshold
#: (skill_aware_panda_gym/envs/__init__.py:24-27).
DISTANCE_THRESHOLD = 0.05
GOAL_XY_RANGE = 0.3
OBJ_XY_RANGE = 0.3
#: The registration's limit, applied by the TimeLimit wrapper that gymnasium.make adds
#: (skill_aware_panda_gym/__init__.py:10).
MAX_EPISODE_STEPS = 50
#: get_state's thresholds (skill_aware_panda_gym/envs/__init__.py:141 and :150).
AT_HIGH_Z = 0.021
PUSH_LOW_Z = 0.019
PUSH_HIGH_Z = 0.21

#: Test data of the stand-in, not values of the clone.  panda-gym's Panda action Box is [-1, 1] and has one value
#: per end-effector axis plus one for the gripper; that class is an external dependency, not in this clone.
ACTION_LOW = [-1.0, -1.0, -1.0, -1.0]                    # placeholder
ACTION_HIGH = [1.0, 1.0, 1.0, 1.0]                       # placeholder
ACTION_SCALE = 0.05                                      # placeholder: displacement from one action value
WORKSPACE_LOW = [-0.3, -0.3, 0.0]                        # placeholder
WORKSPACE_HIGH = [0.3, 0.3, 0.3]                         # placeholder
EE_START = [-0.3, 0.0, 0.05]                             # placeholder
OBJECT_Z = 0.02                                          # placeholder: object centre resting on the table
GOAL_Z = 0.02                                            # placeholder
FINGER_OPEN = 0.08                                       # placeholder
FINGER_STEP = 0.02                                       # placeholder
FINGER_CLOSED = 0.045                                    # placeholder: two-finger contact below this width
CONTACT_XY = 0.03                                        # placeholder
CONTACT_Z = 0.05                                         # placeholder
FALL_STEP = 0.005                                        # placeholder
SPARSE_FAILURE_REWARD = -1.0                             # placeholder: panda-gym's sparse reward
N_ROBOT = 7                                              # placeholder: panda-gym's Panda.get_obs
N_TASK = 13                                              # placeholder: panda-gym's PickAndPlace.get_obs
N_ACHIEVED = 3                                           # placeholder: object position
N_DESIRED = 3                                            # placeholder: goal position


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != self.shape[0]:
            return False
        return all(float(low) <= float(item) <= float(high)
                   for item, low, high in zip(value, self.low, self.high))


def _clip(value, low, high):
    return min(high, max(low, value))


def _distance(first, second):
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(first, second)))


class FakePandaPushEnv:
    """A deterministic analytic stand-in with the step result of ``PandaPushEnv``."""

    def __init__(self, **_options):
        # PandaPushEnv sets the robot's action space from control_type "ee" and block_gripper=False
        # (skill_aware_panda_gym/envs/__init__.py:107-108); the Box itself comes from panda-gym's Panda.
        self.action_space = Box(ACTION_LOW, ACTION_HIGH)             # placeholder values
        self._rng = random.Random(0)                                  # placeholder
        self._ee = list(EE_START)                                     # placeholder
        self._ee_velocity = [0.0, 0.0, 0.0]                           # placeholder
        self._fingers = FINGER_OPEN                                   # placeholder
        self._object = [0.0, 0.0, OBJECT_Z]                           # placeholder
        self._object_velocity = [0.0, 0.0, 0.0]                       # placeholder
        self._goal = [0.0, 0.0, GOAL_Z]                               # placeholder
        self._table_contact = True
        self._finger_contacts = 0
        self._episode_steps = 0
        self._closed = False
        self._reset(None)

    # -- helpers (private: G7 checks only the public surface) ------------------
    def _observation(self):
        """The dict panda-gym's RobotTaskEnv builds (the base class is not in the clone)."""
        robot = [self._ee[0], self._ee[1], self._ee[2],
                 self._ee_velocity[0], self._ee_velocity[1], self._ee_velocity[2],
                 self._fingers]                                        # placeholder layout
        task = [self._object[0], self._object[1], self._object[2],
                0.0, 0.0, 0.0, 1.0,                                    # placeholder rotation
                self._object_velocity[0], self._object_velocity[1], self._object_velocity[2],
                0.0, 0.0, 0.0]                                         # placeholder angular velocity
        if len(robot) != N_ROBOT or len(task) != N_TASK:
            raise AssertionError("the stand-in observation layout changed")
        observation = {
            "observation": robot + task,
            "achieved_goal": list(self._object),
            "desired_goal": list(self._goal),
        }
        if (len(observation["achieved_goal"]) != N_ACHIEVED
                or len(observation["desired_goal"]) != N_DESIRED):
            raise AssertionError("the stand-in goal layout changed")
        return observation

    def _success(self):
        return _distance(self._object, self._goal) < DISTANCE_THRESHOLD

    def _skill(self):
        """The label get_state returns from the object height and the two contact flags."""
        at_high = self._object[2] > AT_HIGH_Z
        zero_table_contact = not self._table_contact
        contact_with_two_fingers = self._finger_contacts >= 2
        if at_high and zero_table_contact and contact_with_two_fingers:
            return "pick"
        if at_high:
            return "roll"
        if PUSH_LOW_Z < self._object[2] < PUSH_HIGH_Z:
            return "push"
        return "down"

    def _reset(self, seed):
        """Place the object and the goal with the wrapper's ranges, then return to the start pose."""
        if seed is not None:
            self._rng = random.Random(int(seed))                       # placeholder generator
        self._ee = list(EE_START)                                      # placeholder
        self._ee_velocity = [0.0, 0.0, 0.0]                            # placeholder
        self._fingers = FINGER_OPEN                                    # placeholder
        self._object = [self._rng.uniform(-OBJ_XY_RANGE, OBJ_XY_RANGE),
                        self._rng.uniform(-OBJ_XY_RANGE, OBJ_XY_RANGE),
                        OBJECT_Z]                                      # placeholder z
        self._object_velocity = [0.0, 0.0, 0.0]                        # placeholder
        self._goal = [self._rng.uniform(-GOAL_XY_RANGE, GOAL_XY_RANGE),
                      self._rng.uniform(-GOAL_XY_RANGE, GOAL_XY_RANGE),
                      GOAL_Z]                                          # placeholder z
        self._table_contact = True
        self._finger_contacts = 0
        self._episode_steps = 0

    # -- the gym environment surface ------------------------------------------
    def reset(self, seed=None, options=None):
        """Reset the stand-in and return ``(observation, info)`` as panda-gym's RobotTaskEnv does."""
        self._reset(seed)
        return self._observation(), {"is_success": self._success()}

    def step(self, action):
        """Apply one action, advance one transition and return the five values of ``PandaPushEnv.step``."""
        values = [float(value) for value in action]
        if len(values) != len(ACTION_LOW):
            raise ValueError(f"PandaSkillAware-v3 takes {len(ACTION_LOW)} action values, got {len(values)}")
        values = [_clip(value, low, high) for value, low, high in zip(values, ACTION_LOW, ACTION_HIGH)]
        previous_ee = list(self._ee)
        displacement = [ACTION_SCALE * values[index] for index in range(3)]   # placeholder scale
        self._ee = [_clip(previous_ee[index] + displacement[index],
                          WORKSPACE_LOW[index], WORKSPACE_HIGH[index])
                    for index in range(3)]                                     # placeholder workspace
        self._ee_velocity = [(self._ee[index] - previous_ee[index]) for index in range(3)]  # placeholder
        if values[3] > 0:
            self._fingers = max(0.0, self._fingers - FINGER_STEP)              # placeholder
        else:
            self._fingers = min(FINGER_OPEN, self._fingers + FINGER_STEP)      # placeholder
        near = (_distance(self._ee[:2], self._object[:2]) <= CONTACT_XY
                and abs(self._ee[2] - self._object[2]) <= CONTACT_Z)           # placeholder
        self._finger_contacts = 2 if near and self._fingers <= FINGER_CLOSED else 0
        grasped = self._finger_contacts == 2 and near and values[3] > 0
        if grasped:
            self._object = [self._ee[0], self._ee[1], max(self._ee[2], OBJECT_Z)]   # placeholder
            self._object_velocity = list(self._ee_velocity)                        # placeholder
            self._table_contact = self._object[2] <= AT_HIGH_Z
        elif (near and values[3] <= 0 and self._fingers > FINGER_CLOSED
              and self._object[2] <= AT_HIGH_Z):
            # A push along the table: the open fingers move the object with the end effector.
            self._object[0] = _clip(self._object[0] + displacement[0],
                                    WORKSPACE_LOW[0], WORKSPACE_HIGH[0])            # placeholder
            self._object[1] = _clip(self._object[1] + displacement[1],
                                    WORKSPACE_LOW[1], WORKSPACE_HIGH[1])            # placeholder
            self._table_contact = True
        elif self._object[2] > OBJECT_Z:
            self._object[2] = max(OBJECT_Z, self._object[2] - FALL_STEP)            # placeholder
            self._table_contact = self._object[2] <= AT_HIGH_Z
        else:
            self._table_contact = True
        self._episode_steps += 1
        terminated = self._success()
        truncated = self._episode_steps >= MAX_EPISODE_STEPS
        reward = 0.0 if terminated else SPARSE_FAILURE_REWARD                        # placeholder
        info = {"is_success": terminated, "state": self._skill()}
        return self._observation(), reward, terminated, truncated, info

    def close(self):
        self._closed = True
