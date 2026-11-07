"""Fake backend for the Flightmare ``FlightEnvVec`` driver: a pure Python stand-in.

Why a fake: the upstream class wraps the compiled ``flightgym`` pybind module
(``flightlib/src/wrapper/pybind_wrapper.cpp:16-33``) and package code never
imports or runs the clone.  This module re-implements the observable Python
surface of ``flightrl_v2.flightrl_v2.envs.flight_env_vec:FlightEnvVec`` (the
class the driver names as ``native``): a 12-value observation, a 4-value
normalized action in [-1, 1], a random reset, the first-environment scalar
return of the vectorized wrapper, the terminal reward and the step limit.

The public members are the ones ``FlightEnvVec`` has (``reset``, ``step``,
``seed`` and ``close``; gate G7).  The space helpers duck-type
``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and
``dtype``.

What this is not: the Flightmare physics engine.  The dynamics below are an
analytic stand-in with placeholder gains; there is no ``flightgym``, no
quadrotor rigid-body integrator, no Unity rendering and no comparison with the
upstream simulator.  Every sourced constant cites its line in the clone at the
pinned commit 22fb5d16eec32b1816aa568c20643d91ca7c76f7.  Numbers marked
``# placeholder`` are test data, not facts, limits or references.

Nothing here talks to a device.
"""

import math
import random

# flightlib/include/flightlib/envs/quadrotor_env/quadrotor_env.hpp:36 (kNObs)
OBS_DIM = 12
# flightlib/include/flightlib/envs/quadrotor_env/quadrotor_env.hpp:39 (kNAct)
ACT_DIM = 4
# flightlib/configs/quadrotor_env.yaml:3 (quadrotor_env.sim_dt: 0.02)
SIM_DT = 0.02
# flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:53 (goal position [0, 0, 5])
GOAL_POSITION = (0.0, 0.0, 5.0)
# flightlib/configs/quadrotor_env.yaml:18-22 (the reward coefficients)
POS_COEFF = -0.002
ORI_COEFF = -0.002
LIN_VEL_COEFF = -0.0002
ANG_VEL_COEFF = -0.0002
ACT_COEFF = -0.0002
# flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:186 (survival reward)
SURVIVAL_REWARD = 0.01
# flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:189-192 (success bonus)
SUCCESS_DISTANCE = 0.1
SUCCESS_SPEED = 0.1
# flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:198-202 (terminal altitude and reward)
TERMINAL_ALTITUDE = 0.05
TERMINAL_REWARD = -10.0
# flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:90-105 (random reset ranges)
RESET_XY_RANGE = 1.0
RESET_Z_OFFSET = 5.0
RESET_VELOCITY_RANGE = 1.0
RESET_ORIENTATION_SCALE = 0.087
# FlightEnvVec.__init__ default max_episode_steps=300 (flight_env_vec.py:35); a
# wrapper default, not a device bound.
MAX_EPISODE_STEPS = 300

# placeholder: fake-only kinematic gains, test data, not upstream facts
VERTICAL_ACCEL_GAIN = 5.0
HORIZONTAL_ACCEL_GAIN = 1.0
ANGULAR_GAIN = 1.0


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"


