"""Fake backend of the MiniGrid driver: a pure Python stand-in for ``minigrid.envs:BlockedUnlockPickupEnv``.

Why a fake: the acceptance gate runs without gymnasium, pygame and numpy (the upstream requirements), and package code
never imports the clone.  This module re-implements the world of ``BlockedUnlockPickupEnv``
(minigrid/envs/blockedunlockpickup.py) and the turn mechanics of ``MiniGridEnv`` (minigrid/minigrid_env.py) in plain
Python.  Every constant cites the line of the clone at the pinned commit (b34a5755dbef71e3f1662552259a94b255c1a8bb).
The public members are the ones the upstream class has (``reset``, ``step``, ``close``; gate G7), and the space
classes duck-type ``gymnasium.spaces.Discrete``, ``Box`` and ``Dict`` (the bridge reads ``n``, ``start``, ``low``,
``high``, ``shape`` and ``spaces`` by class name).

Differences from the upstream environment, all also listed in the fidelity ``gaps`` of the driver:

* the world is one fixed two-room layout built from the upstream constants, not a freshly generated RoomGrid;
* the view is fully visible (no occlusion, no partial observability), so the image is the whole agent window;
* the mission colour comes from Python's ``random.Random(seed)``, upstream draws it from numpy's generator;
* there is no rendering and no ``get_state``/``set_state``.

Nothing here talks to a device.
"""

import random

# minigrid/core/constants.py:17-46
COLOR_NAMES = ["blue", "green", "grey", "purple", "red", "yellow"]           # sorted(COLORS) (constants.py:17)
COLOR_TO_IDX = {"red": 0, "green": 1, "blue": 2, "purple": 3, "yellow": 4, "grey": 5}   # constants.py:20
OBJECT_TO_IDX = {"unseen": 0, "empty": 1, "wall": 2, "floor": 3, "door": 4, "key": 5, "ball": 6, "box": 7,
                 "goal": 8, "lava": 9, "agent": 10}                          # constants.py:25-37
STATE_TO_IDX = {"open": 0, "closed": 1, "locked": 2}                         # constants.py:42-46
DIR_TO_VEC = [(1, 0), (0, 1), (-1, 0), (0, -1)]                              # constants.py:49-57

# minigrid/minigrid_env.py:42 and minigrid/envs/blockedunlockpickup.py:72-83
AGENT_VIEW_SIZE = 7
ROOM_SIZE, NUM_ROWS, NUM_COLS = 6, 1, 2
WIDTH = (ROOM_SIZE - 1) * NUM_COLS + 1                                      # minigrid/core/roomgrid.py:90
HEIGHT = (ROOM_SIZE - 1) * NUM_ROWS + 1                                     # minigrid/core/roomgrid.py:89
MAX_STEPS = 16 * ROOM_SIZE ** 2                                             # blockedunlockpickup.py:72-74

#: The seven actions of minigrid/core/actions.py:6-23.
LEFT, RIGHT, FORWARD, PICKUP, DROP, TOGGLE, DONE = 0, 1, 2, 3, 4, 5, 6


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
    """Duck-typed ``gymnasium.spaces.Box``: the agent view is a 7 x 7 x 3 uint8 image."""

    def __init__(self, low, high, shape):
        count = 1
        for item in shape:
            count *= int(item)
        self.low = [float(low)] * count
        self.high = [float(high)] * count
        self.shape = tuple(int(item) for item in shape)
        self.dtype = "uint8"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: named observation fields."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class _MissionSpace:
    """Duck-typed ``minigrid.core.mission:MissionSpace``: the mission strings of one environment."""

    def __init__(self, values):
        self.values = list(values)

    def sample(self):
        return self.values[0]


class _Object:
    """One world object, encoded like ``minigrid/core/world_object.py`` encodes a tile."""

    def __init__(self, kind, color=None, state=None):
        self.kind, self.color, self.state = kind, color, state

    def can_overlap(self):
        return self.kind == "door" and self.state == "open"

    def can_pickup(self):
        return self.kind in ("key", "ball", "box")


