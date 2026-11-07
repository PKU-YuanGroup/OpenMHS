"""Fake backend of the RoboManipBaselines driver: a pure Python kinematic stand-in for the UR5e cable task.

Why a fake: the upstream package imports ``mujoco``, ``numpy``, ``pin`` and the training stack at module import
(pyproject.toml:25-47), and package code never imports the clone.  This module reproduces the interface of
``robo_manip_baselines.envs.mujoco:MujocoUR5eCableEnv`` (the class the driver names as ``native``): the two spaces,
``reset(seed, options)``, ``step(action)`` and ``close()``, the seven-value actuator action, the fixed start pose of
the cable task and the 32 ms control period.  The public members are the ones the upstream class has or that the
Gymnasium environment interface provides (``reset``, ``step``, ``close``; gate G7), and the two space classes
duck-type ``gymnasium.spaces.Box`` and ``Dict`` (the bridge reads ``low``, ``high``, ``shape`` and ``spaces``).

Every clone constant below cites its line at commit 8535948420f8f9bc979fdb31ed049d1c82b906b2; numbers that are
test data of this fake are marked ``# placeholder``.  The action bounds are the model's actuator ``ctrlrange`` values
(``ur5e_integrated_shared_config.xml:6,11`` and ``ur5e_integrated_specific_config.xml:13``), which gymnasium's
MuJoCo environment uses to build its action Box.  The arm start pose is the one the cable class passes to the base
(``MujocoUR5eCableEnv.py:20-30``).

What this is not: the upstream environment.  It has no rigid-body dynamics, no contacts, no cable or pole geometry,
no actuator or sensor model and no reward geometry; the arm joints approach the commanded positions by a
placeholder fraction of the gap, the normalized gripper value approaches the gripper command, the reward is a
placeholder 0.0, the episode never terminates and the info dictionary is empty.  The observation is a Dict of the
same three shapes as the upstream ``_get_obs`` (``MujocoUR5eEnvBase.py:25-31`` and ``:84-125``).  The camera images
that the upstream info dictionary carries are NOT COVERED.  Nothing here talks to a device.
"""

import math

# MujocoEnvBase.py:12-13: sim_timestep = 0.004 s and frame_skip = 8, so one environment step advances 0.032 s
SIM_TIMESTEP_S = 0.004
FRAME_SKIP = 8
CONTROL_STEP_S = SIM_TIMESTEP_S * FRAME_SKIP

# MujocoUR5eCableEnv.py:20-30: the six arm joint start values; the class appends eight zeros.
INIT_ARM_QPOS = (
    math.pi,
    -math.pi / 2,
    -0.75 * math.pi,
    -0.25 * math.pi,
    math.pi / 2,
    math.pi / 2,
)

# ur5e_integrated_shared_config.xml:6,11 and ur5e_integrated_specific_config.xml:13: actuator ctrlranges.
# The six arm actuators are shoulder_pan, shoulder_lift, elbow, wrist_1, wrist_2 and wrist_3; the last value is
# the gripper tendon actuator.
ACTION_LOW = (-6.2831, -6.2831, -3.1415, -6.2831, -6.2831, -6.2831, 0.0)
ACTION_HIGH = (6.2831, 6.2831, 3.1415, 6.2831, 6.2831, 6.2831, 255.0)

# MujocoUR5eEnvBase.py:25-31: joint_pos and joint_vel have seven values, wrench has six.
ARM_DIM = 6
JOINT_DIM = 7
WRENCH_DIM = 6

# placeholder: the fake has no physics, so each step moves a joint by this fraction of the remaining distance
POSITION_GAIN = 0.1
# placeholder: same idea for the normalized gripper observation
GRIPPER_GAIN = 0.1
# placeholder: the upstream reward depends on cable geometry the fake does not model, so it reports zero
REWARD = 0.0


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: one lower and one upper bound per element."""

    def __init__(self, low, high, shape=None, dtype="float64"):
        if shape is None:
            if isinstance(low, (list, tuple)):
                shape = (len(low),)
            elif isinstance(high, (list, tuple)):
                shape = (len(high),)
            else:
                shape = ()
        self.shape = tuple(int(item) for item in shape)
        count = 1
        for item in self.shape:
            count *= item
        self.low = list(low) if isinstance(low, (list, tuple)) else [low] * count
        self.high = list(high) if isinstance(high, (list, tuple)) else [high] * count
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces`` as a mapping of names to spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeMujocoUR5eCableEnv:
    """The cable task without MuJoCo: the spaces, a fixed start pose and a kinematic step."""

    def __init__(self, **options):
        self._options = dict(options)
        self.action_space = Box(ACTION_LOW, ACTION_HIGH, dtype="float32")
        self.observation_space = Dict(
            {
                "joint_pos": Box([-math.inf] * JOINT_DIM, [math.inf] * JOINT_DIM, dtype="float64"),
                "joint_vel": Box([-math.inf] * JOINT_DIM, [math.inf] * JOINT_DIM, dtype="float64"),
                "wrench": Box([-math.inf] * WRENCH_DIM, [math.inf] * WRENCH_DIM, dtype="float64"),
            }
        )
        self._seed = None
        self._episode = 0
        self._closed = False
        self._joint_pos = self._start_joint_pos()
        # MujocoUR5eEnvBase.py:35 in the clone: setup_robot sets init_qvel to zero, so the start velocities are
        # part of the fixed pose.  (The full path is robo_manip_baselines/envs/mujoco/ur5e/MujocoUR5eEnvBase.py.)
        self._joint_vel = [0.0] * JOINT_DIM
        # placeholder: the fake has no force/torque sensor and does not model the wrench at the start pose
        self._wrench = [0.0] * WRENCH_DIM

    @staticmethod
    def _start_joint_pos():
        # MujocoEnvBase.py:163-165: reset_model restores init_qpos, whose first seven observed values are the six
        # arm angles and a zero normalized gripper value (MujocoUR5eEnvBase.py:112-119).
        return list(INIT_ARM_QPOS) + [0.0]

    def _observation(self):
        return {
            "joint_pos": list(self._joint_pos),
            "joint_vel": list(self._joint_vel),
            "wrench": list(self._wrench),
        }

    def reset(self, *, seed=None, options=None):
        # MujocoEnvBase.py:163-165: the reset restores the fixed start pose; the seed is kept for the receipt only.
        if seed is not None:
            self._seed = int(seed)
        del options
        self._episode += 1
        self._joint_pos = self._start_joint_pos()
        self._joint_vel = [0.0] * JOINT_DIM
        self._wrench = [0.0] * WRENCH_DIM  # placeholder: no force/torque sensor model
        return self._observation(), {}

    def step(self, action):
        values = list(action)
        if len(values) != JOINT_DIM:
            raise ValueError(f"expected {JOINT_DIM} action values, got {len(values)}")
        for index in range(ARM_DIM):
            target = float(values[index])
            delta = POSITION_GAIN * (target - self._joint_pos[index])
            self._joint_pos[index] += delta
            self._joint_vel[index] = delta / CONTROL_STEP_S
        target = float(values[ARM_DIM])
        delta = GRIPPER_GAIN * (target - self._joint_pos[ARM_DIM])
        self._joint_pos[ARM_DIM] += delta
        self._joint_vel[ARM_DIM] = delta / CONTROL_STEP_S
        self._wrench = [0.0] * WRENCH_DIM  # placeholder: no force/torque sensor model
        # MujocoEnvBase.py:82-97: the environment step always reports terminated=False and truncated=False.
        return self._observation(), REWARD, False, False, {}

    def close(self):
        self._closed = True
