"""Fake backend of the MSOX2024A driver: an in-memory stand-in for the upstream ``scope:Scope`` class.

Gate G7: every public method defined here is a method of ``Scope`` in the clone (scope.py): identity and the
generic SCPI query, acquisition control, timebase, channel, trigger, measurement and close.  The state attributes
are private instance data, so the fake surface is the upstream method surface.

The clone ships no simulator for ``Scope`` and no session transcript was available, so this file is an in-memory
stand-in, not a recording.  Every number and string below is test data, not a fact from the clone or a record of an
instrument: each is marked ``# placeholder``.  Nothing here talks to a device.
"""


class FakeScope:
    """A fresh in-memory oscilloscope per endpoint; all starting values are placeholders."""

    def __init__(self, **_options):
        self._scale = 1.0                  # placeholder
        self._offset = 0.0                 # placeholder
        self._coupling = "DC"              # placeholder
        self._display = "ON"               # placeholder
        self._bwlimit = "OFF"              # placeholder
        self._timebase_scale = 0.001       # placeholder
        self._timebase_delay = 0.0         # placeholder
        self._timebase_mode = "MAIN"       # placeholder
        self._trigger_mode = "EDGE"        # placeholder
        self._trigger_source = "CHANnel1"  # placeholder
        self._trigger_level = 0.0          # placeholder
        self._trigger_slope = "POSitive"   # placeholder
        self._trigger_sweep = "AUTO"       # placeholder
        self._running = True               # placeholder
        self.closed = False

    # -- identity and generic SCPI -----------------------------------------------------------------------------------
    def idn(self):
        return "AGILENT TECHNOLOGIES,MSOX2024A,FAKE000000,02.43.2018020635"  # placeholder

    def query(self, cmd):
        command = str(cmd).strip()
        if command == "*IDN?":
            return self.idn()
        if command == ":OPERegister:CONDition?":
            return "8" if self._running else "0"  # placeholder: bit 3
        raise TimeoutError(f"the fake scope does not answer {command!r}")

    # -- acquisition -------------------------------------------------------------------------------------------------
    def run(self):
        self._running = True

    def stop(self):
        self._running = False

    def single(self):
        self._running = True

    # -- timebase ----------------------------------------------------------------------------------------------------
    def set_timebase(self, scale):
        self._timebase_scale = float(scale)

    def set_timebase_delay(self, delay):
        self._timebase_delay = float(delay)

    def get_timebase(self):
        return {
            "scale_s_per_div": self._timebase_scale,
            "delay_s": self._timebase_delay,
            "mode": self._timebase_mode,
        }

    # -- channel -----------------------------------------------------------------------------------------------------
    def set_channel(self, channel, scale=None, offset=None, coupling=None, enabled=None, bwlimit=None):
        if scale is not None:
            self._scale = float(scale)
        if offset is not None:
            self._offset = float(offset)
        if coupling is not None:
            self._coupling = str(coupling).upper()
        if enabled is not None:
            self._display = "ON" if enabled else "OFF"
        if bwlimit is not None:
            self._bwlimit = "ON" if bwlimit else "OFF"

    def get_channel(self, channel):
        return {
            "channel": int(channel),
            "scale_v_per_div": self._scale,
            "offset_v": self._offset,
            "coupling": self._coupling,
            "display": self._display,
            "bwlimit": self._bwlimit,
        }

    # -- trigger -----------------------------------------------------------------------------------------------------
    def set_trigger(self, source, level, slope="positive", mode="edge"):
        self._trigger_mode = str(mode).upper()
        if str(mode).lower() == "edge":
            self._trigger_source = f"CHANnel{int(source)}"
            self._trigger_slope = {
                "positive": "POSitive",
                "negative": "NEGative",
                "either": "EITHer",
            }.get(str(slope).lower(), "POSitive")
            self._trigger_level = float(level)

    def get_trigger(self):
        return {
            "mode": self._trigger_mode,
            "source": self._trigger_source,
            "level_v": self._trigger_level,
            "slope": self._trigger_slope,
            "sweep": self._trigger_sweep,
        }

    # -- measurement -------------------------------------------------------------------------------------------------
    def measure(self, channel, parameter):
        values = {
            "frequency": 1000.0,   # placeholder
            "period": 0.001,       # placeholder
            "vpp": 2.0,            # placeholder
            "vrms": 0.707,         # placeholder
            "vmax": 1.0,           # placeholder
            "vmin": -1.0,          # placeholder
            "vaverage": 0.0,       # placeholder
            "duty": 50.0,          # placeholder
            "rise": 1e-6,          # placeholder
            "fall": 1e-6,          # placeholder
            "overshoot": 1.0,      # placeholder
            "preshoot": 0.5,       # placeholder
            "width": 0.0005,       # placeholder
        }
        key = str(parameter).lower()
        if key not in values:
            raise ValueError(f"Unknown parameter '{parameter}'.")
        return values[key]

    # -- connection --------------------------------------------------------------------------------------------------
    def close(self):
        self.closed = True
