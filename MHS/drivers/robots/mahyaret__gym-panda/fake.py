"""Fake backend of the gym-panda driver: a pure Python kinematic stand-in for ``gym_panda.envs:PandaEnv``.

The upstream environment drives a Franka Emika Panda in PyBullet: it solves inverse kinematics for link 11,
commands the seven arm joints and the two finger joints, calls ``stepSimulation`` once per action and reads the
hand and finger state back (``gym_panda/envs/panda_env.py:34-47``).  The acceptance gate runs without gym,
pybullet or numpy (the upstream imports them at ``panda_env.py:1-10``), and package code never imports the clone,
so this module models the same interface without a physics engine.

Every rule below is the one the upstream code states, with its line:

* the action is four numbers between -1 and 1 (``panda_env.py:22``); the first three scale the hand target by
  0.005 per step (``panda_env.py:28-31``) and the fourth is the position target of both finger joints
  (``panda_env.py:32,41``);
* the episode ends with reward 1 when the object is above z = 0.45 (``panda_env.py:51-56``), or with reward 0
  after more than ``MAX_EPISODE_LEN`` steps (``panda_env.py:13,58-62``);
* a reset draws the object start uniformly in x 0.5 to 0.8 and y -0.2 to 0.2 at z = 0.05
  (``panda_env.py:87-88``).

The parts this module does not reproduce (all disclosed in the driver's fidelity gaps):

* no PyBullet, URDF, inverse kinematics, contacts, joint limits, gravity or motor dynamics: the hand position is
  integrated directly from the action and the finger joints take the commanded value;
* the hand start pose and the grasp rule are placeholders, not the pose PyBullet computes from the rest poses
  (``panda_env.py:77-82``);
* there is no renderer; the bridge binds no render capability.

The public members are the ones ``PandaEnv`` has (``reset``, ``step``, ``close``; gate G7).  ``Box`` duck-types a
one-dimensional ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``.  Every value in
this module is test data, never a fact or a safety limit of a device.
"""

import math
import random

# panda_env.py:13
MAX_EPISODE_LEN = 20 * 100
# panda_env.py:28
DV = 0.005
# panda_env.py:51
REWARD_Z = 0.45
# panda_env.py:87
OBJECT_X = (0.5, 0.8)
OBJECT_Y = (-0.2, 0.2)
OBJECT_Z = 0.05
# panda_env.py:77-82: the rest pose puts both fingers at 0.08
FINGER_REST = 0.08
# placeholder: PyBullet computes the hand pose from the URDF and the rest poses; this stand-in starts the hand
# at a fixed pose near the object instead.
START_HAND = (0.65, 0.0, 0.1)
# placeholder: the stand-in's grasp test (distance in metres) and the finger command that closes the gripper.
GRASP_RADIUS = 0.08
FINGER_CLOSED = 0.0


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakePandaEnv:
    """PandaEnv without PyBullet: ``reset()`` and ``step(action)`` follow the rules cited above."""

    def __init__(self, **_options):
        # panda_env.py:22-23
        self.action_space = Box([-1.0] * 4, [1.0] * 4)
        self.observation_space = Box([-1.0] * 5, [1.0] * 5)
        self.metadata = {"render.modes": ["human"]}                      # panda_env.py:16
        self.step_counter = 0
        self.observation = None
        self._rng = random.Random()
        self._hand = list(START_HAND)
        self._fingers = (FINGER_REST, FINGER_REST)
        self._object = None
        self._offset = None
        self._grasped = False

    def reset(self, seed=None, options=None):
        """Start a new episode; ``seed`` and ``options`` are fake-only extensions of the bridge contract.

        Upstream ``PandaEnv.reset()`` takes no arguments and draws the object start with the global random
        module (``panda_env.py:87``); the fake accepts a seed so ``cap.world.reset.v1`` can be exercised
        reproducibly, and ignores ``options``.
        """
        if seed is not None:
            self._rng = random.Random(int(seed))
        self.step_counter = 0
        self._hand = list(START_HAND)                                    # placeholder
        self._fingers = (FINGER_REST, FINGER_REST)
        # panda_env.py:87-88
        self._object = [self._rng.uniform(*OBJECT_X), self._rng.uniform(*OBJECT_Y), OBJECT_Z]
        self._offset = None
        self._grasped = False
        self.observation = list(self._hand) + list(self._fingers)        # panda_env.py:89-91
        return list(self.observation)

    def step(self, action):
        """Advance one transition with the four-number action ``[dx, dy, dz, fingers]``."""
        # panda_env.py:29-32
        self._hand[0] += action[0] * DV
        self._hand[1] += action[1] * DV
        self._hand[2] += action[2] * DV
        self._fingers = (action[3], action[3])

        if not self._grasped:
            distance = math.sqrt(sum((self._hand[i] - self._object[i]) ** 2 for i in range(3)))
            if action[3] <= FINGER_CLOSED and distance <= GRASP_RADIUS:  # placeholder grasp rule
                self._grasped = True
                self._offset = [self._object[i] - self._hand[i] for i in range(3)]
        elif action[3] > FINGER_CLOSED:
            self._grasped = False
        if self._grasped:
            self._object = [self._hand[i] + self._offset[i] for i in range(3)]

        # panda_env.py:51-56
        if self._object[2] > REWARD_Z:
            reward, done = 1.0, True
        else:
            reward, done = 0.0, False

        self.step_counter += 1
        # panda_env.py:58-62
        if self.step_counter > MAX_EPISODE_LEN:
            reward, done = 0.0, True

        info = {"object_position": list(self._object)}                   # panda_env.py:64
        self.observation = list(self._hand) + list(self._fingers)        # panda_env.py:65-66
        return list(self.observation), reward, done, info

    def close(self):
        """The upstream client disconnects (``panda_env.py:121-122``); the fake only drops its state."""
        self.observation = None
