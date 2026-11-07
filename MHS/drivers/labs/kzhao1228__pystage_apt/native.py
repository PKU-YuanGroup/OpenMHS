"""Hardware backend: opens a Thorlabs APT single-channel controller through the upstream serial port.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed; the acceptance gate runs the fake backend and never imports this module, the upstream package or the
serial port.  It does not claim a loader refusal: this driver is R1, and the loader's refusal of an unreviewed
model-written package applies only at R2 and R3.

Options of the backend: ``port`` (required) is the serial device of the controller (for example /dev/ttyUSB0) and
``serial_number`` (required) is the serial number of that controller.  ``channel`` (default 1) is the APT channel
identity 0x01; the upstream MotorCtrl reads it as chan_ident (stage/motor_ctrl/__init__.py:9-21).  The upstream
serial line is 115200 baud, 8N1, with RTS/CTS (stage/motor_ini/port.py:40-44).  ``Port.create`` selects the
SingleControllerPort or the unsupported CardSlotPort from the serial-number prefix (stage/motor_ini/port.py:196-210).

MotorCtrl has no stop method, so the returned object gets a port wrapper whose stop() sends the documented APT
MGMSG_MOT_MOVE_STOP message (stage/ctrl_msg/motorcontrol.py:691-703).  The wrapper forwards every other port
attribute to the real port, so the MotorCtrl methods keep working unchanged.
"""


class _StopPort:
    """Forward to the upstream port and add the stop() the driver's @estop uses."""

    def __init__(self, port, channel):
        self._port = port
        self._channel = channel

    def __getattr__(self, name):
        return getattr(self._port, name)

    def stop(self, stop_mode=0x01):
        from stage.ctrl_msg import MGMSG_MOT_MOVE_STOP

        self._port.send_message(MGMSG_MOT_MOVE_STOP(chan_ident=self._channel, stop_mode=stop_mode))


def connect(port, serial_number, channel=1, **options):
    from stage.motor_ini.port import Port

    controller = Port.create(port, str(serial_number))
    stages = controller.get_stages([channel])
    stage = stages[channel]
    stage._port = _StopPort(stage._port, channel)
    return stage
