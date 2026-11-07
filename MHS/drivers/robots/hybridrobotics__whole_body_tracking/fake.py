"""Fake backend of the G1 tracking driver: a pure Python stand-in for ``gymnasium.make("Tracking-Flat-G1-v0")``.

Why a fake: the acceptance gate runs without Isaac Sim and Isaac Lab (the repository targets Isaac Sim 4.5.0 and
Isaac Lab 2.1.0 on Linux, README.md:3-6), and package code never imports the read-only clone.  The registered
environment class is ``isaaclab.envs:ManagerBasedRLEnv``, which is not in the clone at all; the clone supplies the
``G1FlatEnvCfg`` configuration (the driver's ``native`` symbol).  This module models the contract of one registered
task, ``Tracking-Flat-G1-v0``, without the simulator:

* the action space is a ``Box`` over the robot's actuated joints: the sole action term is a joint-position action over
  ``[".*"]`` (tracking_env_cfg.py:106), and the actuator groups of robots/g1.py:63-134 name four joints per leg, two
  per ankle, three waist joints and seven per arm, which is 29 joints on the two-legged G1.  The clone states no
  action bound, only a unitless action scale (g1.py:184-195), so the bounds here are infinite;
* the observation is the flat concatenation of the eight policy terms of tracking_env_cfg.py:113-133: the motion command
  (reference joint positions and velocities, commands.py:100-110), the anchor position (3), the anchor orientation
  matrix prefix (6), the base linear and angular velocity (3 each), the joint positions, the joint velocities and the
  last action.  The command width follows the joint count, so the stand-in returns 5 * J + 15 values for J = 29;
* ``reset(seed, options)`` accepts the Gymnasium reset signature and returns ``(observation, info)``.  The seed fixes
  the reset draw, whose joint-position range is the command configuration's -0.1 to 0.1 (tracking_env_cfg.py:98);
* ``step(action)`` returns ``(observation, reward, terminated, truncated, info)``.  It integrates a placeholder joint
  motion, returns a zero reward and terminated ``False``, and truncates after the episode length: 10.0 s
  (tracking_env_cfg.py:313) at 4 simulation steps of 0.005 s per control step (tracking_env_cfg.py:312-315) is 500
  control steps.

What this is not: the Isaac Sim environment.  The G1 URDF and the motion NPZ are not in the clone, no reward,
termination or noise term is modelled, the numbers below are test data of this stand-in, and it was never compared
with an upstream run.  The driver's fidelity ``gaps`` list these omissions.  Nothing here talks to a robot.

The public members are limited to the environment interface the bridge reads (``reset``, ``step``, ``close`` and the
two space attributes; gate G7).  The class inherits no upstream base, so the gate reports those as ``MAYBE_ABSENT``
for the Gymnasium environment interface, which an Isaac Lab base outside the clone provides.
"""

import math
import random

#: Number of actuated G1 joints: the actuator joint expressions of robots/g1.py:63-134 expand to four leg joints, two
#: ankle joints, three waist joints and seven arm joints per side of the humanoid, i.e. 29.  placeholder: the URDF
#: that fixes the real joint set is downloaded from GCS (README.md:46-55) and is not in the clone.
JOINT_COUNT = 29

#: The policy group of tracking_env_cfg.py:113-133: command (joint positions and velocities) + anchor position (3) +
#: anchor orientation matrix prefix (6) + base linear velocity (3) + base angular velocity (3) + joint positions +
#: joint velocities + last action = 5 * JOINT_COUNT + 15.  placeholder: upstream returns grouped tensors and the
#: command width comes from the motion NPZ.
OBSERVATION_SIZE = 5 * JOINT_COUNT + 15

#: Simulation step and decimation of TrackingEnvCfg (tracking_env_cfg.py:312-315); one control step is 0.02 s.
PHYSICS_STEP_S = 0.005
DECIMATION = 4
CONTROL_STEP_S = PHYSICS_STEP_S * DECIMATION

