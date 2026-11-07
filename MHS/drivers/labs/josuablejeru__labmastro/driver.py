"""OpenMHS TagDriver for a Hanmatek HM bench supply through labmastro's Modbus RTU register map.

The upstream class ``HanmatekHmControl`` drives a ``minimalmodbus.Instrument``
with fixed holding registers (``labmastro/power_supply/hanmatek/hm/control.py``).
This configuration-only package declares those registers as tag points; the
SDK's TagBridge reads and writes them through a transport. The fake is a
register store; the hardware backend (``native.py``) builds the minimalmodbus
transport and never starts before a human signs ``reviewed_by`` with scope
hardware (all tag-bridge hardware, every risk class).

Every register cites the pinned clone at 86db05e8dd4e37d66667e18e4d8e2fadbb864b18.
The supply's voltage and current ranges are not stated in the clone (the class
is meant for every HM model), so every setpoint and protection limit is
operator-required. The output-off register write is the stop; it is confirmed
by reading register 0x0001 back, as the upstream power_off does.

Residual hazard for the human reviewer: output_on energises the load at the
setpoints the supply holds at that moment (front panel, an earlier session or
this endpoint). The setpoint registers are only written upstream, so this
package can neither read nor bound the live setpoints; the operator limits bound
only the values this endpoint writes. The operator sets and verifies the
setpoints on the supply before enabling the output.
"""

from mhs.driver import Action, Fact, Field, Limit, TagDriver

CONTROL = "labmastro/power_supply/hanmatek/hm/control.py"
INSTRUMENT = "labmastro/power_supply/hanmatek/hm/instrument.py"

#: Registers exactly as the upstream class addresses them (function codes 3 and 6, unsigned 16-bit words).
POINTS = {
    "output": {"table": "holding", "register": 0x0001, "type": "bool", "access": "read-write",
               "source_ref": f"{CONTROL}:66-82",
               "description": "Output state: power_on writes 1, power_off writes 0, get_power_status reads it"},
    "voltage_display": {"table": "holding", "register": 0x0010, "type": "uint16", "decimals": 2, "access": "read",
                        "source_ref": f"{CONTROL}:14"},
    "current_display": {"table": "holding", "register": 0x0011, "type": "uint16", "decimals": 3, "access": "read",
                        "source_ref": f"{CONTROL}:19"},
    "voltage_set": {"table": "holding", "register": 0x0030, "type": "uint16", "decimals": 2, "access": "write",
                    "source_ref": f"{CONTROL}:32-33"},
    "current_set": {"table": "holding", "register": 0x0031, "type": "uint16", "decimals": 3, "access": "write",
                    "source_ref": f"{CONTROL}:38-41"},
    "over_voltage_set": {"table": "holding", "register": 0x0020, "type": "uint16", "decimals": 2, "access": "write",
                         "source_ref": f"{CONTROL}:46-47"},
    "over_current_set": {"table": "holding", "register": 0x0021, "type": "uint16", "decimals": 3, "access": "write",
                         "source_ref": f"{CONTROL}:52-53"},
}

_RANGE = "the clone states no range for the installed HM model"
_OUTPUT = Field("boolean", description="Output state register 0x0001 read back after the command")
_STOP = {"steps": [{"write": "output", "value": False}], "confirm": [{"point": "output", "equals": False}]}


