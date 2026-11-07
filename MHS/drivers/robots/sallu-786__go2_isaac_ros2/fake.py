"""Fake backend of the Go2 Isaac Lab driver: a kinematic stand-in for the Gymnasium task.

Why a fake: Isaac Sim 4.5.0, Isaac Lab 2.1.x, ROS2 Humble and a GPU are external prerequisites (README.md:4-8 and
:41-43), and package code never imports the clone.  The gate therefore serves this pure Python environment through
the gymnasium bridge.  It exposes only the Gymnasium interface the bridge uses (``reset``, ``step``, ``close``; gate
G7), and the two ``Box`` spaces duck-type ``gymnasium.spaces.Box`` (the bridge reads ``low``, ``high`` and ``shape``).

What this is not: the upstream environment.  The action and observation widths and bounds below are PLACEHOLDERS: the
joint count comes from the external ``UNITREE_GO2_CFG`` articulation (quadruped/go2/go2_env.py:2,47) and the
observation term widths from isaaclab mdp, neither stated in the clone.  The real policy observation concatenates the
eight terms of go2_env.py:74-94; this fake returns a four-number summary.  There is no PhysX, no contact, actuator or
sensor model, no rendering and no ROS2 output.  The reward is always 0, matching the empty ``RewardsCfg`` of
go2_env.py:120-123, and no episode limit is enforced because ``TerminationsCfg`` is empty and ``is_finite_horizon``
is False (go2_env.py:126-129, :171-172).  All of this is listed in the driver's fidelity ``gaps``.

Every numeric constant below is test data of the fake, not a fact about the device.
"""

import random

# The action and observation widths are test data: # placeholder.
ACTION_SIZE = 3          # placeholder
OBSERVATION_SIZE = 4     # placeholder
ACTION_LOW = -1.0        # placeholder
ACTION_HIGH = 1.0        # placeholder
START_BOUND = 0.05       # placeholder, the reset draw of x and y
X_PER_ACTION = 0.10      # placeholder, metres advanced per unit of mean action
YAW_PER_ACTION = 0.05    # placeholder, radians per unit of action difference


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        try:
            values = list(value)
        except TypeError:
            return False
        return len(values) == len(self.low) and all(
            low <= float(item) <= high for item, low, high in zip(values, self.low, self.high))


class FakeGo2Env:
    """A tiny deterministic stand-in with the Gymnasium environment surface of the Go2 task."""

    def __init__(self, **_options):
        self.action_space = Box([ACTION_LOW] * ACTION_SIZE, [ACTION_HIGH] * ACTION_SIZE)        # placeholder
        self.observation_space = Box([-1000.0] * OBSERVATION_SIZE, [1000.0] * OBSERVATION_SIZE)  # placeholder
        self._rng = random.Random()
        self._state = None

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        # placeholder start state: a small random x and y, zero yaw, zero last action
        self._state = [self._rng.uniform(-START_BOUND, START_BOUND),
                       self._rng.uniform(-START_BOUND, START_BOUND), 0.0, 0.0]
        return list(self._state), {}

    def step(self, action):
        if self._state is None:
            raise AssertionError("call reset before step")
        try:
            values = [float(item) for item in action]
        except (TypeError, ValueError) as exc:
            raise AssertionError(f"unsupported action {action!r}") from exc
        if len(values) != ACTION_SIZE:
            raise AssertionError(f"action has {len(values)} values, expected {ACTION_SIZE}")
        mean = sum(values) / len(values)
        self._state[0] += X_PER_ACTION * mean                       # placeholder kinematics
        self._state[2] += YAW_PER_ACTION * (values[-1] - values[0])  # placeholder kinematics
        self._state[3] = mean
        return list(self._state), 0.0, False, False, {}

    def close(self):
        self._state = None
