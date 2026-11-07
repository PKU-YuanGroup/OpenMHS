"""OpenMHS rosbridge driver for gh.realsenseai/realsense-ros: default images, calibration and opt-in cloud.

The upstream realsense2_camera node is a C++ ROS 2 camera driver (source version 4.59.1).  This package is a
configuration-only ``RosDriver`` over rosbridge; it declares no Python native class and never imports the upstream
code.

Profile: the launch file's default node ``/camera/camera`` with its default streams (color RGB8, depth Z16).  The
main resource ``camera`` (``sensor.camera``) serves every pixel of the color ``rgb8`` and depth ``16UC1`` images
through one ``cap.sensing.image.v1`` binding with a finite two-source selector (each artifact keeps its exact ROS 2
header), the complete CameraInfo and Metadata messages of both streams, the DeviceInfo identity service and the
original geometry/metadata summaries.  The second resource ``pointcloud`` (``sensor.depth``) serves the complete
PointCloud2 of ``~/depth/color/points``, which the node publishes only after its operator sets ``pointcloud.enable``
(default false).  Both resources are one device: one rosbridge transport, one e-stop latch and one lifecycle
(package composition, ``extra_resources``).

Independent subscriptions never form a synchronized RGB-D pair; no producer age, calibration validity, deployment
graph, QoS compatibility, model, firmware or native fidelity is claimed.  ``RESULT.json`` names what is NOT COVERED.
Every endpoint, type and fact cites the pinned clone at 7a87097c499e3b0b69518d54a8e7a9ac1924e87c.  The fake
transport is ROS-free; no ROS graph, camera, rosbridge connection or hardware is contacted.
"""

from mhs.driver import Action, DriverFailed, Fact, Field, RosDriver
from mhs.schema import validate

#: README's default-behavior example names the resolved node and endpoints.
_COLOR_INFO = "/camera/camera/color/camera_info"
_COLOR_METADATA = "/camera/camera/color/metadata"
_DEVICE_INFO = "/camera/camera/device_info"
_COLOR_IMAGE = "/camera/camera/color/image_raw"
_DEPTH_IMAGE = "/camera/camera/depth/image_rect_raw"
_DEPTH_INFO = "/camera/camera/depth/camera_info"
_DEPTH_METADATA = "/camera/camera/depth/metadata"
_POINTS = "/camera/camera/depth/color/points"

#: The node builds every stream's camera_info topic as ~/<stream>/camera_info.
_CAMERA_INFO_TOPIC_REF = "README.md:631"
_CAMERA_INFO_SOURCE_NAME = _COLOR_INFO
_CAMERA_INFO_TYPE_REF = "realsense2_camera/src/rs_node_setup.cpp:309-310"

#: The metadata topic is built as ~/<stream>/metadata.
_METADATA_TOPIC_REF = "README.md:633"
_METADATA_TYPE_REF = "realsense2_camera/src/rs_node_setup.cpp:368-370"

#: The node advertises the private service with the DeviceInfo type.
_DEVICE_INFO_REF = "realsense2_camera/src/rs_node_setup.cpp:573-574"

#: README's default topic list shows each absolute endpoint of the default profile on its own line.
_IMAGE_TYPE_REF = "realsense2_camera/src/image_publisher.cpp:24"
_POINTS_REF = "realsense2_camera/src/pointcloud_filter.cpp:72"

#: The new capabilities (complete messages; the three original ones stay unchanged).
IMAGE = "cap.sensing.image.v1"
POINT_CLOUD = "cap.sensing.point_cloud.v1"
COLOR_CAMERA_INFO = "x-cap.realsenseai.color_camera_info.v1"
DEPTH_CAMERA_INFO = "x-cap.realsenseai.depth_camera_info.v1"
COLOR_METADATA = "x-cap.realsenseai.color_metadata.v1"
DEPTH_METADATA = "x-cap.realsenseai.depth_metadata.v1"
_CAMERA_INFO_CAPS = (COLOR_CAMERA_INFO, DEPTH_CAMERA_INFO)
_METADATA_CAPS = (COLOR_METADATA, DEPTH_METADATA)

