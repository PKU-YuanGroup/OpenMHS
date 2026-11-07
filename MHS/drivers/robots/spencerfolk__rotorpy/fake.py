"""Fake backend of the RotorPy driver: one unbatched stand-in for ``QuadrotorEnv`` (``cmd_vel`` mode).

Why a fake: the gate never imports the clone and the upstream environment needs numpy, torch, gymnasium and
stable-baselines3, so this package ships a pure-Python environment.  The class the driver names as ``native`` is
``rotorpy.learning.quadrotor_environments:QuadrotorEnv``; the public members below are the ones that class has
(``reset``, ``step``, ``close``; gate G7) and the two space classes duck-type ``gymnasium.spaces.Box`` (the bridge
reads ``low``, ``high``, ``shape`` and ``dtype``).

The fake is deliberately kinematic: it integrates the velocity command of the default ``cmd_vel`` mode and computes
the upstream hover reward.  It does not implement the rigid-body dynamics, rotor thrust, motor model, wind or
aerodynamics; those omissions are the fidelity gaps of ``driver.py``.  The upstream environment also carries a batch
axis (``num_envs``); this fake serves one quadrotor, so the bridge's single-environment contract can describe it.

Numbers here are test data, not device facts; each is marked ``# placeholder``.  Sources for the shape of the
interface and the reward are the upstream lines named in the comments (commit
40b09697a6a1596d404a67f459941d46a39eedd3).  Nothing here talks to a device.
"""

import math
import random

