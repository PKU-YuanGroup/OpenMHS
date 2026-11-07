"""Fake backend of the Open Duck Mini driver: a pure Python stand-in for ``env_humanoid:BDXEnv``.

Why a fake: the gate never imports or runs the clone, and the upstream environment cannot be opened here anyway:
it imports ``placo`` and builds its MuJoCo scene from the absolute path
``/home/antoine/MISC/mini_BDX/mini_bdx/robots/bdx/scene.xml`` (``experiments/RL/env_humanoid.py:4`` and ``:105``),
outside the clone.  This module models the declared contract of ``experiments/RL/env_humanoid.py:18`` in plain
Python: a 41-value observation box (``:92``), the 13 joint targets the class's action table lists (``:24-36``),
the healthy height range (``:97``) and the reward weights and formula (``:99-101`` and ``:157-165``).

The fake is kinematic, not MuJoCo: an action sets the 13 joint positions and the joint velocities are their
per-tick differences.  The base is held at the BDX model's start height ``0.17`` (``mini_bdx/robots/bdx/robot.xml:69``)
and upright, and the two foot contact flags are constants.  The public members are the ones a Gymnasium env
exposes here: ``action_space``, ``observation_space``, ``reset``, ``step`` and ``close``.  ``reset`` and ``close``
are inherited from gymnasium's ``MujocoEnv`` upstream, which is outside the clone, so gate G7 can only warn that
they occur elsewhere in the repository.

Differences from the upstream environment, all listed in the fidelity ``gaps`` of ``driver.py``: no dynamics,
contacts, actuator or noise model; the initial noise uses Python's ``random.Random`` where upstream uses numpy's
generator; the action box boundaries are placeholder test data because the real box is built by MujocoEnv; and
neck_pitch and the two antenna actuators of the model are not covered.

Nothing here talks to a device.
"""

import math
import random

#: The declared observation is 41 values (env_humanoid.py:92): qpos (7 free-joint + J joints),
#: qvel (6 free-joint + J joints) and the two foot contact flags, so J = (41 - 2 - 7 - 6) / 2.
#: The 13-joint count is a placeholder of this kinematic stand-in, not a sourced limit.
N_JOINTS = 13                                        # placeholder
QPOS_DIM = 7 + N_JOINTS
QVEL_DIM = 6 + N_JOINTS
OBS_DIM = QPOS_DIM + QVEL_DIM + 2

# env_humanoid.py:97: the healthy base height range, in metres
HEALTHY_Z_MIN = 0.1
HEALTHY_Z_MAX = 0.2
# env_humanoid.py:99-101: the reward weights used by the effective reward formula
CTRL_COST_WEIGHT = 0.3
HEALTHY_REWARD = 5.0
# env_humanoid.py:181-182: the reset noise is uniform in [-1e-2, 1e-2]
RESET_NOISE = 1e-2
# mini_bdx/robots/bdx/robot.xml:69: the base body starts at z=0.17; identity quaternion
BASE_Z = 0.17
BASE_QPOS = [0.0, 0.0, BASE_Z, 1.0, 0.0, 0.0, 0.0]
# placeholder test data: the real action box is constructed by gymnasium's external MujocoEnv
ACTION_LOW, ACTION_HIGH = -1.0, 1.0                  # placeholder
CONTACT = 1.0                                        # placeholder


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float64"


class FakeBDXEnv:
    """A kinematic stand-in for ``BDXEnv``: ``reset(seed, options)`` and ``step(action)`` on a flat state."""

    def __init__(self, **kwargs):
        del kwargs
        # placeholder: the external MujocoEnv builds this box from the model's actuators
        self.action_space = Box([ACTION_LOW] * N_JOINTS, [ACTION_HIGH] * N_JOINTS)
        # env_humanoid.py:92: Box(-inf, inf, shape=(41,), dtype=float64)
        self.observation_space = Box([-math.inf] * OBS_DIM, [math.inf] * OBS_DIM)
        self._rng = random.Random()
        self._qpos = list(BASE_QPOS) + [0.0] * N_JOINTS
        self._qvel = [0.0] * QVEL_DIM
        self._tick = 0

    def reset(self, *, seed=None, options=None):
        """A full reset with the upstream uniform noise (env_humanoid.py:181-189)."""
        del options
        if seed is not None:
            self._rng = random.Random(seed)
        self._qpos = list(BASE_QPOS) + [0.0] * N_JOINTS
        self._qvel = [0.0] * QVEL_DIM
        for index in range(QPOS_DIM):
            self._qpos[index] += self._rng.uniform(-RESET_NOISE, RESET_NOISE)
        for index in range(QVEL_DIM):
            self._qvel[index] += self._rng.uniform(-RESET_NOISE, RESET_NOISE)
        self._tick = 0
        return self._observation(), {}

    def step(self, action):
        """Set the joint targets, update the joint velocities and return the upstream reward shape."""
        values = [float(value) for value in action]
        if len(values) != N_JOINTS:
            raise ValueError(f"BDXEnv expects {N_JOINTS} action values, got {len(values)}")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("BDXEnv action values must be finite")
        qpos = list(self._qpos)
        qvel = list(self._qvel)
        for index, value in enumerate(values):
            qpos[7 + index] = value
            qvel[6 + index] = value - self._qpos[7 + index]
        self._qpos = qpos
        self._qvel = qvel
        self._tick += 1
        # env_humanoid.py:157-165: healthy_reward - ctrl_cost - moving_cost; the fake base has no xy motion
        control_cost = CTRL_COST_WEIGHT * sum(value * value for value in values)
        moving_cost = 2.0 * abs(self._qvel[0])       # the upstream expression adds |x_velocity| twice
        reward = HEALTHY_REWARD - control_cost - moving_cost
        return self._observation(), reward, self._terminated(), False, {}

    def close(self):
        return None

    def _observation(self):
        # env_humanoid.py:210-216: qpos, qvel, then the left and right foot contact flags
        return list(self._qpos) + list(self._qvel) + [CONTACT, CONTACT]

    def _terminated(self):
        # env_humanoid.py:133-145: unhealthy base height; the fake base is never tilted
        return not (HEALTHY_Z_MIN < self._qpos[2] < HEALTHY_Z_MAX)
