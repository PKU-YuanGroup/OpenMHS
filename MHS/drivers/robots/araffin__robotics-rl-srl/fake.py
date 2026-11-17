"""Fake backend of the Gymnasium driver: an analytic stand-in for ``OmniRobotEnv``'s in-process simulator.

Why a fake: the upstream simulator imports numpy, OpenCV, PyTorch, SciPy, ZMQ and seaborn and is Python 2 only on its
ROS path (``README.md:27``); package code never imports the clone.  This module re-implements the discrete control of
``environments.omnirobot_gym.omnirobot_env:OmniRobotEnv`` (the class the driver names as ``native``) and of the
in-process ``OmniRobotSimulatorSocket``.  It is an analytic stand-in, not a recording: no captured traffic is replayed.

The public members mirror the native class's surface (gate G7): ``reset``, ``step`` and ``seed`` follow the legacy Gym
API of the clone (the native ``reset`` takes no arguments, ``step`` returns the 4-tuple ``(observation, reward, done,
info)``), and ``getEnvState``, ``getObservation``, ``getTargetPos``, ``getGroundTruth``, ``getGroundTruthDim``,
``getRobotPos``, ``render``, ``actionPolicyTowardTarget``, ``closeServerConnection`` and ``close`` are present.  The
bridge adapts the legacy API; the fake does not modernise the native signatures.

The constants below are the clone's values, cited in comments.  The observation image size and the pixel colours are
test data (marked ``placeholder``), not device facts: the device returns a 224 x 224 x 3 image
(``environments/omnirobot_gym/omnirobot_env.py:29-30,120-122``) and this fake returns a smaller marker image whose real
size is named in RESULT.json and in the driver's fidelity gaps.

Differences from the upstream simulator, all repeated in the fidelity gaps of the driver:

* the background, marker sprites, camera projection, image resizing, luminosity noise and robot/marker noise are not
  modelled; positions are exact and the image is a placeholder;
* ``seed()`` controls this fake's random generator.  The upstream ``SRLGymEnv.seed`` only sets ``np_random``
  (``environments/srl_env.py:71-78``) while the simulator draws from numpy's global generator
  (``real_robots/omnirobot_utils/omnirobot_manager_base.py:88-89``), so the upstream simulator is not seeded by it;
* ``shape_reward`` is stored but not applied, as in the clone (the parameter is documented but unused).
"""

import math
import random

# environments/omnirobot_gym/omnirobot_env.py:29-30
RENDER_HEIGHT = 224
RENDER_WIDTH = 224
# real_robots/constants.py:78-83
REWARD_TARGET_REACH = 1
REWARD_NOTHING = 0
REWARD_BUMP_WALL = -1
# real_robots/constants.py:90-93
MAX_STEPS = 250
MIN_X, MAX_X = -0.85, 0.85
MIN_Y, MAX_Y = -0.85, 0.85
# real_robots/constants.py:96-101
INIT_MIN_X, INIT_MAX_X = -0.7, 0.7
INIT_MIN_Y, INIT_MAX_Y = -0.7, 0.7
TARGET_MIN_X, TARGET_MAX_X = -0.7, 0.7
TARGET_MIN_Y, TARGET_MAX_Y = -0.7, 0.7
# real_robots/constants.py:110,121
DIST_TO_TARGET_THRESHOLD = 0.2
STEP_DISTANCE = 0.1
# environments/omnirobot_gym/omnirobot_env.py:35
N_DISCRETE_ACTIONS = 4
# real_robots/constants.py:114-119
FORWARD, BACKWARD, LEFT, RIGHT = 0, 1, 2, 3

# placeholder: a small stand-in for the 224 x 224 x 3 image, to keep receipts small
FAKE_OBS_SIZE = 16
# placeholder: marker colours of the stand-in image (red target, green robot, both when they overlap)
TARGET_PIXEL = [255, 0, 0]
ROBOT_PIXEL = [0, 128, 0]
OVERLAP_PIXEL = [255, 128, 0]


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
    """Duck-typed ``gym.spaces.Box``: the bounds and shape of the native observation space."""

    def __init__(self, low, high, shape, dtype):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = dtype


