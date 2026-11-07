"""Complete primary image and calibration observations from ros2_usb_camera.

The upstream node is a C++ ROS 2 node.  This package uses a finite ``RosDriver`` profile over rosbridge, plus a pure
CameraInfo wire-shape check; it declares no Python native class. The fixed
root-namespace profile observes /image and /camera_info. Every BGR8 pixel and
the Image's own ROS2 header are retained by the SDK artifact path. Complete
CameraInfo has its own header; separate captures are not a synchronized pair.
The original frame-id capability/resource remain available. Startup settings,
external compressed republishers and physical calibration are not controlled.

Every endpoint, type and fact cites the pinned clone at
146c5911ebcc5539eb8550e02763abe1fdfa8d05.  The fake transport is ROS-free;
no ROS graph or camera hardware is contacted.
"""

from mhs.driver import Action, DriverFailed, Fact, Field, RosDriver
from mhs.schema import validate

#: README names the absolute /camera_info topic.  It is documentation text.
_CAMERA_INFO_REF = "README.md:15"

#: The node constructs the sensor_msgs::msg::CameraInfo message on these lines.
_CAMERA_INFO_TYPE_REF = "src/usb_camera_driver.cpp:131-132"

_FRAME_ID = Field(
    "string",
    description="Transform frame id carried by the CameraInfo header",
)

# These are protocol/host-storage constraints, not camera safety limits.
_HEADER = Field("object", properties={
    "stamp": Field("object", properties={"sec": Field("integer"), "nanosec": Field("integer")}),
    "frame_id": Field("string", max_length=256, pattern=r"^[^\x00-\x1f\x7f]*$"),
})
_ROI = Field("object", properties={
    **{name: Field("integer") for name in ("x_offset", "y_offset", "height", "width")},
    "do_rectify": Field("boolean"),
})
_CAMERA_INFO = Field("object", properties={
    "header": _HEADER,
    "height": Field("integer"), "width": Field("integer"),
    "distortion_model": Field("string", max_length=128),
    "d": Field("array", items=Field("number"), max_items=64),
    "k": Field("array", items=Field("number"), length=9),
    "r": Field("array", items=Field("number"), length=9),
    "p": Field("array", items=Field("number"), length=12),
    "binning_x": Field("integer"), "binning_y": Field("integer"), "roi": _ROI,
})
_CALIBRATION_CAP = "x-cap.klintan.camera_calibration.v1"


def _validate_camera_info(info):
    """Validate integer wire ranges without changing calibration or headers.

    Field schemas cover complete shape/types/array lengths. These additional
    bounds are the ROS2 message integer representation, not physical limits.
    """
    if validate(info, _CAMERA_INFO.to_schema()):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "CameraInfo does not match the complete bounded wire shape")
    values = [(info[name], 0, 2**32-1) for name in ("height", "width", "binning_x", "binning_y")]
    values += [(info["roi"][name], 0, 2**32-1) for name in ("x_offset", "y_offset", "height", "width")]
    values += [(info["header"]["stamp"]["sec"], -(2**31), 2**31-1),
               (info["header"]["stamp"]["nanosec"], 0, 999_999_999)]
    if any(type(value) is not int or not low <= value <= high for value, low, high in values):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "CameraInfo integer field is outside its ROS2 wire range")
    if len(info["header"]["frame_id"].encode("utf-8")) > 256:
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "CameraInfo frame id exceeds the bounded UTF-8 profile")


