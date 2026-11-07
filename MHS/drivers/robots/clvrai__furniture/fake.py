"""Fake backend of the furniture driver: a pure-Python stand-in for ``FurnitureGym`` (IKEASawyer-v0).

Why a fake: the clone needs Python 3.7, MuJoCo 2.0 and Unity 2018.4.23f1 (``docs/installation.md:3-7``), its
``setup.py:11-31`` pulls gym, mujoco-py, numpy, scipy, glfw and Unity bindings, and package code never imports the
clone.  This module mirrors the public members of ``furniture.env.furniture_gym:FurnitureGym`` that the
``GymnasiumBridge`` uses (``reset``, ``step`` and ``close``; gate G7) and the spaces the wrapper copies from the
concrete environment.

The shapes and bounds are the registered ``IKEASawyer-v0`` environment's: the action space is a ``Dict`` with a
``default`` ``Box`` of 3 + 3 + 1 + 1 values bounded -1 to 1 (``furniture/env/furniture.py:294-310`` and
``furniture/env/furniture_sawyer.py:60-64``); ``object_ob`` has (3 + 4) * 3 = 21 values for the three
swivel_chair_0700 bodies (``furniture/env/furniture.py:230-237`` and
``furniture/env/models/assets/objects/swivel_chair_0700.xml:19-47``); ``robot_ob`` has 3 + 4 + 3 + 3 + 2 = 15
values (``furniture/env/furniture_sawyer.py:44-48``).  Every number below is placeholder test data, marked
``# placeholder``, except the cited shape, bound and horizon constants.  The public methods return the legacy
FurnitureGym results: ``reset()`` returns the observation dictionary and ``step(action)`` returns
``(observation, reward, done, info)`` (``furniture/env/furniture_gym.py:52-65``).

What this is not: the MuJoCo furniture-assembly environment.  It has no rigid-body dynamics, contacts, weld
equalities, inverse kinematics, gripper, furniture placement, assembly reward, success predicate or rendering; the
placeholder eef motion is not the clone's controller.  Nothing here talks to a device.
"""

import math

