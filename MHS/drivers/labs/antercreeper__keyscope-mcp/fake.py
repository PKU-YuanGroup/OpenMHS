"""In-memory stand-in for ``keyscope_mcp.scope:Oscilloscope`` (test data only, not a recording).

The fake answers the same public methods the upstream class offers: ``idn``, ``write``, ``query``, ``get_error``, ``measure``,
``reset``, ``opc``, ``run``, ``stop``, ``single``, ``autoscale``, ``connect`` and ``close``.  It keeps the channel,
timebase, trigger and acquisition settings in plain attributes, so a write of ``:CHANnel1:SCALe 0.5`` changes the
reply of ``:CHANnel1:SCALe?`` and the driver reads its own write back.  Nothing here talks to an instrument, no
traffic was captured, and nothing is replayed.

close() follows native.py's stop-preserving lifecycle override; the upstream close() itself sends :RUN.

Every value of the simulated instrument is test data: the identity, the channel and trigger starting values and
the measurement replies are placeholders, not device facts.
"""

_IDN = "Keysight Technologies,EDUX1052G,FAKE0001,00.00"  # placeholder
_DISPLAY = True  # placeholder
_COUPLING = "DC"  # placeholder
_SCALE = 0.5  # placeholder
_OFFSET = 0.0  # placeholder
_INVERT = False  # placeholder
_TIME_SCALE = 0.001  # placeholder
_TIME_POSITION = 0.0  # placeholder
_TRIGGER_LEVEL = 0.0  # placeholder
_ACQUIRE_TYPE = "NORMal"  # placeholder
_ACQUIRE_COUNT = 1  # placeholder

#: One placeholder reply per automatic measurement item (dsl.py:436-439).
_MEASUREMENTS = {
    "vpp": 2.5,  # placeholder
    "vmax": 1.65,  # placeholder
    "vmin": -0.85,  # placeholder
    "vamp": 2.5,  # placeholder
    "vtop": 1.65,  # placeholder
    "vbase": -0.85,  # placeholder
    "vavg": 0.4,  # placeholder
    "vrms": 1.17,  # placeholder
    "freq": 1000.0,  # placeholder
    "per": 0.001,  # placeholder
    "rise": 0.0000001,  # placeholder
    "fall": 0.0000001,  # placeholder
    "pwid": 0.0005,  # placeholder
    "nwid": 0.0005,  # placeholder
    "duty": 50.0,  # placeholder
    "over": 1.0,  # placeholder
    "preshoot": 1.0,  # placeholder
}


class FakeOscilloscope:
    def __init__(self, **_options):
        self.written = []
        self._connected = True
        self._idn = _IDN
        self._display = _DISPLAY
        self._coupling = _COUPLING
        self._scale = _SCALE
        self._offset = _OFFSET
        self._invert = _INVERT
        self._time_scale = _TIME_SCALE
        self._time_position = _TIME_POSITION
        self._trigger_level = _TRIGGER_LEVEL
        self._acquire_type = _ACQUIRE_TYPE
        self._acquire_count = _ACQUIRE_COUNT
        self._running = False

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self):
        self._connected = True

    def close(self):
        self._connected = False

    def idn(self) -> str:
        return self._idn

    def opc(self) -> bool:
        return self.query("*OPC?") == "1"

    def get_error(self):
        code, _, message = self.query(":SYSTem:ERRor?").partition(",")
        return int(code), message.strip('"')

    def run(self):
        self.write(":RUN")

    def stop(self):
        self.write(":STOP")

    def single(self):
        self.write(":SINGle")

    def autoscale(self):
        self.write(":AUToscale")

    def reset(self):
        self._display = _DISPLAY
        self._coupling = _COUPLING
        self._scale = _SCALE
        self._offset = _OFFSET
        self._invert = _INVERT
        self._time_scale = _TIME_SCALE
        self._time_position = _TIME_POSITION
        self._trigger_level = _TRIGGER_LEVEL
        self._acquire_type = _ACQUIRE_TYPE
        self._acquire_count = _ACQUIRE_COUNT

    def measure(self, channel: int, mtype: str) -> float:
        try:
            base = float(_MEASUREMENTS[mtype.lower()])
        except KeyError:
            raise ValueError(f"Unknown measurement type: {mtype}") from None
        # The reply varies with the channel so a test can see that the channel reached the fake.
        return base + (int(channel) - 1) * 0.25  # placeholder

    def query(self, cmd: str) -> str:
        self.written.append(cmd)
        command = cmd.strip().upper()
        if command == "*IDN?":
            return self._idn
        if command == "*OPC?":
            return "1"
        if command == ":SYSTEM:ERROR?":
            return '0,"No error"'
        if command == ":CHANNEL1:DISPLAY?":
            return "1" if self._display else "0"
        if command == ":CHANNEL1:COUPLING?":
            return self._coupling
        if command == ":CHANNEL1:SCALE?":
            return f"{self._scale:.10g}"
        if command == ":CHANNEL1:OFFSET?":
            return f"{self._offset:.10g}"
        if command == ":CHANNEL1:INVERT?":
            return "1" if self._invert else "0"
        if command == ":TIMEBASE:SCALE?":
            return f"{self._time_scale:.10g}"
        if command == ":TIMEBASE:POSITION?":
            return f"{self._time_position:.10g}"
        if command == ":TRIGGER:EDGE:SOURCE?":
            return "CHANNEL1"
        if command == ":TRIGGER:EDGE:LEVEL?":
            return f"{self._trigger_level:.10g}"
        if command == ":TRIGGER:EDGE:SLOPE?":
            return "POSITIVE"
        if command == ":ACQUIRE:TYPE?":
            return self._acquire_type
        if command == ":ACQUIRE:COUNT?":
            return str(self._acquire_count)
        raise ValueError(f"the fake does not answer {cmd!r}")

    def write(self, cmd: str):
        self.written.append(cmd)
        line = cmd.strip()
        command, _, value = line.partition(" ")
        upper = command.upper()
        if upper == "*RST":
            self.reset()
        elif upper == ":RUN":
            self._running = True
        elif upper == ":STOP":
            self._running = False
        elif upper == ":SINGLE":
            self._running = False
        elif upper == ":AUTOSCALE":
            self._scale = 0.5  # placeholder
            self._offset = 0.0  # placeholder
        elif upper == ":CHANNEL1:DISPLAY":
            self._display = value.strip().upper() in ("ON", "1")
        elif upper == ":CHANNEL1:COUPLING":
            self._coupling = value.strip().upper()
        elif upper == ":CHANNEL1:SCALE":
            self._scale = float(value)
        elif upper == ":CHANNEL1:OFFSET":
            self._offset = float(value)
        elif upper == ":CHANNEL1:INVERT":
            self._invert = value.strip().upper() in ("ON", "1")
        elif upper == ":TIMEBASE:SCALE":
            self._time_scale = float(value)
        elif upper == ":TIMEBASE:POSITION":
            self._time_position = float(value)
        elif upper == ":TRIGGER:EDGE:LEVEL":
            self._trigger_level = float(value)
        elif upper == ":ACQUIRE:TYPE":
            self._acquire_type = value.strip()
        else:
            raise ValueError(f"the fake does not accept {cmd!r}")
