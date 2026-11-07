"""OpenMHS driver for gh.jonathanvanschenck/sr830-python: the SR830 lock-in amplifier over its text commands.

A ScpiDriver is configuration only: the class attributes below are the command map of the SCPI bridge, and the
runtime enforces every limit before a command reaches the wire.  The commands are the exact lines the upstream
wrapper sends (``OFLT ?``, ``SENS ?``, ``SYNC ?``, ``FREQ ?`` and ``OUTP? <n>`` in sr830.py; note the space before
the question mark in four of them).  The upstream class opens the instrument through pyVISA over GPIB, which this
driver does not use: the bridge opens the instrument itself (``host``/``port`` or a VISA resource, options of the
hardware backend), so only the command lines are shared.

* reads: the reference frequency, the integration-time index, the sensitivity index, the synchronous-filter index
  and the four data values X, Y, R and Theta;
* writes: the integration-time index, the sensitivity index and the synchronous-filter index, each bounded by the
  table the upstream code states;
* the e-stop writes ``SYNC 0`` and ``SENS 26``: the synchronous filter is turned off and the least sensitive range
  (1 V full scale) is selected.  This wrapper sets no excitation output, so there is no source to switch off.

Every Limit and Fact cites a line of the clone at the pinned commit (fdce76ec409d2fd768a87719854deb2395152026).
This package is model-authored and unreviewed, and its command lines were not tried on an instrument.
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

UPSTREAM = "sr830.py"


class Sr830(ScpiDriver):
    device_id = "sr830"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "sr830:SR830"
    backends = {"fake": ".fake:FakeSr830"}
    vendor, model = "Stanford Research Systems", "SR830 lock-in amplifier"
    display_name = "SRS SR830 lock-in amplifier"
    tags = ["lock-in amplifier", "sr830", "gpib", "scpi"]
    facts = [
        Fact("The class controls a Stanford Research SR830 lock-in amplifier over a GPIB connection through pyVISA",
             source="upstream_code", ref=f"{UPSTREAM}:5-11"),
        Fact("The constructor opens the VISA resource and queries '*IDN?' when it connects", source="upstream_code",
             ref=f"{UPSTREAM}:46-49"),
        Fact("Sensitivity settings run from 2 nV at index 0 to 1 V at index 26", source="upstream_code",
             ref=f"{UPSTREAM}:50-58"),
        Fact("Integration times run from 10 us at index 0 to 30 ks at index 19", source="upstream_code",
             ref=f"{UPSTREAM}:69-75"),
        Fact("An integration time is written as 'OFLT <index>' and read back with 'OFLT ?'", source="upstream_code",
             ref=f"{UPSTREAM}:98-106"),
        Fact("A sensitivity is written as 'SENS <index>' and read back with 'SENS ?'", source="upstream_code",
             ref=f"{UPSTREAM}:122-130"),
        Fact("The synchronous filter is written as 'SYNC 0' (off) or 'SYNC 1' (on) and read back with 'SYNC ?'; "
             "the upstream docstring says it should only be on below 200 Hz", source="upstream_code",
             ref=f"{UPSTREAM}:132-143"),
        Fact("The reference frequency is read with 'FREQ ?' in Hz", source="upstream_code",
             ref=f"{UPSTREAM}:145-146"),
        Fact("A data value is read with 'OUTP? <index>': X at 1, Y at 2, R at 3 and phase in degrees at 4",
             source="upstream_code", ref=f"{UPSTREAM}:148-154"),
        Fact("getRTh returns R in volts and Theta in degrees, and getXY returns X and Y in volts",
             source="upstream_code", ref=f"{UPSTREAM}:155-158"),
    ]
    safe_state = ("synchronous filter off (SYNC 0) and the least sensitive 1 V range selected (SENS 26); "
                  "this wrapper sets no excitation output")
    # The upstream constructor queries *IDN? and prints the reply; it does not state a pattern, so no pattern is
    # configured here.
    idn = True

    parameters = {
        "frequency": Field("number", unit="Hz",
                           description="Reference frequency reported by FREQ ?"),
        "time_constant_index": Field(
            "integer", unit="1", writable=True,
            description="Integration-time index written by OFLT (0 = 10 us ... 19 = 30 ks)",
            limit=Limit(min=0, max=19, source="upstream_code", ref=f"{UPSTREAM}:69-75",
                        reason="the oflt dictionary maps index 0 (10 us, line 69) through index 19 (30 ks, "
                               "line 75)")),
        "sensitivity_index": Field(
            "integer", unit="1", writable=True,
            description="Sensitivity index written by SENS (0 = 2 nV ... 26 = 1 V)",
            limit=Limit(min=0, max=26, source="upstream_code", ref=f"{UPSTREAM}:50-58",
                        reason="the sens dictionary maps index 0 (2 nV, line 50) through index 26 (1 V, line 58)")),
        "sync_filter": Field(
            "integer", unit="1", writable=True,
            description="Synchronous-filter index written by SYNC (0 = off, 1 = on)",
            limit=Limit(min=0, max=1, source="upstream_code", ref=f"{UPSTREAM}:136-137",
                        reason="the setSync docstring states 0->OFF on line 136 and 1->ON on line 137")),
        "x": Field("number", unit="V", description="In-phase component X read with OUTP? 1"),
        "y": Field("number", unit="V", description="Quadrature component Y read with OUTP? 2"),
        "r": Field("number", unit="V", description="Magnitude R read with OUTP? 3"),
        "theta": Field("number", unit="deg", description="Phase in degrees read with OUTP? 4"),
    }
    reads = {
        "frequency": {"query": "FREQ ?", "parse": {"kind": "float"}},
        "time_constant_index": {"query": "OFLT ?", "parse": {"kind": "int"}},
        "sensitivity_index": {"query": "SENS ?", "parse": {"kind": "int"}},
        "sync_filter": {"query": "SYNC ?", "parse": {"kind": "int"}},
        "x": {"query": "OUTP? 1", "parse": {"kind": "float"}},
        "y": {"query": "OUTP? 2", "parse": {"kind": "float"}},
        "r": {"query": "OUTP? 3", "parse": {"kind": "float"}},
        "theta": {"query": "OUTP? 4", "parse": {"kind": "float"}},
    }
    writes = {
        "time_constant_index": {"write": "OFLT {value:d}", "type": "integer"},
        "sensitivity_index": {"write": "SENS {value:d}", "type": "integer"},
        "sync_filter": {"write": "SYNC {value:d}", "type": "integer"},
    }
    safety_bindings = {"estop": {"write": ["SYNC 0", "SENS 26"]}}
