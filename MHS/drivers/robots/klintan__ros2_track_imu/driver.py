"""OpenMHS rosbridge driver for the TrackIMU ROS 2 node (gh.klintan/ros2_track_imu).

The upstream ``ros2_track_imu`` package is an ``ament_python`` ROS 2 node.  Its
``imu_node`` reads a serial line from the TrackIMU board and publishes a
``sensor_msgs/msg/Imu`` message on the relative ``imu`` topic, plus a
``diagnostic_msgs/msg/DiagnosticArray`` on ``diagnostics``.  This package is a
configuration-only :class:`RosDriver` over rosbridge; it declares no Python
native class and it imports, launches or executes nothing from the clone.

The primary interface is the IMU publication.  The binding subscribes to one
fresh message on the resolved root-namespace endpoint ``/imu``; a deployment
that starts the node inside another namespace must expose the corresponding
resolved endpoint.  ``source_name`` keeps the pinned relative literal.

The upstream fills the orientation quaternion and the message covariances but
leaves ``linear_acceleration`` and ``angular_velocity`` at their default zero
vectors: those assignment lines are commented out.  The driver preserves that
wire content and says so instead of claiming a measured accelerometer or gyro.
The node copies ``euler2quat``'s ``q[0..3]`` into orientation x, y, z, w in that
order; transforms3d, outside the clone, documents its quaternions as w first, so
the published component order must be checked on the device (model review
2026-11-04).  The orientation is passed through unchanged.
The class's ``frame`` input selects the body-frame vectors unchanged or the
world-frame vectors rotated by the reported orientation quaternion; the
``sampled_at`` output is the message header stamp in RFC 3339 form.

Every endpoint, type and fact cites the pinned clone at
21741c413ceec1104c62276a6d00deddb95fec4c.  The fake transport is ROS-free; no
ROS graph, serial device or hardware is contacted.
"""

import math
from datetime import datetime, timezone

from mhs.driver import Action, DriverFailed, Fact, Field, RosDriver

#: The node imports sensor_msgs.msg.Imu on this line.
_IMU_TYPE_REF = "ros2_track_imu/driver.py:3"

#: The constructor creates the relative-name Imu publisher with queue size 10.
_IMU_SOURCE_REF = "ros2_track_imu/driver.py:20"

#: The catalogue class this package serves.
_IMU_CAP = "cap.sensing.imu.v1"

_VECTOR_COMPONENTS = ("x", "y", "z")
_QUATERNION_COMPONENTS = ("x", "y", "z", "w")


def _finite_number(value, label):
    """Return ``value`` as a finite float or refuse the mapped output."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", f"IMU {label} is not a number")
    number = float(value)
    if not math.isfinite(number):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", f"IMU {label} is not finite")
    return number


def _vector(raw, label):
    """Convert a sensor_msgs/Vector3 mapping to the class's three-number array."""
    if not isinstance(raw, dict):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", f"IMU {label} is absent")
    return [_finite_number(raw.get(axis), f"{label}.{axis}") for axis in _VECTOR_COMPONENTS]


def _quaternion(raw):
    """Validate and return the orientation components in x, y, z, w order."""
    if not isinstance(raw, dict):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "IMU orientation is absent")
    values = [_finite_number(raw.get(name), f"orientation.{name}") for name in _QUATERNION_COMPONENTS]
    if math.sqrt(sum(value * value for value in values)) == 0.0:
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "IMU orientation is the zero quaternion")
    return values


def _stamp(raw):
    """Render a ROS 1 or ROS 2 header stamp as the class's RFC 3339 string."""
    if not isinstance(raw, dict):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "IMU header stamp is absent")
    if "sec" in raw or "nanosec" in raw:
        seconds = raw.get("sec")
        nanoseconds = raw.get("nanosec")
    elif "secs" in raw or "nsecs" in raw:
        seconds = raw.get("secs")
        nanoseconds = raw.get("nsecs")
    else:
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "IMU header stamp has no seconds")
    if isinstance(seconds, bool) or not isinstance(seconds, int):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "IMU header stamp seconds are not an integer")
    if nanoseconds is None:
        nanoseconds = 0
    if (isinstance(nanoseconds, bool) or not isinstance(nanoseconds, int)
            or not 0 <= nanoseconds < 1_000_000_000):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "IMU header stamp nanoseconds are out of range")
    try:
        base = datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    except (OSError, OverflowError, ValueError) as exc:
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "IMU header stamp is not a representable time") from exc
    return f"{base}.{nanoseconds:09d}Z"


