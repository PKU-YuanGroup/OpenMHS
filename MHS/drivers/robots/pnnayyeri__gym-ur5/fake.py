"""Fake backend of the gym-ur5 driver: a pure Python kinematic stand-in for ``gym_ur5.envs:UR5Env``.

Why a fake: the gate runs without CoppeliaSim, without legacy ``gym``, without the upstream package and without the
PyCopp ``remoteApi`` shared library (the clone vendors only ``remoteApi.dll``, pycopp/sim.py:11-21), and package code
never imports the clone.  This module mirrors the public surface and the control flow of ``UR5Env``
(``gym_ur5/envs/ur5_env.py``) in plain Python: ``reset`` restores the start state and returns the observation only,
``step`` clips the action to the observation +-0.1, integrates the clipped offset into a position, reads back the six
observation values, and returns the legacy ``obs, reward, done, info`` tuple.  The constants taken from the upstream
code cite its line at commit e515a405d6619456a8cd77f8e5108e7f0bc08246; every value that is only test data is marked
``# placeholder``.

What this is not: the CoppeliaSim scene.  Differences, all listed in the fidelity ``gaps`` of the driver:

* there is no UR5, no Jaco hand, no contact physics and no force model; the three force vectors are constant
  placeholders, so the last three observation values never change;
* the action moves the published XYZ signal directly instead of driving the scene's scripts and joints, and the
  target position is a constant placeholder, so the accumulated reward is a simple quadratic stand-in;
* the ``movePathDone`` and ``isTracking`` signals are booleans in this object, not scene signals, and no path is ever
  completed;
* there is no socket, no streaming/buffered remote-API mode and no one-second stop/start delay inside ``resetSim``;
* the physics timestep, the scene and the force readings are not modelled at all.
"""

import math

# gym_ur5/envs/ur5_env.py:31-34
ACTION_DIM = 3
OBSERVATION_DIM = 6
ACTION_MIN, ACTION_MAX = -1.0, 1.0
#: ur5_env.py:64 clips each component to the current observation +-0.1.
ACTION_CLIP = 0.1

#: Test data, not facts: the start pose, the target position and the force vectors of this stand-in.
START_POSITION = [0.0, 0.0, 0.0]        # placeholder
TARGET_POSITION = [0.5, 0.0, 0.0]       # placeholder
FORCE_VECTOR = [0.0, 0.0, 0.0]          # placeholder


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeUR5Env:
    """``UR5Env`` without CoppeliaSim: ``reset()`` and ``step(action)`` have the upstream shapes."""

    def __init__(self):
        self.metadata = {"render.modes": ["human"]}          # ur5_env.py:13
        self.n_substeps = 10                                 # ur5_env.py:29 (unused by the upstream loop)
        self.n_actions = ACTION_DIM                          # ur5_env.py:31
        self.n_states = OBSERVATION_DIM                      # ur5_env.py:32
        self.action_space = Box([ACTION_MIN] * ACTION_DIM, [ACTION_MAX] * ACTION_DIM)          # ur5_env.py:33
        self.observation_space = Box([-math.inf] * OBSERVATION_DIM,
                                     [math.inf] * OBSERVATION_DIM)                             # ur5_env.py:34
        self.stepCount = 0                                   # ur5_env.py:27
        self.reward = 0.0                                    # ur5_env.py:28
        self._position = list(START_POSITION)
        self._target = list(TARGET_POSITION)
        self._forces = [list(FORCE_VECTOR) for _ in range(ACTION_DIM)]
        self._action = [0.0, 0.0, 0.0]
        self._path_done = False                              # placeholder: the scene owns movePathDone
        self._tracking = False                               # placeholder: the scene owns isTracking
        self._render_env = 0.0                               # the renderEnv float signal
        self._closed = False

    # -- the upstream control flow -----------------------------------------
    def reset(self):
        """ur5_env.py:107-113: renderEnv=0, resetSim, prepareSim, then the observation (legacy API)."""
        self._render_env = 0.0
        self.resetSim()
        self.prepareSim()
        return self._get_obs()

    def step(self, action):
        """ur5_env.py:61-71: clip to obs +-0.1, advance one step, return obs, reward, done, info."""
        obs = self._get_obs()
        clipped = [min(max(float(action[index]), obs[index] - ACTION_CLIP), obs[index] + ACTION_CLIP)
                   for index in range(ACTION_DIM)]            # ur5_env.py:64
        self._set_action(clipped)
        self._simulation_step()
        obs = self._get_obs()
        done = self._is_done()
        info = {}
        reward = self._getReward()
        return obs, reward, done, info

    def close(self):
        """ur5_env.py:55-58 finishes the remote API connection; this object only marks itself closed."""
        self._closed = True

    def render(self, mode="human"):
        """ur5_env.py:116-118: set the renderEnv float signal."""
        if mode != "human":
            raise ValueError("the fake UR5 scene renders in 'human' mode only")
        self._render_env = 1.0

    def resetSim(self):
        """ur5_env.py:271-292 restores the scene state and zeroes the counters; no stop/start or sleep here."""
        self.stepCount = 0
        self.reward = 0.0
        self._position = list(START_POSITION)
        self._target = list(TARGET_POSITION)
        self._forces = [list(FORCE_VECTOR) for _ in range(ACTION_DIM)]
        self._action = [0.0, 0.0, 0.0]
        self._path_done = False
        self._tracking = False
        self._render_env = 0.0

    def prepareSim(self):
        """ur5_env.py:251-268 waits for isTracking; the stand-in has no scene, so tracking is immediate."""
        self._tracking = True

    # -- signals and sensors -----------------------------------------------
    def getKinectXYZ(self, initialize=True):
        """ur5_env.py:192-202 returns the actX, actY and actZ float signals."""
        return tuple(self._position)

    def getForce(self, initialize=True):
        """ur5_env.py:205-215 returns the three force sensor vectors."""
        return [list(vector) for vector in self._forces]

    # -- the private helpers of the upstream class -------------------------
    def _set_action(self, action):
        """ur5_env.py:74-82 writes actionX, actionY and actionZ; the stand-in stores the offset."""
        self._action = [float(action[0]), float(action[1]), float(action[2])]

    def _simulation_step(self):
        """ur5_env.py:85-88 triggers one synchronous step; the stand-in integrates the offset."""
        for index in range(ACTION_DIM):
            self._position[index] += self._action[index]

    def _get_obs(self):
        """ur5_env.py:94-98: [X, Y, Z, F1z, F2z, F3z]."""
        x, y, z = self.getKinectXYZ(False)
        forces = self.getForce(False)
        return [x, y, z, forces[0][2], forces[1][2], forces[2][2]]

    def _is_done(self):
        """ur5_env.py:101-104 reads movePathDone; the stand-in never completes a path."""
        return bool(self._path_done)

    def _getTipPos(self, initialize=True):
        """ur5_env.py:146-155 returns the Tip position; the stand-in publishes its position as the tip."""
        return list(self._position)

    def _getTargetPos(self, initialize=True):
        """ur5_env.py:158-167 returns the TargetObject position."""
        return list(self._target)

    def _getReward(self):
        """ur5_env.py:241-248 accumulates minus the squared Tip-to-TargetObject distance."""
        tip = self._getTipPos(False)
        target = self._getTargetPos(False)
        distance = math.dist(tip, target)
        self.stepCount += 1
        self.reward = self.reward - (distance * distance)
        return self.reward
