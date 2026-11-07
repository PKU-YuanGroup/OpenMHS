"""Fake backend of the RLBench driver: a pure Python stand-in for ``rlbench.gym:RLBenchEnv``.

Why a fake: RLBench is built around CoppeliaSim v4.1.0 and PyRep (README.md:64) and the gate must never import or
install the clone.  This module re-implements the *interface* of the class the driver names as ``native`` -- the
``reset``, ``step``, ``render`` and ``close`` methods, the ``metadata`` mapping and the two spaces -- for one
environment, ``rlbench/reach_target-state-v0``.  It is kinematic: an arm delta moves the joint positions, the
gripper value sets the two gripper joints, and success is a distance test.  It models no contacts, collisions,
forces, physics engine, camera or rendering, and it was never compared with a real RLBench run.

Members: ``reset``, ``step``, ``render`` and ``close`` exist on ``RLBenchEnv`` (rlbench/gym.py:20-121); ``metadata``
is its class attribute (rlbench/gym.py:22).  ``action_space`` and ``observation_space`` are the instance attributes
its ``__init__`` builds (rlbench/gym.py:61-74) and are part of the Gymnasium interface its base class provides.  The
helper classes ``Box`` and ``Dict`` are duck-typed stand-ins for ``gymnasium.spaces`` and are not members of the
backend object.

The action bounds are the upstream default action mode (rlbench/action_modes/action_mode.py:77-79, reached from
rlbench/gym.py:40-41).  Every other constant is test data and is marked ``# placeholder``.  Nothing here talks to a
device and nothing here is imported by the upstream clone.
"""

import math
import random

# The Panda arm has seven joints (rlbench/const.py:38-39); the default JointPositionActionMode appends one gripper
# value, so action_bounds() returns seven arm deltas and one gripper value (rlbench/action_modes/action_mode.py:77-79).
ARM_JOINTS = 7                                                        # rlbench/const.py:39
ARM_LOW = [-0.1] * ARM_JOINTS                                         # action_mode.py:77-79
ARM_HIGH = [0.1] * ARM_JOINTS                                         # action_mode.py:77-79
GRIPPER_LOW, GRIPPER_HIGH = 0.0, 0.04                                 # action_mode.py:77-79

# Kinematic stand-in constants: test data only, never a fact, a limit or a reference.
START_SPAN = 0.02                             # placeholder: reset jitter around zero joint positions
TARGET_CENTRE = [0.4, 0.2, 0.3]               # placeholder: far enough from the start for several ticks
TARGET_SPAN = 0.03                            # placeholder: target jitter
SUCCESS_RADIUS = 0.05                         # placeholder: stand-in for the proximity sensor
OPEN_THRESHOLD = (GRIPPER_LOW + GRIPPER_HIGH) / 2  # placeholder: gripper-open threshold
ZERO_FORCE = 0.0                              # placeholder: no force model
IDENTITY_QUATERNION = [0.0, 0.0, 0.0, 1.0]    # placeholder: fixed orientation of the kinematic tip
FRAME = [[[0.0, 0.0, 0.0]]]                   # placeholder: one pixel; a real frame is 640x360x3 (gym.py:53)


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high, shape=None, dtype="float32"):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces`` and maps each key to its space."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None
        self.dtype = None


def _box_for(values):
    """A one-dimensional Box with the upstream wrapper's bounds: 0..255 for rgb, -inf..inf otherwise (gym.py:61-70)."""
    width = len(values)
    return Box([-math.inf] * width, [math.inf] * width, shape=(width,))


