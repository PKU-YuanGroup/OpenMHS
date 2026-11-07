"""Fake backend of the MetaDrive driver: a small kinematic stand-in for ``MetaDriveEnv``.

Why a fake: the acceptance gate runs without MetaDrive's runtime dependencies (panda3d, panda3d-gltf, numpy,
opencv-python; setup.py:90-92) and package code never imports the clone.  This module therefore does not run the
upstream simulator.  It re-implements only the public surface the gymnasium bridge uses -- ``action_space``,
``observation_space``, ``reset``, ``step``, ``seed`` and ``close`` -- which are the members of
``metadrive.envs.metadrive_env:MetaDriveEnv`` reached through ``BaseEnv`` (gate G7).

The fake is kinematic: it integrates one 0.1 s car-like step per environment step, while the upstream environment
runs five 0.02 s physics steps per ``env.step`` (base_env.py:189-191).  It has no Panda3D scene, map, traffic,
contacts, rendering or sensor model.  The observation is a synthetic vector shaped like the default
``LidarStateObservation``: 6 ego values + 10 navigation values + 2 side-detector values + 1 lane-line value + 240
lidar rays = 259 floats in [0, 1] (state_obs.py:22-28 and :175-186, base_navigation.py:18-19 and :280-282,
base_env.py:170).  Nothing here is a physical measurement, and none of it was compared with an upstream run.

Every number below is test data, not a Fact or a Limit: the synthetic ones are marked ``# placeholder``.
"""

import math
import random

# Upstream default sizes; the comments give the clone lines that state them.
EGO_STATE_WIDTH = 6          # placeholder; StateObservation.ego_state_obs_dim (obs/state_obs.py:11)
NAVIGATION_WIDTH = 10        # placeholder; 2 waypoints * 5 values (base_navigation.py:18-19, :280-282)
SIDE_DETECTOR_WIDTH = 2      # placeholder; side_detector num_lasers 0 -> 2 values (state_obs.py:158-159)
LANE_LINE_WIDTH = 1          # placeholder; lane_line_detector num_lasers 0 -> 1 value (state_obs.py:160-161)
LIDAR_WIDTH = 240            # placeholder; default lidar num_lasers (envs/base_env.py:170)
OBSERVATION_WIDTH = EGO_STATE_WIDTH + NAVIGATION_WIDTH + SIDE_DETECTOR_WIDTH + LANE_LINE_WIDTH + LIDAR_WIDTH
ACTION_WIDTH = 2             # placeholder; default Box(-1.0, 1.0, shape=(2,)) (policy/env_input_policy.py:61-62)
HORIZON = 1000               # placeholder; default horizon (envs/metadrive_env.py:58)
STEP_SECONDS = 0.1           # placeholder; 5 * 0.02 s physics steps per env.step (envs/base_env.py:189-191)
MAX_SPEED = 30.0             # placeholder
ACCELERATION = 3.0           # placeholder
TURN_RATE = 1.0              # placeholder
ROAD_HALF_WIDTH = 7.0        # placeholder
REWARD_PER_STEP = 1.0        # placeholder
INITIAL_LATERAL = 0.5        # placeholder
INITIAL_HEADING = 0.05       # placeholder
LIDAR_OFFSET = EGO_STATE_WIDTH + NAVIGATION_WIDTH + SIDE_DETECTOR_WIDTH + LANE_LINE_WIDTH


