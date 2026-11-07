"""Fake backend of the Gymnasium driver: a pure Python stand-in for ``gym_soarm.env:SoArmAlohaEnv``.

The upstream environment needs gymnasium, numpy, dm-control and MuJoCo (pyproject.toml:21-26), and
``gym_soarm/tasks/sim.py`` additionally imports torch, lerobot and a ``.reward_wrapper`` module that is absent from
the clone (sim.py:1-16), so the upstream package cannot be imported or installed where the gate runs.  Package code
never imports the clone.  This module re-implements the observable Gymnasium interface of
``gym_soarm.env:SoArmAlohaEnv`` (the class the driver names as ``native``): the registered ``SoArm-v0`` configuration
of ``gym_soarm/__init__.py:25-34``, its spaces, its reset/step semantics and the 200-step ``TimeLimit`` that
``gymnasium.make("SoArm-v0")`` adds.

The public members of :class:`FakeSoArmAlohaEnv` are the ones ``SoArmAlohaEnv`` has (``reset``, ``step``,
``render``, ``close``; gate G7).  The two space classes duck-type ``gymnasium.spaces.Box`` and
``gymnasium.spaces.Dict`` (the bridge reads ``low``, ``high``, ``shape`` and ``spaces``).  Every constant below is
taken from the clone at the pinned commit and cites its line; the few values that are only test data are marked
``# placeholder``.

What this is not: the upstream MuJoCo simulation.  The differences, all listed in the fidelity ``gaps`` of the
driver, are: a kinematic joint model instead of MuJoCo contacts, forces and actuators; 2x2x3 camera frames instead of
the real 480x640x3 images; no object motion, so the cube stays where the reset placed it; and the cube placement uses
the reset seed, while the upstream ``PickPlaceTask`` samples it from the wall clock (sim.py:246-249).

Nothing here talks to a device.
"""

import math
import random

# gym_soarm/constants.py:8-18 (JOINTS and ACTIONS) and :21-28 (JOINT_LIMITS)
JOINTS = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]
JOINT_LIMITS = [
    (-1.91986, 1.91986),
    (-1.74533, 1.74533),
    (-1.69, 1.69),
    (-1.65806, 1.65806),
    (-2.74385, 2.84121),
    (-0.17453, 1.74533),
]

# gym_soarm/constants.py:31-38 (START_ARM_POSE)
START_ARM_POSE = [0.0, 0.0, -1.57, 0.0, 0.0, 0.0]
# gym_soarm/constants.py:4-5 (DT and FPS)
DT = 0.02
FPS = 50
# gym_soarm/constants.py:42-44 and :55-57: the gripper observation is normalized with these raw positions
GRIPPER_POSITION_OPEN = 1.74533
GRIPPER_POSITION_CLOSE = -0.17453

# gym_soarm/__init__.py:28: SoArm-v0 is registered with max_episode_steps=200
MAX_EPISODE_STEPS = 200
# gym_soarm/tasks/sim.py:251-276: a 3x3 grid around (0.0, 0.4) with +-0.10 m in x, +-0.075 m in y, z = 0.05 m
TABLE_CENTER = (0.0, 0.4)
GRID_DX = (-0.10, 0.0, 0.10)
GRID_DY = (-0.075, 0.0, 0.075)
CUBE_Z = 0.05
# gym_soarm/assets/scene.xml:33: the goal plate starts at (-0.2, 0.4, 0.05)
GOAL_POSITION = (-0.2, 0.4, 0.05)
# gym_soarm/tasks/sim.py:419: the cube is on the goal plate within 10 mm
GOAL_TOLERANCE = 0.01
# gym_soarm/tasks/sim.py:353-361: the reward cutoff and linear distance reward
MAX_DISTANCE = 1.0

# Test data, not facts: the fake render size and the per-tick joint motion.
IMAGE_HEIGHT = 2                                                      # placeholder
IMAGE_WIDTH = 2                                                       # placeholder
MAX_JOINT_DELTA = 0.25                                                # placeholder, radians per tick
IMAGE_BASES = {"front_camera": 32, "wrist_camera": 96, "front_close": 160,  # placeholder
               "overview_camera": 200, "diagonal_camera": 240}


def _normalize_gripper_position(value):
    """``gym_soarm/constants.py:55-57``: 0 is closed and 1 is open."""
    return (value - GRIPPER_POSITION_CLOSE) / (GRIPPER_POSITION_OPEN - GRIPPER_POSITION_CLOSE)


