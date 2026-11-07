"""OpenMHS rosbridge driver for the URSim underwater-vehicle simulator.

URSim is a ROS 1 and Unity 3D simulator for unmanned underwater vehicles
(gh.srmauvsoftware/ursim).  The pinned tree contains a Unity scene that talks
to ROS over rosbridge (``unity/Assets/Scripts/AUV.cs``) and a catkin workspace
under ``ros/src``.  This package is a configuration-only :class:`RosDriver`
over rosbridge; it declares no Python native class and neither imports nor
starts the clone, Unity or ROS.

The exposed surface is the depth and true-heading telemetry that the Unity
scene declares publishers for, and the ``/imu/data`` IMU topic.  In the pinned
scene the depth and heading publishers are registered but their coroutines are
commented out, the IMU publisher is not registered, and ``/imu/data`` is an
input: ``ImuSubscriberCallback`` sets the simulated vehicle's rotation from it
(model review, 2026-11-05).  Each is an explicit fresh-subscription
observation, so the main resource snapshot is empty and a silent publisher
fails only the observation that asked for it.  The scene connects to a
hard-coded rosbridge at ws://192.168.0.100:9090.
The compressed camera frame is NOT COVERED: the pinned coroutine is disabled,
the image class binds a sensor.camera resource rather than this world.sim
device, and the only available image capability is not a truthful simulator
observation here.

The motion/control surface is deliberately not bound.  The Unity scene accepts
thruster forces on ``/thruster`` (``ThrusterCallback.cs:20-25``), but the
pinned ROS publisher is broken (``thruster.py:4-10``) and the only "stop" is a
neutral publication on that topic, which is transmission-only.  The six
action definitions have no success field in their results and the Python
servers contain undefined names and missing success/abort paths, so a
native acknowledged stop cannot be declared.  A control binding would force
the stock e-stop to fail ``MHS.SAFETY.SAFE_STATE_UNREACHED`` rather than
pretend that publication is a stop.  The package therefore serves the
observation profile and records the control surface as NOT COVERED.

Every endpoint, type and fact cites the pinned clone at
feb7d257e61f192067209de5456965d7d0a3a612.  The fake transport is ROS-free;
no ROS graph, Unity process, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references (paths are relative to the clone root)
# ---------------------------------------------------------------------------

_DEPTH_REF = "unity/Assets/Publishers/DepthPublisher.cs:9-13"
_DEPTH_PUBLISH_REF = "unity/Assets/Scripts/AUV.cs:78-84"
_HEADING_REF = "unity/Assets/Publishers/HeadingPublisher.cs:10-16"
_HEADING_PUBLISH_REF = "unity/Assets/Scripts/AUV.cs:114-123"
_IMU_REF = "unity/Assets/Publishers/imuPublisher.cs:9-13"
_IMU_SUBSCRIBER_REF = "unity/Assets/Subscribers/ImuSubscriberCallback.cs:9-14"
_IMU_CALLBACK_REF = "unity/Assets/Subscribers/ImuSubscriberCallback.cs:21-33"
_IMU_REGISTRATION_REF = "unity/Assets/Scripts/AUV.cs:28"
_ROSBRIDGE_REF = "unity/Assets/Scripts/AUV.cs:25"
_SIMPLEJSON_LICENSE_REF = "unity/Assets/Libraries/ROSBridgeLib/SimpleJSON.cs:57-59"
_IMU_PUBLISH_REF = "unity/Assets/Scripts/AUV.cs:87-111"
_IMAGE_REF = "unity/Assets/Publishers/CompressedImagePublisher.cs:9-13"
_IMAGE_PUBLISH_REF = "unity/Assets/Scripts/AUV.cs:54-75"
_AUV_START_REF = "unity/Assets/Scripts/AUV.cs:24-32"
_AUV_UPDATE_REF = "unity/Assets/Scripts/AUV.cs:40-47"
_THRUSTER_INPUT_REF = "unity/Assets/Subscribers/ThrusterCallback.cs:20-25"
_THRUSTER_FORCE_REF = "unity/Assets/Subscribers/ThrusterCallback.cs:52-73"
_THRUSTER_NODE_REF = "ros/src/control/scripts/thruster.py:4-10"
_THRUSTER_MSG_REF = "ros/src/control/msg/thruster.msg:1-8"
_ACTION_LIST_REF = "ros/src/control/CMakeLists.txt:58-68"
_HEAVE_RESULT_REF = "ros/src/control/action/heave.action:4-5"
_HEAVE_SERVER_REF = "ros/src/control/servers/heave.py:1-47"
_ROLL_SERVER_REF = "ros/src/control/servers/roll.py:2-11"

# ---------------------------------------------------------------------------
# Wire schemas
# ---------------------------------------------------------------------------

_STAMP = Field(
    "object",
    description="ROS 1 time stamp as whole seconds and nanoseconds",
    properties={
        "secs": Field("integer", unit="s", description="Whole seconds of the ROS time stamp"),
        "nsecs": Field("integer", unit="ns", description="Nanoseconds within the ROS second"),
    },
)

_HEADER = Field(
    "object",
    description="ROS 1 std_msgs/Header",
    properties={
        "seq": Field("integer", unit="1", description="Message sequence number"),
        "stamp": _STAMP,
        "frame_id": Field("string", description="Coordinate frame of the message"),
    },
)

_QUATERNION = Field(
    "object",
    description="Orientation as an x, y, z, w quaternion",
    properties={
        "x": Field("number", unit="1", description="Quaternion x component"),
        "y": Field("number", unit="1", description="Quaternion y component"),
        "z": Field("number", unit="1", description="Quaternion z component"),
        "w": Field("number", unit="1", description="Quaternion w component"),
    },
)

_VECTOR3 = Field(
    "object",
    description="Raw three-component vector in the clone's native units",
    properties={
        "x": Field("number", unit="1", description="Vector x component"),
        "y": Field("number", unit="1", description="Vector y component"),
        "z": Field("number", unit="1", description="Vector z component"),
    },
)

_COVARIANCE = Field(
    "array",
    description="Nine raw covariance entries in the clone's native units",
    length=9,
    items=Field("number", unit="1", description="One covariance entry"),
)

_DEPTH_OUTPUT = {
    "depth": Field(
        "number",
        unit="1",
        description="Raw /depth data value; the clone publishes Unity world Y and states no unit",
    ),
}

_HEADING_OUTPUT = {
    "heading_deg": Field(
        "number",
        unit="deg",
        description="Raw /imu/HeadingTrue_degree data value in degrees",
    ),
}

_IMU_OUTPUT = {
    "header": _HEADER,
    "orientation": _QUATERNION,
    "orientation_covariance": _COVARIANCE,
    "angular_velocity": _VECTOR3,
    "angular_velocity_covariance": _COVARIANCE,
    "linear_acceleration": _VECTOR3,
    "linear_acceleration_covariance": _COVARIANCE,
}

# ---------------------------------------------------------------------------
# ROS bindings
# ---------------------------------------------------------------------------

_DEPTH_CAP = "x-cap.srmauvsoftware.depth.v1"
_HEADING_CAP = "x-cap.srmauvsoftware.heading.v1"
_IMU_CAP = "x-cap.srmauvsoftware.imu.v1"

# The Unity publishers declare these absolute topics and message types.
_DEPTH = {
    "topic": "/depth",
    "type": "std_msgs/Float64",
    "source_ref": _DEPTH_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"depth": "data"}},
}

_HEADING = {
    "topic": "/imu/HeadingTrue_degree",
    "type": "std_msgs/Float64",
    "source_ref": _HEADING_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"heading_deg": "data"}},
}

_IMU = {
    "topic": "/imu/data",
    "type": "sensor_msgs/Imu",
    "source_ref": _IMU_SUBSCRIBER_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {
        "header": "header",
        "orientation": "orientation",
        "orientation_covariance": "orientation_covariance",
        "angular_velocity": "angular_velocity",
        "angular_velocity_covariance": "angular_velocity_covariance",
        "linear_acceleration": "linear_acceleration",
        "linear_acceleration_covariance": "linear_acceleration_covariance",
    }},
}

class Ursim(RosDriver):
    """Configuration-only ROS 1 rosbridge observations for the URSim simulator."""

    device_id = "ursim"
    device_kind = "world.sim"
    mode = "simulated"
    #: All bound effects are isolated simulated telemetry reads; the card floor is R0.
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeUrsim"}
    tags = ["ros", "ros1", "simulation", "underwater", "auv", "ursim", "depth", "heading", "imu"]
    display_name = "URSim underwater-vehicle simulator"
    vendor = "srmauvsoftware"
    model = "URSim AUV simulator (Unity 3D and ROS 1)"

    facts = [
        Fact("DepthPublisher declares the absolute /depth topic with std_msgs/Float64.",
             source="upstream_code", ref=_DEPTH_REF),
        Fact("AUV.SendDepth publishes vehicle.transform.position.y as a Float64Msg on the depth topic.",
             source="upstream_code", ref=_DEPTH_PUBLISH_REF),
        Fact("HeadingPublisher declares the absolute /imu/HeadingTrue_degree topic with std_msgs/Float64.",
             source="upstream_code", ref=_HEADING_REF),
        Fact("AUV.SendHeading publishes vehicle.transform.rotation.eulerAngles.y as a Float64Msg on the "
             "heading topic.", source="upstream_code", ref=_HEADING_PUBLISH_REF),
        Fact("imuPublisher declares the absolute /imu/data topic with sensor_msgs/Imu.",
             source="upstream_code", ref=_IMU_REF),
        Fact("AUV.Start leaves the ros.AddPublisher(typeof(imuPublisher)) registration commented out.",
             source="upstream_code", ref=_IMU_REGISTRATION_REF),
        Fact("ImuSubscriberCallback subscribes to the absolute /imu/data topic with sensor_msgs/Imu.",
             source="upstream_code", ref=_IMU_SUBSCRIBER_REF),
        Fact("ImuSubscriberCallback.CallBack sets the Capsule's transform.rotation from the received IMU "
             "quaternion.", source="upstream_code", ref=_IMU_CALLBACK_REF),
        Fact("AUV.Start opens a ROSBridgeWebSocketConnection to ws://192.168.0.100 on port 9090.",
             source="upstream_code", ref=_ROSBRIDGE_REF),
        Fact("The vendored SimpleJSON.cs carries the MIT License, Copyright (c) 2012-2017 Markus G\u00f6bel.",
             source="upstream_code", ref=_SIMPLEJSON_LICENSE_REF),
        Fact("AUV.SendImu builds sensor_msgs/Imu with the vehicle quaternion, zero angular-velocity and "
             "linear-acceleration vectors, covariance arrays and a header.",
             source="upstream_code", ref=_IMU_PUBLISH_REF),
        Fact("CompressedImagePublisher declares the absolute /image/compressed topic with "
             "sensor_msgs/CompressedImage.", source="upstream_code", ref=_IMAGE_REF),
        Fact("AUV.SendImage reads a 640x480 RGB24 texture, encodes JPEG, sets the format string 'jpeg' "
             "and publishes a CompressedImageMsg on the compressed-image topic.",
             source="upstream_code", ref=_IMAGE_PUBLISH_REF),
        Fact("AUV.Start registers the CompressedImage, Depth and Heading publishers plus the Thruster and "
             "Imu subscriber callbacks.", source="upstream_code", ref=_AUV_START_REF),
        Fact("AUV.Update has every StartCoroutine call for image, depth, IMU and heading commented out.",
             source="upstream_code", ref=_AUV_UPDATE_REF),
        Fact("ThrusterCallback declares the absolute /thruster topic with type thrusters/ThrusterMsg.",
             source="upstream_code", ref=_THRUSTER_INPUT_REF),
        Fact("ThrusterCallback subtracts 290 from each field and calls AddForceAtPosition on the capsule "
             "Rigidbody.", source="upstream_code", ref=_THRUSTER_FORCE_REF),
        Fact("The ROS thruster node imports thrusterMsg from control.msg but passes thruster, which these "
             "lines do not define, as the rospy.Publisher message class.",
             source="upstream_code", ref=_THRUSTER_NODE_REF),
        Fact("control/thruster.msg defines eight uint16 thruster fields.",
             source="upstream_code", ref=_THRUSTER_MSG_REF),
        Fact("The control CMake action list contains heave, pitch, sway, yaw, roll and surge only; no stop, "
             "pause or reset action is generated.", source="upstream_code", ref=_ACTION_LIST_REF),
        Fact("heave.action carries only a float32 final value in its result, with no success or failure "
             "field.", source="upstream_code", ref=_HEAVE_RESULT_REF),
        Fact("The heave action server uses an undefined Float64 name, reads self.heave before assignment, "
             "references an undefined successt name and an undefined req name, and has no set_aborted path.",
             source="upstream_code", ref=_HEAVE_SERVER_REF),
        Fact("The roll server imports a control.srv roll type and creates a rospy.Service on roll_service.",
             source="upstream_code", ref=_ROLL_SERVER_REF),
    ]

    safe_state = (
        "No actuation is bound: this package only subscribes to the simulator's declared telemetry topics "
        "and commands no motion, so an MHS e-stop is the runtime software latch and no native or physical "
        "stop is claimed."
    )

    #: The checked backend is a ROS-free canned transport, not a recording of captured traffic and not the
    #: Unity simulator.  It has no physics, pacing, ROS graph or image stream.
    fidelity = {
        "engine": "canned:ROS-free topic stand-in (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies with no physics step, pacing or state-hash replay; the "
                     "same placeholder sample is returned on every subscription",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free canned transport: it answers the declared /depth, "
            "/imu/HeadingTrue_degree and /imu/data subscriptions and runs no Unity scene, ROS graph, "
            "physics, buoyancy, collision or sensor simulation",
            "the pinned AUV.Update leaves the telemetry coroutines commented out, so the declared "
            "publishers do not run in the pinned scene; the fake's samples are placeholders and a live "
            "run needs the operator to start a publisher or enable those coroutines",
            "the fake returns one placeholder sample per subscription; it establishes no sample age, "
            "publisher rate, sensor frame, trajectory or physical quantity",
            "the package binds no motion/control: /thruster accepts eight forces in the Unity subscriber, "
            "but the ROS publisher is broken and no acknowledged stop, pause, step or reset endpoint "
            "exists in the pinned source; the action servers and the mission planner are NOT COVERED",
            "the fake has no image, depth-image or point-cloud path; the CompressedImage publisher is "
            "declared but its coroutine is commented out and this package does not capture image "
            "artifacts. /depth is a scalar Float64 topic, not a depth camera",
            "in the pinned scene /imu/data is an input, not simulator output: the IMU publisher is not "
            "registered (AUV.cs:28) and ImuSubscriberCallback sets the vehicle rotation from every received "
            "sample, and no ROS node in the clone publishes it (the sensor package is empty), so the IMU "
            "observation returns another client's sample that also rotates the simulated vehicle; enabling "
            "SendImu as well would feed the scene's own rotation back into it",
            "the scene's rosbridge address is hard-coded to ws://192.168.0.100:9090 (AUV.cs:25); a live run "
            "needs a rosbridge there or an edited scene, and every observation fails NOT_READY until a "
            "publisher runs",
            "SendImu would stamp its header with TimeSpan.Seconds and Milliseconds (AUV.cs:94), the second "
            "component rather than total seconds and milliseconds in the nanosecond field; the fake's "
            "stamp is a placeholder",
        ],
    }

    commands = {
        _DEPTH_CAP: _DEPTH,
        _HEADING_CAP: _HEADING,
        _IMU_CAP: _IMU,
    }
    actions = {
        _DEPTH_CAP: Action(
            name="read_depth",
            verb="read",
            max_duration_ms=2000,
            description=(
                "Subscribe to one fresh /depth Float64 sample from the Unity simulator and return its raw "
                "data value. The clone publishes Unity world Y and states no unit or depth datum."
            ),
            output=_DEPTH_OUTPUT,
        ),
        _HEADING_CAP: Action(
            name="read_heading",
            verb="read",
            max_duration_ms=2000,
            description=(
                "Subscribe to one fresh /imu/HeadingTrue_degree Float64 sample and return the raw heading "
                "value in degrees as declared by the topic name."
            ),
            output=_HEADING_OUTPUT,
        ),
        _IMU_CAP: Action(
            name="read_imu",
            verb="read",
            max_duration_ms=2000,
            description=(
                "Subscribe to one fresh /imu/data sensor_msgs/Imu sample and return the message fields. In "
                "the pinned scene /imu/data is an input that sets the simulated vehicle's rotation and the "
                "scene's own IMU publisher is not registered, so the sample comes from another publisher, "
                "not from the simulator; no unit or frame convention is stated in the clone."
            ),
            output=_IMU_OUTPUT,
        ),
    }
