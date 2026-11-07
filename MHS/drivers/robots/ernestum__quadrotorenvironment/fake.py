"""Fake backend of the QuadrotorEnvironment driver: a pure Python stand-in for the upstream simulator.

The acceptance gate has no ``quadrotor_environment`` installation, no ``gym`` and no ``numpy-quaternion``, and
package code never imports the clone.  This module re-implements the default configuration of
``quadrotor_environment.quadrotor_environment:QuadrotorEnvironment`` (the class the driver names as ``native``):
the explicit ``QuadrotorModel`` dynamics of ``quadrotor_environment/quadrotor_model.py:76-109``, the
``ModelDelayWrapper`` step of ``quadrotor_environment/model_delay_wrapper.py:121-144`` with its zero delay/jitter
defaults, the default ``ToObservationMap`` of ``quadrotor_environment/observation_mapping.py:22-25`` and the
default ``RewardFunction`` of ``quadrotor_environment/reward_function.py:21-39``.  Every constant below cites the
line of the clone at the pinned commit 597f8e3294c6a5d3ffc6907749f94a97dee700f3.

The public members are the ones ``QuadrotorEnvironment`` has (``reset``, ``step``; gate G7).  The two space
stand-ins duck-type ``gym.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``.

What this is not, and what the fidelity ``gaps`` of the driver say:

* the dynamics, the observation map and the reward are re-implemented in pure Python floats; upstream uses
  numpy arrays and numpy-quaternion, so the numbers can differ in the last digits and were never compared;
* the initial state is drawn with Python's ``random.Random`` from the same distributions as
  ``quadrotor_environment/quadrotor_environment.py:180-194``; upstream draws from numpy's global generator, so one
  seed gives different initial states on the two implementations;
* only the default configuration is modelled: no delays, jitter, observation noise or parameter randomization;
* there is no rendering, no ZCM channel and no hardware.

Nothing here talks to a device.
"""

import math
import random

# quadrotor_environment/quadrotor_model.py:41-48 (QuadrotorModel.__init__ defaults)
G0 = 9.80665                                     # gravity (m/s^2), quadrotor_model.py:41
MASS = 1.43805                                   # mass (kg), quadrotor_model.py:42
INERTIA = (0.01467, 0.01441, 0.02441)            # moments of inertia, quadrotor_model.py:43
LP = 0.16                                        # half side length (m), quadrotor_model.py:44
KP = 1.018841e-5                                 # thrust coefficient, quadrotor_model.py:45
IP = 6.32180911740998e-09                        # propeller inertia coefficient, quadrotor_model.py:46
B = 4.82e-8                                      # drag coefficient, quadrotor_model.py:47
# quadrotor_model.py:74: hovering_thrust = sqrt((m * g0 / kp) / 4); the class uses it as a speed.
HOVERING_SPEED = math.sqrt((MASS * G0 / KP) / 4)

# quadrotor_model.py:65-68: the mixer matrix M (moments x, y, z and collective thrust from squared speeds).
M0 = [LP * KP * -1, LP * KP * -1, LP * KP * +1, LP * KP * +1]
M1 = [LP * KP * +1, LP * KP * -1, LP * KP * -1, LP * KP * +1]
M2 = [B * -1, B * +1, B * -1, B * +1]
M3 = [KP * -1, KP * -1, KP * -1, KP * -1]

# quadrotor_environment/quadrotor_environment.py:57-58 (constructor defaults)
BOX_SIDE_LENGTH = 2.0                            # :57
INITIAL_VELOCITY = 1.0                           # :57
INITIAL_ANGULAR_VELOCITY = 1.0                   # :57
MAX_TIME = 10.0                                  # seconds, :58
CONTROLLER_PERIOD = 0.01                         # seconds, :58

# quadrotor_environment/model_state_clipping_wrapper.py:13-16 (StateClippingWrapper defaults)
VELOCITY_BOUND = 5.0
ANGULAR_VELOCITY_BOUND = 20.0

