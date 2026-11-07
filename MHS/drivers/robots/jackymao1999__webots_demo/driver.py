"""OpenMHS rosbridge driver for the pinned Webots demo simulation (gh.jackymao1999/webots_demo).

The upstream repository is a ROS 1 + Webots R2021a demo made of C++ controllers
and launch files, not a Python device class.  This package is therefore a
configuration-only ``RosDriver`` over rosbridge: it imports no ROS, starts no
node, and neither imports nor runs the clone.

The primary interface is the Webots controller's acknowledged
``robot/robot/time_step`` service of type ``webots_ros/set_int``; the demo
controller requests its ``TIME_STEP`` constant (32) with it in every loop
iteration.  The same service with value 0 is the request the upstream
``Webots::Quit`` path sends, unchecked, just before it shuts the ROS node down
and exits.  The service implementation (the webots_ros ``ros`` controller) is
not in the clone, so what a 0 request does is not shown; the demo controller
keeps requesting 32 ms steps and the wheel velocities it last set stay in
effect.  The package therefore declares no e-stop binding and no safe-state
action: an MHS e-stop latches the driver and reports
MHS.SAFETY.SAFE_STATE_UNREACHED.  The 0 request stays available as an ordinary
action whose receipt is an acknowledgement only.

One observation is exposed: ``/robot/gps/values``
(``geometry_msgs/PointStamped``), which the Webots controller publishes and the
pinned gmapping broadcaster subscribes to.  The laser, camera, wheel velocity
services, ``/cmd_vel``, ``/vel``, ``robot/odom``, TF and the navigation stack
are outside this package.

Every endpoint, type and fact cites the pinned clone at
1c45e4bdefb30b8ebbe8e1c4af9b59e22cb0c17f.  The fake transport is ROS-free; no
ROS graph, Webots process or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references (paths are relative to the clone root)
# ---------------------------------------------------------------------------

_TIME_STEP_REF = "include/webots_ros.h:59-61"
_TIME_STEP_TYPE_REF = "include/webots_ros.h:14"
_TIME_STEP_SERVICE_SRV = "srv/set_int.srv:3"
_TIME_STEP_CHECK_REF = "include/webots_ros.h:128-132"
_TIME_STEP_QUIT_REF = "include/webots_ros.h:135-141"
_TIME_STEP_CONST_REF = "src/demo_2dnav_move.cpp:15"
_CONTROLLER_LOOP_REF = "src/demo_2dnav_move.cpp:104-107"
_WORLD_REF = "worlds/webots_map.wbt:173-177"
_DEVICE_LIST_REF = "worlds/webots_map.wbt:20-25"
_MOTORS_REF = "worlds/webots_map.wbt:92-130"
_GPS_SUBSCRIBE_REF = "src/robot_broadcaster_gmapping.cpp:123-126"
_GPS_CALLBACK_REF = "src/robot_broadcaster_gmapping.cpp:85-89"
_GPS_INCLUDE_REF = "src/robot_broadcaster_gmapping.cpp:10-11"
_NAV_LAUNCH_REF = "launch/amcl_demo.launch:15-17"
_LASER_REMAP_REF = "launch/amcl_demo.launch:27"
_LICENSE_REF = "package.xml:16"
_WEBOTS_LAUNCH_REF = "launch/webots.launch:12-16"
_CMD_VEL_CALLBACK_REF = "src/demo_2dnav_move.cpp:72-87"
_MOVE_BASE_REF = "launch/amcl_demo.launch:60-66"
_README_REF = "README.md:3"
_CMAKE_REF = "CMakeLists.txt:161-179"

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

_COORDINATE = Field(
    "number",
    description="Coordinate published in the geometry_msgs/Point; the clone states no physical unit",
)

_POINT = Field(
    "object",
    description="geometry_msgs/Point of the GPS sample; the clone states no physical unit",
    properties={
        "x": _COORDINATE,
        "y": _COORDINATE,
        "z": _COORDINATE,
    },
)

_FRAME_ID = Field("string", description="Frame id carried by the PointStamped header")

# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------

#: Webots::Init creates this relative service client and sends TIME_STEP as
#: the request value.  The set_int response is a single bool success field.
_TIME_STEP = {
    "service": "/robot/robot/time_step",
    "type": "webots_ros/set_int",
    "source_name": "robot/robot/time_step",
    "source_ref": _TIME_STEP_REF,
    "type_ref": _TIME_STEP_TYPE_REF,
    "success": {"path": "success", "equals": True},
}

#: One controller step with the demo's fixed TIME_STEP constant (32).
_STEP = dict(
    _TIME_STEP,
    request={"value": 32},
    result={"map": {"advanced": "success"}},
)

#: The 0-value request the upstream Quit path sends before shutdown.  The
#: clone does not contain the service implementation, so the receipt is an
#: acknowledgement only; it is an ordinary action, not a safe-state action and
#: not an e-stop binding.
_STOP = dict(
    _TIME_STEP,
    request={"value": 0},
    result={"map": {"acknowledged": "success"}},
)

#: The Webots controller publishes the GPS sample; the gmapping broadcaster
#: subscribes to the relative gps/values name and reads point.x and point.z.
_GPS = {
    "topic": "/robot/gps/values",
    "type": "geometry_msgs/PointStamped",
    "source_name": "gps/values",
    "source_ref": _GPS_SUBSCRIBE_REF,
    "type_ref": _GPS_INCLUDE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"point": "point", "frame_id": "header.frame_id"}},
}


class WebotsDemo(RosDriver):
    device_id = "webots_demo"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeWebotsDemo"}
    tags = ["ros", "ros1", "webots", "simulation", "time-step", "gps"]
    display_name = "Webots demo simulator"
    vendor = "jackymao1999"
    facts = [
        Fact("The pinned package.xml licence tag is TODO.", source="upstream_code", ref=_LICENSE_REF),
        Fact("The README requires Webots R2021a on Ubuntu 20.04.", source="vendor_doc", ref=_README_REF),
        Fact("The world Robot uses the ros controller with the controller arguments --use-sim-time, --clock "
             "and --name=robot.", source="upstream_code", ref=_WORLD_REF),
        Fact("webots.launch includes the webots_ros webots.launch with mode realtime and the webots_map world.",
             source="upstream_code", ref=_WEBOTS_LAUNCH_REF),
        Fact("The world declares an InertialUnit, a GPS and a SickLms291 device on the Robot.",
             source="upstream_code", ref=_DEVICE_LIST_REF),
        Fact("The world declares left_motor and right_motor RotationalMotors on the two wheel hinge joints.",
             source="upstream_code", ref=_MOTORS_REF),
        Fact("The Webots helper creates a client for the relative service robot/robot/time_step of type "
             "webots_ros::set_int and sets the request value to TIME_STEP.",
             source="upstream_code", ref=_TIME_STEP_REF),
        Fact("The set_int service response is a single bool success field.",
             source="upstream_code", ref=_TIME_STEP_SERVICE_SRV),
        Fact("The demo controller constant TIME_STEP is 32.",
             source="upstream_code", ref=_TIME_STEP_CONST_REF),
        Fact("Webots::ChecktimeStep calls the time_step service and reports failure when the call or the "
             "service success flag fails.", source="upstream_code", ref=_TIME_STEP_CHECK_REF),
        Fact("Webots::Quit deletes the node handle, sets the time_step request value to 0, calls the service "
             "without checking the result, then calls ros::shutdown() and exit(0).", source="upstream_code",
             ref=_TIME_STEP_QUIT_REF),
        Fact("The demo controller loop calls ChecktimeStep while ros::ok() and breaks when it returns nonzero.",
             source="upstream_code", ref=_CONTROLLER_LOOP_REF),
        Fact("The demo controller's /cmd_vel callback converts linear.x and angular.z into left and right wheel "
             "speeds and calls updateSpeed().", source="upstream_code", ref=_CMD_VEL_CALLBACK_REF),
        Fact("The gmapping broadcaster includes geometry_msgs/PointStamped and sensor_msgs/Imu headers.",
             source="upstream_code", ref=_GPS_INCLUDE_REF),
        Fact("The gmapping broadcaster enables the gps service and subscribes to gps/values.",
             source="upstream_code", ref=_GPS_SUBSCRIBE_REF),
        Fact("The GPS callback reads point.x and point.z into the demo's planar state.",
             source="upstream_code", ref=_GPS_CALLBACK_REF),
        Fact("The amcl launch starts the gmapping broadcaster and demo_2dnav_move.",
             source="upstream_code", ref=_NAV_LAUNCH_REF),
        Fact("The amcl launch also starts move_base with cmd_vel remapped to cmd_vel.",
             source="upstream_code", ref=_MOVE_BASE_REF),
        Fact("The amcl launch remaps the laser scan to robot/Sick_LMS_291/laser_scan/layer0.",
             source="upstream_code", ref=_LASER_REMAP_REF),
        Fact("The package CMakeLists builds the demo controller and broadcaster executables.",
             source="upstream_code", ref=_CMAKE_REF),
    ]
    safe_state = (
        "No acknowledged stop exists: an MHS e-stop only latches the driver, refusing further step requests, "
        "and reports MHS.SAFETY.SAFE_STATE_UNREACHED. It sends nothing to Webots; the realtime-mode simulation, "
        "the demo controller's own 32 ms time_step requests and the wheel velocities it last set from /cmd_vel "
        "continue. The 0 time_step request of the upstream Quit path is not bound: the clone does not show "
        "what it does."
    )
    fidelity = {
        "engine": "canned:ROS-free rosbridge fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned responses with no Webots physics, controller loop, pacing or "
                     "state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free canned transport: it answers the declared time_step service and the "
            "gps/values subscription and runs no Webots R2021a simulation, physics, controller, sensors or "
            "wall-clock loop",
            "the time_step call is answered with a canned success and a placeholder counter; no simulation "
            "state advances and the 32 value is the upstream controller constant, not a fake timestep",
            "the GPS point and frame id are placeholders and do not follow a robot pose or trajectory",
            "the upstream controller's TIME_STEP is 32, but the fake declares no timestep and no pacing",
            "no e-stop binding and no safe-state action: the 0-value time_step request is what the Quit path "
            "sends, unchecked, just before ros::shutdown() and exit(0); the clone does not contain the service "
            "implementation, the demo controller keeps requesting 32 ms steps in its loop, and the wheel "
            "velocities set from /cmd_vel (move_base in the amcl launch) persist, so an MHS e-stop latches and "
            "reports SAFE_STATE_UNREACHED",
            "the GPS coordinates carry no unit because the clone states none",
            "in the clone only the robot broadcasters call the gps enable service before they subscribe to "
            "robot/gps/values; a deployment without one may leave the topic silent, and the read then fails "
            "NOT_READY",
            "the laser, camera, wheel velocity services, /cmd_vel, /vel, robot/odom, TF, keyboard and the "
            "navigation stack are NOT COVERED",
            "no ROS graph, rosbridge connection, Webots process or hardware was run; a live deployment needs "
            "Webots R2021a, ROS 1 Noetic, the webots_ros controller and an operator-run rosbridge endpoint",
        ],
    }

    commands = {
        "x-cap.jackymao1999.step.v1": _STEP,
        "x-cap.jackymao1999.stop.v1": _STOP,
        "x-cap.jackymao1999.gps.v1": _GPS,
    }
    actions = {
        "x-cap.jackymao1999.step.v1": Action(
            name="step",
            verb="invoke",
            description=(
                "Send one fixed 32 time_step service request to the Webots controller. The service "
                "response is the only completion evidence; the action returns no observation and does not "
                "prove physical motion or state."
            ),
            output={"advanced": Field(
                "boolean", description="True when the time_step service returned success=true")},
        ),
        "x-cap.jackymao1999.stop.v1": Action(
            name="send_zero_time_step",
            description=(
                "Send the fixed 0 time_step request that the upstream Quit path sends before it exits. The "
                "clone does not contain the service implementation, so the receipt proves only that the "
                "controller answered success; it is not a stop and not a safe state."
            ),
            output={"acknowledged": Field(
                "boolean",
                description="True when the time_step service returned success=true; this is an "
                            "acknowledgement, not proof of quiescence")},
        ),
        "x-cap.jackymao1999.gps.v1": Action(
            name="read_gps",
            verb="read",
            description="Read one geometry_msgs/PointStamped sample from the gps/values topic.",
            output={"point": _POINT, "frame_id": _FRAME_ID},
        ),
    }
    #: No safety_bindings: the 0-value time_step request has no effect shown in
    #: the clone (include/webots_ros.h:135-141), so the e-stop latches only.
