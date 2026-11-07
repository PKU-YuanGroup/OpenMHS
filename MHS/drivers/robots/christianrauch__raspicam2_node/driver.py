"""OpenMHS rosbridge driver for the Raspberry Pi camera node gh.christianrauch/raspicam2_node.

The upstream ``RasPiCamPublisher`` is a C++ ROS 2 component.  This package is a
configuration-only ``RosDriver`` over rosbridge: it declares no Python native
class and never imports or starts the node.  The primary interface is the
node's unconditional ``sensor_msgs/msg/CompressedImage`` stream on the
relative topic ``image/compressed``.  The node's shipped parameter file
selects the compressed transport, and the encoded callback sets
``format`` to ``"jpeg"``; the package binds that fixed JPEG stream as
``cap.sensing.image.v1`` and returns a bounded local image artifact.

CameraInfo geometry is exposed as read-only resource fields from
``image/camera_info``.  The node also publishes a raw ``sensor_msgs/msg/Image``
only when ``image_transport == "raw"``, but its callback leaves
``Image.step`` unset; that malformed raw message is not used.  Camera
controls, ROS parameter writes and ``set_camera_info`` are not exposed.

Every endpoint, type and fact cites the pinned clone at
749689a967bfc427e74520dfd107f30f5c50bf0e.  The fake transport is ROS-free; no
ROS graph or camera hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: The constructor names the node "raspicam2" in the "camera" namespace.
_NODE_REF = "src/RasPiCamPublisherNode.cpp:4"

#: The compressed publisher is created unconditionally with this relative
#: topic and message type.
_IMAGE_REF = "src/RasPiCamPublisherNode.cpp:124"

#: The CameraInfo publisher is created on this relative topic and type.
_INFO_REF = "src/RasPiCamPublisherNode.cpp:125"

#: The compressed callback stamps the header, sets format "jpeg" and publishes.
_IMAGE_PUBLISH_REF = "src/RasPiCamPublisherNode.cpp:160-170"

_FRAME_ID = Field(
    "string",
    description="Transform frame id carried by the CameraInfo header",
)
_WIDTH = Field(
    "integer",
    description="Image width in pixels reported by the CameraInfo message",
)
_HEIGHT = Field(
    "integer",
    description="Image height in pixels reported by the CameraInfo message",
)


class Raspicam2Node(RosDriver):
    device_id = "raspicam2"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeRaspicam2Node"}
    tags = ["ros", "ros2", "camera", "image", "jpeg", "raspberry-pi"]
    display_name = "Raspberry Pi Camera (raspicam2)"
    vendor = "Christian Rauch"
    resource_id = "camera"
    # A larger encoded JPEG still has to fit one bounded rosbridge frame; this
    # is a client execution bound, not a device limit.
    max_message_bytes = 16 * 1024 * 1024
    facts = [
        Fact("The node constructor names the node 'raspicam2' in the 'camera' namespace.",
             source="upstream_code", ref=_NODE_REF),
        Fact("The constructor always creates a sensor_msgs::msg::CompressedImage publisher on the "
             "relative topic 'image/compressed' with QoS depth 1.",
             source="upstream_code", ref=_IMAGE_REF),
        Fact("The constructor creates a sensor_msgs::msg::CameraInfo publisher on the relative "
             "topic 'image/camera_info' with QoS depth 1.",
             source="upstream_code", ref=_INFO_REF),
        Fact("The compressed-image callback stamps a header, sets format to 'jpeg', and publishes "
             "the encoded bytes on the compressed-image publisher.",
             source="upstream_code", ref=_IMAGE_PUBLISH_REF),
        Fact("The compressed-image callback also stamps and publishes the CameraInfo message "
             "after each compressed frame.",
             source="upstream_code", ref="src/RasPiCamPublisherNode.cpp:172-174"),
        Fact("CameraInfo width and height are copied from the configured width and height ROS "
             "parameters before capture starts.",
             source="upstream_code", ref="src/RasPiCamPublisherNode.cpp:64-65"),
        Fact("The constructor seeds the width, height, fps and JPEG quality parameters with "
             "320, 240, 90 and 80; these are ROS parameter defaults, not device bounds.",
             source="upstream_code", ref="src/RasPiCamPublisherNode.cpp:46-49"),
        Fact("The shipped parameter file selects image_transport 'compressed', width 320, height "
             "240, fps 90 and JPEG quality 80 as an example deployment configuration.",
             source="upstream_code", ref="cfg/params.yaml:4-8"),
        Fact("The constructor defaults image_transport to 'raw' and creates the raw "
             "sensor_msgs::msg::Image publisher only when that parameter equals 'raw'.",
             source="upstream_code", ref="src/RasPiCamPublisherNode.cpp:76-84"),
        Fact("The raw Image callback sets the rgb8 encoding, dimensions and byte data but never "
             "sets Image.step; the package does not use that malformed raw publication.",
             source="upstream_code", ref="src/RasPiCamPublisherNode.cpp:142-157"),
        Fact("The set_camera_info service copies the request camera_info into the member and "
             "returns success=true; it performs no optical calibration or hardware control.",
             source="upstream_code", ref="src/RasPiCamPublisherNode.cpp:179-184"),
        Fact("The constructor calls init_cam and start_capture, and the destructor calls "
             "close_cam.",
             source="upstream_code", ref="src/RasPiCamPublisherNode.cpp:130-140"),
        Fact("README marks the package deprecated because the MMAL rawcam component is legacy and "
             "points deployments to camera_ros instead.",
             source="vendor_doc", ref="README.md:2-4"),
        Fact("The build searches for MMAL, mmal_core, mmal_util, mmal_vc_client, vcos and "
             "bcm_host libraries under /opt/vc and includes /opt/vc/include.",
             source="upstream_code", ref="CMakeLists.txt:28-35"),
    ]

    #: CameraInfo geometry is a read-only observation.  It is not an automatic
    #: image snapshot; image bytes only come from the explicit capability.
    parameters = {
        "frame_id": _FRAME_ID,
        "width": _WIDTH,
        "height": _HEIGHT,
    }
    reads = {
        "frame_id": {
            "topic": "/camera/image/camera_info",
            "type": "sensor_msgs/msg/CameraInfo",
            "path": "header.frame_id",
            "source_name": "image/camera_info",
            "source_ref": _INFO_REF,
        },
        "width": {
            "topic": "/camera/image/camera_info",
            "type": "sensor_msgs/msg/CameraInfo",
            "path": "width",
            "source_name": "image/camera_info",
            "source_ref": _INFO_REF,
        },
        "height": {
            "topic": "/camera/image/camera_info",
            "type": "sensor_msgs/msg/CameraInfo",
            "path": "height",
            "source_name": "image/camera_info",
            "source_ref": _INFO_REF,
        },
    }

    #: The fixed JPEG stream accepts no camera controls; RosDriver replaces the
    #: catalogue class's input schema with a closed, intentionally empty one.
    commands = {
        "cap.sensing.image.v1": {
            "topic": "/camera/image/compressed",
            "type": "sensor_msgs/msg/CompressedImage",
            "operation": "subscribe",
            "source_name": "image/compressed",
            "source_ref": _IMAGE_REF,
            "image": {
                # Client conversion bounds: 8 MiB of encoded input, at most the
                # SDK's 16-Mi-pixel ceiling.  These are not device limits.
                "max_input_bytes": 8 * 1024 * 1024,
                "max_pixels": 16 * 1024 * 1024,
            },
            "timeout_ms": 10000,
        },
    }
    actions = {
        "cap.sensing.image.v1": Action(
            name="capture_image",
            description="Capture one JPEG frame from the fixed /camera/image/compressed stream",
        ),
    }
