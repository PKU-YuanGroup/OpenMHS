"""Fake backend of the TacEx driver: a pure Python kinematic stand-in for the ball-rolling task.

Why a fake: the upstream environment is an Isaac Lab ``DirectRLEnv`` (base_env.py:235) that needs Isaac Sim 4.5,
Isaac Lab 2.1.1, Linux and an NVIDIA GPU (README.md:5 and :40-41; the acceptance gate never starts them) and package
code never imports the clone.  This module keeps the two methods the Gymnasium bridge calls (``reset`` and ``step``;
the upstream base class, outside the clone, provides them) and the two spaces the bridge reads, and reduces the
Franka Panda pushing task (base_env.py:235-603) to one end-effector point, one planar ball and one goal:

* ``reset`` restores the ball to its configured start (base_env.py:188) and draws a goal uniformly within
  +-0.1 m of it, as ``_reset_idx`` does with ``obj_pos_randomization_range[0]`` (base_env.py:219 and :555-562);
* ``step`` clamps the five action components to [-1, 1] (base_env.py:381), moves the end effector by the first
  three components, and moves the ball with it while they touch;
* the reward is the success term only, 10 when the ball is within 0.005 m of the goal (base_env.py:199-203, :480);
* the episode ends on the upstream termination conditions (base_env.py:409-424) and is truncated after the configured
  episode length (base_env.py:222) at the fake's step size.

Every number below is test data or a configuration constant of the clone.  Numbers marked ``# placeholder`` are the
fake's own (start pose, push gain, contact radius) and never enter a Fact, a Limit or the reference; the others
name the line they come from.  What this is not, all repeated in the driver's fidelity ``gaps``:

* no Isaac Sim physics, contacts, friction, mass, IK solver, joint limits, Franka arm, tactile sensor, camera,
  rendering or noise model;
* the ball follows the end effector kinematically instead of being pushed by contact forces;
* the upstream reward is a sum of reaching, tracking, success, orientation, height, action-rate and joint-velocity
  terms (base_env.py:456-501); only the success term is modelled;
* the observation is the 14-value vector of base_env.py:573-603, but the end-effector state is the fake's point and
  the orientation is held at zero;
* the upstream reset's rounding of ``episode_length_s / dt`` happens in the external base class and was not run.

Nothing here talks to a device and nothing here imports the clone.
"""

import math
import random

