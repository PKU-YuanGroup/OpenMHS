"""Fake backend for the Space Robotics Bench Gymnasium driver.

The gate cannot import the upstream package (it needs Python 3.11, NVIDIA Omniverse and Isaac Sim: ``srb/__main__.py``
lines 37-40 and README.md line 7 of the clone), so this module is a small, pure Python stand-in for the single
environment part of ``srb.tasks.manipulation._manipulation.task:Task`` (the template class at
``srb/tasks/manipulation/_manipulation/task.py:53``).  The upstream class is an Isaac Lab ``DirectRLEnv``
(``srb/core/env/common/base/direct/impl.py:27``): its Gymnasium spaces are a Box action space
(``srb/core/env/common/base/direct/impl.py:353-357``) and a Dict observation grouped as ``state``, ``state_dyn``,
``proprio`` and ``proprio_dyn`` (``srb/tasks/manipulation/_manipulation/task.py:235-253``).

The fake keeps a kinematic joint vector so the contract has an observable state, and it records the seed.  It does
not model rigid-body dynamics, contacts, actuators, sensors or noise; the driver's fidelity contract says so and is
F0.  The numbers marked ``# placeholder`` below are test data only; none is copied into a Fact, a Limit or the
reference.  The action Box copies the upstream space: low -1.0, high 1.0 per element
(``srb/core/env/common/base/direct/impl.py:353-357``), with the seven elements that the action manager's
``total_action_dim`` (``srb/core/env/common/base/direct/impl.py:356``) has in the default configuration, the Franka's
six-value relative pose command and the one value of its hand's binary gripper command.
"""

import math
import random

# The upstream width is action_manager.total_action_dim (srb/core/env/common/base/direct/impl.py:356), summed by Isaac
# Lab over the action terms that srb/core/env/common/base/env_cfg.py:557-576 and 761-778 collect from the robot and
# from an active-tool end effector.  The default Franka (srb/core/env/manipulation/env.py:68) brings its relative pose
# command (srb/assets/robot/manipulation/franka.py:91-106), which takes the whole six-value twist
# (srb/core/action/group/manipulation/task_space.py:17-22), and its FrankaHand (franka.py:89) a binary gripper command
# (srb/assets/object/tool/franka_hand.py:53-61) of one value (srb/core/action/group/common/joint.py:51-52).
POSE_ACTION_DIM = 6
GRIPPER_ACTION_DIM = 1
ACTION_DIM = POSE_ACTION_DIM + GRIPPER_ACTION_DIM
# placeholder: the arm's joint count in the observation.  It mirrors a seven-joint arm
# (srb/assets/robot/manipulation/franka.py:95), not a measured device size.
JOINT_COUNT = 7
# placeholder: two hand joints, the left and the right finger of franka_hand.usdz that panda_finger_joint.* names
# (srb/assets/object/tool/franka_hand.py:40-59); that binary USD defines the joints, so no text line counts them.
HAND_JOINT_COUNT = 2
# srb/assets/object/tool/franka_hand.py:58-59: the close and the open command of the binary gripper action; the
# fingers start open (franka_hand.py:40).
HAND_CLOSED, HAND_OPEN = 0.0, 0.04
# placeholder: episode length in agent steps, derived from episode_length_s 10.0 at agent_rate 1/50
# (srb/tasks/manipulation/_manipulation/task.py:41 and srb/core/env/manipulation/env.py:80); the upstream value is
# computed by Isaac Lab from the cfg (srb/core/env/common/base/env_cfg.py:172-173).
MAX_EPISODE_STEPS = 500
# srb/tasks/manipulation/_manipulation/task.py:193: WEIGHT_ACTION_RATE = -0.5
WEIGHT_ACTION_RATE = -0.5
# placeholder: how far one unit of an action moves a joint in this fake; the upstream applies the configured
# action terms and Isaac Sim physics, so this gain is not a device number.
JOINT_GAIN = 0.1
# placeholder: the scale that turns the fake's raw joints into the normalized observation.
JOINT_NORMALIZATION = 3.0
# placeholder: the fake's constant 3D end-effector position and its identity rotation in the 6D representation that
# srb/tasks/manipulation/_manipulation/task.py:173-174 builds.
TCP_POSITION = (0.4, 0.0, 0.4)
TCP_ROTATION_6D = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a low and a high bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _unbounded(size):
    return Box([-math.inf] * size, [math.inf] * size)


def _flatten(groups):
    """One vector per group, its members concatenated in sorted name order: the upstream ``_flatten_observations``
    (``srb/core/env/common/base/direct/impl.py:543-556``), which ``_get_observations`` applies (``:454-458``)."""
    return {group: [value for name in sorted(members) for value in members[name]] for group, members in groups.items()}


