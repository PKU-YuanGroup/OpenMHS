"""Fake backend of the FDCL-GWU gym-rotor Quad-v0 environment.

Why a fake: the acceptance gate neither installs nor imports the clone (``gym_rotor.envs:QuadEnv`` needs numpy,
scipy and gymnasium, and imports ``args_parse`` at module import), and package code never imports the clone.  This
module re-implements the dynamics of ``gym_rotor.envs.quad:QuadEnv`` in pure Python and the 10000-step time limit
that ``gymnasium.make("Quad-v0")`` adds from the registration in ``gym_rotor/__init__.py``.  The public members of
``FakeQuadEnv`` are the ones ``QuadEnv`` has (``reset``, ``step`` and ``close``; gate G7), and the two space classes
duck-type ``gymnasium.spaces.Box`` (the bridge reads ``low``, ``high``, ``shape``, ``dtype``).  Every constant and
rule below cites a line of the clone at the pinned commit 86a25517f401a5ca3a4f393e4f0c04104a04d3a1.

What this is not, and the fidelity ``gaps`` of the driver also say so:

* the initial state comes from Python's ``random.Random(seed)``; upstream draws it with ``numpy.random.uniform`` and
  ``random.random``, which ignore the seed passed to ``QuadEnv.reset``, so a seed does not repeat an upstream
  trajectory;
* the integration is a fixed-step fourth-order Runge-Kutta over one ``dt``; upstream uses
  ``scipy.integrate.solve_ivp`` with method ``DOP853`` (quad.py:263-266);
* the nominal mass, arm, inertia and coefficients are used; upstream's uniform domain randomization
  (quad.py:359-404) is not modelled;
* the four motor thrusts are ideal (no motor lag or drag) and no contact is modelled;
* the reward is the raw scalar of ``reward_wrapper``; the MODUL/MONO interpolation of ``step`` and the observation
  error terms of the wrappers are not modelled;
* there is no rendering (vpython) and no gymnasium wrapper.

Numbers here are test data for the fake, not device facts; every constant reused from the clone cites it.
"""

import math
import random

# Nominal quadrotor parameters, gym_rotor/envs/quad.py:27-33.
MASS = 2.15                                   # kg
ARM = 0.23                                    # m
J1, J2, J3 = 0.022, 0.022, 0.035              # kg m^2
C_TF = 0.0135                                 # torque-to-thrust coefficient
C_TW = 2.2                                    # thrust-to-weight coefficient
GRAVITY = 9.81                                # m/s^2

# Force bounds and the action scaling, gym_rotor/envs/quad.py:36-42.
HOVER_FORCE = MASS * GRAVITY / 4.0
MIN_FORCE = 0.5                               # N, each motor
MAX_FORCE = C_TW * HOVER_FORCE                # N, each motor
AVRG_ACT = (MIN_FORCE + MAX_FORCE) / 2.0
SCALE_ACT = MAX_FORCE - AVRG_ACT

# Simulation step, gym_rotor/envs/quad.py:59-61.
FREQ = 200.0                                  # Hz
DT = 1.0 / FREQ                               # s

# State limits, gym_rotor/envs/quad.py:103-107 and the termination test at :301-318.
X_LIM = 1.0                                   # m
V_LIM = 4.0                                   # m/s
W_LIM = 2.0 * math.pi                         # rad/s
EULER_LIM = 85.0                              # deg

# Reward coefficients, args_parse.py:23-31 (Cx, Cv, Cb1 and Cw12) and quad.py:71-81.
C_X = 6.0
C_V = 0.4
C_B1 = 6.0
C_W = 0.6

# gymnasium registration, gym_rotor/__init__.py:3-6: max_episode_steps=10000.
MAX_EPISODE_STEPS = 10000

# Default training reset bounds, gym_rotor/envs/quad.py:338-351.
TRAIN_X = 0.6                                 # m
TRAIN_V = V_LIM * 0.5                         # m/s
TRAIN_R = 50.0 * math.pi / 180.0              # rad
TRAIN_W = W_LIM * 0.5                         # rad/s
TRAIN_ORIGIN_PROBABILITY = 0.2
EVAL_X = 0.4                                  # m


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape=None, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = dtype


def _hat(vector):
    x, y, z = vector
    return [[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]]


def _mat_mul(left, right):
    return [[sum(left[row][k] * right[k][col] for k in range(3)) for col in range(3)] for row in range(3)]


