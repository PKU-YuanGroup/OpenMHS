"""Fake backend of the Webots Gym driver: a pure-Python analytic stand-in for ``WebotsStickEnv``.

The upstream class exists only inside a Webots R2021a simulation: it subclasses Webots' ``Supervisor`` and the
``gym.Env`` interface, and the gate cannot start Webots.  This module therefore re-implements the part of the
interface the Gymnasium bridge needs -- ``action_space``, ``observation_space``, ``reset`` and ``step`` -- and mirrors
the upstream semantics that are visible in the clone:

* the action space is ``Discrete(2)`` (``controllers/gym_controller/gym_controller.py:32``);
* ``reset`` starts at the fixed four-zero observation (``:72``);
* ``step`` applies the wheel direction of the action and returns the legacy four-tuple
  ``(state, reward, done, info)`` (``:77``, ``:87-97``).

The dynamics are *not* Webots.  Every numeric constant below is test data chosen to make the fake terminate in a few
steps; each is marked ``# placeholder`` and none is cited as a Fact, a Limit or a reference.  The fake does not
import numpy, gym, stable_baselines3, Webots or anything from the clone.  What it does not model is listed in the
driver's fidelity ``gaps``: no rigid-body dynamics, contacts, friction, motor, sensor or noise model, no physical time
step, and it was never compared with a Webots run.
"""

# placeholder: thresholds mirrored from controllers/gym_controller/gym_controller.py:21-22, used only as test data here
X_THRESHOLD = 0.3
THETA_THRESHOLD = 0.2

# placeholder: np.finfo(np.float32).max as written by the upstream Box construction; a finite stand-in bound
FLOAT32_MAX = 3.4028234663852886e38

# placeholder: per-step analytic increments; they are not measurements or upstream constants
STEP_POSITION = 0.00005
STEP_FALL = 0.0001
STEP_DRIVE = 0.00005


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the bridge reads ``n`` and ``start``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeWebotsStickEnv:
    """A minimal stand-in for ``WebotsStickEnv``: fixed zero reset, analytic step, legacy four-tuple result.

    Only the members the bridge needs are public (``action_space``, ``observation_space``, ``reset``, ``step`` and
    ``close``); everything else is private so gate G7 sees the upstream surface, not a new API.
    """

    def __init__(self):
        high = [X_THRESHOLD * 2, FLOAT32_MAX, THETA_THRESHOLD * 2, FLOAT32_MAX]
        self.action_space = Discrete(2)
        self.observation_space = Box([-value for value in high], high)
        self.state = None

    def reset(self):
        # The upstream reset restarts the world and returns np.array([0, 0, 0, 0]) (controller line 72).
        # This fake starts from the same fixed observation; it takes no seed or options, as upstream does.
        self.state = [0.0, 0.0, 0.0, 0.0]
        return list(self.state)

    def step(self, action):
        # Action 1 drives forward and every other action drives backward (controller line 77).  The bridge refuses
        # anything outside Discrete(2), so the upstream "anything else is -1.3" branch is not reachable here.
        drive = 1.0 if action == 1 else -1.0
        x, _x_dot, theta, theta_dot = self.state
        x = x + STEP_POSITION * drive                 # placeholder analytic position increment
        x_dot = STEP_POSITION * drive                 # placeholder analytic velocity
        theta_dot = theta_dot + STEP_FALL * theta + STEP_DRIVE * drive   # placeholder analytic fall
        theta = theta + theta_dot
        self.state = [x, x_dot, theta, theta_dot]
        done = bool(
            self.state[0] < -X_THRESHOLD
            or self.state[0] > X_THRESHOLD
            or self.state[2] < -THETA_THRESHOLD
            or self.state[2] > THETA_THRESHOLD
        )
        reward = 0 if done else 1
        return list(self.state), reward, done, {}

    def close(self):
        self.state = None
