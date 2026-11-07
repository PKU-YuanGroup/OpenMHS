"""Fake backend of the simpler-env driver: a pure Python stand-in for the default state observation.

Why a fake: the upstream environment needs SAPIEN, gymnasium, the downloaded asset directory and a GPU-capable
renderer, and package code never imports the clone.  This module therefore re-implements the parts of
``GraspSingleCokeCanInScene-v0`` that the OpenMHS contract uses: ``reset(seed, options)``, ``step(action)``,
``close()``, the combined Google-robot action space and the default ``state`` observation layout of 47 numbers.
The public members are the ones the upstream class has (gate G7); the two space classes duck-type
``gymnasium.spaces.Box`` for the bridge, which reads ``low``, ``high``, ``shape`` and ``dtype``.

What this is not: the upstream simulator.  It has no rigid-body dynamics, contacts, gripper geometry, camera or
asset loading.  The observation values are placeholders and the motion is a toy kinematic model; the differences
are listed in the fidelity ``gaps`` of ``driver.py``.  Nothing here talks to a device.
"""

import math
import random

# Action space of the default static Google robot (driver.py facts; defaults.py:168-176, 291-307):
# the arm is a 6-vector delta end-effector pose and the gripper one normalized value.  These are source-derived
# bounds, not test data: -1.0..1.0 for position, -pi/2..pi/2 for rotation, -1..1 for the normalized gripper.
ARM_POS_LOW = -1.0
ARM_POS_HIGH = 1.0
ARM_ROT_BOUND = math.pi / 2.0
GRIPPER_LOW = -1.0
GRIPPER_HIGH = 1.0
ACTION_LOW = [ARM_POS_LOW, ARM_POS_LOW, ARM_POS_LOW,
              -ARM_ROT_BOUND, -ARM_ROT_BOUND, -ARM_ROT_BOUND, GRIPPER_LOW]
ACTION_HIGH = [ARM_POS_HIGH, ARM_POS_HIGH, ARM_POS_HIGH,
               ARM_ROT_BOUND, ARM_ROT_BOUND, ARM_ROT_BOUND, GRIPPER_HIGH]

# The default "state" observation of the static Google robot (driver.py facts; googlerobot.py:21-27,
# base_agent.py:173-178, base_env.py:344-347, grasp_single_in_scene.py:390-399):
# 11 qpos + 11 qvel + 1 gripper target_qpos + 7 base pose + 7 tcp pose + 7 object pose + 3 object-minus-tcp.
OBSERVATION_SIZE = 47

# "GraspSingleCokeCanInScene-v0" is registered with max_episode_steps=80 (grasp_single_in_scene.py:613-618);
# gym.make adds the TimeLimit wrapper (registration.py:108-114).  The fake applies the same truncation itself.
MAX_EPISODE_STEPS = 80

# Toy motion and grasp thresholds: test data only, not facts about the device.  # placeholder
STEP_XYZ = 0.02                                      # placeholder
GRASP_RADIUS = 0.06                                  # placeholder
GRASP_CLOSED = 0.5                                   # placeholder
LIFT_MARGIN = 0.02                                   # placeholder
TABLE_HEIGHT = 0.87                                  # placeholder
TCP_HEIGHT = 0.92                                    # placeholder
BASE_HEIGHT = 0.079                                  # placeholder
ROBOT_BASE_XY = [0.35, 0.10]                         # placeholder


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, dtype="float32"):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = dtype

    def contains(self, value):
        return len(value) == self.shape[0] and all(
            low <= float(item) <= high for item, low, high in zip(value, self.low, self.high)
        )


