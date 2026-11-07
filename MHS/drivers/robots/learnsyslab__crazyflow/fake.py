"""Fake backend of the Crazyflow Gymnasium driver: one world of the DroneReachPos-v0 environment.

Why a fake: Crazyflow is a JAX/MuJoCo vector environment (``crazyflow/envs/drone_env.py:48``) and the acceptance
gate does not install JAX, MuJoCo or the clone.  This module is a pure Python stand-in for one world of
``crazyflow.envs.reach_pos_env:ReachPosEnv`` and exposes the public members that class and its ``DroneEnv`` base have
(``reset``, ``step`` and ``close``; gate G7).  The space classes duck-type ``gymnasium.spaces.Box`` and
``Dict`` (the bridge reads ``low``, ``high``, ``shape`` and ``spaces``).

The model parameters below are the upstream defaults of the ``cf2x_L250`` drone (``crazyflow/envs/drone_env.py:68``)
and the fitted ``so_rpy`` dynamics (``crazyflow/dynamics/so_rpy/params.toml:21-34`` and
``crazyflow/dynamics/params.toml:3``).  The start positions and goals are test data, marked ``# placeholder``; they
are not facts, limits or evidence.

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* one world and one drone, not the batched ``(n_worlds, ...)`` arrays of the upstream vector environment;
* the rotational state follows the commanded roll, pitch and yaw directly; the fitted second-order rotational
  dynamics and the angular velocity are not modelled, and the body rate observation stays zero;
* the initial state and goal come from Python's ``random.Random(seed)``, upstream draws them with JAX's generator,
  so one seed does not give the same trajectory on the two;
* there is no rendering, no MuJoCo scene and no collision model.
"""

import math
import random

#: Environment frequency in Hz (crazyflow/envs/drone_env.py:69) and the resulting step, 1 / freq
#: (crazyflow/sim/sim.py:293).
FREQ = 500
DT = 1.0 / FREQ
#: Episode time limit in seconds (crazyflow/envs/drone_env.py:66).
MAX_EPISODE_TIME = 10.0
#: cf2x_L250 parameters of the fitted so_rpy dynamics (crazyflow/dynamics/so_rpy/params.toml:22-31).
MASS = 0.0328
THRUST_MIN_PER_MOTOR = 0.012817578393224994
THRUST_MAX_PER_MOTOR = 0.12
ACC_COEF = 0.0
CMD_F_COEF = 1.023224599403443
#: Global gravity vector, z component (crazyflow/dynamics/params.toml:3).
GRAVITY = 9.81
#: The four motor thrust bounds of the attitude action space (crazyflow/envs/drone_env.py:37-41).
THRUST_MIN = 4.0 * THRUST_MIN_PER_MOTOR
THRUST_MAX = 4.0 * THRUST_MAX_PER_MOTOR
#: Roll, pitch and yaw bounds of the attitude action space (crazyflow/envs/drone_env.py:39-40).
ATTITUDE_LIMIT = math.pi / 2.0
#: Default reset boxes (crazyflow/envs/reach_pos_env.py:32-35) and goal box (:94-96); test data, not facts.
POS_MIN = (-1.0, -1.0, 1.0)  # placeholder
POS_MAX = (1.0, 1.0, 2.0)  # placeholder
VEL_MIN = -1.0  # placeholder
VEL_MAX = 1.0  # placeholder
GOAL_MIN = (-1.0, -1.0, 0.5)  # placeholder
GOAL_MAX = (1.0, 1.0, 1.5)  # placeholder


def _shape(value):
    """The nested shape of a list, so a batched Box reports ``(1, 4)`` like ``gymnasium.vector.utils.batch_space``."""
    shape = []
    item = value
    while isinstance(item, (list, tuple)):
        shape.append(len(item))
        item = item[0] if item else None
    return tuple(shape)


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: bounds, shape and dtype only; no sampling or checking."""

    def __init__(self, low, high):
        self.low = low
        self.high = high
        self.shape = _shape(low)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _clamp(value, low, high):
    return low if value < low else high if value > high else value


def _box(value, default):
    """A three-vector from a reset option, or the default; upstream reads options goal_pos_min/max the same way."""
    return tuple(float(item) for item in (default if value is None else value))


def _euler_to_quat(roll, pitch, yaw):
    """Quaternion (xyzw) of scipy's extrinsic ``Rotation.from_euler("xyz", [roll, pitch, yaw])``."""
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return [
        cy * cp * sr - sy * sp * cr,
        cy * sp * cr + sy * cp * sr,
        sy * cp * cr - cy * sp * sr,
        cy * cp * cr + sy * sp * sr,
    ]


def _body_z(roll, pitch, yaw):
    """The world-frame z axis of the drone at the commanded attitude (so_rpy dynamics uses the rotated z axis)."""
    return (
        math.cos(yaw) * math.sin(pitch) * math.cos(roll) + math.sin(yaw) * math.sin(roll),
        math.sin(yaw) * math.sin(pitch) * math.cos(roll) - math.cos(yaw) * math.sin(roll),
        math.cos(pitch) * math.cos(roll),
    )


