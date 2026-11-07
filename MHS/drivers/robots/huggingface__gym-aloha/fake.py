"""Fake backend of the gym-aloha driver: a pure Python stand-in for ``gym_aloha.env:AlohaEnv``.

Why a fake: the acceptance gate runs where the upstream package cannot be imported (``gym_aloha`` needs MuJoCo and a
GL context, ``pyproject.toml:26-28``), and package code never imports the clone.  This module re-implements the parts
of ``AlohaEnv`` the bridge drives -- ``reset``, ``step`` and ``close``, with the action and observation spaces derived
from the same constants as the upstream (gate G7 checks the public surface against the class in the clone).  Every
constant below cites the line of the clone at the pinned commit
bd3325740ea8d1c97411c41ea1e0f4ce0a7de8da.  The public members are the ones ``AlohaEnv`` has; the space classes
duck-type ``gymnasium.spaces.Box`` and ``Dict`` (the bridge reads ``low``, ``high``, ``shape`` and ``spaces``).

What this is not (all of it is listed in the fidelity ``gaps`` of driver.py):

* there is no MuJoCo physics: the commanded joint targets become the state, nothing is integrated and no contact is
  computed.  The upstream reward is a contact predicate (``gym_aloha/tasks/sim.py:174-219``), so this fake always
  returns reward 0 and never reaches ``terminated``;
* the image is a small uniform stand-in, not a camera render: the upstream renders 480 x 640 x 3 pixels
  (``gym_aloha/tasks/sim.py:92``) and this fake returns 4 x 6 x 3 (``_IMAGE_HEIGHT`` and ``_IMAGE_WIDTH``, both
  placeholders);
* the object poses are drawn with Python's ``random.Random``; upstream draws them with numpy's ``RandomState``
  (``gym_aloha/utils.py:9`` and ``:24``), so one seed gives different poses on the two.

Nothing here talks to a device.
"""

import random

# gym_aloha/constants.py:29-47: the ACTIONS order, six arm joints and one normalized gripper per arm
ACTIONS = [
    "left_arm_waist",
    "left_arm_shoulder",
    "left_arm_elbow",
    "left_arm_forearm_roll",
    "left_arm_wrist_angle",
    "left_arm_wrist_rotate",
    "left_arm_gripper",
    "right_arm_waist",
    "right_arm_shoulder",
    "right_arm_elbow",
    "right_arm_forearm_roll",
    "right_arm_wrist_angle",
    "right_arm_wrist_rotate",
    "right_arm_gripper",
]
ARM_JOINTS = 6                      # six joint values per arm (gym_aloha/tasks/sim.py:16-20)
# gym_aloha/env.py:86: the action space is Box(low=-1, high=1, shape=(len(ACTIONS),), dtype=float32)
ACTION_LOW, ACTION_HIGH = -1, 1
# gym_aloha/env.py:30-31 and :56-59: 640 wide, 480 high, three channels, values 0 to 255
OBSERVATION_WIDTH, OBSERVATION_HEIGHT = 640, 480
PIXEL_LOW, PIXEL_HIGH = 0, 255
# gym_aloha/env.py:77-82: the agent position is bounded by -1000.0 and 1000.0
AGENT_POS_LOW, AGENT_POS_HIGH = -1000.0, 1000.0
# gym_aloha/constants.py:50-67: the start qpos -- waist, shoulder, elbow, forearm roll, wrist angle, wrist rotate and
# the two finger positions -- for the left arm and then for the right arm
START_ARM_POSE = [
    0,
    -0.96,
    1.16,
    0,
    -0.3,
    0,
    0.02239,
    -0.02239,
    0,
    -0.96,
    1.16,
    0,
    -0.3,
    0,
    0.02239,
    -0.02239,
]
# gym_aloha/constants.py:74-75: the puppet gripper position at open and at closed
PUPPET_GRIPPER_POSITION_OPEN = 0.05800
PUPPET_GRIPPER_POSITION_CLOSE = 0.01844
# gym_aloha/utils.py:20-22 (peg) and :33-35 (socket): the uniform ranges of the two object positions
PEG_RANGES = ((0.1, 0.2), (0.4, 0.6), (0.05, 0.05))
SOCKET_RANGES = ((-0.2, -0.1), (0.4, 0.6), (0.05, 0.05))
# gym_aloha/__init__.py:3-11: AlohaInsertion-v0 is registered with max_episode_steps=300, which gymnasium.make()
# applies as a TimeLimit wrapper; it is the only episode bound, since AlohaEnv itself uses time_limit infinity
# (gym_aloha/env.py:109-110)
MAX_EPISODE_STEPS = 300
# placeholder: the stand-in image is 4 x 6 x 3; the upstream render is 480 x 640 x 3 (gym_aloha/tasks/sim.py:92)
_IMAGE_HEIGHT = 4
_IMAGE_WIDTH = 6
_IMAGE_CHANNELS = 3
# placeholder: the three channels of that uniform image are the peg x, y and z scaled, modulo 256
_IMAGE_LEVEL_SCALE = 1000
_IMAGE_LEVEL_MODULUS = 256


