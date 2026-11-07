"""Fake backend of the NSMR driver: a pure Python stand-in for ``NsmrGymEnv`` (the class named by ``native``).

Why a fake: the upstream package is a legacy ``gym`` environment that needs ``gym>=0.10.5`` and numpy
(requirements.txt:1-2) plus the Cython raycasting extension (setup.py:13-15), and package code never imports the clone.
This module re-implements the observable surface of ``nsmr/envs/NsmrGymEnv.py`` (the methods declared by NsmrGymEnv,
gate G7) with the same legacy API: ``reset()`` returns the observation, ``step(action)`` returns the 4-tuple
``(observation, reward, done, info)`` and ``seed(seed)`` returns ``[seed]``.  The two space classes duck-type
``gym.spaces.Dict`` and ``gym.spaces.Box`` (the bridge reads ``spaces``, ``low``, ``high`` and ``shape``).

What this is not (all differences are in the driver's fidelity ``gaps``):

* it does not raycast the map: the observation carries 720 placeholder readings (the real count, robot.json:18) all at
  max_range, so the lidar is shape-faithful but value-placeholder;
* it does not model the upstream noise, stuck state or oversight events, and it never reports a collision;
* it has no renderer: ``render`` returns None;
* it draws its start pose and target from Python's ``random.Random``, while the upstream draws them from numpy's global
  random module (nsmr.py:61-69, 168), so the same seed does not produce the same trajectory on the two.

Numbers marked ``placeholder`` are test data, not facts: they stand for values the upstream draws or computes.  The
configuration constants cite the bundled robot file (nsmr/robots/robot.json) at the pinned commit.
"""

import math
import random

# nsmr/robots/robot.json:2-8 (the default robot configuration)
ROBOT_RADIUS = 0.3
MAX_LINEAR_VELOCITY = 1.0
MIN_LINEAR_VELOCITY = 0.0
MAX_ANGULAR_VELOCITY = 1.0
MIN_ANGULAR_VELOCITY = -1.0
MAX_LINEAR_ACCELERATION = 0.5
MAX_ANGULAR_ACCELERATION = 1.0
# nsmr/robots/robot.json:17-22 (the default lidar configuration)
LIDAR_NUM_RANGE = 720
LIDAR_MIN_RANGE = 0.1
LIDAR_MAX_RANGE = 30.0
# nsmr/envs/nsmr.py:15,18 (the NSMR constructor default)
DT = 0.1
# placeholder: the upstream reward defaults of NsmrGymEnv.py:17-21, used only by this stand-in
DEFAULT_REWARD_PARAMS = {
    "goal_reward": 5.0,
    "collision_penalty": 5.0,
    "alpha": 0.3,
    "beta": 0.01,
    "stop_penalty": 0.05,
}
# placeholder: the stand-in's map is 10 m x 10 m (simple_map.json:2-4, 1000 * 0.01), and a reset keeps the target at
# least 5 m away so a short test sequence does not reach the goal
MAP_LOW, MAP_HIGH = 1.0, 9.0
MIN_TARGET_DISTANCE = 5.0


