"""Fake backend of the TactilePush-v1 driver: a pure Python stand-in for ``gym.make("TactilePush-v1")``.

Why a fake: the upstream environment needs ``redmax_py`` (DiffRedMax), numpy, scipy and torch, and the gate neither
installs nor imports the clone.  This module re-implements the small, readable part of
``envs.tactile_push_env:TactilePushEnv`` that the contract uses: the action space, the reset draws of the object and
the goal, the three-number state part of the observation, the reward arithmetic, the every-tenth-step external force
and the 100-step time limit that ``gym.make("TactilePush-v1")`` adds through its ``TimeLimit`` wrapper.  The tactile
array itself is a zero stand-in: the dense force field is what the upstream simulator computes and this file does not
model contacts.

The public members are the ones the upstream class and its in-clone base have (``reset``, ``step``, ``seed``; gate
G7).  Every rule and constant below cites the line of the clone at commit
0c42783a8b5cc7abe1a9fa3e6aa65e4aeb8eb670; numbers that are invented for the stand-in are marked ``# placeholder``.
The environment state is kept in plain Python scalars and lists, and nothing here talks to a device.
"""

import math
import random

# TactilePushEnv: the tactile map and the state part (envs/tactile_push_env.py:31-40)
TACTILE_ROWS = 13
TACTILE_COLS = 10
TACTILE_CHANNELS = 3
STATE_FIELDS = 3
# envs/tactile_push_env.py:69-70: three control inputs in [-1, 1]
ACTION_DIM = 3
ACTION_LOW = -1.0
ACTION_HIGH = 1.0
# envs/tactile_push_env.py:66-67 and envs/assets/pusher/pusher.xml:2: frame_skip 5 * 5e-3 s
FRAME_SKIP = 5
MODEL_TIMESTEP_S = 5e-3
TIMESTEP_S = FRAME_SKIP * MODEL_TIMESTEP_S
# envs/__init__.py:9-13: the TimeLimit wrapper of TactilePush-v1
MAX_EPISODE_STEPS = 100
# envs/tactile_push_env.py:136: the object y draw
RESET_OBJECT_Y_LOW, RESET_OBJECT_Y_HIGH = -0.02, 0.02
# envs/tactile_push_env.py:144: the goal x/y draw
RESET_GOAL_LOW = (0.15, -0.2)
RESET_GOAL_HIGH = (0.25, 0.2)
# envs/tactile_push_env.py:146: the goal rotation is a band of pi/16 around goal_y * pi
GOAL_ROT_BAND = math.pi / 16.0


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        return len(value) == len(self.low) and all(
            low <= float(item) <= high for item, low, high in zip(value, self.low, self.high))


