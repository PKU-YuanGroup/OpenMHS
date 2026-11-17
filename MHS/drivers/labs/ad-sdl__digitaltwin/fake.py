"""Fake backend of the digitaltwin driver: an analytic stand-in for the centrifuge Mimic environment.

Why a fake: the upstream package is an Isaac Lab 3.0.0 extension.  Importing it needs Isaac Lab, Isaac Sim, torch and
a Linux GPU host, and package code never imports the clone.  This module models only the interface the Gymnasium
bridge needs: a 16-element Box action in the order stated by
``tasks/centrifuge/tasks/src/rpl_centrifuge/openarm/mimic_env.py:13-21``, a bounded episode length derived from
``.../openarm/env_cfg.py:398-402`` and a seeded reset.  It is a pure Python kinematic echo, not a recording and not
the upstream environment: it has no physics, contacts, actuators, sensors, USD scene or termination terms.

The 16-element layout and the two gripper channels in [0, 1] are stated upstream.  The arm position and quaternion
bounds are **placeholders** because the clone does not state the Box bounds: they come from Isaac Lab's action manager,
which is outside the clone.  Every placeholder number below is marked ``# placeholder``; none of them is a Fact, a
Limit or a citation.  ``reset(seed)`` draws the placeholder start offsets from Python's ``random.Random``; the upstream
reset randomizes the USD scene with its own generator.

The public members are only the Gymnasium environment interface used by the bridge (``action_space``,
``observation_space``, ``reset``, ``step``, ``close``).  The native Mimic helper methods
(``get_robot_eef_pose``, ``target_eef_pose_to_action``, ``action_to_target_eef_pose``,
``actions_to_gripper_actions``, ``get_subtask_term_signals``) are not implemented; the fidelity ``gaps`` say so.

Nothing here talks to a device.
"""

import random

# mimic_env.py:13-21: the action tensor is 16-dimensional in a fixed order.
ACTION_DIM = 16
# mimic_env.py:18 and :21: both gripper channels are scalars in [0, 1].
GRIPPER_INDEXES = (7, 15)
GRIPPER_LOW, GRIPPER_HIGH = 0.0, 1.0
# env_cfg.py:399-402: decimation 5 and sim.dt 0.01 s, so one environment step is five physics steps (0.05 s).
DECIMATION = 5
PHYSICS_DT_S = 0.01
CONTROL_DT_S = DECIMATION * PHYSICS_DT_S
# env_cfg.py:400: episode_length_s = 30.0 s.  The fake truncates after 600 control steps.
EPISODE_LENGTH_S = 30.0
MAX_STEPS = int(round(EPISODE_LENGTH_S / CONTROL_DT_S))

# Placeholder bounds for the arm position and quaternion channels.  The clone configures absolute differential-IK
# actions but does not write the Box bounds (Isaac Lab's action manager builds them), so these are test data only.
ARM_LOW, ARM_HIGH = -1.0, 1.0  # placeholder
QUAT_LOW, QUAT_HIGH = -1.0, 1.0  # placeholder
# Placeholder start offsets and identity quaternion; the upstream reset randomizes a USD scene instead.
START_OFFSET = 0.01  # placeholder
START_QUAT = (0.0, 0.0, 0.0, 1.0)  # placeholder
START_GRIPPER = 0.0  # placeholder


def _bounds():
    """Return the per-channel low/high lists of the fake action and observation spaces."""
    low = []
    high = []
    for index in range(ACTION_DIM):
        if index in GRIPPER_INDEXES:
            low.append(GRIPPER_LOW)
            high.append(GRIPPER_HIGH)
        elif 3 <= index < 7 or 11 <= index < 15:
            low.append(QUAT_LOW)  # placeholder
            high.append(QUAT_HIGH)  # placeholder
        else:
            low.append(ARM_LOW)  # placeholder
            high.append(ARM_HIGH)  # placeholder
    return low, high


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a finite lower and upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.low):
            return False
        for item, low, high in zip(value, self.low, self.high):
            if isinstance(item, bool):
                return False
            try:
                number = float(item)
            except (TypeError, ValueError):
                return False
            if not (low <= number <= high):
                return False
        return True


class FakeCentrifugeMimicEnv:
    """A 16-element action echo with a seeded placeholder reset and a 600-step truncation."""

    def __init__(self, **_options):
        low, high = _bounds()
        self.action_space = Box(low, high)
        self.observation_space = Box(low, high)
        self._rng = random.Random()
        self._seed = None
        self._ticks = 0
        self._values = [0.0] * ACTION_DIM  # placeholder buffer, overwritten by reset
        self._closed = False

    def _start_values(self):
        values = [0.0] * ACTION_DIM  # placeholder buffer, filled below
        for index in range(3):
            values[index] = self._rng.uniform(-START_OFFSET, START_OFFSET)  # placeholder
            values[index + 8] = self._rng.uniform(-START_OFFSET, START_OFFSET)  # placeholder
        for index in (3, 11):
            values[index:index + 4] = list(START_QUAT)
        for index in GRIPPER_INDEXES:
            values[index] = START_GRIPPER
        return values

    def reset(self, *, seed=None, options=None):
        """Gymnasium reset: a supplied seed fixes the placeholder start offsets."""
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        elif self._seed is None:
            self._seed = self._rng.randrange(0, 2 ** 31)
        self._values = self._start_values()
        self._ticks = 0
        self._closed = False
        return list(self._values), {}

    def step(self, action):
        """Gymnasium step: echo the 16-element action, count one control step, truncate at episode length."""
        if not self.action_space.contains(action):
            raise ValueError(f"action {action!r} is outside the fake 16-element action space")
        self._values = [float(item) for item in action]
        self._ticks += 1
        terminated = False
        truncated = self._ticks >= MAX_STEPS
        reward = 0.0  # placeholder: the upstream configures no reward manager (env_cfg.py:395)
        return list(self._values), reward, terminated, truncated, {}

    def close(self):
        self._closed = True
