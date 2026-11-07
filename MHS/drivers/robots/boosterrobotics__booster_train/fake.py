"""Fake backend of the Booster T1 tracking driver: a pure Python stand-in for the registered Gymnasium task.

Why a fake: the acceptance gate runs without Isaac Sim, Isaac Lab and booster_assets (README.md:5-7 and :19-21), and
package code never imports the read-only clone.  The registered environment class is
``isaaclab.envs:ManagerBasedRLEnv``, which is not in the clone at all; the clone supplies the
``RoughWoStateEstimationEnvCfg`` configuration (the driver's ``native`` symbol).  This module models the contract of
the registered task ``Booster-T1-MotionTracking-v0`` without the simulator:

* the action space is a ``Box`` over the T1's actuated joints.  The sole action term is a joint-position action over
  ``[".*"]`` (tracking_env_cfg.py:107), and the T1 motion joint order lists 23 joints
  (assets/robots/motion_joint_names.py:28-52); the robot description is the external ``T1_23dof.urdf``
  (assets/robots/booster_t1.py:25).  The clone states no action bound, only a unitless action scale
  (assets/robots/booster_t1.py:128-168), so the bounds here are infinite;
* the policy observation is the flat concatenation of the configured terms (tracking_env_cfg.py:119-134) after the
  T1 rough configuration disables ``motion_anchor_pos_b`` and ``base_lin_vel`` (env_cfg.py:42-46): the motion command
  (reference joint positions and velocities, commands.py:137-139), the motion anchor orientation matrix prefix (6
  values), base angular velocity (3), the joint positions (23), the joint velocities (23) and the last action (23),
  which is 5 * 23 + 9 = 124 values;
* ``reset(seed, options)`` accepts the Gymnasium reset signature and returns ``(observation, info)``.  The seed fixes
  the reset draw, whose joint-position range is the command configuration's -0.1 to 0.1
  (tracking_env_cfg.py:99);
* ``step(action)`` returns ``(observation, reward, terminated, truncated, info)``.  It integrates a placeholder joint
  motion, returns a zero reward and terminated ``False``, and truncates after the episode length: 10.0 s
  (tracking_env_cfg.py:326) at 4 simulation steps of 0.005 s per control step (tracking_env_cfg.py:325-328) is 500
  control steps.

What this is not: the Isaac Sim environment.  The T1 URDF and the motion NPZ are not in the clone, no reward,
termination or noise term is modelled, the numbers below are test data of this stand-in, and it was never compared
with an upstream run.  The driver's fidelity ``gaps`` list these omissions.  Nothing here talks to a robot.

The public members are limited to the environment interface the bridge reads (``reset``, ``step``, ``close`` and the
two space attributes; gate G7).  The class inherits no upstream base, so the gate reports those as ``MAYBE_ABSENT``
for the Gymnasium environment interface, which an Isaac Lab base outside the clone provides.
"""

import math
import random

#: Number of actuated T1 joints: the T1 motion joint order of assets/robots/motion_joint_names.py:28-52 lists 23
#: names, and the robot description is T1_23dof.urdf (assets/robots/booster_t1.py:25).  The URDF itself is in the
#: external booster_assets repository and is not in the clone.
JOINT_COUNT = 23

#: The active policy terms of tracking_env_cfg.py:119-134 after env_cfg.py:42-46 disables motion_anchor_pos_b and
#: base_lin_vel: command (2 * J) + anchor orientation prefix (6) + base angular velocity (3) + joint positions (J) +
#: joint velocities (J) + last action (J) = 5 * J + 9.  placeholder: the command width follows the motion NPZ, which
#: is not in the clone, and upstream returns grouped tensors.
OBSERVATION_SIZE = 5 * JOINT_COUNT + 9

#: Simulation step and decimation of TrackingEnvCfg (tracking_env_cfg.py:325-328); one control step is 0.02 s.
PHYSICS_STEP_S = 0.005
DECIMATION = 4
CONTROL_STEP_S = PHYSICS_STEP_S * DECIMATION

#: Episode length (tracking_env_cfg.py:326): 10.0 s / 0.02 s control step = 500 control steps.
MAX_EPISODE_STEPS = int(round(10.0 / CONTROL_STEP_S))

#: The command configuration's joint_position_range (tracking_env_cfg.py:99) bounds the stand-in's reset draw.
RESET_JOINT_RANGE = 0.1

#: placeholder: velocity per unit of action for one fake integration step (the real action is scaled to a joint target
#: by the T1_ACTION_SCALE of assets/robots/booster_t1.py:128-168, which this stand-in does not compute).
ACTION_GAIN = 1.0

#: placeholder: the reward of the stand-in; the upstream reward terms are in tracking_env_cfg.py:200-260.
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


class FakeT1TrackingEnv:
    """A deterministic analytic stand-in with the action and observation contract of the T1 tracking task."""

    def __init__(self, **_options):
        # The two spaces the environment installs; the bridge derives the whole contract from them.  The action
        # bounds are infinite because the clone states no bound, so no envelope limit is derived.
        self.action_space = Box([-math.inf] * JOINT_COUNT, [math.inf] * JOINT_COUNT,
                                (JOINT_COUNT,), "float32")
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE,
                                     (OBSERVATION_SIZE,), "float64")
        self._rng = random.Random(0)                                     # placeholder: default seed
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
        """The flat policy vector of tracking_env_cfg.py:119-134; every motion-related term is a placeholder."""
        command = [0.0] * (2 * JOINT_COUNT)                              # placeholder: no motion NPZ is loaded
        anchor_ori = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]                      # placeholder: identity matrix first columns
        base_ang_vel = [0.0, 0.0, 0.0]                                   # placeholder
        return (command + anchor_ori + base_ang_vel
                + list(self._joint_pos) + list(self._joint_vel) + list(self._last_action))

    def reset(self, seed=None, options=None):
        """Gymnasium reset: return the initial observation and an empty info object."""
        self._start(seed)
        return self._observation(), {}

    def step(self, action):
        """Apply one action and return the next observation, reward, flags and info."""
        values = list(action)
        if len(values) != JOINT_COUNT:
            raise ValueError(f"Booster-T1-MotionTracking-v0 takes {JOINT_COUNT} action values, got {len(values)}")
        for index, value in enumerate(values):
            self._joint_vel[index] = ACTION_GAIN * float(value)          # placeholder
            self._joint_pos[index] = self._joint_pos[index] + CONTROL_STEP_S * self._joint_vel[index]  # placeholder
        self._last_action = [float(value) for value in values]
        self._tick += 1
        truncated = self._tick >= MAX_EPISODE_STEPS
        return self._observation(), REWARD, False, truncated, {"tick": self._tick}

    def close(self):
        """Nothing to release: the stand-in holds no file or transport."""
