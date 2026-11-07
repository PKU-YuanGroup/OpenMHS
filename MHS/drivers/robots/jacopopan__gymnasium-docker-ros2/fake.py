"""Fake backend of the GDR2 driver: a pure Python stand-in for ``GDR2Env``.

The upstream :class:`gymnasium_docker_ros2.env.GDR2Env` does not model the point
mass itself.  It creates a Docker network and two containers, then forwards a
force over ZeroMQ to the ROS 2 simulation; the ``dynamics`` node integrates the
state and the ZeroMQ bridge steps Gazebo and waits for ``/state``
(``src/gymnasium_docker_ros2/env.py:108-116`` and
``resources/ros2_ws/src/dynamics/dynamics/dynamics_node.py:39-52``).  The gate
has no Docker daemon, ROS 2, Gazebo or ZeroMQ, and package code never imports
the clone, so this module re-implements the dynamics node's update in Python.

What is modelled (all numbers cite the pinned clone):

* one dynamics update per ``step``: ``velocity += force * dt``, ``velocity *= 0.99``,
  ``position += velocity * dt``, clip to [-1, 1], bounce with ``velocity *= -0.5``
  (``resources/ros2_ws/src/dynamics/dynamics/dynamics_node.py:45-52``);
* ``dt = 0.05`` (``src/gymnasium_docker_ros2/env.py:25``; the world SDF fixes
  ``max_step_size`` 0.050 at ``resources/gdr2-world.sdf:5``, and the dynamics
  launch uses ``--rate 20`` at ``resources/tmux_session.yml.erb:18``);
* the reset branch: a special control input of 9999.0 draws the position
  uniformly from [-0.8, 0.8] and sets the velocity to 0
  (``dynamics_node.py:40-42``);
* the environment reward ``-abs(position)``, ``terminated`` false and
  ``truncated`` at ``max_steps`` 1000
  (``src/gymnasium_docker_ros2/env.py:200-205``, ``:24``);
* the published observation and info: position and velocity
  (``src/gymnasium_docker_ros2/env.py:118-122``).

What this is not: the upstream environment.  There is no Docker, ZeroMQ, ROS 2,
Gazebo, rendering or wall-clock timer, and the fake does not reproduce the
ZeroMQ request/reply or the Gazebo multi-step.  The upstream dynamics node seeds
NumPy once to 42 (``dynamics_node.py:21``) and its reset branch ignores the
Gymnasium seed; this fake instead reseeds a Python generator from ``reset(seed)``
so the bridge's seed control is real for the fake.  That difference, and the
absence of a hardware/ROS run, are disclosed in the driver's fidelity gaps.

The fake's action space copies the upstream ``Box(low=-1.0, high=1.0,
shape=(1,))`` (``env.py:34``), so the driver cites that line as
``action_space_ref``.  The start state before the first reset and the initial
counter are test data, not device facts, and are marked ``# placeholder``.
"""

import random

# src/gymnasium_docker_ros2/env.py:34: Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32).
ACTION_LOW = -1.0
ACTION_HIGH = 1.0
# src/gymnasium_docker_ros2/env.py:29-31: Box([-1.0, -5.0], [1.0, 5.0], dtype=np.float32).
OBSERVATION_LOW = (-1.0, -5.0)
OBSERVATION_HIGH = (1.0, 5.0)
# src/gymnasium_docker_ros2/env.py:24-25: max_steps 1000 and dt 0.05.
MAX_STEPS = 1000
DT = 0.05
# dynamics_node.py:40-52: reset range, damping, clip and bounce.
RESET_LOW = -0.8
RESET_HIGH = 0.8
DAMPING = 0.99
POSITION_LIMIT = 1.0
WALL_BOUNCE = -0.5


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bounds and shape the bridge reads."""

    def __init__(self, low, high, shape, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype


class FakeGDR2Env:
    """The public surface of ``GDR2Env`` with the dynamics node's update instead of Docker and ROS 2."""

    def __init__(self, render_mode=None, **_options):
        self.max_steps = MAX_STEPS
        self.dt = DT
        self.obs_low = list(OBSERVATION_LOW)
        self.obs_high = list(OBSERVATION_HIGH)
        self.observation_space = Box(OBSERVATION_LOW, OBSERVATION_HIGH, (2,))
        self.action_space = Box((ACTION_LOW,), (ACTION_HIGH,), (1,))
        self.position = 0.0  # placeholder: upstream starts at 0.0 before a reset (env.py:37)
        self.velocity = 0.0  # placeholder: upstream starts at 0.0 before a reset (env.py:38)
        self.step_count = 0
        self.render_mode = render_mode
        # dynamics_node.py:21 seeds the node's generator once at startup; the fake
        # keeps the same one-generator behavior and reseeds only when reset asks.
        self._rng = random.Random(42)
        self._closed = False

    def reset(self, seed=None, options=None):
        """Return ``(observation, info)`` after the dynamics node's reset branch."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if seed is not None:
            self._rng.seed(int(seed))
        self.position = self._rng.uniform(RESET_LOW, RESET_HIGH)
        self.velocity = 0.0
        self.step_count = 0
        return self._get_obs(), self._get_info()

    def step(self, action):
        """Apply one force, advance one dynamics update and return the five Gymnasium values."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        force = float(action[0] if isinstance(action, (list, tuple)) else action)
        self.velocity += force * self.dt
        self.velocity *= DAMPING
        self.position += self.velocity * self.dt
        self.position = min(POSITION_LIMIT, max(-POSITION_LIMIT, self.position))
        if self.position == -POSITION_LIMIT or self.position == POSITION_LIMIT:
            self.velocity *= WALL_BOUNCE
        self.step_count += 1
        reward = float(-abs(self.position))
        terminated = False
        truncated = self.step_count >= self.max_steps
        return self._get_obs(), reward, terminated, truncated, self._get_info()

    def close(self):
        """The fake owns no container, socket or network; closing only marks it closed."""
        self._closed = True

    def _get_obs(self):
        return [float(self.position), float(self.velocity)]

    def _get_info(self):
        return {"position": float(self.position), "velocity": float(self.velocity)}
