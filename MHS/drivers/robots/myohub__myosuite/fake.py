"""Fake backend for gh.myohub/myosuite: a pure Python stand-in for the Baoding challenge environment.

Why a fake: the gate runs without MyoSuite, MuJoCo, gymnasium or numpy (the clone imports all of them at module
import), and package code never imports or runs the clone.  This module serves the interface of
``myosuite.envs.myo.tasks.challenge.baoding:BaodingEnv`` (the class the driver names as ``native``) through the
public members that class has: ``reset``, ``step``, ``close`` and the ``dt`` property (gate G7).  The two space
objects duck-type ``gymnasium.spaces.Box`` (the bridge reads ``low``, ``high``, ``shape`` and ``dtype``).

What this is not: the MyoSuite environment.  It does not load MuJoCo, contacts, tendons, muscles or a renderer.
The observation vector has the same shape as the real one, but its values are a kinematic placeholder: the
dynamics of the real model and any trajectory are not reproduced.  These differences are listed in the driver's
fidelity ``gaps``.  Every numeric constant below is test data and is marked ``# placeholder``; none of them is a
fact, a limit or a citation.  The step limit repeats the ``max_episode_steps=200`` of the registration at
``myosuite/envs/myo/tasks/challenge/__init__.py:503`` so that a fake episode ends when the wrapped gymnasium
environment ends.

Nothing here talks to a device.
"""

from __future__ import annotations

import math
import random

# placeholder: 39 muscles in the hand model's actuator block (myohand_assets.xml:499-578)
N_ACT = 39
# placeholder: 23 hand hinge joints in myohand_body.xml, before the two balls' free joints
N_HAND = 23
# placeholder: 23 hand coordinates + 2 balls * (position 3 + velocity 3) + 2 targets * (position 3 + error 3) + 39 act
N_OBS = 86
# placeholder: registration max_episode_steps (myosuite/envs/myo/tasks/challenge/__init__.py:503)
MAX_EPISODE_STEPS = 200
# placeholder: nominal control interval (model timestep 0.0025 s * frame_skip 10; myohand_baoding.xml:14, baoding.py:141)
NOMINAL_DT_S = 0.025
# placeholder: start data for the fake's two balls, in metres
BALL1_START = (-0.227, -0.511, 1.452)
BALL2_START = (-0.256, -0.552, 1.442)
# placeholder: orbit radii of the fake's target sites, in metres
TARGET_X_RADIUS = 0.025
TARGET_Y_RADIUS = 0.028
# placeholder: scale of the fake's kinematic ball response to an action, in metres per unit action
BALL_STEP_M = 0.0005
# placeholder: drop height of the task (a constructor option), in metres
DROP_TH = 1.25


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        values = list(value) if isinstance(value, (list, tuple)) else [value]
        return len(values) == len(self.low) and all(
            float(low) <= float(item) <= float(high) for item, low, high in zip(values, self.low, self.high)
        )


