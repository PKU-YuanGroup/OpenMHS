"""OpenMHS driver for gh.sqlim/sr860-python: the SR860/865/865A lock-in amplifier over SCPI.

A ScpiDriver is configuration only: the class attributes below are the command map of the SCPI bridge, and the
runtime enforces every limit before a command reaches the wire.  The commands and reply formats are the ones the
upstream package uses in its API table (srs/sr860.py:8-71): a setting is written as ``COMMAND value`` and read back
as ``COMMAND?``.  The upstream class opens a pyvisa resource itself; this driver does not import it: the bridge
opens the instrument (``host``/``port`` or a VISA resource) and only shares the command words.

* reads: the reference settings (frequency, amplitude, phase, DC offset, harmonic), the two filters, the X/Y/R
  offset values and enables, the three signal components and the P (theta) value.  The data channels are
  ``OUTP? 0`` to ``OUTP? 3`` (srs/sr860.py:62-65).  The time-constant index is read as a separate integer, because
  ``OFLT?`` returns the index while the setting is in seconds (srs/sr860.py:559, 562-580).
* writes: settings whose bounds the upstream code states, each with a sourced Limit; the boolean enables are
  written as ``1``/``0`` exactly as the upstream package converts and sends them (srs/instr.py:50).
* the e-stop writes the lowest stated sine output amplitude, ``SLVL 0.000000001`` (1 nV, srs/sr860.py:201).

Every Fact and Limit cites a line of the clone at the pinned commit (00fa066450759cfa994b1e999eeec7074bc5724c).
This package is model-authored and unreviewed; nothing here ran any hardware backend, and the wire syntax was not
tried on an instrument.
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

UPSTREAM = "srs/sr860.py"

#: The 22 time constants of the upstream tuple, in OFLT-index order (srs/sr860.py:559).
TIME_CONSTANTS = (1e-06, 3e-06, 1e-05, 3e-05, 0.0001, 0.0003, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3,
                  1, 3, 10, 30, 100, 300, 1000.0, 3000.0, 10000.0, 30000.0)


class Sr860(ScpiDriver):
    device_id = "sr860"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "srs.sr860:SR860"
    backends = {"fake": ".fake:FakeSr860"}
    vendor, model = "Stanford Research Systems", "SR860/SR865/SR865A DSP lock-in amplifier"
    display_name = "Stanford Research Systems SR860 DSP lock-in amplifier"
    tags = ["lock-in amplifier", "sr860", "sr865", "sr865a", "scpi"]

    facts = [
        Fact("A setting is written as its command word and a formatted value and read back with the same word "
             "plus '?' (for example 'FREQ {:.3f}' and 'FREQ?').",
             source="upstream_code", ref=f"{UPSTREAM}:11"),
        Fact("The *IDN? reply is comma separated and the second field is the model used to choose the frequency "
             "range.", source="upstream_code", ref=f"{UPSTREAM}:132-134"),
        Fact("The SR860 frequency range is 0.001 Hz to 500 kHz with 1 mHz resolution; the SR865 range is "
             "0.001 Hz to 2 MHz and the SR865A range is 0.001 Hz to 4 MHz.",
             source="upstream_code", ref=f"{UPSTREAM}:80-84"),
        Fact("The sine output amplitude range is 1e-9 V to 2.0 V.", source="upstream_code", ref=f"{UPSTREAM}:201"),
        Fact("The reference phase range is -360000 to 360000 degrees.", source="upstream_code",
             ref=f"{UPSTREAM}:231"),
        Fact("The sine output DC offset range is -5.0 V to 5.0 V.", source="upstream_code",
             ref=f"{UPSTREAM}:261"),
        Fact("The harmonic number range is 1 to 99.", source="upstream_code", ref=f"{UPSTREAM}:291"),
        Fact("The time constants are the 22 values 1e-6, 3e-6, 1e-5, 3e-5 and so on up to 30000 s.",
             source="upstream_code", ref=f"{UPSTREAM}:559"),
        Fact("The X, Y and R offsets are percentages in the range -999.99% to 999.99%.",
             source="upstream_code", ref=f"{UPSTREAM}:798"),
        Fact("The offset enables are written with 'COFA n, value' and read with 'COFA? n' for n = 0 (X), "
             "1 (Y) and 2 (R).", source="upstream_code", ref=f"{UPSTREAM}:50-52"),
        Fact("The advanced filter is written with ADVFILT and read with ADVFILT?.", source="upstream_code",
             ref=f"{UPSTREAM}:27"),
        Fact("X, Y, R and P are read with OUTP? 0, OUTP? 1, OUTP? 2 and OUTP? 3.", source="upstream_code",
             ref=f"{UPSTREAM}:62-65"),
        Fact("The X data output is in volts.", source="upstream_code", ref=f"{UPSTREAM}:1020"),
        Fact("The P data output is in degrees.", source="upstream_code", ref=f"{UPSTREAM}:1044"),
        Fact("init() writes a known state: 1 kHz frequency, 1 V amplitude, 0 phase, 0 DC offset, harmonic 1, "
             "AC coupling, 24 dB/oct filter and the sync filter on.", source="upstream_code",
             ref=f"{UPSTREAM}:88-112"),
    ]
    safe_state = "sine output amplitude set to its lowest stated value, 1e-9 V"
    idn = {"expect": "^[^,]*,SR86[05]A?,"}

    parameters = {
        "frequency": Field(
            "number", unit="Hz", writable=True, description="Reference frequency",
            limit=Limit(min=0.001, max=500000.0, source="upstream_code", ref=f"{UPSTREAM}:80")),
        "amplitude": Field(
            "number", unit="V", writable=True, description="Sine output amplitude",
            limit=Limit(min=1e-9, max=2.0, source="upstream_code", ref=f"{UPSTREAM}:201")),
        "phase": Field(
            "number", unit="deg", writable=True, description="Reference phase",
            limit=Limit(min=-360000, max=360000, source="upstream_code", ref=f"{UPSTREAM}:231")),
        "dc_offset": Field(
            "number", unit="V", writable=True, description="Sine output DC offset",
            limit=Limit(min=-5.0, max=5.0, source="upstream_code", ref=f"{UPSTREAM}:261")),
        "harmonic": Field(
            "integer", unit="1", writable=True, description="Reference harmonic",
            limit=Limit(min=1, max=99, source="upstream_code", ref=f"{UPSTREAM}:291")),
        "time_constant": Field(
            "number", unit="s", writable=True, description="Filter time constant (OFLT index)",
            limit=Limit(allowed=TIME_CONSTANTS, source="upstream_code", ref=f"{UPSTREAM}:559")),
        "time_constant_index": Field(
            "integer", unit="1", description="Time-constant index (OFLT?)"),
        "sync_filter_enable": Field(
            "boolean", writable=True, description="Sync filter enabled"),
        "adv_filter_enable": Field(
            "boolean", writable=True, description="Advanced filter enabled"),
        "x_offset": Field(
            "number", unit="%", writable=True, description="X offset (%)",
            limit=Limit(min=-999.99, max=999.99, source="upstream_code", ref=f"{UPSTREAM}:798")),
        "y_offset": Field(
            "number", unit="%", writable=True, description="Y offset (%)",
            limit=Limit(min=-999.99, max=999.99, source="upstream_code", ref=f"{UPSTREAM}:798")),
        "r_offset": Field(
            "number", unit="%", writable=True, description="R offset (%)",
            limit=Limit(min=-999.99, max=999.99, source="upstream_code", ref=f"{UPSTREAM}:798")),
        "x_offset_enable": Field(
            "boolean", writable=True, description="X offset enabled"),
        "y_offset_enable": Field(
            "boolean", writable=True, description="Y offset enabled"),
        "r_offset_enable": Field(
            "boolean", writable=True, description="R offset enabled"),
        "x": Field("number", unit="V", description="In-phase signal component (OUTP? 0)"),
        "y": Field("number", unit="V", description="Quadrature signal component (OUTP? 1)"),
        "r": Field("number", unit="V", description="Signal magnitude (OUTP? 2)"),
        "theta": Field("number", unit="deg", description="Signal phase P relative to the reference (OUTP? 3)"),
    }

    reads = {
        "frequency": {"query": "FREQ?", "parse": {"kind": "float"}},
        "amplitude": {"query": "SLVL?", "parse": {"kind": "float"}},
        "phase": {"query": "PHAS?", "parse": {"kind": "float"}},
        "dc_offset": {"query": "SOFF?", "parse": {"kind": "float"}},
        "harmonic": {"query": "HARM?", "parse": {"kind": "int"}},
        "time_constant_index": {"query": "OFLT?", "parse": {"kind": "int"}},
        "sync_filter_enable": {"query": "SYNC?", "parse": {"kind": "bool"}},
        "adv_filter_enable": {"query": "ADVFILT?", "parse": {"kind": "bool"}},
        "x_offset": {"query": "COFP? 0", "parse": {"kind": "float"}},
        "y_offset": {"query": "COFP? 1", "parse": {"kind": "float"}},
        "r_offset": {"query": "COFP? 2", "parse": {"kind": "float"}},
        "x_offset_enable": {"query": "COFA? 0", "parse": {"kind": "bool"}},
        "y_offset_enable": {"query": "COFA? 1", "parse": {"kind": "bool"}},
        "r_offset_enable": {"query": "COFA? 2", "parse": {"kind": "bool"}},
        "x": {"query": "OUTP? 0", "parse": {"kind": "float"}},
        "y": {"query": "OUTP? 1", "parse": {"kind": "float"}},
        "r": {"query": "OUTP? 2", "parse": {"kind": "float"}},
        "theta": {"query": "OUTP? 3", "parse": {"kind": "float"}},
    }

    writes = {
        "frequency": {"write": "FREQ {value:.3f}", "type": "number"},
        "amplitude": {"write": "SLVL {value:.9f}", "type": "number"},
        "phase": {"write": "PHAS {value:.7f}", "type": "number"},
        "dc_offset": {"write": "SOFF {value:.4f}", "type": "number"},
        "harmonic": {"write": "HARM {value:d}", "type": "integer"},
        "time_constant": {"write": "OFLT {value:d}", "type": "integer",
                          "enum_map": {seconds: index for index, seconds in enumerate(TIME_CONSTANTS)}},
        "sync_filter_enable": {"write": "SYNC {value:d}", "type": "boolean"},
        "adv_filter_enable": {"write": "ADVFILT {value:d}", "type": "boolean"},
        "x_offset": {"write": "COFP 0, {value:.2f}", "type": "number"},
        "y_offset": {"write": "COFP 1, {value:.2f}", "type": "number"},
        "r_offset": {"write": "COFP 2, {value:.2f}", "type": "number"},
        "x_offset_enable": {"write": "COFA 0, {value:d}", "type": "boolean"},
        "y_offset_enable": {"write": "COFA 1, {value:d}", "type": "boolean"},
        "r_offset_enable": {"write": "COFA 2, {value:d}", "type": "boolean"},
    }

    safety_bindings = {"estop": {"write": "SLVL 0.000000001"}}
