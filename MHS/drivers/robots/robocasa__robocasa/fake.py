"""Fake backend of the RoboCasa driver: a pure Python stand-in for ``gym.make("robocasa/PickPlaceCounterToCabinet")``.

Why a fake: the acceptance gate does not install robosuite, MuJoCo, gymnasium or the roughly 10 GB kitchen assets
(README.md:65), and package code never imports the clone.  This module therefore re-implements only the public
surface of ``robocasa.wrappers.gym_wrapper:RoboCasaGymEnv`` that the gymnasium bridge needs: ``reset``, ``step``,
``render``, ``close``, ``get_basic_observation`` and ``get_observation``, plus duck-typed ``Dict``, ``Box`` and
``Text`` spaces.  Every shape and every number that is a claim about the upstream cites the clone at commit
456174f62b89b8fca99eaaf33949c29fec9cfc2a.  All numbers that exist only to keep the stand-in cheap are test data
and are marked ``# placeholder``; they are never copied into a Fact or a Limit.

What this is not: the upstream environment.  No MuJoCo, robosuite, contact, asset, camera, task success or reward
model is present.  The base success test returns False (kitchen.py:1542-1551), so the fake pays reward 0.0 and never
ends the episode; the concrete task subclass is not modelled.  The fake's state values and its 2x2x3 camera frames
are placeholders; the upstream observation space declares 256x256x3 camera frames (gym_wrapper.py:244-250).  The
sim backend (``gymnasium.make``) was not run, and this fake was never compared with the upstream environment.
"""

import random

# gym_wrapper.py:44-47: the wrapper's camera configuration is 256 by 256 pixels.
CAMERA_WIDTH = 256
CAMERA_HEIGHTS = 256
# gym_wrapper.py:35-41: the three camera names the wrapper maps to video.* keys.
CAMERA_NAMES = ["robot0_agentview_left", "robot0_agentview_right", "robot0_eye_in_hand"]
MAPPED_CAMERA_NAMES = ["video.robot0_agentview_left", "video.robot0_agentview_right", "video.robot0_eye_in_hand"]
# gym_wrapper.py:265-267: the task description is Text(max_length=256).
TEXT_MAX_LENGTH = 256
# gym_wrapper.py:72-76: the final state.* observation boxes are Box(-1, 1).
STATE_LOW, STATE_HIGH = -1.0, 1.0
# gym_wrapper.py:244-250: camera frames are Box(0, 255) of shape (height, width, 3).
IMAGE_LOW, IMAGE_HIGH = 0, 255


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: ``low``, ``high`` and ``shape`` are what the bridge reads."""

    def __init__(self, low, high, shape):
        count = 1
        for item in shape:
            count *= int(item)
        # A small action Box keeps one bound per element (the bridge derives per-element limits).
        if isinstance(low, (int, float)) and count <= 64:
            self.low = [float(low)] * count
            self.high = [float(high)] * count
        else:
            self.low = low
            self.high = high
        self.shape = tuple(int(item) for item in shape)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces`` as a mapping."""

    def __init__(self, spaces=None):
        self.spaces = dict(spaces or {})

    def __setitem__(self, key, value):
        self.spaces[key] = value


class Text:
    """Duck-typed ``gymnasium.spaces.Text``: only the two members the wrapper sets are kept."""

    def __init__(self, max_length, charset):
        self.max_length = int(max_length)
        self.charset = charset


