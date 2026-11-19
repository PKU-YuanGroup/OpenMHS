"""Fake backend for the AV-ALOHA ``gym_guided_vision`` InsertPeg environment (``FakeInsertPegEnv``).

The upstream class is ``gym_guided_vision.env:InsertPegEnv`` (``env.py:412-425``), a Gymnasium environment whose
``step`` writes 21 joint/gripper targets into a MuJoCo model and whose reward is computed from MuJoCo contact pairs.
The gate cannot import the clone, MuJoCo or dm_control: package code never imports the clone, so this module is an
analytic stand-in with the same public Gymnasium API (``reset``, ``step``, ``get_obs``, ``get_reward``, ``close``)
and the same action layout (``env.py:203-226``), not the upstream simulator and not a recording.

What is modelled (every constant below is test data, marked ``# placeholder`` where it is invented):

* the 21-value action layout: six left joints, left gripper, six right joints, right gripper, seven middle joints;
* the observation layout: a per-camera ``pixels`` mapping and a 21-value ``agent_pos`` vector;
* the action space ``Box(-inf, inf, (num_joints,), float32)`` and the observation space
  ``Dict(pixels=<camera: Box(480, 640, 3)>, agent_pos=Box(21))`` copied from the upstream lines named in the
  driver's ``action_space_ref`` and ``facts``;
* ``reset(seed, options)`` returning ``(observation, info)`` and ``step(action)`` returning the Gymnasium
  five-tuple, with the upstream's constant ``terminated=False`` and ``truncated=False`` (``env.py:222-224``).

What is not modelled: MuJoCo physics, contacts, gravity, constraints, actuator dynamics, the peg and hole task
objects, and the contact-based reward of ``InsertPegEnv.get_reward`` (``env.py:425-472``).  The fake therefore
returns reward 0 and ``is_success`` False, and its joints follow the commanded targets immediately.  The upstream
renders six cameras at 480x640x3 (``env.py:66-85``); the fake returns a 2x2x3 placeholder image per camera to keep
receipts small, as disclosed in the driver's fidelity ``gaps`` and in RESULT.json.  Every numeric literal here is
test data, not a Fact, a Limit or a reference.
"""

import random

#: The upstream camera names (constants.py:8-15), copied here so the fake observation dict has the same keys.
CAMERAS = (
    "zed_cam_left",
    "zed_cam_right",
    "wrist_cam_left",
    "wrist_cam_right",
    "overhead_cam",
    "worms_eye_cam",
)

#: placeholder: the fake returns a tiny image; the upstream renders 480x640x3 (env.py:66-85).
FAKE_PIXEL_HEIGHT = 2
FAKE_PIXEL_WIDTH = 2
FAKE_PIXEL_CHANNELS = 3
#: placeholder: the upstream starts its arm poses from constants.py:26-28; the fake starts at zero.
FAKE_START_POSE = 0.0
#: placeholder: the upstream opens the gripper with a normalized 1 (env.py:234-241); the fake does the same.
OPEN_GRIPPER = 1.0
#: The upstream InsertPegEnv sets max_reward = 4 (env.py:420).
MAX_REWARD = 4


class Box:
    """Duck-typed ``gymnasium.spaces.Box`` as the bridge reads it (``__name__ == "Box"``, ``low``/``high``)."""

    def __init__(self, low, high, shape=None, dtype="float64"):
        self.low = low
        self.high = high
        self.shape = tuple(shape) if shape is not None else ()
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces`` as a mapping."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeInsertPegEnv:
    """The public Gymnasium interface of ``InsertPegEnv`` without MuJoCo (see the module docstring)."""

    def __init__(self, xml=None, num_arms=3, cameras=None, observation_height=480, observation_width=640):
        # The xml path is part of the upstream constructor (env.py:36-42); the fake has no MuJoCo model to load.
        if num_arms not in (2, 3):
            raise ValueError(f"Invalid number of arms: {num_arms}")
        self.xml = xml
        self.num_arms = num_arms
        self.cameras = list(CAMERAS if cameras is None else cameras)
        self.observation_height = observation_height
        self.observation_width = observation_width
        self.num_joints = 14 if num_arms == 2 else 21                    # upstream env.py:60-64
        self.action_space = Box([float("-inf")] * self.num_joints,     # upstream env.py:87
                                [float("inf")] * self.num_joints,
                                shape=(self.num_joints,), dtype="float32")
        self.observation_space = Dict({
            "pixels": Dict({
                camera: Box(0.0, 255.0, shape=(observation_height, observation_width, FAKE_PIXEL_CHANNELS),
                            dtype="uint8")                          # upstream env.py:66-78
                for camera in self.cameras
            }),
            "agent_pos": Box([float("-inf")] * self.num_joints,
                             [float("inf")] * self.num_joints,
                             shape=(self.num_joints,), dtype="float64"),  # upstream env.py:79-84
        })
        self.max_reward = MAX_REWARD                                    # upstream env.py:420
        self._qpos = [FAKE_START_POSE] * self.num_joints                # placeholder start pose
        self._open_grippers()
        self._episode = 0
        self._rng = random.Random()                                     # placeholder RNG
        self._closed = False

    def _open_grippers(self):
        """The left and right gripper elements of agent_pos are normalized; upstream opens them (env.py:234-241)."""
        self._qpos[6] = OPEN_GRIPPER                                    # placeholder open gripper
        self._qpos[13] = OPEN_GRIPPER                                   # placeholder open gripper

    def get_obs(self):
        """Return the same observation keys as ``GuidedVisionEnv.get_obs`` (env.py:168-190)."""
        image = [[[0, 0, 0] for _ in range(FAKE_PIXEL_WIDTH)]          # placeholder pixel value
                 for _ in range(FAKE_PIXEL_HEIGHT)]
        return {
            "pixels": {camera: [row[:] for row in image] for camera in self.cameras},
            "agent_pos": list(self._qpos),
        }

    def get_reward(self):
        """The upstream reward is contact-based (env.py:425-472); the fake models no contacts and returns 0."""
        return 0.0

    def step(self, action):
        """Apply the 21-value action layout of ``GuidedVisionEnv.step`` (env.py:203-226)."""
        try:
            values = [float(value) for value in action]
        except (TypeError, ValueError) as exc:
            raise ValueError("action must be a sequence of numbers") from exc
        if len(values) != self.num_joints:
            raise ValueError(f"action must have {self.num_joints} values, got {len(values)}")
        # env.py:204-215: six left joints, left gripper, six right joints, right gripper, seven middle joints.
        self._qpos[:6] = values[:6]
        self._qpos[6] = values[6]
        self._qpos[7:13] = values[7:13]
        self._qpos[13] = values[13]
        if self.num_arms == 3:
            self._qpos[14:21] = values[14:21]
        reward = self.get_reward()
        info = {"is_success": reward == self.max_reward}                # upstream env.py:224
        # env.py:222-223: the upstream step never terminates or truncates.
        return self.get_obs(), reward, False, False, info

    def reset(self, seed=None, options=None):
        """Reset the fake state; ``seed`` and ``options`` are accepted as the upstream reset accepts them."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._qpos = [FAKE_START_POSE] * self.num_joints                # placeholder start pose
        self._open_grippers()
        self._episode += 1
        return self.get_obs(), {"is_success": False}                    # upstream env.py:246-249

    def close(self):
        """The upstream close releases the viewer (env.py:400-408); the fake has none, so it only marks closed."""
        self._closed = True