# furniture/env/models/assets/objects/swivel_chair_0700.xml:19-47: three furniture bodies
OBJECT_COUNT = 3
# furniture/env/furniture.py:236: (3 + 4) values per object (position and quaternion)
OBJECT_VALUES = (3 + 4) * OBJECT_COUNT
# furniture/env/furniture_sawyer.py:47: pos, quat, velp, velr, gripper
ROBOT_VALUES = 3 + 4 + 3 + 3 + 2
# furniture/env/furniture_sawyer.py:60-64: ik dof is 3 + 3 + 1 + 1
ACTION_VALUES = 3 + 3 + 1 + 1
# furniture/env/furniture.py:303-305: the Box bounds are low=-1 and high=1
ACTION_LOW, ACTION_HIGH = -1.0, 1.0
# furniture/config/furniture.py:164-168: max_episode_steps defaults to 2000
MAX_EPISODE_STEPS = 2000                                        # placeholder: configured default


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element and a shape."""

    def __init__(self, low, high, shape=None):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gym.spaces.Dict``: a mapping from member names to their spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeFurnitureGym:
    """A deterministic, physics-free stand-in for ``furniture.env.furniture_gym:FurnitureGym``."""

    def __init__(self, **_options):
        # furniture/env/furniture.py:294-310 and furniture/env/furniture_sawyer.py:60-64
        self.action_space = Dict({"default": Box([ACTION_LOW] * ACTION_VALUES,
                                                 [ACTION_HIGH] * ACTION_VALUES, (ACTION_VALUES,))})
        # furniture/env/furniture.py:230-237 and furniture/env/furniture_sawyer.py:44-48; unbounded like upstream
        self.observation_space = Dict({
            "object_ob": Box([-math.inf] * OBJECT_VALUES, [math.inf] * OBJECT_VALUES, (OBJECT_VALUES,)),
            "robot_ob": Box([-math.inf] * ROBOT_VALUES, [math.inf] * ROBOT_VALUES, (ROBOT_VALUES,)),
        })
        self._closed = False
        self._episode = 0
        self._tick = 0                                           # placeholder
        self._object_ob = self._start_objects()
        self._robot_ob = self._start_robot()

    def reset(self, furniture_id=None, background=None):
        """``furniture/env/furniture_gym.py:52-57``: start an episode and return the observation dictionary.

        The clone's reset takes a furniture id and a background, not a seed; the bridge's seed argument falls back
        to this no-argument call when the environment exposes no ``seed`` method.
        """
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self._episode += 1
        self._tick = 0                                           # placeholder
        self._object_ob = self._start_objects()
        self._robot_ob = self._start_robot()
        return self._observation()

    def step(self, action):
        """``furniture/env/furniture_gym.py:59-65``: return ``(observation, reward, done, info)``.

        The action is the wrapper's dictionary of one ``default`` array (``furniture/env/furniture.py:364-385``).
        The eef and gripper motion, reward and info values are placeholders; one call is one environment step.
        """
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = self._action_values(action)
        if len(values) != ACTION_VALUES:
            raise AssertionError(f"the fake IKEASawyer action needs {ACTION_VALUES} values, got {len(values)}")
        self._tick += 1
        # placeholder kinematics: move the eef by the first 3 elements and map the rest onto velocities and gripper
        self._robot_ob[2] += 0.01 * values[0]                    # placeholder: x
        self._robot_ob[3] += 0.01 * values[1]                    # placeholder: y
        self._robot_ob[4] += 0.01 * values[2]                    # placeholder: z
        self._robot_ob[9:12] = [0.01 * value for value in values[0:3]]    # placeholder: eef_velp
        self._robot_ob[12:15] = [0.01 * value for value in values[3:6]]   # placeholder: eef_velr
        self._robot_ob[0] = values[6]                            # placeholder: gripper_qpos[0]
        self._robot_ob[1] = values[7]                            # placeholder: gripper_qpos[1]
        done = self._tick >= MAX_EPISODE_STEPS                   # placeholder: only the horizon, never success
        info = {"success_reward": 0.0, "touch_reward": 0.0, "pick_reward": 0.0,
                "ctrl_penalty": 0.0}                             # placeholder: the clone's _compute_reward terms
        if done:
            info.update({"episode_success": 0, "episode_reward": 0.0, "episode_length": self._tick,
                         "episode_time": 0.0, "episode_unstable": 0.0,
                         "episode_num_connected": 0})            # placeholder: the clone's _after_step metrics
        return self._observation(), 0.0, done, info              # placeholder: assembly reward is not modelled

    def close(self):
        """The wrapper's close; the stand-in only marks itself closed."""
        self._closed = True

    @staticmethod
    def _action_values(action):
        """The wrapper's action dictionary: a mapping with one ``default`` array (furniture.py:364-385)."""
        if isinstance(action, dict):
            if "default" not in action:
                raise AssertionError("the IKEASawyer action dictionary has no 'default' member")
            action = action["default"]
        return [float(value) for value in action]

    @staticmethod
    def _start_objects():
        """Twenty-one placeholder values: position 3 and quaternion 4 for each of the three parts."""
        return [0.0] * OBJECT_VALUES                             # placeholder

    @staticmethod
    def _start_robot():
        """Fifteen placeholder values: gripper 2, eef pos 3, quat 4, velp 3 and velr 3 (Sawyer ik order)."""
        return [0.0, 0.0,                                      # placeholder: gripper_qpos
                0.0, 0.0, 0.0,                                 # placeholder: eef_pos
                1.0, 0.0, 0.0, 0.0,                            # placeholder: eef_quat xyzw
                0.0, 0.0, 0.0,                                 # placeholder: eef_velp
                0.0, 0.0, 0.0]                                 # placeholder: eef_velr

    def _observation(self):
        """The wrapper's observation dictionary: object_ob and robot_ob (furniture/env/furniture.py:1344-1387)."""
        return {"object_ob": list(self._object_ob), "robot_ob": list(self._robot_ob)}
