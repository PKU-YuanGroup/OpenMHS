"""OpenMHS rosbridge declaration for the map_simulator ROS 2 simulator.

The pinned upstream is a C++ ROS 2 node named ``simulator``.  It renders a
2-D OpenCV map, registers the absolute ``/simulator/spawn`` service and moves
each spawned robot from a per-robot ``cmd_vel`` subscription.  This package is
a configuration-only :class:`RosDriver`; it declares no Python native class and
neither imports nor launches the simulator.

The card names ``RosDriver`` and suggests ``cap.device.configure.v1`` with the
``Unicycle``/``Bicycle``/``Ackermann`` ``set_params`` methods.  Those methods
belong to the optional ``kinematics.py`` animation helper, not to the
simulator's ROS surface, and the spawn service is an effectful command with an
empty response.  The package therefore serves extension capabilities for the
spawn service, the Twist publication and the odometry and scan observations.

The pinned simulator registers no ROS stop, pause or removal service.  The
stop is a sensed confirmation (SAFE-049, simulated only): the e-stop publishes
one all-zero Twist on ``/robot1/cmd_vel``, which proves nothing by itself, and
is achieved only when fresh stamped ``/robot1/odom`` samples satisfy the
operator pose and twist bounds.  A duplicate spawn resets the pose and clears
the stored odometry twist; it is not a stop and is not a reset binding.

Every fact cites the pinned clone at
537a06464d7fcaa2cba4f4fea9532f0556854440.  The fake is a ROS-free canned
transport and runs no map_simulator, OpenCV, collision, laser or wall-clock
code.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: Default simulated-robot namespace used by the declared endpoints.  The
#: spawn executable takes the namespace of the node that runs it
#: (README.md:26); a deployment that uses another namespace must configure the
#: matching absolute endpoints or remap this single-robot declaration.
ROBOT_NAMESPACE = "/robot1"

#: The absolute spawn service registered by SimulatorNode.
_SPAWN_REF = "src/simulator.cpp:42-45"
_SPAWN_TYPE_REF = "include/map_simulator/simulator.h:7"

#: The odom publisher and cmd_vel subscription use the per-robot namespace.
_ODOM_REF = "src/robot.cpp:214"
_ODOM_TYPE_REF = "include/map_simulator/robot.h:8"
_CMD_VEL_REF = "src/robot.cpp:219-226"
_TWIST_TYPE_REF = "include/map_simulator/robot.h:9"

#: The default scan topic and the fallback scan publisher.
_SCAN_TOPIC_REF = "src/robot.cpp:131-132"
_SCAN_REF = "src/robot.cpp:194-211"
_SCAN_TYPE_REF = "include/map_simulator/robot.h:6"

#: The robot lifecycle: the description handshake and the pose/twist reset.
_DESCRIPTION_REF = "src/robot.cpp:113-126"
_RESET_REF = "include/map_simulator/robot.h:135-143"
_REFRESH_REF = "src/simulator.cpp:114-136"
_RATE_REF = "src/simulator.cpp:17-40"

#: The simulator class declaration (two service members: spawn and anchor).
_SERVICE_MEMBERS_REF = "include/map_simulator/simulator.h:17-44"

#: The Spawn service request constants and the empty response.
_SPAWN_SRV_REF = "srv/Spawn.srv:1-19"


_VECTOR3 = Field(
    "object",
    description="Three-component ROS vector from the received message",
    properties={
        "x": Field("number", unit="1", description="x component of the raw ROS vector"),
        "y": Field("number", unit="1", description="y component of the raw ROS vector"),
        "z": Field("number", unit="1", description="z component of the raw ROS vector"),
    },
)

_QUATERNION = Field(
    "object",
    description="Orientation quaternion from the received message",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)

_POSE = Field(
    "object",
    description="nav_msgs/Odometry pose.pose of the simulated robot",
    properties={
        "position": _VECTOR3,
        "orientation": _QUATERNION,
    },
)

_TWIST = Field(
    "object",
    description="nav_msgs/Odometry twist.twist of the simulated robot",
    properties={
        "linear": _VECTOR3,
        "angular": _VECTOR3,
    },
)

_SCAN_FIELDS = {
    "angle_min": Field("number", unit="1", description="Raw LaserScan angle_min field"),
    "angle_max": Field("number", unit="1", description="Raw LaserScan angle_max field"),
    "angle_increment": Field("number", unit="1", description="Raw LaserScan angle_increment field"),
    "range_min": Field("number", unit="1", description="Raw LaserScan range_min field"),
    "range_max": Field("number", unit="1", description="Raw LaserScan range_max field"),
    "ranges": Field(
        "array",
        items=Field("number", unit="1"),
        description="Raw LaserScan ranges array; the count is chosen by the URDF or the fallback default",
    ),
}

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the publication to rosbridge"),
    "confirmed": Field("boolean", description="Always false: a rosbridge publication carries no execution confirmation"),
}

_TWIST_LIMIT_LINEAR_X = Limit.operator_required(
    "the pinned clone and its README state no numeric range or physical unit for cmd_vel linear.x; "
    "the operator supplies the site envelope")
_TWIST_LIMIT_LINEAR_Y = Limit.operator_required(
    "the pinned clone and its README state no numeric range or physical unit for cmd_vel linear.y; "
    "the operator supplies the site envelope")
_TWIST_LIMIT_ANGULAR_Z = Limit.operator_required(
    "the pinned clone and its README state no numeric range or physical unit for cmd_vel angular.z; "
    "the operator supplies the site envelope")

_SPAWN = {
    "service": "/simulator/spawn",
    "type": "map_simulator/srv/Spawn",
    "source_ref": _SPAWN_REF,
    "type_ref": _SPAWN_TYPE_REF,
    # The literal request keeps the remaining Spawn.srv defaults.  The action
    # exposes only the namespace, pose, radius, shape and rectangle size; the
    # other request members stay at the values in srv/Spawn.srv:4-17.
    "request": {
        "robot_namespace": ROBOT_NAMESPACE,
        "x": 0.0,
        "y": 0.0,
        "theta": 0.0,
        "radius": 0.2,
        "size": [0.0, 0.0, 0.0],
        "shape": 1,
        "robot_color": [0, 0, 0],
        "laser_color": [255, 0, 0],
        "force_scanner": True,
        "linear_noise": 0.0,
        "angular_noise": 0.0,
        "static_tf_odom": False,
        "zero_joints": False,
    },
    "args": {
        "robot_namespace": {"from": "input.robot_namespace"},
        "x": {"from": "input.x"},
        "y": {"from": "input.y"},
        "theta": {"from": "input.theta"},
        "radius": {"from": "input.radius"},
        "shape": {"from": "input.shape"},
        "size": {"from": "input.size"},
    },
    "success": {"path": "$", "equals": {}},
    "result": {"acknowledged": {"value": True}},
}

_TWIST_COMMAND = {
    "topic": ROBOT_NAMESPACE + "/cmd_vel",
    "type": "geometry_msgs/msg/Twist",
    "operation": "publish",
    "source_name": "cmd_vel",
    "source_ref": _CMD_VEL_REF,
    "type_ref": _TWIST_TYPE_REF,
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "args": {
        "linear.x": {"from": "input.linear_x"},
        "linear.y": {"from": "input.linear_y"},
        "angular.z": {"from": "input.angular_z"},
    },
}

_ODOM = {
    "topic": ROBOT_NAMESPACE + "/odom",
    "type": "nav_msgs/msg/Odometry",
    "operation": "subscribe",
    "source_name": "odom",
    "source_ref": _ODOM_REF,
    "type_ref": _ODOM_TYPE_REF,
    "result": {"map": {"pose": "output.pose.pose", "twist": "output.twist.twist"}},
}

_ODOM_READ_POSE = {
    "topic": ROBOT_NAMESPACE + "/odom",
    "type": "nav_msgs/msg/Odometry",
    "operation": "subscribe",
    "source_name": "odom",
    "source_ref": _ODOM_REF,
    "type_ref": _ODOM_TYPE_REF,
    "path": "pose.pose",
    "timeout_ms": 2000,
}

_ODOM_READ_TWIST = {
    "topic": ROBOT_NAMESPACE + "/odom",
    "type": "nav_msgs/msg/Odometry",
    "operation": "subscribe",
    "source_name": "odom",
    "source_ref": _ODOM_REF,
    "type_ref": _ODOM_TYPE_REF,
    "path": "twist.twist",
    "timeout_ms": 2000,
}

_SCAN = {
    "topic": ROBOT_NAMESPACE + "/scan",
    "type": "sensor_msgs/msg/LaserScan",
    "operation": "subscribe",
    "source_name": "scan",
    "source_ref": _SCAN_TOPIC_REF,
    "type_ref": _SCAN_TYPE_REF,
    "result": {"map": {
        "angle_min": "output.angle_min",
        "angle_max": "output.angle_max",
        "angle_increment": "output.angle_increment",
        "range_min": "output.range_min",
        "range_max": "output.range_max",
        "ranges": "output.ranges",
    }},
}

_SPAWN_INPUT = {
    "robot_namespace": Field(
        "string",
        pattern=r".+",
        description="Absolute ROS namespace used for the spawned robot's topics (README.md:26); "
                    "the callback appends '/' if it is missing. An empty string is refused: addRobot reads "
                    "robot_namespace.back() with no empty check (src/simulator.cpp:55-57)",
    ),
    "x": Field("number", unit="1", description="Raw Spawn request x value"),
    "y": Field("number", unit="1", description="Raw Spawn request y value"),
    "theta": Field("number", unit="1",
                   description="Spawn heading passed to the simulator's trigonometric pose functions"),
    "radius": Field("number", unit="1",
                    description="Circle radius or square side supplied in the Spawn request (README.md:32)"),
    "shape": Field(
        "integer",
        unit="1",
        enum=[0, 1, 2],
        description="Spawn shape selector: 0 square, 1 circle, 2 rectangle (srv/Spawn.srv:1-3)",
    ),
    "size": Field(
        "array",
        items=Field("number", unit="1"),
        length=3,
        description="Three rectangle values (width, length, x-offset) (README.md:33; srv/Spawn.srv:9)",
    ),
}

_SPAWN_OUTPUT = {
    "acknowledged": Field(
        "boolean",
        description="True once the empty Spawn response arrived; the response has no fields and does not prove "
                    "that a robot was created, that its robot_description arrived, or that it is ready to move",
    ),
}

_TWIST_INPUT = {
    "linear_x": Field(
        "number", unit="1",
        description="Raw geometry_msgs/Twist linear.x copied by the simulator's cmd_vel callback",
        limit=_TWIST_LIMIT_LINEAR_X,
    ),
    "linear_y": Field(
        "number", unit="1",
        description="Raw geometry_msgs/Twist linear.y copied by the simulator's cmd_vel callback",
        limit=_TWIST_LIMIT_LINEAR_Y,
    ),
    "angular_z": Field(
        "number", unit="1",
        description="Raw geometry_msgs/Twist angular.z copied by the simulator's cmd_vel callback",
        limit=_TWIST_LIMIT_ANGULAR_Z,
    ),
}


#: The clone states no at-rest bound.  The operator supplies the number; a live
#: simulation puts it in simulation_deployment["estop_confirmation"].  The
#: fixture placeholders are not facts.
_NO_POSE_BOUND = (
    "the clone states no at-rest bound for the odometry pose; the operator supplies the largest change "
    "over the confirmation window that counts as stopped")
_NO_TWIST_BOUND = (
    "the clone states no at-rest bound for the odometry twist; the operator supplies the largest absolute "
    "value that counts as stopped")

#: One sentence, at most 500 characters (safe_state and sensed_stop.description).
_SAFE_STATE = (
    "Simulated only: /robot1/odom position x and y and orientation z and w stay within the operator span, and "
    "linear.x, linear.y and angular.z stay within the operator absolute bound, for three consecutive fresh stamped "
    "samples inside the confirmation bound. A zero Twist on /robot1/cmd_vel proves nothing; another cmd_vel "
    "publisher can move /robot1 again; nothing is claimed beyond that window or for any other robot."
)

#: Sensed-confirmation stop (SAFE-049).  The request publishes a fixed all-zero Twist; the callback copies
#: linear.x, linear.y and angular.z into odom.twist.twist (src/robot.cpp:223-225) and Robot::move keeps
#: integrating that stored twist (src/robot.cpp:282-293).  Repeating the zero Twist writes zero again.
#: Confirmation reads /robot1/odom.  Pose2D::writeTo assigns position.x, position.y, orientation.w and
#: orientation.z (include/map_simulator/robot.h:62-67); Robot::move then writeTo's that pose onto
#: odom.pose.pose (src/robot.cpp:313-315).  The twist fields are the callback's own stored command, and
#: withNoise multiplies by (1 + std * unit noise) (src/robot.cpp:54-58), so a zero command stays zero.
#: Pose span alone would miss a linear.y or a pure yaw command.  history cites the odom create_publisher
#: call, which is closed on that line with the literal depth 10 and no transient_local (src/robot.cpp:214);
#: the gate's volatile check is that citation, and the line does not contain the word volatile.
#: The client bounds are not source facts.  min_span_ms 100 is three samples at a 50 ms stamp step, the
#: same duration as 1/declare_parameter("rate", 20) (src/simulator.cpp:17).  A live deployment sets its own
#: bounds in simulation_deployment["estop_confirmation"]; a bound the stream does not meet withholds the stop.
_SENSED_STOP = {
    "request": [
        {
            "topic": ROBOT_NAMESPACE + "/cmd_vel",
            "type": "geometry_msgs/msg/Twist",
            "operation": "publish",
            "source_name": "cmd_vel",
            "source_ref": _CMD_VEL_REF,
            "type_ref": _TWIST_TYPE_REF,
            "message": {
                "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
                "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
            },
            "description": "transmission only: one all-zero Twist on /robot1/cmd_vel; the publication proves nothing",
        },
    ],
    "sources": {
        "odom": {
            "topic": ROBOT_NAMESPACE + "/odom",
            "type": "nav_msgs/msg/Odometry",
            "source_name": "odom",
            "source_ref": _ODOM_REF,
            "type_ref": _ODOM_TYPE_REF,
            "fill_refs": {
                "pose.pose.position": "include/map_simulator/robot.h:62-67",
                "pose.pose.orientation": "include/map_simulator/robot.h:62-67",
                "twist.twist.linear": "src/robot.cpp:223-225",
                "twist.twist.angular": "src/robot.cpp:223-225",
            },
            # Cited publisher: create_publisher<Odometry>(robot_namespace + "odom", 10), the call closed
            # on that line.  Not operator_required, so the fixture carries no history.
            "history": {"durability": "volatile", "ref": "src/robot.cpp:214"},
        },
    },
    "predicate": [
        {"source": "odom", "path": "pose.pose.position.x", "name": "rest_x", "unit": "1",
         "span_max": Limit.operator_required(_NO_POSE_BOUND)},
        {"source": "odom", "path": "pose.pose.position.y", "name": "rest_y", "unit": "1",
         "span_max": Limit.operator_required(_NO_POSE_BOUND)},
        {"source": "odom", "path": "pose.pose.orientation.z", "name": "rest_qz", "unit": "1",
         "span_max": Limit.operator_required(_NO_POSE_BOUND)},
        {"source": "odom", "path": "pose.pose.orientation.w", "name": "rest_qw", "unit": "1",
         "span_max": Limit.operator_required(_NO_POSE_BOUND)},
        {"source": "odom", "path": "twist.twist.linear.x", "name": "rest_vx", "unit": "1",
         "abs_max": Limit.operator_required(_NO_TWIST_BOUND)},
        {"source": "odom", "path": "twist.twist.linear.y", "name": "rest_vy", "unit": "1",
         "abs_max": Limit.operator_required(_NO_TWIST_BOUND)},
        {"source": "odom", "path": "twist.twist.angular.z", "name": "rest_wz", "unit": "1",
         "abs_max": Limit.operator_required(_NO_TWIST_BOUND)},
    ],
    "consecutive": 3,
    "min_span_ms": 100,
    "max_gap_ms": 500,
    "confirm_within_ms": 1500,
    "description": _SAFE_STATE,
}


class MapSimulator(RosDriver):
    ros_version = 2
    device_id = "map_simulator"
    device_kind = "world.sim"
    mode = "simulated"
    # cmd_vel is a topic a physical mobile robot's driver also consumes, so the
    # hazard is that robot's (REVIEW.md item 12) even though this card is
    # simulated and the device kind stays world.sim.  The card floor is R1;
    # the higher applies.  Spawn stays R1: it is a simulator-only service.
    risk = "R2"
    backends = {"fake": ".fake:FakeMapSimulator"}
    display_name = "map_simulator ROS 2 2-D simulator"
    vendor = "okermorgant"
    model = "map_simulator 2.0.0"
    tags = ["ros", "ros2", "simulation", "map", "mobile-base", "laser-scan", "cmd-vel"]
    facts = [
        Fact("The package provides a 2-D simulator for mobile robots in ROS 2; robots move through a cmd_vel "
             "topic and may publish a laser scan.",
             source="vendor_doc", ref="README.md:3"),
        Fact("The Simulation node advertises a service to spawn robots in, wrapped by the spawn executable.",
             source="vendor_doc", ref="README.md:22"),
        Fact("The spawn node is run in the same namespace as the robot_description topic, and that namespace is "
             "used to publish the robot topics.",
             source="vendor_doc", ref="README.md:26"),
        Fact("Spawning a robot twice resets only its pose; other parameters are changed by removing and "
             "re-spawning the robot.",
             source="vendor_doc", ref="README.md:43"),
        Fact("The cmd_vel topic is subscribed by the simulator for each robot according to its namespace, and "
             "by default the scan topic is used unless a Gazebo plugin names another topic.",
             source="vendor_doc", ref="README.md:51-53"),
        Fact("Spawn.srv defines SHAPE_SQUARE=0, SHAPE_CIRCLE=1 and SHAPE_RECTANGLE=2, followed by the request "
             "members and an empty response after the separator.",
             source="upstream_code", ref=_SPAWN_SRV_REF),
        Fact("SimulatorNode registers the absolute /simulator/spawn service whose callback calls addRobot, and "
             "the /simulator/add_anchor service.",
             source="upstream_code", ref="src/simulator.cpp:42-50"),
        Fact("The SimulatorNode class declares two ROS service members, spawn_srv and anchor_srv, and no other "
             "service member.",
             source="upstream_code", ref=_SERVICE_MEMBERS_REF),
        Fact("SimulatorNode::addRobot appends a trailing slash to the requested namespace and, for an existing "
             "robot, calls resetTo with the requested pose instead of creating a new robot.",
             source="upstream_code", ref="src/simulator.cpp:53-65"),
        Fact("Robot::resetTo assigns the requested pose, writes it to initial_pose when that transform has a "
             "child frame, and clears odom.pose.pose and odom.twist.twist.",
             source="upstream_code", ref=_RESET_REF),
        Fact("Robot::loadModel assigns odom_pub from create_publisher<nav_msgs::msg::Odometry>(robot_namespace + "
             "\"odom\", 10).",
             source="upstream_code", ref=_ODOM_REF),
        Fact("Robot::loadModel creates a geometry_msgs/Twist subscription on <robot_namespace>cmd_vel; the "
             "callback copies only linear.x, linear.y and angular.z into odom.twist.twist.",
             source="upstream_code", ref=_CMD_VEL_REF),
        Fact("parseLaser defaults to 100 samples and the relative scan topic.",
             source="upstream_code", ref=_SCAN_TOPIC_REF),
        Fact("Without a Gazebo ray plugin and with force_scanner true, loadModel sets angle_max=49*M_PI/50, "
             "angle_min=-angle_max, range_min=0.1, range_max=5, resizes the ranges array to the sample count "
             "and creates the LaserScan publisher.",
             source="upstream_code", ref=_SCAN_REF),
        Fact("SimulatorNode computes dt=1/declare_parameter(\"rate\", 20) and drives refresh from a wall timer.",
             source="upstream_code", ref=_RATE_REF),
        Fact("SimulatorNode::refresh calls robot.move(dt) only for connected robots, then recomputes the laser "
             "scans and publishes each connected robot.",
             source="upstream_code", ref=_REFRESH_REF),
        Fact("Robot::initFromURDF waits 500 ms and subscribes to <robot_namespace>robot_description with "
             "transient-local QoS; the callback calls loadModel with the received description text.",
             source="upstream_code", ref=_DESCRIPTION_REF),
        Fact("Robot::move integrates the pose from the stored odom.twist.twist velocities, each passed through "
             "withNoise, on every call.",
             source="upstream_code", ref="src/robot.cpp:282-293"),
        Fact("Robot::publish assigns odom.header.stamp and transform.header.stamp from its now argument and then "
             "publishes odom.",
             source="upstream_code", ref="src/robot.cpp:74-77"),
        Fact("Pose2D::writeTo(geometry_msgs::msg::Pose) assigns pose.position.x, pose.position.y, "
             "pose.orientation.w and pose.orientation.z.",
             source="upstream_code", ref="include/map_simulator/robot.h:62-67"),
        Fact("Robot::move constructs a Pose2D from odom.pose.pose, calls updateFrom and then "
             "writeTo(odom.pose.pose).",
             source="upstream_code", ref="src/robot.cpp:313-315"),
        Fact("withNoise returns val * (1 + std * unit_noise(random_engine)), where unit_noise is a static "
             "std::normal_distribution<double>(0, 1).",
             source="upstream_code", ref="src/robot.cpp:54-58"),
        Fact("SimulatorNode::addRobot reads spec.robot_namespace.back() without checking for an empty "
             "namespace.",
             source="upstream_code", ref="src/simulator.cpp:53-57"),
        Fact("With the display enabled, a double click in the OpenCV window calls removeRobotAt, which removes "
             "the robots at that pixel.",
             source="upstream_code", ref="src/simulator.cpp:28-36"),
        Fact("The README says a robot is unspawned by double-clicking it, which cannot be done with display "
             "false.",
             source="vendor_doc", ref="README.md:45-47"),
        Fact("The TurtleBot3 example spawns its robot in the namespace given by the name argument, default "
             "turtlebot1, and starts slider_publisher with cmd_vel.yaml in that namespace.",
             source="upstream_code", ref="example/turtlebot3/turtlebot3_world_launch.py:8-36"),
        Fact("The multi-robot example starts slider_publisher with cmd_vel_multi.yaml and spawns robots in the "
             "namespaces r2d2, r2d3 and r2d4.",
             source="upstream_code", ref="example/multirobot/multi_launch.py:21-46"),
        Fact("Robot.__init__, when cmd_type is not None, reads declare_parameter('pub_cmd', True).value and, when "
             "that value is true, creates a Twist publisher on the relative topic 'cmd_vel' with queue size 5.",
             source="upstream_code", ref="src/kinematics.py:101-103"),
        Fact("Robot.publish publishes self.cmd_vel on self.cmd_vel_pub when self.cmd_vel_pub is not None.",
             source="upstream_code", ref="src/kinematics.py:121-122"),
    ]
    safe_state = _SAFE_STATE
    #: RosDriver.timeout_s is 2.0 s (2000 ms).  One request step uses that timeout.  confirm_within_ms is 1500.
    #: 2000 + 1500 = 3500 (SAFE-028, SAFE-040).
    estop_latency_ms = 3500
    #: The deployed fake is a canned ROS transport, not a recording and not the
    #: upstream simulator.  The real simulator runs the pinned C++ node.
    fidelity = {
        "engine": "canned:ROS fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned responses; no physics step, pacing, collision response, laser cast or "
                     "state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free canned transport: it answers the declared /simulator/spawn, "
            "/robot1/cmd_vel, /robot1/odom and /robot1/scan messages and runs no map_simulator, OpenCV, "
            "occupancy-grid, collision, laser or wall-clock code",
            "the odom and scan values are placeholders. An /robot1/odom subscription returns a short burst: its "
            "first sample is the stored twist (the confirmation discards it) and later samples snap to the last "
            "cmd_vel. A non-zero cmd_vel steps the stored pose by a placeholder dt of 0.1 so the command is "
            "observable, and that projection is not stored as the odom twist; two reads with no new command agree. "
            "A zero command stores a still pose and a zero twist. This is not Robot::move, withNoise or an "
            "occupancy-grid ray cast",
            "the real simulator creates the odom and scan publishers only after a robot_description message "
            "arrives (src/robot.cpp:113-126, 170-214); the fake starts with a placeholder /robot1 robot and does "
            "not model that handshake",
            "the real default scan is 100 samples with angle_max=49*M_PI/50 and range 0.1..5 unless a Gazebo "
            "ray plugin overrides it (src/robot.cpp:131-132, 194-211); the fake returns 100 placeholder samples "
            "and does not parse a URDF or a scan-topic remapping",
            "the package exposes only one robot namespace; a multi-robot or differently namespaced deployment "
            "needs per-robot absolute endpoints and is NOT COVERED",
            "/robot1 is this package's deployment choice: no shipped launch spawns it (the examples use "
            "/turtlebot1 or /r2d2, /r2d3 and /r2d4 and also start slider_publisher, a competing cmd_vel "
            "publisher); until a robot is spawned in /robot1 and its robot_description arrives, /robot1/odom "
            "and /robot1/scan do not exist, the resource read fails NOT_READY and every command, the first "
            "spawn included, waits the 2 s read timeout before completing (reviewer probe on the fake)",
            "the simulator keeps integrating the last cmd_vel command on every refresh until another command "
            "or a duplicate spawn arrives (src/robot.cpp:219-226, 282-293); an empty robot_namespace reaches "
            "std::string::back() in addRobot (src/simulator.cpp:55-57)",
            "the sensed stop covers /robot1 only, and only inside its confirmation window. slider_publisher "
            "(example/turtlebot3/turtlebot3_world_launch.py:8-36 and example/multirobot/multi_launch.py:21-46) and "
            "kinematics.py when pub_cmd is true (src/kinematics.py:101-103, 121-122) are other cmd_vel publishers; "
            "if one keeps publishing, the confirmation fails closed. A duplicate spawn calls resetTo "
            "(src/simulator.cpp:53-65, include/map_simulator/robot.h:135-143) and is not a stop. Removing a robot "
            "is a GUI double click (src/simulator.cpp:28-36). The client bounds are not source facts; a live "
            "deployment sets them in simulation_deployment['estop_confirmation']",
            "the package does not expose /simulator/add_anchor, /tf, /joint_states, /ranges, the map_server "
            "lifecycle or any unspawn, pause, reset or step service. kinematics.py is disclosed above and is not "
            "a command of this package",
            "the fake is a canned stand-in, not a recording of captured ROS traffic and not the upstream "
            "simulator",
        ],
    }

    parameters = {
        "odom_pose": _POSE,
        "odom_twist": _TWIST,
    }
    reads = {
        "odom_pose": _ODOM_READ_POSE,
        "odom_twist": _ODOM_READ_TWIST,
    }
    commands = {
        "x-cap.okermorgant.spawn.v1": _SPAWN,
        "x-cap.okermorgant.twist.v1": _TWIST_COMMAND,
        "x-cap.okermorgant.odometry.v1": _ODOM,
        "x-cap.okermorgant.scan.v1": _SCAN,
    }
    actions = {
        "x-cap.okermorgant.spawn.v1": Action(
            name="spawn_robot",
            verb="invoke",
            risk="R1",
            description=(
                "Call the upstream /simulator/spawn service to create a robot or reset an existing robot's "
                "pose. The Spawn response is empty, so the receipt confirms only that the service callback "
                "returned; it does not prove creation, URDF arrival, motion or a stopped robot."
            ),
            input=_SPAWN_INPUT,
            output=_SPAWN_OUTPUT,
            examples=[{
                "robot_namespace": ROBOT_NAMESPACE,
                "x": 0.0,
                "y": 0.0,
                "theta": 0.0,
                "radius": 1.0,
                "shape": 1,
                "size": [1.0, 1.0, 0.0],
            }],
        ),
        "x-cap.okermorgant.twist.v1": Action(
            name="publish_twist",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one geometry_msgs/Twist to the upstream /robot1/cmd_vel subscription. The callback "
                "copies linear.x, linear.y and angular.z into the robot odometry twist. The receipt proves only "
                "that rosbridge accepted the publication; it does not prove motion or a stopped robot. cmd_vel "
                "is a topic a physical mobile robot also consumes, so this action is R2 (REVIEW.md item 12)."
            ),
            input=_TWIST_INPUT,
            output=_PUBLISHED,
            examples=[{"linear_x": 0.0, "linear_y": 0.0, "angular_z": 0.0}],
        ),
        "x-cap.okermorgant.odometry.v1": Action(
            name="read_odometry",
            verb="read",
            risk="R0",
            description="Read one nav_msgs/Odometry sample from the upstream /robot1/odom topic",
            output={"pose": _POSE, "twist": _TWIST},
        ),
        "x-cap.okermorgant.scan.v1": Action(
            name="read_scan",
            verb="read",
            risk="R0",
            description="Read one sensor_msgs/LaserScan sample from the upstream /robot1/scan topic",
            output=dict(_SCAN_FIELDS),
        ),
    }
    # No estop or safe_state binding and no safe-state action: the simulator has
    # no acknowledged stop service.  Duplicate spawn teleports (resetTo) and is
    # left as an ordinary command, not a reset binding (SAFE-042).  No unpause.
    safety_bindings = {"sensed_stop": _SENSED_STOP}
