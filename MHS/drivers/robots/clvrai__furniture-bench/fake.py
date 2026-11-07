"""Fake backend of the FurnitureSim driver: a pure Python kinematic stand-in for ``FurnitureSimEnv``.

Why a fake: the upstream package needs Isaac Gym, CUDA, a Linux GPU machine and ``gym==0.21.0`` on Python < 3.9
(README.md:28, setup.py:7-31), and package code never imports the clone.  This module mirrors the interface of
``furniture_bench.envs.furniture_sim_env:FurnitureSimEnv`` (the class the driver names as ``native``): the public
members are ``reset``, ``step`` and ``close`` (gate G7), and the space classes duck-type ``gym.spaces.Box`` and
``gym.spaces.Dict`` (the bridge reads ``low``, ``high``, ``shape`` and ``spaces``).

What this is not: the upstream environment.  The differences are listed in the fidelity ``gaps`` of the driver:

* there is no rigid-body dynamics, contact, friction, actuator, joint or sensor model: the end-effector position
  moves kinematically by the position part of the action, the orientation stays the identity and the reward is 0;
* the image observations are 2 x 2 x 3 placeholders; the configured real sizes are 224 x 224 (resized) or
  1280 x 720 (full resolution), and no camera, lighting or depth is modelled;
* one environment is modelled (``num_envs`` is not used), and observations have no batch dimension;
* the initial pose jitter is Python's ``random.Random(seed)``, not Isaac Gym's physics and random stream.

Every constant below cites the line of the clone at the pinned commit (a87960a2490a7a19c86ea16a5ef371718b2baa70)
unless it is marked ``# placeholder``: those numbers are test data, not facts.

Nothing here talks to a device.
"""

import random

# furniture_bench/envs/furniture_sim_env.py:653-654,660-666: the quat action is 7 pose values plus the gripper
ACTION_DIM = 8
# furniture_bench/envs/furniture_sim_env.py:70: max_env_steps default
MAX_ENV_STEPS = 3000
# furniture_bench/config.py:35-36: max_gripper_width of square_table
MAX_GRIPPER_WIDTH = 0.065
# furniture_bench/envs/furniture_sim_env.py:135: grasp_margin = 0.02 - 0.001
GRASP_MARGIN = 0.02 - 0.001
# placeholder: the real sizes are 224 x 224 (config.py:79) or 1280 x 720 (config.py:77); the fake stays small.
IMAGE_HEIGHT, IMAGE_WIDTH, IMAGE_CHANNELS = 2, 2, 3
# placeholder: a fixed kinematic start pose for square_table; upstream resets the Franka and the furniture poses.
START_POSITION = [0.5, 0.0, 0.2]
START_QUATERNION = [0.0, 0.0, 0.0, 1.0]
# placeholder: the tiny jitter that makes the seed observable without modelling the upstream randomization ranges.
START_JITTER = 0.01


