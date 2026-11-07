"""Fake backend of the DexVerse GraspKettle driver: a reduced, pure Python Gymnasium environment.

The upstream environment is ``Dexverse-GraspKettle-v0``, registered to
``GraspKettleEnvFloatingDexHandRightCfg`` (a ``@configclass`` in the clone) and executed by Isaac Lab's
``ManagerBasedRLEnv``.  Isaac Sim, Isaac Lab, a CUDA GPU and the gated USD assets are needed to build it
(README.md:84-101 and :144-146), and package code never imports the clone, so this module is a stand-in for the
fake backend only.  It implements the Gymnasium environment surface the bridge uses (``reset``, ``step`` and
``close``; gate G7) and duck-types ``Box`` and ``Dict`` spaces (the bridge reads ``low``, ``high``, ``shape`` and
``spaces``).

What is modelled from the clone:

* the 28-dimensional action vector: 3 wrist translation joints, 3 wrist rotation joints and 22 Shadow finger
  joints (robot_agents/shadow/floating.py:99-113 and :116-126);
* the action range [-1, 1] per element, the range the zero-action script samples from the action-space shape
  (scripts/zero_agent.py:312-313); the clone does not state Isaac Lab's own action-space bounds, so this is the
  fake's contract and the fidelity ``gaps`` say so;
* the control period: decimation 2 at a 1/120 s simulation step, i.e. 1/60 s per control step
  (tasks/dexverse_base_env_cfg.py:1252 and :1318), with a 20 s episode (tasks/config/functional/base_cfg.py:467),
  so 1200 control steps per episode;
* the ``policy`` (last action), ``proprio`` (joint positions), ``state`` (object pose) and ``goal`` observation
  groups (tasks/dexverse_base_env_cfg.py:728-756; tasks/config/functional/base_cfg.py:204-238);
* the kettle and mug reset ranges for the object and goal positions (tasks/config/functional/grasp_kettle_cfg.py:
  85-87 and :123-124), and the table top at 0.6 m (tasks/dexverse_base_env_cfg.py:36);
* the action L2 and action-rate L2 penalties of the reward configuration (tasks/dexverse_base_env_cfg.py:1011-1012
  and tasks/mdp/rewards.py:44-51).

What is not modelled: rigid-body dynamics, contacts, the hand articulation, the kettle or mug USD assets, the task
success and termination terms, cameras and point clouds, and rendering.  The joint positions follow the commanded
joint targets (Isaac Lab's ``JointPositionActionCfg`` default is target = action * scale + default position, with
scale 1.0 and zero default positions; devices/wrist_origin.py:15-18), and the object pose does not move.  Every one
of these omissions is listed in the fidelity ``gaps`` of driver.py.  Nothing here talks to a device.
"""

import math
import random

