"""Fake backend of the roboeval driver: a kinematic stand-in for ``LiftPotPosition``.

The upstream class (``roboeval.envs.lift_pot:LiftPotPosition``) is a Gymnasium environment whose world is
built by Mojo/MuJoCo in ``__init__`` and whose physics runs through MuJoCo.  MuJoCo was not installed where
the gate ran, the clone is never imported by package code, and the upstream package cannot be installed here,
so this module provides the public surface the driver uses: ``reset``, ``step``, ``get_observation``,
``get_info``, ``close`` and the ``seed`` property (gate G7 checks exactly these names against the upstream
class).

What this is not: the upstream environment.  It integrates no physics, models no robot, pot, contacts or
actuators, and returns a one-element placeholder observation.  Every number below is test data, marked
``# placeholder``, not a fact, limit or device property.  The driver's fidelity gaps say the same.
"""

import random


class FakeLiftPotPosition:
    """A deterministic, physics-free stand-in with the upstream environment's public methods."""

    def __init__(self, **_options):
        self._seed = 0                                  # placeholder
        self._rng = random.Random(self._seed)
        self._tick = 0                                  # placeholder
        self._joint = 0.0                               # placeholder
        self._closed = False

    @property
    def seed(self):
        """The seed of the current episode (``roboeval_env.py:234``)."""

        return self._seed

    def reset(self, *, seed=None, options=None):
        """Start a new episode; the options dictionary is accepted and not interpreted."""

        if seed is None:
            seed = self._rng.randrange(2 ** 32)         # placeholder
        self._seed = int(seed)
        self._rng = random.Random(self._seed)
        self._tick = 0
        self._joint = self._rng.uniform(-0.01, 0.01)    # placeholder
        return self.get_observation(), self.get_info()

    def step(self, action=None, fast=False):
        """Advance the placeholder state by one control step."""

        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self._tick += 1
        if action is not None:
            values = [float(item) for item in action]
            if values:
                self._joint = self._joint + 0.001 * (sum(values) / len(values))   # placeholder
        if fast:
            return {}, 0, False, False, {}
        return self.get_observation(), 0.0, False, False, self.get_info()          # placeholder reward

    def get_observation(self):
        """The default observation config is proprioception-only; the arrays here are placeholders."""

        return {
            "proprioception": [self._joint, float(self._tick)],   # placeholders
            "proprioception_grippers": [0.0, 0.0],                # placeholders
        }

    def get_info(self):
        return {"task_success": 0.0}                              # placeholder

    def close(self):
        self._closed = True
