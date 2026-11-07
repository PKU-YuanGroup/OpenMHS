"""Fake backend of the C3000 driver: an in-memory stand-in for the PyLabware C3000SyringePump.

Gate G7: every public method defined here exists on
``PyLabware.devices.tricontinent_c3000:C3000SyringePump`` (and its abstract bases).  The methods and their arguments
mirror the upstream signatures; the upstream class sends DT-protocol commands over a serial connection, while this
object keeps the resulting state in plain attributes.  The start values are test data, not facts: each one is marked
``# placeholder``.  Nothing here opens a port or talks to a device.
"""


class FakeC3000SyringePump:
    def __init__(self, **_options):
        self._plunger = 0                 # placeholder: an empty syringe at the home position
        self._valve = "I"                 # placeholder: the input position used by the usage guide
        self._initialized = True          # placeholder: the fake starts initialized
        self._idle = True                 # placeholder: no command is running
        self._connected = True            # placeholder: the fake answers
        self._speed = 6000                # placeholder: one of the SPEED_MODES values
        self._start_velocity = 1          # placeholder: the lower end of the start-velocity check
        self._stop_velocity = 1           # placeholder: the lower end of the stop-velocity check
        self._speed_code = "0"            # placeholder: one of the SPEED_MODES keys
        self._ramp_code = "1"             # placeholder: one of the RAMP_PLOPE_MODES keys
        self._resolution_mode = "N0"      # placeholder: one of the RESOLUTION_MODES keys
        self._stop_calls = 0              # placeholder: no stop has been recorded yet

    # -- reads --------------------------------------------------------------------------------------------------
    def is_connected(self):
        return self._connected

    def is_initialized(self):
        return self._initialized

    def is_idle(self):
        return self._idle

    def get_plunger_position(self):
        return self._plunger

    def get_valve_position(self):
        return self._valve

    # -- motor configuration ------------------------------------------------------------------------------------
    def set_speed(self, speed: int):
        self._speed = int(speed)

    def set_start_velocity(self, start_velocity: int):
        self._start_velocity = int(start_velocity)

    def set_stop_velocity(self, stop_velocity: int):
        self._stop_velocity = int(stop_velocity)

    def set_predefined_speed(self, velocity_code: int):
        self._speed_code = str(velocity_code)

    def set_ramp_slope(self, ramp_code: str):
        self._ramp_code = str(ramp_code)

    def set_resolution_mode(self, resolution_mode: str):
        self._resolution_mode = str(resolution_mode)

    # -- plunger and valve movement -----------------------------------------------------------------------------
    def set_valve_position(self, requested_position: str):
        self._valve = str(requested_position)

    def move_home(self):
        self._plunger = 0                 # placeholder: the home position of the fake

    def move_plunger_absolute(self, position: int, set_busy: bool = True):
        self._plunger = int(position)

    def move_plunger_relative(self, position: int, set_busy: bool = True):
        if int(position) > 0:
            self.withdraw(int(position), set_busy)
        else:
            self.dispense(abs(int(position)), set_busy)

    def dispense(self, increments: float, set_busy: bool = True):
        self._plunger -= int(increments)

    def withdraw(self, increments: float, set_busy: bool = True):
        self._plunger += int(increments)

    # -- safety -------------------------------------------------------------------------------------------------
    def stop(self):
        self._idle = True
        self._stop_calls += 1
