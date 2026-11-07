"""Fake backend of the GenesisLab driver: a pure Python stand-in for ``ManagerBasedRlEnv``.

Why a fake: the gate does not install or import the upstream package (it needs torch, the Genesis engine and the
downloaded robot assets), and package code never imports the clone.  This module mirrors the public surface of
``genesislab.envs:ManagerBasedRlEnv`` that the Gymnasium bridge uses: ``reset(seed, env_ids, options)`` returning
``(observations, info)``, ``step(action)`` returning ``(observations, reward, terminated, truncated, info)``, and the
two space attributes.  Gate G7 checks the class's methods against the upstream class.

What this is not: the Genesis simulator.  There is no physics, contact, actuator, sensor or noise model.  The state is
a deterministic placeholder that advances one tick per call.  The action vector is an unbounded placeholder box and
the observation list is test data; every such number below is marked ``# placeholder`` and is not a fact or a limit.

The upstream environment sets ``action_space`` to a torch zeros tensor and ``observation_space`` to ``None``
(``source/genesislab/genesislab/envs/manager_based_genesis_env.py:156-165``); it does not expose Gymnasium spaces.
A ``Box`` is used here only so the bridge can shape a joint-position action vector, and ``observation_space`` stays
``None`` as it is upstream.
"""

import math
import random

#: Placeholder action width: the G1 asset is the 29-DOF model named in
#: source/genesis_assets/genesis_assets/robots/g1/official.py:46.  The real width is
#: resolved at construction from the actuator layout, so this is test data, not a fact.
ACTION_DIM = 29  # placeholder

#: Placeholder episode length: 20 s / 20 ms from the task config, used only to exercise truncation.
MAX_STEPS = 1000  # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box`` (the bridge reads ``low``, ``high`` and ``shape``).

    The bounds are infinite: the upstream action term has no clip, so no safety limit is implied.
    """

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float64"


class FakeManagerBasedRlEnv:
    """A deterministic kinematic stand-in for ``ManagerBasedRlEnv`` (all values are placeholders)."""

    def __init__(self, **_options):
        self.num_envs = 1                          # placeholder
        self.device = "cpu"                        # placeholder
        self.step_dt = 0.02                        # placeholder
        # The upstream assigns a torch tensor here; this Box only lets the bridge shape the action.
        self.action_space = Box([-math.inf] * ACTION_DIM, [math.inf] * ACTION_DIM)
        # The upstream sets observation_space = None and never replaces it.
        self.observation_space = None
        self._rng = random.Random()
        self._seed = None
        self._tick = 0
        self._joint_pos = [0.0] * ACTION_DIM       # placeholder
        self._last_action = [0.0] * ACTION_DIM     # placeholder

    def _observation(self):
        """The shape the policy observation group has after concatenation (``components.py:133``): test data."""
        linear = [0.0, 0.0, 0.0]                   # placeholder
        angular = [0.0, 0.0, 0.0]                  # placeholder
        gravity = [0.0, 0.0, -1.0]                 # placeholder
        commands = [0.0, 0.0, 0.0]                 # placeholder
        joint_vel = [0.0] * ACTION_DIM             # placeholder
        values = linear + angular + gravity + commands + list(self._joint_pos) + joint_vel + list(self._last_action)
        return {"policy": values}

    def reset(self, seed=None, env_ids=None, options=None):
        """Reset the placeholder world; return ``(observations, info)`` as the upstream does."""
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        self._tick = 0
        self._joint_pos = [self._rng.uniform(-0.01, 0.01) for _ in range(ACTION_DIM)]  # placeholder
        self._last_action = [0.0] * ACTION_DIM     # placeholder
        return self._observation(), {}

    def step(self, action):
        """Advance one placeholder tick; return the five signals the upstream step returns."""
        values = action.get("values") if isinstance(action, dict) else action
        if isinstance(values, (list, tuple)):
            self._last_action = [float(value) for value in values[:ACTION_DIM]]
        for index, value in enumerate(self._last_action):
            self._joint_pos[index] += 0.001 * value  # placeholder
        self._tick += 1
        truncated = self._tick >= MAX_STEPS
        return self._observation(), 1.0, False, truncated, {}
