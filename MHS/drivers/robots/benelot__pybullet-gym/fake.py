"""Fake backend of the pybullet-gym driver: a pure Python stand-in for ``InvertedPendulumBulletEnv``.

Why a fake: the upstream clone needs pybullet, gym and numpy, and package code never imports the clone, so the
acceptance gate runs this module instead of ``gym.make("InvertedPendulumPyBulletEnv-v0")``.  The public members
(``reset``, ``step``, ``close``; gate G7) and the two spaces match the upstream environment: the robot declares
``action_dim=1`` and ``obs_dim=5`` (``interted_pendulum.py:9``), the action space is ``Box(-1, 1)`` with one element
(``robot_bases.py:24-25``) and the observation space is ``Box(-inf, inf)`` with five elements (``robot_bases.py:26-27``).
The bridge reads only ``low``, ``high``, ``shape`` and ``dtype`` of the spaces.

What this is not: the Bullet physics of the clone.  The fake integrates a simplified cart-pole model with Python's
Euler method and placeholder masses; the pole angle, its reset draw, the 0.2 radian threshold, the reward and the
registered 1000-step limit follow the cited lines, but the motion does not match Bullet's joints and solver.  The
initial angle comes from Python's ``random.Random``; upstream draws it from numpy's generator.  There is no rendering.
The differences are listed in the driver's fidelity ``gaps``.

Nothing here talks to a device.
"""

import math
import random

# InvertedPendulumBulletEnv.create_single_player_scene: gravity 9.8, timestep 0.0165, frame_skip 1
# (pybulletgym/envs/roboschool/envs/pendulum/inverted_pendulum_env.py:14).
GRAVITY = 9.8
TIMESTEP = 0.0165
FRAME_SKIP = 1
DT = TIMESTEP * FRAME_SKIP
# InvertedPendulum.apply_action: 100 * clip(action, -1, 1) (pybulletgym/envs/roboschool/robots/pendula/
# interted_pendulum.py:25).
FORCE_SCALE = 100.0
# InvertedPendulum.robot_specific_reset: uniform(-0.1, 0.1) (interted_pendulum.py:16).
INITIAL_ANGLE = 0.1
# InvertedPendulumBulletEnv.step: done when abs(theta) > 0.2, reward 1.0 (inverted_pendulum_env.py:36, :35).
DONE_ANGLE = 0.2
REWARD = 1.0
# The registration sets max_episode_steps=1000 (pybulletgym/envs/__init__.py:8); gym.make wraps the env in a TimeLimit.
MAX_EPISODE_STEPS = 1000
# InvertedPendulum declares action_dim=1 and obs_dim=5 (interted_pendulum.py:9).
ACTION_SIZE = 1
OBSERVATION_SIZE = 5
# The MJCF pole runs from 0 to 0.6 along z (inverted_pendulum.xml:19); the fake takes its centre of mass halfway.
POLE_LENGTH = 0.6
ARM_LENGTH = POLE_LENGTH / 2.0
# Placeholder test data: the MJCF model states no mass and Bullet derives it from the geometry and density.
MASS_CART = 10.0                                # placeholder
MASS_POLE = 1.0                                 # placeholder
START_X = 0.0                                   # placeholder
START_X_DOT = 0.0                               # placeholder
START_THETA_DOT = 0.0                           # placeholder


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeInvertedPendulumEnv:
    """InvertedPendulumBulletEnv without Bullet: ``reset`` and ``step`` return what the bridge accepts."""

    def __init__(self):
        # robot_bases.py:24-27: Box(-ones([action_dim]), ones([action_dim])) and Box(-inf, inf) of obs_dim.
        self.action_space = Box([-1.0] * ACTION_SIZE, [1.0] * ACTION_SIZE)
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self._rng = random.Random()
        self._x = None
        self._x_dot = None
        self._theta = None
        self._theta_dot = None
        self._elapsed_steps = 0

    def reset(self, *, seed=None, options=None):
        """Start a new episode; the upstream reset takes no arguments, so no option is accepted."""
        if options:
            raise ValueError("InvertedPendulumBulletEnv.reset takes no options")
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._x = START_X
        self._x_dot = START_X_DOT
        self._theta = self._rng.uniform(-INITIAL_ANGLE, INITIAL_ANGLE)      # interted_pendulum.py:16
        self._theta_dot = START_THETA_DOT
        self._elapsed_steps = 0
        return self._observation(), {}

    def step(self, action):
        """One environment step; the fake returns the five-tuple a gymnasium-style bridge accepts."""
        if self._x is None:
            raise RuntimeError("reset() must be called before step()")
        values = list(action.tolist() if hasattr(action, "tolist") else action)
        if len(values) != ACTION_SIZE:
            raise ValueError(f"expected {ACTION_SIZE} action values, got {len(values)}")
        force = FORCE_SCALE * max(-1.0, min(1.0, float(values[0])))        # interted_pendulum.py:25
        total_mass = MASS_CART + MASS_POLE                                  # placeholder masses
        sin_theta, cos_theta = math.sin(self._theta), math.cos(self._theta)
        # placeholder: the 4/3 factor and the squared speed term below are this fake's own coefficients, not
        # constants of the clone's MJCF model.
        temp = (force + MASS_POLE * ARM_LENGTH * self._theta_dot ** 2 * sin_theta) / total_mass
        theta_acc = (GRAVITY * sin_theta - cos_theta * temp) / (
            ARM_LENGTH * (4.0 / 3.0 - MASS_POLE * cos_theta ** 2 / total_mass))
        x_acc = temp - MASS_POLE * ARM_LENGTH * theta_acc * cos_theta / total_mass
        # Euler integration over the scene dt (scene_bases.py:17).
        self._x += DT * self._x_dot
        self._x_dot += DT * x_acc
        self._theta += DT * self._theta_dot
        self._theta_dot += DT * theta_acc
        self._elapsed_steps += 1
        # inverted_pendulum_env.py:34-39: the non-swing-up done test and the constant reward.
        terminated = bool(abs(self._theta) > DONE_ANGLE)
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS      # pybulletgym/envs/__init__.py:8
        return self._observation(), REWARD, terminated, truncated, {}

    def close(self):
        """The upstream _close disconnects its Bullet client; the fake just drops its state."""
        self._x = None
        self._x_dot = None
        self._theta = None
        self._theta_dot = None

    def _observation(self):
        """interted_pendulum.py:48-51: [x, vx, cos(theta), sin(theta), theta_dot]."""
        return [self._x, self._x_dot, math.cos(self._theta), math.sin(self._theta), self._theta_dot]
