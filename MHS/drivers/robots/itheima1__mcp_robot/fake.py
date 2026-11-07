"""Fake backend of the mcp_robot driver: an in-memory stand-in for sources.servo_control_standalone:ServoControllerStandalone.

Gate G7: every public member defined here is a method of ServoControllerStandalone
(sources/servo_control_standalone.py at the pinned commit 18f9ea5ff42c6bf01bc16d659e422c048be6d312), with the
upstream parameter names.  Like the upstream, the read methods return degrees or None, the write methods return a
bool, and the bulk methods call the same lower-level methods the upstream uses.

What it does not do: it opens no serial port, sends no SCS frame, and models no motion over time (a servo's present
position becomes the goal position when the write returns).  The start positions, the torque state and the reply
timing are test data, each marked ``# placeholder``; nothing here is a fact about an arm.  The commands it received
are kept in ``_commands`` and two underscore hooks let a test force a failure or place a servo.
"""

#: Placeholder start positions, one per servo ID 1 to 6, in SCS position units (0-4095): all at 90 degrees.
_START_POSITIONS = (2048, 2048, 2048, 2048, 2048, 2048)  # placeholder
#: Placeholder home pose of go_home in degrees, servo IDs 1 to 6 in order (CLONE:922-929).
_HOME_ANGLES = (90, 0, 180, 180, 90, 90)  # placeholder


class FakeServoControllerStandalone:
    def __init__(self, port_name="COM4", baudrate=1000000, timeout=0.1, debug=False):
        self.port_name = port_name
        self.baudrate = baudrate
        self.timeout = timeout
        self.debug = debug
        self.serial_port = None
        self.is_open = True
        self._positions = {servo_id: _START_POSITIONS[servo_id - 1] for servo_id in range(1, 7)}  # placeholder
        self._torque = {servo_id: True for servo_id in range(1, 7)}  # placeholder
        self._speed = 0
        self._commands = []
        self._failing = set()

    # -- state ----------------------------------------------------------------------------------------------------
    def close(self):
        self.is_open = False
        self._record("close")

    # -- reads (degrees, or None on a failed read) ----------------------------------------------------------------
    def get_servo_angle(self, servo_id):
        self._record("get_servo_angle", servo_id=servo_id)
        if self._fail("get_servo_angle") or not self.is_open or servo_id not in self._positions:
            return None
        return self._degrees(servo_id)

    def get_multiple_servo_angles(self, servo_ids):
        self._record("get_multiple_servo_angles", servo_ids=list(servo_ids))
        if self._fail("get_multiple_servo_angles") or not self.is_open:
            return {servo_id: None for servo_id in servo_ids}
        positions = self.sync_read_positions(servo_ids)
        angles = {}
        for servo_id, position in positions.items():
            angles[servo_id] = None if position is None else (position - 1024) * 180 / 2048
        return angles

    def read_position(self, servo_id):
        self._record("read_position", servo_id=servo_id)
        if self._fail("read_position") or not self.is_open or servo_id not in self._positions:
            return None
        return self._positions[servo_id]

    def read_positions(self, servo_ids):
        self._record("read_positions", servo_ids=list(servo_ids))
        return {servo_id: self.read_position(servo_id) for servo_id in servo_ids}

    def sync_read_positions(self, servo_ids):
        self._record("sync_read_positions", servo_ids=list(servo_ids))
        if self._fail("sync_read_positions"):
            return self.read_positions(servo_ids)
        if not self.is_open:
            return {servo_id: None for servo_id in servo_ids}
        return {servo_id: self._positions.get(servo_id) for servo_id in servo_ids}

    # -- position writes (bool) ------------------------------------------------------------------------------------
    def set_servo_angle(self, servo_id, angle, speed=0):
        self._record("set_servo_angle", servo_id=servo_id, angle=angle, speed=speed)
        if self._fail("set_servo_angle"):
            return False
        position = int(1024 + angle * 2048 / 180)
        position = max(1024, min(3072, position))
        return self.set_position(servo_id, position, speed)

    def set_multiple_servo_angles(self, angles, speed=0):
        self._record("set_multiple_servo_angles", angles=dict(angles), speed=speed)
        if self._fail("set_multiple_servo_angles"):
            return False
        positions = {}
        for servo_id, angle in angles.items():
            position = int(1024 + angle * 2048 / 180)
            positions[servo_id] = max(1024, min(3072, position))
        return self.sync_set_positions(positions, speed)

    def set_position(self, servo_id, position, speed=0):
        self._record("set_position", servo_id=servo_id, position=position, speed=speed)
        if self._fail("set_position") or not self.is_open:
            return False
        position = max(0, min(4095, position))
        self._speed = max(0, min(32767, speed))
        self._positions[servo_id] = position
        return True

    def set_positions(self, positions, speed=0):
        self._record("set_positions", positions=dict(positions), speed=speed)
        results = {}
        for servo_id, position in positions.items():
            results[servo_id] = self.set_position(servo_id, position, speed)
        return results

    def sync_set_positions(self, positions, speed=0):
        self._record("sync_set_positions", positions=dict(positions), speed=speed)
        if self._fail("sync_set_positions"):
            return all(self.set_positions(positions, speed).values())
        if not self.is_open:
            return False
        self._speed = max(0, min(32767, speed))
        for servo_id, position in positions.items():
            self._positions[servo_id] = max(0, min(4095, position))
        return True

    # -- torque (bool) ---------------------------------------------------------------------------------------------
    def enable_torque(self, servo_id):
        self._record("enable_torque", servo_id=servo_id)
        if self._fail("enable_torque") or not self.is_open:
            return False
        self._torque[servo_id] = True
        return True

    def disable_torque(self, servo_id):
        self._record("disable_torque", servo_id=servo_id)
        if self._fail("disable_torque") or not self.is_open:
            return False
        self._torque[servo_id] = False
        return True

    def sync_enable_torque(self, servo_ids):
        self._record("sync_enable_torque", servo_ids=list(servo_ids))
        if self._fail("sync_enable_torque"):
            return all(self.enable_torque(servo_id) for servo_id in servo_ids)
        if not self.is_open:
            return False
        for servo_id in servo_ids:
            self._torque[servo_id] = True
        return True

    def sync_disable_torque(self, servo_ids):
        self._record("sync_disable_torque", servo_ids=list(servo_ids))
        if self._fail("sync_disable_torque"):
            return all(self.disable_torque(servo_id) for servo_id in servo_ids)
        if not self.is_open:
            return False
        for servo_id in servo_ids:
            self._torque[servo_id] = False
        return True

    # -- home (bool) -----------------------------------------------------------------------------------------------
    def go_home(self, speed=0):
        self._record("go_home", speed=speed)
        if self._fail("go_home"):
            return False
        positions = {}
        for servo_id, angle in zip(range(1, 7), _HOME_ANGLES):
            positions[servo_id] = int(1024 + angle * 2048 / 180)
        return self.sync_set_positions(positions, speed)

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _degrees(self, servo_id):
        position = self._positions[servo_id]
        return (position - 1024) * 180 / 2048

    def _record(self, name, **arguments):
        self._commands.append((name, arguments))

    def _fail(self, name):
        if name not in self._failing:
            return False
        self._failing.remove(name)
        return True

    # -- hooks for test_driver.py (not upstream members, never used by the driver) ----------------------------------
    def _force_failure(self, name):
        """Make the next call of ``name`` fail (the method's native failure result)."""
        self._failing.add(name)

    def _set_present(self, servo_id, position):
        """Place a servo at ``position`` without a command (the fake's read-back state)."""
        self._positions[servo_id] = int(position)
