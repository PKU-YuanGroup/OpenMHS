"""Fake backend for the Slimebot Volleyball 1-vs-1 environment.

The upstream class named by ``native`` is ``VolleyBotEnv`` in
``slimebot-volleyball/1_vs_1/environments/volleybot.py`` of the pinned clone.  The clone cannot be imported by the
gate or by this package (it needs gym, numpy, opencv and an optional Webots supervisor), so this module is a pure
Python stand-in for the interface the bridge uses: ``reset``, ``step``, ``seed``, ``action_space`` and
``observation_space``.  Those member names are the upstream environment's own (gate G7).

The numbers below are test data of the fake, not facts of the device.  The ones that mirror an upstream constant
carry the upstream line for orientation, but they remain placeholders; the Facts and Limits of the driver cite the
clone, never this file.  The model is deliberately reduced: simplified ball bounce and agent motion, a static
baseline opponent, and no Webots rendering.  The driver's fidelity ``gaps`` disclose every one of those reductions.
"""

import math
import random

# Game settings of the clone, volleybot.py:36-41.  Test data here (placeholder), cited upstream in the driver facts.
TIMESTEP = 1.0 / 30.0          # placeholder: volleybot.py:36
NUDGE = 0.1                    # placeholder: volleybot.py:37
GRAVITY = -9.8 * 2 * 1.5       # placeholder: volleybot.py:40
MAXLIVES = 5                   # placeholder: volleybot.py:41

# Court settings of the clone, volleybot.py:75-87.  Test data here (placeholder).
COURT_WIDTH = 48.0             # placeholder: volleybot.py:75
COURT_DEPTH = 24.0             # placeholder: volleybot.py:77 (width/2)
WALL_WIDTH = 1.0               # placeholder: volleybot.py:80
PLAYER_VX = 17.5               # placeholder: volleybot.py:83
PLAYER_VY = 13.5               # placeholder: volleybot.py:84
PLAYER_VZ = 17.5               # placeholder: volleybot.py:85
MAX_BALL_V = 15 * 1.5          # placeholder: volleybot.py:86
AGENT_RADIUS = 1.5             # placeholder: volleybot.py:395
BALL_RADIUS = 0.5              # placeholder: volleybot.py:602
T_LIMIT = 3000                 # placeholder: volleybot.py:732
OBS_SCALE = 10.0               # placeholder: volleybot.py:373
FLOAT32_MAX = 3.4028234663852886e38  # placeholder: np.finfo(np.float32).max, volleybot.py:751

# Initial values of Game.reset (volleybot.py:588-604) and Agent.__init__ (volleybot.py:390-406).  Test data.
BALL_X = 0.0                   # placeholder: volleybot.py:602
BALL_Y = COURT_WIDTH / 4 - 1.5  # placeholder: volleybot.py:602
BALL_Z = 0.0                   # placeholder: volleybot.py:602
BALL_VX_LOW, BALL_VX_HIGH = -20.0, 20.0  # placeholder: volleybot.py:599
BALL_VY_LOW, BALL_VY_HIGH = 10.0, 25.0   # placeholder: volleybot.py:600
BALL_VZ_LOW, BALL_VZ_HIGH = -10.0, 10.0  # placeholder: volleybot.py:601
AGENT_Y = 1.5                  # placeholder: volleybot.py:603-604


class MultiBinary:
    """Duck-typed ``gym.spaces.MultiBinary``: ``n`` binary values in a one-dimensional shape."""

    def __init__(self, n):
        self.n = int(n)
        self.shape = (self.n,)
        self.dtype = "int8"

    def contains(self, value):
        try:
            items = list(value)
        except TypeError:
            return False
        return len(items) == self.n and all(item in (0, 1) for item in items)


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        try:
            items = list(value)
        except TypeError:
            return False
        return len(items) == len(self.low) and all(
            low <= item <= high for item, low, high in zip(items, self.low, self.high))


