"""Fake backend of the Lake Shore 336 driver: a source-shaped stand-in for the upstream QCoDeS instrument.

The upstream ``instruments.lakeshore_336:LakeShore336`` is a ``VisaInstrument`` whose methods build text commands
from parts (``KRDG? A``, ``SETP 1,300.0``, ``RANGE 1,3``, ``OUTMODE 1,1,1,0``).  This fake provides only the public
methods the driver calls and keeps the same text/code mapping and parser result types.  It imports no QCoDeS or
PyVISA, opens no VISA session and talks to no instrument.

Fidelity gaps:

* The fake does not exercise the QCoDeS VISA transport, its timeouts, the ``*CLS`` write of the upstream constructor
  or a device-side rejection of a command.  It stores any accepted value; the server enforces the driver limits
  before the fake sees the call.
* ``set_manual_output`` has no query in the upstream class, so the fake stores the level without a readback.
* The fake is an in-memory model, not a recording of captured traffic.  The temperature, raw sensor values and
  identity string are placeholders chosen for the tests; none is a fact about a Lake Shore 336 or a cryostat.
"""


class FakeLakeShore336:
    #: Command-code maps copied from the upstream class (instruments/lakeshore_336.py:32-79), not test data.
    _RANGE_TO_CODE = {"off": 0, "low": 1, "medium": 2, "med": 2, "high": 3, "max": 3}
    _CODE_TO_RANGE = {0: "off", 1: "low", 2: "medium", 3: "high"}
    _MODE_TO_CODE = {"off": 0, "closed loop": 1, "closed_loop": 1, "pid": 1, "zone": 2,
                     "open loop": 3, "open_loop": 3, "monitor": 4, "monitor out": 4, "warmup": 5, "warm-up": 5}
    _CODE_TO_MODE = {0: "off", 1: "closed loop", 2: "zone", 3: "open loop", 4: "monitor", 5: "warmup"}
    _INPUT_TO_CODE = {None: 0, "none": 0, "A": 1, "a": 1, "B": 2, "b": 2, "C": 3, "c": 3, "D": 4, "d": 4}
    _CODE_TO_INPUT = {0: "none", 1: "A", 2: "B", 3: "C", 4: "D", 5: "D2", 6: "D3", 7: "D4", 8: "D5"}

    def __init__(self, **_options):
        self._closed = False
        self._temperatures = {"A": 300.0, "B": 300.0, "C": 300.0, "D": 300.0}   # placeholder, K
        self._sensor_units = {"A": 100.0, "B": 100.0, "C": 100.0, "D": 100.0}   # placeholder, sensor units
        self._setpoint = 300.0                 # placeholder, K
        self._ramp_rate = 1.0                  # placeholder, K/min
        self._ramp_enabled = False             # placeholder
        self._manual_output = 0.0              # placeholder, percent
        self._ranges = {1: 0, 2: 0}            # placeholder, both outputs off
        self._modes = {1: 0, 2: 0}             # placeholder, both modes off
        self._inputs = {1: 0, 2: 0}            # placeholder, no control input
        self._powerup = {1: False, 2: False}   # placeholder

    # -- basic queries ----------------------------------------------------------------------------------------
    def get_idn(self):
        return "Lake Shore Model 336, fake, 0.0"     # placeholder, canned IDN reply

    # -- temperature readings ----------------------------------------------------------------------------------
    def _channel(self, channel):
        ch = str(channel).upper()
        if ch not in self._temperatures:
            raise ValueError(f"Invalid channel {channel!r}. Must be one of ('A', 'B', 'C', 'D').")
        return ch

    def get_temperature(self, channel="A"):
        return self._temperatures[self._channel(channel)]

    def get_sensor_units(self, channel="A"):
        return self._sensor_units[self._channel(channel)]

    # -- setpoint and ramp -------------------------------------------------------------------------------------
    def get_setpoint(self, loop=1):
        return self._setpoint

    def set_setpoint(self, loop=1, value=300.0):
        self._setpoint = float(value)

    def get_ramp(self, loop=1):
        return self._ramp_rate, self._ramp_enabled

    def set_ramp(self, loop=1, rate_K_per_min=1.0, enable=True):
        self._ramp_rate = float(rate_K_per_min)
        self._ramp_enabled = bool(enable)

    # -- heater range and manual output ------------------------------------------------------------------------
    def _output(self, output):
        index = int(output)
        if index not in (1, 2):
            raise ValueError(f"Invalid output {output!r}. Must be 1 or 2.")
        return index

    def get_heater_range(self, output=1, as_text=False):
        code = self._ranges[self._output(output)]
        if as_text:
            return self._CODE_TO_RANGE.get(code, f"unknown({code})")
        return code

    def set_heater_range(self, output=1, heater_range="off"):
        if isinstance(heater_range, str):
            key = heater_range.lower()
            if key not in self._RANGE_TO_CODE:
                raise ValueError(f"Invalid heater_range {heater_range!r}")
            code = self._RANGE_TO_CODE[key]
        else:
            code = int(heater_range)
        self._ranges[self._output(output)] = code

    def set_manual_output(self, output=1, percent=0.0):
        self._output(output)
        self._manual_output = float(percent)

    # -- output mode -------------------------------------------------------------------------------------------
    def get_output_mode(self, output=1):
        index = self._output(output)
        mode_code = self._modes[index]
        input_code = self._inputs[index]
        return {
            "mode_code": mode_code,
            "mode_text": self._CODE_TO_MODE.get(mode_code, f"unknown({mode_code})"),
            "input_code": input_code,
            "input_text": self._CODE_TO_INPUT.get(input_code, f"unknown({input_code})"),
            "powerup_enable": bool(self._powerup[index]),
        }

    def set_output_mode(self, output=1, mode="closed loop", input_channel="A", powerup_enable=False):
        index = self._output(output)
        key = mode.lower()
        if key not in self._MODE_TO_CODE:
            raise ValueError(f"Invalid mode {mode!r}")
        if input_channel not in self._INPUT_TO_CODE:
            raise ValueError(f"Invalid input_channel {input_channel!r}")
        self._modes[index] = self._MODE_TO_CODE[key]
        self._inputs[index] = self._INPUT_TO_CODE[input_channel]
        self._powerup[index] = bool(powerup_enable)

    # -- lifecycle ---------------------------------------------------------------------------------------------
    def close(self):
        self._closed = True