class FakeBaodingEnv:
    """A small kinematic stand-in for ``BaodingEnv``: no MuJoCo, no contact model and no rendering."""

    def __init__(
        self,
        model_path: str = "",
        obsd_model_path: str | None = None,
        seed: int | None = None,
        frame_skip: int = 10,
        drop_th: float = DROP_TH,
        proximity_th: float = 0.015,
        goal_time_period: tuple = (5, 5),
        goal_xrange: tuple = (0.025, 0.025),
        goal_yrange: tuple = (0.028, 0.028),
        obj_size_range: tuple | None = None,
        obj_mass_range: tuple | None = None,
        obj_friction_change=None,
        task_choice: str = "fixed",
        obs_keys: list | None = None,
        weighted_reward_keys: dict | None = None,
        normalize_act: bool = True,
        **kwargs,
    ) -> None:
        # placeholder: the constructor signature mirrors BaodingEnv; the data below is test data.
        self.model_path = model_path
        self.obsd_model_path = obsd_model_path
        self.frame_skip = int(frame_skip)
        self.drop_th = float(drop_th)
        self.proximity_th = float(proximity_th)
        self.goal_time_period = goal_time_period
        self.goal_xrange = goal_xrange
        self.goal_yrange = goal_yrange
        self.obj_size_range = obj_size_range
        self.obj_mass_range = obj_mass_range
        self.obj_friction_change = obj_friction_change
        self.task_choice = task_choice
        self.obs_keys = list(obs_keys) if obs_keys is not None else [
            "hand_pos", "object1_pos", "object1_velp", "object2_pos", "object2_velp",
            "target1_pos", "target2_pos", "target1_err", "target2_err",
        ]
        self.rwd_keys_wt = dict(weighted_reward_keys or {"pos_dist_1": 5.0, "pos_dist_2": 5.0})
        self.normalize_act = bool(normalize_act)
        self.action_space = Box([-1.0] * N_ACT, [1.0] * N_ACT, shape=(N_ACT,))
        self.observation_space = Box([-math.inf] * N_OBS, [math.inf] * N_OBS, shape=(N_OBS,))
        self._rng = random.Random(seed)
        self._closed = False
        self._elapsed = 0
        self._act = [0.0] * N_ACT
        self._ball1 = list(BALL1_START)
        self._ball2 = list(BALL2_START)
        self._target1 = list(self._ball1)
        self._target2 = list(self._ball2)

    @property
    def dt(self) -> float:
        """Control interval of one fake step, in seconds (the real class has the same property)."""

        return NOMINAL_DT_S

    def reset(self, seed: int | None = None, options: dict | None = None, **kwargs):
        """Reset the fake episode; ``options`` is accepted but, like the upstream class, unused."""

        if self._closed:
            raise RuntimeError("the fake Baoding environment is closed")
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._elapsed = 0
        self._act = [0.0] * N_ACT
        # placeholder: a small seed-dependent offset, so two seeds start different episodes
        offset = self._rng.uniform(-0.001, 0.001)
        self._ball1 = [BALL1_START[0] + offset, BALL1_START[1], BALL1_START[2]]
        self._ball2 = [BALL2_START[0] - offset, BALL2_START[1], BALL2_START[2]]
        self._update_targets()
        return self._observation(), {}

    def step(self, action, **kwargs):
        """Advance the fake by one control step and return the Gymnasium five-tuple."""

        if self._closed:
            raise RuntimeError("the fake Baoding environment is closed")
        values = _action_vector(action)
        # placeholder: the fake moves each ball in x and y only, so its z never falls below drop_th
        for index in (0, 1):
            self._ball1[index] += BALL_STEP_M * values[index]
            self._ball2[index] += BALL_STEP_M * values[index + 3]
        self._act = values
        self._elapsed += 1
        self._update_targets()
        reward = self._reward()
        truncated = self._elapsed >= MAX_EPISODE_STEPS
        return self._observation(), reward, False, truncated, {}

    def close(self) -> None:
        """Mark the fake environment closed (no device or renderer is held)."""

        self._closed = True

    def _update_targets(self) -> None:
        # placeholder: a circular orbit at the model's nominal target radii
        phase = self._elapsed * 0.01
        self._target1 = [
            self._ball1[0] + TARGET_X_RADIUS * math.cos(phase),
            self._ball1[1] + TARGET_Y_RADIUS * math.sin(phase),
            self._ball1[2],
        ]
        self._target2 = [
            self._ball2[0] + TARGET_X_RADIUS * math.cos(phase + math.pi),
            self._ball2[1] + TARGET_Y_RADIUS * math.sin(phase + math.pi),
            self._ball2[2],
        ]

    def _reward(self) -> float:
        # placeholder: the negative sum of the two target distances, a finite stand-in for the real dense reward
        error1 = _difference(self._target1, self._ball1)
        error2 = _difference(self._target2, self._ball2)
        return -(_norm(error1) + _norm(error2))

    def _observation(self) -> list[float]:
        error1 = _difference(self._target1, self._ball1)
        error2 = _difference(self._target2, self._ball2)
        # placeholder: the order and lengths follow BaodingEnv._get_obs_dict and the default obs_keys
        values = (
            [0.0] * N_HAND
            + list(self._ball1) + [0.0, 0.0, 0.0]
            + list(self._ball2) + [0.0, 0.0, 0.0]
            + list(self._target1) + list(self._target2)
            + error1 + error2
            + list(self._act)
        )
        return [float(value) for value in values]


def _action_vector(action) -> list[float]:
    """Clip ``action`` to the fake's normalized action space, as the upstream class does."""

    values = list(action)
    if len(values) != N_ACT:
        raise ValueError(f"expected {N_ACT} action values, got {len(values)}")
    return [min(1.0, max(-1.0, float(value))) for value in values]


def _difference(first, second) -> list[float]:
    return [float(a) - float(b) for a, b in zip(first, second)]


def _norm(values) -> float:
    return math.sqrt(sum(float(value) * float(value) for value in values))
