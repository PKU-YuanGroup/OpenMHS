"""ROS-free fake backend for the ALOHA ``RealEnv`` interface.

Every public method below exists on ``aloha_scripts.real_env:RealEnv`` in the
pinned clone: ``get_qpos``, ``get_qvel``, ``get_effort``, ``get_images``,
``get_observation``, ``get_reward``, ``reset``, ``step`` and
``set_gripper_pose``.  The fake imports no ROS, Interbotix SDK or upstream
code.  All numbers in this file are placeholder test data, not device facts.

The four camera images are 2 x 2 x 3 placeholders; the real usb_cam streams are
480 x 640 x 3 (launch/4arms_teleop.launch:93-94). This package does not
implement an artifact output path for those arrays; the images are NOT
COVERED. Immediate state updates do not model cached ROS feedback or native
command interleaving and cannot substantiate a stop or safe-state claim.
"""


class _TimeStep:
    """The small part of dm_env.TimeStep this fake needs."""

    def __init__(self, step_type, reward, observation):
        self.step_type = step_type
        self.reward = reward
        self.discount = None
        self.observation = observation


class FakeRealEnv:
    def __init__(self, **_options):
        self._left_arm = [0.0, -0.4, 0.8, 0.0, -0.2, 0.0]  # placeholder
        self._left_gripper = 0.5                              # placeholder
        self._right_arm = [0.0, -0.4, 0.8, 0.0, -0.2, 0.0]   # placeholder
        self._right_gripper = 0.5                             # placeholder
        self._qvel = [0.0] * 14                               # placeholder
        self._effort = [0.0] * 14                             # placeholder
        self._reward = 0                                      # placeholder
        self._cameras = {
            "cam_high": [[[0, 0, 0], [0, 0, 0]], [[0, 0, 0], [0, 0, 0]]],          # placeholder
            "cam_low": [[[0, 0, 0], [0, 0, 0]], [[0, 0, 0], [0, 0, 0]]],           # placeholder
            "cam_left_wrist": [[[0, 0, 0], [0, 0, 0]], [[0, 0, 0], [0, 0, 0]]],    # placeholder
            "cam_right_wrist": [[[0, 0, 0], [0, 0, 0]], [[0, 0, 0], [0, 0, 0]]],   # placeholder
        }
        # Negative-path switches for the package tests; they are not upstream
        # state and they do not add any public method.
        self.fail_step = False
        self.fail_get_qpos = False

    def get_qpos(self):
        if self.fail_get_qpos:
            raise RuntimeError("fake get_qpos failure")
        return list(self._left_arm) + [self._left_gripper] + list(self._right_arm) + [self._right_gripper]

    def get_qvel(self):
        return list(self._qvel)

    def get_effort(self):
        return list(self._effort)

    def get_images(self):
        return {name: [row[:] for row in image] for name, image in self._cameras.items()}

    def get_observation(self):
        return {
            "qpos": self.get_qpos(),
            "qvel": self.get_qvel(),
            "effort": self.get_effort(),
            "images": self.get_images(),
        }

    def get_reward(self):
        return self._reward

    def set_gripper_pose(self, left_gripper_desired_pos_normalized, right_gripper_desired_pos_normalized):
        self._left_gripper = float(left_gripper_desired_pos_normalized)
        self._right_gripper = float(right_gripper_desired_pos_normalized)

    def reset(self, fake=False):
        if not fake:
            self._left_arm = [0.0, -0.4, 0.8, 0.0, -0.2, 0.0]   # placeholder
            self._left_gripper = 0.5                              # placeholder
            self._right_arm = [0.0, -0.4, 0.8, 0.0, -0.2, 0.0]   # placeholder
            self._right_gripper = 0.5                             # placeholder
            self._qvel = [0.0] * 14                               # placeholder
            self._effort = [0.0] * 14                             # placeholder
        return _TimeStep("FIRST", self.get_reward(), self.get_observation())

    def step(self, action):
        if self.fail_step:
            raise RuntimeError("fake step failure")
        values = [float(value) for value in action]
        if len(values) != 14:
            raise ValueError("RealEnv.step takes the flat 14-value ALOHA action")
        self._left_arm = values[0:6]
        self._left_gripper = values[6]
        self._right_arm = values[7:13]
        self._right_gripper = values[13]
        self._qvel = [0.0] * 14  # placeholder
        return _TimeStep("MID", self.get_reward(), self.get_observation())
