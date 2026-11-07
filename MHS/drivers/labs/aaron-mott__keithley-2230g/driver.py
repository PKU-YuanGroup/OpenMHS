"""OpenMHS driver for gh.aaron-mott/keithley-2230g: the Keithley 2230G power supply over SCPI.

The upstream clone is a single pyvisa class, ``2230G.py:KEI2230G``.  The class is not a usable runtime: its
constructor opens ``self.instr_address`` although its parameter is ``inst_address`` (2230G.py:37), and its
model-specific branches compare the bound method ``self.get_model`` to a string, so they never run
(2230G.py:568).  The driver therefore uses the SCPI command forms the clone shows, not the class itself.  A
``ScpiDriver`` is configuration only: the bridge opens the instrument (host/port or a VISA resource, options of
the hardware backend) and the runtime enforces every limit before a command reaches the wire.

* writes: per-channel voltage and current setpoints and per-channel output enable.  The clone selects a channel
  with ``INST:NSEL`` (2230G.py:403), sets the selected channel with ``VOLT`` (2230G.py:928) and ``CURR``
  (2230G.py:715-731), and switches the selected channel with ``CHAN:OUTP`` (2230G.py:657).  The driver sends the
  selection and the setting as one SCPI compound line (``INST:NSEL n;:VOLT value``); the clone writes them as two
  separate commands, so this composition is checked against the Series 2230 SCPI manual section 4-8, not a hardware run.
* reads: the per-channel setpoints, output states and fresh voltage/current measurements.  The clone reads the
  selected channel with ``VOLT?`` and ``CURR?`` (2230G.py:960, 2230G.py:738), the selected channel output with
  ``CHAN:OUTP?`` (2230G.py:665), and a measurement with ``MEAS:VOLT?`` and ``MEAS:CURR?`` (2230G.py:542,
  2230G.py:496).
* the e-stop and the safe-state action write ``OUTP OFF``, the all-channel output command (2230G.py:820).  This is
  a software output-off through the instrument's own command path; it is not an external hardware e-stop.  The
  safe-state action is the independent stop path the gate can check on the fake backend.

The model is one of 30-3, 30-6 or 60-3 (2230G.py:84), and the clone's voltage and current bounds differ by model.
This command map does not establish the installed model, so every voltage and current
bound is ``Limit.operator_required``: the operator supplies the bound of the actual unit in site-limits.json before
a write is accepted.  Every Fact cites a line of the clone at commit 4c4d9024808f33b20d9148183b006225cced7936.
This package is model-authored and unreviewed; the acceptance gate runs the fake backend only and no hardware was
used.
"""

from mhs.driver import Action, Fact, Field, Limit, ScpiDriver

VOLTAGE_REASON = (
    "The 2230G can be a 30-3, 30-6 or 60-3 (2230G.py:84), and the clone gives different CH1/CH2 voltage bounds "
    "per model (2230G.py:568-652). The model guard compares get_model without calling it (2230G.py:568), and the installed model is "
    "not known at load time; the operator supplies the voltage bound of the actual unit."
)

CURRENT_REASON = (
    "The 2230G current bound depends on the model and channel (2230G.py:715-731). "
    "Those branches compare self.get_model without calling it and therefore do not run. "
    "The operator supplies the current bound of the actual unit."
)


def _voltage_limit() -> Limit:
    """A fresh operator-required voltage bound (the operator overlay fills it before any write)."""

    return Limit.operator_required(VOLTAGE_REASON)


def _current_limit() -> Limit:
    """A fresh operator-required current bound (the operator overlay fills it before any write)."""

    return Limit.operator_required(CURRENT_REASON)


