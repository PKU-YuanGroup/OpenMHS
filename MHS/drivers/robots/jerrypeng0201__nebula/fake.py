"""Fake backend of the SceneManipulation-v1 driver: a pure Python stand-in for the upstream SAPIEN environment.

Why a fake: the acceptance gate runs without SAPIEN, torch, numpy physics or the ReplicaCAD assets, and package code
never imports the clone.  This module mirrors the public members of
``nebula.core.simulation.scenes.base_env:SceneManipulationEnv`` (``reset``, ``step``, ``close``; gate G7) and the two
space members the Gymnasium bridge reads (``action_space``, ``observation_space``).  The action bounds are the bounds of
the deployed configuration: the default Fetch robot with the first controller config, ``pd_joint_delta_pos`` (see the
facts and the citations in driver.py).  The observation is the 15 qpos followed by the 15 qvel of that robot.

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* it is kinematic, not a PhysX simulation: the 13 action values are added to the first 13 qpos entries and the last
  action is copied into qvel; there are no contacts, no controller dynamics and no assets;
* the initial joint offsets are drawn with Python's ``random.Random``, while upstream uses numpy random states, so one
  seed gives different trajectories on the two;
* it returns the unbatched 30-value observation while upstream batches it to (1, 30), and it has no rendering,
  cameras, ``get_state``/``set_state`` or scene builder.

Numbers that are only test data (the initial joint offsets) are marked ``# placeholder``.  Nothing here talks to a
device.
"""

import math
import random

# nebula/core/simulation/scenes/base_env.py:19: the registered max_episode_steps, applied by the gym wrapper
MAX_EPISODE_STEPS = 200

# nebula/core/embodiment/robots/fetch/fetch.py:78-114: 7 arm, 2 gripper, 3 body and 3 base joints
N_ARM = 7
N_GRIPPER = 1
N_BODY = 3
N_BASE = 2
N_ACTION = N_ARM + N_GRIPPER + N_BODY + N_BASE          # 13, the flattened CombinedController Box
N_QPOS = 15
# nebula/core/embodiment/manipulator.py:333-341: proprioception is qpos and qvel (no controller state here)
N_OBS = N_QPOS + N_QPOS

# nebula/core/embodiment/actuators/base_actuator.py:67-72 and :159-169: every controller whose config leaves
# normalize_action at its True default replaces its configured Box with Box(-1, 1); the raw bounds are kept for
# clipping and scaling.  nebula/utils/gym_utils.py:108-110 is that normalized Box.  The arm, gripper, body and base
# configs of fetch.py:132-256 do not override normalize_action, so the flattened pd_joint_delta_pos action space is
# 13 values bounded by -1 and 1 (the order and dimensions are cited above).
ACTION_LOW = [-1.0] * N_ACTION
ACTION_HIGH = [1.0] * N_ACTION


class _Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high, shape=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.low):
            return False
        return all(low <= float(item) <= high for item, low, high in zip(value, self.low, self.high))


class FakeSceneManipulationEnv:
    """The default Fetch configuration of SceneManipulation-v1 without SAPIEN, torch or assets.

    ``reset(seed, options)`` returns ``(observation, info)`` and ``step(action)`` returns
    ``(observation, reward, terminated, truncated, info)``, like the upstream class.  The constructor rejects another
    robot or control mode because the fake only models the configuration the driver deploys.
    """

    def __init__(self, robot_uids="fetch", control_mode="pd_joint_delta_pos", scene_builder_cls="ReplicaCAD",
                 build_config_idxs=None, init_config_idxs=None, num_envs=1, reconfiguration_freq=None,
                 render_mode=None, **kwargs):
        if robot_uids != "fetch":
            raise ValueError("the fake models the fetch robot only")
        if control_mode != "pd_joint_delta_pos":
            raise ValueError("the fake models the pd_joint_delta_pos controller only")
        if num_envs != 1:
            raise ValueError("the fake serves one environment at a time")
        self.action_space = _Box(ACTION_LOW, ACTION_HIGH, shape=(N_ACTION,))
        # gym_utils.py:145-154: a floating-point observation gets -inf to inf bounds
        self.observation_space = _Box([-math.inf] * N_OBS, [math.inf] * N_OBS, shape=(N_OBS,))
        self._rng = random.Random()
        self._qpos = [0.0] * N_QPOS
        self._qvel = [0.0] * N_QPOS
        self._elapsed_steps = 0
        self._terminated = False
        self._truncated = False
        self._closed = False

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))                            # engine.py:884-887, fake RNG
        # placeholders: the fake's initial joint offsets are test data, not the upstream rest pose
        self._qpos = [self._rng.uniform(-0.02, 0.02) for _ in range(N_QPOS)]  # placeholder
        self._qvel = [0.0] * N_QPOS
        self._elapsed_steps = 0
        self._terminated = False
        self._truncated = False
        reconfigure = bool((options or {}).get("reconfigure", False))
        return self._observation(), {"elapsed_steps": 0, "reconfigure": reconfigure}

    def step(self, action):
        if not isinstance(action, (list, tuple)) or len(action) != N_ACTION:
            raise ValueError(f"expected {N_ACTION} action values")
        if not self.action_space.contains(action):
            raise ValueError("action is outside the action space")
        # placeholder: a kinematic stand-in, not the Fetch controller or PhysX
        for index, value in enumerate(action):
            self._qpos[index] += float(value)                               # placeholder joint mapping
            self._qvel[index] = float(value)                                # placeholder velocity report
        self._elapsed_steps += 1
        # base_env.py:19: the registered time limit; base_env.py:142-143: no success/fail, so never terminated
        self._truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        # base_env.py:145-151: the dense and normalized dense rewards are 0
        return self._observation(), 0.0, self._terminated, self._truncated, {
            "elapsed_steps": self._elapsed_steps}

    def close(self):
        self._closed = True

    def _observation(self):
        # engine.py:529-544: the state mode flattens {agent: {qpos, qvel}, extra: {}} into one tensor
        return list(self._qpos) + list(self._qvel)
