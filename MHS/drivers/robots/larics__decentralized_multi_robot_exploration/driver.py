"""OpenMHS rosbridge driver for the Stage multi-robot exploration environment.

The pinned repository is a ROS 1 simulation setup for decentralised multi-robot
exploration.  It vendors Google Cartographer, the ROS navigation stack and a
private fork of ``stage_ros`` (``stage_ros_private``).  The executable
environment node is the C++ ``stageros`` node of that fork.  This package is a
configuration-only :class:`RosDriver` over rosbridge; it declares no Python
native class and does not launch Stage, ROS, rosbridge, Cartographer or any
navigation node.

The served surface is the simulation environment's observable state and its
primary velocity input:

* two ``geometry_msgs/Twist`` publications on ``/robot_0/cmd_vel`` and
  ``/robot_1/cmd_vel`` (the Stage position-model command input);
* resource fields ``robot_0_twist`` and ``robot_1_twist``, each the
  ``twist.twist`` of the first sample on a new subscription of that robot's
  odometry topic (the fake stores the last Twist it accepted there; this is
  not a Stage measurement);
* ``/robot_0/base_scan`` and ``/robot_1/base_scan`` LaserScan observations;
* ``/robot_0/odom`` and ``/robot_1/odom`` Odometry observations;
* the simulated ``/clock`` sample and the exploration stack's
  ``/filtered_frontiers`` output;
* the clone's ``/reset_positions`` ``std_srvs/Empty`` service is not bound.
  It teleports every position model and leaves the last commanded speed, so
  it is not a reset (SAFE-042).

The clone has no acknowledged stop, pause or brake service or action.  A zero
Twist on ``cmd_vel`` only calls ``ModelPosition::SetSpeed`` and proves nothing
by itself.  The e-stop is a sensed-confirmation stop (SAFE-049, simulated
devices only): it publishes that zero Twist on ``/robot_0/cmd_vel`` and
``/robot_1/cmd_vel`` and is achieved only when both odometry streams then show
the robots at rest inside the confirmation window.  A rosbridge publication
receipt is transmission-only.

Every endpoint, type and fact cites the pinned clone at
e7c9c304a4072b5b7177a91ce6383397525ac66a.  The fake is a ROS-free contract
transport; no ROS graph, Stage process, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The private Stage ROS fork and its topic-name defines.
_NAME_ODOM_REF = "stage_ros_private/src/stageros.cpp:65"
_NAME_SCAN_REF = "stage_ros_private/src/stageros.cpp:66"
_NAME_CMD_VEL_REF = "stage_ros_private/src/stageros.cpp:68"
_ODOM_REF = "stage_ros_private/src/stageros.cpp:371"
_CMD_VEL_REF = "stage_ros_private/src/stageros.cpp:373"
_SCAN_REF = "stage_ros_private/src/stageros.cpp:378"
_CLOCK_REF = "stage_ros_private/src/stageros.cpp:402"
_RESET_REF = "stage_ros_private/src/stageros.cpp:405"

#: Message and service type declarations in the same translation unit.
_LASERSCAN_TYPE_REF = "stage_ros_private/src/stageros.cpp:45"
_ODOM_TYPE_REF = "stage_ros_private/src/stageros.cpp:49"
_TWIST_TYPE_REF = "stage_ros_private/src/stageros.cpp:50"
_CLOCK_TYPE_REF = "stage_ros_private/src/stageros.cpp:51"

#: The per-robot namespacing helper and the command/watchdog/reset callbacks.
_MAPNAME_REF = "stage_ros_private/src/stageros.cpp:181-224"
_CMD_CALLBACK_REF = "stage_ros_private/src/stageros.cpp:273-280"
_WATCHDOG_REF = "stage_ros_private/src/stageros.cpp:443-448"
_WATCHDOG_PARAM_REF = "stage_ros_private/src/stageros.cpp:288-291"
_RESET_CALLBACK_REF = "stage_ros_private/src/stageros.cpp:260-268"
_ODOM_POSITION_X_REF = "stage_ros_private/src/stageros.cpp:539"
_ODOM_POSITION_Y_REF = "stage_ros_private/src/stageros.cpp:540"
_ODOM_LINEAR_X_REF = "stage_ros_private/src/stageros.cpp:543"
_ODOM_LINEAR_Y_REF = "stage_ros_private/src/stageros.cpp:544"
_ODOM_ANGULAR_Z_REF = "stage_ros_private/src/stageros.cpp:545"
_ODOM_FILL_REF = "stage_ros_private/src/stageros.cpp:539-554"
_INTERVAL_SIM_REF = "frontier_exploration/stage-worlds/pioneer3dx-sick.world:321"
_INTERVAL_SIM_UNIT_REF = "stage_ros_private/world/willow-erratic.world:61"
_ASSIGNER_GOAL_REF = "frontier_exploration/scripts/decent_robot_assigner.py:246"

#: The shipped world fixes the laser shape and the number of position models.
_WORLD_REF = "frontier_exploration/stage-worlds/pioneer3dx-sick.world:296-319"
_LASER_REF = "frontier_exploration/stage-worlds/pioneer3dx-sick.world:235-243"
_TWO_ROBOTS_REF = "frontier_exploration/launch/multi_robot_assigner.launch:1-10"
_N_ROBOTS_REF = "frontier_exploration/launch/robot_assigner.launch:6-10"
_STAGE_LAUNCH_REF = "frontier_exploration/launch/stage-pioneer-3dx-sick.launch:17-19"

#: The navigation launch and move_base's velocity publisher (a competing cmd_vel source).
_NAV_LAUNCH_REF = "frontier_exploration/launch/multi_robot_navigation.launch:1-10"
_NAV_NODE_REF = "frontier_exploration/launch/navigation.launch:3-6"
_MOVE_BASE_PUB_REF = "navigation/move_base/src/move_base.cpp:91-92"

#: The exploration stack's own output topic and type.
_FRONTIERS_REF = "frontier_exploration/scripts/frontier_filter.py:24"
_FRONTIERS_TYPE_REF = "frontier_exploration/scripts/frontier_filter.py:13"
_FRONTIERS_LAUNCH_REF = "frontier_exploration/launch/robot_assigner.launch:9"

#: No source states a velocity envelope for ModelPosition::SetSpeed.  The
#: driver asks the operator for both bounds instead of copying a demo constant.
_LINEAR_LIMIT = Limit.operator_required(
    "the pinned clone forwards the Twist linear.x to ModelPosition::SetSpeed and states no velocity "
    "bound; the operator supplies the linear speed envelope for this simulated deployment"
)
_ANGULAR_LIMIT = Limit.operator_required(
    "the pinned clone forwards the Twist angular.z to ModelPosition::SetSpeed and states no yaw-rate "
    "bound; the operator supplies the angular speed envelope for this simulated deployment"
)

_CLOCK_OUTPUT = {
    "secs": Field("integer", unit="s", description="Whole seconds of simulated time from the Clock message"),
    "nsecs": Field("integer", unit="ns", description="Nanoseconds within the simulated second"),
}
_SCAN_OUTPUT = {
    "frame_id": Field("string", description="Laser frame id from the LaserScan header"),
    "angle_min": Field("number", unit="rad", description="Start angle of the first range sample"),
    "angle_max": Field("number", unit="rad", description="End angle of the last range sample"),
    "angle_increment": Field("number", unit="rad", description="Angular distance between adjacent samples"),
    "range_min": Field("number", unit="m", description="Minimum range reported by the ranger"),
    "range_max": Field("number", unit="m", description="Maximum range reported by the ranger"),
    "ranges": Field("array", unit="m", description="One measured range per angular sample",
                    items=Field("number", unit="m", description="Range in metres at one sample")),
    "intensities": Field("array", unit="1", description="One intensity value per angular sample",
                         items=Field("number", unit="1", description="Intensity at one sample")),
}
_ODOM_OUTPUT = {
    "frame_id": Field("string", description="Odometry header frame id"),
    "child_frame_id": Field("string", description="Odometry child frame id"),
    "position_x": Field("number", unit="m", description="Estimated position x"),
    "position_y": Field("number", unit="m", description="Estimated position y"),
    "position_z": Field("number", unit="m", description="Estimated position z"),
    "orientation_x": Field("number", unit="1", description="Estimated orientation quaternion x"),
    "orientation_y": Field("number", unit="1", description="Estimated orientation quaternion y"),
    "orientation_z": Field("number", unit="1", description="Estimated orientation quaternion z"),
    "orientation_w": Field("number", unit="1", description="Estimated orientation quaternion w"),
    "linear_x": Field("number", unit="m/s", description="Estimated linear velocity x"),
    "linear_y": Field("number", unit="m/s", description="Estimated linear velocity y"),
    "linear_z": Field("number", unit="m/s", description="Estimated linear velocity z"),
    "angular_x": Field("number", unit="rad/s", description="Estimated angular velocity x"),
    "angular_y": Field("number", unit="rad/s", description="Estimated angular velocity y"),
    "angular_z": Field("number", unit="rad/s", description="Estimated angular velocity z"),
}
_FRONTIERS_OUTPUT = {
    "points": Field("array", description="Filtered frontier centroids from the exploration stack",
                    items=Field("object", description="One frontier centroid",
                                properties={
                                    "x": Field("number", unit="m", description="Frontier x in the map frame"),
                                    "y": Field("number", unit="m", description="Frontier y in the map frame"),
                                    "z": Field("number", unit="m", description="Frontier z in the map frame"),
                                })),
}
_CMD_VEL_OUTPUT = {
    "published": Field("boolean", description="True when the driver handed the Twist to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution confirmation"),
}


def _twist_axis(unit: str, text: str) -> Field:
    return Field("number", unit=unit, description=text)


def _odom_twist_field(robot: str) -> Field:
    """Resource field for one robot: the first odom sample's twist, not a measurement."""
    return Field(
        "object",
        description=(
            f"twist.twist from the first sample of a new /{robot}/odom subscription. On the fake this is the "
            f"last Twist stored for /{robot}/cmd_vel, not GetVelocity and not a Stage measurement. A live "
            "subscriber receives the next WorldCallback publish, and the cmd_vel command does not wait for it."
        ),
        properties={
            "linear": Field(
                "object",
                description="Linear components of that odometry twist",
                properties={
                    "x": _twist_axis("m/s", "twist.twist.linear.x of the sample"),
                    "y": _twist_axis("m/s", "twist.twist.linear.y of the sample"),
                    "z": _twist_axis("m/s", "twist.twist.linear.z of the sample; WorldCallback does not assign it"),
                },
            ),
            "angular": Field(
                "object",
                description="Angular components of that odometry twist",
                properties={
                    "x": _twist_axis("rad/s", "twist.twist.angular.x of the sample; WorldCallback does not assign it"),
                    "y": _twist_axis("rad/s", "twist.twist.angular.y of the sample; WorldCallback does not assign it"),
                    "z": _twist_axis("rad/s", "twist.twist.angular.z of the sample"),
                },
            ),
        },
    )


