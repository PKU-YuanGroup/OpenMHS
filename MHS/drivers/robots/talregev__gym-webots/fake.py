"""Fake backend for the gym-webots pioneer3at camera environment.

The upstream class is a legacy ``gym.Env`` whose ``step`` and ``reset`` talk to
Webots through ROS services and topics; it is not importable or runnable in the
gate (it starts roscore and Webots with ``subprocess.Popen``, imports rospy,
cv2 and skimage, and its reward path slices lists with float indices under
Python 3).  This module is a pure-Python stand-in served through the SDK's
Gymnasium bridge.

What it models: the public environment interface only -- ``reset()`` and
``step(action)`` -- and the three discrete actions implemented by the upstream
``step`` (0 forward, 1 right, 2 left).  Observations have the upstream frame
shape, 1 x 1 x 32 x 32 grayscale pixels, but the pixel values and the motion,
collision and reward are synthetic placeholders, not Webots physics or a
camera rendering.  Every numeric literal below is test data; none is a device
fact or a safety limit.
"""

# Placeholder frame geometry: the upstream class sets img_rows=32,
# img_cols=32 and img_channels=1 (webots_circuit2c_pioneer_camera_nn.py:73-75)
# and reshapes the frame to (1, 1, rows, cols) at line 226.  The values below
# are test data copied only to keep the served observation the same size.
_IMG_ROWS = 32          # placeholder
_IMG_COLS = 32          # placeholder
_IMG_CHANNELS = 1       # placeholder
_PIXELS = _IMG_ROWS * _IMG_COLS   # placeholder
_IMAGE_SHAPE = (1, 1, _IMG_ROWS, _IMG_COLS)   # placeholder


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the bridge reads ``n``, ``start`` and ``shape``."""

    def __init__(self, n):
        self.n = int(n)
        self.start = 0                  # placeholder
        self.shape = ()                 # placeholder
        self.dtype = "int64"

    def __len__(self):
        """A container/value protocol: the SDK's recording proxy keeps space objects unwrapped."""
        return self.n


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "uint8"


class FakeWebotsPioneerEnv:
    """Stand-in for ``WebotsCircuit2cPionner3atCameraNnEnv`` without Webots, ROS or gym.

    ``reset`` and ``step`` are the two public members of the upstream class that
    this backend mirrors (gate G7); the two space attributes are instance data
    the bridge reads to derive the action bounds.
    """

    def __init__(self, **_options):
        # The upstream class defines no action_space or observation_space, so
        # there is no upstream line to cite for these bounds.  They are
        # placeholders derived from the three concrete actions of step()
        # (webots_circuit2c_pioneer_camera_nn.py:123-139) and from the camera
        # frame shape of lines 73-75 and 226.
        self.action_space = Discrete(3)                              # placeholder
        self.observation_space = Box(
            [0] * _PIXELS,                                          # placeholder
            [255] * _PIXELS,                                        # placeholder
            _IMAGE_SHAPE,
        )
        self.img_rows = _IMG_ROWS                                   # placeholder
        self.img_cols = _IMG_COLS                                   # placeholder
        self.img_channels = _IMG_CHANNELS                           # placeholder
        self._reset_state(0)                                        # placeholder seed

    def reset(self, seed=None, options=None):
        """Reset the stand-in and return the initial observation (legacy gym shape).

        ``seed=None`` keeps the seed of the previous reset, matching the bridge's
        rule that an omitted reset seed does not invent a new one.  ``options``
        is accepted and ignored; the upstream reset takes no options.
        """
        if seed is not None:
            self.seed = int(seed)
        self._reset_state(self.seed)
        return self._frame()

    def step(self, action):
        """Apply one of the three upstream actions and return the legacy 4-tuple."""
        code = int(action)
        if code not in (0, 1, 2):
            raise ValueError(f"unsupported pioneer action {action!r}; expected 0, 1 or 2")  # placeholder
        # Placeholder kinematics: forward advances along the corridor, a turn
        # changes the heading; neither is a Webots differential-drive model.
        if code == 0:                                               # placeholder
            self.distance -= 0.1                                    # placeholder
        elif code == 1:                                             # placeholder
            self.heading -= 0.2                                     # placeholder
            self.distance -= 0.03                                   # placeholder
        else:
            self.heading += 0.2                                     # placeholder
            self.distance -= 0.03                                   # placeholder
        self.tick += 1                                              # placeholder
        # The upstream keeps a 50-entry history of turn actions (line 71 and
        # lines 172-178); the same placeholder list drives the loop penalty.
        self.last50actions.pop(0)                                   # placeholder
        self.last50actions.append(0 if code == 0 else 1)            # placeholder
        action_sum = sum(self.last50actions)
        done = self.distance < 0.21                                 # placeholder collision test
        if not done:
            if code == 0:                                           # placeholder
                reward = 1.0 / (abs(self.heading) + 1.0)             # placeholder
            elif action_sum > 45:                                   # placeholder
                reward = -0.5                                       # placeholder
            else:
                reward = 0.5 / (abs(self.heading) + 1.0)            # placeholder
        else:
            reward = -1.0                                           # placeholder
        return self._frame(), reward, done, {}

    # -- private stand-in helpers ------------------------------------------------
    def _reset_state(self, seed):
        self.seed = int(seed)
        self.tick = 0                                               # placeholder
        self.heading = 0.0                                          # placeholder
        self.distance = 1.0                                         # placeholder
        self.last50actions = [0] * 50                               # placeholder
        self.done = False                                           # placeholder
        # A deterministic placeholder lane offset makes a different seed reset
        # to a different (but repeatable) frame.
        self.lane = (self.seed % 5) * 7                             # placeholder

    def _frame(self):
        """A deterministic 1 x 1 x 32 x 32 placeholder grayscale frame."""
        base = self.lane + self.tick * 11                           # placeholder
        frame = [[(base + row * 7 + col * 3) % 256                  # placeholder
                  for col in range(_IMG_COLS)]
                 for row in range(_IMG_ROWS)]
        return [[frame]]
