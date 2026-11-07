"""Fake backend of the Go2-Flat driver: a pure Python interface stand-in for the Isaac Lab locomotion task.

Why a fake: the registered task needs Isaac Sim and Isaac Lab (README_train.md:3), a GPU and an environment
configuration object passed to ``gym.make`` (scripts/rsl_rl/train.py:174), and package code never imports or runs the
clone.  The gate therefore checks this stand-in, which reproduces the parts of the Gymnasium contract the bridge
reads: ``action_space`` and ``observation_space``, ``reset(seed, options)``, ``step(action)`` and ``close``.  The
upstream class ``LocomotionEnv`` inherits the rest of that interface from ``isaaclab.envs.DirectRLEnv`` and
``gymnasium.Env``, both outside the clone.

What this is not: the upstream environment.  It has no Isaac Sim, no rigid bodies, no contacts, no actuator, sensor or
noise model, no robot pose and no command.  The 260-value observation follows the 52-value frame order of
``go2_env_cfg.py:173-183`` (three base linear-velocity values, three base angular-velocity values, three projected
gravity values, three command values, twelve joint positions, twelve joint velocities, twelve last actions and four
clock values) and the five-frame history of ``:185-191``; only the last-action tail of the newest frame reflects the
action, every other value is a fixed test placeholder, and the reward is a fixed test placeholder.  The 12-value
action is the ``action_space`` of ``Go2FlatEnvCfg`` (``go2_env_cfg.py:172``), not a claim that the physics is
modelled.  The upstream task batches 4096 environments by default (``go2_env_cfg.py:337``); this stand-in serves one
environment with the single-environment spaces.  The fake never terminates or truncates, and the upstream episode
time limit and contact-based termination (``locomotion_env.py:571-577``) are not modelled.

The action space is deliberately unbounded: the real action-space object is created by the external ``DirectRLEnv``
and was not inspected, while the clone's own ``_pre_physics_step`` accepts any finite action tensor and clamps it to
+/-3.0 (``locomotion_env.py:322-323`` with ``go2_env_cfg.py:388``).  The fake neither rejects nor clamps an action.
"""

import math

# go2_env_cfg.py:172: action_space = 12.
ACTION_SIZE = 12
# go2_env_cfg.py:173-183: 3 + 3 + 3 + 3 + 12 + 12 + 12 + 4 values per observation frame.
SINGLE_OBSERVATION_SIZE = 52
# go2_env_cfg.py:190: history_length = 5.
HISTORY_LENGTH = 5
# go2_env_cfg.py:191: observation_space *= history_length, so 52 * 5 = 260.
OBSERVATION_SIZE = SINGLE_OBSERVATION_SIZE * HISTORY_LENGTH
# go2_env_cfg.py:173-179: the last-actions term starts after 3 + 3 + 3 + 3 + 12 + 12 values.
ACTION_OFFSET = 36


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeGo2FlatEnv:
    """One Locomotion-Go2-Flat environment without Isaac Sim: the contract, not the physics."""

    def __init__(self, cfg=None, render_mode=None, **kwargs):
        if render_mode is not None:
            raise ValueError("the fake Go2-Flat environment cannot render; use render_mode=None")
        # The action-space bounds are not in the clone (they are built by the external DirectRLEnv), so the fake
        # exposes an unbounded Box of the configured 12 values and invents no envelope.
        self.action_space = Box([-math.inf] * ACTION_SIZE, [math.inf] * ACTION_SIZE)
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self._seed = None
        self._tick = 0
        self._observation = [0.0] * OBSERVATION_SIZE  # placeholder
        self._terminated = False
        self._truncated = False

    def reset(self, *, seed=None, options=None):
        """Start a new episode; ``options`` is accepted for the Gymnasium reset contract and has no effect."""
        if seed is not None:
            self._seed = int(seed)
        self._tick = 0
        self._terminated = False
        self._truncated = False
        self._observation = [0.0] * OBSERVATION_SIZE  # placeholder
        return list(self._observation), {}

    def step(self, action):
        """Apply one 12-value action and advance the reduced state by one control step."""
        values = list(action)
        if len(values) != ACTION_SIZE:
            raise ValueError(f"the action must have {ACTION_SIZE} values, got {len(values)}")
        checked = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"the action values must be numbers, got {value!r}")
            checked.append(float(value))
        # Shift the five-frame history and make the last-action tail of the newest frame observable.
        frame = [0.0] * SINGLE_OBSERVATION_SIZE  # placeholder
        frame[ACTION_OFFSET:ACTION_OFFSET + ACTION_SIZE] = checked
        self._observation = self._observation[SINGLE_OBSERVATION_SIZE:] + frame
        self._tick += 1
        self._terminated = False
        self._truncated = False
        reward = 0.0  # placeholder
        return list(self._observation), reward, self._terminated, self._truncated, {}

    def close(self):
        self._observation = []
