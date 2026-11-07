"""Fake backend of the CALVIN driver: a pure Python stand-in for ``calvin_env.envs.play_table_env:PlayTableSimEnv``.

Why a fake: the acceptance gate runs without pybullet, EGL, hydra or a CALVIN dataset, and package code never imports
the clone.  This module re-implements the public surface of the class named by ``native`` that the bridge uses:
``reset``, ``seed``, ``step``, ``get_obs``, ``get_state_obs``, ``get_camera_obs``, ``get_info`` and ``close``.  It is
a kinematic model, not the upstream simulator: the tcp pose integrates the relative cartesian action with the scales
of ``Robot.relative_to_absolute`` (calvin_env/robot/robot.py:228-237), the gripper opens or closes, and a small scene
state is carried through ``scene_obs``.  There are no contacts, no inverse kinematics, no motors and no sensors.

Every number below is test data, not a device fact: each one is marked ``# placeholder`` and none is used in a Fact, a
Limit or a reference.  The real camera sizes are named in the driver's fidelity ``gaps`` and in facts.md.

What this is not, all listed in the fidelity ``gaps`` of the driver:

* no pybullet: objects never move and contacts are empty;
* the rgb and depth arrays are 4x4 placeholders, while the configured cameras are larger;
* the scene has one door, one button, one switch, one light and three movable poses, not the configured scene;
* the fake draws with Python's ``random.Random``, upstream seeds numpy through ``gym.utils.seeding.np_random``;
* the fake was never compared with a pybullet run.
"""

import random

# Test data (placeholders), not facts: the real camera sizes are in conf/cameras/cameras/*.yaml.
IMAGE_WIDTH = 4                  # placeholder
IMAGE_HEIGHT = 4                 # placeholder
DEPTH_WIDTH = 4                  # placeholder
DEPTH_HEIGHT = 4                 # placeholder

# Test data (placeholders): a stand-in initial pose inside the table top.
INITIAL_TCP_POS = [0.3, 0.0, 0.4]                          # placeholder
INITIAL_TCP_ORN = [0.0, 0.0, 0.0]                          # placeholder
INITIAL_JOINTS = [0.0, -0.1, 0.0, -1.2, 0.0, 1.5, 0.7]     # placeholder
INITIAL_GRIPPER_WIDTH = 0.04                               # placeholder
GRIPPER_OPEN = 0.04                                        # placeholder
GRIPPER_CLOSED = 0.0                                       # placeholder
MAX_REL_POS = 0.02                                         # placeholder (upstream default)
MAX_REL_ORN = 0.05                                         # placeholder (upstream default)
MAGIC_SCALING_POS = 1.0                                    # placeholder
MAGIC_SCALING_ORN = 1.0                                    # placeholder

# Test data (placeholders): a small scene, not the configured CALVIN objects.
SCENE_SLOTS = 4                                            # placeholder: door, button, switch, light
MOVABLE_OBJECTS = 3                                        # placeholder
OBJECT_LOW = -0.10                                         # placeholder
OBJECT_HIGH = 0.10                                         # placeholder
OBJECT_Z = 0.42                                            # placeholder
OBJECT_ORN = 0.20                                          # placeholder
SCENE_OBS_LEN = SCENE_SLOTS + MOVABLE_OBJECTS * 6          # placeholder
ROBOT_OBS_LEN = 3 + 3 + 1 + 7 + 1                          # placeholder
BYTE_CENTRE = 127.0                                        # placeholder
BYTE_SCALE = 100.0                                         # placeholder
BYTE_MAX = 255                                             # placeholder
PIXEL_STEP = 0.01                                          # placeholder
DEPTH_STEP = 0.001                                         # placeholder


def _byte(value):
    """A deterministic 0..255 pixel byte from a pose value (test data, not a device fact)."""
    return max(0, min(BYTE_MAX, int(round(BYTE_CENTRE + value * BYTE_SCALE))))


def _gripper(value):
    """The gripper command as ``Robot.apply_action`` accepts it: a scalar or a one-element list, -1 or 1."""
    if not isinstance(value, int) and isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    if value not in (-1, 1):
        raise ValueError("gripper action must be -1 or 1")
    return int(value)


