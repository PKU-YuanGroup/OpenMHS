"""Fake backend of the homestri-ur5e-rl driver: a kinematic stand-in for ``BaseRobot-v0``.

Why a fake: the acceptance gate runs without gymnasium, gymnasium-robotics or mujoco (the upstream declares them in
setup.py:7-12), and package code never imports the clone.  This module exposes the public members ``BaseRobot`` has
and the bridge reads: ``reset``, ``step``, ``close`` and the ``dt`` property (gate G7 checks them against the clone),
plus the ``action_space`` and ``observation_space`` instance attributes ``BaseRobot`` sets (base_robot_env.py:46,
:65).  The two space classes duck-type ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and
``dtype``.

What this is not: the upstream environment.  The fake has no MuJoCo engine, no controller, no gripper and no cable.
It integrates the seven action values into a stand-in state only, and every number below is a placeholder test datum
(``# placeholder``), not a device fact or a bound.  The differences are listed in the fidelity ``gaps`` of driver.py.

Nothing here talks to a device.
"""

import math
import random

# placeholder: the action and observation sizes mirror base_robot_env.py:65 and :46, but the values below are test data
ACTION_SIZE = 7                                      # placeholder
OBSERVATION_SIZE = 28                                # placeholder
# placeholder: frame_skip 40 (base_robot_env.py:37) times the 0.002 s MuJoCo timestep (scene.xml:6), used as test data
FRAME_SKIP = 40                                      # placeholder
TIMESTEP_S = 0.002                                   # placeholder
STEP_S = FRAME_SKIP * TIMESTEP_S                     # placeholder: 0.08 s per environment step
# placeholder: start-state spread and integration factor of the kinematic stand-in
INITIAL_SPREAD = 0.05                                # placeholder
INTEGRATION_GAIN = 1.0                               # placeholder
REWARD = 0.0                                         # placeholder
WIRE_SIZE = OBSERVATION_SIZE - 2 * ACTION_SIZE       # placeholder: 14 stand-in wire values


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float64"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.low):
            return False
        return all(float(item) >= self.low[index] and float(item) <= self.high[index]
                   for index, item in enumerate(value))


class FakeBaseRobot:
    """A kinematic 7-input stand-in for ``BaseRobot``: ``reset``, ``step``, ``close`` and ``dt``.

    The state is the seven joint positions, their seven placeholder velocities and fourteen placeholder wire values.
    ``step`` writes the action into the velocities and integrates the positions by ``STEP_S``; no force, contact,
    actuator or cable dynamics are modelled.
    """

    def __init__(self, **options):
        self.action_space = Box([-1.0] * ACTION_SIZE, [1.0] * ACTION_SIZE)       # placeholder bounds
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self._options = dict(options)
        self._rng = random.Random()
        self._qpos = [0.0] * ACTION_SIZE
        self._qvel = [0.0] * ACTION_SIZE
        self._wire = [0.0] * WIRE_SIZE
        self._closed = False

    @property
    def dt(self):
        """The environment step interval in seconds; placeholder test data, not a device fact."""
        return STEP_S

    def _observation(self):
        """The 28-element stand-in observation: joint positions, velocities and wire values."""
        return list(self._qpos) + list(self._qvel) + list(self._wire)

    def reset(self, *, seed=None, options=None):
        """Restore a stand-in start state; ``seed`` fixes the placeholder offsets for this fake."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._qpos = [self._rng.uniform(-INITIAL_SPREAD, INITIAL_SPREAD) for _ in range(ACTION_SIZE)]
        self._qvel = [0.0] * ACTION_SIZE                                     # placeholder
        self._wire = [self._rng.uniform(-INITIAL_SPREAD, INITIAL_SPREAD) for _ in range(WIRE_SIZE)]
        return self._observation(), {}

    def step(self, action):
        """Advance one placeholder step: the action becomes velocity and moves the positions by ``STEP_S``."""
        values = list(action)
        if len(values) != ACTION_SIZE:
            raise ValueError(f"the action has {len(values)} values; BaseRobot-v0 takes {ACTION_SIZE}")
        for index, value in enumerate(values):
            self._qvel[index] = float(value)
            self._qpos[index] = self._qpos[index] + float(value) * STEP_S * INTEGRATION_GAIN
        # the gripper value also nudges the placeholder wire values, so the observation follows every input
        for index in range(WIRE_SIZE):
            self._wire[index] = self._wire[index] + float(values[-1]) * STEP_S * INTEGRATION_GAIN
        return self._observation(), REWARD, False, False, {}

    def close(self):
        """Mark the stand-in closed; the bridge calls this when the server closes."""
        self._closed = True
