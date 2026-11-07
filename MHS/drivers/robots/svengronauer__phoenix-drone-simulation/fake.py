"""Fake backend of the Phoenix drone driver: a pure Python stand-in for ``DroneHoverSimpleEnv-v0``.

Why a fake: the gate cannot import the upstream package (setup.py:24-34 needs gymnasium, pybullet, numpy, torch and
more), and package code never imports the clone.  This module re-implements the simplified hover equations of
``phoenix_drone_simulation.envs.hover:DroneHoverSimpleEnv``: the PWM action map of ``envs/control.py:91-104``, the
force model of ``envs/agents.py:259-297`` and the Euler integration of ``envs/physics.py:127-199``.  It also applies
the 500-step ``TimeLimit`` that ``gymnasium.make`` adds to the registration at ``phoenix_drone_simulation/__init__.py:9-11``.
The public members are the ones ``DroneHoverSimpleEnv`` has (``reset`` and ``step``; gate G7).

The two space classes duck-type ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``.
The observation width is the upstream one: two history entries of the 13-value noiseless observation plus the
4-value action (``envs/base.py:44`` and ``:143-149``).

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver: the fake
uses Python's ``random.Random(seed)`` where upstream draws from numpy's global generator and ignores ``seed``; it
models no observation noise, no 10% domain randomization, no PyBullet contact or drag and no first-order motor
dynamics.  Nothing here talks to a device.
"""

import math
import random

# --- upstream constants, each with its source line ---------------------------------------------------------------
ACTION_DIM = 4                          # agents.py:134
HISTORY = 2                             # base.py:44
OBS_DIM = 13                            # hover.py:159: position 3 + quaternion 4 + velocity 3 + angular rate 3
OBS_LIMIT = 1000.0                      # base.py:147
ACTION_LIMIT = 1.0                      # base.py:148
MAX_EPISODE_STEPS = 500                 # __init__.py:11 (the TimeLimit that gymnasium.make adds)
TIMESTEP = 0.01                         # hover.py:263 sim_freq=100, base.py:98 TIME_STEP = 1/SIM_FREQ
GRAVITY = 9.81                          # agents.py:145 and physics.py:19
MASS = 0.027                            # cf21x_sys_eq.urdf:16
ARM = 0.0397                            # cf21x_sys_eq.urdf:10
THRUST2WEIGHT_RATIO = 2.25              # cf21x_sys_eq.urdf:10
IXX = IYY = 1.7e-5                      # cf21x_sys_eq.urdf:17
IZZ = 2.9e-5                            # cf21x_sys_eq.urdf:17
FORCE_TORQUE_FACTOR_0 = 1.56e-5         # agents.py:142
FORCE_TORQUE_FACTOR_1 = 5.96e-3         # agents.py:143
MAX_THRUST = GRAVITY * MASS * THRUST2WEIGHT_RATIO / 4.0   # agents.py:149
HOVER_X = math.sqrt(1.0 / THRUST2WEIGHT_RATIO)            # agents.py:152
HOVER_ACTION = 2.0 / THRUST2WEIGHT_RATIO - 1.0            # agents.py:153
TARGET = (0.0, 0.0, 1.0)                # hover.py:14
DONE_ROLL_PITCH = math.radians(60.0)    # hover.py:93
DONE_ALTITUDE = 0.2                     # hover.py:94
DONE_RATE = math.radians(300.0)         # hover.py:98
PENALTY_ACTION = 1e-4                   # hover.py:18
PENALTY_ANGLE = 0.0                     # hover.py:19
PENALTY_SPIN = 1e-4                     # hover.py:20
PENALTY_TERMINAL = 100.0                # hover.py:21
PENALTY_VELOCITY = 0.0                  # hover.py:22
INFO_VEL_LIMIT = 0.25                   # hover.py:36
INFO_ROLL_PITCH_LIMIT = math.radians(10.0)   # hover.py:37
INFO_RATE_LIMIT = math.radians(200.0)        # hover.py:38
INFO_X_LIMIT = 0.10                     # hover.py:39
INFO_Y_LIMIT = 0.10                     # hover.py:40
INFO_Z_LIMIT = 1.20                     # hover.py:41
RESET_POS_LIMIT = 0.25                  # hover.py:201
RESET_ANGLE_LIMIT = math.pi / 6.0       # hover.py:205
RESET_YAW_LIMIT = 2.0 * math.pi         # hover.py:207
RESET_VEL_LIMIT = 0.1                   # hover.py:212
RESET_RATE_LIMIT = math.radians(200.0)  # hover.py:215
RESET_YAW_RATE_LIMIT = math.radians(20.0)    # hover.py:217


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"


def _clip(value, low, high):
    return low if value < low else high if value > high else value


def _norm(values):
    return math.sqrt(sum(value * value for value in values))


def _cross(left, right):
    return [
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    ]


def _mat_vec(matrix, vector):
    return [sum(row[i] * vector[i] for i in range(3)) for row in matrix]


