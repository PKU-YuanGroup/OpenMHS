"""OpenMHS rosbridge driver for the Franka TMR spine and battery ROS 2 nodes.

The upstream repository is the Franka Robotics ROS 2 integration.  The two
concrete endpoints used here are the Python ROS 2 nodes ``franka_spine_node``
and ``franka_battery_node``: the spine node action/service server wraps
``SpineController`` (the card's internal entry symbol), and the battery node
wraps ``BatteryController``.  This package is a ``RosDriver`` with local input-domain and paired-observation projection; it declares no Python native class and does not import the
clone.

The main motion path is the ``MoveAbsolute`` ROS 2 action.  The spine is a
single powered linear axis, so the catalogue joint-position class (radians,
joint array) does not fit; the move is an extension capability in metres.
The stop path is the acknowledged private ``~/switch_off`` service
(``SwitchedOff``, disabling motion).  The separate ``~/halt`` service is
exposed as an explicit motion stop but is not the safe state because the
upstream re-arms the drive to ``SwitchedOn`` after the quick-stop.  The
upstream's own ``~/switch_on`` service (``SwitchedOn``, enabling motion) is
the declared re-enable after a safety reset (``reenable=True``, CORE-086):
the reset never calls it and the latch refuses it, so the drive stays
switched off after a reset until an explicit switch-on.  It is not the only
command that re-arms the drive: a successful ``~/halt`` re-arms with switch-on
after its quick-stop (spine_controller.py:318-334) and a cancelled move does the
same (spine_controller.py:404-434); both are ordinary commands the latch refuses.

Every endpoint and type cites the pinned clone at
4acc05c01ebfcdf916ee6b3df966df0ad7b2f9ec.  The fake is a ROS-free recording
transport; no ROS graph or hardware is contacted.
"""

import math

from mhs.driver import Action, DriverFailed, Fact, Field, Limit, RosDriver

_CLONE = "4acc05c01ebfcdf916ee6b3df966df0ad7b2f9ec"

_SPINE_NODE = "franka_spine/franka_spine_server/franka_spine_server/spine_action_server.py"
_BATTERY_NODE = "franka_mobile/franka_mobile/battery_server.py"
_SPINE_CONTROLLER = "franka_spine/franka_spine_server/franka_spine_server/spine_controller.py"
_SPINE_API = "franka_spine/franka_spine_server/franka_spine_server/spine_api_client.py"
_SPINE_DOC = "franka_spine/index.rst"
_MOVE_ACTION = "franka_spine/franka_spine_msgs/action/MoveAbsolute.action"
_HALT_SRV = "franka_spine/franka_spine_msgs/srv/Halt.srv"
_SWITCH_OFF_SRV = "franka_spine/franka_spine_msgs/srv/SwitchOff.srv"
_SWITCH_ON_SRV = "franka_spine/franka_spine_msgs/srv/SwitchOn.srv"

#: The action server registers the private MoveAbsolute action on the
#: franka_spine_node node.  The action type is declared by the import block.
_MOVE = {
    "action": "/franka_spine_node/move_absolute",
    "type": "franka_spine_msgs/action/MoveAbsolute",
    "profile": "ros2-native",
    "source_name": "~/move_absolute",
    "source_ref": f"{_SPINE_NODE}:115-123",
    "type_ref": f"{_SPINE_NODE}:17",
    "success": {"path": "success", "equals": True},
    "args": {
        "position": {"from": "input.position"},
        "velocity": {"from": "input.velocity"},
        "acceleration": {"from": "input.acceleration"},
        "deceleration": {"from": "input.deceleration"},
    },
    "result": {
        "map": {
            "reached": "success",
            "stop_by": "stop_by",
            "error": "error",
        }
    },
}