class FakeBlockedUnlockPickupEnv:
    def __init__(self, **_options):
        self.action_space = Discrete(7)                                     # minigrid_env.py:63
        self.observation_space = Dict({                                     # minigrid_env.py:78-83
            "image": Box(0, 255, (AGENT_VIEW_SIZE, AGENT_VIEW_SIZE, 3)),
            "direction": Discrete(4),
            "mission": _MissionSpace(["pick up the red box"]),
        })
        self.max_steps = MAX_STEPS
        self.width, self.height = WIDTH, HEIGHT
        self._rng = random.Random()
        self.step_count = 0
        self.agent_pos = (1, 3)                                             # placeholder position
        self.agent_dir = 0                                                  # facing right (constants.py:49-51)
        self.carrying = None
        self.mission = "pick up the red box"                                # placeholder mission text
        self._grid = {}
        self._target = None

    # -- the environment contract ---------------------------------------------------------------------------
    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._build_grid()
        self.step_count = 0
        self.carrying = None
        return self._gen_obs(), {}

    def step(self, action):
        if action not in (LEFT, RIGHT, FORWARD, PICKUP, DROP, TOGGLE, DONE):
            raise ValueError(f"Unknown action: {action}")                   # minigrid_env.py:585-586
        self.step_count += 1
        reward, terminated, truncated = 0.0, False, False
        if action == LEFT:
            self.agent_dir = (self.agent_dir - 1) % 4                       # minigrid_env.py:539-542
        elif action == RIGHT:
            self.agent_dir = (self.agent_dir + 1) % 4                       # minigrid_env.py:544-546
        elif action == FORWARD:
            front = self._front_pos()
            cell = self._grid.get(front)
            if cell is None or cell.can_overlap():                          # minigrid_env.py:551-553
                self.agent_pos = front
        elif action == PICKUP:
            front = self._front_pos()
            cell = self._grid.get(front)
            if cell is not None and cell.can_pickup() and self.carrying is None:   # minigrid_env.py:561-566
                self.carrying = cell
                del self._grid[front]
        elif action == DROP:
            front = self._front_pos()
            if self._grid.get(front) is None and self.carrying is not None:  # minigrid_env.py:569-573
                self._grid[front] = self.carrying
                self.carrying = None
        elif action == TOGGLE:
            front = self._front_pos()
            cell = self._grid.get(front)
            if cell is not None and cell.kind == "door":                    # minigrid_env.py:576-578
                self._toggle_door(cell)
        if action == PICKUP and self.carrying is not None and self.carrying is self._target:
            reward = 1 - 0.9 * (self.step_count / self.max_steps)           # minigrid_env.py:245
            terminated = True                                               # blockedunlockpickup.py:110-113
        if self.step_count >= self.max_steps:                               # minigrid_env.py:587-588
            truncated = True
        return self._gen_obs(), reward, terminated, truncated, {}

    def close(self):
        self._grid = {}

    # -- the world -------------------------------------------------------------------------------------------
    def _build_grid(self):
        self._grid = {}
        for x in range(WIDTH):
            for y in (0, HEIGHT - 1):
                self._grid[(x, y)] = _Object("wall")
        for y in range(HEIGHT):
            for x in (0, WIDTH - 1):
                self._grid[(x, y)] = _Object("wall")
        for y in range(1, HEIGHT - 1):
            self._grid[(5, y)] = _Object("wall")                            # the wall between the two rooms
        door_color = self._rng.choice(COLOR_NAMES)                          # placeholder colour drawn from the seed
        ball_color = self._rng.choice(COLOR_NAMES)                          # placeholder colour (line 97)
        box_color = self._rng.choice(COLOR_NAMES)                           # placeholder colour (line 93)
        self._grid[(5, 3)] = _Object("door", color=door_color, state="locked")   # blockedunlockpickup.py:95
        self._grid[(4, 3)] = _Object("ball", color=ball_color)              # the ball that blocks the door (line 98)
        self._grid[(2, 2)] = _Object("key", color=door_color)               # the key for that door (line 100)
        self._target = _Object("box", color=box_color)                      # the target box (line 93)
        self._grid[(8, 3)] = self._target
        self.agent_pos, self.agent_dir = (1, 3), 0                          # placeholder start (line 102)
        self.mission = f"pick up the {box_color} box"                       # blockedunlockpickup.py:105

    def _front_pos(self):
        dx, dy = DIR_TO_VEC[self.agent_dir]
        return self.agent_pos[0] + dx, self.agent_pos[1] + dy

    def _toggle_door(self, door):
        if door.state == "locked":
            if (self.carrying is not None and self.carrying.kind == "key"
                    and self.carrying.color == door.color):
                door.state = "open"
                self.carrying = None
        elif door.state == "closed":
            door.state = "open"
        else:
            door.state = "closed"

    def _encode(self, obj):
        if obj is None:
            return [OBJECT_TO_IDX["empty"], 0, 0]
        state = STATE_TO_IDX.get(obj.state, 0) if obj.state is not None else 0
        return [OBJECT_TO_IDX[obj.kind], COLOR_TO_IDX.get(obj.color, 0), state]

    def _gen_obs(self):
        """The agent's view, rotated so that forward is up (minigrid_env.py:625-640, simplified: no occlusion)."""
        half = AGENT_VIEW_SIZE // 2
        forward = DIR_TO_VEC[self.agent_dir]
        side = DIR_TO_VEC[(self.agent_dir + 1) % 4]
        image = []
        for row in range(AGENT_VIEW_SIZE):
            distance = AGENT_VIEW_SIZE - 1 - row
            line = []
            for col in range(AGENT_VIEW_SIZE):
                offset = col - half
                x = self.agent_pos[0] + forward[0] * distance + side[0] * offset
                y = self.agent_pos[1] + forward[1] * distance + side[1] * offset
                if distance == 0 and offset == 0:
                    line.append(self._encode(self.carrying))
                elif 0 <= x < WIDTH and 0 <= y < HEIGHT:
                    line.append(self._encode(self._grid.get((x, y))))
                else:
                    line.append([OBJECT_TO_IDX["unseen"], 0, 0])
            image.append(line)
        return {"image": image, "direction": self.agent_dir, "mission": self.mission}
