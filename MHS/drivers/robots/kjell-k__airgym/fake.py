"""Fake backend of the AirGym driver: a pure Python kinematic stand-in for ``AirSimEnv``.

Why a fake: the gate cannot import the clone (it needs AirSim, gym, numpy, cv2, eventlet and PIL), package code never
imports the clone, and the AirSim RPC server is not attached.  This module re-implements the environment around the
constants and action semantics of ``gym_airsim/envs/AirGym.py`` and ``gym_airsim/envs/myAirSimClient.py`` cited
below.  The public members that exist on ``AirSimEnv`` are ``reset``, ``step``, ``computeReward`` and ``addToLog``
(gate G7); ``reset`` and ``step`` are the modern names the family bridge calls, while the upstream class defines the
legacy ``_reset``/``_step`` hooks (AirGym.py:75-127).

What this is not: the upstream environment.  There is no AirSim physics, no collision query, no camera and no
rendering.  The 30 x 100 observation keeps the shape of the upstream depth image (AirGym.py:24 and
myAirSimClient.py:141-153) but its depth half is a placeholder texture.  The gaps in ``driver.py`` say all of this.

Numbers that are test data (the starting pose, the synthetic depth texture and the two image fill values) are marked
``# placeholder``; no such value is used as a Fact, a Limit or a reference.  Constants copied from the upstream code
cite the upstream line instead.
"""

import math
import random