class _FakeFlightgym:
    """The small part of ``flightgym.QuadrotorEnv_v1`` that ``FlightEnvVec`` calls.

    ``VecEnv<QuadrotorEnv>`` is bound as ``QuadrotorEnv_v1`` with
    ``reset``, ``step``, ``setSeed``, ``close``, ``getNumOfEnvs``,
    ``getObsDim``, ``getActDim`` and ``getExtraInfoNames``
    (flightlib/src/wrapper/pybind_wrapper.cpp:17-33).  One environment is
    modelled; the upstream backend can be configured with more.
    """

    def __init__(self):
        self._rng = random.Random(0)  # placeholder: deterministic fake RNG seed
        self._closed = False
        self._pos = [0.0, 0.0, 0.0]
        self._vel = [0.0, 0.0, 0.0]
        self._euler = [0.0, 0.0, 0.0]
        self._omega = [0.0, 0.0, 0.0]
        self._draw_start()

    def getNumOfEnvs(self):
        return 1

    def getObsDim(self):
        return OBS_DIM

    def getActDim(self):
        return ACT_DIM

    def getExtraInfoNames(self):
        return []

    def setSeed(self, seed):
        self._rng = random.Random(int(seed))

    def reset(self, obs):
        self._draw_start()
        self._write_obs(obs, 0)
        return True

    def step(self, act, obs, reward, done, extra_info):
        values = [float(value) for value in act[0]]
        if len(values) != ACT_DIM:
            raise ValueError(f"the action must contain {ACT_DIM} values")
        self._integrate(values)
        self._write_obs(obs, 0)
        reward[0] = self._reward(values)
        terminal = self._pos[2] <= TERMINAL_ALTITUDE
        done[0] = terminal
        if terminal:
            # perAgentStep adds the terminal reward and resets the environment
            # (flightlib/src/envs/vec_env.cpp:159-162).
            reward[0] += TERMINAL_REWARD
            self._draw_start()
            self._write_obs(obs, 0)
        return True

    def close(self):
        self._closed = True

    def _draw_start(self):
        # flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:90-105
        self._pos = [
            self._rng.uniform(-RESET_XY_RANGE, RESET_XY_RANGE),
            self._rng.uniform(-RESET_XY_RANGE, RESET_XY_RANGE),
            self._rng.uniform(-RESET_VELOCITY_RANGE, RESET_VELOCITY_RANGE) + RESET_Z_OFFSET,
        ]
        self._vel = [self._rng.uniform(-RESET_VELOCITY_RANGE, RESET_VELOCITY_RANGE) for _ in range(3)]
        self._euler = [self._rng.uniform(-RESET_XY_RANGE, RESET_XY_RANGE) * RESET_ORIENTATION_SCALE
                       for _ in range(3)]
        self._omega = [0.0, 0.0, 0.0]

    def _integrate(self, values):
        # placeholder kinematics: the mean command drives vertical acceleration
        # and the motor differences drive small rates; no flightgym model
        mean = sum(values) / float(ACT_DIM)
        self._vel[2] += VERTICAL_ACCEL_GAIN * mean * SIM_DT
        self._vel[0] += HORIZONTAL_ACCEL_GAIN * (values[0] - values[1]) * SIM_DT
        self._vel[1] += HORIZONTAL_ACCEL_GAIN * (values[2] - values[3]) * SIM_DT
        for axis in range(3):
            self._pos[axis] += self._vel[axis] * SIM_DT
        self._omega = [
            ANGULAR_GAIN * (values[1] - values[0]),
            ANGULAR_GAIN * (values[2] - values[3]),
            ANGULAR_GAIN * (values[0] + values[1] - values[2] - values[3]) / 2.0,
        ]
        for axis in range(3):
            self._euler[axis] += self._omega[axis] * SIM_DT

    def _write_obs(self, obs, index):
        # flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:119-128
        obs[index][:] = list(self._pos) + list(self._euler) + list(self._vel) + list(self._omega)

    def _reward(self, values):
        # flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:159-195
        position_error = sum((self._pos[i] - GOAL_POSITION[i]) ** 2 for i in range(3))
        orientation_error = sum(value * value for value in self._euler)
        linear_error = sum(value * value for value in self._vel)
        angular_error = sum(value * value for value in self._omega)
        action_norm = math.sqrt(sum(value * value for value in values))
        total = (POS_COEFF * position_error + ORI_COEFF * orientation_error
                 + LIN_VEL_COEFF * linear_error + ANG_VEL_COEFF * angular_error
                 + ACT_COEFF * action_norm + SURVIVAL_REWARD)
        if math.sqrt(position_error) < SUCCESS_DISTANCE and math.sqrt(linear_error) < SUCCESS_SPEED:
            total += 1.0
        return total


