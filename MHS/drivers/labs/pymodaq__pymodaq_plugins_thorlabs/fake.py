"""Fake backend of the Thorlabs Kinesis brushless-motor driver: an in-memory stand-in for BrushlessDCMotor.

Gate G7: every public method defined here exists on
``pymodaq_plugins_thorlabs.hardware.kinesis:BrushlessDCMotor`` in the clone, with the same channel-index argument
the controller forwards to its ``BrushlessMotorChannel`` (kinesis.py:235-275): ``get_position(channel)``,
``get_target_position(channel)``, ``get_units(channel)``, ``is_homed(channel)``, ``move_abs(position, callback,
channel)``, ``home(channel, callback)``, ``stop(channel)`` and ``close()``.

The starting position, target, unit and homed flag are test data, each marked ``# placeholder``; they are not facts
about a controller or stage.  The fake moves instantly and does not model motion over time, polling, the Kinesis
controller status or the unit converter.  Nothing here talks to a device.
"""


class FakeBrushlessDCMotor:
    def __init__(self, **_options):
        self._position = {1: 0.0, 2: 0.0, 3: 0.0}   # placeholder start positions
        self._target = {1: 0.0, 2: 0.0, 3: 0.0}     # placeholder start targets
        self._homed = {1: False, 2: False, 3: False}  # placeholder homed flags
        self._units = "mm"                            # placeholder unit name
        self._stop_calls = 0                          # test data: how often the native stop was reached
        self.closed = False                           # test data: teardown reached the native close

    # -- the upstream controller surface the driver uses ---------------------------------------------------------
    def get_position(self, channel: int = 1) -> float:
        return self._position[channel]

    def get_target_position(self, channel: int = 1) -> float:
        return self._target[channel]

    def get_units(self, channel: int = 1) -> str:
        return self._units

    def is_homed(self, channel: int = 1) -> bool:
        return self._homed[channel]

    def move_abs(self, position: float, callback=None, channel: int = 1):
        self._target[channel] = float(position)
        self._position[channel] = float(position)   # the fake applies the move immediately
        self._homed[channel] = False

    def home(self, channel: int = 1, callback=None):
        self._position[channel] = 0.0               # placeholder home position
        self._target[channel] = 0.0
        self._homed[channel] = True

    def stop(self, channel: int = 1):
        self._stop_calls += 1

    def close(self):
        self.closed = True
