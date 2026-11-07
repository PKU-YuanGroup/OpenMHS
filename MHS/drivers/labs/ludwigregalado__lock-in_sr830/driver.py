"""OpenMHS driver for gh.ludwigregalado/lock-in_sr830: the SRS SR830 lock-in amplifier over serial.

A SerialDriver is configuration only: the class attributes below are the command map of the serial bridge, and the
runtime enforces every limit before a command reaches the wire.  The upstream is a flat pyserial module, not a
class: every ``ask_device`` and ``set_device`` call opens ``/dev/ttyUSB0`` at 9600 baud, 8 data bits, no parity,
one stop bit and a 0.1 s timeout, then sends a newline-terminated text command (SR830.py:11-29).  The bridge opens
the serial line once, so this package does not import or run the clone.

* reads: X, Y, R and theta (``OUTP? 1`` to ``OUTP? 4``), the reference phase (``PHAS?``), the reference frequency
  (``FREQ?``), the sine output amplitude (``SLVL?``), the input configuration (``ISRC?``), the input shield ground
  (``IGND?``), the input coupling (``ICPL?``), the line notch filter (``ILIN?``), the reserve mode (``RMOD?``), the
  time-constant index (``OFLT?``), the low-pass slope (``OFSL?``), the synchronous filter (``SYNC?``) and the
  identity (``*IDN?``);
* writes: frequency, sine output amplitude, input configuration, ground, coupling, line notch filter, reserve mode,
  time-constant index, slope and synchronous filter.  Each bound is the one the clone's own setter states;
* the e-stop writes ``SLVL 0.004``: the sine output amplitude, the one output this driver sets, goes to the lowest
  value the clone's ``set_ampl`` accepts.  R1: the card's floor is R0 and a lock-in amplifier is a low-energy
  measurement instrument, so no independent hardware e-stop is claimed.

Every Limit and Fact cites a line of the clone at the pinned commit
(fbd78df88f25a051d938cdbe5b0a1263b938e6de).  This package is model-authored and unreviewed: it is checked on the
fake backend only and nothing here ran on an instrument.
"""

from mhs.driver import Fact, Field, Limit, SerialDriver

CLONE = "SR830.py"

#: The 20 time-constant indexes of the clone's set_tau table (SR830.py:266-286): 0 is 10 us, 19 is 30 ks.
TIME_CONSTANT_INDEXES = list(range(20))