class HanmatekHm(TagDriver):
    device_id = "hanmatek-hm"
    device_kind = "instrument.smu"
    mode = "hardware"
    risk = "R2"
    native = "labmastro.power_supply.hanmatek.hm.control:HanmatekHmControl"
    backends = {"fake": ".fake:FakeHanmatek", "hardware": ".native:connect"}
    vendor, model = "Hanmatek", "HM series"
    display_name = "Hanmatek HM bench supply (labmastro Modbus RTU)"
    tags = ["power-supply", "modbus", "modbus-rtu", "tag-bridge", "hanmatek"]
    facts = [
        Fact("HanmatekHmInstrument opens the port in Modbus RTU mode with slave address 1 by default, at 9600 baud, "
             "8 data bits, no parity, 1 stop bit and a 1 s timeout.", source="upstream_code", ref=f"{INSTRUMENT}:7-28"),
        Fact("get_voltage reads holding register 0x0010 with two decimals (function code 3); get_current reads 0x0011 "
             "with three decimals and divides that result by 1000 again before returning it.",
             source="upstream_code", ref=f"{CONTROL}:12-20"),
        Fact("set_voltage writes int(voltage * 100) to register 0x0030 and set_current writes int(current * 1000) to "
             "0x0031, both with function code 6.", source="upstream_code", ref=f"{CONTROL}:30-42"),
        Fact("set_over_voltage_protection writes int(volts * 100) to 0x0020 and set_over_current_protection writes "
             "int(amps * 1000) to 0x0021 with function code 6.", source="upstream_code", ref=f"{CONTROL}:44-54"),
        Fact("power_on and power_off write 1 and 0 to register 0x0001 and then return get_power_status, which reads "
             "0x0001 and reports False only for 0.", source="upstream_code", ref=f"{CONTROL}:66-82"),
        Fact("get_power combines registers 0x0012 and 0x0013 as (high_power < 16) + low_power, a comparison rather "
             "than a shift.", source="upstream_code", ref=f"{CONTROL}:22-28"),
        Fact("set_over_power_protection splits int(watts * 1000) into a high word for 0x0022 and a low word for 0x0023 "
             "and writes them with two separate function code 6 requests.", source="upstream_code",
             ref=f"{CONTROL}:56-64"),
    ]
    safe_state = ("Output disabled: register 0x0001 written 0 and read back 0. Setpoints and protection limits keep "
                  "their values; the reading proves what the supply reports, not that a load is de-energized.")
    tag_config = {"profile": "modbus", "timeout_ms": 1000, "points": POINTS}
    parameters = {
        "output_enabled": Field("boolean", description="Output state register 0x0001 as read back from the supply"),
        "voltage": Field("number", unit="V", description="Displayed output voltage, register 0x0010 (two decimals)"),
        "current": Field("number", unit="A", description="Displayed output current, register 0x0011 (three decimals)"),
        "voltage_setpoint": Field("number", unit="V", writable=True, limit=Limit.operator_required(_RANGE),
                                  description="Voltage setpoint 0x0030 in 0.01 V steps; last acknowledged write"),
        "current_setpoint": Field("number", unit="A", writable=True, limit=Limit.operator_required(_RANGE),
                                  description="Current setpoint 0x0031 in 0.001 A steps; last acknowledged write"),
        "over_voltage_protection": Field("number", unit="V", writable=True, limit=Limit.operator_required(_RANGE),
                                         description="Over-voltage protection 0x0020 in 0.01 V steps; last write"),
        "over_current_protection": Field("number", unit="A", writable=True, limit=Limit.operator_required(_RANGE),
                                         description="Over-current protection 0x0021 in 0.001 A steps; last write"),
    }
    reads = {"output_enabled": {"point": "output"}, "voltage": {"point": "voltage_display"},
             "current": {"point": "current_display"}}
    writes = {"voltage_setpoint": {"point": "voltage_set"}, "current_setpoint": {"point": "current_set"},
              "over_voltage_protection": {"point": "over_voltage_set"},
              "over_current_protection": {"point": "over_current_set"}}
    commands = {
        "x-cap.josuablejeru.output_on.v1": {"steps": [{"write": "output", "value": True}],
                                            "confirm": [{"point": "output", "equals": True}],
                                            "result": {"output_enabled": {"point": "output"}}},
        "x-cap.josuablejeru.output_off.v1": dict(_STOP, result={"output_enabled": {"point": "output"}}),
    }
    actions = {
        "x-cap.josuablejeru.output_on.v1": Action(
            name="output_on", risk="R2", output={"output_enabled": _OUTPUT},
            description=("Enable the output (0x0001 = 1, confirmed by read-back) at the supply's live setpoints, "
                         "which this package cannot read or bound: set and verify them on the supply first")),
        "x-cap.josuablejeru.output_off.v1": Action(
            name="output_off", safe_state=True, output={"output_enabled": _OUTPUT},
            description="Disable the supply output (register 0x0001 = 0) and confirm it by read-back"),
    }
    safety_bindings = {"estop": _STOP}