class FakeOmniRobotEnv:
    """The default discrete OmniRobot environment without the upstream simulator's dependencies."""

    def __init__(self, renders=False, name="Omnirobot", is_discrete=True, save_path='srl_zoo/data/', state_dim=-1,
                 learn_states=False, srl_model="raw_pixels", record_data=False, action_repeat=1,
                 random_target=True, shape_reward=False, env_rank=0, srl_pipe=None, **_):
        if action_repeat != 1:
            raise NotImplementedError                    # environments/omnirobot_gym/omnirobot_env.py:81-82
        if not is_discrete:
            raise NotImplementedError("the fake implements the default discrete action space")
        self._is_discrete = True
        self._random_target = random_target
        self._shape_reward = shape_reward
        self.action_space = Discrete(N_DISCRETE_ACTIONS)  # environments/omnirobot_gym/omnirobot_env.py:105-106
        self.observation_space = Box(0, 255, (RENDER_WIDTH, RENDER_HEIGHT, 3), "uint8")  # :120-122
        self._rng = random.Random()
        self.seed(0)                                    # environments/srl_env.py:31
        self.episode_terminated = False                 # environments/omnirobot_gym/omnirobot_env.py:95
        self._env_step_counter = 0
        self.n_contacts = 0
        self.episode_idx = 0
        self.reward = REWARD_NOTHING
        self.robot_pos = [0.0, 0.0]                     # placeholder: overwritten by reset()
        self.target_pos = [0.0, 0.0]                    # placeholder: overwritten by reset()
        self.observation = self.getObservation()

    # -- legacy Gym API of the clone -------------------------------------------------
    def seed(self, seed=None):
        """Seed the fake's generator (the native method is inherited from ``SRLGymEnv``)."""
        self._rng = random.Random(seed)
        return [seed]

    def reset(self):
        """The native reset: reset the counters and return the first observation."""
        self.episode_terminated = False                 # environments/omnirobot_gym/omnirobot_env.py:272
        self._env_step_counter = 0                      # :274
        self.n_contacts = 0                             # :276
        self.episode_idx += 1                           # real_robots/omnirobot_utils/omnirobot_manager_base.py:113
        self.robot_pos = [                             # manager base:88-89 with constants:96-97
            self._rng.uniform(INIT_MIN_X, INIT_MAX_X),
            self._rng.uniform(INIT_MIN_Y, INIT_MAX_Y),
        ]
        if self._random_target or self.episode_idx == 1:  # simulator_server:413-419 with constants:100-101
            self.target_pos = [
                self._rng.uniform(TARGET_MIN_X, TARGET_MAX_X),
                self._rng.uniform(TARGET_MIN_Y, TARGET_MAX_Y),
            ]
        self.reward = REWARD_NOTHING
        self.getEnvState()
        return self.getObservation()

    def step(self, action):
        """One discrete command; returns ``(observation, reward, done, {})`` like the native ``step``."""
        assert self.action_space.contains(action)       # environments/omnirobot_gym/omnirobot_env.py:182
        self._env_step_counter += 1                     # :193
        bumped = self._move(int(action))
        self.reward = self._reward(bumped)              # manager base:147-158
        observation = self.getObservation()             # :202-203
        done = self._hasEpisodeTerminated()             # :204
        return observation, self.reward, done, {}       # :211-214

    # -- native helpers ---------------------------------------------------------------
    def getEnvState(self):
        """The simulator's state reply: position, reward and target position (native ``getEnvState``)."""
        return {
            "position": list(self.robot_pos),
            "reward": self.reward,
            "target_pos": list(self.target_pos),
        }

    def getObservation(self):
        """Return the placeholder marker image (the native method receives and resizes the camera frame)."""
        self.observation = self._render()
        return self.observation

    def getTargetPos(self):
        return list(self.target_pos)

    @staticmethod
    def getGroundTruthDim():
        return 2                                        # environments/omnirobot_gym/omnirobot_env.py:252

    def getGroundTruth(self):
        return list(self.getRobotPos())                 # :254-259

    def getRobotPos(self):
        return list(self.robot_pos)                     # :261-265

    def render(self, mode='rgb_array'):
        return self.observation                         # :311-341 returns the observation

    def closeServerConnection(self):
        """The fake has no socket to close."""

    def close(self):
        """The fake has no GUI or native resource to release (``SRLGymEnv.close`` is a pass)."""

    def actionPolicyTowardTarget(self):
        """The clone's greedy policy toward the target (used by scripts, kept for the native surface)."""
        if abs(self.robot_pos[0] - self.target_pos[0]) > abs(self.robot_pos[1] - self.target_pos[1]):
            return FORWARD if self.robot_pos[0] < self.target_pos[0] else BACKWARD
        return LEFT if self.robot_pos[1] < self.target_pos[1] else RIGHT

    # -- analytic stand-in of the simulator -------------------------------------------
    def _move(self, action):
        """Move one discrete step, or report a wall bump (manager base:22-68, simulator_server:243-269)."""
        x, y = self.robot_pos
        bumped = False
        if action == FORWARD:
            if x + STEP_DISTANCE < MAX_X:
                x += STEP_DISTANCE
            else:
                bumped = True
        elif action == BACKWARD:
            if x - STEP_DISTANCE > MIN_X:
                x -= STEP_DISTANCE
            else:
                bumped = True
        elif action == LEFT:
            if y + STEP_DISTANCE < MAX_Y:
                y += STEP_DISTANCE
            else:
                bumped = True
        elif action == RIGHT:
            if y - STEP_DISTANCE > MIN_Y:
                y -= STEP_DISTANCE
            else:
                bumped = True
        else:
            raise AssertionError(f"invalid discrete action {action!r}")
        self.robot_pos = [x, y]
        return bumped

    def _reward(self, bumped):
        """The reward rule of manager base:147-158."""
        distance = math.hypot(self.robot_pos[0] - self.target_pos[0],
                              self.robot_pos[1] - self.target_pos[1])
        if distance < DIST_TO_TARGET_THRESHOLD:
            return REWARD_TARGET_REACH
        if bumped:
            return REWARD_BUMP_WALL
        return REWARD_NOTHING

    def _hasEpisodeTerminated(self):
        """The exact native termination rule (environments/omnirobot_gym/omnirobot_env.py:290-301)."""
        if self.episode_terminated or self._env_step_counter > MAX_STEPS:
            return True
        if abs(self.reward - REWARD_TARGET_REACH) < 0.000001:
            self.n_contacts += 1
        else:
            self.n_contacts = 0
        return False

    def _render(self):
        """Placeholder image: one target pixel and one robot pixel on a black background."""
        image = [[[0, 0, 0] for _ in range(FAKE_OBS_SIZE)] for _ in range(FAKE_OBS_SIZE)]
        target_x, target_y = self._pixel(self.target_pos)
        robot_x, robot_y = self._pixel(self.robot_pos)
        if (target_x, target_y) == (robot_x, robot_y):
            image[target_y][target_x] = list(OVERLAP_PIXEL)
        else:
            image[target_y][target_x] = list(TARGET_PIXEL)
            image[robot_y][robot_x] = list(ROBOT_PIXEL)
        return image

    @staticmethod
    def _pixel(position):
        """Map a world position inside the boundary to a placeholder pixel index."""
        x = int(round((position[0] - MIN_X) / (MAX_X - MIN_X) * (FAKE_OBS_SIZE - 1)))
        y = int(round((position[1] - MIN_Y) / (MAX_Y - MIN_Y) * (FAKE_OBS_SIZE - 1)))
        return max(0, min(FAKE_OBS_SIZE - 1, x)), max(0, min(FAKE_OBS_SIZE - 1, y))
