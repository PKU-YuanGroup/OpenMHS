"""Fake backend of the gym-agx driver: a pure Python stand-in for ``gym_agx.envs:BendWireEnv``.

Why a fake: the upstream package imports AGX Dynamics (``agx``, ``agxPython``, ``agxSDK``, ...) at module import and
raises ``DependencyNotInstalled`` without a licensed installation (``gym_agx/envs/agx_env.py:9-20``); package code
never imports the clone.  This module reproduces the environment interface the bridge uses -- ``action_space``,
``observation_space``, ``dt``, ``reset``, ``step`` and ``close`` (gate G7 checks those names against the upstream
class) -- on a small analytic surrogate.  The bridge's space classes are duck-typed by class name: ``Box`` for the
action space and ``Dict``/``Box`` for the nested observation space.

What this is not: AGX Dynamics.  The cable, contacts, plasticity and solver are not modelled, the curvature array is
shorter than the device's, and the start and goal numbers below are test data marked ``# placeholder``.  The control
law is the upstream one: the action is a velocity command in m/s, the speed change per call is bounded by
``max_acceleration*dt`` and the speed by ``max_velocity`` (``gym_agx/rl/end_effector.py:164-192``).
"""

import math
import random

# gym_agx/sims/bend_wire.py:34-35 (the scene builder's simulation parameters)
N_SUBSTEPS = 2
TIMESTEP = 1 / 100                                   # seconds; 100 Hz
DT = TIMESTEP * N_SUBSTEPS                           # gym_agx/envs/agx_goal_env.py:149-151
# gym_agx/__init__.py:34 (max_episode_steps of BendWire-v0)
MAX_EPISODE_STEPS = 1000
# gym_agx/envs/agx_goal_env.py:142 (Box(-1, 1) action space)
ACTION_LOW, ACTION_HIGH = -1.0, 1.0
# gym_agx/envs/explicit/bend_wire_env.py:79-80 (default gripper_right limits)
MAX_VELOCITY = 10 / 1000                             # m/s
MAX_ACCELERATION = 10 / 1000                         # m/s^2
# gym_agx/envs/explicit/bend_wire_env.py:113 (RewardConfig)
REWARD_LOW, REWARD_HIGH = -1.5, 1.5
# gym_agx/envs/explicit/bend_wire_env.py:114
CURVATURE_THRESHOLD = 0.05
# gym_agx/envs/explicit/bend_wire_env.py:34
VELOCITY_SCALE = 100

# The rest are test data of this surrogate, not facts about the device.
N_ACTIONS = 3                                        # placeholder, the default gripper's three translations
CURVATURE_LENGTH = 8                                 # placeholder, the real cable has many more segments
START_POSITION = (0.0, 0.0, 0.0)                     # placeholder
START_JITTER = 0.0005                                # placeholder, metres; makes reset(seed) observable
CURVATURE_BASE = 0.0                                 # placeholder, 1/m
CURVATURE_GAIN = 10.0                                # placeholder, 1/m per metre
GOAL_CURVATURE = tuple([0.2] + [0.0] * (CURVATURE_LENGTH - 1))   # placeholder, 1/m
GOAL_EE_VELOCITY = (0.0, 0.0, 0.0)                   # placeholder, m/s


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype

    def contains(self, value):
        return isinstance(value, (list, tuple)) and len(value) == len(self.low) and all(
            self.low[index] <= float(item) <= self.high[index] for index, item in enumerate(value))


