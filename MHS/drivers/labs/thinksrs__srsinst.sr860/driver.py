"""OpenMHS driver for gh.thinksrs/srsinst.sr860: the SR860 lock-in amplifier over SCPI (a family driver).

A ScpiDriver is configuration only: the class attributes below are the command map of the SCPI bridge, and the
runtime enforces every limit before a command reaches the wire.  The commands are the raw commands of the
upstream package (``FREQ``, ``SLVL``, ``OFLT`` and ``OUTP`` in srsinst/sr860/instruments/components.py); the
package opens the instrument through srsgui, which this driver does not use: the bridge opens the instrument itself
(``host``/``port`` or a VISA resource, options of the hardware backend), so only the commands are shared.

* reads: the reference frequency, the sine output amplitude and the four data values X, Y, R and Theta;
* writes: frequency, amplitude and time constant, each limited by values the upstream code states;
* the e-stop writes ``SLVL 0``: the sine output amplitude, the one output this driver sets, goes to its lowest value.

Every Limit and Fact cites a line of the clone at the pinned commit (c234ec204329c1682fcc5a77d28164e99cdd1f3e).  This
package is model-authored and unreviewed, and its wire syntax has not been tried on an instrument (README.md).
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

COMPONENTS = "srsinst/sr860/instruments/components.py"

#: The 22 time constants of the SR860 in the order of their OFLT index: 1 and 3 times 10^k s, k = -6 to 4.  The same
#: expression builds TimeConstantDict in the clone (components.py:166-171).
TIME_CONSTANTS = [float(f"{j * 10 ** (i - 6):.1e}") for i in range(11) for j in (1.0, 3.0)]


class Sr860(ScpiDriver):
    device_id = "sr860"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "srsinst.sr860.instruments.sr860:SR860"
    backends = {"fake": ".fake:FakeSr860"}
    vendor, model = "Stanford Research Systems", "SR860 series lock-in amplifier"
    display_name = "SRS SR860 lock-in amplifier"
    tags = ["lock-in amplifier", "sr860", "sr865", "sr865a", "scpi"]
    facts = [
        Fact("The SR860, SR865 and SR865A are one family: the identity pattern is 'SR86[05][A]?,'",
             source="upstream_code", ref="srsinst/sr860/instruments/sr860.py:23"),
        Fact("OUTP returns a data value by index: X 0, Y 1, R 2, Theta 3", source="vendor_doc",
             ref="README.md:175-179"),
        Fact("Theta is an angle in degrees (180 / pi * arctan2(y, x))", source="upstream_code",
             ref=f"{COMPONENTS}:738"),
        Fact("The signal input is a voltage (sensitivity in V) or a current (sensitivity in A)",
             source="upstream_code", ref=f"{COMPONENTS}:191-194"),
        Fact("The time constants are 1 and 3 times 10^k s for k = -6 to 4, numbered from 0 in that order",
             source="upstream_code", ref=f"{COMPONENTS}:166-171"),
        Fact("The SR865 reference class allows up to 2000000.0 Hz and the SR865A class up to 4000000.0 Hz",
             source="upstream_code", ref=f"{COMPONENTS}:103-118"),
        Fact("SLVL, the sine output amplitude, ranges from 0 to 2.0 V", source="upstream_code",
             ref=f"{COMPONENTS}:78"),
        Fact("A setting is sent as 'COMMAND value' (OAUT {index})", source="upstream_code", ref=f"{COMPONENTS}:234"),
        Fact("A query with an argument is sent as 'COMMAND? argument' (CAPTUREVAL? {index})", source="upstream_code",
             ref=f"{COMPONENTS}:583"),
        Fact("The upstream README prints the identity 'Stanford_Research_Systems,SR865A,002725,v1.34' on connecting",
             source="vendor_doc", ref="README.md:63"),
    ]
    safe_state = "sine output amplitude set to 0 V"
    idn = {"expect": "^Stanford_Research_Systems,SR86[05]A?,"}

    parameters = {
        "frequency": Field(
            "number", unit="Hz", writable=True, description="Reference frequency (FREQ)",
            limit=Limit(min=0.001, max=500000.0, source="upstream_code", ref=f"{COMPONENTS}:26-60",
                        reason="FREQ takes 0.001 Hz (line 60) up to MaxFrequency = 500000.0 Hz (line 26)")),
        "amplitude": Field(
            "number", unit="V", writable=True, description="Sine output amplitude (SLVL)",
            limit=Limit(min=0, max=2.0, source="upstream_code", ref=f"{COMPONENTS}:78")),
        "time_constant": Field(
            "number", unit="s", writable=True,
            description="Time constant of the low-pass filter (OFLT); the instrument holds its index, "
                        "which this driver does not read back",
            limit=Limit(allowed=TIME_CONSTANTS, source="upstream_code", ref=f"{COMPONENTS}:166-171")),
        "x": Field("number", description="In-phase component X of the signal (volts or amperes, as the input)"),
        "y": Field("number", description="Quadrature component Y of the signal (volts or amperes, as the input)"),
        "r": Field("number", description="Magnitude R of the signal (volts or amperes, as the input)"),
        "theta": Field("number", unit="deg", description="Phase Theta of the signal relative to the reference"),
    }
    reads = {
        "frequency": {"query": "FREQ?", "parse": {"kind": "float"}},
        "amplitude": {"query": "SLVL?", "parse": {"kind": "float"}},
        "x": {"query": "OUTP? 0", "parse": {"kind": "float"}},
        "y": {"query": "OUTP? 1", "parse": {"kind": "float"}},
        "r": {"query": "OUTP? 2", "parse": {"kind": "float"}},
        "theta": {"query": "OUTP? 3", "parse": {"kind": "float"}},
    }
    writes = {
        "frequency": {"write": "FREQ {value:.10g}", "type": "number"},
        "amplitude": {"write": "SLVL {value:.10g}", "type": "number"},
        "time_constant": {"write": "OFLT {value:d}", "type": "integer",
                          "enum_map": {seconds: index for index, seconds in enumerate(TIME_CONSTANTS)}},
    }
    safety_bindings = {"estop": {"write": "SLVL 0"}}
