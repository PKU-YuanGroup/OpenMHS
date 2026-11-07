"""Fake backend of the BrickSim driver: a pure Python stand-in for the state-based assemble-brick environment.

Why a fake: the environment that ``AssembleBrickEnvCfg`` configures is Isaac Lab's ``ManagerBasedRLEnv`` driven by
Isaac Sim, which needs x86-64 Linux, Python 3.11, an NVIDIA GPU and the optional extras pinned in
``python/pyproject.toml:17-19``; none of that is importable where the gate runs, and package code never imports the
clone.  This module re-implements a small kinematic version of the task: the seven action values are the six
relative arm pose commands plus the gripper command, the observation keeps the policy and privileged groups of the
environment, and the 6 x 1/60 s control step of ``python/bricksim/envs/assemble_brick/env.py:492-494`` becomes one
tick.  The public members are the ones the Gymnasium environment interface has (``reset``, ``step``, ``close``; gate
G7), and the space classes duck-type ``gymnasium.spaces.Box`` and ``Dict``.

Every number below is test data of this fake, marked ``# placeholder``, or a value copied from the clone with its
line; nothing here is a fact or a safety limit of a device.  What this is not: Isaac Sim.  There is no contact,
friction, actuator or sensor model, and the fidelity ``gaps`` of the driver say so.
"""

import random

#: placeholder: 7 = the six relative arm pose values plus one gripper value (env.py:278-300)
ACTION_DIM = 7
#: placeholder: one control step lasts 6 simulation steps of 1/60 s, so an episode of 12.0 s is 120 ticks
#: (env.py:492-494)
EPISODE_TICKS = 120
#: placeholder: the policy group is end-effector pose (7), gripper width (1), gripper speed (1), brick pose (7) and
#: target pose (7) concatenated (env.py:323-332)
POLICY_DIM = 23
#: placeholder: the fake starts this far above the target and each step moves 0.2 times the z command
START_GAP_M = 0.05
#: placeholder: the z element of the action is scaled by 0.2, the third entry of the arm scale (env.py:90)
Z_STEP_M = 0.2
#: placeholder: the gripper thresholds of the action term (env.py:297-298)
OPEN_THRESHOLD = 0.2
CLOSE_THRESHOLD = -0.2
#: placeholder: the finger opening and closing commands of the action term (env.py:295-296)
FINGER_OPEN_M = 0.04
FINGER_CLOSED_M = 0.0
#: placeholder: the brick's stud dimensions in the scene configuration (env.py:261)
BRICK_DIMENSIONS = [2.0, 4.0, 3.0]
#: placeholder: reward of an ordinary step and of the step that reaches the target
STEP_REWARD = 0.0
SUCCESS_REWARD = 1.0


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.low):
            return False
        return all(low <= float(item) <= high for low, high, item in zip(self.low, self.high, value))


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a mapping of names to spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _policy(observation):
    """The five policy terms concatenated, in the order of env.py:323-332."""
    out = []
    for name in ("ee_frame_pose", "gripper_width", "gripper_speed", "brick_pose", "target_pose"):
        out.extend(observation[name])
    return out


class FakeAssembleBrickEnv:
    """The state-based task without Isaac Sim: ``reset(seed, options)`` and ``step(action)`` return gymnasium tuples."""

    def __init__(self, **options):
        if options:
            raise ValueError(f"the fake takes no options: {sorted(options)}")
        # placeholder: the action is the normalized [-1, 1] command the ActionsCfg docstring describes (env.py:274)
        self.action_space = Box([-1.0] * ACTION_DIM, [1.0] * ACTION_DIM)
        # placeholder: boxes with the group shapes of the state-based configuration (env.py:323-342)
        self.observation_space = Dict({
            "policy": Box([-1e9] * POLICY_DIM, [1e9] * POLICY_DIM),
            "privileged": Dict({
                "ee_frame_pose": Box([-1e9] * 7, [1e9] * 7),
                "gripper_width": Box([-1e9], [1e9]),
                "gripper_speed": Box([-1e9], [1e9]),
                "brick_pose": Box([-1e9] * 7, [1e9] * 7),
                "target_pose": Box([-1e9] * 7, [1e9] * 7),
                "brick_grasped": Box([0.0], [1.0]),
                "connection_created": Box([0.0], [1.0]),
                "brick_dimensions": Box([0.0] * 3, [1e9] * 3),
            }),
        })
        self._gap = None
        self._finger = FINGER_OPEN_M
        self._tick = 0
        self._terminated = False
        self._truncated = False
        self._success = False
        self._rng = random.Random()

    # -- observation -------------------------------------------------------
    def _observation(self):
        gap = self._gap
        ee = [0.0, 0.0, gap, 1.0, 0.0, 0.0, 0.0]                            # placeholder: identity orientation
        brick = [0.5, -0.2, 0.0, 1.0, 0.0, 0.0, 0.0]                          # placeholder: brick and target poses
        target = [0.5, 0.0, 0.05, 1.0, 0.0, 0.0, 0.0]                         # placeholder
        terms = {
            "ee_frame_pose": ee,
            "gripper_width": [self._finger],
            "gripper_speed": [0.0],                                           # placeholder: no finger dynamics
            "brick_pose": brick,
            "target_pose": target,
        }
        privileged = dict(terms)
        privileged.update({
            "brick_grasped": [1.0 if self._finger == FINGER_CLOSED_M else 0.0],
            "connection_created": [1.0 if self._success else 0.0],
            "brick_dimensions": list(BRICK_DIMENSIONS),
        })
        return {"policy": _policy(terms), "privileged": privileged}

    # -- gymnasium interface ----------------------------------------------
    def reset(self, *, seed=None, options=None):
        if options:
            raise ValueError(f"the fake's reset takes no options: {sorted(options)}")
        if seed is not None:
            self._rng = random.Random(seed)
        # placeholder: a small seeded jitter around the start gap
        self._gap = START_GAP_M + self._rng.uniform(-0.01, 0.01)
        self._finger = FINGER_OPEN_M
        self._tick = 0
        self._terminated = False
        self._truncated = False
        self._success = False
        return self._observation(), {}

    def step(self, action):
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} is not in the action space")
        if self._gap is None:
            raise AssertionError("Call reset before using step method.")
        values = [float(item) for item in action]
        # placeholder: the arm's z command moves the end effector; no other axis changes the scalar gap
        self._gap += Z_STEP_M * values[2]
        if values[6] > OPEN_THRESHOLD:
            self._finger = FINGER_OPEN_M
        elif values[6] < CLOSE_THRESHOLD:
            self._finger = FINGER_CLOSED_M
        self._tick += 1
        reward = STEP_REWARD
        if self._gap <= 0.0 and self._finger == FINGER_OPEN_M:
            # placeholder: reaching the target with the gripper open is the task's success condition
            self._terminated = True
            self._success = True
            reward = SUCCESS_REWARD
        elif self._gap < -START_GAP_M:
            # placeholder: the fake treats a large overshoot as a dropped brick
            self._terminated = True
        if not self._terminated and self._tick >= EPISODE_TICKS:
            self._truncated = True
        return self._observation(), reward, self._terminated, self._truncated, {}

    def close(self):
        self._gap = None
