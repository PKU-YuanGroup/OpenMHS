"""OpenMHS rosbridge driver for the Mobipick tables-demo experiment camera.

The upstream repository is a ROS 1 Noetic demo stack for the Mobipick mobile
manipulator.  The self-contained device it ships is ``experiment_camera``: a
static Gazebo RGB camera whose raw images are published on
``/experiment_camera/image_raw`` by ``libgazebo_ros_camera.so``.  This package
is a configuration-only :class:`~mhs.driver.RosDriver` over that fixed image
stream.  It declares no Python native class, does not start Gazebo or any ROS
node, and does not import the upstream clone.

Every endpoint, type and fact cites the pinned clone at
``adbfa53af2f6221501215bfb18d2d108225bc04f``.  The fake transport is ROS-free.
No ROS graph, Gazebo simulator or camera hardware was contacted.
"""

from mhs.driver import Action, Fact, RosDriver

#: README.md names the camera, the message type and the absolute image topic.
_IMAGE_SOURCE_REF = "experiment_camera_recorder/README.md:3-5"

#: Launch defaults and the xacro forwarding; these are configurable defaults,
#: not device limits.
_CAMERA_LAUNCH_REF = "experiment_camera_recorder/launch/camera.launch:9-11"


class MobipickExperimentCamera(RosDriver):
    device_id = "mobipick_experiment_camera"
    device_kind = "sensor.camera"
    mode = "simulated"
    risk = "R1"
    ros_version = 1
    #: A complete default 1280x720 R8G8B8 frame exceeds the 1 MiB rosbridge
    #: default after JSON encoding.  This is a client transport budget, not a
    #: camera maximum-resolution claim.
    max_message_bytes = 16 * 1024 * 1024
    backends = {"fake": ".fake:FakeMobipickExperimentCamera"}
    tags = ["ros", "ros1", "gazebo", "simulation", "camera", "image", "mobipick"]
    display_name = "Mobipick tables-demo experiment camera"
    vendor = "DFKI-NI"
    resource_id = "camera"
    facts = [
        Fact("The experiment_camera_recorder package provides a transparent, static Gazebo RGB camera "
             "named experiment_camera and publishes sensor_msgs/Image messages on "
             "/experiment_camera/image_raw.",
             source="vendor_doc", ref=_IMAGE_SOURCE_REF),
        Fact("The camera description declares a Gazebo sensor of type camera with always_on true, an "
             "update rate from the update_rate argument, image width and height from the width and "
             "height arguments, and format R8G8B8.",
             source="upstream_code", ref="experiment_camera_recorder/urdf/experiment_camera.urdf.xacro:25-36"),
        Fact("The camera description loads libgazebo_ros_camera.so with cameraName experiment_camera, "
             "robotNamespace /, imageTopicName image_raw and cameraInfoTopicName camera_info.",
             source="upstream_code",
             ref="experiment_camera_recorder/urdf/experiment_camera.urdf.xacro:42-49"),
        Fact("camera.launch declares the launch arguments width, height and update_rate with the defaults "
             "1280, 720 and 10.0.",
             source="upstream_code", ref=_CAMERA_LAUNCH_REF),
        Fact("camera.launch sets the experiment_camera_description parameter by running xacro on "
             "experiment_camera.urdf.xacro with width, height and update_rate taken from its launch "
             "arguments.",
             source="upstream_code", ref="experiment_camera_recorder/launch/camera.launch:17-19"),
        Fact("camera.launch starts frame_recorder.py only when its record argument is true and passes it "
             "the image_topic parameter /experiment_camera/image_raw.",
             source="upstream_code", ref="experiment_camera_recorder/launch/camera.launch:26-28"),
        Fact("The sensor and its camera plugin both set their always-on flags true (`always_on` and "
             "`alwaysOn`).",
             source="upstream_code",
             ref="experiment_camera_recorder/urdf/experiment_camera.urdf.xacro:27-43"),
    ]
    safe_state = ("No actuation: a capture is a passive read of the simulated camera and this package "
                  "declares no motion command or stop endpoint.")
    fidelity = {
        "engine": "analytic:ROS-free scripted transport (no Gazebo rendering)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven stand-in with fixed placeholder pixels; it does not advance a Gazebo "
                     "world clock, render a scene or replay captured traffic.",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free scripted transport: it answers the declared image subscription and "
            "runs no Gazebo rendering, physics, sensor noise, lighting or camera pose",
            "the fake returns a 4x3 RGB8 placeholder frame; the pinned launch defaults are 1280x720, and a "
            "live deployment may override width and height",
            "the fake packet is one fixed sample with placeholder header stamps; it does not establish "
            "producer freshness, frame rate, exposure or a real acquisition timestamp",
            "the fake does not model camera_info, calibration, the configured pose or the sensor clip range",
            "the operator's ROS graph, rosbridge endpoint, Gazebo world and camera namespace are not "
            "contained by this package; no live ROS or camera run was performed",
        ],
    }
    commands = {
        "cap.sensing.image.v1": {
            "topic": "/experiment_camera/image_raw",
            "type": "sensor_msgs/Image",
            "operation": "subscribe",
            "image": {"max_input_bytes": 8 * 1024 * 1024, "max_pixels": 4 * 1024 * 1024},
            "source_ref": _IMAGE_SOURCE_REF,
            "type_ref": "experiment_camera_recorder/README.md:4-5",
        },
    }
    actions = {
        "cap.sensing.image.v1": Action(
            name="capture",
            max_duration_ms=2000,
            cancellable=True,
            description="Capture one complete RGB frame from the fixed Gazebo experiment camera topic as a "
                        "lossless image artifact.",
        ),
    }