#: Episode length (tracking_env_cfg.py:313): 10.0 s / 0.02 s control step = 500 control steps.
MAX_EPISODE_STEPS = int(round(10.0 / CONTROL_STEP_S))

#: The command configuration's joint_position_range (tracking_env_cfg.py:98) bounds the stand-in's reset draw.
RESET_JOINT_RANGE = 0.1

#: placeholder: velocity per unit of action for one fake integration step (the real action is scaled to a joint target
#: by G1_ACTION_SCALE, g1.py:184-195, which this stand-in does not compute).
ACTION_GAIN = 1.0

#: placeholder: the reward of the stand-in; the upstream reward terms are in tracking_env_cfg.py:200-250.
REWARD = 0.0


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None, dtype=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = dtype or "float64"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != self.shape[0]:
            return False
        return all(float(low) <= float(item) <= float(high)
                   for item, low, high in zip(value, self.low, self.high))


class FakeTrackingEnv:
    """A deterministic analytic stand-in with the action and observation contract of Tracking-Flat-G1-v0."""

    def __init__(self, **_options):
        # The two spaces the environment installs; the bridge derives the whole contract from them.  The action
        # bounds are infinite because the clone states no bound, so no envelope limit is derived.
        self.action_space = Box([-math.inf] * JOINT_COUNT, [math.inf] * JOINT_COUNT,
                               (JOINT_COUNT,), "float32")
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE,
                                     (OBSERVATION_SIZE,), "float64")
        self._rng = random.Random(0)                                     # placeholder: the driver's default seed
        self._joint_pos = [0.0] * JOINT_COUNT                            # placeholder
        self._joint_vel = [0.0] * JOINT_COUNT                            # placeholder
        self._last_action = [0.0] * JOINT_COUNT                          # placeholder
        self._tick = 0
        self._start(None)

    def _start(self, seed):
        """Set the stand-in's reset state; ``seed`` fixes the pseudo-random joint draw."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._joint_pos = [self._rng.uniform(-RESET_JOINT_RANGE, RESET_JOINT_RANGE)  # placeholder start noise
                           for _ in range(JOINT_COUNT)]
        self._joint_vel = [0.0] * JOINT_COUNT
        self._last_action = [0.0] * JOINT_COUNT
        self._tick = 0

    def _observation(self):
        """The flat policy vector of tracking_env_cfg.py:113-133; every motion-related term is a placeholder."""
        command = [0.0] * (2 * JOINT_COUNT)                              # placeholder: no motion NPZ is loaded
        anchor_pos = [0.0, 0.0, 0.0]                                     # placeholder
        anchor_ori = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]                      # placeholder: identity rotation prefix
        base_lin_vel = [0.0, 0.0, 0.0]                                   # placeholder
        base_ang_vel = [0.0, 0.0, 0.0]                                   # placeholder
        return (command + anchor_pos + anchor_ori + base_lin_vel + base_ang_vel
                + list(self._joint_pos) + list(self._joint_vel) + list(self._last_action))

    def reset(self, seed=None, options=None):
        """Gymnasium reset: return the initial observation and an empty info object."""
        self._start(seed)
        return self._observation(), {}

    def step(self, action):
        """Apply one action and return the next observation, reward, flags and info."""
        values = list(action)
        if len(values) != JOINT_COUNT:
            raise ValueError(f"Tracking-Flat-G1-v0 takes {JOINT_COUNT} action values, got {len(values)}")
        for index, value in enumerate(values):
            self._joint_vel[index] = ACTION_GAIN * float(value)          # placeholder
            self._joint_pos[index] = self._joint_pos[index] + CONTROL_STEP_S * self._joint_vel[index]  # placeholder
        self._last_action = [float(value) for value in values]
        self._tick += 1
        truncated = self._tick >= MAX_EPISODE_STEPS
        return self._observation(), REWARD, False, truncated, {"tick": self._tick}

    def close(self):
        """Nothing to release: the stand-in holds no file or transport."""
