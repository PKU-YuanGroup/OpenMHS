"""OpenMHS rosbridge driver for the ROBOTIS TurtleBot3 mobile base.

The pinned upstream is a C++ ROS 2 package: ``turtlebot3_node`` subscribes to
the relative ``cmd_vel`` topic, publishes sensor state and exposes the relative
``motor_power`` and ``reset`` services.  This package is a configuration-only
:class:`RosDriver` and declares no Python native class.  No ROS graph,
simulator or robot is contacted by the package.

The primary control is one explicit ``geometry_msgs/msg/TwistStamped``
publication on ``/cmd_vel``. The top-level model parameter files select the
stamped variant (``enable_stamped_cmd_vel: true``), but the Humble-specific
files selected by ``robot.launch.py`` set it false. This explicit stamped
profile excludes that shipped Humble configuration. A deployment that leaves the
node default or overrides the parameter to false uses ``Twist`` and must not
use this declaration.  The callback consumes only ``twist.linear.x`` and
``twist.angular.z`` and publishes no motion acknowledgement, so the command
receipt is transmission evidence only.  It does not prove that the base moved,
reached a pose or stopped.

The native stop path is the acknowledged ``std_srvs/srv/SetBool`` service
``motor_power`` with ``data=false``.  That disables the OpenCR motor-torque
enable register; it is not a brake, not a measured zero velocity and not a
hardware emergency stop.  The upstream ``reset`` Trigger is deliberately not
exposed: it writes IMU recalibration, sleeps for five seconds before reporting
success and only logs the asynchronous odometry-reset reply, so it is not a
safety reset.  Enabling torque is exposed as an ordinary command and is never
performed automatically.

Deployment assumptions kept outside the upstream facts: the operator runs the
upstream nodes and rosbridge separately, launches ``turtlebot3_node`` and
``diff_drive_controller`` in the root namespace of the shipped launch (or
remaps the declared absolute names), and signs ``driver.lock.json`` with a
human hardware review before any hardware backend exists.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The node constructs TwistSubscriber with the relative topic name "cmd_vel".
_CMD_VEL_REF = "turtlebot3_node/src/turtlebot3.cpp:334-336"

#: The TwistStamped include in the subscriber wrapper names the configured type.
_CMD_VEL_TYPE_REF = "turtlebot3_node/include/turtlebot3_node/twist_subscriber.hpp:25"

#: The node registers the relative "motor_power" service.
_MOTOR_POWER_REF = "turtlebot3_node/src/turtlebot3.cpp:213-214"

#: MotorPower's constructor creates a std_srvs::srv::SetBool service.
_MOTOR_POWER_TYPE_REF = "turtlebot3_node/src/devices/motor_power.cpp:31-38"

#: The relative "battery_state" publisher and its declared message type.
_BATTERY_REF = "turtlebot3_node/src/turtlebot3.cpp:179-182"
_BATTERY_TYPE_REF = "turtlebot3_node/src/sensors/battery_state.cpp:30"

#: The relative "sensor_state" publisher and its declared message type.
_SENSOR_STATE_REF = "turtlebot3_node/src/turtlebot3.cpp:191-194"
_SENSOR_STATE_TYPE_REF = "turtlebot3_node/src/sensors/sensor_state.cpp:40"

#: The relative "joint_states" publisher and its declared message type.
_JOINT_STATES_REF = "turtlebot3_node/src/turtlebot3.cpp:202-206"
_JOINT_STATES_TYPE_REF = "turtlebot3_node/src/sensors/joint_state.cpp:37"

#: The diff_drive_controller node publishes odometry on the relative name "odom".
_ODOM_REF = "turtlebot3_node/src/odometry.cpp:81"

#: The model-specific teleoperation velocity caps: Burger 0.22 m/s and
#: 2.84 rad/s, Waffle/Waffle Pi 0.26 m/s and 1.82 rad/s.  This driver declares
#: no signed lower endpoint from these positive magnitudes is treated as a citation.
_TELEOP_CAPS_REF = "turtlebot3_teleop/turtlebot3_teleop/script/teleop_keyboard.py:50-54"

_SPEED_LIMIT = Limit.operator_required(
    "the source gives positive teleoperation cap magnitudes, not a sourced signed site envelope; "
    "the operator supplies both forward and reverse velocity bounds"
)
_TURN_LIMIT = Limit.operator_required(
    "the source gives positive teleoperation cap magnitudes, not a sourced signed site envelope; "
    "the operator supplies both yaw-rate bounds"
)

#: One explicit TwistStamped publication.  A rosbridge publish is a
#: transmission, not a measured arrival, pose or stop.
_CMD_VEL = {
    "topic": "/cmd_vel",
    "type": "geometry_msgs/msg/TwistStamped",
    "operation": "publish",
    "source_name": "cmd_vel",
    "source_ref": _CMD_VEL_REF,
    "type_ref": _CMD_VEL_TYPE_REF,
    "message": {
        "header": {},
        "twist": {
            "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
    },
    "args": {
        "twist.linear.x": {"from": "input.linear_velocity"},
        "twist.angular.z": {"from": "input.angular_velocity"},
    },
}

#: The acknowledged upstream torque-enable service.  The application predicate
#: is the SetBool response's own success flag, not a velocity measurement.
_MOTOR_POWER = {
    "service": "/motor_power",
    "type": "std_srvs/srv/SetBool",
    "source_name": "motor_power",
    "source_ref": _MOTOR_POWER_REF,
    "type_ref": _MOTOR_POWER_TYPE_REF,
    "request": {},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"success": "success", "message": "message"}},
}

#: Fixed, input-free torque-disable service request used by the safe-state
#: action and by the native e-stop binding.
_MOTOR_OFF = dict(
    _MOTOR_POWER,
    request={"data": False},
    args={},
)

_CMD_VEL_OUTPUT = {
    "published": Field("boolean", description="True when the driver handed the TwistStamped to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution confirmation"),
}

_MOTOR_OUTPUT = {
    "success": Field("boolean", description="The upstream SetBool response success flag"),
    "message": Field("string", description="The upstream SetBool response message text"),
}

_BATTERY_VOLTAGE = Field("number", unit="V",
                         description="BatteryState voltage published by the node (0.01 times the raw register)")
_BATTERY_PERCENTAGE = Field("number", unit="1",
                            description="BatteryState percentage published by the node as a 0..1 ratio")
_BATTERY_PRESENT = Field("boolean",
                         description="BatteryState present flag computed by the node (false at <= 7.0 V)")

_ODOM_POSE = Field(
    "object",
    description="nav_msgs/Odometry pose selected from message field pose.pose",
    properties={
        "position": Field("object", description="Position in the odometry frame",
                          properties={
                              "x": Field("number", unit="m", description="Position x"),
                              "y": Field("number", unit="m", description="Position y"),
                              "z": Field("number", unit="m", description="Position z"),
                          }),
        "orientation": Field("object", description="Orientation as a unit quaternion",
                             properties={
                                 "x": Field("number", unit="1", description="Quaternion x"),
                                 "y": Field("number", unit="1", description="Quaternion y"),
                                 "z": Field("number", unit="1", description="Quaternion z"),
                                 "w": Field("number", unit="1", description="Quaternion w"),
                             }),
    },
)

_ODOM_TWIST = Field(
    "object",
    description="nav_msgs/Odometry twist selected from message field twist.twist; the fake echoes the last "
                "published setpoint here as a placeholder, so this is contract data, not measured motion",
    properties={
        "linear": Field("object", description="Linear velocity",
                        properties={
                            "x": Field("number", unit="m/s", description="Linear x"),
                            "y": Field("number", unit="m/s", description="Linear y"),
                            "z": Field("number", unit="m/s", description="Linear z"),
                        }),
        "angular": Field("object", description="Angular velocity",
                         properties={
                             "x": Field("number", unit="rad/s", description="Angular x"),
                             "y": Field("number", unit="rad/s", description="Angular y"),
                             "z": Field("number", unit="rad/s", description="Angular z"),
                         }),
    },
)

_WHEEL_VELOCITY = Field(
    "array",
    unit="m/s",
    description="Two wheel velocities published in sensor_msgs/JointState velocity, in wheel order",
    items=Field("number", unit="m/s"),
    length=2,
)


class Turtlebot3(RosDriver):
    device_id = "turtlebot3"
    device_kind = "robot.mobile_base"
    mode = "hardware"
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeTurtlebot3"}
    tags = ["ros", "ros2", "robotis", "turtlebot3", "mobile-base", "cmd-vel", "motor-power"]
    display_name = "ROBOTIS TurtleBot3 mobile base"
    vendor = "ROBOTIS"
    model = "TurtleBot3 Burger / Waffle / Waffle Pi"
    facts = [
        Fact("The turtlebot3_node package is a ROS 2 ament_cmake package that depends on rclcpp.",
             source="upstream_code", ref="turtlebot3_node/package.xml:18-23"),
        Fact("The bringup launch selects param/humble/<model>.yaml on Humble and param/<model>.yaml otherwise.",
             source="upstream_code", ref="turtlebot3_bringup/launch/robot.launch.py:42-55"),
        Fact("The Humble Burger parameter file disables stamped cmd_vel.",
             source="upstream_code", ref="turtlebot3_bringup/param/humble/burger.yaml:5"),
        Fact("The Humble Waffle parameter file disables stamped cmd_vel.", source="upstream_code",
             ref="turtlebot3_bringup/param/humble/waffle.yaml:5"),
        Fact("The Humble Waffle Pi parameter file disables stamped cmd_vel.", source="upstream_code",
             ref="turtlebot3_bringup/param/humble/waffle_pi.yaml:5"),
        Fact("The Burger bringup parameter file sets enable_stamped_cmd_vel to true.",
             source="upstream_code", ref="turtlebot3_bringup/param/burger.yaml:5"),
        Fact("The Waffle bringup parameter file sets enable_stamped_cmd_vel to true.",
             source="upstream_code", ref="turtlebot3_bringup/param/waffle.yaml:5"),
        Fact("The Waffle Pi bringup parameter file sets enable_stamped_cmd_vel to true.",
             source="upstream_code", ref="turtlebot3_bringup/param/waffle_pi.yaml:5"),
        Fact("TwistSubscriber declares enable_stamped_cmd_vel false when the parameter is absent, then reads "
             "it and subscribes geometry_msgs::msg::TwistStamped when true or geometry_msgs::msg::Twist "
             "otherwise.",
             source="upstream_code",
             ref="turtlebot3_node/include/turtlebot3_node/twist_subscriber.hpp:86-99"),
        Fact("TurtleBot3::cmd_vel_callback constructs TwistSubscriber with the relative topic name "
             "\"cmd_vel\".",
             source="upstream_code", ref=_CMD_VEL_REF),
        Fact("The TwistStamped callback uses only twist.linear.x and twist.angular.z, multiplies each by "
             "100, casts to int32, writes the six-register velocity block to the OpenCR, and returns void "
             "after a debug log; it publishes no motion acknowledgement or stop timer.",
             source="upstream_code", ref="turtlebot3_node/src/turtlebot3.cpp:370-405"),
        Fact("TurtleBot3::add_devices registers the relative \"motor_power\" service.",
             source="upstream_code", ref=_MOTOR_POWER_REF),
        Fact("MotorPower's constructor creates a std_srvs::srv::SetBool service on the supplied server "
             "name.",
             source="upstream_code", ref=_MOTOR_POWER_TYPE_REF),
        Fact("MotorPower::command writes request.data to the motor_torque_enable control-table address "
             "and returns the Dynamixel SDK write's success/message; it does not write a velocity setpoint "
             "or wait for the wheels to stop.",
             source="upstream_code", ref="turtlebot3_node/src/devices/motor_power.cpp:42-51"),
        Fact("TurtleBot3::add_sensors constructs the relative \"battery_state\" publisher.",
             source="upstream_code", ref=_BATTERY_REF),
        Fact("The battery_state publisher is sensor_msgs::msg::BatteryState.",
             source="upstream_code", ref=_BATTERY_TYPE_REF),
        Fact("BatteryState::publish sets design_capacity 1.8, voltage as 0.01 times the battery_voltage "
             "register, percentage as 0.01 times the battery_percentage register, and present false when "
             "voltage is at most 7.0.",
             source="upstream_code", ref="turtlebot3_node/src/sensors/battery_state.cpp:43-53"),
        Fact("TurtleBot3::add_sensors constructs the relative \"sensor_state\" publisher.",
             source="upstream_code", ref=_SENSOR_STATE_REF),
        Fact("The sensor_state publisher is turtlebot3_msgs::msg::SensorState.",
             source="upstream_code", ref=_SENSOR_STATE_TYPE_REF),
        Fact("SensorState::publish reads the motor_torque_enable register into msg->torque.",
             source="upstream_code", ref="turtlebot3_node/src/sensors/sensor_state.cpp:117-119"),
        Fact("TurtleBot3::add_sensors constructs the relative \"joint_states\" publisher.",
             source="upstream_code", ref=_JOINT_STATES_REF),
        Fact("The joint_states publisher is sensor_msgs::msg::JointState.",
             source="upstream_code", ref=_JOINT_STATES_TYPE_REF),
        Fact("JointState::publish pushes two wheel velocities converted by RPM_TO_MS.",
             source="upstream_code", ref="turtlebot3_node/src/sensors/joint_state.cpp:98-99"),
        Fact("The diff_drive_controller node publishes nav_msgs::msg::Odometry on the relative name "
             "\"odom\".",
             source="upstream_code", ref=_ODOM_REF),
        Fact("The node registers the relative \"reset\" service.",
             source="upstream_code", ref="turtlebot3_node/src/turtlebot3.cpp:215-216"),
        Fact("Reset::command writes an IMU recalibration, sleeps five seconds, sets success=true, and then "
             "only logs the asynchronous reset_odometry reply.",
             source="upstream_code", ref="turtlebot3_node/src/devices/reset.cpp:51-78"),
        Fact("The teleoperation script caps Burger at 0.22 m/s and 2.84 rad/s and Waffle/Waffle Pi at "
             "0.26 m/s and 1.82 rad/s; these are teleoperation caps, not measured hardware limits.",
             source="upstream_code", ref=_TELEOP_CAPS_REF),
    ]
    safe_state = (
        "The acknowledged /motor_power std_srvs/SetBool service with data=false disables the OpenCR "
        "motor-torque enable register; this is a torque-disable acknowledgement only, not a brake, not a "
        "measured zero velocity and not a hardware emergency stop."
    )

    parameters = {
        "battery_voltage": _BATTERY_VOLTAGE,
        "battery_percentage": _BATTERY_PERCENTAGE,
        "battery_present": _BATTERY_PRESENT,
        "odom_pose": _ODOM_POSE,
        "odom_twist": _ODOM_TWIST,
        "wheel_velocity": _WHEEL_VELOCITY,
        "torque_enabled": Field("boolean",
                                description="SensorState torque flag read from the motor_torque_enable register"),
    }
    reads = {
        "battery_voltage": {
            "topic": "/battery_state",
            "type": "sensor_msgs/msg/BatteryState",
            "source_name": "battery_state",
            "source_ref": _BATTERY_REF,
            "type_ref": _BATTERY_TYPE_REF,
            "path": "voltage",
            "timeout_ms": 2000,
        },
        "battery_percentage": {
            "topic": "/battery_state",
            "type": "sensor_msgs/msg/BatteryState",
            "source_name": "battery_state",
            "source_ref": _BATTERY_REF,
            "type_ref": _BATTERY_TYPE_REF,
            "path": "percentage",
            "timeout_ms": 2000,
        },
        "battery_present": {
            "topic": "/battery_state",
            "type": "sensor_msgs/msg/BatteryState",
            "source_name": "battery_state",
            "source_ref": _BATTERY_REF,
            "type_ref": _BATTERY_TYPE_REF,
            "path": "present",
            "timeout_ms": 2000,
        },
        "odom_pose": {
            "topic": "/odom",
            "type": "nav_msgs/msg/Odometry",
            "source_name": "odom",
            "source_ref": _ODOM_REF,
            "path": "pose.pose",
            "timeout_ms": 2000,
        },
        "odom_twist": {
            "topic": "/odom",
            "type": "nav_msgs/msg/Odometry",
            "source_name": "odom",
            "source_ref": _ODOM_REF,
            "path": "twist.twist",
            "timeout_ms": 2000,
        },
        "wheel_velocity": {
            "topic": "/joint_states",
            "type": "sensor_msgs/msg/JointState",
            "source_name": "joint_states",
            "source_ref": _JOINT_STATES_REF,
            "type_ref": _JOINT_STATES_TYPE_REF,
            "path": "velocity",
            "timeout_ms": 2000,
        },
        "torque_enabled": {
            "topic": "/sensor_state",
            "type": "turtlebot3_msgs/msg/SensorState",
            "source_name": "sensor_state",
            "source_ref": _SENSOR_STATE_REF,
            "type_ref": _SENSOR_STATE_TYPE_REF,
            "path": "torque",
            "timeout_ms": 2000,
        },
    }
    commands = {
        "x-cap.robotis-git.cmd_vel.v1": _CMD_VEL,
        "x-cap.robotis-git.motor_power.v1": dict(
            _MOTOR_POWER,
            args={"data": {"from": "input.enabled"}},
        ),
        "x-cap.robotis-git.disable_torque.v1": _MOTOR_OFF,
    }
    actions = {
        "x-cap.robotis-git.cmd_vel.v1": Action(
            name="publish_velocity",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one geometry_msgs/TwistStamped velocity setpoint to the upstream cmd_vel topic; "
                "the receipt confirms only that rosbridge accepted the publication, not motion, arrival or "
                "stopping"
            ),
            input={
                "linear_velocity": Field(
                    "number", unit="m/s",
                    description="Body-frame forward velocity; the callback uses only twist.linear.x",
                    limit=_SPEED_LIMIT,
                ),
                "angular_velocity": Field(
                    "number", unit="rad/s",
                    description="Body-frame yaw rate; the callback uses only twist.angular.z",
                    limit=_TURN_LIMIT,
                ),
            },
            output=_CMD_VEL_OUTPUT,
        ),
        "x-cap.robotis-git.motor_power.v1": Action(
            name="set_motor_power",
            verb="invoke",
            risk="R2",
            description=(
                "Call the upstream std_srvs/SetBool motor_power service to enable or disable motor torque; "
                "enabling does not clear a stale cmd_vel setpoint published by another ROS client"
            ),
            input={
                "enabled": Field(
                    "boolean",
                    description="true requests motor torque enable, false requests torque disable; false is "
                                "not a brake or a stopped-state measurement",
                ),
            },
            output=_MOTOR_OUTPUT,
        ),
        "x-cap.robotis-git.disable_torque.v1": Action(
            name="disable_torque",
            verb="invoke",
            safe_state=True,
            description=(
                "Fixed, input-free std_srvs/SetBool(false) request to the upstream motor_power service; it "
                "disables motor torque and reports only the upstream write acknowledgement"
            ),
            output=_MOTOR_OUTPUT,
        ),
    }
    # The native e-stop path is the same fixed torque-disable request.  The
    # runtime latches before it calls this binding; external ROS publishers and
    # the physical coast are not stopped by the acknowledgement.
    safety_bindings = {"estop": _MOTOR_OFF}