# Host budgets, not device limits: one full image or cloud message must fit the rosbridge frame (base64 data) and
# the conversion budget.  A larger deployment profile is refused whole, never truncated or resized.
_IMAGE_BUDGET = {"max_input_bytes": 8 * 1024 * 1024, "max_pixels": 4 * 1024 * 1024}
_CLOUD_BUDGET = {"max_input_bytes": 8 * 1024 * 1024, "max_points": 1_048_576, "max_fields": 64}

_WIDTH = Field("integer", description="CameraInfo image width in pixels")
_HEIGHT = Field("integer", description="CameraInfo image height in pixels")
_FRAME_ID = Field("string", description="Transform frame id carried by the CameraInfo header")
_DISTORTION_MODEL = Field("string", description="Distortion model named by the CameraInfo message")
_BINNING_X = Field("integer", description="Horizontal binning factor reported by CameraInfo")
_BINNING_Y = Field("integer", description="Vertical binning factor reported by CameraInfo")

_DEVICE_NAME = Field("string", description="Device name reported by the device_info service")
_SERIAL_NUMBER = Field("string", description="Device serial number reported by the device_info service")
_FIRMWARE_VERSION = Field("string", description="Firmware version reported by the device_info service")
_USB_TYPE = Field("string", description="USB type descriptor reported by the device_info service")
_FIRMWARE_UPDATE_ID = Field("string", description="Firmware update id reported by the device_info service")
_SENSORS = Field("string", description="Comma-separated ROS sensor names reported by the device_info service")
_PHYSICAL_PORT = Field("string", description="Physical port reported by the device_info service")

_METADATA_JSON = Field("string", description="Camera frame metadata carried as JSON text")

# Complete ROS 2 message shapes.  These are protocol/host constraints, not camera limits.
_HEADER = Field("object", properties={
    "stamp": Field("object", properties={"sec": Field("integer"), "nanosec": Field("integer")}),
    "frame_id": Field("string", max_length=256, pattern=r"^[^\x00-\x1f\x7f]*$"),
})
_ROI = Field("object", properties={
    **{name: Field("integer") for name in ("x_offset", "y_offset", "height", "width")},
    "do_rectify": Field("boolean"),
})
_CAMERA_INFO = Field("object", description="The complete CameraInfo message, as received", properties={
    "header": _HEADER,
    "height": Field("integer"), "width": Field("integer"),
    "distortion_model": Field("string", max_length=128),
    "d": Field("array", items=Field("number"), max_items=64),
    "k": Field("array", items=Field("number"), length=9),
    "r": Field("array", items=Field("number"), length=9),
    "p": Field("array", items=Field("number"), length=12),
    "binning_x": Field("integer"), "binning_y": Field("integer"), "roi": _ROI,
})
_METADATA = Field("object", description="The complete Metadata message: its header and the exact JSON text",
                  properties={"header": _HEADER, "json_data": Field("string")})


def _wire_ranges(values):
    if any(type(value) is not int or not low <= value <= high for value, low, high in values):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "a ROS 2 integer field is outside its wire range")


def _header_ranges(header):
    if len(header["frame_id"].encode("utf-8")) > 256:
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "frame id exceeds the bounded UTF-8 profile")
    return [(header["stamp"]["sec"], -(2**31), 2**31 - 1), (header["stamp"]["nanosec"], 0, 999_999_999)]


def _validate_camera_info(info):
    """Validate the complete shape and integer wire ranges without changing calibration or headers."""
    if validate(info, _CAMERA_INFO.to_schema()):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "CameraInfo does not match the complete bounded wire shape")
    values = [(info[name], 0, 2**32 - 1) for name in ("height", "width", "binning_x", "binning_y")]
    values += [(info["roi"][name], 0, 2**32 - 1) for name in ("x_offset", "y_offset", "height", "width")]
    _wire_ranges(values + _header_ranges(info["header"]))


def _validate_metadata(message):
    """The complete Metadata message: a valid header and the JSON text exactly as received (never parsed here)."""
    if validate(message, _METADATA.to_schema()):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "Metadata does not match the complete bounded wire shape")
    _wire_ranges(_header_ranges(message["header"]))


