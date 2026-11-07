"""Fake backend of the StackingTask driver: an analytic stand-in for the legacy Gym environment.

Why a fake: the upstream class cannot be imported where the gate runs.  It imports ``assembly_gym`` from the
unpopulated submodule ``submodule/assembly-gym`` (``.gitmodules:21-24``), it needs a PyBullet scene, task data and
aggregation properties, and package code never imports the read-only clone.  This module therefore mirrors the public
environment interface the bridge uses (``reset``, ``step``, ``close``; gate G7) and the action and observation keys of
the canonical ``get_env_config`` configuration (``python/algorithm/run_config/env/stacking.py:33-43``).  The two space
classes duck-type ``gym.spaces.Dict`` and ``gym.spaces.Box`` (the bridge reads ``spaces``, ``low``, ``high`` and
``shape``).

What this is not: the upstream environment.  It is an analytic kinematic model with no PyBullet, no contacts, no
inverse kinematics, no task data and no reward model.  Every numeric parameter below is placeholder test data, not a
fact, a limit or a measurement; the fidelity ``gaps`` of the driver list the differences.  The upstream episode logic
is a part-release/target check plus an optional ``time_limit_steps`` (``python/task/stacking_task.py:142-154``,
``python/task/base_task.py:111-112``); the fake only stops at a placeholder step limit.

Nothing here talks to a device.
"""

import math
import random

# Every number in this block is a placeholder of the analytic fake, not a sourced fact or limit.
ARM_JOINTS = 6                  # placeholder: joint count of the canonical UR10 arm
GRIPPER_JOINTS = 1              # placeholder: joint count of the canonical gripper
MAX_EPISODE_STEPS = 100         # placeholder: the fake's episode length
DT_S = 0.05                     # placeholder: simulated seconds per tick
POSITION_SCALE = 2.0            # placeholder: the pose sensors' position bound used for normalization
IDENTITY_ROTATION = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]   # placeholder: first two columns of a 3x3 identity


