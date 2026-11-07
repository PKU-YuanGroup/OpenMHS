"""Fake backend of the gen3 driver: a pure-Python kinematic stand-in for the Gen3-Reach-v0 Isaac Lab task.

Why a fake: the registered environment's entry point is ``isaaclab.envs:ManagerBasedRLEnv``
(source/gen3/gen3/tasks/manager_based/gen3_reach/__init__.py:17), which needs Isaac Sim, Isaac Lab, PhysX and a GPU
(pretrained_models/reach/env.yaml:20 and :78); the acceptance gate has none of them.  The clone registers the task
but imports the simulator classes from packages outside the clone, so the ``fake`` backend re-implements the small
single-environment Gymnasium surface the bridge calls (``reset``, ``step``, ``close``; gate G7 warns that these
come from the Gymnasium interface outside the clone) and models the contract the clone configures:

* the scene robot is the Kinova Gen3 N7 with seven joints and the default joint positions of
  pretrained_models/reach/env.yaml:144-151;
* the reset event ``reset_joints_by_scale`` multiplies those defaults by a factor from 0.75 to 1.25 and leaves the
  joint velocities at zero (env.yaml:352-360);
* the action is a joint-position target over every joint (``joint_names: [.*]``) with ``scale: 0.5`` and
  ``use_default_offset: true`` (env.yaml:339-350, joint_pos_env_cfg.py:39-41);
* one policy step is ``decimation: 2`` physics steps of ``dt: 0.016666666666666666`` s (env.yaml:21 and :76), and an
  episode is 12.0 s (env.yaml:369);
* the policy observation group carries ``joint_pos_rel``, ``joint_vel_rel``, the ``ee_pose`` command and
  ``last_action`` (env.yaml:288-338); the first two add uniform noise in (-0.01, 0.01) (env.yaml:298-315);
* the ``ee_pose`` command is a ``UniformPoseCommand`` resampled every 4.0 s from the ranges recorded in
  env.yaml:508-535 (position x 0.35..0.65, y -0.2..0.2, z 0.15..0.5; roll 0; pitch pi/2; yaw -3.14..3.14).

What this is not: the Isaac Lab task.  The joint positions are set directly to the scaled target on each step; there
is no rigid-body dynamics, actuator effort limit, contact, reward term, forward kinematics or rendering.  The reward is
a constant and only the 12.0 s time-out terminates an episode (env.yaml:490-494).  The upstream also draws the joint
scales, the command and the observation noise from numpy/torch generators; this stand-in uses Python's
``random.Random``, so a seed repeats this fake's own trajectory, not an Isaac Sim trajectory.  Every invented value of
this stand-in (a reset draw, the constant reward, a start state) is marked ``# placeholder``; values copied from the
clone are cited.  The fake was never compared with an Isaac Sim run.

The two space classes duck-type ``gymnasium.spaces.Box`` and ``gymnasium.spaces.Dict``: the bridge reads ``low``,
``high``, ``shape`` and ``spaces``.  Nothing here talks to a device.
"""

import math
import random

# env.yaml:144-151: the scene robot's init_state.joint_pos, in joint order.
JOINT_NAMES = ("joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6", "joint_7")
DEFAULT_JOINT_POS = [0.0, 0.65, 0.0, 1.89, 0.0, 0.6, -1.57]
N_JOINTS = len(JOINT_NAMES)

# env.yaml:347-350: JointPositionAction with joint_names [.*], scale 0.5, offset 0.0, use_default_offset true.
ACTION_SCALE = 0.5

# env.yaml:21 and :76: simulation dt 0.016666666666666666 s, decimation 2.
SIM_DT_S = 0.016666666666666666
DECIMATION = 2
STEP_DT_S = SIM_DT_S * DECIMATION

# env.yaml:369: episode_length_s = 12.0.
EPISODE_LENGTH_S = 12.0
MAX_EPISODE_STEPS = int(round(EPISODE_LENGTH_S / STEP_DT_S))

# env.yaml:352-360: reset_joints_by_scale with position_range (0.75, 1.25) and velocity_range (0.0, 0.0).
RESET_SCALE_LOW = 0.75
RESET_SCALE_HIGH = 1.25
RESET_VELOCITY = 0.0

# env.yaml:298-315: uniform observation noise n_min -0.01, n_max 0.01 on joint_pos and joint_vel.
OBSERVATION_NOISE = 0.01

# env.yaml:508-535: the ee_pose command ranges and its 4.0 s resampling period.
COMMAND_POS_X = (0.35, 0.65)
COMMAND_POS_Y = (-0.2, 0.2)
COMMAND_POS_Z = (0.15, 0.5)
COMMAND_ROLL = (0.0, 0.0)
COMMAND_PITCH = (1.5707963267948966, 1.5707963267948966)
COMMAND_YAW = (-3.14, 3.14)
COMMAND_RESAMPLE_STEPS = int(round(4.0 / STEP_DT_S))

# placeholder: the stand-in's constant reward; the configured reward terms need forward kinematics and are not
# modelled here (env.yaml:370-488).
REWARD = 0.0
INF = math.inf


def _quaternion(roll, pitch, yaw):
    """The wxyz quaternion of a roll-pitch-yaw rotation (a standard conversion, not a value of the clone)."""
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return [
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    ]


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


