"""Fake backend for the RoboTerrain ``RoverEnv`` package.

Why a fake: the upstream environment is a Gymnasium environment that builds a
ROS 2 node with ``rclpy`` and talks to Gazebo Fortress over ROS topics and the
``ign`` service command.  Package code never imports the clone, and the gate
runs without ROS 2, Gazebo, ``rclpy``, ``cv_bridge`` or ``transforms3d``.
This module therefore re-implements the public Gymnasium surface the bridge
uses (``reset``, ``step``, ``close``, ``action_space`` and
``observation_space``) for the class the driver names as ``native``,
``sb3.environments.rover_env:RoverEnv``.

The action and observation spaces copy the upstream class definition
(``ros2_ws/src/sb3/environments/rover_env.py:215-219`` and ``:226-255``).
Everything else here is a small kinematic stand-in, not the upstream
Gazebo/ROS loop.  Its positions, target, step duration, lidar values and
reward are test data, each marked ``# placeholder``; they are not device facts
and are not copied into a Fact or a Limit.

What this is not, also listed in the driver's fidelity ``gaps``:

* no ``rclpy`` node, publishers, subscribers, callbacks or ROS graph;
* no Gazebo Fortress physics, contacts, sensors or wall-clock pacing;
* no ``ign service`` reset, no 100 ``spin_once`` calls and no one-second wait;
* the reward is a simple progress term, not the upstream ``task_reward``;
* the lidar array is a fixed placeholder, not a LaserScan conversion.

Nothing here talks to a device.
"""

import math
import random

