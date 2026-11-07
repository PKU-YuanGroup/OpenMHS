"""Fake backend of the UR5TaskSpaceEnv-v0 driver: a pure Python analytic stand-in.

Why a fake: constructing the upstream environment needs a ROS node, ROS parameters, Gazebo services and the
clone's ``ur_control``/``ur_gazebo``/``ur_pykdl`` packages, and package code never imports or runs the clone.  This
module re-implements ``ur_openai.task_envs.ur5_task_space:UR5TaskSpaceEnv`` at the end-effector level: each
task-space action is the upstream translation delta ``action * 0.001`` m, applied without inverse kinematics,
joint dynamics, contacts or ROS.  The public members are the ones the upstream environment and its
``RobotGazeboEnv`` base have (``reset``, ``step``, ``close``; gate G7).

Constants copied from the pinned clone carry the cited line; every other number is test data and is marked
``# placeholder``.  The action space copies the upstream Box and is cited in driver.py's ``action_space_ref``.
Nothing here talks to a device.
"""

import math
import random

# ur5_task_space.py:38-40: the action space is Box(-1., 1.) with one value per action.
ACTION_LOW = -1.0
ACTION_HIGH = 1.0
# ur5_task_space.py:183: the upstream _set_action tolerates a 0.0001 excess before its assertion.
ACTION_TOLERANCE = 1.0001
# task_space.yaml:28: the simulation task-space configuration sets n_actions 3.
N_ACTIONS = 3
# task_space.yaml:7: agent_control_dt is 0.005 s.
DT = 0.005
# ur5_task_space.py:190: a unit action is 0.001 m of end-effector translation.
TRANSLATION_PER_ACTION = 0.001
# task_space.yaml:32: distance_threshold is 5.0 mm (the termination error is multiplied by 1000).
DISTANCE_THRESHOLD_MM = 5.0
# robot_env.py:76: the base environment truncates when step_count is at least 200.
TRUNCATION_STEPS = 200
# ur5_task_space.py:140-146: 6 joint angles + 7 end-effector pose + 7 target pose + 6 error + 6 velocity.
OBSERVATION_SIZE = 32

# Test data, not facts: the fake's start position, target pose and joint angles.
START_POSITION = [0.0, 0.0, 0.0]  # placeholder
TARGET_POSE = [0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]  # placeholder
START_JOINTS = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder
TARGET_JITTER = 0.005  # placeholder
DEFAULT_SEED = 0  # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype


class FakeUR5TaskSpaceEnv:
    """Analytic end-effector stand-in for ``UR5TaskSpaceEnv-v0`` without ROS or Gazebo."""

    def __init__(self, **_options):
        self.action_space = Box(
            [ACTION_LOW] * N_ACTIONS,
            [ACTION_HIGH] * N_ACTIONS,
            (N_ACTIONS,),
        )
        self.observation_space = Box(
            [float("-inf")] * OBSERVATION_SIZE,
            [float("inf")] * OBSERVATION_SIZE,
            (OBSERVATION_SIZE,),
        )
        self._position = list(START_POSITION)  # placeholder
        self._target = list(TARGET_POSE)  # placeholder
        self._joints = list(START_JOINTS)  # placeholder
        self._velocity = [0.0] * 6  # placeholder
        self._step_count = 0
        self._episode = 0
        self._seed = None
        self._closed = False

    def reset(self, seed=None, options=None):
        """Reset the arm and target; the seed selects the fake's target jitter."""
        self._seed = DEFAULT_SEED if seed is None else int(seed)
        rng = random.Random(self._seed)
        self._position = list(START_POSITION)  # placeholder
        self._joints = list(START_JOINTS)  # placeholder
        self._velocity = [0.0] * 6  # placeholder
        jitter = [rng.uniform(-TARGET_JITTER, TARGET_JITTER) for _ in range(3)]  # placeholder
        self._target = [
            TARGET_POSE[0] + jitter[0],  # placeholder
            TARGET_POSE[1] + jitter[1],  # placeholder
            TARGET_POSE[2] + jitter[2],  # placeholder
            TARGET_POSE[3],
            TARGET_POSE[4],
            TARGET_POSE[5],
            TARGET_POSE[6],
        ]
        self._step_count = 0
        self._episode += 1
        return self._get_obs(), {}

    def step(self, action):
        """Apply the upstream translation delta and return the upstream five-tuple."""
        values = action.tolist() if hasattr(action, "tolist") else list(action)
        values = [float(value) for value in values]
        if len(values) != N_ACTIONS:
            raise ValueError(f"the action has {N_ACTIONS} values, got {len(values)}")
        if any(value < -ACTION_TOLERANCE or value > ACTION_TOLERANCE for value in values):
            raise ValueError(f"the action is outside [{ACTION_LOW}, {ACTION_HIGH}]")

        before = list(self._position)
        self._position = [
            before[index] + values[index] * TRANSLATION_PER_ACTION for index in range(3)
        ]
        self._velocity = [
            (self._position[index] - before[index]) / DT for index in range(3)
        ] + [0.0, 0.0, 0.0]  # placeholder rotation velocity
        self._joints = list(START_JOINTS)  # placeholder: no inverse kinematics is modelled

        distance_m = math.sqrt(
            sum((self._target[index] - self._position[index]) ** 2 for index in range(3))
        )
        terminated = distance_m * 1000.0 < DISTANCE_THRESHOLD_MM
        truncated = self._step_count >= TRUNCATION_STEPS
        reward = 100.0 if terminated else -distance_m * 1000.0
        self._step_count += 1
        return self._get_obs(), reward, terminated, truncated, {}

    def close(self):
        self._closed = True

    def _get_obs(self):
        """The upstream 32-element concatenation (ur5_task_space.py:136-146)."""
        pose = self._position + [0.0, 0.0, 0.0, 1.0]  # placeholder orientation
        error = [self._target[index] - self._position[index] for index in range(3)] + [0.0, 0.0, 0.0]
        velocity = list(self._velocity)
        return list(self._joints) + pose + list(self._target) + error + velocity
