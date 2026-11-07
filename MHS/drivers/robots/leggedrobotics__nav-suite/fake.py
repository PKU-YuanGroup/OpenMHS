"""Fake backend of the nav-suite driver: a pure Python kinematic stand-in for the registered task.

Why a fake: the acceptance gate runs without Isaac Sim, Isaac Lab, a GPU or the git-lfs policy and terrain assets, and
package code never imports the clone.  This module models the task at the interface the Gymnasium bridge needs:
``reset(seed, options)`` and ``step(action)`` over a three-dimensional SE2 velocity command ``[vx, vy, omega]``.
Every constant below cites a line of the clone at the pinned commit (648ba3b28dac61aec48e150a507c2a8507646ea2).

What this is not (all differences are in the ``gaps`` of ``driver.py``): the upstream environment is a
``ManagerBasedRLEnv`` built by Isaac Lab over an ANYmal D articulation, a rough terrain and a depth camera.  This
fake has no rigid-body dynamics, no contacts, no low-level locomotion policy, no terrain, no camera and no reward
terms.  The observation is the planar pose only, not the concatenated policy observation.

The public surface is the Gymnasium environment interface (``reset`` and ``step``; gate G7): the upstream entry class
named by ``native`` is a configuration dataclass whose environment base lies outside the clone, so the bridge's
environment interface is the only surface this fake implements.
"""

import math
import random

# The clone's environment step: sim.dt 0.005 s times decimation 20, written in the comment as 0.1 s at 10 Hz
# (exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:424-428).
STEP_S = 0.1
# episode_length_s 20 s (exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:422) divided by STEP_S.  This is the fake's
# truncation horizon; the upstream time_out term is proportional and is not modelled.
EPISODE_STEPS = 200
# The reset event draws the base yaw from -3.0 to 3.0 radians
# (exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:194-200).
YAW_LOW, YAW_HIGH = -3.0, 3.0
# NavigationSE2ActionCfg.action_dim is 3, [vx, vy, omega]
# (exts/nav_tasks/nav_tasks/mdp/actions/navigation_actions_cfg.py:44-45).
ACTION_DIM = 3
# The fake's observation is the planar pose [x, y, yaw]; the upstream policy group is not modelled.
OBSERVATION_DIM = 3


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape`` only."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeNavTasksEnv:
    """The nav-suite task as a kinematic SE2 robot: ``reset(seed, options)`` and ``step(action)``.

    The action is a velocity command in the robot's body frame, integrated over one 0.1 s environment step.  The
    integration and the zero reward are the fake's model choice, not a claim about the upstream environment.
    """

    def __init__(self, **_options):
        # The action space is a Box of three numbers; NavigationSE2ActionCfg has clip_mode "none" and no scale or
        # offset, so the fake declares no bounds (navigation_actions_cfg.py:44-52).
        self.action_space = Box([-math.inf] * ACTION_DIM, [math.inf] * ACTION_DIM)
        self.observation_space = Box([-math.inf] * OBSERVATION_DIM, [math.inf] * OBSERVATION_DIM)
        self._rng = random.Random()
        self._pose = None
        self._steps = 0
        self._terminated = False
        self._truncated = False

    def reset(self, *, seed=None, options=None):
        if options:
            raise ValueError("the fake nav-suite environment accepts no reset options")
        if seed is not None:
            self._rng = random.Random(seed)
        # The upstream reset yaw event draws from (-3.0, 3.0) (env_cfg_base.py:194-200); the draw below uses Python's
        # generator, while the upstream event uses the Isaac Lab/torch random generators.
        yaw = self._rng.uniform(YAW_LOW, YAW_HIGH)
        self._pose = [0.0, 0.0, yaw]  # placeholder spawn at the origin: the upstream spawn pose is not set here
        self._steps = 0
        self._terminated = False
        self._truncated = False
        return list(self._pose), {}

    def step(self, action):
        if self._pose is None:
            raise AssertionError("Call reset before using step method.")
        values = list(action)
        if len(values) != ACTION_DIM:
            raise ValueError(f"the action has {len(values)} values; the navigation action has {ACTION_DIM}")
        vx, vy, omega = (float(value) for value in values)
        if not all(math.isfinite(value) for value in (vx, vy, omega)):
            raise ValueError("the action values must be finite")
        x, y, yaw = self._pose
        # Body-frame SE2 integration over STEP_S; placeholder kinematics, not the upstream low-level policy.
        x += (vx * math.cos(yaw) - vy * math.sin(yaw)) * STEP_S
        y += (vx * math.sin(yaw) + vy * math.cos(yaw)) * STEP_S
        yaw += omega * STEP_S
        self._pose = [x, y, yaw]
        self._steps += 1
        # Placeholder truncation horizon derived from episode_length_s and STEP_S; the upstream proportional_time_out
        # term and the goal/contact terminations are not modelled.
        self._truncated = self._steps >= EPISODE_STEPS
        # Placeholder reward: the upstream reward terms are not modelled, so the fake reports no progress.
        return list(self._pose), 0.0, False, self._truncated, {}
