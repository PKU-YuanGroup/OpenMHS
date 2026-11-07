"""Fake backend of the LW-BenchHub driver: a pure-Python stand-in for the registered lift environment.

Why a fake: the upstream environment is built on Isaac Sim 5.0 and Isaac Lab, needs a Linux GPU host and the
install.sh stack, and package code never imports the read-only clone.  The gate therefore exercises the package
through this stand-in for the single environment that ``gymnasium.make("Robocasa-Rl-G1LiftObjStateRL")`` would
build (the registration is at ``lw_benchhub_rl/__init__.py:18-27``).  It exposes only the Gymnasium environment
surface the bridge reads: ``action_space``, ``observation_space``, ``reset``, ``step`` and ``close``.  Those names
are part of the Gymnasium environment interface, not members of the card's ``LiftObj`` task class (G7 reports
them as MAYBE_ABSENT warnings).

What this is not: Isaac Sim, PhysX, the kitchen scene, the G1 USD articulation or the Dex3 hand.  The dynamics
below are analytic placeholders: a lift height that rises when a closed hand receives a positive arm command,
the task's real fixed start height and success threshold, and the episode's 400-step truncation derived from the
task's own timing.  Every numeric constant is test data and is marked ``# placeholder``; the clone refs only say
where the stand-in's shape comes from.

The stand-in shapes (test data, not device facts):

* action: 8 numbers, the G1 RL arm (7 joints) plus the binary hand command (1).  The upstream action space is an
  unbounded Box (``manager_based_rl_env.py:343``), so this Box is unbounded too and declares no limit.
* observation: a ``Dict`` with one ``policy`` group of 104 numbers, built from the observation terms the RL task
  concatenates (43 joint positions + 43 joint velocities + a 7-number object pose command + 8 last actions +
  3 object position numbers).  The real dimensions are computed at run time by Isaac Lab; 104 is the stand-in
  value named in ``RESULT.json`` notes.
"""

import math
import random

# Test-data shape of the stand-in (the refs in the driver and facts.md explain the upstream terms).
ACTION_DIM = 8              # placeholder: 7 right-arm joints + 1 binary hand command
JOINT_COUNT = 43            # placeholder: body + hand joints of the G1 43-dof model
POSE_COMMAND_DIM = 7        # placeholder: position xyz + quaternion wxyz
OBJECT_POSITION_DIM = 3     # placeholder: object position in the robot root frame
OBSERVATION_SIZE = JOINT_COUNT + JOINT_COUNT + POSE_COMMAND_DIM + ACTION_DIM + OBJECT_POSITION_DIM
POLICY_START = JOINT_COUNT + JOINT_COUNT
OBJECT_POSITION_START = POLICY_START + POSE_COMMAND_DIM + ACTION_DIM

# Test-data episode and task numbers (the upstream lines are cited in driver.py and facts.md).
START_HEIGHT = 0.95         # placeholder: LiftObj fixes the object at z 0.95 (lift_obj.py:44)
SUCCESS_HEIGHT = 0.965      # placeholder: LiftObj success is root height >= 0.965 (lift_obj.py:88-89)
MAX_EPISODE_STEPS = 400     # placeholder: 8.0 s / (0.01 s sim dt * decimation 2) from base.py:241,247,249
LIFT_RATE = 0.0002          # placeholder: metres added per tick at arm command 1.0
HAND_INDEX = ACTION_DIM - 1 # placeholder: the binary hand command is the last action element
LIFT_INDEX = 0              # placeholder: the first right-arm command drives the stand-in lift
HAND_CLOSED = 0.0           # placeholder: a hand command above zero closes the hand
RESET_SPREAD = 0.08         # placeholder: RL task x/y reset offsets are (-0.08, 0.08) (lift_obj RL:144)
YAW_DEGREES = 90.0          # placeholder: RL task yaw reset range is (0, 90) degrees (lift_obj RL:144)
REWARD_SUCCESS = 1.0        # placeholder: the stand-in pays 1 on the successful step
REWARD_STEP = 0.0           # placeholder: and 0 on every other step


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per array element."""

    def __init__(self, low, high, shape=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float64"

    def contains(self, value):
        try:
            values = list(value)
        except TypeError:
            return False
        return len(values) == len(self.low) and all(
            low <= item <= high for item, low, high in zip(values, self.low, self.high))


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a named mapping of subspaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None
        self.dtype = None

    def contains(self, value):
        if not isinstance(value, dict) or set(value) != set(self.spaces):
            return False
        return all(self.spaces[name].contains(value[name]) for name in self.spaces)


class FakeG1LiftObjEnv:
    """A one-environment stand-in for ``Robocasa-Rl-G1LiftObjStateRL`` (``reset`` and ``step`` return gym tuples)."""

    def __init__(self, **options):
        # Test-data spaces: an unbounded Box action (as ManagerBasedRLEnv builds) and a Dict policy observation.
        self.action_space = Box([-math.inf] * ACTION_DIM, [math.inf] * ACTION_DIM)
        self.observation_space = Dict({
            "policy": Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE),
        })
        self._rng = random.Random()
        self._height = START_HEIGHT
        self._object_xy = (0.0, 0.0)       # placeholder: neutral start offsets
        self._object_yaw = 0.0             # placeholder: neutral start yaw
        self._last_action = [0.0] * ACTION_DIM   # placeholder: neutral last action
        self._tick = 0
        self._closed = False

    def _observation(self):
        # Test-data layout: joint positions, joint velocities, pose command, last action, object position.
        values = [0.0] * JOINT_COUNT       # placeholder: neutral joint positions
        values += [0.0] * JOINT_COUNT      # placeholder: zero joint velocities
        values += [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]      # placeholder: identity pose command
        values += list(self._last_action)
        values += [self._object_xy[0], self._object_xy[1], self._height]
        return {"policy": values}

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        self._height = START_HEIGHT
        self._object_xy = (self._rng.uniform(-RESET_SPREAD, RESET_SPREAD),
                           self._rng.uniform(-RESET_SPREAD, RESET_SPREAD))
        self._object_yaw = self._rng.uniform(0.0, YAW_DEGREES)
        self._last_action = [0.0] * ACTION_DIM   # placeholder: neutral last action
        self._tick = 0
        self._closed = False
        return self._observation(), {}

    def step(self, action):
        values = list(action)
        if len(values) != ACTION_DIM:
            raise AssertionError(f"expected {ACTION_DIM} action values, got {len(values)}")
        self._last_action = [float(value) for value in values]
        closed = self._last_action[HAND_INDEX] > HAND_CLOSED
        if closed and self._last_action[LIFT_INDEX] > 0.0:   # placeholder: positive arm command lifts
            self._height += LIFT_RATE * self._last_action[LIFT_INDEX]
        self._tick += 1
        terminated = self._height >= SUCCESS_HEIGHT
        truncated = self._tick >= MAX_EPISODE_STEPS
        reward = REWARD_SUCCESS if terminated else REWARD_STEP
        return self._observation(), reward, terminated, truncated, {}

    def close(self):
        self._closed = True
