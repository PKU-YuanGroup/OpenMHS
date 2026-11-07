"""Fake backend of the Robot SF driver: a pure Python stand-in for ``robot_sf.gym_env.robot_env:RobotEnv``.

Why a fake: the acceptance gate does not install Robot SF (the clone declares numpy, gymnasium, numba, svgelements,
loguru, shapely and other dependencies at ``pyproject.toml:34-53``, and its simulator imports PySocialForce at
``robot_sf/sim/simulator.py:33``), and package code never imports the clone.  This module re-implements the
smallest part of the single-robot environment that the ``cap.world.*`` bridge needs: ``reset(seed, options)``,
``step(action)`` and ``close()``, with the action space, the observation-space members and the kinematic update of
``robot_sf.robot.differential_drive:DifferentialDriveRobot``.

Every physical constant below cites the line of the clone at the pinned commit
53721be3248600e08641a9816d094b605e3c93e4.  Numbers that are only test data of this stand-in (the start pose range,
the goal, the reduced ray count and the constant ray range) are marked ``# placeholder``.

What this is not, all listed in the fidelity ``gaps`` of ``driver.py``:

* a social-force crowd simulation: there are no pedestrians, no obstacles and no collisions;
* the full fused observation space: the real environment returns a ``Dict`` of ``drive_state`` and ``rays`` with 272
  rays by default (``robot_sf/sensor/range_sensor.py:148``), while this fake returns 8 constant rays;
* the route-completion reward and the collision/route terminal conditions: the reward is 0 and only the simulated
  time limit terminates an episode;
* wheel-speed odometry: the pose is integrated with a simple unicycle Euler step from the polar velocity;
* rendering, recording, telemetry, planners and snapshots.

Nothing here talks to a device.
"""

import math
import random

# robot_sf/sim/sim_config.py:257 and :260 (SimulationSettings defaults)
SIM_TIME_LIMIT = 200.0                  # seconds
DT = 0.1                                # seconds per simulation step

# robot_sf/robot/differential_drive.py:30, :32, :41 and :44 (DifferentialDriveSettings defaults)
MAX_LINEAR_SPEED = 2.0                  # m/s
MAX_ANGULAR_SPEED = 1.0                 # rad/s
MAX_LINEAR_ACCEL = 1.0                  # m/s^2
MAX_ANGULAR_ACCEL = 1.0                 # rad/s^2
# robot_sf/robot/differential_drive.py:53 and :88-89: max_linear_decel defaults to max_linear_accel
MAX_LINEAR_DECEL = 1.0                  # m/s^2
# robot_sf/robot/differential_drive.py:38 and :103-108: allow_backwards is false, so min_linear_speed is 0.0
MIN_LINEAR_SPEED = 0.0                  # m/s
# robot_sf/robot/robot_state.py:63-68: max_sim_steps is the ceiling of sim_time_limit / d_t
MAX_SIM_STEPS = math.ceil(SIM_TIME_LIMIT / DT)

# robot_sf/sensor/range_sensor.py:146 (LidarScannerSettings.max_scan_dist default)
MAX_SCAN_DIST = 10.0                    # m