class Ros2UsbCamera(RosDriver):
    device_id = "usb_camera"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R0"
    ros_version = 2
    # Explicit transport budget for a full default 1280x720 BGR8 JSON sample.
    # This host policy is not a manufacturer maximum resolution claim.
    max_message_bytes = 16 * 1024 * 1024
    backends = {"fake": ".fake:FakeRos2UsbCamera"}
    tags = ["ros", "ros2", "camera", "camera-info", "image", "calibration", "frame"]
    display_name = "ROS 2 USB camera images and calibration"
    vendor = "klintan"
    resource_id = "camera"
    facts = [
        Fact("README.md documents /camera_info as the topic for camera info.",
             source="vendor_doc", ref="README.md:15"),
        Fact("The node declares a configurable frame_id parameter with the literal default "
             "'camera'; a deployment may set a different frame name.",
             source="upstream_code", ref="src/usb_camera_driver.cpp:37"),
        Fact("The node's CameraInfo message type is sensor_msgs::msg::CameraInfo, constructed "
             "from camera_info_manager::CameraInfoManager::getCameraInfo().",
             source="upstream_code", ref="src/usb_camera_driver.cpp:131-132"),
        Fact("The source includes sensor_msgs/msg/camera_info.hpp for the CameraInfo message.",
             source="upstream_code", ref="include/usb_camera_driver.hpp:33"),
        Fact("ImageCallback takes the node clock's current time before stamping the messages.",
             source="upstream_code", ref="src/usb_camera_driver.cpp:134"),
        Fact("ImageCallback assigns that timestamp and the configured frame_id value to the "
             "CameraInfo header.",
             source="upstream_code", ref="src/usb_camera_driver.cpp:139-140"),
        Fact("The node creates an image_transport camera publisher on the relative 'image' base "
             "topic.",
             source="upstream_code", ref="src/usb_camera_driver.cpp:46"),
        Fact("ImageCallback enters its publish branch only when the captured frame is non-empty "
             "and the fps interval has elapsed.",
             source="upstream_code", ref="src/usb_camera_driver.cpp:112-113"),
        Fact("The publish call sends the image and CameraInfo pair.",
             source="upstream_code", ref="src/usb_camera_driver.cpp:142"),
        Fact("The node launch file starts usb_camera_driver_node in the '/camera' namespace.",
             source="upstream_code", ref="launch/usb_camera_node.launch.py:39-40"),
        Fact("The component launch file defines NAMESPACE = '/camera' and uses it for the "
             "container.",
             source="upstream_code", ref="launch/usb_camera_component.launch.py:36-47"),
        Fact("ConvertFrameToMessage constructs sensor_msgs::msg::Image with complete bgr8 data, "
             "height, width, a false endian flag and a stride derived from the frame; non-contiguous "
             "frames are copied row by row.", source="upstream_code", ref="src/usb_camera_driver.cpp:63-103"),
        Fact("ImageCallback assigns the same current node-clock stamp and configured frame id to "
             "the image and CameraInfo before publishing them.", source="upstream_code",
             ref="src/usb_camera_driver.cpp:134-142"),
        Fact("Camera identity, image dimensions, fps and calibration file are read during node "
             "construction before VideoCapture and the timer are initialized.", source="upstream_code",
             ref="src/usb_camera_driver.cpp:37-60"),
        Fact("The source README describes compressed images as an external image_transport "
             "republisher requiring image_transport_plugins.", source="vendor_doc", ref="README.md:42-48"),
    ]

    #: The camera info header is a read-only observation.  The message path
    #: selects header.frame_id only; the separate calibration action exposes the complete message.
    parameters = {"frame_id": _FRAME_ID}
    reads = {
        "frame_id": {
            "topic": "/camera_info",
            "type": "sensor_msgs/msg/CameraInfo",
            "path": "header.frame_id",
            "source_ref": _CAMERA_INFO_REF,
            "type_ref": _CAMERA_INFO_TYPE_REF,
        },
    }
    commands = {
        "cap.sensing.image.v1": {
            "cameras": {"color": {
                "topic": "/image", "source_name": "image",
                "type": "sensor_msgs/msg/Image", "operation": "subscribe",
                "image": {"max_input_bytes": 8 * 1024 * 1024, "max_pixels": 4 * 1024 * 1024},
                "source_ref": "src/usb_camera_driver.cpp:46", "type_ref": "src/usb_camera_driver.cpp:63-66",
            }},
        },
        _CALIBRATION_CAP: {
            "topic": "/camera_info", "type": "sensor_msgs/msg/CameraInfo", "operation": "subscribe",
            "result": {"map": {"camera_info": "output.$"}},
            "source_ref": _CAMERA_INFO_REF, "type_ref": _CAMERA_INFO_TYPE_REF,
        },
        "x-cap.klintan.camera_info.v1": {
            "topic": "/camera_info",
            "type": "sensor_msgs/msg/CameraInfo",
            "operation": "subscribe",
            "path": "header.frame_id",
            "result": {"map": {"frame_id": "output.$"}},
            "source_ref": _CAMERA_INFO_REF,
            "type_ref": _CAMERA_INFO_TYPE_REF,
        },
    }
    actions = {
        "cap.sensing.image.v1": Action(
            name="capture", max_duration_ms=2000, cancellable=True,
            description="Capture every pixel and the exact Image header from the fixed color stream; no age claim",
        ),
        _CALIBRATION_CAP: Action(
            name="read_camera_calibration", verb="read", output={"camera_info": _CAMERA_INFO},
            description="Observe complete CameraInfo without inferring calibration validity or synchronization",
        ),
        "x-cap.klintan.camera_info.v1": Action(
            name="read_camera_info",
            verb="read",
            description="Read the frame id from one CameraInfo message on /camera_info",
            output={"frame_id": _FRAME_ID},
        ),
    }

    def call(self, capability_id, args=None, ctx=None):
        # Native I/O, ownership and artifact publication stay in the stock ROS
        # bridge. This pure post-read check adds exact CameraInfo wire ranges.
        result = super().call(capability_id, args, ctx)
        if capability_id == _CALIBRATION_CAP:
            _validate_camera_info(result["camera_info"])
        return result
