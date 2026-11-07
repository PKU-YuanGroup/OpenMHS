"""Fake backend for gh.luccachiang/gsworld: a pure-Python kinematic stand-in for ``RealFr3-v1``.

Why a fake: the acceptance gate cannot install or import the upstream stack (ManiSkill 3.0.0b15, SAPIEN, PhysX,
torch and the asset downloads), and package code never imports the clone.  This module models the public surface of
``gsworld.mani_skill.envs.tasks.real_fr3_env:RealFr3`` that the Gymnasium bridge uses -- ``reset(seed, options)``,
``step(action)``, ``close()``, ``action_space``, ``observation_space`` and ``dt`` -- with a kinematic 9-joint FR3
(seven arm joints and two gripper fingers, ``fr3_umi.py:41-53``).

The arm action values are normalised deltas; the fake scales them by the controller's physical delta bound of 0.1
(``fr3_umi.py:78-86``).  The normalisation and the exact action dimension are assembled by the external ManiSkill
package and are not declared in the clone, so the normalised action Box is marked ``# placeholder``.  The gripper
command maps the normalised value onto the controller's -0.01 to 0.04 range (``fr3_umi.py:114-121``).  The start
configuration is ``fr3_umi_task_init_qpos`` (``constants.py:63-73``) plus a placeholder reset noise; everything that is
invented for the stand-in is marked ``# placeholder``.

What this is not: SAPIEN/PhysX, the upstream environment, or a validated model.  There are no rigid-body dynamics,
contacts, sensors, cameras or rendering, the observation is the 18-value qpos/qvel part only, and the fake was never
compared with an upstream run.  The driver's fidelity ``gaps`` list these omissions.  The public methods are
``reset``, ``step`` and ``close``; ``reset`` and ``step`` are inherited by the upstream class from the external
ManiSkill ``BaseEnv``, which the clone's AST cannot follow, so gate G7 may report ``MAYBE_ABSENT`` for them.

Nothing here talks to a device.
"""

import math
import random

#: The upstream registration limit (real_fr3_env.py:22) and the deployed control period (20 Hz, from the GSWorld
#: wrapper's sim_freq=100 and control_freq=20, gs_world_wrapper.py:89).
MAX_EPISODE_STEPS = 200000
DT = 0.05

#: The controller bounds the arm delta to -0.1..0.1 (fr3_umi.py:78-86) and the gripper command to -0.01..0.04
#: (fr3_umi.py:114-121).
ARM_DELTA = 0.1
GRIPPER_LOW, GRIPPER_HIGH = -0.01, 0.04

#: The nine-joint FR3 UMI start configuration, constants.py:63-73.
TASK_INIT_QPOS = [
    0.00879998,
    -0.62698067,
    -0.00591884,
    -2.25830053,
    -0.00557862,
    1.63165594,
    0.78539816,
    0.0404319502,
    0.0404319502,
]

#: Test data of this stand-in, not values of the upstream environment.
N_ACTUATORS = 8               # placeholder: 7 arm joints plus the mimic gripper; the exact dimension is external
N_JOINTS = len(TASK_INIT_QPOS)          # 9: fr3_umi.py:41-53
OBSERVATION_SIZE = 2 * N_JOINTS         # qpos and qvel; controller state is not modelled
RESET_NOISE = 0.02            # placeholder: the fake's reset joint noise
REWARD = 0.0                  # placeholder: RealFr3.evaluate returns {}, so this dummy task has no reward term


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, dtype=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype or "float32"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != self.shape[0]:
            return False
        return all(float(low) <= float(item) <= float(high)
                   for item, low, high in zip(value, self.low, self.high))


class FakeRealFr3:
    """A kinematic FR3 in an empty scene: the reset/step/close surface of ``RealFr3`` without SAPIEN."""

    #: The bridge reads this to fill ``fidelity.timestep_ms`` (GymnasiumDriver._derived_fidelity).
    dt = DT

    def __init__(self, **_options):
        # The normalised action Box is a stand-in: ManiSkill assembles the real space from the controller configs.
        self.action_space = Box([-1.0] * N_ACTUATORS, [1.0] * N_ACTUATORS)          # placeholder
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE,
                                     [math.inf] * OBSERVATION_SIZE)                 # qpos + qvel
        self._rng = random.Random(0)                                                # placeholder
        self._qpos = list(TASK_INIT_QPOS)
        self._qvel = [0.0] * N_JOINTS
        self._tick = 0
        self._closed = False
        self.reset(seed=0)

    def reset(self, seed=None, options=None):
        """Reset the stand-in to the FR3 UMI start configuration plus repeatable joint noise."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._qpos = [base + self._rng.uniform(-RESET_NOISE, RESET_NOISE)            # placeholder noise
                      for base in TASK_INIT_QPOS]
        self._qvel = [0.0] * N_JOINTS
        self._tick = 0
        return self._observation(), {}

    def step(self, action):
        """Apply one normalised arm/gripper action and return the next state observation."""
        values = list(action)
        if len(values) != N_ACTUATORS:
            raise ValueError(f"RealFr3-v1 takes {N_ACTUATORS} action values, got {len(values)}")
        for index in range(7):
            delta = float(values[index]) * ARM_DELTA                                 # fr3_umi.py:78-86
            self._qvel[index] = delta / DT                                           # placeholder velocity model
            self._qpos[index] = self._qpos[index] + delta
        # The gripper is a two-joint mimic controller: one command sets both fingers (fr3_umi.py:114-121).
        target = GRIPPER_LOW + (float(values[7]) + 1.0) * 0.5 * (GRIPPER_HIGH - GRIPPER_LOW)
        for index in (7, 8):
            self._qvel[index] = (target - self._qpos[index]) / DT                    # placeholder velocity model
            self._qpos[index] = target
        self._tick += 1
        truncated = self._tick >= MAX_EPISODE_STEPS                                  # real_fr3_env.py:22
        return self._observation(), REWARD, False, truncated, {"tick": self._tick}

    def close(self):
        self._closed = True

    def _observation(self):
        """The agent qpos and qvel; RealFr3 adds no extra observation (real_fr3_env.py:119-123)."""
        return list(self._qpos) + list(self._qvel)
