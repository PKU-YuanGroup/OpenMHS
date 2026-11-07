"""Fake backend of the ANYmal D blind-flat driver: an analytic Gymnasium environment stand-in.

Why a fake: Isaac Sim 4.2 and Isaac Lab 1.4 are external to this clone (README.md:26) and are not installed where
the gate runs, and package code never imports the clone.  This module is a small kinematic stand-in for the
environment registered as ``Isaac-Quadruped-AnymalD-Blind-Flat-v0`` (anymal_d/__init__.py:43-50).  It is *not* a
model of the robot: it has no rigid-body dynamics, contacts, actuators, sensors or noise (fidelity F0), and its
array dimensions and constants are placeholders for the gate, not facts about the device.  The real task is a
``ManagerBasedRLEnv`` configured by ``AnymalDBlindFlatEnvCfg`` and the external robot asset; the configured action
and observation terms are cited in driver.py.

The public members are the Gymnasium environment interface (``reset``, ``step``, ``close``); gate G7 compares them
with the configuration class named by ``native``, whose ``ManagerBasedRLEnvCfg`` base lies outside the clone, and
reports them as ``MAYBE_ABSENT`` warnings.  Nothing here talks to a device.
"""

import random

# placeholder: the fake has a 12-value joint action and a 36-value observation.  The configured task writes one
# joint-position target per joint matched by joint_names [".*"] of the external robot asset and concatenates its
# observation terms (quadruped_env_cfg.py:118 and :130-150), so the real dimensions are not asserted here.
ACTION_SIZE = 12
OBSERVATION_SIZE = 3 * ACTION_SIZE
# placeholder: the fake's action-space test bounds.  The configured JointPositionActionCfg does not state a bound
# in the clone, and a bound derived from an external asset is not available, so this is test data only.
ACTION_LOW, ACTION_HIGH = -1.0, 1.0
# placeholder: the fake starts its joints within this range and moves them by this fraction of the error per step.
RESET_LOW, RESET_HIGH = -0.05, 0.05
TRACKING_GAIN = 0.25
# placeholder: the fake's observation bound, wide enough for its test data.
OBSERVATION_BOUND = 10.0


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: lower and upper bounds per element, read by the bridge."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeAnymalDBlindFlatEnv:
    """A deterministic kinematic stand-in with the Gymnasium ``reset``/``step``/``close`` interface."""

    def __init__(self, **_options):
        self.action_space = Box([ACTION_LOW] * ACTION_SIZE, [ACTION_HIGH] * ACTION_SIZE)       # placeholder
        self.observation_space = Box([-OBSERVATION_BOUND] * OBSERVATION_SIZE,
                                     [OBSERVATION_BOUND] * OBSERVATION_SIZE)                   # placeholder
        self._rng = random.Random()
        self._position = [0.0] * ACTION_SIZE
        self._velocity = [0.0] * ACTION_SIZE
        self._last_action = [0.0] * ACTION_SIZE
        self._tick = 0
        self._closed = False

    def _observation(self):
        return list(self._position) + list(self._velocity) + list(self._last_action)

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._position = [self._rng.uniform(RESET_LOW, RESET_HIGH) for _ in range(ACTION_SIZE)]  # placeholder
        self._velocity = [0.0] * ACTION_SIZE
        self._last_action = [0.0] * ACTION_SIZE
        self._tick = 0
        return self._observation(), {}

    def step(self, action):
        values = [float(value) for value in action]
        if len(values) != ACTION_SIZE:
            raise ValueError(f"expected {ACTION_SIZE} action values, got {len(values)}")
        self._velocity = [target - position for target, position in zip(values, self._position)]
        self._position = [position + TRACKING_GAIN * velocity
                          for position, velocity in zip(self._position, self._velocity)]
        self._last_action = values
        self._tick += 1
        reward = -sum(velocity * velocity for velocity in self._velocity) / ACTION_SIZE
        return self._observation(), reward, False, False, {"tick": self._tick}

    def close(self):
        self._closed = True
