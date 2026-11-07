"""Fake backend for the ArrayCan-v1 environment: a pure Python task-level stand-in.

Why a fake: the upstream environment is a set of files meant to be copied into
ManiSkill (README.md:40-70), and it needs ManiSkill 3.x and SAPIEN 3.x
(README.md:7-8), which are not installed where the gate runs and are never
imported by this package.  This module re-implements the *task layer* of
``envs.array_can:ArrayCanEnv`` (the class the driver names as ``native``):
the five cans, the random tabletop placement, the success predicate and the
reaching reward.  The robot, the contacts and the physics are not modelled.

Every public member below is a member of the upstream class or occurs in the
clone: ``reset``, ``step`` and ``close`` are the Gymnasium environment
methods used by the examples (for example ``examples/array_can.py:15``), and
``evaluate`` and ``compute_dense_reward`` are defined by ``ArrayCanEnv``
(``envs/array_can.py:104`` and ``:153``).  Gate G7 reads the clone's AST.

The upstream constructor inherits ``reset``/``step``/``close`` from
ManiSkill's ``BaseEnv``, which is external to the clone; the fake therefore
does not define ``action_space`` or ``observation_space``.  The bridge then
publishes the step action as an open object instead of inventing bounds the
clone does not state.  The driver's fidelity ``gaps`` and RESULT.json say so.

What this is not: the upstream environment.  The upstream places cans with
ManiSkill's ``UniformPlacementSampler`` and torch's RNG, simulates a Panda arm
with SAPIEN, and returns camera images and qpos arrays.  The fake samples the
declared square directly with Python's ``random.Random``, has no robot, and
returns small scalar observations.  Numbers that are test data (the stand-in
TCP pose) are marked ``# placeholder``.
"""

import math
import random

# envs/array_can.py:21: @register_env("ArrayCan-v1", max_episode_steps=50)
MAX_EPISODE_STEPS = 50
# envs/array_can.py:30: self.num_cans = 5
NUM_CANS = 5
# envs/array_can.py:52-54: self.scale = 0.03, self.radius = 1, self.height = 3.5
CAN_SCALE = 0.03
CAN_RADIUS = 1.0
SCALED_RADIUS = CAN_RADIUS * CAN_SCALE
# envs/array_can.py:85-86: xy = torch.rand((b, 2)) * 0.26 - 0.13, region [[-0.15, -0.15], [0.15, 0.15]]
REGION_LOW = -0.15
REGION_HIGH = 0.15
# envs/array_can.py:113: tol = 0.01
SPACING_TOL = 0.01
# envs/array_can.py:123: lin_tol = 0.001 (the linear test applies only when num_cans == 3)
LINEAR_TOL = 0.001
# placeholder: the fake has no Panda arm or TCP, so the reaching reward uses the table origin
TCP_POSITION = (0.0, 0.0, 0.0)
# placeholder: the fake does not model can orientation; this is the identity quaternion
IDENTITY_QUATERNION = (1.0, 0.0, 0.0, 0.0)


class FakeArrayCanEnv:
    """Task-level ArrayCan-v1: ``reset(seed=..., options=...)`` and ``step(action)``."""

    def __init__(self, robot_uids="panda_wristcam", robot_init_qpos_noise=0.02, **options):
        # envs/array_can.py:27: the upstream defaults; stored but not used by the fake
        self.robot_uids = robot_uids
        self.robot_init_qpos_noise = robot_init_qpos_noise
        self.num_cans = NUM_CANS
        self._options = dict(options)
        self._rng = random.Random()
        self._cans = []
        self._tick = 0
        self._episode = 0
        self._terminated = False
        self._truncated = False
        self._closed = False

    def _observation(self):
        tcp = TCP_POSITION
        obs = {"tcp_pose": list(tcp) + list(IDENTITY_QUATERNION)}
        for idx, (x, y, _z) in enumerate(self._cans):
            obs[f"coke{idx}_pose"] = [x, y, 0.0, *IDENTITY_QUATERNION]
            obs[f"tcp_to_coke{idx}_pos"] = [x - tcp[0], y - tcp[1], -tcp[2]]
        for i in range(self.num_cans):
            for j in range(i + 1, self.num_cans):
                xi, yi, _ = self._cans[i]
                xj, yj, _ = self._cans[j]
                obs[f"coke{i}_to_coke{j}_pos"] = [xj - xi, yj - yi, 0.0]
        return obs

    def _sample_cans(self):
        """Five non-overlapping xy placements in the declared region (envs/array_can.py:85-92)."""
        cans = []
        for _ in range(self.num_cans):
            for _attempt in range(100):  # envs/array_can.py:92: sampler.sample(..., 100, ...)
                x = self._rng.uniform(REGION_LOW, REGION_HIGH)
                y = self._rng.uniform(REGION_LOW, REGION_HIGH)
                if all(math.hypot(x - other[0], y - other[1]) >= 2 * SCALED_RADIUS for other in cans):
                    cans.append((x, y, 0.0))
                    break
            else:
                raise RuntimeError("no non-overlapping can placement found in 100 attempts")
        self._cans = cans

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        self._sample_cans()
        self._tick = 0
        self._terminated = False
        self._truncated = False
        self._episode += 1
        return self._observation(), {"options": dict(options or {}), "episode": self._episode}

    def step(self, action):
        self._tick += 1
        info = self.evaluate()
        reward = self.compute_dense_reward()
        self._truncated = self._tick >= MAX_EPISODE_STEPS  # the TimeLimit of the registration (envs/array_can.py:21)
        return self._observation(), reward, self._terminated, self._truncated, info

    def evaluate(self):
        """The success predicate of envs/array_can.py:104-138, without a robot."""
        positions = [(x, y) for x, y, _z in self._cans]
        distances = sorted(
            math.hypot(positions[i][0] - positions[j][0], positions[i][1] - positions[j][1])
            for i in range(self.num_cans) for j in range(i + 1, self.num_cans)
        )
        d0, d1, d2 = distances[:3]
        is_equally_spaced = abs(d0 - d1) <= SPACING_TOL or abs(d1 - d2) <= SPACING_TOL
        if self.num_cans == 3:  # envs/array_can.py:116-124
            (ax, ay), (bx, by), (cx, cy) = positions
            area = 0.5 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
            is_linear = abs(area) <= LINEAR_TOL
        else:
            is_linear = True  # envs/array_can.py:125-126
        is_can_grasped = False  # the fake has no Panda arm or gripper
        success = is_equally_spaced and is_linear and not is_can_grasped
        return {
            "is_can_grasped": is_can_grasped,
            "is_equally_spaced": bool(is_equally_spaced),
            "is_linear": bool(is_linear),
            "success": bool(success),
        }

    def compute_dense_reward(self, obs=None, action=None, info=None):
        """``2 * (1 - tanh(5 * min_dist))`` of envs/array_can.py:153-161 for the stand-in TCP."""
        distances = [math.hypot(x - TCP_POSITION[0], y - TCP_POSITION[1]) for x, y, _z in self._cans]
        return 2.0 * (1.0 - math.tanh(5.0 * min(distances)))

    def close(self):
        self._closed = True