class FakeGen3ReachEnv:
    """A kinematic standing for the registered ``Gen3-Reach-v0`` environment.

    The bridge calls ``reset``, ``step`` and ``close``; ``action_space`` and ``observation_space`` are the two members
    it reads.  ``reset(seed)`` reseeds a private ``random.Random``, so one seed repeats this fake's own trajectory.
    """

    def __init__(self, **_options):
        # env.yaml:339-350: one joint-position target per joint.  The clone states clip: null and no numeric action
        # bound, so the stand-in publishes an unbounded Box rather than inventing one.
        self.action_space = Box([-INF] * N_JOINTS, [INF] * N_JOINTS, (N_JOINTS,))
        # env.yaml:288-338: the policy group's four terms; each is seven values for the seven joints (the command is
        # position x, y, z plus a wxyz quaternion).
        self.observation_space = Dict({
            "joint_pos": Box([-INF] * N_JOINTS, [INF] * N_JOINTS, (N_JOINTS,)),
            "joint_vel": Box([-INF] * N_JOINTS, [INF] * N_JOINTS, (N_JOINTS,)),
            "pose_command": Box([-INF] * 7, [INF] * 7, (7,)),
            "actions": Box([-INF] * N_JOINTS, [INF] * N_JOINTS, (N_JOINTS,)),
        })
        self._rng = random.Random()
        self._default = list(DEFAULT_JOINT_POS)
        self._joint_pos = list(self._default)
        self._joint_vel = [0.0] * N_JOINTS
        self._last_action = [0.0] * N_JOINTS  # placeholder: no action precedes the first step
        self._command = self._sample_command()
        self._steps = 0
        self._episode = 0
        self._seed = None
        self._closed = False

    def reset(self, *, seed=None, options=None):
        """Start an episode: reseed when a seed is given, scale the default joints and draw a command.

        ``options`` is accepted because the Gymnasium interface passes it; the stand-in uses none.  The clone's reset
        event scales the default joint positions by a factor in (0.75, 1.25) and sets the velocities from (0, 0)
        (env.yaml:352-360).
        """
        del options
        if seed is not None:
            self._seed = int(seed)
            self._rng.seed(self._seed)
        scales = [self._rng.uniform(RESET_SCALE_LOW, RESET_SCALE_HIGH) for _ in range(N_JOINTS)]
        self._joint_pos = [value * scale for value, scale in zip(self._default, scales)]
        self._joint_vel = [RESET_VELOCITY] * N_JOINTS
        self._last_action = [0.0] * N_JOINTS  # placeholder: no action precedes the reset
        self._command = self._sample_command()
        self._steps = 0
        self._episode += 1
        return self._observation(), {}

    def step(self, action):
        """Advance one 30 Hz policy step with the joint-position action and return the five-tuple."""
        values = [float(value) for value in action]
        if len(values) != N_JOINTS:
            raise ValueError(f"the action has {N_JOINTS} values, got {len(values)}")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("the action must be finite")
        # env.yaml:347-350: target = default + 0.5 * action (use_default_offset true, offset 0.0); the stand-in sets
        # the joint position directly instead of driving it through the implicit actuator.
        previous = self._joint_pos
        self._last_action = values
        self._joint_pos = [default + ACTION_SCALE * value for default, value in zip(self._default, values)]
        # placeholder: the stand-in's velocity is the 30 Hz finite difference; there is no actuator model.
        self._joint_vel = [(new - old) / STEP_DT_S for new, old in zip(self._joint_pos, previous)]
        self._steps += 1
        # env.yaml:508-513: UniformPoseCommand resamples every 4.0 s.
        if self._steps % COMMAND_RESAMPLE_STEPS == 0:
            self._command = self._sample_command()
        # env.yaml:369 and :490-494: an episode is 12.0 s and the only termination is the time-out.
        truncated = self._steps >= MAX_EPISODE_STEPS
        return self._observation(), REWARD, False, truncated, {}

    def close(self):
        """Close the stand-in; it holds no external resource."""
        self._closed = True

    def _sample_command(self):
        """A pose command from the recorded ranges (env.yaml:518-535), as position plus a wxyz quaternion."""
        x = self._rng.uniform(*COMMAND_POS_X)
        y = self._rng.uniform(*COMMAND_POS_Y)
        z = self._rng.uniform(*COMMAND_POS_Z)
        roll = self._rng.uniform(*COMMAND_ROLL)
        pitch = self._rng.uniform(*COMMAND_PITCH)
        yaw = self._rng.uniform(*COMMAND_YAW)
        return [x, y, z, *_quaternion(roll, pitch, yaw)]

    def _observation(self):
        """The four policy terms, as a fresh dict; the first two carry the recorded uniform noise."""
        joint_pos = [value - default for value, default in zip(self._joint_pos, self._default)]
        joint_pos = [value + self._rng.uniform(-OBSERVATION_NOISE, OBSERVATION_NOISE) for value in joint_pos]
        joint_vel = [value + self._rng.uniform(-OBSERVATION_NOISE, OBSERVATION_NOISE) for value in self._joint_vel]
        return {
            "joint_pos": joint_pos,
            "joint_vel": joint_vel,
            "pose_command": list(self._command),
            "actions": list(self._last_action),
        }
