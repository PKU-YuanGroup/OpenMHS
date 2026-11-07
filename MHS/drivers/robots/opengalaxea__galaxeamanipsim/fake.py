"""Fake backend of the Galaxea R1Base-v0 driver: a pure Python stand-in for the environment.

Why a fake: the upstream environment needs Sapien, a CUDA machine and the robot URDF/mesh assets
(``pyproject.toml:18-35``), and package code never imports the upstream clone.  This module implements the
public surface of ``galaxea_sim.envs.base.bimanual_manipulation:BimanualManipulationEnv`` that the Gymnasium
bridge uses (``reset``, ``step``, ``close``; gate G7) together with a duck-typed ``Box``/``Dict``/``Text``
action and observation space.

What it is: a *kinematic* stand-in.  It copies the commanded left-arm, left-gripper, right-arm and
right-gripper targets into the observation with zero joint velocities; it does not run Sapien, gravity,
contacts, actuators or the controller's inverse kinematics.  What it is not: the upstream environment.  The
differences, including the omitted camera arrays, are listed in the driver's ``fidelity.gaps`` and in
``RESULT.json``; they were never compared with an upstream run.

Every number in this module is placeholder test data (the initial joint positions, the identity EE poses
and the zero commands), not a fact about the device; the shapes follow the R1 URDF but are not a source for
any Fact or Limit.  Nothing here talks to a device.
"""

import math

