"""Fake backend of the ManiSkill legacy driver: an analytic stand-in for ``OpenCabinetDoor-v0``.

Why a fake: the acceptance gate never imports or runs the upstream clone (it needs SAPIEN, Vulkan, a GPU and the
PartNet Mobility assets; ``install`` in the task card has ``gpu: true``), and package code must not import the
clone.  This module re-implements the *interface* of
``mani_skill.env.open_cabinet_door_drawer:OpenCabinetDoorEnv`` (the class the driver names as ``native``) in plain
Python.  Its public members are the ones that class has (``reset``, ``step``, ``seed``, ``close``; gate G7), and
the two space classes duck-type ``gym.spaces.Box`` (the bridge reads ``low``, ``high`` and ``shape``).

The observation shape follows the clone at commit 58964d08b4c7d2e14c5e6e287dbb9430d900f54d:
``BaseEnv.get_state`` concatenates the padded cabinet state (13 pose/velocity values + 2 * 8 internal values,
``mani_skill/utils/misc.py:51-57`` with ``cabinet_max_dof = 8`` at
``mani_skill/env/open_cabinet_door_drawer.py:35-36``), the 8-element target indicator
(``mani_skill/env/open_cabinet_door_drawer.py:158-159``) and the agent state
(``mani_skill/env/base_env.py:471-479``); for the mobile_a2_single_arm agent that is 75 values.  The values this
fake writes into that vector, except the ones that come from the clone, are test data and are marked ``# placeholder``.

Nothing here talks to a device, imports the clone, or uses numpy.
"""

import random

# mani_skill/env/base_env.py:95 builds the action space as Box(low=-1, high=1,
# shape=self.agent.action_range().shape); mobile_a2_single_arm.yml:18-30 lists the 13 controllable joints.
ACTION_DIM = 13
# 13 pose/velocity values + 2 * cabinet_max_dof (8) + the 8-element target indicator + the 38-value agent state.
OBS_DIM = 75
# The state layout used by get_state: 13 pose values, 8 padded qpos, 8 padded qvel, 8 target indicators.
CABINET_STATE_DIM = 29
TARGET_INDICATOR_OFFSET = 29
# fingers_pos 6 + fingers_vel 6 + base_pos 2 + base_orientation 1 + base_vel 2 + base_ang_vel 1 + qpos 10 + qvel 10.
AGENT_STATE_OFFSET = 37

# mani_skill/assets/config_files/open_cabinet_door.yml:48-49 sets custom.open_extent to 0.9; the success test uses
# target_qpos = lmin + (lmax - lmin) * open_extent (mani_skill/env/open_cabinet_door_drawer.py:51-53 and :237).
OPEN_EXTENT = 0.9

# placeholder: the analytic drawer speed, the initial opening and the episode cap are test data; they are not facts
# about the SAPIEN environment and are never cited as such.
OPEN_PER_STEP = 0.05
INITIAL_OPEN_MAX = 0.01
MAX_EPISODE_STEPS = 200
TARGET_JOINT_INDEX = 0


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element (one-dimensional)."""

    def __init__(self, low, high, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype


class FakeOpenCabinetDoorEnv:
    """Analytic ``OpenCabinetDoor-v0``: ``reset(seed, options)`` and the legacy ``step(action)`` four-tuple."""

    def __init__(self, obs_mode="state", reward_type="dense", frame_skip=5, max_episode_steps=MAX_EPISODE_STEPS,
                 **options):
        # The arguments mirror the parts of BaseEnv.__init__ this fake models; the other options are ignored.
        if obs_mode != "state":
            raise ValueError("the fake OpenCabinetDoor serves state observations only")
        if reward_type not in ("dense", "sparse"):
            raise ValueError("reward_type must be 'dense' or 'sparse'")
        self.obs_mode = obs_mode
        self.reward_type = reward_type
        self.frame_skip = int(frame_skip)
        self._max_episode_steps = int(max_episode_steps)
        self.action_space = Box([-1.0] * ACTION_DIM, [1.0] * ACTION_DIM)        # base_env.py:95
        self.observation_space = Box([float("-inf")] * OBS_DIM, [float("inf")] * OBS_DIM)  # base_env.py:423-427
        self._rng = random.Random()
        self._main_seed = None
        self._open = 0.0
        self._step_in_ep = 0
        self._done = False
        self._closed = False

    def reset(self, *, seed=None, options=None):
        """Start a new episode; ``seed`` selects the random stream (``level`` in the upstream reset)."""
        if self._closed:
            raise RuntimeError("the environment is closed")
        if seed is not None:
            self._main_seed = int(seed)
            self._rng = random.Random(self._main_seed)
        self._open = self._rng.uniform(0.0, INITIAL_OPEN_MAX)                    # placeholder
        self._step_in_ep = 0
        self._done = False
        return self._observation()

    def step(self, action):
        """Advance the analytic drawer by one control step and return ``(obs, reward, done, info)``."""
        if self._closed:
            raise RuntimeError("the environment is closed")
        if self._done:
            raise RuntimeError("the episode has ended; reset the environment first")
        values = [float(value) for value in action]
        if len(values) != ACTION_DIM:
            raise ValueError(f"action must have {ACTION_DIM} values, got {len(values)}")
        # placeholder: a kinematic first-order drawer model, not the upstream rigid-body simulation
        command = sum(values) / ACTION_DIM
        self._open = min(OPEN_EXTENT, max(0.0, self._open + OPEN_PER_STEP * command))
        self._step_in_ep += 1
        success = self._open >= OPEN_EXTENT                               # open_cabinet_door_drawer.py:237
        done = bool(success or self._step_in_ep >= self._max_episode_steps)
        if self.reward_type == "sparse":
            reward = float(success)                                      # base_env.py:556-557
        else:
            reward = self._open - OPEN_EXTENT                            # placeholder dense reward
        info = {"eval_info": {"success": success}, "open_extent": self._open}
        if self._step_in_ep >= self._max_episode_steps and not success:
            info["TimeLimit.truncated"] = True                           # base_env.py:565-567
        self._done = done
        return self._observation(), reward, done, info                   # base_env.py:571

    def seed(self, seed=None):
        """Read or set the main seed, as ``BaseEnv.seed`` does (``base_env.py:676-680``)."""
        if seed is None:
            return self._main_seed
        self._main_seed = int(seed)
        self._rng = random.Random(self._main_seed)
        return None

    def close(self):
        """Release the stand-in state (``BaseEnv.close`` at ``base_env.py:670-674``)."""
        self._closed = True

    def _observation(self):
        """The 75-value state-mode vector: cabinet pose/state, target indicator and agent state."""
        observation = [0.0] * OBS_DIM
        observation[3] = 1.0                                             # identity quaternion of the cabinet root
        observation[13 + TARGET_JOINT_INDEX] = self._open                # padded cabinet qpos
        observation[TARGET_INDICATOR_OFFSET + TARGET_JOINT_INDEX] = 1.0  # one-hot target indicator
        # The remaining cabinet and agent values stay at their placeholder 0.0; the real ones are read from SAPIEN.
        assert len(observation) == OBS_DIM
        return observation
