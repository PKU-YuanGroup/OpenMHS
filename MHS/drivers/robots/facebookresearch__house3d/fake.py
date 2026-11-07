"""Fake backend of the House3D driver: a pure Python stand-in for ``House3D.roomnav.RoomNavTask``.

Why a fake: the upstream task cannot be imported or run here.  ``House3D.roomnav`` imports the compiled
``objrender`` pybind extension (``House3D/roomnav.py:18``), and even a built extension needs SUNCG house data, a
``config.json`` and OpenCV (``INSTRUCTION.md:59-63``).  Package code never imports the clone, so this module
re-implements the *interface* of ``RoomNavTask`` -- ``reset`` and ``step`` returning observations, rewards and the
info dictionary -- on a small kinematic grid.  Gate G7 checks that every public member defined here exists on
``RoomNavTask``; the members are ``reset``, ``step`` and the ``info`` property.

What this is not: the upstream environment.  There is no renderer, no SUNCG house, no semantic or depth image and
no learned reward.  The observation is a reduced 4x4x4 array (the real shape is ``(120, 90, 4)`` at the default
resolution named in ``House3D/roomnav.py:58`` and computed in ``:119-127``); the success test uses a distance
threshold instead of the pixel count of ``:57-60``; and the reward omits the delta/speed/indicator shaping of
``:324-345``.  The driver's fidelity ``gaps`` and ``RESULT.json`` state all of this.

Numbers taken from the upstream code are named with the line they come from.  Numbers that only configure this
stand-in (grid extent, reduced observation size, start cells, yaw choices) are marked ``# placeholder``.
"""

import math
import random

# House3D/roomnav.py:50-54: the 13 entries of discrete_actions, in order.
DISCRETE_ACTIONS = (
    (1.0, 0.0, 0.0),      # 0 forward
    (0.0, 1.0, 0.0),      # 1 left
    (0.0, -1.0, 0.0),     # 2 right
    (0.5, 0.5, 0.0),      # 3 left-forward
    (0.5, -0.5, 0.0),     # 4 right-forward
    (0.0, 0.0, 1.0),      # 5 rotate left
    (0.0, 0.0, -1.0),     # 6 rotate right
    (-0.4, 0.0, 0.0),     # 7 backward
    (0.4, 0.0, 0.0),      # 8 small forward
    (0.0, 0.4, 0.0),      # 9 small left
    (0.0, -0.4, 0.0),     # 10 small right
    (0.0, 0.0, 0.4),      # 11 small rotate left
    (0.0, 0.0, -0.4),     # 12 small rotate right
)
# House3D/roomnav.py:45-46
ROTATION_SENSITIVITY = 30.0
MOVE_SENSITIVITY = 0.5
# House3D/roomnav.py:40-42
SUCCESS_DISTANCE_RANGE = 1.0
SUCCESS_SEE_TARGET_TIME_STEPS = 2
# House3D/roomnav.py:30-34
COLLISION_PENALTY_REWARD = 0.3
STAY_ROOM_REWARD = 0.1
SUCCESS_REWARD = 10.0

