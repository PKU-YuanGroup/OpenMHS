"""Fake backend of the Berkeley Humanoid rough-task driver: a pure Python interface stand-in.

Why a fake: the registered task needs Isaac Sim 4.0.0 with Isaac Lab 1.0.0 (README.md:25-27), a GPU and an
environment configuration object passed to ``gym.make`` (scripts/rsl_rl/train.py:89), and package code never imports
or runs the clone.  The gate therefore checks this stand-in, which reproduces the parts of the Gymnasium contract the
bridge reads: ``action_space`` and ``observation_space``, ``reset(seed, options)``, ``step(action)`` and ``close``.
The upstream class named by the driver, ``BerkeleyHumanoidRoughEnvCfg``, is a configuration class; the environment
interface comes from the external ``omni.isaac.lab.envs:ManagerBasedRLEnv``, which is not in the clone.

What this is not: the upstream environment.  It has no Isaac Sim, no rigid bodies, no contacts, no actuator, sensor or
noise model, no robot pose and no command.  The 12-value action is the joint-position target over the 12 joints named
by the asset's ``init_state.joint_pos`` (berkeley_humanoid.py:96-109) with the configured scale 0.5
(velocity_env_cfg.py:115), but the fake does not move a joint.  The 15-value observation has three stand-in base
values and the 12-value last-action term of the policy group (velocity_env_cfg.py:126-143): every other value is a
fixed placeholder.  The upstream policy group concatenates ten terms and its flattened width is built by Isaac Lab
outside the clone, so the fake returns a smaller observation; the fidelity gaps of the driver say so.  The fake never
terminates or truncates, and the configured time-out and torso-contact termination (velocity_env_cfg.py:315-318) are
not modelled.

The action space is deliberately unbounded: the real action-space object is created by the external
``ManagerBasedRLEnv`` and was not inspected, so the fake exposes an unbounded Box of 12 values and invents no
envelope.  The fake neither rejects nor clamps an action.  Nothing here talks to a device.
"""

import math
import random

# berkeley_humanoid.py:96-109: the twelve joints named by init_state.joint_pos.
JOINT_NAMES = (
    "LL_HR", "LR_HR", "LL_HAA", "LR_HAA", "LL_HFE", "LR_HFE",
    "LL_KFE", "LR_KFE", "LL_FFE", "LR_FFE", "LL_FAA", "LR_FAA",
)
N_JOINTS = len(JOINT_NAMES)
# velocity_env_cfg.py:115: joint_names [".*"] over the twelve joints, so the action is twelve values.
ACTION_SIZE = N_JOINTS
# placeholder: the fake represents three base values before the last-action term of the policy observation.
BASE_VALUES = 3
# The last-action term (velocity_env_cfg.py:143) has the action width; the fake returns it after the base values.
OBSERVATION_SIZE = BASE_VALUES + ACTION_SIZE


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeBerkeleyHumanoidEnv:
    """One Velocity-Rough-Berkeley-Humanoid-v0 environment without Isaac Sim: the contract, not the physics."""

    def __init__(self, cfg=None, render_mode=None, **kwargs):
        if render_mode is not None:
            raise ValueError("the fake Berkeley Humanoid environment cannot render; use render_mode=None")
        self._cfg = cfg  # placeholder: the real environment builds its managers from cfg
        # The action-space bounds are not in the clone (they are built by the external ManagerBasedRLEnv), so the
        # fake exposes an unbounded Box of the configured twelve values and invents no envelope.
        self.action_space = Box([-math.inf] * ACTION_SIZE, [math.inf] * ACTION_SIZE)
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self._seed = None
        self._rng = random.Random(0)  # placeholder: the bridge passes seed 0 for the first episode
        self._tick = 0
        self._observation = [0.0] * OBSERVATION_SIZE  # placeholder

    def reset(self, *, seed=None, options=None):
        """Start a new episode; ``options`` is accepted for the Gymnasium reset contract and has no effect."""
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        self._tick = 0
        # placeholder: three stand-in base values drawn from the seeded generator, then twelve zero last actions.
        self._observation = [round(self._rng.uniform(-1.0, 1.0), 6) for _ in range(BASE_VALUES)] + [0.0] * ACTION_SIZE
        return list(self._observation), {}

    def step(self, action):
        """Apply one twelve-value action and record it in the last-action tail of the reduced observation."""
        values = list(action)
        if len(values) != ACTION_SIZE:
            raise ValueError(f"the action must have {ACTION_SIZE} values, got {len(values)}")
        checked = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"the action values must be numbers, got {value!r}")
            checked.append(float(value))
        # Keep the three placeholder base values and replace the last-action tail with the applied action.
        self._observation = list(self._observation[:BASE_VALUES]) + checked
        self._tick += 1
        reward = 0.0  # placeholder: no reward term is modelled
        return list(self._observation), reward, False, False, {}

    def close(self):
        self._observation = []
