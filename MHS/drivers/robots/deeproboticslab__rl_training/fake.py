"""Fake backend of the Deep Robotics DR02 AMP Gymnasium driver.

The gate cannot import Isaac Lab (Isaac Sim 5.1.0 and Isaac Lab 2.3.2 need Python 3.11, Linux and the GPU stack,
README.md:33), and package code never imports the clone.  This module is a pure Python F0 stand-in for
``rl_training.envs.amp_locomotion_env:AmpLocomotionEnv``: it keeps the Gymnasium ``action_space``/``observation_space``
surface and the ``reset``/``step`` methods that the bridge calls, with the action width and observation group sizes of
the DR02 AMP configuration (``amp_env_cfg.py:135-141`` and :149-156; ``assets/deeprobotics.py:287-295``).

What this is not: the upstream environment.  It runs no Isaac Sim physics, no contacts, actuators, sensors or noise,
and it does not compute the upstream reward or termination terms.  The joint start offsets, the kinematic gain and the
zero observations are test data (each marked ``# placeholder``); they are not Facts, Limits or device numbers.  The
action Box is intentionally unbounded because the upstream Gymnasium action space is built by Isaac Lab's action
manager outside the clone. The endpoint requires an operator input envelope. The fake clips raw input as a placeholder;
it does not reproduce the external manager's scaling, default offsets or clipping order. The 20 ms control period
and the 1000-tick episode are derived from the cited configuration
(``episode_length_s`` 20.0 and ``sim.dt`` 0.005 with ``decimation`` 4, ``amp_env_cfg.py:675-680``).

Nothing here talks to a device.  This fake was not compared with an Isaac Lab run.
"""

import random

# amp_env_cfg.py:135-141: the AMP action is a joint-position target for DR02_DOF_ORDER (assets/deeprobotics.py:287-295).
ACTION_DIM = 21
# Placeholder processing: this copies the config's numbers, not the external action manager's semantics.
# amp_env_cfg.py:140 configures (-10.0, 10.0), with scales and default offsets elsewhere.
JOINT_CLIP = 10.0
# amp_env_cfg.py:149-156: the configured observation groups and their dimensions.
POLICY_DIM = 73
CRITIC_DIM = 121
AMP_HISTORY_DIM = 305
OBS_FUTURE_DIM = 69
VEL_DIM = 3
# amp_env_cfg.py:675-680: episode_length_s 20.0 / (decimation 4 x sim.dt 0.005 s) = 1000 control ticks.
EPISODE_TICKS = 1000
# placeholder: the fake's joint start spread and kinematic gain; not from the clone.
START_SPREAD = 0.05
GAIN = 0.01


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeAmpLocomotionEnv:
    """Single-environment stand-in for ``AmpLocomotionEnv``.

    ``reset`` and ``step`` are the upstream class's own methods (``amp_locomotion_env.py:206`` and :95), so gate G7
    resolves them in the clone; ``action_space``, ``observation_space`` and ``close`` come from the Gymnasium
    environment interface of the base outside the clone.
    """

    def __init__(self, **_options):
        infinite = float("inf")
        self.action_space = Box([-infinite] * ACTION_DIM, [infinite] * ACTION_DIM)
        self.observation_space = Dict({
            # The group sizes are the cited configuration; every value inside is placeholder state.
            "policy": Box([-infinite] * POLICY_DIM, [infinite] * POLICY_DIM),
            "critic": Box([-infinite] * CRITIC_DIM, [infinite] * CRITIC_DIM),
            "amp_obs_history": Box([-infinite] * AMP_HISTORY_DIM, [infinite] * AMP_HISTORY_DIM),
            "obs_future": Box([-infinite] * OBS_FUTURE_DIM, [infinite] * OBS_FUTURE_DIM),
            "vel": Box([-infinite] * VEL_DIM, [infinite] * VEL_DIM),
        })
        self._rng = random.Random()
        self._joint_pos = [0.0] * ACTION_DIM                          # placeholder: start positions
        self._joint_vel = [0.0] * ACTION_DIM                          # placeholder: start velocities
        self._last_action = [0.0] * ACTION_DIM                        # placeholder: no action yet
        self._tick = 0
        self._episode = 0

    def _observation(self):
        """The five configured groups; every component is placeholder state."""
        # placeholder values: the upstream observation manager computes these from the simulated robot.
        policy = ([0.0, 0.0, 0.0] + [0.0, 0.0, 0.0] + [0.0, 0.0, 0.0] + [0.0]
                  + list(self._joint_pos) + list(self._joint_vel) + list(self._last_action))
        return {
            "policy": policy,
            "critic": [0.0, 0.0, 0.0] + policy + [0.0] * 21 + [0.0] * 6 + [0.0] * 6 + [0.0] * 6 + [0.0] * 6,
            "amp_obs_history": [0.0] * AMP_HISTORY_DIM,
            "obs_future": [0.0] * OBS_FUTURE_DIM,
            "vel": [0.0, 0.0, 0.0],
        }

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        # placeholder: the upstream reset restores the asset defaults and applies the configured reset events.
        self._joint_pos = [self._rng.uniform(-START_SPREAD, START_SPREAD) for _ in range(ACTION_DIM)]
        self._joint_vel = [0.0] * ACTION_DIM
        self._last_action = [0.0] * ACTION_DIM
        self._tick = 0
        self._episode += 1
        return self._observation(), {}

    def step(self, action):
        # placeholder: one kinematic update per control tick; no physics, reward or termination model.
        values = [float(value) for value in action]
        clipped = [max(-JOINT_CLIP, min(JOINT_CLIP, value)) for value in values]
        self._last_action = list(clipped)
        for index in range(ACTION_DIM):
            self._joint_pos[index] += GAIN * clipped[index]
            self._joint_vel[index] = GAIN * clipped[index]
        self._tick += 1
        # placeholder: the upstream termination terms are not modelled, and the 20 s episode is a timeout.
        terminated = False
        truncated = self._tick >= EPISODE_TICKS
        return self._observation(), 0.0, terminated, truncated, {}

    def close(self):
        """The bridge may close the environment; the fake holds no external resource."""
