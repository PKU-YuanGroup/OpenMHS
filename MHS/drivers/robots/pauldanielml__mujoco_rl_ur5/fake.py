"""Fake backend of the UR5 grasper driver: a pure Python stand-in for ``gym_grasper.envs:GraspEnv``.

The acceptance gate never imports or runs the upstream clone, and the upstream environment needs mujoco-py, MuJoCo
2.1 binaries, OpenCV, gym and a C compiler.  This module therefore reproduces the parts of ``GraspEnv`` that the
``cap.world.*`` contract exposes: the registered ``Grasper-v0`` action space (a pixel index and one of six wrist
rotations), a dictionary observation with an ``rgb`` and a ``depth`` array, and the binary reward of
``GraspingEnv.py:130-142``.  The action space is the real one: 200 x 200 pixel choices by 6 rotations
(``GraspingEnv.py:31-32``, ``:40``, ``:163-165``).  The observation arrays this fake returns are smaller stand-ins
(8 x 8) than the 200 x 200 x 3 and 200 x 200 arrays of the upstream camera (``GraspingEnv.py:31-32``); the
observation space advertises the real shapes, and the fidelity ``gaps`` of ``driver.py`` name the difference.

What this is not:

* it does not run MuJoCo: there are no rigid bodies, contacts, friction, actuators, sensors, objects or camera; the
  reward is a stand-in that says "this pixel is occupied by an object" and ignores every controller result;
* the observation is not an image of the scene: the arrays are generated from a small occupancy grid;
* the reset does not randomize 40 object joints (``GraspingEnv.py:420-430``), move the arm (``:418``) or run 1000
  controller steps (``:473``);
* no seed gives the same trajectory as the upstream environment, which draws object poses with numpy's global
  generator and ``Quaternion.random`` (``GraspingEnv.py:426-430``).

Public members are the ones the upstream class has (``reset``, ``step``, ``close``; gate G7).  The helper spaces
duck-type the legacy gym spaces the upstream code uses (``spaces.MultiDiscrete`` at ``GraspingEnv.py:163-165`` and
the dictionary observation documented at README.md:69); the bridge reads ``nvec``, ``shape``, ``low``, ``high`` and
``spaces``.  Numbers marked ``# placeholder`` are test data, not facts.
"""

import random

# GraspingEnv.py:31-32: the constructor defaults of image_width and image_height.
DEFAULT_IMAGE_WIDTH = 200
DEFAULT_IMAGE_HEIGHT = 200
# GraspingEnv.py:40: the wrist rotation action is an index into this table (degrees).
ROTATIONS = {0: 0, 1: 30, 2: 60, 3: 90, 4: -30, 5: -60}
# placeholder: the fake observation is 8 x 8, not the real 200 x 200; see the module docstring.
STANDIN_WIDTH = 8
STANDIN_HEIGHT = 8
# placeholder: the stand-in object density of the occupancy grid.
OCCUPANCY = 0.3
# placeholder: the stand-in colours of an empty and an occupied pixel.
EMPTY_RGB = (30, 30, 30)
OBJECT_RGB = (190, 120, 60)
# GraspingEnv.py:124: the upstream code skips a pixel when its projected world z is below this value; the stand-in
# uses the same number as the depth threshold of its occupied/unoccupied pixels.
MIN_GRASP_DEPTH = 0.8


class MultiDiscrete:
    """Duck-typed ``gym.spaces.MultiDiscrete``: the bridge reads ``nvec`` (``GraspingEnv.py:163-165``)."""

    def __init__(self, nvec):
        self.nvec = [int(value) for value in nvec]
        self.shape = (len(self.nvec),)
        self.dtype = "int64"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.nvec):
            return False
        return all(isinstance(item, int) and not isinstance(item, bool) and 0 <= item < size
                   for item, size in zip(value, self.nvec))


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high, shape):
        count = 1
        for size in shape:
            count *= int(size)
        self.low = [float(low)] * count
        self.high = [float(high)] * count
        self.shape = tuple(int(size) for size in shape)
        self.dtype = "float64"


