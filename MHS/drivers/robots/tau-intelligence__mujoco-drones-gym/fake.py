"""Fake backend of the muJoCo-drones-gym driver: a pure Python stand-in for ``HoverAviary``.

Why a fake: the acceptance gate neither installs MuJoCo nor imports the clone, and package code never imports the
clone.  This module re-implements the observable contract of
``multi_drone_mujoco.envs.hover_aviary:HoverAviary`` (the class the driver names as ``native``): a 4-element Box
action of normalized RPM commands in [-1, 1], a 12-element observation (position, roll-pitch-yaw, linear velocity,
angular velocity), the hover reward, the crash/flip altitude and attitude limits, the 10 s truncation and the
position/height-error info dict.  Every constant and rule that comes from the clone cites its line at the pinned
commit ca170dc6760d422e47ef46fb3af46f8cd20410eb.

The dynamics are not the upstream MuJoCo model.  This fake integrates a small kinematic stand-in: the mean action is
a vertical acceleration around hover and the motor differences are angular rates.  The gains are test data, marked
``# placeholder`` below; they are not upstream facts and are not used in any Fact, Limit or reference.  Differences
from upstream, all in the fidelity ``gaps`` of the driver: no MuJoCo rigid-body contacts, thrust/torque actuator,
ground effect, drag, downwash, wind, obstacles or sensors, and no comparison with the upstream environment.  The
public methods are the ones HoverAviary has (``reset``, ``step``, ``close``; gate G7).

Nothing here talks to a device.
"""

import math

