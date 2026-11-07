"""Fake backend of the Cryo-con 34 driver: an in-memory stand-in for the upstream Cryocon34Backend.

Gate G7: every public method defined here exists on
``pica.cryocon.T_Control_CC34_DirectControl_GUI:Cryocon34Backend`` (the class at line 547 of that file).  The fake
keeps the same signatures, the same string replies the controller gives for settings and status, and the same
non-destructive disconnect; it never opens a VISA session and talks to no device.

The starting values and canned replies are test data, not facts about any controller; each numeric one is marked
``# placeholder``.  They never move by themselves, so reading the state twice gives the same state.  The driver
requires Kelvin, so every channel starts in K.
"""


class FakeCryocon34:
    def __init__(self, **_options):
        self.link = None
        self._connected = True
        self._units = {"A": "K", "B": "K", "C": "K", "D": "K"}
        self._temperature = {"A": 4.2, "B": 77.0, "C": 300.0, "D": 20.0}   # placeholder
        self._setpoint = 4.2                                                # placeholder
        self._loop_type = "PID"                                             # placeholder
        self._loop_source = "A"                                             # placeholder
        self._max_power = 50.0                                              # placeholder
        self._max_setpoint = 400.0                                          # placeholder
        self._manual_power = 0.0                                            # placeholder
        self._rate = 1.0                                                    # placeholder
        self._load = 50                                                     # placeholder
        self._control = False                                               # placeholder
        self._heater_readback = "0.0"                                       # placeholder
        self._input_name = "A"                                              # placeholder
        self._alarm_status = "--"                                           # placeholder
        self._alarm = ("400.000", "0.000", "NO", "NO")                      # placeholder
        self._ambient = "+25C"                                              # placeholder
        self._idn = "Cryo-con,34,SN0,3.03A"                                 # placeholder
        self._error_queue = "0,No error"                                    # placeholder
        self._display_resolution = "FULL"                                   # placeholder
        self._display_time_constant = "1"                                   # placeholder
        self._lockout = False                                               # placeholder
        self._factory_sensor_index = 0                                      # placeholder

    # -- connection --------------------------------------------------------------------------------------------

    def disconnect(self):
        """The upstream disconnect only closes the VISA session and changes no setting."""
        self._connected = False
        self.link = None

    # -- reads -------------------------------------------------------------------------------------------------

    def get_temperature(self, channel):
        return self._temperature[channel]

    def get_units(self, channel):
        return self._units[channel]

    def get_loop_source(self, loop):
        return f"CH{self._loop_source}"

    def get_setpoint(self, loop):
        return self._setpoint

    def get_control_status(self):
        return "ON" if self._control else "OFF"

    def get_heater_readback(self, loop):
        return self._heater_readback

    def get_loop_type(self, loop):
        return self._loop_type

    def get_max_power(self, loop):
        return self._max_power

    def get_max_setpoint(self, loop):
        return self._max_setpoint

    def get_manual_power(self, loop):
        return self._manual_power

    def get_rate(self, loop):
        return self._rate

    def get_input_name(self, channel):
        return self._input_name

    def get_alarm_status(self, channel):
        return self._alarm_status

    def get_alarm(self, channel):
        return self._alarm

    def get_ambient(self):
        return self._ambient

    def get_idn(self):
        return self._idn

    def get_error_queue(self):
        return self._error_queue

    def get_display_resolution(self):
        return self._display_resolution

    def get_display_time_constant(self):
        return self._display_time_constant

    def get_lockout(self):
        return "ON" if self._lockout else "OFF"

    def get_load(self):
        return str(self._load)

    def get_factory_sensor_index(self, channel):
        return str(self._factory_sensor_index)

    # -- writes ------------------------------------------------------------------------------------------------

    def set_setpoint_immediate(self, loop, value):
        # The upstream command is TYPE PID;SETPT <value>, so the loop type follows the write.
        self._setpoint = float(value)
        self._loop_type = "PID"
        return f"HEATER:TYPE PID;SETPT {value}"

    def set_max_power(self, loop, percent):
        self._max_power = float(percent)
        return f"HEATER:MAXPWR {percent}"

    def set_max_setpoint(self, loop, value):
        self._max_setpoint = float(value)
        return f"HEATER:MAXSET {value}"

    def set_manual_power(self, loop, percent):
        self._manual_power = float(percent)
        return f"HEATER:PMANUAL {percent}"

    def set_loop_type(self, loop, control_type):
        self._loop_type = control_type
        return f"HEATER:TYPE {control_type}"

    def set_loop_source(self, loop, channel):
        self._loop_source = channel
        return f"HEATER:SOURCE CH{channel}"

    def set_display_time_constant(self, tc):
        self._display_time_constant = str(tc)
        return f"SYSTEM:DISTC {tc}"

    def set_load(self, ohms):
        self._load = int(ohms)
        return f"HEATER:LOAD {ohms}"

    # -- control -----------------------------------------------------------------------------------------------

    def control_engage(self):
        self._control = True
        return "CONTROL"

    def control_stop(self):
        self._control = False
        return "STOP"
