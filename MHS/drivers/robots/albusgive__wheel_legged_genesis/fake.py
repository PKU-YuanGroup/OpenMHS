"""Fake backend of the wheel-legged Genesis driver: a pure Python stand-in for ``WheelLeggedEnv``.

The upstream environment needs Genesis from its main branch, PyTorch, OpenCV and the repository's robot assets
(``README.md:11-13``, ``pyproject.toml:8-14``), none of which is installed where the gate runs.  This module
therefore implements only the public surface of ``WheelLeggedEnv`` that the driver calls: ``step`` and ``reset``
with the upstream five-tuple and two-tuple shapes.  It models one environment: the eight-value action vector, the
286-value observation layout (nine history rows of 28 values, the current 28-value slice and six commands), the
one-step action latency, the episode length and the time-out marker.

What is not modelled: Genesis, rigid-body dynamics, contacts, actuators, terrain, sensors, the upstream reward
terms, domain randomization and the auto-reset inside the upstream step.  Every number below is test data, not a
fact, a limit or a reference; each is marked ``# placeholder``.
"""

import math
import random

# placeholder: the eight actions of the configured robot (six leg joints and two wheel joints)
ACTION_DIM = 8
# placeholder: nine history rows of 28 values + the current 28-value slice + six commands
OBSERVATION_DIM = 286
# placeholder: three base angular velocity, three gravity, six joint positions, eight velocities and eight actions
SLICE_DIM = 28
# placeholder: the configured history length
HISTORY_LENGTH = 9
# placeholder: the configured command count
COMMAND_DIM = 6
# placeholder: 20 s of 0.01 s control periods
EPISODE_LENGTH = 2000
# placeholder: the training configuration's clip_actions
ACTION_CLIP = 100.0
# placeholder: the training configuration's joint action scale
JOINT_ACTION_SCALE = 0.5
# placeholder: the training configuration's wheel action scale
WHEEL_ACTION_SCALE = 10.0
# placeholder: the observation scale of the base angular velocity
ANG_VEL_SCALE = 0.25
# placeholder: the observation scale of the DOF velocities
DOF_VEL_SCALE = 0.05
# placeholder: how fast a joint follows its target in the stand-in model
ACTION_GAIN = 0.5
# placeholder: the width of the uniform draw of the initial joint positions
RESET_JITTER = 0.01
# placeholder: the stand-in reward scale
REWARD_SCALE = 0.001
# placeholder: the stand-in base yaw gain and the wheel integration period
YAW_GAIN = 0.1
WHEEL_PERIOD = 0.01


def _values(action):
    """The eight action values of a list or an array of shape [1, 8]."""
    if hasattr(action, "tolist"):
        action = action.tolist()
    if isinstance(action, (list, tuple)) and action and isinstance(action[0], (list, tuple)):
        action = action[0]
    values = [float(item) for item in action]
    if len(values) != ACTION_DIM:
        raise ValueError(f"action has {len(values)} values; the action buffer has {ACTION_DIM}")
    return values


def _clip(value):
    return max(-ACTION_CLIP, min(ACTION_CLIP, value))


class FakeWheelLeggedEnv:
    """The public surface of ``WheelLeggedEnv`` with a placeholder kinematic model instead of Genesis."""

    def __init__(self, **_options):
        self._options = dict(_options)
        self._episode = 0
        self._tick = 0
        self._episode_length = 0
        self._terminated = False
        self._last_actions = [0.0] * ACTION_DIM          # placeholder
        self._actions = [0.0] * ACTION_DIM               # placeholder
        self._dof_pos = [0.0] * ACTION_DIM               # placeholder
        self._dof_vel = [0.0] * ACTION_DIM               # placeholder
        self._base_ang_vel = [0.0, 0.0, 0.0]             # placeholder
        self._projected_gravity = [0.0, 0.0, -1.0]       # placeholder
        self._commands = [0.0] * COMMAND_DIM             # placeholder
        self._history = [[0.0] * SLICE_DIM for _ in range(HISTORY_LENGTH)]
        self._slice = list(self._build_slice())
        self._observation = self._build_observation()

    # -- the two public operations of WheelLeggedEnv ------------------------------------------------
    def reset(self):
        """Return one placeholder observation row [1, 286] and None, as ``WheelLeggedEnv.reset`` does."""
        self._episode += 1
        self._tick = 0
        self._episode_length = 0
        self._terminated = False
        self._last_actions = [0.0] * ACTION_DIM
        self._actions = [0.0] * ACTION_DIM
        self._dof_pos = [random.uniform(-RESET_JITTER, RESET_JITTER) for _ in range(ACTION_DIM)]
        self._dof_vel = [0.0] * ACTION_DIM
        self._base_ang_vel = [0.0, 0.0, 0.0]
        self._projected_gravity = [0.0, 0.0, -1.0]
        self._commands = [0.0] * COMMAND_DIM
        self._history = [[0.0] * SLICE_DIM for _ in range(HISTORY_LENGTH)]
        self._slice = list(self._build_slice())
        self._observation = self._build_observation()
        return [list(self._observation)], None

    def step(self, action):
        """Advance the placeholder state one tick and return the upstream five-tuple."""
        values = _values(action)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("action values must be finite")
        values = [_clip(value) for value in values]
        executed = list(self._last_actions)             # placeholder: one-step action latency
        for index in range(6):
            target = executed[index] * JOINT_ACTION_SCALE
            self._dof_pos[index] += (target - self._dof_pos[index]) * ACTION_GAIN
            self._dof_vel[index] = (target - self._dof_pos[index]) * ACTION_GAIN
        for index in range(6, ACTION_DIM):
            self._dof_vel[index] = executed[index] * WHEEL_ACTION_SCALE
            self._dof_pos[index] += self._dof_vel[index] * WHEEL_PERIOD
        self._base_ang_vel = [0.0, 0.0, YAW_GAIN * (executed[6] - executed[7])]
        self._actions = list(values)
        self._last_actions = list(values)
        self._tick += 1
        self._episode_length += 1
        self._terminated = self._episode_length > EPISODE_LENGTH
        self._slice = list(self._build_slice())
        self._observation = self._build_observation()
        reward = max(0.0, REWARD_SCALE * (0.0 if self._terminated else 1.0)
                     - 1e-6 * sum(value * value for value in values))   # placeholder
        extras = {"time_outs": [1.0 if self._terminated else 0.0], "episode": {}}
        self._history = self._history[1:] + [list(self._slice)]
        return [list(self._observation)], None, reward, [self._terminated], extras

    # -- helpers ------------------------------------------------------------------------------------
    def _build_slice(self):
        """The placeholder 28-value current slice of the configured observation."""
        values = [value * ANG_VEL_SCALE for value in self._base_ang_vel]     # placeholder
        values += list(self._projected_gravity)                              # placeholder
        values += [self._dof_pos[index] for index in range(6)]               # placeholder
        values += [self._dof_vel[index] * DOF_VEL_SCALE for index in range(ACTION_DIM)]
        values += list(self._actions)                                        # placeholder
        return values

    def _build_observation(self):
        """The placeholder 286-value row: nine history rows, the current slice and six commands."""
        values = []
        for row in self._history:
            values.extend(row)
        values.extend(self._slice)
        values.extend(self._commands)
        return values
