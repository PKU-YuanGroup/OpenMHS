"""OpenMHS rosbridge driver for the Duro Inertial GPS ROS 1 node.

The upstream ``duro_ros`` package is a C++ ROS 1 node that reads Swift Binary
Protocol frames from a Duro/Piksi receiver over TCP and publishes GNSS,
inertial, magnetic, attitude, status and time observations.  This package is a
configuration-only :class:`RosDriver` over rosbridge; it declares no Python
native class and never imports the upstream code.

Scope: the nine topic publications listed in the upstream README.  Each
capability returns one complete ROS 1 message, so the native header, status,
vectors, covariance arrays and time-reference arithmetic are preserved
without a second conversion.  The node creates no ROS service server,
subscriber, action server or actuator command; no stop, reset or safe-state
endpoint is invented.  The hardware path is a rosbridge WebSocket whose
endpoint is an operator deployment setting.

Every endpoint, type and fact cites the pinned clone at
d09c1f33aa07ba89d082c3e213282e2bbdbbe725.  The fake transport is ROS-free;
no ROS graph, receiver or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver


# ---------------------------------------------------------------------------
# Endpoint evidence
# ---------------------------------------------------------------------------

#: main() creates the default NodeHandle and advertises relative publisher
#: names (src/duro.cpp:470-484).  The example launch does not set a namespace,
#: so these resolve under the root namespace unless the operator adds one.
_ODOM_REF = "src/duro.cpp:472"
_POSE_REF = "src/duro.cpp:473"
_FIX_REF = "src/duro.cpp:475"
_MAG_REF = "src/duro.cpp:476"
_IMU_REF = "src/duro.cpp:477"
_ATTITUDE_REF = "src/duro.cpp:478"
_STATUS_FLAG_REF = "src/duro.cpp:480"
_STATUS_TEXT_REF = "src/duro.cpp:481"
_TIME_REF_REF = "src/duro.cpp:482"


# ---------------------------------------------------------------------------
# ROS 1 message schemas
# ---------------------------------------------------------------------------


def _timestamp() -> Field:
    return Field(
        "object",
        description="ROS 1 time value carried as whole seconds and nanoseconds",
        properties={
            "secs": Field("integer", unit="s", description="Whole seconds"),
            "nsecs": Field("integer", unit="ns", description="Nanoseconds within the second"),
        },
    )


def _header(description: str = "ROS 1 std_msgs/Header") -> Field:
    return Field(
        "object",
        description=description,
        properties={
            "seq": Field("integer", description="Publisher sequence number filled by roscpp"),
            "stamp": _timestamp(),
            "frame_id": Field("string", description="Coordinate frame named by the upstream node"),
        },
    )


def _vector(unit: str, description: str) -> Field:
    return Field(
        "object",
        description=description,
        properties={
            "x": Field("number", unit=unit, description="X component"),
            "y": Field("number", unit=unit, description="Y component"),
            "z": Field("number", unit=unit, description="Z component"),
        },
    )


def _covariance(unit: str | None, length: int, description: str) -> Field:
    items = Field("number", unit=unit) if unit is not None else Field("number")
    return Field("array", description=description, items=items, length=length)


def _quaternion(description: str) -> Field:
    return Field(
        "object",
        description=description,
        properties={
            "x": Field("number", unit="1", description="X component"),
            "y": Field("number", unit="1", description="Y component"),
            "z": Field("number", unit="1", description="Z component"),
            "w": Field("number", unit="1", description="W component"),
        },
    )


_POSITION = _vector("m", "Position in metres as published by the node")
_IMU_ORIENTATION = _quaternion(
    "Quaternion copied from pose_msg by the IMU callback; it is not synchronized with this raw IMU sample"
)
_POSE_ORIENTATION = _quaternion(
    "Quaternion written by the orientation callbacks; orientation_source may select the odometry-derived fallback"
)
_ODOM_ORIENTATION = _quaternion(
    "Quaternion carried by nav_msgs/Odometry; pos_ll_callback does not assign it, so the published value "
    "is the publisher default"
)
_ACCELERATION = _vector("m/s2", "Linear acceleration in metres per second squared")
_ANGULAR_VELOCITY = _vector("rad/s", "Angular velocity in radians per second")
_MAGNETIC_FIELD = _vector("T", "Magnetic field in tesla after the node's 1e-6 scaling")


_NAVSAT_STATUS = Field(
    "object",
    description="sensor_msgs/NavSatStatus carried by the fix message",
    properties={
        "status": Field("integer", description="NavSatStatus code; -1 is STATUS_NO_FIX and 0 is STATUS_FIX"),
        "service": Field("integer", description="Service bitmask; the node leaves the publisher default"),
    },
)

_FIX_SAMPLE = Field(
    "object",
    description="Complete sensor_msgs/NavSatFix message published on the fix topic",
    properties={
        "header": _header("std_msgs/Header of the fix sample"),
        "status": _NAVSAT_STATUS,
        "latitude": Field("number", unit="deg", description="Latitude in degrees"),
        "longitude": Field("number", unit="deg", description="Longitude in degrees"),
        "altitude": Field("number", unit="m", description="Altitude in metres"),
        "position_covariance": _covariance(
            "m2", 9,
            "Row-major 3x3 position covariance; the node fills diagonal entries 0, 4 and 8",
        ),
        "position_covariance_type": Field(
            "integer",
            description="NavSatFix covariance type; 2 is COVARIANCE_TYPE_DIAGONAL_KNOWN",
        ),
    },
)

_IMU_SAMPLE = Field(
    "object",
    description="Complete sensor_msgs/Imu message published on the imu topic",
    properties={
        "header": _header("std_msgs/Header of the IMU sample"),
        "orientation": _IMU_ORIENTATION,
        "orientation_covariance": _covariance(
            "1", 9, "Row-major 3x3 orientation covariance; the cited callback leaves it at the default"
        ),
        "angular_velocity": _ANGULAR_VELOCITY,
        "angular_velocity_covariance": _covariance(
            "rad2/s2", 9, "Row-major 3x3 angular-velocity covariance; the cited callback leaves it at the default"
        ),
        "linear_acceleration": _ACCELERATION,
        "linear_acceleration_covariance": _covariance(
            "m2/s4", 9, "Row-major 3x3 linear-acceleration covariance; the cited callback leaves it at the default"
        ),
    },
)

_MAG_SAMPLE = Field(
    "object",
    description="Complete sensor_msgs/MagneticField message published on the mag topic",
    properties={
        "header": _header("std_msgs/Header of the magnetic-field sample"),
        "magnetic_field": _MAGNETIC_FIELD,
        "magnetic_field_covariance": _covariance(
            "T2", 9, "Row-major 3x3 magnetic-field covariance; the cited callback leaves it at the default"
        ),
    },
)

_TIME_REFERENCE_SAMPLE = Field(
    "object",
    description="Complete sensor_msgs/TimeReference message published on the time_ref topic",
    properties={
        "header": _header("std_msgs/Header; the upstream callback sets frame_id to ros_time"),
        "time_ref": _timestamp(),
        "source": Field("string", description="Source label; the upstream callback sets gps_duro"),
    },
)

_POSE_SAMPLE = Field(
    "object",
    description="Complete geometry_msgs/PoseStamped message published on the current_pose topic",
    properties={
        "header": _header("std_msgs/Header of the pose sample"),
        "pose": Field(
            "object",
            description="Pose carried by the message",
            properties={"position": _POSITION, "orientation": _POSE_ORIENTATION},
        ),
    },
)

_ODOMETRY_SAMPLE = Field(
    "object",
    description="Complete nav_msgs/Odometry message published on the odom topic",
    properties={
        "header": _header("std_msgs/Header of the odometry sample"),
        "child_frame_id": Field("string", description="Child frame named by the upstream node"),
        "pose": Field(
            "object",
            description="geometry_msgs/PoseWithCovariance: the pose and its covariance array "
                        "(the node writes odom.pose.pose.position)",
            properties={
                "pose": Field(
                    "object",
                    description="geometry_msgs/Pose carried by the odometry message",
                    properties={"position": _POSITION, "orientation": _ODOM_ORIENTATION},
                ),
                "covariance": _covariance(
                    None, 36,
                    "Row-major 6x6 pose covariance; the cited callback leaves it at the publisher default",
                ),
            },
        ),
        "twist": Field(
            "object",
            description="geometry_msgs/TwistWithCovariance; the cited callback leaves it at the publisher default",
            properties={
                "twist": Field(
                    "object",
                    description="geometry_msgs/Twist carried by the odometry message",
                    properties={
                        "linear": _vector("m/s", "Linear velocity in metres per second"),
                        "angular": _vector("rad/s", "Angular velocity in radians per second"),
                    },
                ),
                "covariance": _covariance(
                    None, 36,
                    "Row-major 6x6 twist covariance; the cited callback leaves it at the publisher default",
                ),
            },
        ),
    },
)

_STATUS_FLAG_SAMPLE = Field(
    "object",
    description="Complete std_msgs/UInt8 message published on the status_flag topic",
    properties={
        "data": Field(
            "integer",
            description="Fix mode from the low three SBP flag bits: 0 Invalid, 1 SPP, 2 DGNSS, 3 Float RTK, "
                        "4 Fixed RTK, 5 Dead Reckoning, 6 SBAS",
        ),
    },
)

_STATUS_TEXT_SAMPLE = Field(
    "object",
    description="Complete std_msgs/String message published on the status_string topic",
    properties={
        "data": Field(
            "string",
            description="Human-readable fix-mode text assigned by the upstream status switch",
        ),
    },
)

_ATTITUDE_SAMPLE = Field(
    "object",
    description="Complete geometry_msgs/Vector3 message published on the rollpitchyaw topic",
    properties={
        "x": Field("number", unit="rad", description="Roll in radians"),
        "y": Field("number", unit="rad", description="Pitch in radians"),
        "z": Field("number", unit="rad", description="Yaw in radians"),
    },
)


def _observation(topic: str, ros_type: str, source_name: str, source_ref: str) -> dict:
    """One read-only rosbridge subscription returning the complete ROS message."""
    return {
        "topic": topic,
        "type": ros_type,
        "operation": "subscribe",
        "path": "$",
        "source_name": source_name,
        "source_ref": source_ref,
        "result": {"map": {"sample": "output.$"}},
    }


class DuroGps(RosDriver):
    """Configuration-only ROS 1 driver for the Duro Inertial GPS topic surface."""

    device_id = "duro-gps"
    device_kind = "sensor"
    mode = "hardware"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeDuroGpsDriver"}
    tags = ["ros", "ros1", "gps", "gnss", "ins", "imu", "magnetometer", "navigation", "sensor"]
    display_name = "Duro Inertial GPS ROS 1 driver"
    vendor = "szenergy"
    model = "Duro Inertial / Piksi Multi Inertial"
    resource_id = "receiver"

    facts = [
        Fact(
            "README documents the topics /gps/duro/current_pose (geometry_msgs/PoseStamped), /gps/duro/fix "
            "(sensor_msgs/NavSatFix), /gps/duro/imu (sensor_msgs/Imu), /gps/duro/mag "
            "(sensor_msgs/MagneticField), /gps/duro/odom (nav_msgs/Odometry), /gps/duro/rollpitchyaw "
            "(geometry_msgs/Vector3), /gps/duro/status_flag (std_msgs/UInt8), /gps/duro/status_string "
            "(std_msgs/String) and /gps/duro/time_ref (sensor_msgs/TimeReference).",
            source="vendor_doc", ref="README.md:91-103",
        ),
        Fact(
            "main advertises the relative publisher names odom, current_pose, current_pose_fake_orientation, "
            "fix, mag, imu, rollpitchyaw, rollpitchyaw_fake, status_flag, status_string, time_ref, time_diff "
            "and time_gps_str on the default node handle.",
            source="upstream_code", ref="src/duro.cpp:467-484",
        ),
        Fact(
            "The advertise calls declare the message types nav_msgs::Odometry, geometry_msgs::PoseStamped, "
            "sensor_msgs::NavSatFix, sensor_msgs::MagneticField, sensor_msgs::Imu, geometry_msgs::Vector3, "
            "std_msgs::UInt8, std_msgs::String, sensor_msgs::TimeReference and std_msgs::Float64.",
            source="upstream_code", ref="src/duro.cpp:472-484",
        ),
        Fact(
            "ros::init initializes a ROS 1 node named duro and the publishers are created on a default "
            "ros::NodeHandle.",
            source="upstream_code", ref="src/duro.cpp:470-471",
        ),
        Fact(
            "The example launch starts package duro_ros executable duronode with node name duro_driver and sets "
            "ip_address, port, gps_receiver_frame_id, imu_frame_id, utm_frame_id, orientation_source and "
            "z_coord_ref_switch parameters.",
            source="upstream_code", ref="launch/duro_example.launch:3-23",
        ),
        Fact(
            "The comment says the first three flag bits are the fix mode (FIX_MODE_POSITION 0, FIX_MODE_MASK 7), "
            "and the fix_modes enum sets INVALID = 0 followed by SINGLE_POINT_POSITION, DIFFERENTIAL_GNSS, FLOAT_RTK, "
            "FIXED_RTK, DEAD_RECKONING and SBAS_POSITION in that order.",
            source="upstream_code", ref="src/duro.cpp:105-121",
        ),
        Fact(
            "pos_ll_callback masks fix_mode out of the position flags, sets the status text to Invalid and "
            "publishes fix_mode as std_msgs::UInt8 with status_flag_pub before the fix_mode > fix_modes::INVALID "
            "check; the comment maps 0 Invalid, 1 SPP, 2 DGNSS, 3 Float RTK, 4 Fixed RTK, 5 Dead Reckoning and "
            "6 SBAS.",
            source="upstream_code", ref="src/duro.cpp:136-154",
        ),
        Fact(
            "In pos_ll_callback the odom_pub, fake_pub, pose_pub and nav_fix_pub publications are inside the "
            "fix_mode > fix_modes::INVALID branch, and status_stri_pub publishes after that branch closes as the "
            "callback's last statement.",
            source="upstream_code", ref="src/duro.cpp:136-271",
        ),
        Fact(
            "The NavSatFix covariance conversion interprets h_accuracy and v_accuracy as millimetres, converts "
            "them to metres and squares them for entries 0, 4 and 8, and sets position_covariance_type to "
            "COVARIANCE_TYPE_DIAGONAL_KNOWN.",
            source="upstream_code", ref="src/duro.cpp:159-165",
        ),
        Fact(
            "The fix status switch maps DEAD_RECKONING and its default case (a mode it does not implement) to "
            "NavSatStatus::STATUS_NO_FIX, and nav_fix_pub.publish(fix) follows the switch.",
            source="upstream_code", ref="src/duro.cpp:253-268",
        ),
        Fact(
            "pose_msg gets the x and y that LatLonToUTMXY computes from latitude and longitude, the "
            "utm_frame_id frame and a z chosen by z_coord_ref_switch (zero, exact, zero_based or orig).",
            source="upstream_code", ref="src/duro.cpp:167-209",
        ),
        Fact(
            "When euler_based_orientation is false, orientation_callback scales the SBP quaternion by 2^-31, "
            "rotates it by -pi/2 about z and writes swapped and negated components into "
            "pose_msg.pose.orientation; the comments call this a left-handed/right-handed conversion.",
            source="upstream_code", ref="src/duro.cpp:273-294",
        ),
        Fact(
            "orientation_euler_callback publishes the roll, pitch and yaw vector with euler_pub and, when "
            "euler_based_orientation is true, writes the quaternion of roll, pitch and pi/2 minus yaw into "
            "pose_msg.pose.orientation.",
            source="upstream_code", ref="src/duro.cpp:326-347",
        ),
        Fact(
            "fake_pose_msg copies the header and position of pose_msg with a yaw-only orientation from "
            "fake_ori.getOri() + pi and is published by fake_pub; pose_pub publishes pose_msg when "
            "orientation_source is gps, fake_pose_msg when it is odom, and nothing for any other value.",
            source="upstream_code", ref="src/duro.cpp:210-227",
        ),
        Fact(
            "pos_ll_callback assigns the odom header stamp and utm_frame_id frame, child_frame_id "
            "gps_receiver_frame_id and pose.pose.position (UTM x and y, height as z) before odom_pub publishes "
            "it; it assigns no odometry orientation, twist or covariance.",
            source="upstream_code", ref="src/duro.cpp:136-271",
        ),
        Fact(
            "The IMU callback converts raw acceleration to m/s2 by dividing by linear_acc_conf and multiplying "
            "by 9.80665, and raw gyro to rad/s by dividing by angular_vel_conf and multiplying by 0.01745.",
            source="upstream_code", ref="src/duro.cpp:349-365",
        ),
        Fact(
            "imu_callback builds and publishes an IMU message only when linear_acc_conf > 0, and copies that "
            "message's orientation from pose_msg.pose.orientation.",
            source="upstream_code", ref="src/duro.cpp:351-373",
        ),
        Fact(
            "linear_acc_conf and angular_vel_conf start at -1.0.",
            source="upstream_code", ref="src/duro.cpp:74-75",
        ),
        Fact(
            "imu_aux_callback sets linear_acc_conf to 16384, 8192, 4096 or 2048 and angular_vel_conf to 16.4, "
            "32.8, 65.6, 131.2 or 262.4 according to the accelerometer and gyro mode bits of imu_conf.",
            source="upstream_code", ref="src/duro.cpp:403-441",
        ),
        Fact(
            "mag_callback multiplies each raw magnetic component by 1e-6 and the comment labels the body-frame "
            "value in microteslas.",
            source="upstream_code", ref="src/duro.cpp:449-459",
        ),
        Fact(
            "orientation_euler_callback divides raw roll, pitch and yaw by 57292374; the comment states the "
            "constant converts raw values from microdegrees to radians.",
            source="upstream_code", ref="src/duro.cpp:326-334",
        ),
        Fact(
            "time_callback sets the TimeReference header frame to ros_time, computes time_ref.sec from the GPS "
            "week and time-of-week plus 315964782 and time_ref.nsec from the millisecond remainder and "
            "ns_residual, and labels the source gps_duro.",
            source="upstream_code", ref="src/duro.cpp:296-311",
        ),
        Fact(
            "The status_string switch assigns Invalid, Single Point Position (SPP), Differential GNSS (DGNSS), "
            "Float RTK, Fixed RTK, Dead Reckoning (DR), SBAS Position or Not implemented.",
            source="upstream_code", ref="src/duro.cpp:230-265",
        ),
        Fact(
            "main advertises topic publishers and then registers SBP callbacks and enters the socket loop; it "
            "creates no ROS service server or subscriber for commands.",
            source="upstream_code", ref="src/duro.cpp:467-516",
        ),
        Fact(
            "setup_socket creates an AF_INET TCP socket and connects to tcp_ip_addr:tcp_ip_port.",
            source="upstream_code", ref="src/duro.cpp:78-96",
        ),
        Fact(
            "The repository's debug script subscribes to /gps/duro/time_ref.",
            source="upstream_code", ref="src/debug_time_drift.py:18",
        ),
    ]

    #: The node publishes observations and has no service, action or actuator
    #: command.  Nothing is declared writable and no stop binding is invented.
    commands = {
        "x-cap.szenergy.fix.v1": _observation("/fix", "sensor_msgs/NavSatFix", "fix", _FIX_REF),
        "x-cap.szenergy.imu.v1": _observation("/imu", "sensor_msgs/Imu", "imu", _IMU_REF),
        "x-cap.szenergy.mag.v1": _observation("/mag", "sensor_msgs/MagneticField", "mag", _MAG_REF),
        "x-cap.szenergy.time_reference.v1": _observation(
            "/time_ref", "sensor_msgs/TimeReference", "time_ref", _TIME_REF_REF
        ),
        "x-cap.szenergy.fix_status.v1": _observation(
            "/status_flag", "std_msgs/UInt8", "status_flag", _STATUS_FLAG_REF
        ),
        "x-cap.szenergy.fix_status_text.v1": _observation(
            "/status_string", "std_msgs/String", "status_string", _STATUS_TEXT_REF
        ),
        "x-cap.szenergy.pose.v1": _observation(
            "/current_pose", "geometry_msgs/PoseStamped", "current_pose", _POSE_REF
        ),
        "x-cap.szenergy.odometry.v1": _observation("/odom", "nav_msgs/Odometry", "odom", _ODOM_REF),
        "x-cap.szenergy.attitude.v1": _observation(
            "/rollpitchyaw", "geometry_msgs/Vector3", "rollpitchyaw", _ATTITUDE_REF
        ),
    }

    actions = {
        "x-cap.szenergy.fix.v1": Action(
            name="read_fix",
            verb="read",
            description="Read one complete sensor_msgs/NavSatFix publication, including its covariance and status; "
                        "completion means a message arrived, not that the fix is valid or the source is recent",
            output={"sample": _FIX_SAMPLE},
        ),
        "x-cap.szenergy.imu.v1": Action(
            name="read_imu",
            verb="read",
            description="Read one complete sensor_msgs/Imu publication, including three-axis acceleration, "
                        "angular velocity and the node's orientation copied from pose_msg; the copied orientation "
                        "is not synchronized with the raw IMU sample",
            output={"sample": _IMU_SAMPLE},
        ),
        "x-cap.szenergy.mag.v1": Action(
            name="read_mag",
            verb="read",
            description="Read one complete sensor_msgs/MagneticField publication, including its covariance array",
            output={"sample": _MAG_SAMPLE},
        ),
        "x-cap.szenergy.time_reference.v1": Action(
            name="read_time_reference",
            verb="read",
            description="Read one complete sensor_msgs/TimeReference publication with the source GPS time; "
                        "completion does not establish absolute accuracy or a fresh source clock",
            output={"sample": _TIME_REFERENCE_SAMPLE},
        ),
        "x-cap.szenergy.fix_status.v1": Action(
            name="read_fix_status",
            verb="read",
            description="Read the numeric fix-mode status published on status_flag",
            output={"sample": _STATUS_FLAG_SAMPLE},
        ),
        "x-cap.szenergy.fix_status_text.v1": Action(
            name="read_fix_status_text",
            verb="read",
            description="Read the human-readable fix status published on status_string",
            output={"sample": _STATUS_TEXT_SAMPLE},
        ),
        "x-cap.szenergy.pose.v1": Action(
            name="read_pose",
            verb="read",
            description="Read one complete geometry_msgs/PoseStamped publication in the UTM frame; "
                        "orientation_source may select the odometry-derived fallback",
            output={"sample": _POSE_SAMPLE},
        ),
        "x-cap.szenergy.odometry.v1": Action(
            name="read_odometry",
            verb="read",
            description="Read one complete nav_msgs/Odometry publication, including the child frame and the pose; "
                        "the pose orientation is not assigned by pos_ll_callback and keeps the publisher "
                        "default",
            output={"sample": _ODOMETRY_SAMPLE},
        ),
        "x-cap.szenergy.attitude.v1": Action(
            name="read_attitude",
            verb="read",
            description="Read one complete geometry_msgs/Vector3 Euler-angle publication",
            output={"sample": _ATTITUDE_SAMPLE},
        ),
    }
