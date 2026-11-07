"""Fake backend of the Quadgym driver: a pure Python stand-in for the upstream attitude environment.

Why a fake: the acceptance gate never installs or imports the upstream package (it needs the legacy ``gym`` package
and numpy, ``setup.py:5``), and package code never imports the clone.  This module re-implements the rotational
dynamics of ``gym_quadrotor.envs:CopterStabilizeAttitudeEnv`` (the class the driver names as ``native``) and the
500-step episode limit that the environment registration adds (``gym_quadrotor/__init__.py:19-23``).

The public members are the ones the native class and its base have (``seed``, ``reset``, ``step``, ``close``; gate
G7), and the two space objects duck-type ``gym.spaces.Box`` (the bridge reads ``low``, ``high``, ``shape`` and
``dtype``).  All numbers below are test data of the fake, not Facts, Limits or references; the physics constants are
copied from ``gym_quadrotor/dynamics/copter.py:8-20`` and the equations from ``gym_quadrotor/dynamics/dynamics.py``.
The fake was not compared with the upstream environment (it was never run here), so the fidelity ``gaps`` of the
driver say where it can differ.

What this is not:

* the upstream model: positions and velocities are not simulated (the upstream fixes them in ``_step_copter`` anyway,
  ``attitude_env.py:27``), and there is no renderer and no ``gym`` ``TimeLimit`` wrapper object (the 500-step limit is
  applied here directly);
* the upstream random stream: initial states come from Python's ``random.Random(seed)``, upstream draws from numpy's
  generator (``base.py:39-41``), so one seed gives different trajectories on the two;
* an exact port: the fake uses Python floats and the documented rotational equations, not the upstream's numpy
  implementation, so round-off and the Euler integration can diverge over long episodes.

Nothing here talks to a device.
"""

import math
import random

# gym_quadrotor/dynamics/copter.py:8-20 (CopterParams defaults); test data of the fake, not a Fact or a Limit.
THRUST_FACTOR = 5.723e-6
DRAG_FACTOR = 1.717e-7
ROTATIONAL_DRAG = 1e-4
ARM_LENGTH = 0.31
ROTOR_INERTIA = 7.321e-5
FRAME_INERTIA = (8.678e-3, 8.678e-3, 32.1e-3)
MAX_ROTOR_SPEED = 500.0
ROTOR_SPEED_HALF_TIME = 1.0 / 16.0

# gym_quadrotor/envs/base.py:49: the environment integrates a fixed 0.02 s step.
DT = 0.02
# gym_quadrotor/__init__.py:22: the registration wraps the environment in a 500-step TimeLimit.
MAX_EPISODE_STEPS = 500

# gym_quadrotor/envs/attitude_env.py:16-18 and 25: the reward thresholds and the boundary penalty.
ERROR_TARGET = math.pi / 180.0
IN_TARGET_REWARD = 0.5
BOUNDARY_PENALTY = 1.0
BOUNDARY_ANGLE = math.pi / 4.0
# gym_quadrotor/envs/attitude_env.py:50-52: the reset distribution, in degrees and radians per second.
RESET_ANGLE_DEGREES = 20.0
RESET_ANGULAR_SPEED = 2.0
RESET_YAW_LIMIT = 0.3


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


def _angle_difference(a, b):
    """Shortest rotation from ``b`` to ``a`` in ``[-pi, pi]`` (coordinates.py:204-218)."""
    n = (a - b) % (2.0 * math.pi)
    return n - 2.0 * math.pi if n > math.pi else n


def _angvel_to_euler(attitude, angular_velocity):
    """Body rates to Euler-angle rates (coordinates.py:157-182, the matrix of lines 176-180)."""
    roll, pitch, _yaw = attitude
    sr, cr = math.sin(roll), math.cos(roll)
    sp, cp = math.sin(pitch), math.cos(pitch)
    wx, wy, wz = angular_velocity
    return [
        wx - sp * wz,
        cr * wy + cp * sr * wz,
        -sr * wy + cp * cr * wz,
    ]


