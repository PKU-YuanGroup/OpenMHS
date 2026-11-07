"""OpenMHS rosbridge driver for the LunarSim lunar-rover simulator (gh.putvision/lunarsim).

The pinned upstream repository ships a closed-source Linux simulator binary
(``LunarSim.x86_64``) inside a ROS 2 Humble container.  It contains no Python
or C++ device class, no ROS 1 node and no source for the simulator itself.
The clone documents only the ROS 2 wire graph: a velocity command topic and
several published sensor topics.  This package is a configuration-only
:class:`RosDriver` over rosbridge; it declares no Python native class and it
imports, launches or executes nothing from the clone.

The primary control is one ``geometry_msgs/msg/Twist`` publication on
``/cmd_vel``.  The pinned README documents no stop, pause or reset service or
action.  A zero-velocity Twist is a client publication, not an acknowledged
stop, and the SDK does not claim that the simulated rover stopped.  The
package therefore declares no safe-state binding and ``RESULT.json`` records
the missing stop path instead of inventing one.

Every endpoint, type and fact cites the pinned clone at
0f3b202624d398ecacbb1e4bab9aec02e394a2d2.  The fake transport is ROS-free;
no ROS graph, simulator process or hardware is contacted.
"""

import math
from datetime import datetime, timezone

from mhs.driver import Action, DriverFailed, Fact, Field, Limit, RosDriver

#: The container installs ROS 2 Humble, which fixes the wire syntax as ROS 2.
_ROS2_REF = "Dockerfile:41-45"

#: The simulator binary is downloaded from the release archive, not in the clone.
_BINARY_REF = "Dockerfile:55-59"

#: The README starts the extracted binary by its release name.
_RUN_REF = "README.md:27-28"

#: The README warns not to source ROS in the terminal that starts LunarSim.
_SOURCE_NOTE_REF = "README.md:31"

#: The README's complete ROS 2 topic list: /cmd_vel and five published topics.
_TOPIC_LIST_REF = "README.md:53-93"

#: The velocity command topic and its message type.
_CMD_VEL_REF = "README.md:59-61"

#: A one-shot Twist publication with linear.x and angular.z is the documented example.
_CMD_VEL_EXAMPLE_REF = "README.md:69"

#: The ground-truth pose topic and its message type.
_POSE_REF = "README.md:65-67"

#: The IMU topic and its message type.
_IMU_REF = "README.md:71-73"

#: The left and right raw camera topics and their message type.
_LEFT_REF = "README.md:75-81"
_RIGHT_REF = "README.md:83-89"

#: The depth image topic and its message type.
_DEPTH_REF = "README.md:91-93"

#: Capability identifiers.  The catalogue has no class for a raw Twist
#: setpoint or for a PoseStamped observation, so those two are extensions.
_DRIVE = "x-cap.putvision.cmd_vel.v1"
_POSE = "x-cap.putvision.gt_pose.v1"
_IMU = "x-cap.putvision.imu.v1"
_IMAGE = "cap.sensing.image.v1"

#: The clone states no numerical velocity envelope for the simulated rover.
_LINEAR_LIMIT = Limit.operator_required(
    "the pinned README documents /cmd_vel but states no maximum linear velocity; "
    "the operator must supply the deployment's simulated rover envelope"
)
_ANGULAR_LIMIT = Limit.operator_required(
    "the pinned README documents /cmd_vel but states no maximum angular velocity; "
    "the operator must supply the deployment's simulated rover envelope"
)

_POSITION = Field(
    "object",
    description="Position selected from the PoseStamped pose",
    properties={
        "x": Field("number", unit="m", description="Position x in the ground-truth frame"),
        "y": Field("number", unit="m", description="Position y in the ground-truth frame"),
        "z": Field("number", unit="m", description="Position z in the ground-truth frame"),
    },
)
_ORIENTATION = Field(
    "object",
    description="Orientation selected from the PoseStamped pose",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)