class FakeTactilePushEnv:
    """A kinematic stand-in for ``TactilePushEnv``: reset draws, a three-number state and the reward arithmetic.

    The observation is the same shape as the upstream ``tactile_flatten`` mode: the three-number goal pose in the
    gripper frame followed by a 390-number tactile vector (3 x 13 x 10).  The tactile values are all zeros here; the
    object motion is a placeholder kinematic response to the action rather than a contact simulation.
    """

    def __init__(self, use_torch=False, gradient=False, observation_type="tactile_flatten", render_tactile=False,
                 verbose=False, seed=0):
        self.observation_type = observation_type
        self.use_torch = use_torch
        self.verbose = verbose
        self.render_tactile = render_tactile
        self.tactile_rows = TACTILE_ROWS
        self.tactile_cols = TACTILE_COLS
        # envs/tactile_push_env.py:34-36: tactile_flatten is one vector of rows*cols*3, plus three state numbers
        self.tactile_obs_shape = (TACTILE_ROWS * TACTILE_COLS * TACTILE_CHANNELS,)
        self.state_obs_shape = (STATE_FIELDS,)
        self.tactile_force_buf = self._zero_tactile()
        self.tactile_obs_buf = self._zero_flat_tactile()
        self.state_q = [0.0] * 7                       # placeholder initial q (upstream reads sim.get_q_init())
        self.goal = [0.0, 0.0, 0.0]
        self.reward_buf = 0.0
        self.done_buf = False
        self.info_buf = {}
        self.external_force = [0.0, 0.0]
        self.current_step = 0
        self.frame_skip = FRAME_SKIP
        self.dt = TIMESTEP_S                          # the bridge derives fidelity.timestep_ms from this value
        self.ndof_u = ACTION_DIM
        self.action_space = Box([ACTION_LOW] * ACTION_DIM, [ACTION_HIGH] * ACTION_DIM)
        # envs/redmax_torch_env.py:18-29: a flat observation becomes a Box; the values are placeholders here.
        self.observation_space = Box([-math.inf] * (STATE_FIELDS + TACTILE_ROWS * TACTILE_COLS * TACTILE_CHANNELS),
                                     [math.inf] * (STATE_FIELDS + TACTILE_ROWS * TACTILE_COLS * TACTILE_CHANNELS))
        self._tick = 0
        self._seed = 0
        self._rng = random.Random()
        self.seed(seed)

    @staticmethod
    def _zero_tactile():
        return [[[0.0 for _ in range(TACTILE_COLS)] for _ in range(TACTILE_ROWS)]
                for _ in range(TACTILE_CHANNELS)]     # placeholder tactile field

    @staticmethod
    def _zero_flat_tactile():
        return [0.0] * (TACTILE_ROWS * TACTILE_COLS * TACTILE_CHANNELS)   # placeholder tactile vector

    def seed(self, seed=None):
        """``RedMaxTorchEnv.seed`` (envs/redmax_torch_env.py:48-50), with Python's generator in place of numpy's."""
        if seed is None:
            seed = 0
        self._seed = int(seed)
        self._rng = random.Random(self._seed)
        return [self._seed]

    def reset(self):
        """The reset draws of ``TactilePushEnv.reset`` (envs/tactile_push_env.py:133-172)."""
        self.state_q = [0.0] * 7                       # placeholder initial q
        self.state_q[1] = -0.001                     # envs/tactile_push_env.py:135
        self.state_q[4] = self._rng.uniform(RESET_OBJECT_Y_LOW, RESET_OBJECT_Y_HIGH)   # :136
        self.robot_rot_prev = 0.0
        self.goal = [0.0, 0.0, 0.0]
        goal_x = self._rng.uniform(RESET_GOAL_LOW[0], RESET_GOAL_HIGH[0])              # :144
        goal_y = self._rng.uniform(RESET_GOAL_LOW[1], RESET_GOAL_HIGH[1])
        self.goal[0], self.goal[1] = goal_x, goal_y
        self.goal[2] = self._rng.uniform(goal_y * math.pi - GOAL_ROT_BAND,
                                         goal_y * math.pi + GOAL_ROT_BAND)             # :146
        self.prev_error_pos = [self.state_q[3] - self.goal[0], self.state_q[4] - self.goal[1]]
        self.prev_error_rot = self.state_q[6] - self.goal[2]
        self.tactile_force_buf = self._zero_tactile()  # placeholder: the upstream reads sim.get_tactile_force_vector()
        self.tactile_obs_buf = self._zero_flat_tactile()
        self.external_force = [0.0, 0.0]
        self.current_step = 0
        self.reward_buf = 0.0
        self.done_buf = False
        self.info_buf = {}
        self._tick = 0
        return self._get_obs()

    def _get_obs(self):
        """``TactilePushEnv._get_obs`` in ``tactile_flatten`` mode (envs/tactile_push_env.py:72-125)."""
        self.tactile_obs_buf = [value for channel in self.tactile_force_buf for row in channel for value in row]
        gripper_rot = self.state_q[0]
        gripper_pos = self.state_q[1:3]
        goal_pos = self.goal[0:2]
        goal_rot = self.goal[2]
        c, s = math.cos(-gripper_rot), math.sin(-gripper_rot)
        goal_x = c * goal_pos[0] - s * goal_pos[1] - gripper_pos[0]
        goal_y = s * goal_pos[0] + c * goal_pos[1] - gripper_pos[1]
        state = [goal_x, goal_y, goal_rot - gripper_rot]
        # envs/tactile_push_env.py:114-119: torch.cat([state_obs_buf, tactile_obs_buf])
        return state + self.tactile_obs_buf

    def step(self, u):
        """A kinematic step with the reward arithmetic and the 100-step limit of ``TactilePush-v1``.

        Upstream ``StepSimFunction`` advances the contact simulation; this stand-in moves the object by a fixed
        placeholder gain of the tanh action and the sampled external force.  The returned five-tuple mirrors what
        ``gym.make`` returns after its ``TimeLimit`` wrapper, so ``truncated`` is carried separately from
        ``terminated`` (the upstream ``step`` itself never reports done, :232).
        """
        values = [float(item) for item in u]
        action = [math.tanh(item) for item in values]  # envs/tactile_push_env.py:175-177
        if self.current_step % 10 == 0:                # :184-190
            if self._rng.uniform(0.0, 1.0) < 0.5:
                self.external_force = [self._rng.uniform(-1.0, 1.0), self._rng.uniform(-1.0, 1.0)]
            else:
                self.external_force = [0.0, 0.0]
        self.state_q[0] += action[2] * 0.05                                     # placeholder gain (gripper rotation)
        self.state_q[1] += action[0] * 0.01                                     # placeholder gain (gripper x)
        self.state_q[2] += action[1] * 0.01                                     # placeholder gain (gripper y)
        self.state_q[3] += action[0] * 0.01 + self.external_force[0] * 0.001   # placeholder gains
        self.state_q[4] += action[1] * 0.01 + self.external_force[1] * 0.001   # placeholder gains
        self.state_q[6] += action[2] * 0.05                                     # placeholder gain
        self.current_step += 1
        self._tick += 1

        object_pos = self.state_q[3:5]
        object_rot = self.state_q[6]
        reward_pos = -((object_pos[0] - self.goal[0]) / 0.01) ** 2 * 0.01 \
            - ((object_pos[1] - self.goal[1]) / 0.01) ** 2 * 0.01             # :206
        reward_rot = -(((object_rot - self.goal[2]) / (math.pi / 36.0)) ** 2) * 0.1   # :207
        reward_touch = 0.0                          # placeholder: no contact model, var is not simulated
        reward_action = -sum(item * item for item in values) * 0.1            # :209
        reward = reward_pos + reward_rot + reward_touch + reward_action       # :211
        self.reward_buf = reward
        self.info_buf = {
            "reward_pos": reward_pos,
            "reward_rot": reward_rot,
            "reward_touch": reward_touch,
            "reward_action": reward_action,
            "final_pos_error": math.hypot(object_pos[0] - self.goal[0], object_pos[1] - self.goal[1]),
            "final_rot_error": abs(object_rot - self.goal[2]),
        }                                                                     # :216-223
        obs = self._get_obs()
        truncated = self._tick >= MAX_EPISODE_STEPS  # envs/__init__.py:12, applied by gym.make's TimeLimit
        return obs, reward, self.done_buf, truncated, dict(self.info_buf)