# The real observation size: the default resolution 120 x 90 (roomnav.py:58) with segment_input=True (3 base
# channels), joint_visual_signal=False and depth_signal=True (+1) (roomnav.py:82-84, 119-127).
REAL_OBSERVATION_SHAPE = (120, 90, 4)
# placeholder: the stand-in returns a 4 x 4 x 4 coarse map so every receipt stays small.
OBSERVATION_SIDE = 4
# placeholder: the stand-in world is a 5 x 5 grid of unit cells.
GRID_MAX = 4
# placeholder: birth cells and yaw choices used by reset(); the upstream choice is random over the house.
START_CELLS = ((0, 0), (0, 2), (2, 0), (2, 2), (4, 0))
YAWS = (0.0, 90.0, 180.0, 270.0)
# placeholder: target cell of the stand-in; the upstream target is a room type chosen by reset_target().
TARGET_CELL = (4, 4)
# House3D/roomnav.py:85: max_steps defaults to -1, which disables the cut-off.
MAX_STEPS_DEFAULT = -1


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed ``gym.spaces.Box``: scalar bounds broadcast to every element of ``shape``."""

    def __init__(self, low, high, shape):
        self.shape = tuple(int(item) for item in shape)
        count = 1
        for item in self.shape:
            count *= item
        self.low = [low] * count
        self.high = [high] * count
        self.dtype = "uint8"


class FakeRoomNavTask:
    """``RoomNavTask`` with ``discrete_action=True`` on a small kinematic grid.

    ``reset(seed, options)`` and ``step(action)`` match the Gymnasium bridge's call shapes; the upstream
    ``RoomNavTask.reset`` takes only ``target`` and seeds in the constructor (``House3D/roomnav.py:77-87, 215``),
    so the seed argument is the bridge's convention, not the upstream signature.
    """

    def __init__(self, **_options):
        self.segment_input = True
        self.joint_visual_signal = False
        self.depth_signal = True
        self.discrete_action = True
        self.move_sensitivity = MOVE_SENSITIVITY
        self.rot_sensitivity = ROTATION_SENSITIVITY
        self.max_steps = MAX_STEPS_DEFAULT
        self.success_measure = "see"
        self.resolution = (120, 90)   # roomnav.py:58 names the default resolution used by the pixel criteria
        self._observation_space = Box(0, 255, REAL_OBSERVATION_SHAPE)
        self._action_space = Discrete(len(DISCRETE_ACTIONS))
        # The bridge reads action_space and observation_space as the environment's spaces (RoomNavTask exposes
        # them as properties at roomnav.py:361-367).
        self.action_space = self._action_space
        self.observation_space = self._observation_space
        self._rng = random.Random()
        self._x = 0.0
        self._y = 0.0
        self._yaw = 0.0
        self._target = TARGET_CELL
        self.current_episode_step = 0
        self.success_stay_cnt = 0
        self.collision_flag = False
        self.last_info = None
        self.last_obs = None

    @property
    def info(self):
        """The members of ``RoomNavTask.info`` (roomnav.py:370-378) that the stand-in can report."""
        gx = int(round(self._x))
        gy = int(round(self._y))
        distance = math.hypot(self._x - self._target[0], self._y - self._target[1])
        yaw_rad = math.radians(self._yaw)
        return {
            "house_id": 0,
            "loc": [self._x, self._y],
            "yaw": self._yaw,
            "grid": [gx, gy],
            "front": [round(math.cos(yaw_rad), 6), round(math.sin(yaw_rad), 6)],
            "right": [round(math.sin(yaw_rad), 6), round(-math.cos(yaw_rad), 6)],
            "dist": distance,
            "scaled_dist": distance,
            "optsteps": int(math.ceil(distance / MOVE_SENSITIVITY)),
            "collision": int(self.collision_flag),
            "target_room": "target",
        }

    def reset(self, seed=None, options=None):
        """Start a new episode: clear the counters, draw a birth pose and return (observation, info)."""
        del options  # the upstream reset takes target, not options; the stand-in accepts and ignores them
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._x, self._y = self._rng.choice(START_CELLS)
        self._yaw = self._rng.choice(YAWS)
        self.current_episode_step = 0
        self.success_stay_cnt = 0
        self.collision_flag = False
        self.last_obs = self._render()
        self.last_info = self.info
        return list(self.last_obs), dict(self.last_info)

    def step(self, action):
        """Apply one discrete action and return (observation, reward, terminated, truncated, info)."""
        if not self.action_space.contains(action):
            raise ValueError(f"invalid discrete action {action!r}")

        det_fwd, det_hor, det_rot = DISCRETE_ACTIONS[action]
        # roomnav.py:288-291: scale the action by the movement and rotation sensitivities.
        self._yaw = (self._yaw + det_rot * self.rot_sensitivity) % 360.0
        yaw_rad = math.radians(self._yaw)
        move_fwd = det_fwd * self.move_sensitivity
        move_hor = det_hor * self.move_sensitivity
        new_x = self._x + move_fwd * math.cos(yaw_rad) + move_hor * math.sin(yaw_rad)
        new_y = self._y + move_fwd * math.sin(yaw_rad) - move_hor * math.cos(yaw_rad)

        reward = 0.0
        # roomnav.py:293-302: rotate, then move; a blocked move is a collision and pays the penalty.
        if 0.0 <= new_x <= GRID_MAX and 0.0 <= new_y <= GRID_MAX:
            self._x, self._y = new_x, new_y
            self.collision_flag = False
        else:
            reward -= COLLISION_PENALTY_REWARD
            self.collision_flag = True

        current = self.info
        distance = current["dist"]
        # roomnav.py:312-313: the in-room reward at zero distance (the stand-in uses the success range).
        if distance <= SUCCESS_DISTANCE_RANGE:
            reward += STAY_ROOM_REWARD
            self.success_stay_cnt += 1
        else:
            self.success_stay_cnt = 0
        terminated = self.success_stay_cnt >= SUCCESS_SEE_TARGET_TIME_STEPS
        if terminated:
            reward += SUCCESS_REWARD
        self.current_episode_step += 1
        # roomnav.py:321-322: max_steps > 0 cuts the episode.
        truncated = self.max_steps > 0 and self.current_episode_step >= self.max_steps

        self.last_obs = self._render()
        self.last_info = current
        return list(self.last_obs), reward, terminated, truncated, dict(current)

    def _render(self):
        """A coarse 4 x 4 x 4 stand-in for the real (120, 90, 4) observation array."""
        distance = math.hypot(self._x - self._target[0], self._y - self._target[1])
        near_target = 255 if distance <= SUCCESS_DISTANCE_RANGE else 0
        x_level = int(round(self._x / GRID_MAX * 255))
        y_level = int(round(self._y / GRID_MAX * 255))
        cells = []
        for row in range(OBSERVATION_SIDE):
            for column in range(OBSERVATION_SIDE):
                depth = max(0, min(255, int((distance + row + column) * 24)))
                cells.extend((depth, near_target, x_level, y_level))
        return cells
