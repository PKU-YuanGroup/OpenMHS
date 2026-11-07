"""Fake backend of the LocoMuJoCo driver: a pure Python stand-in for ``GymnasiumWrapper``.

Why a fake: the acceptance gate runs without the upstream package (it needs jax, mujoco, gymnasium and the separate
``loco_mujoco_models`` model files), and package code never imports the clone.  This module duck-types the surface of
``loco_mujoco.core.wrappers.gymnasium:GymnasiumWrapper`` (the class the driver names as ``native``): ``reset``,
``step`` and ``close``, plus the ``action_space`` and ``observation_space`` Box attributes the bridge reads.  Every
number in this file is placeholder test data, marked ``# placeholder``: it is not a fact, a limit or a device
parameter, and the fidelity ``gaps`` of ``driver.py`` say what the fake does not model.

What this is not: the upstream environment.  The fake has no MuJoCo model, contacts, actuators, sensors, reward
function or termination, and its values were never compared with the upstream simulator.
"""

import math
import random

# placeholder: test-data widths of the stand-in world (not device facts)
JOINT_COUNT = 27
GOAL_COUNT = 3
ROOT_POSITION_COUNT = 5
ROOT_VELOCITY_COUNT = 6
OBSERVATION_DIM = ROOT_POSITION_COUNT + JOINT_COUNT + ROOT_VELOCITY_COUNT + JOINT_COUNT + GOAL_COUNT
# placeholder: the fake starts near zero and integrates the action into the joint position
RESET_SPREAD = 0.01
STEP_GAIN = 0.01
# placeholder: the stand-in never pays a reward and never ends an episode
REWARD = 0.0


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None):
        if isinstance(low, (list, tuple)):
            self.low = [float(value) for value in low]
            self.high = [float(value) for value in high]
        else:
            self.low = float(low)
            self.high = float(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float64"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != self.shape[0]:
            return False
        return all(float(low) <= float(item) <= float(high)
                   for low, high, item in zip(self.low, self.high, value))


class FakeGymnasiumWrapper:
    """Stand-in for ``GymnasiumWrapper``: ``reset(seed, options)``, ``step(action)`` and ``close()``.

    The constructor mirrors the upstream wrapper's ``env_name``, ``render_mode`` and ``**kwargs`` so the family
    driver can construct it with ``env_kwargs``; the values are accepted and ignored.
    """

    def __init__(self, env_name="Atlas", render_mode=None, **kwargs):
        self.env_name = env_name                      # placeholder: the fake world has no robots
        self.render_mode = render_mode
        self.metadata = {"render_modes": ["human", "rgb_array"]}
        # placeholder: the 27-value, -1..1 action space of the Atlas PD controller
        self.action_space = Box([-1.0] * JOINT_COUNT, [1.0] * JOINT_COUNT, (JOINT_COUNT,))
        # placeholder: the wrapper converts the inner observation space to a Box of the same shape
        self.observation_space = Box([-math.inf] * OBSERVATION_DIM, [math.inf] * OBSERVATION_DIM,
                                     (OBSERVATION_DIM,))
        self._rng = random.Random()                   # placeholder: replaced by reset(seed=...)
        self._root = [0.0] * ROOT_POSITION_COUNT      # placeholder
        self._qpos = [0.0] * JOINT_COUNT              # placeholder
        self._root_vel = [0.0] * ROOT_VELOCITY_COUNT  # placeholder
        self._qvel = [0.0] * JOINT_COUNT              # placeholder
        self._goal = [0.0] * GOAL_COUNT               # placeholder
        self._closed = False

    def _observation(self):
        """The fake observation vector: root, joints, root velocity, joint velocity, goal (placeholders)."""
        return list(self._root) + list(self._qpos) + list(self._root_vel) + list(self._qvel) + list(self._goal)

    def reset(self, *, seed=None, options=None):
        """Draw a placeholder start state; ``options`` is accepted and ignored, as the upstream wrapper does."""
        self._rng = random.Random(seed)                                     # placeholder: no upstream RNG
        self._root = [0.0] * ROOT_POSITION_COUNT                            # placeholder
        self._qpos = [self._rng.uniform(-RESET_SPREAD, RESET_SPREAD) for _ in range(JOINT_COUNT)]  # placeholder
        self._root_vel = [0.0] * ROOT_VELOCITY_COUNT                        # placeholder
        self._qvel = [0.0] * JOINT_COUNT                                    # placeholder
        self._goal = [0.0] * GOAL_COUNT                                     # placeholder
        self._closed = False
        return self._observation(), {}

    def step(self, action):
        """Integrate the placeholder action into the joint positions and return the gymnasium five-tuple."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = list(action)
        if len(values) != JOINT_COUNT:
            raise ValueError(f"the fake expects {JOINT_COUNT} action values, got {len(values)}")
        for index, value in enumerate(values):
            self._qpos[index] += STEP_GAIN * float(value)                   # placeholder
            self._qvel[index] = float(value)                                # placeholder
        return self._observation(), REWARD, False, False, {}

    def close(self):
        """Mirror ``GymnasiumWrapper.close``: stop the stand-in world (nothing to stop)."""
        self._closed = True
