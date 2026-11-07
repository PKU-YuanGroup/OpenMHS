"""Fake backend of the gym-rotor-modularrl driver: a pure Python stand-in for ``gym_rotor.envs:QuadEnv``.

Why a fake: the acceptance gate never installs or imports the upstream package (it needs gymnasium, numpy, scipy and
a command-line parser that reads ``sys.argv``, ``quad.py:9-17`` and ``:22-25``), and package code never imports the
clone.  This module re-implements the 18-element rigid-body model of ``gym_rotor/envs/quad.py`` and the
10000-step episode limit of the ``Quad-v0`` registration (``gym_rotor/__init__.py:3-6``).

The public members are the ones the upstream class has (``reset``, ``step`` and ``close``; gate G7), and the two
space objects duck-type ``gymnasium.spaces.Box`` (the bridge reads ``low``, ``high`` and ``shape``).  Every number
below is either copied from the clone at the pinned commit or derived from a copied number; none is a Fact, a Limit
or a reference, and none is copied into the driver's declarations.

What this is not:

* the upstream environment: the fake runs explicit Euler integration at the upstream's 200 Hz step
  (``quad.py:60-61``), while the upstream default is ``scipy.integrate.solve_ivp`` with DOP853 (``quad.py:62`` and
  ``:263-266``);
* the upstream random stream: the fake draws with Python's ``random.Random(seed)``, upstream draws with numpy's
  global generator (``quad.py:6`` and ``:188-198``), so one seed gives different trajectories on the two;
* a working copy of the upstream ``step``: the upstream method indexes a scalar reward and a boolean done
  (``quad.py:153-168``), so it raises ``TypeError``; this fake implements the five-value API that the surrounding
  code and the gymnasium bridge expect;
* a renderer or a gymnasium ``TimeLimit`` wrapper: the registered 10000-step limit is applied here directly.

Nothing here talks to a device.
"""

import math
import random

# gym_rotor/envs/quad.py:27-33 (QuadEnv.__init__), nominal quadrotor parameters.
MASS = 2.15
ARM = 0.23
INERTIA = (0.022, 0.022, 0.035)
C_TF = 0.0135
C_TW = 2.2
GRAVITY = 9.81

# gym_rotor/envs/quad.py:36-42: the thrust envelope of each motor.
HOVER_FORCE = MASS * GRAVITY / 4.0
MIN_FORCE = 0.5
MAX_FORCE = C_TW * HOVER_FORCE
AVRG_ACT = (MIN_FORCE + MAX_FORCE) / 2.0
SCALE_ACT = MAX_FORCE - AVRG_ACT

# gym_rotor/envs/quad.py:60-62: 200 Hz simulation, dt = 0.005 s; the upstream default integrator is solve_ivp.
FREQ = 200.0
DT = 1.0 / FREQ

# gym_rotor/envs/quad.py:103-107: state limits used by the observation space and done_wrapper.
X_LIM = 1.0
V_LIM = 4.0
W_LIM = 2.0 * math.pi
EULER_LIM = 85.0

# gym_rotor/envs/quad.py:340-358: initial-error bounds of sample_init_error.
TRAIN_INIT_X = 0.6
TRAIN_INIT_V = V_LIM * 0.5
TRAIN_INIT_R = 50.0 * math.pi / 180.0
TRAIN_INIT_W = W_LIM * 0.5
EVAL_INIT_X = 0.4
EVAL_INIT_V = 0.0
EVAL_INIT_R = 0.0
EVAL_INIT_W = 0.0

# gym_rotor/__init__.py:3-6: Quad-v0 is registered with max_episode_steps=10000.
MAX_EPISODE_STEPS = 10000

# gym_rotor/envs/quad.py:73-88 and args_parse.py:21-29: reward terms and default coefficients.
REWARD_ALIVE = 0.0
REWARD_CRASH = -1.0
C_X = 6.0
C_V = 0.4
C_B1 = 6.0
C_W = 0.6

# args_parse.py:32-33: uniform domain randomization is on by default, with +-10 percent.
USE_UDM = True
UDM_PERCENTAGE = 10.0


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high, shape=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        values = value.tolist() if hasattr(value, "tolist") else value
        return (isinstance(values, (list, tuple)) and len(values) == len(self.low)
                and all(lo <= float(item) <= hi for item, lo, hi in zip(values, self.low, self.high)))


def _clip(value, low, high):
    return low if value < low else high if value > high else value


def _norm(values):
    return math.sqrt(sum(item * item for item in values))


def _hat(omega):
    wx, wy, wz = omega
    return [[0.0, -wz, wy], [wz, 0.0, -wx], [-wy, wx, 0.0]]


