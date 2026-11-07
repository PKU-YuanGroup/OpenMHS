"""Fake backend of the PyFlyt QuadX Hover driver: a pure Python stand-in for ``PyFlyt/QuadX-Hover-v4``.

Why a fake: package code never imports the read-only clone, and the acceptance gate does not install PyFlyt,
pybullet, numpy or gymnasium.  This module mirrors the public surface of
``PyFlyt.gym_envs.quadx_envs.quadx_hover_env:QuadXHoverEnv`` that the Gymnasium bridge uses (``reset``, ``step``,
``close``; gate G7) and duck-types the two spaces (``low``, ``high``, ``shape``, ``dtype``).  The action bounds
come from ``quadx_base_env.py:80-103`` and the observation layout from ``quadx_hover_env.py:96-115`` and
``quadx_base_env.py:62-115`` at commit 9095d41f6fc5f07fe711346b747b4f7fd475b424.

What this is not: the upstream PyBullet simulation.  It is a kinematic stand-in, not a rigid-body model.  It has
no contacts, drag, motor thrust curve, wind, sensor or noise model, and it was never compared with a PyFlyt run.
Those differences are listed in the driver's fidelity ``gaps``.  The start state and the arbitrary coefficients
below are test data (marked ``# placeholder``), not facts about a device or about the upstream simulator.

Nothing here talks to hardware.
"""

import math

# quadx_base_env.py:80-103: flight_mode 0 action space, xyz_limit = np.pi and thrust_limit = 0.8.
ACTION_LOW = [-math.pi, -math.pi, -math.pi, 0.0]
ACTION_HIGH = [math.pi, math.pi, math.pi, 0.8]
# aviary.py:79/161-164 and quadx.py:27: 240 Hz physics, 120 Hz control, two physics steps per control step.
PHYSICS_HZ = 240.0
CONTROL_HZ = 120.0
UPDATES_PER_STEP = int(PHYSICS_HZ / CONTROL_HZ)   # 2
# placeholder: the default start pose of the upstream hover environment (start_pos [0, 0, 1], start_orn zero)
START_POSITION = [0.0, 0.0, 1.0]
START_ANGLES = [0.0, 0.0, 0.0]
# placeholder: fake-only neutral throttle and gravity for the kinematic translation
HOVER_THROTTLE = 0.4
GRAVITY = 9.81


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: bounds and shape only, no sampling."""

    def __init__(self, low, high, dtype="float64"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype


def _quaternion(roll, pitch, yaw):
    """Quaternion (x, y, z, w) from roll, pitch and yaw, in the ENU convention of the clone."""
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return [
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    ]


class FakeQuadXHoverEnv:
    """Kinematic QuadX Hover stand-in: ``reset(seed, options)`` and ``step(action)`` like the upstream class."""

    def __init__(
        self,
        sparse_reward=False,
        flight_mode=0,
        flight_dome_size=3.0,
        max_duration_seconds=10.0,
        angle_representation="quaternion",
        agent_hz=40,
        render_mode=None,
        render_resolution=(480, 480),
    ):
        if render_mode is not None:
            raise ValueError("the fake QuadX Hover cannot render; use render_mode=None")
        if 120 % int(agent_hz) != 0:
            raise ValueError("agent_hz must be a round denominator of 120")
        if angle_representation not in ("euler", "quaternion"):
            raise ValueError("angle_representation must be 'euler' or 'quaternion'")
        self.sparse_reward = bool(sparse_reward)
        self.flight_mode = int(flight_mode)
        self.flight_dome_size = float(flight_dome_size)
        self.max_duration_seconds = float(max_duration_seconds)
        self.angle_representation = angle_representation
        self.agent_hz = int(agent_hz)
        self.render_mode = None
        self.render_resolution = tuple(render_resolution)
        self.max_steps = int(self.agent_hz * self.max_duration_seconds)
        self.env_step_ratio = int(CONTROL_HZ / self.agent_hz)
        self.timestep_s = self.env_step_ratio * UPDATES_PER_STEP / PHYSICS_HZ
        if self.flight_mode == -1:
            self.action_space = Box([0.0] * 4, [0.8] * 4)
        else:
            self.action_space = Box(ACTION_LOW, ACTION_HIGH)
        attitude_size = 12 if angle_representation == "euler" else 13
        self.observation_space = Box(
            [-math.inf] * (attitude_size + 4 + 4),
            [math.inf] * (attitude_size + 4 + 4),
        )
        self._state = None
        self._seed = None
        self._reset_state()

    def _reset_state(self):
        self._position = list(START_POSITION)
        self._velocity = [0.0, 0.0, 0.0]
        self._angles = list(START_ANGLES)
        self._angular_velocity = [0.0, 0.0, 0.0]
        self._action = [0.0, 0.0, 0.0, 0.0]
        self._motors = [0.0, 0.0, 0.0, 0.0]
        self._step_count = 0
        self._termination = False
        self._truncation = False
        self._reward = 0.0
        self._info = {"out_of_bounds": False, "collision": False, "env_complete": False}

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._seed = int(seed)
        self._reset_state()
        self._state = self._observe()
        return list(self._state), dict(self._info)

    def step(self, action):
        if self._state is None:
            raise RuntimeError("Call reset before using step method.")
        values = [float(value) for value in action]
        if len(values) != 4:
            raise ValueError(f"the action has {len(values)} elements, expected 4")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("the action has a non-finite element")
        self._action = values
        self._step_count += 1

        dt = self.timestep_s
        thrust = min(max(values[3], 0.0), 1.0)
        self._angular_velocity = values[:3]
        for index in range(3):
            self._angles[index] += self._angular_velocity[index] * dt
        # placeholder: fake-only kinematic translation; the upstream model integrates PyBullet forces
        acceleration = [
            GRAVITY * math.sin(self._angles[1]),
            -GRAVITY * math.sin(self._angles[0]),
            GRAVITY * (thrust / HOVER_THROTTLE - 1.0),
        ]
        for index in range(3):
            self._velocity[index] += acceleration[index] * dt
            self._position[index] += self._velocity[index] * dt
        self._motors = [thrust, thrust, thrust, thrust]

        distance = math.sqrt(sum((self._position[index] - [0.0, 0.0, 1.0][index]) ** 2
                                 for index in range(3)))
        angular_distance = math.sqrt(self._angles[0] ** 2 + self._angles[1] ** 2)
        self._termination = bool(self._position[2] <= 0.0
                                 or math.sqrt(sum(value * value for value in self._position))
                                 > self.flight_dome_size)
        self._truncation = bool(self._step_count > self.max_steps)
        self._info["collision"] = bool(self._position[2] <= 0.0)
        self._info["out_of_bounds"] = bool(
            math.sqrt(sum(value * value for value in self._position)) > self.flight_dome_size)
        self._info["env_complete"] = False
        if self._termination:
            self._reward = -100.0
        elif self.sparse_reward:
            self._reward = -0.1
        else:
            self._reward = (-0.1 + 1.0 - distance - angular_distance
                            - 0.01 * self._angular_velocity[2] ** 2)
        self._state = self._observe()
        return list(self._state), self._reward, self._termination, self._truncation, dict(self._info)

    def _observe(self):
        if self.angle_representation == "euler":
            attitude = list(self._angular_velocity) + list(self._angles)
        else:
            attitude = list(self._angular_velocity) + _quaternion(*self._angles)
        return attitude + list(self._velocity) + list(self._position) + list(self._action) + list(self._motors)

    def close(self):
        self._state = None
