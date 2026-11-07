"""Analytic fake backend for the BiGym ``DrawerTopOpen`` task.

This module is a pure-Python stand-in for the environment class named by the driver's ``native``
(``bigym.envs.cupboards:DrawerTopOpen``).  It exists because the upstream package needs MuJoCo, dm_control, mojo and
model assets, and package code never imports the read-only clone.  It is **not** the upstream simulator and not a
recording: it models the task at the level of a drawer progress variable, a floating-base point and the gripper
values, with no contacts, actuators or physics.

The public surface is limited to members that ``BiGymEnv`` and ``DrawerTopOpen`` have (gate G7): ``reset``,
``step``, ``close``, the state properties and the two space attributes.  The action space is a stand-in for the
default H1 ``JointPositionActionMode(floating_base=True, absolute=False)`` configuration; the upstream space is
built from the loaded model at run time (``bigym/action_modes.py:208-232``), so its exact shape and bounds depend on
the constructor arguments.  Numbers below that are not upstream bounds are test data and are marked ``# placeholder``.
"""

import math
import random

# Upstream constants, each cited to the pinned clone (14beb30318ad14c5d6723175c2ee2281129792af).
PHYSICS_DT = 0.002                          # bigym/bigym_env.py:28
MAX_DISTANCE_FROM_ORIGIN = 10.0             # bigym/bigym_env.py:30
SPARSE_REWARD_FACTOR = 1.0                  # bigym/bigym_env.py:31
TOLERANCE = 0.1                             # bigym/envs/cupboards.py:11
RESET_ROBOT_X = -0.2                        # bigym/envs/cupboards.py:17

# Default H1 JointPositionActionMode(floating_base=True, absolute=False) bounds.
# bigym/robots/configs/h1.py:126-127 (floating X/Y and RZ), :145-147 (limb delta),
# bigym/robots/configs/robotiq.py:10 (Robotiq 2F85 range).
FLOATING_LOW = (-0.01, -0.01, -0.05)
FLOATING_HIGH = (0.01, 0.01, 0.05)
LIMB_LOW = (-0.1,) * 10                     # bound h1.py:147; placeholder: 10 arm/wrist actuators
LIMB_HIGH = (0.1,) * 10                     # bound h1.py:147; placeholder: 10 arm/wrist actuators
GRIPPER_LOW = (0.0, 0.0)                    # bigym/robots/configs/robotiq.py:10
GRIPPER_HIGH = (1.0, 1.0)                   # bigym/robots/configs/robotiq.py:10
ACTION_LOW = FLOATING_LOW + LIMB_LOW + GRIPPER_LOW
ACTION_HIGH = FLOATING_HIGH + LIMB_HIGH + GRIPPER_HIGH

# Fake dynamics: test data, not upstream facts.
DRAWER_STEP = 1.0                           # placeholder: drawer progress per unit of mean arm action
DRAWER_COUNT = 3                            # placeholder: the preset enables three drawer joints
PROPRIOCEPTION_LENGTH = 4                   # placeholder: shorter than upstream's len(qpos)+len(qvel)
FLOATING_LENGTH = 3                         # placeholder: the fake's X/Y/yaw float state