def normalize_puppet_gripper_position(x):
    """``gym_aloha/constants.py:94-97``: the finger position as a fraction, 0 closed and 1 open."""

    return (x - PUPPET_GRIPPER_POSITION_CLOSE) / (PUPPET_GRIPPER_POSITION_OPEN - PUPPET_GRIPPER_POSITION_CLOSE)


def unnormalize_puppet_gripper_position(x):
    """``gym_aloha/constants.py:104-105``: the inverse of the normalization above."""

    return x * (PUPPET_GRIPPER_POSITION_OPEN - PUPPET_GRIPPER_POSITION_CLOSE) + PUPPET_GRIPPER_POSITION_CLOSE


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: ``low``, ``high``, ``shape`` and ``dtype`` (what the bridge reads)."""

    def __init__(self, low, high, shape=(), dtype="float32"):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the member spaces by name, nested members included."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None
        self.dtype = None


class FakeAlohaEnv:
    """``AlohaEnv`` without MuJoCo: ``reset(seed, options)`` and ``step(action)`` return what the upstream returns."""

    # gym_aloha/env.py:23
    metadata = {"render_modes": ["rgb_array"], "render_fps": 50}

    def __init__(self, task="insertion", obs_type="pixels_agent_pos", render_mode="rgb_array",
                 observation_width=640, observation_height=480, visualization_width=640,
                 visualization_height=480):
        # The upstream signature has no default for task and uses obs_type="pixels" (gym_aloha/env.py:25-34).  The
        # driver's backend factory passes no options, so these defaults carry the configuration the driver declares
        # in env_kwargs: the insertion task with the pixels_agent_pos observation.  README.md:95 documents both
        # obs_type values; gym_aloha/__init__.py:10 registers the pixels default.
        if task not in ("insertion", "transfer_cube"):
            raise NotImplementedError(task)
        if obs_type not in ("pixels", "pixels_agent_pos"):
            raise NotImplementedError(obs_type)
        self.task = task
        self.obs_type = obs_type
        self.render_mode = render_mode
        self.observation_width = observation_width
        self.observation_height = observation_height
        self.visualization_width = visualization_width
        self.visualization_height = visualization_height
        # gym_aloha/env.py:53-84: the observation space of obs_type pixels_agent_pos
        top = Box(PIXEL_LOW, PIXEL_HIGH,
                  (observation_height, observation_width, _IMAGE_CHANNELS), "uint8")
        if obs_type == "pixels":                                # gym_aloha/env.py:53-63
            self.observation_space = Dict({"top": top})
        else:                                                   # gym_aloha/env.py:64-84
            self.observation_space = Dict({
                "pixels": Dict({"top": top}),
                "agent_pos": Box(AGENT_POS_LOW, AGENT_POS_HIGH, (len(ACTIONS),), "float64"),
            })
        # gym_aloha/env.py:86: Box(low=-1, high=1, shape=(len(ACTIONS),)) -- gymnasium broadcasts the two scalars to
        # one bound per element, which is the form written here
        self.action_space = Box([ACTION_LOW] * len(ACTIONS), [ACTION_HIGH] * len(ACTIONS), (len(ACTIONS),), "float32")
        self._qpos = list(START_ARM_POSE)
        self._peg = [0.0, 0.0, 0.0]
        self._socket = [0.0, 0.0, 0.0]
        self._ticks = 0

    def reset(self, *, seed=None, options=None):
        """``gym_aloha/env.py:150-171``: seed the sampler, draw the object poses, start a new episode."""

        # gym_aloha/env.py:150 accepts options and never reads them
        # gym_aloha/utils.py:24 and :37: one RandomState per object, both seeded with the same seed
        peg_rng = random.Random(seed)
        socket_rng = random.Random(seed)
        self._peg = [peg_rng.uniform(low, high) for low, high in PEG_RANGES]
        self._socket = [socket_rng.uniform(low, high) for low, high in SOCKET_RANGES]
        self._qpos = list(START_ARM_POSE)          # gym_aloha/tasks/sim.py:113 and :162
        self._ticks = 0
        return self._observation(), {"is_success": False}       # gym_aloha/env.py:168-171

    def step(self, action):
        """``gym_aloha/env.py:173-187`` and the 300-step TimeLimit that gymnasium.make() adds."""

        values = [float(value) for value in action]     # gym_aloha/env.py:174 asserts a one-dimensional action
        if len(values) != len(ACTIONS):
            raise AssertionError(f"{len(values)} action values, expected {len(ACTIONS)}")
        left_arm = values[:ARM_JOINTS]
        right_arm = values[ARM_JOINTS + 1:2 * ARM_JOINTS + 1]
        left_gripper = unnormalize_puppet_gripper_position(values[ARM_JOINTS])              # sim.py:44
        right_gripper = unnormalize_puppet_gripper_position(values[2 * ARM_JOINTS + 1])     # sim.py:45
        # gym_aloha/tasks/sim.py:47-52: a finger pair is the gripper position and its negation, and the arm joints
        # take the commanded absolute targets.  Without the physics engine the commanded position becomes the state.
        self._qpos = (list(left_arm) + [left_gripper, -left_gripper]
                      + list(right_arm) + [right_gripper, -right_gripper])
        self._ticks += 1
        # gym_aloha/tasks/sim.py:174-219: the reward counts contact pairs and needs the physics engine, which this
        # fake does not run, so no grasp and no insertion can be observed here.
        reward = 0.0
        terminated = False                                  # gym_aloha/env.py:180
        truncated = self._ticks >= MAX_EPISODE_STEPS        # gym_aloha/__init__.py:6, the TimeLimit of make()
        return self._observation(), reward, terminated, truncated, {"is_success": terminated}

    def close(self):
        """``gym_aloha/env.py:189-190``: the upstream close does nothing, so neither does this one."""

        return None

    # -- helpers (private: gate G7 checks the public surface against AlohaEnv) --------------------------------
    def _observation(self):
        image = self._image()
        if self.obs_type == "pixels":
            return {"top": image}                                   # gym_aloha/env.py:141-142
        return {"pixels": {"top": image}, "agent_pos": self._agent_pos()}   # gym_aloha/env.py:143-147

    def _agent_pos(self):
        """``gym_aloha/tasks/sim.py:60-69``: the arm joints and the normalized gripper position of each arm."""

        left, right = self._qpos[:8], self._qpos[8:16]
        return (list(left[:ARM_JOINTS]) + [normalize_puppet_gripper_position(left[ARM_JOINTS])]
                + list(right[:ARM_JOINTS]) + [normalize_puppet_gripper_position(right[ARM_JOINTS])])

    def _image(self):
        # placeholder: uniform pixels that follow the sampled peg position, one channel per coordinate, so that a
        # seeded reset changes the observation.  This is not a picture of the scene; the upstream renders
        # 480 x 640 x 3 (gym_aloha/tasks/sim.py:92).
        levels = [int(round(value * _IMAGE_LEVEL_SCALE)) % _IMAGE_LEVEL_MODULUS for value in self._peg]
        pixel = [levels[channel % len(levels)] for channel in range(_IMAGE_CHANNELS)]
        return [[list(pixel) for _ in range(_IMAGE_WIDTH)] for _ in range(_IMAGE_HEIGHT)]
