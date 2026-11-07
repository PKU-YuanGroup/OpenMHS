"""Fake backend of the CS285 Gymnasium driver: a pure Python stand-in for the obstacle environment.

Why a fake: the clone needs MuJoCo 2.1 and mujoco-py for its robot environments (README.md:102-119), but this
environment (``cs285.envs.obstacles:Obstacles``) is plain Python and numpy.  The gate never imports the clone and
never installs its dependencies, so this module re-implements the obstacle environment with Python lists.  Every
constant and rule cites a line of the clone at commit 6da04f367e52a451c202ae7e5477994c1d149baf.

The public members are the ones ``Obstacles`` has (``seed``, ``pick_start_pos``, ``reset``, ``do_reset``,
``_get_obs``, ``get_score``, ``get_reward``, ``step``, ``is_valid``, ``oob``; gate G7), and ``Box`` duck-types
``gym.spaces.Box`` (the bridge reads ``low``, ``high``, ``shape``).  The fake keeps ``plt``, ``fig`` and ``render``
out: it cannot draw, and ``cap.world.render.v1`` is not bound.

What this is not: the upstream environment.

* the random start comes from Python's ``random.Random``, upstream draws it from numpy's global generator, so one
  seed gives different start positions on the two implementations;
* observations, rewards and info are plain Python floats and lists, upstream returns float32/float64 numpy arrays;
* the 500-step ``TimeLimit`` that ``gym.make`` adds around ``obstacles-cs285-v0`` is not modelled: this fake serves
  the raw class, whose ``step`` has no truncation;
* upstream ignores ``seed=0`` (``if seed:`` at obstacles_env.py:60); this fake applies it, so the bridge's default
  seed 0 gives a repeatable first episode.

None of these differences is a device bound or a fact; they are test-data choices and are listed in the fidelity
``gaps`` of driver.py.
"""

import math
import random

