"""OpenMHS rosbridge driver for the ArduPilot Copter missions of this repository.

The upstream repository is a ROS 2 / MAVROS integration project, not a C++
or Python device node: ``scripts/missions/mission_simple.py`` is a client that
binds the MAVROS topics and services, and the launch files start the external
``mavros_node``.  This package is therefore a configuration-only
:class:`RosDriver` over rosbridge.  It exposes the client-side contracts the
clone actually uses: the MAVROS state and local-position topics, the GUIDED
mode request, arming, takeoff, a single position-setpoint publication, RTL and
LAND.

The position setpoint is a publication, so its receipt reports transmission
only; the upstream mission script publishes at 20 Hz for a time window and
never verifies the final position.  One rosbridge publish is not a completed
move. LAND is an ordinary mode request, never an achieved safety transition.
Its ``mode_sent`` predicate cannot prove LAND state, touchdown or stopped rotors.
The documented RC procedure does not establish a software stop/settlement contract.  No
ROS graph, MAVROS node, flight controller or hardware is contacted here.

Every endpoint, type and fact cites the pinned clone at
595f9916efe8efb8a08667f35fa515873b2f8450.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# The mission script declares all MAVROS message and service imports in one
# block of lines; the citations below span the import and the use site.
_STATE_REF = "scripts/missions/mission_simple.py:20-44"
_POSE_REF = "scripts/missions/mission_simple.py:20-51"
_SETPOINT_REF = "scripts/missions/mission_simple.py:20-58"
_ARM_REF = "scripts/missions/mission_simple.py:20-61"
_MODE_REF = "scripts/missions/mission_simple.py:20-62"
_TAKEOFF_REF = "scripts/missions/mission_simple.py:20-63"
_LAND_REF = "docs/guides/SITL_SETUP.md:114-116"

_POSITION_REASON = (
    "the clone gives 10 m demo targets, not a flight envelope, and states no safe "
    "workspace or altitude bound; the site supplies the bound"
)
_ALTITUDE_REASON = (
    "the clone's 10 m takeoff target is a demo value, not a safe altitude envelope; "
    "the site supplies the bound"
)

_STATE = {
    "topic": "/mavros/state",
    "type": "mavros_msgs/msg/State",
    "source_name": "/mavros/state",
    "source_ref": _STATE_REF,
}
_POSE = {
    "topic": "/mavros/local_position/pose",
    "type": "geometry_msgs/msg/PoseStamped",
    "source_name": "/mavros/local_position/pose",
    "source_ref": _POSE_REF,
}
_SET_MODE = {
    "service": "/mavros/set_mode",
    "type": "mavros_msgs/srv/SetMode",
    "source_name": "/mavros/set_mode",
    "source_ref": _MODE_REF,
    "success": {"path": "mode_sent", "equals": True},
    "result": {"map": {"mode_sent": "mode_sent"}},
}
_ARM = {
    "service": "/mavros/cmd/arming",
    "type": "mavros_msgs/srv/CommandBool",
    "source_name": "/mavros/cmd/arming",
    "source_ref": _ARM_REF,
    "request": {"value": True},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"success": "success"}},
}
_TAKEOFF = {
    "service": "/mavros/cmd/takeoff",
    "type": "mavros_msgs/srv/CommandTOL",
    "source_name": "/mavros/cmd/takeoff",
    "source_ref": _TAKEOFF_REF,
    "args": {"altitude": {"from": "input.altitude"}},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"success": "success"}},
}
_LAND = {
    "service": "/mavros/set_mode",
    "type": "mavros_msgs/srv/SetMode",
    "source_name": "/mavros/set_mode",
    "source_ref": _LAND_REF,
    "request": {"custom_mode": "LAND"},
    "success": {"path": "mode_sent", "equals": True},
    "result": {"map": {"mode_sent": "mode_sent"}},
}

_POSITION = Field(
    "object",
    description="Local position of the vehicle in the map frame",
    properties={
        "x": Field("number", unit="m", description="Map-frame x coordinate; no north/east axis convention is inferred"),
        "y": Field("number", unit="m", description="Map-frame y coordinate; no north/east axis convention is inferred"),
        "z": Field("number", unit="m", description="Altitude above the local origin"),
    },
)


class Ros2ArdupilotSitlHardware(RosDriver):
    device_id = "ardupilot_copter"
    device_kind = "robot.mobile_base"
    mode = "hardware"
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeRos2ArdupilotSitlHardware"}
    tags = ["ros", "ros2", "ardupilot", "mavros", "copter", "sitl", "flight"]
    display_name = "ArduPilot Copter over MAVROS"
    vendor = "ArduPilot"
    model = "ArduCopter 4.x"
    facts = [
        Fact("The mission script imports mavros_msgs State, CommandBool, SetMode and CommandTOL and "
             "geometry_msgs PoseStamped.", source="upstream_code",
             ref="scripts/missions/mission_simple.py:20-22"),
        Fact("The mission script subscribes /mavros/state as State and /mavros/local_position/pose as "
             "PoseStamped with BEST_EFFORT, VOLATILE, KEEP_LAST depth 10.",
             source="upstream_code", ref="scripts/missions/mission_simple.py:30-51"),
        Fact("The mission script publishes /mavros/setpoint_position/local as PoseStamped at 20 Hz for the "
             "requested duration and then returns True without checking the final position.",
             source="upstream_code", ref="scripts/missions/mission_simple.py:147-176"),
        Fact("The mission script creates clients for /mavros/cmd/arming CommandBool, /mavros/set_mode "
             "SetMode and /mavros/cmd/takeoff CommandTOL.",
             source="upstream_code", ref="scripts/missions/mission_simple.py:60-63"),
        Fact("set_mode maps the mode string to custom_mode and treats the SetMode mode_sent response as "
             "success.", source="upstream_code", ref="scripts/missions/mission_simple.py:82-96"),
        Fact("arm sends value = true and checks the CommandBool success response.",
             source="upstream_code", ref="scripts/missions/mission_simple.py:98-112"),
        Fact("takeoff sets altitude and checks the CommandTOL success response, logging only that the "
             "command was sent.", source="upstream_code",
             ref="scripts/missions/mission_simple.py:114-129"),
        Fact("Altitude attainment is a separate observation loop over /mavros/local_position/pose with a "
             "0.3 m default tolerance.", source="upstream_code",
             ref="scripts/missions/mission_simple.py:131-145"),
        Fact("The demo mission sets GUIDED, arms, requests 10.0 m takeoff, moves to (10.0, 0.0, 10.0) for "
             "15 s and requests RTL; these are demo targets, not safe envelopes.",
             source="upstream_code", ref="scripts/missions/mission_simple.py:192-227"),
        Fact("The SITL guide documents a LAND request on /mavros/set_mode with mavros_msgs/srv/SetMode and "
             "custom_mode LAND.", source="vendor_doc", ref=_LAND_REF),
        Fact("The hardware guide's kill switch is an RC transmitter procedure: switch to manual mode, "
             "disarm via RC switch and emergency land.", source="vendor_doc",
             ref="docs/guides/REAL_HARDWARE_SETUP.md:454-459"),
        Fact("The hardware guide requires propellers to be removed and the drone secured for bench "
             "testing, because motors can spin when armed.", source="vendor_doc",
             ref="docs/guides/REAL_HARDWARE_SETUP.md:10-22"),
        Fact("The hardware guide's in-flight emergency procedure is manual RC control (STABILIZE) and a "
             "manual landing, not a ROS stop service.", source="vendor_doc",
             ref="docs/guides/REAL_HARDWARE_SETUP.md:440-452"),
        Fact("The hardware guide states that the same mission scripts used in SITL work on real "
             "hardware.", source="vendor_doc", ref="docs/guides/REAL_HARDWARE_SETUP.md:387"),
        Fact("The SITL MAVROS configuration sets the setpoint_position frame to map and the "
             "setpoint_velocity MAV frame to LOCAL_NED, and allowlists the setpoint_position and "
             "setpoint_velocity plugins.", source="upstream_code",
             ref="src/simtofly_mavros_sitl/config/mavros_params.yaml:52-88"),
        Fact("The real-hardware launch defaults fcu_url to /dev/ttyACM0:921600 and starts the external "
             "mavros_node with target system/component id 1.",
             source="upstream_code", ref="src/simtofly_mavros_real/launch/cube_orange.launch.py:32-81"),
        Fact("The SITL launch defaults fcu_url to udp://:14550@ and starts the external mavros_node with "
             "target system/component id 1.", source="upstream_code",
             ref="src/simtofly_mavros_sitl/launch/ardupilot_sitl.launch.py:20-69"),
    ]
    # Flight-specific stop, ownership retirement and native transport remain
    # unresolved. No ordinary mode request is granted safety permission.

    # The runtime reads these fields before and after each action.  They are
    # explicit observations of the two topics the mission script subscribes.
    parameters = {
        "connected": Field("boolean", description="MAVROS reports a flight-controller heartbeat"),
        "armed": Field("boolean", description="Flight controller armed state reported by MAVROS"),
        "mode": Field("string", description="Flight mode reported by MAVROS"),
        "position": _POSITION,
    }
    reads = {
        "connected": dict(_STATE, path="connected"),
        "armed": dict(_STATE, path="armed"),
        "mode": dict(_STATE, path="mode"),
        "position": dict(_POSE, path="pose.position"),
    }
    commands = {
        # The mission script's observation topics; each is an explicit
        # extension read capability, not only an automatic resource snapshot.
        "x-cap.sidharthmohannair.state.v1": dict(
            _STATE, operation="subscribe", path="$",
            result={"map": {"connected": "connected", "armed": "armed", "mode": "mode"}},
        ),
        "x-cap.sidharthmohannair.pose.v1": dict(
            _POSE, operation="subscribe", path="pose.position",
            result={"map": {"position": "$"}},
        ),
        # Fixed mode request used by the mission script before takeoff.
        "x-cap.sidharthmohannair.guided.v1": dict(
            _SET_MODE, request={"custom_mode": "GUIDED"},
        ),
        # Fixed arm request used by the mission script.
        "x-cap.sidharthmohannair.arm.v1": _ARM,
        # Takeoff altitude is an operator envelope; the clone's 10 m is a demo.
        "x-cap.sidharthmohannair.takeoff.v1": _TAKEOFF,
        # One transmission of a position setpoint.  The upstream streams at
        # 20 Hz; one rosbridge publish is not a completed move.
        "x-cap.sidharthmohannair.setpoint_position.v1": {
            "topic": "/mavros/setpoint_position/local",
            "type": "geometry_msgs/msg/PoseStamped",
            "source_name": "/mavros/setpoint_position/local",
            "source_ref": _SETPOINT_REF,
            "operation": "publish",
            "message": {
                "header": {"frame_id": "map", "stamp": {"sec": 0, "nanosec": 0}},
                "pose": {"orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}},
            },
            "args": {
                "pose.position.x": {"from": "input.x"},
                "pose.position.y": {"from": "input.y"},
                "pose.position.z": {"from": "input.z"},
            },
            "result": {"map": {"published": "published", "confirmed": "confirmed"}},
        },
        # Fixed return-to-launch request used at the end of the demo mission.
        "x-cap.sidharthmohannair.rtl.v1": dict(
            _SET_MODE, request={"custom_mode": "RTL"},
        ),
        # Fixed LAND request: an ordinary command, not a safe-state action.
        "x-cap.sidharthmohannair.land.v1": _LAND,
    }
    actions = {
        "x-cap.sidharthmohannair.state.v1": Action(
            name="read_state", verb="read",
            description="Read one /mavros/state sample: connection, armed and flight mode",
            output={
                "connected": Field("boolean", description="MAVROS reports a flight-controller heartbeat"),
                "armed": Field("boolean", description="Flight controller armed state"),
                "mode": Field("string", description="Flight mode reported by MAVROS"),
            },
        ),
        "x-cap.sidharthmohannair.pose.v1": Action(
            name="read_pose", verb="read",
            description="Read the local position from /mavros/local_position/pose in the map frame",
            output={"position": _POSITION},
        ),
        "x-cap.sidharthmohannair.guided.v1": Action(
            name="set_guided",
            description="Request GUIDED mode on /mavros/set_mode; mode_sent is the request acknowledgement",
            output={"mode_sent": Field("boolean",
                                       description="True when MAVROS reports the mode request was sent")},
        ),
        "x-cap.sidharthmohannair.arm.v1": Action(
            name="arm",
            description="Request arming with value = true on /mavros/cmd/arming",
            output={"success": Field("boolean",
                                     description="True when the flight controller accepted the arm request")},
        ),
        "x-cap.sidharthmohannair.takeoff.v1": Action(
            name="takeoff",
            description="Request takeoff to an operator-bounded altitude on /mavros/cmd/takeoff",
            input={"altitude": Field("number", unit="m", description="Requested takeoff altitude",
                                     limit=Limit.operator_required(_ALTITUDE_REASON))},
            output={"success": Field("boolean",
                                     description="True when the flight controller accepted the takeoff request")},
        ),
        "x-cap.sidharthmohannair.setpoint_position.v1": Action(
            name="publish_position_setpoint",
            description="Publish one local position setpoint; the receipt is transmission only, not a "
                        "completed move or final-position verification",
            input={
                "x": Field("number", unit="m", description="Map-frame x target",
                           limit=Limit.operator_required(_POSITION_REASON)),
                "y": Field("number", unit="m", description="Map-frame y target",
                           limit=Limit.operator_required(_POSITION_REASON)),
                "z": Field("number", unit="m", description="Altitude target",
                           limit=Limit.operator_required(_POSITION_REASON)),
            },
            output={
                "published": Field("boolean", description="True when rosbridge transmitted the message"),
                "confirmed": Field("boolean",
                                   description="False: a publication is transmission, not goal attainment"),
            },
        ),
        "x-cap.sidharthmohannair.rtl.v1": Action(
            name="return_to_launch",
            description="Request RTL mode on /mavros/set_mode; this is a flight-mode request, not a stop",
            output={"mode_sent": Field("boolean",
                                       description="True when MAVROS reports the mode request was sent")},
        ),
        "x-cap.sidharthmohannair.land.v1": Action(
            name="land",
            description="Request LAND mode on /mavros/set_mode as an ordinary command; it does not "
                        "prove touchdown or stopped rotors",
            output={"mode_sent": Field("boolean",
                                       description="True when MAVROS reports the mode request was sent")},
        ),
    }
    # No source-supported settled emergency stop is declared.
    safety_bindings = {}
