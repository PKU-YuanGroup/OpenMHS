"""Fake backend of the Kinesis driver: an in-memory stand-in for
``pylablib.devices.Thorlabs.kinesis:KinesisMotor``.

Gate G7: every public method defined here exists on KinesisMotor (or on one of its base classes in the clone:
KinesisDevice, BasicKinesisDevice and the ICommBackendWrapper of pylablib/core/devio/comm_backend.py), and the
signatures follow the upstream ones (kinesis.py:440-448, 491-499, 501-509, 517-546, 289-294, 224-241, 388-407).
The values are test data, never facts: the start position, the start velocity parameters, the model number and the
status strings are marked ``# placeholder`` and are not copied into a Fact, a Limit or the reference.  The fake moves
instantly, so reading the state twice gives the same state; nothing here talks to a device.
"""

import collections

_TDeviceInfo = collections.namedtuple(
    "TDeviceInfo", ["serial_no", "model_no", "fw_ver", "hw_type", "hw_ver", "mod_state", "nchannels", "notes"])
_TVelocityParameters = collections.namedtuple(
    "TVelocityParameters", ["min_velocity", "acceleration", "max_velocity"])


class FakeKinesisMotor:
    def __init__(self, **_options):
        self._position = 0              # placeholder: encoder steps at power-up
        self._moving = False
        self._homing = False
        self._homed = False
        self._min_velocity = 0          # the documented minimum of the APT velocity parameters (kinesis.py:522)
        self._acceleration = 5000       # placeholder: encoder steps per second^2
        self._max_velocity = 1000       # placeholder: encoder steps per second
        self._model_no = "KDC101"       # placeholder: a Kinesis controller model number
        self._closed = False

    # -- state the driver reads ---------------------------------------------------------------------------------
    def get_position(self, channel=None, scale=True):
        return float(self._position)

    def is_moving(self, channel=None):
        return self._moving

    def is_homing(self, channel=None):
        return self._homing

    def is_homed(self, channel=None):
        return self._homed

    def get_status(self, channel=None):
        status = ["connected", "enabled"]           # placeholder: a healthy status bit set
        if self._homing:
            status.append("homing")
        if self._homed:
            status.append("homed")
        if self._moving:
            status.append("moving_fw")              # placeholder: the direction of the simulated move
        return status

    def get_velocity_parameters(self, channel=None, scale=True):
        return _TVelocityParameters(self._min_velocity, self._acceleration, self._max_velocity)

    def get_device_info(self, dest="host"):
        # placeholder: a serial number, a firmware version and an empty notes field
        return _TDeviceInfo(12345678, self._model_no, "0.0.0", 0, 0, 0, 1, "")

    def get_number_of_channels(self):
        return 1                                    # placeholder: a single-channel controller

    # -- commands the driver sends ------------------------------------------------------------------------------
    def setup_velocity(self, min_velocity=None, acceleration=None, max_velocity=None, channel=None, scale=True):
        if min_velocity is not None:
            self._min_velocity = int(min_velocity)
        if acceleration is not None:
            self._acceleration = int(acceleration)
        if max_velocity is not None:
            self._max_velocity = int(max_velocity)
        return self.get_velocity_parameters()

    def home(self, sync=True, force=False, channel=None, timeout=None):
        self._homing = False
        self._homed = True

    def move_to(self, position, channel=None, scale=True):
        self._position = int(position)
        self._moving = False

    def stop(self, immediate=False, sync=True, channel=None, timeout=None):
        self._moving = False

    def close(self):
        self._closed = True
