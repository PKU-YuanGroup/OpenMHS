"""Fake backend of the Go2 driver: an in-memory stand-in for Go2Py.robot.interface:GO2Real.

Gate G7: every public member defined here is a method of GO2Real (Go2Py/robot/interface.py at the pinned commit
eff240b82b0ff6dae6ba5ee934a381f38fe64c0d), with the upstream parameter names.  The getters return the dictionaries
the upstream methods return (interface.py:94-111, 159-161), and setCommandsHigh / setCommandsLow record the command
the way the upstream writers would publish it.

Every number below is test data, marked ``# placeholder``; none of it is a fact, a limit or a citation.  The fake
has no DDS, no state thread, no bridge and no motion over time: a low-level command updates the reported joint
state at once, and a high-level command is only recorded.  Nothing here talks to a robot.
"""

# placeholder: stand-in joint state, angles in rad, velocities in rad/s, torques in N.m and temperatures in Cel
_START_Q = [0.0] * 12
_START_DQ = [0.0] * 12
_START_TAU = [0.0] * 12
_START_TEMPERATURE = [25.0] * 12
_START_ACCEL = [0.0, 0.0, 9.81]  # placeholder
_START_GYRO = [0.0, 0.0, 0.0]  # placeholder
_START_QUAT = [0.0, 0.0, 0.0, 1.0]  # placeholder, x y z w
_START_IMU_TEMPERATURE = 25.0  # placeholder
_START_CONTACT = [0.0, 0.0, 0.0, 0.0]  # placeholder
_START_SOC = 100.0  # placeholder


class FakeGo2Real:
    def __init__(self, interface_name=None, mode="lowlevel", vx_max=0.5, vy_max=0.4, wz_max=0.5):
        self._q = list(_START_Q)
        self._dq = list(_START_DQ)
        self._tau = list(_START_TAU)
        self._temperature = list(_START_TEMPERATURE)
        self._accel = list(_START_ACCEL)
        self._gyro = list(_START_GYRO)
        self._quat = list(_START_QUAT)
        self._imu_temperature = _START_IMU_TEMPERATURE
        self._contact = list(_START_CONTACT)
        self._soc = _START_SOC
        self._high_commands = []  # (v_x, v_y, omega_z)
        self._low_commands = []   # (q_des, dq_des, kp, kd, tau_ff) as lists
        self._closed = False

    # -- state reads (interface.py:94-111, 159-161) -------------------------------------------------------------
    def getJointStates(self):
        return {
            "q": list(self._q),
            "dq": list(self._dq),
            "tau_est": list(self._tau),
            "temperature": list(self._temperature),
        }

    def getIMU(self):
        return {
            "accel": list(self._accel),
            "gyro": list(self._gyro),
            "quat": list(self._quat),
            "temp": self._imu_temperature,
        }

    def getFootContacts(self):
        return list(self._contact)

    def getBatteryState(self):
        return self._soc

    # -- commands (interface.py:163-190) -------------------------------------------------------------------------
    def setCommandsHigh(self, v_x, v_y, omega_z, bodyHeight=0.0, footRaiseHeight=0.0, mode=2):
        self._high_commands.append((float(v_x), float(v_y), float(omega_z)))

    def setCommandsLow(self, q_des, dq_des, kp, kd, tau_ff):
        self._low_commands.append((
            [float(value) for value in q_des],
            [float(value) for value in dq_des],
            [float(value) for value in kp],
            [float(value) for value in kd],
            [float(value) for value in tau_ff],
        ))
        self._q = [float(value) for value in q_des]
        self._dq = [float(value) for value in dq_des]
        self._tau = [float(value) for value in tau_ff]

    def close(self):
        self._closed = True
