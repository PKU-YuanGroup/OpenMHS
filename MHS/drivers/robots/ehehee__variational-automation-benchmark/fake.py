"""Fake backend of the VAB driver: a pure Python stand-in for ``libero.vab.env:VABEnv``.

Why a fake: the acceptance gate cannot install robosuite, MuJoCo, numpy or the clone's YAML parser (no network, no
pip), and package code never imports the clone.  This module mirrors the interface of the class the driver names as
``native``: ``reset(init_index=None)`` returns the strict ``{"images", "proprio"}`` observation, ``step(action)``
returns ``(observation, reward, done, info)``, and ``delivery_progress()``, ``reward()``, ``language_instruction`` and
``action_dim`` are the members the driver reads (``libero/libero/vab/env.py:200-283``).

What this is not: the upstream environment.  There is no MuJoCo, no robosuite scene, no contact or controller
dynamics and no rendering.  The robot state is a placeholder first-order motion of a joint vector; the camera frames
are placeholder pixels.  The public members are the ones ``VABEnv`` has (gate G7).  All numbers below are fake test
data, not facts of the clone: each one is marked ``placeholder``.  Nothing here talks to a device.
"""

# placeholder: the real camera frames are 128 x 128 x 3 for the 62 task YAMLs (README.md:93-94)
FRAME_HEIGHT = 2
FRAME_WIDTH = 2
FRAME_CHANNELS = 3
# placeholder: the documented single-arm suites use 50 initial states (README.md:42)
N_INITS = 50
# placeholder: OSC_POSE control width; the clone exposes only robots[0].action_dim (env.py:282-283)
ACTION_DIM = 7
# placeholder: how far one fake step moves a joint per unit of command
STEP_GAIN = 0.01
# placeholder: the default camera names of the task schema (schema.py:39)
CAMERAS = ("agentview", "robot0_eye_in_hand")
# placeholder: the task language is read from YAML upstream; this fake has no YAML
LANGUAGE = "Pick the object and place it in the basket"
# placeholder: the sizes of the proprio arrays in the documented observation contract (README.md:57-61)
JOINT_POS_LEN = 7
EEF_POS_LEN = 3
EEF_QUAT_LEN = 4
GRIPPER_QPOS_LEN = 2


def _frame(phase):
    """A placeholder ``uint8[H,W,3]`` frame whose pixels depend on ``phase`` so a step is observable."""
    frame = []
    for row in range(FRAME_HEIGHT):
        line = []
        for column in range(FRAME_WIDTH):
            line.append([
                (phase + row + column) % 256,
                (2 * phase + row) % 256,
                (3 * phase + column) % 256,
            ])
        frame.append(line)
    return frame


class FakeVABEnv:
    """A stand-in for ``VABEnv``: the same reset, step and observation shape, with placeholder physics."""

    def __init__(self, task=None, **options):
        self.task = task
        self._init_index = 0
        self._tick = 0
        self._reward = 0.0
        self._success = False
        self._done = False
        self._joint_pos = [0.0] * JOINT_POS_LEN
        self._joint_vel = [0.0] * JOINT_POS_LEN
        self._eef_pos = [0.0] * EEF_POS_LEN
        self._eef_quat = [0.0, 0.0, 0.0, 1.0]
        self._gripper_qpos = [0.0, 0.0]
        self._images = {name: _frame(0) for name in CAMERAS}

    def _observation(self):
        return {
            "images": {name: [row[:] for row in frame] for name, frame in self._images.items()},
            "proprio": {
                "joint_pos": list(self._joint_pos),
                "joint_vel": list(self._joint_vel),
                "eef_pos": list(self._eef_pos),
                "eef_quat": list(self._eef_quat),
                "gripper_qpos": list(self._gripper_qpos),
            },
        }

    def reset(self, init_index=None):
        """``env.py:200-212``: select an initial state, clear the episode and return the filtered observation."""
        index = 0 if init_index is None else int(init_index)
        if index < 0 or index >= N_INITS:
            raise IndexError(f"init_index={index} out of range for {N_INITS} inits")
        self._init_index = index
        self._tick = 0
        self._reward = 0.0
        self._success = False
        self._done = False
        # placeholder: an initial-state-dependent offset so different indices are observable
        self._joint_pos = [((index + joint) % 10) * 0.001 for joint in range(JOINT_POS_LEN)]
        self._joint_vel = [0.0] * JOINT_POS_LEN
        self._images = {name: _frame(index) for name in CAMERAS}
        return self._observation()

    def step(self, action):
        """``env.py:214-228``: advance one control step and return the four-tuple the driver unpacks."""
        vector = list(action) if action is not None else []
        for joint in range(JOINT_POS_LEN):
            command = float(vector[joint]) if joint < len(vector) else 0.0
            self._joint_pos[joint] = self._joint_pos[joint] + STEP_GAIN * command
            self._joint_vel[joint] = STEP_GAIN * command
        self._tick += 1
        # placeholder: no success predicate is evaluated; success stays False and reward follows it
        self._success = False
        self._reward = 1.0 if self._success else 0.0
        self._done = False
        self._images = {name: _frame(self._tick + self._init_index) for name in CAMERAS}
        info = {"success": self._success, "language": LANGUAGE, "completion_rate": 0.0}
        return self._observation(), self._reward, self._done, info

    def delivery_progress(self):
        """``env.py:239-249``: ``None`` for a predicate that tracks no per-target progress (placeholder)."""
        return None

    def reward(self, action=None):
        """``env.py:252-253``: 1.0 on success and 0.0 otherwise, from the placeholder success flag."""
        return 1.0 if self._success else 0.0

    @property
    def language_instruction(self):
        """``env.py:277-279``: the task language; this fake has no YAML and returns a placeholder."""
        return LANGUAGE

    @property
    def action_dim(self):
        """``env.py:282-283``: the control width of the robot, a placeholder here."""
        return ACTION_DIM
