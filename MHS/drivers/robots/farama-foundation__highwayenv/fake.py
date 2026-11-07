"""Fake backend of the highwayenv driver: a pure Python kinematic stand-in for ``highway-v0``.

Why a fake: the gate runs without highway_env (the clone needs gymnasium, numpy, pandas, pygame-ce and noise) and
package code never imports the clone.  This module reproduces the interface of the upstream class named as
``native`` (``highway_env.envs.highway_env:HighwayEnv``): the spaces of the default configuration, ``reset(seed,
options)``, ``step(action)`` with the five meta-actions and ``close()``; the public members are the ones
``HighwayEnv`` has (gate G7) and the two space classes duck-type ``gymnasium.spaces.Discrete`` and ``Box`` (the
bridge reads ``n``, ``start``, ``low``, ``high`` and ``shape``).

It is kinematic (fidelity F0): there is no road network and there are no vehicle dynamics.  The ego vehicle changes
lane and speed directly (lane 0 to 3, speed 0 to the speed limit), one policy step advances the simulated time by
1 / policy_frequency, a collision is a distance check on the target lane when the ego changes lane, and the
Kinematics observation is the declared 25-number stand-in.  The driver's fidelity ``gaps`` say what is missing.

Every constant below either cites a line of the clone at the pinned commit
(2a268f348f10f4d1ac83f96bc8a53d2fa50dd3b0) or is marked ``# placeholder``: test data, never a Fact or a Limit.
Nothing here talks to a device.
"""

import math
import random

#: Clone constants: the default configuration served by this fake.
POLICY_FREQUENCY = 1  # abstract.py:115  [Hz]
DURATION = 40.0  # highway_env.py:39  [s]
LANES_COUNT = 4  # highway_env.py:35
OBSERVED_VEHICLES = 5  # observation.py:172
FEATURES = 5  # observation.py:166 (presence, x, y, vx, vy)
ACTIONS_COUNT = 5  # action.py:204 (LANE_LEFT, IDLE, LANE_RIGHT, FASTER, SLOWER)
SPEED_LIMIT = 30.0  # highway_env.py:63 (speed_limit=30)
INITIAL_SPEED = 25.0  # highway_env.py:82 (Vehicle.create_random(speed=25.0))
REWARD_SPEED_RANGE = (20.0, 30.0)  # highway_env.py:48
COLLISION_REWARD = -1.0  # highway_env.py:42
RIGHT_LANE_REWARD = 0.1  # highway_env.py:43
HIGH_SPEED_REWARD = 0.4  # highway_env.py:45
TIME_STEP = 1.0 / POLICY_FREQUENCY  # abstract.py:276  [s]

#: Stand-in constants of the toy scene: test data (# placeholder), not values of the clone.
LANE_WIDTH = 4.0  # placeholder: metres between two lane centres
COLLISION_DISTANCE = 10.0  # placeholder: metres of longitudinal gap that count as a crash
SPEED_CHANGE = 5.0  # placeholder: m/s per FASTER or SLOWER action
FIRST_GAP = 20.0  # placeholder: metres ahead of the ego where the observed vehicles start
GAP_SPREAD = 30.0  # placeholder: metres of random start spread
OTHER_SPEED_LOW = 20.0  # placeholder: m/s
OTHER_SPEED_SPREAD = 10.0  # placeholder: m/s


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
    """Duck-typed ``gymnasium.spaces.Box``: an array of ``shape`` numbers between ``low`` and ``high``."""

    def __init__(self, low, high, shape):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = "float32"


class FakeHighwayEnv:
    """``highway-v0`` without numpy, pygame or the road network: ``reset`` and ``step`` return what gymnasium's do."""

    def __init__(self, **_options):
        self.action_space = Discrete(ACTIONS_COUNT)
        self.observation_space = Box(-math.inf, math.inf, (OBSERVED_VEHICLES, FEATURES))
        self._rng = random.Random()
        self.reset()

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        # The clone draws the scene from the seeded numpy generator (abstract.py:234); this is the stand-in draw.
        self._time = 0.0
        self._lane = self._rng.randrange(LANES_COUNT)  # placeholder
        self._speed = INITIAL_SPEED
        self._position = 0.0
        self._crashed = False
        self._others = []
        for _ in range(OBSERVED_VEHICLES - 1):
            self._others.append({
                "lane": self._rng.randrange(LANES_COUNT),  # placeholder
                "gap": FIRST_GAP + GAP_SPREAD * self._rng.random(),  # placeholder [m]
                "speed": OTHER_SPEED_LOW + OTHER_SPEED_SPREAD * self._rng.random(),  # placeholder [m/s]
            })
        return self._observation(), {}

    def step(self, action):
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} ({type(action)}) invalid")
        self._time += TIME_STEP  # abstract.py:276
        lane_changed = False
        if action == 0:  # LANE_LEFT (action.py:204)
            lane_changed = self._lane > 0
            self._lane = max(self._lane - 1, 0)
        elif action == 2:  # LANE_RIGHT
            lane_changed = self._lane < LANES_COUNT - 1
            self._lane = min(self._lane + 1, LANES_COUNT - 1)
        elif action == 3:  # FASTER
            self._speed = min(self._speed + SPEED_CHANGE, SPEED_LIMIT)
        elif action == 4:  # SLOWER
            self._speed = max(self._speed - SPEED_CHANGE, 0.0)
        self._position += self._speed * TIME_STEP
        for other in self._others:
            other["gap"] += (self._speed - other["speed"]) * TIME_STEP  # placeholder: relative drift
        if lane_changed:  # placeholder: a crash is checked on the lane the ego changed into
            self._crashed = any(other["lane"] == self._lane and abs(other["gap"]) < COLLISION_DISTANCE
                                for other in self._others)
        terminated = bool(self._crashed)  # highway_env.py:141-147
        truncated = self._time >= DURATION  # highway_env.py:149-151
        return self._observation(), self._reward(), terminated, truncated, {}

    def close(self):
        pass

    # -- internals ---------------------------------------------------------
    def _observation(self):
        """The 25-number stand-in for a (5, 5) Kinematics observation (observation.py:166-172, 207-213)."""
        rows = [(1.0, self._position, self._lane * LANE_WIDTH, self._speed, 0.0)]
        for other in self._others:
            rows.append((1.0, other["gap"], other["lane"] * LANE_WIDTH, other["speed"], 0.0))
        return [float(value) for row in rows for value in row]

    def _reward(self):
        """The reward structure of the clone (highway_env.py:100-120), on the stand-in's speed and lane."""
        lane_fraction = self._lane / max(LANES_COUNT - 1, 1)  # highway_env.py:136
        low, high = REWARD_SPEED_RANGE
        scaled = min(max((self._speed - low) / (high - low), 0.0), 1.0)  # highway_env.py:131-137, clipped
        reward = (COLLISION_REWARD * float(self._crashed)
                  + RIGHT_LANE_REWARD * lane_fraction
                  + HIGH_SPEED_REWARD * scaled)
        lowest = COLLISION_REWARD
        highest = HIGH_SPEED_REWARD + RIGHT_LANE_REWARD
        reward = (reward - lowest) / (highest - lowest)  # highway_env.py:110-118
        return reward  # the ego stays on the road, so the on-road term is 1 (highway_env.py:119)
