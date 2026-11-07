"""Fake backend of the Social Navigation driver: a pure Python stand-in for ``SocialNavEnv``.

Why a fake: the upstream class imports ``gym``, ``numpy`` and ``matplotlib`` and reads the ETH Pedestrian data files
under ``gym_social_navigation/envs/data``; the acceptance gate never installs or imports the clone.  This module
re-implements the observable behaviour of ``gym_social_navigation.envs.social_nav_env:SocialNavEnv``: the 43-value
Box observation, the 10-value Discrete action list, the Dubins-car pose update, the synthetic pedestrian history and
the terminal conditions.  The public members are the ones the upstream class has (``reset`` and ``step``; gate G7),
and the space classes duck-type ``gym.spaces.Discrete`` and ``gym.spaces.Box`` (the bridge reads ``n``, ``start``,
``low``, ``high`` and ``shape``).

Every upstream constant below cites the line of the clone at the pinned commit
bdc8e72c0f7f738ebe99b6966b1c37af26a342af.  The pedestrian trace and the narrow start/goal band are synthetic test
data, marked ``# placeholder``; they are not facts, limits or a recording of the ETH dataset.

What this is not, and what the driver's fidelity ``gaps`` say: the pedestrian trace is not the upstream dataset, the
start and goal are drawn from a narrow safe band instead of the full unit square, there is no rendering and no
wall-clock pacing, and the fake's ``reset(seed=...)`` exists only for repeatable tests (upstream ``reset()`` takes no
arguments).
"""

import math
import random

# social_nav_env.py:11-19 and :51 (the constructor's "Parameters worth changing")
AGENT_HIST = 3                          # social_nav_env.py:11
MAX_VEL = 0.75                          # social_nav_env.py:12
DV = 0.25                               # social_nav_env.py:13
STEERING_ANGLE = 30 * math.pi / 180     # social_nav_env.py:14
PROX_RAD = 10                           # social_nav_env.py:15
NUM_AGENTS = 4                          # social_nav_env.py:16
NUM_PATH_POINTS = 4                     # social_nav_env.py:17
MIN_PATH_LEN = 0.45                     # social_nav_env.py:18
EPISODE_SECONDS = 60                    # social_nav_env.py:19
TIMESTEP = 0.4                          # social_nav_env.py:51
EPISODE_STEPS = int(EPISODE_SECONDS / TIMESTEP)   # social_nav_env.py:52

# social_nav_env.py:22-28 (the reward function parameters)
ALPHA = 3.5                             # social_nav_env.py:22
BETA = 5                                # social_nav_env.py:23
GOAL_REWARD = 10                        # social_nav_env.py:24
COLLISION_PENALTY = 20                  # social_nav_env.py:25
OUT_OF_BOUNDS_PENALTY = 15              # social_nav_env.py:26
GOAL_THRESH = 0.05                      # social_nav_env.py:27
COLLISION_DIST = 0.30                   # social_nav_env.py:28

# placeholder: synthetic trace length, not an upstream bound and not a device limit
TRACE_STEPS = 400


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)                  # placeholder: a test-side stand-in, not an upstream bound
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


def _speeds(start):
    """The upstream ``np.arange(start, MAX_VEL + DV, DV)`` values, without numpy.

    ``social_nav_env.py:59`` builds the actions from ``dv`` and ``max_vel + dv``; the step and the rounding keep the
    same endpoints for the two starts (0.25 and 0).
    """
    count = int(round((MAX_VEL + DV - start) / DV))
    return [round(start + index * DV, 10) for index in range(count)]


def _track(phase):
    """A synthetic pedestrian trace on the far side of the unit square (placeholder test data)."""

    points = {}
    for moment in range(TRACE_STEPS):    # placeholder: 400 generated samples, not an upstream length
        angle = 2 * math.pi * moment / 240.0          # placeholder: the trace's period
        points[moment] = [0.5 + 0.32 * math.cos(angle + phase),      # placeholder: x path
                          0.80 + 0.08 * math.sin(angle + phase)]     # placeholder: y path
    return points


def _agent_data():
    """The fake's one scene: two pedestrians, shaped like ``parse_data``'s output (placeholder test data)."""

    track_zero = _track(0.0)             # placeholder
    track_one = _track(math.pi)          # placeholder
    return [{
        0: track_zero,
        1: track_one,
        "num_agents": 1,                 # placeholder: one is the last agent id of the two-agent trace
        "limits": [0, TRACE_STEPS, 0.0, 1.0, 0.0, 1.0],   # placeholder: [mint, maxt, minx, maxx, miny, maxy]
    }]


