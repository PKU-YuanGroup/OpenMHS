"""OpenMHS rosbridge driver for the Raspberry Pi camera node gh.misterblue/ros2_raspicam_node.

The upstream ``ROS2_raspicam_node`` is a Python ROS 2 node that captures JPEG
frames with PiCamera and publishes them as ``sensor_msgs/msg/CompressedImage``.
This package is a configuration-only ``RosDriver`` over rosbridge: it declares
no Python native class and never imports or starts the node.  The primary and
only working interface is the node's fixed compressed-image stream, exposed as
``cap.sensing.image.v1`` and returned as a bounded local image artifact.

The node's ``compressed_image`` parameter defaults to true and its
``compressed_image_topic`` parameter defaults to the relative name
``raspicam_compressed`` under the constructor's ``raspicam`` namespace.  The
node sets ``format`` to ``"jpeg"`` and ``header.frame_id`` to the frame number.
Camera controls are ROS parameters read once during construction; this package
invents no parameter service and exposes no metadata-only substitute.

Every endpoint, type and fact cites the pinned clone at
cebf5fdacd18b50943bd234600e8fc3622ae4a46.  The fake transport is ROS-free; no
ROS graph or camera hardware is contacted.
"""

from mhs.driver import Action, Fact, RosDriver

#: The node constructor names the node and puts it in the relative "raspicam"
#: namespace.  The topic parameters below are therefore relative to that
#: namespace; an operator deployment may remap or re-namespace the node.
_NODE_REF = "src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:30"

#: The constructor seeds compressed_image=True and the relative topic name
#: "raspicam_compressed" as ROS parameter defaults, not as hardware facts.
_TOPIC_REF = "src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:33-35"

#: The module imports only CompressedImage from sensor_msgs.msg.
_TYPE_REF = "src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:23"

#: initialize_publisher creates the compressed publisher from the topic
#: parameter when compressed_image is true.  Its false branch references the
#: unimported name Image and is not a usable stream.
_PUBLISHER_REF = "src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:88-94"

#: take_pictures asks PiCamera for JPEG and write_capture writes the bytes into
#: a CompressedImage message whose format is "jpeg".
_CAPTURE_REF = "src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:158-188"

#: publish_images publishes each queued message unchanged on the publisher.
_PUBLISH_REF = "src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:193-207"


class Ros2Raspicam(RosDriver):
    device_id = "ros2_raspicam"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeRos2Raspicam"}
    tags = ["ros", "ros2", "camera", "image", "jpeg", "raspberry-pi"]
    display_name = "Raspberry Pi camera JPEG stream (ros2_raspicam_node)"
    vendor = "Robert Adams"
    resource_id = "camera"
    # A bounded encoded JPEG plus rosbridge JSON must fit one client frame.
    # This is a host transport policy, not a camera resolution limit.
    max_message_bytes = 16 * 1024 * 1024
    facts = [
        Fact("The node constructor names it 'ros2_raspicam_node' and sets namespace='raspicam'; "
             "the topic parameters are relative to that namespace.",
             source="upstream_code", ref=_NODE_REF),
        Fact("The constructor seeds compressed_image=True and compressed_image_topic='raspicam_compressed' "
             "as ROS parameter defaults; a deployment may override them.",
             source="upstream_code", ref=_TOPIC_REF),
        Fact("The module imports CompressedImage from sensor_msgs.msg.",
             source="upstream_code", ref=_TYPE_REF),
        Fact("initialize_publisher creates a CompressedImage publisher from compressed_image_topic when "
             "compressed_image is true; the false branch references Image, which the module never imports.",
             source="upstream_code", ref=_PUBLISHER_REF),
        Fact("take_pictures requests capture_continuous(..., format='jpeg'), and write_capture builds a "
             "CompressedImage with the captured bytes, format='jpeg' and header.frame_id set to the frame number.",
             source="upstream_code", ref=_CAPTURE_REF),
        Fact("publish_images takes each queued CompressedImage and publishes it unchanged on the publisher.",
             source="upstream_code", ref=_PUBLISH_REF),
        Fact("README documents the absolute topic /raspicam/raspicam_compressed carrying JPEG bytes in "
             "sensor_msgs CompressedImage form with header.frame_id equal to the frame number.",
             source="vendor_doc", ref="README.md:7"),
        Fact("README states the project does not output a raw image, does not output camera info and does "
             "not accept parameters.",
             source="vendor_doc", ref="README.md:9"),
        Fact("destroy_node closes the PiCamera object when one exists and then calls the base destroy_node.",
             source="upstream_code", ref="src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:80-86"),
        Fact("main calls stop_workers and destroy_node only after rclpy.spin returns.",
             source="upstream_code", ref="src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:252-266"),
        Fact("write_capture sets format and header.frame_id; its only header.stamp assignment is commented out.",
             source="upstream_code", ref="src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:180-187"),
        Fact("The node defines its own has_parameter helper, which calls get_parameter and treats a NOT_SET type "
             "as unset, and set_parameter_defaults sets only the parameters that helper reports unset.",
             source="upstream_code", ref="src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:229-249"),
    ]

    #: The fixed compressed stream is the only image path that the pinned node
    #: can construct.  RosDriver replaces the catalogue's caller-controlled
    #: input schema with a closed, intentionally empty one.  The encoded-byte
    #: and decoded-pixel bounds are client conversion limits, not device limits.
    commands = {
        "cap.sensing.image.v1": {
            "topic": "/raspicam/raspicam_compressed",
            "type": "sensor_msgs/msg/CompressedImage",
            "operation": "subscribe",
            "source_name": "raspicam_compressed",
            "source_ref": _TOPIC_REF,
            "type_ref": _TYPE_REF,
            "image": {
                "max_input_bytes": 8 * 1024 * 1024,
                "max_pixels": 16 * 1024 * 1024,
            },
            "timeout_ms": 10000,
        },
    }
    actions = {
        "cap.sensing.image.v1": Action(
            name="capture_image",
            description="Capture one JPEG frame from the fixed /raspicam/raspicam_compressed stream",
        ),
    }