# AirGym.py:29: the flight goal in global xy.
GOAL_X, GOAL_Y = 221.0, -9.0
# AirGym.py:36 and :140: every episode starts the distance log at this value.
DISTANCE_LOG_START = 221
# AirGym.py:100: within this distance of the goal, the episode ends with reward 100.
GOAL_RADIUS = 3.0
# AirGym.py:60 and :70: the distance reward is -1 plus the closed distance.
STEP_PENALTY = -1.0
# AirGym.py:89 and :102: the collision and goal rewards.
COLLISION_REWARD = -100.0
GOAL_REWARD = 100.0
# AirGym.py:111: a cumulative reward below this ends the episode.
PENALTY_LIMIT = -100.0
# myAirSimClient.py:31: the flight altitude of the action loop.
CRUISE_Z = -6.0
# myAirSimClient.py:72, :84 and :95: the action durations.
STRAIGHT_SECONDS, YAW_RIGHT_SECONDS, YAW_LEFT_SECONDS = 1.0, 0.8, 1.0
# myAirSimClient.py:42 and :47: the commanded yaw rates.
YAW_RATE_DEG_S = 30.0
# myAirSimClient.py:72: the straight speed.
STRAIGHT_SPEED_M_S = 4.0
# AirGym.py:24: the observation shape and range.
IMAGE_ROWS, IMAGE_COLS = 30, 100
IMAGE_LOW, IMAGE_HIGH = 0, 255
# myAirSimClient.py:141: the goal-direction block on top of the depth rows.
INFO_ROWS = 10
# myAirSimClient.py:137-139: the resized depth slice is 20 rows tall.
DEPTH_ROWS = IMAGE_ROWS - INFO_ROWS


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
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound over a fixed shape."""

    def __init__(self, low, high, shape):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = "uint8"


class _Position:
    """The ``x_val``/``y_val`` fields ``Vector3r`` exposes to ``computeReward`` (AirGym.py:56-57)."""

    def __init__(self, x_val, y_val):
        self.x_val = x_val
        self.y_val = y_val


class FakeAirSimEnv:
    """Kinematic AirSimEnv stand-in: ``reset(seed, options)`` and ``step(action)`` are the bridge's entry points."""

    def __init__(self, **_options):
        self.action_space = Discrete(3)                                     # AirGym.py:27
        self.observation_space = Box(IMAGE_LOW, IMAGE_HIGH, (IMAGE_ROWS, IMAGE_COLS))   # AirGym.py:24
        self.goal = [GOAL_X, GOAL_Y]                                        # AirGym.py:29
        self.episodeN = 0
        self.stepN = 0
        self.allLogs = {"reward": [0]}
        self.allLogs["distance"] = [DISTANCE_LOG_START]
        self.allLogs["track"] = [-2]
        self.allLogs["action"] = [1]
        self.state = [[IMAGE_LOW] * IMAGE_COLS for _ in range(IMAGE_ROWS)]   # placeholder: AirGym.py:25
        self._position = _Position(0.0, 0.0)                                # placeholder: airgym.home_pos
        self._yaw = math.atan2(GOAL_Y - self._position.y_val,               # placeholder: airgym.home_ori
                               GOAL_X - self._position.x_val)
        self._rng = random.Random(0)                                        # placeholder: default reset seed
        self._depth = self._texture(self._rng)

    def reset(self, seed=None, options=None):
        """Reset the flight and return the depth observation (AirGym.py:127-150)."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        # AirSimEnv._reset takes no options (AirGym.py:127); the bridge may pass an object, so it is ignored.
        self.episodeN += 1
        self.stepN = 0
        self.allLogs = {"reward": [0]}
        self.allLogs["distance"] = [DISTANCE_LOG_START]
        self.allLogs["track"] = [-2]
        self.allLogs["action"] = [1]
        self._position = _Position(0.0, 0.0)                                # placeholder: airgym.home_pos
        self._yaw = math.atan2(GOAL_Y - self._position.y_val,               # placeholder: airgym.home_ori
                               GOAL_X - self._position.x_val)
        self._depth = self._texture(self._rng)
        self.state = self._observe()
        return self.state

    def step(self, action):
        """One action: move or yaw, score the distance change, return state, reward, done, info."""
        assert self.action_space.contains(action), f"{action!r} ({type(action)}) invalid"   # AirGym.py:76
        self.addToLog("action", action)                                     # AirGym.py:78
        self.stepN += 1                                                     # AirGym.py:80

        collided = self._take_action(action)                                # AirGym.py:82
        now = self._position                                                # AirGym.py:84
        track = self._goal_direction()                                      # AirGym.py:85

        if collided is True:                                                # AirGym.py:87-90
            done = True
            reward = COLLISION_REWARD
            distance = self._distance(now)
        elif collided == 99:                                                # AirGym.py:91-94
            done = True
            reward = 0.0
            distance = self._distance(now)
        else:                                                               # AirGym.py:95-97
            done = False
            reward, distance = self.computeReward(now, track)

        if distance < GOAL_RADIUS:                                          # AirGym.py:99-102
            done = True
            reward = GOAL_REWARD

        self.addToLog("reward", reward)                                     # AirGym.py:104
        rewardSum = sum(self.allLogs["reward"])                             # AirGym.py:105
        self.addToLog("distance", distance)                                 # AirGym.py:106
        self.addToLog("track", track)                                       # AirGym.py:107
        if rewardSum < PENALTY_LIMIT:                                       # AirGym.py:109-112
            done = True

        info = {"x_pos": now.x_val, "y_pos": now.y_val}                     # AirGym.py:117
        self.state = self._observe()                                        # AirGym.py:118
        return self.state, reward, done, info                               # AirGym.py:120

    def computeReward(self, now, track):
        """``-1 + distance_before - distance_now`` (AirGym.py:51-72)."""
        distance_now = self._distance(now)
        distance_before = self.allLogs["distance"][-1]
        r = STEP_PENALTY
        r = r + (distance_before - distance_now)
        return r, distance_now

    def addToLog(self, key, value):
        """Append to the per-episode log (AirGym.py:122-125)."""
        if key not in self.allLogs:
            self.allLogs[key] = []
        self.allLogs[key].append(value)

    # -- the AirSim client side (myAirSimClient.py) ---------------------------------
    def _take_action(self, action):
        """The kinematic part of ``take_action`` (myAirSimClient.py:52-104): no collision is modelled."""
        if action == 0:                                                     # myAirSimClient.py:70-72
            distance = STRAIGHT_SPEED_M_S * STRAIGHT_SECONDS
            self._position.x_val += distance * math.cos(self._yaw)
            self._position.y_val += distance * math.sin(self._yaw)
        elif action == 1:                                                   # myAirSimClient.py:82-84
            self._yaw += math.radians(YAW_RATE_DEG_S * YAW_RIGHT_SECONDS)
        elif action == 2:                                                   # myAirSimClient.py:93-95
            self._yaw -= math.radians(YAW_RATE_DEG_S * YAW_LEFT_SECONDS)
        return False                                                        # placeholder: never collides

    def _distance(self, now):
        return math.hypot(self.goal[0] - now.x_val, self.goal[1] - now.y_val)   # AirGym.py:56

    def _goal_direction(self):
        """``goal_direction`` of myAirSimClient.py:106-116, with the simulated yaw instead of getPitchRollYaw()."""
        yaw = math.degrees(self._yaw)
        pos_angle = math.degrees(math.atan2(self.goal[1] - self._position.y_val,
                                            self.goal[0] - self._position.x_val)) % 360
        track = math.radians(pos_angle - yaw)
        return ((math.degrees(track) - 180) % 360) - 180

    def _observe(self):
        """A 30 x 100 uint8 image: the goal-direction rows over the placeholder depth texture (myAirSimClient.py:141-153)."""
        track = self._goal_direction()
        line = int(((track - -180) * (IMAGE_COLS - 0)) / (180 - -180))
        line = max(0, min(IMAGE_COLS - 1, line))
        image = [[IMAGE_HIGH] * IMAGE_COLS for _ in range(INFO_ROWS)]       # placeholder: info_section fill
        for row in image:
            row[line] = IMAGE_LOW                                           # placeholder: goal-direction line
            row[IMAGE_COLS - 1] = IMAGE_LOW                                 # placeholder: info_section[9, :] = 0
        image[INFO_ROWS - 1] = [IMAGE_LOW] * IMAGE_COLS                     # placeholder: info_section[9, :] = 0
        image.extend([list(row) for row in self._depth])
        return image

    @staticmethod
    def _texture(rng):
        """The placeholder 20 x 100 depth slice; only its shape and 0..255 range follow the upstream observation."""
        return [[rng.randrange(IMAGE_HIGH + 1) for _ in range(IMAGE_COLS)] for _ in range(DEPTH_ROWS)]
