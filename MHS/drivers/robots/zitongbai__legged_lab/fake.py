"""Fake backend of the legged_lab driver: a pure-Python kinematic stand-in for the Isaac Lab G1 AMP task.

Why a fake: the gate cannot import the upstream environment.  ``ManagerBasedAmpEnv`` reaches Isaac Lab's
``ManagerBasedRLEnv`` (manager_based_animation_env.py:6 and :13) and builds a PhysX scene, and the acceptance
environment has no Isaac Sim 5.1.0, Isaac Lab 2.3.2, torch or GPU (README.md:3-4 and :64).  This module implements
the single-environment Gymnasium interface the bridge calls (``reset``, ``step``, ``close``; gate G7 warns that these
come from the Gymnasium base outside the clone) and models the contract the clone configures:

* the action is a joint-position target for every G1 joint, scaled by 0.25 on top of the default offsets
  (amp_env_cfg.py:92);
* the 29 joints are the G1 asset's ``joint_sdk_names`` (unitree.py:167-197) and the default offsets are the asset's
  ``init_state.joint_pos`` (unitree.py:94-105);
* one policy step is 4 physics steps of 0.005 s, i.e. 0.02 s, and an episode is 20.0 s, i.e. 1000 steps
  (amp_env_cfg.py:394-397);
* the observation is the policy group's ``joint_pos`` term.  The configured group also carries base_ang_vel,
  root_local_rot_tan_norm, velocity_commands, joint_vel and actions, with a five-step history
  (amp_env_cfg.py:113-129); their widths are computed by Isaac Lab outside the clone and are not reproduced here.

What this is not: the upstream task.  There is no rigid-body dynamics, contact, actuator, sensor, terrain, motion
data, reward or rendering model.  The reward is a constant, only the 20 s time-out truncates an episode, and the
base-height and bad-orientation terminations (amp_env_cfg.py:313-323) are not modelled.  The upstream reset samples a
reference motion (g1_amp_env_cfg.py:200, amp_env_cfg.py:359-361); this fake draws a small joint offset from Python's
``random.Random`` instead.  Every number that is this fake's test data rather than a value from the clone is marked
``# placeholder``, and the fake was never compared with an Isaac Sim run.

The two space classes duck-type ``gymnasium.spaces.Box`` and ``gymnasium.spaces.Dict``: the bridge reads ``low``,
``high``, ``shape`` and ``spaces``.  Nothing here talks to a device.
"""

import math
import random

# unitree.py:167-197: the 29 joint_sdk_names of UNITREE_G1_29DOF_CFG, in the order the asset lists them.
JOINT_NAMES = (
    "left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint", "left_knee_joint",
    "left_ankle_pitch_joint", "left_ankle_roll_joint",
    "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint", "right_knee_joint",
    "right_ankle_pitch_joint", "right_ankle_roll_joint",
    "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint",
    "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_elbow_joint",
    "left_wrist_roll_joint", "left_wrist_pitch_joint", "left_wrist_yaw_joint",
    "right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint", "right_elbow_joint",
    "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint",
)
N_JOINTS = len(JOINT_NAMES)

# amp_env_cfg.py:92: JointPositionActionCfg(joint_names=[".*"], scale=0.25, use_default_offset=True).
ACTION_SCALE = 0.25
# amp_env_cfg.py:394 and :397: decimation 4 with sim.dt 0.005 s, so one policy step is 0.02 s.
DECIMATION = 4
SIM_DT_S = 0.005
STEP_DT_S = DECIMATION * SIM_DT_S
# amp_env_cfg.py:395: episode_length_s = 20.0.
EPISODE_LENGTH_S = 20.0
MAX_EPISODE_STEPS = int(round(EPISODE_LENGTH_S / STEP_DT_S))

# unitree.py:94-105: the init_state.joint_pos patterns, applied to the names above; unnamed joints keep 0.0.
_DEFAULT_PATTERNS = (
    ("left_hip_pitch_joint", -0.1),
    ("right_hip_pitch_joint", -0.1),
    ("*_knee_joint", 0.3),
    ("*_ankle_pitch_joint", -0.2),
    ("*_shoulder_pitch_joint", 0.3),
    ("left_shoulder_roll_joint", 0.25),
    ("right_shoulder_roll_joint", -0.25),
    ("*_elbow_joint", 0.97),
    ("left_wrist_roll_joint", 0.15),
    ("right_wrist_roll_joint", -0.15),
)


