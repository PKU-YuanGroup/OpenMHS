"""OpenMHS rosbridge driver for the Easys simulated camera pipeline (gh.hrjp/easys_sim).

The pinned repository is a ROS 2 Humble / Gazebo Garden simulator for the
Easys underwater robot.  It also ships ``balloon_detect``, a concrete ROS 2
Python node that subscribes to the simulator camera image on ``/camera`` and
publishes an annotated ``sensor_msgs/Image`` on ``image_processed``.

The chosen device is that camera pipeline: the Gazebo camera feed and the
balloon detector's image output.  This package is a configuration-only
:class:`RosDriver` over rosbridge; it declares no Python native class and
never imports, launches or runs ROS, Gazebo or the upstream node.  Complete
Image packets are captured through the SDK's fixed ROS image path as bounded
local PNG artifacts.  The receipt describes the packet that was observed; it
makes no exposure, sample-age, detection-quality or motion claim.

The pinned clone declares no acknowledged ROS stop, pause, reset or world
step service.  The thruster command publications are therefore NOT COVERED:
a zero-thrust topic publication is not an acknowledged stop, and this passive
camera package does not claim to control the vehicle or the simulator world.

Every endpoint, type and fact cites the pinned clone at
65f5daeb8fb82970ea03b5a0cc7a24509ea8c5c5.  The fake transport is ROS-free;
no ROS graph, Gazebo process, camera, balloon detector or hardware is
contacted.
"""

from mhs.driver import Action, Fact, RosDriver

_BRIDGE = "Easys_description/config/ros_gz_bridge/bridge_topic.yaml"
_DETECTOR = "balloon_detect/balloon_detect/balloon_detect.py"

#: The bridge maps the absolute ROS image topic /camera to the Gazebo topic.
_CAMERA_REF = _BRIDGE + ":38-42"
_CAMERA_TYPE_REF = _BRIDGE + ":41"

#: The detector subscription and publisher declarations.
_DETECTOR_PUB_REF = _DETECTOR + ":17"
_DETECTOR_TYPE_REF = _DETECTOR + ":3"

#: The detector's documented processing path from a raw frame to an rgb8 frame.
_DETECTOR_MASKS_REF = _DETECTOR + ":20-55"
_DETECTOR_BOXES_REF = _DETECTOR + ":91-108"
_DETECTOR_PUBLISH_REF = _DETECTOR + ":85-89"

#: The Gazebo camera sensor configured for the easys_a1 model.
_CAMERA_SENSOR_REF = "Easys_description/model/easys_a1.sdf:268-283"

#: Client conversion bounds, not device limits.  They admit the pinned
#: 320x240 rgb8 frame (230400 bytes) with room for the JSON envelope.
_IMAGE = {"max_input_bytes": 1024 * 1024, "max_pixels": 1024 * 1024}


