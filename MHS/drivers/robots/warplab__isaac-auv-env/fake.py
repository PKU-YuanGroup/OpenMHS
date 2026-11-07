"""Fake backend of the WarpAUV driver: a pure Python stand-in for ``Isaac-WarpAUV-Direct-v1``.

Why a fake: the gate cannot run the upstream environment (IsaacSim 4.5.0 and IsaacLab 2.2.0 with a GPU,
README.md:12), and package code never imports the clone.  This module re-implements the interface of
``warpauv_env:WarpAUVEnv`` (``action_space``, ``observation_space``, ``reset``, ``step``) and a reduced version of
its thruster and drag equations.  Every constant below cites the clone at commit
7c5ebe7f7a08acd2570b5fba328e92b7f59f6794.  Numbers that the clone does not state are test data and are marked
``# placeholder``.

What this is not, all listed in the fidelity ``gaps`` of the driver:

* it is not PhysX: there are no contacts, no GPU simulation and no domain randomization of mass or volume;
* it integrates one 1/120 s step per ``step()`` call, while the upstream environment runs two physics substeps per
  control step (decimation = 2);
* it serves one environment, while the clone configures four parallel environments;
* it assumes neutral buoyancy, so gravity and buoyancy cancel;
* it uses Python's ``random.Random`` instead of the upstream torch and numpy generators, so a seed does not
  reproduce an upstream trajectory;
* it has no rendering.

Nothing here talks to a device.
"""

import math
import random

# warpauv_env.py:61: SimulationCfg(dt=1 / 120)
DT = 1.0 / 120.0
# warpauv_env.py:74: decimation = 2 (the upstream control period is two physics steps)
DECIMATION = 2
# warpauv_env.py:76: episode_length_s = 3.0
EPISODE_LENGTH_S = 3.0
# placeholder: the fake's cap is 3.0 s / (1/120 s * 2) = 180 control steps
MAX_STEPS = 180
# warpauv_env.py:85: starting_depth = 8
STARTING_DEPTH = 8.0
# warpauv_env.py:91: goal_spawn_radius = 2.0
GOAL_SPAWN_RADIUS = 2.0
# warpauv_env.py:82-84: max_auv_x = 7, max_auv_y = 7, max_auv_z = 7
MAX_AUV_X = 7.0
MAX_AUV_Y = 7.0
MAX_AUV_Z = 7.0
# warpauv_env.py:109: water_rho = 997.0 kg/m^3; :110 water_beta = 0.001306 Pa s
WATER_RHO = 997.0
WATER_BETA = 0.001306
# warpauv_env.py:111: rotor_constant = 0.1 / 100.0
ROTOR_CONSTANT = 0.1 / 100.0
# warpauv_env.py:113: volume = 0.022747843530591776 m^3; :115 mass = 2.2701e+01 kg
VOLUME = 0.022747843530591776
MASS = 2.2701e01
# warpauv_env.py:174-176: inertia_tensors = (0.37, 0.97, 1.19)
INERTIA = (0.37, 0.97, 1.19)
# warpauv_env.py:100-105: the reward scales used by the total reward
REW_SCALE_POS = 0.2
REW_SCALE_ANG = 0.5
REW_SCALE_ACTIONS = 0.2
REW_SCALE_ANG_VEL = 0.0

# warpauv_env.py:408-410: the PWM-to-rotor-speed polynomial thresholds and coefficients
PWM_DEADBAND = 0.08
PWM_POS_QUADRATIC = -139.0
PWM_POS_LINEAR = 500.0
PWM_POS_OFFSET = 8.28
PWM_NEG_QUADRATIC = 161.0
PWM_NEG_LINEAR = 517.86
PWM_NEG_OFFSET = -5.72


def _quat_from_euler_xyz(roll, pitch, yaw):
    """Quaternion (w, x, y, z) from roll/pitch/yaw, the form used by thruster_dynamics.py:32-38."""
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return _normalize([
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    ])


def _normalize(vector):
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return [0.0 for _ in vector]
    return [value / norm for value in vector]


def _quat_mul(left, right):
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return [
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    ]


def _quat_conjugate(quat):
    return [quat[0], -quat[1], -quat[2], -quat[3]]


def _quat_apply(quat, vector):
    """Rotate ``vector`` by ``quat`` (w, x, y, z); the same operation as isaaclab.utils.math.quat_apply."""
    w, x, y, z = quat
    vx, vy, vz = vector
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return [
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    ]


def _cross(left, right):
    return [
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    ]


def _quat_from_omega(omega, dt):
    """The incremental body-frame rotation for angular velocity ``omega`` over ``dt`` seconds."""
    rate = math.sqrt(sum(value * value for value in omega))
    angle = rate * dt
    if angle == 0.0:
        return [1.0, 0.0, 0.0, 0.0]
    half = angle / 2.0
    scale = math.sin(half) / rate
    return [math.cos(half), omega[0] * scale, omega[1] * scale, omega[2] * scale]


