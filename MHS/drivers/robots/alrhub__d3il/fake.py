"""Fake backend of the d3il driver: a pure Python kinematic stand-in for ``gym.make("sorting-v0")``.

Why a fake: the clone imports MuJoCo, numpy, gym and cv2 at module import, and package code never imports the clone.
This module re-implements the contract of ``gym_sorting.envs:Sorting_Env`` (the class the driver names as ``native``)
without MuJoCo: the two spaces, the seeded start, the box pushing, the reward and the episode limit of the registered
``sorting-v0`` environment.  The public members are the ones the upstream class and its ``GymEnvWrapper`` base have
(``reset``, ``step``, ``seed``, ``get_observation``, ``get_reward``, ``is_finished``; gate G7), and the two space
classes duck-type ``gym.spaces.Box`` (the bridge reads ``low``, ``high`` and ``shape``).

Every upstream constant below cites the line of the clone at commit
``1d9c71850d4fc1477cee17b557c8b97d70b13071``; numbers that are test data of this fake are marked ``# placeholder``.
The start sampling mirrors ``BlockContextManager`` (sorting.py:46-119): six positions are drawn from the six Box spaces
and shuffled, then the first two are assigned to the red and the blue box (sorting.py:121-135).  The fake uses Python's
``random.Random``; upstream uses numpy's global generator, so one seed does not give the same start state on the two.

What this is not: the upstream environment.  It has no arm joints, no MuJoCo contacts, no gripper, no camera and no
rendering, and it does not integrate the 1 ms physics substeps; it advances one 35 ms control step per call.  These
differences are listed in the fidelity ``gaps`` of driver.py.  Nothing here talks to a device.
"""

import math
import random

# sorting-v0 registration: kwargs max_steps_per_episode=100, render=True, num_boxes=2, if_vision=False
# (gym_sorting/__init__.py:7).  The registered value wins over the constructor default 2e3 (sorting.py:197).
MAX_STEPS_PER_EPISODE = 100
# sorting.py:196: n_substeps: int = 35
N_SUBSTEPS = 35
# sorting.py:237-239: the action space low [-0.01, -0.01], high [0.01, 0.01]
ACTION_LOW, ACTION_HIGH = -0.01, 0.01
# sorting.py:240-242: the observation space shape (8,)
OBSERVATION_SIZE = 8
# sorting_objects.py:11: init_end_eff_pos = [0.525, -0.3, 0.25]
ROBOT_START = (0.525, -0.3)
# sorting.py:535-536: the red target region x (0.3, 0.5), y (0.22, 0.41); the blue one x (0.525, 0.725)
RED_TARGET_X, RED_TARGET_Y = (0.3, 0.5), (0.22, 0.41)
BLUE_TARGET_X, BLUE_TARGET_Y = (0.525, 0.725), (0.22, 0.41)
# sorting.py:52-74: (x_min, x_max, y_min, y_max, yaw_min_deg, yaw_max_deg) of box1_space .. box6_space
BOX_SPACES = (
    (0.4, 0.5, -0.15, -0.1, -90.0, 90.0),
    (0.4, 0.5, -0.05, 0.0, -90.0, 90.0),
    (0.4, 0.5, 0.05, 0.1, -90.0, 90.0),
    (0.55, 0.65, -0.15, -0.1, -90.0, 90.0),
    (0.55, 0.65, -0.05, 0.0, -90.0, 90.0),
    (0.55, 0.65, 0.05, 0.1, -90.0, 90.0),
)
# placeholder: the radius within which the fake end-effector pushes a box; test data, not an upstream bound
PUSH_RADIUS = 0.04


