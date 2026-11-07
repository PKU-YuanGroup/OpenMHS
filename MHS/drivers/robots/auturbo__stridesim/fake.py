"""Fake backend of the StrideSim driver: a pure Python kinematic stand-in for the ANYmal-D flat task.

Why a fake: the upstream environment is ``omni.isaac.lab.envs:ManagerBasedRLEnv`` with the
``AnymalDFlatEnvCfg`` config, and it needs Isaac Sim 4.0.0 and Isaac Lab v1.0.0 with a GPU (README.md:30-32).
Package code never imports or runs the clone, and the acceptance gate has no Isaac Sim, so this module supplies an
environment object with the Gymnasium surface the bridge uses (``action_space``, ``observation_space``,
``reset(seed, options)``, ``step(action)`` and ``close``).  The two space classes duck-type
``gymnasium.spaces.Box`` (the bridge reads ``low``, ``high`` and ``shape``).

The array shapes are the ones the clone's ANYmal-D sample uses: 12 actions (joint positions, joint velocities and
the previous action are each 12 values; anymal_articulation.py:88, :151-159 and :211) and a 235-value policy
observation (anymal_articulation.py:144).  The flat task removes the height_scan observation term
(flat_env_cfg.py:21), so this fake publishes the first 48 values of that sample observation: base linear velocity,
base angular velocity, projected gravity, velocity command, joint positions, joint velocities and the previous
action.  The values are synthetic, however: the model is kinematic, has no rigid-body dynamics, contacts, actuators,
sensors, terrain or noise, and was not compared with the upstream environment.  The fidelity ``gaps`` of driver.py
list all of this.

Every number that is test data rather than a value read from the clone is marked ``# placeholder``.  The public
members are limited to the Gymnasium environment interface that a base outside the clone provides (gate G7).
Nothing here talks to a device.
"""

import math
import random

# velocity_env_cfg.py:295-298 (LocomotionVelocityRoughEnvCfg.__post_init__)
DECIMATION = 4
SIM_DT_S = 0.005
EPISODE_LENGTH_S = 20.0
TIMESTEP_S = DECIMATION * SIM_DT_S              # 0.02 s of simulated time per environment step
MAX_STEPS = int(EPISODE_LENGTH_S / TIMESTEP_S)  # the time_out term ends the episode at 20 s
# velocity_env_cfg.py:99 (UniformVelocityCommandCfg.Ranges)
COMMAND_LOW, COMMAND_HIGH = -1.0, 1.0
# velocity_env_cfg.py:108 (JointPositionActionCfg.scale)
ACTION_SCALE = 0.5

# anymal_articulation.py:88, :151-159 and :211 (12 joint positions, velocities and previous actions)
N_ACTUATORS = 12
# anymal_articulation.py:144 is a 235-value policy observation; flat_env_cfg.py:21 removes the height scan,
# leaving the first 48 values of anymal_articulation.py:145-159.
N_OBSERVATIONS = 48
OBSERVATION_LOW = -math.inf                     # placeholder: no observation bound is stated in the clone
OBSERVATION_HIGH = math.inf                     # placeholder: no observation bound is stated in the clone
ACTION_LOW = -math.inf                          # placeholder: the action-space bound is outside the clone
ACTION_HIGH = math.inf                          # placeholder: the action-space bound is outside the clone


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: one lower and one upper bound per element."""

    def __init__(self, low, high, shape):
        self.low = [float(low)] * int(shape[0])
        self.high = [float(high)] * int(shape[0])
        self.shape = (int(shape[0]),)
        self.dtype = "float32"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != self.shape[0]:
            return False
        for item in value:
            if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
                return False
        return True


class FakeAnymalDEnv:
    """A deterministic kinematic stand-in: ``reset(seed, options)`` and ``step(action)`` as Gymnasium uses them."""

    def __init__(self, seed=None):
        self.action_space = Box(ACTION_LOW, ACTION_HIGH, (N_ACTUATORS,))
        self.observation_space = Box(OBSERVATION_LOW, OBSERVATION_HIGH, (N_OBSERVATIONS,))
        self._rng = random.Random(seed)
        self._base = [0.0, 0.0, 0.0]              # placeholder: x, y and yaw of the fake base
        self._velocity = [0.0, 0.0, 0.0]          # placeholder: vx, vy and yaw rate
        self._command = [0.0, 0.0, 0.0]           # placeholder: drawn from COMMAND_LOW..COMMAND_HIGH on reset
        self._joint_positions = [0.0] * N_ACTUATORS   # placeholder
        self._joint_velocities = [0.0] * N_ACTUATORS  # placeholder
        self._last_action = [0.0] * N_ACTUATORS       # placeholder
        self._steps = 0
        self._episode = 0

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._command = [self._rng.uniform(COMMAND_LOW, COMMAND_HIGH) for _ in range(3)]
        self._base = [0.0, 0.0, 0.0]              # placeholder
        self._velocity = [0.0, 0.0, 0.0]          # placeholder
        self._joint_positions = [0.0] * N_ACTUATORS   # placeholder
        self._joint_velocities = [0.0] * N_ACTUATORS  # placeholder
        self._last_action = [0.0] * N_ACTUATORS       # placeholder
        self._steps = 0
        self._episode += 1
        return self._observation(), {"command": list(self._command), "episode": self._episode}

    def step(self, action):
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} is not an action of shape {self.action_space.shape}")
        a = [float(item) for item in action]
        # A kinematic mapping from the placeholder joint targets to a base velocity; not the upstream dynamics.
        vx = ACTION_SCALE * sum(a[0:4]) / 4.0
        vy = ACTION_SCALE * sum(a[4:8]) / 4.0
        wz = ACTION_SCALE * sum(a[8:12]) / 4.0
        yaw = self._base[2] + wz * TIMESTEP_S
        self._base = [
            self._base[0] + (vx * math.cos(yaw) - vy * math.sin(yaw)) * TIMESTEP_S,
            self._base[1] + (vx * math.sin(yaw) + vy * math.cos(yaw)) * TIMESTEP_S,
            yaw,
        ]
        self._velocity = [vx, vy, wz]
        self._joint_positions = [ACTION_SCALE * value for value in a]      # placeholder
        self._joint_velocities = [ACTION_SCALE * value for value in a]     # placeholder
        self._last_action = a
        self._steps += 1
        # A placeholder tracking reward, bounded and finite; the upstream reward terms are in velocity_env_cfg.py.
        error = (abs(vx - self._command[0]) + abs(vy - self._command[1]) + abs(wz - self._command[2])) / 3.0
        reward = 1.0 - error
        terminated = False
        truncated = self._steps >= MAX_STEPS
        return self._observation(), reward, terminated, truncated, {"command": list(self._command),
                                                                    "episode": self._episode}

    def close(self):
        self._velocity = [0.0, 0.0, 0.0]          # placeholder

    def _observation(self):
        # The first 48 values of anymal_articulation.py:145-159; height scan is removed by flat_env_cfg.py:21.
        return ([self._velocity[0], self._velocity[1], 0.0,
                 0.0, 0.0, self._velocity[2],
                 0.0, 0.0, -1.0] +
                list(self._command) +
                list(self._joint_positions) +
                list(self._joint_velocities) +
                list(self._last_action))