def _odom_twist_read(robot: str) -> dict:
    """One resource read. Ordinary subscriptions keep the first sample (the fake's stored echo)."""
    return {
        "topic": f"/{robot}/odom",
        "type": "nav_msgs/Odometry",
        "operation": "subscribe",
        "source_name": "odom",
        "source_ref": _NAME_ODOM_REF,
        "type_ref": _ODOM_TYPE_REF,
        "path": "twist.twist",
        "timeout_ms": 1000,
    }
#: Sensed-confirmation stop (SAFE-049, simulated only).  Each request step is a
#: fixed zero Twist.  cmdvelReceived copies linear.x, linear.y and angular.z
#: into ModelPosition::SetSpeed (stageros.cpp:276-278) and publishes nothing
#: back, so the publication proves nothing.  The confirmation reads the two
#: odometry topics WorldCallback fills from est_pose and GetVelocity and stamps
#: with sim_time (stageros.cpp:539-551).  ROS 1 declares no history: the
#: advertise call passes a queue length and no latch (stageros.cpp:371), and
#: the bridge discards the first sample.  Every threshold is operator_required.
#: The client bounds are a package choice for the fake; a live simulation sets
#: its own in simulation_deployment['estop_confirmation'].  The shipped world
#: sets interval_sim 100 (pioneer3dx-sick.world:321); a sibling world comments
#: that this is a simulation timestep in milliseconds (willow-erratic.world:61),
#: so max_gap_ms 500 sits above one update and a slower-than-realtime run fails
#: closed until the operator raises it.
_NO_SPEED_BOUND = (
    "the clone states no at-rest bound for the odometry twist; the operator supplies the largest absolute "
    "speed that counts as stopped"
)
_NO_SPAN_BOUND = (
    "the clone states no at-rest bound for the odometry position; the operator supplies the largest change "
    "over the confirmation window that counts as stopped"
)
_ODOM_FILL = {
    "pose.pose.position.x": _ODOM_POSITION_X_REF,
    "pose.pose.position.y": _ODOM_POSITION_Y_REF,
    "twist.twist.linear.x": _ODOM_LINEAR_X_REF,
    "twist.twist.linear.y": _ODOM_LINEAR_Y_REF,
    "twist.twist.angular.z": _ODOM_ANGULAR_Z_REF,
}


