"""Fake backend of the MiniWorld Maze driver: a pure Python stand-in for ``miniworld.envs.maze:Maze``.

Why a fake: the real environment needs numpy, pyglet and an OpenGL context (a hidden pyglet window and frame
buffers are created in ``miniworld/miniworld.py:507-518``), and package code never imports the clone.  This module
re-implements the part of the environment that the ``cap.world.*`` contract carries: a kinematic agent on a flat
ground plane, the three movement actions, the sparse reward and the episode limit.  Public members are the ones
``MiniWorldEnv`` has (``reset``, ``step``, ``close``; gate G7), plus the two space objects the bridge reads
(``action_space``, ``observation_space``).

What this is not (all listed in the driver's fidelity ``gaps``):

* no rooms, walls or portals are generated and there is no collision detection;
* no 3D rendering, textures, lighting or occlusion: the observation is a small coarse RGB stand-in;
* the initial pose comes from Python's ``random.Random``, upstream uses gymnasium's numpy generator;
* the red box is placed a fixed distance ahead of the agent (placeholder test data) instead of a random room.

Numbers below are either cited constants of the clone or explicit ``# placeholder`` test data; nothing here talks to
a device.
"""

import math
import random

# miniworld/miniworld.py:453-457: the action enumeration of MiniWorldEnv
ACTION_TURN_LEFT = 0
ACTION_TURN_RIGHT = 1
ACTION_MOVE_FORWARD = 2
# miniworld/envs/maze.py:71: Maze allows Discrete(move_forward + 1), the three movement actions
ACTION_COUNT = ACTION_MOVE_FORWARD + 1
# miniworld/params.py:123-125: the defaults used when domain randomization is off
FORWARD_STEP = 0.15
TURN_STEP_DEG = 15.0
# miniworld/params.py:123-125: the upper bound of forward_step is the environment's max_forward_step
MAX_FORWARD_STEP = 0.17
# miniworld/entity.py:470: the agent's bounding radius
AGENT_RADIUS = 0.4
# miniworld/entity.py:391 and :402: the default Box size 0.8 gives a bounding radius of sqrt(2) * 0.8 / 2
BOX_RADIUS = math.sqrt(0.8 * 0.8 + 0.8 * 0.8) / 2
# miniworld/miniworld.py:975: near() compares the distance with both radii plus 1.1 * max_forward_step
NEAR_DISTANCE = BOX_RADIUS + AGENT_RADIUS + 1.1 * MAX_FORWARD_STEP
# miniworld/envs/maze.py:49, :54 and :58: the default grid, the gap and the episode length formula
DEFAULT_NUM_ROWS = 8
DEFAULT_NUM_COLS = 8
DEFAULT_ROOM_SIZE = 3.0
STEPS_PER_ROOM = 24
GAP_SIZE = 0.25
# miniworld/miniworld.py:473-474 and :489-491: the real observation is a 60 x 80 x 3 RGB image
REAL_OBS_HEIGHT = 60
REAL_OBS_WIDTH = 80
REAL_OBS_CHANNELS = 3
# placeholder: the fake returns a smaller coarse RGB stand-in (36 values) than the 60 x 80 x 3 camera image
FAKE_OBS_HEIGHT = 3
FAKE_OBS_WIDTH = 4
FAKE_OBS_CHANNELS = 3
# placeholder: the fake places the red box this far ahead of the agent instead of in a random room
BOX_AHEAD_METERS = 1.5
# placeholder: the bounds of the uniform initial position on the fake's open plane
SPAWN_MARGIN_METERS = 0.5
OBS_MAX = 255


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: one lower and one upper bound per flattened element."""

    def __init__(self, low, high, shape, dtype="uint8"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype

    def contains(self, value):
        try:
            flat = [float(item) for row in value for cell in row for item in cell]
        except TypeError:
            return False
        return len(flat) == len(self.low) and all(
            low <= item <= high for low, item, high in zip(self.low, flat, self.high))


def _dir_vec(angle):
    """``Entity.dir_vec`` (miniworld/entity.py:100-103): forward is (cos(dir), 0, -sin(dir))."""

    return math.cos(angle), -math.sin(angle)


class FakeMazeEnv:
    """``Maze`` without numpy or OpenGL: the upstream signatures and the same five-value step result shape."""

    def __init__(self, num_rows=DEFAULT_NUM_ROWS, num_cols=DEFAULT_NUM_COLS, room_size=DEFAULT_ROOM_SIZE,
                 max_episode_steps=None, **kwargs):
        self.num_rows = num_rows
        self.num_cols = num_cols
        self.room_size = room_size
        self.gap_size = GAP_SIZE
        # maze.py:58: max_episode_steps or num_rows * num_cols * 24
        self.max_episode_steps = max_episode_steps or num_rows * num_cols * STEPS_PER_ROOM
        # maze.py:71
        self.action_space = Discrete(ACTION_COUNT)
        # miniworld.py:488-491: the real space is (60, 80, 3); this one holds the smaller stand-in
        count = FAKE_OBS_HEIGHT * FAKE_OBS_WIDTH * FAKE_OBS_CHANNELS
        self.observation_space = Box([0] * count, [OBS_MAX] * count,
                                     (FAKE_OBS_HEIGHT, FAKE_OBS_WIDTH, FAKE_OBS_CHANNELS))
        self._rng = random.Random()
        self._span_x = (num_cols - 1) * (room_size + GAP_SIZE) + room_size
        self._span_z = (num_rows - 1) * (room_size + GAP_SIZE) + room_size
        self.step_count = 0
        self.agent_pos = [self._span_x / 2.0, 0.0, self._span_z / 2.0]
        self.agent_dir = 0.0
        self.box_pos = list(self.agent_pos)
        self.closed = False

    # -- gymnasium surface -------------------------------------------------
    def reset(self, *, seed=None, options=None):
        """miniworld.py:544-551: reset(seed, options) starts a new episode and re-seeds the generator."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self.step_count = 0
        # placeholder: a uniform start pose on the fake's open plane (upstream samples rooms and positions)
        x = self._rng.uniform(SPAWN_MARGIN_METERS, self._span_x - SPAWN_MARGIN_METERS)
        z = self._rng.uniform(SPAWN_MARGIN_METERS, self._span_z - SPAWN_MARGIN_METERS)
        self.agent_dir = self._rng.uniform(-math.pi, math.pi)      # miniworld.py:901
        self.agent_pos = [x, 0.0, z]
        forward_x, forward_z = _dir_vec(self.agent_dir)
        self.box_pos = [x + BOX_AHEAD_METERS * forward_x, 0.0, z + BOX_AHEAD_METERS * forward_z]
        return self._render_obs(), {}

    def step(self, action):
        """miniworld.py:670-730 plus maze.py:155-162: one movement action, then reward and termination."""
        self.step_count += 1
        if action == ACTION_MOVE_FORWARD:
            forward_x, forward_z = _dir_vec(self.agent_dir)
            self.agent_pos[0] += FORWARD_STEP * forward_x           # params.py:123; domain_rand off (miniworld.py:478)
            self.agent_pos[2] += FORWARD_STEP * forward_z
        elif action == ACTION_TURN_LEFT:
            self.agent_dir += math.radians(TURN_STEP_DEG)           # miniworld.py:688-689
        elif action == ACTION_TURN_RIGHT:
            self.agent_dir -= math.radians(TURN_STEP_DEG)           # miniworld.py:691-692
        # miniworld.py:719-724: the base step reports reward 0 and a truncation at the episode limit
        if self.step_count >= self.max_episode_steps:
            reward, termination, truncation = 0.0, False, True
        else:
            reward, termination, truncation = 0.0, False, False
        # maze.py:158-160: near the red box the sparse reward is added and the episode terminates
        if self._near_box():
            reward += 1.0 - 0.2 * (self.step_count / self.max_episode_steps)   # miniworld.py:1017
            termination = True
        return self._render_obs(), reward, termination, truncation, {}

    def close(self):
        """miniworld.py:1335-1338: release the environment (the fake has no window to close)."""
        self.closed = True

    # -- internals ---------------------------------------------------------
    def _near_box(self):
        distance = math.hypot(self.box_pos[0] - self.agent_pos[0], self.box_pos[2] - self.agent_pos[2])
        return distance < NEAR_DISTANCE                              # miniworld.py:974-975

    def _cell(self, x, z):
        column = min(FAKE_OBS_WIDTH - 1, max(0, int(x / self._span_x * FAKE_OBS_WIDTH)))
        row = min(FAKE_OBS_HEIGHT - 1, max(0, int(z / self._span_z * FAKE_OBS_HEIGHT)))
        return row, column

    def _render_obs(self):
        """A coarse top-down stand-in, not MiniWorld's rendered camera image (placeholder pixel layout)."""
        image = [[[0, 0, 0] for _ in range(FAKE_OBS_WIDTH)] for _ in range(FAKE_OBS_HEIGHT)]
        agent_row, agent_col = self._cell(self.agent_pos[0], self.agent_pos[2])
        box_row, box_col = self._cell(self.box_pos[0], self.box_pos[2])
        heading = int(((self.agent_dir % (2.0 * math.pi)) / (2.0 * math.pi)) * OBS_MAX)
        image[agent_row][agent_col] = [0, OBS_MAX, heading]
        image[box_row][box_col][0] = OBS_MAX
        return image