def _mat_vec(matrix, vector):
    return [sum(matrix[row][k] * vector[k] for k in range(3)) for row in range(3)]


def _dot(left, right):
    return sum(left[k] * right[k] for k in range(3))


def _cross(left, right):
    return [
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    ]


def _norm(vector):
    return math.sqrt(_dot(vector, vector))


def _unit(vector):
    length = _norm(vector)
    if length <= 0.0:
        return [1.0, 0.0, 0.0]
    return [value / length for value in vector]


def _rotation(roll, pitch, yaw):
    """``Rotation.from_euler('xyz', (roll, pitch, yaw)).as_matrix()`` (quad.py:197-199)."""

    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = [[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]]
    ry = [[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]]
    rz = [[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]]
    return _mat_mul(rz, _mat_mul(ry, rx))


def _flatten(matrix):
    """Column-major flattening, the layout of ``R.reshape(9, 1, order='F')`` (quad.py:204 and :248)."""

    return [matrix[row][col] for col in range(3) for row in range(3)]


def _matrix(flat):
    columns = (flat[6:9], flat[9:12], flat[12:15])
    return [[columns[col][row] for col in range(3)] for row in range(3)]


def _project(matrix):
    """Re-orthonormalize to SO(3), like ``ensure_SO3`` before each upstream step (quad.py:245-249, quad_utils.py:123-142)."""

    first = _unit([matrix[row][0] for row in range(3)])
    second = [matrix[row][1] for row in range(3)]
    second = _unit([second[k] - _dot(second, first) * first[k] for k in range(3)])
    third = _cross(first, second)
    return [[first[row], second[row], third[row]] for row in range(3)]