# Placeholder shapes of the R1Base-v0 configuration: R1Robot has six arm joints per side, one observed
# finger position per hand, a four-joint torso and a three-value chassis observation.  These are test data.
LEFT_ARM_JOINTS = 6  # placeholder
RIGHT_ARM_JOINTS = 6  # placeholder
TORSO_JOINTS = 4  # placeholder
CHASSIS_JOINTS = 3  # placeholder
EE_POSE_VALUES = 7  # placeholder: position 3 + quaternion 4
ACTION_DIM = LEFT_ARM_JOINTS + RIGHT_ARM_JOINTS + 2  # placeholder: two gripper commands


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a mapping of named sub-spaces."""

    def __init__(self, spaces=None):
        self.spaces = dict(spaces or {})


class Text:
    """Duck-typed ``gymnasium.spaces.Text``: the bridge reads no attribute of a Text space."""

    def __init__(self, max_length=1):
        self.max_length = max_length
        self.shape = ()
        self.dtype = "str"


def _box(count):
    """An unbounded float Box with ``count`` elements (placeholder: ``low=-inf``, ``high=inf``)."""
    return Box([-math.inf] * count, [math.inf] * count)


def _arm_box():
    return _box(LEFT_ARM_JOINTS)


def _observation_space():
    """The state-mode observation space of BimanualManipulationEnv (``_get_obs``), as a duck-typed Dict."""
    return Dict({
        "upper_body_observations": Dict({
            "left_arm_joint_position": _arm_box(),
            "right_arm_joint_position": _arm_box(),
            "left_arm_gripper_position": _box(1),
            "right_arm_gripper_position": _box(1),
            "left_arm_joint_velocity": _arm_box(),
            "right_arm_joint_velocity": _arm_box(),
            "left_arm_ee_pose": _box(EE_POSE_VALUES),
            "right_arm_ee_pose": _box(EE_POSE_VALUES),
        }),
        "upper_body_action_dict": Dict({
            "left_arm_joint_position_cmd": _arm_box(),
            "right_arm_joint_position_cmd": _arm_box(),
            "left_arm_gripper_position_cmd": _box(1),
            "right_arm_gripper_position_cmd": _box(1),
        }),
        "lower_body_observations": Dict({
            "chassis_joint_position": _box(CHASSIS_JOINTS),
            "torso_joint_position": _box(TORSO_JOINTS),
        }),
        "lower_body_action_dict": Dict({
            "chassis_target_speed_cmd": _box(CHASSIS_JOINTS),
        }),
        "language_instruction": Text(),
        "object_dict": Dict({}),
    })


class FakeBimanualManipulationEnv:
    """A kinematic stand-in for ``BimanualManipulationEnv`` in its registered R1Base-v0 configuration."""

    def __init__(self, **options):
        # The driver configures obs_mode="state"; the fake records the option but models no cameras.
        self.obs_mode = str(options.get("obs_mode", "state"))  # placeholder
        self.action_space = Box([-math.inf] * ACTION_DIM, [math.inf] * ACTION_DIM)  # placeholder
        self.observation_space = _observation_space()
        self._closed = False
        self._reset_state()

    def _reset_state(self):
        self._left_arm = [0.0] * LEFT_ARM_JOINTS  # placeholder
        self._right_arm = [0.0] * RIGHT_ARM_JOINTS  # placeholder
        self._left_gripper = 0.0  # placeholder
        self._right_gripper = 0.0  # placeholder
        self._torso = [0.0] * TORSO_JOINTS  # placeholder
        self._left_arm_cmd = [0.0] * LEFT_ARM_JOINTS  # placeholder
        self._right_arm_cmd = [0.0] * RIGHT_ARM_JOINTS  # placeholder
        self._left_gripper_cmd = 0.0  # placeholder
        self._right_gripper_cmd = 0.0  # placeholder
        self.last_gripper_cmd = [0.0, 0.0]  # placeholder (BimanualManipulationEnv._init_buffers)

    def _observation(self):
        """The keys of ``_get_obs`` in state mode; all values are placeholder test data."""
        return {
            "upper_body_observations": {
                "left_arm_joint_position": list(self._left_arm),
                "right_arm_joint_position": list(self._right_arm),
                "left_arm_gripper_position": [self._left_gripper],
                "right_arm_gripper_position": [self._right_gripper],
                "left_arm_joint_velocity": [0.0] * LEFT_ARM_JOINTS,  # placeholder
                "right_arm_joint_velocity": [0.0] * RIGHT_ARM_JOINTS,  # placeholder
                "left_arm_ee_pose": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],  # placeholder
                "right_arm_ee_pose": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],  # placeholder
            },
            "upper_body_action_dict": {
                "left_arm_joint_position_cmd": list(self._left_arm_cmd),
                "right_arm_joint_position_cmd": list(self._right_arm_cmd),
                "left_arm_gripper_position_cmd": [self._left_gripper_cmd],
                "right_arm_gripper_position_cmd": [self._right_gripper_cmd],
            },
            "lower_body_observations": {
                "chassis_joint_position": [0.0] * CHASSIS_JOINTS,  # placeholder
                "torso_joint_position": list(self._torso),
            },
            "lower_body_action_dict": {
                "chassis_target_speed_cmd": [0.0] * CHASSIS_JOINTS,  # placeholder
            },
            "language_instruction": "",
            "object_dict": {},
        }

    def reset(self, *, seed=None, options=None):
        """Set the placeholder initial state; like upstream, ``seed`` and ``options`` are accepted and unused."""
        self._closed = False
        self._reset_state()
        return self._observation(), {}

    def step(self, action):
        """Copy the commanded targets into the state and return the fixed reward/terminal flags of the base env."""
        values = [float(value) for value in action]
        if len(values) != ACTION_DIM:
            raise ValueError("R1Base-v0 expects %d action values, got %d" % (ACTION_DIM, len(values)))
        left = values[:LEFT_ARM_JOINTS]
        left_gripper = values[LEFT_ARM_JOINTS]
        right_start = LEFT_ARM_JOINTS + 1
        right = values[right_start:right_start + RIGHT_ARM_JOINTS]
        right_gripper = values[-1]
        self._left_arm_cmd = list(left)
        self._right_arm_cmd = list(right)
        self._left_gripper_cmd = left_gripper
        self._right_gripper_cmd = right_gripper
        self._left_arm = list(left)
        self._right_arm = list(right)
        self._left_gripper = left_gripper
        self._right_gripper = right_gripper
        self.last_gripper_cmd = [left_gripper, right_gripper]
        return self._observation(), 0.0, False, False, {}

    def close(self):
        self._closed = True
