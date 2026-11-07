"""Fake backend of the SoftVTBench Gymnasium driver: a kinematic stand-in for one registered environment.

The upstream environment is ``Isaac-Libero-Franka-IK-v0``.  It is registered with
``entry_point="isaaclab.envs:ManagerBasedRLEnv"`` and ``env_cfg_entry_point=IKLiberoCameraEnvCfg`` in
``SoftVTBench/source/tac_manip/tac_manip/tasks/manipulation/libero/config/franka/__init__.py:32-39``.  Isaac Lab is
an external package (Isaac Sim 4.5 / Isaac Lab 2.1.1, installed separately per README.md:267 and README.md:280-291),
and package code never imports the clone, so this module is the backend the gate can run.  It mirrors the public
Gymnasium environment surface (``action_space``, ``observation_space``, ``reset``, ``step``, ``close``) but it is a
kinematic toy: no Isaac Sim, no rigid-body contacts, no FEM deformables, no cameras and no tactile rendering.

The contract of the real environment is read from the configuration class named by ``native``:

* the arm action is a 6-component differential-IK pose command (``command_type="pose"``, ``scale=1.0``) and the
  default gripper is a binary open/close action (``open_command_expr`` 0.04, ``close_command_expr`` 0.0), seven
  values in total (franka_libero_env_cfg.py:1075-1086 and :496-501);
* the policy observation group has the last action, the end-effector pose, the gripper position and the 7D arm joint
  positions, with ``concatenate_terms = False`` (franka_libero_env_cfg.py:335-347);
* the control step is 1/60 s physics with decimation 3, i.e. 0.05 s (20 Hz), and the default libero_10 episode is
  16.0 s (franka_libero_env_cfg.py:905-909; README.md:67);
* there is no reward manager (``rewards = None``, franka_libero_env_cfg.py:415).

Every number that is a start position or a canned reply is test data and is marked ``# placeholder``.  Structural
dimensions (7 action values, 7 arm joints, 2 gripper fingers) are commented with the configuration line they come
from.  The upstream camera arrays are deliberately not modelled; the driver's fidelity ``gaps`` and RESULT.json say
so.
"""

import math
import random

# franka_libero_env_cfg.py:1075-1086: command_type="pose" -> 6 components; :1097-1103: one binary gripper command.
ARM_ACTION_DIM = 6
GRIPPER_ACTION_DIM = 1
ACTION_DIM = ARM_ACTION_DIM + GRIPPER_ACTION_DIM
# franka_libero_env_cfg.py:343: the policy arm-joint observation is 7D; :341: two finger positions come from gripper_pos.
ARM_JOINT_DIM = 7
GRIPPER_FINGER_DIM = 2
# franka_libero_env_cfg.py:338-343: four policy terms (action, eef pose, gripper position, arm joints).
EEF_POSE_DIM = 7
# franka_libero_env_cfg.py:375 and :386-397: one grasp flag per object of interest; the default libero_10 task 0
# (benchmarks/datasets/libero/config/libero_10.json) lists two.
GRASP_TERMS = 2
# franka_libero_env_cfg.py:905-909: sim.dt = 1/60, decimation = 3, episode_length_s = 16.0 for libero_10.
CONTROL_DT = 3.0 / 60.0
MAX_EPISODE_STEPS = int(16.0 / CONTROL_DT)
# franka_libero_env_cfg.py:496-501: the default binary gripper commands.
GRIPPER_OPEN = 0.04
GRIPPER_CLOSED = 0.0


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element.

    The bridge reads ``low``, ``high`` and ``shape``; the name is how it recognises the space family.
    """

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: named subspaces, as the observation groups and their terms."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _unbounded_box(size):
    """An unbounded Box.

    Isaac Lab builds the environment action space as ``Box(-inf, inf, shape=(action_dim,))`` and this module follows
    it: no file of the clone states a numeric action bound, so the fake invents none.  The observation boxes are
    likewise unbounded; the bridge does not derive limits from them.
    """

    return Box([-math.inf] * size, [math.inf] * size)


def _policy_space():
    # franka_libero_env_cfg.py:338-343: the four policy terms and their dimensions.
    return Dict({
        "actions": _unbounded_box(ACTION_DIM),
        "eef_pose": _unbounded_box(EEF_POSE_DIM),
        "gripper_pos": _unbounded_box(GRIPPER_FINGER_DIM),
        "arm_joint_pos": _unbounded_box(ARM_JOINT_DIM),
    })


def _subtask_space():
    # franka_libero_env_cfg.py:375, :386-397: one grasp term per object of interest (two in the default task).
    return Dict({f"grasp_{index + 1}": _unbounded_box(1) for index in range(GRASP_TERMS)})


class FakeSoftVTEnv:
    """A single-environment kinematic stand-in for ``Isaac-Libero-Franka-IK-v0``.

    ``reset`` and ``step`` return the Gymnasium tuple shapes the bridge consumes.  The arm position integrates the
    first three action values (the pose command); the last value selects the open or close gripper target.  The
    other three pose components, the quaternion and the joint positions stay at their start values because the fake
    models no IK solver and no rigid-body dynamics.
    """

    def __init__(self, **_options):
        self.action_space = _unbounded_box(ACTION_DIM)
        self.observation_space = Dict({"policy": _policy_space(), "subtask_terms": _subtask_space()})
        # The bridge reads dt for the fidelity contract; franka_libero_env_cfg.py:905-909 gives 0.05 s per step.
        self.dt = CONTROL_DT
        self._rng = random.Random(0)
        self._seed = 0
        self._tick = 0
        self._closed = False
        self._reset_state()

    def _reset_state(self):
        # placeholder: the real initial pose comes from the task's JSON regions and the USD robot defaults.
        self._eef_pos = [0.0, 0.0, 0.0]
        self._eef_quat = [1.0, 0.0, 0.0, 0.0]
        self._arm_joint_pos = [0.0] * ARM_JOINT_DIM
        self._last_action = [0.0] * ACTION_DIM
        self._gripper = [GRIPPER_OPEN, -GRIPPER_OPEN]
        self._tick = 0

    def _observation(self):
        return {
            "policy": {
                "actions": list(self._last_action),
                "eef_pose": list(self._eef_pos) + list(self._eef_quat),
                "gripper_pos": list(self._gripper),
                "arm_joint_pos": list(self._arm_joint_pos),
            },
            "subtask_terms": {name: [0.0] for name in (f"grasp_{i + 1}" for i in range(GRASP_TERMS))},
        }

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        self._reset_state()
        return self._observation(), {"seed": self._seed}

    def step(self, action):
        try:
            values = [float(value) for value in action]
        except (TypeError, ValueError) as exc:
            raise ValueError("the action must be a sequence of numbers") from exc
        if len(values) != ACTION_DIM:
            raise ValueError(f"the action has {len(values)} values; this environment takes {ACTION_DIM}")
        self._last_action = values
        for index in range(3):
            self._eef_pos[index] += values[index]
        # franka_libero_env_cfg.py:496-501: a positive binary action opens, the closed command is 0.0.
        target = GRIPPER_OPEN if values[6] > 0.0 else GRIPPER_CLOSED
        self._gripper = [target, -target]
        self._tick += 1
        truncated = self._tick >= MAX_EPISODE_STEPS
        # franka_libero_env_cfg.py:415: rewards = None, so the environment contributes no reward.
        return self._observation(), 0.0, False, truncated, {}

    def close(self):
        self._closed = True
