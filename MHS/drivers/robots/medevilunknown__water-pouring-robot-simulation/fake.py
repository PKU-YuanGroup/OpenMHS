"""Fake backend of the So101PourEnv driver: a pure Python stand-in for the Gymnasium pouring environment.

Why a fake: the acceptance gate cannot import ``mujoco``, ``gymnasium`` or ``numpy``, and package code never imports
the read-only clone.  This module re-implements the parts of ``so101_mujoco.mujoco.pour_env:So101PourEnv`` the bridge
uses: the two spaces, ``reset(seed, options)``, ``step(action)`` and the five-tuple step result.  The public methods
are the upstream class's public methods (``reset`` and ``step``; gate G7), and the duck-typed ``Box`` class supplies
the ``low``/``high``/``shape``/``dtype`` members the Gymnasium bridge reads.

The numbers that come from the upstream source are cited inline; the initial joint values, site positions, tilt
mapping and integration rule are placeholder test data and are marked ``# placeholder``.  They are not facts, limits
or references.

What this is not: MuJoCo.  It integrates no rigid bodies, contacts, friction, gravity, position actuators or free
bottle/beaker bodies, and it was never compared with the upstream environment.  The driver's fidelity ``gaps`` list
all of this.  Nothing here talks to a device.
"""

import math

# pour_env.py:18-19 (spaces.Box(low=-1, high=1, shape=(6,), dtype=np.float32))
ACTION_SIZE = 6
# pour_env.py:18 and :45 ("5 ARM joints" and action[:5])
ARM_JOINTS = 5
# pour_env.py:21-23 (spaces.Box(..., shape=(18,), dtype=np.float32))
OBSERVATION_SIZE = 18
# pour_env.py:45 (delta = action[:5] * 0.05)
DELTA_SCALE = 0.05
# pour_env.py:54-55 (25.0 * min(1.0, (tilt-30)/60.0) * timestep)
FLOW_RATE = 25.0
TILT_THRESHOLD_DEG = 30.0
TILT_SPAN_DEG = 60.0
# scene.xml:5 (the MuJoCo model timestep used by the water-flow calculation)
TIMESTEP_S = 0.002
# pour_env.py:31 and :60 (max_steps = 500; terminated when beaker_ml >= 150 or current_step >= max_steps)
MAX_STEPS = 500
TERMINATION_ML = 150.0
# pour_env.py:30 and :83 (target_ml = 100.0; the overspill penalty applies above 110)
TARGET_ML = 100.0
OVERSPILL_ML = 110.0


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeSo101PourEnv:
    """The upstream environment interface without MuJoCo: ``reset(seed, options)`` and ``step(action)``."""

    def __init__(self, xml_path="scene.xml"):
        # The upstream constructor takes the MJCF path and loads it (pour_env.py:13-16); the fake never reads it.
        self.xml_path = xml_path
        self.action_space = Box([-1.0] * ACTION_SIZE, [1.0] * ACTION_SIZE)          # pour_env.py:18-19
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE,
                                     [math.inf] * OBSERVATION_SIZE)                  # pour_env.py:21-23
        self.beaker_ml = 0.0                                                        # pour_env.py:29
        self.target_ml = TARGET_ML                                                  # pour_env.py:30
        self.max_steps = MAX_STEPS                                                  # pour_env.py:31
        self.current_step = 0                                                       # pour_env.py:32
        self.ctrl = [0.0] * ACTION_SIZE
        self.qpos = [0.0] * ARM_JOINTS
        self.qvel = [0.0] * ARM_JOINTS
        self.gripper_qpos = 0.0
        self.bottle_pos = [0.30, 0.0, 0.07]                  # placeholder: the scene's bottle body position
        self.beaker_pos = [0.25, 0.15, 0.037]                # placeholder: the scene's target glass site
        self.grasp_pos = [0.0, 0.0, 0.20]                    # placeholder: the gripper site position

    def reset(self, seed=None, options=None):
        # The upstream reset ignores options, restores the MuJoCo data with mj_resetData and zeroes these two
        # counters (pour_env.py:34-39).  The fake ignores the seed and starts from the same placeholder state.
        self.ctrl = [0.0] * ACTION_SIZE
        self.qpos = [0.0] * ARM_JOINTS
        self.qvel = [0.0] * ARM_JOINTS
        self.gripper_qpos = 0.0
        self.bottle_pos = [0.30, 0.0, 0.07]                  # placeholder
        self.beaker_pos = [0.25, 0.15, 0.037]                # placeholder
        self.grasp_pos = [0.0, 0.0, 0.20]                    # placeholder
        self.beaker_ml = 0.0
        self.current_step = 0
        return self._get_obs(), {}

    def step(self, action):
        if len(action) != ACTION_SIZE:
            raise ValueError(f"expected {ACTION_SIZE} action values, got {len(action)}")
        self.current_step += 1                                       # pour_env.py:42
        for index in range(ARM_JOINTS):
            self.ctrl[index] += float(action[index]) * DELTA_SCALE   # pour_env.py:45-46
            # placeholder: the fake jumps the joint to the accumulated target instead of running MuJoCo
            self.qpos[index] = self.ctrl[index]
            # placeholder: velocity is the size of one fake move divided by the model timestep
            self.qvel[index] = float(action[index]) * DELTA_SCALE / TIMESTEP_S
        self.ctrl[5] = float(action[5])                              # pour_env.py:47
        self.gripper_qpos = self.ctrl[5]
        # placeholder: the gripper site tracks the first three joint targets; MuJoCo computes it from the model
        self.grasp_pos = [0.30 + 0.01 * self.qpos[0], 0.01 * self.qpos[1], 0.20 + 0.01 * self.qpos[2]]
        tilt = self._get_tilt_deg()
        if tilt > TILT_THRESHOLD_DEG:                                # pour_env.py:54
            flow = FLOW_RATE * min(1.0, (tilt - TILT_THRESHOLD_DEG) / TILT_SPAN_DEG) * TIMESTEP_S
            self.beaker_ml += flow                                   # pour_env.py:55-56
        reward = self._compute_reward()
        terminated = self.beaker_ml >= TERMINATION_ML or self.current_step >= self.max_steps   # pour_env.py:60
        truncated = False                                                                      # pour_env.py:61
        return self._get_obs(), reward, terminated, truncated, {}

    def _get_obs(self):
        observation = (self.qpos[:ARM_JOINTS] + self.qvel[:ARM_JOINTS] + [self.gripper_qpos]
                       + self.bottle_pos + self.beaker_pos + [self.beaker_ml])                  # pour_env.py:65-71
        return [float(value) for value in observation]

    def _compute_reward(self):
        distance = math.sqrt(sum((left - right) ** 2 for left, right in zip(self.grasp_pos, self.bottle_pos)))
        reward = -distance                                                                      # pour_env.py:75-76
        if self.beaker_ml > 0:
            reward += 10.0 * (1.0 - abs(self.beaker_ml - self.target_ml) / self.target_ml)       # pour_env.py:79-80
        if self.beaker_ml > OVERSPILL_ML:
            reward -= 50.0                                                                      # pour_env.py:83-84
        return reward

    def _get_tilt_deg(self):
        # placeholder: the upstream reads the water_bottle quaternion from MuJoCo; the fake uses the wrist angle
        return min(180.0, abs(math.degrees(self.qpos[3])))                                      # pour_env.py:88-94
