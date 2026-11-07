"""OpenMHS driver for gh.samdejong86/agilent33600: the Agilent (Keysight) 33600A arbitrary waveform generator.

The upstream repository is two pyvisa scripts, not a class library.  Both scripts open a VISA resource named
``inst`` (AgilentControl.py:24 and UploadArb.py:65) and send line-oriented SCPI commands over TCP.  This package is
therefore a :class:`mhs.driver.ScpiDriver`: the class attributes below are a command map, and the SCPI bridge opens
the instrument itself (``host``/``port`` or a VISA resource).  ``native`` records the card's entry symbol
(``AgilentControl:inst``, a module-level VISA resource object); it is not a Python class and the bridge never
imports the clone.

Covered: the scalar channel-1 settings the clone's macro files and UploadArb.py write -- frequency, voltage,
offset, function, arbitrary-waveform name and arbitrary sample rate -- plus the ``*IDN?`` identity read and the
``SYST:ERR?`` error queue.  NOT COVERED: the binary arbitrary-waveform upload.  UploadArb.py:82 sends the sample
array through pyvisa's ``write_binary_values`` as a little-endian float block; the declarative SCPI grammar has no
binary block, so the array and the ``SOUR1:DATA:ARB`` exchange are left out rather than re-encoding them into a
different wire syntax.

No Limit below is copied from a catalogue default or a script default.  The clone states no frequency, voltage,
offset or sample-rate range (README.md:10 points to an external manual that is not part of the clone), so those
numeric inputs are ``Limit.operator_required``: every write that sets one is refused until the operator supplies a
bound in ``site-limits.json``.  The 12-character waveform-name maximum is stated by UploadArb.py:31-34.

The query forms (``SOURCE1:FREQUENCY?`` and the others) are the SCPI query form of the set commands the clone
shows; the clone itself only queries ``*IDN?`` and ``SYST:ERR?``.  This is a fidelity gap of the package, not a
device fact.  Every Fact and every sourced Limit cites a line of the clone at the pinned commit
262275ddb4e1486c9643587725908456d765b12b; the four ``operator_required`` limits state why no line supplies a
bound.  The package is model-authored and unreviewed; nothing here ran hardware.
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

#: The waveform-name maximum of the upstream script (UploadArb.py:31-34).
WAVEFORM_NAME_MAX = 12


class Agilent33600(ScpiDriver):
    device_id = "agilent33600"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "AgilentControl:inst"
    backends = {"fake": ".fake:FakeAgilent33600"}
    vendor = "Agilent (Keysight)"
    model = "33600A arbitrary waveform generator"
    display_name = "Agilent 33600A arbitrary waveform generator"
    tags = ["awg", "waveform generator", "agilent", "keysight", "33600a", "scpi"]

    facts = [
        Fact("AgilentControl.py programs an Agilent 33600A arbitrary waveform generator by sending SCPI commands "
             "via TCP", source="vendor_doc", ref="README.md:8"),
        Fact("UploadArb.py uploads a specified arbitrary waveform to the device and saves it to the device's memory",
             source="vendor_doc", ref="README.md:12"),
        Fact("AgilentControl.py opens the VISA resource 'TCPIP::<address>::INSTR'",
             source="upstream_code", ref="AgilentControl.py:24"),
        Fact("UploadArb.py opens the same 'TCPIP::<address>::INSTR' VISA resource",
             source="upstream_code", ref="UploadArb.py:65"),
        Fact("The control script queries '*IDN?' through the VISA session",
             source="upstream_code", ref="AgilentControl.py:43"),
        Fact("After each macro line the control script queries 'SYST:ERR?' and treats a reply whose first two "
             "characters are '+0' as no error", source="upstream_code", ref="AgilentControl.py:73-76"),
        Fact("The upload script truncates an arbitrary-waveform name to 12 characters, the maximum length allowed "
             "by the SCPI interface", source="upstream_code", ref="UploadArb.py:31-34"),
        Fact("The upload script computes the sample rate as 1 divided by the mean interval between the file's "
             "time bins", source="upstream_code", ref="UploadArb.py:52-54"),
        Fact("The upload script sends the waveform as a little-endian float block with pyvisa's "
             "write_binary_values", source="upstream_code", ref="UploadArb.py:82"),
        Fact("After the block upload the script sets the arbitrary sample rate, offset 0, the ARB function and the "
             "amplitude", source="upstream_code", ref="UploadArb.py:90-94"),
        Fact("The frequency-sweep macro selects the sine function and sets the frequency with "
             "'SOURce1:FREQuency +50E+03'", source="upstream_code", ref="freqSweep.awg:2-3"),
        Fact("The square-wave macro selects the square function and sets 20 percent duty cycle, 5000 Hz, "
             "0.07 V high and 0 V low on channel 2", source="upstream_code", ref="squareWave.awg:1-5"),
        Fact("The triangle-wave macro selects the triangle function and sets 50 percent duty cycle, 40000 Hz, "
             "0.50 V high and 0 V low on channel 2", source="upstream_code", ref="triangleWave.awg:1-5"),
        Fact("A stored arbitrary waveform is loaded with 'MMEMORY:LOAD:DATA1' followed by "
             "'SOURCE1:FUNCTION ARB' and 'SOURCE1:FUNCtion:ARBitrary'", source="upstream_code",
             ref="UploadArb.py:122-124"),
        Fact("The macro files switch the channel 1 output on with OUTPUT1 ON", source="upstream_code",
             ref="arb.awg:11"),
    ]

    safe_state = ("channel 1 output switched off (OUTPUT1 OFF, the off form of the OUTPUT1 ON the clone sends); "
                  "the amplitude, offset and waveform settings are left unchanged")
    error_query = "SYST:ERR?"

    parameters = {
        "identity": Field(
            "string", description="Instrument identity string returned by '*IDN?'"),
        "frequency": Field(
            "number", unit="Hz", writable=True, description="Channel 1 frequency (SOURCE1:FREQUENCY)",
            limit=Limit.operator_required(
                "The clone states no frequency range: README.md:10 points to an external manual that is not part "
                "of the clone, and the macro files contain only example frequencies. The operator supplies the "
                "bound at deployment.")),
        "amplitude": Field(
            "number", unit="V", writable=True, description="Channel 1 output amplitude (SOURCE1:VOLTAGE)",
            limit=Limit.operator_required(
                "The clone states no output-amplitude range: UploadArb.py:16 has a pulse-height default and the "
                "macros show example voltages, neither of which is a device bound. The operator supplies the "
                "bound at deployment.")),
        "offset": Field(
            "number", unit="V", writable=True, description="Channel 1 output offset (SOUR1:VOLT:OFFS)",
            limit=Limit.operator_required(
                "The clone only writes offset 0 (UploadArb.py:92) and states no offset range, so the operator "
                "supplies the bound at deployment.")),
        "function": Field(
            "string", writable=True, enum=["SIN", "SQU", "TRI", "ARB"],
            description="Channel 1 waveform function (SOURCE1:FUNC): sine, square, triangle or arbitrary"),
        "waveform": Field(
            "string", writable=True, max_length=WAVEFORM_NAME_MAX,
            description="Arbitrary-waveform name on channel 1 (SOUR1:FUNC:ARB), at most 12 characters"),
        "sample_rate": Field(
            "number", unit="Hz", writable=True,
            description="Sample rate of the selected arbitrary waveform (SOUR1:FUNC:ARB:SRAT)",
            limit=Limit.operator_required(
                "The clone computes the sample rate from the input file (UploadArb.py:52-54) but states no "
                "device range. The operator supplies the bound at deployment.")),
    }
    reads = {
        "identity": {"query": "*IDN?", "parse": {"kind": "str"}},
        "frequency": {"query": "SOURCE1:FREQUENCY?", "parse": {"kind": "float"}},
        "amplitude": {"query": "SOURCE1:VOLTAGE?", "parse": {"kind": "float"}},
        "offset": {"query": "SOUR1:VOLT:OFFS?", "parse": {"kind": "float"}},
        "function": {"query": "SOURCE1:FUNC?", "parse": {"kind": "str"}},
        "waveform": {"query": "SOUR1:FUNC:ARB?", "parse": {"kind": "str"}},
        "sample_rate": {"query": "SOUR1:FUNC:ARB:SRAT?", "parse": {"kind": "float"}},
    }
    writes = {
        "frequency": {"write": "SOURCE1:FREQUENCY {value:.10g}", "type": "number"},
        "amplitude": {"write": "SOURCE1:VOLTAGE {value:.10g}", "type": "number"},
        "offset": {"write": "SOUR1:VOLT:OFFS {value:.10g}", "type": "number"},
        "function": {"write": "SOURCE1:FUNC {value}", "type": "string"},
        "waveform": {"write": "SOUR1:FUNC:ARB {value}", "type": "string"},
        "sample_rate": {"write": "SOUR1:FUNC:ARB:SRAT {value:.10g}", "type": "number"},
    }
    safety_bindings = {"estop": {"write": "OUTPUT1 OFF"}}