class FakeSpaceRoboticsBenchEnv:
    """A kinematic stand-in for ``srb.tasks.manipulation._manipulation.task:Task``.

    ``reset``, ``step`` and ``close`` are the public methods of the upstream class that the Gymnasium bridge calls.
    ``close`` is defined by the upstream base (``srb/core/env/common/base/direct/impl.py:136``); ``reset`` and
    ``step`` come from Isaac Lab's ``DirectRLEnv`` outside the clone (``srb/core/env/common/base/direct/impl.py:7``),
    which the gate reports as an external base.  The observation returns two of the four upstream groups, each one
    vector as the upstream flattens them (``srb/core/env/common/base/direct/impl.py:543-556``); the contact groups are
    not modelled, and the driver's fidelity gaps say so.
    """

    def __init__(self, **_options):
        self.action_space = Box([-1.0] * ACTION_DIM, [1.0] * ACTION_DIM)
        self._rng = random.Random()
        self._joints = [0.0] * JOINT_COUNT          # placeholder: the reset state is drawn below
        self._hand = [HAND_OPEN] * HAND_JOINT_COUNT
        self._previous_action = [0.0] * ACTION_DIM  # placeholder
        self._tick = 0
        self._episode = 0
        # srb/core/env/common/base/direct/impl.py:362-423 builds the observation space from one observation, a Box per
        # group as long as its vector; placeholder: unbounded, where the upstream bounds a Box by its dtype's range
        # (:396-417).
        self.observation_space = Dict({group: _unbounded(len(values)) for group, values in self._observation().items()})

    def _observation(self):
        normalized = [value / JOINT_NORMALIZATION for value in self._joints]  # placeholder normalization
        # srb/tasks/manipulation/_manipulation/task.py:157-170 scales the hand joints to -1..1 between their soft
        # limits, which franka_hand.usdz holds; placeholder: this fake takes the close and the open command as those
        # limits, so an open hand reads 1.0 and a closed one -1.0.
        offset = (HAND_CLOSED + HAND_OPEN) * 0.5
        hand = [2.0 * (value - offset) / (HAND_OPEN - HAND_CLOSED) for value in self._hand]
        # The members of srb/tasks/manipulation/_manipulation/task.py:245-252; sorted by name, the hand's joints come
        # before the arm's.
        return _flatten({
            "proprio": {
                "fk_pos_end_effector": list(TCP_POSITION),
                "fk_rot6d_end_effector": list(TCP_ROTATION_6D),
            },
            "proprio_dyn": {
                "joint_pos_robot_normalized": normalized,
                "joint_pos_end_effector_normalized": hand,
            },
        })

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        # srb/core/env/manipulation/env.py:54-61 resets the robot joints with a uniform offset in
        # (-deg_to_rad(5.0), deg_to_rad(5.0)); placeholder: this fake draws the same offset around zero.
        self._joints = [self._rng.uniform(-math.radians(5.0), math.radians(5.0)) for _ in range(JOINT_COUNT)]
        # srb/core/env/common/base/event_cfg.py:30-34 resets every articulation to its default joints
        # (srb/core/mdp/events.py:60-82), so the hand starts open again.
        self._hand = [HAND_OPEN] * HAND_JOINT_COUNT
        self._previous_action = [0.0] * ACTION_DIM  # placeholder
        self._tick = 0
        self._episode += 1
        return self._observation(), {}

    def step(self, action):
        values = [float(value) for value in action]
        if len(values) != ACTION_DIM:
            raise ValueError(f"the fake expects {ACTION_DIM} action values, got {len(values)}")
        # placeholder: a kinematic update by the pose values; the fake has no dynamics to integrate and solves no
        # inverse kinematics.
        for index in range(min(JOINT_COUNT, POSE_ACTION_DIM)):
            self._joints[index] += values[index] * JOINT_GAIN
        # A negative gripper value selects the close command and any other value the open one (Isaac Lab's
        # BinaryJointAction, outside the clone; srb/assets/object/tool/franka_hand.py:54-61).  placeholder: the fake
        # sets the fingers to the command at once, where the upstream actuator drives them (franka_hand.py:42-50).
        target = HAND_CLOSED if values[POSE_ACTION_DIM] < 0 else HAND_OPEN
        self._hand = [target] * HAND_JOINT_COUNT
        # srb/tasks/manipulation/_manipulation/task.py:192-196: the action-rate penalty only.  The other three
        # reward terms need joint torque, acceleration and contact forces that this kinematic fake does not model.
        squared = [(value - previous) ** 2 for value, previous in zip(values, self._previous_action)]
        reward = WEIGHT_ACTION_RATE * (math.fsum(squared) / len(squared))
        self._previous_action = values
        self._tick += 1
        # srb/tasks/manipulation/_manipulation/task.py:226-233: no termination; truncation at max_episode_length.
        terminated = False
        truncated = self._tick >= MAX_EPISODE_STEPS
        return self._observation(), reward, terminated, truncated, {"tick": self._tick}

    def close(self):
        """Nothing to release: the fake owns no simulator or device handle."""
        return None