class FakeSocialNavEnv:
    """The pure Python SocialNavEnv: ``reset``/``step`` return what the upstream environment returns.

    The observation layout follows ``social_nav_env.py:55-58``: 3 robot-pose values, then
    ``2*NUM_AGENTS*(AGENT_HIST+1)`` pedestrian values, then ``2*NUM_PATH_POINTS`` path values.
    """

    def __init__(self, test=False):
        self.test = bool(test)           # social_nav_env.py:8
        self.agent_hist = AGENT_HIST
        self.steering_angle = STEERING_ANGLE
        self.prox_rad = PROX_RAD
        self.num_agents = NUM_AGENTS
        self.num_path_points = NUM_PATH_POINTS
        self.min_path_len = MIN_PATH_LEN
        self.episode_time = EPISODE_STEPS
        self.alpha = ALPHA
        self.beta = BETA
        self.goal_reward = GOAL_REWARD
        self.collision_penalty = COLLISION_PENALTY
        self.out_of_bounds_penalty = OUT_OF_BOUNDS_PENALTY
        self.goal_thresh = GOAL_THRESH
        self.collision_dist = COLLISION_DIST
        self.timestep = TIMESTEP
        self.agent_data = _agent_data()
        self.actions = ([("L", value) for value in _speeds(DV)]
                        + [("S", value) for value in _speeds(0)]
                        + [("R", value) for value in _speeds(DV)])
        size = 3 + 2 * self.num_agents * (self.agent_hist + 1) + 2 * self.num_path_points
        self.low = [0.0] * size          # social_nav_env.py:56
        self.high = [1.0] * size         # social_nav_env.py:57
        self.observation_space = Box(self.low, self.high)      # social_nav_env.py:58
        self.action_space = Discrete(len(self.actions))        # social_nav_env.py:60
        self._rng = random.Random()      # placeholder: the fake's RNG; upstream uses numpy's global generator
        self.reset()                     # social_nav_env.py:65

    # -- reset ----------------------------------------------------------------
    def reset(self, *, seed=None, options=None):
        """Reset the fake world; ``seed`` and ``options`` are fake conveniences, upstream takes neither."""

        if seed is not None:
            self._rng = random.Random(int(seed))
        index = self._rng.randrange(len(self.agent_data))      # social_nav_env.py:192
        self.agents = self.agent_data[index]                  # social_nav_env.py:193
        self.mint, self.maxt = 0, self.agents["limits"][1] - self.agents["limits"][0]   # social_nav_env.py:194
        self.minx, self.maxx = self.agents["limits"][2], self.agents["limits"][3]       # social_nav_env.py:195
        self.miny, self.maxy = self.agents["limits"][4], self.agents["limits"][5]       # social_nav_env.py:196
        if self.maxt - self.episode_time > 0:                 # social_nav_env.py:199
            self.time = self._rng.randrange(0, self.maxt - self.episode_time)           # social_nav_env.py:200
        else:
            self.time = 0                                     # social_nav_env.py:202
        self.start_time = self.time                           # social_nav_env.py:203
        self._set_random_path()                               # social_nav_env.py:205
        return (self._observation(), {})

    def _set_random_path(self):
        """A start/goal pair from a narrow safe band (placeholder test data, not the upstream full square)."""

        p1 = [self._rng.uniform(0.12, 0.22), self._rng.uniform(0.10, 0.20)]   # placeholder
        p2 = [self._rng.uniform(0.78, 0.88), self._rng.uniform(0.10, 0.20)]   # placeholder
        while math.dist(p1, p2) < self.min_path_len:          # social_nav_env.py:119
            p1 = [self._rng.uniform(0.12, 0.22), self._rng.uniform(0.10, 0.20)]   # placeholder
            p2 = [self._rng.uniform(0.78, 0.88), self._rng.uniform(0.10, 0.20)]   # placeholder
        self.start = p1                                      # social_nav_env.py:123
        self.goal = p2                                       # social_nav_env.py:124
        theta = (math.atan2(self.goal[1] - self.start[1], self.goal[0] - self.start[0])
                 + self._rng.gauss(0, math.pi / 8)) % (2 * math.pi)          # social_nav_env.py:138
        self.pose = [self.start[0] * (self.maxx - self.minx) + self.minx,
                     self.start[1] * (self.maxy - self.miny) + self.miny, theta]   # social_nav_env.py:139
        self.pose_history = [list(self.pose)]                # social_nav_env.py:140
        self.path = []
        for index in range(self.num_path_points):            # social_nav_env.py:137
            fraction = index / max(1, self.num_path_points - 1)
            self.path.extend([p1[0] + (p2[0] - p1[0]) * fraction,
                              p1[1] + (p2[1] - p1[1]) * fraction])

    # -- observation ----------------------------------------------------------
    def _agent_states(self, moment):
        """``get_agent_states`` (social_nav_env.py:150-184): closest first, zero padded to NUM_AGENTS."""

        states = []
        for agent_id in [key for key in self.agents if isinstance(key, int)]:
            if moment not in self.agents[agent_id]:
                continue
            position = self.agents[agent_id][moment]
            offset = [position[0] - self.pose[0], position[1] - self.pose[1]]
            if offset[0] * offset[0] + offset[1] * offset[1] >= self.prox_rad ** 2:
                continue
            row = [0.0] * (2 * (self.agent_hist + 1))
            row[0:2] = position
            for index in range(1, self.agent_hist + 1):
                if moment - index in self.agents[agent_id]:
                    row[2 * index:2 * index + 2] = self.agents[agent_id][moment - index]
                else:
                    fill = self.agents[agent_id][moment - index + 1]
                    for missing in range(self.agent_hist - index + 1):
                        row[2 * (index + missing):2 * (index + missing) + 2] = fill
                    break
            states.append(row)
        if not states:
            return [0.0] * (2 * self.num_agents * (self.agent_hist + 1))
        robot = [(self.pose[0] - self.minx) / (self.maxx - self.minx),
                 (self.pose[1] - self.miny) / (self.maxy - self.miny)]
        states.sort(key=lambda row: math.dist(row[0:2], robot))
        while len(states) < self.num_agents:
            states.append([0.0] * (2 * (self.agent_hist + 1)))
        return [value for row in states[:self.num_agents] for value in row]

    def _observation(self):
        robot = [(self.pose[0] - self.minx) / (self.maxx - self.minx),
                 (self.pose[1] - self.miny) / (self.maxy - self.miny),
                 (self.pose[2] % (2 * math.pi)) / (2 * math.pi)]      # social_nav_env.py:207-208
        return robot + self._agent_states(self.time) + self.path

    # -- step -----------------------------------------------------------------
    def step(self, action):
        """Apply one action and return ``(observation, reward, terminated, truncated, info)``."""

        kind, speed = self.actions[action]                     # social_nav_env.py:224
        previous = list(self.pose)                             # social_nav_env.py:226
        if kind == "L":                                        # social_nav_env.py:229-232
            self.pose[0] += speed / self.steering_angle * (
                math.sin(self.steering_angle * self.timestep + self.pose[2]) - math.sin(self.pose[2]))
            self.pose[1] += speed / self.steering_angle * (
                -math.cos(self.steering_angle * self.timestep + self.pose[2]) + math.cos(self.pose[2]))
            self.pose[2] += self.steering_angle * self.timestep
        elif kind == "R":                                      # social_nav_env.py:233-236
            self.pose[0] += speed / self.steering_angle * (
                -math.sin(-self.steering_angle * self.timestep + self.pose[2]) + math.sin(self.pose[2]))
            self.pose[1] += speed / self.steering_angle * (
                math.cos(-self.steering_angle * self.timestep + self.pose[2]) - math.cos(self.pose[2]))
            self.pose[2] -= self.steering_angle * self.timestep
        else:                                                  # social_nav_env.py:237-239
            self.pose[0] += self.timestep * speed * math.cos(self.pose[2])
            self.pose[1] += self.timestep * speed * math.sin(self.pose[2])
        self.pose[2] = self.pose[2] % (2 * math.pi)            # social_nav_env.py:241
        self.pose_history.insert(0, list(self.pose))           # social_nav_env.py:243
        self.pose_history = self.pose_history[0:self.agent_hist]   # social_nav_env.py:244
        self.time += 1                                         # social_nav_env.py:247
        observation = self._observation()                      # social_nav_env.py:250
        robot = [(self.pose[0] - self.minx) / (self.maxx - self.minx),
                 (self.pose[1] - self.miny) / (self.maxy - self.miny),
                 self.pose[2] / (2 * math.pi)]                 # social_nav_env.py:248
        old_robot = [(previous[0] - self.minx) / (self.maxx - self.minx),
                     (previous[1] - self.miny) / (self.maxy - self.miny),
                     previous[2] / (2 * math.pi)]              # social_nav_env.py:249
        delta_goal = -math.dist(robot[0:2], self.goal) + math.dist(old_robot[0:2], self.goal)   # :253-255
        delta_path = -self._distance_to_path(robot) + self._distance_to_path(old_robot)         # :258-260
        reward = self.alpha * delta_path + self.beta * delta_goal                               # :263
        for agent_id in [key for key in self.agents if isinstance(key, int)]:                   # :267
            if self.time in self.agents[agent_id]:                                              # :269
                agent = [self.agents[agent_id][self.time][0] * (self.maxx - self.minx) + self.minx,
                         self.agents[agent_id][self.time][1] * (self.maxy - self.miny) + self.miny]  # :270-271
                if math.dist(agent, self.pose[:2]) < self.collision_dist:                       # :272
                    return observation, -self.collision_penalty, True, False, {}                 # :273-275
        if math.dist(robot[0:2], self.goal) < self.goal_thresh:                                 # :278
            return observation, self.goal_reward, True, False, {}                                # :279-281
        if self.time >= self.start_time + self.episode_time:                                     # :284
            return observation, reward, True, False, {}                                          # :285-286
        if robot[0] < 0 or robot[0] > 1 or robot[1] < 0 or robot[1] > 1:                         # :289
            return observation, -self.out_of_bounds_penalty, True, False, {}                     # :290-292
        return observation, reward, False, False, {}                                             # :294

    def _distance_to_path(self, pose):
        """``distance_to_path`` (social_nav_env.py:210-217)."""

        a = self.start[1] - self.goal[1]
        b = self.goal[0] - self.start[0]
        c = self.goal[1] * (self.start[0] - self.goal[0]) + self.goal[0] * (self.goal[1] - self.start[1])
        return abs(a * pose[0] + b * pose[1] + c) / math.sqrt(a * a + b * b)
