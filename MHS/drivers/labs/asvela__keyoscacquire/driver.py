"""OpenMHS driver for gh.asvela/keyoscacquire: a Keysight InfiniiVision oscilloscope over SCPI (a family driver).

A ScpiDriver is configuration only: the class attributes below are the command map of the SCPI bridge, and the
runtime enforces every limit before a command reaches the wire.  The commands are the ones the upstream package
writes in ``keyoscacquire/oscilloscope.py``; the bridge owns the transport (``host``/``port`` for raw SCPI or a
``visa_resource`` for pyvisa, options of the hardware backend), so the upstream package is not imported by this
driver.

* reads: the acquisition type, the number of averages, the points mode, the number of points, the waveform
  transfer format and the operation condition register (the third bit says whether the acquisition is running);
* writes: those settings, each bounded by a value the upstream code states;
* ``x-cap.asvela.read_error.v1`` reads (and removes) the oldest entry of the instrument error queue;
* the e-stop writes ``:STOP``: the acquisition stops.

The instrument's trace array is NOT COVERED (see RESULT.json notes): the waveform itself is transferred as an
IEEE binary block and no catalogue class carries a trace array yet, so this package serves the settings and the
status of the instrument, not the waveform.

Every Limit and Fact cites a line of the clone at the pinned commit
(1d093470ab99769c9b149816d7faa4b61a4837d2).  This package is model-authored and unreviewed, and its wire syntax
has not been tried on an instrument.
"""

from mhs.driver import Action, Fact, Field, Limit, ScpiDriver

OSC = "keyoscacquire/oscilloscope.py"
CONFIG = "keyoscacquire/config.py"
CLI = "keyoscacquire/installed_cli_programmes.py"