def _matrix_from_vec(vector):
    """``vector.reshape(3, 3, order='F')`` (quad_utils.py:14)."""
    return [[float(vector[0]), float(vector[3]), float(vector[6])],
            [float(vector[1]), float(vector[4]), float(vector[7])],
            [float(vector[2]), float(vector[5]), float(vector[8])]]


def _vec_from_matrix(matrix):
    """``matrix.reshape(9, 1, order='F').flatten()`` (quad.py:248)."""
    return [matrix[0][0], matrix[1][0], matrix[2][0],
            matrix[0][1], matrix[1][1], matrix[2][1],
            matrix[0][2], matrix[1][2], matrix[2][2]]


def _matmul(left, right):
    return [[sum(left[row][k] * right[k][col] for k in range(3)) for col in range(3)] for row in range(3)]


def _euler_to_matrix(roll, pitch, yaw):
    """``Rotation.from_euler('xyz', [roll, pitch, yaw])`` (quad.py:197-199), i.e. Rz @ Ry @ Rx."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]


def _matrix_to_euler(matrix, degrees=True):
    """The xyz Euler angles of a rotation matrix, in the order [roll, pitch, yaw]."""
    sp = _clip(-matrix[2][0], -1.0, 1.0)
    pitch = math.asin(sp)
    if abs(math.cos(pitch)) > 1e-9:
        roll = math.atan2(matrix[2][1], matrix[2][2])
        yaw = math.atan2(matrix[1][0], matrix[0][0])
    else:
        roll = math.atan2(-matrix[1][2], matrix[1][1])
        yaw = 0.0
    if degrees:
        return [math.degrees(roll), math.degrees(pitch), math.degrees(yaw)]
    return [roll, pitch, yaw]


def _reorthonormalize(matrix):
    """Gram-Schmidt projection back to SO(3), the role of ``ensure_SO3`` (quad_utils.py:123-142)."""
    columns = [[matrix[0][col], matrix[1][col], matrix[2][col]] for col in range(3)]
    first = columns[0]
    first_norm = _norm(first)
    if first_norm == 0.0:
        first, first_norm = [1.0, 0.0, 0.0], 1.0
    first = [item / first_norm for item in first]
    second = columns[1]
    projection = sum(second[k] * first[k] for k in range(3))
    second = [second[k] - projection * first[k] for k in range(3)]
    second_norm = _norm(second)
    if second_norm == 0.0:
        second, second_norm = [0.0, 1.0, 0.0], 1.0
    second = [item / second_norm for item in second]
    third = [first[1] * second[2] - first[2] * second[1],
             first[2] * second[0] - first[0] * second[2],
             first[0] * second[1] - first[1] * second[0]]
    return [[first[0], second[0], third[0]],
            [first[1], second[1], third[1]],
            [first[2], second[2], third[2]]]


class FakeQuadEnv:
    """The Quad-v0 environment without numpy, scipy or gymnasium: ``reset(seed, options)`` and ``step(action)``."""

    metadata = {"render_modes": ["human"]}

    def __init__(self, render_mode=None, **_options):
        if render_mode is not None:
            raise ValueError("the fake QuadEnv cannot render; use render_mode=None")
        self._nominal_mass = MASS
        self._nominal_arm = ARM
        self._nominal_inertia = INERTIA
        self._nominal_c_tf = C_TF
        self._nominal_c_tw = C_TW
        self.g = GRAVITY
        self.freq = FREQ
        self.dt = DT
        self.ode_integrator = "euler"
        self.x_lim = X_LIM
        self.v_lim = V_LIM
        self.W_lim = W_LIM
        self.euler_lim = EULER_LIM
        self.reward_alive = REWARD_ALIVE
        self.reward_crash = REWARD_CRASH
        self.Cx = C_X
        self.Cv = C_V
        self.Cb1 = C_B1
        self.CW = C_W
        self.use_UDM = USE_UDM
        self.UDM_percentage = UDM_PERCENTAGE
        self.xd = [0.0, 0.0, 0.0]
        self.vd = [0.0, 0.0, 0.0]
        self.b1d = [1.0, 0.0, 0.0]
        self.Wd = [0.0, 0.0, 0.0]
        self.action_space = Box([-1.0, -1.0, -1.0, -1.0], [1.0, 1.0, 1.0, 1.0], shape=(4,))   # quad.py:126-132
        low = [-X_LIM] * 3 + [-V_LIM] * 3 + [-1.0] * 9 + [-W_LIM] * 3                      # quad.py:108-117
        high = [X_LIM] * 3 + [V_LIM] * 3 + [1.0] * 9 + [W_LIM] * 3
        self.observation_space = Box(low, high, shape=(18,))
        self.state = None
        self.viewer = None
        self._elapsed_steps = 0
        self._rng = random.Random()
        self._set_parameters(self._nominal_mass, self._nominal_arm, list(self._nominal_inertia),
                             self._nominal_c_tf, self._nominal_c_tw)

    # -- model -----------------------------------------------------------------
    def _set_parameters(self, mass, arm, inertia, c_tf, c_tw):
        """Apply the parameters of ``set_random_parameters`` (quad.py:361-406)."""
        self.m = mass
        self.d = arm
        self.J = list(inertia)
        self.c_tf = c_tf
        self.c_tw = c_tw
        self.f = self.m * self.g
        self.hover_force = self.m * self.g / 4.0
        self.min_force = MIN_FORCE
        self.max_force = self.c_tw * self.hover_force
        self.avrg_act = (self.min_force + self.max_force) / 2.0
        self.scale_act = self.max_force - self.avrg_act
        self.forces_to_fM = [
            [1.0, 1.0, 1.0, 1.0],
            [0.0, -self.d, 0.0, self.d],
            [self.d, 0.0, -self.d, 0.0],
            [-self.c_tf, self.c_tf, -self.c_tf, self.c_tf],
        ]
        self.fM = [0.0, 0.0, 0.0, 0.0]
        self.M = [0.0, 0.0, 0.0]

    def _set_random_parameters(self, env_type="train"):
        """``set_random_parameters``: nominal in eval, uniform +-UDM_percentage in train (quad.py:361-389)."""
        mass, arm = self._nominal_mass, self._nominal_arm
        inertia = list(self._nominal_inertia)
        c_tf, c_tw = self._nominal_c_tf, self._nominal_c_tw
        if env_type == "train":
            uncertainty = self.UDM_percentage / 100.0
            mass_range = mass * uncertainty
            arm_range = arm * uncertainty
            j1_range = inertia[0] * uncertainty
            j3_range = inertia[2] * uncertainty
            c_tf_range = c_tf * uncertainty
            c_tw_range = c_tw * (uncertainty / 2.0)
            mass = self._rng.uniform(mass - mass_range, mass + mass_range)
            arm = self._rng.uniform(arm - arm_range, arm + arm_range)
            j1 = self._rng.uniform(inertia[0] - j1_range, inertia[0] + j1_range)
            j2 = j1
            j3 = self._rng.uniform(inertia[2] - j3_range, inertia[2] + j3_range)
            inertia = [j1, j2, j3]
            c_tf = self._rng.uniform(c_tf - c_tf_range, c_tf + c_tf_range)
            c_tw = self._rng.uniform(c_tw - c_tw_range, c_tw + c_tw_range)
        self._set_parameters(mass, arm, inertia, c_tf, c_tw)

    def _sample_init_error(self, env_type="train"):
        """``sample_init_error`` (quad.py:340-358): the yaw and the initial-error bounds."""
        self.yaw = self._rng.uniform(-math.pi, math.pi)
        if env_type == "train":
            if self._rng.random() < 0.2:
                self.init_x, self.init_v = 0.0, 0.0
                self.init_R, self.init_W = 0.0, 0.0
            else:
                self.init_x, self.init_v = TRAIN_INIT_X, TRAIN_INIT_V
                self.init_R, self.init_W = TRAIN_INIT_R, TRAIN_INIT_W
        elif env_type == "eval":
            self.init_x, self.init_v = EVAL_INIT_X, EVAL_INIT_V
            self.init_R, self.init_W = EVAL_INIT_R, EVAL_INIT_W
        else:
            raise ValueError(f"unknown env_type {env_type!r}")

    def _action_wrapper(self, normalized_action):
        """Linear map from [-1, 1] to [min_force, max_force], clipped (quad.py:225-242)."""
        values = normalized_action.tolist() if hasattr(normalized_action, "tolist") else normalized_action
        if not isinstance(values, (list, tuple)) or len(values) != 4:
            raise ValueError("the action must be four normalized motor commands")
        action = [_clip(self.scale_act * float(item) + self.avrg_act, self.min_force, self.max_force)
                  for item in values]
        self.f1, self.f2, self.f3, self.f4 = action
        self.fM = [sum(self.forces_to_fM[row][col] * action[col] for col in range(4)) for row in range(4)]
        self.f = self.fM[0]
        self.M = self.fM[1:4]
        return action

    def _decompose(self, state):
        return (list(state[0:3]), list(state[3:6]),
                _reorthonormalize(_matrix_from_vec(state[6:15])), list(state[15:18]))

    def _integrate(self, state):
        """One explicit Euler step of ``EoM`` at dt (quad.py:252-262 and :323-337)."""
        x, v, rotation, omega = self._decompose(state)
        current = x + v + _vec_from_matrix(rotation) + omega
        column_three = [rotation[0][2], rotation[1][2], rotation[2][2]]
        x_dot = v
        v_dot = [GRAVITY * (1.0 if axis == 2 else 0.0) - self.f * column_three[axis] / self.m
                 for axis in range(3)]
        rotation_dot = _matmul(rotation, _hat(omega))
        hat_omega = _hat(omega)
        omega_dot = []
        for axis in range(3):
            torque = sum(hat_omega[axis][k] * self.J[k] * omega[k] for k in range(3))
            omega_dot.append((-torque + self.M[axis]) / self.J[axis])
        state_dot = x_dot + v_dot + _vec_from_matrix(rotation_dot) + omega_dot
        next_state = [current[index] + self.dt * state_dot[index] for index in range(18)]
        # Numerical stabilisation: project the stored attitude back onto SO(3).  Upstream re-orthonormalises only
        # inside state_decomposition (quad_utils.py:123-142); the projection here is the same role.
        next_state[6:15] = _vec_from_matrix(_reorthonormalize(_matrix_from_vec(next_state[6:15])))
        self.state = next_state
        return next_state

    def _reward_wrapper(self, state):
        """``reward_wrapper`` (quad.py:276-300): the scalar reward of one observation."""
        x, v, rotation, omega = self._decompose(state)
        ex = [x[index] - self.xd[index] for index in range(3)]
        ev = [v[index] - self.vd[index] for index in range(3)]
        b1 = [rotation[0][0], rotation[1][0], rotation[2][0]]
        dot = sum(self.b1d[i] * b1[i] for i in range(3)) / (_norm(self.b1d) * _norm(b1))
        dot = _clip(dot, -1.0, 1.0)
        angle = math.acos(dot)
        cross_z = self.b1d[0] * b1[1] - self.b1d[1] * b1[0]
        if cross_z < 0:
            angle = -angle
        return (self.reward_alive
                - self.Cx * sum(item * item for item in ex)
                - self.Cv * sum(item * item for item in ev)
                - self.Cb1 * abs(angle / math.pi)
                - self.CW * sum(item * item for item in omega))

    def _done_wrapper(self, state):
        """``done_wrapper`` (quad.py:303-320): the terminal condition of one observation."""
        x, v, rotation, omega = self._decompose(state)
        roll, pitch, _yaw = _matrix_to_euler(rotation, degrees=True)
        return bool(any(abs(item) >= self.x_lim for item in x)
                    or any(abs(item) >= self.v_lim for item in v)
                    or any(abs(item) >= self.W_lim for item in omega)
                    or abs(roll) >= self.euler_lim
                    or abs(pitch) >= self.euler_lim)

    # -- gymnasium API ---------------------------------------------------------
    def reset(self, env_type="train", seed=None, options=None):
        """Reset the state; returns ``(observation, info)`` as the gymnasium bridge expects."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        if self.use_UDM:
            self._set_random_parameters(env_type)
        self.state = [0.0] * 18
        self._sample_init_error(env_type)
        self.state[0:3] = [self._rng.uniform(-self.init_x, self.init_x) for _ in range(3)]       # quad.py:188
        self.state[3:6] = [self._rng.uniform(-self.init_v, self.init_v) for _ in range(3)]       # quad.py:191
        self.state[15:18] = [self._rng.uniform(-self.init_W, self.init_W) for _ in range(3)]     # quad.py:194
        roll, pitch = [self._rng.uniform(-self.init_R, self.init_R) for _ in range(2)]           # quad.py:197
        rotation = _euler_to_matrix(roll, pitch, self.yaw)
        self.state[6:15] = _vec_from_matrix(rotation)
        self.f = self.m * self.g                                                                 # quad.py:207
        self.f1, self.f2, self.f3, self.f4 = (self.hover_force, self.hover_force,
                                              self.hover_force, self.hover_force)
        self.M = [0.0, 0.0, 0.0]
        self._elapsed_steps = 0
        return list(self.state), {}

    def step(self, normalized_action):
        """One environment step; returns ``(observation, reward, terminated, truncated, info)``."""
        if self.state is None:
            raise RuntimeError("call reset before step")
        self._action_wrapper(normalized_action)
        observation = self._integrate(list(self.state))
        reward = self._reward_wrapper(observation)
        terminated = self._done_wrapper(observation)
        if terminated:
            reward = self.reward_crash
        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        return list(observation), float(reward), bool(terminated), bool(truncated), {}

    def close(self):
        self.state = None