def _matches(name, pattern):
    """True when ``name`` matches a joint pattern: an exact name or a ``*`` prefix/suffix pattern."""
    if pattern.startswith("*"):
        return name.endswith(pattern[1:])
    return name == pattern


def _default_joint_positions():
    """The default joint offsets of unitree.py:94-105 for the 29 joints; unnamed joints are 0.0."""
    values = []
    for name in JOINT_NAMES:
        value = 0.0
        for pattern, offset in _DEFAULT_PATTERNS:
            if _matches(name, pattern):
                value = offset
                break
        values.append(value)
    return values


# placeholder: the reset spread of this stand-in; the upstream reset draws a reference motion (g1_amp_env_cfg.py:200).
RESET_JOINT_SPREAD = 0.02
# placeholder: the constant reward of the stand-in; the real reward is the sum of the configured MDP terms.
REWARD = 0.0
INF = math.inf


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a low and a high bound per element."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeLeggedLabAmpEnv:
    """A kinematic standing for ``legged_lab.envs:ManagerBasedAmpEnv``.

    The bridge calls ``reset``, ``step`` and ``close``; the action and observation spaces are the two members it
    reads.  ``reset`` reseeds a private ``random.Random`` so ``reset(seed)`` repeats this fake's own trajectory.
    """

    def __init__(self, **_options):
        # amp_env_cfg.py:92: one joint-position target per joint; the clone states no numeric action bound, so the
        # stand-in publishes the unbounded Box that an unconstrained Isaac Lab action term exposes.
        self.action_space = Box([-INF] * N_JOINTS, [INF] * N_JOINTS, (N_JOINTS,))
        # amp_env_cfg.py:132: the observation group named policy; the fake carries its joint_pos term only.
        self.observation_space = Dict({"policy": Box([-INF] * N_JOINTS, [INF] * N_JOINTS, (N_JOINTS,))})
        self._rng = random.Random()
        self._default = _default_joint_positions()
        self._joint_pos = list(self._default)
        self._joint_vel = [0.0] * N_JOINTS  # placeholder: kept for the stand-in only, not observed
        self._last_action = [0.0] * N_JOINTS  # placeholder: no action precedes the first step
        self._steps = 0
        self._episode = 0
        self._seed = None
        self._closed = False

    def reset(self, *, seed=None, options=None):
        """Start an episode: reseed when a seed is given and draw the stand-in's joint offsets.

        ``options`` is accepted because the Gymnasium interface passes it; the stand-in uses none.  The upstream
        reset instead samples a reference motion (g1_amp_env_cfg.py:200, amp_env_cfg.py:359-361).
        """
        del options
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        # placeholder: the stand-in starts around the default joint positions with a small random offset.
        self._joint_pos = [value + self._rng.uniform(-RESET_JOINT_SPREAD, RESET_JOINT_SPREAD)
                           for value in self._default]
        self._joint_vel = [0.0] * N_JOINTS  # placeholder: the stand-in starts at rest
        self._last_action = [0.0] * N_JOINTS  # placeholder: no action precedes the reset
        self._steps = 0
        self._episode += 1
        return self._observation(), {}

    def step(self, action):
        """Advance one 20 ms policy step with the joint-position action and return the five-tuple."""
        values = [float(value) for value in action]
        if len(values) != N_JOINTS:
            raise ValueError(f"the action has {N_JOINTS} values, got {len(values)}")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("the action must be finite")
        # amp_env_cfg.py:92: target = default + 0.25 * action (use_default_offset=True); the stand-in observes the
        # absolute joint positions, and the joint order is the asset's joint_sdk_names order.
        self._last_action = values
        previous = self._joint_pos
        self._joint_pos = [default + ACTION_SCALE * value for default, value in zip(self._default, values)]
        # placeholder: the stand-in's joint velocity is the 20 ms finite difference; no actuator model.
        self._joint_vel = [(new - old) / STEP_DT_S for new, old in zip(self._joint_pos, previous)]
        self._steps += 1
        # amp_env_cfg.py:395: the episode is 20.0 s; only the time-out is modelled (the physical terminations of
        # amp_env_cfg.py:313-323 are not).
        truncated = self._steps >= MAX_EPISODE_STEPS
        return self._observation(), REWARD, False, truncated, {}

    def close(self):
        """Close the stand-in; it holds no external resource."""
        self._closed = True

    def _observation(self):
        """The joint_pos term of the policy group (amp_env_cfg.py:116), as a fresh list."""
        return {"policy": list(self._joint_pos)}