class FakePlayTableSimEnv:
    """A kinematic stand-in for ``PlayTableSimEnv`` (see the module docstring for what is not modelled)."""

    def __init__(self, robot_cfg=None, seed=0, use_vr=False, bullet_time_step=240.0, cameras=None,
                 show_gui=False, scene_cfg=None, use_scene_info=False, use_egl=False, control_freq=30, **options):
        # The defaults above are test data (placeholders), not facts about the device configuration.
        self.use_vr = use_vr                          # placeholder
        self.show_gui = show_gui                      # placeholder
        self.use_scene_info = use_scene_info          # placeholder
        self.use_egl = use_egl                        # placeholder
        self.control_freq = control_freq              # placeholder
        self.bullet_time_step = bullet_time_step      # placeholder
        self.action_repeat = int(bullet_time_step // control_freq)  # mirrors play_table_env.py:53
        self.cameras = list(cameras) if cameras else ["static", "gripper"]  # placeholder names
        self.cid = -1                                 # placeholder
        self.np_random = None
        self._closed = False
        self._episode = 0
        self._tick = 0
        self.seed(seed)
        self._reset_world(None, None)

    # -- upstream surface ------------------------------------------------------
    def seed(self, seed=None):
        """Set the generator used by the next reset and return ``[seed]`` (play_table_env.py:176-179)."""
        if seed is None:
            seed = random.SystemRandom().randrange(2 ** 31)  # placeholder bound
        self._seed = int(seed)
        self.np_random = random.Random(self._seed)
        return [self._seed]

    def reset(self, robot_obs=None, scene_obs=None):
        """Reset the robot and scene and return one observation (play_table_env.py:170-174)."""
        self._reset_world(robot_obs, scene_obs)
        self._tick = 0
        self._episode += 1
        return self.get_obs()

    def step(self, action):
        """Apply one action and return ``(obs, 0, False, info)`` (play_table_env.py:222-243)."""
        self._apply_action(action)
        for _ in range(self.action_repeat):  # mirrors the physics repeat of play_table_env.py:237-238
            pass
        self._tick += 1
        return self.get_obs(), 0.0, False, self.get_info()

    def close(self):
        self._closed = True

    def get_camera_obs(self):
        """Return the rgb and depth dicts ``get_camera_obs`` returns (play_table_env.py:181-189)."""
        rgb_obs = {}
        depth_obs = {}
        for index, name in enumerate(self.cameras):
            rgb_obs[f"rgb_{name}"] = self._render_rgb(index)
            depth_obs[f"depth_{name}"] = self._render_depth(index)
        return rgb_obs, depth_obs

    def get_obs(self):
        """Camera observations plus the robot and scene state (play_table_env.py:191-196)."""
        rgb_obs, depth_obs = self.get_camera_obs()
        obs = {"rgb_obs": rgb_obs, "depth_obs": depth_obs}
        obs.update(self.get_state_obs())
        return obs

    def get_state_obs(self):
        """Return ``robot_obs`` and ``scene_obs`` (play_table_env.py:198-213)."""
        return {"robot_obs": self._robot_obs(), "scene_obs": self._scene_obs()}

    def get_info(self):
        """Return ``robot_info`` and, when enabled, ``scene_info`` (play_table_env.py:215-220)."""
        info = {"robot_info": {
            "tcp_pos": list(self._tcp_pos),
            "tcp_orn": list(self._tcp_orn),
            "gripper_opening_width": self._gripper_width,
            "arm_joint_states": list(self._joints),
            "gripper_action": self._gripper_action,
            "uid": "fake-play-table-robot",  # placeholder
            "contacts": [],
        }}
        if self.use_scene_info:
            info["scene_info"] = {"movable_objects": [list(pose) for pose in self._objects]}
        return info

    # -- model (test data only) ------------------------------------------------
    def _reset_world(self, robot_obs, scene_obs):
        if robot_obs is None:
            self._tcp_pos = list(INITIAL_TCP_POS)
            self._tcp_orn = list(INITIAL_TCP_ORN)
            self._joints = list(INITIAL_JOINTS)
            self._gripper_width = INITIAL_GRIPPER_WIDTH
            self._gripper_action = 1
        else:
            values = [float(value) for value in robot_obs]
            if len(values) != ROBOT_OBS_LEN:
                raise ValueError(f"robot_obs has {len(values)} values, expected {ROBOT_OBS_LEN}")
            self._tcp_pos = values[:3]
            self._tcp_orn = values[3:6]
            self._gripper_width = values[6]
            self._joints = values[7:14]
            self._gripper_action = int(values[14])
        if scene_obs is None:
            self._scene_slots = [0.0, 0.0, 0.0, 0.0]  # placeholder: door, button, switch, light
            self._objects = []
            for _ in range(MOVABLE_OBJECTS):
                self._objects.append([
                    self.np_random.uniform(OBJECT_LOW, OBJECT_HIGH),
                    self.np_random.uniform(OBJECT_LOW, OBJECT_HIGH),
                    OBJECT_Z,
                    self.np_random.uniform(-OBJECT_ORN, OBJECT_ORN),
                    self.np_random.uniform(-OBJECT_ORN, OBJECT_ORN),
                    self.np_random.uniform(-OBJECT_ORN, OBJECT_ORN),
                ])
        else:
            values = [float(value) for value in scene_obs]
            if len(values) != SCENE_OBS_LEN:
                raise ValueError(f"scene_obs has {len(values)} values, expected {SCENE_OBS_LEN}")
            self._scene_slots = values[:SCENE_SLOTS]
            self._objects = [values[SCENE_SLOTS + index * 6:SCENE_SLOTS + (index + 1) * 6]
                             for index in range(MOVABLE_OBJECTS)]

    def _robot_obs(self):
        return [*self._tcp_pos, *self._tcp_orn, self._gripper_width, *self._joints, self._gripper_action]

    def _scene_obs(self):
        values = list(self._scene_slots)
        for pose in self._objects:
            values.extend(pose)
        return values

    def _apply_action(self, action):
        if isinstance(action, dict):
            kind = action.get("type")
            values = action.get("action")
            if kind == "joint_rel":
                if values is None or len(values) != 8:
                    raise ValueError("joint_rel needs 8 values")
                self._joints = [joint + float(delta) for joint, delta in zip(self._joints, values[:7])]
                self._gripper_action = _gripper(values[-1])
            elif kind == "joint_abs":
                if values is None or len(values) != 8:
                    raise ValueError("joint_abs needs 8 values")
                self._joints = [float(value) for value in values[:7]]
                self._gripper_action = _gripper(values[-1])
            elif kind == "cartesian_rel":
                if values is None or len(values) != 7:
                    raise ValueError("cartesian_rel needs 7 values")
                self._relative_to_absolute(values)
                self._gripper_action = _gripper(values[-1])
            elif kind == "cartesian_abs":
                if values is None or len(values) not in (3, 7, 8):
                    raise ValueError("cartesian_abs needs 3, 7 or 8 values")
                if len(values) == 3:
                    target_pos, target_orn, gripper = values
                else:
                    target_pos = values[:3]
                    target_orn = values[3:6] if len(values) == 7 else values[3:7]
                    gripper = values[-1]
                self._tcp_pos = [float(value) for value in target_pos]
                self._tcp_orn = [float(value) for value in target_orn]
                self._gripper_action = _gripper(gripper)
            else:
                raise ValueError(f"unknown action type {kind!r}")
        else:
            values = list(action)
            if len(values) == 7:
                self._relative_to_absolute(values)
                gripper = values[-1]
            elif len(values) == 3:
                target_pos, target_orn, gripper = values
                self._tcp_pos = [float(value) for value in target_pos]
                self._tcp_orn = [float(value) for value in target_orn]
            else:
                raise ValueError("an action needs a dict type or 7 relative values")
            self._gripper_action = _gripper(gripper)
        self._gripper_width = GRIPPER_OPEN if self._gripper_action == 1 else GRIPPER_CLOSED

    def _relative_to_absolute(self, values):
        """The relative scale of ``Robot.relative_to_absolute`` (calvin_env/robot/robot.py:228-237)."""
        for axis in range(3):
            self._tcp_pos[axis] += float(values[axis]) * MAX_REL_POS * MAGIC_SCALING_POS
        for axis in range(3):
            self._tcp_orn[axis] += float(values[3 + axis]) * MAX_REL_ORN * MAGIC_SCALING_ORN

    def _render_rgb(self, index):
        offset = 0.0 if index == 0 else 0.5  # placeholder: the two cameras see different colours
        image = []
        for y in range(IMAGE_HEIGHT):
            row = []
            for x in range(IMAGE_WIDTH):
                row.append([
                    _byte(self._tcp_pos[0] + offset + x * PIXEL_STEP),
                    _byte(self._tcp_pos[1] + y * PIXEL_STEP),
                    _byte(self._tcp_pos[2] + offset),
                ])
            image.append(row)
        return image

    def _render_depth(self, index):
        offset = 0.0 if index == 0 else 0.01  # placeholder
        return [[round(self._tcp_pos[2] + offset + (x + y) * DEPTH_STEP, 4)
                 for x in range(DEPTH_WIDTH)] for y in range(DEPTH_HEIGHT)]
