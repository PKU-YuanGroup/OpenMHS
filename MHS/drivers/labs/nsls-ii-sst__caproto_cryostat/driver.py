"""OpenMHS TagDriver for the NSLS-II SST ADR cryostat exposed as a caproto EPICS IOC: an R0 observer.

The pinned clone ``cryostat.py`` defines one ``caproto.server.PVGroup`` named
``ADR``, "A class to read temperatures from NIST's adr_gui".  The IOC
subscribes to a ZeroMQ PUB stream from the ADR controller and publishes the
temperatures, heater output, state and cycle identifier as EPICS PVs.

This package addresses those read PVs through the tag-bridge ``epics-ca``
profile: the PV suffixes are the attributes the pinned code declares, and the
deployment prefix is an operator option of ``native.py``.  ``native`` names the
upstream class for provenance; the clone is parsed, never imported.  The fake
is a deterministic ``RecordingTagTransport`` point store.

Scope (model review, 2026-11-05).  The author served the three writable PVs
(``TEMP_SP``, ``PAUSE``, ``START_CYCLE``) at R2 and bound ``PAUSE=1`` as the
e-stop, confirmed by reading ``PAUSE`` back.  Each putter only forwards a JSON
command on a ZeroMQ REQ socket that it closes without reading a reply
(cryostat.py:43-67), and a caproto pvproperty keeps the value its putter
accepted, so the read-back proves only that the IOC stored the put, not that
the controller paused anything; the clone has no heater-off command and nothing
stops a started magnet cycle.  Without a source-backed stop the writes stay
out (NOT COVERED) and the package observes only, the R0 scope the tag-bridge
preflight gives this card ("READY as an R0 observer only").  ``TEMP_SP`` is
not read either: it holds the last value put to the IOC (initially 0.050,
cryostat.py:22), not the controller's setpoint, which ``TEMP_SP_RB`` carries.
"""

from mhs.driver import Action, Fact, Field, TagDriver

#: Read PV suffixes exactly as the pinned ``ADR`` PVGroup declares them.
POINTS = {
    "temperature": {
        "pv": "TEMP", "type": "number", "access": "read", "source_ref": "cryostat.py:21",
        "description": "ADR temperature PV, documented by the clone as 'temperature in k'"},
    "setpoint_readback": {
        "pv": "TEMP_SP_RB", "type": "number", "access": "read", "source_ref": "cryostat.py:23",
        "description": "temperature setpoint read-back PV filled from the controller stream"},
    "temperature_rms": {
        "pv": "TEMP_RMS_UK", "type": "number", "access": "read", "source_ref": "cryostat.py:24",
        "description": "temperature RMS stability PV, documented by the clone as 'in uk'"},
    "alternate_temperature": {
        "pv": "ALT_TEMP", "type": "number", "access": "read", "source_ref": "cryostat.py:25",
        "description": "second temperature channel PV; the clone states no unit"},
    "heater_output": {
        "pv": "HEATER_OUT", "type": "number", "access": "read", "source_ref": "cryostat.py:26",
        "description": "heater output PV; the clone states no unit or range for it"},
    "state": {
        "pv": "STATE", "type": "string", "access": "read", "source_ref": "cryostat.py:27",
        "description": "ADR mode PV"},
    "cycle_uid": {
        "pv": "CYCLE_UID", "type": "string", "access": "read", "source_ref": "cryostat.py:28",
        "description": "cryo cycle identifier PV"},
}

#: The one observation capability (verb read, no input) over the same points.
READINGS = "x-cap.nsls-ii-sst.adr_readings.v1"

_TEMPERATURE = Field("number", unit="K", description="ADR temperature published by the IOC (TEMP, 'in k')")
_SETPOINT_RB = Field("number", description="setpoint read-back filled from the controller stream; the clone states "
                                           "no unit for it")
_RMS = Field("number", unit="uK", description="temperature RMS stability published by the IOC (TEMP_RMS_UK, 'in uk')")
_ALT = Field("number", description="second temperature channel; the clone states no unit")
_HEATER = Field("number", description="heater output as published by the IOC; the clone states no unit or range")
_STATE = Field("string", description="ADR mode string published by the IOC")
_UID = Field("string", description="cryo cycle identifier published by the IOC")