# rotorpy/learning/quadrotor_environments.py:83, :123 (the default sim_rate and t_step)
SIM_RATE_HZ = 100.0                     # placeholder
# rotorpy/learning/quadrotor_environments.py:80 (the default max_time)
MAX_TIME_S = 10.0                       # placeholder
# rotorpy/learning/quadrotor_environments.py:23-25 (the default reset bounds)
POS_BOUND_M = 2.0                       # placeholder
VEL_BOUND_MPS = 0.0                     # placeholder
# rotorpy/learning/quadrotor_environments.py:163 (max_vel = 4/sqrt(4))
MAX_VEL_MPS = 2.0                       # placeholder
# rotorpy/learning/quadrotor_environments.py:170-174 (the default empty world's wbound)
WORLD_BOUND_M = 4.0                     # placeholder
# rotorpy/learning/quadrotor_environments.py:450-454 (the speed and body-rate cutoff)
MAX_SPEED_MPS = 100.0                   # placeholder
MAX_BODY_RATE_RADPS = 100.0             # placeholder
# rotorpy/learning/quadrotor_reward_functions.py:56 (the vec_hover_reward weights)
POSITION_WEIGHT = 1.0                   # placeholder
VELOCITY_WEIGHT = 0.1                   # placeholder
BODY_RATE_WEIGHT = 0.0                  # placeholder
ACTION_WEIGHT = 1e-5                    # placeholder
SURVIVAL_REWARD = 2.0                   # placeholder
OBSERVATION_SIZE = 13                   # placeholder, rotorpy/learning/quadrotor_environments.py:137
COMMAND_VELOCITY_SIZE = 3               # placeholder, rotorpy/learning/quadrotor_environments.py:141
OTHER_CONTROL_SIZE = 4                  # placeholder, rotorpy/learning/quadrotor_environments.py:143


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bounds, shape and dtype the bridge reads."""

    def __init__(self, low, high, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype


def _flat_action(action):
    """The action as a flat list of floats; the bridge sends a list and a caller may send a nested one."""

    raw = action.tolist() if hasattr(action, "tolist") else action
    if isinstance(raw, (list, tuple)) and len(raw) == 1 and isinstance(raw[0], (list, tuple)):
        raw = raw[0]
    return [float(value) for value in raw]


def _norm(values):
    return math.sqrt(sum(value * value for value in values))


class FakeQuadrotorEnv:
    """A single quadrotor with ``reset(seed, options)`` and the legacy ``step(action)`` 4-tuple.

    ``cmd_vel`` is the default control mode of ``QuadrotorEnv`` (quadrotor_environments.py:76): the three action
    values are rescaled from [-1, 1] to [-max_vel, max_vel] and become the instantaneous body velocity.  The fake
    integrates position from it; the quaternion stays identity and the body rate stays zero.
    """

    def __init__(self, **options):
        control_mode = str(options.get("control_mode", "cmd_vel"))
        if control_mode != "cmd_vel":
            raise ValueError("the fake models only the default cmd_vel control mode")
        self.control_mode = control_mode
        self.num_envs = 1                                           # placeholder
        self.sim_rate = float(options.get("sim_rate", SIM_RATE_HZ))
        self.t_step = 1.0 / self.sim_rate
        self.max_time = float(options.get("max_time", MAX_TIME_S))
        self.max_vel = MAX_VEL_MPS
        self.action_space = Box([-1.0] * COMMAND_VELOCITY_SIZE, [1.0] * COMMAND_VELOCITY_SIZE)
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self.reset_options = {
            "initial_states": "random",                             # placeholder
            "pos_bound": POS_BOUND_M,
            "vel_bound": VEL_BOUND_MPS,
        }
        self.t = 0.0                                                # placeholder
        self.reward = 0.0                                           # placeholder
        self.cum_rewards = 0.0                                      # placeholder
        self.vehicle_states = {
            "x": [0.0, 0.0, 0.0],                                   # placeholder
            "v": [0.0, 0.0, 0.0],                                   # placeholder
            "q": [0.0, 0.0, 0.0, 1.0],                              # placeholder
            "w": [0.0, 0.0, 0.0],                                   # placeholder
        }
        self._rng = random.Random()
        self._closed = False

    def _observation(self):
        """``_get_obs``: [x(3), v(3), q(4), w(3)] (quadrotor_environments.py:481-487)."""

        state = self.vehicle_states
        return list(state["x"]) + list(state["v"]) + list(state["q"]) + list(state["w"])

    def reset(self, seed=None, options=None):
        """Reset one quadrotor and return the observation alone (quadrotor_environments.py:262-317)."""

        if seed is not None:
            self._rng.seed(int(seed))
        bounds = dict(self.reset_options)
        if isinstance(options, dict):
            bounds.update(options)
        initial = bounds.get("initial_states", "random")
        state = self.vehicle_states
        if initial == "deterministic":
            state["x"] = [0.0, 0.0, 0.0]                            # placeholder
            state["v"] = [0.0, 0.0, 0.0]                            # placeholder
        elif initial == "random":
            pos_bound = float(bounds.get("pos_bound", POS_BOUND_M))
            vel_bound = float(bounds.get("vel_bound", VEL_BOUND_MPS))
            if pos_bound < 0.0 or vel_bound < 0.0:
                raise ValueError("Bounds must be greater than or equal to 0.")
            state["x"] = [self._rng.uniform(-pos_bound, pos_bound) for _ in range(3)]   # placeholder
            state["v"] = [self._rng.uniform(-vel_bound, vel_bound) for _ in range(3)]   # placeholder
        else:
            raise ValueError(
                "You must either specify 'random', 'deterministic', or provide a dict containing your desired "
                "initial state.")
        state["q"] = [0.0, 0.0, 0.0, 1.0]                           # placeholder
        state["w"] = [0.0, 0.0, 0.0]                                # placeholder
        self.t = 0.0                                                # placeholder
        self.reward = 0.0                                           # placeholder
        self.cum_rewards = 0.0                                      # placeholder
        return self._observation()

    def step(self, action):
        """Advance one tick and return the legacy ``(observation, reward, done, info)`` tuple.

        The done flag folds the upstream out-of-bounds and time checks (quadrotor_environments.py:371 and
        :450-479); the reward is ``vec_hover_reward`` (quadrotor_reward_functions.py:56-74).
        """

        values = _flat_action(action)
        if len(values) != COMMAND_VELOCITY_SIZE:
            raise ValueError("cmd_vel takes three action values")
        # quadrotor_environments.py:34, :440: clip the scaled command to [-max_vel, max_vel]
        command = [
            min(max((value + 1.0) / 2.0 * (2.0 * self.max_vel) - self.max_vel, -self.max_vel), self.max_vel)
            for value in values
        ]
        state = self.vehicle_states
        state["v"] = command
        state["x"] = [position + velocity * self.t_step
                      for position, velocity in zip(state["x"], state["v"])]
        state["q"] = [0.0, 0.0, 0.0, 1.0]                           # placeholder
        state["w"] = [0.0, 0.0, 0.0]                                # placeholder
        self.t += self.t_step
        observation = self._observation()
        out_of_bounds = (
            any(abs(value) > MAX_SPEED_MPS for value in state["v"])
            or any(abs(value) > MAX_BODY_RATE_RADPS for value in state["w"])
            or any(abs(value) > WORLD_BOUND_M for value in state["x"])
        )
        time_done = self.t >= self.max_time
        done = out_of_bounds or time_done
        reward = (
            -POSITION_WEIGHT * _norm(state["x"])
            - VELOCITY_WEIGHT * _norm(state["v"])
            - BODY_RATE_WEIGHT * _norm(state["w"])
            - ACTION_WEIGHT * _norm(values)
            + SURVIVAL_REWARD
        )
        self.reward = reward
        self.cum_rewards += reward
        info = {}
        if done:
            info["terminal_observation"] = observation
            info["TimeLimit.truncated"] = bool(time_done)
        return observation, reward, done, info

    def close(self):
        """Release the fake environment; the upstream method is a no-op (quadrotor_environments.py:208-209)."""

        self._closed = True
