"""Fake backend of the DLCpro driver: an in-memory stand-in for dlccontrol:DLCcontrol.

Gate G7: every public method and property defined here exists on dlccontrol.DLCcontrol in the pinned clone.
The upstream class builds a Toptica SDK connection in __init__; this fake keeps the state in plain attributes and
never imports the vendor SDK.  The properties mirror the upstream property/setter surface the driver uses; the
starting values are arbitrary test data (marked ``# placeholder``), not claims about a real DLCpro.  Nothing here
talks to a device.
"""

import enum


class _OutputChannel(enum.IntEnum):
    """The upstream OutputChannel values, dlccontrol.py:75-81; only .name is used by the driver."""

    PC = 50
    CC = 51
    OutA = 20
    OutB = 21


class FakeDlcControl:
    def __init__(self, **_options):
        self.wl_control_available = True       # placeholder
        self.temp_control_available = True     # placeholder
        self._emission_button = True           # placeholder
        self._current_enabled = False          # placeholder
        self._wavelength_setpoint = 1550.0     # placeholder
        self._wavelength_actual = 1550.0       # placeholder
        self._temp_setpoint = 20.0             # placeholder
        self._temp_actual = 20.0               # placeholder
        self._scan_enabled = False             # placeholder
        self._scan_output_channel = _OutputChannel.PC  # placeholder
        self._scan_frequency = 50.0            # placeholder
        self._scan_amplitude = 21.0            # placeholder
        self._scan_offset = 61.0               # placeholder
        self._scan_start = 50.5                # placeholder
        self._scan_end = 71.5                  # placeholder
        self._user_level = 3                   # placeholder
        self._lims = {
            "vmin": 0.0,       # placeholder
            "vmax": 150.0,     # placeholder
            "cmin": 0.0,       # placeholder
            "cmax": 250.0,     # placeholder
            "fmin": 0.02,      # upstream dlccontrol.py:267
            "fmax": 400.0,     # upstream dlccontrol.py:268
            "tmin": 15.0,      # placeholder
            "tmax": 35.0,      # placeholder
            "wlmin": 1500.0,   # placeholder
            "wlmax": 1600.0,   # placeholder
        }

    # -- emission ----------------------------------------------------------------------------------------------
    @property
    def emission(self):
        return bool(self._emission_button and self._current_enabled)

    @property
    def emission_button(self):
        return bool(self._emission_button)

    @property
    def current_enabled(self):
        return bool(self._current_enabled)

    @current_enabled.setter
    def current_enabled(self, value):
        self._current_enabled = bool(value)

    # -- wavelength and diode temperature ----------------------------------------------------------------------
    @property
    def wavelength_actual(self):
        return self._wavelength_actual if self.wl_control_available else None

    @property
    def wavelength_setpoint(self):
        return self._wavelength_setpoint if self.wl_control_available else None

    @wavelength_setpoint.setter
    def wavelength_setpoint(self, value):
        if not self.wl_control_available:
            raise RuntimeError("Cannot set wavelength when `wl_control_available` is False")
        if value is None:
            return
        self._wavelength_setpoint = float(value)

    @property
    def temp_actual(self):
        return self._temp_actual if self.temp_control_available else None

    @property
    def temp_setpoint(self):
        return self._temp_setpoint if self.temp_control_available else None

    @temp_setpoint.setter
    def temp_setpoint(self, value):
        if not self.temp_control_available:
            raise RuntimeError("Cannot set diode temperature `temp_control_available` is False")
        if value is None:
            return
        self._temp_setpoint = float(value)

    # -- internal scan -----------------------------------------------------------------------------------------
    @property
    def scan_enabled(self):
        return bool(self._scan_enabled)

    @scan_enabled.setter
    def scan_enabled(self, value):
        self._scan_enabled = bool(value)

    @property
    def scan_output_channel(self):
        return self._scan_output_channel

    @property
    def scan_frequency(self):
        return self._scan_frequency

    @scan_frequency.setter
    def scan_frequency(self, value):
        value = float(value)
        if not self._lims["fmin"] <= value <= self._lims["fmax"]:
            raise ValueError(f"{value} is not within the permitted scan frequency range")
        self._scan_frequency = value

    @property
    def scan_amplitude(self):
        return self._scan_amplitude

    @scan_amplitude.setter
    def scan_amplitude(self, value):
        self._scan_amplitude = float(value)

    @property
    def scan_offset(self):
        return self._scan_offset

    @scan_offset.setter
    def scan_offset(self, value):
        self._scan_offset = float(value)

    @property
    def scan_start(self):
        return self._scan_start

    @scan_start.setter
    def scan_start(self, value):
        self._scan_start = float(value)

    @property
    def scan_end(self):
        return self._scan_end

    @scan_end.setter
    def scan_end(self, value):
        self._scan_end = float(value)

    # -- the wrapper's query methods ---------------------------------------------------------------------------
    def get_limits_from_dlc(self, verbose=False):
        return self._lims

    def get_user_level(self):
        return self._user_level
