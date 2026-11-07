"""Synthetic EPICS Channel Access TagDriver fixture: an integer state PV with a confirmed stop."""
from mhs.driver import Action, Fact, Field, TagDriver

POINTS = {
    "state": {"pv": "state", "type": "integer", "access": "read-write", "source_ref": "synthetic_ioc/ioc.py:8"},
    "brightness": {"pv": "brightness", "type": "number", "access": "read",
                   "source_ref": "synthetic_ioc/ioc.py:9"},
    "label": {"pv": "label", "type": "string", "access": "read", "source_ref": "synthetic_ioc/ioc.py:10"},
}
STOP = {"steps": [{"write": "state", "value": 0}], "confirm": [{"point": "state", "equals": 0}]}
ON, OFF, READ = "x-cap.sdk-fixture.lamp_on.v1", "x-cap.sdk-fixture.lamp_off.v1", "x-cap.sdk-fixture.read_lamp.v1"
STATE = Field("integer", unit="1", description="Lamp state PV read back")


class Driver(TagDriver):
    device_id = "tag-epics-fixture"
    device_kind = "light.source"
    mode, risk = "hardware", "R1"
    native = "synthetic_ioc.ioc:LampIOC"
    backends = {"fake": ".fake:FakeIoc", "hardware": ".native:connect"}
    facts = [Fact("The synthetic IOC serves an integer state PV.", source="upstream_code",
                  ref="synthetic_ioc/ioc.py:8")]
    safe_state = "State PV written 0 and read back 0 (synthetic fixture; no physical claim)."
    tag_config = {"profile": "epics-ca", "timeout_ms": 500, "points": POINTS}
    parameters = {"lamp_state": Field("integer", unit="1", description="State PV"),
                  "brightness": Field("number", unit="1", description="Brightness PV")}
    reads = {"lamp_state": {"point": "state"}, "brightness": {"point": "brightness"}}
    commands = {
        ON: {"steps": [{"write": "state", "value": 1}], "confirm": [{"point": "state", "equals": 1}],
             "result": {"lamp_state": {"point": "state"}}},
        OFF: dict(STOP, result={"lamp_state": {"point": "state"}}),
        READ: {"read": {"brightness": "brightness", "label": "label"}},
    }
    actions = {
        ON: Action(name="lamp_on", output={"lamp_state": STATE}, description="Switch the lamp on and confirm it"),
        OFF: Action(name="lamp_off", safe_state=True, output={"lamp_state": STATE},
                    description="Switch the lamp off and confirm it"),
        READ: Action(name="read_lamp", verb="read", description="Read brightness and status text",
                     output={"brightness": Field("number", unit="1", description="Brightness"),
                              "label": Field("string", description="Status text")}),
    }
    safety_bindings = {"estop": STOP}
