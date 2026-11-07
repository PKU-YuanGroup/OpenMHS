"""Fake backend of the gym-pybullet-drones driver: a pure Python stand-in for CtrlAviary (ctrl-aviary-v0).

Why a fake: the acceptance gate runs without pybullet, numpy or the upstream package, and package code never imports
the clone.  This module re-implements the environment behind ``gym_pybullet_drones.envs:CtrlAviary`` at the pinned
commit 7ebad1ecabd28a7000add2d05f888aa2e837c2cc: the action and observation spaces (CtrlAviary.py:74-102), the dummy
reward and flags (CtrlAviary.py:144-200) and the reset state (BaseAviary.py:220-258, :451-470).  Gate G7: the public
members defined here are the ones the environment has (``reset``, ``step``, ``close``).

What this is not: the PyBullet simulation.  The fake integrates only the vertical force balance of one CF2X drone from
the real parameters of the clone (mass, kf and thrust-to-weight of cf2x.urdf:5-11, gravity 9.8 of BaseAviary.py:74) and
leaves x, y, attitude, angular velocity and collisions at their reset values; the fidelity ``gaps`` of driver.py say so.

Every number below is either a constant of the clone (with its line) or a placeholder, marked ``# placeholder``.
"""

import math

# gym_pybullet_drones/envs/BaseAviary.py:74
GRAVITY = 9.8
# gym_pybullet_drones/assets/cf2x.urdf:5-11 (the CF2X parameters the upstream loads from its URDF)
MASS = 0.027
KF = 3.16e-10
THRUST2WEIGHT_RATIO = 2.25
# gym_pybullet_drones/envs/BaseAviary.py:116-119
HOVER_RPM = math.sqrt((GRAVITY * MASS) / (4 * KF))
MAX_RPM = math.sqrt((THRUST2WEIGHT_RATIO * GRAVITY * MASS) / (4 * KF))
# gym_pybullet_drones/envs/BaseAviary.py:77-83 (240 Hz physics and control, so one control step per pybullet step)
PYB_FREQ = 240
DT = 1.0 / PYB_FREQ
# gym_pybullet_drones/envs/CtrlAviary.py:12-26 (the class defaults; ctrl-aviary-v0 registers no kwargs)
NUM_DRONES = 1
# placeholder: the ground level at which the vertical model stops, in metres
GROUND_Z = 0.0
# gym_pybullet_drones/envs/CtrlAviary.py:144-200 (the dummy reward, flags and info of CtrlAviary)
REWARD = -1.0
INFO = {"answer": 42}


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: ``low``, ``high``, ``shape`` and ``dtype`` (what the bridge reads)."""

    def __init__(self, low, high, shape=(), dtype="float32"):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = dtype

    def contains(self, value):
        flat = [float(item) for row in value for item in row] if isinstance(value[0], (list, tuple)) else list(value)
        bounds = [bound for row in self.low for bound in row] if isinstance(self.low[0], (list, tuple)) else list(self.low)
        upper = [bound for row in self.high for bound in row] if isinstance(self.high[0], (list, tuple)) else list(self.high)
        return len(flat) == len(bounds) == len(upper) and all(
            bounds[index] <= flat[index] <= upper[index] for index in range(len(flat)))


class FakeCtrlAviary:
    """``CtrlAviary`` without pybullet or numpy: one drone, the four motor speeds and the 20-value state vector."""

    def __init__(self, drone_model="cf2x", num_drones=1, pyb_freq=240, ctrl_freq=240, gui=False, record=False,
                 physics="pyb", obstacles=False, **_options):
        if num_drones != 1:
            raise NotImplementedError(f"the fake models the single drone of ctrl-aviary-v0; got num_drones={num_drones}")
        if gui or record:
            raise NotImplementedError("the fake cannot render or record")
        self.NUM_DRONES = num_drones
        self.PYB_FREQ = pyb_freq
        self.CTRL_FREQ = ctrl_freq
        self.MAX_RPM = MAX_RPM
        # CtrlAviary.py:74-86: Box(0, MAX_RPM) of shape (NUM_DRONES, 4)
        self.action_space = Box([[0.0] * 4], [[MAX_RPM] * 4], (NUM_DRONES, 4), "float32")
        # CtrlAviary.py:90-102: the 20-value state vector, with the bounds of the class
        self.observation_space = Box(
            [[-math.inf, -math.inf, 0.0, -1.0, -1.0, -1.0, -1.0, -math.pi, -math.pi, -math.pi,
              -math.inf, -math.inf, -math.inf, -math.inf, -math.inf, -math.inf, 0.0, 0.0, 0.0, 0.0]],
            [[math.inf, math.inf, math.inf, 1.0, 1.0, 1.0, 1.0, math.pi, math.pi, math.pi,
              math.inf, math.inf, math.inf, math.inf, math.inf, math.inf, MAX_RPM, MAX_RPM, MAX_RPM, MAX_RPM]],
            (NUM_DRONES, 20), "float32")
        self._state = None

    # -- the members the environment has (gate G7) -------------------------------------------------------------
    def reset(self, *, seed=None, options=None):
        """``BaseAviary.py:220-258``: place the drone at the origin and return its observation and info."""
        self._state = {"xyz": [0.0, 0.0, 0.0], "vel": [0.0, 0.0, 0.0], "rpm": [0.0, 0.0, 0.0, 0.0]}
        return self._observation(), dict(INFO)

    def step(self, action):
        """One control step: clip the motor speeds, integrate the vertical force balance, return the 5-tuple."""
        clipped = self._clip(action)
        if self._state is None:
            raise AssertionError("call reset before step")
        mean_rpm = sum(clipped) / 4.0
        thrust = 4.0 * KF * mean_rpm * mean_rpm            # BaseAviary.py:120 (thrust of four propellers)
        acceleration = thrust / MASS - GRAVITY             # BaseAviary.py:117 (gravity force = G*M)
        velocity = self._state["vel"][2] + acceleration * DT
        position_z = self._state["xyz"][2] + velocity * DT
        if position_z < GROUND_Z:                          # the ground stops a falling drone
            position_z, velocity = GROUND_Z, 0.0
        self._state = {"xyz": [self._state["xyz"][0], self._state["xyz"][1], position_z],
                       "vel": [0.0, 0.0, velocity], "rpm": clipped}
        return self._observation(), REWARD, False, False, dict(INFO)

    def close(self):
        """``BaseAviary.py:416-418``: disconnect from PyBullet; the fake has no client."""
        self._state = None

    # -- the model (private: gate G7 checks only the public surface above) --------------------------------------
    def _clip(self, action):
        """``CtrlAviary.py:121-140``: clip the commanded motor speeds to [0, MAX_RPM]."""
        values = [float(item) for row in action for item in row] if action and isinstance(action[0], (list, tuple)) \
            else [float(item) for item in action]
        if len(values) != 4:
            raise AssertionError(f"an action of shape ({NUM_DRONES}, 4) is expected, got {len(values)} values")
        return [min(max(value, 0.0), MAX_RPM) for value in values]

    def _observation(self):
        """``BaseAviary.py:541-561``: position, quaternion, rpy, velocity, angular velocity and the motor commands."""
        xyz = self._state["xyz"]
        vel = self._state["vel"]
        return [[xyz[0], xyz[1], xyz[2],
                 0.0, 0.0, 0.0, 1.0,                           # placeholder: identity attitude of a reset
                 0.0, 0.0, 0.0,                                # placeholder: level roll, pitch and yaw
                 vel[0], vel[1], vel[2],
                 0.0, 0.0, 0.0,                                # placeholder: no angular velocity
                 self._state["rpm"][0], self._state["rpm"][1], self._state["rpm"][2], self._state["rpm"][3]]]

    # -- hooks for test_driver.py (not environment members, never used by the driver) --------------------------
    def _state_vector(self):
        """The 20 values the environment reports now (the first row of the observation)."""
        return list(self._observation()[0])
