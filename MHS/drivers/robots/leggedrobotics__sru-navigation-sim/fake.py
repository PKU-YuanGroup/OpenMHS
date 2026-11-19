"""Fake backend of the SRU navigation-simulation driver: an analytic stand-in for one AoW-D environment.

Why a fake: the upstream environment is an Isaac Lab task extension.  Its base class ``ManagerBasedRLEnv``, Isaac Sim
4.5 and GPU physics are outside this clone and cannot be imported or run where the gate runs, and package code never
imports the clone (docs/README.md:64-69, task.json install.gpu).  This module therefore models the task contract that
the clone does define: a 3-dimensional SE2 velocity action ``[vx, vy, omega]``, a goal sampled on reset, a 300-step
(60 s at 0.2 s per step) episode, a goal counter that continues after the first goal entry and a reset that randomizes yaw.

It is an analytic model and NOT a recording.  It has no rigid-body dynamics, contact, locomotion policy, depth
sensor, delay buffer or domain randomization; those are listed in the driver's fidelity ``gaps``.  The public members
are the Gymnasium environment interface (``reset``, ``step``, ``close``; the spaces are instance attributes), which
gate G7 accepts for an upstream class whose base implementation lies outside the clone.

The numbers below are the fake's test data.  A number that is derived from the clone is marked with its source line;
the ones marked ``placeholder`` are not facts and are never copied into the driver's Facts, Limits or references:

* action bounds [-1, 1] are the bridge envelope of this fake; upstream's action space is built by the external
  Isaac Lab ``ManagerBasedRLEnv`` and is not defined in the clone;
* the goal radius and the observation sizes are placeholders;
* the per-step kinematics (moving by the processed command times the control period) is an analytic stand-in.

Every derived constant cites the clone at commit 80f6c01c2d9f171374c9f9dba289abd38bcf0c6c.
"""

import math
import random

# isaaclab_nav_task/navigation/navigation_env_cfg.py:48 PLANNING_FREQ = 5.0 Hz
PLANNING_FREQ = 5.0
# isaaclab_nav_task/navigation/navigation_env_cfg.py:424-428 sim.dt = 0.005 and
# decimation = int((1 / sim.dt) / PLANNING_FREQ) = 40, so one environment step is 40 * 0.005 = 0.2 s and
# episode_length_s = 60.0 means 60.0 / 0.2 = 300 environment steps.
CONTROL_DT_S = 0.2
MAX_EPISODE_STEPS = 300
# isaaclab_nav_task/navigation/navigation_env_cfg.py:380 at_goal_navigation distance_threshold = 0.5
GOAL_RADIUS_M = 0.5
# isaaclab_nav_task/navigation/mdp/navigation/goal_commands.py:378 required_steps_at_goal = 4.0 / env.step_dt
# with step_dt = 0.2 s this is 20 steps.
REQUIRED_GOAL_STEPS = 20
# isaaclab_nav_task/navigation/navigation_env_cfg.py:271-275 reset_base samples yaw uniformly from (-pi, pi).
YAW_RANGE = (-math.pi, math.pi)
# isaaclab_nav_task/navigation/navigation_env_cfg.py:163 policy_scaling = [1.5, 1.0, 1.0]
POLICY_SCALING = (1.5, 1.0, 1.0)
# placeholder: this fake samples the goal 2 to 5 m from the origin.
GOAL_RADIUS_RANGE_M = (2.0, 5.0)


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: one lower and one upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float64"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the observation groups of the environment."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _wrap_angle(angle):
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


