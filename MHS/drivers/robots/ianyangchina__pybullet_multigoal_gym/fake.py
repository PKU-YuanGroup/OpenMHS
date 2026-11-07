"""Fake backend of the pybullet_multigoal_gym driver: a pure Python stand-in for the BlockStack environment.

Why a fake: the acceptance gate cannot import the clone (it needs gym, pybullet, numpy, numba and
numpy-quaternion, requirements.txt:1-6), and package code never imports the clone.  This module re-implements
the public surface of ``pybullet_multigoal_gym.envs.task_envs.kuka_multi_step_envs:KukaBlockStackEnv`` (the
class the driver names as ``native``) and the 50-step ``gym`` time limit that ``make_env`` requests through
``max_episode_steps``.  Every constant and rule below cites the line of the clone at the pinned commit
(54b50b8de3d2d58f88f8d4036aafc0858ed3d1e5).  The public members are the ones the environment has (``reset``,
``step``, ``seed``, ``close`` and the ``dt`` property; gate G7), and the two space classes duck-type
``gym.spaces.Box`` and ``gym.spaces.Dict`` (the bridge reads ``low``, ``high``, ``shape`` and ``spaces``).

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* no PyBullet client, no rigid-body dynamics, no inverse kinematics, no contacts and no sensors; the end
  effector moves by a fixed placeholder displacement and the blocks stay where the reset put them;
* the initial state comes from Python's ``random.Random``; upstream seeds ``gym.utils.seeding.np_random``
  (base_env.py:120-122), so one seed gives different numbers on the two;
* observations are Python float lists; upstream returns float32 numpy arrays (base_env.py:86-92);
* image observations, goal images, depth, task decomposition, curriculum, joint control and grip-informed
  goals are not modelled; the fake refuses them rather than pretending.

Nothing here talks to a device.
"""

import math
import random

# pybullet_multigoal_gym/envs/task_envs/kuka_multi_step_envs.py:10 (KukaBlockStackEnv.__init__): the default
# block count, and :7 the default distance threshold.
NUM_BLOCK = 5
DISTANCE_THRESHOLD = 0.05
# pybullet_multigoal_gym/envs/base_envs/base_env.py:6 (make_env default) and :131 (register max_episode_steps):
# the registration's horizon.  gym's TimeLimit wrapper turns it into done=True; the fake does the same.
MAX_EPISODE_STEPS = 50
# pybullet_multigoal_gym/robots/kuka.py:108-113: KukaBlockStackEnv passes grasping=True and joint_control=False,
# so Kuka.action_space is Box(-1, 1) with four values (three translation plus the finger command).
ACTION_LOW, ACTION_HIGH = -1.0, 1.0
ACTION_SIZE = 4
# pybullet_multigoal_gym/robots/kuka.py:71: the parallel jaw gripper's absolute joint limit, used by the fake
# only to keep the finger value in the same range as the upstream mapping (kuka.py:171).
GRIPPER_LIMIT = 0.035
# pybullet_multigoal_gym/envs/base_envs/base_env.py:112-118: dt = timestep * frame_skip; the constructor
# defaults timestep=0.002 and frame_skip=20 (base_env.py:17), so dt is 0.04 s and one step is one action.
TIMESTEP_S = 0.002
FRAME_SKIP = 20
DT = TIMESTEP_S * FRAME_SKIP
# pybullet_multigoal_gym/envs/base_envs/kuka_multi_step_base_env.py:306-307: state and policy_state are clipped
# to [-5, 5].  The fake keeps its placeholder values inside the same bound.
STATE_CLIP = 5.0
# Test data, not a fact: a start end-effector position and per-step displacement chosen so the placeholder
# arrays stay inside the clip bound.  They are not calibrated against the upstream model.
START_END_EFFECTOR = [-0.52, 0.0, 0.25]  # placeholder
STEP_DISPLACEMENT = 0.01  # placeholder
BLOCK_RANGE = 0.10  # placeholder
GOAL_OFFSET = [0.02, 0.0, 0.03]  # placeholder


