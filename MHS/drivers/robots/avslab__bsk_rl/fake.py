"""Fake backend of the bsk_rl driver: a pure Python stand-in for a configured ``SatelliteTasking-v1`` environment.

Why a fake: the acceptance gate cannot install or import bsk_rl (the upstream package needs Basilisk, a C++
astrodynamics engine, and package code never imports the clone), so ``backends`` names this module and the gate never
touches the upstream simulator.  The public members below are the ones ``bsk_rl.gym:SatelliteTasking`` has and the
bridge resolves (``reset``, ``step``, ``close``, ``action_space``, ``observation_space``; gate G7).  The two space
classes duck-type ``gymnasium.spaces.Discrete`` and ``Box`` (the bridge reads ``n``, ``start``, ``low``, ``high`` and
``shape``).

The stand-in satellite is configured like the upstream integration test in
``tests/integration/act/test_int_actions_discrete.py:20-48``: one ``Downlink`` action, ten ``Image`` actions and a
``Time`` observation.  Every number that belongs to that configuration (the ten images, the time limit, the storage
capacity, the step duration, the reward) is TEST DATA, marked ``# placeholder`` below, and is not a Fact, a Limit or
a reference.  The action count is that configuration's, not a bound of the upstream environment, whose action space
is whatever the user's satellite ``action_spec`` defines (``src/bsk_rl/act/discrete_actions.py:34-37``).

What this is not: the upstream environment.  The fake models only the tasking state (simulated time, stored data and
the action index); it has no Basilisk orbit, attitude, power, thermal, sensor or actuator dynamics, and it draws from
Python's ``random.Random`` while upstream seeds numpy's global generator.  Those differences are the driver's
fidelity ``gaps``.  Nothing here talks to a device.
"""

import random
import time

# The Box bounds and shape rule of a list observation (src/bsk_rl/obs/observations.py:43-48).
OBS_LOW = -1e16
OBS_HIGH = 1e16

# ---- test configuration of the stand-in satellite (tests/integration/act/test_int_actions_discrete.py:20-48) ----
N_AHEAD_IMAGE = 10          # placeholder: Image(n_ahead_image=10) in the test configuration
N_ACTIONS = 1 + N_AHEAD_IMAGE   # placeholder: one Downlink action plus the Image actions
TIME_LIMIT_S = 10000.0      # placeholder: the test configuration's time_limit
STEP_DURATION_S = 10.0      # placeholder: no FSW events in the fake, so every step lasts this many simulated seconds
DATA_CAPACITY = 3.0         # placeholder: the test configuration's dataStorageCapacity
DATA_PER_IMAGE = 1.0        # placeholder: fake stand-in for the data one image adds
IMAGE_REWARD = 1.0          # placeholder: fake stand-in for a target's priority


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeSatelliteTasking:
    """A configured ``SatelliteTasking-v1`` environment without Basilisk.

    ``reset(seed, options)`` and ``step(action)`` follow the upstream contract (``src/bsk_rl/gym.py:315-411`` and
    ``:617-619``): reset returns ``(observation, info)``, step returns ``(observation, reward, terminated, truncated,
    info)``, the observation is the normalized simulation time (``src/bsk_rl/obs/observations.py:303-311``), and the
    step info carries ``requires_retasking`` and ``d_ts`` (``src/bsk_rl/gym.py:624-629``).
    """

    def __init__(self):
        self.action_space = Discrete(N_ACTIONS)                 # placeholder configuration
        self.observation_space = Box([OBS_LOW], [OBS_HIGH])
        self._seed = 0
        self._rng = random.Random(0)
        self._sim_time = 0.0
        self._data = 0.0
        self._latest_step_duration = 0.0
        self._requires_retasking = True
        self._alive = True
        self._reset_once = False
        self._closed = False

    def reset(self, seed=None, options=None):
        if seed is None:
            seed = time.time_ns() % 2**32          # src/bsk_rl/gym.py:341-342
        self._seed = int(seed)
        self._rng = random.Random(self._seed)      # upstream: np.random.seed (src/bsk_rl/gym.py:346)
        self._sim_time = 0.0
        self._data = self._rng.uniform(0.0, DATA_PER_IMAGE)     # placeholder starting storage
        self._latest_step_duration = 0.0            # src/bsk_rl/gym.py:356
        self._requires_retasking = True
        self._alive = True
        self._reset_once = True
        observation = [self._sim_time / TIME_LIMIT_S]           # Time observation, placeholder time limit
        info = {"requires_retasking": True, "d_ts": 0.0}        # src/bsk_rl/gym.py:624-629
        return observation, info

    def step(self, action):
        if isinstance(action, bool) or not isinstance(action, int) or not 0 <= action < N_ACTIONS:
            raise ValueError(f"Action index {action} out of range.")   # src/bsk_rl/act/discrete_actions.py:84
        if not self._reset_once:
            raise RuntimeError("Call reset before using step.")

        reward = 0.0
        if action == 0:
            # Downlink: the fake keeps no ground-station geometry, so the only effect is emptying the buffer.
            self._data = 0.0
        elif self._data < DATA_CAPACITY:            # downstream of the unique-image reward (unique_image_data.py:192-199)
            self._data = min(DATA_CAPACITY, self._data + DATA_PER_IMAGE)     # placeholder capacity and data
            reward = IMAGE_REWARD                   # placeholder reward
        # An image that reaches a full buffer adds no new data, so it pays no reward.

        self._sim_time += STEP_DURATION_S           # placeholder step duration
        self._latest_step_duration = STEP_DURATION_S                     # src/bsk_rl/gym.py:525-527
        self._requires_retasking = True
        observation = [self._sim_time / TIME_LIMIT_S]                    # src/bsk_rl/obs/observations.py:303-311
        terminated = not self._alive                                     # src/bsk_rl/gym.py:464-472
        truncated = self._sim_time >= TIME_LIMIT_S                       # src/bsk_rl/gym.py:474-478
        info = {"requires_retasking": self._requires_retasking, "d_ts": self._latest_step_duration}
        return observation, reward, terminated, truncated, info

    def close(self):
        self._closed = True
