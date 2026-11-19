"""Fake backend of the MuscleMimic MyoFullBody driver: a pure Python stand-in for ``MyoFullBody``.

The upstream environment needs MuJoCo, JAX, flax and the separate ``musclemimic_models`` package, and its model file
is not in this clone (``musclemimic/environments/humanoids/myofullbody.py:449-453``, ``pyproject.toml:29-70``);
none of that is installed or run where the gate runs.  This module therefore implements only the public surface the
driver calls, ``reset(key=None)`` and ``step(action)``, with the same return shapes as the repository's
``Mujoco.reset`` and ``Mujoco.step`` (``loco_mujoco/core/mujoco_base.py:194-228`` and ``:230-288``).

What is modelled: a tick counter, a placeholder muscle-excitation state and a placeholder observation row.  What is
not modelled: MuJoCo, MJX, Hill-type muscle dynamics, contacts, tendons, sensors, the observation composition, the
reward and the terminal handlers; the reset restores a fixed zero state.  The fake accepts any non-empty action width
because the real actuator count is model-dependent (``myofullbody.py:394-407``); the driver does not invent it.

Every number below is test data, not a fact, a limit or a reference; each is marked ``# placeholder``.
"""

import math

# placeholder: the length of the stand-in observation row; the real observation length is model-dependent
OBSERVATION_DIM = 8
# placeholder: how far one excitation value moves a stand-in observation entry
ACTION_GAIN = 0.01
# placeholder: scale of the stand-in reward
REWARD_SCALE = 0.01


def _values(action):
    """One flat action row from a list, a NumPy array or a nested row."""
    if hasattr(action, "tolist"):
        action = action.tolist()
    while isinstance(action, (list, tuple)) and action and isinstance(action[0], (list, tuple)):
        action = action[0]
    if not isinstance(action, (list, tuple)):
        raise ValueError("the action is not an array")
    return [float(value) for value in action]


class FakeMyoFullBody:
    """The public surface of ``MyoFullBody`` with a placeholder state instead of MuJoCo."""

    def __init__(self, **_options):
        self._options = dict(_options)
        self._tick = 0
        self._episode = 0
        # placeholder: the stand-in muscle-excitation and observation state
        self._state = [0.0] * OBSERVATION_DIM

    def reset(self, key=None):
        """Restore the placeholder state and return the initial observation row, as ``Mujoco.reset`` does."""
        # placeholder: the default reset state is all zeros; the native key is not used
        self._state = [0.0] * OBSERVATION_DIM
        self._tick = 0
        self._episode += 1
        return list(self._state)

    def step(self, action):
        """Advance the placeholder state one tick and return ``(obs, reward, absorbing, done, info)``."""
        values = _values(action)
        if not values:
            raise ValueError("the action row is empty")
        for index, value in enumerate(values):
            if not math.isfinite(value):
                raise ValueError("action values must be finite")
            if index < OBSERVATION_DIM:
                self._state[index] += math.tanh(value) * ACTION_GAIN  # placeholder
        self._tick += 1
        reward = -REWARD_SCALE * sum(abs(value) for value in values)  # placeholder
        return list(self._state), reward, False, False, {}
