"""Fake backend for the Google Research Football environment (simple115 representation).

Why a package fake: the gate never imports the upstream clone (it needs the C++ ``gfootball_engine``, OpenCV,
``gym`` and numpy; ``requirements.txt`` lists them), and package code never imports the clone.  This module is a
small kinematic stand-in for the environment that ``create_environment`` returns for
``GFootball-11_vs_11_stochastic-simple115-v0``: the same public members as ``FootballEnv`` (``action_space``,
``reset``, ``step``, ``observation`` and ``close``; gate G7) and the same simple115 observation size, action-set
size and episode length.  It does not run the C++ engine and does not model the game; see the fidelity ``gaps`` in
``driver.py``.

Every number that comes from the clone cites its line at commit 3d9e754720a95621bba6475c4d3b0d56fe919014.  The few
values this fake invents (the ball start and its movement) are test data and are marked ``# placeholder``; they are
not facts of the device and are not copied into ``driver.py`` or ``reference.json``.

Nothing here talks to a device.
"""

import math

# gfootball/env/football_action_set.py:129-135 with gfootball/env/config.py:87: the default action set action_set_v1
# has 19 actions (idle, eight directions, four passes/shots, sprint, release_direction, release_sprint, sliding,
# dribble, release_dribble).
NUM_ACTIONS = 19

# gfootball/env/wrappers.py:108-111 and :161-188: the simple115 observation has 115 float32 values.
OBSERVATION_SIZE = 115

# gfootball/scenarios/11_vs_11_stochastic.py:23: the scenario's game_duration, i.e. the number of steps in one
# episode (gfootball/env/football_env_core.py:239-242).
GAME_DURATION = 3000

# gfootball/env/wrappers.py:161-165: fewer than 11 players are backfilled with -1; 88 = 11 players * 2 teams *
# 2 (position and direction) * 2 (x and y).
PLAYER_VALUES = 88
BACKFILL = -1.0

# placeholder: the fake's ball starts at the centre and moves 0.01 per directional action; the upstream engine's
# ball state comes from the C++ game, not from these test values.
BALL_START = [0.0, 0.0, 0.0]
BALL_STEP = 0.01
# placeholder: the eight directional actions of action_set_v1 (indices 1..8), in x/y units, and the field limits
# used only to keep this stand-in's arithmetic finite.
DIRECTIONS = {
    1: (-1.0, 0.0),
    2: (-1.0, 1.0),
    3: (0.0, 1.0),
    4: (1.0, 1.0),
    5: (1.0, 0.0),
    6: (1.0, -1.0),
    7: (0.0, -1.0),
    8: (-1.0, -1.0),
}
FIELD_X = 1.0
FIELD_Y = 0.5


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype


class FakeFootballEnv:
    """A kinematic stand-in for ``gfootball.env.football_env:FootballEnv`` at the simple115 output.

    The public members are the upstream ones the bridge uses: ``action_space``, ``observation_space`` (an instance
    attribute, as the Gymnasium observation wrappers set it), ``reset``, ``step``, ``observation`` and ``close``.
    The upstream ``reset`` takes no arguments, so this fake does too; the bridge's legacy gym path then calls
    ``reset()`` and the requested seed/options are not applied (disclosed in the fidelity gaps).
    """

    def __init__(self):
        self.action_space = Discrete(NUM_ACTIONS)
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self._ball = list(BALL_START)
        self._direction = [0.0, 0.0, 0.0]
        self._step = 0
        self._resetted = False
        self._closed = False

    def reset(self):
        """Start a new episode and return its first observation, like ``FootballEnv.reset`` (football_env.py:185-190)."""
        if self._closed:
            raise RuntimeError("the environment is closed; create a new one")
        self._ball = list(BALL_START)
        self._direction = [0.0, 0.0, 0.0]
        self._step = 0
        self._resetted = True
        return self.observation()

    def step(self, action):
        """Apply one action and return ``(observation, reward, done, info)`` (football_env.py:166-183)."""
        if not self.action_space.contains(action):
            raise AssertionError("action outside the Discrete({}) action space".format(self.action_space.n))
        if not self._resetted:
            raise AssertionError("reset() must be called before step()")
        dx, dy = DIRECTIONS.get(int(action), (0.0, 0.0))
        self._direction = [dx, dy, 0.0]
        self._ball[0] = max(-FIELD_X, min(FIELD_X, self._ball[0] + dx * BALL_STEP))
        self._ball[1] = max(-FIELD_Y, min(FIELD_Y, self._ball[1] + dy * BALL_STEP))
        self._step += 1
        done = self._step >= GAME_DURATION
        reward = 0.0
        info = {"score_reward": reward, "steps_left": GAME_DURATION - self._step}
        return self.observation(), reward, done, info

    def observation(self):
        """The simple115 vector: player slots, ball, possession, active player and game mode (wrappers.py:161-188)."""
        values = [BACKFILL] * PLAYER_VALUES
        values.extend(self._ball)
        values.extend(self._direction)
        values.extend([1.0, 0.0, 0.0])   # ball_owned_team == -1 (wrappers.py:172-173)
        values.extend([0.0] * 11)        # no active player is modelled
        values.extend([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])  # game_mode 0, NormalMode (wrappers.py:184-186)
        return values

    def close(self):
        self._closed = True
        self._resetted = False
