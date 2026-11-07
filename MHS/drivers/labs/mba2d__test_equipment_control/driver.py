"""OpenMHS driver for gh.mba2d/test_equipment_control: the A2D electronic load over SCPI (a family driver).

A ScpiDriver is configuration only: the class attributes below are the command map of the SCPI bridge, and the runtime
enforces every limit before a command reaches the wire.  The commands are the text lines of the upstream class
``lab_equipment.Eload_A2D_Eload:A2D_Eload`` (lab_equipment/Eload_A2D_Eload.py:8), which drives the A2D electronic load
over an RS485 bus with pyvisa.  The clone is a driver pack (five entry symbols); this package covers the electronic
load, the first entry symbol of the card, and facts.md names the other four classes as not covered.

The upstream class takes the channel of the load as an argument of every command and defaults to channel 1
(Eload_A2D_Eload.py:49, 55, 65, 68); this driver always uses that default channel and reads no other channel, so the
site selects the load by its RS485 address, which the driver does not change.

* reads: the supply voltage (MEAS:VOLT), the supply voltage at the ADC (MEAS:VOLT:ADC), the temperature the load
  reports (MEAS:TEMP), the target current the load reports (CURR) and the output relay, the LED and the fan of the
  channel (INSTR:RELAY, INSTR:LED, INSTR:FAN);
* writes: the constant-current setpoint (CURR), bounded by the maximum current the upstream code states, and the
  relay, the LED and the fan (INSTR:*,1/0);
* the e-stop opens the output relay (``INSTR:RELAY 1,0``), the safe state of a current sink.

Every Fact and Limit cites a line of the clone at the pinned commit (34bb54c13c766fdfe7e6260872a03e8dfefd3ad2).  This
package is model-authored and unreviewed: it is checked on the fake backend only, and its wire syntax has not been
tried on an instrument (README.md).
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

ELOAD = "lab_equipment/Eload_A2D_Eload.py"


class A2DEload(ScpiDriver):
    device_id = "a2d-eload"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "lab_equipment.Eload_A2D_Eload:A2D_Eload"
    backends = {"fake": ".fake:FakeA2DEload"}
    vendor, model = "A2D Electronics", "A2D Eload (RS485 electronic load)"
    display_name = "A2D electronic load"
    tags = ["electronic load", "battery test", "rs485", "scpi", "pyvisa"]
    facts = [
        Fact("A2D_Eload is the class that controls the A2D electronic load with pyvisa commands over the RS485 bus",
             source="upstream_code", ref=f"{ELOAD}:1-8"),
        Fact("The class declares max_channels = 32: at most 32 eloads are connected on the RS485 bus",
             source="upstream_code", ref=f"{ELOAD}:9"),
        Fact("initialize() splits the *IDN? reply into manufacturer, model number, serial number and firmware version",
             source="upstream_code", ref=f"{ELOAD}:25-29"),
        Fact("A model number containing 'Eload' sets max_current to 10.0 A", source="upstream_code",
             ref=f"{ELOAD}:31-32"),
        Fact("set_current writes 'CURR {channel},{current_setpoint_A}' and takes the absolute value of a negative "
             "setpoint", source="upstream_code", ref=f"{ELOAD}:49-52"),
        Fact("toggle_output writes 'INSTR:RELAY {channel},1' or 'INSTR:RELAY {channel},0'; closing the relay also "
             "sets the current to 0 first and writes the stored setpoint again", source="upstream_code",
             ref=f"{ELOAD}:55-62"),
        Fact("get_output queries 'INSTR:RELAY {channel}?' and converts the reply to bool", source="upstream_code",
             ref=f"{ELOAD}:65-66"),
        Fact("measure_voltage_supply queries 'MEAS:VOLT {channel}?'", source="upstream_code", ref=f"{ELOAD}:68-69"),
        Fact("measure_voltage_adc_supply queries 'MEAS:VOLT:ADC {channel}?'", source="upstream_code",
             ref=f"{ELOAD}:71-72"),
        Fact("measure_current returns the target current from 'CURR {channel}?' multiplied by -1",
             source="upstream_code", ref=f"{ELOAD}:74-75"),
        Fact("measure_temperature queries 'MEAS:TEMP {channel}?'", source="upstream_code", ref=f"{ELOAD}:80-81"),
        Fact("set_led and set_fan write 'INSTR:LED {channel},1/0' and 'INSTR:FAN {channel},1/0'; get_led and get_fan "
             "query 'INSTR:LED {channel}?' and 'INSTR:FAN {channel}?'", source="upstream_code",
             ref=f"{ELOAD}:83-99"),
        Fact("reset writes '*RST'", source="upstream_code", ref=f"{ELOAD}:40-41"),
        Fact("get_rs485_addr and set_rs485_addr read and write 'INSTR:RS485'", source="upstream_code",
             ref=f"{ELOAD}:125-129"),
    ]
    safe_state = "output relay open and the current setpoint zero (the load does not sink current)"
    # The class reads *IDN? and splits it into four fields (Eload_A2D_Eload.py:25-29); the clone prints no exact
    # identity string, so the bridge queries the identity and accepts any reply.
    idn = True

    parameters = {
        "current": Field(
            "number", unit="A", writable=True, description="Constant-current setpoint of the load (CURR)",
            limit=Limit(max=10.0, source="upstream_code", ref=f"{ELOAD}:31-32",
                        reason="initialize() sets max_current to 10.0 A for a model number containing 'Eload'")),
        "voltage": Field("number", unit="V", description="Supply voltage measured by the load (MEAS:VOLT)"),
        "adc_voltage": Field("number", unit="V",
                             description="Supply voltage measured by the load's ADC (MEAS:VOLT:ADC)"),
        "current_reported": Field(
            "number", unit="A",
            description="Target current as the load reports it (CURR); the reply is negative while the load sinks "
                        "current, and the clone multiplies it by -1 to obtain the positive setpoint"),
        "temperature": Field("number", description="Temperature value the load reports (MEAS:TEMP); the clone does "
                                                   "not state its unit or scale"),
        "output": Field("boolean", writable=True, description="Output relay of the load channel (INSTR:RELAY)"),
        "led": Field("boolean", writable=True, description="LED of the load channel (INSTR:LED)"),
        "fan": Field("boolean", writable=True, description="Fan of the load channel (INSTR:FAN)"),
    }
    reads = {
        "voltage": {"query": "MEAS:VOLT 1?", "parse": {"kind": "float"}},
        "adc_voltage": {"query": "MEAS:VOLT:ADC 1?", "parse": {"kind": "float"}},
        "current_reported": {"query": "CURR 1?", "parse": {"kind": "float"}},
        "temperature": {"query": "MEAS:TEMP 1?", "parse": {"kind": "float"}},
        "output": {"query": "INSTR:RELAY 1?", "parse": {"kind": "bool"}},
        "led": {"query": "INSTR:LED 1?", "parse": {"kind": "bool"}},
        "fan": {"query": "INSTR:FAN 1?", "parse": {"kind": "bool"}},
    }
    writes = {
        "current": {"write": "CURR 1,{value:g}", "type": "number"},
        "output": {"write": "INSTR:RELAY 1,{value}", "type": "integer", "enum_map": {True: 1, False: 0}},
        "led": {"write": "INSTR:LED 1,{value}", "type": "integer", "enum_map": {True: 1, False: 0}},
        "fan": {"write": "INSTR:FAN 1,{value}", "type": "integer", "enum_map": {True: 1, False: 0}},
    }
    safety_bindings = {"estop": {"write": "INSTR:RELAY 1,0"}}
