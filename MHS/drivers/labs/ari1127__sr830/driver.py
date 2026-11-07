"""OpenMHS driver for gh.ari1127/sr830: the SRS SR830 lock-in amplifier over SCPI (a family driver).

A ScpiDriver is configuration only.  The class attributes below are the command map of the SCPI bridge and the
runtime enforces every limit before a line reaches the wire.  The upstream clone is a thin pyvisa wrapper: every
method writes or asks one line whose command word is written out in ``SR830.py``, so this is the family shape the
card names and not a direct driver over the upstream class.  Only the lines are shared; the bridge opens the
instrument itself (``host``/``port`` or a ``visa_resource``), while the clone's ``device`` class opens a VISA
resource at construction (``SR830.py:5-7``).

* reads: X, Y, R, Theta and the raw ``SNAP?1,2,3,4`` snapshot, plus the settings the clone can query;
* writes: the scalar settings that the clone sends with one argument; the time-constant and sensitivity indexes
  have allowed sets because the clone's tables state them, every other numeric bound is operator-required
  because no line of the clone states a device range;
* the e-stop writes ``SLVL 0``: the sine output amplitude, the one output this driver sets, goes to 0 V.

The write forms that take several arguments (``DDEF``, ``OEXP``) and the commands whose effect has no query in the
clone (``OVRM``, ``*RST`` and the auto functions) are not exposed; their read forms are exposed where the clone
has one, and facts.md lists both.  Every Limit and Fact cites a line of the clone at the pinned commit
(930c9c5dcd8016b19e8c0988599f8f76cd928a12).  This package is model-authored and unreviewed; no hardware backend
was run.
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

UPSTREAM = "SR830.py"

#: The clone's time-constant table (SR830.py:8-28) addresses 20 settings by index, 0 = 10 us through 19 = 30 ks.
TIME_CONSTANT_INDEXES = list(range(20))
#: The clone's sensitivity table (SR830.py:29-56) addresses 27 settings by index, 0 = 2 nV through 26 = 1 V.
SENSITIVITY_INDEXES = list(range(27))

_UNSOURCED_RANGE = ("the clone passes the integer code straight through and no line states its allowed values; "
                    "the operator supplies the instrument's range")


class Sr830(ScpiDriver):
    device_id = "sr830"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "SR830:device"
    backends = {"fake": ".fake:FakeSr830"}
    vendor, model = "Stanford Research Systems", "SR830 lock-in amplifier"
    display_name = "SRS SR830 lock-in amplifier"
    tags = ["lock-in amplifier", "sr830", "scpi", "phase-sensitive detection"]
    facts = [
        Fact("The upstream class is device and opens the VISA resource passed to __init__ (default GPIB0::14)",
             source="upstream_code", ref=f"{UPSTREAM}:5-7"),
        Fact("X, Y, R and Theta are read with OUTP? 1 through OUTP? 4 and each reply is converted to float",
             source="upstream_code", ref=f"{UPSTREAM}:151-158"),
        Fact("get_all asks SNAP?1,2,3,4 for the four data values in one exchange",
             source="upstream_code", ref=f"{UPSTREAM}:149-150"),
        Fact("The demo block parses the get_all reply as comma-separated X, Y, R and Theta in that order",
             source="upstream_code", ref=f"{UPSTREAM}:180-184"),
        Fact("The time constant is addressed by index: 0 is 10 us, 6 is 10 ms, 10 is 1 s and 19 is 30 ks",
             source="upstream_code", ref=f"{UPSTREAM}:8-28"),
        Fact("The sensitivity is addressed by index: 0 is 2 nV, 17 is 1 mV, 23 is 100 mV and 26 is 1 V",
             source="upstream_code", ref=f"{UPSTREAM}:29-56"),
        Fact("A setting is sent as the command word followed by one argument (FREQ %f, SLVL %f, PHAS %f)",
             source="upstream_code", ref=f"{UPSTREAM}:109-120"),
        Fact("A query with an argument is sent as the command word, a question mark and the argument (DDEF? %i)",
             source="upstream_code", ref=f"{UPSTREAM}:101-104"),
        Fact("The front panel is overridden with OVRM 1 (disabled) and OVRM 0 (enabled)",
             source="upstream_code", ref=f"{UPSTREAM}:62-65"),
        Fact("The reset method writes *RST", source="upstream_code", ref=f"{UPSTREAM}:58-59"),
        Fact("The auxiliary output is written as AUXV output, value with three decimal places",
             source="upstream_code", ref=f"{UPSTREAM}:121-122"),
        Fact("The auxiliary output is read back as AUXV? output", source="upstream_code", ref=f"{UPSTREAM}:169-170"),
    ]
    safe_state = "sine output amplitude (SLVL) set to 0 V"
    idn = False  # the clone has no identity query; *IDN? would be a line the upstream never sends

    parameters = {
        # Data the instrument measures.
        "x": Field("number", description="In-phase component X (OUTP? 1)"),
        "y": Field("number", description="Quadrature component Y (OUTP? 2)"),
        "r": Field("number", description="Magnitude R (OUTP? 3)"),
        "theta": Field("number", description="Phase Theta (OUTP? 4)"),
        "snapshot": Field("string", description="Raw SNAP?1,2,3,4 reply, X,Y,R,Theta in that order"),
        # Reference and sine output.
        "frequency": Field("number", unit="Hz", writable=True, description="Reference frequency (FREQ)",
                           limit=Limit.operator_required(
                               "no line of the clone states the FREQ range; the operator supplies the band")),
        "amplitude": Field("number", unit="V", writable=True, description="Sine output amplitude (SLVL)",
                           limit=Limit.operator_required(
                               "no line of the clone states the SLVL range; the operator supplies the output limit")),
        "phase": Field("number", unit="deg", writable=True, description="Reference phase (PHAS)",
                       limit=Limit.operator_required(
                           "no line of the clone states the PHAS range; the operator supplies the phase band")),
        "harmonic": Field("integer", unit="1", description="Harmonic number (HARM?, read only in the clone)"),
        "reference_source": Field("integer", unit="1", writable=True, description="Reference source (FMOD)",
                                  limit=Limit.operator_required(_UNSOURCED_RANGE)),
        "trigger_shape": Field("integer", unit="1", description="RSLP value, named trigshape by the clone"),
        "aux_output_1": Field("number", unit="V", description="Auxiliary output 1 (AUXV? 1)"),
        "aux_output_2": Field("number", unit="V", description="Auxiliary output 2 (AUXV? 2)"),
        # Input and filter chain.
        "input_source": Field("integer", unit="1", writable=True, description="Input source (ISRC)",
                              limit=Limit.operator_required(_UNSOURCED_RANGE)),
        "coupling": Field("integer", unit="1", writable=True, description="Input coupling (ICPL)",
                          limit=Limit.operator_required(_UNSOURCED_RANGE)),
        "grounding": Field("integer", unit="1", description="Input ground (IGND?)"),
        "line_filter": Field("integer", unit="1", description="Line notch filter (ILIN?)"),
        "reserve": Field("integer", unit="1", description="Dynamic reserve (RMOD?)"),
        "filter_slope": Field("integer", unit="1", description="Low-pass filter slope (OFSL?)"),
        "sync_filter": Field("integer", unit="1", description="Synchronous filter (SYNC?)"),
        # The two index tables the clone states.
        "time_constant_index": Field(
            "integer", unit="1", writable=True,
            description="OFLT index, 0 = 10 us, 19 = 30 ks",
            limit=Limit(allowed=TIME_CONSTANT_INDEXES, source="upstream_code", ref=f"{UPSTREAM}:8-28")),
        "sensitivity_index": Field(
            "integer", unit="1", writable=True,
            description="SENS index, 0 = 2 nV, 26 = 1 V",
            limit=Limit(allowed=SENSITIVITY_INDEXES, source="upstream_code", ref=f"{UPSTREAM}:29-56")),
        # Display definitions are queried as one comma-separated reply per channel.
        "display_1": Field("string", description="Raw DDEF? 1 reply (display, ratio)"),
        "display_2": Field("string", description="Raw DDEF? 2 reply (display, ratio)"),
        "expand_1": Field("string", description="Raw OEXP? 1 reply (expand, offset)"),
        "expand_2": Field("string", description="Raw OEXP? 2 reply (expand, offset)"),
    }
    reads = {
        "x": {"query": "OUTP? 1", "parse": {"kind": "float"}},
        "y": {"query": "OUTP? 2", "parse": {"kind": "float"}},
        "r": {"query": "OUTP? 3", "parse": {"kind": "float"}},
        "theta": {"query": "OUTP? 4", "parse": {"kind": "float"}},
        "snapshot": {"query": "SNAP?1,2,3,4", "parse": {"kind": "str"}},
        "frequency": {"query": "FREQ?", "parse": {"kind": "float"}},
        "amplitude": {"query": "SLVL?", "parse": {"kind": "float"}},
        "phase": {"query": "PHAS?", "parse": {"kind": "float"}},
        "harmonic": {"query": "HARM?", "parse": {"kind": "int"}},
        "reference_source": {"query": "FMOD?", "parse": {"kind": "int"}},
        "trigger_shape": {"query": "RSLP?", "parse": {"kind": "int"}},
        "aux_output_1": {"query": "AUXV? 1", "parse": {"kind": "float"}},
        "aux_output_2": {"query": "AUXV? 2", "parse": {"kind": "float"}},
        "input_source": {"query": "ISRC?", "parse": {"kind": "int"}},
        "coupling": {"query": "ICPL?", "parse": {"kind": "int"}},
        "grounding": {"query": "IGND?", "parse": {"kind": "int"}},
        "line_filter": {"query": "ILIN?", "parse": {"kind": "int"}},
        "reserve": {"query": "RMOD?", "parse": {"kind": "int"}},
        "filter_slope": {"query": "OFSL?", "parse": {"kind": "int"}},
        "sync_filter": {"query": "SYNC?", "parse": {"kind": "int"}},
        "time_constant_index": {"query": "OFLT?", "parse": {"kind": "int"}},
        "sensitivity_index": {"query": "SENS?", "parse": {"kind": "int"}},
        "display_1": {"query": "DDEF? 1", "parse": {"kind": "str"}},
        "display_2": {"query": "DDEF? 2", "parse": {"kind": "str"}},
        "expand_1": {"query": "OEXP? 1", "parse": {"kind": "str"}},
        "expand_2": {"query": "OEXP? 2", "parse": {"kind": "str"}},
    }
    writes = {
        "frequency": {"write": "FREQ {value:f}", "type": "number"},
        "amplitude": {"write": "SLVL {value:f}", "type": "number"},
        "phase": {"write": "PHAS {value:f}", "type": "number"},
        "reference_source": {"write": "FMOD {value:d}", "type": "integer"},
        "input_source": {"write": "ISRC {value:d}", "type": "integer"},
        "coupling": {"write": "ICPL {value:d}", "type": "integer"},
        "time_constant_index": {"write": "OFLT {value:d}", "type": "integer"},
        "sensitivity_index": {"write": "SENS {value:d}", "type": "integer"},
    }
    safety_bindings = {"estop": {"write": "SLVL 0"}}
