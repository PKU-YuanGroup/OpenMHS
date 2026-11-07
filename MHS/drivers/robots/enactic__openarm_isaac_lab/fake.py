"""Fake backend of the OpenArm Isaac Lab reach driver: a pure Python stand-in for the gymnasium environment.

Why a fake: the real task ``Isaac-Reach-OpenArm-v0`` is built by Isaac Lab 2.3.0 on top of Isaac Sim 5.1.0
(README.md:19-23 of the clone), which needs a Linux machine with a GPU, and package code never imports the upstream
clone.  This module therefore re-implements the small interface the gymnasium bridge consumes (``reset``, ``step``,
``close``, ``action_space``, ``observation_space``) and the shape of the unimanual reach task described by the
configuration files named in ``driver.py``: one seven-joint position action and the four concatenated observation
terms (joint positions, joint velocities, pose command, last action).

What this is not: the upstream environment.  It has no rigid-body dynamics, no contacts, no USD scene, no sensors,
no reward terms and no vectorisation.  Every number below is test data for the package's own cases, marked
``# placeholder``; none of them is a fact, a limit or a reference of the driver.  The real sizes, bounds and
semantics of the action and observation spaces are built by Isaac Lab outside the clone and are not claimed here.
The public members of the fake class are exactly the Gymnasium environment interface the bridge needs.
"""

import math
import random

#: placeholder: the configuration names seven arm joints (openarm_joint1 .. openarm_joint7)
JOINTS = 7
#: placeholder: four concatenated observation terms of seven values each
OBSERVATION_SIZE = 4 * JOINTS
#: placeholder: 12.0 s episode at a 2/60 s control step (reach_env_cfg.py:268-273)
EPISODE_STEPS = 360
#: placeholder: the action scale of the reach task (joint_pos_env_cfg.py:71)
ACTION_SCALE = 0.5
#: placeholder: magnitude of the random joint offsets drawn at reset
RESET_RANGE = 0.01


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeOpenArmReachEnv:
    """Reach without Isaac Lab: ``reset(seed, options)`` and ``step(action)`` return gymnasium-shaped results."""

    def __init__(self, **_options):
        # placeholder: the upstream action envelope is built by Isaac Lab outside the clone, so the fake leaves the
        # seven joint-position offsets unbounded instead of inventing a joint limit.
        self.action_space = Box([-math.inf] * JOINTS, [math.inf] * JOINTS)
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self._rng = random.Random()
        self._joint_pos = [0.0] * JOINTS
        self._joint_vel = [0.0] * JOINTS
        self._command = [0.0] * JOINTS
        self._last_action = [0.0] * JOINTS
        self._tick = 0

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        # placeholder: start joint positions and a pose command, not a modelled reset of the USD articulation
        self._joint_pos = [self._rng.uniform(-RESET_RANGE, RESET_RANGE) for _ in range(JOINTS)]
        self._joint_vel = [0.0] * JOINTS
        self._command = [0.0] * JOINTS
        self._last_action = [0.0] * JOINTS
        self._tick = 0
        return self._observation(), {}

    def step(self, action):
        values = [float(item) for item in action]
        if len(values) != JOINTS:
            raise ValueError(f"the reach task takes {JOINTS} joint-position values, got {len(values)}")
        # placeholder: a first-order joint integration, not the Isaac Lab articulation or actuator model
        self._joint_vel = [ACTION_SCALE * item for item in values]
        self._joint_pos = [position + velocity for position, velocity in zip(self._joint_pos, self._joint_vel)]
        self._last_action = values
        self._tick += 1
        terminated = False
        # placeholder: the episode truncates after the fixed number of control steps
        truncated = self._tick >= EPISODE_STEPS
        reward = 0.0  # placeholder: the fake does not model the reach reward terms
        return self._observation(), reward, terminated, truncated, {}

    def close(self):
        self._joint_pos = []
        self._joint_vel = []
        self._command = []
        self._last_action = []

    def _observation(self):
        return [*self._joint_pos, *self._joint_vel, *self._command, *self._last_action]
