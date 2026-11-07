"""Fake backend of the gym_av_aloha driver: a pure Python kinematic stand-in for ``CubeTransferEnv``.

Why a fake: the upstream package imports mujoco, dm-control and numpy (pyproject.toml:9-12), which are not installed
where the gate runs, and package code never imports the clone.  This module mirrors the public surface the driver
uses (``reset``, ``step``, ``close``, ``get_obs``, ``get_reward``; gate G7) and the two Gymnasium spaces the bridge
reads: a ``Dict`` observation of ``agent_pos`` and ``environment_state``, and an unbounded 21-value ``Box`` action.
It does not import the upstream environment and never talks to a device.

The fake is kinematic: ``step`` stores the commanded action as the arm position and keeps a seeded cube pose; it
has no MuJoCo dynamics, contacts, actuator or sensor model, returns no camera frames and always reports reward 0
and ``terminated=False``.  The driver's fidelity ``gaps`` and RESULT.json say what is not modelled.

Every number below is fake test data, copied from upstream only where the shape of the contract needs it, and is
marked ``# placeholder``; none of it is a Fact or a Limit of the device.
"""

import random

ACTION_DIM = 21                                  # placeholder: AV_ACTION_DIM in sim_config.py:27
ENV_STATE_DIM = 7                                # placeholder: ENV_STATE_DIM in cube_transfer_env.py:15
MAX_REWARD = 4                                   # placeholder: CubeTransferEnv.max_reward
CUBE_X_LOW, CUBE_X_HIGH = -0.05, 0.05            # placeholder: cube_transfer_env.py:99
CUBE_Y_LOW, CUBE_Y_HIGH = 0.05, 0.15             # placeholder: cube_transfer_env.py:100
CUBE_QUAT = [1.0, 0.0, 0.0, 0.0]                 # placeholder: cube_transfer_env.py:104


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float64"

    def contains(self, value):
        try:
            return len(value) == self.shape[0] and all(
                self.low[index] <= float(item) <= self.high[index] for index, item in enumerate(value))
        except (TypeError, ValueError):
            return False


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()

    def contains(self, value):
        return isinstance(value, dict) and set(value) == set(self.spaces)


class FakeCubeTransferEnv:
    """A kinematic cube-transfer environment; the public members are the ones CubeTransferEnv has."""

    def __init__(self, **options):
        # The package configures cameras={}; accept any other construction options and do not model them.
        self.options = dict(options)
        self.max_reward = MAX_REWARD
        self.action_space = Box([-float("inf")] * ACTION_DIM, [float("inf")] * ACTION_DIM)
        self.observation_space = Dict({
            "agent_pos": Box([-float("inf")] * ACTION_DIM, [float("inf")] * ACTION_DIM),
            "environment_state": Box([-float("inf")] * ENV_STATE_DIM, [float("inf")] * ENV_STATE_DIM),
        })
        self._rng = random.Random()
        self._agent_pos = [0.0] * ACTION_DIM
        self._cube_pose = [0.0, 0.0, 0.0] + list(CUBE_QUAT)
        self._step_count = 0
        self._grasp_right = False
        self._closed = False

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        x = self._rng.uniform(CUBE_X_LOW, CUBE_X_HIGH)
        y = self._rng.uniform(CUBE_Y_LOW, CUBE_Y_HIGH)
        self._cube_pose = [x, y, 0.0] + list(CUBE_QUAT)
        self._agent_pos = [0.0] * ACTION_DIM
        self._step_count = 0
        self._grasp_right = False
        self._closed = False
        self.options = dict(options or {})
        return self.get_obs(), {"is_success": False}

    def step(self, action):
        if len(action) != ACTION_DIM:
            raise ValueError(f"the action needs {ACTION_DIM} values, got {len(action)}")
        self._agent_pos = [float(value) for value in action]
        self._step_count += 1
        observation = self.get_obs()
        reward = self.get_reward()
        terminated = reward == self.max_reward
        truncated = False
        info = {"is_success": terminated}
        return observation, reward, terminated, truncated, info

    def get_obs(self):
        return {"agent_pos": list(self._agent_pos), "environment_state": list(self._cube_pose)}

    def get_reward(self):
        return 0.0                                        # placeholder: no contact model

    def close(self):
        self._closed = True
