"""Fake backend of the DRL-Nav Gymnasium driver: a pure Python stand-in for ``AirSimDroneEnv``.

Why a fake: the upstream class connects an ``airsim.MultirotorClient`` to a separately downloaded Windows
Unreal/AirSim scene (``scripts/airsim_env.py:8`` and ``README.md:8``), the clone is never imported or run by
this package, and the gate has no AirSim runtime.  This module re-implements the observation/action surface
of ``scripts.airsim_env:AirSimDroneEnv`` (the class the driver names as ``native``) as a small kinematic
corridor model.  The public members are the ones the upstream class has (``reset``, ``step``, ``get_obs``;
gate G7), and ``Box`` duck-types ``gym.spaces.Box`` (the bridge reads ``low``, ``high`` and ``shape``).

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* the fake moves the agent directly by the commanded body-frame velocity for the 1 s command period; the
  Unreal/AirSim scene has rigid-body dynamics, contacts and a renderer that are not modelled here;
* the observation is a synthetic depth grid of the configured shape with a target marker, not a rendered
  Unreal camera image;
* the fake supports reset options (``start``, ``target``, ``sections``) for deterministic tests; the upstream
  ``reset`` takes no arguments and draws its start from numpy's global generator;
* there is no ``close``, no wrapper stack and no AirSim collision service; the fake computes the wall
  collision from the target distance at the wall crossing (``scripts/airsim_env.py:138-148``).

Every constant copied from the clone cites its line at the pinned commit
a996f5461c90adfe765ca3274d4da7c8499891c3.  The rest are test data and are marked ``# placeholder``.
"""

import math
import random

# scripts/airsim_env.py:28-29 (the action space)
ACTION_LOW = -0.6
ACTION_HIGH = 0.6
# scripts/airsim_env.py:87-88 (the command vx and its duration; client.py:1027 says the duration is in seconds)
FORWARD_SPEED = 0.4
COMMAND_SECONDS = 1.0
# scripts/airsim_env.py:111-113 (depth clip and the 255/3.4 scaling)
DEPTH_CLIP = 3.4
DEPTH_SCALE = 255.0 / 3.4
# scripts/airsim_env.py:138 and :146 (wall crossing and the hole radius the reward uses)
PASS_DISTANCE = 3.7
HOLE_RADIUS = 0.55
# scripts/airsim_env.py:145 (the comment "sin(60) ~ 1.732")
HALF_FOV_SIN = 1.732
# scripts/env_config.yml:3-7 first section (offset 0, target [1, -0.5]); the fake never reads the clone
_DEFAULT_SECTION = {"offset": [0.0], "target": [1.0, -0.5]}   # placeholder
# the synthetic depth grid: pixels per world unit and marker radius
_PIXELS_PER_UNIT = 10.0                                      # placeholder
_MARKER_PIXELS = 4.0                                         # placeholder
_DEFAULT_SEED = 0                                            # placeholder


