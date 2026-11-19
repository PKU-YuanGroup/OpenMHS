"""Fake backend of the LeCroy driver: an in-memory stand-in for the upstream ``LeCroyScope`` class.

Gate G7: every public method defined here is a method of ``LeCroyScope`` in the clone (oscilloscope.py:198):
the identity and capability queries, the channel, timebase, trigger and acquisition methods, one PAVA
measurement, the *CAL? self-calibration, the raw query path and disconnect.  State lives in private instance
attributes, so the fake's public surface is the upstream method surface.

The clone ships no simulator and no test suite for this class, and this package has no captured instrument
traffic, so this file is an in-memory analytic stand-in, not a recording.  Every number and canned reply below
is test data, not a fact of the clone or of an instrument: each is marked ``# placeholder``.  Nothing here talks
to a device.
"""


class FakeLeCroyScope:
    """A fresh in-memory oscilloscope per endpoint; all starting values and replies are placeholders."""

    def __init__(self, **_options):
        self._connected = True
        self._header_mode = "SHORT"  # source default; setup must select OFF before scalar reads
        self._idn = "LECROY,FAKE-WS,000000,0.0"                  # placeholder
        self._date = "01-JAN-2026 00:00:00"                      # placeholder
        self._family = "Fake WaveSurfer"                         # placeholder
        self._channels = 4                                       # placeholder
        self._bandwidth_mhz = 500                                # placeholder
        self._vdiv = 0.5                                         # placeholder
        self._offset = 0.0                                       # placeholder
        self._coupling = "D1M"                                   # placeholder
        self._bwlimit = {number: "OFF" for number in range(1, 5)}  # placeholder
        self._attenuation = 1.0                                  # placeholder
        self._tdiv = 0.001                                       # placeholder
        self._trig_delay = 0.0                                   # placeholder
        self._memory_size = "10K"                                # placeholder
        self._trig_mode = "AUTO"                                 # placeholder
        self._trig_source = "C1"                                 # placeholder
        self._trig_level = 0.0                                   # placeholder
        self._stopped = False
        self._inr = 0                                            # placeholder

    # -- connection and identity ----------------------------------------------------------------------------------
    def connect(self, resource_string=None):
        self._connected = True
        return self.identify()

    def disconnect(self):
        self._connected = False

    def identify(self):
        return self._idn

    def get_date(self):
        return self._date

    def get_capabilities(self):
        return {
            "model": "FAKE-WS",                                  # placeholder
            "idn": self._idn,
            "family": self._family,
            "channels": self._channels,
            "bandwidth_mhz": self._bandwidth_mhz,
            "bits": 8,                                           # placeholder
            "coupling_cmd": "CPL",
            "coupling_values": ["A1M", "D1M", "D50", "GND"],     # placeholder set from the manual
            "bwlimit_values": ["OFF", "20MHZ", "200MHZ", "FULL"],  # placeholder set from the clone profile
            "max_memory_kpts": 10000,                            # placeholder
            "math_channels": 4,                                  # placeholder
            "has_invs": True,
            "has_unit": True,
            "has_sara": False,
            "notes": "in-memory fake",                           # placeholder
        }

    # -- channel settings -----------------------------------------------------------------------------------------
    def _check_channel(self, channel):
        if channel not in range(1, self._channels + 1):
            raise ValueError(f"channel {channel} is outside 1 to {self._channels}")

    def _bwlimit_reply(self):
        return ",".join(f"C{number},{self._bwlimit[number]}" for number in range(1, self._channels + 1))

    def get_channel_info(self, channel):
        self._check_channel(channel)
        return {
            "vdiv": f"{self._vdiv:.6E}",
            "offset": f"{self._offset:.6E}",
            "coupling": self._coupling,
            "bwlimit": self._bwlimit_reply(),
            "trace": "ON",                                       # placeholder
            "invert": "OFF",                                     # placeholder
            "unit": "V",                                         # placeholder
        }

    def set_vdiv(self, channel, volts_per_div):
        self._check_channel(channel)
        self._vdiv = float(volts_per_div)

    def set_offset(self, channel, offset_volts):
        self._check_channel(channel)
        self._offset = float(offset_volts)

    def set_coupling(self, channel, coupling):
        self._check_channel(channel)
        self._coupling = str(coupling).upper()

    def set_bwlimit(self, channel, bwl):
        self._check_channel(channel)
        self._bwlimit[channel] = str(bwl).upper()

    def set_attenuation(self, channel, factor):
        self._check_channel(channel)
        self._attenuation = float(factor)

    # -- timebase -------------------------------------------------------------------------------------------------
    def get_timebase_info(self):
        return {
            "tdiv": f"{self._tdiv:.6E}",
            "trig_delay": f"{self._trig_delay:.6E}",
            "memory_size": self._memory_size,
        }

    def set_tdiv(self, seconds_per_div):
        self._tdiv = float(seconds_per_div)

    def set_trigger_delay(self, seconds):
        self._trig_delay = float(seconds)

    # -- trigger --------------------------------------------------------------------------------------------------
    def get_trigger_info(self):
        result = {
            "mode": self._trig_mode,
            "select": f"EDGE,SR,{self._trig_source},SL,POS,HT,OFF",
        }
        for number in range(1, self._channels + 1):
            result[f"c{number}_trig_level"] = f"{self._trig_level:.6E}"
        return result

    def set_trigger_mode(self, mode):
        self._trig_mode = str(mode).upper()
        self._stopped = self._trig_mode == "STOP"

    def set_trigger_source(self, source, slope="POS"):
        self._trig_source = str(source).upper()

    def set_trigger_level(self, channel, level_volts):
        self._check_channel(channel)
        self._trig_level = float(level_volts)

    def force_trigger(self):
        self._stopped = False
        self._inr = 1                                             # placeholder

    # -- acquisition ----------------------------------------------------------------------------------------------
    def arm(self):
        self._stopped = False
        self._trig_mode = "SINGLE"

    def stop(self):
        self._stopped = True
        self._trig_mode = "STOP"

    def is_stopped(self):
        return "STOP" in self.query("TRMD?").upper()

    def get_acquisition_status(self):
        return f"{self.query('TRMD?')}  |  {self.query('INR?')}"

    # -- measurements and calibration -----------------------------------------------------------------------------
    def measure(self, channel, param):
        self._check_channel(channel)
        return f"{str(param).upper()},1.0E+00,OK"                 # placeholder reply

    def calibrate(self):
        return "*CAL 0"                                           # placeholder reply

    # -- raw query path -------------------------------------------------------------------------------------------
    def write(self, cmd):
        if str(cmd).strip().upper() != "CHDR OFF":
            raise ValueError(f"the fake does not implement {cmd!r}")
        self._header_mode = "OFF"

    def query(self, cmd):
        command = str(cmd).strip().upper()
        if command == "C1:ATTN?":
            return f"{self._attenuation:g}"
        if command == "*IDN?":
            return self._idn
        if command == "DATE?":
            return self._date
        if command == "TRMD?":
            return self._trig_mode
        if command == "INR?":
            return f"INR {self._inr}"                             # placeholder reply
        raise ValueError(f"the fake does not answer {cmd!r}")
