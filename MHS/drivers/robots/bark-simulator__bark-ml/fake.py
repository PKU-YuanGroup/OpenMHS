"""Fake backend for gh.bark-simulator/bark-ml: a pure Python stand-in for ``highway-v0``.

The driver names ``bark_ml.environments.gym:ContinuousHighwayGym`` as its native class.  That class needs the
compiled ``bark-simulator`` package, ``gym``, a scenario map and the BARK C++ extensions, and this package never
imports or installs the clone.  The fake therefore reproduces the *interface* of ``SingleAgentRuntime``:
``reset()``, ``step(action)``, ``action_space`` and ``observation_space``.  It is a kinematic placeholder, not the
BARK scene; the driver's ``fidelity`` gaps name every difference.

The public members are the ones the upstream class has (gate G7):

* ``reset`` and ``step`` are defined in ``bark_ml/environments/single_agent_runtime.py:47-91``;
* ``action_space`` and ``observation_space`` are properties there (``:93-101``);
* the spaces duck-type the upstream ``BoundedContinuous`` and ``Box`` classes (``bark_ml/commons/py_spaces.py:50-89``
  and ``bark_ml/observers/nearest_observer.hpp:170-176``).

Sourced constants cite their line; every number that is only test data is marked ``# placeholder`` and is never
used as a Fact or a Limit.
"""

import math

# The NearestObserver defaults and normalization bounds, bark_ml/observers/nearest_observer.hpp:66-82.
NEAREST_AGENTS = 4
OBSERVATION_LEN = NEAREST_AGENTS * 4 + 6
MIN_S, MAX_S = -100.0, 100.0
MIN_D, MAX_D = -20.0, 20.0
MIN_THETA, MAX_THETA = -math.pi, math.pi
MIN_VEL_LON, MAX_VEL_LON = -30.0, 30.0
MIN_VEL_LAT, MAX_VEL_LAT = -10.0, 10.0

# The highway blueprint's simulation step, bark_ml/environments/blueprints/highway/highway.py:103.
DT = 0.2

# The StepCountFunctor default, bark_ml/evaluators/general_evaluator.py:88-91.
MAX_STEP_COUNT = 220

# The continuous action bounds, bark_ml/behaviors/cont_behavior.py:29-36.
ACTION_LOW = [-5.0, -0.2]     # acceleration (m/s^2), steering rate (rad/s)
ACTION_HIGH = [4.0, 0.2]

# The fake's scenario data.  These values are placeholders, not facts about a BARK scenario.
START_S = 50.0                # placeholder: inside the blueprint's ego range 40..80
START_D = 0.0                 # placeholder: centred on the ego lane
START_THETA = 0.0             # placeholder
START_VLON = 0.0              # placeholder: at rest so the observation stays near its declared box
START_VLAT = 0.0              # placeholder
LANE_INDEX = 2.0              # placeholder: the blueprint's ego lane id (highway.py:65)
LANE_HALF_WIDTH = 5.0         # placeholder: the fake leaves the lane beyond this lateral offset
TRAFFIC = (                   # placeholders: (delta s, delta d, delta vlon, delta vlat)
    (25.0, 0.0, 2.0, 0.0),
    (-18.0, 0.0, -3.0, 0.0),
    (10.0, 3.5, 1.0, 0.0),
    (-35.0, -3.5, 4.0, 0.0),
)


def _norm(value, low, high):
    """The observer's normalization, ``(v - (low+high)/2) / ((high-low)/2)`` (nearest_observer.hpp:85-89)."""
    return (value - (low + high) / 2.0) / ((high - low) / 2.0)


class Box:
    """Duck-typed one-dimensional ``Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeContinuousHighwayGym:
    """A deterministic kinematic stand-in for ``highway-v0`` on its four-lane straight-road simplification."""

    def __init__(self, **_options):
        self._reset_state()

    @property
    def action_space(self):
        """The continuous actions of ``BehaviorContinuousML`` (cont_behavior.py:29-43): acceleration, steering rate."""
        return Box(ACTION_LOW, ACTION_HIGH)

    @property
    def observation_space(self):
        """The NearestObserver box: 22 values, declared low 0 and high 1 (nearest_observer.hpp:170-176)."""
        return Box([0.0] * OBSERVATION_LEN, [1.0] * OBSERVATION_LEN)

    def reset(self, seed=None, options=None):
        """Start the fixed fake episode.

        ``SingleAgentRuntime.reset`` takes only a scenario and returns the observer's observation
        (single_agent_runtime.py:47-64).  The bridge calls ``reset(seed=...)``; both arguments are accepted and
        ignored because the upstream environment has no seed control (highway.py:119-125).
        """
        self._reset_state()
        return self._observation()

    def step(self, action):
        """Advance one 0.2 s step and return ``observation, reward, done, info`` like the upstream runtime."""
        try:
            acceleration = float(action[0])
            steering_rate = float(action[1])
        except (TypeError, ValueError, IndexError) as exc:
            raise ValueError("the fake action is [acceleration, steering_rate]") from exc

        # A kinematic stand-in for BehaviorDynamicModel: the two action components are integrated over DT.
        self._theta += steering_rate * DT
        self._vlon += acceleration * DT
        self._vlat = self._vlon * math.sin(self._theta)
        distance = self._vlon * DT
        self._s += distance * math.cos(self._theta)
        self._d += distance * math.sin(self._theta)
        self._step_count += 1

        departed = abs(self._d) > LANE_HALF_WIDTH                 # placeholder bound
        timed_out = self._step_count > MAX_STEP_COUNT             # the upstream StepCountFunctor default
        done = departed or timed_out
        reward = -1.0 if departed else 0.0                        # placeholder reward
        return self._observation(), reward, done, {}

    def _reset_state(self):
        self._s = START_S
        self._d = START_D
        self._theta = START_THETA
        self._vlon = START_VLON
        self._vlat = START_VLAT
        self._step_count = 0

    def _observation(self):
        """The 22-value NearestObserver layout: 6 ego values followed by 4 values per nearest agent."""
        values = [
            _norm(self._s, MIN_S, MAX_S),
            _norm(self._d, MIN_D, MAX_D),
            _norm(self._theta, MIN_THETA, MAX_THETA),
            _norm(self._vlon, MIN_VEL_LON, MAX_VEL_LON),
            _norm(self._vlat, MIN_VEL_LAT, MAX_VEL_LAT),
            LANE_INDEX,
        ]
        for delta_s, delta_d, delta_vlon, delta_vlat in TRAFFIC:
            values.extend((
                _norm(delta_s, MIN_S, MAX_S),
                _norm(delta_d, MIN_D, MAX_D),
                _norm(delta_vlon, MIN_VEL_LON, MAX_VEL_LON),
                _norm(delta_vlat, MIN_VEL_LAT, MAX_VEL_LAT),
            ))
        return values