class Box:
    """Duck-typed ``gymnasium.spaces.Box`` with flat ``low``/``high`` lists."""

    def __init__(self, low, high, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a mapping of names to spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _observation(pelvis, grippers, accumulated):
    """The default ObservationConfig (no cameras) observation: bigym/bigym_env.py:252-288."""
    return {
        "proprioception": [pelvis[0], pelvis[1], grippers[0], grippers[1]],
        "proprioception_grippers": list(grippers),
        "proprioception_floating_base": list(pelvis),
        "proprioception_floating_base_actions": list(accumulated),
    }


def _observation_space():
    """The space of :func:`_observation`; lengths are fake placeholders."""
    high = [math.inf] * PROPRIOCEPTION_LENGTH
    return Dict({
        "proprioception": Box([-math.inf] * PROPRIOCEPTION_LENGTH, high),
        "proprioception_grippers": Box([0.0, 0.0], [1.0, 1.0]),
        "proprioception_floating_base": Box([-math.inf] * FLOATING_LENGTH, [math.inf] * FLOATING_LENGTH),
        "proprioception_floating_base_actions": Box([-math.inf] * FLOATING_LENGTH, [math.inf] * FLOATING_LENGTH),
    })


class FakeDrawerTopOpen:
    """A pure-Python stand-in for ``bigym.envs.cupboards:DrawerTopOpen``.

    ``reset`` and ``step`` follow the upstream signatures and return shapes.  The dynamics are analytic: the
    floating base is a point integrated by the first three action values, the last drawer moves with the mean arm
    action, and the two gripper values are copied to the gripper state.  Success, failure, reward, termination and
    truncation use the upstream predicates on that fake state.
    """

    def __init__(self, **_options):
        self._rng = random.Random(0)
        self._seed = None
        self._closed = False
        self.action_space = Box(ACTION_LOW, ACTION_HIGH)
        self.observation_space = _observation_space()
        self.reset(seed=0)

    @property
    def action(self):
        """Last action executed (bigym/bigym_env.py:223-226)."""
        return list(self._last_action)

    @property
    def seed(self):
        """Seed of the current episode (bigym/bigym_env.py:143-146)."""
        return self._seed

    @property
    def success(self):
        """Whether the current state satisfies DrawerTopOpen._success (bigym/bigym_env.py:148-151)."""
        return bool(self._success())

    @property
    def fail(self):
        """Whether the pelvis left the 10 m workspace (bigym/bigym_env.py:153-156, 478-492)."""
        return math.hypot(self._pelvis[0], self._pelvis[1]) > MAX_DISTANCE_FROM_ORIGIN

    @property
    def reward(self):
        """Sparse success reward (bigym/bigym_env.py:158-161, 494-496)."""
        return float(self.success) * SPARSE_REWARD_FACTOR

    @property
    def terminate(self):
        """Episode termination: success or failure (bigym/bigym_env.py:163-166)."""
        return bool(self.success or self.fail)

    @property
    def truncate(self):
        """Episode truncation: the simulation health monitor (bigym/bigym_env.py:168-171)."""
        return bool(not self.is_healthy)

    @property
    def is_healthy(self):
        """True while the fake's health flag is set (bigym/bigym_env.py:173-176)."""
        return bool(self._healthy)

    def get_info(self):
        """Info dictionary with the task success flag (bigym/bigym_env.py:326-330)."""
        return {"task_success": float(self.success)}

    def get_observation(self):
        """Current observation (bigym/bigym_env.py:311-320, 332-348)."""
        return _observation(self._pelvis, self._grippers, self._accumulated)

    def get_observation_space(self):
        """Observation space (bigym/bigym_env.py:252-305); fake placeholder lengths."""
        return _observation_space()

    def reset(self, *, seed=None, options=None):
        """Reset the episode and return ``(observation, info)`` (bigym/bigym_env.py:392-406)."""
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        # placeholder: the y/yaw, gripper, accumulated-action, drawer and last-action start values are test data;
        # only RESET_ROBOT_X is an upstream value (bigym/envs/cupboards.py:17).
        self._pelvis = [RESET_ROBOT_X, 0.0, 0.0]
        self._grippers = [0.0, 0.0]
        self._accumulated = [0.0, 0.0, 0.0]
        self._drawers = [0.0] * DRAWER_COUNT
        self._last_action = [0.0] * len(ACTION_LOW)
        self._healthy = True
        self._elapsed_steps = 0
        return self.get_observation(), self.get_info()

    def step(self, action, fast=False):
        """Apply one action and return ``(observation, reward, terminated, truncated, info)``.

        The shape and bounds checks mirror ``BiGymEnv._step_mujoco_simulation`` (bigym/bigym_env.py:449-465).
        """
        if len(action) != len(ACTION_LOW):
            raise ValueError(f"Action shape mismatch: expected {len(ACTION_LOW)} values, got {len(action)}.")
        values = [float(value) for value in action]
        for value, low, high in zip(values, ACTION_LOW, ACTION_HIGH):
            if not math.isfinite(value) or value < low or value > high:
                raise ValueError(f"Action {value} is out of the action space bounds [{low}, {high}].")
        self._elapsed_steps += 1
        self._last_action = values
        self._pelvis = [self._pelvis[0] + values[0], self._pelvis[1] + values[1], self._pelvis[2] + values[2]]
        self._accumulated = [old + delta for old, delta in zip(self._accumulated, values[:3])]
        self._grippers = [values[-2], values[-1]]
        arm = values[3:13]
        if arm:
            self._drawers[-1] = max(0.0, min(1.0, self._drawers[-1] + sum(arm) / len(arm) * DRAWER_STEP))
        if fast:
            return {}, 0, False, False, {}
        return self.get_observation(), self.reward, self.terminate, self.truncate, self.get_info()

    def close(self):
        """Close the environment (bigym/bigym_env.py:498-500)."""
        self._closed = True

    def _success(self):
        """DrawerTopOpen's success predicate on the fake's last drawer (bigym/envs/cupboards.py:37-38)."""
        return abs(self._drawers[-1] - 1.0) <= TOLERANCE
