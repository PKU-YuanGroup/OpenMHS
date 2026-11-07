"""Fake backend of the ManipArena-Sim driver.

Why a fake: the upstream stack needs Isaac Sim 6.x wheels, Isaac Lab, IsaacLab-Arena, Linux and an NVIDIA GPU
(README.md:36-44; docs/install.md:13), and package code never imports or runs the clone.  This module stands in for
the two methods of ``maniparena_sim.environment.assembled_environment:AssembledEnvironment`` that the driver uses,
``build_gym_environment`` (assembled_environment.py:63-109) and ``get_env`` (assembled_environment.py:180-183), and
returns a small pure Python Gymnasium-shaped environment.  Gate G7 checks the members of ``FakeAssembledEnvironment``
against that class; the inner environment is not the backend entry point and is not part of that surface.

What this is not: the upstream simulator.  It models one state coordinate per joint of a placeholder four-value
policy group, has no Isaac Sim physics, contacts, actuators, sensors, cameras or rendering, and was never compared with
the upstream environment.  Every number below is test data only (each marked ``# placeholder``); none is copied into a
Fact, a Limit or the reference.
"""

import random

#: placeholder: the fake action width, standing in for the configured embodiment's total action dimension
ACTION_WIDTH = 12
#: placeholder: the fake policy observation width
OBSERVATION_WIDTH = 4


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a low and a high bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeGymEnv:
    """A Gymnasium-shaped stand-in for the environment ``AssembledEnvironment.build_gym_environment`` returns."""

    def __init__(self):
        # placeholder: every action value is bounded by -1..1 and the fake observes four values
        self.action_space = Box([-1.0] * ACTION_WIDTH, [1.0] * ACTION_WIDTH)
        self.observation_space = Box([-1.0] * OBSERVATION_WIDTH, [1.0] * OBSERVATION_WIDTH)
        self._rng = random.Random()
        # placeholder: the reset state is drawn uniformly from -1..1 per observation value
        self._state = [0.0] * OBSERVATION_WIDTH
        self._tick = 0
        self._reward = 0.0
        self._seed = 0

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        # placeholder: the initial state draw
        self._state = [self._rng.uniform(-1.0, 1.0) for _ in range(OBSERVATION_WIDTH)]
        self._tick = 0
        self._reward = 0.0
        return {"policy": list(self._state)}, {}

    def step(self, action):
        values = action
        if isinstance(action, (list, tuple)) and action and isinstance(action[0], (list, tuple)):
            values = action[0]
        if hasattr(values, "tolist"):
            values = values.tolist()
        if not isinstance(values, (list, tuple)):
            values = []
        # placeholder: one tick moves each observation value by a fixed gain times the matching action value
        self._state = [value + 0.01 * float(command)
                       for value, command in zip(self._state, values)]
        self._tick += 1
        self._reward = 0.0
        return {"policy": list(self._state)}, self._reward, False, False, {"tick": self._tick}

    def close(self):
        self._tick = 0


class FakeAssembledEnvironment:
    """Stand-in for ``AssembledEnvironment``: only its builder and getter, and the env they return.

    Both public methods exist on the upstream class (assembled_environment.py:63 and :180), so gate G7 resolves them.
    """

    def __init__(self, **_options):
        self._env = FakeGymEnv()
        self.is_built = False

    def build_gym_environment(self, args=None, output_dir=None, output_file_name=None, enable_recording=False,
                              dataset_file_handler_class_type=None, mode="collect"):
        """Return the fake gym environment (the upstream method builds and returns a real one)."""
        self.is_built = True
        return self._env

    def get_env(self):
        """Return the fake gym environment, building it on first use like the upstream getter."""
        if not self.is_built:
            return self.build_gym_environment()
        return self._env
