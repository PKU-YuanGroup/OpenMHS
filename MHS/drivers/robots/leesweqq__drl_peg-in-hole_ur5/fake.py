"""Fake backend of the Gymnasium driver: a pure Python kinematic stand-in for ``rlenv:PegInHoleGymEnv``.

Why a fake: the acceptance gate runs without pybullet, and package code never imports the clone.  The upstream
environment connects a PyBullet GUI client, loads UR5 and box URDF files from the clone and renders a 100x100 image
through OpenGL (rlenv.py:16, 59-62, 193-238).  This module re-implements only the interface the Gymnasium bridge calls:
``reset(seed=None, options=None)`` (rlenv.py:97), ``step(action)`` (rlenv.py:142) and ``close()`` (rlenv.py:267), with
the action-space bounds of rlenv.py:43, the hole draw of rlenv.py:110-114, the reward of rlenv.py:240-251, the
insertion threshold of rlenv.py:257-262, the 500-step limit of rlenv.py:25 and the five-tuple of rlenv.py:177.  The
public members are the ones ``PegInHoleGymEnv`` has (``reset``, ``step``, ``close``; gate G7), and the two space
classes duck-type ``gymnasium.spaces.Dict`` and ``Box`` (the bridge reads ``spaces``, ``low``, ``high``, ``shape``).

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* the end effector moves by the action offset in a straight line; there is no inverse kinematics, joint limit,
  gravity, contact or table/hole geometry, so the upstream collision termination (rlenv.py:179-191) is absent;
* the camera image is a synthetic field with the hole and the end effector projected to pixels, not an OpenGL
  render from the camera link;
* the target is drawn from this class's ``random.Random``; upstream draws from the module-level ``random``
  generator and ignores the reset seed, so a seed does not give the same trajectory on the two;
* there is no wall-clock time, no PyBullet timestep and no snapshot API.

Nothing here talks to a device.
"""

import math
import random

# rlenv.py:22-23
IMAGE_WIDTH = 100
IMAGE_HEIGHT = 100
# rlenv.py:25
MAX_STEPS = 500
# rlenv.py:43
ACTION_LOW = -0.005
ACTION_HIGH = 0.005
# rlenv.py:110-114: the hole is drawn in this workspace box and sits at this height
TARGET_X_RANGE = (0.5, 0.6)
TARGET_Y_RANGE = (0.0, 0.1)
TARGET_Z = 0.65
# rlenv.py:257-262
INSERT_XY = 0.01
INSERT_Z = 0.1
# rlenv.py:240-251
REWARD_SCALE = 10.0
REWARD_Z_WEIGHT = 0.5
INSERT_REWARD = 100.0
# placeholder: the fake end-effector start pose (the upstream rest pose is not published as a number in the clone)
START_POS = [0.55, 0.05, 0.8]
# placeholder: pixel values of the synthetic image (the upstream camera image is rendered by OpenGL)
TARGET_PIXEL = 255
EEF_PIXEL = 128


def _flat(value, count):
    """``count`` numbers from a scalar, a flat sequence or a nested sequence (a gymnasium Box broadcast)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [float(value)] * count
    out = []

    def walk(item):
        if isinstance(item, (list, tuple)):
            for element in item:
                walk(element)
        else:
            out.append(float(item))

    walk(value)
    if len(out) != count:
        raise ValueError(f"a Box bound of {len(out)} values cannot fill {count} elements")
    return out


def _count(shape):
    total = 1
    for item in shape:
        total *= int(item)
    return total


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: ``low``, ``high``, ``shape`` and ``dtype`` as the bridge reads them."""

    def __init__(self, low, high, shape, dtype="float32"):
        self.shape = tuple(int(item) for item in shape)
        count = _count(self.shape)
        self.low = _flat(low, count)
        self.high = _flat(high, count)
        self.dtype = dtype

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.low):
            return False
        return all(lo <= float(item) <= hi for item, lo, hi in zip(value, self.low, self.high))


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = None


