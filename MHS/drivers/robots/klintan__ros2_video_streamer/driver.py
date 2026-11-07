"""OpenMHS rosbridge driver for the ros2_video_streamer camera simulator.

The upstream ``camera_simulator`` is a Python ROS 2 node.  This package is a
configuration-only ``RosDriver`` over rosbridge; it declares no Python native
class.  The primary interface is the fixed ``sensor_msgs/msg/Image`` stream the
node publishes for a recorded video or a folder of images.  Complete BGR8
frames and their own ROS 2 headers are captured through the stock bounded
image-artifact path.  The optional CameraInfo publication is calibration
metadata, not a substitute for the image, and the unused
``get_compressed_msg`` helper has no publisher.  Only video mode streams: in
image-folder mode the node publishes every image once inside its constructor,
before it spins, and a video without ``--loop`` exits at its end, so captures
then fail ``MHS.DEVICE.NOT_READY`` (model review of 2026-11-04).

Every endpoint, type and fact cites the pinned clone at
4fc6d858d748322250cb0dc5a7864ac2576d148f.  The fake transport is ROS-free;
no ROS graph, OpenCV decoder, video file or camera is contacted.
"""

from mhs.driver import Action, Fact, RosDriver

#: The node declares image_topic with this absolute source default.
_IMAGE_TOPIC_REF = "camera_simulator/camera_simulator.py:39"

#: The module imports Image from sensor_msgs.msg; the publisher uses Image.
_IMAGE_TYPE_REF = "camera_simulator/camera_simulator.py:18"

#: get_image_msg converts the decoded frame with CvBridge using encoding bgr8.
_IMAGE_ENCODING_REF = "camera_simulator/camera_simulator.py:161"


