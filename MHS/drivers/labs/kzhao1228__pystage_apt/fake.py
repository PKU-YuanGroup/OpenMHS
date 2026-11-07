"""Fake backend of the pystage-apt driver: an in-memory stand-in for stage.motor_ctrl:MotorCtrl.

Gate G7: every public method and property defined here exists on stage.motor_ctrl:MotorCtrl, and the one other
attribute the driver reaches, ``_port``, is set by the upstream __init__ (stage/motor_ctrl/__init__.py:33).  The
upstream MotorCtrl has no stop method, so the driver's real stop is the APT MOVE_STOP message the native.py port
wrapper sends; here ``_port.stop()`` records that stop and clears the motion flag.  The default values are test data,
not facts about any stage: each is marked placeholder.  Nothing here talks to a device.
"""


class _FakePort:
    """The port object a real MotorCtrl owns; only the stop extension the driver uses is needed."""

    def __init__(self, stage):
        self._stage = stage
        self.stop_count = 0

    def stop(self, stop_mode=0x01):
        self.stop_count += 1
        self.last_stop_mode = stop_mode
        self._stage._in_motion = False


class FakeMotorCtrl:
    def __init__(self, **_options):
        self._position = 1.0                    # placeholder: starting position in stage units
        self._min_vel = 0.0                     # placeholder
        self._max_vel = 2.0                     # placeholder
        self._accn = 1.0                        # placeholder
        self._home_vel = 1.0                    # placeholder
        self._home_dir = 1                      # placeholder: 1 forward
        self._home_limit = 1                    # placeholder: 1 reverse switch
        self._home_offset = 0.0                 # placeholder
        self._in_motion = False                 # placeholder
        self._homed = False                     # placeholder
        self._channel_enabled = True            # placeholder
        self._forward_limit = False             # placeholder
        self._reverse_limit = False             # placeholder
        self._units = "mm"                      # placeholder
        self._stage_model = "MTS25-Z8"          # placeholder
        self._serial_number = 83845481          # placeholder
        self._port = _FakePort(self)

    # -- reads ------------------------------------------------------------------------------------------------
    @property
    def pos(self):
        return self._position

    @property
    def is_in_motion(self):
        return self._in_motion

    @property
    def status_homed(self):
        return self._homed

    @property
    def status_channel_enabled(self):
        return self._channel_enabled

    @property
    def status_forward_hardware_limit_switch_active(self):
        return self._forward_limit

    @property
    def status_reverse_hardware_limit_switch_active(self):
        return self._reverse_limit

    @property
    def stage_model(self):
        return self._stage_model

    @property
    def ser_no(self):
        return self._serial_number

    @property
    def units(self):
        return self._units

    @property
    def min_vel(self):
        return self._min_vel

    @property
    def max_vel(self):
        return self._max_vel

    @property
    def accn(self):
        return self._accn

    @property
    def home_vel(self):
        return self._home_vel

    @property
    def home_dir(self):
        return self._home_dir

    @property
    def home_limit_switch(self):
        return self._home_limit

    # -- writes and actions -----------------------------------------------------------------------------------
    def set_pos(self, new_value, blocking=False):
        self._position = float(new_value)
        self._in_motion = False

    def move_by(self, new_value, blocking=False):
        self._position = float(self._position) + float(new_value)
        self._in_motion = False

    def move_home(self, blocking=False):
        self._position = 0.0
        self._homed = True
        self._in_motion = False

    def set_min_vel(self, new_value):
        if float(new_value) < float(self._max_vel):
            self._min_vel = float(new_value)

    def set_max_vel(self, new_value):
        if float(new_value) > float(self._min_vel):
            self._max_vel = float(new_value)

    def set_accn(self, new_value):
        if float(new_value) > 0.0:
            self._accn = float(new_value)

    def set_home_vel(self, new_value):
        if 0.0 < float(new_value) < float(self._max_vel):
            self._home_vel = float(new_value)

    def set_home_dir(self, new_value):
        if int(new_value) in (1, 2):
            self._home_dir = int(new_value)

    def set_limit_switch(self, new_value):
        if int(new_value) in (1, 4):
            self._home_limit = int(new_value)
