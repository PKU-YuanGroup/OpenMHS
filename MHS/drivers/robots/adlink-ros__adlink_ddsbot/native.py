"""Hardware backend: a Python 3 port of the serial path of script/base_control.py:BaseControl.

The pinned clone's node is Python 2 source (``string.split(line, ',')``, base_control.py:69) and its constructor starts
ROS subscribers, publishers and two 10 Hz timers.  This in-process driver needs only the serial frame, the
differential-drive conversion and the reply parse, so this module ports those parts and opens pyserial itself.  The
port is not the upstream node: it does not publish ``base_odom`` and it does not subscribe to ``cmd_vel``.

Used only with backend="hardware" and allow_hardware=True after a human hardware review; the acceptance gate runs the
fake backend and never imports this module.  No hardware backend has been run for this package.
"""

import math


class BaseControlLink:
    """The serial transport the driver expects: members named after BaseControl's serial-facing members."""

    def __init__(self, port="/dev/uno", baudrate=57600, wheel_separation=0.15, wheel_radius=0.0335,
                 timeout_s=0.2, **_options):
        import serial

        self.serial = serial.Serial(port, int(baudrate), timeout=float(timeout_s))
        self.wheelSep = float(wheel_separation)
        self.wheelRad = float(wheel_radius)
        self.trans_x = 0.0
        self.rotat_z = 0.0
        self.WL_send = 0.0
        self.WR_send = 0.0
        # The driver's setup() expects the upstream timer attributes; this port starts no ROS timers.
        self.timer_odom = None
        self.timer_cmd = None

    def cmdCB(self, data):
        self.trans_x = data.linear.x
        self.rotat_z = data.angular.z

    def timerCmdCB(self, event):
        # The same conversion and frame as base_control.py:117-125.
        right = self.trans_x + self.wheelSep / 2.0 * self.rotat_z
        left = self.trans_x - self.wheelSep / 2.0 * self.rotat_z
        self.WR_send = right / self.wheelRad * 180.0 / math.pi
        self.WL_send = left / self.wheelRad * 180.0 / math.pi
        values = [str(self.WL_send), str(self.WR_send), "0"]
        values[2] = str(len(values[0]) + len(values[1]))
        command = ",".join(values).encode()
        self.serial.flushInput()
        self.serial.write(command)


def connect(**options):
    """Open the serial link; port, baud rate and wheel geometry are deployment options."""
    return BaseControlLink(**options)