class Keyoscacquire(ScpiDriver):
    device_id = "keyoscacquire"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "keyoscacquire.oscilloscope:Oscilloscope"
    backends = {"fake": ".fake:FakeKeyoscacquire"}
    vendor, model = "Keysight Technologies", "InfiniiVision X-series oscilloscope (1000 to 6000 series)"
    display_name = "Keysight InfiniiVision oscilloscope"
    tags = ["oscilloscope", "keysight", "infinivision", "scpi"]
    safe_state = "acquisition stopped"
    idn = {"expect": "^(AGILENT|KEYSIGHT) TECHNOLOGIES,"}
    facts = [
        Fact("The clone drives Keysight InfiniiVision X-series oscilloscopes of the 1000, 2000, 3000, 4000 and "
             "6000 series", source="upstream_code", ref=f"{OSC}:30"),
        Fact("'*IDN?' answers maker, model, serial and firmware, for example "
             "'KEYSIGHT TECHNOLOGIES,MSO9104A,MY12345678,06.30.00609'", source="upstream_code", ref=f"{OSC}:90-91"),
        Fact("The error queue is a FIFO of at most 30 entries and ':SYSTem:ERRor?' returns 'error number,"
             "description'", source="upstream_code", ref=f"{OSC}:232-243"),
        Fact("The operation condition register ':OPERegister:CONDition?' has its third bit (value 8) set while "
             "the instrument is running", source="upstream_code", ref=f"{OSC}:286-288"),
        Fact("The acquisition type is NORMal, AVERage or HRESolution; AVER<m> also sets the number of averages to "
             "<m>", source="upstream_code", ref=f"{OSC}:335-340"),
        Fact("The acquisition type is sent as the first four characters in upper case, so NORMal becomes "
             "':ACQuire:TYPE NORM', AVERage 'AVER' and HRESolution 'HRES'", source="upstream_code",
             ref=f"{OSC}:363-365"),
        Fact("The number of averages is checked to lie between 2 and 65,536 before ':ACQuire:COUNt' is written",
             source="upstream_code", ref=f"{OSC}:404-408"),
        Fact("The points mode of the acquisition is one of RAW, MAX and NORMal", source="upstream_code",
             ref=f"{CONFIG}:16"),
        Fact("NORMal points mode is limited to 62,500 points, whereas RAW gives up to 1e6 points",
             source="upstream_code", ref=f"{CONFIG}:14-15"),
        Fact("A num_points value of 0 selects the maximum number of points for the current points mode",
             source="upstream_code", ref=f"{CONFIG}:18-20"),
        Fact("The waveform transfer format is BYTE, WORD or ASCii", source="upstream_code", ref=f"{CLI}:30"),
        Fact("':RUN' sets the oscilloscope running and ':STOP' stops the acquisition", source="upstream_code",
             ref=f"{OSC}:270-276"),
    ]
    parameters = {
        "acq_type": Field(
            "string", writable=True,
            description="Acquisition type: NORMal, AVERage or HRESolution (sent as NORM, AVER or HRES)",
            limit=Limit(allowed=["NORMal", "AVERage", "HRESolution"], source="upstream_code",
                        ref=f"{OSC}:335-340")),
        "num_averages": Field(
            "integer", unit="1", writable=True,
            description="Number of averages taken in AVERage mode",
            limit=Limit(min=2, max=65536, source="upstream_code", ref=f"{OSC}:406")),
        "p_mode": Field(
            "string", writable=True,
            description="Points mode of the acquisition: RAW, MAX or NORMal",
            limit=Limit(allowed=["RAW", "MAX", "NORMal"], source="upstream_code", ref=f"{CONFIG}:16")),
        "num_points": Field(
            "integer", unit="1", writable=True,
            description="Number of points acquired per channel; 0 selects the maximum for the points mode",
            limit=Limit(min=0, max=1000000, source="upstream_code", ref=f"{CONFIG}:14-20",
                        reason="1e6 is the documented maximum in RAW mode, NORMal is limited to 62,500 and 0 "
                               "selects the maximum; the instrument may reduce the number for its memory depth")),
        "wav_format": Field(
            "string", writable=True,
            description="Waveform transfer format: BYTE, WORD or ASCii",
            limit=Limit(allowed=["BYTE", "WORD", "ASCii"], source="upstream_code", ref=f"{CLI}:30")),
        "operation_condition": Field(
            "integer",
            description="Operation condition register (:OPERegister:CONDition?); bit 3 (value 8) is set while "
                        "the acquisition is running"),
    }
    reads = {
        "acq_type": {"query": ":ACQuire:TYPE?", "parse": {"kind": "str"}},
        "num_averages": {"query": ":ACQuire:COUNt?", "parse": {"kind": "int"}},
        "p_mode": {"query": ":WAVeform:POINts:MODE?", "parse": {"kind": "str"}},
        "num_points": {"query": ":WAVeform:POINTs?", "parse": {"kind": "int"}},
        "wav_format": {"query": ":WAVeform:FORMat?", "parse": {"kind": "str"}},
        "operation_condition": {"query": ":OPERegister:CONDition?", "parse": {"kind": "int"}},
    }
    writes = {
        "acq_type": {"write": ":ACQuire:TYPE {value}", "type": "string",
                     "enum_map": {"NORMal": "NORM", "AVERage": "AVER", "HRESolution": "HRES"}},
        "num_averages": {"write": ":ACQuire:COUNt {value:d}", "type": "integer"},
        "p_mode": {"write": ":WAVeform:POINts:MODE {value}", "type": "string"},
        "num_points": {"write": ":WAVeform:POINts {value:d}", "type": "integer"},
        "wav_format": {"write": ":WAVeform:FORMat {value}", "type": "string"},
    }
    commands = {
        "x-cap.asvela.read_error.v1": {
            "query": ":SYSTem:ERRor?", "parse": {"kind": "str"},
            "result": {"map": {"error": "output.$"}},
        },
    }
    actions = {
        "x-cap.asvela.read_error.v1": Action(
            name="read_error",
            description="Read and remove the oldest entry of the instrument error queue (:SYSTem:ERRor?)",
            output={"error": Field("string", description="Error number and description, e.g. '0,\"No error\"'")}),
    }
    safety_bindings = {"estop": {"write": ":STOP"}}
