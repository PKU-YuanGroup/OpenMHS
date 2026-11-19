"""Fake backend of the SkippyMCP driver: an in-memory stand-in for ``skippy_mcp.driver.scope:Scope``.

Gate G7: every public method defined here is a method of ``Scope`` in the clone
(packages/skippy-mcp/src/skippy_mcp/driver/scope.py): identify, configure_channel, configure_trigger, capture,
measure, raw_scpi, reset and close.  The driver calls those methods with plain values (dicts and strings) and the
hardware backend converts them to the upstream dataclasses and enums inside ``native.py``; this fake stores the
same plain values so a write is visible to the next read.

The clone has a ``SimulatedTransport`` for the SCPI layer (transport/simulated.py:48), but that module is part of
the pinned clone and this package may not import or install it.  This file is therefore an in-memory stand-in, not
a recording of a session; every number and string below is test data, marked ``# placeholder``.  Nothing here
talks to a device.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class _Idn:
    manufacturer: str
    model: str
    serial: str
    firmware: str


@dataclass(frozen=True)
class _Measurement:
    value: float
    unit: str


#: The measurement item -> unit map of the clone's Scope (scope.py:37-47).
_UNITS = {
    "vpp": "V", "vrms": "V", "freq": "Hz", "period": "s", "duty": "%",
    "rise": "s", "fall": "s", "delay": "s", "phase": "deg",
}
#: One deterministic stand-in value per item; these are placeholders, not an instrument record.
_VALUES = {  # placeholder
    "vpp": 3.3,  # placeholder
    "vrms": 1.166726,  # placeholder
    "freq": 1000.0,  # placeholder
    "period": 0.001,  # placeholder
    "duty": 50.0,  # placeholder
    "rise": 3.5e-06,  # placeholder
    "fall": 3.5e-06,  # placeholder
    "delay": 0.0,  # placeholder
    "phase": 0.0,  # placeholder
}
_COUPLING_SCPI = {"dc": "DC", "ac": "AC", "gnd": "GND"}
_BANDWIDTH_SCPI = {"off": "OFF", "20m": "20M"}
_TRIGGER_MODE_SCPI = {"edge": "EDGE", "pulse": "PULSe", "pattern": "PATTern"}
_TRIGGER_SLOPE_SCPI = {"rising": "POSitive", "falling": "NEGative", "either": "RFALl"}
_SOURCE_SCPI = {"ch1": "CHANnel1", "ch2": "CHANnel2", "ch3": "CHANnel3", "ch4": "CHANnel4"}


class FakeScope:
    """A fresh in-memory oscilloscope per endpoint; every starting value is a placeholder, not a recording."""

    def __init__(self, **_options):
        self._init_state()
        self.closed = False
        self.written = []
        self.measurements = []

    def _init_state(self):
        self._enabled = True  # placeholder
        self._scale = 0.5  # placeholder
        self._offset = 0.0  # placeholder
        self._coupling = "dc"  # placeholder
        self._probe = 10.0  # placeholder
        self._bandwidth = "20m"  # placeholder
        self._trigger_mode = "edge"  # placeholder
        self._trigger_source = "ch1"  # placeholder
        self._trigger_slope = "rising"  # placeholder
        self._trigger_level = 0.0  # placeholder
        self._running = True  # placeholder

    # -- identity and lifecycle ---------------------------------------------------------------------------------
    def identify(self):
        return _Idn("RIGOL TECHNOLOGIES", "MSO5204", "FAKE00000000", "00.01.03.02.02")  # placeholder

    def reset(self):
        self._init_state()

    def close(self):
        self.closed = True

    # -- analog channel -----------------------------------------------------------------------------------------
    def configure_channel(self, config):
        """Apply the plain-value channel patch the driver builds; only names Scope exposes are read."""
        self.written.append(("configure_channel", dict(config)))
        if config.get("enabled") is not None:
            self._enabled = bool(config["enabled"])
        if config.get("scale_v_per_div") is not None:
            self._scale = float(config["scale_v_per_div"])
        if config.get("offset_v") is not None:
            self._offset = float(config["offset_v"])
        if config.get("coupling") is not None:
            self._coupling = str(config["coupling"])
        if config.get("bandwidth_limit") is not None:
            self._bandwidth = str(config["bandwidth_limit"])
        if config.get("probe_ratio") is not None:
            self._probe = float(config["probe_ratio"])

    # -- trigger ------------------------------------------------------------------------------------------------
    def configure_trigger(self, config):
        """Apply the plain-value trigger patch; edge fields are only meaningful in edge mode."""
        self.written.append(("configure_trigger", dict(config)))
        self._trigger_mode = str(config["mode"])
        if self._trigger_mode == "edge":
            if config.get("source") is not None:
                self._trigger_source = str(config["source"])
            if config.get("slope") is not None:
                self._trigger_slope = str(config["slope"])
            if config.get("trigger_level_v") is not None:
                self._trigger_level = float(config["trigger_level_v"])

    # -- acquisition --------------------------------------------------------------------------------------------
    def capture(self, action):
        self.written.append(("capture", str(action)))
        self._running = str(action) != "stop"

    # -- measurement --------------------------------------------------------------------------------------------
    def measure(self, mtype, source, source2=None):
        self.measurements.append((str(mtype), str(source), source2))
        if str(mtype) not in _VALUES:
            raise ValueError(f"unsupported measurement item {mtype!r}")
        return _Measurement(_VALUES[str(mtype)], _UNITS[str(mtype)])

    # -- raw escape hatch ---------------------------------------------------------------------------------------
    def raw_scpi(self, command, expect_response=None):
        self.written.append(("raw_scpi", command))
        cmd = command.strip()
        if cmd.endswith("?"):
            return self._reply(cmd)
        self._apply(cmd)
        return None

    # -- internals ----------------------------------------------------------------------------------------------
    def _reply(self, cmd):
        if cmd == "*IDN?":
            idn = self.identify()
            return f"{idn.manufacturer},{idn.model},{idn.serial},{idn.firmware}"
        if cmd in (":SYSTem:ERRor?", ":SYST:ERR?"):
            return '0,"No error"'
        replies = {
            ":CHANnel1:DISPlay?": "1" if self._enabled else "0",
            ":CHANnel1:SCALe?": f"{self._scale:g}",
            ":CHANnel1:OFFSet?": f"{self._offset:g}",
            ":CHANnel1:COUPling?": _COUPLING_SCPI[self._coupling],
            ":CHANnel1:PROBe?": f"{self._probe:g}",
            ":CHANnel1:BWLimit?": _BANDWIDTH_SCPI[self._bandwidth],
            ":TRIGger:MODE?": _TRIGGER_MODE_SCPI[self._trigger_mode],
            ":TRIGger:EDGE:SOURce?": _SOURCE_SCPI[self._trigger_source],
            ":TRIGger:EDGE:SLOPe?": _TRIGGER_SLOPE_SCPI[self._trigger_slope],
            ":TRIGger:EDGE:LEVel?": f"{self._trigger_level:g}",
            ":RUN?": "RUN" if self._running else "STOP",
        }
        if cmd in replies:
            return replies[cmd]
        raise ValueError(f"the fake has no reply for {cmd!r}")

    def _apply(self, cmd):
        node, _, argument = cmd.partition(" ")
        value = argument.strip()
        if node.upper() == ":STOP":
            self._running = False
        elif node.upper() in (":RUN", ":SINGLE"):
            self._running = True
        elif node.upper() == ":CHANNEL1:DISPLAY":
            self._enabled = value.upper() in ("ON", "1", "TRUE")
        elif node.upper() == ":CHANNEL1:SCALE":
            self._scale = float(value)
        elif node.upper() == ":CHANNEL1:OFFSET":
            self._offset = float(value)
        elif node.upper() == ":CHANNEL1:COUPLING":
            self._coupling = value.lower()
        elif node.upper() == ":CHANNEL1:PROBE":
            self._probe = float(value)
        elif node.upper() == ":CHANNEL1:BWLIMIT":
            self._bandwidth = value.lower()
        elif node.upper() == ":TRIGGER:MODE":
            self._trigger_mode = value.lower()
        elif node.upper() == ":TRIGGER:EDGE:SOURCE":
            self._trigger_source = {v: k for k, v in _SOURCE_SCPI.items()}.get(value, value.lower())
        elif node.upper() == ":TRIGGER:EDGE:SLOPE":
            self._trigger_slope = {v: k for k, v in _TRIGGER_SLOPE_SCPI.items()}.get(value, value.lower())
        elif node.upper() == ":TRIGGER:EDGE:LEVEL":
            self._trigger_level = float(value)
        else:
            raise ValueError(f"the fake does not understand {cmd!r}")
