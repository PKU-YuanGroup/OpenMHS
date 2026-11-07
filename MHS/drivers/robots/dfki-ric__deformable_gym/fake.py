"""Fake backend of the deformable_gym driver: a pure Python stand-in for ``FloatingMiaGraspInsole-v0``.

Why a fake: the upstream package needs PyBullet, a deformable-body simulation, numpy and pytransform3d
(``pyproject.toml:25-30``), and package code never imports or runs the clone.  The acceptance gate therefore
serves the environment with this module, which re-implements the Gymnasium contract of
``deformable_gym.envs.floating_mia_grasp_env:FloatingMiaGraspEnv``: the two spaces, ``reset(seed, options)`` and
``step(action)``.  The public members are the ones the upstream class has through ``GraspEnv`` and
``BaseBulletEnv`` (``reset``, ``step``, ``close``; gate G7).

The spaces are the published ones of the registered ``FloatingMiaGraspInsole-v0`` environment (the registration
sets ``object_name`` and ``observable_object_pos=True``, ``deformable_gym/__init__.py:6-14``):

* the action is 10 values: 3 end-effector position offsets, 4 orientation offsets and 3 finger commands
  (``deformable_gym/envs/floating_mia_grasp_env.py:117-134``); the offset bounds are ``_MAX_POS_OFFSET`` and
  ``_MAX_ORN_OFFSET`` (``:65-66``), and the finger bounds are the motor limits selected by
  ``actuated_finger_ids = [0, 1, 5]`` (``:88-89``, ``:121``, ``:127``);
* the observation is 19 values with ``observable_object_pos=True``: end-effector position and quaternion (7),
  3 finger joint positions, 6 force readings and 3 object position values
  (``deformable_gym/envs/floating_mia_grasp_env.py:91-115`` and ``:162-174``).

What this is not, all repeated in the driver's fidelity ``gaps``:

* there is no PyBullet, no deformable object and no contact or force simulation; the finger positions are the
  commanded values, the force readings are zero and the object position does not move;
* the reward after the horizon is a placeholder, not the mesh-height test of
  ``deformable_gym/envs/grasp_env.py:60-79``;
* the initial end-effector pose and the joint-limit bounds come from the clone's text, but the trajectories were
  never compared with a real run of the upstream environment;
* there is no rendering.

Nothing here talks to a device.
"""

import math

# deformable_gym/envs/floating_mia_grasp_env.py:65-66
MAX_POS_OFFSET = 0.0005
MAX_ORN_OFFSET = 0.000005
# deformable_gym/robots/mia_hand.py:34-37 sets the index lower limit to 0.0; the upper limit is the URDF limit
# deformable_gym/assets/robots/urdf/mia_hand.urdf:312.
INDEX_LOW, INDEX_HIGH = 0.0, 1.399999976
# deformable_gym/assets/robots/urdf/mia_hand.urdf:326
LITTLE_LOW, LITTLE_HIGH = 0.0, 1.396260023
# deformable_gym/assets/robots/urdf/mia_hand.urdf:371
THUMB_OPP_LOW, THUMB_OPP_HIGH = -0.628, 0.0
# deformable_gym/envs/base_env.py:45 (the default ``horizon`` of BaseBulletEnv)
DEFAULT_HORIZON = 100
# deformable_gym/envs/floating_mia_grasp_env.py:37-39
INITIAL_POSITION = (0.03, -0.025, 1.0)
INITIAL_EULER = (-math.pi / 8.0, math.pi, 0.0)
#: The 3 finger commands use motor-array entries 0, 1 and 5 (floating_mia_grasp_env.py:88-89, :121-127); the fake
#: publishes the same limits rather than guessing the physical joint order.
FINGER_LOW = [INDEX_LOW, LITTLE_LOW, THUMB_OPP_LOW]
FINGER_HIGH = [INDEX_HIGH, LITTLE_HIGH, THUMB_OPP_HIGH]


def _quaternion_from_euler(roll, pitch, yaw):
    """The quaternion ``pybullet.getQuaternionFromEuler((roll, pitch, yaw))`` returns."""
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return [
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    ]


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: one lower and one upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float64"

    def contains(self, value):
        return (len(value) == len(self.low)
                and all(low <= item <= high for item, low, high in zip(value, self.low, self.high)))


class FakeFloatingMiaGraspEnv:
    """``FloatingMiaGraspEnv`` without PyBullet: the same spaces and the same reset/step tuple shape."""

    def __init__(self, horizon=DEFAULT_HORIZON, **_options):
        self._horizon = int(horizon)                                        # base_env.py:45
        self.action_space = Box(
            [-MAX_POS_OFFSET] * 3 + [-MAX_ORN_OFFSET] * 4 + FINGER_LOW,     # floating_mia_grasp_env.py:117-134
            [MAX_POS_OFFSET] * 3 + [MAX_ORN_OFFSET] * 4 + FINGER_HIGH,
        )
        self.observation_space = Box(
            [-2.0, -2.0, 0.0] + [-1.0] * 4 + FINGER_LOW + [-10.0] * 6 + [-2.0] * 3,   # :91-115
            [2.0, 2.0, 2.0] + [1.0] * 4 + FINGER_HIGH + [10.0] * 6 + [2.0] * 3,
        )
        self._position = list(INITIAL_POSITION)
        self._orientation = _quaternion_from_euler(*INITIAL_EULER)
        self._joints = [0.0, 0.0, 0.0]
        self._forces = [0.0] * 6                                           # placeholder: no force simulation
        self._object_position = [0.0, 0.0, 0.0]                            # placeholder: the object does not move
        self._step_counter = 0
        self._seed = None

    def _observation(self):
        return (list(self._position) + list(self._orientation) + list(self._joints)
                + list(self._forces) + list(self._object_position))

    def reset(self, seed=None, options=None):
        """Reset the episode; ``options`` accepts the upstream ``hard_reset`` key (base_env.py:104-105)."""
        options = options or {}
        if not isinstance(options, dict):
            raise TypeError("options must be a mapping")
        self._seed = seed
        self._position = list(INITIAL_POSITION)
        self._orientation = _quaternion_from_euler(*INITIAL_EULER)
        self._joints = [0.0, 0.0, 0.0]
        self._forces = [0.0] * 6                                           # placeholder
        self._object_position = [0.0, 0.0, 0.0]                            # placeholder
        self._step_counter = 0
        return self._observation(), {}

    def step(self, action):
        """Apply one action; the episode terminates at ``horizon`` steps (base_env.py:171)."""
        if len(action) != 10:
            raise ValueError(f"expected a 10-value action, got {len(action)} values")
        self._position = [value + offset for value, offset in zip(self._position, action[:3])]
        self._joints = list(action[7:10])
        self._step_counter += 1
        terminated = self._step_counter >= self._horizon
        # placeholder reward: the upstream reward is the released object's mesh-height test (grasp_env.py:60-79),
        # which this fake does not model.
        reward = -1.0 if terminated else 0.0
        return self._observation(), reward, bool(terminated), False, {}

    def close(self):
        self._step_counter = 0