#: The private Halt service posts the DS402 quick-stop and then re-arms.  It is
#: a motion stop, not the switch-off safe state.
_HALT = {
    "service": "/franka_spine_node/halt",
    "type": "franka_spine_msgs/srv/Halt",
    "source_name": "~/halt",
    "source_ref": f"{_SPINE_NODE}:102-107",
    "type_ref": f"{_SPINE_DOC}:85",
    "success": {"path": "success", "equals": True},
    "result": {"map": {"halted": "success", "state": "state", "message": "message"}},
}

#: The private SwitchOff service transitions the spine to SwitchedOff and
#: disables motion.  Its callback returns after the REST call; the service
#: acknowledgement is an application result, not sensed quiescence.
_SWITCH_OFF = {
    "service": "/franka_spine_node/switch_off",
    "type": "franka_spine_msgs/srv/SwitchOff",
    "source_name": "~/switch_off",
    "source_ref": f"{_SPINE_NODE}:96-101",
    "type_ref": f"{_SPINE_DOC}:71",
    "success": {"path": "success", "equals": True},
    "result": {"map": {"switched_off": "success", "state": "state", "message": "message"}},
}

#: The private SwitchOn service transitions the spine to SwitchedOn and enables
#: motion.  It is the declared re-enable after a safety reset (CORE-086): the
#: reset never calls it, the e-stop latch refuses it, and its acknowledgement
#: is an application result, not sensed device state.
_SWITCH_ON = {
    "service": "/franka_spine_node/switch_on",
    "type": "franka_spine_msgs/srv/SwitchOn",
    "source_name": "~/switch_on",
    "source_ref": f"{_SPINE_NODE}:90-95",
    "type_ref": f"{_SPINE_DOC}:64",
    "success": {"path": "success", "equals": True},
    "result": {"map": {"switched_on": "success", "state": "state", "message": "message"}},
}

#: The battery node publishes sensor_msgs/BatteryState on its private topic.
_BATTERY_STATE = {
    "topic": "/franka_battery_node/battery_state",
    "type": "sensor_msgs/msg/BatteryState",
    "source_name": "~/battery_state",
    "source_ref": f"{_BATTERY_NODE}:83",
    "type_ref": f"{_BATTERY_NODE}:22",
    "operation": "subscribe",
    "path": "$",
    "result": {
        "map": {
            "percentage": "percentage",
            "temperature": "temperature",
            "power_supply_status": "power_supply_status",
            "location": "location",
        }
    },
}

#: The battery node's private std_srvs/Trigger wireless-charging controls.
_CHARGE_STOP = {
    "service": "/franka_battery_node/stop_wireless_charging",
    "type": "std_srvs/srv/Trigger",
    "source_name": "~/stop_wireless_charging",
    "source_ref": f"{_BATTERY_NODE}:62-67",
    "type_ref": f"{_BATTERY_NODE}:23",
    "success": {"path": "success", "equals": True},
    "result": {"map": {"accepted": "success", "message": "message"}},
}
_CHARGE_START = {
    "service": "/franka_battery_node/try_start_wireless_charging",
    "type": "std_srvs/srv/Trigger",
    "source_name": "~/try_start_wireless_charging",
    "source_ref": f"{_BATTERY_NODE}:68-73",
    "type_ref": f"{_BATTERY_NODE}:23",
    "success": {"path": "success", "equals": True},
    "result": {"map": {"accepted": "success", "message": "message"}},
}

_POSITION_LIMIT = Limit.operator_required(
    "the repository states no numeric travel range; GetParameters returns the installed spine's "
    "user limits only at runtime"
)
_VELOCITY_LIMIT = Limit.operator_required(
    "MoveAbsolute.action states only that velocity must be greater than 0; no maximum appears in the repository"
)
_ACCELERATION_LIMIT = Limit.operator_required(
    "MoveAbsolute.action states only that acceleration must be greater than 0; no maximum appears in the repository"
)
_DECELERATION_LIMIT = Limit.operator_required(
    "MoveAbsolute.action states only that deceleration must be greater than 0; no maximum appears in the repository"
)


class _PositiveField(Field):
    """Source-defined open numeric domain; operator envelope still required."""
    def to_schema(self, *, what="field"):
        schema = super().to_schema(what=what)
        schema["exclusiveMinimum"] = 0
        return schema


