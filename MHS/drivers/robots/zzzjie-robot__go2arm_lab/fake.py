"""Fake backend of the Go2Arm Gymnasium driver: an analytic stand-in for the manager environment.

Why a fake: the registered environment needs Isaac Lab v2.2.0, Isaac Sim, a GPU and a scene (README.md:27-30),
none of which the acceptance gate has, and package code never imports the clone.  This module therefore models the
environment's registered contract from the clone: the 12 leg + 6 arm joint position action terms
(go2arm_lab_env_cfg.py:263-289), the 727-value policy observation (go2arm_lab_env_cfg.py:300-323) and the configured
20 s time-out over 20 ms control periods (decimation 4 * sim.dt 0.005, go2arm_lab_env_cfg.py:550-553).  The six-value
manager step (manager_env.py:88) is preserved on the private raw object and converted by the same production helpers
the ``sim`` adapter uses (``driver._normalize_manager_step`` / ``_normalize_manager_reset``), so no reward or
terminal conversion lives only here.

What this is not: an Isaac Sim run or a recording.  It is analytic (F0): there are no rigid-body dynamics, contacts,
actuators, sensors or noise.  The action bounds, the initial observation values and the reward values are synthetic
placeholders, not facts about the device; they are marked ``# placeholder`` below and listed in the driver's fidelity
``gaps``.  The real deployment adapter does not inherit the placeholder action bound: it leaves the manager
environment's action space unbounded unless the deployment supplies ``clip_actions``.

Nothing here talks to a device.
"""

import random
from collections.abc import Mapping

from .driver import _normalize_manager_reset, _normalize_manager_step

#: 12 leg joints plus 6 arm joints (go2arm_lab_env_cfg.py:263-289).  The order is the config's order.
ACTION_DIM = 18
#: 7 history terms of 3, 18, 18, 18, 3, 7, 3 values with history_length 10, plus 5 privileged terms of 1, 1, 18,
#: 3 and 4 values (go2arm_lab_env_cfg.py:300-323): (3+18+18+18+3+7+3)*10 + 1+1+18+3+4 = 727.
OBS_DIM = 727
#: episode_length_s 20.0 / (decimation 4 * sim.dt 0.005) = 1000 control steps (go2arm_lab_env_cfg.py:550-553).
EPISODE_STEPS = 1000
#: The fake's synthetic deployment envelope; placeholder, not a bound stated by the upstream (driver fidelity gaps).
ACTION_LOW = -1.0   # placeholder
ACTION_HIGH = 1.0   # placeholder


class _Box:
    """Duck-typed ``gymnasium.spaces.Box`` (the bridge reads low, high, shape and dtype)."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class _ManagerEnv:
    """Private raw stand-in that keeps the manager environment's six-value step and policy-dict observation."""

    def __init__(self, seed=0):
        self._seed = int(seed)                          # placeholder default; the bridge supplies a reset seed
        self._rng = random.Random(self._seed)
        self._observation = None
        self._tick = 0
        self._closed = False

    def reset(self, seed=None, options=None):
        if options is not None and not isinstance(options, Mapping):
            raise ValueError("options must be an object")
        if seed is not None:
            self._seed = int(seed)
        self._rng = random.Random(self._seed)
        # placeholder synthetic initial observation; the upstream reset randomizes the scene instead
        self._observation = [self._rng.uniform(-0.05, 0.05) for _ in range(OBS_DIM)]
        self._tick = 0
        self._closed = False
        return {"policy": list(self._observation)}, {}

    def step(self, action):
        if self._closed:
            raise RuntimeError("environment is closed")
        if self._observation is None:
            raise RuntimeError("reset must be called before step")
        if not isinstance(action, (list, tuple)) or len(action) != ACTION_DIM:
            raise ValueError(f"action must be a list of {ACTION_DIM} numbers")
        values = [float(item) for item in action]
        self._tick += 1
        # placeholder synthetic kinematic update: the last action moves the first ACTION_DIM channels
        for index, value in enumerate(values):
            self._observation[index] = 0.5 * self._observation[index] + 0.5 * value
        reward = -sum(value * value for value in values) / ACTION_DIM       # placeholder
        arm_reward = -sum(value * value for value in values[12:]) / 6.0     # placeholder
        terminated = False                                                  # placeholder: no contact model
        truncated = self._tick >= EPISODE_STEPS
        return {"policy": list(self._observation)}, reward, arm_reward, terminated, truncated, {}

    def close(self):
        self._closed = True
        self._observation = None


class FakeGo2ArmEnv:
    """Gymnasium-shaped fake: ``reset``, ``step`` and ``close`` only, with synthetic spaces (gate G7).

    The bridge sees the normalized five-value contract; the private raw object is where the manager environment's
    six-value step is preserved before adaptation.
    """

    def __init__(self, seed=0, **options):
        self._raw = _ManagerEnv(seed=seed)
        self.action_space = _Box([ACTION_LOW] * ACTION_DIM, [ACTION_HIGH] * ACTION_DIM)   # placeholder bounds
        self.observation_space = _Box([-float("inf")] * OBS_DIM, [float("inf")] * OBS_DIM)

    def reset(self, seed=None, options=None):
        return _normalize_manager_reset(self._raw.reset(seed=seed, options=options))

    def step(self, action):
        return _normalize_manager_step(self._raw.step(action))

    def close(self):
        self._raw.close()