class FakeNavigationEnv:
    """One analytic AoW-D navigation episode: reset(seed), step(action), close()."""

    def __init__(self, render_mode=None, num_envs=1):
        if render_mode is not None:
            raise ValueError("the analytic fake cannot render; use render_mode=None")
        # placeholder sizes: the clone defines the four observation groups at navigation_env_cfg.py:247-251 and their
        # terms at :174-245, but the external Isaac Lab observation manager builds the actual concatenated dimensions.
        # placeholder: this fake's action envelope; upstream's space is built by the external ManagerBasedRLEnv.
        self.action_space = Box([-1.0, -1.0, -1.0], [1.0, 1.0, 1.0])
        self.observation_space = Dict({
            "policy": Box([-1e6] * 10, [1e6] * 10),
            "critic": Box([-1e6] * 12, [1e6] * 12),
            "low_level_policy": Box([-1e6] * 10, [1e6] * 10),
            "metrics": Box([0.0], [1.0]),
        })
        self._num_envs = int(num_envs)
        self._rng = random.Random()
        self._closed = False
        self._reset(None)

    # -- Gymnasium interface ------------------------------------------------------------------------------------
    def reset(self, *, seed=None, options=None):
        """Reset one episode.  The seed fixes the goal and the reset yaw; options are accepted and not used."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        return self._reset(seed), {}

    def step(self, action):
        """Advance one 0.2 s environment step by the processed SE2 command and return the Gymnasium five-tuple."""
        if self._closed:
            raise RuntimeError("the environment is closed")
        values = list(action)
        if len(values) != 3:
            raise ValueError(f"the SE2 action needs 3 values [vx, vy, omega], got {len(values)}")
        # navigation_se2_actions.py:164-169: use_raw_actions=True keeps the raw action and the gaussian distribution
        # applies tanh; navigation_se2_actions.py:182 then multiplies by policy_scaling (navigation_env_cfg.py:163).
        processed = [math.tanh(float(values[index])) * POLICY_SCALING[index] for index in range(3)]
        vx, vy, omega = processed
        self._x += (vx * math.cos(self._yaw) - vy * math.sin(self._yaw)) * CONTROL_DT_S
        self._y += (vx * math.sin(self._yaw) + vy * math.cos(self._yaw)) * CONTROL_DT_S
        self._yaw = _wrap_angle(self._yaw + omega * CONTROL_DT_S)
        self._last_action = processed
        self._steps += 1

        distance = math.hypot(self._goal_x - self._x, self._goal_y - self._y)
        if distance < GOAL_RADIUS_M:
            self._has_reached_goal = True
        # time_out_navigation records time_at_goal on first entry (terminations.py:62-65), and
        # at_goal_navigation keeps counting while time_at_goal > 0 even after the robot leaves (:158-166).
        if self._has_reached_goal:
            self._goal_steps += 1
        # terminations.py:166 and goal_commands.py:378: truncate when the counter exceeds 4.0 / step_dt.
        if self._goal_steps > REQUIRED_GOAL_STEPS:
            self._truncated = True
        # navigation_env_cfg.py:424-428: episode_length_s = 60.0 and one step is 0.2 s, so 300 steps.
        if self._steps >= MAX_EPISODE_STEPS:
            self._truncated = True
        # placeholder reward: the clone's reward terms (navigation_env_cfg.py:338-367) depend on the physics,
        # contact and goal quantities of the external Isaac Lab environment, which this model does not reproduce.
        reward = 0.0
        return self._observation(), reward, self._terminated, self._truncated, {}

    def close(self):
        self._closed = True

    # -- model --------------------------------------------------------------------------------------------------
    def _reset(self, seed):
        self._x = 0.0                       # placeholder: the reset pose is sampled by the external scene
        self._y = 0.0
        # navigation_env_cfg.py:271-275 reset_base samples yaw from (-pi, pi)
        self._yaw = self._rng.uniform(*YAW_RANGE)
        # placeholder: goal sampled 2 to 5 m from the origin; upstream samples it from terrain masks on reset.
        angle = self._rng.uniform(-math.pi, math.pi)
        radius = self._rng.uniform(*GOAL_RADIUS_RANGE_M)
        self._goal_x = radius * math.cos(angle)
        self._goal_y = radius * math.sin(angle)
        self._goal_steps = 0
        self._has_reached_goal = False
        self._steps = 0
        self._terminated = False
        self._truncated = False
        self._last_action = [0.0, 0.0, 0.0]
        self._seed = seed
        return self._observation()

    def _observation(self):
        distance = math.hypot(self._goal_x - self._x, self._goal_y - self._y)
        in_goal = 1.0 if distance < GOAL_RADIUS_M else 0.0
        time_normalized = self._steps / MAX_EPISODE_STEPS
        common = [self._x, self._y, self._yaw]
        velocity = list(self._last_action)
        goal = [self._goal_x, self._goal_y, distance]
        # The group names and source terms are navigation_env_cfg.py:174-251; the values are this fake's stand-ins.
        return {
            "policy": velocity + goal + list(self._last_action) + [in_goal],
            "critic": velocity + goal + [time_normalized] + common + [float(self._truncated), in_goal],
            "low_level_policy": velocity + common + [distance] + list(self._last_action),
            "metrics": [in_goal],
        }
