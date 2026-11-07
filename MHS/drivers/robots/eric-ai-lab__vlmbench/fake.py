"""Fake backend of the VLMbench driver: a pure Python stand-in for ``amsolver.gym.vlmbench_env:VLMBenchEnv``.

Why a fake: the upstream wrapper launches CoppeliaSim 4.1.0 through PyRep (README.md:20), which is not available where
the gate runs, and package code never imports the clone.  This module implements the public surface of
``VLMBenchEnv`` (``reset``, ``step``, ``render``, ``close``; gate G7) with a kinematic joint model and the same action
and observation layout: seven arm joint values followed by one gripper value
(vlmbench_env.py:40-41, environment.py:41-47 and :188-207, task_environment.py:239-241).  The low-dimensional
observation is the prefix ``get_low_dim_data`` builds (observation.py:72-84): gripper_open, joint velocities, joint
positions, joint forces and gripper pose.  The omitted tail is named in the driver's fidelity ``gaps``.

Every constant below cites the clone at the pinned commit (479bd17b7d80645002af74f142a29dfe8b428876); the initial
joint positions, the gripper start and the joint-force value are test data and are marked ``# placeholder``.
Nothing here talks to a device.
"""

import math
import random

# amsolver/environment.py:41-47: the supported-robot table gives the panda 7 arm joints.
ARM_JOINTS = 7
# amsolver/environment.py:188-207: action_size is the arm action size plus one gripper value.
GRIPPER_VALUES = 1
ACTION_SIZE = ARM_JOINTS + GRIPPER_VALUES                    # 8
# amsolver/task_environment.py:27: the module constant _DT = 0.05 (seconds); the fake's step interval.
DT = 0.05
# amsolver/task_environment.py:251-254: above 0.5 opens, below 0.5 closes, exactly 0.5 keeps the state.
GRIPPER_THRESHOLD = 0.5
# amsolver/backend/scene.py:297-299: the reported gripper_open is 1.0 when the opening is above 0.9.
GRIPPER_OPEN_REPORT_THRESHOLD = 0.9
# amsolver/backend/observation.py:77-81: gripper_open (1) + joint velocities + positions + forces + gripper pose,
# with 7 values per joint array and a 7-value pose for the panda; the fake stops before the parts whose length the
# clone does not state (gripper joint positions, touch forces, task state).
STATE_SIZE = 1 + 4 * ARM_JOINTS                              # 29
# placeholder: the initial joint positions are drawn from this range by reset(seed).
INITIAL_JOINT_RANGE = 0.1


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high, shape=None):
        self.shape = tuple(shape) if shape is not None else (len(low),)
        count = 1
        for value in self.shape:
            count *= int(value)
        self.low = list(low) if isinstance(low, (list, tuple)) else [low] * count
        self.high = list(high) if isinstance(high, (list, tuple)) else [high] * count
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces`` (the member spaces)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None
        self.dtype = None


