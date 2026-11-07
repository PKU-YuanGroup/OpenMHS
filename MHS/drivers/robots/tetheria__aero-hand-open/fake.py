"""ROS-free fake backend for the Aero Hand Open SDK surface.

The fake keeps the public attributes and method signatures the driver uses from
``aero_open_sdk.aero_hand:AeroHand``.  It opens no serial port, speaks no firmware
frame and runs no physics; every value below is test data, not a device fact.
The actuator and joint arrays are placeholder stand-ins derived from the last
command so that reads change with writes; they do not reproduce the tendon
kinematics.  The upstream ``set_joint_positions`` and ``set_actuations`` clamp to
the same constant arrays, and the fake does too.

Two write-failure switches follow the upstream: ``fail_joint_write`` raises, as a
serial error other than a timeout propagates from ``ser.write``; ``timeout_write``
returns None and changes nothing, as both setters catch a ``SerialTimeoutException``,
print it and return (sdk/src/aero_open_sdk/aero_hand.py:163-167, :223-227).
"""


class FakeAeroHand:
    def __init__(self, **_options):
        # Placeholder limits and names copied only as test data for the fake.
        self.joint_names = (
            "thumb_cmc_abd", "thumb_cmc_flex", "thumb_mcp", "thumb_ip",
            "index_mcp_flex", "index_pip", "index_dip",
            "middle_mcp_flex", "middle_pip", "middle_dip",
            "ring_mcp_flex", "ring_pip", "ring_dip",
            "pinky_mcp_flex", "pinky_pip", "pinky_dip",
        )  # placeholder
        self.joint_lower_limits = (0.0,) * 16  # placeholder
        self.joint_upper_limits = (
            100.0, 55.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0,
            90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0,
        )  # placeholder
        self.actuation_names = (
            "thumb_cmc_abd_act", "thumb_cmc_flex_act", "thumb_tendon_act",
            "index_tendon_act", "middle_tendon_act", "ring_tendon_act", "pinky_tendon_act",
        )  # placeholder
        self.actuation_lower_limits = (0.0, 0.0, -15.2789, 0.0, 0.0, 0.0, 0.0)  # placeholder
        self.actuation_upper_limits = (
            100.0, 104.125, 247.15, 288.1603, 288.1603, 288.1603, 288.1603,
        )  # placeholder
        self._joints = [4.0, 5.0, 8.0, 9.0, 7.0, 6.0, 5.0]  # placeholder start pose
        self._actuations = [4.0, 5.0, 8.0, 9.0, 7.0, 6.0, 5.0]  # placeholder start pose
        self._speeds = [32766] * 7  # placeholder
        self._torques = [700] * 7  # placeholder
        self._currents = [12.0, 14.0, 20.0, 18.0, 16.0, 13.0, 11.0]  # placeholder
        self._temperatures = [31.0, 32.0, 33.0, 32.0, 31.0, 30.0, 30.0]  # placeholder
        self.fail_actuations = False  # placeholder negative-path switch
        self.fail_joint_write = False  # placeholder negative-path switch
        self.timeout_write = False  # placeholder negative-path switch: the swallowed write timeout
        self.fail_calibrate = False  # placeholder negative-path switch
        self.closed = False

    # -- reads -----------------------------------------------------------------------------------------------
    def get_actuations(self):
        if self.fail_actuations:
            return None
        return list(self._actuations)

    def get_joint_positions_compact(self):
        if self.fail_actuations:
            return None
        return list(self._joints)

    def get_actuator_speeds(self):
        return list(self._speeds) if not self.fail_actuations else None

    def get_actuator_currents(self):
        return list(self._currents) if not self.fail_actuations else None

    def get_actuator_temperatures(self):
        return list(self._temperatures) if not self.fail_actuations else None

    # -- writes ----------------------------------------------------------------------------------------------
    def set_joint_positions(self, positions):
        if self.fail_joint_write:
            raise RuntimeError("placeholder serial write failure")
        if self.timeout_write:
            return None  # the upstream prints the SerialTimeoutException and returns
        values = [float(value) for value in positions]
        if len(values) == 7:
            values = [
                values[0], values[1], values[2], values[2],
                values[3], values[3], values[3],
                values[4], values[4], values[4],
                values[5], values[5], values[5],
                values[6], values[6], values[6],
            ]  # placeholder expansion, matching the upstream compact conversion
        if len(values) != 16:
            raise ValueError("placeholder: expected 16 joint positions")
        values = [
            max(self.joint_lower_limits[index], min(values[index], self.joint_upper_limits[index]))
            for index in range(16)
        ]
        self._joints = [values[0], values[1], values[2], values[4], values[7], values[10], values[13]]
        # Placeholder projection: the fake does not model the tendon kinematics.
        self._actuations = list(self._joints)

    def set_actuations(self, actuations):
        if self.timeout_write:
            return None  # the upstream prints the SerialTimeoutException and returns
        values = [float(value) for value in actuations]
        if len(values) != 7:
            raise ValueError("placeholder: expected 7 actuations")
        values = [
            max(self.actuation_lower_limits[index], min(values[index], self.actuation_upper_limits[index]))
            for index in range(7)
        ]
        self._actuations = values
        # Placeholder projection: the fake does not model the tendon kinematics.
        self._joints = list(values)

    def set_speed(self, id, speed):
        if not 0 <= id <= 6:
            raise ValueError("placeholder: actuator id 0..6")
        if not 0 <= speed <= 32766:
            raise ValueError("placeholder: speed 0..32766")
        self._speeds[id] = int(speed)
        return {"Servo ID": int(id), "Speed": int(speed)}

    def set_torque(self, id, torque):
        if not 0 <= id <= 6:
            raise ValueError("placeholder: actuator id 0..6")
        if not 0 <= torque <= 1000:
            raise ValueError("placeholder: torque 0..1000")
        self._torques[id] = int(torque)
        return {"Servo ID": int(id), "Torque": int(torque)}

    def calibrate_mid(self, id):
        if self.fail_calibrate:
            raise RuntimeError("placeholder calibration refusal")
        if not 0 <= id <= 6:
            raise ValueError("placeholder: actuator id 0..6")
        present_raw = 2048 + int(id)  # placeholder
        return {"Servo ID": int(id), "Present Raw": present_raw, "Present U16": present_raw // 2}  # placeholder

    def close(self):
        self.closed = True