#: Number of action values: 3 translation + 3 rotation + 22 Shadow finger joints
#: (source/dexverse/dexverse/robot_agents/shadow/floating.py:99-113 and :116-126).
ACTION_DIM = 28
#: The action range the zero-action script samples before zeroing the vector
#: (scripts/zero_agent.py:312-313); the exact Isaac Lab action-space bounds are not stated in the clone.
ACTION_LOW, ACTION_HIGH = -1.0, 1.0
#: Control period: sim.dt = 1/120 s and decimation = 2 (tasks/dexverse_base_env_cfg.py:1252 and :1318).
CONTROL_DT_S = 1.0 / 60.0
#: episode_length_s = 20.0 s (tasks/config/functional/base_cfg.py:467) / the control period.
MAX_EPISODE_STEPS = 1200
#: Table top (tasks/dexverse_base_env_cfg.py:36) plus the kettle half height
#: (tasks/config/functional/grasp_kettle_cfg.py:77).
TABLE_TOP_Z = 0.6
KETTLE_HALF_HEIGHT = 0.04
#: Pour lift height (tasks/config/functional/grasp_kettle_cfg.py:89).
POUR_LIFT_HEIGHT = 0.15
#: Reward weights (tasks/dexverse_base_env_cfg.py:1011-1012) and the clamp of the kernel (tasks/mdp/rewards.py:44-51).
ACTION_L2_WEIGHT = -0.005
ACTION_RATE_L2_WEIGHT = -0.005
REWARD_CLAMP = 1000.0
#: Reset ranges of the kettle object and the mug goal (tasks/config/functional/grasp_kettle_cfg.py:85-87, :123-124).
KETTLE_X_RANGE = (-0.05, 0.15)
KETTLE_Y_RANGE = (-0.3, -0.1)
KETTLE_YAW_RANGE = (3.14 - 0.3, 3.14 + 0.3)
MUG_X_RANGE = (-0.15, 0.15)
MUG_Y_RANGE = (0.05, 0.3)


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: one low and one high bound per element (the bridge reads them)."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: named sub-spaces (the bridge reads ``spaces``)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeDexVerseGraspKettleEnv:
    """A reduced ``Dexverse-GraspKettle-v0``: ``reset(seed, options)`` and ``step(action)`` as Gymnasium defines them."""

    def __init__(self, **_options):
        # The action vector and its bounds are the driver contract; see ACTION_DIM and ACTION_LOW/ACTION_HIGH.
        self.action_space = Box([ACTION_LOW] * ACTION_DIM, [ACTION_HIGH] * ACTION_DIM)
        self.observation_space = Dict({
            "policy": Box([ACTION_LOW] * ACTION_DIM, [ACTION_HIGH] * ACTION_DIM),
            "proprio": Box([-math.inf] * ACTION_DIM, [math.inf] * ACTION_DIM),
            "state": Box([-math.inf] * 7, [math.inf] * 7),
            "goal": Box([-math.inf] * 3, [math.inf] * 3),
        })
        self._rng = random.Random(0)
        self._last_action = [0.0] * ACTION_DIM
        self._joint_positions = [0.0] * ACTION_DIM
        self._object_pose = [0.0] * 7
        self._goal = [0.0] * 3
        self._elapsed_steps = 0
        self._draw_world()

    def _draw_world(self):
        x = self._rng.uniform(*KETTLE_X_RANGE)
        y = self._rng.uniform(*KETTLE_Y_RANGE)
        yaw = self._rng.uniform(*KETTLE_YAW_RANGE)
        # Object position plus a wxyz quaternion about z (the clone resets yaw; roll and pitch default to zero).
        self._object_pose = [x, y, TABLE_TOP_Z + KETTLE_HALF_HEIGHT,
                             math.cos(yaw / 2.0), 0.0, 0.0, math.sin(yaw / 2.0)]
        self._goal = [self._rng.uniform(*MUG_X_RANGE), self._rng.uniform(*MUG_Y_RANGE),
                      TABLE_TOP_Z + POUR_LIFT_HEIGHT]

    def _observation(self):
        return {
            "policy": list(self._last_action),
            "proprio": list(self._joint_positions),
            "state": list(self._object_pose),
            "goal": list(self._goal),
        }

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        if options is not None and not isinstance(options, dict):
            raise TypeError("options must be a dict")
        self._draw_world()
        self._last_action = [0.0] * ACTION_DIM
        self._joint_positions = [0.0] * ACTION_DIM
        self._elapsed_steps = 0
        return self._observation(), {}

    def step(self, action):
        values = [float(value) for value in action]
        if len(values) != ACTION_DIM:
            raise ValueError(f"the action has {len(values)} values; DexVerse uses {ACTION_DIM}")
        previous = self._last_action
        self._last_action = values
        self._joint_positions = list(values)
        action_l2 = min(sum(value * value for value in values), REWARD_CLAMP)
        rate_l2 = min(sum((value - old) ** 2 for value, old in zip(values, previous)), REWARD_CLAMP)
        reward = ACTION_L2_WEIGHT * action_l2 + ACTION_RATE_L2_WEIGHT * rate_l2
        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        # The upstream task also terminates on success and object-out-of-bound; those terms are not modelled here.
        return self._observation(), reward, False, truncated, {}

    def close(self):
        self._joint_positions = [0.0] * ACTION_DIM