class FakeVLMBenchEnv:
    """A kinematic VLMBenchEnv: ``reset(seed=, options=)`` and ``step(action)`` return the Gymnasium shapes."""

    metadata = {"render.modes": ["human", "rgb_array"]}       # vlmbench_env.py:17

    def __init__(self, task_class=None, observation_mode="state", render_mode=None):
        if observation_mode not in ("state", "vision"):
            raise ValueError("Unrecognised observation_mode: %s." % observation_mode)   # vlmbench_env.py:29-31
        self._observation_mode = observation_mode             # vlmbench_env.py:21
        self._render_mode = render_mode                       # vlmbench_env.py:22
        # vlmbench_env.py:40-41: Box(low=-1.0, high=1.0, shape=(self.env.action_size,)).
        self.action_space = Box(-1.0, 1.0, shape=(ACTION_SIZE,))
        if observation_mode == "state":
            # vlmbench_env.py:43-45: Box(-inf, inf, shape=obs.get_low_dim_data().shape).
            self.observation_space = Box(-math.inf, math.inf, shape=(STATE_SIZE,))
        else:
            # vlmbench_env.py:46-59: the state plus four camera images.  The image data is a 1x1 placeholder; the
            # real default resolution is 128x128 (observation_config.py:14) and is named in the fidelity gaps.
            image = Box(0.0, 1.0, shape=(1, 1, 3))           # placeholder: 1x1 instead of 128x128
            self.observation_space = Dict({
                "state": Box(-math.inf, math.inf, shape=(STATE_SIZE,)),
                "left_shoulder_rgb": image,
                "right_shoulder_rgb": image,
                "wrist_rgb": image,
                "front_rgb": image,
            })
        self._task_class = task_class                         # vlmbench_env.py:19; the fake models no task
        self._rng = random.Random()
        self._started = False
        self._joint_velocities = [0.0] * ARM_JOINTS
        self._joint_positions = [0.0] * ARM_JOINTS
        self._joint_forces = [0.0] * ARM_JOINTS               # placeholder: the kinematic model has no forces
        self._gripper_pose = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        self._gripper_opening = 1.0

    # -- observation ---------------------------------------------------------
    def _observation(self):
        """``Observation.get_low_dim_data`` order (observation.py:72-84), truncated to the stated parts."""
        gripper_open = 1.0 if self._gripper_opening > GRIPPER_OPEN_REPORT_THRESHOLD else 0.0
        values = [gripper_open] + list(self._joint_velocities) + list(self._joint_positions) \
            + list(self._joint_forces) + list(self._gripper_pose)
        if self._observation_mode == "state":
            return values
        # vlmbench_env.py:71-81: the vision dict carries the state and four RGB arrays.
        image = [[[0.0, 0.0, 0.0]]]                           # placeholder: a black 1x1 RGB frame
        return {
            "state": values,
            "left_shoulder_rgb": image,
            "right_shoulder_rgb": image,
            "wrist_rgb": image,
            "front_rgb": image,
        }

    # -- gymnasium API -------------------------------------------------------
    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        # placeholder: the task's object placement is not modelled; only the robot joints start randomly.
        self._joint_positions = [self._rng.uniform(-INITIAL_JOINT_RANGE, INITIAL_JOINT_RANGE)
                                 for _ in range(ARM_JOINTS)]
        self._joint_velocities = [0.0] * ARM_JOINTS
        self._joint_forces = [0.0] * ARM_JOINTS
        self._gripper_pose = self._pose_from_joints()
        self._gripper_opening = 1.0                          # placeholder: the gripper starts open
        self._started = True
        return self._observation(), {}

    def step(self, action):
        if not self._started:
            raise RuntimeError("Call reset before using step method.")   # task_environment.py:235-237
        if len(action) != ACTION_SIZE:
            raise ValueError("Expected the action shape to be: (%d,), but was shape: (%d,)"
                             % (ACTION_SIZE, len(action)))               # task_environment.py:110-114
        arm_action = [float(value) for value in action[:-1]]             # task_environment.py:239-241
        gripper_action = float(action[-1])
        self._joint_velocities = arm_action
        self._joint_positions = [position + DT * velocity
                                 for position, velocity in zip(self._joint_positions, arm_action)]
        self._joint_forces = [0.0] * ARM_JOINTS                          # placeholder: no dynamics
        self._gripper_pose = self._pose_from_joints()
        if gripper_action > GRIPPER_THRESHOLD:                           # task_environment.py:251-254
            self._gripper_opening = 1.0
        elif gripper_action < GRIPPER_THRESHOLD:
            self._gripper_opening = 0.0
        # The task's success() is not modelled: the fake never terminates or truncates (task_environment.py:422-430;
        # the registration sets no max_episode_steps, amsolver/gym/__init__.py:13-26).
        return self._observation(), 0.0, False, False, {}

    def render(self, mode="human"):
        if mode != self._render_mode:                                   # vlmbench_env.py:83-91
            raise ValueError("The render mode must match the render mode selected in the constructor.")
        if mode == "rgb_array":
            return [[[0.0, 0.0, 0.0]]]                                   # placeholder
        return None

    def close(self):
        self._started = False

    def _pose_from_joints(self):
        """The fake's gripper pose: the first three joint positions and an identity quaternion (placeholder)."""
        return [self._joint_positions[0], self._joint_positions[1], self._joint_positions[2],
                0.0, 0.0, 0.0, 1.0]
