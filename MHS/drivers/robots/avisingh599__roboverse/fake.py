"""Fake backend of the roboverse driver: a pure Python stand-in for ``roboverse.envs.widow250:Widow250Env``.

Why a fake: the upstream package is a legacy Gym 0.12.1 / PyBullet environment (requirements.txt:1-2) and package code
never imports or runs the read-only clone.  The gate runs without gym, numpy or pybullet, so this module re-implements
the public surface of ``Widow250Env`` that the Gymnasium bridge uses (``action_space``, ``observation_space``,
``reset``, ``step``, ``close``) plus its observation, reward and info helpers.  The constants and rules below cite the
line of the clone at the pinned commit a443f79af67529158ba409889fd7b8006b1d3f88.

The model is deliberately kinematic (fidelity F0): the end-effector position changes by ``xyz_action_scale`` times the
action and is clipped to the upstream ``ee_pos`` bounds, the abc action accumulates a tracked Euler orientation, and
the gripper opens or closes.  There are no rigid-body dynamics, contacts, inverse kinematics, tray, table or camera.
The real observation image is 48x48x3 float32 values (6912, ``roboverse/envs/widow250.py:339-341``); the fake returns a
12-value stand-in (test data) to keep receipts small, and the driver's fidelity ``gaps`` and RESULT.json say so.

Every number below that is not read from the upstream source is test data and is marked ``# placeholder``.  Nothing
here talks to a device or to PyBullet.
"""

import math
import random

# roboverse/envs/widow250.py:27
ACTION_DIM = 8
# roboverse/envs/widow250.py:57-59 (constructor defaults)
XYZ_ACTION_SCALE = 0.2
ABC_ACTION_SCALE = 20.0
GRIPPER_ACTION_SCALE = 20.0
# roboverse/envs/widow250.py:61-62 (constructor defaults)
EE_POS_LOW = (0.4, -0.2, -0.34)
EE_POS_HIGH = (0.8, 0.4, -0.1)
# roboverse/envs/widow250.py:24-25
GRIPPER_OPEN_STATE = (0.036, -0.036)
GRIPPER_CLOSED_STATE = (0.015, -0.015)
# roboverse/envs/widow250.py:22-23 (GRIPPER_LIMITS_LOW/HIGH from JOINT_LIMIT_LOWER/UPPER)
GRIPPER_LIMITS_LOW = (0.015, -0.037)
GRIPPER_LIMITS_HIGH = (0.037, -0.015)
# roboverse/envs/widow250.py:41-42 (constructor defaults of the object position range)
OBJECT_POSITION_LOW = (0.5, 0.18, -0.30)
OBJECT_POSITION_HIGH = (0.7, 0.27, -0.30)
# roboverse/envs/widow250.py:50-52 (constructor defaults)
GRASP_HEIGHT_THRESHOLD = -0.25
GRASP_DISTANCE_THRESHOLD = 0.1
# roboverse/envs/widow250.py:337-347: the state is 10 values bounded by 100 (the image is reduced below)
STATE_DIM = 10
OBS_BOUND = 100.0
# The real image length is observation_img_dim ** 2 * 3 with observation_img_dim 48 (widow250.py:35, :339): 6912.
REAL_IMAGE_LENGTH = 48 * 48 * 3
# placeholder: a 12-value stand-in for the real 6912-value observation image, so receipts stay small
FAKE_IMAGE_LENGTH = 12
# placeholder: the upstream ee pose at reset comes from PyBullet forward kinematics of RESET_JOINT_VALUES
# (roboverse/envs/widow250.py:11-13); the fake starts from this fixed pose instead
START_EE_POS = (0.6, 0.0, -0.2)
START_EE_DEG = (0.0, 0.0, 0.0)
# roboverse/envs/widow250.py:38-40: the default object orientation is (0, 0, 1, 0)
OBJECT_ORIENTATION = (0, 0, 1, 0)


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype

    def contains(self, value):
        values = list(value)
        return len(values) == len(self.low) and all(
            self.low[index] <= values[index] <= self.high[index] for index in range(len(values)))


class Dict:
    """Duck-typed ``gym.spaces.Dict``: the bridge reads ``spaces`` as a mapping."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None
        self.dtype = None


def _clip(value, low, high):
    return max(low, min(high, value))


def _distance(left, right):
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def _deg_to_quat(deg):
    """PyBullet's ``getQuaternionFromEuler(deg_to_rad(deg))`` as [x, y, z, w] (roboverse/bullet/control.py:128-131)."""

    roll, pitch, yaw = (math.radians(value) for value in deg)
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return [sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
            cr * cp * cy + sr * sp * sy]