def _zero_twist(robot: str) -> dict:
    """One fixed zero Twist for one Stage position model.  Repeating it calls SetSpeed(0, 0, 0) again."""
    return {
        "topic": f"/{robot}/cmd_vel",
        "type": "geometry_msgs/Twist",
        "source_name": "cmd_vel",
        "source_ref": _NAME_CMD_VEL_REF,
        "type_ref": _TWIST_TYPE_REF,
        "timeout_ms": 1000,
        "message": {"linear": {"x": 0.0, "y": 0.0, "z": 0.0}, "angular": {"x": 0.0, "y": 0.0, "z": 0.0}},
        "description": f"a zero Twist on /{robot}/cmd_vel (transmission only; SetSpeed of the three axes)",
    }


def _odom_source(robot: str) -> dict:
    return {
        "topic": f"/{robot}/odom",
        "type": "nav_msgs/Odometry",
        "source_name": "odom",
        "source_ref": _NAME_ODOM_REF,
        "type_ref": _ODOM_TYPE_REF,
        "fill_refs": dict(_ODOM_FILL),
    }


def _rest_terms(source: str, prefix: str) -> list:
    speed = Limit.operator_required(_NO_SPEED_BOUND)
    span = Limit.operator_required(_NO_SPAN_BOUND)
    return [
        {"source": source, "path": "twist.twist.linear.x", "name": f"{prefix}_linear_x", "unit": "m/s",
         "abs_max": speed},
        {"source": source, "path": "twist.twist.linear.y", "name": f"{prefix}_linear_y", "unit": "m/s",
         "abs_max": speed},
        {"source": source, "path": "twist.twist.angular.z", "name": f"{prefix}_angular_z", "unit": "rad/s",
         "abs_max": speed},
        {"source": source, "path": "pose.pose.position.x", "name": f"{prefix}_x", "unit": "m", "span_max": span},
        {"source": source, "path": "pose.pose.position.y", "name": f"{prefix}_y", "unit": "m", "span_max": span},
    ]