_STAMP = Field(
    "object",
    description="ROS 2 builtin_interfaces/Time selected from the message header",
    properties={
        "sec": Field("integer", unit="s", description="Whole seconds"),
        "nanosec": Field("integer", unit="ns", description="Nanoseconds within the second"),
    },
)
_POSE_OUTPUT = {
    "frame_id": Field("string", description="Frame id from the PoseStamped header"),
    "stamp": _STAMP,
    "position": _POSITION,
    "orientation": _ORIENTATION,
}
_IMU_OUTPUT = {
    "orientation": _ORIENTATION,
    "linear_acceleration": Field(
        "array", unit="m/s2", length=3,
        items=Field("number", unit="m/s2", description="Linear acceleration component"),
        description="Linear acceleration selected from sensor_msgs/msg/Imu",
    ),
    "angular_velocity": Field(
        "array", unit="rad/s", length=3,
        items=Field("number", unit="rad/s", description="Angular velocity component"),
        description="Angular velocity selected from sensor_msgs/msg/Imu",
    ),
    "sampled_at": Field("string", description="Header stamp rendered as RFC 3339"),
}
_DRIVE_OUTPUT = {
    "published": Field("boolean", description="True when the driver handed the Twist to rosbridge"),
    "confirmed": Field(
        "boolean",
        description="Always false: a rosbridge publication carries no execution or stop confirmation",
    ),
}

_VECTOR_COMPONENTS = ("x", "y", "z")
_QUATERNION_COMPONENTS = ("x", "y", "z", "w")


def _finite(value, label):
    """Return ``value`` as a finite float or refuse the mapped IMU output."""
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
    return [_finite(raw.get(axis), f"{label}.{axis}") for axis in _VECTOR_COMPONENTS]


def _quaternion(raw):
    """Validate and return the orientation components in x, y, z, w order."""
    if not isinstance(raw, dict):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "IMU orientation is absent")
    values = [_finite(raw.get(name), f"orientation.{name}") for name in _QUATERNION_COMPONENTS]
    if math.sqrt(sum(value * value for value in values)) == 0.0:
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "IMU orientation is the zero quaternion")
    return values


def _stamp(raw):
    """Render a ROS 2 header stamp as the class's RFC 3339 string."""
    if not isinstance(raw, dict):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "IMU header stamp is absent")
    seconds, nanoseconds = raw.get("sec"), raw.get("nanosec")
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
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID",
                           "IMU header stamp is not a representable time") from exc
    return f"{base}.{nanoseconds:09d}Z"


def _rotate(quaternion, vector):
    """Rotate a body-frame vector into the world frame with the reported orientation."""
    x, y, z, w = quaternion
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    vx, vy, vz = vector
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return [
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    ]


def _image_stream(topic, source_ref):
    """One fixed raw-image stream; image bytes are bounded by the SDK client policy."""
    return {
        "topic": topic,
        "type": "sensor_msgs/msg/Image",
        "operation": "subscribe",
        "source_ref": source_ref,
        "image": {"max_input_bytes": 8 * 1024 * 1024, "max_pixels": 4 * 1024 * 1024},
    }


