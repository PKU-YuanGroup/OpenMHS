"""Fake backend of the SUMO-RL driver: a pure-Python stand-in for ``sumo_rl.environment.env:SumoEnvironment``.

Why a fake: the upstream import needs ``SUMO_HOME`` and the SUMO tools (``sumo_rl/environment/env.py:8-12``), and
neither sumo-rl nor SUMO is installed where the gate runs; package code never imports the clone.  This module
implements only the surface the ``GymnasiumBridge`` reads from the class the driver names as ``native``: ``reset``,
``step``, ``close``, ``sim_step``, ``action_space`` and ``observation_space``.  The public members are the ones
``SumoEnvironment`` has (gate G7), and the two space classes duck-type ``gymnasium.spaces.Discrete`` and ``Box``
(the bridge reads ``n``, ``start``, ``low``, ``high`` and ``shape``).

What this is not: SUMO.  It has no vehicle dynamics, car-following, lane changing, routing, traffic-signal timing or
TraCI interaction.  It advances an analytic four-lane queue stand-in by ``delta_time`` simulated seconds per step,
returns the observation layout of ``DefaultObservationFunction`` (a one-hot phase, a min-green flag, lane densities
and lane queues), and reports the same five-tuple for the single-agent API.  The driver's fidelity ``gaps`` say this,
and no hardware device is modelled.

Every configuration and reply number below is test data of this stand-in, not a safety limit or a fact; each such
literal is marked ``# placeholder``.  The layout and the formulas cite the clone at the pinned commit
(86f0fc41401eeca724b2e8878f5020dc6d70c9b4) only where the stand-in reproduces them.
"""

import random

# The single-intersection network of tests/gym_test.py:8-14 has two green phases (net xml :58-63) and four
# controlled incoming lanes (net xml :41-55); observations.py:45-50 sizes the Box as num_green_phases + 1 + 2 * lanes.
NUM_GREEN_PHASES = 2                                                            # placeholder
NUM_LANES = 4                                                                   # placeholder
OBSERVATION_SIZE = NUM_GREEN_PHASES + 1 + 2 * NUM_LANES                         # placeholder (11)
DELTA_TIME = 5                                                                  # placeholder (env.py:106 default)
YELLOW_TIME = 2                                                                 # placeholder (env.py:107 default)
MIN_GREEN = 5                                                                   # placeholder (env.py:108 default)
NUM_SECONDS = 100                                                               # placeholder (tests/gym_test.py:10)
DRAIN_PER_STEP = 0.10                                                           # placeholder
FILL_PER_STEP = 0.05                                                            # placeholder
QUEUE_RATIO = 0.5                                                               # placeholder


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
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeSumoEnvironment:
    """A four-lane, two-phase stand-in with the public surface of ``SumoEnvironment``."""

    def __init__(self, **options):
        self._net = options.get("net_file")
        self._route = options.get("route_file")
        self.use_gui = bool(options.get("use_gui", False))
        self.begin_time = int(options.get("begin_time", 0))                     # placeholder
        self.num_seconds = int(options.get("num_seconds", NUM_SECONDS))         # placeholder
        self.sim_max_time = self.begin_time + self.num_seconds                  # env.py:142
        self.delta_time = int(options.get("delta_time", DELTA_TIME))            # placeholder
        self.yellow_time = int(options.get("yellow_time", YELLOW_TIME))         # placeholder
        self.min_green = int(options.get("min_green", MIN_GREEN))               # placeholder
        self.max_green = int(options.get("max_green", 50))                      # placeholder
        self.single_agent = True
        self.ts_ids = ["t"]                                                     # placeholder
        self.action_space = Discrete(NUM_GREEN_PHASES)                          # traffic_signal.py:118
        self.observation_space = Box([0.0] * OBSERVATION_SIZE,
                                     [1.0] * OBSERVATION_SIZE)                  # observations.py:45-50
        self.episode = 0
        self.sumo = None
        self._closed = False
        self._seed = 0                                                          # placeholder
        self._rng = random.Random(self._seed)
        self._phase = 0                                                         # placeholder
        self._time_since_change = 0                                             # placeholder
        self._sim_step = float(self.begin_time)
        self._lane_load = [0.0] * NUM_LANES                                     # placeholder
        self._last_observation = self._observation()

    @property
    def sim_step(self):
        """The simulated time in seconds (the upstream property reads it from SUMO, env.py:285-288)."""
        return self._sim_step

    def reset(self, seed=None, options=None):
        """Restart the stand-in; a supplied seed is masked to 31 bits like the upstream reset (env.py:269-270)."""
        if options is not None and not isinstance(options, dict):
            raise TypeError("options must be a mapping")
        if seed is not None:
            self._seed = int(seed) & 0x7FFFFFFF
        self._rng = random.Random(self._seed)
        self._lane_load = [round(self._rng.random(), 3) for _ in range(NUM_LANES)]  # placeholder
        self._phase = 0                                                         # placeholder
        self._time_since_change = 0                                             # placeholder
        self._sim_step = float(self.begin_time)
        self._closed = False
        self.episode += 1                                                       # env.py:266
        self._last_observation = self._observation()
        return list(self._last_observation), {"step": self._sim_step}

    def step(self, action):
        """Advance one action period; the bridge enforces the action space before this call."""
        if not self.action_space.contains(action):
            raise ValueError(f"action {action!r} is outside Discrete({self.action_space.n})")
        if self._closed:
            raise RuntimeError("the environment is closed")
        old_total = sum(self._lane_load)
        if action != self._phase and self._time_since_change >= self.yellow_time + self.min_green:
            self._phase = int(action)                                           # traffic_signal.py:191-203
            self._time_since_change = 0
        self._sim_step += float(self.delta_time)                                # env.py:143
        self._time_since_change += self.delta_time
        for lane in range(NUM_LANES):
            if lane // (NUM_LANES // NUM_GREEN_PHASES) == self._phase:          # placeholder lane grouping
                self._lane_load[lane] = max(0.0, self._lane_load[lane] - DRAIN_PER_STEP)
            else:
                self._lane_load[lane] = min(1.0, self._lane_load[lane] + FILL_PER_STEP)
        self._last_observation = self._observation()
        # placeholder: the /100 scale follows TrafficSignal._diff_waiting_time_reward (traffic_signal.py:232-236)
        reward = (old_total - sum(self._lane_load)) / 100.0
        info = {"step": self._sim_step}
        truncated = self._sim_step >= self.sim_max_time                          # env.py:341-344
        return list(self._last_observation), reward, False, truncated, info

    def close(self):
        """Stop the stand-in; upstream close stops SUMO and clears self.sumo (env.py:459-472)."""
        self.sumo = None
        self._closed = True

    def _observation(self):
        """The layout of DefaultObservationFunction (observations.py:38-43)."""
        phase = [1.0 if self._phase == index else 0.0 for index in range(NUM_GREEN_PHASES)]
        min_green = [1.0 if self._time_since_change >= self.min_green + self.yellow_time else 0.0]
        density = list(self._lane_load)
        queue = [min(1.0, value * QUEUE_RATIO) for value in self._lane_load]    # placeholder
        return phase + min_green + density + queue
