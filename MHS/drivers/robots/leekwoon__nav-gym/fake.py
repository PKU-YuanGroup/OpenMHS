"""Fake backend of the NavGym-v0 driver: an analytic open-space stand-in.

Why a fake: the upstream class imports torch, OpenCV, pyastar2d, range_libc,
CMap2D and pose2d and loads a Torch policy in its constructor
(``nav_gym/src/nav_gym_env/env.py:1-28`` and ``:111-119``).  Package code never
imports or runs the clone, so the gate cannot open the upstream environment.
This module mirrors the public surface the Gymnasium bridge uses (``reset``,
``step``, ``action_space``, ``observation_space``; gate G7) and the two-element
velocity action, the 512-angle scan observation and the goal-distance success
terminal of ``NavGymEnv`` (``nav_gym/src/nav_gym_env/env.py:508-512``,
``:591-728`` and ``nav_gym/src/nav_gym_env/keti_robot.py:65-93``).

What this is not: the upstream crowd simulation.  There is no generated map,
crowd, human policy, lidar ray casting, collision, discomfort or scan noise, and
the trajectories were never compared with the upstream environment.  The scan
is a constant maximum-range return, so the crash terminal is never reached.
Every number below is test data, not a device fact, and is marked placeholder.
"""

import math

# Copied registration defaults and KetiRobot geometry; all are placeholder test
# data, not limits or facts (nav_gym/src/nav_gym_env/__init__.py:8-13,19-25 and
# nav_gym/src/nav_gym_env/keti_robot.py:44-48).
TIMESTEP_S = 0.2                     # placeholder: registration time_step
LINVEL_LOW, LINVEL_HIGH = 0.0, 0.5  # placeholder: registration linvel_range
ROTVEL_LOW, ROTVEL_HIGH = -0.64, 0.64  # placeholder: registration rotvel_range
N_ANGLES = 512                       # placeholder: KetiRobot.n_angles
SCAN_RANGE_M = 25.0                  # placeholder: KetiRobot.range_max
OBSERVATION_SIZE = N_ANGLES + 7      # placeholder: scan + prev_pose + pose + vel + yaw
DISTANCE_THRESHOLD_M = 0.5           # placeholder: registration distance_threshold
START_PX, START_PY, START_THETA = 0.0, 0.0, 0.0  # placeholder: fixed fake start
GOAL_X, GOAL_Y = 10.0, 0.0           # placeholder: fixed fake goal, within [10, 20] m
REAR_AXLE_OFFSET_M = 0.14474         # placeholder: KetiRobot rotation-centre offset
REWARD_SCALE = 15.0                  # placeholder: registration reward_scale
REWARD_SUCCESS_FACTOR = 1.0          # placeholder: registration success factor
REWARD_PROGRESS_FACTOR = 0.001       # placeholder: registration progress factor
REWARD_FORWARD_FACTOR = 0.0          # placeholder: registration forward factor
REWARD_ROTATION_FACTOR = 0.005       # placeholder: registration rotation factor


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gym.spaces.Dict``: the bridge reads the ``spaces`` mapping."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeNavGymEnv:
    """NavGym-v0 without its simulator: ``reset()`` and ``step(action)`` as the bridge calls them."""

    def __init__(self, **_options):
        # placeholder: the two-element Box is the upstream linvel/rotvel Box
        self.action_space = Box([LINVEL_LOW, ROTVEL_LOW], [LINVEL_HIGH, ROTVEL_HIGH])
        # placeholder: the upstream Dict observation space
        self.observation_space = Dict({
            "observation": Box([float("-inf")] * OBSERVATION_SIZE,
                               [float("inf")] * OBSERVATION_SIZE, shape=(OBSERVATION_SIZE,)),
            "achieved_goal": Box([float("-inf")] * 2, [float("inf")] * 2, shape=(2,)),
            "desired_goal": Box([float("-inf")] * 2, [float("inf")] * 2, shape=(2,)),
        })
        self.reset()

    def reset(self):
        """Start a fixed episode and return the initial observation (upstream returns the observation)."""
        self.px, self.py, self.theta = START_PX, START_PY, START_THETA  # placeholder
        self.gx, self.gy = GOAL_X, GOAL_Y                                # placeholder
        self.prev_pose = [self.px, self.py]                              # placeholder
        self.prev_action = [0.0, 0.0]                                    # placeholder
        self.steps_since_reset = 0                                       # placeholder: counter start
        self.terminated = False
        self.is_success = False
        self.is_crash = False
        self.distance = self._distance()
        return self._observation()

    def step(self, action):
        """Apply ``[linvel, rotvel]`` for one 200 ms step and return the upstream four-tuple."""
        linvel, rotvel = float(action[0]), float(action[1])
        self._move(linvel, rotvel)
        self.steps_since_reset += 1
        observation = self._observation()
        self.distance = self._distance()
        success = self.distance < DISTANCE_THRESHOLD_M     # placeholder: upstream success rule
        crash = False                                      # placeholder: no obstacle model
        reward = self._reward(success)
        self.terminated = success or crash
        self.is_success, self.is_crash = success, crash
        self.prev_pose = [self.px, self.py]
        self.prev_action = [linvel, rotvel]
        info = {"is_success": success, "is_crash": crash, "distance": self.distance}
        return observation, reward, self.terminated, info

    def _move(self, linvel, rotvel):
        """KetiRobot.set_vel with the rotation-centre offset and wrapped yaw (keti_robot.py:65-93)."""
        rot_px = self.px + REAR_AXLE_OFFSET_M * math.cos(self.theta)  # placeholder offset
        rot_py = self.py + REAR_AXLE_OFFSET_M * math.sin(self.theta)  # placeholder offset
        theta = self.theta + rotvel * TIMESTEP_S                      # placeholder timestep
        rot_px += math.cos(theta) * linvel * TIMESTEP_S               # placeholder timestep
        rot_py += math.sin(theta) * linvel * TIMESTEP_S               # placeholder timestep
        self.px = rot_px - REAR_AXLE_OFFSET_M * math.cos(theta)       # placeholder offset
        self.py = rot_py - REAR_AXLE_OFFSET_M * math.sin(theta)       # placeholder offset
        self.theta = theta % (2 * math.pi)                            # placeholder wrap

    def _observation(self):
        """The upstream observation: scan + prev_pose + pose + previous action + corrected yaw."""
        scan = [SCAN_RANGE_M] * N_ANGLES                              # placeholder max range
        yaw = math.atan2(math.sin(self.theta), math.cos(self.theta))
        return {
            "observation": scan + list(self.prev_pose) + [self.px, self.py]
                           + list(self.prev_action) + [yaw],
            "achieved_goal": [self.px, self.py],
            "desired_goal": [self.gx, self.gy],
        }

    def _distance(self):
        return math.hypot(self.px - self.gx, self.py - self.gy)

    def _reward(self, success):
        """The reward terms that remain without humans, obstacles or noise (env.py:557-562)."""
        prev_distance = math.hypot(self.prev_pose[0] - self.gx, self.prev_pose[1] - self.gy)
        reward = 0.0
        if success:
            reward += REWARD_SUCCESS_FACTOR * REWARD_SCALE             # placeholder factor
        reward += (prev_distance - self.distance) * REWARD_PROGRESS_FACTOR * REWARD_SCALE  # placeholder
        reward += self.prev_action[0] * REWARD_FORWARD_FACTOR * REWARD_SCALE               # placeholder
        reward -= (self.prev_action[1] ** 2) * REWARD_ROTATION_FACTOR * REWARD_SCALE       # placeholder
        return reward