# quadrotor_environment/observation_mapping.py:22-25 (ToObservationMap defaults)
POSITION_SCALE = 0.5
VELOCITY_SCALE = 0.5
ANGULAR_VELOCITY_SCALE = 0.15

# quadrotor_environment/reward_function.py:22-39 (RewardFunction defaults)
REWARD_SCALE = 0.00076
POSITION_H, POSITION_V = 9.5, 2.2
VELOCITY_H, VELOCITY_V = 0.9, 1.5
ROTATION_H, ROTATION_V = 2.0, 2.0
ANGULAR_VELOCITY_H, ANGULAR_VELOCITY_V = 2.0, 2.0
PROPELLER_SPEED_DEVIATION = 1.0
PROPELLER_ACCELERATION = 1.0

# quadrotor_environment/observation_mapping.py:139-145: the default observation concatenates the position (3),
# velocity (3), rotation matrix (9) and angular velocity (3) components; the propeller speed, dt and
# observation-age scales default to 0 (:22-25), so those components are omitted.
OBSERVATION_SIZE = 18


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element of a flat vector."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


def _multiply(a, b):
    """Hamilton product of two quaternions ``(w, x, y, z)``."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw)


def _conjugate(q):
    return (q[0], -q[1], -q[2], -q[3])


def _normalize(q):
    length = math.sqrt(sum(value * value for value in q))
    if length == 0.0:
        return (1.0, 0.0, 0.0, 0.0)
    return tuple(value / length for value in q)


def _exp_pure(vector):
    """``numpy.quaternion(0, *vector).exp()``: rotation by the angle ``|vector|`` around ``vector / |vector|``."""
    angle = math.sqrt(sum(value * value for value in vector))
    if angle == 0.0:
        return (1.0, 0.0, 0.0, 0.0)
    s = math.sin(angle) / angle
    return (math.cos(angle), vector[0] * s, vector[1] * s, vector[2] * s)


def _rotate_vector(q, vector):
    """``quadrotor_environment/utils.py:9-10``: ``(q.conjugate() * (0, v) * q).components[1:4]``."""
    rotated = _multiply(_multiply(_conjugate(q), (0.0, vector[0], vector[1], vector[2])), q)
    return [rotated[1], rotated[2], rotated[3]]


def _rotation_matrix(q):
    """The row-major rotation matrix of a unit quaternion (numpy-quaternion ``as_rotation_matrix``)."""
    w, x, y, z = _normalize(q)
    return [
        1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - w * z), 2.0 * (x * z + w * y),
        2.0 * (x * y + w * z), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - w * x),
        2.0 * (x * z - w * y), 2.0 * (y * z + w * x), 1.0 - 2.0 * (x * x + y * y),
    ]


def _euler_zyx(q):
    """``quadrotor_environment/utils.py:86-99`` (quat2eulzyx)."""
    q0, q1, q2, q3 = q
    v1_x = 2 * (q0 * q0 + q1 * q1) - 1
    v1_y = 2 * (q0 * -q3 + q1 * q2)
    v2_x = 2 * (q0 * q2 + q3 * q1)
    v2_y = 2 * (-q0 * q1 + q3 * q2)
    v2_z = 2 * (q0 * q0 + q3 * q3) - 1
    if v2_x < -0.9999999999 or v2_x > 0.9999999999:
        return [0.0, 0.0, 0.0]
    return [math.atan2(v1_y, v1_x), -math.asin(v2_x), math.atan2(v2_y, v2_z)]


def _inverted_huber_loss(value, d=2.0):
    """``quadrotor_environment/utils.py:55-61``."""
    if value > 0:
        low_range_value = math.sqrt(2 * value)
        return low_range_value if low_range_value < d else value / d + 0.5 * d
    low_range_value = math.sqrt(2 * -value)
    return -low_range_value if low_range_value < d else value / d - 0.5 * d


def _sample_random_rotation(rng):
    """``quadrotor_environment/utils.py:32-41`` (sample_random_rotation) with a Python ``random.Random``."""
    length = 0.0
    alpha = [0.0, 0.0, 0.0]
    while length == 0:
        alpha = [rng.gauss(0.0, 1.0) for _ in range(3)]
        length = math.sqrt(sum(value * value for value in alpha))
    alpha = [value / length for value in alpha]
    amount = rng.gauss(0.0, 1.0) * math.pi / 2
    return _exp_pure([value * amount for value in alpha])


class FakeQuadrotorEnvironment:
    """The default ``QuadrotorEnvironment`` without numpy: ``reset()`` and ``step(action)`` as the upstream has them.

    ``reset()`` returns the initial 18-element observation and ``step(action)`` returns
    ``(observation, reward, done, {})``, the legacy Gym shape of
    ``quadrotor_environment/quadrotor_environment.py:178``.  The bridge accepts that shape (it unpacks a four-tuple
    as terminated with truncated ``False``), as it does the upstream ``reset`` that takes no ``seed``/``options``.
    The keyword ``seed`` and ``options`` arguments are an adapter convenience for the bridge's seed input; the
    upstream ``reset`` has no seed parameter, which the fidelity notes of the driver state.
    """

    def __init__(self, **options):
        if options:
            # The upstream constructor takes many configuration dicts; this stand-in models the default only.
            raise ValueError(f"the fake models the default QuadrotorEnvironment; unsupported options {sorted(options)}")
        self.action_space = Box([-1.0, -1.0, -1.0, -1.0], [1.0, 1.0, 1.0, 1.0])
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self._rng = random.Random()
        self._time = 0.0
        self._state = None
        self._pending_action = None
        self._previous_relative_speed = None
        self._dt = CONTROLLER_PERIOD

    # -- public upstream members -------------------------------------------------
    def reset(self, initial_state=None, initial_propeller_speed=None, seed=None, options=None):
        """Reset to a random state (drawn from ``seed`` when given) and return the initial observation."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        if initial_state is None:
            position = [self._rng.uniform(-BOX_SIDE_LENGTH, BOX_SIDE_LENGTH) for _ in range(3)]
            velocity = [self._rng.uniform(-INITIAL_VELOCITY, INITIAL_VELOCITY) for _ in range(3)]
            rotation = _sample_random_rotation(self._rng)
            angular_velocity = [self._rng.uniform(-INITIAL_ANGULAR_VELOCITY, INITIAL_ANGULAR_VELOCITY)
                                for _ in range(3)]
        else:
            position, velocity, rotation, angular_velocity = initial_state
            rotation = tuple(rotation)
        if initial_propeller_speed is None:
            initial_propeller_speed = [HOVERING_SPEED] * 4
        self._state = {
            "position": [float(value) for value in position],
            "velocity": [float(value) for value in velocity],
            "rotation": _normalize(rotation),
            "angular_velocity": [float(value) for value in angular_velocity],
            "propeller_speed": [float(value) for value in initial_propeller_speed],
        }
        self._pending_action = [float(value) for value in initial_propeller_speed]
        self._previous_relative_speed = [value / HOVERING_SPEED for value in self._pending_action]
        self._time = 0.0
        self._dt = CONTROLLER_PERIOD
        return self._observation()

    def step(self, action):
        """Apply one action for one controller period; return ``(observation, reward, done, {})``."""
        if self._state is None:
            raise RuntimeError("call reset before step")
        values = [float(value) for value in action]
        if len(values) != 4:
            raise ValueError(f"the action must have four elements, got {len(values)}")
        dt = self._dt
        # propeller_speed_mapping.py:51-57 with the defaults of :13-15 (relative_min 0, relative_max 3, direct).
        relative_target = [(value + 1.0) / 2.0 * 3.0 for value in values]
        relative_acceleration = [(target - previous) / dt
                                 for target, previous in zip(relative_target, self._previous_relative_speed)]
        self._previous_relative_speed = relative_target
        propeller_speeds = [value * HOVERING_SPEED for value in relative_target]
        # quadrotor_environment.py:151-153: reward_base 'current_state' rewards the state before the step.
        reward = self._reward(self._state, relative_target, relative_acceleration)
        # model_delay_wrapper.py:131-144 with zero delay: the previous action is held for the period and the new
        # action becomes the pending one; compute_past_state at the new time returns the materialized state.
        self._state = self._next_state(self._state, self._pending_action, dt)
        self._pending_action = propeller_speeds
        self._time += dt
        return self._observation(), reward, self._time >= MAX_TIME, {}

    # -- internals ---------------------------------------------------------------
    def _observation(self):
        state = self._state
        position = _rotate_vector(state["rotation"], [value * POSITION_SCALE for value in state["position"]])
        velocity = _rotate_vector(state["rotation"], [value * VELOCITY_SCALE for value in state["velocity"]])
        angular_velocity = [value * ANGULAR_VELOCITY_SCALE for value in state["angular_velocity"]]
        return position + velocity + _rotation_matrix(state["rotation"]) + angular_velocity

    def _next_state(self, state, propeller_speed, h):
        """``quadrotor_model.py:76-109`` plus the clipping of ``model_state_clipping_wrapper.py:33-46``."""
        next_propeller_speed = [
            speed - (IP ** h - 1.0) * (target - speed)
            for speed, target in zip(state["propeller_speed"], propeller_speed)
        ]
        squared = [value * value for value in next_propeller_speed]
        moments = [
            sum(a * b for a, b in zip(row, squared))
            for row in (M0, M1, M2, M3)
        ]
        thrust = [0.0, 0.0, moments[3] / MASS]
        acceleration = _rotate_vector(_conjugate(state["rotation"]), thrust)
        acceleration[2] += G0
        next_position = [p + v * h + a * h * h / 2.0
                         for p, v, a in zip(state["position"], state["velocity"], acceleration)]
        next_velocity = [v + a * h for v, a in zip(state["velocity"], acceleration)]
        omega_half_h = [(w * h + moment / inertia * h * h / 2.0) / 2.0
                        for w, moment, inertia in zip(state["angular_velocity"], moments[:3], INERTIA)]
        next_rotation = _normalize(_multiply(state["rotation"], _exp_pure(omega_half_h)))
        next_angular_velocity = [w + moment / inertia * h
                                 for w, moment, inertia in zip(state["angular_velocity"], moments[:3], INERTIA)]
        return {
            "position": next_position,
            "velocity": [min(max(value, -VELOCITY_BOUND), VELOCITY_BOUND) for value in next_velocity],
            "rotation": next_rotation,
            "angular_velocity": [min(max(value, -ANGULAR_VELOCITY_BOUND), ANGULAR_VELOCITY_BOUND)
                                 for value in next_angular_velocity],
            "propeller_speed": next_propeller_speed,
        }

    def _reward(self, state, relative_speed, relative_acceleration):
        """``reward_function.py:21-39`` and ``:108-137`` with inverted huber scaling, reward_base current_state."""
        position, velocity = state["position"], state["velocity"]
        angular = state["angular_velocity"]
        terms = [
            _inverted_huber_loss(POSITION_H * math.hypot(position[0], position[1])),
            _inverted_huber_loss(POSITION_V * abs(position[2])),
            _inverted_huber_loss(VELOCITY_H * math.hypot(velocity[0], velocity[1])),
            _inverted_huber_loss(VELOCITY_V * abs(velocity[2])),
            _inverted_huber_loss(ANGULAR_VELOCITY_H * math.hypot(angular[0], angular[1])),
            _inverted_huber_loss(ANGULAR_VELOCITY_V * abs(angular[2])),
        ]
        euler = _euler_zyx(state["rotation"])
        terms.append(_inverted_huber_loss(ROTATION_H * abs(euler[1])))
        terms.append(_inverted_huber_loss(ROTATION_V * abs(euler[0])))
        mean = sum(relative_speed) / len(relative_speed)
        terms.append(PROPELLER_SPEED_DEVIATION * sum((value - mean) ** 2 for value in relative_speed))
        terms.append(PROPELLER_ACCELERATION * sum(value * value for value in relative_acceleration))
        return -REWARD_SCALE * sum(terms)
