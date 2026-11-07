"""Fake backend of the Factor-World driver: a pure-Python stand-in for ``SawyerNutAssemblyEnvV2``.

Why a fake: the acceptance gate runs without MuJoCo 2.1, mujoco_py or gym (``conda_env.yml:19-46``), and package code
never imports the clone.  This module implements only the surface the ``GymnasiumBridge`` uses from the class the
driver names as ``native``: ``action_space``, ``observation_space``, ``dt``, ``reset()``, ``step(action)``,
``seed(seed)`` and ``close()``.  Those members exist on
``envs.tasks.sawyer_assembly_peg_v2:SawyerNutAssemblyEnvV2`` and its clone bases (gate G7).

What this is not: the MuJoCo task.  There is no MJCF loading, no mujoco_py, no rigid-body dynamics, no contact, no
mocap weld, no gripper actuator, no object motion, no camera render and no assembly reward.  The 39-element proprio
vector is the upstream shape (``envs/sawyer_xyz_env.py:391-425``), but every start position, object point, goal point
and previous-frame value below is placeholder test data, marked ``# placeholder``.  The action bounds, the 500-step
episode length, the action scale and the time step are the upstream constants, each cited.  Nothing here talks to a
device.
"""

from collections.abc import Mapping

# envs/sawyer_xyz_env.py:164-167: the action Box is four elements from -1 to +1
ACTION_LOW = [-1.0, -1.0, -1.0, -1.0]
ACTION_HIGH = [1.0, 1.0, 1.0, 1.0]
# envs/sawyer_xyz_env.py:100: SawyerXYZEnv.max_path_length = 500
MAX_PATH_LENGTH = 500
# envs/sawyer_xyz_env.py:116: action_scale=1./100
ACTION_SCALE = 1.0 / 100.0
# third_party/metaworld/metaworld/envs/assets_v2/scene/basic_scene.xml:2 (0.0025 s) times
# envs/sawyer_xyz_env.py:111 (frame_skip=5)
TIMESTEP_S = 0.0025
FRAME_SKIP = 5
DT = TIMESTEP_S * FRAME_SKIP
# envs/sawyer_xyz_env.py:396: the v2 proprio observation is 39 elements
OBSERVATION_SIZE = 39


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element and a shape."""

    def __init__(self, low, high, shape=None):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gym.spaces.Dict``: named member spaces (the bridge reads ``spaces``)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        if not isinstance(self.spaces, Mapping):
            raise TypeError("Dict spaces must be a mapping")
        self.dtype = "dict"


class FakeSawyerNutAssemblyEnvV2:
    """A deterministic, physics-free stand-in for the assembly-v2 task class."""

    def __init__(self, **_options):
        # envs/sawyer_xyz_env.py:164-167
        self.action_space = Box(ACTION_LOW, ACTION_HIGH)
        # envs/sawyer_xyz_env.py:474-483: without images the observation space has only proprio
        self.observation_space = Dict({
            "proprio": Box([float("-inf")] * OBSERVATION_SIZE, [float("inf")] * OBSERVATION_SIZE),
        })
        self._closed = False
        self._episode = 0
        self._tick = 0
        self._seed = None
        self._hand = [0.0, 0.5, 0.2]            # placeholder: hand position
        self._gripper = 0.0                     # placeholder: gripper distance
        self._object = [0.1, 0.7, 0.02]         # placeholder: object position
        self._goal = [0.1, 0.8, 0.1]            # placeholder: goal position
        self._prev = self._current()
        self._observation = self._make_observation()

    @property
    def dt(self):
        """``MujocoEnv.dt`` (envs/mujoco_env.py:118-120): model.opt.timestep times frame_skip."""

        return DT

    def seed(self, seed):
        """``MujocoEnv.seed`` (envs/mujoco_env.py:75-81): record the seed and return it in a list.

        Upstream also seeds the numpy generator and the spaces; the fake records it only, because the configured
        task's ``random_init`` is false and its reset uses fixed start positions.
        """

        if seed is None:
            raise AssertionError("seed must not be None")
        self._seed = int(seed)
        return [self._seed]

    def reset(self):
        """``SawyerXYZEnv.reset`` (envs/sawyer_xyz_env.py:540-542): start an episode and return the observation."""

        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self._episode += 1
        self._tick = 0
        self._hand = [0.0, 0.5, 0.2]            # placeholder
        self._gripper = 0.0                     # placeholder
        self._object = [0.1, 0.7, 0.02]         # placeholder
        self._goal = [0.1, 0.8, 0.1]            # placeholder
        self._prev = self._current()
        self._observation = self._make_observation()
        return self._observation

    def step(self, action):
        """One environment step: move the hand, set the gripper and advance the tick.

        ``SawyerXYZEnv.step`` (envs/sawyer_xyz_env.py:486-488) applies action[:3] through ``set_xyz_action`` and
        action[-1] as ``[action[-1], -action[-1]]``; here the hand moves by the normalised action at ``action_scale``
        and no physics is integrated.  The reward and the success flag are placeholders, so the episode ends only at
        ``max_path_length`` (envs/sawyer_xyz_env.py:100, :522).
        """

        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = [float(value) for value in action]
        if len(values) != 4:
            raise AssertionError(f"Actions should be size 4, got {len(values)}")
        for index in range(3):
            clipped = max(-1.0, min(1.0, values[index]))       # envs/sawyer_xyz_env.py:207
            self._hand[index] += clipped * ACTION_SCALE        # envs/sawyer_xyz_env.py:208
        self._gripper = max(-1.0, min(1.0, values[3]))         # placeholder: no contact model
        current = self._current()
        self._observation = {
            "image": None,                     # envs/sawyer_xyz_env.py:417-422 (get_image_obs is false)
            "proprio": current + self._prev + list(self._goal),
        }
        self._prev = current
        self._tick += 1
        done = self._tick >= MAX_PATH_LENGTH                   # envs/sawyer_xyz_env.py:522
        info = {
            "success": 0.0,                    # placeholder: the assembly success is not computed
            "near_object": 0.0,                # placeholder
            "grasp_success": False,            # placeholder
            "grasp_reward": 0.0,               # placeholder
            "in_place_reward": 0.0,            # placeholder
            "obj_to_target": 0.0,              # placeholder
            "unscaled_reward": 0.0,            # placeholder
        }
        return self._observation, 0.0, done, info            # placeholder: reward is always 0.0

    def close(self):
        """``MujocoEnv.close`` (envs/mujoco_env.py:157-160); the stand-in only marks itself closed."""

        self._closed = True

    def _current(self):
        """The 18-element current part of the v2 observation (envs/sawyer_xyz_env.py:343-384)."""

        return (list(self._hand) + [self._gripper] + list(self._object)
                + [1.0, 0.0, 0.0, 0.0] + [0.0] * 7)           # placeholder: object quaternion and padding

    def _make_observation(self):
        """The 39-element v2 proprio dictionary (envs/sawyer_xyz_env.py:391-425)."""

        return {
            "image": None,                     # envs/sawyer_xyz_env.py:417-422
            "proprio": self._current() + list(self._prev) + list(self._goal),
        }
