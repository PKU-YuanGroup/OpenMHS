"""Fake backend of the Humanoid-Base-v0 driver: a pure Python kinematic stand-in for the Gymnasium environment.

Why a fake: the upstream environment needs Isaac Sim 4.2 and Isaac Lab 1.2.0 (README.md:17), the H1/USD assets are
hosted on Hugging Face rather than in the clone (README.md:23), and package code never imports or runs the clone.
This module mirrors the public Gymnasium environment surface that ``BaseEnv`` (the class the driver names as
``native``) inherits from the external ``DirectRLEnv``: ``action_space``, ``observation_space``, ``dt``, ``reset``,
``step`` and ``close`` (gate G7 allows these standard names with a warning).  Every constant below cites the line of
the clone at the pinned commit 4489a673153d40f0dcba84c9210c426edfc62812.

What this is not: the upstream simulator.  It has no rigid-body dynamics, contacts, friction, actuators, sensors or
rendering; it writes the action vector to joint positions directly (fidelity level F0).  All values in the returned
observation are placeholders (``# placeholder``), not facts about the H1 robot or the task scene.  The camera
arrays are 1 x 1 instead of the upstream sizes (360 x 640 per eye camera, concatenated to 360 x 1280; 720 x 1280
for the main and hand cameras; base_env.py:63-112, :257-259); the full sizes are recorded in the fidelity ``gaps``
of the driver and in RESULT.json notes.

Nothing here talks to a device.
"""

import math
import random

#: base_env.py:32 ``dt=1 / 120`` and :118 ``decimation = 4``; BaseEnv computes ``self.dt`` from them (:142).
DT = (1.0 / 120.0) * 4
#: base_env.py:117 ``episode_length_s = 0.5``; the step count is derived from it and DT, not copied from a default.
MAX_EPISODE_STEPS = int(round(0.5 / DT))
#: base_env.py:120 ``num_actions = 50`` and :124 ``action_space = num_actions``.
NUM_ACTIONS = 50
#: base_env.py:158-159: the end-effector target poses are 7-vectors (position and quaternion).
POSE_LENGTH = 7


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: 50 real values per action, with no numeric bound.

    The clone states the action dimension but not a numeric joint range: ``_apply_action`` clamps to the robot's
    soft joint limits, which come from the H1 asset data outside the clone (base_env.py:140-141, :211-214).  The
    bridge therefore derives the length only and publishes no invented limit.
    """

    def __init__(self, shape):
        self.shape = (int(shape),)
        self.low = [float("-inf")] * self.shape[0]
        self.high = [float("inf")] * self.shape[0]
        self.dtype = "float32"


class FakeHumanoidEnv:
    """``Humanoid-Base-v0`` without Isaac Sim/Isaac Lab: a deterministic kinematic stub of the Gymnasium interface."""

    def __init__(self, **_options):
        #: base_env.py:142: the environment's control timestep (sim dt times decimation).
        self.dt = DT
        self.action_space = Box(NUM_ACTIONS)
        #: BaseEnv does not declare an observation space in the clone; Isaac Lab's DirectRLEnv builds it from the
        #: cfg and the task subclasses add keys.  The fake publishes none rather than invent one.
        self.observation_space = None
        self._rng = random.Random(0)
        self._seed = None
        self._options = {}
        self._step = 0
        self._qpos = [0.0] * NUM_ACTIONS
        self._action = [0.0] * NUM_ACTIONS
        self._terminated = False
        self._truncated = False
        self._reset_state()

    def reset(self, *, seed=None, options=None):
        """The Gymnasium ``reset(seed=..., options=...)`` call the bridge makes before the first step."""
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        self._options = dict(options or {})
        self._reset_state()
        return self._observation(), {"seed": self._seed}

    def step(self, action):
        """The Gymnasium ``step(action)`` call; returns ``(observation, reward, terminated, truncated, info)``."""
        values = list(action)
        if len(values) != NUM_ACTIONS:
            raise ValueError(f"the action must have {NUM_ACTIONS} elements, got {len(values)}")
        floats = [float(value) for value in values]
        if not all(math.isfinite(value) for value in floats):
            raise ValueError("the action must be finite")
        #: placeholder kinematic stand-in for _apply_action (base_env.py:211-214): no clamp and no physics here.
        self._action = floats
        self._qpos = list(floats)
        self._step += 1
        #: base_env.py:217-219: the timeout is returned as both terminated and truncated.
        self._terminated = self._step >= MAX_EPISODE_STEPS
        self._truncated = self._terminated
        #: base_env.py:297-298: BaseEnv._get_rewards is empty, so the base environment pays no reward.
        return self._observation(), 0.0, self._terminated, self._truncated, {}

    def close(self):
        """The Gymnasium ``close()`` call (DirectRLEnv closes its simulator; this fake has none)."""
        self._qpos = [0.0] * NUM_ACTIONS
        self._action = [0.0] * NUM_ACTIONS

    # -- private helpers ----------------------------------------------------
    def _reset_state(self):
        #: placeholder: random initial joint offsets, so a seed is observable; upstream randomizes object poses
        #: with torch (base_env.py:130-132), not these joint values.
        self._qpos = [0.0] * NUM_ACTIONS
        self._qpos[0] = self._rng.uniform(-0.1, 0.1)
        self._qpos[1] = self._rng.uniform(-0.1, 0.1)
        self._action = [0.0] * NUM_ACTIONS
        self._step = 0
        self._terminated = False
        self._truncated = False

    def _observation(self):
        """The 16 keys of ``BaseEnv._get_observations`` (base_env.py:278-295), with placeholder values."""
        pixel = [[[0.5, 0.5, 0.5]]]                      # placeholder: upstream rgb is 360 x 1280 x 3
        depth = [[0.5]]                                  # placeholder: upstream fixed_d is 720 x 1280
        pose = [0.0] * POSE_LENGTH                       # placeholder: upstream pose is a real body pose
        finger = [[0.0, 0.0, 0.0]]                       # placeholder: upstream is (num_fingers, 3)
        return {
            "rgb": pixel,
            "fixed_rgb": pixel,
            "fixed_d": depth,
            "left_hand_rgb": pixel,
            "right_hand_rgb": pixel,
            "qpos": list(self._qpos),
            "qvel": [0.0] * NUM_ACTIONS,                 # placeholder
            "action": list(self._action),
            "left_ee_pose": list(pose),
            "right_ee_pose": list(pose),
            "left_target_ee_pose": list(pose),
            "right_target_ee_pose": list(pose),
            "left_finger_tip_pos": [list(finger[0])],
            "right_finger_tip_pos": [list(finger[0])],
            "left_hand_contact_force": 0.0,              # placeholder
            "right_hand_contact_force": 0.0,             # placeholder
        }
