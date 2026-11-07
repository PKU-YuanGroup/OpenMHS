"""Fake backend of the Octoaxes driver: an in-memory stand-in for hardware.serial_thread:SerialThread.

Gate G7: every public method here exists on hardware.serial_thread:SerialThread in
software/common/hardware/serial_thread.py (send_binary_command, is_connected, get_status and stop).
The fake keeps the axis microstep counters and the illumination ports in plain instance attributes and
answers get_status with the same keys the hardware adapter publishes: x_um, y_um, z_steps and moving.

The fake receives the 8-byte payload the driver builds, exactly as SerialThread.send_binary_command
receives it from the upstream GUI.  SerialThread itself prefixes 0x02 and appends the CRC-8-CCITT byte
(serial_thread.py:375-383); the fake does not need that transport framing to interpret the command id in
byte 1 and the payload in bytes 2 to 6.  Starting positions and port values are test data, not facts.
"""

import struct

#: The same conversion the upstream AXIS_MM_PER_STEP table builds for X and Y
#: (software/octoaxes/constants.py:63-64, 80-81, 168-173).
_MM_PER_STEP = {
    "X": 2.54 / (200 * 256),
    "Y": 2.54 / (200 * 256),
}

_MOVETO = {6: "X", 7: "Y", 8: "Z"}


class FakeSerialThread:
    """A serial-thread stand-in that answers the position and illumination commands of the driver."""

    def __init__(self, **_options):
        # Placeholder test state: a freshly homed stage would report different values.
        self._steps = {"X": 0, "Y": 0, "Z": 0}       # placeholder
        self._enabled = {0: False, 1: False, 2: False, 5: False, 7: False}  # placeholder
        self._ports = {index: {"percent": 0, "on": False} for index in range(5)}  # placeholder
        self._last_port = ""                          # placeholder
        self._last_percent = 0.0                      # placeholder
        self._moving = False                          # placeholder
        self._running = True
        self._port_open = True
        self.commands = []

    # -- SerialThread surface -------------------------------------------------------------------------
    def send_binary_command(self, binary_data):
        """Accept one 8-byte payload and update the fake state (True like the upstream send path)."""
        if len(binary_data) < 8:
            return False
        command = bytes(binary_data)
        self.commands.append(command)
        command_id = command[1]
        if command_id in _MOVETO:
            self._steps[_MOVETO[command_id]] = struct.unpack(">i", command[2:6])[0]
            self._moving = False
        elif command_id == 32:                       # SET_AXIS_DISABLE_ENABLE
            self._enabled[command[2]] = command[3] != 0
            if command[3] == 0:
                self._moving = False
        elif command_id == 37:                       # SET_PORT_ILLUMINATION
            raw = (command[3] << 8) | command[4]
            percent = int(round(raw / 65535.0 * 100.0))
            self._ports[command[2]] = {"percent": percent, "on": command[5] != 0}
            self._last_port = f"D{command[2] + 1}"
            self._last_percent = float(percent)
        elif command_id == 39:                       # TURN_OFF_ALL_PORTS
            for port in self._ports:
                self._ports[port]["on"] = False
            self._last_percent = 0.0
        return True

    def is_connected(self):
        return self._running and self._port_open

    def get_status(self):
        return {
            "running": self._running,
            "port_open": self._port_open,
            "x_um": self._steps["X"] * _MM_PER_STEP["X"] * 1000.0,
            "y_um": self._steps["Y"] * _MM_PER_STEP["Y"] * 1000.0,
            "z_steps": self._steps["Z"],
            "moving": self._moving,
            "illumination_port": self._last_port,
            "illumination_percent": self._last_percent,
        }

    def stop(self):
        """De-energise every axis and turn every illumination port off (the safe state)."""
        self._moving = False
        for axis in self._enabled:
            self._enabled[axis] = False
        for port in self._ports:
            self._ports[port]["on"] = False
        self._last_percent = 0.0
        return True
