"""OpenMHS rosbridge driver for the clydemcqueen/flock2 drone controller.

The pinned upstream is a ROS 2 package.  Its launched controller is the C++
``drone_base`` node; the entry symbol named by the task card
(``flock_simple_path:TrajectoryVelocityFlyer``) is a Python trajectory helper
that is installed by ``CMakeLists.txt`` but is not started by any shipped
launch file.  This package is a configuration-only :class:`RosDriver` over the
production node's topic contract.  It declares no Python native class and
neither imports nor starts the upstream code.

The exposed control is the same topic contract the launch file uses:
``/start_mission`` and ``/stop_mission`` are absolute ``std_msgs/Empty``
subscriptions of ``drone_base``, ``cmd_vel`` is its relative
``geometry_msgs/Twist`` publication, and ``base_odom`` is its relative
``nav_msgs/Odometry`` subscription.  The shipped single-drone launch runs
``drone_base`` under the ``solo`` namespace, so the two relative endpoints are
declared as ``/solo/cmd_vel`` and ``/solo/base_odom``; the operator can remap a
different deployment namespace.  A rosbridge publication is a
transmission, not an execution or landing acknowledgement.

There is no ROS service or action stop in the pinned clone.  ``/stop_mission``
clears the mission flag, publishes a zero Twist through ``all_stop()`` and, when
the node believes it is flying and the action manager is free, forwards a land
command to the external ``tello_action`` service.  The action manager drops the
land request while busy, and the service response only reports acceptance;
completion is a later ``tello_response`` topic message.  This package therefore
declares no e-stop binding and no safe-state action.  The R2 mobile base is
blocked on that missing acknowledged stop; the driver is not presented as a
safe flight controller.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: drone_base.cpp creates the relative cmd_vel publication with a Twist.
_CMD_VEL_REF = "src/drone_base.cpp:169"
_CMD_VEL_TYPE_REF = "include/drone_base.hpp:5"

#: drone_base.cpp subscribes to the absolute mission topics with Empty.
_START_MISSION_REF = "src/drone_base.cpp:180"
_STOP_MISSION_REF = "src/drone_base.cpp:181"
_EMPTY_TYPE_REF = "include/drone_base.hpp:9"

#: The relative odometry and plan subscriptions and their message types.
_ODOM_REF = "src/drone_base.cpp:185"
_ODOM_TYPE_REF = "include/drone_base.hpp:6"
_PLAN_REF = "src/drone_base.cpp:186"
_PLAN_TYPE_REF = "include/drone_base.hpp:7"

#: The stop path and its asynchronous land action.
_ALL_STOP_REF = "src/drone_base.cpp:428-432"
_STOP_MISSION_PATH_REF = "src/drone_base.cpp:266-273"
_START_CALLBACK_REF = "src/drone_base.cpp:252-257"
_STOP_CALLBACK_REF = "src/drone_base.cpp:259-264"
_START_ACTION_REF = "src/drone_base.cpp:381-396"
_ACTION_MGR_REF = "include/action_mgr.hpp:11-20"
_ACTION_SEND_REF = "src/action_mgr.cpp:8-21"
_ACTION_RESPONSE_REF = "src/action_mgr.cpp:23-48"
_ACTION_COMPLETE_REF = "src/action_mgr.cpp:50-70"

#: The Python demo's stop is explicitly not a landing and is not launched.
_FLYER_STOP_REF = "src/flock_simple_path.py:202-215"
_FLYER_NODE_REF = "src/flock_simple_path.py:347-367"
_FLYER_CMD_REF = "src/flock_simple_path.py:430-440"
_LAUNCH_REF = "launch/launch_one.py:28-33"

#: The internal controller clamps its own published velocity components.
_FLIGHT_CONTROLLER_CLAMP_REF = "include/flight_controller_interface.hpp:60-68"

_NORMALIZED_LIMIT = Limit.operator_required(
    "the clone states no physical unit or numeric range for the ROS cmd_vel components; "
    "the internal controller clamps its own output but the topic consumer's range is external, "
    "so the operator supplies the deployed envelope"
)

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the message to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution confirmation"),
}

_CMD_VEL = {
    "topic": "/solo/cmd_vel",
    "type": "geometry_msgs/msg/Twist",
    "operation": "publish",
    "source_name": "cmd_vel",
    "source_ref": _CMD_VEL_REF,
    "type_ref": _CMD_VEL_TYPE_REF,
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "args": {
        "linear.x": {"from": "input.linear_x"},
        "linear.y": {"from": "input.linear_y"},
        "linear.z": {"from": "input.linear_z"},
        "angular.z": {"from": "input.angular_z"},
    },
}

_START_MISSION = {
    "topic": "/start_mission",
    "type": "std_msgs/msg/Empty",
    "operation": "publish",
    "source_name": "/start_mission",
    "source_ref": _START_MISSION_REF,
    "type_ref": _EMPTY_TYPE_REF,
}

_STOP_MISSION = {
    "topic": "/stop_mission",
    "type": "std_msgs/msg/Empty",
    "operation": "publish",
    "source_name": "/stop_mission",
    "source_ref": _STOP_MISSION_REF,
    "type_ref": _EMPTY_TYPE_REF,
}

_POSITION = Field(
    "object",
    description="Position from nav_msgs/Odometry pose.pose.position",
    properties={
        "x": Field("number", unit="m", description="Position x in the odometry frame"),
        "y": Field("number", unit="m", description="Position y in the odometry frame"),
        "z": Field("number", unit="m", description="Position z in the odometry frame"),
    },
)

_ORIENTATION = Field(
    "object",
    description="Orientation from nav_msgs/Odometry pose.pose.orientation",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)

_LINEAR = Field(
    "object",
    description="Linear velocity from nav_msgs/Odometry twist.twist.linear",
    properties={
        "x": Field("number", unit="m/s", description="Linear velocity x"),
        "y": Field("number", unit="m/s", description="Linear velocity y"),
        "z": Field("number", unit="m/s", description="Linear velocity z"),
    },
)

_ANGULAR = Field(
    "object",
    description="Angular velocity from nav_msgs/Odometry twist.twist.angular",
    properties={
        "x": Field("number", unit="rad/s", description="Angular velocity x"),
        "y": Field("number", unit="rad/s", description="Angular velocity y"),
        "z": Field("number", unit="rad/s", description="Angular velocity z"),
    },
)

_ODOM_TWIST = Field(
    "object",
    description="Twist from nav_msgs/Odometry twist.twist",
    properties={"linear": _LINEAR, "angular": _ANGULAR},
)


class Flock2(RosDriver):
    device_id = "flock2"
    device_kind = "robot.mobile_base"
    mode = "hardware"
    # The card floor is R1, but the launched node commands a flying mobile base.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeFlock2"}
    tags = ["ros", "ros2", "flock2", "tello", "mobile-base", "cmd-vel", "odometry"]
    display_name = "flock2 drone controller"
    vendor = "Clyde McQueen"
    model = "Tello drone with flock2 drone_base"
    facts = [
        Fact("The drone_base header includes geometry_msgs/msg/twist.hpp, nav_msgs/msg/odometry.hpp, "
             "nav_msgs/msg/path.hpp and std_msgs/msg/empty.hpp.",
             source="upstream_code", ref="include/drone_base.hpp:5-9"),
        Fact("DroneBase::DroneBase registers a relative cmd_vel publisher of geometry_msgs::msg::Twist with "
             "queue size 1.",
             source="upstream_code", ref=_CMD_VEL_REF),
        Fact("DroneBase::DroneBase subscribes to the absolute /start_mission and /stop_mission topics of "
             "std_msgs::msg::Empty with queue size 10.",
             source="upstream_code", ref="src/drone_base.cpp:180-181"),
        Fact("DroneBase::DroneBase subscribes to the relative base_odom nav_msgs::msg::Odometry and plan "
             "nav_msgs::msg::Path topics with queue size 10.",
             source="upstream_code", ref="src/drone_base.cpp:185-186"),
        Fact("DroneBase::start_mission_callback only sets mission_ to true and returns; it publishes no "
             "acknowledgement and starts no takeoff.",
             source="upstream_code", ref=_START_CALLBACK_REF),
        Fact("DroneBase::stop_mission_callback logs and calls stop_mission().",
             source="upstream_code", ref=_STOP_CALLBACK_REF),
        Fact("DroneBase::stop_mission clears mission_, calls all_stop(), and, only when the state is flight or "
             "flight_odom, calls start_action(Action::land).",
             source="upstream_code", ref=_STOP_MISSION_PATH_REF),
        Fact("DroneBase::all_stop publishes a zero velocity through the flight controller.",
             source="upstream_code", ref=_ALL_STOP_REF),
        Fact("FlightControllerInterface::publish_velocity clamps throttle, strafe, vertical and yaw each to "
             "-1.0..1.0 and publishes them as a geometry_msgs::msg::Twist.",
             source="upstream_code", ref=_FLIGHT_CONTROLLER_CLAMP_REF),
        Fact("DroneBase::start_action drops the requested action when the action manager is busy; otherwise it "
             "calls action_mgr_->send(action, g_actions[action]).",
             source="upstream_code", ref=_START_ACTION_REF),
        Fact("The action manager sends a TelloAction service request with request->cmd set to the action "
             "string and then waits for the service future.",
             source="upstream_code", ref=_ACTION_SEND_REF),
        Fact("The service response's rc is compared with OK, ERROR_BUSY and ERROR_NOT_CONNECTED; an OK response "
             "only marks the action as accepted and leaves state waiting_for_response.",
             source="upstream_code", ref=_ACTION_RESPONSE_REF),
        Fact("The action manager completes an action only when a later tello_response topic message reports "
             "success, failure or timeout.",
             source="upstream_code", ref=_ACTION_COMPLETE_REF),
        Fact("The action manager comment states that tello_driver uses a ROS service plus a ROS topic to "
             "simulate an action, and that only one action can be active at a time.",
             source="upstream_code", ref=_ACTION_MGR_REF),
        Fact("TrajectoryVelocityFlyer.stop sends a zero four-component command when launching or running and "
             "explicitly does not try to land the flying drone.",
             source="upstream_code", ref=_FLYER_STOP_REF),
        Fact("FlockSimplePath publishes the relative cmd_vel Twist topic and subscribes to absolute "
             "/start_mission, /stop_mission and /tf; it creates no service or action server.",
             source="upstream_code", ref=_FLYER_NODE_REF),
        Fact("FlockSimplePath::flyer_cmd_callback passes the flyer's four velocity components through to a "
             "geometry_msgs::msg::Twist and publishes it.",
             source="upstream_code", ref=_FLYER_CMD_REF),
        Fact("The shipped launch starts the drone_base controller and does not start the flock_simple_path "
             "script.",
             source="upstream_code", ref=_LAUNCH_REF),
        Fact("The shipped single-drone launch starts drone_base with namespace 'solo'.",
             source="upstream_code", ref="launch/launch_one.py:31-33"),
    ]
    safe_state = (
        "No acknowledged safe stop exists in the pinned clone: /stop_mission is a ROS 2 publication whose "
        "callback clears the mission flag, publishes a zero Twist and may forward an asynchronous land request "
        "to the external tello_action service; the publication and the service acceptance do not prove that "
        "the drone stopped, hovered or landed."
    )

    parameters = {
        "odom_position": _POSITION,
        "odom_orientation": _ORIENTATION,
        "odom_twist": _ODOM_TWIST,
    }
    reads = {
        "odom_position": {
            "topic": "/solo/base_odom",
            "type": "nav_msgs/msg/Odometry",
            "operation": "subscribe",
            "source_name": "base_odom",
            "source_ref": _ODOM_REF,
            "type_ref": _ODOM_TYPE_REF,
            "path": "pose.pose.position",
            "timeout_ms": 2000,
        },
        "odom_orientation": {
            "topic": "/solo/base_odom",
            "type": "nav_msgs/msg/Odometry",
            "operation": "subscribe",
            "source_name": "base_odom",
            "source_ref": _ODOM_REF,
            "type_ref": _ODOM_TYPE_REF,
            "path": "pose.pose.orientation",
            "timeout_ms": 2000,
        },
        "odom_twist": {
            "topic": "/solo/base_odom",
            "type": "nav_msgs/msg/Odometry",
            "operation": "subscribe",
            "source_name": "base_odom",
            "source_ref": _ODOM_REF,
            "type_ref": _ODOM_TYPE_REF,
            "path": "twist.twist",
            "timeout_ms": 2000,
        },
    }
    commands = {
        "x-cap.clydemcqueen.cmd_vel.v1": _CMD_VEL,
        "x-cap.clydemcqueen.start_mission.v1": _START_MISSION,
        "x-cap.clydemcqueen.stop_mission.v1": _STOP_MISSION,
    }
    actions = {
        "x-cap.clydemcqueen.cmd_vel.v1": Action(
            name="publish_cmd_vel",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one geometry_msgs/Twist to the drone controller's cmd_vel topic. The four values are "
                "the controller's normalized rate components; the clone states no physical unit. The receipt "
                "is a publication acknowledgement only."
            ),
            input={
                "linear_x": Field(
                    "number", unit="1",
                    description="Twist linear.x, a normalized body-frame rate component",
                    limit=_NORMALIZED_LIMIT,
                ),
                "linear_y": Field(
                    "number", unit="1",
                    description="Twist linear.y, a normalized body-frame rate component",
                    limit=_NORMALIZED_LIMIT,
                ),
                "linear_z": Field(
                    "number", unit="1",
                    description="Twist linear.z, a normalized vertical rate component",
                    limit=_NORMALIZED_LIMIT,
                ),
                "angular_z": Field(
                    "number", unit="1",
                    description="Twist angular.z, a normalized yaw-rate component",
                    limit=_NORMALIZED_LIMIT,
                ),
            },
            output=_PUBLISHED,
            examples=[{"linear_x": 0.0, "linear_y": 0.0, "linear_z": 0.0, "angular_z": 0.0}],
        ),
        "x-cap.clydemcqueen.start_mission.v1": Action(
            name="start_mission",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one std_msgs/Empty to /start_mission. The callback only sets mission_ true; the "
                "receipt proves only that rosbridge accepted the publication."
            ),
            output=_PUBLISHED,
        ),
        "x-cap.clydemcqueen.stop_mission.v1": Action(
            name="stop_mission",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one std_msgs/Empty to /stop_mission. This is an ordinary mission-stop request, not an "
                "acknowledged safe state: the callback publishes a zero Twist and may forward an asynchronous "
                "land request to an external service."
            ),
            output=_PUBLISHED,
        ),
    }
