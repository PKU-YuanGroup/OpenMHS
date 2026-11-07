"""Fake backend of the Matterix Beakers driver: a pure Python stand-in for the registered Gymnasium environment.

The upstream environment is ``Matterix-Test-Beakers-Franka-v1``, whose entry point is
``matterix.envs:MatterixBaseEnv`` (the class the driver names as ``native``).  It needs Isaac Sim 5.0, Isaac Lab 3.0,
a GPU and a configuration object built by ``isaaclab_tasks.utils.parse_env_cfg`` (README.md:27-39, scripts/
random_agent.py:60-64), so it cannot be imported or constructed where the gate runs.  This module therefore
re-implements the public Gymnasium surface the bridge uses (gate G7: ``reset``, ``step`` and ``close`` exist on
``MatterixBaseEnv``) with duck-typed ``Dict``/``Box`` spaces, and provides a small deterministic kinematic model.

What is modelled: two 3-vector end-effector positions in a ``policy`` observation group (the same terms the task
declares, ``ee_pos_robot`` and ``ee_pos_robot2``; test_franka_beakers.py:29-34 and observations.py:49-53) and a
16-value action vector (two Franka arms, seven joint values plus one gripper value each, the action terms of
``FRANKA_PANDA_CFG`` at franka_arms.py:100-105 and of the IK arm at :322-333).  One ``step`` is one
environment/control step, it is not one physics step: Matterix's default decimation is 5, so one step advances five
times the physics timestep.

What is not modelled (all listed in the fidelity ``gaps`` of driver.py): no Isaac Sim, no PhysX, no Franka asset, no
beaker or table, no contacts, gravity, actuators or sensors, and no wall-clock pacing.  The numbers below are test
data only, marked ``# placeholder``; none of them is a fact, a limit or a reference.
"""

import math
import random

# placeholder: the action vector of the Beakers task (2 arms x (7 joint position values + 1 binary gripper value))
ACTION_DIM = 16
# placeholder: the two observation terms of the task's policy group, each three coordinates (observations.py:49-53)
OBSERVATION_TERMS = ("ee_pos_robot", "ee_pos_robot2")
# placeholder: how far the fake end effectors move per unit of a tanh-squashed action value
ACTION_GAIN = 0.01
# placeholder: the random offset of a fresh reset
RESET_JITTER = 0.02
# placeholder: ceil(episode_length_s / step_dt) = ceil(30 s / (5 * 1/60 s)) = 360, from the upstream defaults
MAX_EPISODE_STEPS = 360
# placeholder: the reward the fake reports; the upstream task configures no reward term
REWARD = 0.0


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: ``low``/``high`` (nested lists) and a batch shape."""

    def __init__(self, low, high):
        self.low = low
        self.high = high
        self.shape = _shape_of(low)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: named subspaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _shape_of(value):
    shape = []
    while isinstance(value, list):
        shape.append(len(value))
        value = value[0] if value else None
    return tuple(shape)


def _batch(low, high, count, width):
    """A batched Box of ``count`` environments, each with ``width`` values."""

    return Box([[low] * width for _ in range(count)], [[high] * width for _ in range(count)])


class FakeMatterixEnv:
    """The public surface of ``MatterixBaseEnv`` with a small kinematic model instead of Isaac Sim.

    ``reset(seed, env_ids, options)`` and ``step(action)`` follow the signatures of the upstream class
    (matterix_base_env.py:215 and :501); ``env_ids`` and ``options`` are accepted for compatibility and ignored, as
    the bridge only serves the one environment this fake owns.
    """

    def __init__(self, **options):
        self._options = dict(options)
        self.action_space = _batch(-math.inf, math.inf, 1, ACTION_DIM)              # placeholder: unbounded Box
        self.observation_space = Dict({                                              # placeholder: one policy group
            "policy": Dict({
                term: _batch(-math.inf, math.inf, 1, 3) for term in OBSERVATION_TERMS
            })
        })
        self._rng = random.Random(0)                                                 # placeholder
        self._seed = None
        self._episode = 0
        self._elapsed_steps = 0
        self._joints = [0.0] * ACTION_DIM
        self._closed = False

    def reset(self, seed=None, env_ids=None, options=None):
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        self._episode += 1
        self._elapsed_steps = 0
        self._joints = [self._rng.uniform(-RESET_JITTER, RESET_JITTER) for _ in range(ACTION_DIM)]
        return self._observation(), {"episode": self._episode}

    def step(self, action):
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = list(action)
        if len(values) != ACTION_DIM:
            raise ValueError(f"action has {len(values)} values; the action space has {ACTION_DIM}")
        for index, value in enumerate(values):
            number = float(value)
            if not math.isfinite(number):
                raise ValueError("action values must be finite")
            self._joints[index] += math.tanh(number) * ACTION_GAIN
        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        return self._observation(), REWARD, False, truncated, {}

    def close(self):
        self._closed = True

    def _observation(self):
        """The batched observation of the one environment, shaped like the task's non-concatenated policy group."""

        # The first arm owns the first eight action values and the second arm the last eight (placeholder indices).
        first = self._joints[0:3]
        second = self._joints[8:11]
        return {"policy": {
            "ee_pos_robot": [list(first)],
            "ee_pos_robot2": [list(second)],
        }}