class Dict:
    """Duck-typed ``gym.spaces.Dict``: a mapping of field names to spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = None


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element plus a shape."""

    def __init__(self, low, high, shape=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"


def _angle_normalize(angle):
    """``angle_normalize`` of nsmr/utils/utils.py:3-4."""

    return math.atan2(math.sin(angle), math.cos(angle))


class FakeNsmrGymEnv:
    """``NsmrGymEnv`` without gym, numpy or the Cython raycasting extension."""

    # NsmrGymEnv.py:10-13
    metadata = {"render.modes": ["human", "rgb_array"], "video.frames_per_second": 50}

    def __init__(self, robot="robot", layout="simple_map", reward_params=None, max_steps=500):  # max_steps: NsmrGymEnv.py:22
        self.robot_name = robot
        self.layout_name = layout
        self.reward_params = dict(DEFAULT_REWARD_PARAMS)
        if reward_params:
            self.reward_params.update(reward_params)
        self.max_steps = int(max_steps)
        self._rng = random.Random()
        self._pre_linear = 0.0
        self._pre_angular = 0.0
        self.set_gym_space()
        self.reset()

    def set_gym_space(self):
        # NsmrGymEnv.py:119-127: the observation space; NsmrGymEnv.py:128-134: the action space
        self.observation_space = Dict({
            "lidar": Box([LIDAR_MIN_RANGE], [LIDAR_MAX_RANGE], (LIDAR_NUM_RANGE,)),
            "target": Box([0.0, -1.0, -1.0], [100.0, 1.0, 1.0], (3,)),
        })
        self.action_space = Box([MIN_LINEAR_VELOCITY, MIN_ANGULAR_VELOCITY],
                                [MAX_LINEAR_VELOCITY, MAX_ANGULAR_VELOCITY], (2,))

    def set_reward_params(self, reward_params):
        self.reward_params = dict(reward_params)
        self.reset()

    def set_env_config(self, robot, layout):
        self.robot_name = robot
        self.layout_name = layout
        self.set_gym_space()
        self.reset()

    def reset(self):
        # NsmrGymEnv.py:53-60: reset the pose and the noise parameters, then take the first observation
        self.t = 0
        self.pose = self._random_pose()
        self.target = self._random_target(self.pose)
        observation = self.get_observation()
        self.pre_dis = observation["target"][0]
        self.goal = False
        return observation

    def step(self, action):
        # NsmrGymEnv.py:62-72 with the update chain of nsmr.py:71-77
        linear, angular = float(action[0]), float(action[1])
        # nsmr.py:79-86: acceleration limit, then velocity clamp
        linear = max(self._pre_linear - MAX_LINEAR_ACCELERATION * DT,
                     min(self._pre_linear + MAX_LINEAR_ACCELERATION * DT, linear))
        angular = max(self._pre_angular - MAX_ANGULAR_ACCELERATION * DT,
                      min(self._pre_angular + MAX_ANGULAR_ACCELERATION * DT, angular))
        linear = max(MIN_LINEAR_VELOCITY, min(MAX_LINEAR_VELOCITY, linear))
        angular = max(MIN_ANGULAR_VELOCITY, min(MAX_ANGULAR_VELOCITY, angular))
        self._pre_linear, self._pre_angular = linear, angular
        # nsmr.py:88-98: the closed-form unicycle transition
        theta = self.pose[2]
        if abs(angular) < 1e-10:
            self.pose[0] += linear * math.cos(theta) * DT
            self.pose[1] += linear * math.sin(theta) * DT
            self.pose[2] += angular * DT
        else:
            self.pose[0] += linear / angular * (math.sin(theta + angular * DT) - math.sin(theta))
            self.pose[1] += linear / angular * (-math.cos(theta + angular * DT) + math.cos(theta))
            self.pose[2] += angular * DT
        self.pose[2] = _angle_normalize(self.pose[2])
        self.t += 1
        observation = self.get_observation()
        reward = self.get_reward(observation)
        done = self.is_done()
        info = {"pose": list(self.pose), "target": list(self.target), "goal": self.goal}
        return observation, reward, done, info

    def render(self, mode="human"):
        # placeholder: no renderer in this stand-in (the upstream uses nsmr/envs/renderer.py)
        return None

    def get_observation(self):
        # nsmr/envs/NsmrGymEnv.py:77-81
        return {
            "lidar": [LIDAR_MAX_RANGE] * LIDAR_NUM_RANGE,  # placeholder: no raycasting, every ray at max range
            "target": self._relative_target(),
        }

    def get_reward(self, observation):
        # nsmr/envs/NsmrGymEnv.py:83-98; collisions are never reported by this stand-in
        dis = observation["target"][0]
        ddis = self.pre_dis - dis
        theta = math.acos(max(-1.0, min(1.0, observation["target"][2])))
        if dis < ROBOT_RADIUS:
            reward = self.reward_params["goal_reward"]
            self.goal = True
        else:
            reward = self.reward_params["alpha"] * ddis
        if abs(ddis) < 1e-6:
            reward -= self.reward_params["stop_penalty"]
        reward -= self.reward_params["beta"] / (2 * math.pi) * abs(theta)
        self.pre_dis = dis
        return reward

    def is_done(self):
        # nsmr/envs/NsmrGymEnv.py:100-108 without the collision branch
        return bool(self.t >= self.max_steps or self.goal)

    def close(self):
        # nsmr/envs/NsmrGymEnv.py:110-111: there is no renderer window to close here
        self._closed = True

    def seed(self, seed=None):
        # nsmr/envs/NsmrGymEnv.py:113-115; this stand-in does use the generator, unlike NSMR's global numpy draws
        seeded = int(seed) if seed is not None else None
        self._rng = random.Random(seeded)
        self.np_random = self._rng
        return [seeded]

    def _random_pose(self):
        # placeholder: a pose drawn inside the 10 m x 10 m map (the upstream checks a collision map)
        return [
            self._rng.uniform(MAP_LOW, MAP_HIGH),
            self._rng.uniform(MAP_LOW, MAP_HIGH),
            self._rng.uniform(-math.pi, math.pi),
        ]

    def _random_target(self, pose):
        # placeholder: an in-map target at least MIN_TARGET_DISTANCE away
        for _ in range(100):
            target = [self._rng.uniform(MAP_LOW, MAP_HIGH), self._rng.uniform(MAP_LOW, MAP_HIGH)]
            if math.hypot(target[0] - pose[0], target[1] - pose[1]) >= MIN_TARGET_DISTANCE:
                return target
        return [MAP_HIGH, MAP_HIGH]  # placeholder: never reached with the loop above in practice

    def _relative_target(self):
        # nsmr.py:154-162: [distance, sin(theta), cos(theta)]
        theta = math.atan2(self.target[1] - self.pose[1], self.target[0] - self.pose[0])
        theta = _angle_normalize(theta - self.pose[2])
        return [
            math.hypot(self.target[0] - self.pose[0], self.target[1] - self.pose[1]),
            math.sin(theta),
            math.cos(theta),
        ]
