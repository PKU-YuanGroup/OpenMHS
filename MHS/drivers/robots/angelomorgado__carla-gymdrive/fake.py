"""Fake backend of the CARLA GymDrive driver: a pure Python stand-in for ``CarlaEnv``.

Why a fake: the upstream environment opens a CARLA server (``src/carlacore/world.py`` connects to ``localhost:2000``)
and the gate runs without CARLA, without gymnasium and without numpy, and the gate never imports the clone.  This
module re-implements the surface of ``src.env.environment:CarlaEnv`` that the Gymnasium bridge uses -- ``action_space``,
``observation_space``, ``reset``, ``step``, ``render`` and ``close`` (gate G7) -- as a small kinematic model.  The
observation keys, ranks and dtypes follow ``src/env/observation_action_space.py``; the numbers are test data, each
marked ``# placeholder``, and never facts about CARLA.

What this is not: the upstream environment.  The differences are listed in the driver's fidelity ``gaps``:

* the fake moves the ego vehicle by an analytic rule, with no vehicle dynamics, contacts, sensors, traffic,
  pedestrians, weather or rendering; CARLA runs the real simulation;
* the fake returns a 4 x 4 x 3 RGB image and a 3 x 4 LiDAR array instead of the upstream 360 x 640 x 3 and 3 x 500
  arrays, to keep receipts and state hashes small;
* the fake truncates on a step count instead of the upstream wall-clock time limit, and draws the scenario with
  Python's ``random.Random`` instead of numpy and CARLA;
* nothing here talks to a device.
"""

import math
import random

# The real observation shapes are declarations, not test data: src/env/observation_action_space.py:5-13 names
# rgb_data (360, 640, 3) and lidar_data (3, 500).  The fake uses smaller arrays of the same type and rank so the
# state hash stays small (driver-authoring.md section 6); the driver's fidelity gaps name the real sizes.
REAL_RGB_SHAPE = (360, 640, 3)
REAL_LIDAR_SHAPE = (3, 500)
# placeholder: small stand-ins for the arrays above
FAKE_RGB_SHAPE = (4, 4, 3)
FAKE_LIDAR_SHAPE = (3, 4)

# placeholder: test data, not a fact about CARLA's physics or timing
DT_S = 1.0 / 30.0
SIM_FPS = 30
MAX_SPEED = 5.0
THROTTLE_RATE = 1.0
STEER_RATE = 0.5
TARGET_DISTANCE = 0.5

# src/env/observation_action_space.py:15-20
SITUATIONS = ("Road", "Roundabout", "Junction", "Tunnel")
SITUATION_INDEX = {name: index for index, name in enumerate(SITUATIONS)}


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
    """Duck-typed ``gymnasium.spaces.Box``: the bounds and shapes the bridge reads."""

    def __init__(self, low, high, shape=None, dtype="float32"):
        self.low = low
        self.high = high
        self.shape = tuple(shape) if shape is not None else _shape_of(low)
        self.dtype = dtype

    def contains(self, value):
        try:
            values = _flatten(value)
        except (TypeError, ValueError):
            return False
        return all(self._inside(item) for item in values)

    def _inside(self, value):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        low = self.low if not isinstance(self.low, (list, tuple)) else min(_flatten(self.low))
        high = self.high if not isinstance(self.high, (list, tuple)) else max(_flatten(self.high))
        return low <= value <= high


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None
        self.dtype = None


def _shape_of(value):
    if isinstance(value, (list, tuple)):
        return (len(value),)
    return ()


def _flatten(value):
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(_flatten(item))
        return out
    return [float(value)]