#: The upstream action space: Box([-1.0, -pi], [1.0, pi]) (rover_env.py:215-219).
ACTION_LOW = [-1.0, -math.pi]
ACTION_HIGH = [1.0, math.pi]
#: The upstream observation space (rover_env.py:226-255): a 32-cell lidar over
#: 0..12 m, pose bounds, IMU angle bounds, target distance/angle and velocities.
LIDAR_POINTS = 32
MAX_LIDAR_RANGE = 12.0
POSE_LOW = [-30.0, -30.0, -10.0]
POSE_HIGH = [30.0, 30.0, 10.0]
TARGET_LOW = [0.0, -math.pi]
TARGET_HIGH = [100.0, math.pi]
VELOCITY_LOW = [-10.0, -10.0]
VELOCITY_HIGH = [10.0, 10.0]
#: Test data, not a device fact: the fake's per-tick displacement window.
STEP_SECONDS = 0.1  # placeholder
#: Test data, not a device fact: the fake's fixed target and lidar reading.
TARGET_X = 3.0  # placeholder
TARGET_Y = 4.0  # placeholder
LIDAR_READING = 6.0  # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box`` with ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=()):
        self.shape = tuple(shape)
        self.low = list(low) if isinstance(low, (list, tuple)) else [float(low)]
        self.high = list(high) if isinstance(high, (list, tuple)) else [float(high)]
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict`` with a ``spaces`` mapping."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeRoverEnv:
    """A ROS-free stand-in for ``RoverEnv``: ``reset(seed, options)`` and ``step(action)``.

    The constructor accepts the upstream keyword names so the bridge can build
    the environment without arguments.  Only ``reset``, ``step`` and ``close``
    are public methods; those names exist on the upstream class (gate G7).
    """

    def __init__(self, size=(64, 64), length=2000, scan_topic="/scan", imu_topic="/imu/data",
                 cmd_vel_topic="/cmd_vel", camera_topic="/camera/image_raw", world_n="inspect",
                 connection_check_timeout=30, lidar_points=LIDAR_POINTS,
                 max_lidar_range=MAX_LIDAR_RANGE):
        self._size = tuple(size)  # placeholder
        self._length = int(length)
        self._scan_topic = scan_topic
        self._imu_topic = imu_topic
        self._cmd_vel_topic = cmd_vel_topic
        self._camera_topic = camera_topic
        self._world_name = world_n
        self._connection_check_timeout = int(connection_check_timeout)
        self._lidar_points = int(lidar_points)
        self._max_lidar_range = float(max_lidar_range)
        self._rng = random.Random()  # placeholder: seeded only by reset(seed=...)
        self._closed = False
        self._x = 0.0  # placeholder
        self._y = 0.0  # placeholder
        self._yaw = 0.0  # placeholder
        self._linear_velocity = 0.0  # placeholder
        self._angular_velocity = 0.0  # placeholder
        self._target_x = TARGET_X  # placeholder
        self._target_y = TARGET_Y  # placeholder
        self._step_count = 0
        self._total_steps = 0
        self._previous_distance = None
        self._lidar = [LIDAR_READING] * self._lidar_points  # placeholder
        self.action_space = Box(ACTION_LOW, ACTION_HIGH, (2,))  # rover_env.py:215-219
        self.observation_space = Dict({  # rover_env.py:226-255
            "lidar": Box(0.0, self._max_lidar_range, (self._lidar_points,)),
            "pose": Box(POSE_LOW, POSE_HIGH, (3,)),
            "imu": Box([-math.pi, -math.pi, -math.pi], [math.pi, math.pi, math.pi], (3,)),
            "target": Box(TARGET_LOW, TARGET_HIGH, (2,)),
            "velocities": Box(VELOCITY_LOW, VELOCITY_HIGH, (2,)),
        })

    def reset(self, seed=None, options=None):
        """Reset the stand-in state, using ``seed`` when the bridge supplies one.

        The upstream reset (rover_env.py:599-683) calls ``super().reset(seed=seed)``,
        then draws positions with the module-level ``np.random`` generator, runs
        an ``ign service`` command and waits; this fake uses a local
        ``random.Random`` and returns immediately.
        """
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._x = self._rng.uniform(-1.0, 1.0)  # placeholder
        self._y = self._rng.uniform(-1.0, 1.0)  # placeholder
        self._yaw = self._rng.uniform(-math.pi, math.pi)  # placeholder
        self._linear_velocity = 0.0  # placeholder
        self._angular_velocity = 0.0  # placeholder
        self._target_x = TARGET_X  # placeholder
        self._target_y = TARGET_Y  # placeholder
        self._step_count = 0
        self._total_steps = 0
        self._previous_distance = None
        self._lidar = [LIDAR_READING] * self._lidar_points  # placeholder
        return self.get_observation(), {}

    def step(self, action):
        """Apply one ``[speed, relative_heading]`` action and advance the stand-in."""
        speed = float(action[0])
        relative_heading = float(action[1])
        self._linear_velocity = speed
        self._angular_velocity = relative_heading
        self._yaw = math.atan2(math.sin(self._yaw + relative_heading * STEP_SECONDS),
                               math.cos(self._yaw + relative_heading * STEP_SECONDS))
        self._x += speed * math.cos(self._yaw) * STEP_SECONDS
        self._y += speed * math.sin(self._yaw) * STEP_SECONDS
        distance = self.get_target_info()[0]
        if self._previous_distance is None:
            reward = 0.0  # placeholder: the upstream first reward is also 0.0 (rover_env.py:490-492)
        else:
            reward = self._previous_distance - distance  # placeholder: progress, not task_reward()
        self._previous_distance = distance
        self._step_count += 1
        self._total_steps += 1
        # The upstream done flag is _step >= _length (rover_env.py:412-414).
        terminated = self._step_count >= self._length
        info = {"steps": self._step_count, "total_steps": self._total_steps, "reward": reward}
        return self.get_observation(), float(reward), bool(terminated), False, info

    def get_observation(self):
        """The upstream observation mapping (rover_env.py:446-455)."""
        return {
            "lidar": list(self._lidar),
            "pose": [self._x, self._y, 0.0],
            "imu": [0.0, 0.0, self._yaw],
            "target": self.get_target_info(),
            "velocities": [self._linear_velocity, self._angular_velocity],
        }

    def get_target_info(self):
        """Distance and relative azimuth to the target (rover_env.py:560-582)."""
        distance = math.sqrt((self._x - self._target_x) ** 2 + (self._y - self._target_y) ** 2)
        target_heading = math.atan2(self._target_y - self._y, self._target_x - self._x)
        relative_angle = math.atan2(math.sin(target_heading - self._yaw),
                                    math.cos(target_heading - self._yaw))
        return [distance, relative_angle]

    def close(self):
        """The upstream close() drops its ROS node; this fake only marks itself closed."""
        self._closed = True
