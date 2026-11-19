"""Fake backend of the TrackerLab G1 23-DoF tracking driver: a pure Python contract stand-in.

The gate cannot import the upstream environment (it needs Isaac Lab, Isaac Sim, torch and a GPU, README.md:58-59),
and package code never imports or runs the clone.  This module therefore implements the public surface the
Gymnasium bridge uses on ``trackerLab.tracker_env:ManagerBasedTrackerEnv``: ``action_space``,
``observation_space``, ``reset``, ``step`` and ``close``.  The upstream class defines ``reset`` and ``step``
(manager_based_tracker_env.py:41 and :35) and inherits the Gymnasium members from Isaac Lab's ``ManagerBasedRLEnv``
outside the clone.

What is taken from the clone, with its line:

* 23 joint actions for the G1 23-DoF tracking task (``motion_align_cfg.py:1-16``);
* the joint-position action scale 0.5 and the processed-action clip -6.0 to 6.0
  (``manager_based_tracker_env_cfg/configs.py:154-159``), approximated with zero default joint offsets;
* 4 physics steps of 0.005 s per environment step, a 20.0 s episode and 1000 environment steps
  (``tracking_env_base.py:40-43`` and ``g1_23d_tracking_env_cfg.py:186``);
* the reset base velocity ranges (``g1_23d_tracking_env_cfg.py:132-137``);
* angular-velocity and joint-velocity observation scales 0.25 and 0.05
  (``g1_23d_tracking_env_cfg.py:174-179``);
* the 100.0 clip on the state observation terms (``manager_based_tracker_env_cfg/configs.py:179-188``);
* the policy observation order and the disabled height scan
  (``manager_based_tracker_env_cfg/configs.py:171-188``, ``tracking_env_base.py:75-78``,
  ``g1_23d_tracking_env_cfg.py:167``).

Everything else is an analytic stand-in, not Isaac Sim physics: the processed joint target is written straight to
the relative joint-position observation, velocity is a finite difference of that target, base velocities stay at
their reset values, commands are zero and the reward is zero.  Those values are test data, marked ``# placeholder``;
none is copied into a Fact, a Limit or the reference.  The raw action space is built by Isaac Lab outside the clone
and was not observed, so the action Box is unbounded; the endpoint requires an operator envelope.  The upstream
environment is vectorised and returns torch tensors; this fake serves one environment with Python lists.

Nothing here talks to a device.
"""

import math
import random

# motion_align_cfg.py:1-16 lists the 23 gym joint names of the G1 23-DoF tracking task.
NUM_JOINTS = 23
# RootVelCommand.command is the motion's root velocity (exbody_command.py:82-104): three components.
NUM_ROOT_VEL = 3
# manager_based_tracker_env_cfg/configs.py:171-188: the policy terms are the dof-position command (23), the
# root-velocity command (3), base linear velocity (3), base angular velocity (3), projected gravity (3), relative
# joint position (23), relative joint velocity (23) and last action (23). height_scan is set to None.
NUM_POLICY_OBS = NUM_JOINTS + NUM_ROOT_VEL + 3 + 3 + 3 + NUM_JOINTS + NUM_JOINTS + NUM_JOINTS
# manager_based_tracker_env_cfg/configs.py:154-159: JointPositionActionCfg scale 0.5 and clip (-6.0, 6.0).
ACTION_SCALE = 0.5
ACTION_CLIP = 6.0
# tracking_env_base.py:40-43: decimation 4 and sim.dt 0.005 s, a 0.02 s environment step.
DECIMATION = 4
SIM_DT_S = 0.005
STEP_DT_S = DECIMATION * SIM_DT_S
# g1_23d_tracking_env_cfg.py:186: episode_length_s = 20.0, so 20.0 / 0.02 = 1000 environment steps.
EPISODE_LENGTH_S = 20.0
MAX_EPISODE_STEPS = int(EPISODE_LENGTH_S / STEP_DT_S)
# manager_based_tracker_env_cfg/configs.py:179-188: the state terms are clipped to (-100, 100).
OBS_CLIP = 100.0
# g1_23d_tracking_env_cfg.py:174-179: the task scales these observation terms.
BASE_ANG_VEL_OBS_SCALE = 0.25
JOINT_VEL_OBS_SCALE = 0.05
# g1_23d_tracking_env_cfg.py:132-137: reset base velocity ranges x/y/z (-1.0, 1.0) and roll/pitch/yaw (-0.5, 0.5).
BASE_LIN_VEL_RANGE = (-1.0, 1.0)
BASE_ANG_VEL_RANGE = (-0.5, 0.5)
# placeholder: independent initial joint velocities; this is not reset_joints_by_scale's default-velocity scaling.
JOINT_VEL_RANGE = (-1.0, 1.0)


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None
        self.dtype = None


