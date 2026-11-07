"""OpenMHS driver for gh.quantumllama/python-lab-drivers: the Siglent SDG 2042X signal generator (SCPI family).

The upstream clone has no class and no installer: it is two PyVISA debug scripts, one tested on a Siglent SDG 2042X
function generator (``func_gen_test.py:3``) and one on a Siglent SDS 1202X oscilloscope (``oscope_test.py:3``).  This
package serves the function generator, the first of the card's two entry symbols.  The card's ``ScpiDriver`` fits:
the clone writes plain command lines (``C2:OUTP``, ``C2:BaSic_WaVe``, ``*IDN?``), and the bridge opens the
instrument itself over a TCP socket (``host``/``port``) or a VISA resource, so only the command words are shared.

* reads: output state (``C2:OUTP?``), waveform, frequency, peak-to-peak amplitude, DC offset and duty cycle
  (``C2:BaSic_WaVe?``), parsed from the responses the guide documents;
* writes: those six settings, in the long command spelling the clone uses (``C2:BaSic_WaVe FRQ,100``);
* the e-stop writes ``C2:OUTP OFF``: the generator output, the physical effect this driver controls, is disabled.

The frequency, amplitude and offset ranges are ``Limit.operator_required``: the guide gives their units and refers
the range of valid values to the data sheet, which is not in the clone.  The waveform types and the duty-cycle range
are stated only by the programming guide in the clone, a PDF (``SDG_Wavegen_Programming_Guide.pdf``, page 20), which
the gate cannot read; a model review accepts no PDF citation, so those two writes are ``Limit.operator_required``
as well, and the guide's statements are in facts.md, not in a Fact.  The output tokens come from the script.

Every Fact and Limit cites a file of the clone at commit 3fee8226c25d749e86f9108c0c9df2051a4aceb8.  The package is
model-authored and unreviewed, is checked on the fake backend only, and never ran on hardware.  NOT COVERED: the
oscilloscope (``oscope_test.py``), whose interface in the clone is only ``*IDN?`` and ``MENU ON``/``MENU OFF``.
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

SCRIPT = "func_gen_test.py"

#: The output states the clone sends (SCRIPT lines 22 and 25).
OUTPUT_STATES = ["ON", "OFF"]


class Sdg2042x(ScpiDriver):
    device_id = "sdg2042x"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "func_gen_test:func_gen"
    backends = {"fake": ".fake:FakeSdg2042x"}
    vendor, model = "Siglent Technologies", "SDG 2042X"
    display_name = "Siglent SDG 2042X function/arbitrary waveform generator"
    tags = ["signal generator", "function generator", "waveform generator", "awg", "siglent", "sdg2042x", "scpi"]
    facts = [
        Fact("The clone is a function-generator debug script tested on a Siglent SDG 2042X",
             source="upstream_code", ref=f"{SCRIPT}:3"),
        Fact("The script opens the first VISA resource and queries *IDN? to confirm the instrument",
             source="upstream_code", ref=f"{SCRIPT}:14-19"),
        Fact("The script writes C2:OUTP OFF, then C2:BaSic_WaVe WVTP,SQUARE,FRQ,100,AMP,2.5,OFST,1.25,DUTY,50, "
             "then C2:OUTP ON,LOAD,HZ,PLRT,NOR",
             source="upstream_code", ref=f"{SCRIPT}:22-25"),
    ]
    safe_state = "generator output disabled"
    idn = {"expect": "^Siglent Technologies,SDG"}

    parameters = {
        "output": Field(
            "string", writable=True, description="Output state, ON or OFF (C2:OUTP?)",
            limit=Limit(allowed=OUTPUT_STATES, source="upstream_code", ref=f"{SCRIPT}:22-25")),
        "waveform": Field(
            "string", writable=True, description="Basic waveform type, WVTP (C2:BaSic_WaVe?)",
            limit=Limit.operator_required(
                "only the programming guide, a PDF the gate cannot read, lists the waveform types (page 20); the "
                "site supplies the types its bench uses")),
        "frequency": Field(
            "number", unit="Hz", writable=True, description="Basic waveform frequency, FRQ (C2:BaSic_WaVe?)",
            limit=Limit.operator_required(
                "the programming guide states the unit (Hz) but refers the range of valid values to the data sheet, "
                "which is not in the clone; the site supplies the range of its generator")),
        "amplitude": Field(
            "number", unit="V", writable=True,
            description="Basic waveform amplitude, peak-to-peak Vpp, AMP (C2:BaSic_WaVe?)",
            limit=Limit.operator_required(
                "the programming guide states the unit (Vpp) but refers the range of valid values to the data sheet, "
                "which is not in the clone; the site supplies the range of its generator output")),
        "offset": Field(
            "number", unit="V", writable=True, description="DC offset, OFST (C2:BaSic_WaVe?)",
            limit=Limit.operator_required(
                "the programming guide states the unit (V) but refers the range of valid values to the data sheet, "
                "which is not in the clone; the site supplies the offset range")),
        "duty_cycle": Field(
            "number", unit="%", writable=True, description="Duty cycle in percent, DUTY (C2:BaSic_WaVe?)",
            limit=Limit.operator_required(
                "only the programming guide, a PDF the gate cannot read, states 0 to 100 percent (page 20), and the "
                "range depends on the frequency; the site supplies the duty-cycle range")),
    }
    reads = {
        "output": {"query": "C2:OUTP?", "parse": {"kind": "regex", "pattern": r"^C2:OUTP (ON|OFF)", "group": 1}},
        "waveform": {"query": "C2:BaSic_WaVe?", "parse": {"kind": "regex", "pattern": r"WVTP,([A-Z]+)", "group": 1}},
        "frequency": {"query": "C2:BaSic_WaVe?",
                      "parse": {"kind": "float", "pattern": r"FRQ,([-+0-9.eE]+)", "group": 1}},
        "amplitude": {"query": "C2:BaSic_WaVe?",
                      "parse": {"kind": "float", "pattern": r"AMP,([-+0-9.eE]+)", "group": 1}},
        "offset": {"query": "C2:BaSic_WaVe?",
                   "parse": {"kind": "float", "pattern": r"OFST,([-+0-9.eE]+)", "group": 1}},
        "duty_cycle": {"query": "C2:BaSic_WaVe?",
                       "parse": {"kind": "float", "pattern": r"DUTY,([-+0-9.eE]+)", "group": 1}},
    }
    writes = {
        "output": {"write": "C2:OUTP {value}", "type": "string"},
        "waveform": {"write": "C2:BaSic_WaVe WVTP,{value}", "type": "string"},
        "frequency": {"write": "C2:BaSic_WaVe FRQ,{value:.10g}", "type": "number"},
        "amplitude": {"write": "C2:BaSic_WaVe AMP,{value:.10g}", "type": "number"},
        "offset": {"write": "C2:BaSic_WaVe OFST,{value:.10g}", "type": "number"},
        "duty_cycle": {"write": "C2:BaSic_WaVe DUTY,{value:.10g}", "type": "number"},
    }
    safety_bindings = {"estop": {"write": "C2:OUTP OFF"}}
