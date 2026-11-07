"""Fake backend of the CoppeliaSim cart-pole driver: a pure Python stand-in for ``CartPoleEnv``.

Why a fake: the upstream environment opens a legacy CoppeliaSim remote API connection on port 19997
(``CartPole/CartPoleEnv.py:52-54``) and needs the CoppeliaSim application and ``cart_pole.ttt``
(``README.md:16,27``); neither is available where the gate runs and package code never imports or runs the clone.
This module re-implements the parts of ``CartPole.CartPoleEnv:CartPoleEnv`` that the driver serves: the discrete
action mapping (``CartPoleEnv.py:37-38,84-90``), the failure thresholds (``:24-25,99``), the reward rule
(``:102-117``), the observation layout with velocities over 0.005 s (``:119-121``) and the seeded start draw
(``:46-47,70-72,129-134``).

The public members are the ones the upstream class has (``seed``, ``step``, ``reset``, ``render``, ``close``; gate
G7), plus the two duck-typed spaces the bridge reads (``action_space``/``observation_space``).

What this is not: the CoppeliaSim scene. The displacement constants below are placeholders for test data, not
measurements or device facts; the real dynamics live in the binary ``cart_pole.ttt`` and the engine. The driver's
fidelity ``gaps`` say this, and this fake was never compared with a running CoppeliaSim.

Nothing here talks to a device or imports the clone.
"""

import math
import random

# CartPole/CartPoleEnv.py:24-25: the failure thresholds
THETA_MAX = 40 * math.pi / 360
CART_POS_MAX = 0.8
# CartPole/CartPoleEnv.py:46-47 and :133: the seeded start draw
START_LOW = -0.05
START_HIGH = 0.05
# CartPole/CartPoleEnv.py:119-120: velocities are differences over 0.005 s
DT = 0.005
# CartPole/CartPoleEnv.py:27-35: the observation bounds for the two velocities
VELOCITY_BOUND = 1000000.0
# The next two constants stand in for the unseen scene dynamics only; they are test data, not facts.
CART_STEP = 0.02  # placeholder: cart position change per tick per unit push
POLE_STEP = 0.02  # placeholder: pole angle change per tick per unit push


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n

    def sample(self):
        return self.start


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeCartPoleEnv:
    """The discrete-action ``CartPoleEnv`` without CoppeliaSim, numpy or gym.

    ``reset(seed=..., options=...)`` and ``step(action)`` return the Gymnasium shapes; the upstream class is a legacy
    ``gym.Env`` whose ``reset`` takes no seed and whose ``step`` returns four values, which the bridge also accepts.
    """

    def __init__(self, action_type="discrete"):
        if action_type != "discrete":
            # CartPoleEnv.py:37-42 builds only 'discrete' and 'continuous'; this package serves the demo's
            # 'discrete' configuration (examples/demo_cart_pole_learning.py:19).
            raise ValueError("this package serves the discrete action configuration only")
        self.action_type = action_type
        self.action_space = Discrete(3)                                   # CartPoleEnv.py:37-38
        high = [CART_POS_MAX, THETA_MAX, VELOCITY_BOUND, VELOCITY_BOUND]  # CartPoleEnv.py:27-35
        self.observation_space = Box([-value for value in high], high)    # CartPoleEnv.py:44
        self._rng = random.Random()
        self._force = 0.0
        self._q = [0.0, 0.0]  # prismatic joint position, revolute joint position (CartPoleEnv.py:78-82)
        self._q_last = [0.0, 0.0]
        self.state = [0.0, 0.0, 0.0, 0.0]                                 # CartPoleEnv.py:121
        self.counts = 0                                                   # CartPoleEnv.py:48
        self.steps_beyond_done = None                                     # CartPoleEnv.py:49
        self.seed()                                                       # CartPoleEnv.py:46
        self._draw_start()

    def seed(self, seed=None):
        """``CartPoleEnv.seed`` (CartPoleEnv.py:70-72) with Python's generator instead of numpy's."""
        self._rng = random.Random(seed)
        return [seed]

    def _draw_start(self):
        self._q = [self._rng.uniform(START_LOW, START_HIGH) for _ in range(2)]  # CartPoleEnv.py:47,133
        self._q_last = list(self._q)
        self.state = [self._q[0], self._q[1], 0.0, 0.0]

    def reset(self, *, seed=None, options=None):
        """Restart the episode: draw a start state, zero the push and the step counter (CartPoleEnv.py:129-134)."""
        if seed is not None:
            self.seed(seed)
        # The upstream reset takes no options; the gymnasium bridge's legacy fallback drops them too.  They are
        # accepted and ignored here, never used to change the start draw.
        self.counts = 0
        self._force = 0.0
        self.steps_beyond_done = None
        self._draw_start()                                                # CartPoleEnv.py:133
        return list(self.state), {}

    def step(self, action):
        """Apply one discrete action for one tick and return ``(observation, reward, terminated, truncated, info)``."""
        if not self.action_space.contains(action):                        # CartPoleEnv.py:75-76
            raise AssertionError(f"{action!r} ({type(action).__name__}) invalid")
        if action == 0:
            self._force = 0.0                                             # CartPoleEnv.py:85-86
        elif action == 1:
            self._force = 1.0                                             # CartPoleEnv.py:87-88
        else:
            self._force = -1.0                                            # CartPoleEnv.py:89-90
        self._q_last = list(self._q)
        self._q[0] += self._force * CART_STEP                             # placeholder dynamics
        self._q[1] += self._force * POLE_STEP                             # placeholder dynamics
        done = (self._q[0] <= -CART_POS_MAX or self._q[0] >= CART_POS_MAX
                or self._q[1] < -THETA_MAX or self._q[1] > THETA_MAX)     # CartPoleEnv.py:99
        done = bool(done)
        if not done:
            reward = 1.0                                                 # CartPoleEnv.py:102-103
        elif self.steps_beyond_done is None:
            self.steps_beyond_done = 0
            reward = 1.0                                                 # CartPoleEnv.py:104-107
        else:
            self.steps_beyond_done += 1
            reward = 0.0                                                 # CartPoleEnv.py:116-117
        self.state = [self._q[0], self._q[1],
                      (self._q[0] - self._q_last[0]) / DT,
                      (self._q[1] - self._q_last[1]) / DT]                # CartPoleEnv.py:119-121
        self.counts += 1                                                 # CartPoleEnv.py:122
        return list(self.state), reward, done, False, {"counts": self.counts}

    def render(self):
        """``CartPoleEnv.render`` does nothing (CartPoleEnv.py:146-147)."""
        return None

    def close(self):
        """``CartPoleEnv.close`` stops the simulation (CartPoleEnv.py:149-152); there is none here."""
        self._q = [0.0, 0.0]
        self.state = [0.0, 0.0, 0.0, 0.0]
        return None
