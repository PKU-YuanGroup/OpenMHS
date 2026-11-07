"""Fake backend of the DexPoint driver: a pure-Python kinematic stand-in for ``AllegroRelocateRLEnv``.

Why a fake: the gate runs without SAPIEN (the upstream package pins ``sapien==2.1.0``, ``setup.py:23``), package code
never imports or runs the clone, and the clone does not carry the ``day.ktx`` scene file or the ShapeNet/EGAD assets
its README downloads.  This module mirrors the public interface the gymnasium bridge uses (``reset``, ``step``,
``seed`` and, because the upstream class has it, ``is_done``) and the two spaces the bridge derives its contract from.

What it models (fidelity F0 of the driver): the shape of the oracle state at ``relocate_env.py:87-91``, the action
space at ``base.py:400-402`` (one element per degree of freedom of the default robot, 6 + 16 at
``common_robot_utils.py:53-56``), the reset draws at ``sim_env/relocate_env.py:81-100`` and the horizon at
``relocate_env.py:155-157``.  It does not model SAPIEN, contacts, friction, actuators or lift: the object and target
stay at their reset poses, the first three action values move a palm position, and the last sixteen are recorded as
qpos.  Every geometry constant below is a placeholder for the stand-in, not a measurement of the device or a Fact.

The initial object and target poses use Python's ``random.Random``; upstream draws them with numpy's generator, so a
seed gives different poses on the two.  Nothing here talks to a device.
"""

import math
import random

# The default robot allegro_hand_xarm6_wrist_mounted_face_front declares hand_dof 16 and arm_dof 6
# (common_robot_utils.py:53-56); action_dim is robot.dof (base.py:78-80) and the action space is Box(-1, 1) with
# that many elements (base.py:400-402).
DOF = 6 + 16
# get_oracle_state concatenates robot qpos (dof), palm position (3), object pose (7), object-in-tip (4 x 3 = 12),
# contact flags (5), target-in-object (3), target quaternion (4) and target angle (1) (relocate_env.py:87-91).
OBS_DIM = DOF + 3 + 7 + 12 + 5 + 3 + 4 + 1
# relocate_env.py:155-157
HORIZON = 200
# relocate_env.py:13
OBJECT_LIFT_LOWER_LIMIT = -0.03
# relocate_env.py:52-53: the thumb weight 0.04 and the other three tips 0.01
FINGER_REWARD_SCALE = [0.04, 0.01, 0.01, 0.01]
# Placeholders of the stand-in: they are test data, not device facts.
OBJECT_HEIGHT = 0.04                             # placeholder
PALM_START = [0.0, 0.0, 0.10]                    # placeholder
TIP_OFFSETS = [(0.03, 0.0, -0.03), (-0.03, 0.0, -0.03),
               (0.0, 0.03, -0.03), (0.0, -0.03, -0.03)]  # placeholder
CONTACT_RADIUS = 0.05                            # placeholder
ARM_STEP = 0.01                                  # placeholder
OBJECT_QUAT = [1.0, 0.0, 0.0, 0.0]               # placeholder (upstream uses YCB_ORIENTATION[object_name])
TARGET_QUAT = [1.0, 0.0, 0.0, 0.0]               # placeholder (no orientation randomness upstream)