class FakeCarlaEnv:
    """The surface of ``CarlaEnv`` used by the Gymnasium bridge, without CARLA or gymnasium."""

    metadata = {"render_modes": ["human"], "render_fps": SIM_FPS}          # placeholder render_fps

    def __init__(self, continuous=True, scenarios=None, time_limit=60, synchronous_mode=True, **_options):
        self._continuous = bool(continuous)
        self._synchronous_mode = bool(synchronous_mode)
        self._scenario_names = list(scenarios) if scenarios else list(SITUATIONS)
        # placeholder: 30 is SIM_FPS; the upstream limit is wall-clock seconds, this fake counts steps
        self._max_steps = max(1, int(round(float(time_limit) * SIM_FPS)))
        self.action_space = (Box([-1.0, -1.0], [1.0, 1.0], shape=(2,), dtype="float32")
                             if self._continuous else Discrete(4))
        self.observation_space = Dict({
            "rgb_data": Box(0, 255, shape=FAKE_RGB_SHAPE, dtype="uint8"),
            "lidar_data": Box(-math.inf, math.inf, shape=FAKE_LIDAR_SHAPE, dtype="float32"),
            "position": Box(-math.inf, math.inf, shape=(3,), dtype="float32"),
            "target_position": Box(-math.inf, math.inf, shape=(3,), dtype="float32"),
            "next_waypoint_position": Box(-math.inf, math.inf, shape=(3,), dtype="float32"),
            "speed": Box(-math.inf, math.inf, shape=(1,), dtype="float32"),
            "situation": Discrete(4),
        })
        self._rng = random.Random()
        self._seed = None
        self._scenario = None
        self._situation = 0
        self._position = [0.0, 0.0, 0.0]
        self._target = [0.0, 0.0, 0.0]
        self._next_waypoint = [0.0, 0.0, 0.0]
        self._speed = 0.0
        self._heading = 0.0
        self._steering = 0.0
        self._throttle = 0.0
        self._steps = 0
        self._terminated = False
        self._truncated = False
        self._observation = None

    # -- gymnasium surface -------------------------------------------------
    def reset(self, seed=None, options=None):
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        options = dict(options or {})
        requested = options.get("scenario_name")
        if requested is None:
            self._scenario = self._rng.choice(self._scenario_names)
        else:
            self._scenario = str(requested)
        self._situation = SITUATION_INDEX.get(self._scenario, 0)
        # placeholder: initial position, heading and target are test data
        self._position = [self._rng.uniform(-2.0, 2.0), self._rng.uniform(-2.0, 2.0), 0.0]
        self._heading = self._rng.uniform(-0.2, 0.2)
        self._target = [10.0 + self._rng.uniform(-1.0, 1.0), self._rng.uniform(-1.0, 1.0), 0.0]
        self._next_waypoint = [(self._position[0] + self._target[0]) / 2.0,
                               (self._position[1] + self._target[1]) / 2.0, 0.0]
        self._speed = 0.0
        self._heading = 0.0
        self._steering = 0.0
        self._throttle = 0.0
        self._steps = 0
        self._terminated = False
        self._truncated = False
        self._observation = self._make_observation()
        info = {"scenario_name": self._scenario,
                "waypoints": [list(self._next_waypoint), list(self._target)]}
        return self._observation, info

    def step(self, action):
        if self._observation is None:
            raise RuntimeError("reset() must be called before step()")
        if self._terminated or self._truncated:
            raise RuntimeError("the episode has ended; reset() first")
        steering, throttle = self._decode_action(action)
        self._steering = steering
        self._throttle = throttle
        self._steps += 1
        # placeholder: an analytic kinematic rule, not CARLA's vehicle physics
        self._speed = min(MAX_SPEED, max(0.0, self._speed + throttle * THROTTLE_RATE * DT_S))
        self._heading += steering * STEER_RATE * DT_S
        self._position = [self._position[0] + self._speed * math.cos(self._heading) * DT_S,
                          self._position[1] + self._speed * math.sin(self._heading) * DT_S,
                          0.0]
        distance = math.dist(self._position[:2], self._target[:2])
        self._next_waypoint = [(self._position[0] + self._target[0]) / 2.0,
                               (self._position[1] + self._target[1]) / 2.0, 0.0]
        # placeholder: reward and termination are test data
        reward = -0.01 * distance
        self._terminated = distance <= TARGET_DISTANCE
        self._truncated = self._steps >= self._max_steps
        self._observation = self._make_observation()
        info = {"scenario_name": self._scenario,
                "waypoints": [list(self._next_waypoint), list(self._target)]}
        return self._observation, reward, self._terminated, self._truncated, info

    def render(self, mode="human"):
        if mode != "human":
            raise NotImplementedError("This mode is not implemented yet")
        return None

    def close(self):
        self._observation = None

    # -- helpers -----------------------------------------------------------
    def _decode_action(self, action):
        if not self._continuous:
            index = int(action)
            # placeholder: accelerate, decelerate, left, right
            table = {0: (0.0, 1.0), 1: (0.0, -1.0), 2: (-1.0, 0.5), 3: (1.0, 0.5)}
            if index not in table:
                raise ValueError("discrete action must be 0..3")
            return table[index]
        values = _flatten(action)
        if len(values) != 2:
            raise ValueError("continuous action must have two elements")
        return float(values[0]), float(values[1])

    def _make_observation(self):
        # placeholder: the pixel and scan values are test data; the keys, ranks and dtypes are the upstream ones
        red = int(128 + 16 * self._situation)
        green = int(max(0, min(255, 128 + 20 * self._speed)))
        blue = int(max(0, min(255, 128 + 20 * self._steering)))
        rgb = [[[red, green, blue] for _ in range(FAKE_RGB_SHAPE[1])]
               for _ in range(FAKE_RGB_SHAPE[0])]
        distance = math.dist(self._position[:2], self._target[:2])
        lidar = [[distance, self._speed, self._steering, self._heading]
                 for _ in range(FAKE_LIDAR_SHAPE[0])]
        return {
            "rgb_data": rgb,
            "lidar_data": lidar,
            "position": list(self._position),
            "target_position": list(self._target),
            "next_waypoint_position": list(self._next_waypoint),
            "speed": [self._speed],
            "situation": self._situation,
        }