class FakeFlightEnvVec:
    """A pure Python ``FlightEnvVec``: the first environment of a one-row batch.

    The native class is vectorized, but its Python ``reset`` and ``step``
    already return the first environment's observation and scalar reward
    (flightrl_v2/flightrl_v2/envs/flight_env_vec.py:110-113 and :180-186), so
    this fake preserves that same scalar surface instead of adding an adapter.
    """

    metadata = {"render_modes": ["human", "rgb_array"]}

    def __init__(self, impl=None, max_episode_steps=MAX_EPISODE_STEPS, **_options):
        if impl is None:
            impl = _FakeFlightgym()
        self.wrapper = impl
        self.num_obs = impl.getObsDim()
        self.num_acts = impl.getActDim()
        self.max_episode_steps = int(max_episode_steps)
        self.observation_space = Box([-math.inf] * self.num_obs, [math.inf] * self.num_obs)
        # flightrl_v2/flightrl_v2/envs/flight_env_vec.py:53-58 (normalized [-1, 1])
        self.action_space = Box([-1.0] * self.num_acts, [1.0] * self.num_acts)
        self._observation = [[0.0] * self.num_obs]
        self._reward = [0.0]
        self._truncated = [False]
        self._extra_info_names = list(impl.getExtraInfoNames())
        self._extra_info = [[0.0] * len(self._extra_info_names)]
        self.episode_rewards = [[]]
        self._episode_lengths = [0]
        self._seed = None
        self._closed = False

    def seed(self, seed=None):
        """Set the backend seed, like ``FlightEnvVec.seed`` (flight_env_vec.py:77-81)."""
        if seed is not None:
            self._seed = int(seed)
            self.wrapper.setSeed(int(seed))

    def reset(self, *, seed=None, options=None):
        """Reset one row; ``options`` is accepted and unused, as upstream (:83-113)."""
        if self._closed:
            raise RuntimeError("the fake FlightEnvVec is closed")
        if seed is not None:
            self.seed(seed)
        self._reward[0] = 0.0
        self._truncated[0] = False
        self._episode_lengths[0] = 0
        self.episode_rewards = [[]]
        self.wrapper.reset(self._observation)
        return list(self._observation[0]), {}

    def step(self, action):
        """Advance one environment step and return the first row, like upstream (:115-186)."""
        if self._closed:
            raise RuntimeError("the fake FlightEnvVec is closed")
        if isinstance(action, (str, bytes)):
            raise ValueError("the action must be a sequence of numbers")
        try:
            values = list(action)
        except TypeError as exc:
            raise ValueError("the action must be a sequence of numbers") from exc
        if values and isinstance(values[0], (list, tuple)):
            # FlightEnvVec accepts a (1, num_acts) row as well as a 1-D action
            # (flight_env_vec.py:131-133); this fake models one row.
            if len(values) != 1:
                raise ValueError("the fake serves one environment row")
            values = list(values[0])
        try:
            flat = [float(value) for value in values]
        except (TypeError, ValueError) as exc:
            raise ValueError("the action must be a sequence of numbers") from exc
        if len(flat) != self.num_acts:
            raise ValueError(f"the action must contain {self.num_acts} values")
        done_array = [False]
        self.wrapper.step([flat], self._observation, self._reward, done_array, self._extra_info)
        self._episode_lengths[0] += 1
        self.episode_rewards[0].append(self._reward[0])
        info = {}
        if self._extra_info_names:
            info["extra_info"] = {
                name: self._extra_info[0][index]
                for index, name in enumerate(self._extra_info_names)
            }
        terminated = bool(done_array[0])
        truncated = self._episode_lengths[0] >= self.max_episode_steps
        if terminated or truncated:
            info["episode"] = {
                "r": sum(self.episode_rewards[0]),
                "l": self._episode_lengths[0],
            }
            self.episode_rewards[0].clear()
            self._episode_lengths[0] = 0
        return (list(self._observation[0]), float(self._reward[0]), terminated, truncated, info)

    def close(self):
        """Close the backend, like ``FlightEnvVec.close`` (:193-196)."""
        self._closed = True
        if hasattr(self, "wrapper"):
            self.wrapper.close()