class Box:
    """Duck-typed ``gym.spaces.Box``: one lower and one upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeSortingEnv:
    """``Sorting_Env`` without MuJoCo: the spaces, the seeded start, the pushing and the episode limit."""

    def __init__(
        self,
        n_substeps=N_SUBSTEPS,
        max_steps_per_episode=MAX_STEPS_PER_EPISODE,
        debug=False,
        random_env=False,
        interactive=False,
        render=True,
        num_boxes=2,
        if_vision=False,
        **options,
    ):
        del options, debug, random_env, render
        if int(num_boxes) != 2:
            raise ValueError("this fake models only the registered num_boxes=2 environment")
        if if_vision:
            raise ValueError("this fake cannot render the camera observations of if_vision=True")
        self.n_substeps = int(n_substeps)
        self.max_steps_per_episode = int(max_steps_per_episode)
        self.num_boxes = int(num_boxes)
        self.interactive = bool(interactive)
        # sorting.py:237-242: the action and observation spaces of Sorting_Env
        self.action_space = Box([ACTION_LOW, ACTION_LOW], [ACTION_HIGH, ACTION_HIGH])
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self._rng = random.Random(0)  # placeholder: the bridge seeds the generator before the first reset
        self.np_random = self._rng
        # GymEnvWrapper.__init__ (gym_env_wrapper.py:31-35) and Sorting_Env.reset (sorting.py:545-552)
        self.episode = 0
        self.env_step_counter = 0
        self.terminated = False
        self.success = False
        self.min_inds = []
        self._robot = list(ROBOT_START)
        # placeholder: reset replaces both boxes and their yaw with the sampled context
        self._red, self._red_yaw = None, 0.0
        self._blue, self._blue_yaw = None, 0.0

    # gym_env_wrapper.py:41-43: seed(seed=None) seeds the environment's generator and returns the accepted seed
    def seed(self, seed=None):
        if seed is not None:
            seed = int(seed)
            self._rng = random.Random(seed)
            self.np_random = self._rng
        return [seed]

    # sorting.py:545-557: reset clears the counters and starts a new context
    def reset(self, random=True, context=None):
        self.terminated = False
        self.success = False
        self.env_step_counter = 0
        self.episode += 1
        self.min_inds = []
        sampled = self._sample_context() if random or context is None else context
        self._robot = list(ROBOT_START)
        (self._red, self._red_yaw) = sampled[0]
        (self._blue, self._blue_yaw) = sampled[1]
        return self.get_observation()

    # sorting.py:340-350: [robot xy, red box xy, red yaw tangent, blue box xy, blue yaw tangent]
    def get_observation(self):
        return [
            self._robot[0],
            self._robot[1],
            self._red[0],
            self._red[1],
            math.tan(math.radians(self._red_yaw)),
            self._blue[0],
            self._blue[1],
            math.tan(math.radians(self._blue_yaw)),
        ]

    # sorting.py:509-511: get_reward returns 0
    def get_reward(self):
        return 0.0

    # gym_env_wrapper.py:124-137: the episode ends on the terminated flag, early termination or the step limit
    def is_finished(self):
        if (
            self.terminated
            or self._check_early_termination()
            or self.env_step_counter >= self.max_steps_per_episode - 1
        ):
            return True
        return False

    # sorting.py:444-458: one step moves the robot, then reports observation, reward, done and info
    def step(self, action, gripper_width=None, desired_vel=None, desired_acc=None):
        del gripper_width, desired_vel, desired_acc
        dx, dy = float(action[0]), float(action[1])
        self._robot[0] += dx
        self._robot[1] += dy
        self._push(self._red, dx, dy)
        self._push(self._blue, dx, dy)
        observation = self.get_observation()
        reward = self.get_reward()
        done = self.is_finished()
        self.success = self._check_early_termination()
        self.env_step_counter += 1
        # placeholder: mode is a fake summary of which box is inside its target; upstream packs two mode bits
        mode = (1 if self._inside(self._red, RED_TARGET_X, RED_TARGET_Y) else 0) | (
            2 if self._inside(self._blue, BLUE_TARGET_X, BLUE_TARGET_Y) else 0
        )
        return observation, reward, done, {"mode": mode, "success": self.success, "min_inds": list(self.min_inds)}

    # sorting.py:513-543: both boxes must leave the start region and enter their target region
    def _check_early_termination(self):
        if self._inside(self._red, RED_TARGET_X, RED_TARGET_Y) and self._inside(
            self._blue, BLUE_TARGET_X, BLUE_TARGET_Y
        ):
            self.terminated = True
            return True
        return False

    @staticmethod
    def _inside(position, x_range, y_range):
        return x_range[0] < position[0] < x_range[1] and y_range[0] < position[1] < y_range[1]

    def _push(self, box, dx, dy):
        distance = math.hypot(self._robot[0] - box[0], self._robot[1] - box[1])
        if distance <= PUSH_RADIUS:
            box[0] += dx
            box[1] += dy

    # sorting.py:88-119: six samples from the six spaces, shuffled before the first two become the red and blue box
    def _sample_context(self):
        contexts = []
        for x_min, x_max, y_min, y_max, yaw_min, yaw_max in BOX_SPACES:
            position = [self._rng.uniform(x_min, x_max), self._rng.uniform(y_min, y_max)]
            contexts.append((position, self._rng.uniform(yaw_min, yaw_max)))
        self._rng.shuffle(contexts)
        return contexts
