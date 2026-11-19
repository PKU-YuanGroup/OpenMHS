"""Fake backend of the Easy DRL Isaac Sim driver: a pure Python, kinematic stand-in for ``Isaac_envs``.

Why a fake: the upstream environment imports ``omni.isaac`` and starts the proprietary Isaac Sim 2021.2.1
SimulationApp from its constructor (``DRL_Isaac_lib/env.py:27-30``; ``README.md:70-74``).  Neither Isaac Sim nor
``gym`` is installed where the acceptance gate runs, and package code never imports the clone.  This module mirrors
the public methods of the upstream ``Isaac_envs`` class (``reset``, ``step``, ``seed``, ``close``, ``render``,
``get_observations`` and ``get_dt``; gate G7) and its old Gym calling convention: ``reset`` returns an observation
only, and ``step`` returns ``(observation, reward, done, info)``.

What this is: a 2D kinematic model of the fixed ``random_walk`` scene the upstream constructor hardcodes
(``env.py:40-42,53-57``), the Jetbot's three discrete movements (``isaac_robots.py:317-320``), the upstream reward and
three terminal conditions (``env.py:157-189``), the 12-beam lidar's range against the fixed obstacle boxes
(``isaac_envs.py:157-171,203-219``, ``:312-321``, ``:365-372``), and the upstream random reset of the goal and the
robot (``env.py:195-203``, ``isaac_envs.py:409-430``).

What this is not: the upstream simulator.  The commanded linear and yaw velocity is integrated directly; there is no
PhysX rigid-body dynamics, wheel-ground friction, actuator response, contact response or rendering.  The upstream
initial/reset draws use numpy's global generator (``env.py:249-252``) while this fake uses ``random.Random``, so one
seed does not reproduce upstream trajectories.  Observations are Python lists, not numpy arrays.  All differences
are also listed in the driver's fidelity ``gaps``.

Nothing here talks to a device.
"""

import math
import random

# DRL_Isaac_lib/env.py:18-25 (Isaac_envs.__init__ defaults) and :31-34 (derived step interval)
DEFAULT_SKIP_FRAME = 1
DEFAULT_PHYSICS_DT = 1.0 / 60.0
DEFAULT_RENDERING_DT = 1.0 / 60.0
DEFAULT_MAX_EPISODE_LENGTH = 3000

# DRL_Isaac_lib/isaac_envs.py:157-171 (lidar defaults for the Jetbot)
LIDAR_LASERS = 12
LIDAR_MIN_RANGE = 0.15
LIDAR_MAX_RANGE = 1.0

# DRL_Isaac_lib/isaac_envs.py:248-264 (the random_walk map parameters for the Jetbot)
MAP_DIMENSION = 5
MAP_DIST_UNIT = 0.5
MAP_HEIGHT = 0.2

# DRL_Isaac_lib/isaac_envs.py:365-372 (the fixed map used when _generate_map is called with random=False)
FIXED_MAP = (
    (1.0, 0.0, 1.0, 0.0, 0.0),
    (0.0, 0.0, 0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0, 1.0),
    (1.0, 0.0, 1.0, 0.0, 1.0),
)

# DRL_Isaac_lib/isaac_robots.py:317-320 (Jetbot discrete movements: [linear, yaw])
JETBOT_MOVEMENTS = ((15.0, 0.785), (25.0, 0.0), (15.0, -0.785))

# DRL_Isaac_lib/env.py:168-189 (reward and terminal thresholds)
COLLISION_LIDAR_RANGE = 0.155
GOAL_REACHED_DISTANCE = 0.5
COLLISION_REWARD_FACTOR = 10.0
COLLISION_REFERENCE_RANGE = 0.6
LANDING_REWARD = 90.0

# DRL_Isaac_lib/isaac_envs.py:411,421,427-429 (random_walk poses; the non-random defaults are the same formulas)
ROBOT_Y = MAP_DIST_UNIT * (-1.5)
GOAL_Y = MAP_DIST_UNIT * 5.5
GOAL_Z = 0.25


