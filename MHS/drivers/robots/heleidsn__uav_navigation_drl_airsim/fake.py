"""Fake backend of the AirSim UAV driver: a pure Python stand-in for the NH_center Gym environment.

Why a fake: importing the clone needs AirSim, PyQt5, torch, cv2 and keyboard
(``gym_env/gym_env/envs/airsim_env.py:1-18``) and package code never imports the clone.  This module re-implements
the parts of ``gym_env.envs:AirsimGymEnv`` and ``MultirotorDynamicsSimple`` that the environment exposes, for the
configuration ``configs/config_NH_center_SimpleMultirotor_3D.ini``: the 3D kinematic multirotor update, the goal and
workspace, ``compute_reward_final`` and the ``is_*`` termination checks.

The public methods are the ones ``AirsimGymEnv`` has (``reset``, ``step``, ``get_obs``, ``get_obs_vector``,
``is_done``, ``is_not_inside_workspace``, ``is_in_desired_pose``, ``is_crashed``, ``get_distance_to_goal_3d``,
``compute_reward_final``; gate G7).  The two space objects duck-type the Gym ``Box`` (the bridge reads ``low``,
``high`` and ``shape``).

What this is not, all listed in the fidelity ``gaps`` of the driver:

* there is no AirSim scene, depth image, collision query, physics engine or rendering; the five depth features and
  the minimum obstacle distance are placeholders (``# placeholder``);
* the start yaw and the goal are drawn with Python's ``random.Random``, upstream draws them with numpy's global
  generator, so one seed does not give the same trajectory on both;
* the upstream declares observation shape (1, 28) for this configuration but ``get_obs_vector`` returns 5 + 3 = 8
  values; this fake publishes and returns the actual 8 values;
* there is no PyQt signal and no AirSim RPC.

Nothing here talks to a device.
"""

import math
import random

