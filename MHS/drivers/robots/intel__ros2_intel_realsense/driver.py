"""OpenMHS rosbridge driver for gh.intel/ros2_intel_realsense.

The upstream ``realsense_ros2_camera`` is a C++ ROS 2 node for Intel
RealSense D400-series cameras.  This package is a configuration-only
``RosDriver`` over rosbridge: it declares no Python native class and never
imports, launches or runs the node.  The primary interface is the fixed
``sensor_msgs/msg/Image`` color stream on the relative topic
``camera/color/image_raw``; the constructor's default namespace makes it
``/camera/color/image_raw``.  Image bytes become a bounded local PNG artifact.

CameraInfo geometry for the same color stream is exposed as read-only resource
fields.  Depth, infrared and fisheye images, the PointCloud2 streams, IMU data,
TF and camera controls are not covered by this package.  The node publishes no
ROS service, so the camera is a passive R0 observation endpoint and the package
claims no stop or safe state.  Closing a subscription is not camera power-off.

Every endpoint, type and fact cites the pinned clone at
74efb28ba4c4c41d5aaf588c969372616d6f5928.  The fake transport is ROS-free; no
ROS graph, rosbridge connection, camera or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: The color publisher is created with this relative name; the upstream README
#: records the resolved absolute name and the sensor_msgs/msg/Image type.
_IMAGE_SOURCE_NAME = "camera/color/image_raw"
_IMAGE_TOPIC = "/camera/color/image_raw"
_IMAGE_SOURCE_REF = "realsense_ros2_camera/src/realsense_camera_node.cpp:408-410"
_IMAGE_TYPE_REF = "realsense_ros2_camera/src/realsense_camera_node.cpp:27"

#: CameraInfo is created on the relative sibling topic with queue depth 1.
_INFO_SOURCE_NAME = "camera/color/camera_info"
_INFO_TOPIC = "/camera/color/camera_info"
_INFO_SOURCE_REF = "realsense_ros2_camera/src/realsense_camera_node.cpp:411-412"
_INFO_TYPE_REF = "realsense_ros2_camera/src/realsense_camera_node.cpp:26"

#: publishFrame fills the image metadata and publishes CameraInfo then the image.
_PUBLISH_REF = "realsense_ros2_camera/src/realsense_camera_node.cpp:1295-1308"

#: The constructor maps the color stream to libRS RGB8 and ROS rgb8.
_ENCODING_REF = "realsense_ros2_camera/src/realsense_camera_node.cpp:144-146"

_FRAME_ID = Field(
    "string",
    description="Optical frame id carried by the color CameraInfo header",
)
_WIDTH = Field(
    "integer",
    description="Color image width in pixels reported by CameraInfo",
)
_HEIGHT = Field(
    "integer",
    description="Color image height in pixels reported by CameraInfo",
)


class RealSenseD400(RosDriver):
    device_id = "realsense"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeRos2IntelRealsense"}
    tags = ["ros", "ros2", "camera", "image", "realsense", "rgb", "depth"]
    display_name = "Intel RealSense D400 series camera"
    vendor = "Intel"
    resource_id = "camera"
    #: A base64 ROS Image frame is larger than its raw bytes.  This is a local
    #: transport budget for one bounded message, not a device resolution limit.
    max_message_bytes = 16 * 1024 * 1024
    facts = [
        Fact("The node class is RealSenseCameraNode and its constructor passes "
             "Node(\"RealSenseCameraNode\", ...) to rclcpp::Node.",
             source="upstream_code",
             ref="realsense_ros2_camera/src/realsense_camera_node.cpp:98-103"),
        Fact("The node includes sensor_msgs/msg/image.hpp.",
             source="upstream_code", ref=_IMAGE_TYPE_REF),
        Fact("publishFrame assigns a sensor_msgs::msg::Image::SharedPtr from "
             "cv_bridge::CvImage(...).toImageMsg().",
             source="upstream_code",
             ref="realsense_ros2_camera/src/realsense_camera_node.cpp:1295-1296"),
        Fact("The constructor maps the color stream to RS2_FORMAT_RGB8 and the ROS "
             "encoding to sensor_msgs::image_encodings::RGB8.",
             source="upstream_code", ref=_ENCODING_REF),
        Fact("getParameters reads enable_color with ENABLE_COLOR as its default.",
             source="upstream_code",
             ref="realsense_ros2_camera/src/realsense_camera_node.cpp:230"),
        Fact("ENABLE_COLOR is true.",
             source="upstream_code",
             ref="realsense_ros2_camera/include/realsense_ros2_camera/constants.hpp:67"),
        Fact("setupPublishers creates the color image_transport publisher on the "
             "relative topic camera/color/image_raw inside the enable-color branch.",
             source="upstream_code", ref=_IMAGE_SOURCE_REF),
        Fact("setupPublishers creates a sensor_msgs::msg::CameraInfo publisher on "
             "the relative topic camera/color/camera_info with queue depth 1.",
             source="upstream_code", ref=_INFO_SOURCE_REF),
        Fact("publishFrame sets width, height, is_bigendian=false and "
             "step=width*bpp, stamps the header, then publishes CameraInfo and the image.",
             source="upstream_code", ref=_PUBLISH_REF),
        Fact("The README lists the Color image topic as /camera/color/image_raw with "
             "a sensor_msgs/msg/Image message link.",
             source="vendor_doc", ref="README.md:82-85"),
        Fact("getParameters reads color_width and color_height with COLOR_WIDTH and "
             "COLOR_HEIGHT as defaults.",
             source="upstream_code",
             ref="realsense_ros2_camera/src/realsense_camera_node.cpp:227-228"),
        Fact("COLOR_WIDTH is 640 and COLOR_HEIGHT is 480; these are ROS parameter "
             "defaults, not device bounds.",
             source="upstream_code",
             ref="realsense_ros2_camera/include/realsense_ros2_camera/constants.hpp:48-49"),
        Fact("updateStreamCalibData copies the intrinsic width and height and the "
             "configured optical frame id into CameraInfo.",
             source="upstream_code",
             ref="realsense_ros2_camera/src/realsense_camera_node.cpp:717-719"),
        Fact("The constructor maps the depth stream to "
             "sensor_msgs::image_encodings::TYPE_16UC1.",
             source="upstream_code",
             ref="realsense_ros2_camera/src/realsense_camera_node.cpp:125"),
        Fact("setupPublishers creates the depth image transporter on the relative "
             "topic camera/depth/image_rect_raw inside the enable-depth branch.",
             source="upstream_code",
             ref="realsense_ros2_camera/src/realsense_camera_node.cpp:370-372"),
        Fact("The constructor maps the infra1 stream and the infra2 stream to "
             "sensor_msgs::image_encodings::TYPE_8UC1.",
             source="upstream_code",
             ref="realsense_ros2_camera/src/realsense_camera_node.cpp:128-141"),
        Fact("setupPublishers creates the infra1 image transporter on the relative "
             "topic camera/infra1/image_rect_raw.",
             source="upstream_code",
             ref="realsense_ros2_camera/src/realsense_camera_node.cpp:394-396"),
        Fact("setupPublishers creates the aligned point-cloud publisher on the "
             "relative topic camera/aligned_depth_to_color/color/points when aligned "
             "point cloud and aligned depth are enabled.",
             source="upstream_code",
             ref="realsense_ros2_camera/src/realsense_camera_node.cpp:388-390"),
        Fact("The signalHandler function stops and closes every queried sensor and "
             "calls rclcpp::shutdown; it is a process signal handler body, not a ROS service.",
             source="upstream_code",
             ref="realsense_ros2_camera/src/realsense_camera_node.cpp:77-86"),
        Fact("The constructor registers signalHandler for SIGINT.",
             source="upstream_code",
             ref="realsense_ros2_camera/src/realsense_camera_node.cpp:113"),
        Fact("The README states that Intel ceased maintenance and no longer accepts "
             "patches for the project.",
             source="vendor_doc", ref="README.md:1-9"),
        Fact("The README's known issues state that the node provides no dynamic "
             "reconfigure support for camera properties or presets.",
             source="vendor_doc", ref="README.md:114-116"),
    ]

    #: CameraInfo geometry for the color stream is a read-only observation; it is
    #: not an automatic image snapshot.  Image bytes only come from the explicit
    #: fixed-stream capability.
    parameters = {
        "frame_id": _FRAME_ID,
        "width": _WIDTH,
        "height": _HEIGHT,
    }
    reads = {
        "frame_id": {
            "topic": _INFO_TOPIC,
            "type": "sensor_msgs/msg/CameraInfo",
            "path": "header.frame_id",
            "source_name": _INFO_SOURCE_NAME,
            "source_ref": _INFO_SOURCE_REF,
            "type_ref": _INFO_TYPE_REF,
        },
        "width": {
            "topic": _INFO_TOPIC,
            "type": "sensor_msgs/msg/CameraInfo",
            "path": "width",
            "source_name": _INFO_SOURCE_NAME,
            "source_ref": _INFO_SOURCE_REF,
            "type_ref": _INFO_TYPE_REF,
        },
        "height": {
            "topic": _INFO_TOPIC,
            "type": "sensor_msgs/msg/CameraInfo",
            "path": "height",
            "source_name": _INFO_SOURCE_NAME,
            "source_ref": _INFO_SOURCE_REF,
            "type_ref": _INFO_TYPE_REF,
        },
    }

    #: The fixed subscription accepts no camera controls; RosDriver replaces the
    #: catalogue class's input schema with a closed, intentionally empty one.
    commands = {
        "cap.sensing.image.v1": {
            "topic": _IMAGE_TOPIC,
            "type": "sensor_msgs/msg/Image",
            "operation": "subscribe",
            "source_name": _IMAGE_SOURCE_NAME,
            "source_ref": _IMAGE_SOURCE_REF,
            "type_ref": _IMAGE_TYPE_REF,
            # Client conversion bounds: 16 MiB of decoded RGB input and at most
            # 4 Mi pixels.  These are SDK execution bounds, not camera limits.
            "image": {
                "max_input_bytes": 16 * 1024 * 1024,
                "max_pixels": 4 * 1024 * 1024,
            },
            "timeout_ms": 10000,
        },
    }
    actions = {
        "cap.sensing.image.v1": Action(
            name="capture_image",
            description="Capture one RGB frame from the fixed /camera/color/image_raw stream",
        ),
    }
