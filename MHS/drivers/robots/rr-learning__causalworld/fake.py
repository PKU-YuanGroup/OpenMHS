"""Fake backend of the CausalWorld driver: a pure Python kinematic stand-in for the reaching task.

Why a fake: the upstream class imports gym, pybullet, numpy and its own TriFinger assets
(causal_world/envs/causalworld.py:1-14), and package code never imports or runs the clone, so the gate cannot open
the PyBullet environment.  This module mirrors the public surface the bridge uses (``reset``, ``step``, ``seed``,
``close``; gate G7) and the reaching task's action and observation shape: a normalized 9-element joint-position
action (causal_world/envs/robot/action.py:21-24, :61-64) and a normalized 37-element structured observation
(causal_world/task_generators/reaching.py:47-51, :85-89; causal_world/envs/robot/observations.py:73-74).

What this is not: the upstream PyBullet model.  The arm, contacts, friction, PD controller and the 4 ms physics
substeps are replaced by setting the normalized joint positions directly once per 40 ms control step.  The start
joints come from Python's random.Random, not numpy's generator, so a seed does not give the same trajectory as
upstream.  The driver's fidelity ``gaps`` list all of this.  Every numeric constant below is test data, marked
``# placeholder``; the citations are only the upstream lines the stand-in mirrors, never evidence for a Fact or a
Limit.

Nothing here talks to a device.
"""

import random

# causal_world/envs/robot/action.py:21-24, :61-64: normalized joint positions, 3 fingers x 3 joints.
ACTION_LOW, ACTION_HIGH = -1.0, 1.0                       # placeholder: normalized action bounds
N_ACTION = 9                                             # placeholder: 3 fingers x 3 joints
# causal_world/envs/causalworld.py:93-96 with the default skip_frame 10 (:26): one 40 ms control step.
DT = 0.04                                                # placeholder: control step in seconds
# causal_world/task_generators/base_task.py:1198-1202, causal_world/envs/causalworld.py:167-170: 5 s / 0.04 s.
MAX_EPISODE_LENGTH = 125                                 # placeholder: default reaching time limit in steps
# causal_world/task_generators/reaching.py:47-51, :85-89: 1 time-left + 9 + 9 + 9 robot and 3 x 3 goal values.
N_OBSERVATION = 37                                       # placeholder: structured reaching observation size
# causal_world/envs/robot/observations.py:73-74: normalized observations use -1 and 1.
OBSERVATION_LOW, OBSERVATION_HIGH = -1.0, 1.0            # placeholder: normalized observation bounds
# causal_world/envs/robot/observations.py:59-62: raw joint velocities are bounded by +-50.
JOINT_VELOCITY_BOUND = 50.0                              # placeholder: raw joint-velocity bound
# causal_world/task_generators/reaching.py:10-12: the three default goals, normalized with the silhouette bounds of
# causal_world/envs/scene/silhouette.py:41-56.  These are stand-in observation values, not device evidence.
GOAL_POSITIONS = [0.0, 0.0, -0.60,                       # placeholder: default goal_60 [0, 0, 0.10] normalized
                  0.0, 0.0, -0.48,                       # placeholder: default goal_120 [0, 0, 0.13] normalized
                  0.0, 0.0, -0.36]                       # placeholder: default goal_300 [0, 0, 0.16] normalized
GOAL_POSITIONS_RAW = [0.0, 0.0, 0.10,                    # placeholder: reaching.py:10
                      0.0, 0.0, 0.13,                    # placeholder: reaching.py:11
                      0.0, 0.0, 0.16]                    # placeholder: reaching.py:12


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float64"


