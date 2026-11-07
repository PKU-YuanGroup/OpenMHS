"""Fake backend of the thorlabs_apt driver: an in-memory stand-in for thorlabs_apt.core:Motor.

Gate G7: every public method and property defined here exists on thorlabs_apt.core:Motor in the clone.  The class
mirrors the upstream call shapes the driver uses: ``move_to(value, blocking=False)``, ``move_by(value,
blocking=False)``, ``move_home(blocking=False)`` and the tuple getters (thorlabs_apt/core.py:344-363, 444-466,
574-597, 636-669, 763-843).  There is no upstream simulator or mock in the clone, so this is an in-memory fake.  It
keeps no serial port, DLL or device and never moves anything.  Every number below is test data (``# placeholder``),
not a fact about a motor.
"""


class FakeMotor:
    """Minimal stand-in for the upstream ``Motor`` object (same public surface the driver touches)."""

    def __init__(self, **_options):
        self._serial_number = 12345678              # placeholder: test identity only
        self._position = 0.0                        # placeholder: test start position
        self._in_motion = False                     # placeholder: test start state
        self._homed = False                         # placeholder: test start state
        self._settled = True                        # placeholder: test start state
        self._motion_error = False                  # placeholder: test start state
        self._enabled = False                       # placeholder: test start state
        self._forward_limit_active = False          # placeholder: test start state
        self._reverse_limit_active = False          # placeholder: test start state
        self._active_channel = 0                    # placeholder: channel 1
        self._velocity = (0.0, 1.0, 5.0)            # placeholder: (min, acceleration, max) in native stage units
        self._stage = (-10.0, 10.0, 1, 1.0)         # placeholder: (min_pos, max_pos, units, pitch)
        self._limit_switches = (1, 1)               # placeholder: (reverse, forward) mode
        self._home_params = (1, 1, 1.0, 0.0)        # placeholder: (direction, lim_switch, velocity, zero_offset)
        self._last_velocity_direction = 0           # placeholder: no commanded direction

    # -- state properties -------------------------------------------------------------------------------------
    @property
    def serial_number(self):
        return self._serial_number

    @property
    def position(self):
        return self._position

    @property
    def is_in_motion(self):
        return self._in_motion

    @property
    def has_homing_been_completed(self):
        return self._homed

    @property
    def is_settled(self):
        return self._settled

    @property
    def motion_error(self):
        return self._motion_error

    @property
    def is_channel_enabled(self):
        return self._enabled

    @property
    def is_forward_hardware_limit_switch_active(self):
        return self._forward_limit_active

    @property
    def is_reverse_hardware_limit_switch_active(self):
        return self._reverse_limit_active

    @property
    def active_channel(self):
        return self._active_channel

    # -- configuration getters and setters --------------------------------------------------------------------
    def get_velocity_parameters(self):
        return self._velocity

    def set_velocity_parameters(self, min_vel, accn, max_vel):
        self._velocity = (float(min_vel), float(accn), float(max_vel))

    def get_stage_axis_info(self):
        return self._stage

    def set_stage_axis_info(self, min_pos, max_pos, units, pitch):
        self._stage = (float(min_pos), float(max_pos), int(units), float(pitch))

    def get_hardware_limit_switches(self):
        return self._limit_switches

    def set_hardware_limit_switches(self, rev, fwd):
        self._limit_switches = (int(rev), int(fwd))

    def get_move_home_parameters(self):
        return self._home_params

    def set_move_home_parameters(self, direction, lim_switch, velocity, zero_offset):
        self._home_params = (int(direction), int(lim_switch), float(velocity), float(zero_offset))

    # -- motion and channel commands --------------------------------------------------------------------------
    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False
        self._in_motion = False
        self._settled = True

    def move_to(self, value, blocking=False):
        self._position = float(value)
        self._in_motion = True
        self._settled = False
        if blocking:
            self._in_motion = False
            self._settled = True

    def move_by(self, value, blocking=False):
        self._position = self._position + float(value)
        self._in_motion = True
        self._settled = False
        if blocking:
            self._in_motion = False
            self._settled = True

    def move_home(self, blocking=False):
        self._position = 0.0                        # placeholder: the fake's home datum
        self._homed = True
        self._in_motion = False
        self._settled = True

    def move_velocity(self, direction):
        self._last_velocity_direction = int(direction)
        self._in_motion = True
        self._settled = False

    def stop_profiled(self):
        self._in_motion = False
        self._settled = True