class FakeCopterStabilizeAttitudeEnv:
    """The attitude environment without gym or numpy: legacy ``seed()``/``reset()`` and a 5-tuple ``step()``."""

    def __init__(self):
        # The native class inherits Box(0, 1, (4,)) from QuadRotorEnvBase (base.py:18); the observation space is
        # the upstream Box(0, 1, (6,)) even though the state is not confined to it (attitude_env.py:8-12).
        self.action_space = Box([0.0] * 4, [1.0] * 4)
        self.observation_space = Box([0.0] * 6, [1.0] * 6)
        self._rng = random.Random()
        self._attitude = [0.0, 0.0, 0.0]
        self._angular_velocity = [0.0, 0.0, 0.0]
        self._rotor_speeds = [0.0] * 4
        self._elapsed_steps = 0
        self.seed()

    def seed(self, seed=None):
        """The legacy ``gym.Env.seed`` the base class installs (base.py:39-41); returns ``[seed]``."""
        self._rng = random.Random(seed)
        self._seed = seed
        return [seed]

    def reset(self):
        """Zero state, then the randomisation of ``_reset_copter`` (attitude_env.py:49-55)."""
        self._attitude = [0.0, 0.0, 0.0]
        self._angular_velocity = [0.0, 0.0, 0.0]
        self._rotor_speeds = [0.0] * 4
        limit = RESET_ANGLE_DEGREES * math.pi / 180.0
        self._attitude[0] = self._rng.uniform(-limit, limit)
        self._attitude[1] = self._rng.uniform(-limit, limit)
        self._rng.uniform(-math.pi, math.pi)  # the yaw of random_angle() is overwritten below
        self._angular_velocity = [self._rng.uniform(-RESET_ANGULAR_SPEED, RESET_ANGULAR_SPEED) for _ in range(3)]
        self._attitude[2] = self._rng.uniform(-RESET_YAW_LIMIT, RESET_YAW_LIMIT)
        self._angular_velocity[2] *= 0.5
        self._elapsed_steps = 0
        return self._state()

    def step(self, action):
        """One fixed 0.02 s step: desired rotor speeds, torques, attitude integration, reward and truncation."""
        if len(action) != 4:
            raise AssertionError(f"action must have four values, got {len(action)}")
        action = [min(1.0, max(0.0, float(value))) for value in action]
        desired = [math.sqrt(value) * MAX_ROTOR_SPEED for value in action]
        gamma = 1.0 - 0.5 ** (DT / ROTOR_SPEED_HALF_TIME)
        self._rotor_speeds = [
            max(0.0, speed + gamma * (target - speed))
            for speed, target in zip(self._rotor_speeds, desired)
        ]

        # dynamics.py:31-63: propeller torques, rotor gyro, rotational drag and the Euler cross term.
        o = self._rotor_speeds
        wx, wy, wz = self._angular_velocity
        rotor_net = o[0] - o[1] + o[2] - o[3]
        torque_roll = ARM_LENGTH * THRUST_FACTOR * (o[3] ** 2 - o[1] ** 2)
        torque_pitch = ARM_LENGTH * THRUST_FACTOR * (o[0] ** 2 - o[2] ** 2)
        torque_yaw = DRAG_FACTOR * (o[3] ** 2 + o[1] ** 2 - o[2] ** 2 - o[0] ** 2)
        gyro_roll = rotor_net * ROTOR_INERTIA * wz
        gyro_pitch = -rotor_net * ROTOR_INERTIA * wy
        i0, i1, i2 = FRAME_INERTIA
        cross_roll = (i2 - i1) * wy * wz
        cross_pitch = (i0 - i2) * wx * wz
        cross_yaw = (i1 - i0) * wx * wy
        momentum = [
            torque_roll - ROTATIONAL_DRAG * wx + gyro_roll - cross_roll,
            torque_pitch - ROTATIONAL_DRAG * wy + gyro_pitch - cross_pitch,
            torque_yaw - ROTATIONAL_DRAG * wz - cross_yaw,
        ]
        angular_acceleration = [value / inertia for value, inertia in zip(momentum, FRAME_INERTIA)]
        self._angular_velocity = [
            rate + DT * acceleration for rate, acceleration in zip(self._angular_velocity, angular_acceleration)
        ]
        euler_rate = _angvel_to_euler(self._attitude, self._angular_velocity)
        self._attitude = [angle + DT * rate for angle, rate in zip(self._attitude, euler_rate)]

        reward = self._reward()
        # attitude_env.py:25-26: clip roll and pitch at pi/4 and subtract the boundary penalty.
        if abs(self._attitude[0]) > BOUNDARY_ANGLE or abs(self._attitude[1]) > BOUNDARY_ANGLE:
            self._attitude[0] = min(BOUNDARY_ANGLE, max(-BOUNDARY_ANGLE, self._attitude[0]))
            self._attitude[1] = min(BOUNDARY_ANGLE, max(-BOUNDARY_ANGLE, self._attitude[1]))
            self._angular_velocity = [0.0, 0.0, 0.0]
            reward -= BOUNDARY_PENALTY

        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        return self._state(), reward, False, truncated, {}

    def close(self):
        """No renderer to release; the native base closes its renderer (base.py:63-64)."""
        self._rotor_speeds = [0.0] * 4

    def _reward(self):
        """attitude_env.py:31-40 with AttitudeReward(1.0, attitude_error_transform=sqrt) of line 19."""
        roll, pitch, yaw = self._attitude
        angle_error = math.sqrt(roll ** 2 + pitch ** 2 + yaw ** 2)
        angular_error = sum(rate ** 2 for rate in self._angular_velocity)
        reward = -angle_error - 1e-2 * angular_error
        if abs(roll) < ERROR_TARGET:
            reward += IN_TARGET_REWARD / 3.0
        if abs(pitch) < ERROR_TARGET:
            reward += IN_TARGET_REWARD / 3.0
        if abs(_angle_difference(yaw, 0.0)) < ERROR_TARGET:
            reward += IN_TARGET_REWARD / 3.0
        return reward

    def _state(self):
        """attitude_env.py:42-47: [roll, pitch, wrapped yaw, roll rate, pitch rate, yaw rate]."""
        rates = _angvel_to_euler(self._attitude, self._angular_velocity)
        return [
            self._attitude[0],
            self._attitude[1],
            _angle_difference(self._attitude[2], 0.0),
            rates[0],
            rates[1],
            rates[2],
        ]
