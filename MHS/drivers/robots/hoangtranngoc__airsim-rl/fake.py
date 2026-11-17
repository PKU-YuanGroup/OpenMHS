"""Pure-Python analytic fake of the AirSim-RL car environment.

The fake preserves the upstream ``AirSimCarEnv`` surface the bridge uses: ``metadata``, ``action_space`` and
``observation_space``, the legacy ``reset()`` return value, the legacy ``step(action)`` four-tuple, ``render()`` and
``close()``.  Its ``car_agent`` is a stand-in for ``gym_airsim.car_agent:CarAgent`` that keeps the methods the
environment calls (``restart``, ``observe``, ``move``, ``getCarState``, ``getCarControls``,
``simGetWayPoints``, ``simGet2ClosestWayPoints`` and the AirSim client ``reset``).

It is not AirSim, Unreal Engine, a car physics engine, a camera or a recording: no AirSim RPC client is imported or
contacted.  It is an analytic stand-in used to check the MHS contract where AirSim and the legacy ``gym``/``airsim``
packages are not installed.  Every numeric geometry, pose and pixel value below is test data and is marked
``# placeholder``; the reward thresholds and the 5 m destination rule are copies of the upstream rules
(``utils.py:14-27`` and ``gym_airsim/airsim_car_env.py:95``).  The fake returns an 8 x 8 x 3 image while the upstream
camera Box is 144 x 256 x 3 (``config.ini:3-5``); the real frame is not covered by this fake.

The public members of ``FakeAirSimCarEnv`` are exactly the upstream environment's public members (``reset``,
``step``, ``render``, ``close``); all state and helper objects are module-private.
"""

import math

