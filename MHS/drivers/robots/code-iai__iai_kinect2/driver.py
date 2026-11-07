"""OpenMHS rosbridge driver for the iai_kinect2 Kinect v2 bridge.

The upstream ``kinect2_bridge`` is a C++ ROS 1 node that bridges
libfreenect2 to ROS.  This package is a configuration-only ``RosDriver``
over rosbridge: it declares no Python native class and never imports,
launches or runs the node.  The primary interface is the fixed
``sensor_msgs/Image`` SD stream family.  Three complete planes are exposed
through the image selector:

* ``color``: ``/kinect2/sd/image_color_rect`` (BGR8, 512x424)
* ``depth``: ``/kinect2/sd/image_depth_rect`` (16UC1, 512x424)
* ``ir``: ``/kinect2/sd/image_ir`` (16UC1, 512x424)

The bridge's raw SD depth and infrared images are 16-bit samples.  The
image artifact path preserves the samples losslessly but does not infer
depth units, calibration or a colormap.  The HD and QHD streams, the
``image_depth`` and ``image_ir_rect`` SD variants, compressed transports,
mono streams, point clouds, TF and camera controls are outside this
package's selected scope.

Every endpoint, type and fact cites the pinned clone at
0e2c5f63134a076606bb79963406e1d47f2da651.  The fake transport is
ROS-free; no ROS graph, rosbridge connection, camera or hardware is
contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: README lists the absolute SD topics and their resolution.
_SD_TOPICS_REF = "kinect2_bridge/README.md:80"
_COLOR_TOPIC_REF = "kinect2_bridge/README.md:86"
_DEPTH_TOPIC_REF = "kinect2_bridge/README.md:90"
_IR_TOPIC_REF = "kinect2_bridge/README.md:92"
_INFO_TOPIC_REF = "kinect2_bridge/README.md:85"

#: initTopics advertises sensor_msgs::Image for every composed topic.
_IMAGE_PUBLISHER_REF = "kinect2_bridge/src/kinect2_bridge.cpp:513"

#: initTopics advertises the SD CameraInfo message on the same base name.
_INFO_PUBLISHER_REF = "kinect2_bridge/src/kinect2_bridge.cpp:518"

_COLOR_TOPIC = "/kinect2/sd/image_color_rect"
_DEPTH_TOPIC = "/kinect2/sd/image_depth_rect"
_IR_TOPIC = "/kinect2/sd/image_ir"
_INFO_TOPIC = "/kinect2/sd/camera_info"

_FRAME_ID = Field(
    "string",
    description="Optical frame id carried by the SD CameraInfo header",
)
_WIDTH = Field(
    "integer",
    description="SD image width in pixels reported by CameraInfo",
)
_HEIGHT = Field(
    "integer",
    description="SD image height in pixels reported by CameraInfo",
)


class IaiKinect2(RosDriver):
    device_id = "kinect2"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeIaiKinect2"}
    tags = ["ros", "ros1", "camera", "depth", "infrared", "kinect2", "image"]
    display_name = "Kinect v2 depth camera (iai_kinect2)"
    vendor = "code-iai"
    model = "Kinect v2"
    resource_id = "camera"
    #: A raw 512x424 BGR8 frame is about 636 KiB before base64 and JSON
    #: expansion.  This is a local rosbridge message budget, not a camera
    #: resolution limit.
    max_message_bytes = 4 * 1024 * 1024
    facts = [
        Fact("The bridge README describes the node as a bridge between libfreenect2 and ROS.",
             source="vendor_doc", ref="kinect2_bridge/README.md:11"),
        Fact("initialize reads the private base_name parameter with std::string(K2_DEFAULT_NS) as its default.",
             source="upstream_code", ref="kinect2_bridge/src/kinect2_bridge.cpp:247"),
        Fact("K2_DEFAULT_NS is the literal \"kinect2\".",
             source="upstream_code",
             ref="kinect2_bridge/include/kinect2_bridge/kinect2_definitions.h:24"),
        Fact("The topic macros define the /sd group and the /image_color, /image_depth, /image_ir, _rect and "
             "/camera_info suffixes.",
             source="upstream_code",
             ref="kinect2_bridge/include/kinect2_bridge/kinect2_definitions.h:32-41"),
        Fact("initTopics composes the SD color-rectified, depth-rectified and raw IR topic names from those macros.",
             source="upstream_code", ref="kinect2_bridge/src/kinect2_bridge.cpp:487-495"),
        Fact("initTopics advertises sensor_msgs::Image and sensor_msgs::CompressedImage publishers for every "
             "composed topic as base_name + topics[i].",
             source="upstream_code", ref="kinect2_bridge/src/kinect2_bridge.cpp:513-514"),
        Fact("initTopics advertises sensor_msgs::CameraInfo on base_name + K2_TOPIC_SD + K2_TOPIC_INFO.",
             source="upstream_code", ref=_INFO_PUBLISHER_REF),
        Fact("The constructor sets sizeColor to 1920x1080, sizeIr to 512x424 and sizeLowRes to half sizeColor.",
             source="upstream_code", ref="kinect2_bridge/src/kinect2_bridge.cpp:138"),
        Fact("The README states that the SD raw IR and depth topics carry 512x424 images.",
             source="vendor_doc", ref=_SD_TOPICS_REF),
        Fact("createImage assigns TYPE_16UC1 to the IR and depth images, BGR8 to the color images and TYPE_8UC1 "
             "to the mono images.",
             source="upstream_code", ref="kinect2_bridge/src/kinect2_bridge.cpp:1380-1402"),
        Fact("createImage copies the Mat height, width and step, sets is_bigendian to false and copies the byte "
             "payload into the ROS Image.",
             source="upstream_code", ref="kinect2_bridge/src/kinect2_bridge.cpp:1407-1413"),
        Fact("The SD color-rectified image is produced by registration->apply into sizeIr buffers and converted "
             "from BGRA/RGBA to BGR.",
             source="upstream_code", ref="kinect2_bridge/src/kinect2_bridge.cpp:1171-1188"),
        Fact("The SD depth-rectified image is produced by remapping depthShifted at sizeIr.",
             source="upstream_code", ref="kinect2_bridge/src/kinect2_bridge.cpp:1208-1215"),
        Fact("createCameraInfo copies its size argument into CameraInfo height and width; infoIR is created with "
             "sizeIr.",
             source="upstream_code", ref="kinect2_bridge/src/kinect2_bridge.cpp:739-747"),
        Fact("publishImages assigns the frame id baseNameTF + K2_TF_IR_OPT_FRAME to the SD group, including the "
             "SD CameraInfo.",
             source="upstream_code", ref="kinect2_bridge/src/kinect2_bridge.cpp:1273-1279"),
        Fact("callbackStatus starts the device streams when a client subscribes and stops the device when no "
             "client remains.",
             source="upstream_code", ref="kinect2_bridge/src/kinect2_bridge.cpp:785-810"),
        Fact("The README states that images from the same frame share a timestamp and recommends ExactTime "
             "synchronization.",
             source="vendor_doc", ref="kinect2_bridge/README.md:102"),
        Fact("The README states that point clouds are only published when the launch file is used.",
             source="vendor_doc", ref="kinect2_bridge/README.md:101"),
    ]

    #: The SD CameraInfo geometry is a read-only observation; it is not an
    #: automatic image snapshot.  Image bytes only come from the explicit
    #: image capability.
    parameters = {
        "frame_id": _FRAME_ID,
        "width": _WIDTH,
        "height": _HEIGHT,
    }
    reads = {
        "frame_id": {
            "topic": _INFO_TOPIC,
            "type": "sensor_msgs/CameraInfo",
            "path": "header.frame_id",
            "source_ref": _INFO_TOPIC_REF,
            "type_ref": _INFO_PUBLISHER_REF,
        },
        "width": {
            "topic": _INFO_TOPIC,
            "type": "sensor_msgs/CameraInfo",
            "path": "width",
            "source_ref": _INFO_TOPIC_REF,
            "type_ref": _INFO_PUBLISHER_REF,
        },
        "height": {
            "topic": _INFO_TOPIC,
            "type": "sensor_msgs/CameraInfo",
            "path": "height",
            "source_ref": _INFO_TOPIC_REF,
            "type_ref": _INFO_PUBLISHER_REF,
        },
    }

    #: These are fixed subscriptions, so the RosDriver image selector
    #: replaces the catalogue input with a closed camera-name choice.  The
    #: byte/pixel bounds are client conversion bounds, not device limits.
    commands = {
        "cap.sensing.image.v1": {
            "cameras": {
                "color": {
                    "topic": _COLOR_TOPIC,
                    "type": "sensor_msgs/Image",
                    "operation": "subscribe",
                    "image": {"max_input_bytes": 2 * 1024 * 1024,
                              "max_pixels": 2 * 1024 * 1024},
                    "timeout_ms": 10000,
                    "source_ref": _COLOR_TOPIC_REF,
                    "type_ref": _IMAGE_PUBLISHER_REF,
                },
                "depth": {
                    "topic": _DEPTH_TOPIC,
                    "type": "sensor_msgs/Image",
                    "operation": "subscribe",
                    "image": {"max_input_bytes": 2 * 1024 * 1024,
                              "max_pixels": 2 * 1024 * 1024},
                    "timeout_ms": 10000,
                    "source_ref": _DEPTH_TOPIC_REF,
                    "type_ref": _IMAGE_PUBLISHER_REF,
                },
                "ir": {
                    "topic": _IR_TOPIC,
                    "type": "sensor_msgs/Image",
                    "operation": "subscribe",
                    "image": {"max_input_bytes": 2 * 1024 * 1024,
                              "max_pixels": 2 * 1024 * 1024},
                    "timeout_ms": 10000,
                    "source_ref": _IR_TOPIC_REF,
                    "type_ref": _IMAGE_PUBLISHER_REF,
                },
            },
        },
    }
    actions = {
        "cap.sensing.image.v1": Action(
            name="capture_image",
            max_duration_ms=20000,
            description="Capture one complete image from the selected fixed Kinect v2 SD stream; "
                        "no depth unit, calibration or synchronization claim",
        ),
    }
