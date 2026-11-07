"""Fake backend of the RoboLab Gymnasium driver: a pure-Python kinematic stand-in for RobolabEnv.

Why a fake: the acceptance gate cannot import the upstream stack (Isaac Sim, Isaac Lab, a GPU and the
pinned assets are not available where the gate runs), and package code never imports the clone.  This
module models only the Gymnasium interface of ``robolab.core.environments.env:RobolabEnv`` that the
family bridge uses: ``action_space``, ``observation_space``, ``reset(seed, options)``, ``step(action)``
and ``close()``.  The public methods are the ones the gymnasium environment interface provides
(gate G7: they are part of the interface of the environment base class outside the clone).

What the deployed environment is, and what this is not:

* the deployed action is the DROID joint-position action: 7 arm joint targets plus a binary gripper,
  8 values (``robolab/robots/README.md:28``); the binary gripper closes when the action is greater
  than 0.5 and opens otherwise (``robolab/robots/droid.py:306-320``);
* the deployed observation groups are ``image_obs``, ``proprio_obs`` and ``viewport_cam``
  (``robolab/registrations/droid/auto_env_registrations_jointpos.py:83-86``); the proprioception
  terms are listed in ``robolab/robots/droid.py:433-442``;
* the deployed wrist camera is 720x1280 RGB (``robolab/robots/droid.py:48-50``) and the viewport
  camera is 480x864 RGB (``robolab/variations/camera.py:184-186``); this fake returns much smaller
  images to keep receipts small, and the real sizes are named in the driver's fidelity gaps and in
  RESULT.json.

Every numeric literal below is test data of the stand-in, marked ``placeholder``.  None of them is
copied into a Fact, a Limit or the reference: the fake does not claim to reproduce Isaac Lab physics.
The only sourced numbers are the upstream gripper threshold 0.5 (robolab/robots/droid.py:317) and the
observation bounds the clone states (the gripper open fraction is clipped to 0-1,
robolab/robots/droid.py:436); every other value is a placeholder.
"""

import math
import random

# placeholder: the action layout is 7 arm joint targets plus a binary gripper (robolab/robots/README.md:28)
ARM_JOINTS = 7
ACTION_VALUES = 8
# placeholder: the fake's start offset and first-order tracking gain, not the model's parameters
START_JOINT = 0.05
TRACKING_GAIN = 0.1
# placeholder: the fake's image stand-ins; the real cameras are 720x1280 and 480x864 RGB
WRIST_HEIGHT = 4
WRIST_WIDTH = 6
VIEW_HEIGHT = 2
VIEW_WIDTH = 3


class Box:
    """Duck-typed ``gymnasium.spaces.Box`` (the bridge reads ``low``, ``high``, ``shape`` and ``dtype``)."""

    def __init__(self, low, high, shape):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict`` (the bridge reads ``spaces``)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None
        self.dtype = None


def _image(tick, height, width, salt):
    """A deterministic placeholder RGB image; the values are test data, not camera output."""
    return [
        [
            # placeholder: the hash-like pixel formula and its multipliers
            [(tick * 3 + row * 17 + column * 29 + salt + channel) % 256 for channel in range(3)]
            for column in range(width)
        ]
        for row in range(height)
    ]


class FakeRobolabEnv:
    """A kinematic stand-in for RobolabEnv: ``reset`` and ``step`` return Gymnasium-shaped values."""

    def __init__(self, **_options):
        # placeholder: an action Box with no finite bounds; the fake does not reproduce joint limits
        self.action_space = Box(-math.inf, math.inf, (ACTION_VALUES,))
        self.observation_space = Dict({
            "image_obs": Dict({
                # placeholder: the 0-255 pixel range and the stand-in size; the real wrist camera is 720x1280
                "wrist_cam": Box(0.0, 255.0, (WRIST_HEIGHT, WRIST_WIDTH, 3)),
            }),
            "proprio_obs": Dict({
                "arm_joint_pos": Box(-math.inf, math.inf, (ARM_JOINTS,)),
                "gripper_pos": Box(0.0, 1.0, (1,)),  # sourced: clip=(0, 1) in droid.py:436
                "ee_pos": Box(-math.inf, math.inf, (3,)),
                "ee_quat": Box(-math.inf, math.inf, (4,)),  # placeholder: no bound is stated for quaternions
                "eef_pos": Box(-math.inf, math.inf, (3,)),
                "eef_quat": Box(-math.inf, math.inf, (4,)),  # placeholder: no bound is stated for quaternions
            }),
            "viewport_cam": Dict({
                # placeholder: the 0-255 pixel range and the stand-in size; the real viewport camera is 480x864
                "egocentric_mirrored_camera": Box(0.0, 255.0, (VIEW_HEIGHT, VIEW_WIDTH, 3)),
            }),
        })
        self._rng = random.Random()
        self._joints = [START_JOINT] * ARM_JOINTS
        self._gripper = 1.0
        self._tick = 0
        self._seed = None

    def reset(self, *, seed=None, options=None):
        """Reset the stand-in; ``seed`` fixes the placeholder start offsets of the arm joints."""
        if seed is not None:
            self._rng = random.Random(int(seed))
            self._seed = int(seed)
        # placeholder: the start offset range and the open-gripper value are stand-in test data
        self._joints = [START_JOINT + self._rng.uniform(-0.01, 0.01) for _ in range(ARM_JOINTS)]
        self._gripper = 1.0
        self._tick = 0
        return self._observation(), {}

    def step(self, action):
        """Advance one placeholder transition; the arm tracks the target and the gripper is binary."""
        values = self._values(action)
        for index in range(ARM_JOINTS):
            # placeholder: the first-order tracking gain is the stand-in's, not an actuator model
            self._joints[index] += TRACKING_GAIN * (values[index] - self._joints[index])
        # placeholder: 0.0 is the closed and 1.0 the open state; 0.5 is the upstream threshold (droid.py:317)
        self._gripper = 0.0 if values[ARM_JOINTS] > 0.5 else 1.0
        self._tick += 1
        return self._observation(), 0.0, False, False, {"tick": self._tick}

    def close(self):
        """Close the stand-in; it holds no external resource."""
        self._tick = 0

    @staticmethod
    def _values(action):
        """Accept the bridge's list of action values (or a ``{"values": [...]}`` object)."""
        if isinstance(action, dict):
            action = action.get("values", [])
        return [float(value) for value in action]

    def _observation(self):
        """The three observation groups of the built-in DROID registration, as Python lists."""
        arm = list(self._joints)
        ee_pos = [0.4 + 0.02 * sum(arm), -0.1 + 0.01 * arm[0], 0.5 + 0.01 * arm[1]]  # placeholder
        return {
            "image_obs": {
                "wrist_cam": _image(self._tick, WRIST_HEIGHT, WRIST_WIDTH, 5),  # placeholder image size
            },
            "proprio_obs": {
                "arm_joint_pos": arm,
                "gripper_pos": [self._gripper],
                "ee_pos": ee_pos,
                "ee_quat": [1.0, 0.0, 0.0, 0.0],  # placeholder identity orientation
                "eef_pos": list(ee_pos),
                "eef_quat": [1.0, 0.0, 0.0, 0.0],  # placeholder identity orientation
            },
            "viewport_cam": {
                # placeholder image size
                "egocentric_mirrored_camera": _image(self._tick, VIEW_HEIGHT, VIEW_WIDTH, 11),
            },
        }