def _rot90_ccw(grid):
    """``np.rot90(grid, axes=(0,1))`` (isaac_envs.py:372): a counter-clockwise quarter turn."""
    size = len(grid)
    return tuple(tuple(grid[column][size - 1 - row] for column in range(size)) for row in range(size))


def _rectangle(cx, cy, width, depth):
    return (cx - width / 2.0, cx + width / 2.0, cy - depth / 2.0, cy + depth / 2.0)


def _fixed_obstacles():
    """The fixed random_walk boxes: four outer walls and the cells whose rotated map value is 1."""
    walls = (
        # isaac_envs.py:266-275, :276-285, :286-295, :296-305
        _rectangle(MAP_DIST_UNIT * (MAP_DIMENSION - 1) / 2.0, -MAP_DIST_UNIT * (MAP_DIMENSION - 2),
                   MAP_DIST_UNIT * (MAP_DIMENSION + 2), MAP_DIST_UNIT),
        _rectangle(-MAP_DIST_UNIT * 2, MAP_DIST_UNIT * (MAP_DIMENSION - 1) / 2.0,
                   MAP_DIST_UNIT, MAP_DIST_UNIT * (MAP_DIMENSION + 2 + 4)),
        _rectangle(MAP_DIST_UNIT * (MAP_DIMENSION + 1), MAP_DIST_UNIT * (MAP_DIMENSION - 1) / 2.0,
                   MAP_DIST_UNIT, MAP_DIST_UNIT * (MAP_DIMENSION + 2 + 4)),
        _rectangle(MAP_DIST_UNIT * (MAP_DIMENSION - 1) / 2.0, MAP_DIST_UNIT * (MAP_DIMENSION + 2),
                   MAP_DIST_UNIT * (MAP_DIMENSION + 2), MAP_DIST_UNIT),
    )
    rotated = _rot90_ccw(FIXED_MAP)
    cells = []
    for row in range(MAP_DIMENSION):
        for column in range(MAP_DIMENSION):
            if rotated[row][column] == 1.0:
                # isaac_envs.py:312-321: one map_dist_unit cube at (row*unit, column*unit)
                cells.append(_rectangle(row * MAP_DIST_UNIT, column * MAP_DIST_UNIT,
                                        MAP_DIST_UNIT, MAP_DIST_UNIT))
    return walls + tuple(cells)


OBSTACLES = _fixed_obstacles()


def _wrap_angle(angle):
    """Wrap to (-pi, pi] the way ``np.arctan2(np.sin(a), np.cos(a))`` does (isaac_robots.py:259)."""
    return math.atan2(math.sin(angle), math.cos(angle))


def _ray_box_distance(px, py, dx, dy, rectangle):
    """Distance from ``(px, py)`` along the unit ray ``(dx, dy)`` to an axis-aligned box, or None."""
    xmin, xmax, ymin, ymax = rectangle
    tmin, tmax = 0.0, math.inf
    for origin, direction, low, high in ((px, dx, xmin, xmax), (py, dy, ymin, ymax)):
        if abs(direction) < 1e-12:
            if origin < low or origin > high:
                return None
            continue
        first = (low - origin) / direction
        second = (high - origin) / direction
        if first > second:
            first, second = second, first
        tmin = max(tmin, first)
        tmax = min(tmax, second)
        if tmin > tmax:
            return None
    return tmin


def _lidar_ranges(x, y, yaw):
    """The 12 horizontal ranges of the Jetbot lidar against the fixed boxes, clamped to the sensor range."""
    ranges = []
    for index in range(LIDAR_LASERS):
        # isaac_envs.py:203-219: 360 degree horizontal FOV, 360/number_lasers between beams, yaw_offset 0
        angle = yaw + 2.0 * math.pi * index / LIDAR_LASERS
        dx, dy = math.cos(angle), math.sin(angle)
        nearest = LIDAR_MAX_RANGE
        for rectangle in OBSTACLES:
            distance = _ray_box_distance(x, y, dx, dy, rectangle)
            if distance is not None and distance < nearest:
                nearest = distance
        ranges.append(min(LIDAR_MAX_RANGE, max(LIDAR_MIN_RANGE, nearest)))
    return ranges


