"""Fake backend of the Jiminy CartPole driver: a pure Python stand-in for ``CartPoleJiminyEnv``.

Why a fake: the acceptance gate cannot import the upstream package (it needs the compiled Jiminy engine,
NumPy and Gymnasium), and package code never imports the clone.  This module re-implements the interface the
Gymnasium bridge uses (``reset``, ``step``, ``close``, ``unwrapped`` and the two spaces) and the physics of
``gym_jiminy.envs:CartPoleJiminyEnv`` in the simple pendulum form described by the toy URDF.

The constants that the upstream files state are cited below; the values that are only a modelling choice of
this fake are marked ``# placeholder``.  The fake is not the upstream environment: it uses Python's
``random.Random`` rather than the numpy generator seeded by ``BaseJiminyEnv._initialize_seed``, it does not
run the Jiminy engine, and it was never compared with a real run.  Those differences are in the fidelity
``gaps`` of the driver.

Gate G7 reads this class: its public methods and property are names that ``CartPoleJiminyEnv`` (through
``BaseJiminyEnv``) defines in the clone.
"""

import math
import random

# python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:20-23
STEP_DT = 0.02
CONTROL_DT = 0.02
# python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:24-27
X_THRESHOLD = 2.4
THETA_THRESHOLD = 12.0 * math.pi / 180.0
# python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:28-35
RANDOM_MAX = 0.05
# python/gym_jiminy/envs/gym_jiminy/envs/__init__.py:31-38 (the TimeLimit gym.make adds to the registration)
MAX_EPISODE_STEPS = 500
# data/toys_models/cartpole/cartpole.urdf:25
EFFORT_LIMIT = 10.0
# The three commands of AVAIL_CTRL (cartpole.py:131-134): left, zero, right.
AVAIL_CTRL = (-EFFORT_LIMIT, 0.0, EFFORT_LIMIT)
# data/toys_models/cartpole/cartpole.urdf:37-40 and :59-64
MASS_CART = 1.0
MASS_POLE = 0.1
POLE_LENGTH = 1.0
# placeholder: standard gravity of the simplified point-mass model; the Jiminy engine owns it upstream
GRAVITY = 9.81
# The default simulation_duration_max of BaseJiminyEnv (generic.py:125); the fake keeps the same truncation.
SIMULATION_DURATION_MAX = 86400.0
# The joint velocity limits of the toy URDF (cartpole.urdf:25 and :47), which bound the observation space.
VELOCITY_LIMIT = 100.0


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float64"

    def contains(self, values):
        return len(values) == len(self.low) and all(
            low <= value <= high for low, value, high in zip(self.low, values, self.high))


class FakeCartPoleJiminyEnv:
    """A point-mass cart-pole with the actions and truncations of ``CartPoleJiminyEnv``.

    The observation order follows the upstream ``EncoderSensor`` layout: the matrix rows are Q then V
    (core/src/hardware/basic_sensors.cc:394), the columns are the slider then the pole sensor
    (cartpole.py:117-121), and ``reshape((-1,))`` flattens it row by row (cartpole.py:197-199), so the
    four values are ``[cart position, pole angle, cart velocity, pole velocity]``.
    """

    def __init__(self, continuous=False, debug=False, viewer_kwargs=None):
        if continuous:
            raise ValueError("the fake CartPole implements only the default discrete action space")
        self.debug = bool(debug)
        self.viewer_kwargs = dict(viewer_kwargs or {})
        self.action_space = Discrete(len(AVAIL_CTRL))
        self.observation_space = Box(
            [-X_THRESHOLD, -THETA_THRESHOLD, -VELOCITY_LIMIT, -VELOCITY_LIMIT],
            [X_THRESHOLD, THETA_THRESHOLD, VELOCITY_LIMIT, VELOCITY_LIMIT])
        self._rng = random.Random()
        self._state = None
        self._elapsed_steps = 0
        self._done = False

    @property
    def unwrapped(self):
        return self

    def reset(self, *, seed=None, options=None):
        if options:
            # BaseJiminyEnv.reset only reads options["reset_hook"] (generic.py:640-647); a JSON caller cannot
            # supply a callable, so the fake accepts and ignores the mapping.
            pass
        if seed is not None:
            self._rng = random.Random(seed)
        x = self._rng.uniform(-RANDOM_MAX, RANDOM_MAX)                 # cartpole.py:189-190
        theta = self._rng.uniform(-RANDOM_MAX, RANDOM_MAX)             # cartpole.py:189-190
        x_dot = self._rng.uniform(-RANDOM_MAX, RANDOM_MAX)             # cartpole.py:192-193
        theta_dot = self._rng.uniform(-RANDOM_MAX, RANDOM_MAX)         # cartpole.py:192-193
        self._state = [x, theta, x_dot, theta_dot]
        self._elapsed_steps = 0
        self._time_s = 0.0
        self._done = False
        return self._observation(), {}

    def step(self, action):
        if not self.action_space.contains(action):                    # cartpole.py:177-180
            raise AssertionError(f"{action!r} ({type(action)}) invalid")
        if self._state is None:
            raise RuntimeError("No simulation running. Please call `reset` before `step`.")
        if self._done:
            raise RuntimeError("the episode has ended; reset the environment first")
        x, theta, x_dot, theta_dot = self._state
        force = AVAIL_CTRL[action]                                    # cartpole.py:208
        sin_theta, cos_theta = math.sin(theta), math.cos(theta)
        # placeholder: the textbook point-mass cart-pole equations for the toy URDF (MASS_CART at the
        # slider, MASS_POLE at POLE_LENGTH).  Jiminy integrates the same rigid body with its own engine.
        denominator = MASS_CART + MASS_POLE * sin_theta * sin_theta
        x_acc = (force + MASS_POLE * POLE_LENGTH * theta_dot * theta_dot * sin_theta
                 - MASS_POLE * GRAVITY * sin_theta * cos_theta) / denominator
        theta_acc = (GRAVITY * sin_theta - x_acc * cos_theta) / POLE_LENGTH
        # cartpole.py:143-146: the euler_explicit integrator; positions use the old velocities.
        x = x + STEP_DT * x_dot
        theta = theta + STEP_DT * theta_dot
        x_dot = x_dot + STEP_DT * x_acc
        theta_dot = theta_dot + STEP_DT * theta_acc
        self._state = [x, theta, x_dot, theta_dot]
        self._elapsed_steps += 1
        self._time_s += STEP_DT
        # BaseJiminyEnv.has_terminated truncates when the observation leaves its bounds (generic.py:1461-1464),
        # and generic.py:847-849 adds the simulation-duration bound; the registration adds the 500-step limit.
        truncated = bool(
            abs(x) > X_THRESHOLD or abs(theta) > THETA_THRESHOLD
            or abs(x_dot) > VELOCITY_LIMIT or abs(theta_dot) > VELOCITY_LIMIT
            or self._elapsed_steps >= MAX_EPISODE_STEPS
            or self._time_s > SIMULATION_DURATION_MAX)
        self._done = truncated
        # cartpole.py:210-216: the reward is 1.0 as long as the episode is not terminated; the default
        # has_terminated never sets terminated, so the truncating step still pays 1.0.
        reward = 1.0
        return self._observation(), reward, False, truncated, {}

    def close(self):
        self._state = None
        self._done = True

    def _observation(self):
        x, theta, x_dot, theta_dot = self._state
        return [x, theta, x_dot, theta_dot]