class FakeTrackerEnv:
    """A single-environment analytic stand-in for ``ManagerBasedTrackerEnv``.

    The public methods are ``reset``, ``step`` and ``close``: ``reset`` and ``step`` are the upstream class's own
    (manager_based_tracker_env.py:41 and :35); the Gymnasium ``close`` comes from the base outside the clone.  The
    bridge constructs the class without arguments (the upstream constructor takes a cfg, which the fake does not
    receive), so ``__init__`` accepts keyword options and ignores them.
    """

    def __init__(self, **options):
        self.action_space = Box([-math.inf] * NUM_JOINTS, [math.inf] * NUM_JOINTS)
        self.observation_space = Dict({
            "policy": Box([-math.inf] * NUM_POLICY_OBS, [math.inf] * NUM_POLICY_OBS),
        })
        self._options = dict(options)
        self._rng = random.Random()
        self._seed = None
        self._episode = 0
        self._tick = 0
        self._truncated = False
        self._closed = False
        # placeholder: the state before the first reset; the bridge always resets before it steps
        self._dofpos_command = [0.0] * NUM_JOINTS
        self._root_vel_command = [0.0] * NUM_ROOT_VEL
        self._base_lin_vel = [0.0] * 3
        self._base_ang_vel = [0.0] * 3
        self._joint_pos_rel = [0.0] * NUM_JOINTS
        self._joint_vel_rel = [0.0] * NUM_JOINTS
        self._last_action = [0.0] * NUM_JOINTS

    def reset(self, seed=None, options=None):
        """Reset to a seeded analytic start; ``options`` is accepted and ignored (the fake has no scenario)."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        elif self._seed is None:
            # placeholder: a direct caller that supplies no seed gets seed 0; the bridge itself seeds the first
            # reset with 0 when the driver declares no default seed.
            self._seed = 0
            self._rng = random.Random(0)
        # placeholder: the motion command and the default relative joint position are zero; the upstream command
        # manager draws them from the motion buffer.
        self._dofpos_command = [0.0] * NUM_JOINTS
        self._root_vel_command = [0.0] * NUM_ROOT_VEL
        self._joint_pos_rel = [0.0] * NUM_JOINTS
        self._last_action = [0.0] * NUM_JOINTS
        # g1_23d_tracking_env_cfg.py:132-137: the reset samples base velocities in the configured ranges.
        self._base_lin_vel = [self._rng.uniform(*BASE_LIN_VEL_RANGE) for _ in range(3)]
        self._base_ang_vel = [self._rng.uniform(*BASE_ANG_VEL_RANGE) for _ in range(3)]
        # placeholder: independent samples instead of the upstream default-joint-velocity scaling.
        self._joint_vel_rel = [self._rng.uniform(*JOINT_VEL_RANGE) for _ in range(NUM_JOINTS)]
        self._tick = 0
        self._truncated = False
        self._episode += 1
        return self._observation(), {}

    def step(self, action):
        """Apply one action as a joint-position target; returns the Gymnasium five-tuple."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = self._action_values(action)
        # The config states scale and clip, with use_default_offset=True. This fake approximates the
        # default offset as zero and writes the target straight to relative position; no physics runs.
        previous = self._joint_pos_rel
        self._joint_pos_rel = [
            max(-ACTION_CLIP, min(ACTION_CLIP, ACTION_SCALE * value)) for value in values
        ]
        # placeholder: velocity is a finite difference of the analytic target over the 0.02 s control step.
        self._joint_vel_rel = [
            (new - old) / STEP_DT_S for new, old in zip(self._joint_pos_rel, previous)
        ]
        self._last_action = values
        self._tick += 1
        # g1_23d_tracking_env_cfg.py:186 and tracking_env_base.py:40-43: 20.0 s / 0.02 s = 1000 steps.
        # This is the fake's episode budget; Isaac Lab owns its own timeout and in-step reset semantics.
        self._truncated = self._tick >= MAX_EPISODE_STEPS
        # placeholder: the upstream reward terms are not modelled, so the fake reports no reward.
        return self._observation(), 0.0, False, self._truncated, {"tick": self._tick}

    def close(self):
        self._closed = True

    # -- helpers (private: gate G7 does not count them as the fake's public surface) -------------------------------
    def _action_values(self, action):
        values = action.tolist() if hasattr(action, "tolist") else action
        if isinstance(values, dict):
            values = values.get("values")
        if not isinstance(values, (list, tuple)) or len(values) != NUM_JOINTS:
            raise ValueError(f"the action must have {NUM_JOINTS} joint values, got {values!r}")
        out = []
        for value in values:
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"the action contains a non-finite value: {value!r}")
            out.append(number)
        return out

    def _observation(self):
        # manager_based_tracker_env_cfg/configs.py:171-188: the policy order, with the state terms clipped to 100.
        state = [
            *self._base_lin_vel,
            *[value * BASE_ANG_VEL_OBS_SCALE for value in self._base_ang_vel],
            0.0, 0.0, -1.0,                                        # placeholder: upright projected gravity
            *self._joint_pos_rel,
            *[value * JOINT_VEL_OBS_SCALE for value in self._joint_vel_rel],
            *self._last_action,
        ]
        return {
            "policy": [
                *self._dofpos_command,
                *self._root_vel_command,
                *[max(-OBS_CLIP, min(OBS_CLIP, value)) for value in state],
            ]
        }
