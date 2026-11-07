"""OpenMHS driver for gh.natlabrockies/keithley_gpt: a Keithley 2400 series SMU over SCPI (a family driver).

A ScpiDriver is configuration only: the class attributes below are the command map of the SCPI bridge, and the
runtime enforces every limit before a command reaches the wire.  The upstream clone (Keithley2400GPT.py) wraps a
pyvisa resource and sends the SCPI lines quoted in each Fact; the bridge opens the resource itself
(``visa_resource`` or ``host``/``port``, options of the hardware backend), so this package does not import the
upstream module.

* reads: the identity and the settings the upstream code writes, each read back with the standard SCPI query of
  the same command;
* writes: the current compliance, the source and measure ranges, the NPLC and the 2-/4-wire sensing mode;
* the e-stop writes ``:OUTP OFF``: the source output, which the upstream enables only inside ``iv_sweep``, is
  turned off.  This driver does not expose ``iv_sweep`` and never enables the output.

Every Fact cites a line of the clone at commit 4cad464fd26eac9684d3b2df8ed88c17a6dff972.  No text in the clone
states a compliance, range or NPLC bound, so those fields use ``Limit.operator_required`` and stay refused until an
operator supplies the bench bounds in ``site-limits.json``.  This package is model-authored and unreviewed; the
read-back queries are standard SCPI forms of the commands the clone writes and have not been tried on an instrument.
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

SOURCE = "Keithley2400GPT.py"


class Keithley2400(ScpiDriver):
    device_id = "keithley2400"
    device_kind = "instrument.smu"
    mode = "hardware"
    risk = "R1"
    native = "Keithley2400GPT:Keithley2400Controller"
    backends = {"fake": ".fake:FakeKeithley2400"}
    vendor, model = "Keithley", "2400 series source measure unit"
    display_name = "Keithley 2400 series source measure unit"
    tags = ["source measure unit", "smu", "keithley 2400", "scpi"]

    facts = [
        Fact("The upstream controller class is Keithley2400Controller", source="upstream_code",
             ref=f"{SOURCE}:3"),
        Fact("identify() returns the reply to the SCPI identity query *IDN?", source="upstream_code",
             ref=f"{SOURCE}:17-18"),
        Fact("Measurement mode 2 selects 2-wire sensing with ':SYST:RSEN OFF'; mode 4 selects 4-wire sensing "
             "with ':SYST:RSEN ON'", source="upstream_code", ref=f"{SOURCE}:28-34"),
        Fact("set_current_compliance writes ':SENS:CURR:PROT <compliance>'", source="upstream_code",
             ref=f"{SOURCE}:118-120"),
        Fact("set_source_current_range writes ':SOUR:CURR:RANG <range>'", source="upstream_code",
             ref=f"{SOURCE}:106-107"),
        Fact("set_source_voltage_range writes ':SOUR:VOLT:RANG <range>'", source="upstream_code",
             ref=f"{SOURCE}:109-110"),
        Fact("set_measure_current_range writes ':SENS:CURR:RANG <range>'", source="upstream_code",
             ref=f"{SOURCE}:112-113"),
        Fact("set_measure_voltage_range writes ':SENS:VOLT:RANG <range>'", source="upstream_code",
             ref=f"{SOURCE}:115-116"),
        Fact("set_nplc writes ':SENS:CURR:NPLC <nplc>' for CURR and ':SENS:VOLT:NPLC <nplc>' for VOLT",
             source="upstream_code", ref=f"{SOURCE}:122-128"),
        Fact("iv_sweep enables the source output with ':OUTP ON' and disables it after the reading with "
             "':OUTP OFF'", source="upstream_code", ref=f"{SOURCE}:94-99"),
        Fact("The README names the device a Keithley 2400 series Source Measure Unit (SMU)", source="vendor_doc",
             ref="README.md:3"),
    ]

    safe_state = "source output off"
    #: The upstream turns the output off after a sweep (Keithley2400GPT.py:99); no output-on command is bound here.
    safety_bindings = {"estop": {"write": ":OUTP OFF"}}

    parameters = {
        "identity": Field("string", description="Identity string returned by the SCPI query *IDN?"),
        "current_compliance": Field(
            "number", unit="A", writable=True,
            description="Current compliance",
            limit=Limit.operator_required("the clone writes the compliance but states no allowable range; the "
                                          "operator supplies the bench limit")),
        "measure_current_range": Field(
            "number", unit="A", writable=True,
            description="Measurement current range",
            limit=Limit.operator_required("the clone writes the measurement current range but states no allowable "
                                          "range; the operator supplies the bench limit")),
        "measure_voltage_range": Field(
            "number", unit="V", writable=True,
            description="Measurement voltage range",
            limit=Limit.operator_required("the clone writes the measurement voltage range but states no allowable "
                                          "range; the operator supplies the bench limit")),
        "four_wire": Field(
            "boolean", writable=True,
            description="4-wire sensing; false selects 2-wire"),
        "nplc_current": Field(
            "number", unit="1", writable=True,
            description="Current integration time (power line cycles)",
            limit=Limit.operator_required("the clone writes the current NPLC but states no allowable range; the "
                                          "operator supplies the bench limit")),
        "nplc_voltage": Field(
            "number", unit="1", writable=True,
            description="Voltage integration time (power line cycles)",
            limit=Limit.operator_required("the clone writes the voltage NPLC but states no allowable range; the "
                                          "operator supplies the bench limit")),
        "source_current_range": Field(
            "number", unit="A", writable=True,
            description="Source current range",
            limit=Limit.operator_required("the clone writes the source current range but states no allowable range; "
                                          "the operator supplies the bench limit")),
        "source_voltage_range": Field(
            "number", unit="V", writable=True,
            description="Source voltage range",
            limit=Limit.operator_required("the clone writes the source voltage range but states no allowable range; "
                                          "the operator supplies the bench limit")),
    }

    reads = {
        "identity": {"query": "*IDN?", "parse": {"kind": "str"}},
        "current_compliance": {"query": ":SENS:CURR:PROT?", "parse": {"kind": "float"}},
        "measure_current_range": {"query": ":SENS:CURR:RANG?", "parse": {"kind": "float"}},
        "measure_voltage_range": {"query": ":SENS:VOLT:RANG?", "parse": {"kind": "float"}},
        "four_wire": {"query": ":SYST:RSEN?", "parse": {"kind": "bool"}},
        "nplc_current": {"query": ":SENS:CURR:NPLC?", "parse": {"kind": "float"}},
        "nplc_voltage": {"query": ":SENS:VOLT:NPLC?", "parse": {"kind": "float"}},
        "source_current_range": {"query": ":SOUR:CURR:RANG?", "parse": {"kind": "float"}},
        "source_voltage_range": {"query": ":SOUR:VOLT:RANG?", "parse": {"kind": "float"}},
    }

    writes = {
        "current_compliance": {"write": ":SENS:CURR:PROT {value:g}", "type": "number"},
        "measure_current_range": {"write": ":SENS:CURR:RANG {value:g}", "type": "number"},
        "measure_voltage_range": {"write": ":SENS:VOLT:RANG {value:g}", "type": "number"},
        "four_wire": {"write": ":SYST:RSEN {value}", "type": "string",
                      "enum_map": {False: "OFF", True: "ON"}},
        "nplc_current": {"write": ":SENS:CURR:NPLC {value:g}", "type": "number"},
        "nplc_voltage": {"write": ":SENS:VOLT:NPLC {value:g}", "type": "number"},
        "source_current_range": {"write": ":SOUR:CURR:RANG {value:g}", "type": "number"},
        "source_voltage_range": {"write": ":SOUR:VOLT:RANG {value:g}", "type": "number"},
    }
