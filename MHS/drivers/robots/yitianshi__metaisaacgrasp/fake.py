"""Fake backend of the MetaIsaacGrasp driver: a pure Python kinematic stand-in for ``AIREnvData``.

Why a fake: ``AIREnvData`` is an Isaac Lab environment that needs Isaac Sim 4.5 and Isaac Lab 2.0 (README.md:1,
:55-57) and a GPU, none of which exist where the acceptance gate runs, and package code never imports the clone.
This module implements only the Gymnasium surface the bridge calls -- ``action_space``, ``observation_space``,
``reset``, ``step`` and ``close`` -- with the dimensions the clone configures.

What is taken from the clone:

* six arm joints (element_cfg.py:182-189) and one binary gripper action term (env_cfg.py:133-137), so the fake's
  action is seven values;
* the arm's default joint positions are the ARM_JOINT values computed from BOW_ANGLE, DOWN_RATION and WRIST_LIFT
  (element_cfg.py:46-50, :182-189);
* the gripper's open and close positions are 0.0425 and 0.0 (element_cfg.py:162-175);
* the world position of the camera (element_cfg.py:64) and the configured 480 x 640 camera resolution
  (element_cfg.py:63);
* the 30-step per-episode total (element_cfg.py:43);
* the 1/60 s environment step built from sim.dt 1/120 s and decimation 2 (env_cfg.py:287-292).

What is not the upstream environment (also listed in the driver's fidelity ``gaps``):

* the dynamics are kinematic: each of the six arm values moves a joint position by a small increment and nothing
  models contacts, friction, gravity, actuators, sensors or noise;
* the upstream ``AIREnvBase.step`` takes a grasp pose and a policy inference criteria tensor and loops
  (air_env_base/env.py:276); the fake is a single-transition Gymnasium step;
* the observation is reduced to two seven-value poses: the camera pose and the end-effector pose.  The policy
  group's rgb, normals, instance_segmentation_fast, distance_to_image_plane and pcd arrays are NOT COVERED; their
  configured size is 480 x 640 (element_cfg.py:63);
* the fake never terminates on a grasp; it truncates after 30 transitions, and the reward is a fixed 0.0.

Every number below that is not taken from the clone is test data and is marked ``# placeholder``; none is copied
into a Fact, a Limit or the reference.  Nothing here talks to a device.
"""

import math
import random

# element_cfg.py:46-50
BOW_ANGLE = 0.1
DOWN_RATION = 0.75
WRIST_LIFT = 0.5
# element_cfg.py:182-189: the six arm joints in their configured default positions.
ARM_JOINT_DEFAULT = (
    0.0,
    -math.pi * DOWN_RATION + BOW_ANGLE,
    math.pi * DOWN_RATION,
    -math.pi / 2 - BOW_ANGLE - WRIST_LIFT,
    -math.pi / 2,
    math.pi,
)
ARM_JOINT_COUNT = 6
# element_cfg.py:162-175: the hand-e gripper's open and closed finger positions.
GRIPPER_OPEN = 0.0425
GRIPPER_CLOSE = 0.0
# env_cfg.py:287-292: sim.dt = 1/120 s and decimation = 2, so one environment step is 1/60 s.
PHYSICS_DT_S = 1.0 / 120.0
DECIMATION = 2
STEP_DT_S = PHYSICS_DT_S * DECIMATION
# element_cfg.py:43: the per-episode step total of the data environment.
STEP_TOTAL = 30
# env_cfg.py:144-173: the observation groups are cam_pos and policy; the fake keeps the two pose vectors
# (camera pose and end-effector pose) and leaves the image terms out, as the module docstring and the fidelity gaps
# say.  The end-effector pose is represented here by the six arm joints plus the gripper opening.
CAMERA_POSE_SIZE = 7                                                        # placeholder: pose convention of the fake
ACTION_SIZE = ARM_JOINT_COUNT + 1                                           # six arm joints + one binary gripper
OBSERVATION_SIZE = CAMERA_POSE_SIZE + ARM_JOINT_COUNT + 1                   # two 7-value poses, test data

# element_cfg.py:64: VIEW_POS_W = (0.7, 0, 1.); the orientation is a placeholder because the clone's default camera
# orientation is composed by Isaac Lab at run time.
CAMERA_POSITION = (0.7, 0.0, 1.0)                                           # element_cfg.py:64
CAMERA_ORIENTATION = (1.0, 0.0, 0.0, 0.0)                                   # placeholder
# placeholder: the fake's start jitter, its kinematic gain and its fixed reward; test data only.
RESET_JITTER = 0.05                                                         # placeholder
ACTION_GAIN = 0.01                                                          # placeholder
STEP_REWARD = 0.0                                                           # placeholder

INF = float("inf")


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeAIREnvData:
    """One ``AIREnvData`` without Isaac Sim: the Gymnasium method surface and the configured dimensions."""

    def __init__(self, **_options):
        # The clone states no action bounds (the action manager builds the space), so the fake leaves it unbounded
        # instead of inventing a limit.  The observation is the fake's reduced two-pose vector.
        self.action_space = Box([-INF] * ACTION_SIZE, [INF] * ACTION_SIZE)
        self.observation_space = Box([-INF] * OBSERVATION_SIZE, [INF] * OBSERVATION_SIZE)
        self._rng = random.Random()
        self._arm = list(ARM_JOINT_DEFAULT)
        self._gripper = GRIPPER_OPEN
        self._camera_pose = list(CAMERA_POSITION) + list(CAMERA_ORIENTATION)
        self._steps = 0

    def reset(self, *, seed=None, options=None):
        """Reset one environment, echoing the Gymnasium reset contract."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._arm = [value + self._rng.uniform(-RESET_JITTER, RESET_JITTER)              # placeholder
                     for value in ARM_JOINT_DEFAULT]
        self._gripper = GRIPPER_OPEN
        self._camera_pose = list(CAMERA_POSITION) + list(CAMERA_ORIENTATION)
        self._steps = 0
        return self._observation(), {}

    def step(self, action):
        """Apply six joint-target increments and the binary gripper command, then advance one step."""
        values = list(action)
        if len(values) != ACTION_SIZE:
            raise ValueError(f"the action must hold {ACTION_SIZE} values, got {len(values)}")
        for index in range(ARM_JOINT_COUNT):
            self._arm[index] += ACTION_GAIN * float(values[index])                      # placeholder
        self._gripper = GRIPPER_OPEN if float(values[ARM_JOINT_COUNT]) >= 0.0 else GRIPPER_CLOSE
        self._steps += 1
        # The upstream step loops over its state machine until a policy criterion is met (air_env_base/env.py:276);
        # the fake is one transition and truncates at the 30-step episode total (element_cfg.py:43).
        truncated = self._steps >= STEP_TOTAL
        return self._observation(), STEP_REWARD, False, truncated, {}                    # reward placeholder

    def close(self):
        self._arm = []
        self._steps = 0

    def _observation(self):
        """The reduced observation: the camera pose followed by the six arm joints and the gripper opening."""
        observation = list(self._camera_pose) + list(self._arm) + [self._gripper]
        if len(observation) != OBSERVATION_SIZE:
            raise AssertionError(f"the fake observation has {len(observation)} values, expected {OBSERVATION_SIZE}")
        return observation