def _clip(value, low, high):
    """Clamp a float to ``[low, high]`` (test data; the upstream policy clips to [-1, 1] at env_input_policy.py:34)."""
    return max(low, min(high, float(value)))


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: one lower and one upper bound per flattened element.

    The gymnasium bridge reads ``low``, ``high``, ``shape`` and ``dtype`` through this surface and derives the
    ``cap.world.step.v1`` input schema and its limits from them.
    """

    def __init__(self, low, high, shape=(), dtype="float32"):
        self.shape = tuple(int(size) for size in shape)
        count = 1
        for size in self.shape:
            count *= size
        if isinstance(low, (list, tuple)):
            self.low = [float(value) for value in low]
        else:
            self.low = [float(low)] * count
        if isinstance(high, (list, tuple)):
            self.high = [float(value) for value in high]
        else:
            self.high = [float(high)] * count
        self.dtype = dtype

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.low):
            return False
        return all(self.low[index] <= float(item) <= self.high[index] for index, item in enumerate(value))


class FakeMetaDriveEnv:
    """A kinematic stand-in with the public members of ``MetaDriveEnv`` that the bridge uses.

    ``reset(seed)`` returns ``(observation, info)``, ``step(action)`` returns the five-value
    ``(observation, reward, terminated, truncated, info)`` tuple, and ``seed``/``close`` mirror the upstream
    methods.  The public members are the names the upstream class inherits from ``BaseEnv`` (gate G7).
    """

    def __init__(self, config=None):
        if config:
            raise ValueError("the fake MetaDrive does not accept a configuration")
        self._rng = random.Random(0)
        self._seed = 0
        self._pending_seed = None
        self._observation = None
        self._episode_length = 0
        self._x = 0.0
        self._y = 0.0
        self._heading = 0.0
        self._speed = 0.0
        self._steering = 0.0
        self._throttle = 0.0
        self._terminated = False
        self._truncated = False

    @property
    def action_space(self):
        """The default continuous action: ``Box(-1.0, 1.0, shape=(2,))`` (env_input_policy.py:61-62)."""
        return Box(-1.0, 1.0, shape=(ACTION_WIDTH,))

    @property
    def observation_space(self):
        """The default lidar/state observation: ``Box(-0.0, 1.0, shape=(259,))`` (state_obs.py:186)."""
        return Box(-0.0, 1.0, shape=(OBSERVATION_WIDTH,))

    def seed(self, seed=None):
        """Remember a seed for the next reset (upstream ``BaseEnv.seed``, base_env.py:684-686)."""
        if seed is not None:
            self._pending_seed = int(seed)
            self._rng = random.Random(int(seed))

    def reset(self, seed=None):
        """Reset the kinematic state and return ``(observation, info)``."""
        if seed is None:
            seed = self._pending_seed if self._pending_seed is not None else self._seed
        self._pending_seed = None
        self._seed = int(seed) if seed is not None else 0
        self._rng = random.Random(self._seed)
        self._x = 0.0                                                          # placeholder
        self._y = self._rng.uniform(-INITIAL_LATERAL, INITIAL_LATERAL)         # placeholder
        self._heading = self._rng.uniform(-INITIAL_HEADING, INITIAL_HEADING)   # placeholder
        self._speed = 0.0                                                      # placeholder
        self._steering = 0.0                                                   # placeholder
        self._throttle = 0.0                                                   # placeholder
        self._episode_length = 0
        self._terminated = False
        self._truncated = False
        self._observation = self._observe()
        return list(self._observation), {"seed": self._seed}

    def step(self, action):
        """Apply one 0.1 s kinematic step and return the five-value environment result."""
        if self._observation is None:
            raise RuntimeError("Call reset before using step method.")
        if not isinstance(action, (list, tuple)) or len(action) != ACTION_WIDTH:
            raise ValueError(f"expected a {ACTION_WIDTH}-element action, got {action!r}")
        self._steering = _clip(action[0], -1.0, 1.0)              # placeholder bounds
        self._throttle = _clip(action[1], -1.0, 1.0)              # placeholder bounds
        self._speed = _clip(self._speed + self._throttle * ACCELERATION * STEP_SECONDS,
                            0.0, MAX_SPEED)                       # placeholder model
        self._heading += self._steering * TURN_RATE * STEP_SECONDS * (self._speed / MAX_SPEED)  # placeholder
        self._x += math.cos(self._heading) * self._speed * STEP_SECONDS    # placeholder
        self._y += math.sin(self._heading) * self._speed * STEP_SECONDS    # placeholder
        self._episode_length += 1
        self._truncated = self._episode_length >= HORIZON
        self._terminated = abs(self._y) > ROAD_HALF_WIDTH
        reward = 0.0 if self._terminated else REWARD_PER_STEP     # placeholder
        self._observation = self._observe()
        info = {"seed": self._seed, "episode_length": self._episode_length}
        return list(self._observation), reward, self._terminated, self._truncated, info

    def close(self):
        """Drop the observation; the fake owns no engine."""
        self._observation = None

    def _observe(self):
        """Build the synthetic 259-float observation.  Every value is test data (placeholder)."""
        values = [0.0] * OBSERVATION_WIDTH                        # placeholder
        values[0] = _clip(0.5 + self._x / 100.0, 0.0, 1.0)        # placeholder ego state
        values[1] = _clip(0.5 + self._y / 100.0, 0.0, 1.0)        # placeholder ego state
        values[2] = _clip(0.5 + self._heading / math.pi, 0.0, 1.0)  # placeholder ego state
        values[3] = _clip(self._speed / MAX_SPEED, 0.0, 1.0)      # placeholder ego state
        values[4] = _clip((self._steering + 1.0) / 2.0, 0.0, 1.0)  # placeholder ego state
        values[5] = _clip((self._throttle + 1.0) / 2.0, 0.0, 1.0)  # placeholder ego state
        values[6] = _clip(0.5 + self._y / (2.0 * ROAD_HALF_WIDTH), 0.0, 1.0)  # placeholder side detector
        values[7] = _clip(0.5 - self._y / (2.0 * ROAD_HALF_WIDTH), 0.0, 1.0)  # placeholder side detector
        values[8] = _clip(0.5 + self._y / ROAD_HALF_WIDTH, 0.0, 1.0)          # placeholder lane detector
        values[9] = _clip(self._x / 100.0, 0.0, 1.0)              # placeholder navigation
        values[10] = _clip(1.0 - self._x / 100.0, 0.0, 1.0)       # placeholder navigation
        for index in range(11, LIDAR_OFFSET):
            values[index] = 0.5                                   # placeholder navigation
        for index in range(LIDAR_OFFSET, OBSERVATION_WIDTH):
            values[index] = _clip(0.5 + 0.5 * math.sin(0.1 * index + self._y + self._heading + self._seed),
                                  0.0, 1.0)                        # placeholder lidar
        return values