class ADR(TagDriver):
    device_id = "caproto-cryostat"
    device_kind = "thermal.zone"
    mode = "hardware"
    risk = "R0"
    native = "cryostat:ADR"
    backends = {"fake": ".fake:FakeADR", "hardware": ".native:connect"}
    vendor, model = "NSLS-II SST", "ADR cryostat"
    display_name = "NSLS-II SST ADR cryostat (caproto EPICS IOC, read only)"
    tags = ["cryostat", "adr", "epics", "caproto", "tag-bridge", "temperature", "read-only"]
    facts = [
        Fact("ADR is documented as a class to read temperatures from NIST's adr_gui.",
             source="upstream_code", ref="cryostat.py:17-20"),
        Fact("ADR declares TEMP as an ai pvproperty documented as 'temperature in k'.",
             source="upstream_code", ref="cryostat.py:21"),
        Fact("ADR declares TEMP_SP as an ai pvproperty with the initial value 0.050, documented as 'temperature "
             "setpoint'.", source="upstream_code", ref="cryostat.py:22"),
        Fact("The TEMP_SP putter sends the command set_temp_sp_k with the written value.",
             source="upstream_code", ref="cryostat.py:65-67"),
        Fact("ADR declares TEMP_SP_RB as an ai pvproperty documented as 'temperature setpoint readback'.",
             source="upstream_code", ref="cryostat.py:23"),
        Fact("The update hook writes TEMP_SP_RB from the controller message key temp_sp_rb.",
             source="upstream_code", ref="cryostat.py:87-88"),
        Fact("ADR declares TEMP_RMS_UK as an ai pvproperty documented as 'temperature rms stability in uk'.",
             source="upstream_code", ref="cryostat.py:24"),
        Fact("The update hook writes TEMP_RMS_UK from the controller message key stddev.",
             source="upstream_code", ref="cryostat.py:82-83"),
        Fact("ADR declares ALT_TEMP as an ai pvproperty documented as '2nd channel temperature'.",
             source="upstream_code", ref="cryostat.py:25"),
        Fact("The update hook writes ALT_TEMP from the controller message key alt_temp.",
             source="upstream_code", ref="cryostat.py:75-76"),
        Fact("ADR declares HEATER_OUT as an ai pvproperty documented as 'heater'.",
             source="upstream_code", ref="cryostat.py:26"),
        Fact("The update hook writes HEATER_OUT from the controller message key heater.",
             source="upstream_code", ref="cryostat.py:80-81"),
        Fact("ADR declares STATE as a string pvproperty documented as 'ADR Mode'.",
             source="upstream_code", ref="cryostat.py:27"),
        Fact("For the controller message key state, the update hook writes STATE only when the value differs from "
             "the current STATE value.", source="upstream_code", ref="cryostat.py:77-79"),
        Fact("ADR declares CYCLE_UID as a string pvproperty documented as 'Cycle UID'.",
             source="upstream_code", ref="cryostat.py:28"),
        Fact("For the controller message key uid, the update hook writes CYCLE_UID only when the value differs from "
             "the current CYCLE_UID value.", source="upstream_code", ref="cryostat.py:84-86"),
        Fact("ADR declares PAUSE as a writable pvproperty documented as 'Pause PID Loop'.",
             source="upstream_code", ref="cryostat.py:29"),
        Fact("The PAUSE putter sends pausePID when the written value is 1 and resumePID otherwise.",
             source="upstream_code", ref="cryostat.py:53-58"),
        Fact("ADR declares START_CYCLE as a writable pvproperty documented as 'Start Cryo Cycle'.",
             source="upstream_code", ref="cryostat.py:30"),
        Fact("The START_CYCLE putter sends start_mag_cycle when the written value is truthy.",
             source="upstream_code", ref="cryostat.py:60-63"),
        Fact("The update hook is a 0.1 s scan that receives one JSON message from the ZeroMQ SUB socket "
             "and dispatches temperature, alt_temp, state, heater, stddev, uid and temp_sp_rb.",
             source="upstream_code", ref="cryostat.py:69-88"),
        Fact("The ADR constructor connects a ZeroMQ SUB socket to the configured address and sub_port and "
             "subscribes to every message.",
             source="upstream_code", ref="cryostat.py:33-40"),
        Fact("command serializes method, params and kwargs as JSON, sends it on a ZeroMQ REQ socket to the "
             "configured control_port, closes the socket and does not read a reply.",
             source="upstream_code", ref="cryostat.py:43-51"),
    ]
    safe_state = ("No change: the package only reads the IOC's PVs; it writes no PV and declares no stop, so the "
                  "ADR controller, its PID loop, heater output and any magnet cycle stay as they are.")
    tag_config = {
        "profile": "epics-ca",
        "timeout_ms": 1000,
        "points": POINTS,
    }
    parameters = {
        "temperature": _TEMPERATURE,
        "setpoint_readback": _SETPOINT_RB,
        "temperature_rms": _RMS,
        "alternate_temperature": _ALT,
        "heater_output": _HEATER,
        "state": _STATE,
        "cycle_uid": _UID,
    }
    reads = {name: {"point": name} for name in POINTS}
    commands = {READINGS: {"read": {name: name for name in POINTS}}}
    actions = {
        READINGS: Action(
            name="read_adr", verb="read",
            description=("Read the ADR temperatures, setpoint read-back, RMS stability, heater output, mode and "
                         "cycle id the IOC last published (no input, no write)"),
            output={
                "temperature": _TEMPERATURE,
                "setpoint_readback": _SETPOINT_RB,
                "temperature_rms": _RMS,
                "alternate_temperature": _ALT,
                "heater_output": _HEATER,
                "state": _STATE,
                "cycle_uid": _UID,
            }),
    }