# config_NH_center_SimpleMultirotor_3D.ini:39-44 and dynamics/multirotor_simple.py:53-56
DT = 0.1
V_XY_MIN = 0.5
V_XY_MAX = 5.0
V_Z_MAX = 2.0
YAW_RATE_MAX_DEG = 30.0
YAW_RATE_MAX_RAD = math.radians(YAW_RATE_MAX_DEG)
MAX_VERTICAL_DIFFERENCE = 5
# config lines 35-36, 31 and 18
CRASH_DISTANCE = 1
ACCEPT_RADIUS = 2
MAX_DEPTH_METERS = 15
CNN_FEATURE_NUM = 25
# airsim_env.py:69-79 for env_name NH_center
START_POSITION = [0.0, 0.0, 5.0]
GOAL_RECT = [-128, -128, 128, 128]
WORK_SPACE_X = [-140, 140]
WORK_SPACE_Y = [-140, 140]
WORK_SPACE_Z = [0.5, 20]
MAX_EPISODE_STEPS = 1000
# airsim_env.py:521-530 and :577-578 (compute_reward_final)
REWARD_REACH = 10
REWARD_CRASH = -20
REWARD_OUTSIDE = -10
DISTANCE_REWARD_COEF = 500
# airsim_env.py:394-425: the depth image is split into five columns and each maximum is one feature
DEPTH_FEATURES = 5
STATE_FEATURES = 3
# the vector observation actually returned for this configuration: 5 depth features + 3 state features
OBSERVATION_LENGTH = DEPTH_FEATURES + STATE_FEATURES


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element and the array shape."""

    def __init__(self, low, high, shape=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"


class FakeAirsimGymEnv:
    """The NH_center SimpleMultirotor environment without AirSim, numpy or Qt."""

    def __init__(self, **options):
        del options  # the upstream AirsimGymEnv constructor takes no arguments
        # dynamics/multirotor_simple.py:62-65: Box(low=[v_xy_min, -v_z_max, -yaw_rate_max_rad], ...)
        self.action_space = Box(
            [V_XY_MIN, -V_Z_MAX, -YAW_RATE_MAX_RAD],
            [V_XY_MAX, V_Z_MAX, YAW_RATE_MAX_RAD],
            shape=(3,),
        )
        # airsim_env.py:394-425: the actual vector is five depth features plus the three state features
        self.observation_space = Box([0.0] * OBSERVATION_LENGTH, [1.0] * OBSERVATION_LENGTH,
                                     shape=(1, OBSERVATION_LENGTH))
        self._rng = random.Random(0)  # placeholder: a seed the bridge supplies on first reset
        self._reset_state()

    # -- upstream-shaped state ------------------------------------------------
    def _reset_state(self):
        self.episode_num = 0
        self.step_num = 0
        self.total_step = 0
        self.cumulated_episode_reward = 0
        self.previous_distance_from_des_point = 0
        self.min_distance_to_obstacles = MAX_DEPTH_METERS  # placeholder: no depth image is rendered
        self.trajectory_list = []
        self.feature_all = []
        self.state_raw = [0.0] * 6
        self.state_norm = [0.0] * STATE_FEATURES
        self.x, self.y, self.z = START_POSITION
        self.yaw = 0.0
        self.v_xy = 0.0
        self.v_z = 0.0
        self.yaw_rate = 0.0
        self.goal_position = [0.0, 0.0, START_POSITION[2]]
        self.goal_distance = 1.0  # placeholder: avoids division by zero before the first reset
        self.start_position = list(START_POSITION)
        self.start_random_angle = 2 * math.pi
        self.goal_random_angle = 2 * math.pi
        self.goal_rect = list(GOAL_RECT)

    # -- AirsimGymEnv.reset (airsim_env.py:201-215) ---------------------------
    def reset(self, seed=None, options=None):
        del options  # the upstream reset takes no seed or options; the bridge only uses them for determinism
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._update_goal_pose()                                                # multirotor_simple.py:75-77
        yaw_noise = self.start_random_angle * self._rng.random()                # multirotor_simple.py:79
        self.x, self.y, self.z = self.start_position
        self.yaw = yaw_noise
        self.v_xy = 0.0
        self.v_z = 0.0
        self.yaw_rate = 0.0
        self.episode_num += 1
        self.step_num = 0
        self.cumulated_episode_reward = 0
        self.goal_distance = self._distance_to_goal_2d()                        # airsim_env.py:208
        self.previous_distance_from_des_point = self.goal_distance              # airsim_env.py:209
        self.trajectory_list = []
        return self.get_obs()                                                   # airsim_env.py:213-215

    # -- AirsimGymEnv.step (airsim_env.py:217-303) ----------------------------
    def step(self, action):
        self._set_action(action)                                                # airsim_env.py:219-223
        position = [self.x, self.y, self.z]
        self.trajectory_list.append(position)                                   # airsim_env.py:225-226
        obs = self.get_obs()                                                    # airsim_env.py:229
        done = self.is_done()                                                   # airsim_env.py:230
        info = {
            "is_success": self.is_in_desired_pose(),
            "is_crash": self.is_crashed(),
            "is_not_in_workspace": self.is_not_inside_workspace(),
            "step_num": self.step_num,
        }                                                                       # airsim_env.py:231-236
        reward = self.compute_reward_final(done, action)                        # airsim_env.py:250-251
        self.cumulated_episode_reward += reward                                 # airsim_env.py:298
        self.step_num += 1                                                      # airsim_env.py:300
        self.total_step += 1                                                    # airsim_env.py:301
        return obs, reward, done, info                                          # airsim_env.py:303

    def _set_action(self, action):
        """MultirotorDynamicsSimple.set_action (multirotor_simple.py:97-116)."""
        self.v_xy = float(action[0])
        self.v_z = float(action[1])
        self.yaw_rate = float(action[-1])
        self.x += self.v_xy * math.cos(self.yaw) * DT
        self.y += self.v_xy * math.sin(self.yaw) * DT
        self.z += self.v_z * DT
        self.yaw += self.yaw_rate * DT
        if self.yaw > math.radians(180):
            self.yaw -= math.pi * 2
        elif self.yaw < math.radians(-180):
            self.yaw += math.pi * 2

    # -- observation (airsim_env.py:306-425) ---------------------------------
    def get_obs(self):
        return self.get_obs_vector()

    def get_obs_vector(self):
        # placeholder: no depth image exists, so the five depth-column maxima are zeros
        image_feature = [0.0] * DEPTH_FEATURES
        self.min_distance_to_obstacles = MAX_DEPTH_METERS  # placeholder: the shallowest depth was not sampled
        state_feature = [value / 255.0 for value in self._get_state_feature()]
        self.feature_all = image_feature + state_feature
        return [self.feature_all]

    def _get_state_feature(self):
        """MultirotorDynamicsSimple._get_state_feature (multirotor_simple.py:187-229), 3D without velocity state."""
        distance = self._distance_to_goal_2d()
        relative_yaw = self._get_relative_yaw()
        relative_pose_z = self.z - self.goal_position[2]
        vertical_distance_norm = (relative_pose_z / MAX_VERTICAL_DIFFERENCE / 2 + 0.5) * 255
        distance_norm = distance / self.goal_distance * 255
        relative_yaw_norm = (relative_yaw / math.pi / 2 + 0.5) * 255
        linear_velocity_norm = (self.v_xy - V_XY_MIN) / (V_XY_MAX - V_XY_MIN) * 255
        linear_velocity_z_norm = (self.v_z / V_Z_MAX / 2 + 0.5) * 255
        angular_velocity_norm = (self.yaw_rate / YAW_RATE_MAX_RAD / 2 + 0.5) * 255
        self.state_raw = [
            distance,
            relative_pose_z,
            math.degrees(relative_yaw),
            self.v_xy,
            self.v_z,
            math.degrees(self.yaw_rate),
        ]
        state_norm = [
            distance_norm,
            vertical_distance_norm,
            relative_yaw_norm,
            linear_velocity_norm,
            linear_velocity_z_norm,
            angular_velocity_norm,
        ]
        state_norm = [_clip(value, 0.0, 255.0) for value in state_norm]
        self.state_norm = state_norm[:STATE_FEATURES]                            # multirotor_simple.py:218-220
        return self.state_norm

    # -- termination (airsim_env.py:860-902) ---------------------------------
    def is_done(self):
        return (self.is_not_inside_workspace()
                or self.is_in_desired_pose()
                or self.is_crashed()
                or self.step_num >= MAX_EPISODE_STEPS)

    def is_not_inside_workspace(self):
        return (self.x < WORK_SPACE_X[0] or self.x > WORK_SPACE_X[1]
                or self.y < WORK_SPACE_Y[0] or self.y > WORK_SPACE_Y[1]
                or self.z < WORK_SPACE_Z[0] or self.z > WORK_SPACE_Z[1])

    def is_in_desired_pose(self):
        return self.get_distance_to_goal_3d() < ACCEPT_RADIUS

    def is_crashed(self):
        # The upstream also asks AirSim's simGetCollisionInfo(); there is no client here (fidelity gap).
        return self.min_distance_to_obstacles < CRASH_DISTANCE

    def get_distance_to_goal_3d(self):
        return math.sqrt(
            (self.x - self.goal_position[0]) ** 2
            + (self.y - self.goal_position[1]) ** 2
            + (self.z - self.goal_position[2]) ** 2
        )

    # -- reward (airsim_env.py:521-587) --------------------------------------
    def compute_reward_final(self, done, action):
        if not done:
            distance_now = self.get_distance_to_goal_3d()
            reward_distance = DISTANCE_REWARD_COEF * (
                self.previous_distance_from_des_point - distance_now
            ) / self.goal_distance
            self.previous_distance_from_des_point = distance_now
            punishment_xy = _clip(
                _point_to_line_distance(self.x, self.y, 0.0, 0.0,
                                        self.goal_position[0], self.goal_position[1]) / 10,
                0.0, 1.0,
            )
            punishment_z = 0.5 * _clip((self.z - self.goal_position[2]) / 5, 0.0, 1.0)
            punishment_pose = punishment_xy + punishment_z
            if self.min_distance_to_obstacles < 10:
                punishment_obs = 1 - _clip(
                    (self.min_distance_to_obstacles - CRASH_DISTANCE) / 5, 0.0, 1.0)
            else:
                punishment_obs = 0
            v_z_cost = (abs(float(action[1])) / V_Z_MAX) ** 2
            z_err_cost = (abs(self.state_raw[1]) / MAX_VERTICAL_DIFFERENCE) ** 2
            punishment_action = v_z_cost + z_err_cost + abs(float(action[-1])) / YAW_RATE_MAX_RAD
            yaw_error_cost = abs(self.state_raw[2] / 90)
            return (reward_distance - 0.1 * punishment_pose - 0.2 * punishment_obs
                    - 0.1 * punishment_action - 0.5 * yaw_error_cost)
        reward = 0
        if self.is_in_desired_pose():
            reward = REWARD_REACH
        if self.is_crashed():
            reward = REWARD_CRASH
        if self.is_not_inside_workspace():
            reward = REWARD_OUTSIDE
        return reward

    # -- private geometry -----------------------------------------------------
    def _distance_to_goal_2d(self):
        return math.sqrt((self.x - self.goal_position[0]) ** 2
                         + (self.y - self.goal_position[1]) ** 2)

    def _get_relative_yaw(self):
        angle = math.atan2(self.goal_position[1] - self.y, self.goal_position[0] - self.x)
        yaw_error = angle - self.yaw
        if yaw_error > math.pi:
            yaw_error -= 2 * math.pi
        elif yaw_error < -math.pi:
            yaw_error += 2 * math.pi
        return yaw_error

    def _update_goal_pose(self):
        """MultirotorDynamicsSimple.update_goal_pose (multirotor_simple.py:128-143)."""
        goal_x, goal_y = self._goal_from_rect(self.goal_rect, self.goal_random_angle)
        self.goal_distance = math.sqrt(goal_x * goal_x + goal_y * goal_y)        # multirotor_simple.py:139
        self.goal_position = [goal_x, goal_y, self.start_position[2]]

    def _goal_from_rect(self, rect, random_angle):
        """MultirotorDynamicsSimple.get_goal_from_rect (multirotor_simple.py:156-185)."""
        del rect  # multirotor_simple.py:161 replaces the argument with the same rectangle
        angle = random_angle * self._rng.random() - math.pi
        rectangle = GOAL_RECT
        if abs(angle) == math.pi / 2:
            goal_x = 0
            goal_y = rectangle[3] if angle > 0 else rectangle[1]
        if abs(angle) <= math.pi / 4:
            goal_x = rectangle[2]
            goal_y = goal_x * math.tan(angle)
        elif math.pi / 4 < abs(angle) <= math.pi / 4 * 3:
            if angle > 0:
                goal_y = rectangle[3]
                goal_x = goal_y / math.tan(angle)
            else:
                goal_y = rectangle[1]
                goal_x = goal_y / math.tan(angle)
        else:
            goal_x = rectangle[0]
            goal_y = goal_x * math.tan(angle)
        return goal_x, goal_y


def _clip(value, low, high):
    return max(low, min(high, value))


def _point_to_line_distance(point_x, point_y, line_x1, line_y1, line_x2, line_y2):
    """AirsimGymEnv.getDis (airsim_env.py:914-924)."""
    a = line_y2 - line_y1
    b = line_x1 - line_x2
    c = line_x2 * line_y1 - line_x1 * line_y2
    return abs(a * point_x + b * point_y + c) / math.sqrt(a * a + b * b)
