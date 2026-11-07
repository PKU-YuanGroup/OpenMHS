"""OpenMHS driver for gh.majidbenk/interfaz-virtual-control-remoto-instrumentos-rigol: a RIGOL DP832A
triple-output DC power supply over SCPI (a family driver).

The upstream repository is a Tkinter/PyVISA application, not a headless SDK: ``FuenteContinua`` creates a Tk
``Toplevel`` in its constructor and its command methods read Tk variables
(``intefaz_FuenteContinua_v2.py:32-43`` and ``:428-448``).  The driver therefore follows the card's ScpiDriver
shape: the runtime opens the instrument itself (``host``/``port`` or a VISA resource) and the class attributes below
are the command map.  The commands are the SCPI lines the upstream class builds for the DP832A:

* writes: select a channel with ``:INST:NSEL n`` and set that channel's voltage, current, voltage protection or
  current protection; enable or disable a channel with ``:OUTP CHn,ON`` / ``:OUTP CHn,OFF``;
* reads: the measured voltage, current and power of each channel with ``:MEAS:VOLT? CHn``,
  ``:MEAS:CURR? CHn`` and ``:MEAS:POWE? CHn``;
* ``x-cap.majidbenk.output_off.v1`` disables all three outputs and is the declared safe state; the e-stop writes the
  same three OFF commands.

Every Limit and Fact cites a line of the clone at the pinned commit
770ab3a1f81699873a7aeb86df0b1ab4a5061f5f.  This package is model-authored and unreviewed (``reviewed_by`` is
null).  The loader refuses the hardware backend of an unreviewed model-written package only at R2 and R3; this
driver is R1, so nothing mechanical prevents a hardware run: a human must review the package before anyone passes
``--allow-hardware``.  No hardware was attached and no instrument run is claimed.
"""

from mhs.driver import Action, Fact, Field, Limit, ScpiDriver

UPSTREAM = "intefaz_FuenteContinua_v2.py"
README = "README.txt"


