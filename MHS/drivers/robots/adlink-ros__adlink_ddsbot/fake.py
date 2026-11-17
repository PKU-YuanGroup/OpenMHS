"""Analytic fake backend of the ADLINK DDSBot base: the serial path of script/base_control.py:BaseControl.

This is not a recording and not the upstream simulator.  It reproduces the upstream class's members and the wire
frame the node writes (``left,right,checksum``); reads return ``0,0`` as the pinned ``odom_pub=false`` firmware does,
even after a nonzero command. It does not model motor dynamics, steering corrections or the firmware's report timer.
Writes update the stored request immediately, while reads remain placeholder zeros. Every number below is fake placeholder
data, not a device fact.

Gate G7 checks every public member here against script/base_control.py:BaseControl.
"""

import math


class _FakeSerial:
    """A pyserial-shaped transport with the pinned firmware's non-sensing zero reply."""

    def __init__(self):
        self.timeout = 0.2                      # placeholder: the driver's bounded read
        self._reply = "0,0\r\n"                 # placeholder: the firmware's idle reply
        self._left = 0.0                        # placeholder
        self._right = 0.0                       # placeholder
        self.last_command = ""                  # placeholder: the last accepted frame

    def flushInput(self):
        pass

    def write(self, data):
        text = data.decode("ascii") if isinstance(data, bytes) else str(data)
        parts = text.split(",")
        if len(parts) != 3:
            return len(data)
        try:
            float(parts[0])
            float(parts[1])
            checksum = int(float(parts[2]))
        except ValueError:
            return len(data)
        if checksum != len(parts[0]) + len(parts[1]):
            return len(data)                    # the firmware ignores it, but the host wrote the bytes
        self.last_command = text
        self._left = float(parts[0])
        self._right = float(parts[1])
        self._reply = "0,0\r\n"                  # placeholder: odom_pub=false, independent of motion
        return len(data)

    def readline(self):
        return self._reply

    def close(self):
        pass


class FakeBaseControl:
    """The fake native peer; every public member exists on the upstream BaseControl class."""

    def __init__(self, **_options):
        self.serial = _FakeSerial()
        self.wheelSep = 0.15                    # placeholder: launch default, not a device bound
        self.wheelRad = 0.0335                  # placeholder: launch default, not a device bound
        self.trans_x = 0.0                      # placeholder: initial twist
        self.rotat_z = 0.0                      # placeholder: initial twist
        self.WL_send = 0.0                      # placeholder
        self.WR_send = 0.0                      # placeholder
        self.timer_odom = None
        self.timer_cmd = None

    def cmdCB(self, data):
        self.trans_x = data.linear.x
        self.rotat_z = data.angular.z

    def timerCmdCB(self, event):
        # The same conversion and frame as script/base_control.py:117-125.
        right = self.trans_x + self.wheelSep / 2.0 * self.rotat_z
        left = self.trans_x - self.wheelSep / 2.0 * self.rotat_z
        self.WR_send = right / self.wheelRad * 180.0 / math.pi
        self.WL_send = left / self.wheelRad * 180.0 / math.pi
        values = [str(self.WL_send), str(self.WR_send), "0"]
        values[2] = str(len(values[0]) + len(values[1]))
        command = ",".join(values).encode()
        self.serial.flushInput()
        self.serial.write(command)