# multi_drone_mujoco/envs/hover_aviary.py:22-23 (constructor defaults of sim_freq and ctrl_freq)
SIM_FREQ = 240
CTRL_FREQ = 48
# multi_drone_mujoco/envs/hover_aviary.py:32 (EPISODE_LEN_SEC)
EPISODE_LEN_SEC = 10
# multi_drone_mujoco/envs/hover_aviary.py:27, 31 (target_height = 1.0)
DEFAULT_TARGET_HEIGHT = 1.0
# multi_drone_mujoco/envs/hover_aviary.py:33-34 (the default initial position)
DEFAULT_INITIAL_XYZ = (0.0, 0.0, 0.1)
# multi_drone_mujoco/envs/hover_aviary.py:105-110 (the termination thresholds)
MIN_ALTITUDE = 0.0
MAX_ALTITUDE = 3.0
MAX_ROLL_PITCH = math.pi / 2
# fake-only dynamics gains: test data, not upstream facts
ACCEL_GAIN = 2.0                                # placeholder
ANGULAR_GAIN = 2.0                              # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeHoverAviary:
    """HoverAviary without MuJoCo: ``reset(seed, options)`` and ``step(action)`` return what the Gymnasium env does."""

    def __init__(
        self,
        drone_model=None,
        physics=None,
        sim_freq=SIM_FREQ,
        ctrl_freq=CTRL_FREQ,
        gui=False,
        record=False,
        obstacles=False,
        target_height=DEFAULT_TARGET_HEIGHT,
        initial_xyzs=None,
        render_mode=None,
    ):
        if sim_freq % ctrl_freq != 0:                       # base_aviary.py:350-351
            raise ValueError("sim_freq must be divisible by ctrl_freq")
        self.SIM_FREQ = int(sim_freq)
        self.CTRL_FREQ = int(ctrl_freq)
        self.SIM_STEPS_PER_CTRL = int(sim_freq / ctrl_freq)  # base_aviary.py:352
        self.CTRL_TIMESTEP = 1.0 / ctrl_freq                # base_aviary.py:353
        self.SIM_TIMESTEP = 1.0 / sim_freq                  # base_aviary.py:354
        self.EPISODE_LEN_SEC = EPISODE_LEN_SEC
        self.TARGET_HEIGHT = float(target_height)
        self.NUM_DRONES = 1
        self.render_mode = render_mode
        self._closed = False
        if initial_xyzs is None:
            initial_xyzs = [DEFAULT_INITIAL_XYZ]
        rows = list(initial_xyzs)
        if rows and hasattr(rows[0], "__len__") and not isinstance(rows[0], (str, bytes)):
            first = list(rows[0])
        else:
            first = rows
        self.INIT_XYZS = [float(value) for value in first[:3]]
        if len(self.INIT_XYZS) != 3:
            raise ValueError("initial_xyzs must give one position with 3 coordinates")
        # hover_aviary.py:51-53: Box(low=-1, high=1) for the four motors
        self.action_space = Box([-1.0] * 4, [1.0] * 4)
        # hover_aviary.py:55-60: a 12-element unbounded observation
        self.observation_space = Box([-math.inf] * 12, [math.inf] * 12)
        self.pos = list(self.INIT_XYZS)
        self.rpy = [0.0, 0.0, 0.0]
        self.vel = [0.0, 0.0, 0.0]
        self.ang_v = [0.0, 0.0, 0.0]
        self.last_clipped_action = [0.0, 0.0, 0.0, 0.0]
        self.step_counter = 0
        self.seed = None

    def reset(self, seed=None, options=None):
        """Reset the pose and counters (base_aviary.py:490-524); ``options`` is accepted and unused upstream too."""
        self.seed = seed
        self.pos = list(self.INIT_XYZS)
        self.rpy = [0.0, 0.0, 0.0]
        self.vel = [0.0, 0.0, 0.0]
        self.ang_v = [0.0, 0.0, 0.0]
        self.last_clipped_action = [0.0, 0.0, 0.0, 0.0]
        self.step_counter = 0
        return self._computeObs(), self._computeInfo()

    def step(self, action):
        """Advance one control step with a kinematic stand-in for the MuJoCo dynamics (base_aviary.py:528-598)."""
        try:
            values = [float(value) for value in action]
        except TypeError as exc:
            raise ValueError("action must be a sequence of 4 normalized RPM values") from exc
        if len(values) != 4:
            raise ValueError("action must contain 4 normalized RPM values")
        values = [max(-1.0, min(1.0, value)) for value in values]       # hover_aviary.py:64
        self.last_clipped_action = values

        mean = sum(values) / 4.0
        roll_cmd = ((values[0] + values[2]) - (values[1] + values[3])) / 4.0
        pitch_cmd = ((values[0] + values[1]) - (values[2] + values[3])) / 4.0
        yaw_cmd = ((values[0] + values[3]) - (values[1] + values[2])) / 4.0
        dt = self.CTRL_TIMESTEP

        # placeholder kinematics: no thrust/torque model, no contacts
        self.vel[0] += ACCEL_GAIN * math.sin(self.rpy[1]) * dt
        self.vel[1] -= ACCEL_GAIN * math.sin(self.rpy[0]) * dt
        self.vel[2] += ACCEL_GAIN * mean * dt
        self.ang_v = [ANGULAR_GAIN * roll_cmd, ANGULAR_GAIN * pitch_cmd, ANGULAR_GAIN * yaw_cmd]
        for axis in range(3):
            self.pos[axis] += self.vel[axis] * dt
            self.rpy[axis] += self.ang_v[axis] * dt

        # base_aviary.py:585: one control step is SIM_STEPS_PER_CTRL physics sub-steps
        self.step_counter += self.SIM_STEPS_PER_CTRL
        return (self._computeObs(), self._computeReward(), self._computeTerminated(),
                self._computeTruncated(), self._computeInfo())

    def close(self):
        """Close the environment: the fake has no renderer or model to release."""
        self._closed = True

    def _computeObs(self):
        """12 values: pos(3), rpy(3), vel(3), ang_v(3) (hover_aviary.py:68-73)."""
        return [float(value) for value in self.pos + self.rpy + self.vel + self.ang_v]

    def _computeReward(self):
        """The hover reward of hover_aviary.py:83-95."""
        height_error = abs(self.pos[2] - self.TARGET_HEIGHT)
        xy_error = math.hypot(self.pos[0], self.pos[1])
        speed = math.sqrt(sum(value * value for value in self.vel))
        reward = -height_error - 0.1 * xy_error
        reward -= 0.05 * speed
        reward -= 0.05 * (abs(self.rpy[0]) + abs(self.rpy[1]))
        if height_error < 0.05 and xy_error < 0.05:
            reward += 1.0
        if self._computeTerminated():
            reward -= 100.0
        return float(reward)

    def _computeTerminated(self):
        """Crash, flip or fly away (hover_aviary.py:99-111)."""
        if self.pos[2] < MIN_ALTITUDE:
            return True
        if abs(self.rpy[0]) > MAX_ROLL_PITCH or abs(self.rpy[1]) > MAX_ROLL_PITCH:
            return True
        if self.pos[2] > MAX_ALTITUDE:
            return True
        return False

    def _computeTruncated(self):
        """Truncate at EPISODE_LEN_SEC of simulated time (hover_aviary.py:113-115)."""
        return self.step_counter / self.SIM_FREQ >= self.EPISODE_LEN_SEC

    def _computeInfo(self):
        """The info dict of hover_aviary.py:117-121."""
        return {"position": list(self.pos), "height_error": abs(self.pos[2] - self.TARGET_HEIGHT)}