class RigolDp832a(ScpiDriver):
    device_id = "rigol-dp832a"
    device_kind = "instrument"
    mode = "hardware"
    #: A bench supply can energise a load, but its declared envelope is bounded at 30 V / 3 A per channel.
    risk = "R1"
    native = "intefaz_FuenteContinua_v2:FuenteContinua"
    backends = {"fake": ".fake:FakeRigolDP832A"}
    vendor, model = "RIGOL", "DP832A triple-output DC power supply"
    display_name = "RIGOL DP832A DC power supply"
    tags = ["power-supply", "dc-source", "rigol", "dp832a", "scpi", "visa"]
    facts = [
        Fact("The README states the project controls RIGOL instruments (an oscilloscope and a DC power supply) "
             "over PYVISA", source="vendor_doc", ref=f"{README}:2-3"),
        Fact("The README maps the DS1000 oscilloscope to interfaz_osciloscopio_v4.py and the DP800 DC supply to "
             "intefaz_FuenteContinua_v2.py", source="vendor_doc", ref=f"{README}:10-11"),
        Fact("FuenteContinua is a Tk window: its __init__ creates a Toplevel", source="upstream_code",
             ref=f"{UPSTREAM}:31-35"),
        Fact("Connection opens the selected VISA resource with pyvisa and queries *IDN?", source="upstream_code",
             ref=f"{UPSTREAM}:68-74"),
        Fact("The supply window names the instrument RIGOL DP832A", source="upstream_code", ref=f"{UPSTREAM}:36"),
        Fact("A channel is selected with :INST:NSEL and its voltage and current set points are written with "
             ":VOLT and :CURR", source="upstream_code", ref=f"{UPSTREAM}:435-440"),
        Fact("The voltage and current protections are written with :VOLT:PROT and :CURR:PROT on the selected "
             "channel", source="upstream_code", ref=f"{UPSTREAM}:443-448"),
        Fact("A channel output is enabled or disabled with :OUTP CHn,ON or :OUTP CHn,OFF", source="upstream_code",
             ref=f"{UPSTREAM}:411-413"),
        Fact("The measured voltage, current and power are read with :MEAS:VOLT?, :MEAS:CURR? and :MEAS:POWE? on a "
             "named channel", source="upstream_code", ref=f"{UPSTREAM}:452-458"),
        Fact("The channel labels state 30 V and 3 A for channels 1 and 2 and 5 V and 3 A for channel 3",
             source="upstream_code", ref=f"{UPSTREAM}:234-240"),
        Fact("The protection dialog states maximum protection values CH1 33V-3.3A, CH2 33V-3.3A and "
             "CH3 5.5V-3.3A", source="upstream_code", ref=f"{UPSTREAM}:216"),
        Fact("The protection entry defaults are 33 V and 3.3 A, and channel 3 starts at 5.5 V", source="upstream_code",
             ref=f"{UPSTREAM}:335-359"),
        Fact("The transistor sweep writes 0 V and 0.4 A and then disables both channels", source="upstream_code",
             ref=f"{UPSTREAM}:153-203"),
    ]
    safe_state = ("all three channel outputs disabled (:OUTP CHn,OFF); the voltage and current set points are "
                  "left unchanged")
    idn = {"expect": "^RIGOL"}

    parameters = {
        "voltage_1": Field(
            "number", unit="V", writable=True, description="CH1 voltage setpoint",
            limit=Limit(min=0, max=30.0, source="upstream_code", ref=f"{UPSTREAM}:234")),
        "voltage_2": Field(
            "number", unit="V", writable=True, description="CH2 voltage setpoint",
            limit=Limit(min=0, max=30.0, source="upstream_code", ref=f"{UPSTREAM}:237")),
        "voltage_3": Field(
            "number", unit="V", writable=True, description="CH3 voltage setpoint",
            limit=Limit(min=0, max=5.0, source="upstream_code", ref=f"{UPSTREAM}:240")),
        "current_1": Field(
            "number", unit="A", writable=True, description="CH1 current setpoint",
            limit=Limit(min=0, max=3.0, source="upstream_code", ref=f"{UPSTREAM}:234")),
        "current_2": Field(
            "number", unit="A", writable=True, description="CH2 current setpoint",
            limit=Limit(min=0, max=3.0, source="upstream_code", ref=f"{UPSTREAM}:237")),
        "current_3": Field(
            "number", unit="A", writable=True, description="CH3 current setpoint",
            limit=Limit(min=0, max=3.0, source="upstream_code", ref=f"{UPSTREAM}:240")),
        "ovp_1": Field(
            "number", unit="V", writable=True, description="CH1 OVP level",
            limit=Limit(min=0, max=33.0, source="upstream_code", ref=f"{UPSTREAM}:216")),
        "ovp_2": Field(
            "number", unit="V", writable=True, description="CH2 OVP level",
            limit=Limit(min=0, max=33.0, source="upstream_code", ref=f"{UPSTREAM}:216")),
        "ovp_3": Field(
            "number", unit="V", writable=True, description="CH3 OVP level",
            limit=Limit(min=0, max=5.5, source="upstream_code", ref=f"{UPSTREAM}:216")),
        "ocp_1": Field(
            "number", unit="A", writable=True, description="CH1 OCP level",
            limit=Limit(min=0, max=3.3, source="upstream_code", ref=f"{UPSTREAM}:216")),
        "ocp_2": Field(
            "number", unit="A", writable=True, description="CH2 OCP level",
            limit=Limit(min=0, max=3.3, source="upstream_code", ref=f"{UPSTREAM}:216")),
        "ocp_3": Field(
            "number", unit="A", writable=True, description="CH3 OCP level",
            limit=Limit(min=0, max=3.3, source="upstream_code", ref=f"{UPSTREAM}:216")),
        "out_1": Field("boolean", writable=True, description="CH1 output"),
        "out_2": Field("boolean", writable=True, description="CH2 output"),
        "out_3": Field("boolean", writable=True, description="CH3 output"),
        "measured_voltage_1": Field(
            "number", unit="V", description="Measured CH1 output voltage"),
        "measured_voltage_2": Field(
            "number", unit="V", description="Measured CH2 output voltage"),
        "measured_voltage_3": Field(
            "number", unit="V", description="Measured CH3 output voltage"),
        "measured_current_1": Field(
            "number", unit="A", description="Measured CH1 output current"),
        "measured_current_2": Field(
            "number", unit="A", description="Measured CH2 output current"),
        "measured_current_3": Field(
            "number", unit="A", description="Measured CH3 output current"),
        "measured_power_1": Field(
            "number", unit="W", description="Measured CH1 output power"),
        "measured_power_2": Field(
            "number", unit="W", description="Measured CH2 output power"),
        "measured_power_3": Field(
            "number", unit="W", description="Measured CH3 output power"),
    }
    reads = {
        "measured_voltage_1": {"query": ":MEAS:VOLT? CH1", "parse": {"kind": "float"}},
        "measured_voltage_2": {"query": ":MEAS:VOLT? CH2", "parse": {"kind": "float"}},
        "measured_voltage_3": {"query": ":MEAS:VOLT? CH3", "parse": {"kind": "float"}},
        "measured_current_1": {"query": ":MEAS:CURR? CH1", "parse": {"kind": "float"}},
        "measured_current_2": {"query": ":MEAS:CURR? CH2", "parse": {"kind": "float"}},
        "measured_current_3": {"query": ":MEAS:CURR? CH3", "parse": {"kind": "float"}},
        "measured_power_1": {"query": ":MEAS:POWE? CH1", "parse": {"kind": "float"}},
        "measured_power_2": {"query": ":MEAS:POWE? CH2", "parse": {"kind": "float"}},
        "measured_power_3": {"query": ":MEAS:POWE? CH3", "parse": {"kind": "float"}},
    }
    writes = {
        "voltage_1": {"write": ":INST:NSEL 1;:VOLT {value:.6g}", "type": "number"},
        "voltage_2": {"write": ":INST:NSEL 2;:VOLT {value:.6g}", "type": "number"},
        "voltage_3": {"write": ":INST:NSEL 3;:VOLT {value:.6g}", "type": "number"},
        "current_1": {"write": ":INST:NSEL 1;:CURR {value:.6g}", "type": "number"},
        "current_2": {"write": ":INST:NSEL 2;:CURR {value:.6g}", "type": "number"},
        "current_3": {"write": ":INST:NSEL 3;:CURR {value:.6g}", "type": "number"},
        "ovp_1": {"write": ":INST:NSEL 1;:VOLT:PROT {value:.6g}", "type": "number"},
        "ovp_2": {"write": ":INST:NSEL 2;:VOLT:PROT {value:.6g}", "type": "number"},
        "ovp_3": {"write": ":INST:NSEL 3;:VOLT:PROT {value:.6g}", "type": "number"},
        "ocp_1": {"write": ":INST:NSEL 1;:CURR:PROT {value:.6g}", "type": "number"},
        "ocp_2": {"write": ":INST:NSEL 2;:CURR:PROT {value:.6g}", "type": "number"},
        "ocp_3": {"write": ":INST:NSEL 3;:CURR:PROT {value:.6g}", "type": "number"},
        "out_1": {"write": ":OUTP CH1,{value}", "type": "string",
                  "enum_map": {True: "ON", False: "OFF"}},
        "out_2": {"write": ":OUTP CH2,{value}", "type": "string",
                  "enum_map": {True: "ON", False: "OFF"}},
        "out_3": {"write": ":OUTP CH3,{value}", "type": "string",
                  "enum_map": {True: "ON", False: "OFF"}},
    }
    commands = {
        "x-cap.majidbenk.output_off.v1": {
            "write": ":OUTP CH1,OFF;:OUTP CH2,OFF;:OUTP CH3,OFF",
            "description": "Disable all three channel outputs",
        },
    }
    actions = {
        "x-cap.majidbenk.output_off.v1": Action(
            name="output_off", safe_state=True,
            description="Disable all three channel outputs; the safe state of the supply"),
    }
    safety_bindings = {
        "estop": {
            "write": [":OUTP CH1,OFF", ":OUTP CH2,OFF", ":OUTP CH3,OFF"],
            "description": "Disable all three channel outputs",
        },
    }