class Box:
    """Duck-typed ``gym.spaces.Box``: one low and one high value per element."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gym.spaces.Dict``: a mapping of names to spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _unit_box(count):
    """A Box of ``count`` elements in [-1, 1] (the normalizer's output range)."""
    return Box([-1.0] * count, [1.0] * count)


def _clip(value):
    """Keep a synthesized observation inside the normalized Box."""
    return max(-1.0, min(1.0, float(value)))


def _rotation(yaw):
    """The first two columns (row-major) of a rotation about z, as the pose sensors publish them."""
    cosine, sine = math.cos(yaw), math.sin(yaw)
    return [cosine, -sine, sine, cosine, 0.0, 0.0]


class FakeStackingTask:
    """A small deterministic stand-in for ``task.stacking_task:StackingTask``."""

    def __init__(self, **options):
        # The upstream constructor takes controllers, sensors, rewards, task data and aggregation properties, not
        # options; the backend options are accepted and ignored.
        del options
        # The action keys are the canonical controller names "<prefix>_controller_ur10_<component>"
        # (python/task/controllers/robot_component_controller.py:22-23).
        self.action_space = Dict({
            "joint_velocity_difference_controller_ur10_arm": _unit_box(ARM_JOINTS),
            "joint_position_controller_ur10_gripper": _unit_box(GRIPPER_JOINTS),
        })
        # The observation keys are the sensors of the canonical configuration (stacking.py:41-43); every continuous
        # sensor is normalized to [-1, 1] (python/task/sensors/continuous_sensor.py:18-22).
        self.observation_space = Dict({
            "arm_joint_pos_sin": _unit_box(ARM_JOINTS),
            "arm_joint_pos_cos": _unit_box(ARM_JOINTS),
            "arm_joint_vel": _unit_box(ARM_JOINTS),
            "gripper_joint_pos": _unit_box(GRIPPER_JOINTS),
            "gripper_joint_vel": _unit_box(GRIPPER_JOINTS),
            "end_effector_pos": _unit_box(3),
            "end_effector_rot": _unit_box(6),
            "end_effector_vel_angular": _unit_box(3),
            "end_effector_vel_linear": _unit_box(3),
            "current_part_pos": _unit_box(3),
            "current_part_rot": _unit_box(6),
            "current_part_vel_angular": _unit_box(3),
            "current_part_vel_linear": _unit_box(3),
            "current_part_target_pos": _unit_box(3),
            "current_part_target_rot": _unit_box(6),
            "time": _unit_box(1),
        })
        self._rng = random.Random(0)   # placeholder: default generator seed
        self._ready = False

    def reset(self, seed=None, options=None):
        """Start an episode; the upstream ``reset`` takes no arguments (base_task.py:160) and the fake adds a seed."""
        del options
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._joint_positions = [self._rng.uniform(-0.1, 0.1) for _ in range(ARM_JOINTS)]  # placeholder
        self._joint_velocities = [0.0] * ARM_JOINTS
        self._gripper_position = self._rng.uniform(-0.2, 0.2)                              # placeholder
        self._gripper_velocity = 0.0
        self._end_effector_pos = [0.0, 0.0, 0.5]                                           # placeholder
        self._yaw = self._rng.uniform(-0.1, 0.1)                                           # placeholder
        self._part_pos = [self._rng.uniform(-0.2, 0.2) for _ in range(3)]                  # placeholder
        self._part_vel_linear = [0.0, 0.0, 0.0]
        self._part_vel_angular = [0.0, 0.0, 0.0]
        self._target_pos = [0.0, 0.0, 0.5]                                                 # placeholder
        self._step = 0
        self._done = False
        self._ready = True
        return self._observation()

    def step(self, action):
        """Apply one controller dictionary and return the legacy ``(observation, reward, done, info)`` tuple."""
        if not self._ready:
            raise RuntimeError("call reset before step")
        if self._done:
            raise RuntimeError("the episode has ended; call reset")
        try:
            arm = list(action["joint_velocity_difference_controller_ur10_arm"])
            gripper = list(action["joint_position_controller_ur10_gripper"])
        except (KeyError, TypeError) as exc:
            raise ValueError("the action needs the arm and gripper controller entries") from exc
        if len(arm) != ARM_JOINTS or len(gripper) != GRIPPER_JOINTS:
            raise ValueError("the action has the wrong number of joint values")
        for index in range(ARM_JOINTS):
            velocity = 0.9 * self._joint_velocities[index] + 0.1 * float(arm[index])        # placeholder
            self._joint_velocities[index] = _clip(velocity)
            position = self._joint_positions[index] + DT_S * self._joint_velocities[index]  # placeholder
            self._joint_positions[index] = math.remainder(position, 2.0 * math.pi)
        self._gripper_velocity = _clip(0.9 * self._gripper_velocity + 0.1 * float(gripper[0]))  # placeholder
        self._gripper_position = _clip(0.9 * self._gripper_position + 0.1 * float(gripper[0]))  # placeholder
        for index in range(3):
            moved = 0.95 * self._end_effector_pos[index] + 0.01 * float(arm[index])          # placeholder
            self._end_effector_pos[index] = _clip(moved / POSITION_SCALE) * POSITION_SCALE
        self._yaw = math.remainder(self._yaw + 0.01 * float(arm[5]), 2.0 * math.pi)          # placeholder
        self._step += 1
        self._done = self._step >= MAX_EPISODE_STEPS
        # Placeholder rewards: the upstream reward is a sum of four task reward terms, which the fake does not model.
        reward = -0.01 * math.dist(self._end_effector_pos, self._target_pos)                 # placeholder
        info = {"metrics": {"current_part_position_error": math.dist(self._part_pos, self._target_pos),
                            "parts_placed": 0}}
        return self._observation(), reward, self._done, info

    def close(self):
        """The bridge closes the environment at teardown; the fake keeps no external resource."""
        self._ready = False

    def _observation(self):
        return {
            "arm_joint_pos_sin": [_clip(math.sin(value)) for value in self._joint_positions],
            "arm_joint_pos_cos": [_clip(math.cos(value)) for value in self._joint_positions],
            "arm_joint_vel": [_clip(value) for value in self._joint_velocities],
            "gripper_joint_pos": [_clip(self._gripper_position)],
            "gripper_joint_vel": [_clip(self._gripper_velocity)],
            "end_effector_pos": [_clip(value / POSITION_SCALE) for value in self._end_effector_pos],
            "end_effector_rot": [_clip(value) for value in _rotation(self._yaw)],
            "end_effector_vel_angular": [_clip(value) for value in self._joint_velocities[3:]],
            "end_effector_vel_linear": [_clip(value) for value in self._joint_velocities[:3]],
            "current_part_pos": [_clip(value / POSITION_SCALE) for value in self._part_pos],
            "current_part_rot": list(IDENTITY_ROTATION),
            "current_part_vel_angular": [_clip(value) for value in self._part_vel_angular],
            "current_part_vel_linear": [_clip(value) for value in self._part_vel_linear],
            "current_part_target_pos": [_clip(value / POSITION_SCALE) for value in self._target_pos],
            "current_part_target_rot": list(IDENTITY_ROTATION),
            "time": [_clip(2.0 * self._step / MAX_EPISODE_STEPS - 1.0)],
        }
