"""Fake backend of the racecar_gym Gymnasium driver: a pure Python stand-in for ``SingleAgentRaceEnv``.

Why a fake: the upstream package needs pybullet, numpy and gymnasium (``requirements.txt``), downloads its track
scenes on first use, and package code never imports the read-only clone.  The gate therefore runs the package's own
fake.  Its public methods are the ones ``racecar_gym.envs.gym_api:SingleAgentRaceEnv`` defines (gate G7):
``reset``, ``step`` and the ``observation_space`` property; ``action_space`` is the instance attribute upstream sets
in ``__init__``.  The ``Dict`` and ``Box`` classes only duck-type the Gymnasium spaces the bridge reads
(``spaces``, ``low``, ``high``, ``shape``); they are not imported from the clone.

What this is not: the pybullet model.  The dynamics, progress, reward, pose and lidar values are placeholders, not the
vehicle physics or the real track.  The real lidar length is 1080 rays (``models/vehicles/racecar/racecar.yml:55``);
the scan here is a constant list of that length.  All differences are listed in the driver's fidelity ``gaps``.

Every numeric constant here is fake test data, not a fact about the device: each is marked ``# placeholder`` and none
is copied into a ``Fact``, a ``Limit`` or the reference.
"""

import random

# placeholder: the simulation interval used by this fake; the real scene supplies its own time_step
STEP_S = 0.01
# placeholder: progress gained per transition at full motor command
PROGRESS_PER_STEP = 0.001
# placeholder: the maximize_progress default reward scaling used by this fake
PROGRESS_REWARD = 100.0
# placeholder: the start progress is drawn uniformly from this interval
START_PROGRESS_MAX = 0.01
# placeholder: the real single-agent observation has 1080 lidar rays (models/vehicles/racecar/racecar.yml:55)
LIDAR_RAYS = 1080
# placeholder: the real lidar space is bounded by min_range and min_range+range (racecar_gym/bullet/sensors.py:109-112)
LIDAR_MIN = 0.25
LIDAR_MAX = 15.25
# placeholder: a finite stand-in for the real pose space bounds
POSE_XY = 100.0
POSE_Z = 3.0
POSE_ANGLE = 3.141592653589793
# placeholder: the real velocity space bounds (models/vehicles/racecar/racecar.yml:46-47)
VELOCITY_LINEAR = 14.0
VELOCITY_ANGULAR = 6.0
# placeholder: the real acceleration bounds are infinite; a finite stand-in keeps this module simple
ACCELERATION = 1000.0
# placeholder: upstream declares the observation time Box from 0 to 1 but writes the growing simulation time
TIME_DECLARED_MAX = 1.0


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: ``low`` and ``high`` per element and a ``shape``."""

    def __init__(self, low, high, shape=None):
        if shape is None:
            low = list(low) if isinstance(low, (list, tuple)) else [low]
            high = list(high) if isinstance(high, (list, tuple)) else [high]
            if len(low) != len(high):
                raise ValueError("low and high must have the same length")
            shape = (len(low),)
        else:
            shape = tuple(shape)
            count = 1
            for size in shape:
                count *= int(size)
            low = [float(low)] * count
            high = [float(high)] * count
        self.low = low
        self.high = high
        self.shape = shape
        self.dtype = "float32"

    def contains(self, value):
        values = value if isinstance(value, (list, tuple)) else [value]
        return len(values) == len(self.low) and all(
            float(item) >= low and float(item) <= high for item, low, high in zip(values, self.low, self.high))


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a mapping of space name to space (the bridge reads ``spaces``)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _first(value):
    """The scalar of an action member: the bridge passes a one-element list, upstream passes a numpy array."""
    item = getattr(value, "item", None)
    if callable(item):
        try:
            value = item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, (list, tuple)):
        return float(value[0])
    return float(value)


def _clip(value):
    return max(-1.0, min(1.0, value))


class FakeSingleAgentRaceEnv:
    """The single-agent race environment without pybullet: ``reset(seed, options)`` and ``step(action)`` only."""

    def __init__(self, scenario=None, render_mode=None, render_options=None):
        # The real class builds these from the scenario path and the vehicle YAML; the fake uses stand-ins.
        self.action_space = Dict({
            # placeholder: the normalized command bounds of the two default actuators
            "steering": Box(low=[-1.0], high=[1.0]),
            # placeholder: the normalized command bounds of the two default actuators
            "motor": Box(low=[-1.0], high=[1.0]),
        })
        self._observation_space = Dict({
            # placeholder: six-element pose (x, y, z, roll, pitch, yaw)
            "pose": Box(
                low=[-POSE_XY, -POSE_XY, -POSE_Z, -POSE_ANGLE, -POSE_ANGLE, -POSE_ANGLE],
                high=[POSE_XY, POSE_XY, POSE_Z, POSE_ANGLE, POSE_ANGLE, POSE_ANGLE],
            ),
            # placeholder: six-element velocity (three linear and three angular components)
            "velocity": Box(
                low=[-VELOCITY_LINEAR] * 3 + [-VELOCITY_ANGULAR] * 3,
                high=[VELOCITY_LINEAR] * 3 + [VELOCITY_ANGULAR] * 3,
            ),
            # placeholder: six-element acceleration (three linear and three angular components)
            "acceleration": Box(low=[-ACCELERATION] * 6, high=[ACCELERATION] * 6),
            # placeholder: the real lidar length and its stand-in bounds
            "lidar": Box(low=LIDAR_MIN, high=LIDAR_MAX, shape=(LIDAR_RAYS,)),
            # placeholder: one simulated-time element, declared 0 to 1 while the real value grows
            "time": Box(low=0.0, high=TIME_DECLARED_MAX, shape=(1,)),
        })
        self._scenario = scenario
        self._render_mode = render_mode
        self._render_options = dict(render_options or {})
        self._initialized = False
        self._rng = random.Random()
        self._time = 0.0
        self._progress = 0.0
        self._speed = 0.0
        self._tick = 0

    @property
    def observation_space(self):
        return self._observation_space

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        mode = (options or {}).get("mode", "grid")
        if mode not in ("grid", "random", "random_bidirectional", "random_ball"):
            raise NotImplementedError(mode)
        self._progress = self._rng.uniform(0.0, START_PROGRESS_MAX)
        self._speed = 0.0
        self._tick = 0
        self._time = STEP_S
        self._initialized = True
        return self._observation(), self._state()

    def step(self, action):
        if not self._initialized:
            raise AssertionError("Reset before calling step")
        # placeholder: the stand-in accepts both normalized commands and does not turn the car with steering
        _steering = _clip(_first(action["steering"]))
        motor = _clip(_first(action["motor"]))
        previous = self._progress
        # placeholder: a simple kinematic speed and progress model, not the pybullet vehicle
        self._speed = 0.5 * motor
        self._progress = min(1.0, self._progress + max(0.0, self._speed) * PROGRESS_PER_STEP)
        self._time += STEP_S
        self._tick += 1
        reward = (self._progress - previous) * PROGRESS_REWARD
        return self._observation(), reward, False, False, self._state()

    def _state(self):
        # placeholder: the ground-truth state fields of the real agent, with stand-in values
        return {
            "time": self._time,
            "progress": self._progress,
            "lap": 0,
            "wall_collision": False,
            "opponent_collisions": [],
        }

    def _observation(self):
        # placeholder: a parked car at a progress-derived x position and a constant lidar scan
        pose = [self._progress * 100.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        velocity = [self._speed, 0.0, 0.0, 0.0, 0.0, 0.0]
        acceleration = [0.0] * 6
        lidar = [LIDAR_MAX] * LIDAR_RAYS
        return {
            "pose": pose,
            "velocity": velocity,
            "acceleration": acceleration,
            "lidar": lidar,
            "time": [self._time],
        }
