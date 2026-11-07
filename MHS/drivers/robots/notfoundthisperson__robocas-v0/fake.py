"""Fake backend of the RoboCAS driver: a pure Python stand-in for ``TaskBaseEnv``.

Why a fake: the acceptance gate runs without SAPIEN, ManiSkill2, the submodule assets or the clone (package code
never imports the clone), and ``TaskBaseEnv`` constructs a SAPIEN scene, a mobile Franka Panda and a PartNet-Mobility
/ GraspNet scene on open.  This module models only the Gymnasium surface the driver serves: ``reset(seed, options)``,
``step(action)`` and an ``action_space``.  It reads no asset and talks to no device.

The public members are ``reset`` and ``step`` (gate G7 checks them against ``TaskBaseEnv``; ``close`` is omitted
because the pure Python object owns no resource).  ``observation_space`` is omitted because the pinned parent commit
records the ManiSkill2 submodule only as a gitlink, so the gate's class-surface reader cannot see the attribute on
the imported ``BaseEnv``; the bridge derives the observation JSON from the returned values instead.  ``Box``
duck-types ``gym.spaces.Box`` (the bridge reads ``low``, ``high`` and ``shape``).  The action layout and bounds are
those of ``TaskBaseEnv``'s default control mode at commit b7844e975df7b54963b299d2f59ab3283523d708; every constant
cites its line.

What this is not (all listed in the fidelity ``gaps`` of the driver):

* no physics: no SAPIEN rigid-body integration, contacts, inverse kinematics, PartNet-Mobility objects or GraspNet
  grasps.  The fake echoes the commanded base joint positions, end-effector pose and gripper width and derives
  velocities by finite difference;
* the observation is a 22-float surrogate (11 state values plus 11 velocities), not the upstream state observation
  or its image observation;
* the initial end-effector pose and jitter are fake test data, not a device fact;
* the upstream ``TaskBaseEnv.evaluate`` stub reports success on every step; the fake returns ``terminated=True`` to
  mirror it and the driver sets ``autoreset=True`` so the bridge starts the next episode.
"""

import math
import random

# Action layout of the default control mode: base (3), absolute end-effector pose in the arm-base frame (6),
# gripper (2); CombinedController flattens base, arm and gripper action spaces in that order
# (3rd_party/ManiSkill/mani_skill2/agents/base_controller.py:228-235 and
# 3rd_party/ManiSkill/mani_skill2/agents/utils.py:36-64).
# Base joint limits: assets/urdf/mobile_franka_panda.urdf:41 (x), :49 (y) and :57 (rotation z).
# End-effector position: robot_sim/agents/configs/mobile_franka_panda/defaults.py:58-59; rotation: :239 (rot_bound
# np.pi, applied as +/- pi by 3rd_party/ManiSkill/mani_skill2/agents/controllers/pd_ee_pose.py:142-159).
# Gripper: robot_sim/agents/configs/mobile_franka_panda/defaults.py:288-297.
ACTION_LOW = [-0.2, -0.8, -3.1415926, -1.0, -1.0, 0.0, -math.pi, -math.pi, -math.pi, -0.01, -0.01]
ACTION_HIGH = [0.8, 0.8, 1.5707, 1.0, 1.0, 1.5, math.pi, math.pi, math.pi, 0.04, 0.04]

#: One control step at the TaskBaseEnv default control_freq 10 Hz (robot_sim/envs/basic_env.py:31).
TIMESTEP_MS = 100.0
OBSERVATION_SIZE = 22

