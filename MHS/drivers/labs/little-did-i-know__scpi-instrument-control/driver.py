"""OpenMHS driver for gh.little-did-i-know/scpi-instrument-control: a Siglent SPD3303X power supply.

The upstream package is a multi-instrument SCPI library.  This package binds one entry symbol,
``scpi_control.power_supply:PowerSupply`` (power_supply.py:35), and configures it for the Siglent SPD3303X/SPD3303X-E
command dialect: the model-specific commands in ``PSUSCPICommandSet.SIGLENT_SPD_OVERRIDES``
(psu_scpi_commands.py:94-145).  A ScpiDriver is configuration only; the bridge sends the text lines and the runtime
enforces every limit before a line reaches the wire.

* output 1: voltage setpoint (``CH1:VOLT``), current limit (``CH1:CURR``), measured voltage and current
  (``MEASure:VOLTage? CH1`` and ``MEASure:CURRent? CH1``);
* tracking mode (``OUTP:TRACK``) takes the numeric wire values 0, 1 and 2;
* identify (``*IDN?``) and the error queue (``SYST:ERR?``);
* the e-stop writes ``OUTPut CH1,OFF`` and ``OUTPut CH2,OFF``, the two programmable outputs.

Every Limit and Fact cites a line of the clone at commit e252a04dd33d57a543f5a65280cadfbaa634a4a5.  The device model
is the SPD3303X/SPD3303X-E, because the upstream code states its voltage and current bounds; the generic fallback
profile is explicitly a conservative guess (psu_models.py:265-295) and is not used.  This package is model-authored,
unreviewed, and no hardware backend was run.
"""

from mhs.driver import Action, Fact, Field, Limit, ScpiDriver

PSU_MODELS = "scpi_control/psu_models.py"
PSU_COMMANDS = "scpi_control/psu_scpi_commands.py"
PSU_OUTPUT = "scpi_control/power_supply_output.py"
PSU = "scpi_control/power_supply.py"


