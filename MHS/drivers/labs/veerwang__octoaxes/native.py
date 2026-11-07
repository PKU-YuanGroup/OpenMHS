"""Hardware backend: wrap hardware.serial_thread:SerialThread from the pinned Octoaxes clone.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The acceptance gate
runs the fake backend and never imports this module or the upstream software.  This package is
model-authored and unreviewed; no hardware run is claimed.

Deployment needs the upstream software/common directory on PYTHONPATH and the dependencies the upstream
README names (PyQt5, pyserial, crc; README.md:149).  The adapter starts SerialThread, listens to its
binary_response signal and keeps the last 24-byte position packet so get_status can publish x_um, y_um,
z_steps and moving to the driver.  The signal is emitted by the upstream reader thread
(serial_thread.py:201, 209); the upstream GUI connects it in the same way
(software/common/gui/main_window.py:581).

The adapter's public methods are the subset of SerialThread's surface the driver uses:
send_binary_command, is_connected, get_status and stop.
"""

import struct
import threading


def connect(port, baudrate=115200, **_options):
    """Open the serial port named by ``port`` through the upstream SerialThread."""
    return SerialBackend(port, baudrate=baudrate)


class SerialBackend:
    """A SerialThread plus the position snapshot parsed from its binary_response signal."""

    def __init__(self, port, baudrate=115200):
        from hardware.serial_thread import SerialThread

        self._thread = SerialThread(port=port, baudrate=baudrate)
        self._lock = threading.Lock()
        # Placeholder state until the first position broadcast arrives.
        self._steps = {"X": 0, "Y": 0, "Z": 0}
        self._moving = False
        self._illumination_port = ""
        self._illumination_percent = 0.0
        self._thread.binary_response.connect(self._on_binary_response)
        self._thread.start()

    def _on_binary_response(self, data):
        """Keep the last 24-byte packet: cmd_id, status, then X/Y/Z/W as big-endian int32."""
        if len(data) != 24:
            return
        x, y, z, w = struct.unpack(">4i", data[2:18])
        with self._lock:
            self._steps = {"X": x, "Y": y, "Z": z}
            self._moving = data[1] == 1

    # -- the SerialThread surface the driver uses ------------------------------------------------------
    def send_binary_command(self, binary_data):
        command = bytes(binary_data)
        accepted = bool(self._thread.send_binary_command(binary_data))
        if not accepted or len(command) < 8:
            return accepted
        if command[1] == 37:                        # SET_PORT_ILLUMINATION
            raw = (command[3] << 8) | command[4]
            with self._lock:
                self._illumination_port = f"D{command[2] + 1}"
                self._illumination_percent = round(raw / 65535.0 * 100.0, 6)
        elif command[1] == 39:                      # TURN_OFF_ALL_PORTS
            with self._lock:
                self._illumination_percent = 0.0
        return accepted

    def is_connected(self):
        return bool(self._thread.is_connected())

    def get_status(self):
        status = dict(self._thread.get_status())
        with self._lock:
            steps = dict(self._steps)
            moving = self._moving
            port = self._illumination_port
            percent = self._illumination_percent
        status.update({
            "x_um": steps["X"] * 2.54 / (200 * 256) * 1000.0,
            "y_um": steps["Y"] * 2.54 / (200 * 256) * 1000.0,
            "z_steps": steps["Z"],
            "moving": moving,
            "illumination_port": port,
            "illumination_percent": percent,
        })
        return status

    def stop(self):
        """De-energise X, Y, Z, W and Turret and turn every illumination port off."""
        for axis in (0, 1, 2, 5, 7):
            command = bytearray(8)
            command[1] = 32                     # SET_AXIS_DISABLE_ENABLE
            command[2] = axis
            command[3] = 0
            if not self._thread.send_binary_command(command):
                return False
        command = bytearray(8)
        command[1] = 39                         # TURN_OFF_ALL_PORTS
        if not self._thread.send_binary_command(command):
            return False
        with self._lock:
            self._moving = False
            self._illumination_percent = 0.0
        return True