class Box:
    """Duck-typed ``gym.spaces.Box``: flattened ``low``/``high`` bounds, a ``shape`` and a ``dtype``."""

    def __init__(self, low, high, shape, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype


def _norm(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def _clip(value, low, high):
    return low if value < low else high if value > high else value


class FakeAllegroRelocateRLEnv:
    """The upstream environment's interface with a kinematic state, without SAPIEN or numpy.

    ``reset``, ``step``, ``seed`` and ``is_done`` have the upstream names; the bridge only calls the first three.
    """

    def __init__(self, use_gui=False, frame_skip=10, robot_name="allegro_hand_xarm6_wrist_mounted_face_front",
                 rotation_reward_weight=0, object_category="YCB", object_name="tomato_soup_can",
                 randomness_scale=1, friction=1, root_frame="robot", **renderer_kwargs):
        # The fake has no renderer, so it deploys the headless configuration the upstream example uses
        # (example/example_use_state_only_env.py:14-22); the values are kept so the interface matches.
        self.use_gui = use_gui
        self.frame_skip = frame_skip
        self.robot_name = robot_name
        self.rotation_reward_weight = rotation_reward_weight
        self.object_category = object_category
        self.object_name = object_name
        self.randomness_scale = randomness_scale
        self.friction = friction
        self.root_frame = root_frame
        self.action_space = Box([-1.0] * DOF, [1.0] * DOF, (DOF,))
        self.observation_space = Box([-math.inf] * OBS_DIM, [math.inf] * OBS_DIM, (OBS_DIM,))
        self.current_step = 0
        self.object_lift = 0.0
        self._qpos = [0.0] * DOF
        self._palm = list(PALM_START)
        self._object_pos = [0.0, 0.0, OBJECT_HEIGHT]
        self._target_pos = [0.0, 0.0, 0.25]
        self._rng = random.Random()
        self.seed()

    def seed(self, seed=None):
        """``BaseSimulationEnv.seed`` (sim_env/base.py:58-60): install the generator and return ``[seed]``."""
        self._rng = random.Random(seed)
        return [seed]

    def reset(self, *, seed=None, return_info=False, options=None):
        """``AllegroRelocateRLEnv.reset`` (relocate_env.py:124-150) without the SAPIEN scene.

        ``return_info`` and ``options`` are accepted because the upstream signature has them; upstream ignores both.
        """
        if seed is not None:
            self.seed(seed)
        self.current_step = 0
        self.object_lift = 0.0
        self._qpos = [0.0] * DOF
        self._palm = list(PALM_START)
        # The same two draws as generate_random_object_pose then generate_random_target_pose
        # (sim_env/relocate_env.py:81-100), with Python's generator instead of numpy's.
        self._object_pos = [self._rng.uniform(-0.1, 0.1) * self.randomness_scale,
                            self._rng.uniform(-0.1, 0.1) * self.randomness_scale,
                            OBJECT_HEIGHT]
        self._target_pos = [self._rng.uniform(-0.2, 0.2) * self.randomness_scale,
                            self._rng.uniform(-0.2, 0.2) * self.randomness_scale,
                            0.25]
        return self._observation()

    def step(self, action):
        """``BaseRLEnv.step`` (base.py:204-217) with the legacy ``(obs, reward, done, info)`` result."""
        if len(action) != DOF:
            raise ValueError(f"the action has {len(action)} values; the upstream robot has {DOF} degrees of freedom")
        # base.py:144 clips every action value to [-1, 1].
        clipped = [_clip(float(value), -1.0, 1.0) for value in action]
        # Placeholder kinematics: the first three values move the palm, the last sixteen are recorded as hand qpos.
        self._palm = [self._palm[i] + ARM_STEP * clipped[i] for i in range(3)]
        self._qpos[6:] = clipped[6:]
        self.current_step += 1
        observation = self._observation()
        reward = self._reward()
        done = self.is_done()
        info = {}
        # base.py:214-216: the horizon ends the episode and reports a time-limit truncation.
        if self.current_step >= HORIZON:
            info["TimeLimit.truncated"] = not done
            done = True
        return observation, reward, done, info

    def is_done(self):
        """``AllegroRelocateRLEnv.is_done`` (relocate_env.py:152-153); the stand-in never lowers the object."""
        return self.object_lift < OBJECT_LIFT_LOWER_LIMIT

    def _tip_positions(self):
        """Placeholder fingertip positions: fixed offsets from the palm (upstream reads SAPIEN link poses)."""
        return [[self._palm[0] + dx, self._palm[1] + dy, self._palm[2] + dz] for dx, dy, dz in TIP_OFFSETS]

    def _observation(self):
        tips = self._tip_positions()
        object_pose_vec = list(self._object_pos) + list(OBJECT_QUAT)
        object_in_tip = [self._object_pos[i] - tip[i] for tip in tips for i in range(3)]
        contact = [1.0 if _norm(tip, self._object_pos) <= CONTACT_RADIUS else 0.0 for tip in tips]
        contact.append(1.0 if _norm(self._palm, self._object_pos) <= CONTACT_RADIUS else 0.0)
        target_in_object = [self._target_pos[i] - self._object_pos[i] for i in range(3)]
        # relocate_env.py:79-80: the angle between the object and target quaternions.
        dot = sum(OBJECT_QUAT[i] * TARGET_QUAT[i] for i in range(4))
        angle = math.acos(_clip(dot * dot * 2.0 - 1.0, -1.0 + 1e-8, 1.0 - 1e-8))
        return (list(self._qpos) + list(self._palm) + object_pose_vec + object_in_tip + contact
                + target_in_object + list(TARGET_QUAT) + [angle])

    def _reward(self):
        """The reachable part of ``AllegroRelocateRLEnv.get_reward`` (relocate_env.py:100-122)."""
        tips = self._tip_positions()
        distances = [_clip(_norm(self._object_pos, tip), 0.03, 0.8) for tip in tips]
        reward = sum(1.0 / (0.06 + distances[i]) * FINGER_REWARD_SCALE[i] for i in range(len(tips)))
        contact = [1.0 if _norm(tip, self._object_pos) <= CONTACT_RADIUS else 0.0 for tip in tips]
        contact.append(1.0 if _norm(self._palm, self._object_pos) <= CONTACT_RADIUS else 0.0)
        if sum(contact) >= 2:
            reward += 0.5
        # The stand-in keeps the object at its reset pose, so object_lift stays 0 and the lift, target and
        # rotation terms of relocate_env.py:109-118 cannot trigger; qvel and cartesian_error are not modelled.
        return reward / 10.0