class Box:
    """Duck-typed ``gym.spaces.Box``: flat bounds, a shape and a dtype."""

    def __init__(self, low, high, shape=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gym.spaces.Dict``: a mapping of observation names to their spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None
        self.dtype = None


def _robot_box(size):
    """A robot-state member: Box(-inf, inf) of ``size`` elements (furniture_sim_env.py:674,685-687)."""
    return Box([float("-inf")] * size, [float("inf")] * size, (size,))


def _image_box():
    """A colour image: Box(0, 255) with shape (*img_size, 3) (furniture_sim_env.py:677,688-689)."""
    count = IMAGE_HEIGHT * IMAGE_WIDTH * IMAGE_CHANNELS
    return Box([0] * count, [255] * count, (IMAGE_HEIGHT, IMAGE_WIDTH, IMAGE_CHANNELS))


class FakeFurnitureSimEnv:
    """FurnitureSimEnv without Isaac Gym: a kinematic ``reset(seed, options)`` and ``step(action)``."""

    def __init__(self, furniture="square_table", num_envs=1, headless=True, **kwargs):
        # placeholder: these constructor options are accepted so the driver's env_kwargs fit; only one environment
        # and the kinematic fake are modelled.
        self.furniture = furniture
        self.num_envs = num_envs
        self.headless = headless
        # furniture_sim_env.py:651-666: Box(-1, 1) with shape (num_envs, pose_dim + 1) for the quat representation
        self.action_space = Box([-1.0] * ACTION_DIM, [1.0] * ACTION_DIM, (1, ACTION_DIM))
        # furniture_sim_env.py:673-703 and observation.py:19-27: the default visual observation
        self.observation_space = Dict({
            "robot_state": Dict({
                "ee_pos": _robot_box(3),           # robot_state.py:18
                "ee_quat": _robot_box(4),          # robot_state.py:19
                "ee_pos_vel": _robot_box(3),       # robot_state.py:20
                "ee_ori_vel": _robot_box(3),       # robot_state.py:21
                "gripper_width": _robot_box(1),    # robot_state.py:25
            }),
            "color_image1": _image_box(),
            "color_image2": _image_box(),
        })
        self._rng = random.Random()
        self._seed = None
        self._tick = 0
        self._ee_pos = list(START_POSITION)
        self._ee_quat = list(START_QUATERNION)
        self._ee_pos_vel = [0.0, 0.0, 0.0]
        self._ee_ori_vel = [0.0, 0.0, 0.0]
        self._gripper_width = MAX_GRIPPER_WIDTH
        # furniture_sim_env.py:134: last_grasp starts at -1.0, which is the open gripper
        self._last_grasp = -1.0
        self._closed = False

    def reset(self, *, seed=None, options=None):
        """Reset the kinematic pose; ``seed`` repeats the placeholder jitter (upstream reset takes no seed)."""
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        jitter = [self._rng.uniform(-START_JITTER, START_JITTER) for _ in range(3)]  # placeholder
        self._tick = 0
        self._ee_pos = [value + delta for value, delta in zip(START_POSITION, jitter)]
        self._ee_quat = list(START_QUATERNION)
        self._ee_pos_vel = [0.0, 0.0, 0.0]
        self._ee_ori_vel = [0.0, 0.0, 0.0]
        self._gripper_width = MAX_GRIPPER_WIDTH
        self._last_grasp = -1.0
        return self._observation()

    def step(self, action):
        """Apply one clamped end-effector delta and return the upstream four-tuple."""
        values = _flat_action(action)
        # furniture_sim_env.py:720-723: clip the action to the action-space bounds
        values = [max(-1.0, min(1.0, value)) for value in values]
        # furniture_sim_env.py:750-753: the position part is a delta added to the end-effector position
        self._ee_pos = [position + delta for position, delta in zip(self._ee_pos, values[:3])]
        # furniture_sim_env.py:762-774: a negative gripper value opens, a positive one closes
        grasp = values[-1]
        if (grasp < 0) != (self._last_grasp < 0) and abs(grasp) > GRASP_MARGIN:
            self._last_grasp = grasp
        self._gripper_width = MAX_GRIPPER_WIDTH if self._last_grasp < 0 else 0.0
        # placeholder: no dynamics, so the reported velocity is the command that was just applied
        self._ee_pos_vel = list(values[:3])
        self._tick += 1
        # furniture_sim_env.py:1009-1016: done when the step count exceeds max_env_steps
        done = self._tick > MAX_ENV_STEPS
        # furniture_sim_env.py:822-827: (observation, reward, done, info); no assembly model, so the reward is 0
        return self._observation(), 0.0, done, {"obs_success": True, "action_success": True}

    def close(self):
        self._closed = True

    def _observation(self):
        """The default visual observation (observation.py:19-27) without the upstream batch dimension."""
        return {
            "robot_state": {
                "ee_pos": list(self._ee_pos),
                "ee_quat": list(self._ee_quat),
                "ee_pos_vel": list(self._ee_pos_vel),
                "ee_ori_vel": list(self._ee_ori_vel),
                "gripper_width": [self._gripper_width],
            },
            "color_image1": self._image(offset=0),
            "color_image2": self._image(offset=1),
        }

    def _image(self, offset):
        """A small deterministic placeholder image; the real camera images are not modelled."""
        # placeholder: the pixel values are test data, not camera data
        value = (self._tick * 7 + offset * 31 + (self._seed or 0)) % 256
        return [[[float((value + row + column + channel) % 256) for channel in range(IMAGE_CHANNELS)]
                 for column in range(IMAGE_WIDTH)] for row in range(IMAGE_HEIGHT)]


def _flat_action(action):
    """Accept the bridge's flat list (or a one-row nested list) and require the 8 quat values."""
    if isinstance(action, (list, tuple)) and len(action) == 1 and isinstance(action[0], (list, tuple)):
        action = action[0]
    if hasattr(action, "tolist"):
        action = action.tolist()
    if not isinstance(action, (list, tuple)):
        raise ValueError(f"the fake FurnitureSim action must be a list of {ACTION_DIM} numbers")
    values = [float(value) for value in action]
    if len(values) != ACTION_DIM:
        raise ValueError(f"the fake FurnitureSim action needs {ACTION_DIM} values for the quat representation, "
                         f"got {len(values)}")
    return values
