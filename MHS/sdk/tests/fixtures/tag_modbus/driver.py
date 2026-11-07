"""Synthetic Modbus TagDriver fixture: coils, discrete inputs, scaled and two-word registers, a confirmed stop."""
from mhs.driver import Action, Fact, Field, Limit, TagDriver

POINTS = {
    "heater": {"table": "coil", "register": 0, "type": "bool", "access": "read-write",
               "source_ref": "synthetic_plc/device.py:12-15"},
    "door": {"table": "discrete", "register": 10, "type": "bool", "access": "read",
             "source_ref": "synthetic_plc/device.py:18"},
    "temperature": {"table": "input", "register": 100, "type": "int16", "decimals": 1, "access": "read",
                    "source_ref": "synthetic_plc/device.py:21"},
    "setpoint": {"table": "holding", "register": 200, "type": "uint16", "decimals": 1, "access": "write",
                 "source_ref": "synthetic_plc/device.py:24"},
    "counter": {"table": "holding", "register": 300, "type": "uint32", "word_order": "big", "access": "read",
                "source_ref": "synthetic_plc/device.py:27"},
    "flow": {"table": "input", "register": 400, "type": "float32", "word_order": "little", "access": "read",
             "source_ref": "synthetic_plc/device.py:30"},
    "mode": {"table": "holding", "register": 500, "type": "uint16", "access": "read-write",
             "source_ref": "synthetic_plc/device.py:33-36"},
}
STOP = {"steps": [{"write": "heater", "value": False}], "confirm": [{"point": "heater", "equals": False}]}
ON, OFF, PROCESS = "x-cap.sdk-fixture.heater_on.v1", "x-cap.sdk-fixture.heater_off.v1", "x-cap.sdk-fixture.read_process.v1"
HEATER = Field("boolean", description="Heater enable coil read back")


class Driver(TagDriver):
    device_id = "tag-modbus-fixture"
    device_kind = "thermal.zone"
    mode, risk = "hardware", "R2"
    native = "synthetic_plc.device:SyntheticPlc"
    backends = {"fake": ".fake:FakePlc", "hardware": ".native:connect"}
    facts = [Fact("The synthetic map writes the heater enable to coil 0.", source="upstream_code",
                  ref="synthetic_plc/device.py:15")]
    safe_state = "Heater coil 0 written off and read back off (synthetic fixture; no physical claim)."
    tag_config = {"profile": "modbus", "timeout_ms": 500, "points": POINTS}
    parameters = {
        "heater_on": Field("boolean", description="Heater enable coil 0"),
        "door_closed": Field("boolean", description="Door discrete input 10"),
        "temperature": Field("number", unit="Cel", description="Input register 100 in tenths"),
        "counter": Field("integer", unit="1", description="Holding 300-301 counter"),
        "flow": Field("number", unit="L/min", description="Input 400-401 float32 flow"),
        "setpoint": Field("number", unit="Cel", writable=True, limit=Limit.operator_required("synthetic"),
                          description="Holding 200 setpoint in 0.1 steps; last acknowledged write"),
        "mode": Field("integer", unit="1", writable=True, limit=Limit.operator_required("synthetic"),
                      description="Holding 500 mode word, verified by read-back"),
    }
    reads = {"heater_on": {"point": "heater"}, "door_closed": {"point": "door"},
             "temperature": {"point": "temperature"}, "counter": {"point": "counter"},
             "flow": {"point": "flow"}, "mode": {"point": "mode"}}
    writes = {"setpoint": {"point": "setpoint"}, "mode": {"point": "mode", "verify": "mode"}}
    commands = {
        ON: {"steps": [{"write": "heater", "value": True}], "confirm": [{"point": "heater", "equals": True}],
             "result": {"heater_on": {"point": "heater"}}},
        OFF: dict(STOP, result={"heater_on": {"point": "heater"}}),
        PROCESS: {"read": {"temperature": "temperature", "flow": "flow"}},
    }
    actions = {
        ON: Action(name="heater_on", risk="R2", output={"heater_on": HEATER}, description="Enable the heater coil"),
        OFF: Action(name="heater_off", safe_state=True, output={"heater_on": HEATER},
                    description="Disable the heater coil and confirm it"),
        PROCESS: Action(name="read_process", verb="read", description="Read temperature and flow",
                        output={"temperature": Field("number", unit="Cel", description="Temperature"),
                                 "flow": Field("number", unit="L/min", description="Flow")}),
    }
    safety_bindings = {"estop": STOP}