class FakePegInHoleEnv:
    """The peg-in-hole environment without pybullet: ``reset`` and ``step`` return what ``PegInHoleGymEnv`` returns."""

    def __init__(self):
        # rlenv.py:22-25
        self.image_width = IMAGE_WIDTH
        self.image_height = IMAGE_HEIGHT
        self.max_steps = MAX_STEPS
        self.step_count = 0
        # rlenv.py:63
        self.eef_link_index = 6
        # rlenv.py:89-90
        self.arm_joints = [0, 1, 2, 3, 4, 5]          # placeholder: six arm joints
        self.rest_poses = [0, -1.57, 1.57, -1.5, -1.57, 0.0]
        # rlenv.py:33-40 (the same 100x100x1 uint8 image space)
        self.observation_space = Dict({
            "cam_image": Box(low=0, high=255, shape=(self.image_height, self.image_width, 1), dtype="uint8"),
        })
        # rlenv.py:43
        self.action_space = Box(low=ACTION_LOW, high=ACTION_HIGH, shape=(3,), dtype="float32")
        # placeholder: the client and body ids the upstream constructor creates (rlenv.py:16, 57, 61, 115)
        self.physics_client = 0
        self.robot_id = 0
        self.table_id = 1
        self.hole_id = None
        self.camera_link_index = -1                    # rlenv.py:195
        self.target_pos = [0.0, 0.0, TARGET_Z]         # placeholder: overwritten by reset
        self.eef_pos = list(START_POS)
        self._rng = random.Random()
        self.reset()

    # -- the Gymnasium surface (rlenv.py:97, 142, 267) -------------------------
    def reset(self, seed=None, options=None):
        """``PegInHoleGymEnv.reset`` without the PyBullet calls; ``seed`` is this fake's own extension."""
        self.step_count = 0
        if seed is not None:
            self._rng.seed(int(seed))
        if self.hole_id is not None:
            self.hole_id = None
        x = self._rng.uniform(*TARGET_X_RANGE)          # rlenv.py:111
        y = self._rng.uniform(*TARGET_Y_RANGE)          # rlenv.py:112
        self.target_pos = [x, y, TARGET_Z]              # rlenv.py:113-114
        # placeholder: a fresh hole body id (upstream loads ./urdf/box.urdf at rlenv.py:115)
        self.hole_id = 2
        self.eef_pos = list(START_POS)                  # placeholder: rest pose of the fake
        return self._get_obs(), {}

    def step(self, action):
        """``PegInHoleGymEnv.step``: clip, move, reward, insertion, truncation, five-tuple (rlenv.py:142-177)."""
        self.step_count += 1
        info = {"insertion_success": False}             # rlenv.py:144
        values = [float(item) for item in action]
        # rlenv.py:146: clip to the action space
        values = [min(max(value, low), high)
                  for value, low, high in zip(values, self.action_space.low, self.action_space.high)]
        # rlenv.py:152-153: new_pos = current_pos + action, without inverse kinematics or physics
        self.eef_pos = [self.eef_pos[i] + values[i] for i in range(3)]
        obs = self._get_obs()
        reward, _dist_xy, _dist_z = self._compute_reward()
        collided = self._check_collision()
        done = True if collided else self._check_done()
        if self._check_inserted():                      # rlenv.py:169-171
            info = {"insertion_success": True}
        truncated = self.step_count >= self.max_steps   # rlenv.py:175
        return obs, reward, done, truncated, info       # rlenv.py:177

    def close(self):
        """``PegInHoleGymEnv.close`` without pybullet: drop the client handle (rlenv.py:267-268)."""
        self.physics_client = None

    # -- internals (same private names as the upstream class) ------------------
    def move_arm_to(self, pos, orn):
        """The fake has no inverse kinematics; the motion is the direct position assignment of ``step``."""
        self.eef_pos = [float(item) for item in pos]

    def update_simulation(self, steps, sleep_time=0.01):   # rlenv.py:92
        """The fake models no simulated time, so a simulation update is a no-op."""
        return None

    def render(self):
        return None

    def _get_obs(self):
        # rlenv.py:193-204 returns a 100x100x1 grayscale camera image; this fake projects two markers into it.
        image = [0] * (self.image_width * self.image_height)   # placeholder: black background
        target = self._pixel(self.target_pos)
        eef = self._pixel(self.eef_pos)
        image[target] = TARGET_PIXEL                            # placeholder: hole marker
        image[eef] = EEF_PIXEL                                  # placeholder: end-effector marker
        return {"cam_image": image}

    def _render_camera_from_link(self, body_id, link_index):
        # The public name exists upstream (rlenv.py:206); the fake renders the projection of _get_obs instead.
        return self._get_obs()["cam_image"]

    def _compute_reward(self):
        dist_xy, dist_z = self._distances()
        reward = REWARD_SCALE * (-dist_xy - REWARD_Z_WEIGHT * dist_z)   # rlenv.py:246
        if self._check_inserted():
            reward += INSERT_REWARD                                     # rlenv.py:248-249
        return reward, dist_xy, dist_z

    def _check_done(self):
        return self._check_inserted()                                   # rlenv.py:253-255

    def _check_inserted(self):
        dist_xy, dist_z = self._distances()
        return dist_xy < INSERT_XY and dist_z < INSERT_Z                # rlenv.py:261

    def _check_collision(self):
        # rlenv.py:179-191 tests PyBullet contact points; the kinematic fake has no contacts to test.
        return False

    def _distances(self):
        dist_xy = math.hypot(self.eef_pos[0] - self.target_pos[0], self.eef_pos[1] - self.target_pos[1])
        dist_z = abs(self.eef_pos[2] - self.target_pos[2])
        return dist_xy, dist_z

    def _pixel(self, pos):
        """Map a position in the rlenv.py:110-114 workspace box to one flat image index."""
        px = int((pos[0] - TARGET_X_RANGE[0]) / (TARGET_X_RANGE[1] - TARGET_X_RANGE[0])
                 * (self.image_width - 1))
        py = int((pos[1] - TARGET_Y_RANGE[0]) / (TARGET_Y_RANGE[1] - TARGET_Y_RANGE[0])
                 * (self.image_height - 1))
        px = min(max(px, 0), self.image_width - 1)
        py = min(max(py, 0), self.image_height - 1)
        return py * self.image_width + px