class Keithley2230g(ScpiDriver):
    device_id = "keithley-2230g"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R3"
    native = "pyfile:2230G.py#KEI2230G"
    backends = {"fake": ".fake:FakeKeithley2230g"}
    vendor = "Keithley Instruments"
    model = "2230G series multi-channel programmable DC power supply"
    display_name = "Keithley 2230G multi-channel power supply"
    tags = ["power supply", "keithley", "2230g", "scpi", "instrument"]
    idn = True
    safe_state = "all three channel outputs disabled (OUTP OFF)"
    facts = [
        Fact("The upstream README says the author used National Instruments VISA and could not test the code on "
             "the instrument", source="vendor_doc", ref="README.md:1"),
        Fact("The clone imports visa and defines the device class KEI2230G", source="upstream_code",
             ref="2230G.py:10-12"),
        Fact("The constructor takes inst_address but opens self.instr_address, which it never sets",
             source="upstream_code", ref="2230G.py:14-40"),
        Fact("get_info queries *IDN? and splits the reply on commas into manufacturer, model, serial and firmware",
             source="upstream_code", ref="2230G.py:77-81"),
        Fact("Channel selection writes INST:NSEL with a channel number validated to range(1, 4)",
             source="upstream_code", ref="2230G.py:402-403"),
        Fact("The set_volt body contains VOLT command text for the selected channel", source="upstream_code",
             ref="2230G.py:928"),
        Fact("The set_curr body contains CURR command text for the selected channel", source="upstream_code",
             ref="2230G.py:715-731"),
        Fact("The voltage readback body contains VOLT? query text", source="upstream_code", ref="2230G.py:960"),
        Fact("A current setpoint is queried as CURR?", source="upstream_code", ref="2230G.py:738"),
        Fact("The selected channel output is set with CHAN:OUTP", source="upstream_code", ref="2230G.py:657"),
        Fact("The selected channel output is queried with CHAN:OUTP?", source="upstream_code",
             ref="2230G.py:665"),
        Fact("All channel outputs are set with OUTP", source="upstream_code", ref="2230G.py:820"),
        Fact("All channel outputs are queried with OUTP?", source="upstream_code", ref="2230G.py:828"),
        Fact("A fresh voltage measurement is requested with MEAS:VOLT? on a named channel",
             source="upstream_code", ref="2230G.py:542"),
        Fact("A fresh current measurement is requested with MEAS:CURR? on a named channel",
             source="upstream_code", ref="2230G.py:496"),
        Fact("get_model documents the model types 30-3, 30-6 and 60-3", source="upstream_code",
             ref="2230G.py:84"),
        Fact("The model-specific branches compare the bound method self.get_model to the string '30-3', so they "
             "never run", source="upstream_code", ref="2230G.py:568"),
        Fact("The voltage readback method calls the misspelt self.inst.quert, so that method is broken",
             source="upstream_code", ref="2230G.py:960"),
        Fact("The error queue is queried with SYST:ERR?", source="upstream_code", ref="2230G.py:1320"),
        Fact("The output protection state is cleared with OUTP:PROT:CLE", source="upstream_code",
             ref="2230G.py:784"),
    ]

    parameters = {
        "voltage_setpoint_ch1": Field(
            "number", unit="V", writable=True, description="Channel 1 voltage setpoint (VOLT)",
            limit=_voltage_limit()),
        "voltage_setpoint_ch2": Field(
            "number", unit="V", writable=True, description="Channel 2 voltage setpoint (VOLT)",
            limit=_voltage_limit()),
        "voltage_setpoint_ch3": Field(
            "number", unit="V", writable=True, description="Channel 3 voltage setpoint (VOLT)",
            limit=_voltage_limit()),
        "current_limit_ch1": Field(
            "number", unit="A", writable=True, description="Channel 1 current limit (CURR)",
            limit=_current_limit()),
        "current_limit_ch2": Field(
            "number", unit="A", writable=True, description="Channel 2 current limit (CURR)",
            limit=_current_limit()),
        "current_limit_ch3": Field(
            "number", unit="A", writable=True, description="Channel 3 current limit (CURR)",
            limit=_current_limit()),
        "output_ch1": Field("boolean", writable=True, description="Channel 1 output enabled (CHAN:OUTP)"),
        "output_ch2": Field("boolean", writable=True, description="Channel 2 output enabled (CHAN:OUTP)"),
        "output_ch3": Field("boolean", writable=True, description="Channel 3 output enabled (CHAN:OUTP)"),
        "measured_voltage_ch1": Field("number", unit="V", description="Channel 1 voltage measurement"),
        "measured_voltage_ch2": Field("number", unit="V", description="Channel 2 voltage measurement"),
        "measured_voltage_ch3": Field("number", unit="V", description="Channel 3 voltage measurement"),
        "measured_current_ch1": Field("number", unit="A", description="Channel 1 current measurement"),
        "measured_current_ch2": Field("number", unit="A", description="Channel 2 current measurement"),
        "measured_current_ch3": Field("number", unit="A", description="Channel 3 current measurement"),
    }
    reads = {
        "voltage_setpoint_ch1": {"query": "INST:NSEL 1;:VOLT?", "parse": {"kind": "float"}},
        "voltage_setpoint_ch2": {"query": "INST:NSEL 2;:VOLT?", "parse": {"kind": "float"}},
        "voltage_setpoint_ch3": {"query": "INST:NSEL 3;:VOLT?", "parse": {"kind": "float"}},
        "current_limit_ch1": {"query": "INST:NSEL 1;:CURR?", "parse": {"kind": "float"}},
        "current_limit_ch2": {"query": "INST:NSEL 2;:CURR?", "parse": {"kind": "float"}},
        "current_limit_ch3": {"query": "INST:NSEL 3;:CURR?", "parse": {"kind": "float"}},
        "output_ch1": {"query": "INST:NSEL 1;:CHAN:OUTP?", "parse": {"kind": "bool"}},
        "output_ch2": {"query": "INST:NSEL 2;:CHAN:OUTP?", "parse": {"kind": "bool"}},
        "output_ch3": {"query": "INST:NSEL 3;:CHAN:OUTP?", "parse": {"kind": "bool"}},
        "measured_voltage_ch1": {"query": "MEAS:VOLT? CH1", "parse": {"kind": "float"}},
        "measured_voltage_ch2": {"query": "MEAS:VOLT? CH2", "parse": {"kind": "float"}},
        "measured_voltage_ch3": {"query": "MEAS:VOLT? CH3", "parse": {"kind": "float"}},
        "measured_current_ch1": {"query": "MEAS:CURR? CH1", "parse": {"kind": "float"}},
        "measured_current_ch2": {"query": "MEAS:CURR? CH2", "parse": {"kind": "float"}},
        "measured_current_ch3": {"query": "MEAS:CURR? CH3", "parse": {"kind": "float"}},
    }
    writes = {
        "voltage_setpoint_ch1": {"write": "INST:NSEL 1;:VOLT {value:g}", "type": "number"},
        "voltage_setpoint_ch2": {"write": "INST:NSEL 2;:VOLT {value:g}", "type": "number"},
        "voltage_setpoint_ch3": {"write": "INST:NSEL 3;:VOLT {value:g}", "type": "number"},
        "current_limit_ch1": {"write": "INST:NSEL 1;:CURR {value:g}", "type": "number"},
        "current_limit_ch2": {"write": "INST:NSEL 2;:CURR {value:g}", "type": "number"},
        "current_limit_ch3": {"write": "INST:NSEL 3;:CURR {value:g}", "type": "number"},
        "output_ch1": {"write": "INST:NSEL 1;:CHAN:OUTP {value}", "enum_map": {True: "ON", False: "OFF"}},
        "output_ch2": {"write": "INST:NSEL 2;:CHAN:OUTP {value}", "enum_map": {True: "ON", False: "OFF"}},
        "output_ch3": {"write": "INST:NSEL 3;:CHAN:OUTP {value}", "enum_map": {True: "ON", False: "OFF"}},
    }
    commands = {
        "x-cap.aaron-mott.output_off.v1": {"write": "OUTP OFF",
                                           "description": "Disable all three channel outputs"},
    }
    actions = {
        "x-cap.aaron-mott.output_off.v1": Action(
            name="output_off", description="Disable all three channel outputs (safe state)",
            safe_state=True),
    }
    safety_bindings = {
        "estop": {"write": "OUTP OFF", "description": "disable all outputs"},
        "safe_state": {"write": "OUTP OFF", "description": "disable all outputs"},
    }
