"""Fake backend of the ManiSkill2 real2sim driver: a pure Python stand-in for its default state environment.

Why a fake: the acceptance gate never imports the clone (SAPIEN, PyTorch and the asset tree are not installed where
the gate runs), and package code never imports the clone either. This module re-implements the public surface of
``mani_skill2_real2sim.envs.custom_scenes.grasp_single_in_scene:GraspSingleCokeCanInSceneEnv`` that the Gymnasium
bridge uses: ``reset``, ``step``, ``close``, ``get_state``, ``set_state``, ``action_space`` and
``observation_space``. Those names all exist on the upstream class (gate G7).

What this is not: the upstream environment. The fidelity ``gaps`` of the driver list the differences. In short:

* the physics is not simulated: the observation is a stand-in vector whose changes follow the action, so a step has
  an observable effect but no contact, actuator or object dynamics;
* the initial jitter comes from Python's ``random.Random(seed)``; upstream draws from numpy's ``RandomState``;
* the action bounds and the 48-value state layout follow the default upstream configuration, but the values in this
  file are test data (each block is marked ``# placeholder``), not facts and not a replacement for the clone;
* there is no rendering and no asset loading.

Nothing here talks to a device.
"""

import math
import random
import struct

# placeholder: the 80-step TimeLimit that gymnasium.make adds to GraspSingleCokeCanInScene-v0
# (grasp_single_in_scene.py:613; registration.py:127-130). Test data in this fake.
MAX_EPISODE_STEPS = 80

# placeholder: the default seven-element action Box derived from the upstream configuration:
# three position deltas in [-1.0, 1.0] and three rotation deltas in [-pi/2, pi/2]
# (agents/configs/google_robot/defaults.py:168-176 and agents/controllers/pd_ee_pose.py:161-178),
# then the normalized gripper action in [-1, 1] (agents/configs/google_robot/defaults.py:291-307,
# utils/common.py:121-123). Test data in this fake.
# Match the explicit float32 Box conversion; the selected arm has normalize_action=False.
_ROTATION_BOUND = struct.unpack("f", struct.pack("f", math.pi / 2))[0]
ACTION_LOW = [-1.0] * 3 + [-_ROTATION_BOUND] * 3 + [-1.0]
ACTION_HIGH = [1.0] * 3 + [_ROTATION_BOUND] * 3 + [1.0]

# placeholder: 11 qpos + 11 qvel + 2 gripper targets + 7 base pose + 7 tcp pose + 7 object pose + 3 relative position.
# The layout follows the default state observation (agents/robots/googlerobot.py:21 and :173-186,
# envs/custom_scenes/base_env.py:344-346, envs/custom_scenes/grasp_single_in_scene.py:390-398).
OBSERVATION_SIZE = 48

