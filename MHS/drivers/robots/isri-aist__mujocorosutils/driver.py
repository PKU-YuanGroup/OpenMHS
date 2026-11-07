"""OpenMHS rosbridge driver for the MuJoCo ROS utilities plugins (gh.isri-aist/mujocorosutils).

The pinned upstream is a ROS 2 C++ plugin package for the MuJoCo simulator.  It
contains no Python driver class.  This package is a configuration-only
``RosDriver`` over rosbridge: the operator runs the ``simulate`` application
with the plugins registered and a rosbridge node separately.  Nothing here
imports, builds or launches the upstream code.

Scope is the sample plugin graph in ``xml/sample_mujoco_ros_utils.xml``:

* ``/clock`` (``rosgraph_msgs/msg/Clock``) is a read-only observation.
* ``/pose`` (``geometry_msgs/msg/PoseStamped``) and ``/vel``
  (``geometry_msgs/msg/TwistStamped``) are the body pose and velocity
  observations.
* ``/box_rangefinder`` (``mujoco_ros_utils/msg/ScalarStamped``) is a scalar
  sensor observation.
* ``/camera_pan`` (``std_msgs/msg/Float64``) is the plugin's actuator command
  subscription and the package's primary control channel.

The pinned clone registers no ROS service or action server.  ``ActuatorCommand``
writes the received value into ``d->ctrl`` once and then clears its cached value;
its plugin reset is empty, and no ROS callback can acknowledge a stop.  A stock
``RosDriver`` therefore cannot prove an acknowledged stop for the command
channel, so this package declares no safety binding and records the concrete
blocker in ``RESULT.json``.  The fake is ROS-free, F0 and made of placeholders;
no ROS graph, simulator or hardware run is claimed.

Every endpoint, type and fact cites the pinned clone at
7fc0bc03a3d33db627bada456b5304922d849747.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The README declares that this branch targets ROS 2, not ROS 1.
_ROS2_REF = "README.md:1"

#: The feature list names the upstream ROS interfaces.
_FEATURES_REF = "README.md:13"

#: ClockPublisher's default topic literal and its rosgraph_msgs publisher.
_CLOCK_TOPIC_REF = "plugin/ClockPublisher.cpp:124-126"
_CLOCK_TYPE_REF = "plugin/ClockPublisher.cpp:138"

#: PosePublisher's default body topic names and the two publisher types.
_POSE_TOPIC_REF = "plugin/PosePublisher.cpp:173-180"
_POSE_TYPE_REF = "plugin/PosePublisher.cpp:201-202"

#: ActuatorCommand's default topic, subscription type and one-shot write.
_ACTUATOR_TOPIC_REF = "plugin/ActuatorCommand.cpp:112-115"
_ACTUATOR_TYPE_REF = "plugin/ActuatorCommand.cpp:127-128"
_ACTUATOR_WRITE_REF = "plugin/ActuatorCommand.cpp:145-153"
_ACTUATOR_RESET_REF = "plugin/ActuatorCommand.cpp:134-138"

#: SensorPublisher's dimension dispatch and its ScalarStamped publisher.
_SENSOR_DISPATCH_REF = "plugin/SensorPublisher.cpp:94-118"
_SENSOR_TYPE_REF = "plugin/SensorPublisher.cpp:183-185"

#: The sample MJCF instantiates the four concrete endpoints used below.
_SAMPLE_ACTUATOR_REF = "xml/sample_mujoco_ros_utils.xml:66-69"
_SAMPLE_POSE_REF = "xml/sample_mujoco_ros_utils.xml:73-80"
_SAMPLE_SENSOR_REF = "xml/sample_mujoco_ros_utils.xml:101-106"

#: ScalarStamped carries a standard header and one Float64 value.
_SCALAR_STAMPED_REF = "msg/ScalarStamped.msg:1-2"

#: ImagePublisher and ExternalForce exist but are not exposed by this package.
_IMAGE_REF = "plugin/ImagePublisher.cpp:316-339"
_EXTERNAL_FORCE_REF = "plugin/ExternalForce.cpp:133-134"

_CLOCK_TIME = Field(
    "object",
    description="Simulation clock sample from the rosgraph_msgs/Clock clock field",
    properties={
        "sec": Field("integer", unit="s", description="Whole seconds of the simulation clock"),
        "nanosec": Field("integer", unit="ns", description="Nanoseconds within the simulation second"),
    },
)

_VECTOR3 = Field(
    "object",
    description="Three-component ROS vector from the message; the clone states no physical unit",
    properties={
        "x": Field("number", unit="1", description="x component"),
        "y": Field("number", unit="1", description="y component"),
        "z": Field("number", unit="1", description="z component"),
    },
)

_QUATERNION = Field(
    "object",
    description="Orientation quaternion from the pose message",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)

_POSE = Field(
    "object",
    description="geometry_msgs/PoseStamped pose field of the observed body",
    properties={"position": _VECTOR3, "orientation": _QUATERNION},
)

_TWIST = Field(
    "object",
    description="geometry_msgs/TwistStamped twist field of the observed body",
    properties={"linear": _VECTOR3, "angular": _VECTOR3},
)

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the publication to rosbridge"),
    "confirmed": Field("boolean", description="Always false: a rosbridge publication carries no execution confirmation"),
    "message": Field(
        "object",
        description="The std_msgs/Float64 message handed to rosbridge; it does not prove native reception",
        properties={"data": Field("number", unit="1", description="Scalar written to the message data field")},
    ),
}

_FRAME_ID = Field("string", description="Transform frame id carried by the observed message header")

_DISTANCE = Field("number", unit="1", description="Scalar rangefinder value from sensordata; the clone states no unit")

_ACTUATOR_INPUT = Field(
    "number",
    unit="1",
    description=(
        "Scalar written to d->ctrl for the configured actuator; the MJCF actuator type, scale and range are "
        "model configuration, so no numeric envelope is stated by the clone"
    ),
    limit=Limit.operator_required(
        "the pinned plugin and sample model state no numeric range or physical unit for the Float64 written to "
        "d->ctrl; the operator supplies the deployment envelope"
    ),
)

_CLOCK_TOPIC = {
    "topic": "/clock",
    "type": "rosgraph_msgs/msg/Clock",
    "source_name": "/clock",
    "source_ref": _CLOCK_TOPIC_REF,
    "type_ref": _CLOCK_TYPE_REF,
}

_POSE_TOPIC = {
    "topic": "/pose",
    "type": "geometry_msgs/msg/PoseStamped",
    "source_name": "/pose",
    "source_ref": _SAMPLE_POSE_REF,
    "type_ref": _POSE_TYPE_REF,
}

_VEL_TOPIC = {
    "topic": "/vel",
    "type": "geometry_msgs/msg/TwistStamped",
    "source_name": "/vel",
    "source_ref": _SAMPLE_POSE_REF,
    "type_ref": _POSE_TYPE_REF,
}

_SENSOR_TOPIC = {
    "topic": "/box_rangefinder",
    "type": "mujoco_ros_utils/msg/ScalarStamped",
    "source_name": "/box_rangefinder",
    "source_ref": _SAMPLE_SENSOR_REF,
    "type_ref": _SENSOR_TYPE_REF,
}

_ACTUATOR_TOPIC = {
    "topic": "/camera_pan",
    "type": "std_msgs/msg/Float64",
    "operation": "publish",
    "source_name": "/camera_pan",
    "source_ref": _SAMPLE_ACTUATOR_REF,
    "type_ref": _ACTUATOR_TYPE_REF,
    "message": {"data": 0.0},
    "args": {"data": {"from": "input.value"}},
}


class MujocoRosUtils(RosDriver):
    device_id = "mujoco_ros_utils"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeMujocoRosUtils"}
    tags = ["ros", "ros2", "mujoco", "simulation", "clock", "pose", "rangefinder", "actuator"]
    display_name = "MuJoCo ROS utilities"
    vendor = "ISRI-AIST"
    model = "mujoco_ros_utils plugins"
    facts = [
        Fact("The pinned branch is the ROS 2 branch of MujocoRosUtils.",
             source="vendor_doc", ref=_ROS2_REF),
        Fact("The README's feature list states that the plugins retrieve body poses and camera images, send "
             "commands to actuators and apply external forces through ROS interfaces.",
             source="vendor_doc", ref=_FEATURES_REF),
        Fact("ClockPublisher defaults topic_name_ to the absolute /clock when the MJCF plugin config is empty.",
             source="upstream_code", ref=_CLOCK_TOPIC_REF),
        Fact("ClockPublisher creates a rosgraph_msgs::msg::Clock publisher on topic_name_.",
             source="upstream_code", ref=_CLOCK_TYPE_REF),
        Fact("PosePublisher defaults the pose topic to mujoco/<body name>/pose and the velocity topic to "
             "mujoco/<body name>/vel; the sample explicitly sets them to /pose and /vel.",
             source="upstream_code", ref=_POSE_TOPIC_REF),
        Fact("PosePublisher creates a geometry_msgs::msg::PoseStamped publisher and a "
             "geometry_msgs::msg::TwistStamped publisher.",
             source="upstream_code", ref=_POSE_TYPE_REF),
        Fact("ActuatorCommand defaults an empty topic_name to mujoco/<actuator name>; the sample overrides "
             "it with /camera_pan.",
             source="upstream_code", ref=_ACTUATOR_TOPIC_REF),
        Fact("ActuatorCommand creates a std_msgs::msg::Float64 subscription on topic_name.",
             source="upstream_code", ref=_ACTUATOR_TYPE_REF),
        Fact("ActuatorCommand::compute spins its own executor once and, when ctrl_ is not NaN, writes it into "
             "d->ctrl[actuator_id_] and sets ctrl_ to NaN; while ctrl_ is NaN it leaves d->ctrl unchanged.",
             source="upstream_code", ref=_ACTUATOR_WRITE_REF),
        Fact("ActuatorCommand::reset has an empty body.",
             source="upstream_code", ref=_ACTUATOR_RESET_REF),
        Fact("SensorPublisher maps a one-dimensional sensor to MsgScalar and creates a "
             "mujoco_ros_utils::msg::ScalarStamped publisher for it.",
             source="upstream_code", ref=_SENSOR_DISPATCH_REF),
        Fact("SensorPublisher creates the concrete mujoco_ros_utils::msg::ScalarStamped publisher on "
             "topic_name_ for scalar sensors.",
             source="upstream_code", ref=_SENSOR_TYPE_REF),
        Fact("The sample MJCF attaches ActuatorCommand to the camera_pan actuator and configures the topic "
             "/camera_pan.",
             source="upstream_code", ref=_SAMPLE_ACTUATOR_REF),
        Fact("The sample MJCF declares the camera_pan hinge joint with range -90 90 and a position actuator "
             "named camera_pan on that joint.",
             source="upstream_code", ref="xml/sample_mujoco_ros_utils.xml:50-63"),
        Fact("The sample MJCF configures ClockPublisher with publish_rate 100 and the pose and rangefinder "
             "publishers with publish_rate 30.",
             source="upstream_code", ref="xml/sample_mujoco_ros_utils.xml:28-106"),
        Fact("The sample MJCF configures PosePublisher's pose_topic_name and vel_topic_name as /pose and /vel.",
             source="upstream_code", ref=_SAMPLE_POSE_REF),
        Fact("The sample MJCF declares a box_rangefinder sensor and configures SensorPublisher's topic_name as "
             "/box_rangefinder.",
             source="upstream_code", ref=_SAMPLE_SENSOR_REF),
        Fact("ScalarStamped carries a std_msgs/Header and one std_msgs/Float64 value.",
             source="upstream_code", ref=_SCALAR_STAMPED_REF),
        Fact("ImagePublisher publishes a sensor_msgs::msg::Image with encoding rgb8 for color and 32FC1 for "
             "depth; this package does not expose the camera plugin.",
             source="upstream_code", ref=_IMAGE_REF),
        Fact("ExternalForce subscribes to mujoco_ros_utils::msg::ExternalForce; this package does not expose "
             "the force plugin.",
             source="upstream_code", ref=_EXTERNAL_FORCE_REF),
    ]
    safe_state = (
        "No acknowledged ROS stop is declared: the pinned plugins create only publishers and subscriptions, "
        "ActuatorCommand's reset is empty and a Float64 publication is transmission-only, so the package does not "
        "claim a safe state it cannot confirm."
    )
    fidelity = {
        "engine": "canned:ROS fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned observations; no MuJoCo step, pacing or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free canned transport: it answers the declared /clock, /pose, /vel, "
            "/box_rangefinder and /camera_pan endpoints and runs no MuJoCo physics, plugins, sensors or "
            "wall-clock loop",
            "all clock, pose, twist and rangefinder values are placeholders; they do not advance with the "
            "MuJoCo simulation or establish a trajectory",
            "the package exposes no acknowledged stop, reset or step endpoint; the plugin reset callbacks are "
            "internal, and a Float64 topic publication is transmission-only",
            "the sample's optional output_tf PosePublisher and its frame broadcasts are not exposed",
            "the ActuatorCommand write persists: the plugin writes d->ctrl once and then leaves it unchanged, so "
            "a published value stays the actuator's control input (the sample's camera_pan is a position "
            "actuator); the fake records only the publication",
            "the plugin topics publish only while MuJoCo steps the model; while the simulate application is "
            "paused or not stepping, the four resource reads fail NOT_READY at their 2000 ms timeout and every "
            "command still publishes but completes only after those reads (reviewer probe on the fake)",
            "the camera color/depth images and CameraInfo, the ExternalForce subscription, the PointStamped, "
            "Vector3Stamped and QuaternionStamped sensor variants, /box_framepos and /box_framequat are NOT "
            "COVERED",
        ],
    }

    parameters = {
        "sim_time": _CLOCK_TIME,
        "body_pose": _POSE,
        "body_twist": _TWIST,
        "rangefinder": _DISTANCE,
    }
    reads = {
        "sim_time": dict(_CLOCK_TOPIC, path="clock", timeout_ms=2000),
        "body_pose": dict(_POSE_TOPIC, path="pose", timeout_ms=2000),
        "body_twist": dict(_VEL_TOPIC, path="twist", timeout_ms=2000),
        "rangefinder": dict(_SENSOR_TOPIC, path="value.data", timeout_ms=2000),
    }
    commands = {
        "x-cap.isri-aist.clock.v1": dict(
            _CLOCK_TOPIC,
            operation="subscribe",
            result={"map": {"sim_time": "output.clock"}},
        ),
        "x-cap.isri-aist.body_pose.v1": dict(
            _POSE_TOPIC,
            operation="subscribe",
            result={"map": {"pose": "output.pose", "frame_id": "output.header.frame_id"}},
        ),
        "x-cap.isri-aist.body_twist.v1": dict(
            _VEL_TOPIC,
            operation="subscribe",
            result={"map": {"twist": "output.twist", "frame_id": "output.header.frame_id"}},
        ),
        "x-cap.isri-aist.rangefinder.v1": dict(
            _SENSOR_TOPIC,
            operation="subscribe",
            result={"map": {"distance": "output.value.data", "frame_id": "output.header.frame_id"}},
        ),
        "x-cap.isri-aist.actuator_command.v1": _ACTUATOR_TOPIC,
    }
    actions = {
        "x-cap.isri-aist.clock.v1": Action(
            name="read_sim_clock",
            verb="read",
            description="Read one /clock sample published by the ClockPublisher plugin",
            output={"sim_time": _CLOCK_TIME},
        ),
        "x-cap.isri-aist.body_pose.v1": Action(
            name="read_body_pose",
            verb="read",
            description="Read one body pose sample and its frame id from the PosePublisher /pose topic",
            output={"pose": _POSE, "frame_id": _FRAME_ID},
        ),
        "x-cap.isri-aist.body_twist.v1": Action(
            name="read_body_twist",
            verb="read",
            description="Read one body velocity sample and its frame id from the PosePublisher /vel topic",
            output={"twist": _TWIST, "frame_id": _FRAME_ID},
        ),
        "x-cap.isri-aist.rangefinder.v1": Action(
            name="read_rangefinder",
            verb="read",
            description="Read one scalar rangefinder sample from the SensorPublisher topic",
            output={"distance": _DISTANCE, "frame_id": _FRAME_ID},
        ),
        "x-cap.isri-aist.actuator_command.v1": Action(
            name="publish_actuator_command",
            verb="invoke",
            risk="R0",
            description=(
                "Publish one std_msgs/Float64 to the ActuatorCommand subscription. The plugin writes the "
                "value into d->ctrl once and leaves it there until another message arrives, so it stays the "
                "actuator's control input. The receipt proves only that rosbridge accepted the publication; it "
                "does not prove motion, target arrival or stopping."
            ),
            input={"value": _ACTUATOR_INPUT},
            output=_PUBLISHED,
            examples=[{"value": 0.0}],
        ),
    }
    # The pinned plugins create no ROS service or action server.  A Float64
    # publication is transmission-only and is not an acknowledged stop, so this
    # declaration leaves safety_bindings empty instead of fabricating one.
    safety_bindings = {}

    def call(self, capability_id, args=None, ctx=None):
        # The bridge's publication receipt is constant.  Returning the message
        # that was actually handed to rosbridge makes the requested value
        # observable without claiming native reception or motion.
        result = super().call(capability_id, args, ctx)
        if capability_id == "x-cap.isri-aist.actuator_command.v1" and isinstance(result, dict):
            result = dict(result)
            result["message"] = {"data": (args or {}).get("value")}
        return result