def _random_quat(rng):
    """A uniform random orientation, the role of isaaclab.utils.math.random_orientation (warpauv_env.py:348)."""
    values = [rng.gauss(0.0, 1.0) for _ in range(4)]
    norm = math.sqrt(sum(value * value for value in values))
    while norm == 0.0:                                             # placeholder: retry a degenerate draw
        values = [rng.gauss(0.0, 1.0) for _ in range(4)]
        norm = math.sqrt(sum(value * value for value in values))
    return [value / norm for value in values]


def _random_ball(rng, radius):
    """Uniform sample in a ball, the role of WarpAUVEnv._sample_from_sphere (warpauv_env.py:378-385)."""
    coords = [rng.gauss(0.0, 1.0) for _ in range(3)]
    norm = math.sqrt(sum(value * value for value in coords))
    if norm == 0.0:                                                # placeholder: retry a degenerate draw
        return [0.0, 0.0, 0.0]
    sampled_radius = radius * rng.random() ** (1.0 / 3.0)          # warpauv_env.py:383
    return [sampled_radius * value / norm for value in coords]


# thruster_dynamics.py:32-47: offsets in metres and orientations from the clone, in action order
# (0 drive_left, 1 drive_right, 2 rear_left, 3 rear_right, 4 front_left, 5 front_right)
THRUSTERS = (
    ((-0.4127, 0.1506, -0.0889), (1.0, 0.0, 0.0, 0.0)),
    ((-0.4127, -0.1506, -0.0889), (1.0, 0.0, 0.0, 0.0)),
    ((-0.303, 0.1461, -0.1587), _quat_from_euler_xyz(0.0, -0.785398, 1.5708)),
    ((-0.303, -0.1461, -0.1587), _quat_from_euler_xyz(0.0, -0.785398, -1.5708)),
    ((0.0585, 0.1461, -0.0540), _quat_from_euler_xyz(0.0, 0.785398, 1.5708)),
    ((0.0585, -0.1461, -0.0540), _quat_from_euler_xyz(0.0, 0.785398, -1.5708)),
)


def _thruster_force(pwm):
    """PWM -> rotor speed (warpauv_env.py:408-410) -> thrust (thruster_dynamics.py:141)."""
    value = max(-1.0, min(1.0, float(pwm)))                        # warpauv_env.py:227-232
    if abs(value) < PWM_DEADBAND:
        rotor = 0.0
    elif value >= PWM_DEADBAND:
        rotor = (PWM_POS_QUADRATIC * value * value + PWM_POS_LINEAR * value + PWM_POS_OFFSET)
    else:
        rotor = (PWM_NEG_QUADRATIC * value * value + PWM_NEG_LINEAR * value + PWM_NEG_OFFSET)
    return ROTOR_CONSTANT * abs(rotor) * rotor


def _half_dimensions():
    """rigid_body_hydrodynamics.py:53-58: the half dimensions of the equivalent inertia box."""
    ix, iy, iz = INERTIA
    factor = 3.0 / (2.0 * MASS)
    return (
        math.sqrt(factor * (iy + iz - ix)),
        math.sqrt(factor * (iz + ix - iy)),
        math.sqrt(factor * (ix + iy - iz)),
    )


def _drag(lin_vel_b, ang_vel_b):
    """Quadratic and viscous drag, rigid_body_hydrodynamics.py:68-90, in the body frame."""
    rx, ry, rz = _half_dimensions()
    r_eq = (rx + ry + rz) / 3.0                                    # rigid_body_hydrodynamics.py:85
    quad_coeff = (2.0 * WATER_RHO * ry * rz,
                  2.0 * WATER_RHO * rx * rz,
                  2.0 * WATER_RHO * rx * ry)
    force = [-quad_coeff[index] * abs(lin_vel_b[index]) * lin_vel_b[index]
             - 6.0 * WATER_BETA * math.pi * r_eq * lin_vel_b[index]
             for index in range(3)]
    torque = [
        -0.5 * WATER_RHO * rx * (ry ** 4 + rz ** 4) * abs(ang_vel_b[0]) * ang_vel_b[0]
        - 8.0 * WATER_BETA * math.pi * r_eq ** 3 * ang_vel_b[0],
        -0.5 * WATER_RHO * ry * (rx ** 4 + rz ** 4) * abs(ang_vel_b[1]) * ang_vel_b[1]
        - 8.0 * WATER_BETA * math.pi * r_eq ** 3 * ang_vel_b[1],
        -0.5 * WATER_RHO * rz * (rx ** 4 + ry ** 4) * abs(ang_vel_b[2]) * ang_vel_b[2]
        - 8.0 * WATER_BETA * math.pi * r_eq ** 3 * ang_vel_b[2],
    ]
    return force, torque


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, dtype="float64"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype

    def contains(self, value):
        try:
            values = list(value)
        except TypeError:
            return False
        return len(values) == len(self.low) and all(
            self.low[index] <= float(item) <= self.high[index] for index, item in enumerate(values))