# placeholder: upstream start qpos of the static Google robot (envs/custom_scenes/base_env.py:265-275).
# Test data in this fake; it is not copied into a Fact, Limit or reference.
START_QPOS = [
    -0.2639457174606611,
    0.0831913360274175,
    0.5017611504652179,
    1.156859026208673,
    0.028583671314766423,
    1.592598203487462,
    -1.080652960128774,
    0.0,
    0.0,
    -0.00285961,
    0.7851361,
]  # placeholder


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box`` for the bridge (``low``, ``high``, ``shape``, ``dtype``).

    This class is not the backend; it is the space object the backend exposes. The bridge reads only those four
    attributes.
    """

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


def _initial_observation(rng):
    """A 48-value stand-in state. Every value is test data, not a device fact (``# placeholder``)."""

    qpos = [value + rng.uniform(-0.01, 0.01) for value in START_QPOS]       # placeholder: small seed jitter
    qvel = [0.0] * 11                                                       # placeholder
    gripper_target = [0.0, 0.0]                                            # placeholder
    base_pose = [0.35, 0.1, 0.079, 0.0, 0.0, 0.0, 1.0]                     # placeholder
    tcp_pose = [0.3, 0.0, 0.5, 0.0, 0.0, 0.0, 1.0]                         # placeholder
    obj_pose = [-0.23, 0.2, 0.887, 0.0, 0.0, 0.0, 1.0]                     # placeholder
    relative = [obj_pose[0] - tcp_pose[0], obj_pose[1] - tcp_pose[1],
                obj_pose[2] - tcp_pose[2]]                                  # placeholder
    return qpos + qvel + gripper_target + base_pose + tcp_pose + obj_pose + relative


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _rng_json(rng):
    # Explicit codec for Python Random state version 3: version, internal tuple, Gaussian cache.
    # https://github.com/python/cpython/blob/v3.14.0/Lib/random.py#L163-L171
    # Word count/index: Modules/_randommodule.c:81-82,383-455 at the same CPython tag.
    version, words, gaussian = rng.getstate()
    result = {"version": version, "words": list(words), "gaussian": gaussian}
    _rng_from_json(result)
    return result


def _rng_from_json(state):
    if type(state) is not dict or set(state) != {"version", "words", "gaussian"}:
        raise ValueError("invalid fake RNG checkpoint fields")
    if type(state["version"]) is not int or state["version"] != 3:
        raise ValueError("only Python Random state version 3 is supported")
    words = state["words"]
    if type(words) is not list or len(words) != 625:
        raise ValueError("fake RNG checkpoint needs 624 words and an index")
    if any(type(word) is not int or not 0 <= word < 2 ** 32 for word in words[:-1]):
        raise ValueError("fake RNG checkpoint word is invalid")
    if type(words[-1]) is not int or not 0 <= words[-1] <= 624:
        raise ValueError("fake RNG checkpoint index is invalid")
    gaussian = state["gaussian"]
    if gaussian is not None and not _finite(gaussian):
        raise ValueError("fake RNG Gaussian cache must be finite or null")
    candidate = random.Random(0)
    candidate.setstate((3, tuple(words), gaussian))
    return candidate


class FakeGraspSingleCokeCanEnv:
    """A stand-in for ``GraspSingleCokeCanInScene-v0`` with the bridge's Gymnasium surface."""

    def __init__(self, **kwargs):
        if kwargs:
            raise ValueError("the fake supports only the fixed default configuration")
        self.render_mode = None
        self._closed = False
        self.model_id = "coke_can"                                          # placeholder
        self.action_space = Box(ACTION_LOW, ACTION_HIGH)
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self._rng = random.Random(0)                                        # placeholder
        self._observation = _initial_observation(self._rng)
        self._tick = 0
        self._terminated = False
        self._truncated = False

    def reset(self, seed=None, options=None):
        self._check_open()
        if options:
            raise ValueError("the fake does not implement native reset options")
        if seed is not None:
            if type(seed) is not int or seed < 0:
                raise ValueError("seed must be a nonnegative integer")
            self._rng = random.Random(seed)
        self._tick = 0
        self._terminated = False
        self._truncated = False
        self._observation = _initial_observation(self._rng)
        info = {"model_id": self.model_id}                                  # placeholder: a subset of upstream info
        return list(self._observation), info

    def step(self, action):
        self._check_open()
        if self._terminated or self._truncated:
            raise ValueError("reset is required after episode termination")
        if not isinstance(action, (list, tuple)) or len(action) != len(ACTION_LOW):
            raise ValueError(f"the fake needs a {len(ACTION_LOW)}-element action, got {action!r}")
        if any(not _finite(value) or not low <= value <= high
               for value, low, high in zip(action, ACTION_LOW, ACTION_HIGH)):
            raise ValueError("action must contain finite values within the declared Box")
        values = [float(value) for value in action]
        # placeholder: a small kinematic effect so the step is observable; this is not upstream physics.
        for index in range(6):
            self._observation[index] = self._observation[index] + 0.01 * values[index]
        self._observation[22] = values[6]                                   # placeholder: gripper target
        self._observation[23] = values[6]                                   # placeholder: gripper target
        self._observation[31] = self._observation[31] + 0.001 * values[0]    # placeholder: tcp x
        self._observation[32] = self._observation[32] + 0.001 * values[1]    # placeholder: tcp y
        self._observation[33] = self._observation[33] + 0.001 * values[2]    # placeholder: tcp z
        self._observation[45] = self._observation[38] - self._observation[31]  # placeholder: relative x
        self._observation[46] = self._observation[39] - self._observation[32]  # placeholder: relative y
        self._observation[47] = self._observation[40] - self._observation[33]  # placeholder: relative z
        self._tick += 1
        self._terminated = False
        self._truncated = self._tick >= MAX_EPISODE_STEPS
        reward = 0.0                                                        # placeholder: the sparse reward
        info = {"elapsed_steps": self._tick, "success": False, "model_id": self.model_id}  # placeholder
        return list(self._observation), reward, self._terminated, self._truncated, info

    def _check_open(self):
        if self._closed:
            raise RuntimeError("fake environment is closed")

    def close(self):
        self._closed = True
        self._observation = None

    def get_state(self):
        """Finite JSON state of this fake only, including subsequent-reset RNG continuation."""
        self._check_open()
        return {
            "schema": "openmhs.simplerenv.fake.v1",
            "model_id": self.model_id,
            "observation": list(self._observation),
            "tick": self._tick,
            "terminated": self._terminated,
            "truncated": self._truncated,
            "rng": _rng_json(self._rng),
        }

    def set_state(self, state):
        self._check_open()
        required = {"schema", "model_id", "observation", "tick", "terminated", "truncated", "rng"}
        if type(state) is not dict or set(state) != required:
            raise ValueError("invalid fake checkpoint fields")
        if state["schema"] != "openmhs.simplerenv.fake.v1" or state["model_id"] != "coke_can":
            raise ValueError("checkpoint configuration does not match this fake")
        observation = state["observation"]
        if type(observation) is not list or len(observation) != OBSERVATION_SIZE or not all(
                _finite(value) for value in observation):
            raise ValueError("checkpoint observation must contain 48 finite numbers")
        tick = state["tick"]
        if type(tick) is not int or not 0 <= tick <= MAX_EPISODE_STEPS:
            raise ValueError("checkpoint tick is outside the fake episode")
        if type(state["terminated"]) is not bool or state["terminated"]:
            raise ValueError("this fake does not implement successful native task termination")
        if type(state["truncated"]) is not bool or state["truncated"] != (tick == MAX_EPISODE_STEPS):
            raise ValueError("checkpoint TimeLimit state contradicts its tick")
        rng = _rng_from_json(state["rng"])
        # Validate everything before committing; neither invalid data nor a failed
        # RNG codec may partly rewind observation, episode metadata or RNG state.
        self._observation = list(observation)
        self._tick = tick
        self._terminated = state["terminated"]
        self._truncated = state["truncated"]
        self._rng = rng