class FakeRLBenchEnv:
    """``RLBenchEnv`` for ``rlbench/reach_target-state-v0`` without CoppeliaSim, PyRep or numpy.

    ``reset(seed, options)`` returns ``(observation, {"text_descriptions": [...]})`` and ``step(action)`` returns
    ``(observation, reward, terminated, truncated, info)`` like the wrapper does (rlbench/gym.py:101-118).  The
    observation is the state dictionary of ``_extract_obs`` (rlbench/gym.py:76-93) with synthetic values.
    """

    # RLBenchEnv.metadata (rlbench/gym.py:22)
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 4}

    def __init__(self, task_class=None, observation_mode="state", render_mode=None, action_mode=None):
        if observation_mode != "state":
            raise ValueError("the fake serves observation_mode 'state' only")
        if render_mode is not None and render_mode not in self.metadata["render_modes"]:
            raise ValueError(f"render_mode must be None or one of {self.metadata['render_modes']}")
        self.task_class = task_class
        self.observation_mode = observation_mode
        self.render_mode = render_mode
        self._closed = False
        self._reset_called = False
        self._rng = random.Random()
        if action_mode is None:
            # rlbench/gym.py:40-41 selects JointPositionActionMode when no action mode is supplied.
            low, high = ARM_LOW + [GRIPPER_LOW], ARM_HIGH + [GRIPPER_HIGH]
        else:
            low, high = action_mode.action_bounds()
        self.action_space = Box(list(low), list(high), shape=(len(low),))
        self._reset_world(None)
        self.observation_space = Dict({name: _box_for(values)
                                       for name, values in self._observation().items()})

    # -- state -----------------------------------------------------------------
    def _reset_world(self, seed):
        if seed is not None:
            self._rng = random.Random(seed)
        self._joints = [self._rng.uniform(-START_SPAN, START_SPAN) for _ in range(ARM_JOINTS)]
        self._velocities = [ZERO_FORCE] * ARM_JOINTS
        self._gripper_joint = GRIPPER_LOW
        self._target = [centre + self._rng.uniform(-TARGET_SPAN, TARGET_SPAN) for centre in TARGET_CENTRE]
        self._descriptions = ["reach the target", "touch the target with the panda gripper"]  # placeholder
        self._terminated = False
        self._reset_called = True

    def _observation(self):
        """The state dictionary ``RLBenchEnv._extract_obs`` keeps (rlbench/gym.py:76-93)."""
        tip = list(self._joints[:3]) + list(IDENTITY_QUATERNION)
        return {
            "joint_velocities": list(self._velocities),
            "joint_positions": list(self._joints),
            "joint_forces": [ZERO_FORCE] * ARM_JOINTS,
            "gripper_open": [1.0 if self._gripper_joint > OPEN_THRESHOLD else 0.0],
            "gripper_pose": tip,
            "gripper_joint_positions": [self._gripper_joint, self._gripper_joint],
            "gripper_touch_forces": [ZERO_FORCE] * 6,
            "task_low_dim_state": list(self._target),                   # ReachTarget.get_low_dim_state (reach_target.py:46-48)
        }

    def _distance_to_target(self):
        return math.sqrt(sum((tip - target) ** 2 for tip, target in zip(self._joints[:3], self._target)))

    # -- Gymnasium interface ---------------------------------------------------
    def reset(self, seed=None, options=None):
        if options is not None and options.get("reset_to_demo") is not None:
            raise ValueError("the fake has no demo to restore")
        self._reset_world(seed)
        return self._observation(), {"text_descriptions": list(self._descriptions)}

    def step(self, action):
        if not self._reset_called:
            raise RuntimeError("Call 'reset' before calling 'step' on a task.")
        values = [float(value) for value in action]
        if len(values) != len(self.action_space.low):
            raise ValueError(f"expected an action of {len(self.action_space.low)} values, got {len(values)}")
        arm = values[:ARM_JOINTS]
        self._joints = [position + delta for position, delta in zip(self._joints, arm)]
        self._velocities = list(arm)
        self._gripper_joint = values[ARM_JOINTS]
        success = self._distance_to_target() < SUCCESS_RADIUS
        self._terminated = success
        # TaskEnvironment.step returns float(success) as the reward (rlbench/task_environment.py:100-102)
        return self._observation(), (1.0 if success else 0.0), success, False, {}

    def render(self):
        if self.render_mode == "rgb_array":
            return [row[:] for row in FRAME]
        return None

    def close(self):
        self._closed = True
