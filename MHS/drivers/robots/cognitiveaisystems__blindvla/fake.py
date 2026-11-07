"""Fake backend of the BlindVLA driver: a pure Python stand-in for ``ManiSkill Empty-v1``.

Why a fake: ManiSkill needs SAPIEN, PyTorch, gymnasium and its asset store, none of which the acceptance gate has, and
package code never imports the upstream clone.  This module mirrors the members of
``ManiSkill.mani_skill.envs.tasks.empty_env:EmptyEnv`` that the Gymnasium bridge uses (``reset``, ``step``, ``close``;
gate G7) and the two spaces the bridge reads (``action_space`` and ``observation_space``).  The public methods are the
three EmptyEnv has; the space and fake classes are duck-typed stand-ins for ``gymnasium.spaces.Box``.

The action space is the one ManiSkill serves for the default Panda control mode, ``pd_joint_delta_pos``: eight values,
-1 .. 1 each.  Its arm and mimic gripper configs (panda.py:90-98, :177-184) set no ``normalize_action``, whose default
is True (pd_joint_pos.py:121), so each controller serves Box(-1, 1) of its shape (base_controller.py:65-67,
gym_utils.py:108-110) and the combined controller flattens the seven arm values and the one gripper value (the mimic
controller has one action dimension, pd_joint_pos.py:126-131) into one space (base_controller.py:281-285).  ``step``
clips and scales each value as the controllers do (gym_utils.py:102-105): to an arm joint delta in -0.1 .. 0.1 and to
the gripper target in -0.01 .. 0.04.  The observation space is the flattened state observation of the default state
observation mode: qpos and qvel of the nine Panda joints, so 18 numbers (base_agent.py:337; the nine joint names are
panda.py:53-65).  EmptyEnv has only reward mode ``none`` (empty_env.py:19), so every step pays zero
(sapien_env.py:611-612), and its ``evaluate`` returns no success or fail key (empty_env.py:47-48), so a step never
terminates (sapien_env.py:959-963).  The registered time limit is 200000 steps (empty_env.py:17).

What this is not: the upstream environment.  It is kinematic (fidelity F0): a step adds the scaled delta to qpos and
clears qvel; there is no PhysX simulation, no contact, friction, actuator, sensor or noise model, and no rendering.
The zero start positions and instantaneous target-to-position update are test data (# placeholder), not facts or limits; the action
space, its width and the scaling ranges are the upstream's and carry no mark.  It was not compared with upstream
ManiSkill.  Nothing here talks to a device.
"""

import math

# Panda's arm and gripper joint counts (panda.py:53-65); one mimic action for the two gripper joints
# (pd_joint_pos.py:126-131), and qpos + qvel for the state observation (base_agent.py:337).
ARM_JOINTS = 7
GRIPPER_JOINTS = 2
QPOS_SIZE = ARM_JOINTS + GRIPPER_JOINTS
OBSERVATION_SIZE = 2 * QPOS_SIZE
ACTION_SIZE = ARM_JOINTS + 1

# The normalised action space (gym_utils.py:108-110) and the ranges the default pd_joint_delta_pos configs scale it to:
# an arm joint delta (panda.py:90-98) and the gripper target (panda.py:177-184).
ACTION_LOW, ACTION_HIGH = -1.0, 1.0
ARM_LOW, ARM_HIGH = -0.1, 0.1
GRIPPER_LOW, GRIPPER_HIGH = -0.01, 0.04

# Empty-v1's registered max_episode_steps (empty_env.py:17); the MSTimeLimit wrapper truncates there
# (registration.py:160-163 and :249-254).
MAX_EPISODE_STEPS = 200000


def clip_and_scale(value, low, high):
    """clip_and_scale_action (gym_utils.py:102-105): clip to -1 .. 1, then map -1 .. 1 onto low .. high."""
    return 0.5 * (high + low) + 0.5 * (high - low) * max(ACTION_LOW, min(ACTION_HIGH, value))


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype

    def contains(self, value):
        try:
            values = [float(item) for item in value]
        except (TypeError, ValueError):
            return False
        return len(values) == len(self.low) and all(
            low <= item <= high for item, low, high in zip(values, self.low, self.high))


class FakeEmptyEnv:
    """The Empty-v1 state/action interface without SAPIEN: ``reset(seed, options)`` and ``step(action)``."""

    def __init__(self, robot_uids="panda", **options):
        self.robot_uids = robot_uids
        self.options = dict(options)
        self.action_space = Box([ACTION_LOW] * ACTION_SIZE,
                                [ACTION_HIGH] * ACTION_SIZE)        # gym_utils.py:108-110, base_controller.py:281-285
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE,
                                     [math.inf] * OBSERVATION_SIZE)  # base_agent.py:337
        self._qpos = None
        self._qvel = None
        self._elapsed_steps = 0
        self._seed = None

    def reset(self, *, seed=None, options=None):
        self._qpos = [0.0] * QPOS_SIZE                             # placeholder
        self._qvel = [0.0] * QPOS_SIZE                             # placeholder
        self._elapsed_steps = 0
        if seed is not None:
            self._seed = int(seed)
        return self._observation(), {}

    def step(self, action):
        if self._qpos is None:
            raise AssertionError("Call reset before using step method.")
        values = [float(item) for item in action]
        if len(values) != ACTION_SIZE:
            raise ValueError(f"expected {ACTION_SIZE} action values, got {len(values)}")
        # As the normalised controllers do, each value is clipped and scaled first (base_controller.py:131-132).
        # Kinematic stand-in for pd_joint_delta_pos: the arm target is the current qpos plus the delta
        # (pd_joint_pos.py:73-86); the mimic gripper broadcasts the same target to both joints.
        # Immediate qpos assignment is still kinematic placeholder behavior; native drive dynamics and asset limits
        # are not reproduced or inferred from the target configuration.
        for index in range(ARM_JOINTS):
            self._qpos[index] = self._qpos[index] + clip_and_scale(values[index], ARM_LOW, ARM_HIGH)
        target = clip_and_scale(values[ARM_JOINTS], GRIPPER_LOW, GRIPPER_HIGH)
        self._qpos[ARM_JOINTS] = target                            # placeholder
        self._qpos[ARM_JOINTS + 1] = target                        # placeholder
        self._qvel = [0.0] * QPOS_SIZE                              # placeholder
        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS        # empty_env.py:17, registration.py:160-163
        return self._observation(), 0.0, False, truncated, {"elapsed_steps": self._elapsed_steps}

    def close(self):
        self._qpos = None
        self._qvel = None

    def _observation(self):
        return list(self._qpos) + list(self._qvel)