class Dict:
    """Duck-typed ``gym.spaces.Dict``: the bridge reads ``spaces`` (the observation dictionary of README.md:69)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeGraspEnv:
    """A small stand-in for ``GraspEnv``: ``reset(seed, options)`` and ``step(action)`` as the bridge calls them."""

    def __init__(
        self,
        file="/UR5+gripper/UR5gripper_2_finger_many_objects.xml",
        image_width=DEFAULT_IMAGE_WIDTH,
        image_height=DEFAULT_IMAGE_HEIGHT,
        show_obs=True,
        demo=False,
        render=False,
    ):
        # GraspingEnv.py:28-36: the constructor parameters of the upstream class.
        self.file = file
        self.IMAGE_WIDTH = int(image_width)
        self.IMAGE_HEIGHT = int(image_height)
        self.show_observations = show_obs
        self.demo_mode = demo
        self.render = render
        self.rotations = dict(ROTATIONS)                                # GraspingEnv.py:40
        self.action_space_type = "multidiscrete"                        # GraspingEnv.py:41
        self.step_called = 0                                            # GraspingEnv.py:42
        self.TABLE_HEIGHT = 0.91                                        # GraspingEnv.py:56
        self.initialized = True
        self.grasp_counter = 0
        self._set_action_space()
        # The upstream observation is a dictionary of the camera's RGB and depth arrays (GraspingEnv.py:402-404).
        # The real default resolution is IMAGE_WIDTH x IMAGE_HEIGHT; this fake returns the smaller stand-in arrays.
        self.observation_space = Dict({
            "rgb": Box(0.0, 255.0, (self.IMAGE_WIDTH, self.IMAGE_HEIGHT, 3)),
            "depth": Box(0.0, 10.0, (self.IMAGE_WIDTH, self.IMAGE_HEIGHT)),
        })
        self.current_observation = None
        self._rng = random.Random(0)                                    # placeholder: fixed initial generator
        self._closed = False

    def _set_action_space(self):
        """The upstream space: ``MultiDiscrete([IMAGE_HEIGHT * IMAGE_WIDTH, len(rotations)])`` (line 163-165)."""
        self.action_space = MultiDiscrete(
            [self.IMAGE_HEIGHT * self.IMAGE_WIDTH, len(self.rotations)]
        )
        return self.action_space

    def _make_observation(self):
        """Build the stand-in RGB and depth arrays from a seeded occupancy grid (the ``# placeholder`` numbers)."""
        objects = [[1 if self._rng.random() < OCCUPANCY else 0 for _ in range(STANDIN_WIDTH)]
                   for _ in range(STANDIN_HEIGHT)]
        # placeholder: always leave one object so a successful grasp can be exercised.
        objects[STANDIN_HEIGHT // 2][STANDIN_WIDTH // 2] = 1
        rgb = [[list(OBJECT_RGB if objects[row][col] else EMPTY_RGB) for col in range(STANDIN_WIDTH)]
               for row in range(STANDIN_HEIGHT)]
        depth = [[1.0 if objects[row][col] else 0.0 for col in range(STANDIN_WIDTH)]
                 for row in range(STANDIN_HEIGHT)]
        return {"rgb": rgb, "depth": depth}

    def reset(self, seed=None, options=None):
        """Reset the occupancy grid; ``seed`` fixes it, and the upstream reset reads no options."""
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
                raise ValueError("seed must be a non-negative integer")
            self._rng = random.Random(seed)
        # The upstream reset_model reads no options (GraspingEnv.py:409-477); accepted for the Gymnasium bridge.
        self.step_called = 0                                            # GraspingEnv.py:42
        self.current_observation = self._make_observation()
        self._closed = False
        return self.current_observation

    def step(self, action, record_grasps=False, markers=False, action_info="no info"):
        """Decode the pixel action, return the observation, a binary reward, ``done=False`` and ``{}``."""
        if self.current_observation is None:
            raise AssertionError("Call reset before using step method.")
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} ({type(action)}) invalid")
        pixel, rotation = int(action[0]), int(action[1])
        # GraspingEnv.py:94-97: x = action[0] % IMAGE_WIDTH, y = action[0] // IMAGE_WIDTH, rotation = action[1].
        x = pixel % self.IMAGE_WIDTH
        y = pixel // self.IMAGE_WIDTH
        row = min(STANDIN_HEIGHT - 1, y * STANDIN_HEIGHT // self.IMAGE_HEIGHT)
        col = min(STANDIN_WIDTH - 1, x * STANDIN_WIDTH // self.IMAGE_WIDTH)
        depth = self.current_observation["depth"][row][col]
        # GraspingEnv.py:124-131: a pixel below the grasp depth gets reward 0 and is not executed.
        reward = 0 if depth < MIN_GRASP_DEPTH else 1
        # GraspingEnv.py:152-156: refresh the observation, count the step, return done=False and empty info.
        self.step_called += 1
        return self.current_observation, reward, False, {}

    def close(self):
        """Drop the observation; the upstream close also closes the MuJoCo environment and its windows."""
        self.current_observation = None
        self._closed = True
