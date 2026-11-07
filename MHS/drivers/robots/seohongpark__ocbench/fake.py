"""Fake backend for gh.seohongpark/ocbench: a pure Python stand-in for ``BlockEnv``.

Why a fake: the upstream environment imports MuJoCo, dm_control, Gymnasium and numpy
(``ocbench/envs/block_env.py:1-3``, ``pyproject.toml:9-14``), none of which is available where the acceptance
gate runs, and package code never imports the clone.  This module therefore mirrors the public surface of
``ocbench.envs.block_env:BlockEnv`` that the Gymnasium bridge uses: ``action_space``, ``observation_space``,
``reset``, ``step`` and ``close`` (gate G7 checks the public methods against the AST of the upstream class).

The real environment is a MuJoCo manipulation task: ``BlockEnv`` is a ``ManipulationEnv`` whose action space
is a seven-value ``Box(-1, 1)`` (``ocbench/envs/manipulation_env.py:107-114``) and whose observation
concatenates proprioception with one block record per cube (``ocbench/envs/block_env.py:308-336``).  This
stand-in reproduces that interface only.  Every number below is test data of the stand-in, marked
``# placeholder``; none of them is a fact, a limit or a reference.

What this is not: the MuJoCo model.  It keeps no contacts, actuator forces, inverse kinematics, task success,
reward or contact sensors, and it was never compared with the upstream environment.  The driver's fidelity
``gaps`` list these omissions.  Nothing here talks to a device.
"""

import math
import random

#: One action value per joint of the seven-value upstream action Box
#: (ocbench/envs/manipulation_env.py:107-114); 7 is this stand-in's test data.
N_ACTUATORS = 7                       # placeholder
#: The fake's observation layout: 6 joint positions, 6 joint velocities, 3 effector positions, cos and sin
#: of the effector yaw, scaled gripper opening, gripper contact, then the single cube's 3 positions, 4
#: quaternion values and cos and sin of its yaw.  Upstream: manipulation_env.py:374-393 and
#: block_env.py:326-333; the total 28 is this stand-in's test data.
OBSERVATION_SIZE = 28                 # placeholder
#: block-cpu-single-task1-v0 is registered with max_episode_steps=1250
#: (ocbench/__init__.py:74-79); the fake models the registration's time limit.
MAX_EPISODE_STEPS = 1250              # placeholder
#: ManipulationEnv defaults control_timestep to 0.02 s (manipulation_env.py:17); the fake uses the same
#: tick interval for its simple integrator.
DT_S = 0.02                           # placeholder
#: The stand-in's dynamics.  These are not upstream constants; they only make the observation change.
JOINT_DECAY = 0.5                     # placeholder
JOINT_RATE = 0.5                      # placeholder
GRIPPER_RATE = 0.1                    # placeholder
EFFECTOR_X_RATE = 0.05                # placeholder
EFFECTOR_Y_RATE = 0.02                # placeholder
EFFECTOR_Z_RATE = 0.01                # placeholder
#: The block starts near the single task's goal region; the draw uses this stand-in's bounds.
BLOCK_START_X = 0.425                 # placeholder
BLOCK_START_Z = 0.03                  # placeholder
BLOCK_JITTER_X = 0.05                 # placeholder
BLOCK_JITTER_Y = 0.20                 # placeholder


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeBlockEnv:
    """``BlockEnv`` without MuJoCo: the seven-value action and the 28-value single-cube observation.

    The upstream class has the same public surface (``reset``, ``step`` and ``close`` inherited from
    ``CustomMuJoCoEnv``; ``action_space`` and ``observation_space`` properties on ``ManipulationEnv``),
    which is what gate G7 checks.  The fake returns the five-tuple form the bridge accepts.
    """

    def __init__(self):
        #: manipulation_env.py:107-114: the normalised seven-value joint-delta action.
        self.action_space = Box([-1.0] * N_ACTUATORS, [1.0] * N_ACTUATORS)          # placeholder
        #: manipulation_env.py:95-105: the state observation is unbounded.
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE,                  # placeholder
                                     [math.inf] * OBSERVATION_SIZE)                   # placeholder
        self._rng = random.Random(0)                                                   # placeholder
        self._qpos = [0.0] * 6                                                          # placeholder
        self._qvel = [0.0] * 6                                                          # placeholder
        self._gripper = 0.5                                                             # placeholder
        self._block = [BLOCK_START_X, 0.0, BLOCK_START_Z]                              # placeholder
        self._block_yaw = 0.0                                                           # placeholder
        self._tick = 0
        self._closed = False
        self._reset(None)

    def reset(self, seed=None, options=None):
        """Gymnasium reset: return the initial observation and an info object."""
        self._reset(seed)
        return self._observation(), {"success": False, "failure": False, "healthy": True}

    def step(self, action):
        """Apply one seven-value action and return observation, reward, flags and info."""
        values = [float(value) for value in action]
        if len(values) != N_ACTUATORS:
            raise ValueError(f"block-cpu-single-task1-v0 takes {N_ACTUATORS} action values, got {len(values)}")
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        for index in range(6):
            self._qvel[index] = JOINT_DECAY * self._qvel[index] + values[index]       # placeholder
            self._qpos[index] = self._qpos[index] + DT_S * JOINT_RATE * self._qvel[index]  # placeholder
        self._gripper = min(1.0, max(0.0, self._gripper + GRIPPER_RATE * values[6]))  # placeholder
        self._tick += 1
        truncated = self._tick >= MAX_EPISODE_STEPS                                   # placeholder
        return (self._observation(), 0.0, False, truncated,
                {"success": False, "failure": False, "healthy": True, "tick": self._tick})

    def close(self):
        """Mark the stand-in closed; the upstream close releases the MuJoCo viewer and renderer."""
        self._closed = True

    def _reset(self, seed):
        """Start a new episode; a seed fixes the block draw of this stand-in."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._qpos = [0.0] * 6                                                             # placeholder
        self._qvel = [0.0] * 6                                                             # placeholder
        self._gripper = 0.5                                                                # placeholder
        self._block = [
            BLOCK_START_X + self._rng.uniform(-BLOCK_JITTER_X, BLOCK_JITTER_X),            # placeholder
            self._rng.uniform(-BLOCK_JITTER_Y, BLOCK_JITTER_Y),                            # placeholder
            BLOCK_START_Z,                                                                 # placeholder
        ]
        self._block_yaw = self._rng.uniform(0.0, 2.0 * math.pi)                            # placeholder
        self._tick = 0

    def _observation(self):
        """The single-cube state vector in the order of block_env.py:308-336."""
        effector = [
            BLOCK_START_X + EFFECTOR_X_RATE * self._qpos[0],                               # placeholder
            EFFECTOR_Y_RATE * self._qpos[1],                                               # placeholder
            0.30 + EFFECTOR_Z_RATE * self._qpos[2],                                        # placeholder
        ]
        yaw = self._qpos[3]
        return (
            list(self._qpos)
            + list(self._qvel)
            + effector
            + [math.cos(yaw), math.sin(yaw)]
            + [3.0 * self._gripper, 0.0]                                                   # placeholder
            + list(self._block)
            + [1.0, 0.0, 0.0, 0.0]                                                         # placeholder
            + [math.cos(self._block_yaw), math.sin(self._block_yaw)]
        )