class FakeWarpAUVEnv:
    """One WarpAUV environment without IsaacSim: ``reset(seed, options)`` and ``step(action)``."""

    def __init__(self, **options):
        self.options = dict(options)
        self.dt = DT                                                       # warpauv_env.py:61
        self.action_space = Box([-1.0] * 6, [1.0] * 6)                     # warpauv_env.py:71
        self.observation_space = Box([-math.inf] * 17, [math.inf] * 17)    # warpauv_env.py:70
        self._rng = random.Random()
        self._seed = None
        self._initialized = False
        self._origin = [0.0, 0.0, STARTING_DEPTH]                          # warpauv_env.py:85, :213
        self._pos = [0.0, 0.0, STARTING_DEPTH]                             # warpauv_env.py:213
        self._quat = [1.0, 0.0, 0.0, 0.0]                                  # placeholder: asset orientation
        self._lin_vel_w = [0.0, 0.0, 0.0]                                  # placeholder: asset velocity
        self._ang_vel_b = [0.0, 0.0, 0.0]                                  # placeholder: asset velocity
        self._goal = [1.0, 0.0, 0.0, 0.0]                                  # placeholder: replaced by reset
        self._actions = [0.0] * 6                                          # placeholder: no command yet
        self._tick = 0

    def _observation(self):
        """warpauv_env.py:248-257: goal, body-frame offset, quaternion, body-frame linear and angular velocity."""
        conjugate = _quat_conjugate(self._quat)
        offset_b = _quat_apply(conjugate, [self._origin[index] - self._pos[index] for index in range(3)])
        linear_b = _quat_apply(conjugate, self._lin_vel_w)
        return (list(self._goal) + offset_b + list(self._quat) + linear_b + list(self._ang_vel_b))

    def reset(self, *, seed=None, options=None):
        """Reset one fake episode; ``options`` is accepted for the Gymnasium reset signature."""
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        # placeholder: the clone does not state the USD asset's initial orientation or velocity
        offset = _random_ball(self._rng, GOAL_SPAWN_RADIUS)                 # warpauv_env.py:316-318
        self._pos = [self._origin[index] + offset[index] for index in range(3)]
        self._quat = [1.0, 0.0, 0.0, 0.0]                                  # placeholder: asset orientation
        self._lin_vel_w = [0.0, 0.0, 0.0]                                  # placeholder: asset velocity
        self._ang_vel_b = [0.0, 0.0, 0.0]                                  # placeholder: asset velocity
        self._goal = _random_quat(self._rng)                               # warpauv_env.py:346-348
        self._actions = [0.0] * 6                                          # placeholder: no command yet
        self._tick = 0
        self._initialized = True
        return self._observation(), {}

    def step(self, action):
        """Apply six thruster commands and advance the reduced model by one physics timestep."""
        if not self._initialized:
            raise RuntimeError("Call reset before using step method.")
        if not self.action_space.contains(action):
            raise ValueError(f"{action!r} is not in the action space")
        actions = [max(-1.0, min(1.0, float(value))) for value in action]   # warpauv_env.py:227-232
        self._actions = actions

        force_b = [0.0, 0.0, 0.0]
        torque_b = [0.0, 0.0, 0.0]
        for pwm, (offset, orientation) in zip(actions, THRUSTERS):
            thrust = _thruster_force(pwm)                                  # warpauv_env.py:408-410
            force = _quat_apply(orientation, [thrust, 0.0, 0.0])           # warpauv_env.py:420-424
            cross = _cross(offset, force)                                  # warpauv_env.py:432
            for index in range(3):
                force_b[index] += force[index]
                torque_b[index] += cross[index]

        conjugate = _quat_conjugate(self._quat)
        linear_b = _quat_apply(conjugate, self._lin_vel_w)
        drag_force, drag_torque = _drag(linear_b, self._ang_vel_b)
        for index in range(3):
            force_b[index] += drag_force[index]
            torque_b[index] += drag_torque[index]

        force_world = _quat_apply(self._quat, force_b)
        for index in range(3):
            self._lin_vel_w[index] += (force_world[index] / MASS) * DT
            self._pos[index] += self._lin_vel_w[index] * DT
            self._ang_vel_b[index] += (torque_b[index] / INERTIA[index]) * DT
        self._quat = _normalize(_quat_mul(self._quat, _quat_from_omega(self._ang_vel_b, DT)))
        self._tick += 1

        relative = [self._pos[index] - self._origin[index] for index in range(3)]
        terminated = (abs(relative[0]) > MAX_AUV_X or abs(relative[1]) > MAX_AUV_Y
                      or abs(relative[2]) > MAX_AUV_Z)                     # warpauv_env.py:295-304
        truncated = self._tick >= MAX_STEPS                                # placeholder: episode cap
        offset_b = _quat_apply(_quat_conjugate(self._quat), [-value for value in relative])
        dot = sum(self._goal[index] * self._quat[index] for index in range(4))
        reward = (REW_SCALE_POS * math.exp(-sum(value * value for value in offset_b))
                  + REW_SCALE_ANG * math.exp(-(1.0 - dot * dot))
                  + REW_SCALE_ACTIONS * math.exp(-sum(value * value for value in actions))
                  + REW_SCALE_ANG_VEL * math.exp(-sum(value * value for value in self._ang_vel_b)))
        return self._observation(), reward, terminated, truncated, {}