class FakeQuadEnv:
    """Quad-v0 without numpy/scipy: ``reset(seed, options)`` and ``step(action)`` return what the env returns."""

    metadata = {"render_modes": ["human"]}                    # quad.py:20

    def __init__(self, render_mode=None):
        if render_mode not in (None, "human"):
            raise ValueError("the fake Quad-v0 supports render_mode None or 'human'")
        self.f = MASS * GRAVITY                                # quad.py:36
        self.hover_force = HOVER_FORCE                         # quad.py:38
        self.min_force = MIN_FORCE                             # quad.py:39
        self.max_force = MAX_FORCE                             # quad.py:40
        self.avrg_act = AVRG_ACT                               # quad.py:41
        self.scale_act = SCALE_ACT                             # quad.py:42
        self.freq = FREQ                                       # quad.py:60
        self.dt = DT                                           # quad.py:61
        self.x_lim = X_LIM                                     # quad.py:104
        self.v_lim = V_LIM                                     # quad.py:105
        self.W_lim = W_LIM                                     # quad.py:106
        self.euler_lim = EULER_LIM                             # quad.py:107
        high = [X_LIM] * 3 + [V_LIM] * 3 + [1.0] * 9 + [W_LIM] * 3
        self.observation_space = Box([-value for value in high], high, shape=(18,))   # quad.py:108-124
        self.action_space = Box([-1.0] * 4, [1.0] * 4, shape=(4,))                    # quad.py:126-132
        self.state = None                                      # quad.py:135
        self._rng = random.Random()
        self._steps = 0

    def reset(self, env_type="train", seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        yaw = self._rng.uniform(-math.pi, math.pi)              # quad.py:339
        if env_type == "train":
            if self._rng.random() < TRAIN_ORIGIN_PROBABILITY:   # quad.py:342
                init_x = init_v = init_r = init_w = 0.0
            else:
                init_x, init_v = TRAIN_X, TRAIN_V               # quad.py:348-349
                init_r, init_w = TRAIN_R, TRAIN_W               # quad.py:350-351
        elif env_type == "eval":
            init_x, init_v = EVAL_X, 0.0                        # quad.py:353-354
            init_r, init_w = 0.0, 0.0                           # quad.py:355-356
        else:
            init_x, init_v, init_r, init_w = TRAIN_X, TRAIN_V, TRAIN_R, TRAIN_W
        x = [self._rng.uniform(-init_x, init_x) for _ in range(3)]       # quad.py:188
        v = [self._rng.uniform(-init_v, init_v) for _ in range(3)]       # quad.py:191
        w = [self._rng.uniform(-init_w, init_w) for _ in range(3)]       # quad.py:194
        roll = self._rng.uniform(-init_r, init_r)                        # quad.py:197
        pitch = self._rng.uniform(-init_r, init_r)
        state = list(x) + list(v) + _flatten(_rotation(roll, pitch, yaw)) + list(w)
        self.state = [float(value) for value in state]
        self._steps = 0
        return list(self.state), {}

    def _forces(self, normalized_action):
        """Scale the normalized action and clip each motor thrust (quad.py:225-235)."""

        forces = []
        for value in normalized_action:
            force = SCALE_ACT * float(value) + AVRG_ACT
            forces.append(min(MAX_FORCE, max(MIN_FORCE, force)))
        return forces

    def _derivative(self, flat, thrust, moment):
        """The equations of motion of quad.py:321-335, as an 18-element state derivative."""

        x, v, w = flat[0:3], flat[3:6], flat[15:18]
        matrix = _matrix(flat)
        third = [matrix[0][2], matrix[1][2], matrix[2][2]]
        v_dot = [-thrust * third[k] / MASS for k in range(3)]
        v_dot[2] += GRAVITY
        rotation_dot = _flatten(_mat_mul(matrix, _hat(w)))
        jw = [J1 * w[0], J2 * w[1], J3 * w[2]]
        gyro = _mat_vec(_hat(w), jw)
        w_dot = [(-gyro[k] + moment[k]) / (J1, J2, J3)[k] for k in range(3)]
        return list(v) + v_dot + rotation_dot + w_dot

    def _integrate(self, flat, thrust, moment):
        """One fixed-step RK4 over ``dt`` (upstream uses solve_ivp/DOP853, quad.py:263-266)."""

        k1 = self._derivative(flat, thrust, moment)
        k2 = self._derivative([flat[k] + 0.5 * DT * k1[k] for k in range(18)], thrust, moment)
        k3 = self._derivative([flat[k] + 0.5 * DT * k2[k] for k in range(18)], thrust, moment)
        k4 = self._derivative([flat[k] + DT * k3[k] for k in range(18)], thrust, moment)
        return [flat[k] + DT / 6.0 * (k1[k] + 2.0 * k2[k] + 2.0 * k3[k] + k4[k]) for k in range(18)]

    def _reward(self, flat):
        """The raw ``reward_wrapper`` scalar of quad.py:274-298 with the default coefficients."""

        x, v, w = flat[0:3], flat[3:6], flat[15:18]
        matrix = _matrix(flat)
        heading = math.atan2(matrix[1][0], matrix[0][0])    # get_current_b1, quad_utils.py:97-101
        return (-C_X * _dot(x, x) - C_V * _dot(v, v)
                - C_B1 * abs(heading / math.pi) - C_W * _dot(w, w))

    def _terminated(self, flat):
        """The termination test of quad.py:301-318 with the state limits of quad.py:103-107."""

        x, v, w = flat[0:3], flat[3:6], flat[15:18]
        matrix = _matrix(flat)
        roll = math.atan2(matrix[2][1], matrix[2][2])
        pitch = math.atan2(-matrix[2][0], math.sqrt(matrix[0][0] ** 2 + matrix[1][0] ** 2))
        return bool(any(abs(value) >= X_LIM for value in x)
                    or any(abs(value) >= V_LIM for value in v)
                    or any(abs(value) >= W_LIM for value in w)
                    or abs(math.degrees(roll)) >= EULER_LIM
                    or abs(math.degrees(pitch)) >= EULER_LIM)

    def step(self, normalized_action):
        if self.state is None:
            raise RuntimeError("call reset before step")
        forces = self._forces(normalized_action)
        thrust = sum(forces)
        moment = [
            ARM * (forces[3] - forces[1]),                        # quad.py:51-56
            ARM * (forces[0] - forces[2]),
            C_TF * (-forces[0] + forces[1] - forces[2] + forces[3]),
        ]
        state = self._integrate(list(self.state), thrust, moment)
        rotation = _project(_matrix(state))
        state[6:15] = _flatten(rotation)
        self.state = [float(value) for value in state]
        self._steps += 1
        observation = list(self.state)
        reward = self._reward(self.state)
        terminated = self._terminated(self.state)
        truncated = self._steps >= MAX_EPISODE_STEPS
        return observation, reward, terminated, truncated, {}

    def close(self):
        self.state = None
