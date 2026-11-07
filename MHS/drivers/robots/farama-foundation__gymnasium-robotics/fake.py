"""Fake backend of the FetchSlide-v4 driver: a pure Python stand-in for ``MujocoFetchSlideEnv``.

Why a fake: the gate cannot import the upstream package (it needs Python 3.11 or newer, MuJoCo, numpy and the
MuJoCo model assets; pyproject.toml:11 and :31-38), and package code never imports the clone.  This module
re-implements the contract of ``gymnasium_robotics.envs.fetch.slide:MujocoFetchSlideEnv`` that the Gymnasium bridge
uses: ``reset(seed, options)``, ``step(action)``, ``close()``, ``action_space`` and ``observation_space``.  The two
space classes duck-type ``gymnasium.spaces.Box`` and ``Dict`` (the bridge reads ``low``, ``high``, ``shape`` and
``spaces``).  Every fixed constant cites the line of the clone at the pinned commit
(b8da02a89191daf8f004e7f7510ff655f7a90100); numbers of this simplified kinematic model are test data and are marked
``# placeholder``.

What this is not: the upstream MuJoCo environment.  It has no contact solver, no friction, no actuator or sensor
model and no rendering.  The gripper is moved by the documented position control (``fetch_env.py:92``) and the puck is
pushed by a placeholder rule when the gripper is close; the resulting trajectories differ from MuJoCo and from the
numpy random stream of the upstream environment.  The driver's fidelity ``gaps`` say so.
"""

import math
import random

# gymnasium_robotics/envs/robot_env.py:87
ACTION_LOW = -1.0
ACTION_HIGH = 1.0
# gymnasium_robotics/envs/fetch/fetch_env.py:92: pos_ctrl *= 0.05
POSITION_SCALE = 0.05
# gymnasium_robotics/envs/fetch/slide.py:49: 20 substeps, dt = 0.002 s, f = 25 Hz
TIMESTEP_S = 20 * 0.002
# gymnasium_robotics/__init__.py:37: max_episode_steps=50
MAX_EPISODE_STEPS = 50
# gymnasium_robotics/envs/fetch/slide.py:184: distance_threshold=0.05
DISTANCE_THRESHOLD = 0.05
# gymnasium_robotics/envs/fetch/slide.py:132: gripper starts at [1, 0.75, 0.41]
GRIPPER_START = (1.0, 0.75, 0.41)
# gymnasium_robotics/envs/fetch/slide.py:134: the puck's fixed height is z = 0.42
PUCK_Z = 0.42
# gymnasium_robotics/envs/fetch/slide.py:134: initial xy offset uniform in [-0.1, 0.1], distance > 0.1
OBJECT_RANGE = 0.1
# gymnasium_robotics/envs/fetch/slide.py:137 and :183: target offset uniform in [-0.3, 0.3]
TARGET_RANGE = 0.3
# gymnasium_robotics/envs/fetch/slide.py:181: target_offset = [0.4, 0.0, 0.0]
TARGET_OFFSET_X = 0.4

# placeholder: the fake's own contact radius and puck response (not a device or upstream bound)
HIT_RADIUS = 0.1
PUCK_RESPONSE = 0.5