#: Upstream camera Box: image_height 144, image_width 256, image_channels 3 (config.ini:3-5).
REAL_IMAGE_SHAPE = (144, 256, 3)
#: placeholder: the fake returns a smaller image than the device to keep receipts small; 8 x 8 x 3.
IMAGE_SIDE = 8
IMAGE_CHANNELS = 3
#: placeholder: a straight synthetic track of 11 waypoints 30 m apart, from x = 0 to x = 300.
WAYPOINT_COUNT = 11
WAYPOINT_SPACING_M = 30.0
#: placeholder: the fake advances 5 m per transition and turns by steering * 0.15 rad.
STEP_DISTANCE_M = 5.0
STEER_GAIN_RAD = 0.15
#: The shipped config.ini sets track_width = 12 (config.ini:7), fixed_throttle = 0.75 (config.ini:22),
#: steering_max = 0.3 and steering_granularity = 7 (config.ini:17-20), actions = 7 (config.ini:24).
TRACK_WIDTH = 12.0
FIXED_THROTTLE = 0.75
STEERING_VALUES = [-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3]
#: gym_airsim/airsim_car_env.py:95: the car is done within 5 m of the destination.
DESTINATION_RADIUS_M = 5.0


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
    """Duck-typed ``gym.spaces.Box``: ``low``/``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=(), dtype="float32"):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = dtype


class _Vec3:
    def __init__(self, x_val, y_val, z_val):
        self.x_val = x_val
        self.y_val = y_val
        self.z_val = z_val


class _Kinematics:
    def __init__(self, position):
        self.position = position


class _CarState:
    def __init__(self, x, y, z=0.0):
        self.kinematics_estimated = _Kinematics(_Vec3(x, y, z))


class _CarControls:
    def __init__(self, throttle=0.0, steering=0.0, brake=0.0):
        self.throttle = throttle
        self.steering = steering
        self.brake = brake


def _distance_to_line(p1, p2, p3):
    """``abs(cross(p2 - p3, p3 - p1)) / norm(p2 - p3)`` (gym_airsim/airsim_car_env.py:81)."""
    ax, ay = p2[0] - p3[0], p2[1] - p3[1]
    bx, by = p3[0] - p1[0], p3[1] - p1[1]
    norm = math.hypot(ax, ay)
    return abs(ax * by - ay * bx) / norm if norm else 0.0


def _compute_reward_distance_to_center(distance_to_center, track_width):
    """The reward ladder of ``utils.py:14-27``: 1, 0.5, 0.1 inside three markers, else -1."""
    marker_1 = 0.1 * track_width
    marker_2 = 0.25 * track_width
    marker_3 = 0.5 * track_width
    if distance_to_center <= marker_1:
        return 1
    if distance_to_center <= marker_2:
        return 0.5
    if distance_to_center <= marker_3:
        return 0.1
    return -1


class FakeCarAgent:
    """Stand-in for ``gym_airsim.car_agent:CarAgent`` without AirSim.

    The environment calls ``restart``, ``move``, ``getCarState``, ``getCarControls``, ``observe``,
    ``simGetWayPoints`` and ``simGet2ClosestWayPoints``; ``reset`` mirrors the inherited AirSim client reset that
    ``AirSimCarEnv.close`` calls.  No AirSim RPC method is imported or invoked.
    """

    def __init__(self):
        self.image_height, self.image_width, self.image_channels = IMAGE_SIDE, IMAGE_SIDE, IMAGE_CHANNELS
        self.image_size = self.image_height * self.image_width * self.image_channels
        self.action_mode = 0                    # config.ini:14 ships action_mode = 0
        self.throttle = FIXED_THROTTLE
        self.steering_granularity = 7           # config.ini:20
        self.steering_values = list(STEERING_VALUES)
        # placeholder: synthetic waypoints along a straight track, not the AirSim scene's WayPoint actors
        self.waypoints = [[index * WAYPOINT_SPACING_M, 0.0] for index in range(WAYPOINT_COUNT)]
        # placeholder: the car starts at the first waypoint, stationary and heading along +x
        self.position = [0.0, 0.0, 0.0]
        self.heading = 0.0
        self.controls = _CarControls()
        self.api_control = False
        self.reset()

    def reset(self):
        """Mirror the AirSim client reset: put the car back at the start pose."""
        self.position = [0.0, 0.0, 0.0]         # placeholder
        self.heading = 0.0                      # placeholder
        self.controls = _CarControls(FIXED_THROTTLE, 0.0, 0.0)
        self.api_control = False

    def restart(self):
        self.reset()
        self.api_control = True

    def observe(self):
        """A placeholder 8 x 8 x 3 frame; the upstream camera is 144 x 256 x 3 (config.ini:3-5)."""
        base = int((self.position[0] * 7 + self.position[1] * 11 + self.heading * 13) % 200)  # placeholder
        return [[[(base + row * 3) % 256, (base + column * 5) % 256, (base + row + column) % 256]  # placeholder
                 for column in range(self.image_width)]
                for row in range(self.image_height)]

    def move(self, action):
        controls = self._interpret_action(action)
        if not isinstance(controls, _CarControls):
            raise TypeError(f"action mode {self.action_mode} is not implemented upstream")
        self.controls = controls
        # placeholder: one transition advances STEP_DISTANCE_M in the heading direction and turns by the steering.
        self.heading += controls.steering * STEER_GAIN_RAD
        self.position[0] += STEP_DISTANCE_M * math.cos(self.heading)
        self.position[1] += STEP_DISTANCE_M * math.sin(self.heading)

    def _interpret_action(self, action):
        car_controls = _CarControls()
        if self.action_mode == 0:
            car_controls.throttle = self.throttle
            car_controls.steering = self.steering_values[action]
        elif self.action_mode in (1, 2):
            return NotImplemented
        else:
            return NotImplemented
        return car_controls

    def getCarState(self):
        return _CarState(*self.position)

    def getCarControls(self):
        return _CarControls(self.controls.throttle, self.controls.steering, self.controls.brake)

    def simGetWayPoints(self):
        return [list(waypoint) for waypoint in self.waypoints]

    def simGet2ClosestWayPoints(self):
        car_point = (self.position[0], self.position[1])
        min_dist = None
        min_index = 0
        for index in range(len(self.waypoints) - 1):
            distance = (math.dist(car_point, self.waypoints[index])
                        + math.dist(car_point, self.waypoints[index + 1]))
            if min_dist is None or distance < min_dist:
                min_dist = distance
                min_index = index
        return self.waypoints[min_index], self.waypoints[min_index + 1]


class FakeAirSimCarEnv:
    """The public legacy-Gym surface of ``gym_airsim.airsim_car_env:AirSimCarEnv``."""

    metadata = {"render.modes": ["human"]}

    def __init__(self, **_options):
        # config.ini:24 ships actions = 7 and config.ini:3-5 ships the camera shape.
        self.action_space = Discrete(len(STEERING_VALUES))
        self.image_height, self.image_width, self.image_channels = IMAGE_SIDE, IMAGE_SIDE, IMAGE_CHANNELS
        self.track_width = TRACK_WIDTH
        # placeholder: the upstream Box is (144, 256, 3) uint8; the fake's downscaled frame is 8 x 8 x 3.
        self.observation_space = Box(0, 255, shape=(IMAGE_SIDE, IMAGE_SIDE, IMAGE_CHANNELS), dtype="uint8")
        self.car_agent = FakeCarAgent()

    def step(self, action):
        self.car_agent.move(action)
        car_state = self.car_agent.getCarState()
        reward = self._compute_reward(car_state)
        car_controls = self.car_agent.getCarControls()
        done = self._isDone(car_state, car_controls, reward)
        info = {}
        observation = self.car_agent.observe()
        return observation, reward, done, info

    def reset(self):
        self.car_agent.restart()
        observation = self.car_agent.observe()
        return observation

    def render(self, mode="human"):
        return

    def close(self):
        self.car_agent.reset()
        return

    def _compute_reward(self, car_state):
        way_point1, way_point2 = self.car_agent.simGet2ClosestWayPoints()
        car_pos = car_state.kinematics_estimated.position
        car_point = (car_pos.x_val, car_pos.y_val)
        distance_to_center = _distance_to_line(car_point, way_point1, way_point2)
        return _compute_reward_distance_to_center(distance_to_center, self.track_width)

    def _isDone(self, car_state, car_controls, reward):
        if reward < 0:
            return True
        car_pos = car_state.kinematics_estimated.position
        car_point = (car_pos.x_val, car_pos.y_val)
        destination = self.car_agent.simGetWayPoints()[-1]
        return math.dist(car_point, destination) < DESTINATION_RADIUS_M
