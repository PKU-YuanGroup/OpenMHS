"""Fake backend of the DiffTactile driver: a pure Python stand-in for the ``box_open`` TactileEnv.

Why a fake: the upstream package needs Taichi, NumPy, MPM/FEM solvers and GPU-capable kernels, and package code
never imports or runs the clone.  This module re-implements the *interface* of
``difftactile.baseline.tactile_env:TactileEnv`` (the class the driver names as ``native``): the same
``reset(seed=None, options=None)`` and ``step(action)`` returns, the two duck-typed ``Box`` spaces, and ``close``.
The public members of the fake class are the ones TactileEnv has (``reset``, ``step``, ``close``; gate G7).

Structural constants are copied from the cited upstream lines: the action bound of ``TactileEnv.__init__``, the
registered ``box_open`` task size and step limit, and the 544 particle indices.  Every observed value, every
particle offset, the toy deformation and the reward delta are placeholder data (``# placeholder``) and are not
measurements, limits or facts.  The fake does not integrate the FEM sensor or the MPM object: it has no contact,
material, friction, force or rendering model.

This is not the upstream environment, and nothing here talks to a device.
"""

import random

# difftactile/baseline/tactile_env.py:45: Box(low=-0.015, high=0.015, shape=(n_actions,))
ACTION_LOW = -0.015
ACTION_HIGH = 0.015
# difftactile/baseline/tactile_env.py:46: Box(low=-1000, high=1000, shape=(n_observations,))
OBSERVATION_BOUND = 1000.0
# difftactile/baseline/tactile_env.py:55 and :64-67: downsample_num = 2 * 136 * 2 particle indices
DOWNSAMPLE = 2 * 136 * 2
# difftactile/baseline/register_tasks.py:73: box_open registers n_actions = 6
N_ACTIONS = 6
# difftactile/baseline/register_tasks.py:75: state_n_observations = 2 * 136 * 2 * 3 + 6
N_OBSERVATIONS = DOWNSAMPLE * 3 + 6
# difftactile/baseline/register_tasks.py:76-78: dt = 5e-5 s, total_steps = 600, sub_steps = 50
DT = 5e-5
TIME_LIMIT = 600
SUB_STEPS = 50
# difftactile/baseline/tactile_env.py:211-217: the box_open reward scale and base
REWARD_SCALE = 1.0
REWARD_BASE = 2000.0
#: Placeholder size of the toy particle field, one three-vector per index.
PARTICLE_VALUES = DOWNSAMPLE * 3


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeTactileEnv:
    """A minimal stand-in for the ``box_open`` ``TactileEnv``: ``reset``, ``step`` and ``close``.

    The constructor takes the ``**_options`` shape a backend factory may receive; the ``box_open`` parameters are
    fixed to the registered task values so the fake publishes the same spaces and the same 600-step episode.
    """

    def __init__(self, **_options):
        # difftactile/baseline/tactile_env.py:45-46: the two spaces of the environment
        self.action_space = Box([ACTION_LOW] * N_ACTIONS, [ACTION_HIGH] * N_ACTIONS)
        self.observation_space = Box([-OBSERVATION_BOUND] * N_OBSERVATIONS,
                                     [OBSERVATION_BOUND] * N_OBSERVATIONS)
        # The attributes TactileEnv.__init__ keeps (tactile_env.py:43-71); the values below that carry no upstream
        # bound are placeholders.
        self.n_actions = N_ACTIONS
        self.n_observations = N_OBSERVATIONS
        self.task_name = "box_open"
        self.obs_tactile = False
        self.time_step = 0
        self.time_limit = TIME_LIMIT
        self.total_rewards = 0.0
        self.actions = []
        self.index = list(range(DOWNSAMPLE))
        self.max_rewards = 0
        self.model = None
        self.rewards = []
        self.iters = []
        self._seed = 0
        self._particles = []
        self._pose = []
        self.reset()

    def reset(self, seed=None, options=None):
        """Return ``(observation, infos)`` as ``tactile_env.py:104-123`` does.

        Upstream accepts ``seed`` and ``options`` and never reads them.  The fake uses the seed for its placeholder
        particle field (and ignores ``options``), so a seeded reset is reproducible in the fake.
        """
        if seed is not None:
            self._seed = int(seed)
        # placeholder: a deterministic toy particle field, not the MPM object state
        rng = random.Random(self._seed)
        self._particles = [rng.uniform(-0.05, 0.05) for _ in range(PARTICLE_VALUES)]
        # placeholder: the six sensor pose values that box_open appends after the particles
        self._pose = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.time_step = 0
        self.total_rewards = 0.0
        self.actions = []
        self.iter = 0
        return self._observation(), {}

    def step(self, action):
        """Apply one placeholder action and return the Gymnasium five-tuple (``tactile_env.py:85-102``)."""
        values = list(action)
        if len(values) != N_ACTIONS:
            raise AssertionError(f"box_open expects {N_ACTIONS} action values, got {len(values)}")
        self.time_step += 1
        self.iter = self.time_step
        self.actions.append(values)
        # placeholder: a toy displacement of every particle, not an FEM/MPM contact solve
        for axis in range(3):
            delta = values[axis] * 1e-2
            for particle in range(DOWNSAMPLE):
                self._particles[3 * particle + axis] += delta
        # placeholder: the sensor pose follows the position and orientation deltas
        for axis in range(3):
            self._pose[axis] += values[axis] * 10.0
            self._pose[3 + axis] += values[3 + axis] * 100.0
        observation = self._observation()
        # tactile_env.py:211-217: reward = scale * 2000 - delta_loss; the delta is placeholder data
        delta_loss = 1000.0 * abs(values[1])
        reward = REWARD_SCALE * REWARD_BASE - delta_loss
        # tactile_env.py:220-224 and :94: the episode ends at the time limit, and the fake has no NaNs
        terminated = self.time_step >= self.time_limit
        truncated = terminated
        # tactile_env.py:96-101: the running total excludes the terminal step
        if not truncated:
            self.total_rewards += reward
        return observation, reward, terminated, truncated, {}

    def close(self):
        """``tactile_env.py:230-231``: the environment has nothing to release."""
        pass

    def _observation(self):
        """A full-length placeholder observation: particle positions plus the six sensor pose values."""
        return self._particles + self._pose