class FakeVolleyBotEnv:
    """The 1-vs-1 environment without gym, numpy, opencv or Webots.

    ``reset`` returns the observation (the legacy interface), ``step`` returns ``(observation, reward, done, info)``
    and ``seed`` returns ``[seed]``.  These are the upstream signatures the bridge falls back to for legacy gym.
    """

    def __init__(self, training=False, update=False):
        self.training = bool(training)
        self.update = bool(update)
        self.action_space = MultiBinary(5)  # placeholder: volleybot.py:744
        high = [FLOAT32_MAX] * 18            # placeholder: volleybot.py:751
        self.observation_space = Box([-item for item in high], high)  # placeholder: volleybot.py:752
        self._rng = random.Random()
        self._reset_state()

    # -- environment interface -------------------------------------------------
    def seed(self, seed=None):
        """Upstream ``seed`` (volleybot.py:765-769): reseed and return ``[seed]``."""

        self._rng = random.Random(seed)
        return [seed]

    def reset(self, seed=None, options=None):
        """Start a new episode.  ``options`` is accepted for the family bridge but has no effect (a gap)."""

        if seed is not None:
            self._rng = random.Random(seed)
        self._reset_state()
        return self._observation()

    def step(self, action, otherAction=None):
        """Advance one timestep with the five binary values of the external (right) agent."""

        try:
            values = list(action)
        except TypeError as exc:
            raise ValueError("action must be a sequence of five binary values") from exc
        if len(values) != 5:
            raise ValueError("action must have five binary values")

        self._move_agent(values)
        self._move_opponent()
        reward = self._move_ball()
        self.t += 1

        done = self.t >= T_LIMIT or self.right_life <= 0 or self.left_life <= 0
        info = {
            "ale.lives": self.right_life,
            "ale.otherLives": self.left_life,
            "EnvDepth": COURT_DEPTH,
        }
        return self._observation(), reward, done, info

    # -- reduced physics -------------------------------------------------------
    def _reset_state(self):
        self.t = 0
        self.right_life = MAXLIVES
        self.left_life = MAXLIVES
        self.right_x = COURT_WIDTH / 4                       # placeholder: volleybot.py:604
        self.right_y = AGENT_Y
        self.right_z = 0.0
        self.right_vx = 0.0
        self.right_vy = 0.0
        self.right_vz = 0.0
        self.left_x = -COURT_WIDTH / 4                       # placeholder: volleybot.py:603
        self.left_y = AGENT_Y
        self.left_z = 0.0
        self.left_vx = 0.0
        self.left_vy = 0.0
        self.left_vz = 0.0
        self._place_ball()

    def _place_ball(self):
        self.ball_x = BALL_X
        self.ball_y = BALL_Y
        self.ball_z = BALL_Z
        self.ball_vx = self._rng.uniform(BALL_VX_LOW, BALL_VX_HIGH)   # placeholder
        self.ball_vy = self._rng.uniform(BALL_VY_LOW, BALL_VY_HIGH)   # placeholder
        self.ball_vz = self._rng.uniform(BALL_VZ_LOW, BALL_VZ_HIGH)   # placeholder

    def _move_agent(self, values):
        forward = values[0] > 0
        backward = values[1] > 0
        jump = values[2] > 0
        right = values[3] > 0
        left = values[4] > 0

        desired_vx = 0.0
        desired_vy = 0.0
        desired_vz = 0.0
        if forward and not backward:
            desired_vx = -PLAYER_VX
        if backward and not forward:
            desired_vx = PLAYER_VX
        if jump:
            desired_vy = PLAYER_VY
        if right and not left:
            desired_vz = PLAYER_VZ
        if left and not right:
            desired_vz = -PLAYER_VZ

        self.right_vy += GRAVITY * TIMESTEP
        if self.right_y <= NUDGE * TIMESTEP:
            self.right_vy = desired_vy
        self.right_vx = desired_vx
        self.right_vz = desired_vz
        self.right_x += self.right_vx * TIMESTEP
        self.right_y += self.right_vy * TIMESTEP
        self.right_z += self.right_vz * TIMESTEP

        if self.right_y < 0.0:
            self.right_y = 0.0
            self.right_vy = 0.0
        low_x = WALL_WIDTH / 2 + AGENT_RADIUS
        high_x = COURT_WIDTH / 2 - AGENT_RADIUS
        if self.right_x <= low_x:
            self.right_x = low_x
            self.right_vx = 0.0
        if self.right_x >= high_x:
            self.right_x = high_x
            self.right_vx = 0.0
        limit_z = COURT_DEPTH / 2 - AGENT_RADIUS
        if self.right_z <= -limit_z:
            self.right_z = -limit_z
            self.right_vz = 0.0
        if self.right_z >= limit_z:
            self.right_z = limit_z
            self.right_vz = 0.0

    def _move_opponent(self):
        # The baseline policy of the clone moves the left agent; this fake keeps it on its half (a disclosed gap).
        self.left_vy += GRAVITY * TIMESTEP
        if self.left_y <= NUDGE * TIMESTEP:
            self.left_vy = 0.0
        self.left_vx = 0.0
        self.left_vz = 0.0
        self.left_x += self.left_vx * TIMESTEP
        self.left_y += self.left_vy * TIMESTEP
        self.left_z += self.left_vz * TIMESTEP
        if self.left_y < 0.0:
            self.left_y = 0.0
            self.left_vy = 0.0

    def _move_ball(self):
        self.ball_vy += GRAVITY * TIMESTEP
        speed = math.sqrt(self.ball_vx * self.ball_vx + self.ball_vy * self.ball_vy
                          + self.ball_vz * self.ball_vz)
        if speed > MAX_BALL_V:
            scale = MAX_BALL_V / speed
            self.ball_vx *= scale
            self.ball_vy *= scale
            self.ball_vz *= scale

        self.ball_x += self.ball_vx * TIMESTEP
        self.ball_y += self.ball_vy * TIMESTEP
        self.ball_z += self.ball_vz * TIMESTEP

        limit_x = COURT_WIDTH / 2 - BALL_RADIUS
        if self.ball_x <= -limit_x:
            self.ball_x = -limit_x
            self.ball_vx = -self.ball_vx
        if self.ball_x >= limit_x:
            self.ball_x = limit_x
            self.ball_vx = -self.ball_vx
        limit_z = COURT_DEPTH / 2 - BALL_RADIUS
        if self.ball_z <= -limit_z:
            self.ball_z = -limit_z
            self.ball_vz = -self.ball_vz
        if self.ball_z >= limit_z:
            self.ball_z = limit_z
            self.ball_vz = -self.ball_vz
        if self.ball_y >= COURT_WIDTH - BALL_RADIUS:
            self.ball_y = COURT_WIDTH - BALL_RADIUS
            self.ball_vy = -self.ball_vy

        if self.ball_y <= BALL_RADIUS:
            # checkEdges (volleybot.py:225-235): the floor contact scores for the other side.
            self.ball_y = BALL_RADIUS
            self.ball_vy = -self.ball_vy
            if self.ball_x <= 0.0:
                self.left_life -= 1
                reward = 1.0
            else:
                self.right_life -= 1
                reward = -1.0
            self._place_ball()
            return reward
        return 0.0

    def _observation(self):
        values = [
            self.right_x, self.right_y, self.right_z,
            self.right_vx, self.right_vy, self.right_vz,
            self.ball_x, self.ball_y, self.ball_z,
            self.ball_vx, self.ball_vy, self.ball_vz,
            -self.left_x, self.left_y, self.left_z,
            -self.left_vx, self.left_vy, self.left_vz,
        ]
        return [item / OBS_SCALE for item in values]
