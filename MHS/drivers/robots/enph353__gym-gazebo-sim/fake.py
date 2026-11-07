"""Fake backend of the Gym-Gazebo-Sim CartpoleEnv driver: a pure-Python kinematic stand-in.

Why a fake: the upstream ``CartpoleEnv`` constructor calls ``GazeboEnv.__init__``, which starts
``ros2 launch`` for Gazebo Harmonic and ROS 2 Jazzy and sleeps four seconds
(``src/gym_gazebo/core/gazebo_env.py:26-34``); the gate has no ROS 2, Gazebo or sourced
workspace, and package code never imports the clone.  This module therefore re-implements the
public surface of ``gym_gazebo.envs.cartpole_env:CartpoleEnv`` - ``reset(seed, options)``,
``step(action)``, ``close()`` and the two spaces - with the upstream action rule and terminal
semantics and no simulator.

What is modelled (cited from the clone):

* the action rule ``current_vel += 0.2 if action == 1 else -0.2``
  (``src/gym_gazebo/envs/cartpole_env.py:136-137``);
* the returned state order [x, x_dot, theta, theta_dot] rounded to two decimals
  (``src/gym_gazebo/envs/cartpole_env.py:66-78``);
* the termination condition ``|theta| > theta_limit_rad or |x| > x_limit`` and the 1.0/0.0
  reward (``src/gym_gazebo/envs/cartpole_env.py:176-204``) with the limits 12*pi/180 and 15
  (``src/gym_gazebo/envs/cartpole_env.py:28-29``);
* the ``gym.spaces.Box`` observation space and ``gym.spaces.Discrete(2)`` action space
  (``src/gym_gazebo/envs/cartpole_env.py:31-39``);
* the 3000-step registration limit (``src/gym_gazebo/__init__.py:6-10``), which gymnasium.make
  applies as a TimeLimit wrapper.

What this is not: the upstream simulator.  There is no Gazebo, ros_gz_bridge, ROS 2 graph,
DART physics, cart-pole body, joint or controller.  The cart position is advanced by a
placeholder bookkeeping interval (``# placeholder``) so the action has an observable effect;
the pole angle and angular velocity stay at placeholder zero values and no dynamics are
integrated.  All start-state numbers are placeholders, not device facts.  The fake was never
compared with a live Gazebo run.
"""

import math

# src/gym_gazebo/envs/cartpole_env.py:28-29: theta_limit_rad = 12 * pi / 180, x_limit = 15.
THETA_LIMIT_RAD = 12 * math.pi / 180
X_LIMIT = 15
# src/gym_gazebo/envs/cartpole_env.py:136-137: current_vel changes by 0.2 per step.
VELOCITY_STEP = 0.2
# src/gym_gazebo/__init__.py:6-10: registration max_episode_steps=3000.
MAX_EPISODE_STEPS = 3000
# placeholder: the fake's own bookkeeping interval, not the Gazebo physics step (SDF max_step_size
# is 0.005 s at ros2_ws/src/cartpole_ros/world/cartpole.sdf:6-9) and not a measured message period.
STEP_S = 0.01
# placeholder: the fake starts every episode from rest at the world origin; the real pose comes
# from the Gazebo world and the reset plugin.
START_X = 0.0
START_X_DOT = 0.0
START_THETA = 0.0
START_THETA_DOT = 0.0


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
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeCartpoleEnv:
    """The public surface of ``CartpoleEnv`` without Gazebo or ROS 2."""

    def __init__(self):
        self.theta_limit_rad = THETA_LIMIT_RAD
        self.x_limit = X_LIMIT
        # src/gym_gazebo/envs/cartpole_env.py:31-39: the declared Box and Discrete spaces.
        self.observation_space = Box(
            [-2 * THETA_LIMIT_RAD, -15, float("-inf"), float("-inf")],
            [2 * THETA_LIMIT_RAD, 15, float("inf"), float("inf")],
        )
        self.action_space = Discrete(2)
        self.current_vel = START_X_DOT  # placeholder
        self._x = START_X           # placeholder
        self._theta = START_THETA   # placeholder
        self._theta_dot = START_THETA_DOT  # placeholder
        self._steps = 0
        self._terminated = False
        self._closed = False

    def reset(self, seed=None, options=None):
        """Upstream reset returns ``(state, {})``; seed and options are accepted and unused."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self.current_vel = START_X_DOT
        self._x = START_X
        self._theta = START_THETA
        self._theta_dot = START_THETA_DOT
        self._steps = 0
        self._terminated = False
        return self._observation(), {}

    def step(self, action):
        """Apply the upstream velocity rule and return the five Gymnasium values."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if self._terminated:
            raise RuntimeError("the episode is over; call reset()")
        self.current_vel += VELOCITY_STEP if action == 1 else -VELOCITY_STEP
        self._x += self.current_vel * STEP_S
        self._steps += 1
        state = self._observation()
        terminated = abs(state[2]) > self.theta_limit_rad or abs(state[0]) > self.x_limit
        self._terminated = terminated
        truncated = self._steps >= MAX_EPISODE_STEPS
        reward = 1.0 if not terminated else 0.0
        return state, reward, terminated, truncated, {}

    def close(self):
        """The fake owns no simulator process; closing only marks it closed."""
        self._closed = True

    def _observation(self):
        """The upstream returned order, rounded to two decimals (cartpole_env.py:77-78)."""
        return [round(self._x, 2), round(self.current_vel, 2),
                round(self._theta, 2), round(self._theta_dot, 2)]