class FakeWidow250Env:
    """The Widow250Grasp-v0 environment without gym, numpy or PyBullet (gate G7 checks the public members)."""

    def __init__(self, control_mode="discrete_gripper", observation_mode="pixels", **options):
        if observation_mode != "pixels":
            raise NotImplementedError
        self.control_mode = control_mode
        self.observation_mode = observation_mode
        self.reward_type = options.get("reward_type", "grasping")
        self.use_neutral_action = bool(options.get("use_neutral_action", False))
        self.target_object = options.get("target_object", "beer_bottle")
        self.object_names = (self.target_object,)
        self.action_space = Box([-1.0] * ACTION_DIM, [1.0] * ACTION_DIM)
        self.observation_space = Dict({
            "image": Box([0.0] * FAKE_IMAGE_LENGTH, [1.0] * FAKE_IMAGE_LENGTH),
            "state": Box([-OBS_BOUND] * STATE_DIM, [OBS_BOUND] * STATE_DIM),
        })
        self._rng = random.Random()
        self._tick = 0
        self._attached = False
        self._attach_offset = [0.0, 0.0, 0.0]
        self.reset()

    def reset(self, seed=None, options=None):
        """Reset the kinematic scene and return the observation (legacy Gym returns the observation only)."""

        if seed is not None:
            self._rng = random.Random(int(seed))
        self.ee_pos = list(START_EE_POS)
        self.ee_deg = list(START_EE_DEG)
        self.gripper_state = list(GRIPPER_OPEN_STATE)
        self.is_gripper_open = True
        self._attached = False
        self.object_position = [self._rng.uniform(OBJECT_POSITION_LOW[index], OBJECT_POSITION_HIGH[index])
                                for index in range(3)]
        self.object_orientation = list(OBJECT_ORIENTATION)
        self._tick = 0
        return self.get_observation()

    def step(self, action):
        """Apply one action and return the legacy four-value (observation, reward, done, info) tuple."""

        values = [float(item) for item in action]
        if len(values) != ACTION_DIM:
            raise ValueError(f"expected {ACTION_DIM} action values, got {len(values)}")
        if any(math.isnan(value) for value in values):
            raise RuntimeError("Action has NaN entries")     # roboverse/envs/widow250.py:197-199
        values = [_clip(value, -1.0, 1.0) for value in values]  # roboverse/envs/widow250.py:201
        xyz_action = values[:3]
        abc_action = values[3:6]
        gripper_action = values[6]
        neutral_action = values[7]
        self.ee_pos = [_clip(self.ee_pos[index] + XYZ_ACTION_SCALE * xyz_action[index],
                             EE_POS_LOW[index], EE_POS_HIGH[index]) for index in range(3)]
        self.ee_deg = [self.ee_deg[index] + ABC_ACTION_SCALE * abc_action[index] for index in range(3)]
        self._apply_gripper(gripper_action)
        if self.use_neutral_action and neutral_action > 0.5:
            self.ee_pos = list(START_EE_POS)
            self.ee_deg = list(START_EE_DEG)
            self.gripper_state = list(GRIPPER_OPEN_STATE)
            self.is_gripper_open = True
            self._attached = False
        if self._attached:
            self.object_position = [self.ee_pos[index] + self._attach_offset[index] for index in range(3)]
        self._tick += 1
        info = self.get_info()
        reward = self.get_reward(info)
        done = False                                    # roboverse/envs/widow250.py:274
        return self.get_observation(), reward, done, info

    def get_observation(self):
        state = list(self.ee_pos) + _deg_to_quat(self.ee_deg) + list(self.gripper_state) \
            + [float(self.is_gripper_open)]
        return {
            "object_position": list(self.object_position),
            "object_orientation": list(self.object_orientation),
            "state": state,
            "image": self.render_obs(),
        }

    def get_reward(self, info):
        if self.reward_type == "grasping":
            return float(info["grasp_success_target"])   # roboverse/envs/widow250.py:299-304
        raise NotImplementedError

    def get_info(self):
        success = self._check_grasp()
        return {"grasp_success": success, "grasp_success_target": success}

    def render_obs(self):
        """The 12-value image stand-in (test data): the real image is 6912 float32 values in 1/255 units."""

        # placeholder: deterministic 12-value stand-in for the real 48x48x3 image
        return [(math.sin(self.ee_pos[0] * 10.0 + index) + 1.0) / 2.0 for index in range(FAKE_IMAGE_LENGTH)]

    def get_gripper_state(self):
        return list(self.gripper_state)

    def close(self):
        self._attached = False

    def _apply_gripper(self, gripper_action):
        if self.control_mode == "continuous":
            target = [self.gripper_state[0] - GRIPPER_ACTION_SCALE * gripper_action,
                      self.gripper_state[1] + GRIPPER_ACTION_SCALE * gripper_action]
            self.gripper_state = [_clip(target[0], GRIPPER_LIMITS_LOW[0], GRIPPER_LIMITS_HIGH[0]),
                                  _clip(target[1], GRIPPER_LIMITS_LOW[1], GRIPPER_LIMITS_HIGH[1])]
        elif self.control_mode == "discrete_gripper":
            if gripper_action > 0.5 and not self.is_gripper_open:
                self.gripper_state = list(GRIPPER_OPEN_STATE)
                self.is_gripper_open = True
                self._attached = False
            elif gripper_action < -0.5 and self.is_gripper_open:
                self.gripper_state = list(GRIPPER_CLOSED_STATE)
                self.is_gripper_open = False
                if _distance(self.ee_pos, self.object_position) < GRASP_DISTANCE_THRESHOLD:
                    self._attached = True
                    self._attach_offset = [self.object_position[index] - self.ee_pos[index] for index in range(3)]
        else:
            raise NotImplementedError

    def _check_grasp(self):
        # roboverse/bullet/object_utils.py:46-56: height above the threshold and distance below the threshold
        return (self.object_position[2] > GRASP_HEIGHT_THRESHOLD
                and _distance(self.ee_pos, self.object_position) < GRASP_DISTANCE_THRESHOLD)