def _observation(x, y, yaw, goal, linear, yaw_rate):
    """The upstream observation dict: lidar, goal distance/angle and base velocities (env.py:220-237)."""
    lidar = _lidar_ranges(x, y, yaw)
    dx, dy, dz = goal[0] - x, goal[1] - y, goal[2]
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)               # isaac_robots.py:230-232
    # isaac_robots.py:250-259: alpha is the goal bearing; theta is read from the [x, y, z, w] quaternion
    # [0, 0, sin(yaw/2), cos(yaw/2)], whose denominator 1 - 2*(qw^2 + qz^2) is -1 for a z rotation.
    # The pinned numerator is 2*(qy*qz + qw*qx), which is zero for this planar quaternion.
    # Preserve that expression's result rather than substituting a conventional heading calculation.
    theta = math.atan2(0.0, -1.0)
    alpha = math.atan2(dy, dx)
    if alpha < 0:
        alpha += 2.0 * math.pi
    angle = math.atan2(math.sin(theta - alpha), math.cos(alpha - theta))
    return {
        "IR_raleted": [lidar],                                      # env.py:108: (1, 12)
        "pos_raleted": [distance, angle],                           # env.py:229
        "vel_raleted": [abs(linear), yaw_rate],                     # env.py:235
    }


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
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None, dtype="float32"):
        self.low = low
        self.high = high
        self.shape = tuple(shape) if shape is not None else ()
        self.dtype = dtype


