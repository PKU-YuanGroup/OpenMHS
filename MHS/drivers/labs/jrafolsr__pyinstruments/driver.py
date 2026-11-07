"""OpenMHS driver for gh.jrafolsr/pyinstruments: the keysight33210A function generator over SCPI.

The upstream class (``instruments/keysight33210A.py``) is a pyvisa object whose public methods write and query
standard SCPI commands.  This package is a :class:`~mhs.driver.ScpiDriver` command map: the bridge opens the
instrument itself (``host``/``port`` or a VISA resource) and the runtime enforces every limit before a command
reaches the wire.  The upstream class is named only as ``native``; its pyvisa transport is not used.

* reads: frequency, amplitude, DC offset, waveform function, output termination and output relay state;
* writes: frequency, amplitude, offset, function, load and output, each with a source or an operator-required bound;
* the e-stop and the safe state write ``:OUTP OFF``, the output-off command of the upstream class.

The clone at the pinned commit is ``labs/jrafolsr/pyinstruments``; every Fact and Limit cites a line of it.  This
package is model-authored and unreviewed; no hardware backend was run (see RESULT.json notes).
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

CLASS = "instruments/keysight33210A.py"

#: The waveform functions the upstream constructor accepts (line 20).
FUNCTIONS = ["SIN", "SQU", "RAMP", "PULS", "NOIS", "DC", "USER"]
#: The output terminations the upstream setter accepts (line 36).
LOADS = ["50", "INF"]
#: The output relay commands of the upstream class (lines 171-176).
OUTPUTS = ["ON", "OFF"]


class Keysight33210A(ScpiDriver):
    device_id = "keysight33210a"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "instruments.keysight33210A:keysight33210A"
    backends = {"fake": ".fake:Fake33210A"}
    vendor, model = "Keysight / Agilent Technologies", "33210A function generator"
    display_name = "Keysight 33210A function generator"
    tags = ["function generator", "keysight", "agilent", "33210a", "scpi"]
    facts = [
        Fact("The class requires the identity string to start with 'Agilent Technologies'",
             source="upstream_code", ref=f"{CLASS}:16"),
        Fact("The waveform functions are SIN, SQU, RAMP, PULS, NOIS, DC and USER",
             source="upstream_code", ref=f"{CLASS}:20"),
        Fact("The frequency setter accepts 1e-3 Hz to 10e6 Hz",
             source="upstream_code", ref=f"{CLASS}:29-30"),
        Fact("The load setter accepts 50 ohm or the string 'INF'",
             source="upstream_code", ref=f"{CLASS}:36"),
        Fact("The amplitude setter rejects amplitude <= 0",
             source="upstream_code", ref=f"{CLASS}:95-96"),
        Fact("The load-dependent Vmax is 5 V for 50 ohm and 10 V for INF",
             source="upstream_code", ref=f"{CLASS}:34-47"),
        Fact("The offset setter refuses |offset| > Vmax - Vpp/2 with the load-dependent Vmax",
             source="upstream_code", ref=f"{CLASS}:134-138"),
        Fact("The output relay commands are ':OUTP OFF' and ':OUTP ON'",
             source="upstream_code", ref=f"{CLASS}:171-176"),
        Fact("FUNC? reads the current waveform function", source="upstream_code", ref=f"{CLASS}:69"),
        Fact(":OUTP:LOAD? reads the output termination", source="upstream_code", ref=f"{CLASS}:105"),
        Fact("VOLT? reads the current amplitude", source="upstream_code", ref=f"{CLASS}:128"),
        Fact("A setting is sent as 'COMMAND value', for example 'FREQ {frequency:.4e}'",
             source="upstream_code", ref=f"{CLASS}:87"),
        Fact("The offset command is 'VOLT:OFFS {offset:.4f}V'", source="upstream_code", ref=f"{CLASS}:142"),
        Fact("The duty cycle setter accepts 20 to 80 percent and only when the function is SQU",
             source="upstream_code", ref=f"{CLASS}:148-153"),
        Fact("The DC voltage setter writes FUNC DC then VOLT:OFFS and bounds the value by the current Vmax",
             source="upstream_code", ref=f"{CLASS}:163-168"),
    ]
    safe_state = "output relay off with ':OUTP OFF'"
    idn = {"expect": r"^Agilent Technologies"}

    parameters = {
        "frequency": Field(
            "number", unit="Hz", writable=True, description="Output frequency (FREQ)",
            limit=Limit(min=1e-3, max=10e6, source="upstream_code", ref=f"{CLASS}:29-30",
                        reason="set_frequency accepts min_freq = 1e-3 Hz (line 29) through max_freq = 10e6 Hz (line 30)")),
        "amplitude": Field(
            "number", unit="V", writable=True, description="Output amplitude in the selected voltage unit (VOLT)",
            limit=Limit.operator_required(
                "the upstream setter only rejects amplitude <= 0; the maximum depends on the load and the output "
                "configuration, so the site sets the range")),
        "offset": Field(
            "number", unit="V", writable=True, description="DC offset in volts (VOLT:OFFS)",
            limit=Limit.operator_required(
                "the upstream bound depends on the current amplitude and the load-dependent Vmax "
                "(|offset| <= Vmax - Vpp/2); the site sets the range")),
        "function": Field(
            "string", writable=True, description="Waveform function (FUNC)",
            limit=Limit(allowed=FUNCTIONS, source="upstream_code", ref=f"{CLASS}:20")),
        "load": Field(
            "string", writable=True,
            description="Output termination (OUTP:LOAD): '50' for 50 ohm or 'INF' for high impedance",
            limit=Limit(allowed=LOADS, source="upstream_code", ref=f"{CLASS}:36")),
        "output": Field(
            "string", writable=True, description="Output relay state (OUTP): ON or OFF",
            limit=Limit(allowed=OUTPUTS, source="upstream_code", ref=f"{CLASS}:171-176")),
    }
    reads = {
        "frequency": {"query": "FREQ?", "parse": {"kind": "float"}},
        "amplitude": {"query": "VOLT?", "parse": {"kind": "float"}},
        "offset": {"query": "VOLT:OFFS?", "parse": {"kind": "float"}},
        "function": {"query": "FUNC?", "parse": {"kind": "str"}},
        "load": {"query": ":OUTP:LOAD?", "parse": {"kind": "str"}},
        "output": {"query": ":OUTP?", "parse": {"kind": "str"}},
    }
    writes = {
        "frequency": {"write": "FREQ {value:.4e}", "type": "number"},
        "amplitude": {"write": "VOLT {value:.4f}", "type": "number"},
        "offset": {"write": "VOLT:OFFS {value:.4f}V", "type": "number"},
        "function": {"write": "FUNC {value}", "type": "string"},
        "load": {"write": ":OUTP:LOAD {value}", "type": "string"},
        "output": {"write": ":OUTP {value}", "type": "string"},
    }
    safety_bindings = {"estop": {"write": ":OUTP OFF"}, "safe_state": {"write": ":OUTP OFF"}}
