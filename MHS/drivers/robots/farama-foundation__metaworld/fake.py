"""Fake backend of the Meta-World driver: a pure-Python stand-in for ``SawyerNutAssemblyEnvV3``.

Why a fake: the gate runs without metaworld, MuJoCo or numpy (the upstream install needs them,
metaworld/pyproject.toml), and package code never imports the clone.  This module implements only the surface the
``GymnasiumBridge`` reads from the class the driver names as ``native``: ``reset``, ``step``, ``action_space`` and
``observation_space``.  Every upstream constant cites its line of the clone at the pinned commit
(c0dafaf1557f31cad3b96ba2b62462f45638f5a5); invented test data is marked ``# placeholder``.

What this is not: the MuJoCo environment.  It has no contacts, rigid-body dynamics, gripper or object motion.  It
applies the first three action elements to the hand position as a pure translation and returns an observation of
the declared 39-element shape; one environment step advances one control period of ``frame_skip`` physics frames.
The driver's fidelity ``gaps`` say this, and no hardware device is modelled.
"""

# metaworld/sawyer_xyz_env.py:239-243 (SawyerXYZEnv.__init__)
ACTION_LOW = [-1.0, -1.0, -1.0, -1.0]
ACTION_HIGH = [1.0, 1.0, 1.0, 1.0]
# metaworld/sawyer_xyz_env.py:175-183 (frame_skip and action_scale defaults)
FRAME_SKIP = 5
ACTION_SCALE = 1.0 / 100.0
# metaworld/sawyer_xyz_env.py:153-154 (the task horizon)
MAX_PATH_LENGTH = 500
# metaworld/sawyer_xyz_env.py:475-527 (the observation layout: 18 current + 18 previous + 3 goal)
CURRENT_SIZE = 18
OBJECT_PAD = 14
OBSERVATION_SIZE = 39
# metaworld/envs/sawyer_assembly_peg_v3.py:28-29 (hand_low / hand_high of this task)
HAND_LOW = [-0.5, 0.40, 0.05]
HAND_HIGH = [0.5, 1.0, 0.5]
# metaworld/envs/sawyer_assembly_peg_v3.py:47-53 (the task's init_config and default goal)
OBJ_INIT = [0.0, 0.6, 0.02]
HAND_INIT = [0.0, 0.6, 0.2]
GOAL_POS = [0.1, 0.8, 0.1]


class _Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float64"


class FakeSawyerNutAssemblyEnvV3:
    """The assembly task without MuJoCo: ``reset(seed, options)`` and ``step(action)`` as the upstream class has them."""

    # metaworld/sawyer_xyz_env.py:153-154
    max_path_length = MAX_PATH_LENGTH

    def __init__(self):
        # metaworld/sawyer_xyz_env.py:239-243
        self.action_space = _Box(ACTION_LOW, ACTION_HIGH)
        # metaworld/sawyer_xyz_env.py:537-577: the hand bounds repeated, gripper -1..1, 14 object values, goal bounds
        hand_low, hand_high = list(HAND_LOW), list(HAND_HIGH)
        low = hand_low + [-1.0] + [-float("inf")] * OBJECT_PAD + hand_low + [-1.0] + [-float("inf")] * OBJECT_PAD \
            + [-0.1, 0.75, 0.1]
        high = hand_high + [1.0] + [float("inf")] * OBJECT_PAD + hand_high + [1.0] + [float("inf")] * OBJECT_PAD \
            + [0.1, 0.85, 0.1]
        self.observation_space = _Box(low, high)
        self.curr_path_length = 0
        self._hand = list(HAND_INIT)
        self._object = list(OBJ_INIT)
        self._gripper = 0.0  # placeholder
        self._prev_obs = [0.0] * CURRENT_SIZE  # placeholder
        self._last_observation = self._observation()

    def reset(self, seed=None, options=None):
        """Reset the task; like the upstream method (sawyer_xyz_env.py:664-682) it ignores seed and options."""
        self.curr_path_length = 0
        self._hand = list(HAND_INIT)
        self._object = list(OBJ_INIT)
        self._gripper = 0.0  # placeholder
        self._prev_obs = [0.0] * CURRENT_SIZE  # placeholder
        self._last_observation = self._observation()
        return list(self._last_observation), {}

    def step(self, action):
        """Apply one 4-element action; the value ranges are enforced by the bridge from action_space."""
        if len(action) != 4:
            raise AssertionError(f"Actions should be size 4, got {len(action)}")  # sawyer_xyz_env.py:591
        for index in range(3):
            delta = max(-1.0, min(1.0, float(action[index]))) * ACTION_SCALE  # sawyer_xyz_env.py:327-328
            self._hand[index] = max(HAND_LOW[index], min(HAND_HIGH[index], self._hand[index] + delta))
        self._gripper = max(0.0, min(1.0, abs(float(action[3]))))  # placeholder
        self.curr_path_length += 1
        self._last_observation = self._observation()
        # placeholder: a kinematic stand-in pays no dense reward and reports no task success
        reward = 0.0
        info = {"success": False, "near_object": 0.0, "grasp_success": False, "grasp_reward": 0.0,
                "in_place_reward": 0.0, "obj_to_target": 0.0, "unscaled_reward": 0.0}
        truncated = self.curr_path_length == self.max_path_length  # sawyer_xyz_env.py:631-642
        return list(self._last_observation), reward, False, truncated, info

    def _current(self):
        """The 18-element current observation: hand (3), gripper (1) and 14 padded object values."""
        quat = [1.0, 0.0, 0.0, 0.0]  # placeholder: the object stays at its start orientation
        object_values = list(self._object) + quat + [0.0] * (OBJECT_PAD - 7)  # placeholder padding
        return list(self._hand) + [self._gripper] + object_values

    def _observation(self):
        """The 39-element flat observation of sawyer_xyz_env.py:513-527."""
        current = self._current()
        observation = current + list(self._prev_obs) + list(GOAL_POS)
        self._prev_obs = current  # sawyer_xyz_env.py:526
        return observation