class EasysSimCamera(RosDriver):
    device_id = "easys-camera"
    device_kind = "sensor.camera"
    mode = "simulated"
    # The selected camera pipeline is passive: it renders and annotates
    # images and exposes no actuator, motion command, stop or reset endpoint
    # in this package.
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeEasysSim"}
    tags = ["ros", "ros2", "gazebo", "simulation", "camera", "image", "balloon", "underwater"]
    display_name = "Easys simulated camera and balloon detector"
    vendor = "hrjp"
    model = "Easys camera and balloon_detect pipeline"
    resource_id = "camera"
    facts = [
        Fact("The README states Ubuntu 22.04, ROS 2 Humble and Gazebo Garden.",
             source="vendor_doc", ref="README.md:4-7"),
        Fact("The simulation launch includes the ros_gz_sim Gazebo launch and starts the "
             "ros_gz_bridge parameter_bridge node with the bridge_topic.yaml config.",
             source="upstream_code", ref="Easys_description/launch/sim.launch.xml:7-15"),
        Fact("bridge_topic.yaml maps the ROS topic /camera to the Gazebo topic /camera with "
             "ROS type sensor_msgs/msg/Image and Gazebo type gz.msgs.Image.",
             source="upstream_code", ref=_CAMERA_REF),
        Fact("The Easys camera sensor is named camera, type camera, with width 320, height 240, "
             "horizontal FOV 1.047, update rate 30 Hz and Gazebo topic camera.",
             source="upstream_code", ref=_CAMERA_SENSOR_REF),
        Fact("balloon_detect imports Image from sensor_msgs.msg, subscribes to the absolute /camera "
             "topic with queue size 10 and creates an Image publisher on the relative "
             "image_processed topic with queue size 10.",
             source="upstream_code", ref=_DETECTOR + ":3-17"),
        Fact("image_callback converts the received frame from RGB to HSV, builds a red mask from two "
             "hue bands and blue and yellow masks, and passes each mask with the label Red, Blue or "
             "Yellow to mask2boudingbox.",
             source="upstream_code", ref=_DETECTOR_MASKS_REF),
        Fact("mask2boudingbox finds the external contours of the mask it is given and, for each "
             "contour whose area exceeds 50, draws a green rectangle and the color label on the "
             "current frame.",
             source="upstream_code", ref=_DETECTOR_BOXES_REF),
        Fact("image_callback converts the annotated frame back to an Image with cv2_to_imgmsg and "
             "encoding rgb8, passing no header, and publishes it with self.publisher.",
             source="upstream_code", ref=_DETECTOR_PUBLISH_REF),
        Fact("The Under Water Robocon launch includes the simulation launch and starts the "
             "balloon_detect node.",
             source="upstream_code", ref="uw_robocon_sim/launch/joy_sim.launch.xml:5-10"),
        Fact("bridge_topic.yaml maps four thruster command topics, /left_down/cmd_thruster, "
             "/right_down/cmd_thruster, /left_up/cmd_thruster and /right_up/cmd_thruster, "
             "from std_msgs/msg/Float64 to gz.msgs.Double.",
             source="upstream_code", ref=_BRIDGE + ":2-24"),
        Fact("bridge_topic.yaml also maps /tf as tf2_msgs/msg/TFMessage (Gazebo gz.msgs.Pose_V) and "
             "/imu as sensor_msgs/msg/Imu (Gazebo gz.msgs.IMU).",
             source="upstream_code", ref=_BRIDGE + ":26-36"),
        Fact("The simulation launch also starts robot_state_publisher, joy_node, the Easys_ros nodes "
             "joy2cmd, Easys_controller and thruster_output_converter, and rviz2.",
             source="upstream_code", ref="Easys_description/launch/sim.launch.xml:17-41"),
        Fact("The README's manual setup clones the separate Easys_ros repository next to Easys_sim.",
             source="vendor_doc", ref="README.md:11-19"),
        Fact("The easys model declares a camera sensor named camera with width 320, height 240, "
             "update rate 30 Hz and Gazebo topic camera, like easys_a1.",
             source="upstream_code", ref="Easys_description/model/easys.sdf:268-283"),
        Fact("The balloon_detect package manifest leaves its licence as 'TODO: License declaration'.",
             source="upstream_code", ref="balloon_detect/package.xml:8"),
    ]
    safe_state = (
        "The selected camera pipeline is passive: the pinned clone exposes no actuator, stop, "
        "pause, reset or world-control ROS endpoint for it. An MHS e-stop engages only the "
        "software latch and refuses new captures; it does not stop Gazebo, the balloon_detect "
        "node or any external thruster publisher."
    )
    #: The fake answers the two declared image subscriptions with canned frames and runs no
    #: Gazebo renderer, detector, physics or ROS graph.  It is an analytic stand-in, not a
    #: recording of captured traffic.
    fidelity = {
        "engine": "analytic:ROS-free canned camera packets (no renderer or detector)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned image replies with no Gazebo render, camera timing, "
                     "balloon detection or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free rosbridge contract stand-in: it answers the two declared "
            "Image subscriptions and runs no Gazebo Garden renderer, sensors system, "
            "ros_gz_bridge, balloon_detect, OpenCV mask or bounding-box code",
            "the fake returns a 2x2 rgb8 placeholder frame, not the pinned sensor's 320x240 "
            "image; the real dimensions and the 30 Hz update rate are source facts, not the "
            "fake's timing or resolution",
            "the /image_processed reply is a canned frame; the fake does not execute the "
            "detector, so it cannot show that a balloon was detected or annotated",
            "the detector publishes the annotated frame without assigning a header "
            "(balloon_detect.py:85-89), so the detected stream's stamp and frame id are whatever "
            "cv_bridge's cv2_to_imgmsg leaves (cv_bridge is not in the clone and was not checked); "
            "the fake answers it with a zero stamp and an empty frame id as placeholders",
            "only the Under Water Robocon launch (joy_sim.launch.xml) starts balloon_detect; with "
            "the default sim.launch.xml no node publishes /image_processed and a detected capture "
            "fails after its deadline",
            "sim.launch.xml also starts joy_node and the Easys_ros joystick, controller and thruster "
            "nodes (Easys_ros is a separate repository, not in the clone); they command the "
            "thrusters independently of this package and an MHS e-stop does not stop them",
            "the thruster command publications, /imu, /tf, the Gazebo world step, pause, reset "
            "and any vehicle motion are NOT COVERED by this passive camera package",
            "the pinned clone declares no acknowledged ROS stop, pause or reset endpoint for "
            "this package; an e-stop latches in software and does not stop Gazebo or the "
            "detector node",
            "no live ROS graph, Gazebo world, camera render or hardware run was performed; "
            "the evidence is contract_checked only",
        ],
    }

    commands = {
        "cap.sensing.image.v1": {
            "cameras": {
                "camera": {
                    "topic": "/camera",
                    "type": "sensor_msgs/msg/Image",
                    "operation": "subscribe",
                    "image": dict(_IMAGE),
                    "source_name": "/camera",
                    "source_ref": _CAMERA_REF,
                    "type_ref": _CAMERA_TYPE_REF,
                },
                "detected": {
                    "topic": "/image_processed",
                    "type": "sensor_msgs/msg/Image",
                    "operation": "subscribe",
                    "image": dict(_IMAGE),
                    "source_name": "image_processed",
                    "source_ref": _DETECTOR_PUB_REF,
                    "type_ref": _DETECTOR_TYPE_REF,
                },
            },
        },
    }
    actions = {
        "cap.sensing.image.v1": Action(
            name="capture",
            max_duration_ms=2000,
            cancellable=True,
            description=(
                "Capture one complete sensor_msgs/Image packet from the selected Easys stream: "
                "camera for the raw Gazebo /camera feed, detected for the balloon_detect "
                "/image_processed output. The receipt reports the observed pixels and header; "
                "it makes no exposure, age, detection-quality or motion claim."
            ),
        ),
    }
