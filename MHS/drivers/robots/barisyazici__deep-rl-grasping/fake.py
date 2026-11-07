"""Fake backend for the gripper-env-v0 driver: a pure Python stand-in for ``RobotEnv``.

The upstream environment needs gym 0.19.0, pybullet 3.2.5 and tensorflow 1.14.0 (``setup.py:6-24``) and a YAML
configuration; the gate neither installs nor imports the clone.  This module therefore implements only the public
surface of ``manipulation_main.gripperEnv.robot:RobotEnv`` that the Gymnasium bridge calls: ``reset``, ``step``,
``seed`` and ``close`` (the first three are inherited from ``World`` in the clone).  The two spaces are duck-typed
``gym.spaces.Box`` objects: the bridge reads ``low``, ``high`` and ``shape``.

The fake models the continuous, non-simplified, depth-observation variant of the environment: a five-element
normalized action (translation xyz, yaw, open/close) and a depth-plus-actuator observation.  The real observation
space is 64 x 64 x 2 (``tests_gripper/test_sim.py:39-40``); the fake returns a smaller 8 x 8 x 2 stand-in so a
receipt stays small (``RESULT.json`` notes and the fidelity ``gaps`` of ``driver.py`` name the real size).

What this is not: the upstream environment.  There is no pybullet rigid-body scene, no camera render, no TensorFlow
encoder and no upstream reward function; the pose is advanced kinematically and the reward is a constant.  Every
numeric constant below is either cited from the clone or marked ``# placeholder``; none of them is a Fact, a Limit
or a reference in ``driver.py``.
"""

import math
import random

# The camera config of the clone gives a 64 x 64 image (config/camera_info.yaml:1-2) and the upstream test expects
# the depth-plus-actuator space (64, 64, 2) (tests_gripper/test_sim.py:39-40).
REAL_HEIGHT, REAL_WIDTH, REAL_CHANNELS = 64, 64, 2  # placeholder: the real space is larger than this stand-in
HEIGHT, WIDTH = 8, 8  # placeholder: smaller stand-in, named in the fidelity gaps
# RobotEnv.__init__ sets _initial_height = 0.3 and reset_model starts the model at [0., 0., 0.3] (robot.py:59,131)
INITIAL_HEIGHT = 0.3
# The continuous test config has time_horizon 150 (tests_gripper/config/test_continous.yaml:67), but this is a
# constructor value, not a bound of the device: the fake uses it only as a stand-in episode length.
TIME_HORIZON = 150  # placeholder
# Kinematic scales of the stand-in; the upstream MinMaxScaler and max_translation/step_size config are not modelled.
TRANSLATION_STEP = 0.01  # placeholder
YAW_STEP = 0.15  # placeholder
INITIAL_OBJECT = 0.03  # placeholder: the scene objects are not modelled


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element and the declared shape."""

    def __init__(self, low, high, shape):
        self.shape = tuple(int(item) for item in shape)
        count = 1
        for item in self.shape:
            count *= item
        self.low = _expand(low, count)
        self.high = _expand(high, count)
        self.dtype = "float32"


def _expand(value, count):
    """Broadcast a scalar bound to ``count`` elements, as numpy's Box does; keep an explicit list."""
    if isinstance(value, (list, tuple)):
        return [float(item) for item in value]
    return [float(value)] * count


class FakeRobotEnv:
    """A kinematic stand-in for ``RobotEnv``: ``reset()``, ``step(action)``, ``seed(seed)`` and ``close()``."""

    def __init__(self, **options):
        # The bridge opens the fake with the driver's options (empty here); unknown options are not a device command.
        self.options = dict(options)
        self.action_space = Box(-1.0, 1.0, (5,))  # actuator.py:71-73
        self.observation_space = Box(0.0, 255.0, (REAL_HEIGHT, REAL_WIDTH, REAL_CHANNELS))  # robot.py:226-228
        self._rng = random.Random()
        self._tick = 0
        self._pose = [0.0, 0.0, INITIAL_HEIGHT]
        self._yaw = 0.0
        self._gripper_open = True
        self._object = [0.0, 0.0]
        self._last_observation = None
        self._closed = False

    def seed(self, seed=None, evaluate=False, validate=False):
        """``World.seed`` (simulation.py:91-100) adapted to Python's RNG: fix the stream used by the next reset."""
        # The upstream evaluate mode fixes the RNG to RandomState(1); reproduce the same choice, not its algorithm.
        self._rng = random.Random(1 if evaluate else seed)
        return self._rng

    def reset(self):
        """Start a new episode; ``RobotEnv.reset`` takes no arguments (robot.py:115)."""
        self._tick = 0
        self._pose = [0.0, 0.0, INITIAL_HEIGHT]  # robot.py:130-132
        self._yaw = 0.0
        self._gripper_open = True
        self._object = [self._rng.uniform(-INITIAL_OBJECT, INITIAL_OBJECT),
                        self._rng.uniform(-INITIAL_OBJECT, INITIAL_OBJECT)]  # placeholder
        self._last_observation = self._observe()
        return self._last_observation

    def step(self, action):
        """Apply one five-element action; return the legacy gym 4-tuple (robot.py:146-181)."""
        values = [float(item) for item in action]
        translation, yaw_rotation, open_close = values[:3], values[3], values[4]
        if open_close > 0.0 and not self._gripper_open:
            self._gripper_open = True
        elif open_close < 0.0 and self._gripper_open:
            self._gripper_open = False
        else:
            # The normalized translation is clipped to unit norm and then moved by a stand-in scale.
            norm = math.sqrt(sum(item * item for item in translation))
            if norm > 1.0:
                translation = [item / norm for item in translation]
            self._pose[0] += translation[0] * TRANSLATION_STEP  # placeholder
            self._pose[1] += translation[1] * TRANSLATION_STEP  # placeholder
            self._pose[2] += translation[2] * TRANSLATION_STEP  # placeholder
            self._yaw += yaw_rotation * YAW_STEP  # placeholder
        self._tick += 1
        done = self._tick >= TIME_HORIZON
        self._last_observation = self._observe()
        info = {"is_success": False, "episode_step": self._tick, "status": 3 if done else 0}
        return self._last_observation, 0.0, done, info  # reward is not modelled (fidelity gap)

    def close(self):
        """``World.close`` disconnects the physics client (simulation.py:88-89); the fake only marks itself closed."""
        self._closed = True

    def _observe(self):
        """A small depth-plus-actuator image; the depth channel moves with the kinematic pose."""
        actuator = 1.0 if self._gripper_open else 0.0
        rows = []
        for row in range(HEIGHT):
            line = []
            for column in range(WIDTH):
                depth = (128.0 + 100.0 * (row / HEIGHT - 0.5) + 100.0 * (column / WIDTH - 0.5)
                         + 50.0 * (self._pose[2] - INITIAL_HEIGHT) + 20.0 * self._pose[0]
                         + 10.0 * self._object[0])  # placeholder
                depth = max(0.0, min(255.0, depth))  # the declared space is Box(0, 255) (robot.py:226-228)
                # robot.py:199-205 stacks depth with a zero pad whose [0][0] carries the actuator state.
                line.append([depth, actuator if (row, column) == (0, 0) else 0.0])
            rows.append(line)
        return rows