def _rotate(quaternion, vector):
    """Rotate a body-frame vector into the world frame with the reported orientation."""
    x, y, z, w = quaternion
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    vx, vy, vz = vector
    # t = 2 * (q_vec x v); v' = v + w * t + q_vec x t
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return [
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    ]


class TrackImu(RosDriver):
    """Configuration-only ROS 2 rosbridge driver for the TrackIMU node."""

    device_id = "track_imu"
    device_kind = "sensor.imu"
    mode = "hardware"
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeRos2TrackImu"}
    tags = ["ros", "ros2", "imu", "sensor", "trackimu", "serial"]
    display_name = "TrackIMU ROS 2 IMU"
    vendor = "klintan"
    model = "TrackIMU"
    safe_state = (
        "The node is a passive IMU publisher: it exposes no actuation, stop or reset service, and this "
        "package binds only its observation topic, so it commands no safe state."
    )

    facts = [
        Fact("Ros2TrackIMUDriver is an rclpy Node constructed with the name 'track_imu_driver'.",
             source="upstream_code", ref="ros2_track_imu/driver.py:15-17"),
        Fact("The node imports the ROS 2 sensor_msgs.msg.Imu message.",
             source="upstream_code", ref=_IMU_TYPE_REF),
        Fact("The constructor creates a publisher for Imu on the relative topic name 'imu' with queue size 10.",
             source="upstream_code", ref=_IMU_SOURCE_REF),
        Fact("The constructor also creates a DiagnosticArray publisher on the relative topic name "
             "'diagnostics' with queue size 10.",
             source="upstream_code", ref="ros2_track_imu/driver.py:22"),
        Fact("The node declares a frame_id parameter whose default is the string 'base_imu_link'.",
             source="upstream_code", ref="ros2_track_imu/driver.py:28"),
        Fact("The constructor fills the orientation, angular-velocity and linear-acceleration covariance "
             "diagonals with 0.0025, 0.02 and 0.04 based on the comments' noise estimates.",
             source="upstream_code", ref="ros2_track_imu/driver.py:30-64"),
        Fact("publish_imu_data decodes a UTF-8 line, strips the 'ypr,' prefix and tab characters, and splits "
             "the remaining text on commas.",
             source="upstream_code", ref="ros2_track_imu/driver.py:159-162"),
        Fact("For a line with more than two comma-separated fields, the node negates yaw, adds "
             "imu_yaw_calibration, wraps yaw to [-180, 180], negates pitch, and converts yaw, pitch and roll "
             "from degrees to radians.",
             source="upstream_code", ref="ros2_track_imu/driver.py:163-174"),
        Fact("publish_imu_data assigns the local yaw, pitch and roll only when the line has more than two "
             "comma-separated fields, and calls quaternion_from_euler with them after that branch.",
             source="upstream_code", ref="ros2_track_imu/driver.py:163-189"),
        Fact("The node imports transforms3d.euler.euler2quat under the name quaternion_from_euler.",
             source="upstream_code", ref="ros2_track_imu/driver.py:9"),
        Fact("The node converts roll, pitch and yaw with quaternion_from_euler and assigns q[0], q[1], q[2] and "
             "q[3] to orientation x, y, z and w.",
             source="upstream_code", ref="ros2_track_imu/driver.py:189-193"),
        Fact("The node stamps the Imu header from its clock, sets the configured frame_id, increments a "
             "sequence counter and publishes the message on 'imu'.",
             source="upstream_code", ref="ros2_track_imu/driver.py:196-199"),
        Fact("The linear_acceleration and angular_velocity assignment lines in publish_imu_data are commented "
             "out.",
             source="upstream_code", ref="ros2_track_imu/driver.py:179-187"),
        Fact("The node publishes a DiagnosticArray named 'Track_IMU' at level OK with message "
             "'Received AHRS measurement', roll/yaw/pitch in degrees and the sequence number.",
             source="upstream_code", ref="ros2_track_imu/driver.py:201-233"),
        Fact("imu_node.main declares the port parameter with default '/dev/tty.usbmodemHIDFH1' and the baud "
             "parameter with default 115200, then opens serial.Serial with a one-second timeout.",
             source="upstream_code", ref="ros2_track_imu/nodes/imu_node.py:43-47"),
        Fact("The main loop flushes the first 200 serial lines, reads one line per iteration and calls "
             "publish_imu_data until rclpy is no longer OK.",
             source="upstream_code", ref="ros2_track_imu/nodes/imu_node.py:65-73"),
        Fact("The calls to configure_imu and to start the datastream with '#o1' are commented out in main.",
             source="upstream_code", ref="ros2_track_imu/nodes/imu_node.py:56-60"),
        Fact("The README documents 'ros2 run ros2_track_imu imu_node' as the usage command.",
             source="vendor_doc", ref="README.md:13"),
        Fact("The README's launch section says ROS 2 launch is not implemented yet.",
             source="vendor_doc", ref="README.md:30"),
        Fact("The publisher launch file track-imu-pub.py is a commented-out ROS 1 launch snippet.",
             source="upstream_code", ref="launch/track-imu-pub.py:1-6"),
        Fact("package.xml declares an ament_python package with exec dependencies rclpy, python-serial, "
             "sensor_msgs and diagnostics_msgs.",
             source="upstream_code", ref="package.xml:19-27"),
        Fact("setup.py registers the console script ros2_track_imu = ros2_track_imu.nodes.imu_node:main.",
             source="upstream_code", ref="setup.py:20-22"),
        Fact("The accelerometer, magnetometer, gyroscope and yaw-calibration values are declared ROS "
             "parameters with constructor defaults.",
             source="upstream_code", ref="ros2_track_imu/driver.py:75-100"),
    ]

    commands = {
        _IMU_CAP: {
            "topic": "/imu",
            "type": "sensor_msgs/msg/Imu",
            "source_name": "imu",
            "source_ref": _IMU_SOURCE_REF,
            "type_ref": _IMU_TYPE_REF,
            "operation": "subscribe",
            "path": "$",
            "result": {"map": {
                "orientation": "orientation",
                "linear_acceleration": "linear_acceleration",
                "angular_velocity": "angular_velocity",
                "sampled_at": "header.stamp",
            }},
        },
    }
    actions = {
        _IMU_CAP: Action(
            name="read_imu",
            max_duration_ms=2000,
            input={
                "frame": Field(
                    "string",
                    description=(
                        "Reference frame for the returned vectors: 'body' preserves the sensor_msgs/Imu "
                        "vectors, while 'world' rotates them by the reported orientation quaternion. The "
                        "pinned publisher fills only orientation, so both vectors are zero there."
                    ),
                ),
            },
            description=(
                "Subscribe to one fresh sensor_msgs/Imu sample on the upstream 'imu' topic and return the "
                "orientation quaternion plus the linear-acceleration and angular-velocity vectors in the "
                "requested frame. The upstream leaves the two vectors at their default zeros; only the "
                "orientation is computed from the serial AHRS line, and the node copies euler2quat's q[0..3] "
                "into x, y, z, w unchanged, so verify the component order on the device."
            ),
        ),
    }

    def call(self, capability_id, args=None, ctx=None):
        """Map the ROS message objects onto the class's array output contract."""
        result = super().call(capability_id, args, ctx)
        if capability_id != _IMU_CAP:
            return result
        frame = dict(args or {}).get("frame")
        if frame not in ("body", "world"):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "the IMU frame must be 'body' or 'world'")
        orientation = _quaternion(result.get("orientation"))
        linear = _vector(result.get("linear_acceleration"), "linear_acceleration")
        angular = _vector(result.get("angular_velocity"), "angular_velocity")
        if frame == "world":
            linear = _rotate(orientation, linear)
            angular = _rotate(orientation, angular)
        return {
            "orientation": dict(zip(_QUATERNION_COMPONENTS, orientation)),
            "linear_acceleration": linear,
            "angular_velocity": angular,
            "sampled_at": _stamp(result.get("sampled_at")),
        }
