"""Fake backend of the GenSim2 driver: a pure-Python kinematic stand-in for ``GenSimTaskWrapper``.

Why a fake: the upstream environment needs ``gym``, ``sapien==2.2.2``, a CUDA-capable SAPIEN renderer and the
asset tree (requirements.txt:24, gensim2/env/sapien/constructor.py:42), and package code never imports the clone.
This module re-implements only the wrapper's legacy Gym surface the bridge uses: ``reset``, ``step``, ``seed``,
``close``, ``get_observation``, ``dt``, ``horizon``, ``action_space`` and ``observation_space`` (gate G7 checks these
names against ``gensim2/env/wrappers.py:GenSimTaskWrapper``).

The action space (8 values in [-1, 1]), the observation width (15), the 50-step horizon and the 800 ms control period
are the upstream values (base_env.py:111-117 and :327-329, sim.py:80-84).  The start pose, target pose, joint values
and move fraction are test data and are marked ``placeholder``; they are not facts about any upstream task.  The fake
models a one-stage reach: the end-effector moves toward the commanded pose, the reward is the upstream
``l2_distance_reward`` shape (rewards.py:65-68), and the episode ends when the goal is reached or the horizon passes.
Differences from the SAPIEN environment are listed in the driver's fidelity ``gaps``.

Nothing here talks to a device.  ``make_env`` is the deployment factory for the real simulator; it imports the
installed upstream package only when called, so the fake itself still needs no upstream dependency.  The SDK reserves
``.native`` for a hardware backend, so the real environment factory lives here and the gate never calls it.
"""

import math
import random as _random

# Placeholders: the fake's own start pose, target pose and joint values.  They are not read from an upstream task or
# asset and must never be cited as a Fact or a Limit.
START_TCP = [0.3, 0.0, 0.7]                      # placeholder
START_QUAT = [1.0, 0.0, 0.0, 0.0]                # placeholder
START_QPOS = [0.0, -0.32, 0.0, -2.61799, 0.0, 2.23, 0.7854, 0.0, 0.0]  # placeholder
TARGET = [0.5, 0.0, 0.9]                         # placeholder
MOVE_FRACTION = 0.5                              # placeholder: share of the remaining distance closed per step
RANDOM_TCP_LOW = [0.2, -0.15, 0.6]               # placeholder
RANDOM_TCP_HIGH = [0.4, 0.15, 0.8]               # placeholder
RANDOM_TARGET_LOW = [0.4, -0.1, 0.8]             # placeholder
RANDOM_TARGET_HIGH = [0.6, 0.1, 1.0]             # placeholder

# gensim2/env/utils/rewards.py:65-68 (l2_distance_reward)
REWARD_SCALE = 3.0
REACH_THRESHOLD = 0.05


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeGenSimTaskEnv:
    """A kinematic stand-in for ``GenSimTaskWrapper``: one eight-value action, one 15-value state observation."""

    def __init__(self, **options):
        self.dt = 0.8                            # sim.py:81-84: 80 steps at 100 Hz
        self.horizon = 50                        # base_env.py:115-117
        self.cameras = {}
        self.gripper_state = 1
        self.action_space = Box([-1.0] * 8, [1.0] * 8)          # base_env.py:327-329 with action_dim 8
        self.observation_space = Box([-math.inf] * 15, [math.inf] * 15)  # base_env.py:304-319
        self._rng = _random.Random()
        self._tick = 0
        self._closed = False
        self.reset()

    def seed(self, seed=None):
        """``base_env.py:76-78``: replace the generator and return ``[seed]``."""
        self._rng = _random.Random(seed)
        return [seed]

    def reset(self, random=False):
        """The upstream wrapper accepts only ``random`` (wrappers.py:112); seed() is separate.

        The legacy Gymnasium bridge retries reset() after its unsupported seed/options arguments are refused;
        options['random'] is therefore not a protocol route to randomized native resets.
        """
        self._tick = 0
        self._closed = False
        if random:
            self._tcp = [self._rng.uniform(low, high)
                         for low, high in zip(RANDOM_TCP_LOW, RANDOM_TCP_HIGH)]      # placeholder
            self._target = [self._rng.uniform(low, high)
                            for low, high in zip(RANDOM_TARGET_LOW, RANDOM_TARGET_HIGH)]  # placeholder
        else:
            self._tcp = list(START_TCP)          # placeholder
            self._target = list(TARGET)          # placeholder
        self._quat = list(START_QUAT)            # placeholder
        self._qpos = list(START_QPOS)            # placeholder
        self.gripper_state = 1
        return self.get_observation()

    def step(self, action, eval=-1, eval_cam_names=None, whole_eps=False):
        """Move toward the commanded pose and return the legacy ``obs, reward, done, info`` tuple."""
        if len(action) != 8:
            raise ValueError(f"expected an 8-value action, got {len(action)} values")
        commanded = [float(value) for value in action]
        self._tcp = [current + MOVE_FRACTION * (wanted - current)      # placeholder fraction
                     for current, wanted in zip(self._tcp, commanded[:3])]
        quat = commanded[3:7]
        norm = math.sqrt(sum(value * value for value in quat))
        if norm > 1e-9:
            self._quat = [value / norm for value in quat]
        # sapien/env.py:424-435 writes integer openness, including negative targets, rather than a sign test.
        # placeholder: the kinematic fake immediately reaches that target; no finger dynamics are simulated.
        finger_target = int(commanded[7]) * 0.04
        self._qpos[-2:] = [finger_target, finger_target]
        self._tick += 1

        distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(self._tcp, self._target)))
        reward = 1.0 - math.tanh(REWARD_SCALE * distance)               # rewards.py:65-68
        success = distance < REACH_THRESHOLD                            # rewards.py:65-68
        done = bool((success and not whole_eps) or self._tick >= self.horizon)
        info = {
            "success": bool(success),
            "current_task": "reach",
            "current_task_description": "Reach the target pose",
            "next_task": "reach",
            "next_task_description": "Reach the target pose",
            "task_step": 0,
            "task_progress": [1.0 if success else 0.0],
            "all_done": bool(success),
            "sub_task_success": bool(success),
        }
        return self.get_observation(), float(reward), done, info

    def get_observation(self):
        """``base_env.py:304-319``: position (3), quaternion (4), first eight joint positions (8)."""
        return ([float(value) for value in self._tcp]
                + [float(value) for value in self._quat]
                + [float(value) for value in self._qpos[:-1]])

    def close(self):
        """Fake-only cleanup; upstream wrapper.close calls task.close, absent on the shipped base tasks.

        This convenience is not a model of successful SAPIEN cleanup.  The declared live backend remains blocked.
        """
        self._closed = True


def make_env(task_name=None, **kwargs):
    """Deployment factory for the real simulator: a ``GenSimTaskWrapper`` built by the installed upstream package.

    The gate never calls this (the ``sim`` backend is not the acceptance backend), and the upstream import is inside
    the function so the fake module needs no upstream dependency.  ``task_name`` is required: the upstream factory
    evaluates that task class (gensim2/env/create_task.py:20-21), and choosing a default would claim a task the
    operator did not select.
    """
    if not isinstance(task_name, str) or not task_name:
        raise ValueError("make_env needs task_name=<a task class of gensim2.env.task>, for example 'TurnOnFaucet'")
    from gensim2.env.create_task import create_gensim

    return create_gensim(task_name, **kwargs)
