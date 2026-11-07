"""Fake backend of the safe-control-gym CartPole driver: a pure Python stand-in for ``CartPole``.

The acceptance gate never imports or runs the upstream clone: ``safe_control_gym`` depends on PyBullet, CasADi,
gymnasium, numpy and matplotlib (``setup.py:5-31``), and package code must not import the clone.  This module therefore
re-implements the environment's public surface (``reset``, ``step``, ``close``; gate G7 checks these names against the
upstream class) and the two space objects the Gymnasium bridge reads.

The equations below are the standard cart-pole rigid-body equations with a force input, integrated with the Euler
scheme at the upstream control timestep.  The constants are the upstream defaults:

* gravity 9.8 m/s^2 (``safe_control_gym/envs/gym_control/cartpole.py:200``);
* cart mass 1.0 kg, pole mass 0.1 kg and pole box length 1.0 m, whose half-length is 0.5 m
  (``safe_control_gym/envs/gym_control/assets/cartpole_template.urdf:37``, ``:61`` and ``:52``, read by
  ``cartpole.py:719-736``);
* force bounds -10 to 10 N and control timestep 0.02 s (``cartpole.py:441-444`` and
  ``safe_control_gym/envs/benchmark_env.py:143-145``);
* failure thresholds 2.4 m and 90 degrees (``cartpole.py:452-454``) and stabilization goal tolerance 0.05
  (``cartpole.py:115-123``);
* default initial-state bounds -0.05 to 0.05 (``cartpole.py:88-112``) and episode limit 250 control steps
  (``benchmark_env.py:66`` and ``:143-145``, ``:497-501``).

These constants are implementation data of the fake.  The values that are *test data* (the particular initial state
this fake draws and every canned reply) are marked ``# placeholder`` and are never copied into a Fact, a Limit or a
reference in ``driver.py``.

What this is not: the upstream environment.  It is not PyBullet; the upstream URDF contact/inertia/damping behaviour,
the symbolic model, the constraints, the disturbances and the rendering are not modelled.  The upstream
``CartPole.step`` returns the legacy four-tuple ``(obs, reward, done, info)``; this fake returns the modern five-tuple
``(obs, reward, terminated, truncated, info)`` so the bridge can report the 5 s time limit as a truncation.  The
initial state uses Python's ``random.Random`` instead of numpy's generator, so one seed gives different trajectories
on the fake and on the upstream environment.  These differences are listed in the driver's fidelity ``gaps``.
"""

import math
import random

# Upstream defaults, cited in the module docstring; this file is not a source for any Fact or Limit.
GRAVITY = 9.8
CART_MASS = 1.0
POLE_MASS = 0.1
HALF_LENGTH = 0.5
TOTAL_MASS = CART_MASS + POLE_MASS
POLE_MASS_LENGTH = POLE_MASS * HALF_LENGTH
FORCE_LIMIT = 10.0
TIMESTEP = 0.02
X_THRESHOLD = 2.4
THETA_THRESHOLD = math.pi / 2
GOAL_TOLERANCE = 0.05
EPISODE_STEPS = 250

# placeholder: the fake draws its initial state uniformly from these bounds; the upstream bounds are the same but
# upstream uses numpy's generator (cartpole.py:88-112, :323-330).
INIT_LOW = -0.05
INIT_HIGH = 0.05
# placeholder: the reward's action penalty is a fake-side weight; the upstream default is rew_act_weight=0.0001
# (cartpole.py:135 and :611-635).
REWARD_ACTION_WEIGHT = 0.0001
# placeholder: two observation bounds not used by the dynamics but needed to shape the space like upstream.
X_DOT_BOUND = 20.0
THETA_DOT_BOUND = 20.0


class Box:
    """Duck-typed one-dimensional space with a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


def _wrap_angle(angle):
    """Wrap an angle to (-pi, pi] like the upstream normalization used in the reward."""

    return (angle + math.pi) % (2.0 * math.pi) - math.pi


class FakeCartPole:
    """The public surface of ``safe_control_gym.envs.gym_control.cartpole:CartPole`` without PyBullet."""

    def __init__(self, **_options):
        self.action_space = Box([-FORCE_LIMIT], [FORCE_LIMIT])
        high = [X_THRESHOLD * 2, X_DOT_BOUND, THETA_THRESHOLD * 2, THETA_DOT_BOUND]
        self.observation_space = Box([-value for value in high], high)
        self.state = None
        self._rng = random.Random()
        self._steps = 0
        self._episode = 0

    def reset(self, seed=None):
        """Draw an initial state and return ``(observation, info)``, like the upstream reset."""

        if seed is not None:
            self._rng = random.Random(int(seed))
        # placeholder: a fresh test state, not a Fact or a Limit.
        self.state = [self._rng.uniform(INIT_LOW, INIT_HIGH) for _ in range(4)]
        self._steps = 0
        self._episode += 1
        return list(self.state), {"current_step": 0, "episode": self._episode}

    def step(self, action):
        """Apply one force and return ``(observation, reward, terminated, truncated, info)``."""

        if self.state is None:
            raise RuntimeError("call reset before step")
        raw = action[0] if isinstance(action, (list, tuple)) else action
        force = min(max(float(raw), -FORCE_LIMIT), FORCE_LIMIT)  # upstream clips at :498-500
        x, x_dot, theta, theta_dot = self.state
        costheta = math.cos(theta)
        sintheta = math.sin(theta)
        temp = (force + POLE_MASS_LENGTH * theta_dot * theta_dot * sintheta) / TOTAL_MASS
        thetaacc = (GRAVITY * sintheta - costheta * temp) / (
            HALF_LENGTH * (4.0 / 3.0 - POLE_MASS * costheta * costheta / TOTAL_MASS)
        )
        xacc = temp - POLE_MASS_LENGTH * thetaacc * costheta / TOTAL_MASS
        # Euler integration at the upstream control timestep (benchmark_env.py:143-145).
        x = x + TIMESTEP * x_dot
        x_dot = x_dot + TIMESTEP * xacc
        theta = theta + TIMESTEP * theta_dot
        theta_dot = theta_dot + TIMESTEP * thetaacc
        self.state = [x, x_dot, theta, theta_dot]
        self._steps += 1

        wrapped = _wrap_angle(theta)
        distance = x * x + x_dot * x_dot + wrapped * wrapped + theta_dot * theta_dot
        reward = math.exp(-distance - REWARD_ACTION_WEIGHT * force * force)
        goal_reached = math.sqrt(distance) < GOAL_TOLERANCE
        out_of_bounds = abs(x) > X_THRESHOLD or abs(wrapped) > THETA_THRESHOLD
        terminated = bool(goal_reached or out_of_bounds)
        truncated = bool(not terminated and self._steps >= EPISODE_STEPS)
        info = {
            "current_step": self._steps,
            "goal_reached": bool(goal_reached),
            "out_of_bounds": bool(out_of_bounds),
            "mse": wrapped * wrapped + x * x,
        }
        if truncated:
            info["TimeLimit.truncated"] = True
        return list(self.state), float(reward), terminated, truncated, info

    def close(self):
        """Release the test state; the fake holds no outside resource."""

        self.state = None