class FrankaTmrSpine(RosDriver):
    device_id = "franka_tmr"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeFrankaRos2"}
    tags = ["ros", "ros2", "franka", "tmr", "spine", "battery", "linear-axis"]
    display_name = "Franka TMR spine and battery ROS 2 interfaces"
    vendor = "Franka Robotics"
    model = "TMR"

    facts = [
        Fact("The position topic republishes the last successful position on read failure with valid=false; "
             "the state topic copies success into valid and includes error_code and error_description.",
             source="upstream_code", ref=f"{_SPINE_NODE}:146-164"),
        Fact("Cancellation waits for the blocking motion worker, then re-arms the drive before returning "
             "the cancelled motion result.", source="upstream_code", ref=f"{_SPINE_CONTROLLER}:404-434"),
        Fact("BatteryState voltage, current, charge, capacity and design_capacity are set to NaN by the source node.",
             source="upstream_code", ref=f"{_BATTERY_NODE}:133-138"),
        Fact("SpineActionServer constructs the ROS 2 node with the base name franka_spine_node.",
             source="upstream_code", ref=f"{_SPINE_NODE}:35-39"),
        Fact("The spine node registers the private MoveAbsolute action '~/move_absolute' with a ReentrantCallbackGroup.",
             source="upstream_code", ref=f"{_SPINE_NODE}:115-123"),
        Fact("The spine node registers private services '~/get_state', '~/get_position', '~/switch_off', "
             "'~/halt' and '~/get_parameters_spine'.",
             source="upstream_code", ref=f"{_SPINE_NODE}:72-113"),
        Fact("The spine node publishes SpinePosition on '~/position' and SpineState on '~/state' at "
             "1/feedback_rate, and only while each topic has a subscriber.",
             source="upstream_code", ref=f"{_SPINE_NODE}:125-164"),
        Fact("The spine action server fills MoveAbsolute.Result.success from the motion result and copies "
             "stop_by and error from the same result.",
             source="upstream_code", ref=f"{_SPINE_NODE}:195-216"),
        Fact("SpineController.move_absolute requires the drive to be SwitchedOn before it starts motion and "
             "returns an error otherwise.",
             source="upstream_code", ref=f"{_SPINE_CONTROLLER}:376-385"),
        Fact("SpineController.switch_off posts the REST switch-off call, invalidates the cached state and "
             "reports success only when the REST call succeeded.",
             source="upstream_code", ref=f"{_SPINE_CONTROLLER}:307-316"),
        Fact("The spine REST client's switch_off method posts 'spine:switch-off'.",
             source="upstream_code", ref=f"{_SPINE_API}:58-60"),
        Fact("SpineController.halt posts the DS402 quick-stop, waits for SwitchedOff and then re-arms with "
             "switch-on, so a successful Halt returns the drive to SwitchedOn rather than leaving it disabled.",
             source="upstream_code", ref=f"{_SPINE_CONTROLLER}:318-334"),
        Fact("The spine REST client has no motion:halt route; halt_motion posts 'motion:quick-stop', which enters "
             "QuickStopActive and then SwitchedOff.",
             source="upstream_code", ref=f"{_SPINE_API}:95-100"),
        Fact("Halt.srv describes the halt service as immediately halting ongoing motion and ending in SwitchedOn.",
             source="upstream_code", ref=f"{_HALT_SRV}:1"),
        Fact("SwitchOff.srv describes the switch-off service as transitioning to SwitchedOff and disabling motion.",
             source="upstream_code", ref=f"{_SWITCH_OFF_SRV}:1"),
        Fact("The spine node registers the private SwitchOn service '~/switch_on' with the ReentrantCallbackGroup.",
             source="upstream_code", ref=f"{_SPINE_NODE}:90-95"),
        Fact("The switch-on callback calls SpineController.switch_on and copies its success, state and message into "
             "the SwitchOn response.", source="upstream_code", ref=f"{_SPINE_NODE}:242-248"),
        Fact("SpineController.switch_on posts the REST switch-on call, invalidates the cached state and reports "
             "success only when the REST call succeeded.", source="upstream_code", ref=f"{_SPINE_CONTROLLER}:296-305"),
        Fact("The spine REST client's switch_on method posts 'spine:switch-on'.",
             source="upstream_code", ref=f"{_SPINE_API}:62-64"),
        Fact("SwitchOn.srv describes the switch-on service as transitioning to SwitchedOn and enabling motion.",
             source="upstream_code", ref=f"{_SWITCH_ON_SRV}:1"),
        Fact("MoveAbsolute.action declares position in metres and velocity, acceleration and deceleration as "
             "float64 values with a strictly positive requirement.",
             source="upstream_code", ref=f"{_MOVE_ACTION}:1-5"),
        Fact("MOTION_READ_TIMEOUT is 600.0 seconds: a hang guard for the blocking motion-mm:start POST, not a "
             "device motion limit; the device holds the POST until the move finishes or is quick-stopped.",
             source="upstream_code", ref=f"{_SPINE_API}:21-24"),
        Fact("UserLimitsData stores lower_limit and upper_limit with 0.0 dataclass defaults.",
             source="upstream_code", ref=f"{_SPINE_CONTROLLER}:205-210"),
        Fact("SpineController.get_parameters reads the device parameters response and returns its lower_limit "
             "and upper_limit values.",
             source="upstream_code", ref=f"{_SPINE_CONTROLLER}:336-352"),
        Fact("BatteryServer constructs the ROS 2 node with the base name franka_battery_node.",
             source="upstream_code", ref=f"{_BATTERY_NODE}:32-36"),
        Fact("BatteryServer registers std_srvs/Trigger services '~/stop_wireless_charging' and "
             "'~/try_start_wireless_charging'; their callbacks copy the controller result's success and message.",
             source="upstream_code", ref=f"{_BATTERY_NODE}:62-106"),
        Fact("BatteryServer publishes sensor_msgs/BatteryState on '~/battery_state' when enable_battery_topic "
             "is true and publish_rate is positive.",
             source="upstream_code", ref=f"{_BATTERY_NODE}:75-92"),
        Fact("BatteryServer converts battery_level_rsoc to BatteryState.percentage by dividing by 100 and copies "
             "batt_pos_terminal to temperature; charging flags select the power-supply status and location.",
             source="upstream_code", ref=f"{_BATTERY_NODE}:108-139"),
        Fact("BatteryController.stop_wireless_charging and try_start_wireless_charging call the battery REST API "
             "and return success with a message.",
             source="upstream_code", ref="franka_mobile/franka_mobile/battery_controller.py:170-182"),
        Fact("The battery API client exposes 'wireless-charging:stop' and 'wireless-charging:try-start' POST routes.",
             source="upstream_code", ref="franka_mobile/franka_mobile/battery_api_client.py:50-56"),
    ]

    safe_state = (
        "The spine drive is switched off through the acknowledged /franka_spine_node/switch_off service, "
        "which transitions it to SwitchedOff and disables motion; the separate halt service is not the safe "
        "state because it re-arms the drive to SwitchedOn."
    )

    # The resource snapshot uses the upstream's recommended topic observations.
    parameters = {
        "position": Field("number", unit="m", nullable=True,
                          description="Published position in metres when position_valid is true; null for an invalid cached sample"),
        "position_valid": Field("boolean", description="Upstream validity from the same message as position"),
        "state": Field("string", nullable=True,
                       description="Published DS402 state when state_valid is true; null for an invalid sample"),
        "state_valid": Field("boolean", description="Upstream validity from the same message as state"),
        "state_error_code": Field("string", description="Error code from the state sample, including invalid samples"),
        "state_error_description": Field("string", description="Error description from the same state sample"),
    }
    reads = {
        "position": {
            "topic": "/franka_spine_node/position",
            "type": "franka_spine_msgs/msg/SpinePosition",
            "source_name": "~/position",
            "source_ref": f"{_SPINE_NODE}:125",
            "type_ref": f"{_SPINE_NODE}:18",
            "path": "$",
        },
        "state": {
            "topic": "/franka_spine_node/state",
            "type": "franka_spine_msgs/msg/SpineState",
            "source_name": "~/state",
            "source_ref": f"{_SPINE_NODE}:126",
            "type_ref": f"{_SPINE_NODE}:18",
            "path": "$",
        },
    }


    # All companion fields use the complete source message. read() groups them
    # into one subscription per topic, so consecutive samples cannot mis-pair
    # a value and its validity flag. No unseen cached numeric value is invented.
    for _field in ("position_valid",):
        reads[_field] = dict(reads["position"])
    for _field in ("state_valid", "state_error_code", "state_error_description"):
        reads[_field] = dict(reads["state"])
    del _field

    def call(self, capability_id, args=None, ctx=None):
        if capability_id == "x-cap.frankarobotics.spine_move.v1":
            for name in ("velocity", "acceleration", "deceleration"):
                value = (args or {}).get(name)
                if (isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(value) or value <= 0):
                    raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                                       f"{name} must be finite and strictly positive (MoveAbsolute.action:1-5)")
        return super().call(capability_id, args, ctx)

    def read(self, resource_id, fields=None, ctx=None):
        requested = [name for name in (fields or self.parameters) if name in self.parameters]
        if not requested:
            return super().read(resource_id, ["__unbound__"], ctx)
        bases = list(dict.fromkeys("position" if name.startswith("position") else "state"
                                  for name in requested))
        samples = super().read(resource_id, bases, ctx)
        output = {}
        for base, sample in samples.items():
            if not isinstance(sample, dict) or type(sample.get("valid")) is not bool:
                raise DriverFailed("MHS.RESOURCE.STATE_INVALID", f"{base} message lacks boolean validity")
            output[base] = sample[base] if sample["valid"] else None
            output[base + "_valid"] = sample["valid"]
            if base == "state":
                output["state_error_code"] = sample["error_code"]
                output["state_error_description"] = sample["error_description"]
        return {name: output[name] for name in requested}

    commands = {
        "x-cap.frankarobotics.spine_move.v1": _MOVE,
        "x-cap.frankarobotics.spine_halt.v1": _HALT,
        "x-cap.frankarobotics.spine_switch_off.v1": _SWITCH_OFF,
        "x-cap.frankarobotics.spine_switch_on.v1": _SWITCH_ON,
        "x-cap.frankarobotics.battery_state.v1": _BATTERY_STATE,
        "x-cap.frankarobotics.wireless_charge_stop.v1": _CHARGE_STOP,
        "x-cap.frankarobotics.wireless_charge_start.v1": _CHARGE_START,
    }

    actions = {
        "x-cap.frankarobotics.spine_move.v1": Action(
            name="move_absolute",
            verb="invoke",
            long_running=True,
            cancellable=True,
            max_duration_ms=600000,
            description=(
                "Move the spine to an absolute position through the ROS 2 MoveAbsolute action; the action "
                "returns the spine's reached flag and stop reason, and cancellation requests the upstream "
                "quick-stop and re-arm path"
            ),
            input={
                "position": Field(
                    "number", unit="m",
                    description="Target spine position in metres",
                    limit=_POSITION_LIMIT,
                ),
                "velocity": _PositiveField(
                    "number", unit="m/s",
                    description="Motion velocity in metres per second",
                    limit=_VELOCITY_LIMIT,
                ),
                "acceleration": _PositiveField(
                    "number", unit="m/s2",
                    description="Motion acceleration in metres per second squared",
                    limit=_ACCELERATION_LIMIT,
                ),
                "deceleration": _PositiveField(
                    "number", unit="m/s2",
                    description="Motion deceleration in metres per second squared",
                    limit=_DECELERATION_LIMIT,
                ),
            },
            output={
                "reached": Field("boolean",
                                 description="True when MoveAbsolute.Result reports the target was reached"),
                "stop_by": Field("string",
                                 description="Stop reason reported by the spine action result"),
                "error": Field("string",
                               description="Error text reported by the spine action result"),
            },
        ),
        "x-cap.frankarobotics.spine_halt.v1": Action(
            name="halt_motion",
            verb="invoke",
            description=(
                "Halt an ongoing spine motion through the acknowledged Halt service; the upstream quick-stop "
                "then waits for SwitchedOff and re-arms the drive to SwitchedOn, so this is not the safe state"
            ),
            output={
                "halted": Field("boolean",
                                description="True when the Halt service reported success"),
                "state": Field("string",
                               description="Spine state reported after the halt"),
                "message": Field("string",
                                 description="Human-readable Halt service result"),
            },
        ),
        "x-cap.frankarobotics.spine_switch_off.v1": Action(
            name="switch_off_spine",
            verb="invoke",
            safe_state=True,
            description=(
                "Switch the spine drive off through the acknowledged SwitchOff service; the callback returns "
                "after the REST transition to SwitchedOff, which disables motion"
            ),
            output={
                "switched_off": Field("boolean",
                                      description="True when the SwitchOff service reported success"),
                "state": Field("string",
                               description="Spine state reported after switching off"),
                "message": Field("string",
                                 description="Human-readable SwitchOff service result"),
            },
        ),
        "x-cap.frankarobotics.spine_switch_on.v1": Action(
            name="switch_on_spine",
            verb="invoke",
            reenable=True,
            description=(
                "Switch the spine drive on through the acknowledged SwitchOn service (SwitchedOn, enabling "
                "motion); the declared re-enable after a safety reset: the reset never calls it and it is refused "
                "while the e-stop is latched"
            ),
            output={
                "switched_on": Field("boolean",
                                     description="True when the SwitchOn service reported success"),
                "state": Field("string",
                               description="Spine state reported after switching on"),
                "message": Field("string",
                                 description="Human-readable SwitchOn service result"),
            },
        ),
        "x-cap.frankarobotics.battery_state.v1": Action(
            name="read_battery_state",
            verb="read",
            description=(
                "Read one sensor_msgs/BatteryState sample from the battery node's private topic; the sample "
                "reports the charge fraction, battery temperature, charging status and charging location"
            ),
            output={
                "percentage": Field("number", unit="1",
                                    description="State of charge as a fraction of full charge"),
                "temperature": Field("number", unit="Cel",
                                     description="Battery terminal temperature reported by the node"),
                "power_supply_status": Field("integer", unit="1",
                                             description="sensor_msgs/BatteryState power-supply status code"),
                "location": Field("string",
                                  description="Charging location string published by the node"),
            },
        ),
        "x-cap.frankarobotics.wireless_charge_stop.v1": Action(
            name="stop_wireless_charging",
            verb="invoke",
            description=(
                "Stop wireless charging through the acknowledged std_srvs/Trigger service; the output is the "
                "service's application result, not a measured charging state"
            ),
            output={
                "accepted": Field("boolean",
                                  description="True when the Trigger service reported success"),
                "message": Field("string",
                                 description="Human-readable Trigger service message"),
            },
        ),
        "x-cap.frankarobotics.wireless_charge_start.v1": Action(
            name="try_start_wireless_charging",
            verb="invoke",
            description=(
                "Attempt to start wireless charging through the acknowledged std_srvs/Trigger service; the "
                "output is the service's application result, not a measured charging state"
            ),
            output={
                "accepted": Field("boolean",
                                  description="True when the Trigger service reported success"),
                "message": Field("string",
                                 description="Human-readable Trigger service message"),
            },
        ),
    }

    # The native stop is the same acknowledged switch-off service as the
    # input-free safe-state action.  The runtime latches before this call.
    safety_bindings = {"estop": _SWITCH_OFF}