class Dict:
    """Duck-typed ``gym.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None
        self.dtype = None


def _curvature_box():
    return Box([-math.inf] * CURVATURE_LENGTH, [math.inf] * CURVATURE_LENGTH, (CURVATURE_LENGTH,))


def _vector_box():
    return Box([-math.inf] * N_ACTIONS, [math.inf] * N_ACTIONS, (N_ACTIONS,))


class FakeBendWireEnv:
    """BendWire-v0 without AGX Dynamics: ``reset(seed, options)`` and the legacy four-value ``step(action)``."""

    def __init__(self, **options):
        # options is accepted so the backend can be built with the family's keyword arguments; none are used.
        self.action_space = Box([ACTION_LOW] * N_ACTIONS, [ACTION_HIGH] * N_ACTIONS, (N_ACTIONS,))
        goal_space = Dict({"dlo_curvature": _curvature_box(), "ee_velocity": Dict({"gripper_right": _vector_box()})})
        observation_space = Dict({"dlo_curvature": _curvature_box(),
                                  "ee_position": Dict({"gripper_right": _vector_box()})})
        self.observation_space = Dict({"desired_goal": goal_space, "achieved_goal": goal_space,
                                       "observation": observation_space})
        self._rng = random.Random()
        self._position = list(START_POSITION)
        self._velocity = [0.0] * N_ACTIONS
        self._curvature = self._curvature_at(self._position)
        self._goal = list(GOAL_CURVATURE)
        self._tick = 0
        self._done = False
        self._closed = False

    @property
    def dt(self):
        """The action time step: ``sim.getTimeStep() * n_substeps`` (gym_agx/envs/agx_goal_env.py:149-151)."""
        return DT

    def _curvature_at(self, position):
        return [CURVATURE_BASE + CURVATURE_GAIN * position[0] for _ in range(CURVATURE_LENGTH)]

    def _distance(self):
        return math.sqrt(sum((achieved - desired) ** 2 for achieved, desired in zip(self._curvature, self._goal)))

    def _is_success(self):
        return bool(self._distance() < CURVATURE_THRESHOLD)

    def _reward(self):
        distance = self._distance()
        if distance < CURVATURE_THRESHOLD:
            speed = math.sqrt(sum(value * value for value in self._velocity))
            reward = REWARD_HIGH - VELOCITY_SCALE * speed
        else:
            reward = -distance
        return round(min(REWARD_HIGH, max(REWARD_LOW, reward)), 4)

    def _observation(self):
        return {
            "observation": {
                "dlo_curvature": list(self._curvature),
                "ee_position": {"gripper_right": list(self._position)},
            },
            "achieved_goal": {
                "dlo_curvature": list(self._curvature),
                "ee_velocity": {"gripper_right": list(self._velocity)},
            },
            "desired_goal": {
                "dlo_curvature": list(self._goal),
                "ee_velocity": {"gripper_right": list(GOAL_EE_VELOCITY)},
            },
        }

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng.seed(int(seed))
        jitter = [self._rng.uniform(-START_JITTER, START_JITTER) for _ in range(N_ACTIONS)]
        self._position = [START_POSITION[index] + jitter[index] for index in range(N_ACTIONS)]
        self._velocity = [0.0] * N_ACTIONS
        self._curvature = self._curvature_at(self._position)
        self._goal = list(GOAL_CURVATURE)
        self._tick = 0
        self._done = False
        self._closed = False
        return self._observation()

    def step(self, action):
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} is not in the action space")
        for index in range(N_ACTIONS):
            target = min(MAX_VELOCITY, max(-MAX_VELOCITY, float(action[index])))
            current = self._velocity[index]
            if abs((target - current) / DT) > MAX_ACCELERATION:
                current = current + math.copysign(MAX_ACCELERATION * DT, target - current)
            if abs(current) > MAX_VELOCITY:
                current = math.copysign(MAX_VELOCITY, current)
            self._velocity[index] = current
        for index in range(N_ACTIONS):
            self._position[index] = self._position[index] + self._velocity[index] * DT
        self._curvature = self._curvature_at(self._position)
        self._tick += 1
        done = self._tick >= MAX_EPISODE_STEPS
        self._done = done
        info = {"gripper_right": list(self._velocity), "is_success": self._is_success(),
                "distance": self._distance()}
        return self._observation(), self._reward(), done, info

    def close(self):
        self._closed = True