class FakeRoboCasaEnv:
    """A cheap kinematic stand-in for the RoboCasa gym wrapper, not the MuJoCo environment."""

    def __init__(self, env_name=None, camera_names=None, camera_widths=None, camera_heights=None,
                 enable_render=True, split="test", **kwargs):
        self.env_name = env_name
        self.camera_names = list(camera_names or CAMERA_NAMES)
        self.camera_widths = camera_widths if camera_widths is not None else CAMERA_WIDTH
        self.camera_heights = camera_heights if camera_heights is not None else CAMERA_HEIGHTS
        self.enable_render = enable_render
        self.split = split
        self.render_obs_key = f"{self.camera_names[0]}_image"
        self.render_cache = None
        self._rng = random.Random()
        # placeholder task language: the real string comes from env.get_ep_meta()["lang"] (gym_wrapper.py:299)
        self._language = ""
        # gym_wrapper.py:83-102 with :268: five float Box fields, every element bounded by -1 and 1.
        self.action_space = Dict({
            "action.gripper_close": Box(-1.0, 1.0, (1,)),
            "action.end_effector_position": Box(-1.0, 1.0, (3,)),
            "action.end_effector_rotation": Box(-1.0, 1.0, (3,)),
            "action.base_motion": Box(-1.0, 1.0, (4,)),
            "action.control_mode": Box(-1.0, 1.0, (1,)),
        })
        # gym_wrapper.py:303-326 maps the observations to state.* floats, three video.* frames and the task text.
        observation_space = Dict({
            # placeholder lengths: the robot observation lengths depend on the robot model and controller.
            "state.gripper_qpos": Box(STATE_LOW, STATE_HIGH, (2,)),
            "state.base_position": Box(STATE_LOW, STATE_HIGH, (3,)),
            "state.base_rotation": Box(STATE_LOW, STATE_HIGH, (4,)),
            "state.end_effector_position_relative": Box(STATE_LOW, STATE_HIGH, (3,)),
            "state.end_effector_rotation_relative": Box(STATE_LOW, STATE_HIGH, (4,)),
        })
        for name in MAPPED_CAMERA_NAMES:
            observation_space[name] = Box(IMAGE_LOW, IMAGE_HIGH,
                                          (self.camera_heights, self.camera_widths, 3))
        observation_space["annotation.human.task_description"] = Text(TEXT_MAX_LENGTH, "utf-8")
        self.observation_space = observation_space
        self._state = None
        self._tick = 0
        self._closed = False
        self._reset_state()

    def _reset_state(self):
        # placeholder state: the real reset samples a kitchen scene and a robot pose from the MuJoCo model.
        self._state = {
            "gripper_qpos": [self._rng.uniform(-0.05, 0.05) for _ in range(2)],
            "base_position": [self._rng.uniform(-0.05, 0.05) for _ in range(3)],
            "base_rotation": [0.0, 0.0, 0.0, 1.0],
            "end_effector_position_relative": [self._rng.uniform(-0.05, 0.05) for _ in range(3)],
            "end_effector_rotation_relative": [0.0, 0.0, 0.0, 1.0],
        }
        self._tick = 0
        self.render_cache = self._frame()

    def _frame(self):
        # placeholder camera frame; the upstream declares 256x256x3 and the fake keeps 2x2x3.
        return [[[0, 0, 0], [0, 0, 0]], [[0, 0, 0], [0, 0, 0]]]

    @staticmethod
    def _values(value, count):
        if isinstance(value, (list, tuple)):
            values = [float(item) for item in value]
        else:
            values = [float(value)] * count
        if len(values) != count:
            raise ValueError(f"the action field needs {count} values, got {len(values)}")
        return values

    def _observation(self):
        observation = {
            "state.gripper_qpos": list(self._state["gripper_qpos"]),
            "state.base_position": list(self._state["base_position"]),
            "state.base_rotation": list(self._state["base_rotation"]),
            "state.end_effector_position_relative": list(self._state["end_effector_position_relative"]),
            "state.end_effector_rotation_relative": list(self._state["end_effector_rotation_relative"]),
            "annotation.human.task_description": self._language,
        }
        for name in MAPPED_CAMERA_NAMES:
            observation[name] = self._frame()
        return observation

    def reset(self, seed=None, options=None):
        # gym_wrapper.py:342-346: a seed replaces the inner RNG; options is accepted and not used.
        if seed is not None:
            self._rng = random.Random(seed)
        self._reset_state()
        self._closed = False
        info = {"success": False}
        return self._observation(), info

    def step(self, action_dict):
        if self._closed:
            raise RuntimeError("the environment is closed")
        if self._state is None:
            raise RuntimeError("Call reset before using step method.")
        action = dict(action_dict)
        gripper = self._values(action["action.gripper_close"], 1)[0]
        position = self._values(action["action.end_effector_position"], 3)
        rotation = self._values(action["action.end_effector_rotation"], 3)
        base = self._values(action["action.base_motion"], 4)
        control_mode = self._values(action["action.control_mode"], 1)[0]
        # placeholder motion: 0.01 of the normalised action per tick, no contacts and no MuJoCo.
        for index in range(3):
            self._state["end_effector_position_relative"][index] += 0.01 * position[index]
            self._state["base_position"][index] += 0.01 * base[index]
            self._state["end_effector_rotation_relative"][index] += 0.01 * rotation[index]
        self._state["base_position"][2] += 0.01 * base[3]
        self._state["gripper_qpos"][0] += 0.01 * gripper
        self._state["gripper_qpos"][1] += 0.01 * gripper
        self._state["base_rotation"][3] = 1.0 if control_mode >= 0.0 else -1.0  # placeholder branch only
        self._tick += 1
        self.render_cache = self._frame()
        # gym_wrapper.py:374-385: reward 1.0 only on success, truncated is always False and done comes from the
        # inner env.  Kitchen._check_success returns False by default (kitchen.py:1542-1551), so the fake stays
        # reward 0.0 and done False; the concrete task's success test is not modelled.
        reward = 0.0
        done = False
        truncated = False
        info = {"success": False, "tick": self._tick}
        return self._observation(), reward, done, truncated, info

    def get_basic_observation(self, raw_obs):
        observation = dict(raw_obs)
        self.render_cache = observation[self.render_obs_key]
        observation["language"] = self._language
        return observation

    def get_observation(self, raw_obs):
        return self.get_basic_observation(raw_obs)

    def render(self):
        # gym_wrapper.py:387-390: render returns the cached frame and refuses before a reset or step.
        if self.render_cache is None:
            raise RuntimeError("Must run reset or step before render.")
        return self.render_cache

    def close(self):
        # gym_wrapper.py:392-393: close delegates to the inner environment and returns nothing.
        self.render_cache = None
        self._closed = True
