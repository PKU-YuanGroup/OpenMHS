"""Fake backend of the BlueSky-Gym driver: a pure Python stand-in for ``gymnasium.make("DescentEnv-v0")``.

Why a fake: the acceptance gate cannot import the upstream package (it needs ``bluesky-simulator``, gymnasium, numpy,
pygame, torch and stable-baselines3, ``pyproject.toml:4-11``), and package code never imports the clone.  This module
models the contract of ``bluesky_gym.envs.descent_env:DescentEnv`` (the class the driver names as ``native``) without
BlueSky.  Every constant taken from the clone cites its line at the pinned commit
(``8d7d79c63a3dab5de0e7bd8c2afb74737377f2e5``); a constant invented for this stand-in is marked ``# placeholder``.

The public methods are the ones ``DescentEnv`` defines (``reset``, ``step``, ``close``; gate G7).  The space classes
duck-type ``gymnasium.spaces.Dict`` and ``Box``: the bridge reads ``spaces`` on a ``Dict`` and ``low``, ``high``,
``shape`` and ``dtype`` on a ``Box``.  The observation dict and the five-member step tuple are what the bridge
consumes.

What this is not: the BlueSky simulation.  Differences, all listed in the driver's fidelity ``gaps``:

* the fake moves the altitude by the commanded vertical speed and closes the runway distance at a placeholder rate;
  upstream integrates the BlueSky aircraft performance model and derives the runway distance from the position;
* the reset draw uses Python's ``random.Random``; upstream draws with numpy's generator, so a seed gives different
  initial states;
* there is no rendering, no intruder or weather model and no snapshot support.

Nothing here talks to a device.
"""

import random

# bluesky_gym/envs/descent_env.py:10-15: normalisation constants of the observation
ALT_MEAN = 1500
ALT_STD = 3000
VZ_MEAN = 0
VZ_STD = 5
RWY_DIS_MEAN = 100
RWY_DIS_STD = 200
# descent_env.py:17: metres per second of vertical speed per unit of action
ACTION_2_MS = 12.5
# descent_env.py:19-21: reward scales
ALT_DIF_REWARD_SCALE = -5 / 3000
CRASH_PENALTY = -100
RWY_ALT_DIF_REWARD_SCALE = -50 / 3000
# descent_env.py:23-25: bounds of the reset draw
ALT_MIN = 2000
ALT_MAX = 4000
TARGET_ALT_DIF = 500
# descent_env.py:27: aircraft speed passed to BlueSky on reset
AC_SPD = 150
# descent_env.py:29: BlueSky simulation steps per environment step
ACTION_FREQUENCY = 30
# descent_env.py:71: the stack command 'DT 1;FF' sets BlueSky's simulation step setting to 1
SIM_DT = 1.0
# bluesky_gym/__init__.py:9: the TimeLimit that gymnasium.make adds to DescentEnv-v0
MAX_EPISODE_STEPS = 300
#: The fake starts at this runway distance and closes it by this much per environment step.  Neither is stated in
#: the clone: upstream derives both from the BlueSky aircraft position and ground speed (descent_env.py:94-101).
RUNWAY_DISTANCE_START_KM = 120.0   # placeholder
RUNWAY_CLOSURE_KM_PER_STEP = 0.25  # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None, dtype=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = dtype or "float64"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != self.shape[0]:
            return False
        return all(float(low) <= float(item) <= float(high)
                   for item, low, high in zip(value, self.low, self.high))


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces`` (a mapping of name to space)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeDescentEnv:
    """A deterministic analytic world with the action and observation contract of ``DescentEnv-v0``."""

    def __init__(self, render_mode=None, **_options):
        # The two space attributes are the ones DescentEnv sets in its __init__ (descent_env.py:52-61); the bridge
        # derives the contract from them.
        unbounded = Box([-float("inf")], [float("inf")], (), "float64")
        self.observation_space = Dict({
            "altitude": unbounded,
            "vz": Box([-float("inf")], [float("inf")], (), "float64"),
            "target_altitude": Box([-float("inf")], [float("inf")], (), "float64"),
            "runway_distance": Box([-float("inf")], [float("inf")], (), "float64"),
        })
        self.action_space = Box([-1.0], [1.0], (1,), "float64")
        self.render_mode = render_mode
        self._rng = random.Random()
        self._altitude = 0.0
        self._vz = 0.0
        self._target_alt = 0.0
        self._runway_distance = RUNWAY_DISTANCE_START_KM
        self._total_reward = 0.0
        self._final_altitude = 0
        self._tick = 0
        self._closed = False

    def _reset(self, seed):
        """Set the start state; a seed fixes the pseudo-random draw."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        alt_init = self._rng.randrange(ALT_MIN, ALT_MAX)                 # descent_env.py:169
        self._target_alt = float(alt_init + self._rng.randrange(-TARGET_ALT_DIF, TARGET_ALT_DIF))  # :170
        self._altitude = float(alt_init)
        self._vz = 0.0
        self._runway_distance = RUNWAY_DISTANCE_START_KM                 # placeholder
        self._total_reward = 0.0
        self._final_altitude = 0
        self._tick = 0

    def _observation(self):
        """The four normalised fields DescentEnv._get_obs returns (descent_env.py:104-114)."""
        return {
            "altitude": [(self._altitude - ALT_MEAN) / ALT_STD],
            "vz": [(self._vz - VZ_MEAN) / VZ_STD],
            "target_altitude": [(self._target_alt - ALT_MEAN) / ALT_STD],
            "runway_distance": [(self._runway_distance - RWY_DIS_MEAN) / RWY_DIS_STD],
        }

    def _info(self):
        return {"total_reward": self._total_reward, "final_altitude": self._final_altitude}

    def _reward(self):
        """DescentEnv._get_reward (descent_env.py:127-143), in the same branch order."""
        if self._runway_distance > 0 and self._altitude > 0:
            return abs(self._target_alt - self._altitude) * ALT_DIF_REWARD_SCALE, False
        if self._altitude <= 0:
            self._final_altitude = -100
            return CRASH_PENALTY, True
        self._final_altitude = self._altitude
        return self._altitude * RWY_ALT_DIF_REWARD_SCALE, True

    def reset(self, seed=None, options=None):
        """Gymnasium reset: return the initial observation and the info object."""
        self._reset(seed)
        return self._observation(), self._info()

    def step(self, action):
        """Apply one action, advance ACTION_FREQUENCY BlueSky steps and return the step tuple."""
        values = list(action)
        if len(values) != 1:
            raise ValueError(f"DescentEnv-v0 takes one action value, got {len(values)}")
        self._vz = float(values[0]) * ACTION_2_MS                       # descent_env.py:147
        for _ in range(ACTION_FREQUENCY):                               # descent_env.py:187-189
            self._altitude += self._vz * SIM_DT                         # descent_env.py:71
            self._runway_distance -= RUNWAY_CLOSURE_KM_PER_STEP / ACTION_FREQUENCY  # placeholder
        reward, terminated = self._reward()
        self._total_reward += reward
        self._tick += 1
        truncated = self._tick >= MAX_EPISODE_STEPS and not terminated  # bluesky_gym/__init__.py:9
        return self._observation(), reward, terminated, truncated, self._info()

    def close(self):
        """Release the stand-in's state (DescentEnv.close sends 'quit' to BlueSky)."""
        self._closed = True
