"""OpenMHS rosbridge driver for the pinned ROS 2 AMR simulation.

The upstream repository is a ROS 2 Jazzy / Gazebo Harmonic description and
launch stack for one differential-drive AMR.  It contains no ROS 2 service or
action server and no Python device class that is reachable over the wire.  The
executable interface in the clone is the bridged ROS 2 topic graph:

* ``/cmd_vel`` carries ``geometry_msgs/msg/Twist`` from ROS 2 to the Gazebo
  diff-drive plugin;
* ``/odom``, ``/clock`` and ``/joint_states`` are published from Gazebo back
  into ROS 2;
* ``amr_menu.py`` is a local interactive client that publishes the same Twist
  at 10 Hz and stops by publishing an all-zero Twist.

The package therefore exposes the velocity publication, the odometry
observation and the clock/joint-state observations.  The clone has no stop,
pause or reset service or action, and a zero-Twist publication (or the
menu's ``stop()`` sleep) is transmission only, not proof that the simulated
base stopped.  This simulated package therefore declares a
sensed-confirmation stop (SAFE-049, the user's decision of 2026-11-05,
simulated devices only): the e-stop publishes the zero Twist the README
prescribes and is achieved only when the bridged ``/odom`` pose stays still in
three consecutive fresh samples within the bound; otherwise it fails
``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the latch held and is retried in the
background.  The predicate reads the odometry pose only: the twist fields are
filled by the gz-sim DiffDrive plugin outside the clone, and the local gz-sim
clone is not the Harmonic version the clone uses.

Every endpoint and fact cites the pinned clone at
202aad5cac8842dcf94385be4ed186fdd8b29718.  The fake transport is ROS-free; no
ROS graph, Gazebo process, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The ros_gz_bridge configuration is the wire declaration for every topic.
_CLOCK_REF = "src/robot_description/config/ros_gz_bridge.yaml:11-15"
_CMD_VEL_REF = "src/robot_description/config/ros_gz_bridge.yaml:17-21"
_ODOM_REF = "src/robot_description/config/ros_gz_bridge.yaml:23-27"
_JOINT_STATES_REF = "src/robot_description/config/ros_gz_bridge.yaml:35-39"

#: SAFE-049 (verification F1 of phase 3): the /odom publisher is ros_gz_bridge's parameter_bridge, whose source is
#: outside this clone; the clone's bridge entry (ros_gz_bridge.yaml:23-27) and its launch parameters
#: (gazebo.launch.py:144-153: config_file and use_sim_time only) set no QoS, so its durability is the bridge's default,
#: which nothing in the clone states. The operator states it for a live simulation; the fake's placeholder is in
#: fixtures/estop-confirmation.json.
_ODOM_HISTORY_UNSTATED = ("the /odom publisher is ros_gz_bridge's parameter_bridge, outside the clone; its bridge "
                          "entry (src/robot_description/config/ros_gz_bridge.yaml:23-27) and launch parameters "
                          "(src/robot_description/launch/gazebo.launch.py:144-153) set no QoS, so the bridge's "
                          "default durability applies, which the clone does not state")

#: The gz-sim DiffDrive plugin declaration supplies the joint names, the
#: configured velocity caps and the odometry publication rate.
_DIFF_DRIVE_REF = "src/robot_description/urdf/gazebo.xacro:183-216"

#: The JointStatePublisher plugin declaration (no <topic> element) and the
#: launch that adds a GUI /joint_states publisher.
_JOINT_STATE_PLUGIN_REF = "src/robot_description/urdf/gazebo.xacro:221-236"
_ROBOT_LAUNCH_DISPLAY_REF = "src/robot_description/launch/robot.launch.py:24-31"
_JSP_GUI_REF = "src/robot_description/launch/display.launch.py:96-133"

#: The interactive menu is a client of the same /cmd_vel topic.
_MENU_PUBLISHER_REF = "amr_menu.py:21"
_MENU_LOOP_REF = "amr_menu.py:31-54"
_MENU_MOTION_REF = "amr_menu.py:58-72"

#: The README states how to drive and how to ask the base to stop.
_README_DRIVE_REF = "README.md:1916"
_README_STOP_REF = "README.md:1921-1923"
_README_DIRECTION_REF = "README.md:2395-2397"
#: The README states what the DiffDrive plugin's /odom carries (vendor document lines for the sensed fields).
_README_ODOM_POSITION_REF = "README.md:2405"
_README_ODOM_CONTENT_REF = "README.md:2407"
_README_ODOM_REF = "README.md:1179-1186"

#: The diff-drive plugin states only positive maxima (max_linear_velocity 2.0
#: and max_angular_velocity 2.0 at gazebo.xacro:198-199) and no reverse or
#: negative bound.  A one-sided Limit(max=2.0) left every negative command
#: unbounded (a reviewer probe published linear.x -1000 m/s), and a plugin
#: clamp is not a command envelope, so both inputs are operator_required; the
#: example overlay site-limits.example.json is an example, not a source.
_SPEED_LIMIT = Limit.operator_required(
    "the clone states only the DiffDrive clamp max_linear_velocity 2.0 and no reverse bound; the operator "
    "supplies the signed forward-speed envelope")
_TURN_LIMIT = Limit.operator_required(
    "the clone states only the DiffDrive clamp max_angular_velocity 2.0 and no negative bound; the operator "
    "supplies the signed yaw-rate envelope")

_POSITION = Field(
    "object",
    description="Position selected from nav_msgs/Odometry pose.pose.position",
    properties={
        "x": Field("number", unit="m", description="Position x in the odometry frame"),
        "y": Field("number", unit="m", description="Position y in the odometry frame"),
        "z": Field("number", unit="m", description="Position z in the odometry frame"),
    },
)
_ORIENTATION = Field(
    "object",
    description="Orientation selected from nav_msgs/Odometry pose.pose.orientation",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)
_POSE = Field(
    "object",
    description="nav_msgs/Odometry pose selected from message field pose.pose",
    properties={"position": _POSITION, "orientation": _ORIENTATION},
)
_LINEAR = Field(
    "object",
    description="Linear velocity selected from nav_msgs/Odometry twist.twist.linear",
    properties={
        "x": Field("number", unit="m/s", description="Linear velocity x"),
        "y": Field("number", unit="m/s", description="Linear velocity y"),
        "z": Field("number", unit="m/s", description="Linear velocity z"),
    },
)
_ANGULAR = Field(
    "object",
    description="Angular velocity selected from nav_msgs/Odometry twist.twist.angular",
    properties={
        "x": Field("number", unit="rad/s", description="Angular velocity x"),
        "y": Field("number", unit="rad/s", description="Angular velocity y"),
        "z": Field("number", unit="rad/s", description="Angular velocity z"),
    },
)
_TWIST = Field(
    "object",
    description="nav_msgs/Odometry twist selected from message field twist.twist",
    properties={"linear": _LINEAR, "angular": _ANGULAR},
)
_CLOCK_TIME = Field(
    "object",
    description="Simulation time selected from a rosgraph_msgs/Clock sample",
    properties={
        "sec": Field("integer", unit="s", description="Whole seconds of simulated time"),
        "nanosec": Field("integer", unit="ns", description="Nanoseconds within the simulated second"),
    },
)
_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the Twist to rosbridge"),
    "confirmed": Field("boolean", description="Always false: a rosbridge publication carries no execution "
                                               "or stop confirmation"),
}
_JOINT_STATES_OUTPUT = {
    "frame_id": Field("string", description="Frame id from the JointState header"),
    "names": Field("array", description="Joint names from the JointState message",
                   items=Field("string", description="One joint name")),
    "positions": Field("array", unit="rad", description="Joint positions from the JointState message",
                       items=Field("number", unit="rad", description="One joint position")),
    "velocities": Field("array", unit="rad/s", description="Joint velocities from the JointState message",
                        items=Field("number", unit="rad/s", description="One joint velocity")),
}

#: One explicit geometry_msgs/Twist publication on the bridged command topic.
#: The diff-drive plugin consumes it; no motion, arrival or stop acknowledgement
#: is sent back on /cmd_vel.
_CMD_VEL = {
    "topic": "/cmd_vel",
    "type": "geometry_msgs/msg/Twist",
    "operation": "publish",
    "source_ref": _CMD_VEL_REF,
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "args": {
        "linear.x": {"from": "input.linear_velocity"},
        "angular.z": {"from": "input.angular_velocity"},
    },
}

#: The simulation clock is a non-latched topic observation.
_CLOCK = {
    "topic": "/clock",
    "type": "rosgraph_msgs/msg/Clock",
    "operation": "subscribe",
    "source_ref": _CLOCK_REF,
    "path": "clock",
    "result": {"map": {"sim_time": "output.$"}},
}

#: Wheel joint state published by the gz JointStatePublisher plugin.
_JOINT_STATES = {
    "topic": "/joint_states",
    "type": "sensor_msgs/msg/JointState",
    "operation": "subscribe",
    "source_ref": _JOINT_STATES_REF,
    "path": "$",
    "result": {"map": {
        "frame_id": "header.frame_id",
        "names": "name",
        "positions": "position",
        "velocities": "velocity",
    }},
}

#: The raw odometry published by the gz-sim DiffDrive plugin.
_ODOM = {
    "topic": "/odom",
    "type": "nav_msgs/msg/Odometry",
    "operation": "subscribe",
    "source_ref": _ODOM_REF,
}


#: Sensed-confirmation stop (SAFE-049): the zero Twist proves nothing by itself (README.md:1921-1923 prescribes it;
#: amr_menu.py:50-54 sends it and only sleeps).  The confirmation reads the stamped /odom pose that the DiffDrive
#: plugin publishes at 50 Hz through ros_gz_bridge (gazebo.xacro:208, 216; ros_gz_bridge.yaml:23-27); the README
#: states its position and orientation content (fill_refs, vendor document lines).  /joint_states is never a
#: source: display.launch.py also starts joint_state_publisher_gui on it.  The thresholds are operator_required
#: (the clone states no at-rest bound); the client bounds are fake-scale and a live deployment sets them, with a
#: consecutive count whose samples span min_span_ms at the 50 Hz odometry rate, in its estop_confirmation.
_NO_REST_BOUND = ("the clone states no at-rest bound for the odometry pose; the operator supplies the largest change "
                  "over the confirmation window that counts as stopped")

_SENSED_STOP = {
    "request": [
        {"topic": "/cmd_vel", "type": "geometry_msgs/msg/Twist", "source_ref": _CMD_VEL_REF,
         "message": {"linear": {"x": 0.0, "y": 0.0, "z": 0.0}, "angular": {"x": 0.0, "y": 0.0, "z": 0.0}},
         "description": "the zero Twist the README prescribes to stop the robot (transmission only)"},
    ],
    "sources": {
        "odom": {"topic": "/odom", "type": "nav_msgs/msg/Odometry", "source_ref": _ODOM_REF,
                 "fill_refs": {"pose.pose.position": _README_ODOM_POSITION_REF,
                               "pose.pose.orientation": _README_ODOM_CONTENT_REF},
                 "history": {"operator_required": _ODOM_HISTORY_UNSTATED}},
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
    "consecutive": 3,
    "min_span_ms": 200,
    "max_gap_ms": 500,
    "confirm_within_ms": 1500,
    "description": "zero velocity commanded on /cmd_vel and the base sensed still on the /odom pose in three "
                   "consecutive fresh samples within the bound",
}


class Ros2AmrSimulation(RosDriver):
    device_id = "ros2-amr-simulation"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    # The base is a mobile robot in a warehouse world; the catalogue class for
    # a mobile base is R2 and the card floor is R1, so the higher class applies.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeRos2AmrSimulation"}
    tags = ["ros", "ros2", "gazebo", "simulation", "mobile-base", "cmd-vel", "odometry",
            "differential-drive"]
    display_name = "ros2-amr-simulation differential-drive base"
    vendor = "karthik0497"
    model = "amr_robot in the warehouse.sdf world"
    facts = [
        Fact("The ros_gz_bridge configuration declares /clock with rosgraph_msgs/msg/Clock, "
             "bridged GZ_TO_ROS.", source="upstream_code", ref=_CLOCK_REF),
        Fact("The ros_gz_bridge configuration declares /cmd_vel with geometry_msgs/msg/Twist, "
             "bridged ROS_TO_GZ.", source="upstream_code", ref=_CMD_VEL_REF),
        Fact("The ros_gz_bridge configuration declares /odom with nav_msgs/msg/Odometry, "
             "bridged GZ_TO_ROS.", source="upstream_code", ref=_ODOM_REF),
        Fact("The ros_gz_bridge configuration bridges the Gazebo topic /joint_states (gz.msgs.Model) to the "
             "ROS 2 topic /joint_states with sensor_msgs/msg/JointState, GZ_TO_ROS.", source="upstream_code",
             ref=_JOINT_STATES_REF),
        Fact("The gz-sim DiffDrive plugin configures left_wheel_joint and right_wheel_joint, "
             "wheel_separation 0.34 m, wheel_radius 0.05 m, the cmd_vel command topic and the odom "
             "odometry topic.", source="upstream_code", ref=_DIFF_DRIVE_REF),
        Fact("The DiffDrive plugin declares max_linear_acceleration 1.0, max_angular_acceleration 2.0, "
             "max_linear_velocity 2.0 and max_angular_velocity 2.0 after a comment stating that these "
             "are velocity limits preventing simulation instability.", source="upstream_code",
             ref="src/robot_description/urdf/gazebo.xacro:195-199"),
        Fact("The DiffDrive plugin publishes odometry at 50 Hz and names odom and base_footprint as "
             "its frame ids.", source="upstream_code",
             ref="src/robot_description/urdf/gazebo.xacro:211-216"),
        Fact("AMRController creates a publisher for geometry_msgs/Twist on the absolute /cmd_vel "
             "topic with queue size 10.", source="upstream_code", ref=_MENU_PUBLISHER_REF),
        Fact("AMRController.publish_velocity publishes the same Twist at 10 Hz for a caller-computed "
             "duration, and stop() publishes one all-zero Twist and sleeps; neither reads a reply or "
             "checks that the robot stopped.", source="upstream_code", ref=_MENU_LOOP_REF),
        Fact("move_forward and move_backward compute a duration from the local speed attribute, call "
             "publish_velocity and then stop.", source="upstream_code", ref=_MENU_MOTION_REF),
        Fact("The README drives the robot with one geometry_msgs/msg/Twist publication on /cmd_vel.",
             source="vendor_doc", ref=_README_DRIVE_REF),
        Fact("The README instructs the operator to stop the robot by publishing one Twist with "
             "linear.x 0.0 and angular.z 0.0 on /cmd_vel.", source="vendor_doc", ref=_README_STOP_REF),
        Fact("The README describes /cmd_vel as a ROS 2 to Gazebo only bridge and says Gazebo never "
             "sends velocity commands back to ROS 2.", source="vendor_doc", ref=_README_DIRECTION_REF),
        Fact("The JointStatePublisher plugin is declared without a <topic> element, after a comment saying it "
             "publishes to the /world/*/model/*/joint_state Gazebo topic.", source="upstream_code",
             ref=_JOINT_STATE_PLUGIN_REF),
        Fact("robot.launch.py includes display.launch.py with use_rsp false.", source="upstream_code",
             ref=_ROBOT_LAUNCH_DISPLAY_REF),
        Fact("display.launch.py starts joint_state_publisher_gui without a condition; its comment says the "
             "sliders publish to /joint_states and that the node is only for testing.", source="upstream_code",
             ref=_JSP_GUI_REF),
        Fact("The LICENSE file is the MIT License.", source="vendor_doc", ref="LICENSE:1"),
        Fact("The robot_description package.xml declares the licence Apache-2.0.", source="upstream_code",
             ref="src/robot_description/package.xml:9"),
        Fact("The README says the DiffDrive plugin publishes /odom (nav_msgs/Odometry) with the estimated robot "
             "position.", source="vendor_doc", ref=_README_ODOM_REF),
        Fact("The README says the DiffDrive plugin calculates the robot position by integrating wheel rotations "
             "and that /odom contains position x, y, z, orientation and velocity.", source="vendor_doc",
             ref="README.md:2404-2407"),
        Fact("AMRController.stop() publishes one default-constructed (all-zero) Twist with its publisher and "
             "sleeps.",
             source="upstream_code", ref="amr_menu.py:50-54"),
    ]
    safe_state = (
        "Simulated only: zero velocity commanded on /cmd_vel and the base sensed still on the bridged /odom pose "
        "(position and orientation within the operator's bounds) in three consecutive fresh stamped samples "
        "within the confirmation bound. The zero-Twist publication alone proves nothing; another /cmd_vel "
        "publisher can move the base again; nothing is claimed beyond the confirmation window."
    )
    #: The request step's timeout (timeout_s 2000 ms) plus confirm_within_ms (1500 ms): the e-stop's budget.
    estop_latency_ms = 3500
    fidelity = {
        "engine": "analytic:ROS fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven rosbridge fake with no physics step, diff-drive integration, "
                     "wall-clock pacing or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free rosbridge contract stand-in, not a recording of captured traffic: "
            "it runs no Gazebo physics, diff-drive plugin, robot model, warehouse world or ROS graph",
            "the /odom pose and twist are placeholder values; the fake echoes the last published twist "
            "only as a contract effect and does not integrate motion or claim a trajectory",
            "the /clock sample is a fixed placeholder and does not advance with simulation time",
            "the /joint_states names, positions and velocities are two placeholder wheel-joint "
            "entries; the real JointStatePublisher plugin publishes the model's own joint set, which "
            "this fake does not reproduce",
            "a live /joint_states read may time out or return GUI slider values: the JointStatePublisher "
            "plugin declares no <topic> and its comment names the /world/*/model/*/joint_state Gazebo topic, "
            "while the bridge reads the Gazebo topic /joint_states (gazebo.xacro:221-236, "
            "ros_gz_bridge.yaml:35-39); robot.launch.py also starts joint_state_publisher_gui through "
            "display.launch.py, which publishes slider positions on /joint_states",
            "the linear and angular velocity inputs are operator_required: the clone states only the DiffDrive "
            "clamps max_linear_velocity 2.0 and max_angular_velocity 2.0 and no reverse or negative bound; "
            "site-limits.example.json is an example overlay, not a source",
            "no stop, pause or reset service or action exists in the pinned clone: the e-stop is a "
            "sensed-confirmation stop (SAFE-049, simulated only) that publishes the zero Twist and is achieved only "
            "on three consecutive fresh /odom samples whose pose is still within the bound; the thresholds are "
            "operator_required (fake placeholders in fixtures/estop-confirmation.json) and the client bounds are "
            "fake-scale, so a live deployment sets both, with a consecutive count that spans min_span_ms at "
            "the 50 Hz odometry rate, in simulation_deployment['estop_confirmation']",
            "the fake starts driving at a placeholder 0.3 m/s and models the DiffDrive speed limiter as a "
            "placeholder ramp of 1.0 m/s^2 and 2.0 rad/s^2 per 0.1 s sample with pose integration and simulated "
            "stamps, not Gazebo; amr_menu.py and drive_pattern.py are further /cmd_vel publishers that can move "
            "the base after a confirmed stop, which a reset's re-confirmation refuses but nothing prevents",
            "the predicate reads the odometry pose only: the twist fields are filled by the gz-sim DiffDrive "
            "plugin outside the clone, and the local gz-sim clone is not the Harmonic version this clone uses",
            "the interactive amr_menu.py client and its 10 Hz publication loop are not started; the "
            "fake models only the ROS wire contract",
            "a live run requires the operator's Gazebo Harmonic world, ros_gz_sim, ros_gz_bridge and "
            "the upstream launch; none of them is started or validated here",
        ],
    }

    parameters = {"pose": _POSE, "twist": _TWIST}
    reads = {
        "pose": dict(_ODOM, path="pose.pose", timeout_ms=2000),
        "twist": dict(_ODOM, path="twist.twist", timeout_ms=2000),
    }
    commands = {
        "x-cap.karthik0497.cmd_vel.v1": _CMD_VEL,
        "x-cap.karthik0497.clock.v1": _CLOCK,
        "x-cap.karthik0497.joint_states.v1": _JOINT_STATES,
    }
    actions = {
        "x-cap.karthik0497.cmd_vel.v1": Action(
            name="publish_cmd_vel",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one geometry_msgs/Twist velocity setpoint to /cmd_vel for the gz-sim "
                "DiffDrive plugin. The receipt confirms only that rosbridge accepted the publication, "
                "not motion, arrival or stopping."
            ),
            input={
                "linear_velocity": Field(
                    "number", unit="m/s",
                    description="Body-frame forward velocity written to twist.linear.x",
                    limit=_SPEED_LIMIT,
                ),
                "angular_velocity": Field(
                    "number", unit="rad/s",
                    description="Body-frame yaw rate written to twist.angular.z",
                    limit=_TURN_LIMIT,
                ),
            },
            output=_PUBLISHED,
            examples=[{"linear_velocity": 0.0, "angular_velocity": 0.0}],
        ),
        "x-cap.karthik0497.clock.v1": Action(
            name="read_sim_clock",
            verb="read",
            description="Read one rosgraph_msgs/Clock sample from the bridged /clock topic",
            output={"sim_time": _CLOCK_TIME},
        ),
        "x-cap.karthik0497.joint_states.v1": Action(
            name="read_joint_states",
            verb="read",
            description="Read one sensor_msgs/JointState sample from the bridged /joint_states topic",
            output=_JOINT_STATES_OUTPUT,
        ),
    }
    # The clone exposes no ROS service or action that could acknowledge a stop, and a zero-velocity publication
    # alone is not one: the e-stop is the sensed-confirmation stop above (SAFE-049).
    safety_bindings = {"sensed_stop": _SENSED_STOP}
