"""OpenMHS driver for gh.zhangxp93/pyinsts: the Rohde & Schwarz FSV3030 spectrum analyzer over SCPI.

A ScpiDriver is configuration only: the class attributes below are the command map of the SCPI bridge, and
the runtime enforces every limit before a command reaches the wire.  The commands are the raw commands of the
upstream class ``pyinsts.instrument_drivers.rohde_schwarz.fsv3030:FSV3030Sp`` (and the SCPI replies its own
simulator file records); the bridge opens the instrument itself (``host``/``port`` or a VISA resource, options
of the hardware backend), so the upstream package is not imported.

* reads: the center frequency, the marker frequency and level, and the delta-marker frequency and level;
* writes: center frequency, span, marker frequency, the error display and the continuous peak search.  No text
  of the clone states a frequency range of this analyzer, so the three numeric writes are
  ``Limit.operator_required``: the site supplies their bounds before use (``site-limits.example.json`` shows
  the overlay);
* the e-stop writes ``ABOR``: the measurement is stopped; this driver energizes no output.

Only marker 1 and delta marker 1 are exposed.  The upstream methods accept marker numbers 1 to 7 (``fsv3030.py``
docstrings), but a family command map cannot vary the marker number inside the command word without building the
command from parts, so markers 2 to 7 and the trace arrays are not covered (see notes in RESULT.json).

Every Limit and Fact cites a line of the clone at the pinned commit
(3bcaa2acbea14bb3ed30de140808e9d0de70c96a).  This package is model-authored and unreviewed; its wire syntax was
never tried on an instrument.
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

FSV = "src/pyinsts/instrument_drivers/rohde_schwarz/fsv3030.py"
BASE = "src/pyinsts/instrument_drivers/baseinstrument.py"
SIM = "src/pyinsts/instrument/sim/Fsv3030.yaml"

ON_OFF = ["ON", "OFF"]


class Fsv3030(ScpiDriver):
    device_id = "fsv3030"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "pyinsts.instrument_drivers.rohde_schwarz.fsv3030:FSV3030Sp"
    backends = {"fake": ".fake:FakeFsv3030"}
    vendor, model = "Rohde & Schwarz", "FSV3030 spectrum analyzer"
    display_name = "Rohde & Schwarz FSV3030 spectrum analyzer"
    tags = ["spectrum analyzer", "fsv3030", "rohde schwarz", "scpi"]
    facts = [
        Fact("FSV3030Sp is the spectrum-mode class of the FSV3030 driver family and derives from FSV3030Base",
             source="upstream_code", ref=f"{FSV}:239"),
        Fact("The FSV3030 constructor opens the instrument through BaseInstrument and sends SYST:DISP:UPD ON",
             source="upstream_code", ref=f"{FSV}:13-23"),
        Fact("BaseInstrument writes *CLS and then queries *IDN? while it connects", source="upstream_code",
             ref=f"{BASE}:172-176"),
        Fact("The center frequency is written as 'SENSE:FREQ:CENT <value><unit>'", source="upstream_code",
             ref=f"{FSV}:110"),
        Fact("The span is written as 'FREQ:SPAN <value><unit>' and the full span as 'SENS:FREQ:SPAN:FULL'",
             source="upstream_code", ref=f"{FSV}:258-267"),
        Fact("set_mark_freq accepts marker numbers 1 to 7 and writes 'CALC:MARK<x>:X <Hz value>' after converting "
             "the caller's unit to Hz", source="upstream_code", ref=f"{FSV}:118-134"),
        Fact("query_marker_x reads 'CALC:MARK<x>:X?' and divides the reply by the requested unit, so the reply "
             "is in Hz", source="upstream_code", ref=f"{FSV}:138-155"),
        Fact("query_marker_y reads 'CALC:MARK<x>:Y?' and returns the reply as a float", source="upstream_code",
             ref=f"{FSV}:157-165"),
        Fact("query_delta_mkr_x reads 'CALC:DELT<x>:X?' and query_delta_mkr_y reads 'CALC:DELT<x>:Y?'",
             source="upstream_code", ref=f"{FSV}:364-384"),
        Fact("set_err_disp writes 'SYST:ERR:DISP ON' or 'SYST:ERR:DISP OFF'", source="upstream_code",
             ref=f"{FSV}:94-101"),
        Fact("set_continuous_peak writes 'CALCulate1:MARKer1:MAXimum:AUTO ON' or '... OFF'", source="upstream_code",
             ref=f"{FSV}:286-293"),
        Fact("set_abort_meas writes 'ABOR' to abort the current measurement", source="upstream_code",
             ref=f"{FSV}:61-67"),
        Fact("The clone's FSV3030 simulator identifies the instrument as 'Rohde&Schwarz,FSV3030,100001,3.40'",
             source="upstream_code", ref=f"{SIM}:12-13"),
        Fact("The clone's FSV3030 simulator answers FREQ:CENT?", source="upstream_code", ref=f"{SIM}:60-62"),
        Fact("The clone's FSV3030 simulator answers CALC:MARK1:X?, CALC:MARK1:Y?, CALC:DELT1:X? and "
             "CALC:DELT1:Y?", source="upstream_code", ref=f"{SIM}:113-143"),
    ]
    safe_state = "measurement aborted (ABOR); this driver energizes no output"
    idn = {"expect": "^Rohde&Schwarz,FSV3030"}

    parameters = {
        "center_frequency": Field(
            "number", unit="Hz", writable=True, description="Center frequency of the analyzer (SENSE:FREQ:CENT)",
            limit=Limit.operator_required(
                "no text of the clone states the tuning range of the FSV3030; the simulator defaults are test "
                "data, not bounds, so the site supplies the range of its analyzer")),
        "span": Field(
            "number", unit="Hz", writable=True, description="Frequency span of the analyzer (FREQ:SPAN)",
            limit=Limit.operator_required(
                "no text of the clone states the span range of the FSV3030; the site supplies the range of its "
                "analyzer")),
        "marker_frequency": Field(
            "number", unit="Hz", writable=True, description="Frequency of marker 1 (CALC:MARK1:X)",
            limit=Limit.operator_required(
                "no text of the clone states the frequency range of a marker; the site supplies the range of its "
                "analyzer")),
        "error_display": Field(
            "string", enum=ON_OFF, writable=True, description="Show the instrument error messages (SYST:ERR:DISP)",
            limit=Limit(allowed=ON_OFF, source="upstream_code", ref=f"{FSV}:94-101")),
        "continuous_peak": Field(
            "string", enum=ON_OFF, writable=True,
            description="Continuous peak search of marker 1 (CALCulate1:MARKer1:MAXimum:AUTO)",
            limit=Limit(allowed=ON_OFF, source="upstream_code", ref=f"{FSV}:286-293")),
        "marker_level": Field(
            "number", description="Level of marker 1 (CALC:MARK1:Y?); the clone does not state its unit"),
        "delta_marker_frequency": Field(
            "number", unit="Hz", description="Frequency of delta marker 1 (CALC:DELT1:X?)"),
        "delta_marker_level": Field(
            "number", description="Level of delta marker 1 (CALC:DELT1:Y?); the clone does not state its unit"),
    }
    reads = {
        "center_frequency": {"query": "FREQ:CENT?", "parse": {"kind": "float"}},
        "marker_frequency": {"query": "CALC:MARK1:X?", "parse": {"kind": "float"}},
        "marker_level": {"query": "CALC:MARK1:Y?", "parse": {"kind": "float"}},
        "delta_marker_frequency": {"query": "CALC:DELT1:X?", "parse": {"kind": "float"}},
        "delta_marker_level": {"query": "CALC:DELT1:Y?", "parse": {"kind": "float"}},
    }
    writes = {
        "center_frequency": {"write": "SENSE:FREQ:CENT {value:.10g}Hz", "type": "number"},
        "span": {"write": "FREQ:SPAN {value:.10g}Hz", "type": "number"},
        "marker_frequency": {"write": "CALC:MARK1:X {value:.10g}", "type": "number"},
        "error_display": {"write": "SYST:ERR:DISP {value}", "type": "string"},
        "continuous_peak": {"write": "CALCulate1:MARKer1:MAXimum:AUTO {value}", "type": "string"},
    }
    safety_bindings = {"estop": {"write": "ABOR"}}