class FakeCausalWorld:
    """CausalWorld's reaching task without PyBullet: the legacy gym reset/step/seed surface."""

    def __init__(self):
        self.action_space = Box([ACTION_LOW] * N_ACTION, [ACTION_HIGH] * N_ACTION)       # placeholder
        self.observation_space = Box([OBSERVATION_LOW] * N_OBSERVATION,
                                     [OBSERVATION_HIGH] * N_OBSERVATION)                  # placeholder
        self.dt = DT                                                                     # placeholder
        self._rng = random.Random()                                                      # placeholder
        self._joint_positions = [0.0] * N_ACTION                                         # placeholder
        self._joint_velocities = [0.0] * N_ACTION                                        # placeholder
        self._end_effector_positions = [0.0] * N_ACTION                                  # placeholder
        self._episode_length = 0
        self._closed = False

    def seed(self, seed=None):
        """Reseed the start-joint generator; upstream reseeds gym's np_random and numpy (causalworld.py:333-344)."""
        self._rng = random.Random(seed) if seed is not None else random.Random()
        return [seed]

    def reset(self):
        """Start an episode and return the normalized 37-element observation (causalworld.py:346-372)."""
        self._episode_length = 0
        self._joint_positions = [self._rng.uniform(-0.2, 0.2) for _ in range(N_ACTION)]   # placeholder
        self._joint_velocities = [0.0] * N_ACTION                                         # placeholder
        self._end_effector_positions = self._derive_end_effector_positions()              # placeholder
        return self._observation()

    def step(self, action):
        """Advance one 40 ms control step and return the legacy four-value step result (causalworld.py:254-290)."""
        values = [float(value) for value in action]
        if len(values) != N_ACTION:
            raise ValueError(f"the joint-position action has {N_ACTION} values, got {len(values)}")
        previous = list(self._joint_positions)
        # action.py:87-93 and trifinger.py:336-341: the upstream clips the action to the action space.
        clipped = [min(ACTION_HIGH, max(ACTION_LOW, value)) for value in values]          # placeholder
        self._joint_positions = clipped
        self._joint_velocities = [
            max(-1.0, min(1.0, (clipped[index] - previous[index]) / DT / JOINT_VELOCITY_BOUND))  # placeholder
            for index in range(N_ACTION)
        ]
        self._end_effector_positions = self._derive_end_effector_positions()             # placeholder
        self._episode_length += 1
        reward = -0.001 * sum(abs(value) for value in clipped)                            # placeholder
        done = self._episode_length > MAX_EPISODE_LENGTH                                  # causalworld.py:422-430
        info = {
            "desired_goal": list(GOAL_POSITIONS_RAW),                                     # placeholder
            "achieved_goal": list(self._end_effector_positions),                          # placeholder
            "success": False,                                                             # placeholder
            "fractional_success": 0.0,                                                    # placeholder
        }
        return self._observation(), reward, done, info

    def close(self):
        """Release the stand-in state; upstream closes the PyBullet clients (causalworld.py:401-410)."""
        self._closed = True
        self._joint_positions = None
        self._joint_velocities = None
        self._end_effector_positions = None

    def _derive_end_effector_positions(self):
        """A placeholder kinematic map from the 9 normalized joints to 9 normalized finger-tip values."""
        joints = self._joint_positions or [0.0] * N_ACTION                               # placeholder
        return [
            0.5 * joints[0] + 0.25 * joints[1],                                          # placeholder
            0.25 * joints[2],                                                            # placeholder
            -0.4 + 0.2 * joints[0],                                                      # placeholder
            0.5 * joints[3] + 0.25 * joints[4],                                          # placeholder
            0.25 * joints[5],                                                            # placeholder
            -0.4 + 0.2 * joints[3],                                                      # placeholder
            0.5 * joints[6] + 0.25 * joints[7],                                          # placeholder
            0.25 * joints[8],                                                            # placeholder
            -0.4 + 0.2 * joints[6],                                                      # placeholder
        ]

    def _observation(self):
        """The reaching observation order: time-left, joints, velocities, tips and three goals."""
        time_left = (MAX_EPISODE_LENGTH - self._episode_length) / MAX_EPISODE_LENGTH     # placeholder
        time_left = max(-1.0, min(1.0, 2.0 * time_left - 1.0))                            # placeholder
        return (
            [time_left]
            + list(self._joint_positions)                                                 # placeholder
            + list(self._joint_velocities)                                                # placeholder
            + list(self._end_effector_positions)                                          # placeholder
            + list(GOAL_POSITIONS)                                                        # placeholder
        )
