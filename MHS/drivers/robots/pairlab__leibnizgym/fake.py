"""Fake backend of the LeibnizGym TriFinger driver: a pure Python stand-in for ``TrifingerEnv``.

The upstream environment needs IsaacGym Preview Release 2, PyTorch and a configuration dict
(``README.md:7-17``, ``leibnizgym/envs/trifinger/trifinger_env.py:258-277``), none of which is installed where the
gate runs.  This module therefore implements only the public surface of ``TrifingerEnv`` that the driver calls
(``reset``, ``step``, ``seed``, ``close`` and the ``get_*_dim``/``get_*_shape``/``get_num_instances`` accessors), with
a small deterministic kinematic stand-in instead of IsaacGym.

What is modelled: one environment instance, a nine-value normalized joint command, a tick counter and a 41-value
observation row (the default observation spec: robot_q 9, robot_u 9, object_q 7, object_q_des 7 and command 9).  What
is not modelled: IsaacGym, PhysX, rigid-body dynamics, contacts, actuators, sensors, the upstream reward terms and
the auto-reset at episode_length; a reset draws placeholder values from Python's ``random.Random`` instead.  Every
number below is test data, not a fact, a limit or a reference; each is marked ``# placeholder``.
"""

import math
import random

# placeholder: the nine action values of the default position command mode
ACTION_DIM = 9
# placeholder: robot_q 9 + robot_u 9 + object_q 7 + object_q_des 7 + command 9
OBSERVATION_DIM = 41
# placeholder: half-width of the uniform reset draw
RESET_HALF_WIDTH = 0.05
# placeholder: how far a joint moves per unit of a tanh-squashed action value
ACTION_GAIN = 0.01
# placeholder: scale of the stand-in reward
REWARD_SCALE = 0.01


def _values(action):
    """The nine action values of a list or an array of shape [1, 9]."""
    if hasattr(action, "tolist"):
        action = action.tolist()
    if isinstance(action, (list, tuple)) and action and isinstance(action[0], (list, tuple)):
        action = action[0]
    values = [float(item) for item in action]
    if len(values) != ACTION_DIM:
        raise ValueError(f"action has {len(values)} values; the action buffer has {ACTION_DIM}")
    return values


class FakeTrifingerEnv:
    """The public surface of ``TrifingerEnv`` with a placeholder kinematic model instead of IsaacGym."""

    def __init__(self, **_options):
        self._options = dict(_options)
        self._rng = random.Random(0)                         # placeholder
        self._seed = 0                                       # placeholder
        self._episode = 0
        self._tick = 0
        self._closed = False
        # placeholder: the joint positions, joint velocities and object pose of the one instance
        self._joints = [0.0] * ACTION_DIM
        self._velocities = [0.0] * ACTION_DIM
        self._object = [0.0] * 7
        self._object_goal = [0.0] * 7

    # -- properties the upstream base class exposes ---------------------------
    def get_num_instances(self) -> int:
        return 1

    def get_obs_dim(self) -> int:
        return OBSERVATION_DIM

    def get_action_dim(self) -> int:
        return ACTION_DIM

    def get_obs_shape(self):
        return (1, OBSERVATION_DIM)

    def get_action_shape(self):
        return (1, ACTION_DIM)

    # -- operations -----------------------------------------------------------
    def seed(self, seed=None):
        """``TrifingerEnv.seed``: reseed the generator a reset draws from."""
        self._seed = 0 if seed is None else int(seed)       # placeholder: None is mapped to 0
        self._rng = random.Random(self._seed)

    def reset(self):
        """Return one placeholder observation row [1, 41], as ``TrifingerEnv.reset`` returns [N, obs_dim]."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self._episode += 1
        self._tick = 0
        self._joints = [self._rng.uniform(-RESET_HALF_WIDTH, RESET_HALF_WIDTH) for _ in range(ACTION_DIM)]
        self._velocities = [0.0] * ACTION_DIM               # placeholder
        self._object = [self._rng.uniform(-RESET_HALF_WIDTH, RESET_HALF_WIDTH) for _ in range(7)]
        self._object_goal = [0.0] * 7                       # placeholder
        return [self._observation()]

    def step(self, action):
        """Advance the placeholder state one tick and return ``(observation, reward, done, info)``."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = _values(action)
        for index, value in enumerate(values):
            if not math.isfinite(value):
                raise ValueError("action values must be finite")
            self._joints[index] += math.tanh(value) * ACTION_GAIN   # placeholder
            self._velocities[index] = math.tanh(value) * ACTION_GAIN  # placeholder
        self._tick += 1
        reward = -REWARD_SCALE * sum(abs(value) for value in values)  # placeholder
        return [self._observation()], reward, False, {}

    def close(self):
        self._closed = True

    # -- helpers --------------------------------------------------------------
    def _observation(self):
        """The placeholder 41-value row of the default observation spec."""
        return (list(self._joints) + list(self._velocities) + list(self._object)
                + list(self._object_goal) + [0.0] * ACTION_DIM)
