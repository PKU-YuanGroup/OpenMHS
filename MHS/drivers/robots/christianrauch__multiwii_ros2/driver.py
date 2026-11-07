"""OpenMHS rosbridge driver for the MultiWii ROS 2 bridge (gh.christianrauch/multiwii_ros2).

The upstream ``multiwii2_node`` is a C++ ROS 2 node.  This package is a
configuration-only :class:`RosDriver` over rosbridge and declares no Python
native class.  It exposes the node's actual wire surface: the two
``mavros_msgs/msg/OverrideRCIn`` command subscriptions (``rc/override`` and
``rc/override/raw``), the flight state, RC input and motor output
observations, the attitude quaternion, the relative altitude and the raw IMU
linear acceleration and angular velocity.

Every topic is configured by its absolute resolved name while the upstream
relative literal is kept in ``source_name``.  A deployment that namespaces
the node must expose the configured endpoints.

The node has no arm, disarm, stop or reset service.  Publication on the RC
override topics is transmission only: it neither acknowledges execution nor
proves that the flight controller stopped.  No ``Limit`` below is a device
bound copied from the code; the RC channel values are left to the operator
because the clone states no valid range.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned endpoint declarations
# ---------------------------------------------------------------------------

#: onImu / onAttitude / onRc / onMotor / onAnalog / onAltitude / onState
#: advertise these relative names in the constructor (MultiWiiNode.cpp:29-36).
_STATE = {
    "topic": "/state",
    "type": "mavros_msgs/msg/State",
    "source_name": "state",
    "source_ref": "multiwii2_node/src/MultiWiiNode.cpp:36",
}
_RC_IN = {
    "topic": "/rc/in",
    "type": "mavros_msgs/msg/RCIn",
    "source_name": "rc/in",
    "source_ref": "multiwii2_node/src/MultiWiiNode.cpp:32",
}
_MOTORS = {
    "topic": "/motors",
    "type": "mavros_msgs/msg/RCOut",
    "source_name": "motors",
    "source_ref": "multiwii2_node/src/MultiWiiNode.cpp:33",
}
_LOCAL_POSE = {
    "topic": "/local_position/pose",
    "type": "geometry_msgs/msg/PoseStamped",
    "source_name": "local_position/pose",
    "source_ref": "multiwii2_node/src/MultiWiiNode.cpp:31",
}
_ALTITUDE = {
    "topic": "/global_position/rel_alt",
    "type": "std_msgs/msg/Float64",
    "source_name": "global_position/rel_alt",
    "source_ref": "multiwii2_node/src/MultiWiiNode.cpp:35",
}
_IMU = {
    "topic": "/imu/data_raw",
    "type": "sensor_msgs/msg/Imu",
    "source_name": "imu/data_raw",
    "source_ref": "multiwii2_node/src/MultiWiiNode.cpp:29",
}
_RC_OVERRIDE = {
    "topic": "/rc/override",
    "type": "mavros_msgs/msg/OverrideRCIn",
    "source_name": "rc/override",
    "source_ref": "multiwii2_node/src/MultiWiiNode.cpp:40-42",
}
_RC_OVERRIDE_RAW = {
    "topic": "/rc/override/raw",
    "type": "mavros_msgs/msg/OverrideRCIn",
    "source_name": "rc/override/raw",
    "source_ref": "multiwii2_node/src/MultiWiiNode.cpp:43-45",
}

#: The callback reads channels[0]..channels[7] and forwards them to setRc in
#: AERT (Aileron, Elevator, Rudder, Throttle) or RPYT order (lines 227-233).
_AERT_REASON = (
    "the clone forwards channels 0..7 unchanged to fcu->setRc in AERT/RPYT order and states no valid "
    "RC pulse or normalized range; the site must supply the eight channel bounds"
)
_RAW_REASON = (
    "the clone forwards the received vector unchanged to fcu->setRc(vector<uint16_t>) and states no "
    "valid channel count or value range; the site must supply the channel bounds"
)

_CHANNEL = Field(
    "integer",
    unit="1",
    description="One raw RC channel value as published upstream; the clone declares no physical unit",
)

_AERT_CHANNELS = Field(
    "array",
    description=(
        "Eight channel values in the order documented by rc_override_AERT1234: Aileron, Elevator, "
        "Rudder, Throttle, then channels 4-7 (AERT1234); the callback indexes 0..7 without a length check"
    ),
    items=_CHANNEL,
    length=8,
    limit=Limit.operator_required(_AERT_REASON),
)
_RAW_CHANNELS = Field(
    "array",
    description=(
        "Raw channel vector forwarded unchanged to setRc(vector<uint16_t>); the clone declares no "
        "length or value range"
    ),
    items=_CHANNEL,
    limit=Limit.operator_required(_RAW_REASON),
)

_ORIENTATION = Field(
    "object",
    description="Attitude quaternion derived from the Euler roll, pitch and yaw published on local_position/pose",
    properties={
        "x": Field("number", unit="1", description="Quaternion x component"),
        "y": Field("number", unit="1", description="Quaternion y component"),
        "z": Field("number", unit="1", description="Quaternion z component"),
        "w": Field("number", unit="1", description="Quaternion w component"),
    },
)
_ACCELERATION = Field(
    "object",
    description="Linear acceleration from imu/data_raw, converted through msp::msg::ImuSI with 9.80665",
    properties={
        "x": Field("number", unit="m/s2", description="Body x acceleration"),
        "y": Field("number", unit="m/s2", description="Body y acceleration"),
        "z": Field("number", unit="m/s2", description="Body z acceleration"),
    },
)
_ANGULAR_VELOCITY = Field(
    "object",
    description="Angular velocity from imu/data_raw; the node converts the gyro value from degrees to radians",
    properties={
        "x": Field("number", unit="rad/s", description="Body x angular velocity"),
        "y": Field("number", unit="rad/s", description="Body y angular velocity"),
        "z": Field("number", unit="rad/s", description="Body z angular velocity"),
    },
)
_RC_CHANNELS = Field(
    "array",
    description="Raw channel values published on rc/in; the node copies the flight controller vector unchanged",
    items=_CHANNEL,
)
_MOTOR_CHANNELS = Field(
    "array",
    description="Raw motor outputs published on motors; the node copies the flight controller vector unchanged",
    items=_CHANNEL,
)
_ARMED = Field("boolean", description="Flight-controller armed flag published by onState from fcu->isArmed()")
_ALTITUDE_M = Field("number", unit="m", description="Relative altitude published on global_position/rel_alt")
_PUBLISHED = Field(
    "boolean",
    description="True when rosbridge transmitted the message; a publication is not an acknowledgement",
)
_CONFIRMED = Field(
    "boolean",
    description=(
        "Always false: a ROS publication carries no acknowledgement of execution, target attainment "
        "or stopping"
    ),
)


class MultiwiiRos2(RosDriver):
    """Configuration-only ROS 2 rosbridge driver for the MultiWii node."""

    device_id = "multiwii"
    device_kind = "robot.mobile_base"
    mode = "hardware"
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeMultiwiiRos2"}
    tags = ["ros", "ros2", "multiwii", "flight", "msp", "rc", "telemetry"]
    display_name = "MultiWii flight-controller bridge"
    vendor = "Christian Rauch"
    model = "MultiWii"

    facts = [
        Fact("MultiWiiNode is an rclcpp::Node constructed with the node name \"multiwii\".",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:12"),
        Fact("main initializes rclcpp, spins one MultiWiiNode and shuts rclcpp down.",
             source="upstream_code", ref="multiwii2_node/src/multiwii_node.cpp:3-7"),
        Fact("The constructor declares device_path (default /dev/ttyUSB0) and baud (default 115200), "
             "constructs fcu::FlightController and calls connect(device_path, baud).",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:14-27"),
        Fact("The constructor advertises eight relative-name SensorDataQoS publishers: imu/data_raw "
             "(sensor_msgs::msg::Imu), imu/mag (MagneticField), local_position/pose (PoseStamped), "
             "rc/in (mavros_msgs::msg::RCIn), motors (mavros_msgs::msg::RCOut), battery "
             "(BatteryState), global_position/rel_alt (std_msgs::msg::Float64) and state "
             "(mavros_msgs::msg::State).",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:29-36"),
        Fact("The constructor subscribes to the relative topics rc/override and rc/override/raw with "
             "mavros_msgs::msg::OverrideRCIn and SystemDefaultsQoS.",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:40-45"),
        Fact("The constructor block that registers the RC override subscriptions contains no service "
             "server registration.",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:38-47"),
        Fact("rc_override_AERT1234 forwards channels 0 through 7 to fcu->setRc in AERT (Aileron, "
             "Elevator, Rudder, Throttle) or RPYT (Roll, Pitch, Yaw, Throttle) order.",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:227-233"),
        Fact("rc_override_raw copies every received channel into std::vector<uint16_t> and calls "
             "fcu->setRc(channels).",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:235-239"),
        Fact("The constructor creates a 100 ms wall timer that calls onState.",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:47"),
        Fact("onState publishes state.armed from fcu->isArmed() on the state topic; the other State "
             "fields are left at their defaults.",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:221-225"),
        Fact("onRc publishes the received rc.channels on rc/in.",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:163-170"),
        Fact("onMotor copies every motor.motor value into the motors RCOut channels.",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:172-180"),
        Fact("onAttitude converts roll, pitch and yaw from degrees to radians, builds a quaternion "
             "from them, publishes the orientation in local_position/pose and broadcasts a TF child "
             "frame attitude.",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:137-160"),
        Fact("onAltitude publishes altitude.altitude on global_position/rel_alt; the code comments "
             "that the value is in meters.",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:192-204"),
        Fact("onImu constructs ImuSI(imu, 512.0, 1/4.096, 0.092, 9.80665), publishes imu_si.acc as "
             "linear_acceleration and deg2rad(imu_si.gyro) as angular_velocity in imu/data_raw, and "
             "publishes imu_si.mag * 1e-6 in imu/mag.",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:110-134"),
        Fact("onAnalog copies analog.vbat and analog.amperage into battery.voltage and "
             "battery.current.",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:182-190"),
        Fact("The only flight-controller writes in this range are the two RC override callbacks' "
             "fcu->setRc calls; onState only reads fcu->isArmed().",
             source="upstream_code", ref="multiwii2_node/src/MultiWiiNode.cpp:221-239"),
        Fact("The multiwii_msgs package generates SendMSPRawMessage and ReceiveMSPRawMessage service "
             "definitions.",
             source="upstream_code", ref="multiwii_msgs/CMakeLists.txt:21-26"),
    ]

    # The node's command surface is publish-only.  No source-backed arm,
    # disarm, stop or reset endpoint exists, so no independent stop is
    # declared.  The sentence records the absence instead of claiming safety.
    safe_state = (
        "No acknowledged safe state is available: the node creates no arm, disarm or stop service and "
        "its only command inputs are the publish-only rc/override topics; a software latch cannot "
        "confirm that the flight controller stopped."
    )
    # No safety_bindings: an unacknowledged publication is not a stop binding.

    parameters = {
        "armed": _ARMED,
        "rc_channels": _RC_CHANNELS,
        "motor_channels": _MOTOR_CHANNELS,
        "orientation": _ORIENTATION,
        "altitude_m": _ALTITUDE_M,
        "linear_acceleration": _ACCELERATION,
        "angular_velocity": _ANGULAR_VELOCITY,
    }
    reads = {
        "armed": dict(_STATE, path="armed"),
        "rc_channels": dict(_RC_IN, path="channels"),
        "motor_channels": dict(_MOTORS, path="channels"),
        "orientation": dict(_LOCAL_POSE, path="pose.orientation"),
        "altitude_m": dict(_ALTITUDE, path="data"),
        "linear_acceleration": dict(_IMU, path="linear_acceleration"),
        "angular_velocity": dict(_IMU, path="angular_velocity"),
    }
    commands = {
        "x-cap.christianrauch.flight_state.v1": dict(
            _STATE, operation="subscribe", path="$",
            result={"map": {"armed": "armed"}},
        ),
        "x-cap.christianrauch.rc_input.v1": dict(
            _RC_IN, operation="subscribe", path="$",
            result={"map": {"channels": "channels"}},
        ),
        "x-cap.christianrauch.motor_outputs.v1": dict(
            _MOTORS, operation="subscribe", path="$",
            result={"map": {"channels": "channels"}},
        ),
        "x-cap.christianrauch.attitude.v1": dict(
            _LOCAL_POSE, operation="subscribe", path="$",
            result={"map": {"orientation": "pose.orientation"}},
        ),
        "x-cap.christianrauch.altitude.v1": dict(
            _ALTITUDE, operation="subscribe", path="$",
            result={"map": {"altitude_m": "data"}},
        ),
        "x-cap.christianrauch.imu.v1": dict(
            _IMU, operation="subscribe", path="$",
            result={"map": {"linear_acceleration": "linear_acceleration",
                            "angular_velocity": "angular_velocity"}},
        ),
        # The primary control: one publication of the eight AERT1234 channels.
        "x-cap.christianrauch.rc_override.v1": {
            **_RC_OVERRIDE,
            "operation": "publish",
            "message": {
                "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": ""},
                "channels": [],
            },
            "args": {"channels": {"from": "input.channels"}},
            "result": {"map": {"published": "published", "confirmed": "confirmed"}},
        },
        # The alternate raw vector path; its length is a deployment property,
        # not a bound stated in the clone.
        "x-cap.christianrauch.rc_override_raw.v1": {
            **_RC_OVERRIDE_RAW,
            "operation": "publish",
            "message": {
                "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": ""},
                "channels": [],
            },
            "args": {"channels": {"from": "input.channels"}},
            "result": {"map": {"published": "published", "confirmed": "confirmed"}},
        },
    }
    actions = {
        "x-cap.christianrauch.flight_state.v1": Action(
            name="read_flight_state", verb="read",
            description="Read the armed flag from the state topic published every 100 ms",
            output={"armed": _ARMED},
        ),
        "x-cap.christianrauch.rc_input.v1": Action(
            name="read_rc_input", verb="read",
            description="Read the RC channel vector from rc/in",
            output={"channels": _RC_CHANNELS},
        ),
        "x-cap.christianrauch.motor_outputs.v1": Action(
            name="read_motor_outputs", verb="read",
            description="Read the motor output vector from motors",
            output={"channels": _MOTOR_CHANNELS},
        ),
        "x-cap.christianrauch.attitude.v1": Action(
            name="read_attitude", verb="read",
            description="Read the attitude quaternion from local_position/pose",
            output={"orientation": _ORIENTATION},
        ),
        "x-cap.christianrauch.altitude.v1": Action(
            name="read_altitude", verb="read",
            description="Read the relative altitude in meters from global_position/rel_alt",
            output={"altitude_m": _ALTITUDE_M},
        ),
        "x-cap.christianrauch.imu.v1": Action(
            name="read_imu", verb="read",
            description="Read linear acceleration and angular velocity from imu/data_raw",
            output={"linear_acceleration": _ACCELERATION, "angular_velocity": _ANGULAR_VELOCITY},
        ),
        "x-cap.christianrauch.rc_override.v1": Action(
            name="publish_rc_override",
            description=(
                "Publish one eight-channel OverrideRCIn message on rc/override; the receipt is "
                "transmission only and does not prove execution or stopping"
            ),
            input={"channels": _AERT_CHANNELS},
            output={"published": _PUBLISHED, "confirmed": _CONFIRMED},
        ),
        "x-cap.christianrauch.rc_override_raw.v1": Action(
            name="publish_rc_override_raw",
            description=(
                "Publish one variable-length OverrideRCIn message on rc/override/raw; the receipt is "
                "transmission only and does not prove execution or stopping"
            ),
            input={"channels": _RAW_CHANNELS},
            output={"published": _PUBLISHED, "confirmed": _CONFIRMED},
        ),
    }
    # The node exposes no service or action that stops the flight controller.
    safety_bindings = {}