class Box:
    """Duck-typed one-dimensional or shaped ``gymnasium.spaces.Box``: flattened low/high and a shape."""

    def __init__(self, low, high, shape, dtype="float64"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces`` and maps it member by member."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _box(low, high, shape, dtype="float64"):
    count = 1
    for size in shape:
        count *= size
    return Box([low] * count, [high] * count, shape, dtype)


def _matmul(left, right):
    return [[sum(left[row][k] * right[k][column] for k in range(4)) for column in range(4)] for row in range(4)]


def _translation(x, y, z):
    return [[1.0, 0.0, 0.0, x], [0.0, 1.0, 0.0, y], [0.0, 0.0, 1.0, z], [0.0, 0.0, 0.0, 1.0]]


def _rotation_z(angle):
    cosine, sine = math.cos(angle), math.sin(angle)
    return [[cosine, -sine, 0.0, 0.0], [sine, cosine, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def _forward_kinematics(joint_angles):
    """The arm of ``gym_soarm/tasks/sim.py:28-107``: five joint angles to the end-effector position."""
    q1, q2, q3, q4, q5 = joint_angles[:5]
    base = _matmul(_rotation_z(math.pi / 2), _translation(0.0, 0.15, 0.0))
    t1 = _matmul(_translation(0.0388353, 0.0, 0.0624), _rotation_z(q1))
    t2 = _matmul(_translation(-0.0303992, -0.0182778, -0.0542), _rotation_z(q2))
    t3 = _matmul(_translation(-0.11257, -0.028, 0.0), _rotation_z(q3))
    t4 = _matmul(_translation(-0.1349, 0.0052, 0.0), _rotation_z(q4))
    t5 = _matmul(_translation(0.0, -0.0611, 0.0181), _rotation_z(q5))
    end_effector = _translation(-0.0079, -0.000218121, -0.0981274)
    total = base
    for matrix in (t1, t2, t3, t4, t5, end_effector):
        total = _matmul(total, matrix)
    return [total[row][3] for row in range(3)]


class FakeSoArmAlohaEnv:
    """The SoArm-v0 environment without MuJoCo: the same methods and spaces, a kinematic stand-in inside."""

    metadata = {"render_modes": ["rgb_array", "human"], "render_fps": 50}  # gym_soarm/env.py:20

    def __init__(
        self,
        task="pick_place",
        obs_type="pixels_agent_pos",
        render_mode="rgb_array",
        reward_mode="math",
        observation_width=640,
        observation_height=480,
        visualization_width=640,
        visualization_height=480,
        camera_config="front_wrist",
        render_camera="overview_camera",
    ):
        if task != "pick_place":
            raise NotImplementedError("the fake models the pick_place task only")
        valid_configs = ["front_only", "front_wrist", "diagonal_wrist", "all"]  # gym_soarm/env.py:47
        if camera_config not in valid_configs:
            raise ValueError(f"camera_config must be one of {valid_configs}, got {camera_config}")
        self.task = task
        self.obs_type = obs_type
        self.render_mode = render_mode
        self.reward_mode = reward_mode
        self.observation_width = observation_width
        self.observation_height = observation_height
        self.visualization_width = visualization_width
        self.visualization_height = visualization_height
        self.camera_config = camera_config
        self.render_camera = render_camera
        self._camera_names = self._get_camera_names(camera_config)
        self._rng = random.Random()
        self._qpos = list(START_ARM_POSE)
        self._qvel = [0.0] * len(JOINTS)
        self._tick = 0
        self._terminated = False
        self._truncated = False
        self._closed = False
        self._goal_position = list(GOAL_POSITION)
        self._cube_position = self._grid_position(0)

        # gym_soarm/env.py:60-110: the same three observation spaces and the 6-joint action Box.  The image
        # members are the fake's 2x2x3 stand-ins (the real size is 480x640x3, sim.py:188-192).
        cameras = {name: _box(0, 255, (IMAGE_HEIGHT, IMAGE_WIDTH, 3), "uint8") for name in self._camera_names}
        if self.obs_type == "state":
            self.observation_space = _box(-math.inf, math.inf, (len(JOINTS) * 2 + 7,), "float64")
        elif self.obs_type == "pixels":
            self.observation_space = Dict(cameras)
        elif self.obs_type == "pixels_agent_pos":
            self.observation_space = Dict({
                "pixels": Dict(cameras),
                "agent_pos": _box(-math.inf, math.inf, (len(JOINTS),), "float64"),
            })
        else:
            raise ValueError(f"unknown obs_type {obs_type!r}")
        self.action_space = Box(
            [low for low, _high in JOINT_LIMITS],
            [high for _low, high in JOINT_LIMITS],
            (len(JOINTS),),
            "float32",
        )

    def _get_camera_names(self, camera_config):
        """``gym_soarm/env.py:112-123``."""
        if camera_config == "front_only":
            return ["front_camera"]
        if camera_config == "front_wrist":
            return ["front_camera", "wrist_camera"]
        if camera_config == "diagonal_wrist":
            return ["diagonal_camera", "wrist_camera"]
        return ["overview_camera", "front_camera", "front_close", "wrist_camera"]

    def _grid_position(self, index):
        positions = [[TABLE_CENTER[0] + dx, TABLE_CENTER[1] + dy, CUBE_Z]
                     for dx in GRID_DX for dy in GRID_DY]
        return positions[index]

    def _random_cube(self):
        positions = [[TABLE_CENTER[0] + dx, TABLE_CENTER[1] + dy, CUBE_Z]
                     for dx in GRID_DX for dy in GRID_DY]
        return self._rng.choice(positions)

    def _agent_pos(self):
        """``gym_soarm/tasks/sim.py:144-151`` and ``gym_soarm/env.py:261-270``."""
        return self._qpos[:5] + [_normalize_gripper_position(self._qpos[5])]

    def _state_vector(self):
        """``gym_soarm/env.py:61-68``: qpos (6) + qvel (6) + end-effector position (3) + quaternion (4)."""
        return list(self._qpos) + list(self._qvel) + _forward_kinematics(self._qpos) + [1.0, 0.0, 0.0, 0.0]

    def _image(self, camera_name):
        """A 2x2x3 placeholder frame derived from the joints, not a scene render."""
        base = IMAGE_BASES.get(camera_name, 0)
        rows = []
        for row in range(IMAGE_HEIGHT):
            pixels = []
            for column in range(IMAGE_WIDTH):
                joint = self._qpos[(row * IMAGE_WIDTH + column) % len(self._qpos)]
                value = base + int((joint + 3.0) * 20.0) + self._tick      # placeholder pixel arithmetic
                pixels.append([max(0, min(255, value)),                      # 255 is the space high (env.py:73-78)
                               max(0, min(255, base + row * 10)),            # placeholder pixel arithmetic
                               max(0, min(255, base + column * 10))])        # placeholder pixel arithmetic
            rows.append(pixels)
        return rows

    def _observation(self):
        """``gym_soarm/env.py:243-271``."""
        if self.obs_type == "state":
            return self._state_vector()
        images = {name: self._image(name) for name in self._camera_names}
        if self.obs_type == "pixels":
            return images
        return {"pixels": images, "agent_pos": self._agent_pos()}

    def reset(self, seed=None, options=None):
        """``gym_soarm/env.py:273-309``: seed, then the optional cube_grid_position options."""
        if seed is not None:
            self._rng = random.Random(seed)
        self._qpos = list(START_ARM_POSE)
        self._qvel = [0.0] * len(JOINTS)
        self._tick = 0
        self._terminated = False
        self._truncated = False
        cube = None
        if options is not None and "cube_grid_position" in options:
            position = options["cube_grid_position"]
            if position is not None and position != -1 and (position < 0 or position > 8):
                raise ValueError("cube_grid_position must be between 0 and 8 (inclusive), -1 for custom "
                                 "coordinates, or None for random")
            if position == -1:
                if "cube_x" not in options or "cube_y" not in options:
                    raise ValueError("cube_x and cube_y must be provided when cube_grid_position is -1")
                cube = [float(options["cube_x"]), float(options["cube_y"]), CUBE_Z]
            elif position is None:
                cube = self._random_cube()
            else:
                cube = self._grid_position(int(position))
        else:
            cube = self._random_cube()
        self._cube_position = list(cube)
        info = {"is_success": False, "blue_cube_position": list(self._cube_position)}
        return self._observation(), info

    def step(self, action):
        """``gym_soarm/env.py:311-330``: clip, advance, then the goal-plate termination and the reward."""
        if self._closed:
            raise RuntimeError("the environment is closed")
        try:
            values = [float(value) for value in action]
        except (TypeError, ValueError) as exc:
            raise ValueError("action must be a sequence of six joint positions") from exc
        if len(values) != len(JOINTS):
            raise ValueError(f"action must have {len(JOINTS)} values, got {len(values)}")
        targets = [min(max(value, low), high) for value, (low, high) in zip(values, JOINT_LIMITS)]
        deltas = [min(max(target - current, -MAX_JOINT_DELTA), MAX_JOINT_DELTA)   # placeholder dynamics
                  for target, current in zip(targets, self._qpos)]
        self._qpos = [current + delta for current, delta in zip(self._qpos, deltas)]
        self._qvel = [delta / DT for delta in deltas]                            # placeholder velocity model
        self._tick += 1
        self._terminated = self._cube_on_goal_plate()
        self._truncated = self._tick >= MAX_EPISODE_STEPS
        reward = self._reward()
        info = {"is_success": self._terminated}
        return self._observation(), reward, self._terminated, self._truncated, info

    def _cube_on_goal_plate(self):
        """``gym_soarm/tasks/sim.py:401-419``."""
        distance = math.dist(self._cube_position, self._goal_position)
        return distance < GOAL_TOLERANCE

    def _reward(self):
        """``gym_soarm/tasks/sim.py:321-361`` with the same link offsets and distance formula."""
        end_effector = _forward_kinematics(self._qpos)
        distance = math.dist(end_effector, self._cube_position)
        if distance > MAX_DISTANCE:
            return 0.0
        return max(0.0, 1.0 - (distance / MAX_DISTANCE))

    def render(self):
        """``gym_soarm/env.py:125-133``: the small stand-in frame of the selected camera."""
        if self.render_mode in ("rgb_array", "human"):
            return self._image(self.render_camera)
        raise ValueError(f"Unsupported render mode: {self.render_mode}")

    def close(self):
        """``gym_soarm/env.py:332-365``: release the environment."""
        self._closed = True
