"""OpenMHS rosbridge declaration for the taucrates Unitree Go1 Gazebo simulation.

The pinned repository is a ROS 1 Noetic launch/configuration package: it
describes a Unitree Go1 in Gazebo with the CHAMP kinematics, a Hokuyo laser, a
depth camera and a RealSense description.  This package is a configuration-only
:class:`RosDriver` over rosbridge; it declares no Python native class and it
does not import, launch or execute anything from the clone.

The declaration preserves the repository's primary control surface, one
``geometry_msgs/Twist`` publication on the relative ``cmd_vel`` endpoint that
the upstream velocity-smoother launch wires into the CHAMP controller
(``go1_simulation/launch/velocity_smoother.launch:5-7``), and one
``sensor_msgs/LaserScan`` observation on the ``scan`` endpoint that the laser
scan matcher and the move_base costmaps consume
(``go1_simulation/launch/navigate.launch:14`` and
``go1_config/config/move_base/costmap_common_params.yaml:14``).

Two source limits are recorded honestly rather than papered over:

* the pinned tree contains no ``.msg``, ``.srv`` or ``.action`` file and no
  line that spells a fully qualified ROS message type.  The launch and xacro
  files name the topics and the Gazebo plugins, and the costmap YAML uses the
  short names ``LaserScan`` and ``PointCloud2``, but the message packages are
  not declared there.  Gate G7 therefore cannot accept the conventional type
  names used by this declaration; ``RESULT.json`` records the resulting
  ``ROS_TYPE_NOT_UPSTREAM`` findings and does not claim that they are verified.
* the pinned tree exposes no ROS service or action that acknowledges a stop,
  pause or reset.  The ``paused`` launch argument in
  ``go1_simulation/launch/gazebo.launch:6,21`` is a launch-time option that is
  forwarded to the external ``gazebo_ros`` empty-world launch; it is not a
  runtime endpoint.  A zero-Twist publication is transmission only.  No stop
  is fabricated, so the stock e-stop cannot report an achieved safe state and
  ``RESULT.json`` records the package as blocked rather than passed.

The fake is a ROS-free analytic rosbridge contract stand-in, not a recording
of captured traffic.  Every value it returns is test data marked
``# placeholder``; no Gazebo physics, CHAMP controller, laser ray casting,
camera, state estimator or ROS graph is run.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The velocity-smoother launch names the relative cmd_vel command endpoint.
_CMD_VEL_REF = "go1_simulation/launch/velocity_smoother.launch:5-7"

#: The navigation launch remaps the scan topic and the velocity topic.
_SCAN_ENDPOINT_REF = "go1_simulation/launch/navigate.launch:14"

#: The move_base costmap names the scan data type with its short ROS type name.
_SCAN_TYPE_REF = "go1_config/config/move_base/costmap_common_params.yaml:14"

#: The pinned tree states no signed command envelope.  The CHAMP gait
#: configuration gives a maximum forward, lateral and yaw rate, but those are
#: gait parameters of the external controller, not an accepted /cmd_vel
#: envelope, and no negative bound is stated.  The operator supplies the
#: deployment envelope.
_LINEAR_X = Limit.operator_required(
    "the pinned clone states a CHAMP gait max_linear_vel_x of 0.5 but no signed /cmd_vel "
    "acceptance envelope or negative bound; the operator supplies the installed forward bound"
)
_LINEAR_Y = Limit.operator_required(
    "the pinned clone states a CHAMP gait max_linear_vel_y of 0.25 but no signed /cmd_vel "
    "acceptance envelope or negative bound; the operator supplies the installed lateral bound"
)
_ANGULAR_Z = Limit.operator_required(
    "the pinned clone states a CHAMP gait max_angular_vel_z of 1.0 but no signed /cmd_vel "
    "acceptance envelope or negative bound; the operator supplies the installed yaw-rate bound"
)

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the Twist to rosbridge"),
    "confirmed": Field(
        "boolean",
        description="Always false: a rosbridge publication carries no execution, arrival or stop confirmation",
    ),
}

_SCAN_OUTPUT = {
    "frame_id": Field("string", description="Frame id from the LaserScan header"),
    "angle_min": Field("number", unit="rad", description="First scan angle"),
    "angle_max": Field("number", unit="rad", description="Last scan angle"),
    "angle_increment": Field("number", unit="rad", description="Angular distance between consecutive samples"),
    "time_increment": Field("number", unit="s", description="Time between consecutive samples"),
    "scan_time": Field("number", unit="s", description="Time between scans"),
    "range_min": Field("number", unit="m", description="Minimum range value"),
    "range_max": Field("number", unit="m", description="Maximum range value"),
    "ranges": Field(
        "array",
        unit="m",
        description="Measured ranges in metres; the pinned ray sensor is configured for 800 samples",
        items=Field("number", unit="m", description="One measured range"),
    ),
    "intensities": Field(
        "array",
        description="Per-sample intensities from the LaserScan message",
        items=Field("number", description="One intensity sample"),
    ),
}

#: One explicit Twist publication.  The upstream launch uses the relative
#: name ``cmd_vel``; a deployment resolves it under the robot namespace.
_CMD_VEL = {
    "topic": "/cmd_vel",
    "type": "geometry_msgs/Twist",
    "operation": "publish",
    "source_name": "cmd_vel",
    "source_ref": _CMD_VEL_REF,
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

#: One explicit LaserScan observation.  The costmap citation shows the short
#: type name only; the fully qualified sensor_msgs type is conventional and is
#: not declared in the pinned tree, which is why G7 rejects this binding.
_SCAN = {
    "topic": "/scan",
    "type": "sensor_msgs/LaserScan",
    "operation": "subscribe",
    "source_name": "scan",
    "source_ref": _SCAN_ENDPOINT_REF,
    "type_ref": _SCAN_TYPE_REF,
    "path": "$",
    "timeout_ms": 2000,
    "result": {
        "map": {
            "frame_id": "header.frame_id",
            "angle_min": "angle_min",
            "angle_max": "angle_max",
            "angle_increment": "angle_increment",
            "time_increment": "time_increment",
            "scan_time": "scan_time",
            "range_min": "range_min",
            "range_max": "range_max",
            "ranges": "ranges",
            "intensities": "intensities",
        }
    },
}


class SimulationUnitreeGo1(RosDriver):
    device_id = "taucrates-go1-sim"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    # A commanded mobile base is at least R2; the card floor is R0.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeSimulationUnitreeGo1"}
    tags = ["ros", "ros1", "gazebo", "simulation", "unitree", "go1", "quadruped",
            "mobile-base", "cmd-vel", "laser-scan"]
    display_name = "Unitree Go1 Gazebo simulation (taucrates)"
    vendor = "taucrates"
    model = "Unitree Go1 with CHAMP kinematics in Gazebo"
    facts = [
        Fact("The README states that the repository simulates the Unitree Go1 in Gazebo using the "
             "configuration from champ_setup_assistant and kinematics generated by the champ package, "
             "with a Hokuyo laser and a RealSense installed.",
             source="vendor_doc", ref="README.md:1"),
        Fact("The README states that the package is tested on Ubuntu 20.04 with ROS Noetic.",
             source="vendor_doc", ref="README.md:3"),
        Fact("The README lists Champ, Yocs velocity smoother, the edited RealSense Gazebo plugin, the "
             "RealSense description, Scan Tools and a modified slam_gmapping as required workspace "
             "dependencies.", source="vendor_doc", ref="README.md:15-22"),
        Fact("The README's Gazebo example spawns unitree_go1 and states that it has a Hokuyo laser and a "
             "RealSense installed.", source="vendor_doc", ref="README.md:36-40"),
        Fact("go1_simulation.launch sets use_sim_time true and includes bringup.launch and gazebo.launch.",
             source="upstream_code", ref="go1_simulation/launch/go1_simulation.launch:12-34"),
        Fact("gazebo.launch includes the external gazebo_ros empty_world.launch and forwards a paused "
             "launch argument to it.", source="upstream_code",
             ref="go1_simulation/launch/gazebo.launch:18-24"),
        Fact("gazebo.launch spawns the robot model from robot_description with gazebo_ros spawn_model, "
             "loads the ros_control configuration and spawns the joint_states and joint_group_position "
             "controllers.", source="upstream_code", ref="go1_simulation/launch/gazebo.launch:28-37"),
        Fact("The velocity_smoother launch names the relative cmd_vel raw and robot command topics, the "
             "cmd_vel/smooth intermediate topic and the odom topic, and includes the external "
             "yocs_velocity_smoother launch.", source="upstream_code",
             ref="go1_simulation/launch/velocity_smoother.launch:5-22"),
        Fact("navigate.launch remaps the laser scan matcher's scan, odom and vel topics to scan, odom and "
             "cmd_vel.", source="upstream_code", ref="go1_simulation/launch/navigate.launch:14-18"),
        Fact("The Hokuyo xacro declares a ray sensor with 800 horizontal samples over -3.1415926535897 to "
             "3.1415926535897 rad, and a range of 0.45 to 20 m with 0.01 m resolution.",
             source="upstream_code", ref="go1_description/xacro/hokuyo.xacro:35-51"),
        Fact("The Hokuyo xacro loads libgazebo_ros_laser.so with topicName scan and frameName set from the "
             "laser name, at update_rate 20.", source="upstream_code",
             ref="go1_description/xacro/hokuyo.xacro:62-72"),
        Fact("The gazebo xacro declares an IMU sensor with topicName trunk_imu and updateRateHZ 1000.",
             source="upstream_code", ref="go1_description/xacro/gazebo.xacro:42-59"),
        Fact("The gazebo xacro declares a depth camera sensor at update_rate 20 with a 640 by 480 image, "
             "and the plugin names /camera_link/color/image_raw, /camera_link/depth/image_raw and "
             "/camera_link/depth/points.", source="upstream_code",
             ref="go1_description/xacro/gazebo.xacro:135-159"),
        Fact("The ros_control configuration declares a joint_state_controller at publish_rate 30 and a "
             "joint_group_position_controller of type effort_controllers/JointTrajectoryController for "
             "the twelve leg joints.", source="upstream_code",
             ref="go1_config/config/ros_control/ros_control.yaml:1-20"),
        Fact("The CHAMP gait configuration records max_linear_vel_x 0.5, max_linear_vel_y 0.25 and "
             "max_angular_vel_z 1.0 as gait parameters; it states no signed /cmd_vel acceptance "
             "envelope.", source="upstream_code", ref="go1_config/config.json:197-202"),
        Fact("The gait_config header repeats MAX_LINEAR_VELOCITY_X 0.5, MAX_LINEAR_VELOCITY_Y 0.25 and "
             "MAX_ANGULAR_VELOCITY_Z 1.0 as CHAMP gait constants; they are not a ROS command contract.",
             source="upstream_code", ref="go1_config/include/gait_config.h:7-9"),
    ]
    safe_state = (
        "No acknowledged safe state is declared: the pinned tree exposes no ROS stop, pause or reset "
        "service or action. The paused launch argument in gazebo.launch:6,21 is a launch-time option "
        "forwarded to the external gazebo_ros empty-world launch, not a runtime endpoint; a zero-Twist "
        "publication is transmission only. The package is blocked rather than claiming a stop."
    )
    fidelity = {
        "engine": "analytic:ROS-free rosbridge contract stand-in (no Gazebo physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven rosbridge fake with no Gazebo physics, CHAMP gait, ray sensor, state "
                     "integration, camera or wall-clock pacing; placeholder observations do not establish "
                     "trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free analytic contract stand-in, not a recording of captured traffic: it "
            "runs no Gazebo, gazebo_ros plugins, CHAMP controller, laser sensor, depth camera or ROS graph",
            "the /scan sample is three placeholder ranges; the pinned ray sensor is configured for 800 "
            "samples over -3.1415926535897 to 3.1415926535897 rad at 20 Hz",
            "the /cmd_vel publication is recorded by the fake; no base, leg joint or physics state moves",
            "the depth camera, IMU, odometry, TF, contact sensors, move_base, AMCL and gmapping are not "
            "exposed by this package",
            "the pinned tree declares no fully qualified ROS message type, so the conventional "
            "geometry_msgs/Twist and sensor_msgs/LaserScan names used by the bindings are not verified by "
            "the upstream source and G7 reports ROS_TYPE_NOT_UPSTREAM",
            "the pinned tree exposes no acknowledged ROS stop, pause or reset service or action; G6 reports "
            "the missing safe state",
            "the bridge refuses non-finite numbers, so a scan that carries inf or NaN ranges is refused rather "
            "than returned; whether the external gazebo_ros laser plugin publishes such values for samples "
            "without a return is not shown in the clone",
            "a live run requires the operator's ROS Noetic workspace, the external champ, "
            "yocs_velocity_smoother, gazebo_ros, realsense and scan-matcher packages, Gazebo, the launch "
            "files and rosbridge; none is started or validated here",
        ],
    }

    commands = {
        "x-cap.taucrates.cmd_vel.v1": _CMD_VEL,
        "x-cap.taucrates.scan.v1": _SCAN,
    }
    actions = {
        "x-cap.taucrates.cmd_vel.v1": Action(
            name="publish_cmd_vel",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one geometry_msgs/Twist velocity setpoint to the CHAMP cmd_vel endpoint. The "
                "receipt confirms only that rosbridge accepted the publication, not motion, arrival or "
                "stopping."
            ),
            input={
                "linear_x": Field(
                    "number",
                    unit="m/s",
                    description="Body-frame forward velocity written to twist.linear.x",
                    limit=_LINEAR_X,
                ),
                "linear_y": Field(
                    "number",
                    unit="m/s",
                    description="Body-frame lateral velocity written to twist.linear.y",
                    limit=_LINEAR_Y,
                ),
                "angular_z": Field(
                    "number",
                    unit="rad/s",
                    description="Body-frame yaw rate written to twist.angular.z",
                    limit=_ANGULAR_Z,
                ),
            },
            output=_PUBLISHED,
            examples=[{"linear_x": 0.0, "linear_y": 0.0, "angular_z": 0.0}],
        ),
        "x-cap.taucrates.scan.v1": Action(
            name="read_scan",
            verb="read",
            description="Read one sensor_msgs/LaserScan sample from the scan topic",
            output=_SCAN_OUTPUT,
        ),
    }
    # No runtime stop exists in the pinned source.  The launch-time paused
    # argument is not a service/action and a zero-Twist publication is not an
    # acknowledgement, so no safety binding is invented.
    safety_bindings = {}
