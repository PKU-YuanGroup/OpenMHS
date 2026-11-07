"""OpenMHS rosbridge driver for the Kinova Kortex ROS 1 base stop services.

The upstream ``kortex_driver`` is a C++ ROS 1 node.  This package is a
configuration-only :class:`RosDriver` over rosbridge and declares no Python
native class.  The scope is deliberately narrow: the acknowledged
``base/stop`` and ``base/apply_emergency_stop`` services only.  It does not
expose joint or Cartesian motion, gripper commands, fault clearing, other
reset/reenable services, state observations or node shutdown.

Every endpoint, type and fact cites the pinned clone at
c3280d8a6a6b5d96590d51538e3f265710a6c77d.  The fake transport is ROS-free;
no ROS graph or robot is contacted.  A successful service callback is a
callback acknowledgement, not sensed zero velocity and not a physical
emergency stop.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: The BaseRobotServices constructor advertises the relative "base/stop"
#: service and binds it to BaseRobotServices::Stop.
_STOP_REF = "kortex_driver/src/generated/robot/base_services.cpp:154"

#: The generated interface header includes the generated Stop service message.
_STOP_TYPE_REF = "kortex_driver/include/kortex_driver/generated/interfaces/base_services_interface.h:106"

#: The constructor advertises the relative "base/apply_emergency_stop"
#: service and binds it to BaseRobotServices::ApplyEmergencyStop.
_APPLY_EMERGENCY_STOP_REF = "kortex_driver/src/generated/robot/base_services.cpp:169"

#: The generated interface header includes the generated ApplyEmergencyStop
#: service message.
_APPLY_EMERGENCY_STOP_TYPE_REF = (
    "kortex_driver/include/kortex_driver/generated/interfaces/base_services_interface.h:121"
)

#: Both callbacks take and return the generated service messages; their .srv
#: files declare Empty input and Empty output.
_STOP = {
    "service": "/my_gen3/base/stop",
    "type": "kortex_driver/Stop",
    "source_name": "base/stop",
    "source_ref": _STOP_REF,
    "type_ref": _STOP_TYPE_REF,
    "request": {"input": {}},
    "success": {"path": "output", "equals": {}},
}

_APPLY_EMERGENCY_STOP = {
    "service": "/my_gen3/base/apply_emergency_stop",
    "type": "kortex_driver/ApplyEmergencyStop",
    "source_name": "base/apply_emergency_stop",
    "source_ref": _APPLY_EMERGENCY_STOP_REF,
    "type_ref": _APPLY_EMERGENCY_STOP_TYPE_REF,
    "request": {"input": {}},
    "success": {"path": "output", "equals": {}},
}

_ACKNOWLEDGED = Field(
    "boolean",
    description="True when the upstream ROS service callback returned true; this is not a stopped-state measurement",
)


class KortexRos1Stop(RosDriver):
    device_id = "kortex_arm"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeKortexRos1Stop"}
    tags = ["ros", "ros1", "kinova", "kortex", "stop", "emergency-stop"]
    display_name = "Kinova Kortex ROS 1 base stop services"
    vendor = "Kinovarobotics"
    facts = [
        Fact("BaseRobotServices advertises the relative ROS 1 service \"base/stop\" and binds it to "
             "BaseRobotServices::Stop.",
             source="upstream_code", ref=_STOP_REF),
        Fact("BaseRobotServices advertises the relative ROS 1 service \"base/apply_emergency_stop\" and binds it "
             "to BaseRobotServices::ApplyEmergencyStop.",
             source="upstream_code", ref=_APPLY_EMERGENCY_STOP_REF),
        Fact("BaseRobotServices::Stop declares kortex_driver::Stop::Request and kortex_driver::Stop::Response "
             "parameters in the service callback signature.",
             source="upstream_code", ref="kortex_driver/src/generated/robot/base_services.cpp:2651"),
        Fact("BaseRobotServices::Stop calls m_base->Stop(m_current_device_id, m_api_options) and leaves the "
             "response message untouched.",
             source="upstream_code", ref="kortex_driver/src/generated/robot/base_services.cpp:2651-2679"),
        Fact("BaseRobotServices::Stop catches Kinova::Api::KDetailedException and std::runtime_error, returns "
             "false in both handlers, and returns true after a successful call.",
             source="upstream_code", ref="kortex_driver/src/generated/robot/base_services.cpp:2661-2678"),
        Fact("BaseRobotServices::ApplyEmergencyStop declares kortex_driver::ApplyEmergencyStop::Request and "
             "kortex_driver::ApplyEmergencyStop::Response parameters in the service callback signature.",
             source="upstream_code", ref="kortex_driver/src/generated/robot/base_services.cpp:3136"),
        Fact("BaseRobotServices::ApplyEmergencyStop calls "
             "m_base->ApplyEmergencyStop(m_current_device_id, m_api_options) and leaves the response message "
             "untouched.",
             source="upstream_code", ref="kortex_driver/src/generated/robot/base_services.cpp:3136-3164"),
        Fact("BaseRobotServices::ApplyEmergencyStop catches Kinova::Api::KDetailedException and "
             "std::runtime_error, returns false in both handlers, and returns true after a successful call.",
             source="upstream_code", ref="kortex_driver/src/generated/robot/base_services.cpp:3146-3163"),
        Fact("Stop.srv declares \"Empty input\" before the request separator and \"Empty output\" after it, so "
             "the generated request and response nest an Empty message under input and output.",
             source="upstream_code", ref="kortex_driver/srv/generated/base/Stop.srv:1-3"),
        Fact("ApplyEmergencyStop.srv declares \"Empty input\" before the request separator and \"Empty output\" "
             "after it, so the generated request and response nest an Empty message under input and output.",
             source="upstream_code", ref="kortex_driver/srv/generated/base/ApplyEmergencyStop.srv:1-3"),
        Fact("The generated interface header includes \"kortex_driver/Stop.h\", the generated header of the Stop "
             "service type.",
             source="upstream_code", ref=_STOP_TYPE_REF),
        Fact("The generated interface header includes \"kortex_driver/ApplyEmergencyStop.h\", the generated "
             "header of the ApplyEmergencyStop service type.",
             source="upstream_code", ref=_APPLY_EMERGENCY_STOP_TYPE_REF),
    ]
    safe_state = (
        "The upstream ApplyEmergencyStop callback returned true; this is service acknowledgement only, not "
        "sensed zero velocity, not a physical emergency stop and not power isolation."
    )

    # The registrations use relative names. The configured "/my_gen3" prefix is
    # an explicit deployment namespace: the operator must launch the Kortex
    # node in that namespace or expose the same service names under it.
    commands = {
        "x-cap.kinovarobotics.stop.v1": dict(
            _STOP, result={"acknowledged": {"value": True}}
        ),
        "x-cap.kinovarobotics.apply_emergency_stop.v1": dict(
            _APPLY_EMERGENCY_STOP, result={"acknowledged": {"value": True}}
        ),
    }
    actions = {
        "x-cap.kinovarobotics.stop.v1": Action(
            name="stop",
            verb="invoke",
            description=(
                "Invoke the acknowledged Kortex base/stop service; this reports the ROS callback result only, "
                "not a measured stopping position or zero velocity"
            ),
            output={"acknowledged": _ACKNOWLEDGED},
        ),
        "x-cap.kinovarobotics.apply_emergency_stop.v1": Action(
            name="apply_emergency_stop",
            verb="invoke",
            safe_state=True,
            description=(
                "Invoke the acknowledged Kortex base/apply_emergency_stop service; this reports the ROS callback "
                "result only and does not claim a physical emergency stop"
            ),
            output={"acknowledged": _ACKNOWLEDGED},
        ),
    }
    # The native e-stop is the upstream apply_emergency_stop service. The
    # safe-state permission comes from Action(safe_state=True); the runtime
    # latches before the e-stop path. No hardware physical stop is claimed.
    safety_bindings = {"estop": _APPLY_EMERGENCY_STOP}