class Box:
    """Duck-typed ``gym.spaces.Box``: flat ``low``/``high`` bounds and a ``shape``."""

    def __init__(self, low, high, shape=None, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = dtype


def _sections(env_config):
    """The section list of ``env_config``, or the single default section of this fake."""
    if isinstance(env_config, dict):
        sections = env_config.get("sections")
        if sections:
            return list(sections)
    return [dict(_DEFAULT_SECTION)]


class FakeAirSimDroneEnv:
    """A kinematic corridor with the ``reset``/``step``/``get_obs`` surface of ``AirSimDroneEnv``."""

    def __init__(self, ip_address="127.0.0.1", image_shape=(50, 50, 1), env_config=None, input_mode="depth"):
        # The upstream constructor takes these four arguments (scripts/airsim_env.py:12).  The defaults are
        # the depth configuration of train.py:22; they are placeholders, not device limits.
        self.image_shape = tuple(int(value) for value in image_shape)
        self.input_mode = input_mode
        if input_mode == "multi_rgb":
            self._obs_shape = (self.image_shape[0], self.image_shape[1] * 3, 1)   # scripts/airsim_env.py:20-22
        else:
            self._obs_shape = self.image_shape
        count = 1
        for value in self._obs_shape:
            count *= int(value)
        self._obs_count = count
        self.action_space = Box([ACTION_LOW] * 2, [ACTION_HIGH] * 2, shape=(2,), dtype="float32")
        self.observation_space = Box([0] * count, [255] * count, shape=self._obs_shape, dtype="uint8")
        self.sections = _sections(env_config)
        self._rng = random.Random(_DEFAULT_SEED)
        self.info = {"collision": False}
        self.collision_time = 0
        self.random_start = True
        self.agent_start_pos = float(_DEFAULT_SECTION["offset"][0])
        self.target_pos = [float(value) for value in _DEFAULT_SECTION["target"]]
        self.target_dist_prev = 0.0
        self._x = self.agent_start_pos
        self._y = 0.0
        self._z = 0.0
        self._tick = 0
        self._done = False

    def reset(self, *, seed=None, options=None):
        """Start a new episode; ``seed`` fixes the fake's random start (the upstream reset takes none)."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        options = dict(options or {})
        sections = options.get("sections") or self.sections
        if options.get("section") is not None:
            index = int(options["section"]) % len(sections)
        elif self.random_start and len(sections) > 1:
            index = self._rng.randrange(len(sections))
        else:
            index = 0
        section = sections[index]
        self.agent_start_pos = float(section["offset"][0])
        self.target_pos = [float(value) for value in section["target"]]
        if options.get("target") is not None:
            self.target_pos = [float(value) for value in options["target"]]
        start = options.get("start")
        if start is None:
            y_pos, z_pos = (self._rng.uniform(-1.0, 1.0), self._rng.uniform(-1.0, 1.0))  # scripts/airsim_env.py:72
        else:
            y_pos, z_pos = float(start[0]), float(start[1])
        self._x = self.agent_start_pos
        self._y = y_pos
        self._z = z_pos
        self._tick = 0
        self._done = False
        self.collision_time = 0
        self.info = {"collision": False}
        self.target_dist_prev = math.hypot(y_pos - self.target_pos[0], -z_pos - self.target_pos[1])
        return self.get_obs()                                   # scripts/airsim_env.py:42-45

    def step(self, action):
        """Advance one 1 s velocity command and return the legacy (obs, reward, done, info) tuple."""
        if self._done:
            raise RuntimeError("the episode has ended; reset the environment first")
        if len(action) != 2:
            raise ValueError("the action must contain vy and vz")
        self._x += FORWARD_SPEED * COMMAND_SECONDS              # scripts/airsim_env.py:87-88
        self._y += float(action[0]) * COMMAND_SECONDS
        self._z += float(action[1]) * COMMAND_SECONDS
        self._tick += 1
        traveled = self._x - self.agent_start_pos
        target_dist = math.hypot(self._y - self.target_pos[0], -self._z - self.target_pos[1])
        distance_3d = math.sqrt(target_dist * target_dist + (PASS_DISTANCE - traveled) ** 2)
        reward = math.exp(-distance_3d) * 30.0                 # scripts/airsim_env.py:125-130
        collision = traveled >= PASS_DISTANCE and target_dist > HOLE_RADIUS
        done = False
        if collision:                                          # scripts/airsim_env.py:133-135
            reward = -100.0
            done = True
        elif traveled > PASS_DISTANCE:                         # scripts/airsim_env.py:137-139
            done = True
        elif (target_dist - HOLE_RADIUS) > (PASS_DISTANCE - traveled) * HALF_FOV_SIN:
            reward = -100.0                                    # scripts/airsim_env.py:141-148
            done = True
        self._done = done
        self.info = {"collision": collision}
        return self.get_obs(), reward, done, dict(self.info)

    def get_obs(self):
        """A synthetic depth image of the configured shape with the target marker."""
        height = int(self._obs_shape[0])
        width = int(self._obs_shape[1])
        channels = int(self._obs_shape[2]) if len(self._obs_shape) > 2 else 1
        traveled = self._x - self.agent_start_pos
        ahead = max(0.0, PASS_DISTANCE - traveled)
        base = int(min(DEPTH_CLIP, ahead) * DEPTH_SCALE)        # scripts/airsim_env.py:111-113
        base = max(0, min(255, base))
        rel_y = self._y - self.target_pos[0]
        rel_z = -self._z - self.target_pos[1]
        center_x = int(width / 2.0 + rel_y * _PIXELS_PER_UNIT)
        center_y = int(height / 2.0 + rel_z * _PIXELS_PER_UNIT)
        radius_sq = _MARKER_PIXELS * _MARKER_PIXELS
        pixels = [base] * (height * width)
        for row in range(height):
            for col in range(width):
                if (col - center_x) ** 2 + (row - center_y) ** 2 <= radius_sq:
                    pixels[row * width + col] = 0
        if channels == 1:
            return pixels
        expanded = []
        for value in pixels:
            expanded.extend([value] * channels)
        return expanded
