"""OpenMHS rosbridge driver for the pinned AuNa ROS 2 navigation simulator.

AuNa is a ROS 2 framework and Gazebo testbed for multi-robot autonomous
navigation.  The concrete, in-repository control entry point is the
``auna_control`` ``cmd_vel_multiplexer_node``: it subscribes to one topic per
configured input source, selects one source, converts it to Ackermann drive and
publishes the result on the robot's ``cmd_vel_twist`` topic.  The Gazebo
race-car model consumes that topic through ``libgazebo_ros_ackermann_drive.so``.

This package is a configuration-only :class:`RosDriver`; it declares no Python
native class, imports no ROS and never starts the upstream stack.  The operator
runs the AuNa nodes, Gazebo and rosbridge separately.  The scope is one robot
namespace, ``/robot1``: the first robot of the shipped docker-compose services
(``ROBOT_INDEX=1``; the launch file's own default without that variable is
``robot0``): the command source, the teleop command topic and the
source-status service.  The absolute
``/trigger_emergency_stop`` and ``/get_estop_status`` services are not used:
every namespaced multiplexer registers those same absolute names, so a call
would not be robot-scoped.  The namespaced ``toggle_cmd_vel_source`` service is
the per-robot stop path.

Every endpoint, type and fact cites the pinned clone at
1d8bb13d574deca84c42e0bc9a0ff04d470d371f.  The fake transport is ROS-free and
is an analytic contract stand-in, not a replay of captured traffic.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The control configuration names the four multiplexer inputs and the output
#: topics.  The teleop input is the TwistStamped one used by this package.
_TOPIC_CONFIG_REF = "auna_common/config/control/topics.yaml:1-24"
_TELEOP_TOPIC_REF = "auna_common/config/control/topics.yaml:6-8"

#: The multiplexer headers include every message/service type used here.
_TYPE_REF = "packages/src/auna_control/include/auna_control/cmd_vel_multiplexer_node.hpp:32-39"

#: The node registers services, subscribes to the configured inputs and runs
#: the timer that republishes the selected last message.
_SERVICE_REF = "packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:128-161"
_SOURCE_CALLBACK_REF = (
    "packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:308-337"
)
_STATUS_CALLBACK_REF = (
    "packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:429-436"
)
_TIMER_REF = "packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:359-417"
_RATE_REF = "packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:62"
_SUBSCRIBE_REF = "packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:218-228"
_CALLBACK_REF = "packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:278-293"
_CONVERT_REF = "packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:511-518"
_ZERO_REF = "packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:503-508"
_PARAM_REF = "auna_common/config/control/params.yaml:1-5"
_INIT_REF = "packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:91-118"
_LAUNCH_REF = "packages/src/auna_control/launch/cmd_vel_multiplexer.launch.py:32-36"
_LAUNCH_NODE_REF = "packages/src/auna_control/launch/cmd_vel_multiplexer.launch.py:39-69"
_PLUGIN_REF = "packages/src/auna_gazebo/models/race_car/model.urdf:395-417"
_REMAP_REF = "packages/src/auna_gazebo/models/race_car/model.urdf:435-440"
_MODEL_PARAM_REF = "auna_common/config/model_params/race_car.yaml:7-11"
_COMPOSE_MUX_REF = "docker-compose.yml:307-314"
_COMPOSE_TELEOP_REF = "docker-compose.yml:594-609"
_TELEOP_NODE_REF = "packages/src/auna_teleoperation/auna_teleoperation/teleop.py:38-72"
_TELEOP_TOPIC_NODE_REF = "packages/src/auna_teleoperation/auna_teleoperation/teleop.py:124-136"
_PANEL_REF = "packages/src/auna_control/src/control_panel/control_panel_ros_interface.cpp:83-92"
_F110_REF = "packages/src/auna_f110/launch/vesc.launch.py:41-67"

#: The stop is the multiplexer's own source selection: OFF makes the timer
#: publish createZeroAckermann() instead of the cached source message.
_OFF_STOP = {
    "service": "/robot1/toggle_cmd_vel_source",
    "type": "auna_msgs/srv/SetString",
    "source_name": "toggle_cmd_vel_source",
    "source_ref": _SERVICE_REF,
    "type_ref": _TYPE_REF,
    "request": {"data": "OFF"},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"source_off": "success"}},
    "description": (
        "Set the multiplexer's velocity source to OFF.  Its timer then publishes zero speed and steering "
        "on cmd_vel_twist; the acknowledgement reports the source change, not sensed vehicle quiescence."
    ),
}

#: The source selection service.  The request is the upstream SetString.data.
_SOURCE_SELECT = {
    "service": "/robot1/toggle_cmd_vel_source",
    "type": "auna_msgs/srv/SetString",
    "source_name": "toggle_cmd_vel_source",
    "source_ref": _SERVICE_REF,
    "type_ref": _TYPE_REF,
    "args": {"data": {"from": "input.source"}},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"success": "success", "message": "message"}},
    "description": "Select the multiplexer input source; OFF stops forwarding and publishes zero commands.",
}

#: The source-status service uses std_srvs/Trigger.
_SOURCE_STATUS = {
    "service": "/robot1/get_source_status",
    "type": "std_srvs/srv/Trigger",
    "source_name": "get_source_status",
    "source_ref": _SERVICE_REF,
    "type_ref": _TYPE_REF,
    "operation": "read",
    "success": {"path": "success", "equals": True},
    "result": {"map": {"success": "success", "message": "message"}},
    "description": "Read the multiplexer's current velocity source; the callback only reports the stored string.",
}

#: One explicit geometry_msgs/TwistStamped publication on the teleop input.
#: A rosbridge publication is transmission-only: it does not establish that
#: the multiplexer, Gazebo or the vehicle received or executed the command.
_TELEOP_COMMAND = {
    "topic": "/robot1/cmd_vel/teleop",
    "type": "geometry_msgs/msg/TwistStamped",
    "operation": "publish",
    "source_name": "cmd_vel/teleop",
    "source_ref": _TELEOP_TOPIC_REF,
    "type_ref": _TYPE_REF,
    "message": {
        "header": {},
        "twist": {
            "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
    },
    "args": {
        "twist.linear.x": {"from": "input.speed"},
        "twist.angular.z": {"from": "input.steering_angle"},
    },
    "description": (
        "Publish one speed and steering-angle command to the teleop multiplexer input.  The multiplexer "
        "caches the last message per source and repeats it at its publish rate while that source is selected."
    ),
}

#: The active Gazebo model's drive plugin clamps commands at an absolute 10.0 m/s and 0.6458 rad
#: (model.urdf:409-417).  Those are simulator clamps, not a source-stated command envelope, and the
#: cited lines state no negative bound, so both inputs are operator_required.
_SPEED_LIMIT = Limit.operator_required(
    "no command envelope is stated: the race-car plugin clamps the absolute speed at 10.0 m/s and "
    "race_car.yaml records 1.5; the operator sets the site speed range"
)
_STEER_LIMIT = Limit.operator_required(
    "no command envelope is stated: the race-car plugin clamps the absolute steering angle at "
    "0.6458 rad; the operator sets the site steering range"
)

_SOURCE = Field(
    "string",
    enum=["OFF", "wallfollowing", "teleop", "nav2", "cacc"],
    description="Configured multiplexer source name; OFF selects the zero-command branch",
)
_PUBLISHED = {
    "published": Field("boolean", description="True when rosbridge accepted the topic publication"),
    "confirmed": Field("boolean", description="Always false: a publication carries no execution confirmation"),
}
_SELECT_OUTPUT = {
    "success": Field("boolean", description="True when the multiplexer accepted the source name"),
    "message": Field("string", description="Upstream response message naming the selected source"),
}
_STATUS_OUTPUT = {
    "success": Field("boolean", description="True when the status callback returned"),
    "message": Field("string", description="Upstream message of the form 'Current source: <name>'"),
}
_STOP_OUTPUT = {
    "source_off": Field("boolean", description="True when the multiplexer acknowledged the OFF source"),
}


class Auna(RosDriver):
    device_id = "auna"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeAuna"}
    tags = ["ros", "ros2", "gazebo", "simulation", "mobile-base", "cmd-vel", "ackermann"]
    display_name = "AuNa Gazebo Ackermann race car"
    vendor = "Harun Teper"
    model = "race_car"
    facts = [
        Fact("The control configuration declares four multiplexer inputs (wallfollowing AckermannDriveStamped "
             "on cmd_vel/wallfollowing, teleop TwistStamped on cmd_vel/teleop, cacc Twist on cmd_vel/cacc, nav2 "
             "Twist on cmd_vel/nav2) and three outputs (cmd_vel_twist Twist, cmd_vel_twist_stamped "
             "TwistStamped, cmd_vel_ackermann AckermannDriveStamped).",
             source="upstream_code", ref=_TOPIC_CONFIG_REF),
        Fact("The multiplexer node starts with current_source_ set to OFF unless initial_source names a "
             "configured source, and initializes estop_active_ to false.", source="upstream_code", ref=_INIT_REF),
        Fact("The constructor registers the relative toggle_cmd_vel_source (auna_msgs/SetString), "
             "get_source_status, get_input_sources and debug_state (std_srvs/Trigger) services, plus the "
             "absolute /trigger_emergency_stop (std_srvs/SetBool) and /get_estop_status (std_srvs/Trigger) "
             "services, on the multiplexer node.", source="upstream_code", ref=_SERVICE_REF),
        Fact("toggleSourceCallback sets current_source_ to OFF for the literal OFF, accepts a configured input "
             "name, and returns success=false with a message for an unknown source.",
             source="upstream_code", ref=_SOURCE_CALLBACK_REF),
        Fact("getSourceStatusCallback sets success=true and returns 'Current source: ' followed by the stored "
             "source name.", source="upstream_code", ref=_STATUS_CALLBACK_REF),
        Fact("The publish timer uses the last received message of the selected source, or createZeroAckermann "
             "when the source is OFF or has no message, and publishes it on every configured output.",
             source="upstream_code", ref=_TIMER_REF),
        Fact("The multiplexer declares publish_rate with a default of 20.0 Hz.",
             source="upstream_code", ref=_RATE_REF),
        Fact("createZeroAckermann sets drive.speed and drive.steering_angle to 0.0.",
             source="upstream_code", ref=_ZERO_REF),
        Fact("twist_to_ackermann copies TwistStamped.linear.x to drive.speed and TwistStamped.angular.z to "
             "drive.steering_angle.", source="upstream_code", ref=_CONVERT_REF),
        Fact("setupSubscribers creates a TwistStamped subscription for each configured source whose declared "
             "type is TwistStamped.", source="upstream_code", ref=_SUBSCRIBE_REF),
        Fact("twist_callback stores twist_to_ackermann(msg) in last_received_msgs_ under the source name.",
             source="upstream_code", ref=_CALLBACK_REF),
        Fact("The shipped control parameters set publish_rate 20.0, wheelbase 0.32 and "
             "convert_yaw_to_steering_angle false for every cmd_vel_multiplexer_node.",
             source="upstream_code", ref=_PARAM_REF),
        Fact("The timer converts the steering angle from a yaw rate with the wheelbase only when "
             "convert_yaw_to_steering_angle is true.", source="upstream_code",
             ref="packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:392-401"),
        Fact("The launch reads ROBOT_INDEX (default '0') and INITIAL_SOURCE (default 'OFF') from the environment "
             "and builds the namespace robot{ROBOT_INDEX}.", source="upstream_code", ref=_LAUNCH_REF),
        Fact("The launch builds param_file from auna_common/config/control/params.yaml and topic_file from "
             "auna_common/config/control/topics.yaml, and starts the multiplexer node with that namespace, "
             "those files and initial_source.", source="upstream_code", ref=_LAUNCH_NODE_REF),
        Fact("docker-compose.yml runs cmd_multiplexer_robot1 with ROBOT_INDEX=1 and INITIAL_SOURCE=OFF.",
             source="upstream_code", ref=_COMPOSE_MUX_REF),
        Fact("docker-compose.yml's teleop service, in the teleop and manual_control profiles, runs "
             "auna_teleoperation keyboard_teleop_hold.", source="upstream_code", ref=_COMPOSE_TELEOP_REF),
        Fact("The teleop node declares publish_rate 10.0 and base_namespace robot, creates its first publisher "
             "for the namespace robot0 and calls _publish from a timer at publish_rate.",
             source="upstream_code", ref=_TELEOP_NODE_REF),
        Fact("The teleop node publishes on /{namespace}/cmd_vel/teleop as TwistStamped or Twist.",
             source="upstream_code", ref=_TELEOP_TOPIC_NODE_REF),
        Fact("The control panel creates clients for the absolute /trigger_emergency_stop and /get_estop_status "
             "and for the namespaced get_source_status, get_input_sources and toggle_cmd_vel_source services.",
             source="upstream_code", ref=_PANEL_REF),
        Fact("The F1TENTH vesc.launch.py defines vesc_driver_node (vesc_driver), vesc_to_odom_node and "
             "ackermann_to_vesc_node (vesc_ackermann) with its namespace launch configuration.",
             source="upstream_code", ref=_F110_REF),
        Fact("The race-car Gazebo model loads libgazebo_ros_ackermann_drive.so, declares max_steer 0.6458 rad "
             "with the comment that a greater cmd_vel angular z is capped, and declares max_speed 10.0 m/s "
             "as the maximum absolute linear speed.", source="upstream_code", ref=_PLUGIN_REF),
        Fact("The race-car plugin remaps cmd_vel to cmd_vel_twist and odom to odom.",
             source="upstream_code", ref=_REMAP_REF),
        Fact("The shipped race_car model-parameter file records drive max_steer 0.6458 and max_speed 1.5 under "
             "robot.plugins.drive.", source="upstream_code", ref=_MODEL_PARAM_REF),
    ]
    safe_state = (
        "The multiplexer velocity source is set to OFF and its timer publishes zero speed and steering commands "
        "on cmd_vel_twist; the service acknowledgement is not sensed vehicle quiescence, the cached source "
        "message is retained, and re-selecting a source re-publishes the cached command. Any client of "
        "toggle_cmd_vel_source, such as the control panel, can re-select a source while MHS is latched."
    )
    #: The deployed backend is an analytic ROS-free stand-in; it runs no Gazebo
    #: physics, no multiplexer node and no vehicle.
    fidelity = {
        "engine": "analytic:ROS-free multiplexer contract stand-in (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven fake with no wall-clock timer or Gazebo step; placeholder source and "
                     "command state do not establish trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free analytic stand-in: it answers the declared multiplexer services and "
            "teleop topic but runs no cmd_vel_multiplexer_node, rosbridge, Gazebo, physics or vehicle",
            "the fake does not repeat the cached command at the node's 20 Hz timer; it records only the last "
            "publication, so it cannot demonstrate continuous motion or stopping time",
            "the fake does not model the Gazebo ackermann drive plugin's speed, steering, collision, tyre or "
            "terrain behaviour; the plugin limits are recorded as source facts",
            "the upstream model-parameter file records 1.5 m/s while the active model.urdf plugin records "
            "10.0 m/s; the package uses the active plugin bound and the example site overlay narrows to 1.5",
            "the absolute /trigger_emergency_stop and /get_estop_status services are not bound because every "
            "namespaced multiplexer creates the same absolute names; per-robot stop is the namespaced "
            "toggle_cmd_vel_source service",
            "the source-OFF stop is a software source change, not an independent hardware emergency stop; the "
            "upstream service acknowledgement does not sense that the simulated vehicle has stopped",
            "selecting a non-OFF source re-publishes the multiplexer's cached last command for that source, so "
            "the operator must publish the intended command before selecting the source after a stop",
            "the driver assumes the shipped convert_yaw_to_steering_angle=false configuration; if an operator "
            "sets it true, the input angular.z is treated as a yaw rate and is converted to a steering angle",
            "speed and steering are operator_required: the plugin's absolute 10.0 m/s and 0.6458 rad are "
            "clamps the simulator applies, not a stated command envelope; the example overlay uses 1.5 m/s "
            "and 0.6458 rad",
            "the shipped keyboard teleop (docker-compose teleop and manual_control profiles) publishes "
            "/robotN/cmd_vel/teleop at 10 Hz on the namespace it selects, overwriting this package's cached "
            "teleop command; the nav2, wallfollowing and CACC nodes publish the other inputs",
            "any client of toggle_cmd_vel_source (the RViz control panel, another rosbridge client) can "
            "re-select a source while the MHS latch is held; the fake has no other client",
            "the clone also ships an F1TENTH platform launch with a VESC motor driver; nothing in the clone "
            "connects the multiplexer's cmd_vel_ackermann output to it, but a deployment that remaps it would "
            "drive a real car through this package",
        ],
    }
    commands = {
        "x-cap.harunteper.velocity_source.v1": _SOURCE_SELECT,
        "x-cap.harunteper.teleop_velocity.v1": _TELEOP_COMMAND,
        "x-cap.harunteper.source_status.v1": _SOURCE_STATUS,
        "x-cap.harunteper.stop.v1": _OFF_STOP,
    }
    actions = {
        "x-cap.harunteper.velocity_source.v1": Action(
            name="select_velocity_source",
            verb="invoke",
            risk="R2",
            description=(
                "Select one configured multiplexer input source.  Selecting OFF stops forwarding and makes the "
                "timer publish zero commands; selecting a motion source can immediately re-publish that "
                "source's cached last command."
            ),
            input={"source": _SOURCE},
            output=_SELECT_OUTPUT,
            examples=[{"source": "teleop"}],
        ),
        "x-cap.harunteper.teleop_velocity.v1": Action(
            name="publish_teleop_velocity",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one speed and steering-angle command on the teleop multiplexer input.  The multiplexer "
                "caches it and repeats it at its timer rate only while the teleop source is selected.  The "
                "receipt confirms transmission to rosbridge, not motion, arrival or stopping."
            ),
            input={
                "speed": Field(
                    "number",
                    unit="m/s",
                    description="Forward speed written to twist.linear.x; negative values reverse",
                    limit=_SPEED_LIMIT,
                ),
                "steering_angle": Field(
                    "number",
                    unit="rad",
                    description="Steering angle written to twist.angular.z and copied to drive.steering_angle",
                    limit=_STEER_LIMIT,
                ),
            },
            output=_PUBLISHED,
            examples=[{"speed": 0.0, "steering_angle": 0.0}],
        ),
        "x-cap.harunteper.source_status.v1": Action(
            name="read_velocity_source",
            verb="read",
            description="Read the multiplexer's stored current velocity source through its Trigger service",
            output=_STATUS_OUTPUT,
        ),
        "x-cap.harunteper.stop.v1": Action(
            name="stop_velocity_source",
            safe_state=True,
            description=(
                "Set the multiplexer velocity source to OFF, making its timer publish zero speed and steering "
                "commands.  Input-free, acknowledged service call; no input is accepted during the latch."
            ),
            output=_STOP_OUTPUT,
        ),
    }
    #: The namespaced source-OFF service is the per-robot stop.  The absolute
    #: /trigger_emergency_stop service is not robot-scoped.
    safety_bindings = {"estop": _OFF_STOP}
