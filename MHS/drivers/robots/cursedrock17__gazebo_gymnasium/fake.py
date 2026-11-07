"""Analytic fake backend of the GazeboCartPole-v0 driver.

The acceptance gate cannot build the upstream environment: its constructor imports
the native ``gz.sim8`` bindings (inprocess_vec_env.py:476-480), and the package
needs Linux, ROS 2 Jazzy, Gazebo Harmonic, gymnasium and stable-baselines3.  This
module therefore stands in for ``GazeboEnv`` (the class named by ``native``) with
a pure-Python point-mass cartpole integrator.

It preserves the native Gymnasium surface: ``action_space``, ``observation_space``,
``reset(seed, options)`` returning ``(observation, info)``, ``step(action)``
returning ``(observation, reward, terminated, truncated, info)``, ``render()`` and
``close()``.  The action space, observation space, reward, thresholds and limits
are copied from the pinned upstream code and cited below.  The equations and
their mass/length/gravity constants are placeholders: they are not the SDF
inertias and no trajectory was compared with Gazebo.  Nothing here talks to a
device or imports the clone.
"""

import math
import random

# agent_spec.py:740,748: action 1 applies +10 N, every other action -10 N.
ACTION_FORCE = 10.0
# agent_spec.py:730-731: termination thresholds.
POLE_ANGLE_LIMIT = 0.20944
CART_POSITION_LIMIT = 2.4
# agent_spec.py:753,757: the reset pole angle is uniform in +/-0.05 rad.
RESET_ANGLE = 0.05
# agent_spec.py:221-222: five physics ticks per step and a 500-transition limit.
FRAME_SKIP = 5
MAX_EPISODE_STEPS = 500
# inprocess_vec_env.py:57: the in-process world's maximum physics step.
PHYSICS_DT = 0.01
STEP_DT = FRAME_SKIP * PHYSICS_DT
# agent_spec.py:762-767: the Box observation bounds.
OBSERVATION_LOW = [-4.8, -math.inf, -0.41887903, -math.inf]
OBSERVATION_HIGH = [4.8, math.inf, 0.41887903, math.inf]

# Point-mass cartpole constants of this analytic stand-in.  They are test data,
# not the cartpole_bare SDF inertias, and are deliberately marked as such.
GRAVITY = 9.8  # placeholder
CART_MASS = 1.0  # placeholder
POLE_MASS = 1.0  # placeholder
POLE_HALF_LENGTH = 0.5  # placeholder
POLE_INERTIA_FACTOR = 4.0 / 3.0  # placeholder


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete`` (the bridge reads ``n`` and ``start``)."""

    def __init__(self, n):
        self.n = int(n)
        self.start = 0
        self.shape = ()
        self.dtype = "int64"


class Box:
    """Duck-typed ``gymnasium.spaces.Box`` (the bridge reads ``low``, ``high`` and ``shape``)."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeGazeboCartPole:
    """``GazeboEnv(agent='cartpole')`` without Gazebo: the same API and result semantics."""

    metadata = {"render_modes": []}

    def __init__(self, **_options):
        self.observation_space = Box(OBSERVATION_LOW, OBSERVATION_HIGH)
        self.action_space = Discrete(2)  # agent_spec.py:773
        self._rng = random.Random()
        self._x = 0.0  # agent_spec.py:756: reset cart position
        self._x_dot = 0.0  # agent_spec.py:756: reset cart velocity
        self._theta = 0.0
        self._theta_dot = 0.0
        self._steps = 0
        self._started = False
        self._closed = False

    def reset(self, *, seed=None, options=None):
        """``GazeboEnv.reset``: reseed only when asked, reset joints, return ``(obs, {})``."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if seed is not None:
            self._rng = random.Random(int(seed))
        # agent_spec.py:752-758: cart at zero, pole angle uniform in +/-0.05,
        # both velocities zero.
        self._x = 0.0
        self._x_dot = 0.0
        self._theta = self._rng.uniform(-RESET_ANGLE, RESET_ANGLE)
        self._theta_dot = 0.0
        self._steps = 0
        self._started = True
        return self._observation(), {}

    def step(self, action):
        """Advance five 0.01 s ticks, then apply the upstream scoring semantics."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if not self._started:
            raise RuntimeError("reset() must be called before step()")
        index = int(action)
        if index not in (0, 1):
            raise ValueError("the cartpole action must be 0 or 1")
        force = ACTION_FORCE if index == 1 else -ACTION_FORCE

        # Point-mass cartpole equations, integrated for one 50 ms environment
        # step.  This is the placeholder dynamics of the fake, not the SDF model.
        sin_theta = math.sin(self._theta)
        cos_theta = math.cos(self._theta)
        total_mass = CART_MASS + POLE_MASS
        pole_mass_length = POLE_MASS * POLE_HALF_LENGTH
        temp = (force + pole_mass_length * self._theta_dot * self._theta_dot * sin_theta) / total_mass
        theta_acc = ((GRAVITY * sin_theta - cos_theta * temp)
                     / (POLE_HALF_LENGTH * (POLE_INERTIA_FACTOR
                                            - POLE_MASS * cos_theta * cos_theta / total_mass)))
        x_acc = temp - pole_mass_length * theta_acc * cos_theta / total_mass

        self._x_dot += x_acc * STEP_DT
        self._x += self._x_dot * STEP_DT
        self._theta_dot += theta_acc * STEP_DT
        self._theta += self._theta_dot * STEP_DT
        self._steps += 1

        # agent_spec.py:776-779: terminate on the angle or position threshold.
        terminated = (abs(self._theta) > POLE_ANGLE_LIMIT
                      or abs(self._x) > CART_POSITION_LIMIT)
        # inprocess_vec_env.py:1168-1181 and gym_env.py:73-79: the TimeLimit
        # marker is dropped when the episode also terminated.
        truncated = self._steps >= MAX_EPISODE_STEPS and not terminated
        return self._observation(), 1.0, bool(terminated), bool(truncated), {}

    def render(self):
        """``GazeboEnv.metadata`` declares no render modes, so rendering is a no-op."""
        return None

    def close(self):
        self._closed = True

    def _observation(self):
        """agent_spec.py:774-775: cart position/velocity, then pole angle/velocity."""
        return [float(self._x), float(self._x_dot), float(self._theta), float(self._theta_dot)]
