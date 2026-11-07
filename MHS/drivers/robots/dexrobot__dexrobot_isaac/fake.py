"""Fake backend of the DexHand Isaac Gym driver: a pure Python stand-in for ``DexHandBase``.

Why a fake: ``DexHandBase`` imports ``isaacgym``, ``torch`` and the bundled hand model, which are not available
where the acceptance gate runs, and package code never imports the clone.  This module re-implements the public
surface the Gymnasium bridge uses (``reset``, ``step``, ``seed``, ``close``, ``action_space``,
``observation_space``) for the class the driver names as ``native``
(``dexhand_env.tasks.dexhand_base:DexHandBase``).  Every constant below cites the line of the clone at the pinned
commit ``dc85a0b54a7051470f0162c7df22a2a1c69cfaf1``; the numbers that are only the fake's simplification are marked
``# placeholder`` and are not facts about the environment.

What this is not: the Isaac Gym simulation.  The fake has no contacts, no rigid-body dynamics, no actuator or
sensor model and no rendering; it integrates the commanded position deltas of a single environment.  The driver's
fidelity ``gaps`` state these differences.  Upstream ``step`` and ``reset`` return the batched observation buffer
``(num_envs, num_observations)``; the bridge serves one environment, so this fake returns the single row as a flat
list.  Nothing here talks to a device.
"""

import math

# dexhand_env/constants.py:8-9 (NUM_BASE_DOFS, NUM_ACTIVE_FINGER_DOFS)
NUM_BASE_DOFS = 6
NUM_ACTIVE_FINGER_DOFS = 12
NUM_ACTIONS = NUM_BASE_DOFS + NUM_ACTIVE_FINGER_DOFS
# dexhand_env/constants.py:11 (NUM_FINGERS)
NUM_FINGERS = 5
# dexhand_env/cfg/task/BaseTask.yaml:103-116: the 13 policy observation components and their dimensions
OBSERVATION_DIM = 6 + 6 + 12 + 12 + 7 + 5 + NUM_ACTIONS + 6 + 12 + 35 + 35 + 35 + 35
# dexhand_env/cfg/task/BaseTask.yaml:19 (episodeLength)
MAX_EPISODE_LENGTH = 300
# dexhand_env/cfg/task/BaseTask.yaml:10 (sim.dt, 200 Hz)
PHYSICS_DT = 0.005
# dexhand_env/cfg/task/BaseTask.yaml:43-45 (component-wise velocity limits of position_delta mode)
MAX_FINGER_JOINT_VELOCITY = 1.0
MAX_BASE_LINEAR_VELOCITY = 0.5
MAX_BASE_ANGULAR_VELOCITY = 1.5
# dexhand_env/cfg/task/BaseTask.yaml:62 (reward_weights.alive)
ALIVE_REWARD = 0.1
# dexhand_env/cfg/task/BaseTask.yaml:17-18 (initialHandPos, initialHandRot)
INITIAL_HAND_POSITION = [0.0, 0.0, 0.5]
INITIAL_HAND_ROTATION = [0.0, 0.0, 0.0, 1.0]
# dexhand_env/components/termination/termination_manager.py:229-230: timeout at episodeLength - 1
TIMEOUT_STEP = MAX_EPISODE_LENGTH - 1
# placeholder: offsets of the five fingertips and fingerpads in the hand frame; the fake has no finger kinematics
FINGERTIP_OFFSETS = [[0.02 * (index + 1), 0.0, 0.05] for index in range(NUM_FINGERS)]
FINGERPAD_OFFSETS = [[0.02 * (index + 1), 0.0, 0.03] for index in range(NUM_FINGERS)]
_INFINITY = float("inf")