class Spd3303x(ScpiDriver):
    device_id = "spd3303x"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "scpi_control.power_supply:PowerSupply"
    backends = {"fake": ".fake:FakeSpd3303x"}
    vendor, model = "Siglent", "SPD3303X / SPD3303X-E"
    display_name = "Siglent SPD3303X programmable power supply"
    tags = ["power supply", "psu", "siglent", "spd3303x", "scpi"]
    facts = [
        Fact("The package controls generic SCPI-99 power supplies and Siglent SPD series models",
             source="upstream_code", ref=f"{PSU}:3-4"),
        Fact("PowerSupply is the power-supply entry class and creates its outputs after connect",
             source="upstream_code", ref=f"{PSU}:35"),
        Fact("The SPD3303X and SPD3303X-E outputs 1 and 2 are rated 30 V and 3 A",
             source="upstream_code", ref=f"{PSU_MODELS}:77-78"),
        Fact("A voltage setpoint is accepted only when 0 <= volts <= max_voltage",
             source="upstream_code", ref=f"{PSU_OUTPUT}:76"),
        Fact("A current setpoint is accepted only when 0 <= amps <= max_current",
             source="upstream_code", ref=f"{PSU_OUTPUT}:116"),
        Fact("The Siglent setpoint commands are CH{ch}:VOLT and CH{ch}:CURR",
             source="upstream_code", ref=f"{PSU_COMMANDS}:96-99"),
        Fact("A voltage setting is sent as 'CH1:VOLT 5.0'",
             source="upstream_code", ref=f"{PSU_COMMANDS}:183"),
        Fact("The Siglent measurement commands are MEASure:VOLTage? CH{ch} and MEASure:CURRent? CH{ch}",
             source="upstream_code", ref=f"{PSU_COMMANDS}:103-105"),
        Fact("The Siglent output command is OUTPut CH{ch},{ON|OFF}",
             source="upstream_code", ref=f"{PSU_COMMANDS}:107"),
        Fact("Tracking is sent as OUTP:TRACK {mode} with the numeric wire values 0 independent, 1 series, 2 parallel",
             source="upstream_code", ref=f"{PSU_COMMANDS}:140-151"),
        Fact("The identity example is 'Siglent Technologies,SPD3303X,SPD3XXXXXXXXXXX,V1.01' and *IDN? returns it",
             source="upstream_code", ref=f"{PSU}:196-205"),
        Fact("SYST:ERR? reads the error queue",
             source="upstream_code", ref=f"{PSU}:219-225"),
        Fact("reset() writes *RST and turns off all outputs",
             source="upstream_code", ref=f"{PSU}:207-213"),
    ]
    safe_state = "outputs 1 and 2 switched off (OUTPut CH1,OFF and OUTPut CH2,OFF)"
    idn = {"expect": r"^Siglent Technologies,SPD3303X(-E)?,"}

    parameters = {
        "voltage": Field(
            "number", unit="V", writable=True, description="Output 1 voltage setpoint (CH1:VOLT)",
            limit=Limit(min=0.0, max=30.0, source="upstream_code", ref=f"{PSU_MODELS}:77",
                        reason="the SPD3303X output 1 is rated 30 V (psu_models.py:77); the setter accepts "
                               "0 through max_voltage (power_supply_output.py:76)")),
        "current": Field(
            "number", unit="A", writable=True, description="Output 1 current limit (CH1:CURR)",
            limit=Limit(min=0.0, max=3.0, source="upstream_code", ref=f"{PSU_MODELS}:77",
                        reason="the SPD3303X output 1 is rated 3 A (psu_models.py:77); the setter accepts "
                               "0 through max_current (power_supply_output.py:116)")),
        "tracking": Field(
            "integer", unit="1", writable=True, enum=[0, 1, 2],
            description="Tracking mode: 0 independent, 1 series, 2 parallel (OUTP:TRACK)",
            limit=Limit(allowed=[0, 1, 2], source="upstream_code", ref=f"{PSU_COMMANDS}:151",
                        reason="the wire values are 0 independent, 1 series and 2 parallel")),
        "measured_voltage": Field("number", unit="V",
                                  description="Measured output 1 voltage (MEASure:VOLTage? CH1)"),
        "measured_current": Field("number", unit="A",
                                  description="Measured output 1 current (MEASure:CURRent? CH1)"),
        "identity": Field("string", description="Reply to *IDN?"),
        "last_error": Field("string", description="Head of the SYST:ERR? error queue"),
    }
    reads = {
        "voltage": {"query": "CH1:VOLT?", "parse": {"kind": "float"}},
        "current": {"query": "CH1:CURR?", "parse": {"kind": "float"}},
        "tracking": {"query": "OUTP:TRACK?", "parse": {"kind": "int"}},
        "measured_voltage": {"query": "MEASure:VOLTage? CH1", "parse": {"kind": "float"}},
        "measured_current": {"query": "MEASure:CURRent? CH1", "parse": {"kind": "float"}},
        "identity": {"query": "*IDN?", "parse": {"kind": "str"}},
        "last_error": {"query": "SYST:ERR?", "parse": {"kind": "str"}},
    }
    writes = {
        "voltage": {"write": "CH1:VOLT {value:.6g}", "type": "number"},
        "current": {"write": "CH1:CURR {value:.6g}", "type": "number"},
        "tracking": {"write": "OUTP:TRACK {value:d}", "type": "integer"},
    }
    commands = {
        "x-cap.little-did-i-know.identify.v1": {
            "query": "*IDN?", "parse": {"kind": "str"},
            "result": {"map": {"identity": "output.$"}},
        },
        "x-cap.little-did-i-know.measure_voltage.v1": {
            "query": "MEASure:VOLTage? CH1", "parse": {"kind": "float"},
            "result": {"map": {"voltage": "output.$"}},
        },
        "x-cap.little-did-i-know.measure_current.v1": {
            "query": "MEASure:CURRent? CH1", "parse": {"kind": "float"},
            "result": {"map": {"current": "output.$"}},
        },
    }
    actions = {
        "x-cap.little-did-i-know.identify.v1": Action(
            name="identify", description="Read the instrument identity",
            output={"identity": Field("string", description="Reply to *IDN?")}),
        "x-cap.little-did-i-know.measure_voltage.v1": Action(
            name="measure_voltage", description="Measure output 1 voltage",
            output={"voltage": Field("number", unit="V", description="Measured output 1 voltage")}),
        "x-cap.little-did-i-know.measure_current.v1": Action(
            name="measure_current", description="Measure output 1 current",
            output={"current": Field("number", unit="A", description="Measured output 1 current")}),
    }
    safety_bindings = {
        "estop": {"write": ["OUTPut CH1,OFF", "OUTPut CH2,OFF"],
                  "description": "switch both programmable outputs off"},
    }