class FakeGraspSingleCokeCanEnv:
    """``GraspSingleCokeCanInScene-v0`` without SAPIEN: the contract is the same, the physics is a toy."""

    def __init__(self, **_options):
        self.action_space = Box(ACTION_LOW, ACTION_HIGH)
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE,
                                     [math.inf] * OBSERVATION_SIZE)
        self._rng = None
        self._seed = None
        self._elapsed_steps = 0
        self._reset = False
        self._obj_xyz = [0.0, 0.0, TABLE_HEIGHT]
        self._obj_quat = [0.0, 0.0, 0.0, 1.0]
        self._base_xyz = [ROBOT_BASE_XY[0], ROBOT_BASE_XY[1], BASE_HEIGHT]
        self._tcp_xyz = [ROBOT_BASE_XY[0], ROBOT_BASE_XY[1], TCP_HEIGHT]
        self._tcp_quat = [0.0, 0.0, 0.0, 1.0]
        self._gripper_target = 0.0
        self._success = False
        self._grasped = False

    # -- native surface ----------------------------------------------------
    def reset(self, seed=None, options=None):
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        elif self._rng is None:
            self._rng = random.Random(0)                         # placeholder default stream

        options = dict(options or {})
        obj_options = dict(options.get("obj_init_options") or {})
        robot_options = dict(options.get("robot_init_options") or {})

        obj_init_xy = obj_options.get("init_xy")
        if obj_init_xy is None:
            # upstream draws the object xy from [-0.35, -0.02] to [-0.12, 0.42] (grasp_single_in_scene.py:268-277)
            obj_init_xy = [self._rng.uniform(-0.35, -0.12),
                           self._rng.uniform(-0.02, 0.42)]      # placeholder draw, source range
        self._obj_xyz = [float(obj_init_xy[0]), float(obj_init_xy[1]), TABLE_HEIGHT]
        self._obj_quat = [0.0, 0.0, 0.0, 1.0]                   # placeholder

        robot_init_xy = robot_options.get("init_xy")
        if robot_init_xy is None:
            # upstream draws the static Google base x from 0.30 to 0.40 and y from 0.0 to 0.2
            # (base_env.py:309-311)
            robot_init_xy = [self._rng.uniform(0.30, 0.40),
                             self._rng.uniform(0.0, 0.2)]       # placeholder draw, source range
        self._base_xyz = [float(robot_init_xy[0]), float(robot_init_xy[1]), BASE_HEIGHT]
        self._tcp_xyz = [self._base_xyz[0], self._base_xyz[1], TCP_HEIGHT]
        self._tcp_quat = [0.0, 0.0, 0.0, 1.0]                   # placeholder
        self._gripper_target = 0.0                              # placeholder
        self._elapsed_steps = 0
        self._success = False
        self._grasped = False
        self._reset = True
        return self._observation(), {
            "model_id": "coke_can",
            "model_scale": 1.0,
            "orientation": "upright",                           # placeholder
        }

    def step(self, action):
        if not self._reset:
            raise AssertionError("Call reset before using step method.")
        values = self._action_values(action)
        if len(values) != len(ACTION_LOW):
            raise ValueError("the action must be 7 numbers")
        dx, dy, dz, _drx, _dry, _drz, gripper = values
        self._tcp_xyz = [self._tcp_xyz[0] + STEP_XYZ * dx,
                         self._tcp_xyz[1] + STEP_XYZ * dy,
                         self._tcp_xyz[2] + STEP_XYZ * dz]
        self._gripper_target = gripper
        distance = math.sqrt(sum((tcp - obj) ** 2
                                 for tcp, obj in zip(self._tcp_xyz, self._obj_xyz)))
        self._grasped = distance <= GRASP_RADIUS and gripper >= GRASP_CLOSED
        # the upstream task is successful once the object is grasped and lifted (grasp_single_in_scene.py:434-440)
        self._success = self._grasped and (self._tcp_xyz[2] - self._obj_xyz[2]) >= LIFT_MARGIN
        if self._success:
            self._obj_xyz = [self._tcp_xyz[0], self._tcp_xyz[1], self._tcp_xyz[2]]
        reward = 1.0 if self._success else 0.0
        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        info = {
            "elapsed_steps": self._elapsed_steps,
            "success": self._success,
            "is_grasped": self._grasped,
            "lifted_object": self._success,
        }
        return self._observation(), reward, self._success, truncated, info

    def close(self):
        self._reset = False

    # -- internal ----------------------------------------------------------
    @staticmethod
    def _action_values(action):
        if isinstance(action, dict):
            action = action.get("values", [])
        return [float(value) for value in action]

    def _observation(self):
        qpos = [0.0] * 11                                      # placeholder
        qpos[7] = qpos[8] = self._gripper_target
        qvel = [0.0] * 11                                      # placeholder
        controller = [self._gripper_target]
        tcp_to_obj = [obj - tcp for obj, tcp in zip(self._obj_xyz, self._tcp_xyz)]
        values = (qpos + qvel + controller
                  + self._base_xyz + self._tcp_quat
                  + self._tcp_xyz + self._tcp_quat
                  + self._obj_xyz + self._obj_quat
                  + tcp_to_obj)
        if len(values) != OBSERVATION_SIZE:
            raise AssertionError("the fake observation layout must stay at 47 numbers")
        return values