_SENSED_STOP = {
    "request": [_zero_twist("robot_0"), _zero_twist("robot_1")],
    "sources": {"odom_0": _odom_source("robot_0"), "odom_1": _odom_source("robot_1")},
    "predicate": _rest_terms("odom_0", "r0") + _rest_terms("odom_1", "r1"),
    "consecutive": 3,
    "min_span_ms": 200,
    "max_gap_ms": 500,
    "confirm_within_ms": 1500,
    "description": (
        "zero Twists commanded on /robot_0/cmd_vel and /robot_1/cmd_vel, and both odometry streams sensed "
        "at rest within the confirmation window"
    ),
}


def _cmd_vel(robot: str) -> dict:
    """One relative-topic Twist publication for one Stage position model."""
    return {
        "topic": f"/{robot}/cmd_vel",
        "type": "geometry_msgs/Twist",
        "operation": "publish",
        "source_name": "cmd_vel",
        "source_ref": _NAME_CMD_VEL_REF,
        "type_ref": _TWIST_TYPE_REF,
        "message": {
            "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
        "args": {
            "linear.x": {"from": "input.linear_velocity"},
            "angular.z": {"from": "input.angular_velocity"},
        },
        "result": {"published": {"value": True}, "confirmed": {"value": False}},
    }


def _scan(robot: str) -> dict:
    return {
        "topic": f"/{robot}/base_scan",
        "type": "sensor_msgs/LaserScan",
        "operation": "subscribe",
        "source_name": "base_scan",
        "source_ref": _NAME_SCAN_REF,
        "type_ref": _LASERSCAN_TYPE_REF,
        "path": "$",
        "result": {"map": {
            "frame_id": "output.header.frame_id",
            "angle_min": "output.angle_min",
            "angle_max": "output.angle_max",
            "angle_increment": "output.angle_increment",
            "range_min": "output.range_min",
            "range_max": "output.range_max",
            "ranges": "output.ranges",
            "intensities": "output.intensities",
        }},
    }


def _odom(robot: str) -> dict:
    return {
        "topic": f"/{robot}/odom",
        "type": "nav_msgs/Odometry",
        "operation": "subscribe",
        "source_name": "odom",
        "source_ref": _NAME_ODOM_REF,
        "type_ref": _ODOM_TYPE_REF,
        "path": "$",
        "result": {"map": {
            "frame_id": "output.header.frame_id",
            "child_frame_id": "output.child_frame_id",
            "position_x": "output.pose.pose.position.x",
            "position_y": "output.pose.pose.position.y",
            "position_z": "output.pose.pose.position.z",
            "orientation_x": "output.pose.pose.orientation.x",
            "orientation_y": "output.pose.pose.orientation.y",
            "orientation_z": "output.pose.pose.orientation.z",
            "orientation_w": "output.pose.pose.orientation.w",
            "linear_x": "output.twist.twist.linear.x",
            "linear_y": "output.twist.twist.linear.y",
            "linear_z": "output.twist.twist.linear.z",
            "angular_x": "output.twist.twist.angular.x",
            "angular_y": "output.twist.twist.angular.y",
            "angular_z": "output.twist.twist.angular.z",
        }},
    }


def _cmd_vel_action(robot: str) -> Action:
    return Action(
        name="publish_cmd_vel",
        risk="R2",
        description=(
            f"Publish one geometry_msgs/Twist velocity setpoint to the {robot} Stage position model. "
            "The receipt reports only that rosbridge accepted the publication. The next read of "
            f"{robot}_twist is the first sample of a new /{robot}/odom subscription; the fake stores this "
            "Twist there, which is not a Stage measurement."
        ),
        input={
            "linear_velocity": Field(
                "number", unit="m/s",
                description=f"Forward velocity for {robot}; mapped to Twist linear.x",
                limit=_LINEAR_LIMIT,
            ),
            "angular_velocity": Field(
                "number", unit="rad/s",
                description=f"Yaw rate for {robot}; mapped to Twist angular.z",
                limit=_ANGULAR_LIMIT,
            ),
        },
        output=_CMD_VEL_OUTPUT,
    )


class DecentralizedMultiRobotExploration(RosDriver):
    """Configuration-only ROS 1 rosbridge driver for the Stage exploration world."""

    device_id = "stage_multi_robot"
    device_kind = "world.sim"
    mode = "simulated"
    # REVIEW.md item 12: the commands publish geometry_msgs/Twist on cmd_vel.
    # A physical mobile base behind the same bridge would act on that topic, so
    # the hazard is the mobile base's (R2) however simulated the deployment.
    # The card's floor stays R0.  The third pioneer model is not commanded.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeDecentralizedMultiRobotExploration"}
    tags = ["ros", "ros1", "stage", "simulation", "multi-robot", "exploration", "laser"]
    display_name = "Stage decentralised multi-robot exploration world"
    vendor = "LARICS"
    model = "stage_ros_private pioneer3dx"
    facts = [
        Fact("The repository sets up a decentralised multi-robot exploration simulation with the 2D Stage "
             "simulator and a map from Google Cartographer.",
             source="vendor_doc", ref="README.md:1-2"),
        Fact("The Stage launch starts the package's private stageros node against the shipped pioneer3dx-sick "
             "world file.",
             source="upstream_code", ref=_STAGE_LAUNCH_REF),
        Fact("The shipped world places three pioneer3dx models named pioneer0, pioneer1 and pioneer2, each with "
             "a fixed pose and a fancysicklaser.",
             source="upstream_code", ref=_WORLD_REF),
        Fact("The shipped sicklaser ranger declares range [ 0.0 20.0 ], fov 365.0 and 1081 samples.",
             source="upstream_code", ref=_LASER_REF),
        Fact("robot_assigner.launch sets the assigner's n_robots parameter to 2.",
             source="upstream_code", ref=_N_ROBOTS_REF),
        Fact("The multi-robot assigner launch includes robot_assigner.launch for robot index 0 and robot "
             "index 1.",
             source="upstream_code", ref=_TWO_ROBOTS_REF),
        Fact("StageNode::mapName returns the relative name robot_<id>/<name> when more than one position "
             "model is present, unless use_model_names is set and the model token has no colon.",
             source="upstream_code", ref=_MAPNAME_REF),
        Fact("SubscribeModels advertises nav_msgs/Odometry on the mapName(ODOM) topic for each position model, "
             "with queue length 10.",
             source="upstream_code", ref=_ODOM_REF),
        Fact("SubscribeModels creates a geometry_msgs/Twist subscription on the mapName(CMD_VEL) topic for each "
             "position model.",
             source="upstream_code", ref=_CMD_VEL_REF),
        Fact("SubscribeModels advertises a sensor_msgs/LaserScan on the mapName(BASE_SCAN) topic for each laser "
             "model.",
             source="upstream_code", ref=_SCAN_REF),
        Fact("SubscribeModels advertises rosgraph_msgs/Clock on the absolute /clock topic.",
             source="upstream_code", ref=_CLOCK_REF),
        Fact("SubscribeModels advertises the relative reset_positions service with std_srvs/Empty.",
             source="upstream_code", ref=_RESET_REF),
        Fact("cmdvelReceived passes the Twist linear.x, linear.y and angular.z to ModelPosition::SetSpeed and "
             "records the simulated time of the last command.",
             source="upstream_code", ref=_CMD_CALLBACK_REF),
        Fact("WorldCallback zeroes every position model's speed only when base_watchdog_timeout is greater than "
             "0 and the simulated time since the last command reaches that timeout.",
             source="upstream_code", ref=_WATCHDOG_REF),
        Fact("WorldCallback sets odometry pose.pose.position.x and position.y from est_pose, twist.twist.linear.x, "
             "linear.y and angular.z from GetVelocity, and header.stamp from sim_time, then publishes the message.",
             source="upstream_code", ref=_ODOM_FILL_REF),
        Fact("base_watchdog_timeout is a ROS parameter whose default is 0.2 s when the parameter is not set.",
             source="upstream_code", ref=_WATCHDOG_PARAM_REF),
        Fact("cb_reset_srv sets every position model to its stored initial pose and clears SetStall, then "
             "returns true; it does not set the commanded speed to zero.",
             source="upstream_code", ref=_RESET_CALLBACK_REF),
        Fact("frontier_filter publishes the relative filtered_frontiers topic as frontier_exploration/PointArray.",
             source="upstream_code", ref=_FRONTIERS_REF),
        Fact("The exploration launch reads /filtered_frontiers as the assigner's frontier topic.",
             source="upstream_code", ref=_FRONTIERS_LAUNCH_REF),
        Fact("multi_robot_navigation.launch includes navigation.launch with robot_name robot_0 and with "
             "robot_name robot_1.",
             source="upstream_code", ref=_NAV_LAUNCH_REF),
        Fact("navigation.launch starts move_base in the namespace given by robot_name.",
             source="upstream_code", ref=_NAV_NODE_REF),
        Fact("MoveBase advertises a geometry_msgs::Twist publisher on the relative cmd_vel topic.",
             source="upstream_code", ref=_MOVE_BASE_PUB_REF),
        Fact("The assigner calls sendGoal.",
             source="upstream_code", ref=_ASSIGNER_GOAL_REF),
        Fact("The shipped pioneer3dx-sick world sets interval_sim 100.",
             source="upstream_code", ref=_INTERVAL_SIM_REF),
        Fact("A Stage world file in the clone comments that interval_sim 100 is a simulation timestep in "
             "milliseconds.",
             source="upstream_code", ref=_INTERVAL_SIM_UNIT_REF),
    ]
    safe_state = (
        "Simulated only: zero Twists on /robot_0/cmd_vel and /robot_1/cmd_vel, then both odom streams at rest "
        "for three fresh samples within the operator bounds. The zero Twist proves nothing. The watchdog can rest "
        "every model, including unsensed pioneer2, without that request, and 0 disables it. move_base on the same "
        "cmd_vel topics (assigners call sendGoal) fails the confirmation closed. Nothing is claimed after the window. "
        "/reset_positions teleports and leaves the last speed, so it is not this reset."
    )
    #: Two request steps at 1000 ms each plus confirm_within_ms 1500 ms.
    estop_latency_ms = 3500
    #: The fake is a ROS-free contract transport; it runs no Stage physics,
    #: laser ray casting, odometry integration, Cartographer mapping, frontier
    #: detection or move_base navigation.
    fidelity = {
        "engine": "analytic:ROS-free rosbridge contract fake (no Stage, no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven placeholder contract with no Stage step, no ray casting, no odometry "
                     "integration and no pacing; the same command does not reproduce a Stage trajectory",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake answers the declared ROS endpoints with placeholder messages; it runs no Stage world, "
            "no collision or laser ray casting, no odometry integration and no wall-clock pacing",
            "the laser ranges, intensities, odometry poses and frontier points are test data, not a recording "
            "of a Stage run and not a physics result",
            "robot_0_twist and robot_1_twist are the first sample of a new odometry subscription; the fake "
            "stores the last Twist it accepted on that robot's cmd_vel and reports it there, which is not "
            "GetVelocity and not a Stage measurement. A live subscriber receives the next WorldCallback "
            "publish, and the cmd_vel command does not wait for that publish",
            "the real shipped world has 1081 laser samples and three position models; this package serves the "
            "two robots configured by the exploration launch and a fake array whose length is a placeholder",
            "Cartographer mapping, the frontier detector, the frontier filter, move_base navigation and TF are "
            "outside this package",
            "no acknowledged stop, pause or brake endpoint exists; the e-stop is a sensed-confirmation stop "
            "(SAFE-049, simulated only) that publishes a zero Twist on /robot_0/cmd_vel and /robot_1/cmd_vel "
            "and is achieved only when both odometry streams then stay at rest for three consecutive fresh "
            "samples; the thresholds are operator_required (fake placeholders in fixtures/estop-confirmation.json) "
            "and the client bounds are a package choice, so a live deployment sets both in "
            "simulation_deployment['estop_confirmation']",
            "the confirmation proves the sensed state over its window only: WorldCallback also zeroes every "
            "position model once base_watchdog_timeout (default 0.2 s when unset, and skipped when the parameter "
            "is 0) elapses without a command, so the robots can be at rest without the zero Twist having been "
            "applied; a publisher that refreshes cmd_vel, including move_base, keeps the watchdog from firing "
            "and the confirmation fails closed",
            "the shipped world has three position models (pioneer0, pioneer1, pioneer2); this stop commands and "
            "senses only robot_0 and robot_1, the two the exploration launch configures, and pioneer2 is zeroed "
            "only by the watchdog",
            "with multi_robot_navigation.launch running, move_base publishes cmd_vel in each robot namespace "
            "while the assigners send it goals through sendGoal; those publications compete with this package "
            "and the stop then fails closed; nothing watches the robots after the confirmation window",
            "cb_reset_srv teleports every position model to its initial pose and clears stall without zeroing "
            "the commanded speed, so it is not bound as the reset and is not offered as a re-enable; the MHS "
            "reset re-confirms the sensed stop and changes nothing on the Stage models",
            "the odometry advertise call passes queue length 10 and no latch argument; this is ROS 1, so the "
            "bridge discards the first sample and no history is declared",
        ],
    }

    #: Read-only.  TCAP-003 hashes this resource.  The two cmd_vel publications
    #: return the same rosbridge receipt, so the effect is this echo: the fake
    #: stores the Twist and the next ordinary odom subscription's first sample
    #: reports it.  Nothing here is a Stage measurement.
    parameters = {
        "robot_0_twist": _odom_twist_field("robot_0"),
        "robot_1_twist": _odom_twist_field("robot_1"),
    }
    reads = {
        "robot_0_twist": _odom_twist_read("robot_0"),
        "robot_1_twist": _odom_twist_read("robot_1"),
    }
    commands = {
        "x-cap.larics.sim_clock.v1": {
            "topic": "/clock",
            "type": "rosgraph_msgs/Clock",
            "operation": "subscribe",
            "source_ref": _CLOCK_REF,
            "type_ref": _CLOCK_TYPE_REF,
            "path": "$",
            "result": {"map": {"secs": "output.clock.secs", "nsecs": "output.clock.nsecs"}},
        },
        "x-cap.larics.scan_robot0.v1": _scan("robot_0"),
        "x-cap.larics.scan_robot1.v1": _scan("robot_1"),
        "x-cap.larics.odom_robot0.v1": _odom("robot_0"),
        "x-cap.larics.odom_robot1.v1": _odom("robot_1"),
        "x-cap.larics.frontiers.v1": {
            "topic": "/filtered_frontiers",
            "type": "frontier_exploration/PointArray",
            "operation": "subscribe",
            "source_name": "filtered_frontiers",
            "source_ref": _FRONTIERS_REF,
            "type_ref": _FRONTIERS_TYPE_REF,
            "path": "$",
            "result": {"map": {"points": "output.points"}},
        },
        "x-cap.larics.cmd_vel_robot0.v1": _cmd_vel("robot_0"),
        "x-cap.larics.cmd_vel_robot1.v1": _cmd_vel("robot_1"),
    }
    actions = {
        "x-cap.larics.sim_clock.v1": Action(
            name="read_sim_clock",
            verb="read",
            description="Read one simulated clock sample published by Stage",
            output=_CLOCK_OUTPUT,
        ),
        "x-cap.larics.scan_robot0.v1": Action(
            name="read_scan_0",
            verb="read",
            description="Read one robot_0 LaserScan from the Stage environment",
            output=_SCAN_OUTPUT,
        ),
        "x-cap.larics.scan_robot1.v1": Action(
            name="read_scan_1",
            verb="read",
            description="Read one robot_1 LaserScan from the Stage environment",
            output=_SCAN_OUTPUT,
        ),
        "x-cap.larics.odom_robot0.v1": Action(
            name="read_odom_0",
            verb="read",
            description="Read one robot_0 odometry sample from the Stage environment",
            output=_ODOM_OUTPUT,
        ),
        "x-cap.larics.odom_robot1.v1": Action(
            name="read_odom_1",
            verb="read",
            description="Read one robot_1 odometry sample from the Stage environment",
            output=_ODOM_OUTPUT,
        ),
        "x-cap.larics.frontiers.v1": Action(
            name="read_frontiers",
            verb="read",
            description="Read the exploration stack's filtered frontier list",
            output=_FRONTIERS_OUTPUT,
        ),
        "x-cap.larics.cmd_vel_robot0.v1": _cmd_vel_action("robot_0"),
        "x-cap.larics.cmd_vel_robot1.v1": _cmd_vel_action("robot_1"),
    }
    # No acknowledged stop exists.  reset_positions teleports the models and leaves the last SetSpeed, so it
    # is not a safety reset and not a re-enable (SAFE-042).  The e-stop is the sensed-confirmation stop above.
    safety_bindings = {"sensed_stop": _SENSED_STOP}
