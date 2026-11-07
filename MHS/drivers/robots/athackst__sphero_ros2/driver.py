"""OpenMHS rosbridge driver for the pinned Sphero ROS 2 node (gh.athackst/sphero_ros2).

The upstream ``sphero_node`` is a Python ROS 2 node (``rclpy``) that wraps the
Bluetooth ``sphero_driver`` package.  This package is a configuration-only
:class:`RosDriver`; it declares no Python native class and neither imports nor
starts the upstream code.  The operator runs the node and rosbridge separately.

The node exposes only ROS topics: four publishers (``odom``, ``imu``,
``collision`` and ``/diagnostics``) and six subscriptions (``cmd_vel``,
``set_color``, ``set_back_led``, ``disable_stabilization``, ``set_heading`` and
``set_angular_velocity``).  It creates no ROS service or action server, so this
declaration can expose no acknowledged stop binding.  The node's own
``cmd_vel_timeout`` rolls the ball to zero after 0.6 s without a command, and
its shutdown-only ``stop()`` method rolls zero and disconnects; neither is a
ROS-accessible, acknowledged safe state and neither is an independent hardware
e-stop.  A zero-velocity publication is transmission-only.  The package is
therefore an honest partial declaration: G3 refuses the R2 mobile base for the
missing independent stop (``NO_HARDWARE_FREE_PATH``), and this file does not
pretend that a topic publication proves that the ball stopped.

The callback consumes ``twist.linear.x`` and ``twist.linear.y`` only.  It
derives ``speed = hypot(x, y)`` and ``heading = atan2(x, y)`` and passes the
truncated values to the native ``roll`` command, whose documented range is
0..255 and 0..359 degrees.  The source states no physical unit for the ROS
``Twist`` components, so the inputs are declared in the raw native count rather
than inventing m/s.  ``twist.angular.z`` is ignored and is not exposed.

Every endpoint, type and fact cites the pinned clone at
bcbb7e12172c559eaa298484c94c1c6ed0ebcd14.  The fake transport is ROS-free and
all of its numbers are placeholders.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: ``_init_pubsub`` creates the four publishers and six subscriptions.
_PUBSUB_REF = "sphero_node/sphero.py:65-75"

#: Type imports in the node.
_IMU_TYPE_REF = "sphero_node/sphero.py:15"
_ODOM_TYPE_REF = "sphero_node/sphero.py:16"
_TWIST_TYPE_REF = "sphero_node/sphero.py:17"
_COLLISION_TYPE_REF = "sphero_node/sphero.py:18"
_STD_TYPE_REF = "sphero_node/sphero.py:19"
_DIAG_TYPE_REF = "sphero_node/sphero.py:20"

#: Individual publisher/subscription registrations.
_ODOM_REF = "sphero_node/sphero.py:66"
_IMU_REF = "sphero_node/sphero.py:67"
_COLLISION_REF = "sphero_node/sphero.py:68"
_DIAG_REF = "sphero_node/sphero.py:69"
_CMD_VEL_REF = "sphero_node/sphero.py:70"
_COLOR_REF = "sphero_node/sphero.py:71"
_BACK_LED_REF = "sphero_node/sphero.py:72"
_STABILIZATION_REF = "sphero_node/sphero.py:73"
_HEADING_REF = "sphero_node/sphero.py:74"
_ANGULAR_VELOCITY_REF = "sphero_node/sphero.py:75"

#: Native driver documentation and clamping.
_ROLL_DOC_REF = "sphero_driver/src/sphero_driver/sphero_driver.py:675-690"
_RGB_DOC_REF = "sphero_driver/src/sphero_driver/sphero_driver.py:640-654"
_BACK_LED_DOC_REF = "sphero_driver/src/sphero_driver/sphero_driver.py:656-664"
_HEADING_DOC_REF = "sphero_driver/src/sphero_driver/sphero_driver.py:471-482"
_STABILIZATION_DOC_REF = "sphero_driver/src/sphero_driver/sphero_driver.py:484-494"
_ROTATION_DOC_REF = "sphero_driver/src/sphero_driver/sphero_driver.py:496-509"

_SPEED_LIMIT = Limit.operator_required(
    "the callback truncates hypot(linear.x, linear.y) to int and the native roll command documents "
    "0..255 counts, but the clone states no bound for the ROS Twist components and no physical unit; "
    "the operator supplies the site envelope"
)
_COLOR_LIMIT = Limit.operator_required(
    "the callback multiplies each ColorRGBA component by 255 and the native setter clamps the result "
    "to 0..255; the clone states no bound for the ROS component, so the operator supplies it"
)
_HEADING_LIMIT = Limit.operator_required(
    "the callback normalizes any Float32 angle with fmod and converts it to whole degrees; the clone "
    "states no bound for the ROS input, so the operator supplies the site envelope"
)
_ROTATION_LIMIT = Limit.operator_required(
    "the callback converts the Float32 value to native rotation-rate counts of 0.784 degrees/s and the "
    "native setter clamps those counts to 0..255, but the clone states no bound for the ROS input; "
    "the operator supplies the site envelope"
)

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
_ODOM_POSE = Field(
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
_ODOM_TWIST = Field(
    "object",
    description="nav_msgs/Odometry twist selected from message field twist.twist",
    properties={"linear": _LINEAR, "angular": _ANGULAR},
)
_IMU_ORIENTATION = Field(
    "object",
    description="Quaternion selected from sensor_msgs/Imu orientation",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)
_IMU_LINEAR_ACCELERATION = Field(
    "object",
    description="Linear acceleration selected from sensor_msgs/Imu linear_acceleration",
    properties={
        "x": Field("number", unit="m/s2", description="Linear acceleration x"),
        "y": Field("number", unit="m/s2", description="Linear acceleration y"),
        "z": Field("number", unit="m/s2", description="Linear acceleration z"),
    },
)
_IMU_ANGULAR_VELOCITY = Field(
    "object",
    description="Angular velocity selected from sensor_msgs/Imu angular_velocity",
    properties={
        "x": Field("number", unit="rad/s", description="Angular velocity x"),
        "y": Field("number", unit="rad/s", description="Angular velocity y"),
        "z": Field("number", unit="rad/s", description="Angular velocity z"),
    },
)
_COLLISION = Field(
    "object",
    description="sphero_msgs/SpheroCollision sample; the message declares only int32 fields and states no units",
    properties={
        "x": Field("integer", unit="1", description="Raw collision X field"),
        "y": Field("integer", unit="1", description="Raw collision Y field"),
        "z": Field("integer", unit="1", description="Raw collision Z field"),
        "axis": Field("integer", unit="1", description="Raw collision axis field"),
        "x_magnitude": Field("integer", unit="1", description="Raw x magnitude field"),
        "y_magnitude": Field("integer", unit="1", description="Raw y magnitude field"),
        "speed": Field("integer", unit="1", description="Raw collision speed field"),
        "timestamp": Field("integer", unit="1", description="Raw collision timestamp field"),
    },
)
_BATTERY_STATUS = Field(
    "string",
    description="DiagnosticStatus message from the first /diagnostics status entry; the node publishes it only "
                "after the cmd_vel timeout branch runs",
)

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the publication to rosbridge"),
    "confirmed": Field("boolean", description="Always false: a rosbridge publication carries no execution confirmation"),
}

_CMD_VEL = {
    "topic": "/cmd_vel",
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
    },
}

_COLOR = {
    "topic": "/set_color",
    "type": "std_msgs/msg/ColorRGBA",
    "operation": "publish",
    "source_name": "set_color",
    "source_ref": _COLOR_REF,
    "type_ref": _STD_TYPE_REF,
    "message": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 1.0},
    "args": {
        "r": {"from": "input.red"},
        "g": {"from": "input.green"},
        "b": {"from": "input.blue"},
    },
}

_BACK_LED = {
    "topic": "/set_back_led",
    "type": "std_msgs/msg/Float32",
    "operation": "publish",
    "source_name": "set_back_led",
    "source_ref": _BACK_LED_REF,
    "type_ref": _STD_TYPE_REF,
    "message": {"data": 0.0},
    "args": {"data": {"from": "input.brightness"}},
}

_STABILIZATION = {
    "topic": "/disable_stabilization",
    "type": "std_msgs/msg/Bool",
    "operation": "publish",
    "source_name": "disable_stabilization",
    "source_ref": _STABILIZATION_REF,
    "type_ref": _STD_TYPE_REF,
    "message": {"data": False},
    "args": {"data": {"from": "input.disabled"}},
}

_HEADING = {
    "topic": "/set_heading",
    "type": "std_msgs/msg/Float32",
    "operation": "publish",
    "source_name": "set_heading",
    "source_ref": _HEADING_REF,
    "type_ref": _STD_TYPE_REF,
    "message": {"data": 0.0},
    "args": {"data": {"from": "input.heading_rad"}},
}

_ANGULAR_VELOCITY = {
    "topic": "/set_angular_velocity",
    "type": "std_msgs/msg/Float32",
    "operation": "publish",
    "source_name": "set_angular_velocity",
    "source_ref": _ANGULAR_VELOCITY_REF,
    "type_ref": _STD_TYPE_REF,
    "message": {"data": 0.0},
    "args": {"data": {"from": "input.angular_velocity_rad"}},
}

_STOP = {
    "topic": "/cmd_vel",
    "type": "geometry_msgs/msg/Twist",
    "operation": "publish",
    "source_name": "cmd_vel",
    "source_ref": _CMD_VEL_REF,
    "type_ref": _TWIST_TYPE_REF,
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
}


class SpheroRos2(RosDriver):
    device_id = "sphero_ros2"
    device_kind = "robot.mobile_base"
    mode = "hardware"
    # The card's floor is R1, but MHS 04-safety classifies mobile-base transit as R2.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeSpheroRos2"}
    tags = ["ros", "ros2", "sphero", "mobile-base", "cmd-vel", "led", "imu", "odometry"]
    display_name = "Sphero ROS 2 node"
    vendor = "Allison Thackston"
    model = "Sphero 2.0 / SPRK+ (sphero_ros2 node)"
    facts = [
        Fact("SpheroNode is an rclpy Node subclass constructed with the node name \"sphero\".",
             source="upstream_code", ref="sphero_node/sphero.py:23-46"),
        Fact("_init_pubsub creates the odom, imu, collision and /diagnostics publishers and the cmd_vel, "
             "set_color, set_back_led, disable_stabilization, set_heading and set_angular_velocity "
             "subscriptions; it creates no ROS service or action.",
             source="upstream_code", ref=_PUBSUB_REF),
        Fact("The odom publisher is nav_msgs/Odometry and is registered on the relative name \"odom\".",
             source="upstream_code", ref=_ODOM_REF),
        Fact("The imu publisher is sensor_msgs/Imu and is registered on the relative name \"imu\".",
             source="upstream_code", ref=_IMU_REF),
        Fact("The collision publisher is sphero_msgs/SpheroCollision and is registered on the relative name "
             "\"collision\".",
             source="upstream_code", ref=_COLLISION_REF),
        Fact("The /diagnostics publisher is diagnostic_msgs/DiagnosticArray.",
             source="upstream_code", ref=_DIAG_REF),
        Fact("The cmd_vel subscriber is geometry_msgs/Twist and is registered on the relative name \"cmd_vel\".",
             source="upstream_code", ref=_CMD_VEL_REF),
        Fact("The set_color subscriber is std_msgs/ColorRGBA and is registered on the relative name "
             "\"set_color\".",
             source="upstream_code", ref=_COLOR_REF),
        Fact("The set_back_led subscriber is std_msgs/Float32 and is registered on the relative name "
             "\"set_back_led\".",
             source="upstream_code", ref=_BACK_LED_REF),
        Fact("The disable_stabilization subscriber is std_msgs/Bool and is registered on the relative name "
             "\"disable_stabilization\".",
             source="upstream_code", ref=_STABILIZATION_REF),
        Fact("The set_heading subscriber is std_msgs/Float32 and is registered on the relative name "
             "\"set_heading\".",
             source="upstream_code", ref=_HEADING_REF),
        Fact("The set_angular_velocity subscriber is std_msgs/Float32 and is registered on the relative name "
             "\"set_angular_velocity\".",
             source="upstream_code", ref=_ANGULAR_VELOCITY_REF),
        Fact("The cmd_vel callback sets heading to normalize_angle_positive(atan2(linear.x, linear.y)) in "
             "degrees and speed to hypot(linear.x, linear.y), truncates both with int(), and calls "
             "robot.roll(speed, heading, 1, False); it ignores twist.angular.z and publishes no motion "
             "acknowledgement.",
             source="upstream_code", ref="sphero_node/sphero.py:209-214"),
        Fact("The cmd_vel timeout is set to 0.6 s.",
             source="upstream_code", ref="sphero_node/sphero.py:81"),
        Fact("The timer callback rolls zero when the cmd_vel timeout has elapsed and the last commanded "
             "heading or speed was nonzero, then publishes diagnostics once per second.",
             source="upstream_code", ref="sphero_node/sphero.py:115-126"),
        Fact("The only stop() method is the node shutdown path: it rolls zero, sets shutdown, sleeps one "
             "second, disconnects and joins; it is not registered as a ROS service or action.",
             source="upstream_code", ref="sphero_node/sphero.py:128-134"),
        Fact("The set_color callback multiplies ColorRGBA r, g and b by 255 and passes the truncated values to "
             "set_rgb_led with save=0.",
             source="upstream_code", ref="sphero_node/sphero.py:216-218"),
        Fact("The set_back_led callback passes Float32 data unchanged to robot.set_back(data, False).",
             source="upstream_code", ref="sphero_node/sphero.py:220-222"),
        Fact("The set_stabilization callback passes 1 to set_stablization when the Bool is false and 0 when it "
             "is true.",
             source="upstream_code", ref="sphero_node/sphero.py:224-229"),
        Fact("The set_heading callback normalizes Float32 radians, converts to whole degrees and calls "
             "set_heading.",
             source="upstream_code", ref="sphero_node/sphero.py:231-234"),
        Fact("The set_angular_velocity callback converts Float32 radians per second to int((value*180/pi)/0.784) "
             "and calls set_rotation_rate.",
             source="upstream_code", ref="sphero_node/sphero.py:236-241"),
        Fact("The native roll command documents speed 0..255 and heading 0..359 degrees and clamps speed to "
             "0..255 before packing.",
             source="upstream_code", ref=_ROLL_DOC_REF),
        Fact("The native set_rgb_led command clamps red, green and blue each to 0..255 before packing.",
             source="upstream_code", ref=_RGB_DOC_REF),
        Fact("The native set_back_led command documents brightness 0..255 and clamps it to 0..255.",
             source="upstream_code", ref=_BACK_LED_DOC_REF),
        Fact("The native set_heading command documents a heading range of 0..359 degrees.",
             source="upstream_code", ref=_HEADING_DOC_REF),
        Fact("The native set_stablization command documents 00h for off and 01h for on.",
             source="upstream_code", ref=_STABILIZATION_DOC_REF),
        Fact("The native set_rotation_rate command documents units of 0.784 degrees/s, 255 as the maximum and "
             "1 as the minimum, and clamps the rate to 0..255.",
             source="upstream_code", ref=_ROTATION_DOC_REF),
        Fact("SpheroCollision declares one std_msgs/Header and eight int32 fields (x, y, z, axis, x_magnitude, "
             "y_magnitude, speed, timestamp) with no unit annotations.",
             source="upstream_code", ref="sphero_msgs/msg/SpheroCollision.msg:1-9"),
    ]
    safe_state = (
        "No acknowledged ROS stop exists: the node offers only a zero cmd_vel publication, a 0.6 s "
        "no-command roll(0,0) timer and a shutdown-only stop() method, none of which is a ROS-accessible "
        "acknowledged safe state or an independent hardware e-stop."
    )

    parameters = {
        "odom_pose": _ODOM_POSE,
        "odom_twist": _ODOM_TWIST,
        "imu_orientation": _IMU_ORIENTATION,
        "imu_linear_acceleration": _IMU_LINEAR_ACCELERATION,
        "imu_angular_velocity": _IMU_ANGULAR_VELOCITY,
        "collision": _COLLISION,
        "battery_status": _BATTERY_STATUS,
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
        "imu_orientation": {
            "topic": "/imu",
            "type": "sensor_msgs/msg/Imu",
            "operation": "subscribe",
            "source_name": "imu",
            "source_ref": _IMU_REF,
            "type_ref": _IMU_TYPE_REF,
            "path": "orientation",
            "timeout_ms": 2000,
        },
        "imu_linear_acceleration": {
            "topic": "/imu",
            "type": "sensor_msgs/msg/Imu",
            "operation": "subscribe",
            "source_name": "imu",
            "source_ref": _IMU_REF,
            "type_ref": _IMU_TYPE_REF,
            "path": "linear_acceleration",
            "timeout_ms": 2000,
        },
        "imu_angular_velocity": {
            "topic": "/imu",
            "type": "sensor_msgs/msg/Imu",
            "operation": "subscribe",
            "source_name": "imu",
            "source_ref": _IMU_REF,
            "type_ref": _IMU_TYPE_REF,
            "path": "angular_velocity",
            "timeout_ms": 2000,
        },
        "collision": {
            "topic": "/collision",
            "type": "sphero_msgs/msg/SpheroCollision",
            "operation": "subscribe",
            "source_name": "collision",
            "source_ref": _COLLISION_REF,
            "type_ref": _COLLISION_TYPE_REF,
            "path": "$",
            "timeout_ms": 2000,
        },
        "battery_status": {
            "topic": "/diagnostics",
            "type": "diagnostic_msgs/msg/DiagnosticArray",
            "operation": "subscribe",
            "source_name": "/diagnostics",
            "source_ref": _DIAG_REF,
            "type_ref": _DIAG_TYPE_REF,
            "path": "status.0.message",
            "timeout_ms": 2000,
        },
    }
    commands = {
        "x-cap.athackst.cmd_vel.v1": _CMD_VEL,
        "x-cap.athackst.set_color.v1": _COLOR,
        "x-cap.athackst.set_back_led.v1": _BACK_LED,
        "x-cap.athackst.disable_stabilization.v1": _STABILIZATION,
        "x-cap.athackst.set_heading.v1": _HEADING,
        "x-cap.athackst.set_angular_velocity.v1": _ANGULAR_VELOCITY,
        "x-cap.athackst.stop.v1": _STOP,
    }
    actions = {
        "x-cap.athackst.cmd_vel.v1": Action(
            name="publish_cmd_vel",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one geometry_msgs/Twist to the upstream cmd_vel subscription; the callback uses "
                "linear.x and linear.y to derive native speed and heading, truncates both, and publishes no "
                "motion acknowledgement. The receipt proves only that rosbridge accepted the publication."
            ),
            input={
                "linear_x": Field(
                    "number", unit="1",
                    description="Raw Twist linear.x; the callback forms atan2(x, y) heading and hypot(x, y) speed",
                    limit=_SPEED_LIMIT,
                ),
                "linear_y": Field(
                    "number", unit="1",
                    description="Raw Twist linear.y; the callback uses it as the heading reference (y is forward)",
                    limit=_SPEED_LIMIT,
                ),
            },
            output=_PUBLISHED,
            examples=[{"linear_x": 0.0, "linear_y": 0.0}],
        ),
        "x-cap.athackst.set_color.v1": Action(
            name="publish_color",
            verb="invoke",
            risk="R1",
            description=(
                "Publish one std_msgs/ColorRGBA to set_color; the callback multiplies r, g and b by 255 and "
                "drives the native RGB LED. The receipt is a publication acknowledgement only."
            ),
            input={
                "red": Field("number", unit="1", description="ColorRGBA r component",
                             limit=_COLOR_LIMIT),
                "green": Field("number", unit="1", description="ColorRGBA g component",
                               limit=_COLOR_LIMIT),
                "blue": Field("number", unit="1", description="ColorRGBA b component",
                              limit=_COLOR_LIMIT),
            },
            output=_PUBLISHED,
            examples=[{"red": 0.0, "green": 0.0, "blue": 0.0}],
        ),
        "x-cap.athackst.set_back_led.v1": Action(
            name="publish_back_led",
            verb="invoke",
            risk="R1",
            description=(
                "Publish one std_msgs/Float32 brightness to set_back_led; the native command clamps it to "
                "0..255. The receipt is a publication acknowledgement only."
            ),
            input={
                "brightness": Field(
                    "number", unit="1",
                    description="Back-LED brightness in the native 0..255 count documented by set_back_led",
                    limit=Limit(min=0, max=255, source="upstream_code", ref=_BACK_LED_DOC_REF),
                ),
            },
            output=_PUBLISHED,
            examples=[{"brightness": 0}],
        ),
        "x-cap.athackst.disable_stabilization.v1": Action(
            name="publish_stabilization",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one std_msgs/Bool to disable_stabilization. True requests native stabilization off "
                "(0) and false requests it on (1). The receipt is a publication acknowledgement only."
            ),
            input={
                "disabled": Field(
                    "boolean",
                    description="True to disable stabilization; the node inverts it before calling set_stablization",
                ),
            },
            output=_PUBLISHED,
            examples=[{"disabled": False}],
        ),
        "x-cap.athackst.set_heading.v1": Action(
            name="publish_heading",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one std_msgs/Float32 heading in radians to set_heading; the callback normalizes it and "
                "converts to whole degrees. The receipt is a publication acknowledgement only."
            ),
            input={
                "heading_rad": Field(
                    "number", unit="rad",
                    description="Heading passed to normalize_angle_positive before conversion to degrees",
                    limit=_HEADING_LIMIT,
                ),
            },
            output=_PUBLISHED,
            examples=[{"heading_rad": 0.0}],
        ),
        "x-cap.athackst.set_angular_velocity.v1": Action(
            name="publish_angular_velocity",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one std_msgs/Float32 angular velocity in radians per second to set_angular_velocity; "
                "the callback converts it to native 0.784 degree/s counts. The receipt is a publication "
                "acknowledgement only."
            ),
            input={
                "angular_velocity_rad": Field(
                    "number", unit="rad/s",
                    description="Angular velocity passed to the callback's 0.784 degree/s conversion",
                    limit=_ROTATION_LIMIT,
                ),
            },
            output=_PUBLISHED,
            examples=[{"angular_velocity_rad": 0.0}],
        ),
        "x-cap.athackst.stop.v1": Action(
            name="publish_zero_velocity",
            verb="invoke",
            risk="R2",
            description=(
                "Publish a fixed zero geometry_msgs/Twist to cmd_vel. This is an ordinary stop command, not an "
                "acknowledged safe state, not proof that the ball stopped and not an independent hardware e-stop."
            ),
            output=_PUBLISHED,
        ),
    }
    # The node exposes no service or action that could be a native e-stop.  A
    # zero-velocity publication is explicitly not accepted as an acknowledged
    # stop binding, so this declaration leaves the safety binding empty and G3
    # refuses the R2 device instead of claiming a stop the source cannot prove.
    safety_bindings = {}
