"""OpenMHS rosbridge driver for the ROBOTIS TurtleBot3 fake simulation node.

The pinned upstream is the ROS 2 ``turtlebot3_fake_node`` C++ node.  This
package is a configuration-only :class:`RosDriver` over rosbridge; it declares
no Python native class and neither imports nor launches the upstream node.
The operator runs the fake node and rosbridge separately.

Scope is the fake node's single-device ROS 2 surface:

* ``/cmd_vel`` (``geometry_msgs/msg/Twist``) is the node's only command
  subscription.  Its callback reads only ``linear.x`` and ``angular.z`` and
  converts them to two wheel-speed setpoints.  It returns void and publishes
  no acknowledgement, so a Twist publication is transmission only.
* ``/odom`` (``nav_msgs/msg/Odometry``) is the node's simulated odometry.
* ``/joint_states`` (``sensor_msgs/msg/JointState``) carries the two wheel
  joint positions and velocities.
* ``/tf`` (``tf2_msgs/msg/TFMessage``) is published but is not exposed by this
  package; the odometry pose carries the same transform.

The node registers no ROS service or action server.  The e-stop is a
sensed-confirmation stop (SAFE-049, simulated only): one all-zero Twist on
``/cmd_vel``, achieved only when the ``/odom`` pose stays within the operator's
bounds across five fresh stamped samples.  The 1 s stale-command branch is a
watchdog and is not that confirmation.  ``/cmd_vel`` is also a physical
TurtleBot3 command topic, so the class and the publication are R2.

Every fact cites the pinned clone at
9be186fb03d84ed4f293e5c0db71d8c05bbc91f3.  The fake is a ROS-free canned
transport; every invented value is marked a placeholder.  No ROS graph,
simulator process or hardware was run.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The node constructs the relative cmd_vel subscription with Twist.
_CMD_VEL_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:48-50"
_CMD_VEL_TYPE_REF = "turtlebot3_fake_node/include/turtlebot3_fake_node/turtlebot3_fake_node.hpp:54"

#: The node constructs the relative odom and joint_states publishers.
_ODOM_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:43"
_ODOM_TYPE_REF = "turtlebot3_fake_node/include/turtlebot3_fake_node/turtlebot3_fake_node.hpp:49"
_JOINT_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:44"
_JOINT_TYPE_REF = "turtlebot3_fake_node/include/turtlebot3_fake_node/turtlebot3_fake_node.hpp:50"

#: KeepLast(10) is assigned in the same span as the odom create_publisher.  The call sets no
#: durability and the span has no transient_local, which is the cited volatile history.
_ODOM_QOS_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:40-43"
#: update_odometry writes the pose fields the confirmation reads.
_ODOM_POSITION_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:228-230"
_ODOM_ORIENTATION_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:235-238"
_ODOM_STAMP_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:165-166"

#: The command callback and the stale-command watchdog.
_CALLBACK_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:135-146"
_TIMEOUT_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:99"
_TIMEOUT_BRANCH_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:157-161"

#: The update loop publishes odometry, joint states and tf on its timer.
_UPDATE_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:151-178"
_TIMER_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:59"

#: Unit comments in update_odometry and the wheel-state update.
_ODOM_UNIT_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:191-192"
_WHEEL_STATE_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:247-253"
_WHEEL_NAMES_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:122-126"
_ODOM_STEP_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:215-221"
_WHEEL_PARAM_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:88-89"
_BURGER_PARAM_REF = "turtlebot3_fake_node/param/burger.yaml:3-5"
_FAKE_LAUNCH_REF = "turtlebot3_fake_node/launch/turtlebot3_fake_node.launch.py:60-75"
_DRIVE_PUB_REF = "turtlebot3_gazebo/src/turtlebot3_drive.cpp:42"
_DRIVE_SEND_REF = "turtlebot3_gazebo/src/turtlebot3_drive.cpp:98-104"

#: The constructor ends after publishers, subscribers and one timer; no service
#: or action server is created.  The package description calls the node a
#: robot-free test path.
_NO_SERVICE_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:40-59"
_DESCRIPTION_REF = "turtlebot3_fake_node/package.xml:6-8"

_LINEAR_LIMIT = Limit.operator_required(
    "the pinned node applies cmd_vel.linear.x directly to the wheel-speed setpoints and states no "
    "numeric range or clamp; the operator supplies the signed site envelope")
_ANGULAR_LIMIT = Limit.operator_required(
    "the pinned node applies cmd_vel.angular.z directly to the wheel-speed setpoints and states no "
    "numeric range or clamp; the operator supplies the signed site envelope")
_NO_REST_BOUND = (
    "the clone states no at-rest bound for the odometry pose; the operator supplies the largest change "
    "over the confirmation window that counts as stopped")

_CMD_VEL = {
    "topic": "/cmd_vel",
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
        "linear.x": {"from": "input.linear_velocity"},
        "angular.z": {"from": "input.angular_velocity"},
    },
}

_ODOM_COMMAND = {
    "topic": "/odom",
    "type": "nav_msgs/msg/Odometry",
    "operation": "subscribe",
    "source_name": "odom",
    "source_ref": _ODOM_REF,
    "type_ref": _ODOM_TYPE_REF,
    "result": {"map": {"pose": "output.pose.pose", "twist": "output.twist.twist"}},
}

_JOINT_COMMAND = {
    "topic": "/joint_states",
    "type": "sensor_msgs/msg/JointState",
    "operation": "subscribe",
    "source_name": "joint_states",
    "source_ref": _JOINT_REF,
    "type_ref": _JOINT_TYPE_REF,
    "result": {"map": {"names": "output.name", "positions": "output.position",
                       "velocities": "output.velocity"}},
}

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the Twist to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution confirmation"),
}

_VECTOR3 = Field(
    "object",
    description="Three-component ROS vector as populated by the pinned node",
    properties={
        "x": Field("number", unit="1", description="x component (the clone states no physical unit)"),
        "y": Field("number", unit="1", description="y component (the clone states no physical unit)"),
        "z": Field("number", unit="1", description="z component (the clone states no physical unit)"),
    },
)

_QUATERNION = Field(
    "object",
    description="Orientation quaternion from the odometry pose",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)

_ODOM_POSE = Field(
    "object",
    description="nav_msgs/Odometry pose.pose from the fake node's simulated odometry",
    properties={
        "position": _VECTOR3,
        "orientation": _QUATERNION,
    },
)

_ODOM_TWIST = Field(
    "object",
    description="nav_msgs/Odometry twist.twist; the node sets only linear.x and angular.z from its "
                "wheel integration, and the fake's stored sample carries a placeholder command until a "
                "zero Twist is applied",
    properties={
        "linear": Field(
            "object",
            description="Linear velocity; the source comment labels this quantity [m/s]",
            properties={
                "x": Field("number", unit="m/s", description="Forward velocity populated by the node"),
                "y": Field("number", unit="m/s", description="Lateral velocity (left at the message default)"),
                "z": Field("number", unit="m/s", description="Vertical velocity (left at the message default)"),
            },
        ),
        "angular": Field(
            "object",
            description="Angular velocity; the source comment labels this quantity [rad/s]",
            properties={
                "x": Field("number", unit="rad/s", description="Roll rate (left at the message default)"),
                "y": Field("number", unit="rad/s", description="Pitch rate (left at the message default)"),
                "z": Field("number", unit="rad/s", description="Yaw rate populated by the node"),
            },
        ),
    },
)

_WHEEL_VELOCITY = Field(
    "array",
    unit="rad/s",
    description="Two wheel velocities in JointState.velocity, in wheel order",
    items=Field("number", unit="rad/s"),
    length=2,
)

_WHEEL_POSITIONS = Field(
    "array",
    unit="rad",
    description="Two wheel rotation values in JointState.position, in wheel order",
    items=Field("number", unit="rad"),
    length=2,
)

_WHEEL_NAMES = Field(
    "array",
    description="Joint names published by the node, in wheel order",
    items=Field("string", description="ROS joint name"),
    length=2,
)

#: Sensed-confirmation stop (SAFE-049).  The zero Twist proves nothing: command_velocity_callback
#: copies linear.x and angular.z into setpoints and returns void (cpp:135-146).  Confirmation reads
#: the pose update_odometry assigns (cpp:228-238) on samples whose header.stamp update_callback sets
#: (cpp:165-166).  The node publishes every 10 ms (cpp:59).  throttle_ms 50 and consecutive 5 make the
#: counted window span (5 - 1) * 50 ms = 200 ms, which meets min_span_ms 200 (the check is a strict
#: less-than).  An unthrottled window of five 10 ms samples spans 40 ms and cannot meet it.  Volatile
#: history replays nothing, and the bridge still discards the first sample of the new subscription.
#: A second all-zero Twist leaves the setpoints at zero, so repeating the request undoes nothing.
_SENSED_STOP = {
    "request": [
        {"topic": "/cmd_vel", "type": "geometry_msgs/msg/Twist", "source_name": "cmd_vel",
         "source_ref": _CMD_VEL_REF,
         "message": {"linear": {"x": 0.0, "y": 0.0, "z": 0.0}, "angular": {"x": 0.0, "y": 0.0, "z": 0.0}},
         "description": "one all-zero Twist on /cmd_vel (transmission only; the callback stores the "
                        "setpoints and returns void)"},
    ],
    "sources": {
        "odom": {"topic": "/odom", "type": "nav_msgs/msg/Odometry", "source_name": "odom",
                 "source_ref": _ODOM_REF, "type_ref": _ODOM_TYPE_REF,
                 "stamp_path": "header.stamp", "throttle_ms": 50,
                 "fill_refs": {"pose.pose.position": _ODOM_POSITION_REF,
                               "pose.pose.orientation": _ODOM_ORIENTATION_REF},
                 "history": {"durability": "volatile", "ref": _ODOM_QOS_REF}},
    },
    "predicate": [
        {"source": "odom", "path": "pose.pose.position.x", "name": "rest_x", "unit": "m",
         "span_max": Limit.operator_required(_NO_REST_BOUND)},
        {"source": "odom", "path": "pose.pose.position.y", "name": "rest_y", "unit": "m",
         "span_max": Limit.operator_required(_NO_REST_BOUND)},
        {"source": "odom", "path": "pose.pose.orientation.z", "name": "rest_qz", "unit": "1",
         "span_max": Limit.operator_required(_NO_REST_BOUND)},
        {"source": "odom", "path": "pose.pose.orientation.w", "name": "rest_qw", "unit": "1",
         "span_max": Limit.operator_required(_NO_REST_BOUND)},
    ],
    "consecutive": 5,
    "min_span_ms": 200,
    "max_gap_ms": 500,
    "confirm_within_ms": 1500,
    "description": "zero velocity commanded on /cmd_vel and the fake node's /odom pose (position x and y, "
                   "orientation z and w) still within the operator's bounds in five consecutive fresh "
                   "stamped samples within the confirmation bound",
}


class Turtlebot3Simulations(RosDriver):
    device_id = "turtlebot3-sim"
    device_kind = "world.sim"
    mode = "simulated"
    # /cmd_vel is a mobile-base command topic a physical TurtleBot3 also consumes, so the class is R2
    # even though device_kind stays world.sim and the card floor is R0.  There is no unpause and no
    # re-enable: reset only re-reads /odom.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeTurtlebot3Simulations"}
    display_name = "ROBOTIS TurtleBot3 fake simulation node"
    vendor = "ROBOTIS"
    model = "turtlebot3_fake_node (ROS 2)"
    tags = ["ros", "ros2", "simulation", "turtlebot3", "fake-node", "cmd-vel", "odometry",
            "joint-states"]
    watchdog_ms = 1000
    facts = [
        Fact("The turtlebot3_fake_node package is a ROS 2 ament_cmake package that depends on rclcpp.",
             source="upstream_code", ref="turtlebot3_fake_node/package.xml:19-29"),
        Fact("The package description says the node supports simple tests without a robot.",
             source="vendor_doc", ref=_DESCRIPTION_REF),
        Fact("The constructor names the node turtlebot3_fake_node.", source="upstream_code",
             ref="turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:24-25"),
        Fact("The constructor creates an odom publisher, a joint_states publisher and a tf publisher on "
             "relative names, then one cmd_vel subscription, then a 10 ms wall timer; it creates no ROS "
             "service or action server.",
             source="upstream_code", ref=_NO_SERVICE_REF),
        Fact("The odom publisher is nav_msgs::msg::Odometry.", source="upstream_code",
             ref=_ODOM_TYPE_REF),
        Fact("The joint_states publisher is sensor_msgs::msg::JointState.", source="upstream_code",
             ref=_JOINT_TYPE_REF),
        Fact("The cmd_vel subscription is geometry_msgs::msg::Twist on the relative name cmd_vel.",
             source="upstream_code", ref=_CMD_VEL_REF),
        Fact("The wall timer is created with a 10 ms period and calls update_callback.",
             source="upstream_code", ref=_TIMER_REF),
        Fact("command_velocity_callback records the command time, copies cmd_vel.linear.x and "
             "cmd_vel.angular.z to goal velocities and computes the two wheel-speed setpoints from the "
             "wheel separation; it returns void and publishes no acknowledgement.",
             source="upstream_code", ref=_CALLBACK_REF),
        Fact("init_variables sets cmd_vel_timeout_ to 1.0 s.", source="upstream_code", ref=_TIMEOUT_REF),
        Fact("update_callback's stale-command watchdog zeroes both wheel-speed setpoints when the last "
             "cmd_vel sample is older than cmd_vel_timeout_; its comment reads 'stop the robot if no cmd_vel'.",
             source="upstream_code", ref=_TIMEOUT_BRANCH_REF),
        Fact("update_callback publishes odometry, joint states and tf on every timer tick.",
             source="upstream_code", ref=_UPDATE_REF),
        Fact("update_odometry comments label the translational velocity [m/s] and the rotational velocity "
             "[rad/s].", source="upstream_code", ref=_ODOM_UNIT_REF),
        Fact("init_variables names the two wheel joints wheel_left_joint and wheel_right_joint and sizes "
             "position, velocity and effort to two entries.",
             source="upstream_code", ref=_WHEEL_NAMES_REF),
        Fact("update_joint_state copies last_position_ into position and last_velocity_ into velocity for "
             "the left and right wheels.",
             source="upstream_code", ref=_WHEEL_STATE_REF),
        Fact("update_odometry sets each wheel's last_velocity_ to its wheel-speed setpoint divided by "
             "wheel_radius_ and adds that rate times the step time to last_position_; its comment labels the "
             "wheel rotation value [rad].",
             source="upstream_code", ref="turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:181-214"),
        Fact("The constructor assigns a KeepLast(10) QoS and passes that QoS to the odom publisher.",
             source="upstream_code", ref=_ODOM_QOS_REF),
        Fact("update_callback assigns odom_.header.stamp from time_now and publishes odom_.",
             source="upstream_code", ref=_ODOM_STAMP_REF),
        Fact("update_odometry assigns odom_.pose.pose.position.x and y from odom_pose_ and sets z to 0.",
             source="upstream_code", ref=_ODOM_POSITION_REF),
        Fact("update_odometry builds a quaternion with setRPY of odom_pose_[2] and assigns it to "
             "odom_.pose.pose.orientation.",
             source="upstream_code", ref="turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:232-238"),
        Fact("update_odometry adds delta_s and delta_theta, computed from wheel_l and wheel_r, to odom_pose_.",
             source="upstream_code", ref=_ODOM_STEP_REF),
        Fact("init_parameters reads wheels.separation into wheel_seperation_ and wheels.radius into "
             "wheel_radius_, and the default of each get_parameter_or call is 0.0.",
             source="upstream_code", ref=_WHEEL_PARAM_REF),
        Fact("The burger parameter file sets wheels.separation to 0.160 and wheels.radius to 0.033.",
             source="upstream_code", ref=_BURGER_PARAM_REF),
        Fact("The fake-node launch includes rviz2.launch.py and starts the turtlebot3_fake_node and "
             "robot_state_publisher executables.",
             source="upstream_code", ref=_FAKE_LAUNCH_REF),
        Fact("turtlebot3_drive creates a geometry_msgs::msg::Twist publisher on the relative name cmd_vel.",
             source="upstream_code", ref=_DRIVE_PUB_REF),
        Fact("turtlebot3_drive's update_cmd_vel assigns linear.x and angular.z and publishes that Twist.",
             source="upstream_code", ref=_DRIVE_SEND_REF),
    ]
    safe_state = (
        "Simulated only: zero velocity commanded on /cmd_vel and the fake node's /odom pose (position x and y, "
        "orientation z and w) still within the operator's bounds in five consecutive fresh stamped samples "
        "within the confirmation bound. The zero-Twist publication alone proves nothing; another /cmd_vel "
        "publisher can move the base again; nothing is claimed beyond the confirmation window."
    )
    # The request step sets no timeout_ms, so it uses RosDriver.timeout_s (2.0 s, 2000 ms).
    # confirm_within_ms is 1500.  The declared e-stop latency covers both.
    estop_latency_ms = 3500
    fidelity = {
        "engine": "canned:ROS fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned responses; the /odom burst is a placeholder unicycle stepped by "
                     "the subscription throttle, not the node's 10 ms integrator or a physics step",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free canned transport: it answers the declared /cmd_vel, /odom and "
            "/joint_states endpoints and runs no turtlebot3_fake_node code, physics or 10 ms timer",
            "odometry and wheel values are placeholders; a non-zero /cmd_vel is recorded and is not stored, "
            "and a burst while that command holds is a projection the next read does not keep; a zero Twist "
            "freezes the stored pose. This is not the node's trajectory or its 10 ms timing",
            "the confirmation subscribes to /odom with throttle_ms 50 so five counted samples span "
            "(5-1)*50 ms = 200 ms (min_span_ms). The node publishes every 10 ms "
            "(turtlebot3_fake_node.cpp:59); an unthrottled window of five samples spans 40 ms and cannot "
            "meet min_span_ms. The fake spaces producer stamps by the subscription throttle_rate; a live "
            "rosbridge throttle_rate is not run here",
            "the pose span thresholds are operator_required (the clone states no at-rest bound). "
            "fixtures/estop-confirmation.json holds fake placeholders only. A live simulation sets its own "
            "in simulation_deployment['estop_confirmation']; client bounds may only tighten the window",
            "init_parameters defaults wheels.separation and wheels.radius to 0.0 "
            "(turtlebot3_fake_node.cpp:88-89). cpp:194 divides each wheel speed by wheel_radius_. "
            "cpp:204-210 replace a NaN wheel increment with 0. cpp:215 multiplies by wheel_radius_. "
            "cpp:216 multiplies by wheel_radius_ and divides by wheel_seperation_. Both defaults still 0 "
            "and a zero command make delta_theta NaN, and the pose becomes non-finite. Radius 0 with a "
            "non-zero separation and a zero command keeps delta_s and delta_theta at 0, so the pose stays "
            "finite while the wheel velocities stay NaN. A non-zero command with radius 0 makes delta_s "
            "non-finite. The pose-only confirmation does not read joint velocities and does not validate "
            "wheel geometry: a finite stationary pose still confirms. burger.yaml sets separation 0.160 "
            "and radius 0.033 (burger.yaml:3-5). Those yaml numbers are not limits",
            "the fake-node launch starts turtlebot3_fake_node and robot_state_publisher and includes rviz "
            "(launch.py:60-75) and does not publish /cmd_vel. turtlebot3_drive in this clone creates a "
            "Twist publisher on cmd_vel and publishes linear.x and angular.z (turtlebot3_drive.cpp:42, "
            "98-104); CMakeLists.txt builds that executable and no launch file in the clone starts it. A "
            "competing /cmd_vel publisher (that node, a teleop node or Nav2) keeps the pose moving and the "
            "confirmation fails closed",
            "the 1 s stale-command watchdog (cpp:157-161) is a second path. The confirmation does not read "
            "it and does not rely on it. The fake has no wall-clock timer and does not reproduce it",
            "/cmd_vel is also the command topic of a physical TurtleBot3. A rosbridge endpoint pointed at "
            "that robot would move it. This package declares only the fake node, in simulated mode, and "
            "claims nothing beyond the confirmation window",
            "the package does not expose /tf, the Gazebo worlds, /scan, /imu, the camera or any ROS service "
            "or action. There is no unpause and no re-enable: reset re-confirms the /odom pose read-only "
            "and resumes nothing",
            "every number in fake.py is a placeholder, including the initial 0.2 m/s command, the 12-sample "
            "burst, the 0.033 m radius and 0.160 m separation used only to fill joint velocities, and the "
            "stamp clock",
        ],
    }

    parameters = {
        "odom_pose": _ODOM_POSE,
        "odom_twist": _ODOM_TWIST,
        "wheel_velocity": _WHEEL_VELOCITY,
    }
    reads = {
        "odom_pose": {
            "topic": "/odom",
            "type": "nav_msgs/msg/Odometry",
            "operation": "subscribe",
            "source_name": "odom",
            "source_ref": _ODOM_REF,
            "type_ref": _ODOM_TYPE_REF,
            "path": "pose.pose",
            "timeout_ms": 2000,
        },
        "odom_twist": {
            "topic": "/odom",
            "type": "nav_msgs/msg/Odometry",
            "operation": "subscribe",
            "source_name": "odom",
            "source_ref": _ODOM_REF,
            "type_ref": _ODOM_TYPE_REF,
            "path": "twist.twist",
            "timeout_ms": 2000,
        },
        "wheel_velocity": {
            "topic": "/joint_states",
            "type": "sensor_msgs/msg/JointState",
            "operation": "subscribe",
            "source_name": "joint_states",
            "source_ref": _JOINT_REF,
            "type_ref": _JOINT_TYPE_REF,
            "path": "velocity",
            "timeout_ms": 2000,
        },
    }
    commands = {
        "x-cap.robotis-git.turtlebot3_sim_cmd_vel.v1": _CMD_VEL,
        "x-cap.robotis-git.turtlebot3_sim_odometry.v1": _ODOM_COMMAND,
        "x-cap.robotis-git.turtlebot3_sim_joint_states.v1": _JOINT_COMMAND,
    }
    actions = {
        "x-cap.robotis-git.turtlebot3_sim_cmd_vel.v1": Action(
            name="publish_velocity",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one geometry_msgs/Twist to the upstream /cmd_vel subscription; the fake node "
                "consumes only linear.x and angular.z. The receipt confirms only that rosbridge accepted "
                "the publication, not motion, arrival or stopping. /cmd_vel is also a physical TurtleBot3 "
                "command topic, so this action is R2."
            ),
            input={
                "linear_velocity": Field(
                    "number",
                    unit="m/s",
                    description="Body-frame forward velocity mapped to Twist.linear.x",
                    limit=_LINEAR_LIMIT,
                ),
                "angular_velocity": Field(
                    "number",
                    unit="rad/s",
                    description="Body-frame yaw rate mapped to Twist.angular.z",
                    limit=_ANGULAR_LIMIT,
                ),
            },
            output=_PUBLISHED,
            examples=[{"linear_velocity": 0.0, "angular_velocity": 0.0}],
        ),
        "x-cap.robotis-git.turtlebot3_sim_odometry.v1": Action(
            name="read_odometry",
            verb="read",
            description="Read one odometry sample from the upstream /odom topic",
            output={"pose": _ODOM_POSE, "twist": _ODOM_TWIST},
        ),
        "x-cap.robotis-git.turtlebot3_sim_joint_states.v1": Action(
            name="read_joint_states",
            verb="read",
            description="Read one wheel joint-state sample from the upstream /joint_states topic",
            output={
                "names": _WHEEL_NAMES,
                "positions": _WHEEL_POSITIONS,
                "velocities": _WHEEL_VELOCITY,
            },
        ),
    }
    # Exclusive with estop and safe_state bindings.  The request is the zero Twist; the safe state is
    # the /odom pose window above.  Reset re-confirms that window and publishes nothing.
    safety_bindings = {"sensed_stop": _SENSED_STOP}
