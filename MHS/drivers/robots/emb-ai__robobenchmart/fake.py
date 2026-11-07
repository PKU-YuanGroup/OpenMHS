"""Fake backend for ``MoveFromBoardToBoardVanishContEnv``: a small analytic stand-in, no ManiSkill, no SAPIEN.

The acceptance gate runs without ManiSkill, SAPIEN, Vulkan or the generated scene data the upstream environment
needs (README.md:15 and :45-55), and package code never imports the clone.  This module therefore models only the
interface the Gymnasium bridge uses: ``reset(seed, options)`` returns ``(observation, info)`` and ``step(action)``
returns ``(observation, reward, terminated, truncated, info)``, as the upstream environment is used at
``scripts/eval_policy_client.py:161`` and ``:175``.

The observation is NOT the upstream observation: the real environment returns a ManiSkill observation dictionary
with three RGB camera streams and the agent state (``scripts/eval_policy_client.py:32-44``).  This fake returns only
the ten joint positions, a deliberately smaller array; the fidelity ``gaps`` of ``driver.py`` and ``RESULT.json``
say so.  The ten-value action box and the initial joint spread below are test data of the fake (each marked
``placeholder``), not measurements of the upstream environment.

Every public member is one the upstream class has or inherits: the G7 gate reads ``reset`` from the clone's
``DarkstoreCellBaseEnv`` (``dsynth/envs/darkstore_cell_base.py:79``) and warns that ``step`` comes from the external
ManiSkill base (the clone only uses ``step`` in ``dsynth/utils.py:356``).  Nothing here talks to a device.
"""

import random

# Test data of this fake, not facts of the upstream environment: the policy client uses at least ten action
# components (scripts/eval_policy_client.py:171-174), and a normalised joint-position controller is the common
# ManiSkill shape, but the clone never states the bounds.  These numbers are placeholders.
NUM_JOINTS = 10                                                             # placeholder
ACTION_LOW = -1.0                                                           # placeholder
ACTION_HIGH = 1.0                                                           # placeholder
START_SPREAD = 0.05                                                         # placeholder
STEP_GAIN = 0.1                                                             # placeholder
JOINT_LIMIT = 1.0                                                           # placeholder

# dsynth/envs/move_from_board_to_board.py:459-460 registers the task with max_episode_steps=200000.
MAX_EPISODE_STEPS = 200000


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeMoveFromBoardToBoardVanishContEnv:
    """Ten scalar joints, seeded start state and a deterministic kinematic step (test data only)."""

    def __init__(self):
        self.action_space = Box([ACTION_LOW] * NUM_JOINTS, [ACTION_HIGH] * NUM_JOINTS)
        self._rng = random.Random(0)                                        # placeholder
        self._state = None
        self._elapsed_steps = 0

    def reset(self, seed=None, options=None):
        """Mirror ``DarkstoreCellBaseEnv.reset`` (``dsynth/envs/darkstore_cell_base.py:79-85``); options are accepted."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._state = [self._rng.uniform(-START_SPREAD, START_SPREAD) for _ in range(NUM_JOINTS)]
        self._elapsed_steps = 0
        return list(self._state), {"success": False, "is_obj_placed": False, "is_robot_static": True,
                                   "is_non_target_produncts_displaced": False}

    def step(self, action):
        """Move every joint by ``STEP_GAIN`` times the normalised action, then report the episode flags."""
        if self._state is None:
            self.reset()
        values = list(action)
        if len(values) != NUM_JOINTS:
            raise ValueError(f"expected {NUM_JOINTS} action values, got {len(values)}")
        for index, value in enumerate(values):
            moved = self._state[index] + STEP_GAIN * float(value)
            self._state[index] = max(-JOINT_LIMIT, min(JOINT_LIMIT, moved))
        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        info = {"success": False, "is_obj_placed": False, "is_robot_static": True,
                "is_non_target_produncts_displaced": False, "elapsed_steps": self._elapsed_steps}
        return list(self._state), 0.0, False, truncated, info
