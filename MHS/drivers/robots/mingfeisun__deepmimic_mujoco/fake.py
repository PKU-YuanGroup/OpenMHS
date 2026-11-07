"""Fake backend of the DeepMimic driver: a reduced pure-Python stand-in for ``HumanoidDeepMimic-v0``.

Why a fake: the upstream environment is a legacy ``gym``/``mujoco-py`` environment (MuJoCo 2.1), its constructor
loads the asset through the absolute path of one host (``humanoid_deepmimic_env.py:7``), and the ``envs`` package
imports a module that does not exist (``envs/__init__.py:2``).  Package code never imports or runs the clone, so this
module keeps the two public methods the bridge calls (``reset`` and ``step``; gate G7) and a small deterministic
surrogate of the environment's state.  The one-step reward follows ``humanoid_deepmimic_env.py:14-19``: forward
reward from the root x displacement over dt, minus a 0.5*sum(a^2) control cost, minus a contact cost, plus a survive
reward of 1.0.  The done test follows ``humanoid_deepmimic_env.py:21-23``: the state must be finite and its third
element in [0.2, 1.0]; here the third element of the full state is the reduced torso height.

What this is not, and what the fidelity ``gaps`` of driver.py also say:

* no MuJoCo: no rigid-body integration, joints, contacts or ``cfrc_ext``; the observation is a 9-number reduction,
  while the model's own observation has 16 qpos values, 17 qvel values and 48 cfrc_ext values (81 numbers);
* the action is bounded by the model's motor control range of -0.3 to 0.3 (``humanoid_deepmimic.xml:7``) for the
  three chest motors (``humanoid_deepmimic.xml:123-125``); the legacy gym action space is not reproduced;
* the reset noise is this module's own ``random.Random`` stream, not the upstream numpy generator;
* there is no rendering and no viewer.

Every number below that is not a cited model constant is test data and is marked ``# placeholder``.  It must never be
copied into a Fact, a Limit or the reference.
"""

import math
import random

# Sourced constants: humanoid_deepmimic_env.py:7 passes frame_skip 5 and humanoid_deepmimic.xml:9 sets timestep 0.003.
FRAME_SKIP = 5
MODEL_TIMESTEP = 0.003
DT = FRAME_SKIP * MODEL_TIMESTEP                       # 15 ms per environment step

# Sourced constants: humanoid_deepmimic.xml:7 (default motor ctrlrange) and :123-125 (three chest motors).
ACTION_LOW, ACTION_HIGH = -0.3, 0.3
ACTION_SIZE = 3

# Sourced constants: humanoid_deepmimic_env.py:21-22 (state[2] in [0.2, 1.0]).
HEIGHT_LOW, HEIGHT_HIGH = 0.2, 1.0

# Test data, not facts: the reduced observation layout and the surrogate dynamics.
OBSERVATION_SIZE = 9                                    # placeholder
START_HEIGHT = 0.8                                      # placeholder
RESET_HEIGHT_SPAN = 0.1                                 # placeholder
RESET_X_SPAN = 0.1                                      # placeholder
RESET_VX_SPAN = 0.05                                    # placeholder
FORCE_GAIN = 0.01                                       # placeholder
HEIGHT_DECAY = 0.0005                                   # placeholder


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        try:
            values = list(value)
        except TypeError:
            return False
        return len(values) == len(self.low) and all(
            low <= float(item) <= high for item, low, high in zip(values, self.low, self.high))


class FakeHumanoidDeepMimicEnv:
    """A reduced stand-in for the legacy ``HumanoidDeepMimicEnv``: ``reset`` and ``step`` only."""

    dt = DT

    def __init__(self):
        self.action_space = Box([ACTION_LOW] * ACTION_SIZE, [ACTION_HIGH] * ACTION_SIZE)
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self.frame_skip = FRAME_SKIP
        self._rng = random.Random()
        self._height = START_HEIGHT
        self._x = 0.0
        self._vx = 0.0
        self._vy = 0.0
        self._vz = 0.0
        self._tick = 0

    def _get_obs(self):
        """A 9-number reduction of ``qpos[2:] + qvel + cfrc_ext`` (humanoid_deepmimic_env.py:31-36)."""
        return [self._height, self._vx, self._vy, self._vz, self._x, 0.0, 0.0, 0.0, 0.0]

    def reset(self, *, seed=None, options=None):
        """Reset the reduced state; ``seed`` makes the draw repeatable (the fake's own determinism control)."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._height = START_HEIGHT + self._rng.uniform(-RESET_HEIGHT_SPAN, RESET_HEIGHT_SPAN)  # placeholder
        self._x = self._rng.uniform(-RESET_X_SPAN, RESET_X_SPAN)                               # placeholder
        self._vx = self._rng.uniform(-RESET_VX_SPAN, RESET_VX_SPAN)                            # placeholder
        self._vy = 0.0
        self._vz = 0.0
        self._tick = 0
        return self._get_obs(), {}

    def step(self, action):
        """Apply one reduced step and return the legacy four-tuple ``(observation, reward, done, info)``."""
        values = [float(item) for item in action]
        if len(values) != ACTION_SIZE:
            raise ValueError(f"expected {ACTION_SIZE} motor values, got {len(values)}")
        xposbefore = self._x
        control_cost = 0.5 * sum(value * value for value in values)                  # humanoid_deepmimic_env.py:15
        self._vx += FORCE_GAIN * sum(values)                                        # placeholder
        self._x += self._vx * DT                                                    # placeholder
        self._height -= HEIGHT_DECAY * sum(value * value for value in values)       # placeholder
        self._tick += 1
        forward_reward = (self._x - xposbefore) / DT                                # humanoid_deepmimic_env.py:14
        contact_cost = 0.0                                                          # placeholder: the fake has no contacts
        survive_reward = 1.0                                                        # humanoid_deepmimic_env.py:18
        reward = forward_reward - control_cost - contact_cost + survive_reward      # humanoid_deepmimic_env.py:19
        done = not (math.isfinite(self._height) and HEIGHT_LOW <= self._height <= HEIGHT_HIGH)  # :21-23
        return self._get_obs(), reward, done, {
            "reward_forward": forward_reward,
            "reward_ctrl": -control_cost,
            "reward_contact": -contact_cost,
            "reward_survive": survive_reward,
            "tick": self._tick,
        }
