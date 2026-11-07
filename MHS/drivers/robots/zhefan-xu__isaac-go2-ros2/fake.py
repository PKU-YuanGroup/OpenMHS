"""Fake backend of the Isaac Lab Go2 driver: a pure Python stand-in for the environment object.

Why a fake: the upstream environment needs Isaac Sim 4.5, Isaac Lab 2.1.0, ROS 2 Humble, a GPU and a trained RSL-RL
checkpoint (README.md:26-30, go2/go2_ctrl.py:80-91), none of which exists where the gate runs.  Package code never
imports the clone.  This module implements the Gymnasium surface the bridge reads (``action_space``,
``observation_space``, ``reset``, ``step``, ``close``) without numpy, so it runs on the SDK's Python.

What this is not: the Isaac Sim environment.  The fake models no rigid-body dynamics, contacts, actuator, sensor or
noise behaviour.  It advances a tick, moves the joint positions by the upstream action scale (go2/go2_env.py:173) and
echoes the last action into the observation term that the upstream observes (go2/go2_env.py:89).  The observation and
action dimensions are placeholders (``# placeholder``); the upstream joint dimension comes from ``UNITREE_GO2_CFG``
outside the clone and the height scan from the grid configured at go2/go2_env.py:52-58.  The fidelity ``gaps`` of
``driver.py`` state all of this.

Sourced constants (cited so a reviewer can check them):
  * decimation 8 and sim.dt 0.005 s -> one environment transition is 0.04 s (go2/go2_env.py:161, :164;
    isaac_go2_ros2.py:78);
  * joint position actions are scaled by 0.25 (go2/go2_env.py:173);
  * the reward configuration has no terms (go2/go2_env.py:120-123), so the fake pays 0.0;
  * the episode has no finite horizon (go2/go2_env.py:171-172), so the fake does not truncate.

Nothing here talks to a device.
"""

import math
import random

# go2/go2_env.py:161 and :164; one environment transition is decimation * sim.dt = 0.04 s (isaac_go2_ros2.py:78).
CONTROL_DECIMATION = 8
PHYSICS_DT_S = 0.005
CONTROL_DT_S = CONTROL_DECIMATION * PHYSICS_DT_S
# go2/go2_env.py:173
ACTION_SCALE = 0.25
# The Go2 joint count is not stated in the clone (UNITREE_GO2_CFG is external): test data, not a fact.
JOINTS = 12          # placeholder
SCAN_POINTS = 8      # placeholder: the upstream grid is configured at go2/go2_env.py:52-58


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads the ``spaces`` mapping."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()


class FakeGo2Env:
    """A kinematic stand-in for the Go2 environment; the public members are the Gymnasium environment surface."""

    def __init__(self, **options):
        # The action bound is test data: the clone does not state the Isaac Lab action-space bounds.  # placeholder
        self.action_space = Box([-1.0] * JOINTS, [1.0] * JOINTS)  # placeholder
        unbounded = [math.inf] * 3
        self.observation_space = Dict({
            "base_lin_vel": Box([-value for value in unbounded], unbounded),
            "base_ang_vel": Box([-value for value in unbounded], unbounded),
            "projected_gravity": Box([-value for value in unbounded], unbounded),
            "base_vel_cmd": Box([-value for value in unbounded], unbounded),
            "joint_pos": Box([-math.inf] * JOINTS, [math.inf] * JOINTS),      # placeholder
            "joint_vel": Box([-math.inf] * JOINTS, [math.inf] * JOINTS),      # placeholder
            "actions": Box([-math.inf] * JOINTS, [math.inf] * JOINTS),        # placeholder
            "height_scan": Box([-math.inf] * SCAN_POINTS, [math.inf] * SCAN_POINTS),  # placeholder
        })
        self._rng = random.Random()
        self._joint_pos = None
        self._joint_vel = [0.0] * JOINTS      # placeholder
        self._actions = [0.0] * JOINTS        # placeholder
        self._height_scan = [0.0] * SCAN_POINTS  # placeholder
        self._tick = 0

    def reset(self, *, seed=None, options=None):
        """Reset the stand-in; ``seed`` fixes the initial joint positions, ``options`` is accepted and ignored."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        # A small random joint offset is test data, so a reset with the same seed repeats and a new seed differs.
        self._joint_pos = [self._rng.uniform(-0.01, 0.01) for _ in range(JOINTS)]  # placeholder
        self._joint_vel = [0.0] * JOINTS      # placeholder
        self._actions = [0.0] * JOINTS        # placeholder
        self._height_scan = [0.0] * SCAN_POINTS  # placeholder
        self._tick = 0
        return self._observation(), {}

    def step(self, action):
        """Apply one joint-position action and return the gymnasium five-tuple."""
        if self._joint_pos is None:
            raise RuntimeError("reset() must be called before step()")
        values = [float(value) for value in action]
        if len(values) != JOINTS:
            raise ValueError(f"the action needs {JOINTS} values")
        self._actions = values
        self._joint_pos = [position + ACTION_SCALE * value
                           for position, value in zip(self._joint_pos, values)]
        self._joint_vel = [ACTION_SCALE * value / CONTROL_DT_S for value in values]
        self._tick += 1
        return self._observation(), 0.0, False, False, {"tick": self._tick}

    def close(self):
        self._joint_pos = None

    def _observation(self):
        # The keys are the observation terms of go2/go2_env.py:75-94; the values are simple stand-ins.
        return {
            "base_lin_vel": [0.0, 0.0, 0.0],
            "base_ang_vel": [0.0, 0.0, 0.0],
            "projected_gravity": [0.0, 0.0, -1.0],
            "base_vel_cmd": [0.0, 0.0, 0.0],
            "joint_pos": list(self._joint_pos),
            "joint_vel": list(self._joint_vel),
            "actions": list(self._actions),
            "height_scan": list(self._height_scan),
        }
