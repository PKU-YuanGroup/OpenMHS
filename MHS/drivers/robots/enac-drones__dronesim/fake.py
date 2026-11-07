"""Fake backend of the dronesim driver: a pure Python stand-in for ``dronesim.envs.CtrlAviary:CtrlAviary``.

Why a fake: the upstream package needs pyBullet, numpy and the legacy ``gym`` package (setup.py:5-15), none of which
is installed where the gate runs, and package code never imports or runs the clone.  This module mirrors the public
surface of ``CtrlAviary`` that the bridge uses -- ``reset``, ``step`` and ``close`` (gate G7) -- plus duck-typed
``Dict``, ``Box`` and ``MultiBinary`` spaces.  The bridge reads the action space (one Box per drone, bounded by the
drone's PWM limits) and the observation space.

What this is not: the PyBullet rigid-body model.  The fake is an F0 analytic kinematic stand-in with one four-motor
tello drone (CtrlAviary's default ``drone_model=['tello']``, ``num_drones=1``).  It keeps the 20-value state vector of
``BaseAviary._getDroneStateVector`` (position, quaternion, roll-pitch-yaw, velocity, angular velocity and the last
motor command), the upstream reward -1, done False and info ``{"answer": 42}``, and the 240 Hz timestep.  It has no
forces, contacts, aerodynamics, actuator, sensor or noise model, as the driver's fidelity ``gaps`` say.  Every number
that is only test data (the start height and the per-tick kinematic increments) is marked ``# placeholder``.

The action space is one Box(4) -- the single tello's four PWM values -- rather than upstream's Dict keyed by the
numeric drone index ("0"): the bridge derives limit paths from the action-space keys and its field-name grammar cannot
name a key that starts with a digit (``action.0``).  For one drone the Box carries exactly the same four commands; the
fake's ``step`` also accepts the upstream Dict form ``{"0": [p0, p1, p2, p3]}``.

Constants that are taken from the clone cite the line at the pinned commit
(158e40f4631e64d731f16f81641f629fa7b2a986).  Nothing here talks to a device.
"""

import math

# dronesim/envs/CtrlAviary.py:21 (freq=240 default) and dronesim/envs/BaseAviary.py:185-186 (TIMESTEP = 1/SIM_FREQ)
SIM_FREQ = 240
TIMESTEP = 1.0 / SIM_FREQ
# dronesim/assets/tello.urdf:30 (actuator_nr=4) and :47 (PWM limit min 0, max 1)
NUM_MOTORS = 4
PWM_LOW, PWM_HIGH = 0.0, 1.0

# placeholder: the kinematic stand-in's start height and per-tick response, not a fact about the upstream model
START_Z = 0.1205
LIFT_GAIN = 1.0
YAW_GAIN = 0.05


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, values):
        values = list(values)
        return len(values) == len(self.low) and all(
            low <= float(value) <= high for value, low, high in zip(values, self.low, self.high))


class MultiBinary:
    """Duck-typed ``gym.spaces.MultiBinary``: ``n`` binary elements (the bridge reads ``n`` and ``shape``)."""

    def __init__(self, n):
        self.n = int(n)
        self.shape = (self.n,)
        self.dtype = "int8"


class Dict:
    """Duck-typed ``gym.spaces.Dict``: a mapping of named subspaces (the bridge reads ``spaces``)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _observation_space():
    """CtrlAviary's per-drone Dict, with the 20 values ``_getDroneStateVector`` actually returns (CtrlAviary.py:196-208)."""
    low = [-math.inf, -math.inf, 0.0, -1.0, -1.0, -1.0, -1.0, -math.pi, -math.pi, -math.pi,
           -math.inf, -math.inf, -math.inf, -math.inf, -math.inf, -math.inf,
           PWM_LOW, PWM_LOW, PWM_LOW, PWM_LOW]
    high = [math.inf, math.inf, math.inf, 1.0, 1.0, 1.0, 1.0, math.pi, math.pi, math.pi,
            math.inf, math.inf, math.inf, math.inf, math.inf, math.inf,
            PWM_HIGH, PWM_HIGH, PWM_HIGH, PWM_HIGH]
    return Dict({"0": Dict({"state": Box(low, high), "neighbors": MultiBinary(1)})})


class FakeCtrlAviary:
    """One tello in a CtrlAviary-like environment: ``reset`` and ``step`` return what the upstream class returns."""

    def __init__(self, **options):
        # The upstream CtrlAviary accepts drone_model, num_drones and initial_* options; this fake models the default
        # one-tello world only and ignores the options it cannot represent (the driver's fidelity gaps say so).
        self._options = dict(options)
        self.action_space = Box([PWM_LOW] * NUM_MOTORS, [PWM_HIGH] * NUM_MOTORS)
        self.observation_space = _observation_space()
        self._state = None
        self._reset_state()

    def _reset_state(self):
        self._pos = [0.0, 0.0, START_Z]                 # placeholder: derived from the default initial pose
        self._quat = [0.0, 0.0, 0.0, 1.0]
        self._rpy = [0.0, 0.0, 0.0]
        self._vel = [0.0, 0.0, 0.0]
        self._ang_v = [0.0, 0.0, 0.0]
        self._last = [0.0] * NUM_MOTORS
        self._step_counter = 0

    def _observation(self):
        state = (self._pos + self._quat + self._rpy + self._vel + self._ang_v + self._last)
        return {"0": {"state": list(state), "neighbors": [1]}}

    def _clip(self, action):
        if isinstance(action, dict):
            # the upstream CtrlAviary action form: one array per numeric drone index
            unknown = sorted(set(action) - {"0"})
            if unknown:
                raise AssertionError(f"this fake models drone 0 only; got keys {unknown}")
            values = action.get("0")
            if values is None:
                raise AssertionError("action has no entry for drone '0'")
        else:
            values = action
        if not isinstance(values, (list, tuple)):
            raise AssertionError(f"an action must be one array of {NUM_MOTORS} PWM values")
        values = list(values)
        if len(values) != NUM_MOTORS:
            raise AssertionError(f"drone 0 needs {NUM_MOTORS} PWM values, got {len(values)}")
        return [min(max(float(value), PWM_LOW), PWM_HIGH) for value in values]

    def reset(self, *, seed=None, options=None):
        """Reset to the fixed initial state; the upstream reset takes no seed (BaseAviary.py:406), so it is unused."""
        self._reset_state()
        return self._observation()

    def step(self, action):
        """Advance one 240 Hz tick with the kinematic stand-in and return the upstream four-value tuple."""
        command = self._clip(action)
        # placeholder: fixed per-tick kinematics, not a force model
        mean = sum(command) / float(NUM_MOTORS)
        self._vel[2] += (mean - 0.5) * LIFT_GAIN
        self._rpy[2] += (command[0] + command[1] - command[2] - command[3]) * YAW_GAIN * TIMESTEP
        for axis in range(3):
            self._pos[axis] += self._vel[axis] * TIMESTEP
        self._last = command
        self._step_counter += 1
        self._state = self._observation()
        # CtrlAviary.py:278 (reward -1), :293 (done False) and :308-310 (info {"answer": 42})
        return self._observation(), -1, False, {"answer": 42}

    def close(self):
        """Terminate the environment; the fake holds no external resource."""
        self._state = None
