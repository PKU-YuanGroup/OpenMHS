"""OpenMHS rosbridge driver for gh.ros2/ros_astra_camera.

The upstream ``astra_camera`` executable is a C++ ROS 2 node.  This package is a
configuration-only ``RosDriver`` over rosbridge; it declares no Python native
class and never imports, launches or runs the node.  The primary interface is
the relative ``sensor_msgs::msg::Image`` color publisher named ``image``; the
node's default root namespace resolves it to ``/image``.  Image bytes become a
bounded local PNG artifact through the stock SDK image path.  This is the flat
fixed-subscription profile: it keeps the existing ``image_ref``/``width``/
``height``/``media_type`` output and does not add the ROS source header to the
artifact descriptor.

The node also publishes a float depth image, an IR image and a depth CameraInfo
topic.  The pinned source converts depth to ``TYPE_32FC1`` before publishing,
which the fixed image artifact profile refuses; IR is not bound because the
pinned source never assigns the IR video mode's pixel format.  These limits are
recorded in ``RESULT.json`` and ``facts.md`` rather than guessed.

Every endpoint, type and fact cites the pinned clone at
ac20ab9eea9ff14d4b2dd841d580cf9b3c875110.  The fake transport is ROS-free; no
ROS graph, camera or hardware is contacted.
"""

from mhs.driver import Action, Fact, RosDriver

#: The color branch creates a publisher on this relative name with the exact
#: sensor_msgs::msg::Image template type.  The same line shows both the endpoint
#: literal and the message type, so it serves as source_ref and type_ref.
_IMAGE_SOURCE_NAME = "image"
_IMAGE_TOPIC = "/image"
_IMAGE_REF = "src/astra_driver.cpp:190"

#: The color callback assigns the configured color frame id and publishes the
#: frame received from the frame listener.
_IMAGE_PUBLISH_REF = "src/astra_driver.cpp:555-559"

#: The frame listener fills the ROS 2 Image message from the device frame and
#: maps the requested RGB888 pixel format to the ROS rgb8 encoding.
_IMAGE_FILL_REF = "src/astra_frame_listener.cpp:115-123"
_ENCODING_REF = "src/astra_frame_listener.cpp:145-147"

#: The constructor requests the color video mode as PIXEL_FORMAT_RGB888.
_COLOR_MODE_REF = "src/astra_driver.cpp:153-154"


class RosAstraCamera(RosDriver):
    device_id = "astra_camera"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeRosAstraCamera"}
    tags = ["ros", "ros2", "camera", "image", "rgb", "astra", "orbbec"]
    display_name = "Orbbec Astra ROS 2 color camera"
    vendor = "Orbbec"
    resource_id = "camera"
    #: A base64 ROS Image frame is larger than its raw bytes.  The node's
    #: default 1280x1024 RGB8 frame is 3,932,160 raw bytes; this is a local
    #: transport budget for one bounded message, not a device resolution limit.
    max_message_bytes = 8 * 1024 * 1024
    facts = [
        Fact("The node main creates an rclcpp node named astra_camera.",
             source="upstream_code", ref="ros/astra_camera_node.cpp:131"),
        Fact("The color branch creates a publisher on the relative topic 'image' with message type "
             "sensor_msgs::msg::Image and sensor-data QoS.",
             source="upstream_code", ref=_IMAGE_REF),
        Fact("The driver requests the color video mode with PIXEL_FORMAT_RGB888.",
             source="upstream_code", ref=_COLOR_MODE_REF),
        Fact("The frame listener maps PIXEL_FORMAT_RGB888 to the ROS RGB8 encoding and sets step to "
             "3 bytes per pixel.",
             source="upstream_code", ref=_ENCODING_REF),
        Fact("The frame listener fills width and height from the device frame, copies the frame data, "
             "and sets is_bigendian to 0.",
             source="upstream_code", ref=_IMAGE_FILL_REF),
        Fact("The color callback assigns the configured color frame id to the image header and "
             "publishes the image on the color publisher.",
             source="upstream_code", ref=_IMAGE_PUBLISH_REF),
        Fact("The color publisher is created only inside the hasColorSensor branch.",
             source="upstream_code", ref="src/astra_driver.cpp:185-191"),
        Fact("The node main initializes the color request to width 1280, height 1024 and frame rate 30.",
             source="upstream_code", ref="ros/astra_camera_node.cpp:110-112"),
        Fact("parse_command_options replaces the color width, height and frame rate from the -w, -h and -f "
             "command-line options.",
             source="upstream_code", ref="ros/astra_camera_node.cpp:56-69"),
        Fact("rawToFloatingPointConversion sets the new image encoding to TYPE_32FC1 and step to "
             "sizeof(float)*width, maps unsigned-short samples equal to 0 or 0x7FF to NaN and divides every "
             "other sample by 1000.",
             source="upstream_code", ref="src/astra_driver.cpp:1114-1145"),
        Fact("The depth branch creates a publisher on the relative 'depth' topic with message type "
             "sensor_msgs::msg::Image.",
             source="upstream_code", ref="src/astra_driver.cpp:210"),
        Fact("The depth branch publishes the converted floating-point image through pub_depth_raw_.",
             source="upstream_code", ref="src/astra_driver.cpp:623"),
        Fact("The depth branch publishes a CameraInfo message on the relative 'depth_camera_info' topic.",
             source="upstream_code", ref="src/astra_driver.cpp:211"),
        Fact("The -C command-line option sets use_color to false.",
             source="upstream_code", ref="ros/astra_camera_node.cpp:101"),
        Fact("The node sets the use_color parameter from the parsed command-line option when it is not "
             "already set.",
             source="upstream_code", ref="ros/astra_camera_node.cpp:135"),
    ]

    #: The main resource has no transport-backed fields: image capture is the
    #: explicit primary capability, never an automatic topic snapshot.  The
    #: driver's resource snapshot is therefore the documented empty object.
    parameters = {}
    reads = {}

    #: Fixed subscription: the caller selects no camera, size, exposure or
    #: encoding.  The limits are SDK host budgets, not camera safety limits.
    commands = {
        "cap.sensing.image.v1": {
            "topic": _IMAGE_TOPIC,
            "type": "sensor_msgs/msg/Image",
            "operation": "subscribe",
            "source_name": _IMAGE_SOURCE_NAME,
            "source_ref": _IMAGE_REF,
            "type_ref": _IMAGE_REF,
            "image": {
                "max_input_bytes": 4 * 1024 * 1024,
                "max_pixels": 4 * 1024 * 1024,
            },
            "timeout_ms": 10000,
        },
    }
    actions = {
        "cap.sensing.image.v1": Action(
            name="capture_image",
            description="Capture one RGB8 frame from the fixed relative 'image' color stream",
        ),
    }
