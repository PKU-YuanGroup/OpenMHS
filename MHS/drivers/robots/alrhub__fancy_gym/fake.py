"""Fake backend of the fancy_gym driver: a pure Python stand-in for ``gymnasium.make("fancy/SimpleReacher-v0")``.

Why a fake: the acceptance gate runs without fancy_gym, gymnasium, numpy or matplotlib (the clone imports all of
them at module import, ``simple_reacher.py:3-5``), and package code never imports the clone.  This module
re-implements the torque-controlled reaching model of
``fancy_gym.envs.classic_control.simple_reacher.simple_reacher:SimpleReacherEnv`` and of its two base classes
(``BaseReacherTorqueEnv`` and ``BaseReacherEnv``), and the 200-step time limit that the registration
``fancy/SimpleReacher-v0`` adds (``fancy_gym/envs/__init__.py:38-46``).

Every upstream constant below cites the line of the clone at commit
``da1bced0181ced8267247779c001509a2fc94635``; the numbers that exist only as test data are marked ``# placeholder``.
The public members of ``FakeSimpleReacherEnv`` are the ones the upstream class has (``reset``, ``step``, ``close``
and the ``dt`` property; gate G7); the two space classes duck-type ``gymnasium.spaces.Box`` (the bridge reads
``low``, ``high``, ``shape`` and ``dtype``).  Instance attributes are not checked by G7.

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* the random generator is Python's ``random.Random``, upstream uses numpy's generator, so one seed does not give
  the same trajectory on both;
* states and observations are Python floats and lists; upstream returns float32 numpy arrays;
* the self-collision test only checks the joint limits, not the segment intersections of
  ``base_reacher.py:114-118``;
* there is no rendering, no ``PassiveEnvChecker`` and no fancy_gym movement-primitive wrapper.

Nothing here talks to a device.
"""

import math
import random

# fancy_gym/envs/__init__.py:38-45: the registration sets n_links=2 and max_episode_steps=200
DEFAULT_N_LINKS = 2
MAX_EPISODE_STEPS = 200
# fancy_gym/envs/classic_control/base_reacher/base_reacher_torque.py:16: self.max_torque = 1000
MAX_TORQUE = 1000.0
# fancy_gym/envs/classic_control/base_reacher/base_reacher.py:21: self._dt = 0.01
DT = 0.01
# fancy_gym/envs/classic_control/simple_reacher/simple_reacher.py:31: self.steps_before_reward = 199
STEPS_BEFORE_REWARD = 199
# fancy_gym/envs/classic_control/base_reacher/base_reacher.py:38-39: the joint limits are -pi and +pi
JOINT_LIMIT = math.pi
# fancy_gym/envs/classic_control/base_reacher/base_reacher.py:34: the straight start is [pi/2, 0, ...]
START_FIRST_JOINT = math.pi / 2


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.low):
            return False
        return all(low <= float(item) <= high for item, low, high in zip(value, self.low, self.high))