def _quaternion(roll, pitch, yaw):
    """``get_quaternion_from_euler`` (envs/utils.py:32-56), returned as [x, y, z, w]."""
    half_yaw, half_pitch, half_roll = yaw * 0.5, pitch * 0.5, roll * 0.5
    cos_yaw, sin_yaw = math.cos(half_yaw), math.sin(half_yaw)
    cos_pitch, sin_pitch = math.cos(half_pitch), math.sin(half_pitch)
    cos_roll, sin_roll = math.cos(half_roll), math.sin(half_roll)
    x = sin_roll * cos_pitch * cos_yaw - cos_roll * sin_pitch * sin_yaw
    y = cos_roll * sin_pitch * cos_yaw + sin_roll * cos_pitch * sin_yaw
    z = cos_roll * cos_pitch * sin_yaw - sin_roll * sin_pitch * cos_yaw
    w = cos_roll * cos_pitch * cos_yaw + sin_roll * sin_pitch * sin_yaw
    return [x, y, z, w]


def _rotation_matrix(quaternion):
    """PyBullet's ``getMatrixFromQuaternion`` for [x, y, z, w]."""
    x, y, z, w = quaternion
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return [
        [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
        [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
        [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
    ]


class FakeDroneHoverEnv:
    """``DroneHoverSimpleEnv-v0`` without numpy or PyBullet: ``reset(seed, options)`` and ``step(action)``."""

    def __init__(self, **options):
        # placeholder: the fake ignores the upstream constructor options; the spaces are the upstream shapes
        self._options = dict(options)
        self.action_space = Box([-ACTION_LIMIT] * ACTION_DIM, [ACTION_LIMIT] * ACTION_DIM)       # base.py:148-150
        width = HISTORY * (OBS_DIM + ACTION_DIM)                                                # base.py:143
        self.observation_space = Box([-OBS_LIMIT] * width, [OBS_LIMIT] * width)                 # base.py:147-149
        self._rng = random.Random(0)    # placeholder: the default seed is test data, not a device fact
        self._xyz = list(TARGET)
        self._rpy = [0.0, 0.0, 0.0]
        self._quaternion = _quaternion(*self._rpy)
        self._xyz_dot = [0.0, 0.0, 0.0]
        self._rpy_dot = [0.0, 0.0, 0.0]
        self._last_action = [0.0] * ACTION_DIM
        self._observation_history = []
        self._action_history = []
        self._elapsed_steps = 0

    # -- upstream surface ------------------------------------------------------------------------------------------
    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        del options  # upstream accepts options and ignores them (base.py:382-429)
        self._elapsed_steps = 0
        # placeholder: the reset distribution is the upstream one (hover.py:200-228); the random stream is not
        self._xyz = [TARGET[i] + self._rng.uniform(-RESET_POS_LIMIT, RESET_POS_LIMIT) for i in range(3)]
        roll = self._rng.uniform(-RESET_ANGLE_LIMIT, RESET_ANGLE_LIMIT)
        pitch = self._rng.uniform(-RESET_ANGLE_LIMIT, RESET_ANGLE_LIMIT)
        yaw = self._rng.uniform(-RESET_YAW_LIMIT, RESET_YAW_LIMIT)
        self._rpy = [roll, pitch, yaw]
        self._quaternion = _quaternion(roll, pitch, yaw)
        self._xyz_dot = [self._rng.uniform(-RESET_VEL_LIMIT, RESET_VEL_LIMIT) for _ in range(3)]
        self._rpy_dot = [self._rng.uniform(-RESET_RATE_LIMIT, RESET_RATE_LIMIT) for _ in range(3)]
        self._rpy_dot[2] = self._rng.uniform(-RESET_YAW_RATE_LIMIT, RESET_YAW_RATE_LIMIT)
        # placeholder: the upstream reset draws motor states around HOVER_X and HOVER_ACTION (hover.py:223-228)
        self._last_action = [_clip(self._rng.gauss(HOVER_ACTION, 0.02), -1.0, 1.0) for _ in range(ACTION_DIM)]
        self._observation_history = []
        self._action_history = []
        observation = self._compute_observation()
        for _ in range(HISTORY):
            self._observation_history.append(list(observation))
            self._action_history.append(list(self._last_action))
        return list(self._compute_history()), {}

    def step(self, action):
        values = [_clip(float(value), -1.0, 1.0) for value in action]
        if len(values) != ACTION_DIM:
            raise ValueError(f"expected {ACTION_DIM} motor commands, got {len(values)}")
        self._last_action = list(values)        # apply_action sets last_action before the reward (agents.py:264)
        self._integrate(values)
        self._elapsed_steps += 1
        observation = self._compute_history()
        reward = self._compute_reward(values)
        info = self._compute_info()
        terminated = self._compute_done()
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        return observation, reward, terminated, truncated, info

    # -- upstream helpers (private, so gate G7 does not treat them as surface) --------------------------------------
    def _integrate(self, action):
        forces = []
        for value in action:
            pwm = 30000.0 + value * 30000.0                                  # control.py:94-100
            forces.append(MAX_THRUST * (pwm / 60000.0))                      # agents.py:280-293
        torques = [FORCE_TORQUE_FACTOR_1 * force + FORCE_TORQUE_FACTOR_0 for force in forces]
        z_torque = -torques[0] + torques[1] - torques[2] + torques[3]        # agents.py:287-289
        thrust_world = _mat_vec(_rotation_matrix(self._quaternion), [0.0, 0.0, sum(forces)])
        force_world = [thrust_world[0], thrust_world[1], thrust_world[2] - GRAVITY * MASS]
        x_torque = (-forces[0] - forces[1] + forces[2] + forces[3]) * ARM / math.sqrt(2.0)
        y_torque = (-forces[0] + forces[1] + forces[2] - forces[3]) * ARM / math.sqrt(2.0)
        inertia = [IXX, IYY, IZZ]
        gyroscopic = _cross(self._rpy_dot, [inertia[i] * self._rpy_dot[i] for i in range(3)])
        body_torque = [x_torque - gyroscopic[0], y_torque - gyroscopic[1], z_torque - gyroscopic[2]]
        rpy_dot_dot = [body_torque[i] / inertia[i] for i in range(3)]
        acceleration = [force_world[i] / MASS for i in range(3)]
        self._xyz_dot = [self._xyz_dot[i] + TIMESTEP * acceleration[i] for i in range(3)]
        self._rpy_dot = [self._rpy_dot[i] + TIMESTEP * rpy_dot_dot[i] for i in range(3)]
        self._xyz = [self._xyz[i] + TIMESTEP * self._xyz_dot[i] for i in range(3)]
        self._xyz[2] = max(self._xyz[2], 0.0)                                # physics.py:180-181
        self._rpy = [self._rpy[i] + TIMESTEP * self._rpy_dot[i] for i in range(3)]
        self._quaternion = _quaternion(*self._rpy)

    def _compute_observation(self):
        # hover.py:159: [position (3), quaternion (4), linear velocity (3), angular rate (3)]
        return list(self._xyz) + list(self._quaternion) + list(self._xyz_dot) + list(self._rpy_dot)

    def _compute_history(self):
        # base.py:303-319
        observation = self._compute_observation()
        self._observation_history.append(observation)
        if len(self._observation_history) > HISTORY:
            del self._observation_history[0]
        history = []
        for obs, action in zip(self._observation_history, self._action_history):
            history.extend(obs)
            history.extend(action)
        self._action_history.append(list(self._last_action))
        if len(self._action_history) > HISTORY:
            del self._action_history[0]
        return history

    def _compute_done(self):
        # hover.py:89-101
        if abs(self._rpy[0]) > DONE_ROLL_PITCH or abs(self._rpy[1]) > DONE_ROLL_PITCH:
            return True
        if self._xyz[2] < DONE_ALTITUDE:
            return True
        return any(abs(value) > DONE_RATE for value in self._rpy_dot)

    def _compute_info(self):
        # hover.py:103-129
        info = {}
        cost = 0.0
        if abs(self._xyz[0]) > INFO_X_LIMIT or abs(self._xyz[1]) > INFO_Y_LIMIT or self._xyz[2] > INFO_Z_LIMIT:
            cost = 1.0
            info["xyz_limit"] = list(self._xyz)
        if any(abs(value) > INFO_ROLL_PITCH_LIMIT for value in self._rpy[:2]):
            cost = 1.0
            info["rpy"] = list(self._rpy)
        if any(abs(value) > INFO_VEL_LIMIT for value in self._xyz_dot):
            cost = 1.0
            info["xzy_dot"] = list(self._xyz_dot)
        if any(abs(value) > INFO_RATE_LIMIT for value in self._rpy_dot):
            cost = 1.0
            info["rpy_dot"] = [value * 180.0 / math.pi for value in self._rpy_dot]
        info["cost"] = cost
        return info

    def _compute_reward(self, action):
        # hover.py:169-187; apply_action already set last_action to action, so the action-rate term is zero
        normed = [0.5 * (_clip(value, -1.0, 1.0) + 1.0) for value in action]
        penalty_action = PENALTY_ACTION * _norm(normed)
        penalty_angle = PENALTY_ANGLE * _norm(self._rpy)
        penalty_spin = PENALTY_SPIN * _norm(self._rpy_dot)
        penalty_terminal = PENALTY_TERMINAL if self._compute_done() else 0.0
        penalty_velocity = PENALTY_VELOCITY * _norm(self._xyz_dot)
        distance = _norm([self._xyz[i] - TARGET[i] for i in range(3)])
        return -distance - (penalty_action + penalty_angle + penalty_spin + penalty_terminal + penalty_velocity)