# --- test data of this stand-in, never a Fact or a Limit ------------------------------------------------
NUM_RAYS = 8                            # placeholder: the real default is 272 rays
START_XY = 1.0                          # placeholder: initial x and y are drawn from -1.0 .. 1.0
GOAL_X, GOAL_Y = 5.0, 0.0               # placeholder: a fixed goal point for the target vector
RAY_RANGE = MAX_SCAN_DIST               # placeholder: no obstacle model, every ray reads max range
STEP_REWARD = 0.0                       # placeholder: the reward model is not reproduced


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: named subspace members (the bridge reads ``spaces``)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeRobotEnv:
    """A kinematic single-robot stand-in: ``reset``, ``step`` and ``close`` as ``RobotEnv`` has them."""

    def __init__(self, **_options):
        # robot_sf/robot/differential_drive.py:335-343 (DifferentialDriveRobot.action_space)
        self.action_space = Box(
            [-MAX_LINEAR_DECEL, -MAX_ANGULAR_ACCEL],
            [MAX_LINEAR_ACCEL, MAX_ANGULAR_ACCEL],
        )
        # robot_sf/sensor/sensor_fusion.py:71-89: the fused space is a Dict of drive_state and rays.
        # The bounds are the robot's own observation (robot_sf/robot/differential_drive.py:315-323), the target
        # vector (bounded by max_scan_dist in this stand-in) and the LiDAR range.
        self.observation_space = Dict({
            "drive_state": Box(
                [MIN_LINEAR_SPEED, -MAX_ANGULAR_SPEED, -MAX_SCAN_DIST, -MAX_SCAN_DIST],
                [MAX_LINEAR_SPEED, MAX_ANGULAR_SPEED, MAX_SCAN_DIST, MAX_SCAN_DIST],
            ),
            "rays": Box([0.0] * NUM_RAYS, [MAX_SCAN_DIST] * NUM_RAYS),
        })
        self._rng = random.Random()     # replaced by reset(seed=...)
        self._pose = None
        self._velocity = None
        self._steps = 0

    # -- Gymnasium surface -----------------------------------------------------------------------------
    def reset(self, seed=None, options=None):
        """Draw a new start pose and return ``(observation, info)`` like ``RobotEnv.reset``.

        ``RobotEnv.reset`` seeds the global generators and forwards ``seed`` and ``options`` to
        ``gymnasium.Env.reset`` (robot_sf/gym_env/robot_env.py:1272-1284); this stand-in only seeds the local
        ``random.Random`` and accepts, but does not interpret, ``options``.
        """
        if seed is not None:
            self._rng = random.Random(int(seed))
        elif self._pose is None:
            self._rng = random.Random()
        x = self._rng.uniform(-START_XY, START_XY)          # placeholder
        y = self._rng.uniform(-START_XY, START_XY)          # placeholder
        theta = self._rng.uniform(-math.pi, math.pi)        # placeholder
        self._pose = (x, y, theta)
        self._velocity = (0.0, 0.0)
        self._steps = 0
        return self._observation(), {}

    def step(self, action):
        """Apply one acceleration command and return the Gymnasium five-tuple.

        The update follows ``DifferentialDriveMotion._robot_velocity`` (robot_sf/robot/differential_drive.py:181-193):
        clip the commanded linear and angular accelerations, integrate them over ``DT`` and clip the resulting speeds.
        The pose is then advanced with a simple unicycle Euler step, which is this stand-in's approximation of the
        wheel-speed odometry of ``DifferentialDriveMotion.move`` (robot_sf/robot/differential_drive.py:140-156).
        """
        if self._pose is None:
            raise RuntimeError("Call reset before using step method.")
        if len(action) != 2:
            raise ValueError("the action is [linear acceleration, angular acceleration]")
        linear_accel = _clip(float(action[0]), -MAX_LINEAR_DECEL, MAX_LINEAR_ACCEL)
        angular_accel = _clip(float(action[1]), -MAX_ANGULAR_ACCEL, MAX_ANGULAR_ACCEL)
        linear_speed = _clip(self._velocity[0] + linear_accel * DT, MIN_LINEAR_SPEED, MAX_LINEAR_SPEED)
        angular_speed = _clip(self._velocity[1] + angular_accel * DT, -MAX_ANGULAR_SPEED, MAX_ANGULAR_SPEED)
        self._velocity = (linear_speed, angular_speed)
        x, y, theta = self._pose
        x += linear_speed * math.cos(theta) * DT
        y += linear_speed * math.sin(theta) * DT
        theta += angular_speed * DT
        self._pose = (x, y, theta)
        self._steps += 1
        # robot_sf/robot/robot_state.py:120-130: the step sets is_timeout at max_sim_steps, and the environment's
        # step returns that terminal flag with truncated False (robot_sf/gym_env/robot_env.py:1264-1270).
        terminated = self._steps >= MAX_SIM_STEPS
        return self._observation(), STEP_REWARD, terminated, False, {}

    def close(self):
        self._pose = None
        self._velocity = None

    # -- internals --------------------------------------------------------------------------------------
    def _observation(self):
        x, y, _theta = self._pose
        linear_speed, angular_speed = self._velocity
        return {
            "drive_state": [linear_speed, angular_speed, GOAL_X - x, GOAL_Y - y],
            "rays": [RAY_RANGE] * NUM_RAYS,     # placeholder: no obstacle model
        }


def _clip(value, low, high):
    return min(max(value, low), high)
