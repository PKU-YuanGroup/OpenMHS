"""OpenMHS driver for gh.python-ivi/python-ivi: the LeCroy WaveRunner 104MXi-A oscilloscope over SCPI (family driver).

A ScpiDriver is configuration only: the class attributes below are the command map of the SCPI bridge, and the runtime
enforces every limit before a command reaches the wire.  The commands are the ones the clone's LeCroy WaveRunner Xi-A /
MXi-A IVI specific driver sends through its string interface (ivi/lecroy/lecroyBaseScope.py, ivi/lecroy/lecroyWRXIA.py
and ivi/lecroy/lecroyWR104MXIA.py); the upstream object is an IVI property API over that wire, which this driver does
not use: the bridge opens the instrument itself (``host``/``port`` or a VISA resource, options of the hardware
backend).

* reads: the trigger mode, the acquisition type, the sample mode, the number of averages, the timebase mode and the
  timebase reference, plus the frequency, period and peak-to-peak voltage measurements of channel C1;
* writes: those six settings, each limited by a value the clone states;
* the e-stop writes ``:stop``, the clone's command that stops a continuous acquisition.

Waveform and screenshot transfers (the clone's Waveform/Screenshot interfaces) are out of scope: they return large
arrays and this package does not fake them (facts.md).  Every Limit and Fact cites a line of the clone at the pinned
commit (cfa45ceade0758debe4bc24ba4c8195222cad1e2).  This package is model-authored and unreviewed, and its wire syntax
has not been tried on an instrument (facts.md).
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

BASE = "ivi/lecroy/lecroyBaseScope.py"


class LecroyWR104MXIA(ScpiDriver):
    device_id = "lecroy-wr104mxia"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "ivi.lecroy.lecroyWR104MXIA:lecroyWR104MXIA"
    backends = {"fake": ".fake:FakeLecroyWR104MXIA"}
    vendor, model = "LeCroy", "WaveRunner 104MXi-A"
    display_name = "LeCroy WaveRunner 104MXi-A oscilloscope"
    tags = ["oscilloscope", "lecroy", "waverunner", "wr104mxia", "scpi"]
    facts = [
        Fact("The clone's WaveRunner Xi-A / MXi-A driver supports the models WR204MXI-A, WR204XI-A, WR104MXI-A, "
             "WR104XI-A, WR64MXI-A, WR64XI-A, WR62XI-A, WR44MXI-A and WR44XI-A",
             source="upstream_code", ref="ivi/lecroy/lecroyWRXIA.py:78-79"),
        Fact("The WaveRunner 104MXi-A is a 4-channel, 1 GHz member: its constructor sets 4 analog channels, 0 digital "
             "channels and _bandwidth = 1e9", source="upstream_code", ref="ivi/lecroy/lecroyWR104MXIA.py:37-40"),
        Fact("The manufacturer identity field is 'LeCroy'", source="upstream_code", ref=f"{BASE}:212"),
        Fact("The identity response is split on commas into manufacturer (field 0), model (field 1) and firmware "
             "revision (field 3)", source="upstream_code", ref=f"{BASE}:477-481"),
        Fact("The clone turns the command header off when it constructs the driver ('CHDR OFF') so every response is "
             "a bare value", source="upstream_code", ref=f"{BASE}:221-222"),
        Fact("TriggerModes is the set auto, norm, single, stop", source="upstream_code", ref=f"{BASE}:44"),
        Fact("The trigger mode is set with TRMD and queried with TRMD?", source="upstream_code",
             ref=f"{BASE}:1209-1221"),
        Fact("The acquisition type is sent with :acquire:type, mapping normal to norm, peak_detect to peak, "
             "high_resolution to hres and average to aver", source="upstream_code", ref=f"{BASE}:35-40"),
        Fact("The sample mode is sent with :acquire:mode, mapping real_time to rtim and equivalent_time to etim",
             source="upstream_code", ref=f"{BASE}:94-95"),
        Fact("The number of averages is sent with :acquire:count and is limited to 1 through 65536",
             source="upstream_code", ref=f"{BASE}:1589-1592"),
        Fact("The timebase mode is sent with :timebase:mode, mapping main to main, window to wind, xy to xy and roll "
             "to roll", source="upstream_code", ref=f"{BASE}:141-145"),
        Fact("The timebase reference is sent with :timebase:reference, mapping left to left, center to cent and right "
             "to righ", source="upstream_code", ref=f"{BASE}:146-149"),
        Fact("The measurement functions of the clone's mapping include frequency, period and voltage_peak_to_peak "
             "(sent as vpp)", source="upstream_code", ref=f"{BASE}:101-107"),
        Fact("A waveform measurement query is built as ':measure:<function>? <channel>', for example "
             "':measure:frequency? C1'", source="upstream_code", ref=f"{BASE}:1527-1543"),
        Fact("A continuous acquisition is stopped with ':stop' (the boolean trigger-continuous setter writes 'run' "
             "for true and 'stop' for false)", source="upstream_code", ref=f"{BASE}:1573-1579"),
        Fact("Analog channels are named C1 through C4", source="upstream_code", ref=f"{BASE}:563-564"),
    ]
    safe_state = "acquisition stopped by ':stop', the clone's stop command for a continuous acquisition"
    idn = {"expect": "(?i)^lecroy,"}

    parameters = {
        "trigger_mode": Field(
            "string", writable=True, description="Trigger mode (TRMD): auto, norm, single or stop",
            limit=Limit(allowed=["auto", "norm", "single", "stop"], source="upstream_code", ref=f"{BASE}:44",
                        reason="TriggerModes = set(['auto', 'norm', 'single', 'stop']) on line 44")),
        "acquisition_type": Field(
            "string", writable=True,
            description="Acquisition type in the wire tokens of the clone's mapping: norm, peak, hres or aver "
                        "(:acquire:type)",
            limit=Limit(allowed=["norm", "peak", "hres", "aver"], source="upstream_code", ref=f"{BASE}:35-40",
                        reason="AcquisitionTypeMapping sends the values norm, peak, hres and aver (lines 35-40)")),
        "sample_mode": Field(
            "string", writable=True,
            description="Sample mode in the wire tokens of the clone's mapping: rtim (real time) or etim "
                        "(equivalent time) (:acquire:mode)",
            limit=Limit(allowed=["rtim", "etim"], source="upstream_code", ref=f"{BASE}:94-95",
                        reason="SampleModeMapping sends real_time as rtim and equivalent_time as etim (lines 94-95)")),
        "acquisition_averages": Field(
            "integer", unit="1", writable=True,
            description="Number of averages of an average acquisition (:acquire:count)",
            limit=Limit(min=1, max=65536, source="upstream_code", ref=f"{BASE}:1589-1592",
                        reason="the clone refuses a count below 1 or above 65536 (line 1589) and sends it at line "
                               "1592")),
        "timebase_mode": Field(
            "string", writable=True,
            description="Timebase mode in the wire tokens of the clone's mapping: main, wind, xy or roll "
                        "(:timebase:mode)",
            limit=Limit(allowed=["main", "wind", "xy", "roll"], source="upstream_code", ref=f"{BASE}:141-145",
                        reason="TimebaseModeMapping sends the values main, wind, xy and roll (lines 141-145)")),
        "timebase_reference": Field(
            "string", writable=True,
            description="Timebase reference in the wire tokens of the clone's mapping: left, cent or righ "
                        "(:timebase:reference)",
            limit=Limit(allowed=["left", "cent", "righ"], source="upstream_code", ref=f"{BASE}:146-149",
                        reason="TimebaseReferenceMapping sends the values left, cent and righ (lines 146-149)")),
        "measurement_frequency": Field(
            "number", unit="Hz",
            description="Frequency measured on channel C1 (:measure:frequency? C1)"),
        "measurement_period": Field(
            "number", unit="s", description="Period measured on channel C1 (:measure:period? C1)"),
        "measurement_vpp": Field(
            "number", unit="V",
            description="Peak-to-peak voltage measured on channel C1 (:measure:vpp? C1)"),
    }
    reads = {
        "trigger_mode": {"query": "TRMD?", "parse": {"kind": "str"}},
        "acquisition_type": {"query": ":acquire:type?", "parse": {"kind": "str"}},
        "sample_mode": {"query": ":acquire:mode?", "parse": {"kind": "str"}},
        "acquisition_averages": {"query": ":acquire:count?", "parse": {"kind": "int"}},
        "timebase_mode": {"query": ":timebase:mode?", "parse": {"kind": "str"}},
        "timebase_reference": {"query": ":timebase:reference?", "parse": {"kind": "str"}},
        "measurement_frequency": {"query": ":measure:frequency? C1", "parse": {"kind": "float"}},
        "measurement_period": {"query": ":measure:period? C1", "parse": {"kind": "float"}},
        "measurement_vpp": {"query": ":measure:vpp? C1", "parse": {"kind": "float"}},
    }
    writes = {
        "trigger_mode": {"write": "TRMD {value}", "type": "string"},
        "acquisition_type": {"write": ":acquire:type {value}", "type": "string"},
        "sample_mode": {"write": ":acquire:mode {value}", "type": "string"},
        "acquisition_averages": {"write": ":acquire:count {value:d}", "type": "integer"},
        "timebase_mode": {"write": ":timebase:mode {value}", "type": "string"},
        "timebase_reference": {"write": ":timebase:reference {value}", "type": "string"},
    }
    safety_bindings = {"estop": {"write": ":stop"}}