# base_env.py:80 and :83: decimation = 1 and sim.dt = 0.01 s; :256 multiplies them into the step interval.
DT = 0.01
# base_env.py:222: episode_length_s = 8.3333 / 2 s.  The fake uses int(episode_length_s / DT) = 416; the upstream
# comment says 500 timesteps, but 8.3333/2 s at 0.01 s is 416.665 steps.  # placeholder: the rounding is the fake's.
EPISODE_LENGTH_S = 8.3333 / 2
MAX_EPISODE_STEPS = int(EPISODE_LENGTH_S / DT)
# base_env.py:223: the action is (dx, dy, dz, droll, dpitch); dyaw is omitted.  base_env.py:381 clamps it to [-1, 1].
ACTION_SIZE = 5
ACTION_LIMIT = 1.0
# base_env.py:219: obj_pos_randomization_range[0] = [-0.1, 0.1] per axis; _reset_idx samples the goal offset
# (base_env.py:555-562).
GOAL_SPREAD = 0.1
# base_env.py:229-232: ball_radius 0.005 m, x_bounds (0.225, 0.75), y_bounds (-0.375, 0.375), too_far 0.35 m;
# base_env.py:199-203 gives a success reward of 10 below a 0.005 m object-goal distance.
BALL_RADIUS = 0.005
BALL_START = (0.5, 0.0)                                  # base_env.py:188, the ball init_state pos
X_BOUNDS = (0.225, 0.75)
Y_BOUNDS = (-0.375, 0.375)
TOO_FAR = 0.35
SUCCESS_DISTANCE = 0.005
SUCCESS_REWARD = 10.0
# The fake's own kinematics.  # placeholder
EE_START = (0.5, 0.0, 0.01)
EE_STEP = 0.001                                          # placeholder: one action unit moves 1 mm
CONTACT_DISTANCE = 0.05
OBJECT_TOO_FAR = 1.0                                     # base_env.py:417


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a low and a high bound per element (the bridge reads low/high/shape)."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeBallRollingEnv:
    """A kinematic stand-in for ``BallRollingEnv`` (base_env.py:235).

    ``reset`` and ``step`` are the two public methods of the Gymnasium environment API that the bridge calls; the
    upstream class inherits them from Isaac Lab's ``DirectRLEnv``, whose base lies outside the clone (gate G7 reports
    that as ``MAYBE_ABSENT``).  The action space is a five-element Box bounded by the clamp at base_env.py:381, and the
    observation space is the 14-value Box of base_env.py:224-226.
    """

    def __init__(self, **_options):
        self.action_space = Box([-ACTION_LIMIT] * ACTION_SIZE, [ACTION_LIMIT] * ACTION_SIZE)
        self.observation_space = Box([-math.inf] * 14, [math.inf] * 14)
        # base_env.py:256: the step interval is sim.dt * decimation; the bridge reads it for fidelity.timestep_ms.
        self.dt = DT
        self._rng = random.Random()
        self._ee = list(EE_START)                        # placeholder: the fake's end-effector point
        self._ball = list(BALL_START)
        self._goal = list(BALL_START)
        self._action = [0.0] * ACTION_SIZE
        self._tick = 0
        self._terminated = False
        self._truncated = False

    # -- state --------------------------------------------------------------
    def _observation(self):
        """The 14 values of base_env.py:588-603: ee pos 3, orientation 2, object 2, goal 2, actions 5."""
        return [
            self._ee[0], self._ee[1], self._ee[2],
            0.0, 0.0,                                    # placeholder: the orientation stays at zero
            self._ball[0], self._ball[1],
            self._goal[0], self._goal[1],
            self._action[0], self._action[1], self._action[2], self._action[3], self._action[4],
        ]

    def _ee_ball_distance(self):
        return math.sqrt((self._ee[0] - self._ball[0]) ** 2 + (self._ee[1] - self._ball[1]) ** 2
                         + (self._ee[2] - BALL_RADIUS) ** 2)

    def _done(self):
        ball = self._ball
        out_of_bounds = (ball[0] < X_BOUNDS[0] or ball[0] > X_BOUNDS[1]
                         or ball[1] < Y_BOUNDS[0] or ball[1] > Y_BOUNDS[1])
        object_too_far = math.hypot(ball[0] - self._goal[0], ball[1] - self._goal[1]) > OBJECT_TOO_FAR
        ee_too_far = self._ee_ball_distance() > TOO_FAR
        return bool(out_of_bounds or object_too_far or ee_too_far)

    # -- gymnasium API -------------------------------------------------------
    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._ee = list(EE_START)                        # placeholder: no robot state is loaded
        self._ball = list(BALL_START)
        # base_env.py:555-562: the goal is the object default position plus a uniform offset in each axis.
        self._goal = [self._ball[0] + self._rng.uniform(-GOAL_SPREAD, GOAL_SPREAD),
                      self._ball[1] + self._rng.uniform(-GOAL_SPREAD, GOAL_SPREAD)]
        self._action = [0.0] * ACTION_SIZE
        self._tick = 0
        self._terminated = False
        self._truncated = False
        return self._observation(), {}

    def step(self, action):
        values = [float(value) for value in action]      # placeholder: a malformed action is a driver test error
        if len(values) != ACTION_SIZE:
            raise ValueError(f"the action must have {ACTION_SIZE} components")
        values = [max(-ACTION_LIMIT, min(ACTION_LIMIT, value)) for value in values]   # base_env.py:381
        self._action = values
        touching = self._ee_ball_distance() <= CONTACT_DISTANCE   # placeholder: decide before the ee moves
        self._ee = [self._ee[index] + values[index] * EE_STEP for index in range(3)]   # placeholder: kinematics
        if touching:                                      # placeholder: the ball is pushed while touching
            self._ball[0] += values[0] * EE_STEP
            self._ball[1] += values[1] * EE_STEP
        self._tick += 1
        self._terminated = self._done()                   # base_env.py:409-424
        self._truncated = self._tick >= MAX_EPISODE_STEPS
        distance = math.hypot(self._ball[0] - self._goal[0], self._ball[1] - self._goal[1])
        # base_env.py:480: only the success term of the reward sum is modelled.
        reward = SUCCESS_REWARD if distance < SUCCESS_DISTANCE else 0.0
        return self._observation(), reward, self._terminated, self._truncated, {"tick": self._tick}
