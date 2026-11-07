"""Fake backend of the RLRoverLab driver: an analytic stand-in for the AAU Rover navigation task.

The upstream environment is an Isaac Sim / Isaac Lab task (README.md:11) and neither Isaac Sim nor Isaac Lab is
installed where the gate runs, so the ``fake`` backend is a small pure-Python kinematic model of the same
Gymnasium interface.  It implements only the public members the upstream ``RoverEnv`` has (``reset``, ``step``,
``close``; gate G7) and the two spaces the Gymnasium bridge reads (``action_space``, ``observation_space``).

The model is intentionally F0 (kinematic/analytic):
``[linear velocity, angular velocity]`` moves a point robot directly, the target is a point at
``target_distance`` sampled on a circle, and the four scalar observation terms are computed from that state.
The height scan, the rigid-body dynamics, the contacts, the wheel-level Ackermann mapping, the reward terms and
the terminations are not modelled; the driver's fidelity ``gaps`` say so.  Every sourced constant cites its line
of the clone at the pinned commit; values that are test data carry ``# placeholder``.
"""

from __future__ import annotations

import math
import random

# rover_envs/envs/navigation/rover_env_cfg.py:352-353 (RoverEnvCfg.__post_init__): the control step is
# sim.dt * decimation.
SIM_DT_S = 1 / 30.0
DECIMATION = 6
CONTROL_DT_S = SIM_DT_S * DECIMATION

# rover_envs/envs/navigation/utils/terrains/terrain_importer.py:167 (RoverTerrainImporter.__init__)
TARGET_DISTANCE_M = 9.0
# rover_envs/envs/navigation/rover_env_cfg.py:274-276: the heading command is uniform in (-pi, pi).
HEADING_LOW, HEADING_HIGH = -math.pi, math.pi
# rover_envs/envs/navigation/rover_env_cfg.py:171-184: the observation scales of the distance and angle terms.
DISTANCE_SCALE = 0.11
ANGLE_SCALE = 1 / math.pi

# rover_envs/mdp/actions/ackermann_actions.py:70-72: a two-dimensional action (linear, angular velocity).
ACTION_DIM = 2
# The four scalar observation terms the fake keeps: the last action (2) and distance, heading, angle difference.
OBSERVATION_DIM = ACTION_DIM + 3


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``.

    The clone states no numeric action bounds: the space is supplied by the Isaac Lab base outside this repository,
    and the Ackermann term applies the two values directly (``process_actions``: ``raw * scale + offset``).  The fake
    therefore publishes an unbounded Box rather than inventing a bound.
    """

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


def _wrap_to_pi(angle):
    """Map an angle to ``[-pi, pi)`` (the upstream command uses Isaac Lab's ``wrap_to_pi``)."""
    return (angle + math.pi) % (2 * math.pi) - math.pi


class FakeAAURoverEnv:
    """The AAU Rover navigation task without Isaac Sim: a point robot with the same spaces and reset/step shape."""

    def __init__(self):
        self.action_space = Box([-math.inf] * ACTION_DIM, [math.inf] * ACTION_DIM, (ACTION_DIM,))
        self.observation_space = Box([-math.inf] * OBSERVATION_DIM, [math.inf] * OBSERVATION_DIM,
                                     (OBSERVATION_DIM,))
        self._rng = random.Random()
        self._x = 0.0                         # placeholder: a spawn position on the terrain
        self._y = 0.0                         # placeholder: a spawn position on the terrain
        self._yaw = 0.0                       # placeholder: a random spawn yaw
        self._target_x = TARGET_DISTANCE_M    # placeholder: replaced by reset()
        self._target_y = 0.0                  # placeholder: replaced by reset()
        self._target_heading = 0.0            # placeholder: replaced by reset()
        self._last_action = [0.0, 0.0]        # placeholder: the action term starts at zero (ackermann_actions.py:61)
        self._reset(seed=0, options=None)      # placeholder: the first episode starts from a fixed seed

    def _reset(self, seed, options):
        if seed is not None:
            self._rng = random.Random(seed)
        self._x = 0.0                                                   # placeholder
        self._y = 0.0                                                   # placeholder
        self._yaw = 0.0                                                 # placeholder
        # terrain_importer.py:207-214 samples a direction uniformly and puts the target on a circle.
        theta = self._rng.uniform(-math.pi, math.pi)                    # placeholder: the sampled direction
        self._target_x = TARGET_DISTANCE_M * math.cos(theta)
        self._target_y = TARGET_DISTANCE_M * math.sin(theta)
        # rover_env_cfg.py:274-276: the heading command is sampled uniformly from (-pi, pi).
        self._target_heading = self._rng.uniform(HEADING_LOW, HEADING_HIGH)
        self._last_action = [0.0, 0.0]                                  # placeholder
        return self._observation(), {}

    def _observation(self):
        """The four scalar observation terms the fake keeps (the height scan is omitted; see the driver gaps)."""
        dx, dy = self._target_x - self._x, self._target_y - self._y
        # angle_to_target_observation (observations.py:15-24) and distance_to_target_euclidean (:27-32).
        heading = math.atan2(dy, dx)
        distance = math.hypot(dx, dy)
        # angle_diff (observations.py:48-53) is the heading command minus the rover heading, wrapped.
        angle_diff = _wrap_to_pi(self._target_heading - self._yaw)
        # The observation scales are those of ObservationCfg (rover_env_cfg.py:171-184).
        return [self._last_action[0], self._last_action[1], DISTANCE_SCALE * distance,
                ANGLE_SCALE * heading, ANGLE_SCALE * angle_diff]

    def reset(self, *, seed=None, options=None):
        """Gymnasium reset: ``(observation, info)``; ``seed`` fixes the target and the next episode."""
        return self._reset(seed, options)

    def step(self, action):
        """Gymnasium step: ``(observation, reward, terminated, truncated, info)``.

        The motion is the direct kinematic integration of the two action values
        (``ackermann_actions.py:70-72``), not the wheel-level Ackermann mapping and not a rigid-body simulation.
        """
        if not isinstance(action, (list, tuple)) or len(action) != ACTION_DIM:
            raise ValueError(f"the action must be a list of {ACTION_DIM} numbers")
        linear, angular = float(action[0]), float(action[1])
        if not (math.isfinite(linear) and math.isfinite(angular)):
            raise ValueError("the action values must be finite")
        self._yaw = _wrap_to_pi(self._yaw + angular * CONTROL_DT_S)     # placeholder kinematics
        self._x += linear * CONTROL_DT_S * math.cos(self._yaw)          # placeholder kinematics
        self._y += linear * CONTROL_DT_S * math.sin(self._yaw)          # placeholder kinematics
        self._last_action = [linear, angular]
        # placeholder: the eight upstream reward terms (rover_env_cfg.py:199-241) and the terminations
        # (rover_env_cfg.py:244-261) are not modelled, so the fake reports zero reward and no done flag.
        return self._observation(), 0.0, False, False, {}

    def close(self):
        """Gymnasium close; the fake holds no resources."""