_INF = math.inf


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape, dtype="float64"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a mapping of named subspaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeFetchSlideEnv:
    """FetchSlide-v4 without MuJoCo, numpy or model files: the bridge's ``cap.world.*`` contract only."""

    def __init__(self, reward_type="sparse", render_mode=None, **_kwargs):
        if reward_type not in ("sparse", "dense"):
            raise ValueError("reward_type must be 'sparse' or 'dense'")
        if render_mode not in (None, "human", "rgb_array"):
            raise ValueError(f"unsupported render_mode {render_mode!r}")
        self.reward_type = reward_type
        self.render_mode = render_mode
        self.action_space = Box([ACTION_LOW] * 4, [ACTION_HIGH] * 4, (4,), "float32")
        # gymnasium_robotics/envs/fetch/slide.py:67 (25 values), :97 and :105 (two 3-value goals)
        self.observation_space = Dict({
            "observation": Box([-_INF] * 25, [_INF] * 25, (25,), "float64"),
            "achieved_goal": Box([-_INF] * 3, [_INF] * 3, (3,), "float64"),
            "desired_goal": Box([-_INF] * 3, [_INF] * 3, (3,), "float64"),
        })
        self._rng = random.Random()
        self._gripper = list(GRIPPER_START)
        self._puck = [GRIPPER_START[0], GRIPPER_START[1], PUCK_Z]
        self._goal = [GRIPPER_START[0] + TARGET_OFFSET_X, GRIPPER_START[1], PUCK_Z]
        self._gripper_velocity = [0.0, 0.0, 0.0]
        self._puck_velocity = [0.0, 0.0, 0.0]
        self._elapsed_steps = 0
        self._closed = False

    # -- the three public methods of the upstream class (gate G7) ----------------
    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._closed = False
        self._gripper = list(GRIPPER_START)                    # slide.py:132
        self._gripper_velocity = [0.0, 0.0, 0.0]
        self._puck_velocity = [0.0, 0.0, 0.0]
        # slide.py:134: offset uniform in [-0.1, 0.1] until the 2D distance is greater than 0.1
        offset = (OBJECT_RANGE, OBJECT_RANGE)                  # placeholder: fallback after 100 draws
        for _attempt in range(100):
            dx = self._rng.uniform(-OBJECT_RANGE, OBJECT_RANGE)
            dy = self._rng.uniform(-OBJECT_RANGE, OBJECT_RANGE)
            if math.hypot(dx, dy) > OBJECT_RANGE:              # slide.py:134
                offset = (dx, dy)
                break
        self._puck = [self._gripper[0] + offset[0], self._gripper[1] + offset[1], PUCK_Z]
        # slide.py:137 and :181: uniform offset in [-0.3, 0.3] plus target_offset [0.4, 0, 0], height 0.42
        self._goal = [
            self._gripper[0] + self._rng.uniform(-TARGET_RANGE, TARGET_RANGE) + TARGET_OFFSET_X,
            self._gripper[1] + self._rng.uniform(-TARGET_RANGE, TARGET_RANGE),
            PUCK_Z,
        ]
        self._elapsed_steps = 0
        return self._observation(), {}

    def step(self, action):
        if len(action) != len(self.action_space.low):
            raise ValueError("Action dimension mismatch")      # robot_env.py:129-130
        values = [min(max(float(value), ACTION_LOW), ACTION_HIGH) for value in action]  # robot_env.py:132
        self._gripper = [self._gripper[index] + POSITION_SCALE * values[index] for index in range(3)]
        self._gripper_velocity = [POSITION_SCALE * values[index] for index in range(3)]  # velocity * dt
        previous_puck = list(self._puck)
        distance = math.hypot(self._gripper[0] - self._puck[0], self._gripper[1] - self._puck[1])
        if distance <= HIT_RADIUS:                             # placeholder: a simple contact rule
            self._puck = [
                self._puck[0] + PUCK_RESPONSE * POSITION_SCALE * values[0],
                self._puck[1] + PUCK_RESPONSE * POSITION_SCALE * values[1],
                PUCK_Z,
            ]
        self._puck_velocity = [self._puck[index] - previous_puck[index] for index in range(3)]
        self._elapsed_steps += 1
        reward = self._compute_reward()
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS   # __init__.py:37 and slide.py:142
        info = {"is_success": self._is_success()}              # robot_env.py:139-141
        return self._observation(), reward, False, truncated, info

    def close(self):
        self._closed = True

    # -- helpers ----------------------------------------------------------------
    def _observation(self):
        grip = list(self._gripper)
        puck = list(self._puck)
        relative = [puck[index] - grip[index] for index in range(3)]
        # The order of fetch_env.py:107-143: grip, object, relative, gripper state, rotation, velocities.
        values = (
            grip
            + puck
            + relative
            + [0.0, 0.0]                                       # slide.py:177 block_gripper=True
            + [0.0, 0.0, 0.0]                                  # placeholder: the puck's Euler rotation
            + list(self._puck_velocity)
            + [0.0, 0.0, 0.0]
            + list(self._gripper_velocity)
            + [0.0, 0.0]
        )
        return {"observation": values, "achieved_goal": puck, "desired_goal": list(self._goal)}

    def _distance(self):
        return math.sqrt(sum((self._puck[index] - self._goal[index]) ** 2 for index in range(3)))

    def _compute_reward(self):
        distance = self._distance()
        if self.reward_type == "sparse":                       # fetch_env.py:74-78
            return -1.0 if distance > DISTANCE_THRESHOLD else 0.0
        return -distance                                       # fetch_env.py:79-80

    def _is_success(self):
        return self._distance() < DISTANCE_THRESHOLD           # fetch_env.py:168-170
