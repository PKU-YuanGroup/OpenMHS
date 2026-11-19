"""Fake backend of the learn2walk Gymnasium driver: an analytic stand-in for ``MimicWalker3dEnv``.

Why an analytic stand-in: the acceptance gate runs without gym, mujoco-py or MuJoCo, and package code never imports
the clone.  The upstream environment also cannot be constructed at the pinned commit: the package initializer
imports a missing ``mimic_walker2d`` module, the configured model ``walker3d_flat_feet_lowmass.xml`` is not in the
assets directory, and the reference-trajectory loader uses hard-coded absolute paths outside the clone.  This module
therefore serves the environment-step interface with a deterministic phase-driven walker and marks every invented
value as a placeholder (they are test data, never facts).

What this is not: MuJoCo or the upstream imitation environment.  There are no rigid-body dynamics, contacts,
friction, actuators, sensors or noise; the action perturbs a synthetic reference gait, the reward is an analytic
imitation-like score, and no trajectory was compared with an upstream run.  The differences are listed in the
``fidelity`` gaps of driver.py and in RESULT.json.

The public members are the environment interface the bridge uses: ``reset``, ``step`` and ``close``.  The constants
that are real upstream configuration are cited by line; everything invented says ``# placeholder``.
"""

import math
import random

# scripts/config_light.py:8,10 (maximum walking distance and episode length)
MAX_WALKING_DISTANCE = 10.0
MAX_EPISODE_STEPS = 3000
# scripts/config_light.py:30,32 and mujoco/gym_mimic_envs/mimic_env.py:184-189: 1000 Hz / 200 Hz = 5 substeps of 1 ms
CONTROL_STEP_S = 0.005
# placeholder envelope borrowed from walker3d_flat_feet.xml:8, not the missing configured lowmass model's space.
CTRL_LOW, CTRL_HIGH = -300.0, 300.0
# scripts/common/config.py:29-33 with scripts/config_light.py:36: peak torques repeated for both sides
PEAK_TORQUES = [50.0, 50.0, 50.0, 5.0, 50.0, 50.0, 50.0, 5.0]
# scripts/common/config.py:128,146: pose 0.8, velocity 0.2, COM 0, power 0; alive bonus 0.2
REWARD_WEIGHTS = (0.8, 0.2, 0.0, 0.0)
ALIVE_BONUS = 0.2
# assets/ref_trajecs/mocaps_readme.md:3: the constant-speed mocap is 1.5 m/s
DESIRED_WALKING_SPEED = 1.5
# mujoco/gym_mimic_envs/mimic_env.py:583-610: early-termination thresholds
MAX_POSITIVE_SAGITTAL = 0.3
MAX_NEGATIVE_SAGITTAL = -0.05
MAX_FRONTAL_DEVIATION = 0.2
MAX_AXIAL_DEVIATION = 0.5
MAX_LATERAL_COM = 0.2
MIN_COM_HEIGHT = 0.75
FALL_COM_HEIGHT = 0.5
# The 3D observation layout of mimic_env.py:351-388: phase, desired speed, 13 qpos values and 14 qvel values.
OBSERVATION_SIZE = 29
# The MJCF model has 14 joints (6 trunk/COM + 8 actuated joints); mimic_walker3d.py:15-27 lists them in qpos order.
QPOS_SIZE = 14

# The synthetic gait is the fake's own data, not an upstream fact.  Each value below is a placeholder.
GAIT_STEPS = 100                                  # placeholder: control steps per synthetic gait step
ACTION_GAIN = 0.08                                # placeholder: how far a normalised action moves a joint
JOINT_LAG = 0.25                                  # placeholder: first-order lag of a joint toward its target
TRUNK_ACTION_GAIN = 0.02                          # placeholder: sagittal torque drift per unit action
TRUNK_DAMPING = 0.05                              # placeholder: pull of the trunk back to upright
FRONTAL_ACTION_GAIN = 0.01                        # placeholder: frontal torque drift per unit action
AXIAL_ACTION_GAIN = 0.01                          # placeholder: axial torque drift per unit action
LATERAL_ACTION_GAIN = 0.01                        # placeholder: lateral COM drift per unit action
COM_BOB = 0.02                                    # placeholder: vertical bob amplitude
COM_SAG_DROP = 0.06                               # placeholder: COM height lost per radian of sagittal tilt
COM_LATERAL_DROP = 0.02                           # placeholder: COM height lost per metre of lateral offset
RESET_PHASE_JITTER = 0.25                         # placeholder: random initial-phase window
RESET_LATERAL_JITTER = 0.01                       # placeholder: random initial lateral offset
DEFAULT_SEED = 0                                  # placeholder: seed used before the first seeded reset


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