class Dict:
    """Duck-typed ``gym.spaces.Dict``: a name-to-space mapping (the bridge reads ``spaces``)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeIsaacEnv:
    """``Isaac_envs`` without Isaac Sim: the fixed random_walk scene for the Jetbot with discrete actions."""

    metadata = {"render.modes": ["human"]}                         # env.py:16

    def __init__(self, skip_frame=DEFAULT_SKIP_FRAME, physics_dt=DEFAULT_PHYSICS_DT,
                 rendering_dt=DEFAULT_RENDERING_DT, max_episode_length=DEFAULT_MAX_EPISODE_LENGTH,
                 seed=0, headless=True):
        # env.py:18-34: the constructor's configuration and derived step interval
        self.headless = headless
        self._skip_frame = int(skip_frame)
        self._dt = physics_dt * self._skip_frame
        self._max_episode_length = max_episode_length
        self._steps_after_reset = int(rendering_dt / physics_dt)
        self._env_name = "random_walk"                              # env.py:40
        self._action_type = "discrete"                              # env.py:42
        self.episode_count = 0
        self.goal_count = 0
        self.step_count = 0
        self.distance_count = 0

        # env.py:93-94 and isaac_robots.py:312-320
        self.action_space = Discrete(3)
        self.movements = JETBOT_MOVEMENTS

        # env.py:96-120: the observation spaces the class publishes
        self.state_pos_space = Box([0.0, -math.pi], [8.0, math.pi])
        self.state_vel_space = Box([0.0, -math.pi / 4.0], [10.0, math.pi / 4.0])
        self.state_IR_space = Box(0.0, 1.0, shape=(1, 12))
        self.depth_obs_space = Box(0.0, 1.0, shape=(1, 128, 128))
        self.rgb_obs_space = Box(0.0, 255.0, shape=(128, 128, 3))
        self.observation_space = Dict({
            "IR_raleted": self.state_IR_space,
            "pos_raleted": self.state_pos_space,
            "vel_raleted": self.state_vel_space,
        })
        self.reward_range = (-float("inf"), float("inf"))           # env.py:90

        # placeholder: the constructor state before the first reset is the upstream non-random pose
        # (isaac_envs.py:421-422,429), not a sampled episode
        self._x = MAP_DIST_UNIT * (MAP_DIMENSION - 1) / 2.0
        self._y = ROBOT_Y
        self._yaw = 0.0
        self._goal = [MAP_DIST_UNIT * (MAP_DIMENSION - 1) / 2.0, GOAL_Y, GOAL_Z]
        self._linear = 0.0
        self._yaw_rate = 0.0
        self._world_index = 0
        self._rng = random.Random(seed)
        self._closed = False

    def reset(self):
        """Reset the fixed random_walk scene and return the observation (the old Gym API, env.py:195-213)."""
        if self._closed:
            raise RuntimeError("the fake Isaac environment is closed")
        # env.py:199-203: the goal is drawn first, then the robot pose; isaac_envs.py:409-430 gives the draws
        goal_x = MAP_DIST_UNIT * self._rng.randrange(MAP_DIMENSION)
        self._goal = [goal_x, GOAL_Y, GOAL_Z]
        robot_x = MAP_DIST_UNIT * self._rng.randrange(MAP_DIMENSION)
        a = self._rng.random() * math.pi
        self._x = robot_x
        self._y = ROBOT_Y
        self._yaw = _wrap_angle(2.0 * a)
        self._linear = 0.0
        self._yaw_rate = 0.0
        self._world_index = 0
        self.step_count = 0
        self.distance_count = 0
        observations = self.get_observations()
        self.episode_count += 1
        return observations

    def step(self, action):
        """Apply one discrete movement and return ``(observation, reward, done, info)`` (env.py:126-193)."""
        if self._closed:
            raise RuntimeError("the fake Isaac environment is closed")
        selected = self.movements[action]                           # env.py:139; IndexError for a bad action
        linear_value, yaw_value = float(selected[0]), float(selected[1])
        # placeholder: this kinematic gain is a fake choice, not a source-backed unit conversion.
        # isaac_robots.py:142-163 gives wheel geometry and wheel targets but states no linear velocity unit.
        self._linear = linear_value / 100.0
        self._yaw_rate = yaw_value
        previous_x, previous_y = self._x, self._y
        for _ in range(self._skip_frame):                           # env.py:130-146
            self._world_index += 1
            self._integrate()
        self.distance_count += math.hypot(self._x - previous_x, self._y - previous_y)   # env.py:150
        observations = self.get_observations()                      # env.py:153

        done = False
        if self._world_index - self._steps_after_reset >= self._max_episode_length:     # env.py:159
            done = True
        goal = self._goal
        dx, dy, dz = goal[0] - self._x, goal[1] - self._y, goal[2]
        current_dist_to_goal = math.sqrt(dx * dx + dy * dy + dz * dz)                   # env.py:162-163
        lidar_min = min(observations["IR_raleted"][0])                                  # env.py:165-166

        # env.py:168-175
        step_conservation = 1.0 - (self._world_index / self._max_episode_length)
        distance_reward = (-current_dist_to_goal) / 100.0
        reward = distance_reward * step_conservation if distance_reward > 0 else distance_reward
        # env.py:181-183
        if lidar_min <= COLLISION_LIDAR_RANGE:
            done = True
            reward -= COLLISION_REWARD_FACTOR * (COLLISION_REFERENCE_RANGE - lidar_min)
        # env.py:185-189
        if current_dist_to_goal <= GOAL_REACHED_DISTANCE:
            done = True
            self.goal_count += 1
            reward += 10.0 + LANDING_REWARD * (1.0 - (self._world_index / self._max_episode_length))
        self.step_count = self._world_index
        return observations, reward, done, {}

    def get_observations(self):
        """The upstream observation dict (env.py:215-240); the fake has no camera or depth frame."""
        return _observation(self._x, self._y, self._yaw, self._goal, self._linear, self._yaw_rate)

    def render(self, mode="human"):
        return None

    def close(self):
        self._closed = True

    def seed(self, seed=None):
        """Seed the fake's Python generator (the upstream method is env.py:249-252)."""
        self._rng = random.Random(seed)
        return [seed]

    def get_dt(self):
        return self._dt

    def _integrate(self):
        """One physics interval of the kinematic model: the commanded velocities are integrated directly."""
        # The upstream world steps physics_dt per skip frame (env.py:31-32,130-146); no body dynamics are modelled.
        dt = self._dt / self._skip_frame
        self._x += self._linear * math.cos(self._yaw) * dt
        self._y += self._linear * math.sin(self._yaw) * dt
        self._yaw = _wrap_angle(self._yaw + self._yaw_rate * dt)
