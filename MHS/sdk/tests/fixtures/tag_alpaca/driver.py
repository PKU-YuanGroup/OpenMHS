"""Synthetic ASCOM Alpaca TagDriver fixture: properties, an input-bound method and a confirmed abort."""
from mhs.driver import Action, Fact, Field, Limit, TagDriver

POINTS = {
    "azimuth": {"member": "azimuth", "type": "number", "access": "read", "source_ref": "synthetic_alpaca/dome.py:8"},
    "slewing": {"member": "slewing", "type": "boolean", "access": "read", "source_ref": "synthetic_alpaca/dome.py:13"},
    "slewtoazimuth": {"member": "slewtoazimuth", "method": True, "params": {"Azimuth": "number"},
                      "source_ref": "synthetic_alpaca/dome.py:18"},
    "abortslew": {"member": "abortslew", "method": True, "source_ref": "synthetic_alpaca/dome.py:23"},
}
STOP = {"steps": [{"invoke": "abortslew"}], "confirm": [{"point": "slewing", "equals": False}]}
SLEW, ABORT = "x-cap.sdk-fixture.slew.v1", "x-cap.sdk-fixture.abort.v1"


class Driver(TagDriver):
    device_id = "tag-alpaca-fixture"
    device_kind = "motion.axis"
    mode, risk = "hardware", "R2"
    native = "synthetic_alpaca.dome:Dome"
    backends = {"fake": ".fake:FakeDome", "hardware": ".native:connect"}
    facts = [Fact("The synthetic responders include an abortslew method.", source="upstream_code",
                  ref="synthetic_alpaca/dome.py:23")]
    safe_state = "AbortSlew acknowledged and Slewing read back false (synthetic fixture; no physical claim)."
    tag_config = {"profile": "alpaca", "device_type": "dome", "device_number": 0,
                  "device_type_ref": "synthetic_alpaca/app.py:5",
                  "timeout_ms": 500, "points": POINTS}
    parameters = {"azimuth": Field("number", unit="deg", description="Dome azimuth property"),
                  "slewing": Field("boolean", description="Slewing property")}
    reads = {"azimuth": {"point": "azimuth"}, "slewing": {"point": "slewing"}}
    commands = {
        SLEW: {"steps": [{"invoke": "slewtoazimuth", "args": {"Azimuth": {"input": "azimuth"}}}],
               "result": {"target_azimuth": {"input": "azimuth"}}},
        ABORT: dict(STOP, result={"slewing": {"point": "slewing"}}),
    }
    actions = {
        SLEW: Action(name="slew", risk="R2", description="Start a slew to an azimuth (acknowledged start only)",
                     input={"azimuth": Field("number", unit="deg", description="Target azimuth",
                                              limit=Limit.operator_required("synthetic"))},
                     output={"target_azimuth": Field("number", unit="deg", description="Requested azimuth")}),
        ABORT: Action(name="abort", safe_state=True, description="Abort the slew and confirm Slewing is false",
                      output={"slewing": Field("boolean", description="Slewing read back")}),
    }
    safety_bindings = {"estop": STOP}