class Box:
    """Duck-typed ``gym.spaces.Box``: a bounded array with a shape and a dtype."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"

    def contains(self, value):
        try:
            values = [float(item) for item in value]
        except TypeError:
            return False
        return len(values) == len(self.low) and all(
            self.low[index] <= values[index] <= self.high[index] for index in range(len(values)))


class Dict:
    """Duck-typed ``gym.spaces.Dict``: named member spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeKukaBlockStackEnv:
    """KukaBlockStackEnv without PyBullet: legacy-gym ``reset(test)`` returns the observation, ``step`` the
    ``(observation, reward, done, info)`` tuple (base_env.py:124-138)."""

    def __init__(self, render=False, binary_reward=True, distance_threshold=DISTANCE_THRESHOLD, random_order=True,
                 image_observation=False, goal_image=False, depth_image=False, visualize_target=True,
                 camera_setup=None, observation_cam_id=0, goal_cam_id=0, gripper_type="parallel_jaw",
                 grip_informed_goal=False, num_block=NUM_BLOCK, joint_control=False, task_decomposition=False,
                 use_curriculum=False, num_goals_to_generate=1e5):
        if image_observation or goal_image or depth_image:
            raise ValueError("the fake models the non-image BlockStack configuration only")
        if grip_informed_goal or joint_control or task_decomposition or use_curriculum:
            raise ValueError("the fake models the plain BlockStack configuration (no joint control, task "
                             "decomposition, curriculum or grip-informed goal)")
        if gripper_type not in ("parallel_jaw", "robotiq85"):
            raise ValueError("gripper_type must be 'parallel_jaw' or 'robotiq85'")
        if isinstance(num_block, bool) or not isinstance(num_block, int) or not 1 <= num_block <= 5:
            raise ValueError("the upstream registration allows at most 5 blocks (__init__.py:108)")
        self.render = bool(render)  # placeholder: the fake never opens a window
        self.num_block = int(num_block)
        self.binary_reward = bool(binary_reward)
        self.distance_threshold = float(distance_threshold)
        self.gripper_type = gripper_type
        self._rng = None
        self.seed(0)  # base_env.py:24 seeds the environment with 0 in the constructor
        self._ee = list(START_END_EFFECTOR)  # placeholder
        self._ee_velocity = [0.0, 0.0, 0.0]  # placeholder
        self._finger_closeness = GRIPPER_LIMIT  # placeholder; the real value comes from PyBullet
        self._finger_velocity = 0.0  # placeholder
        self._blocks = []  # placeholder block positions, filled by reset()
        self._block_rpy = []  # placeholder block orientations, filled by reset()
        self._desired_goal = []  # placeholder target positions, filled by reset()
        self._steps = 0
        self._done = False
        self._closed = False
        self.action_space = Box([ACTION_LOW] * ACTION_SIZE, [ACTION_HIGH] * ACTION_SIZE, (ACTION_SIZE,))
        # base_env.py:86-92: the non-image observation space is a Dict of four Box(-inf, inf) float32 members.
        self.observation_space = Dict({
            "state": Box([-math.inf] * self._state_size(), [math.inf] * self._state_size(), (self._state_size(),)),
            "policy_state": Box([-math.inf] * self._policy_size(), [math.inf] * self._policy_size(),
                                (self._policy_size(),)),
            "achieved_goal": Box([-math.inf] * self._goal_size(), [math.inf] * self._goal_size(),
                                 (self._goal_size(),)),
            "desired_goal": Box([-math.inf] * self._goal_size(), [math.inf] * self._goal_size(),
                                (self._goal_size(),)),
        })
        self.reset()

    @property
    def dt(self):
        """The action interval ``timestep * frame_skip`` (base_env.py:112-118)."""
        return DT

    def seed(self, seed=None):
        """Seed the placeholder generator and return ``[seed]`` like base_env.py:120-122."""
        if seed is None:
            seed = random.SystemRandom().randrange(2 ** 31)
        self._rng = random.Random(int(seed))
        return [seed]

    def reset(self, test=False):
        """Reset the placeholder blocks and return the observation (base_env.py:124-128)."""
        self._ee = list(START_END_EFFECTOR)  # placeholder
        self._ee_velocity = [0.0, 0.0, 0.0]  # placeholder
        self._finger_closeness = GRIPPER_LIMIT  # placeholder
        self._finger_velocity = 0.0  # placeholder
        self._blocks = [[round(self._rng.uniform(-BLOCK_RANGE, BLOCK_RANGE) - 0.52, 6),
                         round(self._rng.uniform(-BLOCK_RANGE, BLOCK_RANGE), 6),
                         0.175]  # placeholder
                        for _ in range(self.num_block)]
        self._block_rpy = [[0.0, 0.0, 0.0] for _ in range(self.num_block)]  # placeholder
        self._desired_goal = [[round(block[0] + GOAL_OFFSET[0], 6),
                               round(block[1] + GOAL_OFFSET[1], 6),
                               round(block[2] + GOAL_OFFSET[2], 6)]  # placeholder
                              for block in self._blocks]
        self._steps = 0
        self._done = False
        return self._observation()

    def step(self, action):
        """Apply one placeholder action, then the upstream sparse reward and the registration's time limit."""
        if self._done:
            raise RuntimeError("the episode has ended; reset the environment")
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} is not in the environment's action space")
        values = [float(item) for item in action]
        self._ee = [self._ee[index] + STEP_DISPLACEMENT * values[index] for index in range(3)]  # placeholder
        self._ee_velocity = [STEP_DISPLACEMENT * values[index] / DT for index in range(3)]  # placeholder
        # kuka.py:171 maps the last action value to the finger command in [0, gripper_abs_joint_limit].
        self._finger_closeness = (values[3] + 1.0) * (GRIPPER_LIMIT / 2.0)  # placeholder
        self._finger_velocity = 0.0  # placeholder
        self._steps += 1
        # kuka_multi_step_base_env.py:338-345: the sparse reward is -1 outside the distance threshold and 0 inside.
        distance = self._distance()
        reward = -1.0 if distance > self.distance_threshold else 0.0
        if not self.binary_reward:
            reward = -distance
        # __init__.py:6 and :131: make_env registers max_episode_steps=50 by default; gym's TimeLimit returns
        # done=True after that many steps.
        self._done = self._steps >= MAX_EPISODE_STEPS
        info = {"goal_achieved": bool(distance <= self.distance_threshold)}
        return self._observation(), float(reward), bool(self._done), info

    def close(self):
        self._closed = True

    # -- placeholder observation (leading underscore: not part of the upstream surface) -------------------
    def _state_size(self):
        # kuka_multi_step_base_env.py:282-283: gripper xyz (3), finger closeness (1), gripper velocity (3),
        # finger velocity (1), and 15 values per block (kuka_multi_step_base_env.py:264-280).
        return 8 + 15 * self.num_block

    def _policy_size(self):
        # kuka_multi_step_base_env.py:283: gripper xyz, finger closeness and the relative block xyz per block.
        return 4 + 3 * self.num_block

    def _goal_size(self):
        return 3 * self.num_block

    def _distance(self):
        """Euclidean distance between the achieved (block) and desired goals (kuka_multi_step_base_env.py:340)."""
        achieved = [value for block in self._blocks for value in block]
        desired = [value for goal in self._desired_goal for value in goal]
        return math.sqrt(sum((float(a) - float(d)) ** 2 for a, d in zip(achieved, desired)))

    def _observation(self):
        """The non-image observation dict (kuka_multi_step_base_env.py:317-320), with placeholder values."""
        block_states = []
        policy_block_states = []
        for block, rpy in zip(self._blocks, self._block_rpy):
            relative = [self._ee[index] - block[index] for index in range(3)]
            zeros = [0.0, 0.0, 0.0]  # placeholder relative linear and angular velocities
            block_states.extend(list(block) + relative + list(rpy) + zeros + zeros)
            policy_block_states.extend(relative)
        state = ([self._ee[0], self._ee[1], self._ee[2], self._finger_closeness,
                  self._ee_velocity[0], self._ee_velocity[1], self._ee_velocity[2], self._finger_velocity]
                 + block_states)
        policy_state = ([self._ee[0], self._ee[1], self._ee[2], self._finger_closeness] + policy_block_states)
        achieved_goal = [value for block in self._blocks for value in block]
        desired_goal = [value for goal in self._desired_goal for value in goal]
        return {
            "observation": [max(-STATE_CLIP, min(STATE_CLIP, float(value))) for value in state],
            "policy_state": [max(-STATE_CLIP, min(STATE_CLIP, float(value))) for value in policy_state],
            "achieved_goal": [float(value) for value in achieved_goal],
            "desired_goal": [float(value) for value in desired_goal],
        }
