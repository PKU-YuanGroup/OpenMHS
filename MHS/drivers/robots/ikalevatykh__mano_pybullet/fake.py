"""Fake backend of the mano_pybullet driver: a pure Python stand-in for ``mano_pybullet.envs:HandLiftEnv``.

Why a fake: the upstream package needs gym, pybullet, numpy, chumpy, transforms3d and the MANO model files that
are downloaded separately (README.md:25-29, setup.py:36-43), and package code never imports the upstream clone.
This module re-implements the interface the bridge reads from the default ``HandLiftEnv``: the gym Tuple spaces of
``HandEnv`` in joint mode and the object part that ``HandObjectEnv`` appends, the reset/step/close members, and the
lift reward and termination rule of ``HandLiftEnv``.  The public members are the ones the upstream class has
(``reset``, ``step``, ``close``; gate G7).  Every numeric literal below is test data of the fake (marked
``# placeholder``); none is a Fact, a Limit or a reference.

What this is not: the upstream environment.  The fake is kinematic and runs no PyBullet: the object follows the
commanded hand base position, joint angles only shape the observation, there are no contacts, gravity, damping or
actuators, and the upstream constructor/model-loading path was not run.  The driver's fidelity ``gaps`` list these
differences.  Nothing here talks to a device.
"""

import math

# mano_pybullet/envs/hand_lift_env.py:11 (target_height default) and mano_pybullet/hand_model.py:122-123 (20 DOF)
TARGET_HEIGHT = 0.25                  # placeholder
JOINT_COUNT = 20                      # placeholder

# mano_pybullet/hand_model.py:166-182: HandModel20 joint limits in degrees, flattened in dofs_limits order.
JOINT_LOW_DEG = (-20, -10, 0, 0, -30, -10, 0, 0, -40, -10, 0, 0,
                 -30, -10, 0, 0, -10, -40, 0, 0)          # placeholder
JOINT_HIGH_DEG = (20, 90, 100, 100, 20, 90, 100, 100, 40, 90, 100, 100,
                  20, 90, 100, 100, 150, 40, 100, 100)    # placeholder

# mano_pybullet/envs/hand_env.py:144-146: the default right hand starts at (0, -0.10, 0.25).
HAND_POSITION = (0.0, -0.10, 0.25)     # placeholder
HAND_ORIENTATION = (0.0, 0.0, 0.0, 1.0)  # placeholder
OBJECT_POSITION = (0.0, 0.0, 0.0)      # placeholder


class Box:
    """Duck-typed ``gym.spaces.Box``: flat low/high lists, a shape and a dtype (the bridge reads those)."""

    def __init__(self, low, high):
        self.low = [float(item) for item in low]
        self.high = [float(item) for item in high]
        if len(self.low) != len(self.high):
            raise ValueError("Box low and high differ in length")
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Tuple:
    """Duck-typed ``gym.spaces.Tuple``: an ordered list of subspaces (the bridge reads ``spaces``)."""

    def __init__(self, spaces):
        self.spaces = list(spaces)
        self.shape = ()

    def __repr__(self):
        return f"Tuple({self.spaces!r})"


def _box(low, high, count):
    """A one-dimensional Box with ``count`` elements; the values are fake test data."""
    return Box([low] * count, [high] * count)


def _vector(value, count):
    """The value as ``count`` finite floats, or None when it is not that shape (a fake input guard)."""
    if not isinstance(value, (list, tuple)) or len(value) != count:
        return None
    out = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
            return None
        out.append(float(item))
    return out


class FakeHandLiftEnv:
    """HandLiftEnv without PyBullet: the default right hand, joint mode, and one object to lift."""

    def __init__(self, **_options):
        joint_low = [math.radians(item) for item in JOINT_LOW_DEG]
        joint_high = [math.radians(item) for item in JOINT_HIGH_DEG]
        # mano_pybullet/envs/hand_env.py:75-80 and 92-101: the default joint-mode action space.
        hand_action = Tuple((
            _box(-5.0, 5.0, 3),                      # placeholder: base position x,y,z
            _box(-1.0, 1.0, 4),                      # placeholder: base quaternion x,y,z,w
            Box(joint_low, joint_high),              # the HandModel20 joint limits
        ))
        self.action_space = Tuple([hand_action])
        # mano_pybullet/envs/hand_env.py:81-89 and mano_pybullet/envs/hand_object_env.py:32-37.
        hand_observation = Tuple((
            _box(-5.0, 5.0, 3),                      # placeholder: base position
            _box(-1.0, 1.0, 4),                      # placeholder: base quaternion
            _box(-10.0, 10.0, 6),                    # placeholder: constraint forces
            Box(joint_low, joint_high),              # joint angles
            _box(-3.0, 3.0, JOINT_COUNT),            # placeholder: joint velocities
            _box(-1.0, 1.0, JOINT_COUNT),            # placeholder: joint torques
        ))
        object_observation = Tuple((
            _box(-5.0, 5.0, 3),                      # placeholder: object position
            _box(-1.0, 1.0, 4),                      # placeholder: object quaternion
        ))
        self.observation_space = Tuple((Tuple([hand_observation]), object_observation))
        self._closed = False
        self._episode = 0
        self._reset_state()

    # -- gym.Env surface ---------------------------------------------------------
    def reset(self, seed=None, options=None, **_kwargs):
        """Start a new episode and return the initial observation (the upstream reset returns the observation)."""
        self._episode += 1
        self._reset_state()
        return self._observation()

    def step(self, action):
        """Apply one action, advance one environment step and return observation, reward, done, info."""
        self._apply(action)
        observation = self._observation()
        reward = float(observation[1][0][2])
        done = reward > self._target_height
        return observation, reward, done, {}

    def close(self):
        """Stop the fake environment (the upstream close disconnects the PyBullet client)."""
        self._closed = True

    # -- fake internals ----------------------------------------------------------
    def _reset_state(self):
        self._target_height = TARGET_HEIGHT
        self._hand_pos = list(HAND_POSITION)
        self._hand_orn = list(HAND_ORIENTATION)
        self._hand_angles = [0.0] * JOINT_COUNT
        self._object_pos = list(OBJECT_POSITION)
        self._object_orn = list(HAND_ORIENTATION)

    def _apply(self, action):
        """The object follows the first hand's base position; an unrecognised action is a no-op."""
        if not isinstance(action, (list, tuple)) or not action:
            return
        hand = action[0]
        if not isinstance(hand, (list, tuple)) or len(hand) != 3:
            return
        position = _vector(hand[0], 3)
        orientation = _vector(hand[1], 4)
        angles = _vector(hand[2], JOINT_COUNT)
        if position is None or orientation is None or angles is None:
            return
        self._hand_pos = position
        self._hand_orn = orientation
        self._hand_angles = angles
        self._object_pos = [position[0], position[1], max(0.0, position[2])]
        self._object_orn = list(orientation)

    def _observation(self):
        hand = (
            list(self._hand_pos),
            list(self._hand_orn),
            [0.0] * 6,
            list(self._hand_angles),
            [0.0] * JOINT_COUNT,
            [0.0] * JOINT_COUNT,
        )
        return [hand], (list(self._object_pos), list(self._object_orn))
