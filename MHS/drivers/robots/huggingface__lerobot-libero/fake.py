"""Fake backend of the LIBERO coffee-table environment: a small stand-in for the upstream env class.

Why a fake: the upstream environment constructs a robosuite/MuJoCo world, parses a BDDL task file and needs the
robosuite, bddl and mujoco packages.  Those packages are not installed where the acceptance gate runs (checked with
importlib.util.find_spec), package code never imports the clone, and the clone must never be executed.  This module
instead mirrors the public interface the driver uses: ``seed(seed)``, ``reset()`` and ``step(action)`` (the members of
``libero.libero.envs.bddl_base_domain:BDDLBaseDomain`` at bddl_base_domain.py:162 and :800), plus ``close`` (which
occurs throughout the clone and is the robosuite environment close).  Gate G7 compares these names with the upstream
class.

What this is not: the upstream environment.  There is no MuJoCo world, no robosuite robot, no BDDL parsing, no
placement sampler, no camera and no contact model.  Its state is a short list of placeholder numbers, and every
number below is test data, marked ``# placeholder``, not a fact, a limit or a device property.  The driver's
fidelity ``gaps`` state the same.  Nothing here talks to a device.
"""

import random


class FakeLiberoCoffeeTableManipulation:
    """A deterministic, physics-free stand-in for ``Libero_Coffee_Table_Manipulation``."""

    def __init__(self, **_options):
        self._seed = 0                                   # placeholder
        self._rng = random.Random(self._seed)
        self._tick = 0                                   # placeholder
        self._episode = 0                                # placeholder
        self._eef = [0.0, 0.0, 0.0]                      # placeholder
        self._gripper = [0.0, 0.0]                       # placeholder
        self._closed = False

    def seed(self, seed):
        """``bddl_base_domain.py:162-163``: the upstream seed forwards to numpy's global random generator."""

        self._seed = int(seed)
        self._rng.seed(self._seed)

    def reset(self):
        """Start a new episode; the upstream reset returns an observation dictionary."""

        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self._episode += 1
        self._tick = 0
        self._eef = [self._rng.uniform(-0.01, 0.01) for _ in range(3)]      # placeholder
        self._gripper = [self._rng.uniform(-0.04, 0.04) for _ in range(2)]  # placeholder
        return self._observation()

    def step(self, action):
        """``bddl_base_domain.py:800-809``: return ``(obs, reward, done, info)``; values are placeholders."""

        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = [float(item) for item in action]
        self._tick += 1
        for index in range(3):
            if index < len(values):
                self._eef[index] = self._eef[index] + 0.01 * values[index]  # placeholder gain
        return self._observation(), 0.0, False, {"success": False}          # placeholders

    def close(self):
        """The robosuite environment close; the stand-in only marks itself closed."""

        self._closed = True

    def _observation(self):
        """A placeholder observation with the keys the clone's robot state vector names (bddl_base_domain.py:826-829)."""

        return {
            "robot0_eef_pos": list(self._eef),           # placeholder
            "robot0_eef_quat": [0.0, 0.0, 0.0, 1.0],     # placeholder
            "robot0_gripper_qpos": list(self._gripper),  # placeholder
            "tick": self._tick,                           # placeholder
        }
