"""Fake backend of the PlasticineLab driver: a pure Python stand-in for the Move-v1 environment.

Why a fake: the upstream clone needs Taichi, the legacy ``gym`` package, numpy and a GPU, and package code never
imports the clone; the gate also never imports the upstream package.  This module re-implements the public surface
of ``plb.envs.env:PlasticineEnv`` (the class the driver names as ``native``) that the bridge drives: ``reset()`` and
``step(action)``, plus the ``action_space`` and ``observation_space`` attributes the class assigns in ``__init__``
(gate G7).  The two space classes duck-type the legacy ``gym.spaces.Box`` the bridge reads (``low``, ``high``,
``shape``).  Constants copied from the clone cite their line; every start position and canned value of this
stand-in is fake test data and is marked ``# placeholder``.

What this is not: the upstream MPM solver.  It keeps the real Move-v1 array length (200 observed particles x 6
position/velocity values plus 2 primitives x 7 state values = 1214) but the particle values are placeholders, only
the primitive positions move (by ``action * 0.01``), the reward is always 0.0 and there is no soft-body
deformation, contact, friction, gravity or rendering.  The driver's fidelity ``gaps`` say all of this.

Nothing here talks to a device.
"""

import math

# ---------------------------------------------------------------------------
# Copied from the clone at ac1a2f7b0bbbe88706b51bf3aa9d72483e1d05b6.
# ---------------------------------------------------------------------------
MOVE = "plb/envs/move.yml"
N_PRIMITIVES = 2                              # two Sphere primitives (plb/envs/move.yml:10-26)
ACTION_PER_PRIMITIVE = 3                      # each declares action.dim 3 (plb/envs/move.yml:17, :25)
ACTION_DIM = N_PRIMITIVES * ACTION_PER_PRIMITIVE
ACTION_SCALE = 0.01                           # action.scale of both primitives (plb/envs/move.yml:18, :26)
ACTION_LOW, ACTION_HIGH = -1.0, 1.0           # Box(-1, 1) action space (plb/envs/env.py:26)
OBSERVED_PARTICLES = 200                      # ENV.n_observed_particles (plb/config/default_config.py:72)
PARTICLE_DIM = 3                              # SIMULATOR.dim is 3 (plb/config/default_config.py:13)
PRIMITIVE_STATE_DIM = 7                       # 3 position + 4 quaternion (plb/engine/primitive/primive_base.py:130-146)
OBSERVATION_DIM = 2 * OBSERVED_PARTICLES * PARTICLE_DIM + N_PRIMITIVES * PRIMITIVE_STATE_DIM
LOWER_BOUND, UPPER_BOUND = 0.0, 1.0           # Primitive xyz_limit (plb/engine/primitive/primive_base.py:216-217)
MAX_EPISODE_STEPS = 50                        # gym.register max_episode_steps (plb/envs/__init__.py:12)

# ---------------------------------------------------------------------------
# Test data of this stand-in, not facts of the upstream environment.
# ---------------------------------------------------------------------------
PLASTICINE_CENTER = (0.6757143040494873, 0.5619162002773135, 0.7515980438048129)  # placeholder: move.yml:8
INITIAL_PRIMITIVES = (                        # placeholder: move.yml:13, :21
    (0.5757143040494873, 0.5619162002773135, 0.7515980438048129),  # placeholder
    (0.7757143040494873, 0.5619162002773135, 0.7515980438048129),  # placeholder
)
INITIAL_ROTATION = (1.0, 0.0, 0.0, 0.0)       # placeholder: Primitive.default_config init_rot (primive_base.py:214)
INITIAL_VELOCITY = (0.0, 0.0, 0.0)            # placeholder: a reset zeroes the particle velocity (env.py:29)
REWARD = 0.0                                  # placeholder: the fake does not model the loss reward


class Box:
    """Duck-typed ``gym.spaces.Box``: a low and a high per element and the flat shape the bridge reads."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float64"


class FakePlasticineEnv:
    """The subset of ``PlasticineEnv`` the bridge drives: ``reset()`` and ``step(action)``."""

    def __init__(self, **_options):
        self.action_space = Box([ACTION_LOW] * ACTION_DIM, [ACTION_HIGH] * ACTION_DIM)   # env.py:26
        self.observation_space = Box([-math.inf] * OBSERVATION_DIM,
                                     [math.inf] * OBSERVATION_DIM)                      # env.py:25
        self._particle_x = []
        self._particle_v = []
        self._primitive_x = []
        self._primitive_rot = []
        self._elapsed_steps = 0
        self.reset()

    def reset(self):
        """Restore the fixed start state and return the observation, as ``PlasticineEnv.reset`` does (env.py:28-31)."""

        self._particle_x = [list(PLASTICINE_CENTER) for _ in range(OBSERVED_PARTICLES)]   # placeholder
        self._particle_v = [list(INITIAL_VELOCITY) for _ in range(OBSERVED_PARTICLES)]    # placeholder
        self._primitive_x = [list(position) for position in INITIAL_PRIMITIVES]           # placeholder
        self._primitive_rot = [list(INITIAL_ROTATION) for _ in range(N_PRIMITIVES)]       # placeholder
        self._elapsed_steps = 0
        return self._get_obs()

    def step(self, action):
        """Move the primitives by ``action * scale`` and truncate at the registered 50-step limit."""

        values = list(action)
        if len(values) != ACTION_DIM:
            raise ValueError(f"Move-v1 expects {ACTION_DIM} action values, got {len(values)}")
        # Primitives.set_action clips every element (primitives.py:290-294).
        values = [max(ACTION_LOW, min(ACTION_HIGH, float(value))) for value in values]
        for primitive in range(N_PRIMITIVES):
            for axis in range(ACTION_PER_PRIMITIVE):
                index = primitive * ACTION_PER_PRIMITIVE + axis
                moved = self._primitive_x[primitive][axis] + values[index] * ACTION_SCALE
                # forward_kinematics clamps the position to the primitive's xyz_limit (primive_base.py:118-119).
                self._primitive_x[primitive][axis] = max(LOWER_BOUND, min(UPPER_BOUND, moved))
        self._elapsed_steps += 1
        # The FakePlasticineEnv is a stand-in for the registered env, so the gym TimeLimit of 50 steps is modelled
        # (plb/envs/__init__.py:12); PlasticineEnv.step itself always returns done=False (env.py:57).
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        return self._get_obs(), REWARD, False, truncated, {}

    def _get_obs(self):
        """The observation layout of ``PlasticineEnv._get_obs`` (env.py:33-41), with placeholder particle data."""

        values = []
        for index in range(OBSERVED_PARTICLES):
            values.extend(self._particle_x[index])
            values.extend(self._particle_v[index])
        for primitive in range(N_PRIMITIVES):
            values.extend(self._primitive_x[primitive])
            values.extend(self._primitive_rot[primitive])
        return values
