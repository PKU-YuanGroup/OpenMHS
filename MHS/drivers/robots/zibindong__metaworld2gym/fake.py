"""Fake backend of the metaworld2gym driver: a pure-Python stand-in for ``MetaWorldEnv`` (the upstream wrapper).

Why a fake: the gate runs without gym, mujoco-py or torch (setup.py:9-16), package code never imports the clone, and
the upstream wrapper renders camera images and builds a point cloud through a CUDA point-cloud generator.  This module
implements only the surface the ``GymnasiumBridge`` uses from the class the driver names as ``native``:
``action_space``, ``reset()``, ``step(action)`` and ``close()`` (the members of
``metaworld2gym.metaworld_env:MetaWorldEnv``; gate G7 compares the fake's public methods with that class).  The action
space mirrors the wrapped environment's four-element Box from -1 to +1
(metaworld/envs/mujoco/sawyer_xyz/sawyer_xyz_env.py:128-131); ``action_scale`` is 1/100 (sawyer_xyz_env.py:98).

What this is not: the Meta-World MuJoCo environment.  There is no rigid-body dynamics, contact, gripper, object motion,
camera, depth sensor, point-cloud generator or assembly reward.  Every number below is placeholders test data, marked
``# placeholder``, except the constants that restate the upstream shape and are cited: the four-element action bound,
the episode length 200 (metaworld2gym/metaworld_env.py:207) and the declared observation shapes
(README.md:39-43).  The image, depth and point-cloud arrays are deliberately smaller than the configured device
(the real sizes are named here and in the driver's fidelity ``gaps``); agent_pos and full_state keep their real
lengths.  Nothing here talks to a device.
"""

# metaworld2gym/metaworld_env.py:207 (episode_length = _max_episode_steps = 200)
EPISODE_LENGTH = 200
# README.md:39-43 (the configured observation shapes; only the first three are reduced by the fake)
IMAGE_SHAPE = (3, 8, 8)            # placeholder: the real image is (3, 224, 224)
DEPTH_SHAPE = (8, 8)               # placeholder: the real depth is (224, 224)
POINT_CLOUD_SHAPE = (16, 6)        # placeholder: the real point cloud is (1024, 6)
AGENT_POS = 9                      # README.md:42
FULL_STATE = 39                    # README.md:43


class Box:
    """Duck-typed ``gym.spaces.Box``: the lower and upper bound per element and a shape."""

    def __init__(self, low, high, shape=None):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"


class FakeMetaWorldEnv:
    """A deterministic, physics-free stand-in for ``metaworld2gym.metaworld_env:MetaWorldEnv``."""

    def __init__(self, **_options):
        # metaworld/envs/mujoco/sawyer_xyz/sawyer_xyz_env.py:128-131
        self.action_space = Box([-1.0, -1.0, -1.0, -1.0], [1.0, 1.0, 1.0, 1.0], (4,))
        self._closed = False
        self._episode = 0
        self._tick = 0                                  # placeholder
        self._position = [0.0, 0.6, 0.2, 0.0]           # placeholder: x, y, z and gripper effort
        self._observation = self._make_observation()

    def reset(self):
        """``metaworld2gym/metaworld_env.py:302-308``: start an episode and return the observation dictionary."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self._episode += 1
        self._tick = 0                                  # placeholder
        self._position = [0.0, 0.6, 0.2, 0.0]           # placeholder
        self._observation = self._make_observation()
        return self._observation

    def step(self, action):
        """``metaworld2gym/metaworld_env.py:295-300``: return ``(observation, reward, done, info)``.

        The first three elements move the hand and the last is the gripper effort, as the wrapped environment's
        ``set_xyz_action``/``do_simulation`` pair does (sawyer_xyz_env.py:406-408).  The gain and the reward are
        placeholders; one call is one wrapper step of ``frame_skip=5`` physics frames.
        """
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = [float(value) for value in action]
        if len(values) != 4:
            raise AssertionError(f"Actions should be size 4, got {len(values)}")  # sawyer_xyz_env.py:128-131
        for index in range(3):
            clipped = max(-1.0, min(1.0, values[index]))       # sawyer_xyz_env.py:327-328 (set_xyz_action clips)
            self._position[index] += 0.01 * clipped             # placeholder: action_scale is 1/100
        self._position[3] = max(-1.0, min(1.0, values[3]))      # placeholder: gripper effort, not a bound
        self._tick += 1
        self._observation = self._make_observation()
        reward = 0.0                                            # placeholder: the assembly reward is not modelled
        done = self._tick >= EPISODE_LENGTH                     # metaworld2gym/metaworld_env.py:207, :299
        info = {"success": False, "reachDist": 0.0, "pickRew": 0.0, "epRew": 0.0,
                "goalDist": 0.0, "unscaled_reward": 0.0}        # placeholders
        return self._observation, reward, done, info

    def close(self):
        """The wrapper's close; the stand-in only marks itself closed."""
        self._closed = True

    def _make_observation(self):
        """The wrapper's default dictionary (metaworld2gym/metaworld_env.py:121-127), with placeholder arrays."""
        tick = self._tick
        x, y, z, gripper = self._position
        image = [[[(x + y + z + tick + channel * 7 + row + column) % 256 for column in range(IMAGE_SHAPE[2])]
                  for row in range(IMAGE_SHAPE[1])] for channel in range(IMAGE_SHAPE[0])]          # placeholder
        depth = [[(x + y + tick + row + column * 0.5) for column in range(DEPTH_SHAPE[1])]
                 for row in range(DEPTH_SHAPE[0])]                                                 # placeholder
        agent_pos = [x, y, z, x + 0.01, y, z, x - 0.01, y, z]                                    # placeholder
        point_cloud = [[x + 0.001 * index, y, z, 128.0, 128.0, 128.0]
                       for index in range(POINT_CLOUD_SHAPE[0])]                                  # placeholder
        full_state = [x, y, z] + [0.0] * (FULL_STATE - 4) + [float(tick)]                          # placeholder
        return {
            "image": image,               # real shape (3, 224, 224), README.md:39
            "depth": depth,               # real shape (224, 224), README.md:40
            "agent_pos": agent_pos,       # README.md:42
            "point_cloud": point_cloud,   # real shape (1024, 6), README.md:41
            "full_state": full_state,     # README.md:43
        }