class LunarSim(RosDriver):
    """Configuration-only ROS 2 rosbridge driver for the LunarSim topic graph."""

    device_id = "lunarsim"
    #: One Driver has one catalogue kind.  The camera-suite kind is the only
    #: kind that binds the supported image artifact class for the three
    #: camera streams; the drive, pose and IMU are extension capabilities.
    device_kind = "sensor.camera"
    mode = "simulated"
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeLunarsim"}
    tags = ["ros", "ros2", "simulation", "lunarsim", "lunar-rover", "mobile-base",
            "cmd-vel", "pose", "imu", "camera"]
    display_name = "LunarSim lunar-rover simulator"
    vendor = "PUTvision"
    model = "LunarSim"
    facts = [
        Fact("The container installs ROS 2 Humble with ros-humble-desktop.",
             source="upstream_code", ref=_ROS2_REF),
        Fact("The image downloads LunarSim.tar.xz from the project's releases/latest URL and extracts "
             "LunarSim.x86_64.", source="upstream_code", ref=_BINARY_REF),
        Fact("The README runs the extracted simulator binary with ./LunarSim.x86_64.",
             source="vendor_doc", ref=_RUN_REF),
        Fact("The README warns not to source ROS in the terminal where LunarSim runs.",
             source="vendor_doc", ref=_SOURCE_NOTE_REF),
        Fact("The README's ROS 2 Topics section lists /cmd_vel as the subscribed topic and five published "
             "topics: /lunarsim/gt/pose, /lunarsim/imu, the left and right camera images and the depth image; "
             "it documents no service, action, pause, reset or stop endpoint.",
             source="vendor_doc", ref=_TOPIC_LIST_REF),
        Fact("The README documents /cmd_vel as a geometry_msgs/Twist velocity command for the robot.",
             source="vendor_doc", ref=_CMD_VEL_REF),
        Fact("The README example publishes one geometry_msgs/msg/Twist on /cmd_vel with linear.x 1.0 and "
             "angular.z 0.0.", source="vendor_doc", ref=_CMD_VEL_EXAMPLE_REF),
        Fact("The README documents /lunarsim/gt/pose as a geometry_msgs/PoseStamped ground-truth robot pose.",
             source="vendor_doc", ref=_POSE_REF),
        Fact("The README documents /lunarsim/imu as sensor_msgs/Imu data.", source="vendor_doc", ref=_IMU_REF),
        Fact("The README documents /lunarsim/camera_left/raw as a sensor_msgs/Image left camera image.",
             source="vendor_doc", ref=_LEFT_REF),
        Fact("The README documents /lunarsim/camera_right/raw as a sensor_msgs/Image right camera image.",
             source="vendor_doc", ref=_RIGHT_REF),
        Fact("The README documents /lunarsim/camera_depth/depth as a sensor_msgs/Image depth image.",
             source="vendor_doc", ref=_DEPTH_REF),
    ]
    safe_state = (
        "No acknowledged ROS stop, pause or reset service or action exists in the pinned clone: "
        "/cmd_vel is an unacknowledged Twist publication, so this package declares no safe state and "
        "the stock e-stop only latches it in software without claiming that the simulated rover stopped."
    )
    #: The fake is an event-driven contract stand-in, not a capture of simulator
    #: traffic.  It runs no LunarSim binary, engine, renderer, physics or clock.
    fidelity = {
        "engine": "analytic:ROS-free contract fake with canned placeholder replies (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies; no LunarSim binary, physics step, sensor renderer, "
                     "wall-clock pacing or state-hash replay. It is not a recording of live ROS traffic.",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free RecordingRosTransport: it answers the declared /cmd_vel publication and "
            "the five declared subscriptions with placeholder messages and runs no LunarSim binary, ROS graph, "
            "physics, renderer or wall-clock loop",
            "the pose, IMU and image values are placeholders and do not move, accelerate or update; a live run "
            "must receive the simulator's own samples",
            "the upstream simulator binary is downloaded from the latest release (Dockerfile:55-59), not built "
            "from the clone, so its internal timing, physics, camera encodings and image dimensions are not "
            "available in the pinned source",
            "the fake returns a 4x2 BGR8 left/right frame and a 4x2 16UC1 depth frame; the real camera sizes "
            "and encodings are not stated in the clone and the SDK rejects encodings outside its supported set",
            "the README also documents /lunarsim/camera_left/compressed and /lunarsim/camera_right/compressed "
            "(README.md:79, README.md:87); those CompressedImage streams are NOT COVERED and the driver selects "
            "the raw Image streams",
            "no stop, pause or reset service or action exists in the pinned clone; a zero-velocity Twist is "
            "transmission-only and the fake does not invent an acknowledgement",
            "a live run requires the operator's LunarSim container, ROS 2 Humble graph and rosbridge "
            "WebSocket endpoint; none of them is started or validated here",
        ],
    }

    parameters = {}
    reads = {}
    commands = {
        _DRIVE: {
            "topic": "/cmd_vel",
            "type": "geometry_msgs/msg/Twist",
            "operation": "publish",
            "source_ref": _CMD_VEL_REF,
            "type_ref": _CMD_VEL_REF,
            "message": {
                "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
                "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
            },
            "args": {
                "linear.x": {"from": "input.linear_velocity"},
                "angular.z": {"from": "input.angular_velocity"},
            },
        },
        _POSE: {
            "topic": "/lunarsim/gt/pose",
            "type": "geometry_msgs/msg/PoseStamped",
            "operation": "subscribe",
            "source_ref": _POSE_REF,
            "type_ref": _POSE_REF,
            "result": {"map": {
                "frame_id": "header.frame_id",
                "stamp": "header.stamp",
                "position": "pose.position",
                "orientation": "pose.orientation",
            }},
        },
        _IMU: {
            "topic": "/lunarsim/imu",
            "type": "sensor_msgs/msg/Imu",
            "operation": "subscribe",
            "source_ref": _IMU_REF,
            "type_ref": _IMU_REF,
            "result": {"map": {
                "orientation": "orientation",
                "linear_acceleration": "linear_acceleration",
                "angular_velocity": "angular_velocity",
                "sampled_at": "header.stamp",
            }},
        },
        _IMAGE: {
            "cameras": {
                "left": _image_stream("/lunarsim/camera_left/raw", _LEFT_REF),
                "right": _image_stream("/lunarsim/camera_right/raw", _RIGHT_REF),
                "depth": _image_stream("/lunarsim/camera_depth/depth", _DEPTH_REF),
            },
        },
    }
    actions = {
        _DRIVE: Action(
            name="publish_cmd_vel",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one geometry_msgs/msg/Twist velocity setpoint to /cmd_vel. The receipt confirms "
                "only that rosbridge accepted the publication, not motion, arrival or stopping; the pinned "
                "clone exposes no acknowledged stop."
            ),
            input={
                "linear_velocity": Field(
                    "number", unit="m/s",
                    description="Body-frame forward velocity written to twist.linear.x",
                    limit=_LINEAR_LIMIT,
                ),
                "angular_velocity": Field(
                    "number", unit="rad/s",
                    description="Body-frame yaw rate written to twist.angular.z",
                    limit=_ANGULAR_LIMIT,
                ),
            },
            output=_DRIVE_OUTPUT,
        ),
        _POSE: Action(
            name="read_gt_pose",
            verb="read",
            description=(
                "Subscribe to one fresh geometry_msgs/msg/PoseStamped sample on /lunarsim/gt/pose and return "
                "the ground-truth position, orientation, frame id and header stamp."
            ),
            output=_POSE_OUTPUT,
        ),
        _IMU: Action(
            name="read_imu",
            verb="read",
            max_duration_ms=2000,
            input={
                "frame": Field(
                    "string",
                    description=(
                        "Reference frame for the returned vectors: 'body' preserves the sensor_msgs/msg/Imu "
                        "vectors, while 'world' rotates them by the reported orientation quaternion."
                    ),
                    enum=["body", "world"],
                ),
            },
            output=_IMU_OUTPUT,
            description=(
                "Subscribe to one fresh sensor_msgs/msg/Imu sample on /lunarsim/imu and return the "
                "orientation quaternion, linear acceleration, angular velocity and the RFC 3339 header stamp."
            ),
        ),
    }
    #: The pinned clone exposes no ROS service or action that could acknowledge
    #: a stop.  A zero-velocity publication is transmission-only, so the driver
    #: declares no fabricated safety binding; the stock e-stop reports the gap.
    safety_bindings = {}

    def call(self, capability_id, args=None, ctx=None):
        """Map the IMU message objects onto this extension's array output contract."""
        result = super().call(capability_id, args, ctx)
        if capability_id != _IMU:
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