class FakeSimpleReacherEnv:
    """``SimpleReacherEnv`` without numpy: ``reset(seed, options)`` and ``step(action)`` return gymnasium tuples."""

    def __init__(self, n_links=DEFAULT_N_LINKS, target=None, random_start=True, allow_self_collision=False,
                 **options):
        del options                                    # upstream passes **kwargs through to its base classes
        self.n_links = int(n_links)
        self.inital_target = target                    # the upstream spelling (simple_reacher.py:24)
        self.random_start = bool(random_start)
        self.allow_self_collision = bool(allow_self_collision)
        self.link_lengths = [1.0] * self.n_links
        self._dt = DT
        # base_reacher_torque.py:16-18: one torque per link, bounded by +-max_torque
        bound = [MAX_TORQUE] * self.n_links
        self.action_space = Box([-value for value in bound], bound)
        # simple_reacher.py:33-40: the declared bounds are 3*n_links+3 long (cos, sin, velocity, target x/y, steps)
        state_bound = ([JOINT_LIMIT] * self.n_links + [JOINT_LIMIT] * self.n_links
                       + [math.inf] * self.n_links + [math.inf, math.inf, math.inf])
        self.observation_space = Box([-value for value in state_bound], state_bound)
        # base_reacher.py:34-35: the default straight arm and zero velocity
        self._start_pos = [START_FIRST_JOINT] + [0.0] * (self.n_links - 1)
        self._start_vel = [0.0] * self.n_links
        self.j_min = [-JOINT_LIMIT] * self.n_links
        self.j_max = [JOINT_LIMIT] * self.n_links
        self.steps_before_reward = STEPS_BEFORE_REWARD
        self._joint_angles = list(self._start_pos)
        self._angle_velocity = list(self._start_vel)
        self._joints = [[0.0, 0.0] for _ in range(self.n_links + 1)]
        self._goal = [1.0, 1.0]                        # placeholder: replaced by reset()
        self._steps = 0
        self._elapsed_steps = 0
        self._is_collided = False
        self._rng = random.Random()                    # placeholder: the fake's generator, upstream uses numpy
        self._update_joints()

    @property
    def dt(self):
        """``BaseReacherEnv.dt`` (base_reacher.py:61-63)."""

        return self._dt

    # -- gymnasium API -----------------------------------------------------
    def reset(self, *, seed=None, options=None):
        # simple_reacher.py:46-54: generate a goal, reset, generate the goal again, reset again
        self._generate_goal()
        self._reset_state(seed, options)
        self._generate_goal()
        return self._reset_state(seed, options)

    def step(self, action):
        # base_reacher_torque.py:20-37: a torque step with no termination and no truncation of the class itself
        values = [float(item) for item in action]
        self._angle_velocity = [speed + self.dt * torque for speed, torque in zip(self._angle_velocity, values)]
        self._joint_angles = [angle + self.dt * speed for angle, speed in zip(self._joint_angles, self._angle_velocity)]
        self._update_joints()
        self._is_collided = self._check_collisions()
        reward, info = self._get_reward(values)
        self._steps += 1
        # fancy_gym/envs/__init__.py:42: gymnasium.make wraps fancy/SimpleReacher-v0 in a 200-step TimeLimit
        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        return self._get_obs(), reward, False, truncated, info

    def close(self):
        self._joint_angles = None

    # -- the upstream model ------------------------------------------------
    def _reset_state(self, seed, options):
        if seed is not None:
            self._rng = random.Random(int(seed))       # placeholder: Python RNG, upstream uses numpy
        try:
            random_start = options.get("random_start", self.random_start)
        except AttributeError:
            random_start = self.random_start
        if random_start:
            first_joint = self._rng.uniform(math.pi / 4, 3 * math.pi / 4)   # base_reacher.py:82
            self._joint_angles = [first_joint] + [0.0] * (self.n_links - 1)
            self._start_pos = list(self._joint_angles)
        else:
            self._joint_angles = list(self._start_pos)
        self._angle_velocity = list(self._start_vel)
        self._joints = [[0.0, 0.0] for _ in range(self.n_links + 1)]
        self._update_joints()
        self._steps = 0
        self._elapsed_steps = 0
        return self._get_obs(), {}

    def _update_joints(self):
        # base_reacher.py:95-103: link lengths are one and the angles are cumulative
        angles = []
        total = 0.0
        for angle in self._joint_angles:
            total += angle
            angles.append(total)
        self._joints = [[0.0, 0.0]]
        for angle, length in zip(angles, self.link_lengths):
            self._joints.append([self._joints[-1][0] + length * math.cos(angle),
                                 self._joints[-1][1] + length * math.sin(angle)])

    def _check_self_collision(self):
        # base_reacher.py:105-112: a joint outside its limits is a collision; the segment test of :114-118 is a gap
        if self.allow_self_collision:
            return False
        return any(angle > limit or angle < -limit
                   for angle, limit in zip(self._joint_angles, self.j_max))

    def _check_collisions(self):
        return self._check_self_collision()            # simple_reacher.py:98-99

    def _get_reward(self, action):
        # simple_reacher.py:56-70: the distance term starts at steps_before_reward; reward_ctrl is the squared torque
        diff = [effector - goal for effector, goal in zip(self._end_effector(), self._goal)]
        reward_dist = 0.0
        if not self.allow_self_collision:
            self._is_collided = self._check_self_collision()
        if self._steps >= self.steps_before_reward:
            reward_dist -= math.sqrt(sum(item * item for item in diff))
        reward_ctrl = sum(item * item for item in action)
        return reward_dist - reward_ctrl, {"reward_dist": reward_dist, "reward_ctrl": reward_ctrl}

    def _get_obs(self):
        # simple_reacher.py:75-83: cos, sin, velocity, end effector minus goal, steps
        theta = self._joint_angles
        diff = [effector - goal for effector, goal in zip(self._end_effector(), self._goal)]
        return ([math.cos(angle) for angle in theta] + [math.sin(angle) for angle in theta]
                + list(self._angle_velocity) + diff + [float(self._steps)])

    def _end_effector(self):
        return self._joints[self.n_links]               # base_reacher.py:137-139

    def _generate_goal(self):
        # simple_reacher.py:85-96: draw from the square of side 2*total_length until the norm is below total_length
        if self.inital_target is None:
            total_length = sum(self.link_lengths)
            goal = [total_length, total_length]
            while math.sqrt(sum(item * item for item in goal)) >= total_length:
                goal = [self._rng.uniform(-total_length, total_length) for _ in range(2)]
        else:
            goal = [float(item) for item in self.inital_target]
        self._goal = goal