def _reference_joints(phase):
    """A synthetic eight-joint gait at ``phase`` in [0, 1): four right joints then four left joints.

    Every amplitude and phase below is a placeholder of this fake, not a value from the clone or a device.
    """
    angle = 2.0 * math.pi * phase
    sine = math.sin(angle)
    cosine = math.cos(angle)
    return [
        0.35 * sine,                              # placeholder: right hip sagittal
        0.05 * cosine,                            # placeholder: right hip frontal
        0.25 * (1.0 - cosine),                    # placeholder: right knee
        -0.15 * sine,                             # placeholder: right ankle
        -0.35 * sine,                             # placeholder: left hip sagittal
        -0.05 * cosine,                           # placeholder: left hip frontal
        0.25 * (1.0 + cosine),                    # placeholder: left knee
        0.15 * sine,                              # placeholder: left ankle
    ]


class FakeMimicWalker3dEnv:
    """Deterministic analytic stand-in for ``MimicWalker3dEnv``: ``reset``, ``step`` and ``close``.

    ``step`` returns the upstream legacy four-tuple ``(observation, reward, done, info)``; the bridge accepts it and
    reports ``truncated`` as False.  ``reset`` returns a 29-float observation, as the legacy environment does.
    """

    def __init__(self):
        high = [math.inf] * OBSERVATION_SIZE
        self.action_space = Box([CTRL_LOW] * len(PEAK_TORQUES), [CTRL_HIGH] * len(PEAK_TORQUES))  # placeholder
        self.observation_space = Box([-value for value in high], high)
        self._rng = random.Random(DEFAULT_SEED)                  # placeholder: default random generator
        self._closed = False
        self._initialize()

    # -- environment interface -------------------------------------------------
    def seed(self, seed=None):
        """Legacy Gym seed surface; this controls only the fake's placeholder initial state."""
        self._rng = random.Random(seed)
        return [seed]

    def reset(self):
        """Legacy reset without keyword arguments; the bridge falls back to seed(seed), then reset()."""
        if self._closed:
            self._closed = False
        self._initialize()
        return list(self._observation())

    def step(self, action):
        """Apply one control action for one 5 ms control period, as ``MimicEnv.step`` does."""
        if self._done:
            raise RuntimeError("the episode has ended; reset the environment first")
        values = self._action_values(action)
        clipped = [max(-1.0, min(1.0, value)) for value in values]
        self._episode_steps += 1
        self._advance(clipped)
        reward = self._reward()
        return list(self._observation()), reward, bool(self._done), {}

    def close(self):
        """Release nothing: the stand-in has no simulator or file handle.  The next reset reopens the episode."""
        self._closed = True

    # -- state -----------------------------------------------------------------
    def _initialize(self):
        """Start a new episode at a random gait phase and a small lateral offset (both placeholders)."""
        self._phase = self._rng.uniform(0.0, RESET_PHASE_JITTER)          # placeholder
        self._gait_step = 0
        self._episode_steps = 0
        self._distance = 0.0
        self._lateral = self._rng.uniform(-RESET_LATERAL_JITTER,
                                          RESET_LATERAL_JITTER)          # placeholder
        self._trunk_sag = 0.0
        self._trunk_front = 0.0
        self._trunk_axial = 0.0
        self._joints = _reference_joints(self._phase)
        self._ref_joints = list(self._joints)
        self._ref_vels = [0.0] * len(self._joints)
        self._joint_vels = [0.0] * len(self._joints)
        self._com_velocity = [0.0, 0.0, 0.0]
        self._trunk_velocity = [0.0, 0.0, 0.0]
        self._done = False

    def _action_values(self, action):
        try:
            values = list(action)
        except TypeError as exc:
            raise AssertionError(f"{action!r} is not an eight-value action") from exc
        if len(values) != len(PEAK_TORQUES):
            raise AssertionError(f"the action has {len(values)} values, expected {len(PEAK_TORQUES)}")
        out = []
        for value in values:
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise AssertionError(f"{value!r} is not a number") from exc
            if not math.isfinite(number):
                raise AssertionError(f"{value!r} is not finite")
            out.append(number)
        return out

    def _advance(self, action):
        """Advance the synthetic gait by one control period (all dynamics here are placeholders)."""
        previous_qpos = self._qpos()
        previous_joints = list(self._joints)
        previous_ref = list(self._ref_joints)
        self._phase += 1.0 / GAIT_STEPS
        if self._phase >= 1.0:
            self._phase -= 1.0
            self._gait_step += 1
        self._ref_joints = _reference_joints(self._phase)
        self._ref_vels = [(self._ref_joints[index] - previous_ref[index]) / CONTROL_STEP_S
                          for index in range(len(self._joints))]
        for index in range(len(self._joints)):
            target = self._ref_joints[index] + ACTION_GAIN * action[index]
            self._joints[index] += JOINT_LAG * (target - self._joints[index])
            self._joint_vels[index] = (self._joints[index] - previous_joints[index]) / CONTROL_STEP_S
        mean_action = sum(action) / len(action)
        self._trunk_sag += TRUNK_ACTION_GAIN * mean_action - TRUNK_DAMPING * self._trunk_sag
        self._trunk_front += FRONTAL_ACTION_GAIN * (action[1] + action[5]) / 2.0 \
            - TRUNK_DAMPING * self._trunk_front
        self._trunk_axial += AXIAL_ACTION_GAIN * (action[2] - action[6]) / 2.0 \
            - TRUNK_DAMPING * self._trunk_axial
        self._lateral += LATERAL_ACTION_GAIN * (action[1] + action[5]) / 2.0 \
            - TRUNK_DAMPING * self._lateral
        if self._distance < MAX_WALKING_DISTANCE + 1.0:
            self._distance += DESIRED_WALKING_SPEED * CONTROL_STEP_S
        qpos = self._qpos()
        self._com_velocity = [(qpos[index] - previous_qpos[index]) / CONTROL_STEP_S for index in range(3)]
        self._trunk_velocity = [(qpos[index] - previous_qpos[index]) / CONTROL_STEP_S for index in range(3, 6)]
        com_height_too_low = qpos[2] < MIN_COM_HEIGHT
        max_eplen_reached = (self._episode_steps >= MAX_EPISODE_STEPS
                             or qpos[0] > MAX_WALKING_DISTANCE + 0.01)
        early = (com_height_too_low
                 or self._trunk_sag > MAX_POSITIVE_SAGITTAL
                 or self._trunk_sag < MAX_NEGATIVE_SAGITTAL
                 or abs(self._trunk_front) > MAX_FRONTAL_DEVIATION
                 or abs(self._trunk_axial) > MAX_AXIAL_DEVIATION
                 or abs(qpos[1]) > MAX_LATERAL_COM)
        self._done = bool(qpos[2] < FALL_COM_HEIGHT or max_eplen_reached or early)

    def _qpos(self):
        """The 14 qpos values in the order of mimic_walker3d.py:15-27 (all generated values are placeholders)."""
        com_height = 1.08 + COM_BOB * math.sin(4.0 * math.pi * self._phase) \
            - COM_SAG_DROP * abs(self._trunk_sag) - COM_LATERAL_DROP * abs(self._lateral)
        return ([self._distance, self._lateral, com_height,
                 self._trunk_front, self._trunk_sag, self._trunk_axial]
                + list(self._joints))

    def _qvel(self):
        """The 14 qvel values paired with ``_qpos``; the root velocities and the joint velocities."""
        return (list(self._com_velocity) + list(self._trunk_velocity) + list(self._joint_vels))

    def _observation(self):
        """``[phase, desired speed] + qpos[1:] + qvel`` (mimic_env.py:351-374)."""
        return [self._phase, DESIRED_WALKING_SPEED] + self._qpos()[1:] + self._qvel()

    def _reward(self):
        """Analytic imitation-like reward with the configured weights (all terms below are placeholders)."""
        pose_error = sum((self._joints[index] - self._ref_joints[index]) ** 2
                         for index in range(len(self._joints)))
        pose_reward = math.exp(-3.0 * pose_error)                     # placeholder: pose scale
        velocity_error = sum((self._joint_vels[index] - self._ref_vels[index]) ** 2
                             for index in range(len(self._joints)))
        velocity_reward = math.exp(-0.05 * velocity_error)            # placeholder: velocity scale
        com_error = self._lateral ** 2 + (self._qpos()[2] - 1.08) ** 2
        com_reward = math.exp(-16.0 * com_error)                      # placeholder: COM scale
        weights = REWARD_WEIGHTS
        reward = (weights[0] * pose_reward + weights[1] * velocity_reward
                  + weights[2] * com_reward)
        if not self._done:
            reward += ALIVE_BONUS
        return reward
