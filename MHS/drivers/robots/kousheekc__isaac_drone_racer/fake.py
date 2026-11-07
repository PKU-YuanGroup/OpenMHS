"""Fake backend of the Isaac Drone Racer driver: a pure Python stand-in for the registered environment.

Why a fake: the gate cannot open the upstream environment.  ``Isaac-Drone-Racer-v0`` is registered with the
external entry point ``isaaclab.envs:ManagerBasedRLEnv`` (tasks/drone_racer/__init__.py:15), and Isaac Sim 4.5.0
(README.md:7), Isaac Lab v2.1.0 (README.md:44-48) and a GPU are required; package code never imports the clone.
This module is a deterministic stand-in with the Gymnasium environment interface the bridge reads
(``action_space``, ``observation_space``, ``reset``, ``step``, ``close``; gate G7).

What it models, from the clone at the pinned commit (d530f67768d53701454f406e4da967e0e9c30842):

* four raw actions per environment (``tasks/drone_racer/mdp/actions.py:44``), each clamped to [-1, 1] and mapped
  by (x + 1) / 2 to a rotor speed up to omega_max (``actions.py:97-99, 152``);
* the total thrust ``thrust_coef * sum(omega**2)`` along the body z axis (``actions.py:106-109, 148``); the
  vertical acceleration is ``thrust / mass - gravity`` with the mass and gravity of the thrust-coefficient
  derivation (``actions.py:150-151``);
* the policy observation group as six concatenated terms: position (3), attitude quaternion (4), body linear
  velocity (3), body angular velocity (3), target position in the body frame (3) and the last action (4)
  (``tasks/drone_racer/drone_racer_env_cfg.py:88-97``), 20 values in one ``policy`` group because the critic
  group is disabled (``drone_racer_env_cfg.py:215``);
* the 10 ms environment step (decimation 4 of a 1/400 s simulation step, ``drone_racer_env_cfg.py:220-226``),
  the 20 s time limit (``drone_racer_env_cfg.py:221``) and the 20 m flyaway termination
  (``drone_racer_env_cfg.py:188``);
* the default first gate at (0.0, 0.0, 1.0) (``drone_racer_env_cfg.py:41``).

What this is not, and every difference is also a fidelity gap of the driver:

* the rigid-body attitude dynamics, the body moments, aerodynamic drag and contacts are not modelled: only the
  vertical acceleration from the total thrust moves the drone;
* the collision termination and the reward terms are not modelled: ``step`` always returns reward 0.0;
* the initial state is drawn from placeholder bounds and was not compared with the upstream reset;
* the action and observation spaces are inferred from the configuration and the Gymnasium environment interface;
  the isaaclab class that builds them lies outside the clone and was not run.

The numbers marked ``placeholder`` below are test data of this stand-in, not facts of the device.
"""

import math
import random

# tasks/drone_racer/mdp/actions.py:144-155 (ControlActionCfg); the moments of the allocation matrix are not modelled
THRUST_COEF = 2.25e-7               # actions.py:148
OMEGA_MAX = 5145.0                  # actions.py:152
MOTOR_COUNT = 4                     # actions.py:44 (four raw actions, one per rotor)
DRONE_MASS = 0.6076                 # actions.py:150 (the thrust-coefficient derivation states this mass)
GRAVITY = 9.81                      # actions.py:150
# tasks/drone_racer/drone_racer_env_cfg.py:220-226: decimation 4 * sim.dt 1/400 s
TIMESTEP_S = 0.01                   # placeholder arithmetic: 4 / 400
# tasks/drone_racer/drone_racer_env_cfg.py:221 with the 10 ms step: 20 s / 0.01 s
EPISODE_STEPS = 2000                # placeholder arithmetic: 20 / 0.01
FLYAWAY_DISTANCE = 20.0             # drone_racer_env_cfg.py:188
FIRST_GATE = (0.0, 0.0, 1.0)        # drone_racer_env_cfg.py:41
# placeholder: this stand-in starts near the first gate; the upstream reset pose is drawn by the command term
START_OFFSET = 0.5
OBSERVATION_SIZE = 20               # placeholder: 3 + 4 + 3 + 3 + 3 + 4 terms of drone_racer_env_cfg.py:88-93


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()


class FakeDroneRacerEnv:
    """Isaac-Drone-Racer-v0 without Isaac Sim: ``reset(seed, options)`` and ``step(action)`` only.

    The observations are the 20 values of the policy group; the environment is single-instance (the upstream
    configuration runs 4096 parallel environments, which this stand-in does not mirror).
    """

    def __init__(self, **_options):
        # actions.py:97 (raw action in [-1, 1]) and actions.py:44 (four raw actions)
        self.action_space = Box([-1.0] * MOTOR_COUNT, [1.0] * MOTOR_COUNT)
        # drone_racer_env_cfg.py:88-97 and :215: one concatenated policy group, no critic group
        self.observation_space = Dict({"policy": Box([-math.inf] * OBSERVATION_SIZE,
                                                      [math.inf] * OBSERVATION_SIZE)})
        self._rng = random.Random()
        self._pos = [0.0, 0.0, FIRST_GATE[2]]
        self._vel = [0.0, 0.0, 0.0]
        self._ang_vel = [0.0, 0.0, 0.0]
        self._target = list(FIRST_GATE)
        self._last_action = [0.0] * MOTOR_COUNT
        self._tick = 0
        self._episode = 0
        self._closed = False

    def _observation(self):
        position = list(self._pos)
        attitude = [1.0, 0.0, 0.0, 0.0]                       # identity quaternion (w, x, y, z)
        linear_velocity = list(self._vel)
        angular_velocity = list(self._ang_vel)
        target_b = [self._target[index] - self._pos[index] for index in range(3)]
        return {"policy": position + attitude + linear_velocity + angular_velocity + target_b
                + list(self._last_action)}

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._pos = [self._target[0] + self._rng.uniform(-START_OFFSET, START_OFFSET),
                     self._target[1] + self._rng.uniform(-START_OFFSET, START_OFFSET),
                     self._target[2] + self._rng.uniform(-START_OFFSET, START_OFFSET)]
        self._vel = [0.0, 0.0, 0.0]
        self._ang_vel = [0.0, 0.0, 0.0]
        self._last_action = [0.0] * MOTOR_COUNT
        self._tick = 0
        self._episode += 1
        return self._observation(), {}

    def step(self, action):
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = [float(value) for value in action]
        if len(values) != MOTOR_COUNT:
            raise ValueError(f"the action has {MOTOR_COUNT} components, got {len(values)}")
        # actions.py:97-99: clamp to [-1, 1], map to [0, 1] and scale to the maximum rotor speed
        clamped = [min(1.0, max(-1.0, value)) for value in values]
        speeds = [(value + 1.0) / 2.0 * OMEGA_MAX for value in clamped]
        thrust = THRUST_COEF * sum(speed * speed for speed in speeds)        # actions.py:148, 106-107
        acceleration = thrust / DRONE_MASS - GRAVITY                         # actions.py:150-151
        self._vel[2] += acceleration * TIMESTEP_S
        self._pos[2] += self._vel[2] * TIMESTEP_S
        self._last_action = clamped
        self._tick += 1
        distance = math.dist(self._pos, self._target)
        terminated = distance > FLYAWAY_DISTANCE                             # drone_racer_env_cfg.py:188
        truncated = self._tick >= EPISODE_STEPS                              # drone_racer_env_cfg.py:221
        return self._observation(), 0.0, terminated, truncated, {}

    def close(self):
        self._closed = True