class Ros2VideoStreamer(RosDriver):
    device_id = "video_streamer"
    device_kind = "sensor.camera"
    mode = "simulated"
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeRos2VideoStreamer"}
    tags = ["ros", "ros2", "camera", "simulator", "image", "video", "replay"]
    display_name = "ROS 2 video streamer camera simulator"
    vendor = "klintan"
    model = "camera_simulator"
    resource_id = "camera"
    #: A default 1280x720 BGR8 frame is about 2.7 MB of bytes before base64
    #: and JSON expansion.  This is a client transport budget, not a camera
    #: resolution limit; the upstream node declares no fixed frame size.
    max_message_bytes = 16 * 1024 * 1024
    facts = [
        Fact("The node declares the image_topic parameter with the absolute default '/image/image_raw'.",
             source="upstream_code", ref=_IMAGE_TOPIC_REF),
        Fact("The node declares the camera_info_topic parameter with the absolute default '/image/camera_info'.",
             source="upstream_code", ref="camera_simulator/camera_simulator.py:40"),
        Fact("The module imports Image, CompressedImage and CameraInfo from sensor_msgs.msg.",
             source="upstream_code", ref=_IMAGE_TYPE_REF),
        Fact("The node creates a sensor_msgs Image publisher on image_topic_ with queue size 5 and a CameraInfo "
             "publisher on camera_info_topic_ with queue size 5.",
             source="upstream_code", ref="camera_simulator/camera_simulator.py:47-48"),
        Fact("The node declares the frame_id parameter with the literal default 'camera'.",
             source="upstream_code", ref="camera_simulator/camera_simulator.py:42"),
        Fact("image_callback calls get_time_msg and passes the result with the frame to get_image_msg.",
             source="upstream_code", ref="camera_simulator/camera_simulator.py:117-118"),
        Fact("get_time_msg fills builtin_interfaces Time sec and nanosec from the node clock's "
             "seconds_nanoseconds().",
             source="upstream_code", ref="camera_simulator/camera_simulator.py:147-153"),
        Fact("get_image_msg converts the frame with CvBridge().cv2_to_imgmsg(image, encoding='bgr8').",
             source="upstream_code", ref=_IMAGE_ENCODING_REF),
        Fact("get_image_msg sets header.stamp to its time argument and header.frame_id to self.frame_id_.",
             source="upstream_code", ref="camera_simulator/camera_simulator.py:162-163"),
        Fact("image_callback publishes CameraInfo only when self.calib is truthy, then publishes the Image.",
             source="upstream_code", ref="camera_simulator/camera_simulator.py:120-124"),
        Fact("get_camera_info fills CameraInfo width, height, distortion_model and d, k, r and p from the "
             "calibration YAML.",
             source="upstream_code", ref="camera_simulator/camera_simulator.py:132-141"),
        Fact("get_compressed_msg constructs a CompressedImage and sets format 'jpeg'.",
             source="upstream_code", ref="camera_simulator/camera_simulator.py:166-175"),
        Fact("For video mode the node creates a timer with period 1.0/video_fps and registers image_callback.",
             source="upstream_code", ref="camera_simulator/camera_simulator.py:90-93"),
        Fact("In CameraSimulator.__init__, when type is not 'video', the node publishes every .jpg, .jpeg or "
             ".png file of the folder in natural-sort order without a timer and then logs that all images have "
             "been published.",
             source="upstream_code", ref="camera_simulator/camera_simulator.py:36-98"),
        Fact("In video mode, when a read fails and loop is false, image_callback cancels the timer, destroys the "
             "node and calls exit(); when loop is true it rewinds to 0 ms and reads again.",
             source="upstream_code", ref="camera_simulator/camera_simulator.py:100-110"),
        Fact("main constructs CameraSimulator and only then calls rclpy.spin.",
             source="upstream_code", ref="camera_simulator/camera_simulator.py:191-196"),
        Fact("The README describes the package as a ROS2 python node that streams video files or folder images "
             "to a topic and is used as a camera simulator.",
             source="vendor_doc", ref="README.md:3-5"),
        Fact("The README documents supplying a camera calibration file to publish camera_info.",
             source="vendor_doc", ref="README.md:10"),
    ]
    #: The published size follows the chosen video or image file; the upstream
    #: node declares no fixed geometry.  This is the fidelity of the ROS-free
    #: controlled peer, not the upstream simulator's timing.
    fidelity = {
        "engine": "analytic:ROS-free controlled peer (no video decode, no ROS graph)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven test peer with fixed placeholder packets; it does not replay captured "
                     "traffic, advance a video, or model the upstream timer",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake answers only the declared /image/image_raw subscription with a 4x2 placeholder BGR8 "
            "packet; it runs no ROS node, OpenCV, video decoder or camera",
            "the upstream node publishes the decoded frame's own dimensions and declares no fixed resolution; "
            "the placeholder frame is smaller than a real video frame",
            "the fake does not pace frames at the source video's FPS; the upstream interval is 1.0/video_fps "
            "(camera_simulator/camera_simulator.py:90-93)",
            "the optional CameraInfo/calibration stream and the unused get_compressed_msg helper are outside "
            "this profile's selected image scope",
            "transport, pixel and artifact bounds are client host policies, not camera resolution limits",
            "in image-folder mode the node publishes every image once inside its constructor, before rclpy.spin "
            "and without a timer, so a rosbridge subscription opened later receives no frame, and in video mode "
            "without --loop the node exits at the end of the file; captures then fail MHS.DEVICE.NOT_READY (a "
            "probe with the topic silent failed after 2 s), so only a looping video gives repeatable captures",
            "a capture waits for a fresh frame only up to the binding's default 2 s timeout, not the action's "
            "10 s max_duration_ms, so a video slower than 0.5 fps fails NOT_READY",
        ],
    }

    #: The fixed source default is an absolute ROS 2 topic.  A deployment that
    #: overrides image_topic needs an explicitly reviewed remapping; caller
    #: arguments cannot select a topic, type or camera.
    commands = {
        "cap.sensing.image.v1": {
            "cameras": {
                "color": {
                    "topic": "/image/image_raw",
                    "type": "sensor_msgs/msg/Image",
                    "operation": "subscribe",
                    # Client conversion bounds: 8 MiB of raw image bytes and
                    # 4,194,304 pixels, not camera limits.
                    "image": {"max_input_bytes": 8 * 1024 * 1024,
                              "max_pixels": 4 * 1024 * 1024},
                    "source_ref": _IMAGE_TOPIC_REF,
                    "type_ref": _IMAGE_TYPE_REF,
                },
            },
        },
    }
    actions = {
        "cap.sensing.image.v1": Action(
            name="capture_image",
            max_duration_ms=10000,
            cancellable=True,
            description="Capture one complete frame and its exact ROS 2 header from the fixed color stream; "
                        "no freshness, calibration or codec claim",
        ),
    }