class Sr830(SerialDriver):
    device_id = "sr830"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "SR830:ask_device"
    backends = {"fake": ".fake:FakeLockInSr830"}
    vendor, model = "Stanford Research Systems", "SR830"
    display_name = "SRS SR830 lock-in amplifier"
    tags = ["lock-in amplifier", "sr830", "serial", "measurement", "phase"]
    facts = [
        Fact("The README says the code sends and requests information from an SR830 lock-in amplifier",
             source="vendor_doc", ref="README.md:2"),
        Fact("The README says the code is written in a sequential fashion and is to be updated to object-oriented "
             "code", source="vendor_doc", ref="README.md:5"),
        Fact("The only third-party import is pyserial (import serial)", source="upstream_code", ref="SR830.py:9"),
        Fact("ask_device opens /dev/ttyUSB0 at 9600 baud, 8 data bits, no parity, one stop bit and a 0.1 s timeout",
             source="upstream_code", ref="SR830.py:13"),
        Fact("ask_device encodes the command as text, writes and flushes it, reads one line and decodes it as UTF-8",
             source="upstream_code", ref="SR830.py:16-20"),
        Fact("set_device opens the same port, writes and flushes the encoded command, closes the port and reads no "
             "reply", source="upstream_code", ref="SR830.py:24-29"),
        Fact("Commands are newline-terminated text (ask_device('PHAS?\\n'))", source="upstream_code",
             ref="SR830.py:37"),
        Fact("PHAS? queries the reference phase shift", source="upstream_code", ref="SR830.py:36-37"),
        Fact("FREQ? queries the reference frequency", source="upstream_code", ref="SR830.py:40-41"),
        Fact("FREQ sets the reference frequency when the source is internal and accepts 0.001 to 102000 Hz",
             source="upstream_code", ref="SR830.py:183-189"),
        Fact("SLVL? queries the sine output amplitude", source="upstream_code", ref="SR830.py:46-47"),
        Fact("SLVL sets the sine output amplitude and accepts 0.004 to 5.000", source="upstream_code",
             ref="SR830.py:202-204"),
        Fact("OUTP? returns X for index 1, Y for 2, R for 3 and theta for 4", source="upstream_code",
             ref="SR830.py:373-378"),
        Fact("ISRC sets the input configuration to 0, 1, 2 or 3", source="upstream_code", ref="SR830.py:209-212"),
        Fact("IGND sets the input shield grounding to 0 or 1", source="upstream_code", ref="SR830.py:213-216"),
        Fact("ICPL sets the input coupling to 0 or 1", source="upstream_code", ref="SR830.py:217-220"),
        Fact("ILIN sets the line notch filter to 0, 1, 2 or 3", source="upstream_code", ref="SR830.py:221-224"),
        Fact("RMOD sets the reserve mode to 0, 1 or 2", source="upstream_code", ref="SR830.py:258-261"),
        Fact("OFLT selects one of the 20 time-constant indexes of the set_tau table, 0 for 10 us through 19 for "
             "30 ks", source="upstream_code", ref="SR830.py:264-286"),
        Fact("OFSL sets the low-pass filter slope to 0, 1 or 2", source="upstream_code", ref="SR830.py:289-292"),
        Fact("SYNC sets the synchronous filter to 0 or 1", source="upstream_code", ref="SR830.py:293-296"),
        Fact("*IDN? queries the device identification string", source="upstream_code", ref="SR830.py:408-409"),
        Fact("set_phas sends FREQ instead of PHAS, so the clone has no working phase write command",
             source="upstream_code", ref="SR830.py:165-167"),
        Fact("set_aux_inp builds the AUXV command with ++, which raises TypeError when called", source="upstream_code",
             ref="SR830.py:319-322"),
    ]
    safe_state = "sine output amplitude (SLVL) set to 0.004, the lowest value the clone's set_ampl accepts"

    #: The serial line settings the clone hard-codes (SR830.py:13); a hardware deployment may pass a port option.
    port = "/dev/ttyUSB0"
    baudrate = 9600
    bytesize = 8
    parity = "N"
    stopbits = 1
    timeout_s = 0.1
    encoding = "ascii"
    terminator = "\n"

    parameters = {
        "x": Field("number", description="In-phase component X returned by OUTP? 1; the clone does not name the unit"),
        "y": Field("number", description="Quadrature component Y returned by OUTP? 2; the clone does not name the "
                                         "unit"),
        "r": Field("number", description="Magnitude R returned by OUTP? 3; the clone does not name the unit"),
        "theta": Field("number", description="Phase theta returned by OUTP? 4; the clone does not name the unit"),
        "phase": Field("number", description="Reference phase shift returned by PHAS?; the clone does not name the "
                                            "unit"),
        "frequency": Field(
            "number", unit="Hz", writable=True, description="Reference frequency (FREQ)",
            limit=Limit(min=0.001, max=102000, source="upstream_code", ref="SR830.py:185")),
        "amplitude": Field(
            "number", unit="1", writable=True,
            description="Sine output amplitude (SLVL); the clone does not name the unit",
            limit=Limit(min=0.004, max=5.0, source="upstream_code", ref="SR830.py:203")),
        "input_config": Field(
            "integer", unit="1", writable=True, description="Input configuration index (ISRC)",
            limit=Limit(allowed=[0, 1, 2, 3], source="upstream_code", ref="SR830.py:211")),
        "ground": Field(
            "integer", unit="1", writable=True, description="Input shield ground index (IGND)",
            limit=Limit(allowed=[0, 1], source="upstream_code", ref="SR830.py:215")),
        "coupling": Field(
            "integer", unit="1", writable=True, description="Input coupling index (ICPL)",
            limit=Limit(allowed=[0, 1], source="upstream_code", ref="SR830.py:219")),
        "line_filter": Field(
            "integer", unit="1", writable=True, description="Line notch filter index (ILIN)",
            limit=Limit(allowed=[0, 1, 2, 3], source="upstream_code", ref="SR830.py:223")),
        "reserve": Field(
            "integer", unit="1", writable=True, description="Reserve mode index (RMOD)",
            limit=Limit(allowed=[0, 1, 2], source="upstream_code", ref="SR830.py:260")),
        "time_constant_index": Field(
            "integer", unit="1", writable=True, description="Time-constant index (OFLT) of the set_tau table",
            limit=Limit(allowed=TIME_CONSTANT_INDEXES, source="upstream_code", ref="SR830.py:267-286")),
        "slope": Field(
            "integer", unit="1", writable=True, description="Low-pass filter slope index (OFSL)",
            limit=Limit(allowed=[0, 1, 2], source="upstream_code", ref="SR830.py:291")),
        "sync": Field(
            "integer", unit="1", writable=True, description="Synchronous filter index (SYNC)",
            limit=Limit(allowed=[0, 1], source="upstream_code", ref="SR830.py:295")),
        "identity": Field("string", description="Identification string returned by *IDN?"),
    }
    reads = {
        "x": {"command": "OUTP? 1", "parse": {"kind": "float"}},
        "y": {"command": "OUTP? 2", "parse": {"kind": "float"}},
        "r": {"command": "OUTP? 3", "parse": {"kind": "float"}},
        "theta": {"command": "OUTP? 4", "parse": {"kind": "float"}},
        "phase": {"command": "PHAS?", "parse": {"kind": "float"}},
        "frequency": {"command": "FREQ?", "parse": {"kind": "float"}},
        "amplitude": {"command": "SLVL?", "parse": {"kind": "float"}},
        "input_config": {"command": "ISRC?", "parse": {"kind": "int"}},
        "ground": {"command": "IGND?", "parse": {"kind": "int"}},
        "coupling": {"command": "ICPL?", "parse": {"kind": "int"}},
        "line_filter": {"command": "ILIN?", "parse": {"kind": "int"}},
        "reserve": {"command": "RMOD?", "parse": {"kind": "int"}},
        "time_constant_index": {"command": "OFLT?", "parse": {"kind": "int"}},
        "slope": {"command": "OFSL?", "parse": {"kind": "int"}},
        "sync": {"command": "SYNC?", "parse": {"kind": "int"}},
        "identity": {"command": "*IDN?", "parse": {"kind": "str"}},
    }
    writes = {
        "frequency": {"command": "FREQ {value:.10g}", "type": "number", "response": False},
        "amplitude": {"command": "SLVL {value:.10g}", "type": "number", "response": False},
        "input_config": {"command": "ISRC {value:d}", "type": "integer", "response": False},
        "ground": {"command": "IGND {value:d}", "type": "integer", "response": False},
        "coupling": {"command": "ICPL {value:d}", "type": "integer", "response": False},
        "line_filter": {"command": "ILIN {value:d}", "type": "integer", "response": False},
        "reserve": {"command": "RMOD {value:d}", "type": "integer", "response": False},
        "time_constant_index": {"command": "OFLT {value:d}", "type": "integer", "response": False},
        "slope": {"command": "OFSL {value:d}", "type": "integer", "response": False},
        "sync": {"command": "SYNC {value:d}", "type": "integer", "response": False},
    }
    safety_bindings = {"estop": {"command": "SLVL 0.004"}}