class FakeReachPosEnv:
    """One world of ``ReachPosEnv``: ``reset(seed, options)`` and ``step(action)`` return what the upstream env does."""

    def __init__(self, **_options):
        # The batched attitude action space of one world (crazyflow/envs/drone_env.py:35-41, :110-111).
        low = [[-ATTITUDE_LIMIT, -ATTITUDE_LIMIT, -ATTITUDE_LIMIT, THRUST_MIN]]
        high = [[ATTITUDE_LIMIT, ATTITUDE_LIMIT, ATTITUDE_LIMIT, THRUST_MAX]]
        self.action_space = Box(low, high)
        # The batched observation space of one world plus difference_to_goal (crazyflow/envs/drone_env.py:112-120,
        # crazyflow/envs/reach_pos_env.py:48-51).
        inf = float("inf")
        self.observation_space = Dict({
            "pos": Box([[-inf, -inf, -inf]], [[inf, inf, inf]]),
            "quat": Box([[-inf, -inf, -inf, -inf]], [[inf, inf, inf, inf]]),
            "vel": Box([[-inf, -inf, -inf]], [[inf, inf, inf]]),
            "ang_vel": Box([[-inf, -inf, -inf]], [[inf, inf, inf]]),
            "difference_to_goal": Box([[-inf, -inf, -inf]], [[inf, inf, inf]]),
        })
        self._rng = random.Random()
        self._pos = None
        self._quat = None
        self._vel = None
        self._ang_vel = None
        self._goal = None
        self._steps = 0

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        options = dict(options or {})
        # Position and velocity randomization (crazyflow/envs/reach_pos_env.py:101-110).
        self._pos = [self._rng.uniform(POS_MIN[i], POS_MAX[i]) for i in range(3)]  # placeholder
        self._vel = [self._rng.uniform(VEL_MIN, VEL_MAX) for _ in range(3)]  # placeholder
        self._quat = [0.0, 0.0, 0.0, 1.0]
        self._ang_vel = [0.0, 0.0, 0.0]
        # Goal sampling (crazyflow/envs/reach_pos_env.py:54-60, :94-96); options override the bounds.
        pmin = _box(options.get("goal_pos_min"), GOAL_MIN)
        pmax = _box(options.get("goal_pos_max"), GOAL_MAX)
        self._goal = [self._rng.uniform(pmin[i], pmax[i]) for i in range(3)]  # placeholder
        self._steps = 0
        return self._obs(), {}

    def step(self, action):
        values = list(action)
        if len(values) != 4:
            raise ValueError(f"action has {len(values)} elements; the attitude action space has 4")
        roll = _clamp(float(values[0]), -ATTITUDE_LIMIT, ATTITUDE_LIMIT)
        pitch = _clamp(float(values[1]), -ATTITUDE_LIMIT, ATTITUDE_LIMIT)
        yaw = _clamp(float(values[2]), -ATTITUDE_LIMIT, ATTITUDE_LIMIT)
        thrust = _clamp(float(values[3]), THRUST_MIN, THRUST_MAX)
        # Translational part of the fitted so_rpy dynamics (crazyflow/dynamics/so_rpy/dynamics.py:149-155).
        body_z = _body_z(roll, pitch, yaw)
        total_thrust = ACC_COEF + CMD_F_COEF * thrust
        acc = [
            total_thrust * body_z[0] / MASS,
            total_thrust * body_z[1] / MASS,
            total_thrust * body_z[2] / MASS - GRAVITY,
        ]
        # Semi-implicit Euler step, the default integrator of the simulation.
        self._vel = [self._vel[i] + acc[i] * DT for i in range(3)]
        self._pos = [self._pos[i] + self._vel[i] * DT for i in range(3)]
        self._quat = _euler_to_quat(roll, pitch, yaw)
        self._steps += 1
        terminated = self._pos[2] < 0.0
        truncated = self._steps * DT >= MAX_EPISODE_TIME
        if terminated:
            reward = -1.0
        else:
            distance = math.sqrt(sum((self._pos[i] - self._goal[i]) ** 2 for i in range(3)))
            reward = math.exp(-2.0 * distance)
        return self._obs(), reward, terminated, truncated, {}

    def close(self):
        self._pos = None

    def _obs(self):
        # One world, so every array keeps the leading world dimension (crazyflow/envs/drone_env.py:198-206).
        difference = [self._goal[i] - self._pos[i] for i in range(3)]
        return {
            "pos": [list(self._pos)],
            "quat": [list(self._quat)],
            "vel": [list(self._vel)],
            "ang_vel": [list(self._ang_vel)],
            "difference_to_goal": [difference],
        }