class RealsenseRos(RosDriver):
    device_id = "realsense"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R0"
    ros_version = 2
    # Explicit transport budget for one full image or cloud message as rosbridge JSON (base64 data).  This host
    # policy is not a resolution or point-count claim about any RealSense model.
    max_message_bytes = 16 * 1024 * 1024
    backends = {"fake": ".fake:FakeRealsenseRos"}
    tags = ["ros", "ros2", "camera", "realsense", "camera-info", "metadata", "device-info", "image", "depth",
            "point-cloud"]
    display_name = "RealSense ROS 2 camera"
    vendor = "RealSense"
    resource_id = "camera"
    extra_resources = {"pointcloud": {"kind": "sensor.depth",
                                      "title": "Opt-in depth point cloud (pointcloud.enable)"}}
    facts = [
        Fact("The launch file declares the default camera_name 'camera' and camera_namespace 'camera'.",
             source="upstream_code", ref="realsense2_camera/launch/rs_launch.py:23-24"),
        Fact("README's default-behavior example lists node /camera/camera, topic "
             "/camera/camera/color/camera_info, and service /camera/camera/device_info.",
             source="vendor_doc", ref="README.md:379-404"),
        Fact("README lists /camera/camera/color/camera_info and /camera/camera/color/metadata among the "
             "published topics of the default node.",
             source="vendor_doc", ref="README.md:631-633"),
        Fact("The node constructs each stream's camera_info topic as ~/<stream_name>/camera_info.",
             source="upstream_code", ref="realsense2_camera/src/rs_node_setup.cpp:283"),
        Fact("The node creates a sensor_msgs::msg::CameraInfo publisher on that topic for non-SC streams.",
             source="upstream_code", ref="realsense2_camera/src/rs_node_setup.cpp:306-310"),
        Fact("The node creates the private ~/device_info service of type "
             "realsense2_camera_msgs::srv::DeviceInfo.",
             source="upstream_code", ref="realsense2_camera/src/rs_node_setup.cpp:573-574"),
        Fact("The DeviceInfo service response carries seven strings: device_name, serial_number, "
             "firmware_version, usb_type_descriptor, firmware_update_id, sensors and physical_port.",
             source="upstream_code", ref="realsense2_camera_msgs/srv/DeviceInfo.srv:2-8"),
        Fact("getDeviceInfo fills the response from the live device's name, serial number, firmware "
             "version, USB type descriptor, firmware update id, physical port and available ROS sensor "
             "names.",
             source="upstream_code", ref="realsense2_camera/src/rs_node_setup.cpp:640-657"),
        Fact("README documents device_info as retrieving the device serial number, firmware version and "
             "the other DeviceInfo fields.",
             source="vendor_doc", ref="README.md:877-880"),
        Fact("The node constructs each stream's metadata topic as ~/<stream_name>/metadata and publishes "
             "realsense2_camera_msgs::msg::Metadata there.",
             source="upstream_code", ref="realsense2_camera/src/rs_node_setup.cpp:368-370"),
        Fact("realsense2_camera_msgs/msg/Metadata carries a std_msgs/Header and a json_data string.",
             source="upstream_code", ref="realsense2_camera_msgs/msg/Metadata.msg:1-2"),
        Fact("README says the metadata messages store the camera's available metadata in JSON format.",
             source="vendor_doc", ref="README.md:805"),
        Fact("handleHWReset stops every available ROS sensor and calls _dev.hardware_reset(); it catches "
             "exceptions and only warns, and its std_srvs/Empty response carries no failure status.",
             source="upstream_code", ref="realsense2_camera/src/rs_node_setup.cpp:614-637"),
        # Default image acquisition (added by the model review; the facts above are the author's).
        Fact("The launch file enables the color stream by default with the RGB8 color format.",
             source="upstream_code", ref="realsense2_camera/launch/rs_launch.py:36-38"),
        Fact("The launch file enables the depth stream by default with the Z16 depth format; the infra, infra1 "
             "and infra2 streams default to false.",
             source="upstream_code", ref="realsense2_camera/launch/rs_launch.py:40-45"),
        Fact("README's default topic list shows /camera/camera/color/image_raw, /camera/camera/depth/camera_info, "
             "/camera/camera/depth/image_rect_raw and /camera/camera/depth/metadata.",
             source="vendor_doc", ref="README.md:387-393"),
        Fact("The node names each image topic ~/<stream_name>/image_raw, with image_rect_raw for the rectified "
             "depth stream.",
             source="upstream_code", ref="realsense2_camera/src/rs_node_setup.cpp:276-282"),
        Fact("The image publisher is a sensor_msgs::msg::Image publisher.",
             source="upstream_code", ref="realsense2_camera/src/image_publisher.cpp:24"),
        Fact("The node maps the Z16 format to the 16UC1 image encoding and RGB8 to rgb8.",
             source="upstream_code", ref="realsense2_camera/src/base_realsense_node.cpp:215-216"),
        Fact("Each image message gets the stream's optical frame id, the frame stamp, height, width, "
             "is_bigendian false and step = width * element size.",
             source="upstream_code", ref="realsense2_camera/src/base_realsense_node.cpp:1246-1251"),
        Fact("fix_depth_scale passes 16-bit depth samples through when the device depth scale is 0.001 m and "
             "otherwise rescales every sample to that unit.",
             source="upstream_code", ref="realsense2_camera/src/base_realsense_node.cpp:272-309"),
        Fact("Without stream intrinsics the node uses zeroed intrinsics; CameraInfo then gets the stream width, "
             "height and optical frame, K and P from fx, fy, ppx and ppy, an identity R and plumb_bob (5) or "
             "equidistant (4) distortion coefficients.",
             source="upstream_code", ref="realsense2_camera/src/base_realsense_node.cpp:800-859"),
        Fact("CameraInfo is stamped with the frame time and published only while it has subscribers.",
             source="upstream_code", ref="realsense2_camera/src/base_realsense_node.cpp:1397-1411"),
        Fact("Metadata JSON holds frame_number, clock_domain, frame_timestamp and every metadata key the frame "
             "supports; the message is published only while it has subscribers.",
             source="upstream_code", ref="realsense2_camera/src/base_realsense_node.cpp:1479-1508"),
        # Opt-in point cloud and outputs this package does not serve.
        Fact("The launch file defaults pointcloud.enable to false, pointcloud.stream_filter to 2, "
             "pointcloud.ordered_pc to false and align_depth.enable to false.",
             source="upstream_code", ref="realsense2_camera/launch/rs_launch.py:77-82"),
        Fact("README says the pointcloud filter adds the topic /camera/camera/depth/color/points.",
             source="vendor_doc", ref="README.md:827"),
        Fact("The pointcloud filter creates its sensor_msgs::msg::PointCloud2 publisher on ~/depth/color/points "
             "only while it is enabled.",
             source="upstream_code", ref="realsense2_camera/src/pointcloud_filter.cpp:67-79"),
        Fact("An unordered cloud gets width = valid point count, height 1 and is_dense true.",
             source="upstream_code", ref="realsense2_camera/src/pointcloud_filter.cpp:242-247"),
        Fact("The launch file defaults enable_rgbd, enable_gyro, enable_accel and enable_motion to false.",
             source="upstream_code", ref="realsense2_camera/launch/rs_launch.py:62-65"),
        Fact("IMU info is published once with the latched QoS profile, and the extrinsics publishers use the "
             "same latched profile.",
             source="upstream_code", ref="realsense2_camera/src/rs_node_setup.cpp:358-382"),
        Fact("The latched QoS profile is keep-last 1, reliable and transient-local.",
             source="upstream_code", ref="realsense2_camera/include/constants.h:94-105"),
    ]

    #: The read-only resource state is identity plus color-stream geometry.
    parameters = {
        "frame_id": _FRAME_ID,
        "width": _WIDTH,
        "height": _HEIGHT,
        "device_name": _DEVICE_NAME,
        "serial_number": _SERIAL_NUMBER,
        "firmware_version": _FIRMWARE_VERSION,
    }
    reads = {
        "frame_id": {
            "topic": _COLOR_INFO,
            "type": "sensor_msgs/msg/CameraInfo",
            "path": "header.frame_id",
            "source_name": _CAMERA_INFO_SOURCE_NAME,
            "source_ref": _CAMERA_INFO_TOPIC_REF,
            "type_ref": _CAMERA_INFO_TYPE_REF,
        },
        "width": {
            "topic": _COLOR_INFO,
            "type": "sensor_msgs/msg/CameraInfo",
            "path": "width",
            "source_name": _CAMERA_INFO_SOURCE_NAME,
            "source_ref": _CAMERA_INFO_TOPIC_REF,
            "type_ref": _CAMERA_INFO_TYPE_REF,
        },
        "height": {
            "topic": _COLOR_INFO,
            "type": "sensor_msgs/msg/CameraInfo",
            "path": "height",
            "source_name": _CAMERA_INFO_SOURCE_NAME,
            "source_ref": _CAMERA_INFO_TOPIC_REF,
            "type_ref": _CAMERA_INFO_TYPE_REF,
        },
        "device_name": {
            "service": _DEVICE_INFO,
            "type": "realsense2_camera_msgs/srv/DeviceInfo",
            "operation": "read",
            "path": "device_name",
            "source_name": "~/device_info",
            "source_ref": _DEVICE_INFO_REF,
        },
        "serial_number": {
            "service": _DEVICE_INFO,
            "type": "realsense2_camera_msgs/srv/DeviceInfo",
            "operation": "read",
            "path": "serial_number",
            "source_name": "~/device_info",
            "source_ref": _DEVICE_INFO_REF,
        },
        "firmware_version": {
            "service": _DEVICE_INFO,
            "type": "realsense2_camera_msgs/srv/DeviceInfo",
            "operation": "read",
            "path": "firmware_version",
            "source_name": "~/device_info",
            "source_ref": _DEVICE_INFO_REF,
        },
    }
    commands = {
        "x-cap.realsenseai.camera_info.v1": {
            "topic": _COLOR_INFO,
            "type": "sensor_msgs/msg/CameraInfo",
            "operation": "subscribe",
            "path": "$",
            "source_name": _CAMERA_INFO_SOURCE_NAME,
            "source_ref": _CAMERA_INFO_TOPIC_REF,
            "type_ref": _CAMERA_INFO_TYPE_REF,
            "result": {"map": {
                "width": "output.width",
                "height": "output.height",
                "frame_id": "output.header.frame_id",
                "distortion_model": "output.distortion_model",
                "binning_x": "output.binning_x",
                "binning_y": "output.binning_y",
            }},
        },
        "x-cap.realsenseai.device_info.v1": {
            "service": _DEVICE_INFO,
            "type": "realsense2_camera_msgs/srv/DeviceInfo",
            "operation": "read",
            "source_name": "~/device_info",
            "source_ref": _DEVICE_INFO_REF,
            "result": {"map": {
                "device_name": "output.device_name",
                "serial_number": "output.serial_number",
                "firmware_version": "output.firmware_version",
                "usb_type_descriptor": "output.usb_type_descriptor",
                "firmware_update_id": "output.firmware_update_id",
                "sensors": "output.sensors",
                "physical_port": "output.physical_port",
            }},
        },
        "x-cap.realsenseai.frame_metadata.v1": {
            "topic": _COLOR_METADATA,
            "type": "realsense2_camera_msgs/msg/Metadata",
            "operation": "subscribe",
            "path": "json_data",
            "source_name": _COLOR_METADATA,
            "source_ref": _METADATA_TOPIC_REF,
            "type_ref": _METADATA_TYPE_REF,
            "result": {"map": {"json_data": "output.$"}},
        },
        # Complete primary images of the two default streams: one fixed source per selector value.
        IMAGE: {"cameras": {
            "color": {"topic": _COLOR_IMAGE, "type": "sensor_msgs/msg/Image", "operation": "subscribe",
                      "image": dict(_IMAGE_BUDGET), "timeout_ms": 5000,
                      "source_ref": "README.md:389", "type_ref": _IMAGE_TYPE_REF},
            "depth": {"topic": _DEPTH_IMAGE, "type": "sensor_msgs/msg/Image", "operation": "subscribe",
                      "image": dict(_IMAGE_BUDGET), "timeout_ms": 5000,
                      "source_ref": "README.md:392", "type_ref": _IMAGE_TYPE_REF},
        }},
        COLOR_CAMERA_INFO: {
            "topic": _COLOR_INFO, "type": "sensor_msgs/msg/CameraInfo", "operation": "subscribe",
            "result": {"map": {"camera_info": "output.$"}},
            "source_ref": "README.md:388", "type_ref": _CAMERA_INFO_TYPE_REF,
        },
        DEPTH_CAMERA_INFO: {
            "topic": _DEPTH_INFO, "type": "sensor_msgs/msg/CameraInfo", "operation": "subscribe",
            "result": {"map": {"camera_info": "output.$"}},
            "source_ref": "README.md:391", "type_ref": _CAMERA_INFO_TYPE_REF,
        },
        COLOR_METADATA: {
            "topic": _COLOR_METADATA, "type": "realsense2_camera_msgs/msg/Metadata", "operation": "subscribe",
            "result": {"map": {"metadata": "output.$"}},
            "source_ref": "README.md:390", "type_ref": _METADATA_TYPE_REF,
        },
        DEPTH_METADATA: {
            "topic": _DEPTH_METADATA, "type": "realsense2_camera_msgs/msg/Metadata", "operation": "subscribe",
            "result": {"map": {"metadata": "output.$"}},
            "source_ref": "README.md:393", "type_ref": _METADATA_TYPE_REF,
        },
        # Opt-in: the node publishes this topic only after pointcloud.enable (default false).
        POINT_CLOUD: {
            "topic": _POINTS, "type": "sensor_msgs/msg/PointCloud2", "operation": "subscribe",
            "point_cloud": dict(_CLOUD_BUDGET), "timeout_ms": 5000,
            "source_name": "~/depth/color/points", "source_ref": _POINTS_REF,
        },
    }
    actions = {
        "x-cap.realsenseai.camera_info.v1": Action(
            name="read_camera_info",
            verb="read",
            description="Read one color CameraInfo message's geometry fields",
            output={
                "width": _WIDTH,
                "height": _HEIGHT,
                "frame_id": _FRAME_ID,
                "distortion_model": _DISTORTION_MODEL,
                "binning_x": _BINNING_X,
                "binning_y": _BINNING_Y,
            },
        ),
        "x-cap.realsenseai.device_info.v1": Action(
            name="read_device_info",
            verb="read",
            description="Read the device identity strings from the acknowledged device_info service",
            output={
                "device_name": _DEVICE_NAME,
                "serial_number": _SERIAL_NUMBER,
                "firmware_version": _FIRMWARE_VERSION,
                "usb_type_descriptor": _USB_TYPE,
                "firmware_update_id": _FIRMWARE_UPDATE_ID,
                "sensors": _SENSORS,
                "physical_port": _PHYSICAL_PORT,
            },
        ),
        "x-cap.realsenseai.frame_metadata.v1": Action(
            name="read_frame_metadata",
            verb="read",
            description="Read one color frame's metadata JSON text from the metadata topic",
            output={"json_data": _METADATA_JSON},
        ),
        IMAGE: Action(
            name="capture_image", max_duration_ms=10000, cancellable=True,
            description="Capture every pixel and the exact Image header of one default stream (color rgb8 or "
                        "depth 16UC1); captures are independent, with no synchronization or age claim",
        ),
        COLOR_CAMERA_INFO: Action(
            name="read_color_camera_info", verb="read", output={"camera_info": _CAMERA_INFO},
            description="Observe the complete color CameraInfo message without inferring calibration validity",
        ),
        DEPTH_CAMERA_INFO: Action(
            name="read_depth_camera_info", verb="read", output={"camera_info": _CAMERA_INFO},
            description="Observe the complete depth CameraInfo message without inferring calibration validity",
        ),
        COLOR_METADATA: Action(
            name="read_color_metadata", verb="read", output={"metadata": _METADATA},
            description="Observe one complete color Metadata message: its header and exact JSON text",
        ),
        DEPTH_METADATA: Action(
            name="read_depth_metadata", verb="read", output={"metadata": _METADATA},
            description="Observe one complete depth Metadata message: its header and exact JSON text",
        ),
        POINT_CLOUD: Action(
            name="capture_point_cloud", resource="pointcloud", max_duration_ms=10000, cancellable=True,
            description="Capture one complete PointCloud2 (all fields and bytes, exact header); the node "
                        "publishes it only when pointcloud.enable is set, otherwise the capture times out",
        ),
    }

    def call(self, capability_id, args=None, ctx=None):
        # Native I/O, ownership and artifact publication stay in the stock ROS bridge.  This pure post-read check
        # adds the exact ROS 2 wire ranges of the complete CameraInfo and Metadata messages.
        result = super().call(capability_id, args, ctx)
        if capability_id in _CAMERA_INFO_CAPS:
            _validate_camera_info(result.get("camera_info") if isinstance(result, dict) else None)
        elif capability_id in _METADATA_CAPS:
            _validate_metadata(result.get("metadata") if isinstance(result, dict) else None)
        return result