# placeholder: initial state and jitter of the fake, test data only (the upstream agent init_qpos is at
# robot_sim/agents/configs/mobile_franka_panda/defaults.py:69, but the fake does not simulate the robot or the scene)
INIT_BASE = [0.0, 0.0, 0.0]
INIT_EE_POS = [0.4, 0.0, 0.6]
INIT_EE_ROT = [0.0, 0.0, 0.0]
INIT_GRIPPER = [0.02, 0.02]
EE_POS_JITTER = 0.01


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeTaskBaseEnv:
    """``TaskBaseEnv`` without SAPIEN, ManiSkill2, numpy or assets: ``reset`` and ``step`` return plain Python values."""

    def __init__(self, render_mode=None, control_mode="base_pd_pos_arm_pd_ee_abs_pose_wrt_arm_base", num_objects=5,
                 sim_freq=240, control_freq=10, obj_place_mode="random", rand_rotate_obj_around_z=True,
                 rand_rotate_obj_xy=False, tight_factor=1.0, obj_repeat_num=1, articulation_configs=None,
                 use_room=True, random_background=False, actor_configs=None, **options):
        # The constructor accepts TaskBaseEnv's parameters so the upstream configuration can be passed through; the
        # fake models none of them beyond the two spaces and the control step.
        del options
        self.render_mode = render_mode
        self.control_mode = control_mode
        self.num_objects = num_objects
        self.sim_freq = sim_freq
        self.control_freq = control_freq
        self.obj_place_mode = obj_place_mode
        self.rand_rotate_obj_around_z = rand_rotate_obj_around_z
        self.rand_rotate_obj_xy = rand_rotate_obj_xy
        self.tight_factor = tight_factor
        self.obj_repeat_num = obj_repeat_num
        self.articulation_configs = articulation_configs
        self.use_room = use_room
        self.random_background = random_background
        self.actor_configs = actor_configs
        # TaskBaseEnv.action_space is the agent's flat Box action space (3rd_party/ManiSkill/mani_skill2/envs/
        # sapien_env.py:194 and base_controller.py:228-235).
        self.action_space = Box(ACTION_LOW, ACTION_HIGH)
        # The fake substitutes 22 floats for the upstream state vector and for the image observation of the
        # benchmark configuration.  There is no observation_space member: the gate's class-surface reader cannot
        # follow the gitlink submodule that defines BaseEnv.observation_space.
        self._rng = random.Random()
        self._seed = None
        self._base = list(INIT_BASE)
        self._ee_pos = list(INIT_EE_POS)
        self._ee_rot = list(INIT_EE_ROT)
        self._gripper = list(INIT_GRIPPER)
        self._velocity = [0.0] * 11
        self._elapsed_steps = 0

    # robot_sim/envs/basic_env.py:264-270 delegates to 3rd_party/ManiSkill/mani_skill2/envs/sapien_env.py:472-493,
    # which seeds the episode RNG and returns (observation, info).
    def reset(self, seed=None, options=None):
        if options is not None and not isinstance(options, dict):
            raise ValueError("options must be a mapping")
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
                raise ValueError("seed must be a non-negative integer")
            self._rng = random.Random(seed)
            self._seed = seed
        else:
            self._seed = self._rng.randrange(2 ** 32)
            self._rng = random.Random(self._seed)
        # placeholder: a fresh fake state, not the upstream initial object layout
        self._base = list(INIT_BASE)
        jitter = [self._rng.uniform(-EE_POS_JITTER, EE_POS_JITTER) for _ in range(3)]
        self._ee_pos = [INIT_EE_POS[index] + jitter[index] for index in range(3)]
        self._ee_rot = list(INIT_EE_ROT)
        self._gripper = list(INIT_GRIPPER)
        self._velocity = [0.0] * 11
        self._elapsed_steps = 0
        return self._observation(), {}

    # 3rd_party/ManiSkill/mani_skill2/envs/sapien_env.py:552-560 returns (obs, reward, terminated, False, info);
    # TaskBaseEnv.evaluate returns success True (robot_sim/envs/basic_env.py:322-324) and get_done reads it
    # (sapien_env.py:584-585), so every upstream step terminates.  The reward is 0 because
    # TaskBaseEnv.compute_normalized_dense_reward returns 0 (basic_env.py:326-328).
    def step(self, action):
        try:
            values = [float(item) for item in action]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"action must be an iterable of 11 numbers: {exc}") from exc
        if len(values) != 11:
            raise ValueError(f"action must have 11 elements, got {len(values)}")
        if not all(math.isfinite(item) for item in values):
            raise ValueError("action elements must be finite")
        previous = self._state()
        self._base = values[0:3]
        self._ee_pos = values[3:6]
        self._ee_rot = values[6:9]
        self._gripper = values[9:11]
        current = self._state()
        seconds = TIMESTEP_MS / 1000.0
        self._velocity = [(current[index] - previous[index]) / seconds for index in range(11)]
        self._elapsed_steps += 1
        return self._observation(), 0.0, True, False, {"elapsed_steps": self._elapsed_steps, "success": True}

    def _state(self):
        return list(self._base) + list(self._ee_pos) + list(self._ee_rot) + list(self._gripper)

    def _observation(self):
        return self._state() + list(self._velocity)
