"""Fake backend of the RoboDesk driver: a pure Python kinematic stand-in for ``robodesk.robodesk:RoboDesk``.

Why a fake: the upstream package needs ``dm_control``, ``gym``, ``numpy`` and ``PIL`` (setup.py:31-34) and does not
register a Gymnasium id, so the gate cannot make the environment; package code never imports the clone.  This module
implements only the public surface of the upstream class that the Gymnasium bridge touches (``reset``, ``step``,
``action_space``, ``observation_space``; gate G7) and duck-types the two gym spaces the bridge reads.  It does not
integrate the MuJoCo model: positions are moved directly and the reward is a constant placeholder.

Every numeric constant below is test data for the fake (a stand-in image size, an episode length, kinematic
scales, a start position and the canned reward), not a fact about the device; each definition is marked
``# placeholder``.  The values the upstream device uses are cited in driver.py facts with their file:line.

Differences from the upstream environment (all listed in the driver's fidelity ``gaps``):

* no MuJoCo, no contacts, no Franka Panda joints, no inverse kinematics and no rendering;
* the image is a 4 x 4 x 3 stand-in for the upstream 64 x 64 x 3 default;
* the reward is 0.0 (upstream computes a task reward clamped to [0, 1], robodesk/robodesk.py:375-378);
* the observation values are placeholders; the upstream defect that fills ``qpos_objects`` from ``qvel`` is
  mirrored (robodesk/robodesk.py:385);
* reset() takes no seed, as upstream does (robodesk/robodesk.py:207), so a reset seed is recorded by the bridge
  but does not control the fake.
"""

import random

IMAGE_SIZE = 4                        # placeholder: stand-in for the configurable image_size
EPISODE_LENGTH = 500                 # placeholder: stand-in for the upstream default time limit
ACTION_DIM = 5                       # placeholder: the five upstream end-effector inputs
NUM_JOINTS = 9                       # placeholder: the nine upstream robot joints
NUM_OBJECT_COORDS = 26               # placeholder: the upstream object state length
END_EFFECTOR_SCALE = 0.01            # placeholder: kinematic step of the fake
WRIST_SCALE = 0.02                   # placeholder: kinematic step of the fake
START_END_EFFECTOR = [0.0, 0.0, 0.6]  # placeholder: a fake start position


class Box:
    """Duck-typed ``gym.spaces.Box``: ``low``/``high``/``shape``/``dtype`` are what the bridge reads."""

    def __init__(self, low, high, shape=None, dtype="float32"):
        self.low = low
        self.high = high
        if shape is None:
            shape = (len(low),) if isinstance(low, (list, tuple)) else ()
        self.shape = tuple(shape)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gym.spaces.Dict``: the bridge reads ``spaces`` as a mapping of key to space."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeRoboDesk:
    """The RoboDesk environment surface without MuJoCo: ``reset()`` and ``step(action)`` return gymnasium-shaped data."""

    def __init__(self):
        self._action_space = Box([-1.0] * ACTION_DIM, [1.0] * ACTION_DIM)   # placeholder bounds
        self._observation_space = Dict({
            "image": Box(0, 255, (IMAGE_SIZE, IMAGE_SIZE, 3), "uint8"),
            "qpos_robot": Box([-float("inf")] * NUM_JOINTS, [float("inf")] * NUM_JOINTS),
            "qvel_robot": Box([-float("inf")] * NUM_JOINTS, [float("inf")] * NUM_JOINTS),
            "end_effector": Box([-float("inf")] * 3, [float("inf")] * 3),
            "qpos_objects": Box([-float("inf")] * NUM_OBJECT_COORDS, [float("inf")] * NUM_OBJECT_COORDS),
            "qvel_objects": Box([-float("inf")] * NUM_OBJECT_COORDS, [float("inf")] * NUM_OBJECT_COORDS),
        })
        self._rng = random.Random(0)     # placeholder seed: keeps the fake reproducible across fresh servers
        self._num_steps = 0
        self._tick = 0
        self._done = False
        self._end_effector = list(START_END_EFFECTOR)
        self._qpos_robot = [0.0] * NUM_JOINTS
        self._qvel_robot = [0.0] * NUM_JOINTS
        self._object_qvel = [0.0] * NUM_OBJECT_COORDS

    @property
    def action_space(self):
        return self._action_space

    @property
    def observation_space(self):
        return self._observation_space

    def reset(self):
        """Start a new episode: upstream reset() takes no arguments and randomizes the start state."""
        self._num_steps = 0
        self._tick = 0
        self._done = False
        self._end_effector = [START_END_EFFECTOR[0] + 0.05 * self._rng.random(),   # placeholder draw
                              START_END_EFFECTOR[1] + 0.05 * self._rng.random(),   # placeholder draw
                              START_END_EFFECTOR[2]]                                # placeholder value
        self._qpos_robot = [0.0] * NUM_JOINTS
        self._qpos_robot[0:3] = list(self._end_effector)
        self._qvel_robot = [0.0] * NUM_JOINTS
        self._object_qvel = [self._rng.uniform(-0.01, 0.01) for _ in range(NUM_OBJECT_COORDS)]  # placeholder
        return self._get_obs()

    def step(self, action):
        """Apply one five-value end-effector action and return (observation, reward, done, info)."""
        values = [float(value) for value in action]
        for index in range(3):
            self._end_effector[index] += END_EFFECTOR_SCALE * values[index]
        self._qpos_robot[0:3] = list(self._end_effector)
        self._qpos_robot[6] += WRIST_SCALE * values[3]
        self._qpos_robot[7] += WRIST_SCALE * values[4]
        self._qpos_robot[8] = self._qpos_robot[7]
        self._num_steps += 1
        self._tick += 1
        self._done = self._num_steps >= EPISODE_LENGTH     # placeholder time limit
        return self._get_obs(), 0.0, self._done, {"discount": 1.0}   # placeholder reward

    def _get_obs(self):
        image = []
        for y in range(IMAGE_SIZE):
            for x in range(IMAGE_SIZE):
                for channel in range(3):
                    image.append((self._tick * 7 + y * 11 + x * 13 + channel * 17) % 256)  # placeholder pattern
        return {
            "image": image,
            "qpos_robot": list(self._qpos_robot),
            "qvel_robot": list(self._qvel_robot),
            "end_effector": list(self._end_effector),
            # upstream fills qpos_objects from physics.data.qvel (robodesk/robodesk.py:385); mirrored here.
            "qpos_objects": list(self._object_qvel),
            "qvel_objects": list(self._object_qvel),
        }