# hw4/cs285/envs/obstacles/obstacles_env.py:11-12
ACTION_DIM = 2
OBSERVATION_DIM = 4
# hw4/cs285/envs/obstacles/obstacles_env.py:13-14
BOUNDARY_MIN = -0.99
BOUNDARY_MAX = 0.99
# hw4/cs285/envs/obstacles/obstacles_env.py:40
EPS = 0.1
# hw4/cs285/envs/obstacles/obstacles_env.py:32-38: [x of top left, y of top left, width x, height y]
OBSTACLES = [
    [-0.4, 0.8, 0.4, 0.3],
    [-0.9, 0.3, 0.2, 0.6],
    [0.6, -0.1, 0.12, 0.4],
    [-0.1, 0.2, 0.15, 0.4],
    [0.1, -0.7, 0.3, 0.15],
]


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeObstacles:
    """``Obstacles`` without numpy or matplotlib: ``reset(seed)`` and ``step(action)`` return what the clone's do."""

    def __init__(self, start=(-0.5, 0.75), end=(0.7, -0.8), random_starts=True):
        # The three constructor defaults are test data of the upstream class (obstacles_env.py:6), not device
        # bounds: the deployment may pass other start/end/random_starts values.
        self.action_dim = self.ac_dim = ACTION_DIM                         # placeholder (obstacles_env.py:11)
        self.observation_dim = self.obs_dim = OBSERVATION_DIM              # placeholder (obstacles_env.py:12)
        self.boundary_min = BOUNDARY_MIN                                  # placeholder (obstacles_env.py:13)
        self.boundary_max = BOUNDARY_MAX                                  # placeholder (obstacles_env.py:14)
        self.action_space = Box([self.boundary_min] * ACTION_DIM,
                                [self.boundary_max] * ACTION_DIM)          # placeholder (obstacles_env.py:16-18)
        self.observation_space = Box([-math.inf] * OBSERVATION_DIM,
                                     [math.inf] * OBSERVATION_DIM)        # placeholder (obstacles_env.py:20-22)
        self.env_name = "obstacles"                                       # placeholder (obstacles_env.py:24)
        self.is_gym = True                                                # placeholder (obstacles_env.py:25)
        self.start = [float(value) for value in start]                    # placeholder (obstacles_env.py:6)
        self.end = [float(value) for value in end]                        # placeholder (obstacles_env.py:6)
        self.current = list(self.start)                                   # placeholder (obstacles_env.py:29)
        self.random_starts = bool(random_starts)                          # placeholder (obstacles_env.py:6)
        self.obstacles = [list(obstacle) for obstacle in OBSTACLES]       # placeholder (obstacles_env.py:33-38)
        self.eps = EPS                                                    # placeholder (obstacles_env.py:40)
        self.reset_pose = list(self.start)
        self.reset_vel = list(self.end)
        self.counter = 0
        self.reward_dict = {}
        self._rng = random.Random()
        self._rng.seed(0)                                                 # placeholder (test-data seed)

    def seed(self, seed):
        """``np.random.seed(seed)`` (obstacles_env.py:43-44) with Python's generator for one fake object."""
        self._rng = random.Random(int(seed))

    def pick_start_pos(self):
        """Draw a valid random start, or return the configured start (obstacles_env.py:48-55)."""
        if self.random_starts:
            while True:
                temp = [
                    self._rng.uniform(self.boundary_min, self.boundary_min + 1.25),
                    self._rng.uniform(self.boundary_max - 0.4, self.boundary_max),
                ]
                if self.is_valid(temp):
                    return temp
        return list(self.start)

    def reset(self, seed=None):
        """``reset(seed=None)`` (obstacles_env.py:59-66); unlike the clone it also honours ``seed=0``."""
        if seed is not None:
            self.seed(seed)
        self.reset_pose = self.pick_start_pos()
        self.reset_vel = list(self.end)
        return self.do_reset(self.reset_pose, self.reset_vel)

    def do_reset(self, reset_pose, reset_vel, reset_goal=None):
        """Set current and end and return the observation (obstacles_env.py:68-78)."""
        self.current = [float(value) for value in reset_pose]
        self.end = [float(value) for value in reset_vel]
        self.counter = 0
        return self._get_obs()

    def _get_obs(self):
        """``np.concatenate([self.current, self.end])`` (obstacles_env.py:82-83)."""
        return [float(self.current[0]), float(self.current[1]), float(self.end[0]), float(self.end[1])]

    def get_score(self, obs):
        """``-1 * np.abs(current - end)`` per axis (obstacles_env.py:85-89)."""
        return [-abs(float(obs[0]) - float(obs[-2])), -abs(float(obs[1]) - float(obs[-1]))]

    def get_reward(self, observations, actions):
        """Negative Euclidean distance and the done flag (obstacles_env.py:114-132)."""
        current = [float(observations[0]), float(observations[1])]
        end = [float(observations[-2]), float(observations[-1])]
        distance = math.hypot(current[0] - end[0], current[1] - end[1])
        self.reward_dict = {"dist": -distance, "r_total": -distance}
        done = 1.0 if distance < self.eps else 0.0
        if (current[0] < self.boundary_min or current[1] < self.boundary_min
                or current[0] > self.boundary_max or current[1] > self.boundary_max):
            done = 1.0
        return -distance, done

    def step(self, action):
        """Clip, scale and apply one move (obstacles_env.py:139-156)."""
        self.counter += 1
        clipped = [max(-1.0, min(1.0, float(value))) for value in action]
        scaled = [value / 10.0 for value in clipped]
        candidate = [self.current[0] + scaled[0], self.current[1] + scaled[1]]
        if self.is_valid(candidate):
            self.current = candidate
        observation = self._get_obs()
        reward, done = self.get_reward(observation, scaled)
        score = self.get_score(observation)
        info = {
            "ob": list(observation),
            "rewards": {name: (-list(value) if isinstance(value, list) else value)
                        for name, value in self.reward_dict.items()},
            "score": list(score),
        }
        return observation, reward, done, info

    def is_valid(self, point):
        """Boundary and obstacle test of ``is_valid`` (obstacles_env.py:194-221)."""
        if any(value <= self.boundary_min or value >= self.boundary_max for value in point):
            return False
        for top_left_x, top_left_y, width, height in self.obstacles:
            bottom_left_y = top_left_y - height
            top_right_x = top_left_x + width
            if top_left_x < point[0] < top_right_x and bottom_left_y < point[1] < top_left_y:
                return False
        return True

    def oob(self, point):
        """``(x <= boundary_min) | (x >= boundary_max)`` per axis (obstacles_env.py:224-225)."""
        return [value <= self.boundary_min or value >= self.boundary_max for value in point]
