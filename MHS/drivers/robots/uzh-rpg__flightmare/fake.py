"""Native-shaped fake of ``flightrl.rpg_baselines.envs.vec_env_wrapper:FlightEnvVec``.

The upstream class is a Stable-Baselines ``VecEnv`` wrapping the pybind
``flightgym.QuadrotorEnv_v1`` vector environment.  Its batch interface returns
observations shaped ``(num_envs, num_obs)``, reward and done vectors of length
``num_envs`` and a list of per-environment info dictionaries
(vec_env_wrapper.py:34-55).  This fake preserves that interface before any
adaptation: it returns the same four-element tuple and batched arrays, and it
models the native auto-reset of a done environment (vec_env.cpp:148-162).

No number below is a fact or a limit of the upstream simulator.  This module
imports no upstream code, no ``flightgym`` extension and no ``gym`` package.
"""

import math
import random

# placeholder: the fake serves one environment, the production adapter's scope
NUM_ENVS = 1
# placeholder: the shipped QuadrotorEnv dimensions, used only as fake shapes
NUM_OBS = 12
NUM_ACTS = 4
# placeholder: how far the fake altitude falls per environment step
ALTITUDE_STEP = 0.001
# placeholder: the fake starts at this altitude
ALTITUDE_START = 5.0
# placeholder: the reward of a terminal step in the fake
TERMINAL_REWARD = -0.02


class Box:
    """A duck-typed per-agent ``gym.spaces.Box`` with plain-list bounds."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class FakeFlightEnvVec:
    """The public surface of ``FlightEnvVec`` with placeholder vector dynamics.

    The class deliberately implements the batch methods of the upstream class,
    not the scalar Gymnasium interface.  ``reset`` returns one batched
    observation array, ``step`` returns ``(obs, reward, done, info)`` with
    per-environment values, and ``seed`` delegates to the same method name the
    upstream wrapper exposes.  The production adapter in driver.py performs
    the per-environment extraction.
    """

    def __init__(self, impl=None, **_options):
        self.impl = impl
        self._num_envs = NUM_ENVS
        self._num_obs = NUM_OBS
        self._num_acts = NUM_ACTS
        self._observation_space = Box(
            [-math.inf] * self._num_obs,
            [math.inf] * self._num_obs,
            (self._num_obs,),
        )
        # the bounds are copied from the upstream action space (vec_env_wrapper.py:16-19)
        self._action_space = Box([-1.0] * self._num_acts, [1.0] * self._num_acts,
                                 (self._num_acts,))
        self._extra_info_names = []
        self._rng = random.Random(0)                       # placeholder
        self._seed = None
        self._closed = False
        self._altitude = [ALTITUDE_START] * self._num_envs  # placeholder
        self._observation = self._initial_observation()

    # -- public native surface -------------------------------------------------
    def seed(self, seed=0):
        # placeholder: deterministic test RNG; the upstream VecEnv::setSeed
        # calls std::srand while its mt19937 is seeded from std::random_device
        self._seed = int(seed)
        self._rng = random.Random(self._seed)

    def step(self, action):
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        rows = self._action_rows(action)
        done = [False] * self._num_envs
        reward = [0.0] * self._num_envs
        for index in range(self._num_envs):
            self._altitude[index] -= ALTITUDE_STEP
            self._observation[index][0] += rows[index][0] * 0.001
            if self._altitude[index] <= 0.02:             # placeholder: native terminal predicate
                done[index] = True
                reward[index] = TERMINAL_REWARD           # placeholder
                # the native perAgentStep resets a done environment immediately (vec_env.cpp:159-161)
                self._altitude[index] = ALTITUDE_START
                self._observation[index] = self._initial_observation()[0]
        info = [{} for _ in range(self._num_envs)]
        return ([list(row) for row in self._observation],
                list(reward),
                list(done),
                info)

    def reset(self):
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self._altitude = [ALTITUDE_START] * self._num_envs  # placeholder
        self._observation = self._initial_observation()
        return [list(row) for row in self._observation]

    def close(self):
        self._closed = True

    # -- public native properties ----------------------------------------------
    @property
    def num_envs(self):
        return self._num_envs

    @property
    def observation_space(self):
        return self._observation_space

    @property
    def action_space(self):
        return self._action_space

    @property
    def extra_info_names(self):
        return list(self._extra_info_names)

    # -- helpers ---------------------------------------------------------------
    def _initial_observation(self):
        return [[self._rng.uniform(-1.0, 1.0) for _ in range(self._num_obs)]  # placeholder
                for _ in range(self._num_envs)]

    def _action_rows(self, action):
        if hasattr(action, "tolist"):
            action = action.tolist()
        if not isinstance(action, (list, tuple)):
            raise ValueError("the fake VecEnv step expects a batch of actions")
        values = list(action)
        if values and isinstance(values[0], (list, tuple)):
            rows = [list(row) for row in values]
        else:
            rows = [values]
        if len(rows) != self._num_envs:
            raise ValueError("the action batch does not match num_envs")
        for row in rows:
            if len(row) != self._num_acts:
                raise ValueError("the action row does not match the action dimension")
            for value in row:
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError("action values must be finite")
        return [[float(value) for value in row] for row in rows]
