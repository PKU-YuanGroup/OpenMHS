"""OpenMHS rosbridge driver for the PX4 SITL ROS example (simulation environment).

The pinned repository is a ROS 1 PX4 SITL/Gazebo example set. Its ``offb`` and
``offb_velocity`` C++ nodes talk to the external MAVROS/PX4 graph and the
``trajectory`` packages are launch/world scaffolding. This package is a
configuration-only :class:`RosDriver` over rosbridge; it declares no Python
native class, does not launch Gazebo or PX4, and neither imports nor runs the
upstream nodes. The operator runs PX4 SITL with MAVROS (the px4 package's
``mavros_posix_sitl.launch``, which is outside the clone) and rosbridge
separately, and not the clone's ``offb.launch`` or ``offb_velocity.launch``:
they also start ``offb_node``, which streams its own hover setpoint and
re-requests OFFBOARD and arming every 5 s, or the velocity node's own arm,
takeoff, velocity and land sequence, both competing with this driver.

The exposed surface is the MAVROS contract the clone's nodes use:

* ``mavros/state`` (``mavros_msgs/State``) and ``/mavros/altitude``
  (``mavros_msgs/Altitude``) as the resource state;
* one position setpoint publication on ``mavros/setpoint_position/local`` and
  the body and local-NED velocity publications on ``mavros/setpoint_raw/local``;
* the acknowledged ``mavros/set_mode`` (fixed OFFBOARD), ``/mavros/cmd/arming``
  (fixed true) and ``/mavros/cmd/land`` (fixed empty) services.

The clone's only landing path is the ``/mavros/cmd/land`` ``CommandTOL``
request. Its ``success`` flag acknowledges a LAND request; it is not a
touchdown confirmation, it does not disarm the vehicle, it does not stop the
simulator and it does not stop other ROS clients (``offb_node`` would request
OFFBOARD again within 5 s). After the land call the velocity node only sleeps
for five seconds and then returns; the clone's stop path contains no sensed
landed-state check and no disarm step. A LAND request alone is not a stop
(model review of 2026-11-04). This simulated package therefore declares a
sensed-confirmation stop (SAFE-049, the user's decision of 2026-11-05,
simulated devices only): the e-stop sends ``/mavros/cmd/land`` and a
``/mavros/cmd/arming`` disarm request and is achieved only when
``/mavros/state`` reports connected and disarmed and ``/mavros/altitude``
stays still in three consecutive fresh samples within the bound; otherwise it
fails ``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the latch held and is retried
in the background. ``/mavros/cmd/land`` also stays an ordinary command.
MAVROS can drive a real PX4 over a serial or UDP link: that path is out of
scope and never served.

Every endpoint, type and fact cites the pinned clone at
60dc45513f635ca9a53a0bf1883ea76c25a0eb3f. The fake transport is ROS-free and
all of its state values are placeholders.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references (paths are relative to the clone root)
# ---------------------------------------------------------------------------

#: offb_node subscribes the relative mavros/state topic with mavros_msgs/State.
_STATE_REF = "src/offb/src/offb_node.cpp:23-24"
_STATE_TYPE_REF = "src/offb/src/offb_node.cpp:11"

#: offb_node advertises geometry_msgs/PoseStamped on mavros/setpoint_position/local.
_POSITION_PUB_REF = "src/offb/src/offb_node.cpp:25-26"
_POSITION_TYPE_REF = "src/offb/src/offb_node.cpp:8"

#: The shipped offb pose (declared, three position fields set, then published
#: unchanged) and its publishing loop, which also re-requests OFFBOARD and
#: arming every 5 s.
_POSITION_FIELDS_REF = "src/offb/src/offb_node.cpp:41-80"
_POSITION_LOOP_REF = "src/offb/src/offb_node.cpp:32-33"
_POSITION_SEND_REF = "src/offb/src/offb_node.cpp:46-51"
_POSITION_PUBLISH_REF = "src/offb/src/offb_node.cpp:53-84"
_OFFB_CLIENTS_REF = "src/offb/src/offb_node.cpp:27-30"

#: The shipped launch files: each includes px4's mavros_posix_sitl.launch and
#: starts one of the clone's nodes.
_OFFB_LAUNCH_REF = "src/offb/launch/offb.launch:3-5"
_VELOCITY_LAUNCH_REF = "src/offb_velocity/launch/offb_velocity.launch:3-5"

#: The velocity example logs "NED: Move towards South" before vy -2 and
#: "NED: Go Up" before vz 2: the ROS-side signs MAVROS receives.
_NED_SIGN_REF = "src/offb_velocity/src/offb_velocity_node.cpp:145-152"
_BODY_SIGN_REF = "src/offb_velocity/src/offb_velocity_node.cpp:116-120"

#: Drone constructor: PositionTarget publisher and the three service clients.
_VELOCITY_PUB_REF = "src/offb_velocity/src/drone_offboard.cpp:11"
_TAKEOFF_CLIENT_REF = "src/offb_velocity/src/drone_offboard.cpp:12"
_MODE_CLIENT_REF = "src/offb_velocity/src/drone_offboard.cpp:13"
_LAND_CLIENT_REF = "src/offb_velocity/src/drone_offboard.cpp:14"
_VELOCITY_TYPE_REF = "src/offb_velocity/src/drone_offboard.cpp:5"

#: The velocity helpers, the degree-to-radian conversion and the land service.
_BODY_HELPER_REF = "src/offb_velocity/src/drone_offboard.cpp:128-147"
_NED_HELPER_REF = "src/offb_velocity/src/drone_offboard.cpp:149-167"
_TO_RAD_REF = "src/offb_velocity/src/drone_offboard.cpp:123-126"
_LAND_CALL_REF = "src/offb_velocity/src/drone_offboard.cpp:57-71"
_ARM_CALL_REF = "src/offb_velocity/src/drone_offboard.cpp:29-35"
_MODE_CALL_REF = "src/offb_velocity/src/drone_offboard.cpp:73-80"
_ARMING_CLIENT_REF = "src/offb_velocity/src/drone_offboard.cpp:29"
_ARMING_TYPE_REF = "src/offb_velocity/src/drone_offboard.cpp:2"
_LAND_TYPE_REF = "src/offb_velocity/src/drone_offboard.cpp:3"
#: Consumer lines of the sensed fields: offb_node reads connected and armed from mavros/state, the Drone
#: altitude callback reads amsl from /mavros/altitude.
_CONNECTED_READ_REF = "src/offb/src/offb_node.cpp:36"
_ARMED_READ_REF = "src/offb/src/offb_node.cpp:70"
_AMSL_READ_REF = "src/offb_velocity/src/drone_offboard.cpp:120"

#: The altitude subscription and its type include; the wait loop follows it.
_ALTITUDE_REF = "src/offb_velocity/src/drone_offboard.cpp:107-108"
_ALTITUDE_WAIT_REF = "src/offb_velocity/src/drone_offboard.cpp:105-114"
_ALTITUDE_TYPE_REF = "src/offb_velocity/include/drone_offboard.h:5"

#: The velocity node's overall arm -> takeoff -> velocity -> land flow.
_VELOCITY_FLOW_REF = "src/offb_velocity/src/offb_velocity_node.cpp:16-66"

#: After the land service call the node only sleeps and shuts down.
_POST_LAND_REF = "src/offb_velocity/src/offb_velocity_node.cpp:59-70"

# ---------------------------------------------------------------------------
# Units and limits
# ---------------------------------------------------------------------------

#: The clone states no numeric envelope for any setpoint component: the
#: example literals (2 m, 5 m/s, 60 degrees and so on) are demonstration
#: values, not device bounds. The operator supplies the deployed envelope.
_POSITION_X = Limit.operator_required(
    "the pinned offb example sets a demonstration position but states no numeric workspace bound for "
    "mavros/setpoint_position/local x; the operator supplies the deployed envelope")
_POSITION_Y = Limit.operator_required(
    "the pinned offb example sets a demonstration position but states no numeric workspace bound for "
    "mavros/setpoint_position/local y; the operator supplies the deployed envelope")
_POSITION_Z = Limit.operator_required(
    "the pinned offb example sets a demonstration position but states no numeric workspace bound for "
    "mavros/setpoint_position/local z; the operator supplies the deployed envelope")
_VELOCITY_X = Limit.operator_required(
    "the pinned velocity example contains demonstration velocities but states no numeric bound for "
    "mavros/setpoint_raw/local velocity x; the operator supplies the deployed envelope")
_VELOCITY_Y = Limit.operator_required(
    "the pinned velocity example contains demonstration velocities but states no numeric bound for "
    "mavros/setpoint_raw/local velocity y; the operator supplies the deployed envelope")
_VELOCITY_Z = Limit.operator_required(
    "the pinned velocity example contains demonstration velocities but states no numeric bound for "
    "mavros/setpoint_raw/local velocity z; the operator supplies the deployed envelope")
_YAW_RATE = Limit.operator_required(
    "the pinned body helper converts a demonstration yaw rate from degrees to radians but states no numeric "
    "bound for the message yaw_rate; the operator supplies the deployed envelope")
_YAW = Limit.operator_required(
    "the pinned NED helper converts a demonstration yaw from degrees to radians but states no numeric bound "
    "for the message yaw; the operator supplies the deployed envelope")

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_STATE_OUTPUT = {
    "connected": Field("boolean", description="mavros_msgs/State.connected as last published"),
    "armed": Field("boolean", description="mavros_msgs/State.armed as last published"),
    "mode": Field("string", description="mavros_msgs/State.mode as last published"),
}

_ALTITUDE_OUTPUT = {
    "amsl": Field("number", unit="m", description="mavros_msgs/Altitude.amsl as last published"),
}

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the message to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication has no execution acknowledgement"),
}

_ARM_OUTPUT = {
    "success": Field("boolean", description="The mavros_msgs/CommandBool response success flag"),
}

_MODE_OUTPUT = {
    "mode_sent": Field("boolean", description="The mavros_msgs/SetMode response mode_sent flag"),
}

_LAND_OUTPUT = {
    "success": Field("boolean", description="The mavros_msgs/CommandTOL response success flag"),
}

# ---------------------------------------------------------------------------
# Fixed messages
# ---------------------------------------------------------------------------

#: offb_node's own hover pose: position (0, 0, 2) and default header,
#: orientation and frame_id (src/offb/src/offb_node.cpp:41-80). The all-zero
#: orientation is the clone's default-constructed quaternion, not a unit one.
_HOVER_MESSAGE = {
    "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": ""},
    "pose": {
        "position": {"x": 0.0, "y": 0.0, "z": 2.0},
        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0},
    },
}

#: PositionTarget field values the body helper derives from the MAVLink
#: constants: FRAME_BODY_NED (8) and the ignore/force mask 1991.
_BODY_MESSAGE = {
    "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": ""},
    "coordinate_frame": 8,
    "type_mask": 1991,
    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
    "velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
    "acceleration_or_force": {"x": 0.0, "y": 0.0, "z": 0.0},
    "yaw": 0.0,
    "yaw_rate": 0.0,
}

#: PositionTarget field values the NED helper derives: FRAME_LOCAL_NED (1)
#: and the ignore/force mask 3015.
_NED_MESSAGE = {
    "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": ""},
    "coordinate_frame": 1,
    "type_mask": 3015,
    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
    "velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
    "acceleration_or_force": {"x": 0.0, "y": 0.0, "z": 0.0},
    "yaw": 0.0,
    "yaw_rate": 0.0,
}

# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------

_STATE = {
    "topic": "/mavros/state",
    "type": "mavros_msgs/State",
    "source_name": "mavros/state",
    "source_ref": _STATE_REF,
    "type_ref": _STATE_TYPE_REF,
    "operation": "subscribe",
    "result": {"map": {"connected": "output.connected", "armed": "output.armed", "mode": "output.mode"}},
}

_ALTITUDE = {
    "topic": "/mavros/altitude",
    "type": "mavros_msgs/Altitude",
    "source_ref": _ALTITUDE_REF,
    "type_ref": _ALTITUDE_TYPE_REF,
    "operation": "subscribe",
    "result": {"map": {"amsl": "output.amsl"}},
}

_HOVER = {
    "topic": "/mavros/setpoint_position/local",
    "type": "geometry_msgs/PoseStamped",
    "source_name": "mavros/setpoint_position/local",
    "source_ref": _POSITION_PUB_REF,
    "type_ref": _POSITION_TYPE_REF,
    "operation": "publish",
    "message": _HOVER_MESSAGE,
    "description": "Publish the offb example's fixed hover PoseStamped (position 0, 0, 2); transmission only",
}

_POSITION_SETPOINT = {
    "topic": "/mavros/setpoint_position/local",
    "type": "geometry_msgs/PoseStamped",
    "source_name": "mavros/setpoint_position/local",
    "source_ref": _POSITION_PUB_REF,
    "type_ref": _POSITION_TYPE_REF,
    "operation": "publish",
    "message": _HOVER_MESSAGE,
    "args": {
        "pose.position.x": {"from": "input.x"},
        "pose.position.y": {"from": "input.y"},
        "pose.position.z": {"from": "input.z"},
    },
    "description": "Publish one position setpoint on mavros/setpoint_position/local; transmission only",
}

_VELOCITY_BODY = {
    "topic": "/mavros/setpoint_raw/local",
    "type": "mavros_msgs/PositionTarget",
    "source_name": "mavros/setpoint_raw/local",
    "source_ref": _VELOCITY_PUB_REF,
    "type_ref": _VELOCITY_TYPE_REF,
    "operation": "publish",
    "message": _BODY_MESSAGE,
    "args": {
        "velocity.x": {"from": "input.vx"},
        "velocity.y": {"from": "input.vy"},
        "velocity.z": {"from": "input.vz"},
        "yaw_rate": {"from": "input.yaw_rate"},
    },
    "description": "Publish one body-frame velocity PositionTarget; transmission only",
}

_VELOCITY_NED = {
    "topic": "/mavros/setpoint_raw/local",
    "type": "mavros_msgs/PositionTarget",
    "source_name": "mavros/setpoint_raw/local",
    "source_ref": _VELOCITY_PUB_REF,
    "type_ref": _VELOCITY_TYPE_REF,
    "operation": "publish",
    "message": _NED_MESSAGE,
    "args": {
        "velocity.x": {"from": "input.vx"},
        "velocity.y": {"from": "input.vy"},
        "velocity.z": {"from": "input.vz"},
        "yaw": {"from": "input.yaw"},
    },
    "description": "Publish one local-NED velocity PositionTarget; transmission only",
}

_ARM = {
    "service": "/mavros/cmd/arming",
    "type": "mavros_msgs/CommandBool",
    "source_ref": _ARMING_CLIENT_REF,
    "request": {"value": True},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"success": "success"}},
    "description": "Fixed CommandBool value=true arming request; success is the service response flag",
}

_OFFBOARD_MODE = {
    "service": "/mavros/set_mode",
    "type": "mavros_msgs/SetMode",
    "source_name": "mavros/set_mode",
    "source_ref": _MODE_CLIENT_REF,
    "request": {"custom_mode": "OFFBOARD"},
    "success": {"path": "mode_sent", "equals": True},
    "result": {"map": {"mode_sent": "mode_sent"}},
    "description": "Fixed SetMode custom_mode=OFFBOARD request; mode_sent is a request acknowledgement",
}

_LAND = {
    "service": "/mavros/cmd/land",
    "type": "mavros_msgs/CommandTOL",
    "source_ref": _LAND_CLIENT_REF,
    "request": {},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"success": "success"}},
    "description": "Fixed CommandTOL landing request; success is a request acknowledgement, not touchdown or disarm",
}


#: Sensed-confirmation stop (SAFE-049): the request steps prove nothing by themselves.  The CommandTOL land
#: request is the clone's landing path (drone_offboard.cpp:57-71); the disarm request (CommandBool value false on
#: the clone's arming endpoint, drone_offboard.cpp:29) is refused by PX4 in the air and repeats harmlessly on the
#: ground; the background retry sends both again.  The confirmation reads MAVROS's stamped state and altitude
#: (filled by MAVROS outside the clone; the clone consumes the cited fields).  The at-rest altitude bound is
#: operator_required: the clone states none.  The client bounds are fake-scale; a live deployment sets them in its
#: estop_confirmation.
_SENSED_STOP = {
    "request": [
        {"service": "/mavros/cmd/land", "type": "mavros_msgs/CommandTOL", "source_ref": _LAND_CLIENT_REF,
         "type_ref": _LAND_TYPE_REF, "request": {}, "success": {"path": "success", "equals": True},
         "timeout_ms": 1000, "description": "the clone's CommandTOL land request (default-constructed request)"},
        {"service": "/mavros/cmd/arming", "type": "mavros_msgs/CommandBool", "source_ref": _ARMING_CLIENT_REF,
         "type_ref": _ARMING_TYPE_REF, "request": {"value": False}, "success": {"path": "success", "equals": True},
         "timeout_ms": 1000, "description": "a disarm request (refused in the air; succeeds after touchdown)"},
    ],
    "sources": {
        "state": {"topic": "/mavros/state", "type": "mavros_msgs/State", "source_name": "mavros/state",
                  "source_ref": _STATE_REF, "type_ref": _STATE_TYPE_REF,
                  "fill_refs": {"connected": _CONNECTED_READ_REF, "armed": _ARMED_READ_REF}},
        "altitude": {"topic": "/mavros/altitude", "type": "mavros_msgs/Altitude", "source_ref": _ALTITUDE_REF,
                     "type_ref": _ALTITUDE_TYPE_REF, "fill_refs": {"amsl": _AMSL_READ_REF}},
    },
    "predicate": [
        {"source": "state", "path": "connected", "equals": True},
        {"source": "state", "path": "armed", "equals": False},
        {"source": "altitude", "path": "amsl", "name": "altitude_rest", "unit": "m",
         "span_max": Limit.operator_required(
             "the clone states no at-rest altitude bound; the operator supplies the largest AMSL change over the "
             "confirmation window that counts as landed and still")},
    ],
    "consecutive": 3,
    "min_span_ms": 200,
    "max_gap_ms": 500,
    "confirm_within_ms": 1500,
    "description": "landing requested; connected and disarmed on /mavros/state and the AMSL altitude still, "
                   "sensed in three consecutive fresh samples within the bound",
}


class Px4Sitl(RosDriver):
    device_id = "px4-sitl"
    device_kind = "world.sim"
    mode = "simulated"
    #: A command surface that flies a simulated multirotor is a mobile-base
    #: motion source even without attached hardware; the card floor is R0.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakePx4Sitl"}
    tags = ["ros", "ros1", "px4", "sitl", "gazebo", "mavros", "uav", "simulation"]
    display_name = "PX4 SITL ROS offboard examples"
    vendor = "darienmt"
    model = "PX4 SITL and MAVROS offboard control examples"
    facts = [
        Fact("offb_node subscribes the relative mavros/state topic with mavros_msgs::State and queue size 10.",
             source="upstream_code", ref=_STATE_REF),
        Fact("offb_node includes the generated mavros_msgs/State header.",
             source="upstream_code", ref=_STATE_TYPE_REF),
        Fact("offb_node advertises geometry_msgs::PoseStamped on the relative mavros/setpoint_position/local "
             "topic with queue size 10.", source="upstream_code", ref=_POSITION_PUB_REF),
        Fact("offb_node includes the generated geometry_msgs/PoseStamped header.",
             source="upstream_code", ref=_POSITION_TYPE_REF),
        Fact("offb_node declares a geometry_msgs::PoseStamped pose, sets only pose.pose.position.x, y and z, to 0, "
             "0 and 2, and publishes that pose unchanged.", source="upstream_code", ref=_POSITION_FIELDS_REF),
        Fact("The offb node's comment states the setpoint publishing rate must be faster than 2 Hz and constructs "
             "ros::Rate(20.0).", source="upstream_code", ref=_POSITION_LOOP_REF),
        Fact("offb_node publishes the pose 100 times, spinning and sleeping on the rate each time, under the comment "
             "'send a few setpoints before starting'.", source="upstream_code", ref=_POSITION_SEND_REF),
        Fact("offb_node creates a mavros_msgs::CommandBool client on the relative mavros/cmd/arming name and a "
             "mavros_msgs::SetMode client on the relative mavros/set_mode name.",
             source="upstream_code", ref=_OFFB_CLIENTS_REF),
        Fact("In its loop offb_node sends the custom_mode OFFBOARD request when the reported mode is not OFFBOARD "
             "and more than 5 s have passed since the last request, otherwise sends the arming request with value "
             "true when the vehicle is not armed and more than 5 s have passed, and publishes the pose on every "
             "cycle.", source="upstream_code", ref=_POSITION_PUBLISH_REF),
        Fact("offb.launch includes px4's mavros_posix_sitl.launch and starts the offb node (type offb_node).",
             source="upstream_code", ref=_OFFB_LAUNCH_REF),
        Fact("offb_velocity.launch includes px4's mavros_posix_sitl.launch and starts the offb_velocity node "
             "(type node).", source="upstream_code", ref=_VELOCITY_LAUNCH_REF),
        Fact("Drone::Drone advertises mavros_msgs::PositionTarget on the relative mavros/setpoint_raw/local topic "
             "with queue size 10.", source="upstream_code", ref=_VELOCITY_PUB_REF),
        Fact("Drone::Drone creates a mavros_msgs::CommandTOL client on /mavros/cmd/takeoff.",
             source="upstream_code", ref=_TAKEOFF_CLIENT_REF),
        Fact("Drone::Drone creates a mavros_msgs::SetMode client on the relative mavros/set_mode name.",
             source="upstream_code", ref=_MODE_CLIENT_REF),
        Fact("Drone::Drone creates a mavros_msgs::CommandTOL client on /mavros/cmd/land.",
             source="upstream_code", ref=_LAND_CLIENT_REF),
        Fact("Drone::Drone includes the generated mavros_msgs/PositionTarget header.",
             source="upstream_code", ref=_VELOCITY_TYPE_REF),
        Fact("Drone::arm creates a mavros_msgs::CommandBool client on /mavros/cmd/arming, sets request.value "
             "to true and returns the response success flag.", source="upstream_code", ref=_ARM_CALL_REF),
        Fact("Drone::setOffboardMode sets request.custom_mode to OFFBOARD and returns the response mode_sent "
             "flag.", source="upstream_code", ref=_MODE_CALL_REF),
        Fact("Drone::land returns false without a call while home_set_ is false; otherwise it sends an empty "
             "mavros_msgs::CommandTOL request to the land client and returns the response success flag.",
             source="upstream_code", ref=_LAND_CALL_REF),
        Fact("Drone::setOffboardVelocityBody sets coordinate_frame FRAME_BODY_NED and the type_mask IGNORE_PX, "
             "IGNORE_PY, IGNORE_PZ, IGNORE_AFX, IGNORE_AFY, IGNORE_AFZ, FORCE and IGNORE_YAW, sets velocity x, y "
             "and z and yaw_rate, and publishes the message count times with a rate_.sleep() after each.",
             source="upstream_code", ref=_BODY_HELPER_REF),
        Fact("Drone::setOffboardVelocityNED sets coordinate_frame FRAME_LOCAL_NED and the type_mask IGNORE_PX, "
             "IGNORE_PY, IGNORE_PZ, IGNORE_AFX, IGNORE_AFY, IGNORE_AFZ, FORCE and IGNORE_YAW_RATE, sets velocity "
             "x, y and z and yaw, and publishes the message count times with a rate_.sleep() after each.",
             source="upstream_code", ref=_NED_HELPER_REF),
        Fact("The velocity example logs 'NED: Move towards South' before a setOffboardVelocityNED call with vy -2 "
             "and 'NED: Go Up' before one with vz 2.", source="upstream_code", ref=_NED_SIGN_REF),
        Fact("The velocity example logs 'Body: Turn around yaw clockwise and climb' before a "
             "setOffboardVelocityBody call with vz 1 and yaw_rate -60, and 'Body: Turn yaw anti-clockwise' before "
             "one with yaw_rate 60.", source="upstream_code", ref=_BODY_SIGN_REF),
        Fact("Drone::toRadFromDeg returns deg / 180 * M_PI as a float.",
             source="upstream_code", ref=_TO_RAD_REF),
        Fact("Drone::getAltitude subscribes /mavros/altitude with mavros_msgs::Altitude and spins while "
             "altitude_received_ is false.", source="upstream_code", ref=_ALTITUDE_WAIT_REF),
        Fact("The drone_offboard header includes the generated mavros_msgs/Altitude header.",
             source="upstream_code", ref=_ALTITUDE_TYPE_REF),
        Fact("The velocity node arms, takes off, runs the NED and body velocity sequences and then calls land.",
             source="upstream_code", ref=_VELOCITY_FLOW_REF),
        Fact("After the land service call the velocity node sleeps for five seconds, shuts ROS down and returns; "
             "it reads no landed state and sends no disarm request.", source="upstream_code",
             ref=_POST_LAND_REF),
        Fact("offb_node waits in a loop while current_state.connected is false before it sends setpoints.",
             source="upstream_code", ref="src/offb/src/offb_node.cpp:35-39"),
        Fact("Drone::getAltitudeCB stores the message and copies altitude_.amsl into altitude_in_amsl_.",
             source="upstream_code", ref="src/offb_velocity/src/drone_offboard.cpp:116-121"),
        Fact("drone_offboard.cpp includes the generated mavros_msgs/CommandBool and mavros_msgs/CommandTOL headers.",
             source="upstream_code", ref="src/offb_velocity/src/drone_offboard.cpp:2-3"),
    ]
    safe_state = (
        "Simulated only: landing requested and the vehicle sensed landed and disarmed: /mavros/state connected and "
        "not armed and /mavros/altitude AMSL still within the operator's bound, in three consecutive fresh stamped "
        "samples within the confirmation bound. The land response alone proves nothing; a running offb_node may "
        "re-arm the vehicle afterwards; nothing is claimed beyond the confirmation window."
    )
    #: The request steps' timeouts (1000 + 1000 ms) plus confirm_within_ms (1500 ms): the e-stop's budget.
    estop_latency_ms = 3500
    fidelity = {
        "engine": "analytic:ROS-free recording fake for the MAVROS/PX4 SITL contract (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies with no PX4/Gazebo step or wall-clock pacing; placeholder "
                     "state does not establish flight, trajectory or landing replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free ros_transport handler: it answers the declared MAVROS subscriptions and "
            "services and records the setpoint publications, but it runs no PX4 SITL, Gazebo, MAVROS, controller "
            "loop or wall-clock timer",
            "state, altitude, setpoint effects and all service replies are placeholders; a live run needs the "
            "operator's MAVROS/PX4 graph and rosbridge endpoint",
            "the fake snaps its placeholder AMSL altitude to the z of a published position setpoint so the "
            "resource changes; it integrates no motion and the publication receipt makes no arrival claim",
            "a single rosbridge publication is not the clone's continuous 20 Hz or 10 Hz setpoint stream; MAVROS "
            "may reject an offboard setpoint that is not streamed",
            "the fake starts armed in OFFBOARD at the offb hover altitude (2 m placeholder AMSL); its landing is a "
            "placeholder descent per sample and a disarm at touchdown (PX4's land detector and COM_DISARM_LAND live "
            "in the px4-firmware submodule, outside the citable clone), not PX4 or Gazebo",
            "the e-stop is a sensed-confirmation stop (SAFE-049, simulated only): it sends /mavros/cmd/land and a "
            "/mavros/cmd/arming disarm request and is achieved only on three consecutive fresh samples of "
            "/mavros/state (connected, not armed) and /mavros/altitude (AMSL still) within the bound; the "
            "altitude bound is operator_required (a fake placeholder in fixtures/estop-confirmation.json) and the "
            "client bounds are fake-scale, so a live deployment sets both in "
            "simulation_deployment['estop_confirmation']",
            "without PX4 auto-disarm the first e-stop stays unconfirmed (the disarm request is refused in the air) "
            "and the background retry's disarm after touchdown confirms it; a running offb_node requests OFFBOARD "
            "and arming again every 5 s and undoes a confirmed stop, which a reset's re-confirmation refuses but "
            "nothing prevents",
            "MAVROS drives a real PX4 over a serial or network link with another fcu_url; this package is a "
            "simulated device only and that path is out of scope",
            "the clone's offb.launch and offb_velocity.launch also start offb_node, which streams the (0, 0, 2) "
            "hover setpoint at 20 Hz and requests OFFBOARD and arming every 5 s, or the velocity node's own arm, "
            "takeoff, velocity and land sequence; with either node running the vehicle has competing commanders",
            "velocity inputs are passed through with the clone's ROS-side signs (its examples log vz 2 as 'Go Up', "
            "vy -2 as 'Move towards South' and body yaw_rate -60 deg/s as clockwise); MAVROS's frame conversion "
            "is outside the clone and the driver performs none",
            "the example site overlay values are operator examples, not device or flight-approval facts; without "
            "an overlay every numeric setpoint is refused",
            "takeoff, the home-position topic, the trajectory packages, ROS parameters, QoS, namespaces, "
            "remapping and MAVLink framing are NOT COVERED",
        ],
    }

    # Resource state: the clone's own MAVROS state and altitude topics.
    parameters = {
        "connected": Field("boolean", description="mavros_msgs/State.connected as last published"),
        "armed": Field("boolean", description="mavros_msgs/State.armed as last published"),
        "mode": Field("string", description="mavros_msgs/State.mode as last published"),
        "altitude_amsl": Field("number", unit="m", description="mavros_msgs/Altitude.amsl as last published"),
    }
    reads = {
        "connected": {
            "topic": "/mavros/state",
            "type": "mavros_msgs/State",
            "source_name": "mavros/state",
            "source_ref": _STATE_REF,
            "type_ref": _STATE_TYPE_REF,
            "path": "connected",
            "timeout_ms": 2000,
        },
        "armed": {
            "topic": "/mavros/state",
            "type": "mavros_msgs/State",
            "source_name": "mavros/state",
            "source_ref": _STATE_REF,
            "type_ref": _STATE_TYPE_REF,
            "path": "armed",
            "timeout_ms": 2000,
        },
        "mode": {
            "topic": "/mavros/state",
            "type": "mavros_msgs/State",
            "source_name": "mavros/state",
            "source_ref": _STATE_REF,
            "type_ref": _STATE_TYPE_REF,
            "path": "mode",
            "timeout_ms": 2000,
        },
        "altitude_amsl": {
            "topic": "/mavros/altitude",
            "type": "mavros_msgs/Altitude",
            "source_ref": _ALTITUDE_REF,
            "type_ref": _ALTITUDE_TYPE_REF,
            "path": "amsl",
            "timeout_ms": 2000,
        },
    }
    commands = {
        "x-cap.darienmt.state.v1": _STATE,
        "x-cap.darienmt.altitude.v1": _ALTITUDE,
        "x-cap.darienmt.hover.v1": _HOVER,
        "x-cap.darienmt.setpoint_position.v1": _POSITION_SETPOINT,
        "x-cap.darienmt.setpoint_velocity_body.v1": _VELOCITY_BODY,
        "x-cap.darienmt.setpoint_velocity_ned.v1": _VELOCITY_NED,
        "x-cap.darienmt.request_arm.v1": _ARM,
        "x-cap.darienmt.request_offboard.v1": _OFFBOARD_MODE,
        "x-cap.darienmt.request_land.v1": _LAND,
    }
    actions = {
        "x-cap.darienmt.state.v1": Action(
            name="read_state",
            verb="read",
            description="Read one mavros_msgs/State sample from /mavros/state",
            output=_STATE_OUTPUT,
        ),
        "x-cap.darienmt.altitude.v1": Action(
            name="read_altitude",
            verb="read",
            description="Read one mavros_msgs/Altitude sample from /mavros/altitude",
            output=_ALTITUDE_OUTPUT,
        ),
        "x-cap.darienmt.hover.v1": Action(
            name="hover",
            verb="invoke",
            risk="R2",
            description="Publish the offb example's fixed hover PoseStamped (0, 0, 2); the receipt confirms "
                        "transmission only, not reception, arrival or motion",
            output=_PUBLISHED,
        ),
        "x-cap.darienmt.setpoint_position.v1": Action(
            name="setpoint_position",
            verb="invoke",
            risk="R2",
            description="Publish one position setpoint on mavros/setpoint_position/local; the receipt confirms "
                        "transmission only, not arrival or a continuous stream",
            input={
                "x": Field("number", unit="m", description="Setpoint position x", limit=_POSITION_X),
                "y": Field("number", unit="m", description="Setpoint position y", limit=_POSITION_Y),
                "z": Field("number", unit="m", description="Setpoint position z", limit=_POSITION_Z),
            },
            output=_PUBLISHED,
        ),
        "x-cap.darienmt.setpoint_velocity_body.v1": Action(
            name="setpoint_velocity_body",
            verb="invoke",
            risk="R2",
            description="Publish one body-frame velocity PositionTarget on mavros/setpoint_raw/local; the receipt "
                        "confirms transmission only",
            input={
                "vx": Field("number", unit="m/s", description="Body-frame velocity x", limit=_VELOCITY_X),
                "vy": Field("number", unit="m/s", description="Body-frame velocity y", limit=_VELOCITY_Y),
                "vz": Field("number", unit="m/s", description="Body-frame velocity z; the clone's example climbs "
                                                              "with positive z", limit=_VELOCITY_Z),
                "yaw_rate": Field("number", unit="rad/s", description="Body-frame yaw rate; the clone's example "
                                                                      "turns clockwise with negative values",
                                  limit=_YAW_RATE),
            },
            output=_PUBLISHED,
        ),
        "x-cap.darienmt.setpoint_velocity_ned.v1": Action(
            name="setpoint_velocity_ned",
            verb="invoke",
            risk="R2",
            description="Publish one local-NED velocity PositionTarget on mavros/setpoint_raw/local; the receipt "
                        "confirms transmission only",
            input={
                "vx": Field("number", unit="m/s", description="FRAME_LOCAL_NED velocity x", limit=_VELOCITY_X),
                "vy": Field("number", unit="m/s", description="FRAME_LOCAL_NED velocity y; the clone's example "
                                                              "moves south with negative y", limit=_VELOCITY_Y),
                "vz": Field("number", unit="m/s", description="FRAME_LOCAL_NED velocity z; the clone's example "
                                                              "goes up with positive z", limit=_VELOCITY_Z),
                "yaw": Field("number", unit="rad", description="FRAME_LOCAL_NED yaw", limit=_YAW),
            },
            output=_PUBLISHED,
        ),
        "x-cap.darienmt.request_arm.v1": Action(
            name="request_arm",
            verb="invoke",
            risk="R2",
            description="Send the fixed mavros_msgs/CommandBool value=true arming request; success is the service "
                        "response flag, not a sensed armed transition",
            output=_ARM_OUTPUT,
        ),
        "x-cap.darienmt.request_offboard.v1": Action(
            name="request_offboard",
            verb="invoke",
            risk="R2",
            description="Send the fixed mavros_msgs/SetMode custom_mode=OFFBOARD request; mode_sent is a request "
                        "acknowledgement, not a sensed mode transition",
            output=_MODE_OUTPUT,
        ),
        "x-cap.darienmt.request_land.v1": Action(
            name="request_land",
            verb="invoke",
            risk="R2",
            description="Send the fixed mavros_msgs/CommandTOL landing request, an ordinary command: success "
                        "acknowledges a LAND request, not touchdown, disarm or sensed quiescence, and the e-stop "
                        "latch refuses it",
            output=_LAND_OUTPUT,
        ),
    }
    #: A LAND request acknowledgement alone does not certify a stop (drone_offboard.cpp:57-71;
    #: offb_velocity_node.cpp:59-70): the e-stop is the sensed-confirmation stop above (SAFE-049), never an
    #: acknowledged binding.
    safety_bindings = {"sensed_stop": _SENSED_STOP}