class Box:
    """Duck-typed ``gym.spaces.Box``: the bounds and shape the Gymnasium bridge reads."""

    def __init__(self, low, high, shape, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype

    def contains(self, value):
        values = list(value)
        return len(values) == len(self.low) and all(
            self.low[index] <= float(item) <= self.high[index] for index, item in enumerate(values))


class FakeDexHandBase:
    """One DexHand environment without Isaac Gym: ``reset()``, ``step(actions)``, ``seed(seed)`` and ``close()``.

    ``step`` follows ``dexhand_env/tasks/dexhand_base.py:893-921`` and returns
    ``(observation, reward, done, info)``; ``reset`` follows ``:805-838`` and returns the initial observation.
    """

    def __init__(self, **_options):
        self.num_envs = 1                        # placeholder: the bridge serves one environment
        self.num_actions = NUM_ACTIONS
        self.num_observations = OBSERVATION_DIM
        self.max_episode_length = MAX_EPISODE_LENGTH
        self.dt = PHYSICS_DT
        self._action_space = Box([-1.0] * NUM_ACTIONS, [1.0] * NUM_ACTIONS, (NUM_ACTIONS,))
        self._observation_space = Box([-_INFINITY] * OBSERVATION_DIM, [_INFINITY] * OBSERVATION_DIM,
                                      (OBSERVATION_DIM,))
        self._seed = None
        self._closed = False
        self._base_pos = [0.0] * NUM_BASE_DOFS
        self._base_vel = [0.0] * NUM_BASE_DOFS
        self._finger_pos = [0.0] * NUM_ACTIVE_FINGER_DOFS
        self._finger_vel = [0.0] * NUM_ACTIVE_FINGER_DOFS
        self._prev_actions = [0.0] * NUM_ACTIONS
        self._base_target = [0.0] * NUM_BASE_DOFS
        self._finger_target = [0.0] * NUM_ACTIVE_FINGER_DOFS
        self._contact = [0.0] * NUM_FINGERS       # placeholder: the fake models no contacts
        self._episode_step_count = 0
        self._episode = 0

    # -- Gymnasium bridge surface -------------------------------------------------
    def reset(self):
        """Reset the environment and return its initial observation (dexhand_base.py:805-838)."""
        self._base_pos = [0.0] * NUM_BASE_DOFS
        self._base_vel = [0.0] * NUM_BASE_DOFS
        self._finger_pos = [0.0] * NUM_ACTIVE_FINGER_DOFS
        self._finger_vel = [0.0] * NUM_ACTIVE_FINGER_DOFS
        self._prev_actions = [0.0] * NUM_ACTIONS
        self._base_target = [0.0] * NUM_BASE_DOFS
        self._finger_target = [0.0] * NUM_ACTIVE_FINGER_DOFS
        self._contact = [0.0] * NUM_FINGERS       # placeholder: the fake models no contacts
        self._episode_step_count = 0
        self._episode += 1
        return self._observation()

    def step(self, actions):
        """Apply one normalized action and return ``(observation, reward, done, info)``."""
        values = self._checked_actions(actions)
        self._base_vel = [
            values[index] * MAX_BASE_LINEAR_VELOCITY for index in range(3)
        ] + [
            values[3 + index] * MAX_BASE_ANGULAR_VELOCITY for index in range(3)
        ]
        self._finger_vel = [
            values[NUM_BASE_DOFS + index] * MAX_FINGER_JOINT_VELOCITY
            for index in range(NUM_ACTIVE_FINGER_DOFS)
        ]
        self._base_pos = [position + velocity * PHYSICS_DT
                          for position, velocity in zip(self._base_pos, self._base_vel)]
        self._finger_pos = [position + velocity * PHYSICS_DT
                            for position, velocity in zip(self._finger_pos, self._finger_vel)]
        self._base_target = list(self._base_pos)
        self._finger_target = list(self._finger_pos)
        self._prev_actions = values
        self._episode_step_count += 1
        done = self._episode_step_count >= TIMEOUT_STEP
        info = {"episode_step_count": self._episode_step_count, "timeout": done}
        return self._observation(), ALIVE_REWARD, done, info

    def seed(self, seed=None):
        """Record the seed; this fake's reset is deterministic, as the default BaseTask reset is."""
        if seed is None:
            return None
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError(f"{seed!r} is not a non-negative integer seed")
        self._seed = seed
        return None

    def close(self):
        """Close the environment (dexhand_base.py:1073)."""
        self._closed = True

    @property
    def action_space(self):
        """The normalized action space (dexhand_base.py:1162-1169)."""
        return self._action_space

    @property
    def observation_space(self):
        """The flat observation space (dexhand_base.py:1150-1160)."""
        return self._observation_space

    # -- helpers -------------------------------------------------------------------
    def _checked_actions(self, actions):
        try:
            values = [float(item) for item in actions]
        except (TypeError, ValueError) as exc:
            raise ValueError("actions must be a sequence of numbers") from exc
        if len(values) != NUM_ACTIONS:
            raise ValueError(f"expected {NUM_ACTIONS} actions, got {len(values)}")
        if any(not math.isfinite(item) or item < -1.0 or item > 1.0 for item in values):
            raise ValueError("actions must be finite and inside [-1, 1]")
        return values

    def _observation(self):
        hand_position = [INITIAL_HAND_POSITION[index] + self._base_pos[index] for index in range(3)]
        hand_pose = hand_position + list(INITIAL_HAND_ROTATION)
        fingertip_world = []
        fingertip_hand = []
        fingerpad_world = []
        fingerpad_hand = []
        for index in range(NUM_FINGERS):
            tip = FINGERTIP_OFFSETS[index]
            pad = FINGERPAD_OFFSETS[index]
            fingertip_hand.extend(tip + [0.0, 0.0, 0.0, 1.0])
            fingerpad_hand.extend(pad + [0.0, 0.0, 0.0, 1.0])
            fingertip_world.extend([hand_position[axis] + tip[axis] for axis in range(3)] + [0.0, 0.0, 0.0, 1.0])
            fingerpad_world.extend([hand_position[axis] + pad[axis] for axis in range(3)] + [0.0, 0.0, 0.0, 1.0])
        observation = (
            list(self._base_pos)
            + list(self._base_vel)
            + list(self._finger_pos)
            + list(self._finger_vel)
            + hand_pose
            + list(self._contact)
            + list(self._prev_actions)
            + list(self._base_target)
            + list(self._finger_target)
            + fingertip_world
            + fingertip_hand
            + fingerpad_world
            + fingerpad_hand
        )
        if len(observation) != OBSERVATION_DIM:  # a coding error, never a device state
            raise RuntimeError(f"fake observation has {len(observation)} values, expected {OBSERVATION_DIM}")
        return observation
