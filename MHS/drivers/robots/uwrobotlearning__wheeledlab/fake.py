"""Fake backend of the Gymnasium driver: a pure Python, kinematic stand-in for the Isaac-MushrDriftRL-v0 task.

Why a fake: the upstream environment is an Isaac Lab ``ManagerBasedRLEnv`` that needs Isaac Sim 4.5.0, Isaac Lab 2.0.2,
Linux and a GPU (``README.md:7-10``); the gate neither installs nor imports the clone.  This module implements the
Gymnasium members a ``GymnasiumDriver`` needs -- ``action_space``, ``observation_space``, ``reset``, ``step`` and
``close`` -- with the dimensions the upstream configuration names:

* the action is the two components of the Ackermann action term, target velocity then target steering angle
  (``source/wheeledlab/wheeledlab/envs/mdp/actions/ackermann_actions.py:103-105``, ``:136-140``);
* the action scale is (3.0, 0.488) with no reverse and the ``clip`` bounding strategy
  (``source/wheeledlab_tasks/wheeledlab_tasks/common/actions.py:20-22``);
* the observation is the concatenation of root position, root Euler angles, base linear velocity, base angular
  velocity and the last action (``source/wheeledlab_tasks/wheeledlab_tasks/common/observations.py:27-50``); the
  per-term widths come from Isaac Lab helpers outside the clone, so the 14-element layout used here is placeholder
  test data;
* one step is one control period of ``decimation`` 4 physics steps of ``sim.dt`` 0.005 s
  (``source/wheeledlab_tasks/wheeledlab_tasks/drifting/mushr_drift_env_cfg.py:393-394``), and the episode is 5 s
  (``:396``).

The fake is deliberately not the upstream environment: it is a kinematic bicycle with no contacts, tire slip,
actuator, sensor or noise model, it never terminates, its reward is a constant and it models one environment instead
of the upstream's batched ``num_envs``.  The driver's fidelity ``gaps`` list every one of these differences.
Nothing here talks to a device.
"""

import math
import random

# source/wheeledlab_tasks/wheeledlab_tasks/common/actions.py:17-23
BASE_LENGTH = 0.325
BASE_WIDTH = 0.2
WHEEL_RADIUS = 0.05
VELOCITY_SCALE = 3.0
STEERING_SCALE = 0.488
NO_REVERSE = True
# source/wheeledlab_tasks/wheeledlab_tasks/drifting/mushr_drift_env_cfg.py:393-394
PHYSICS_DT = 0.005
DECIMATION = 4
#: One environment step is one control period (decimation physics steps).
CONTROL_DT = PHYSICS_DT * DECIMATION
# source/wheeledlab_tasks/wheeledlab_tasks/drifting/mushr_drift_env_cfg.py:396 (5 s / 0.02 s control period)
EPISODE_STEPS = 250
#: Test data: the fake starts every episode at the origin with a small random yaw.
START_YAW_SPREAD = 0.05
#: Test data: the fake has no reward model and pays this constant.
FAKE_REWARD = 0.0
#: Test data: the observation has the five terms of observations.py:27-50, with 3 + 3 + 3 + 3 + 2 values.
OBSERVATION_SIZE = 14
ACTION_SIZE = 2


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype


class FakeMushrDriftEnv:
    """A kinematic single-environment stand-in for the MuSHR drift task; one action = one control period."""

    def __init__(self, **options):
        if options:
            # The upstream task takes its configuration through the registered env_cfg_entry_point, not through
            # gym.make keyword arguments.  The fake accepts none.
            raise ValueError(f"the fake MuSHR drift environment takes no options, got {sorted(options)}")
        self.action_space = Box([-1.0] * ACTION_SIZE, [1.0] * ACTION_SIZE)
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self._rng = random.Random()
        self._x = 0.0
        self._y = 0.0
        self._yaw = 0.0
        self._velocity = 0.0
        self._yaw_rate = 0.0
        self._throttle = 0.0
        self._steering = 0.0
        self._tick = 0
        self._reset_done = False

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        if options:
            raise ValueError("the fake MuSHR drift environment declares no reset options")
        self._x = 0.0
        self._y = 0.0
        self._yaw = self._rng.uniform(-START_YAW_SPREAD, START_YAW_SPREAD)   # placeholder
        self._velocity = 0.0
        self._yaw_rate = 0.0
        self._throttle = 0.0
        self._steering = 0.0
        self._tick = 0
        self._reset_done = True
        return self._observation(), {}

    def step(self, action):
        if not self._reset_done:
            raise AssertionError("call reset before step")
        if not isinstance(action, (list, tuple)) or len(action) != ACTION_SIZE:
            raise ValueError(f"the action must be a list of {ACTION_SIZE} numbers")
        throttle, steering = float(action[0]), float(action[1])
        if not (math.isfinite(throttle) and math.isfinite(steering)):
            raise ValueError("the action components must be finite")
        # The upstream action term clips to [-1, 1] before scaling (ackermann_actions.py:123-124).
        throttle = max(-1.0, min(1.0, throttle))
        steering = max(-1.0, min(1.0, steering))
        velocity = throttle * VELOCITY_SCALE
        if NO_REVERSE and velocity < 0.0:
            # ackermann_actions.py:132-133 clamps the velocity component when no_reverse is set
            velocity = 0.0
        steering_angle = steering * STEERING_SCALE
        yaw_rate = velocity * math.tan(steering_angle) / BASE_LENGTH
        self._x += velocity * math.cos(self._yaw) * CONTROL_DT
        self._y += velocity * math.sin(self._yaw) * CONTROL_DT
        self._yaw += yaw_rate * CONTROL_DT
        self._velocity = velocity
        self._yaw_rate = yaw_rate
        self._throttle = throttle
        self._steering = steering
        self._tick += 1
        truncated = self._tick >= EPISODE_STEPS
        return self._observation(), FAKE_REWARD, False, truncated, {}

    def close(self):
        self._reset_done = False

    def _observation(self):
        """root_pos_w, root_euler_xyz, base_lin_vel, base_ang_vel, last_action (observations.py:27-50)."""
        return [
            self._x, self._y, 0.0,
            0.0, 0.0, self._yaw,
            self._velocity, 0.0, 0.0,
            0.0, 0.0, self._yaw_rate,
            self._throttle, self._steering,
        ]
