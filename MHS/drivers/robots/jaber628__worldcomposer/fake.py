"""Fake backend of the WorldComposer Tableware driver: a pure Python interface stand-in.

Why a fake: the registered task needs Isaac Sim, Isaac Lab, a CUDA GPU and the external ``Assets/`` dataset
(README.md:45-54 and :74-86), and package code never imports or runs the clone.  The gate therefore checks this
stand-in, which reproduces the parts of the Gymnasium contract the bridge reads: ``action_space`` and
``observation_space``, ``reset(seed, options)``, ``step(action)`` and ``close``.  The upstream class ``TablewareEnv``
inherits the rest of that interface from ``isaaclab.envs.DirectRLEnv`` and ``gymnasium.Env``, both outside the clone.

What this is not: the upstream environment.  It has no Isaac Sim, no rigid bodies, no contacts, no actuator, sensor
or noise model and no camera images.  The observation has the two keys of ``Tableware.py:110-113`` and six values
each, and on a step the joint positions are set directly from the action as a kinematic stand-in for the joint
position target of ``Tableware.py:97-101``.  The default joint positions are the ones ``Tableware_cfg.py:31-38``
configures; the reset randomization of ``Tableware.py:157`` onwards is not modelled.  The reward is the task's 0
(``Tableware.py:133-135``), and the time-out marks both terminated and truncated as ``Tableware.py:137-139`` does.
The action space is deliberately unbounded because the real space object is created by the external ``DirectRLEnv``
and was not inspected; the fake neither rejects nor clamps a finite action, so no action limit is published.
"""

import math

# Tableware_cfg.py:20: action_space = 6.
ACTION_SIZE = 6
# Tableware_cfg.py:21: observation_space = 6.
OBSERVATION_SIZE = 6
# Tableware_cfg.py:17, :18 and :25: decimation 1, episode_length_s 60 and dt 1/120 s.
TIMESTEP_S = 1.0 / 120.0
# placeholder: 60 s / (1/120 s) = 7200 control steps; the time limit itself is applied by the external DirectRLEnv.
MAX_EPISODE_STEPS = 7200
# Tableware_cfg.py:31-38 in the ACTION_NAMES order of lerobot.py:17-24 (radians of the SO101 joint positions).
DEFAULT_JOINT_POSITIONS = [-0.0363, -1.7135, 1.4979, -1.5, -0.085, -0.01176]


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeTablewareEnv:
    """One WorldComposer-Tableware-v0 environment without Isaac Sim: the contract, not the physics."""

    def __init__(self, **_options):
        # The action-space bounds are not in the clone (they are built by the external DirectRLEnv), so the fake
        # exposes an unbounded Box of the configured 6 values and invents no envelope.
        self.action_space = Box([-math.inf] * ACTION_SIZE, [math.inf] * ACTION_SIZE)
        self.observation_space = Dict({
            "action": Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE),
            "observation.state": Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE),
        })
        self._seed = None
        self._tick = 0
        self._episode = 0
        self._action = [0.0] * ACTION_SIZE
        self._joint_pos = list(DEFAULT_JOINT_POSITIONS)
        self._terminated = False
        self._truncated = False

    def reset(self, *, seed=None, options=None):
        """Start a new episode; ``options`` is accepted for the Gymnasium reset contract and has no effect."""
        if seed is not None:
            self._seed = int(seed)
        self._tick = 0
        self._episode += 1
        self._action = [0.0] * ACTION_SIZE
        self._joint_pos = list(DEFAULT_JOINT_POSITIONS)
        self._terminated = False
        self._truncated = False
        return self._observation(), {}

    def step(self, action):
        """Apply one six-value joint-position action and advance one control step."""
        values = list(action)
        if len(values) != ACTION_SIZE:
            raise ValueError(f"the action must have {ACTION_SIZE} values, got {len(values)}")
        checked = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"the action values must be numbers, got {value!r}")
            checked.append(float(value))
        self._action = checked
        # placeholder: kinematic stand-in for set_joint_position_target; no rigid-body dynamics are modelled.
        self._joint_pos = list(checked)
        self._tick += 1
        self._terminated = self._tick >= MAX_EPISODE_STEPS
        self._truncated = self._terminated
        return self._observation(), 0.0, self._terminated, self._truncated, {"tick": self._tick}

    def close(self):
        """Release the stand-in's state; the upstream close has the same role."""
        self._action = []
        self._joint_pos = []

    def _observation(self):
        return {"action": list(self._action), "observation.state": list(self._joint_pos)}
