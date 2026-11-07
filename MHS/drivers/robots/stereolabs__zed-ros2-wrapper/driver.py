"""OpenMHS rosbridge driver for gh.stereolabs/zed-ros2-wrapper.

The upstream ``zed_components`` package is a C++ ROS 2 composable node.  This
package is a configuration-only ``RosDriver`` over rosbridge; it declares no
Python native class and never imports, launches or runs the upstream code.

Scope: one fixed subscription to the rectified RGB image stream that the ZED
camera publishes at ``~/rgb/color/rect/image``.  The endpoint below resolves
the private ``~/`` root with the launch file's default camera name and node
name.  Image bytes become a bounded local PNG artifact; no camera setting,
depth map, point cloud, tracking service or motion command is exposed.

The camera is observational, so the package is R0 and claims no stop or safe
state.  Closing the subscription is not camera power-off.  Every endpoint,
type and fact cites the pinned clone at
b19902daf0136b6e841b5e415c2d01f425411c45.  The fake transport is ROS-free; no
ROS graph, camera, rosbridge connection or hardware is contacted.
"""

from mhs.driver import Fact, RosDriver

#: The private image topic built by make_topic("rgb/", "color/", "rect/", "image")
#: for the launch defaults camera_name=zed and node_name=zed_node.  ``~/``
#: resolves against the node, so the operator must keep that graph name.
_IMAGE_TOPIC = "/zed/zed_node/rgb/color/rect/image"
_IMAGE_SOURCE_NAME = "~/rgb/color/rect/image"

#: CHANGELOG records the new literal topic name; this is the exact token that
#: make_topic builds from the four source constants.
_IMAGE_SOURCE_REF = "CHANGELOG.rst:164"

#: The specialized TypeAdapter publishes the private topic as a
#: sensor_msgs::msg::Image, so rosbridge subscribes with that ROS type.
_IMAGE_TYPE_REF = "zed_components/src/tools/include/sl_types.hpp:116"


class ZedRos2Wrapper(RosDriver):
    device_id = "zed"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R0"
    ros_version = 2
    #: The local transport budget covers a BGRA frame at the resolutions the
    #: pinned model configs select, whose canonical base64 expansion is larger
    #: than the raw bytes.  This is a local budget, not a device limit; a
    #: configured stream that does not fit is refused rather than resized.
    max_message_bytes = 16 * 1024 * 1024
    backends = {"fake": ".fake:FakeZedRos2Wrapper"}
    tags = ["ros", "ros2", "camera", "stereolabs", "zed", "image", "rgb"]
    display_name = "Stereolabs ZED ROS 2 wrapper"
    vendor = "Stereolabs"
    resource_id = "camera"
    facts = [
        Fact("The camera component stores its private topic root as the literal \"~/\".",
             source="upstream_code",
             ref="zed_components/src/zed_camera/include/zed_camera_component.hpp:449"),
        Fact("initVideoDepthPublishers names the RGB sensor prefix \"rgb/\", the color mode \"color/\", "
             "the rectified variant \"rect/\" and the image suffix \"image\".",
             source="upstream_code",
             ref="zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:41-50"),
        Fact("make_topic concatenates the private root with those parts and resolves the result through "
             "the node's topic interface, so \"~/\" acquires the deployed node name and namespace.",
             source="upstream_code",
             ref="zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:53-58"),
        Fact("The RGB image topic is built with make_topic(sens_rgb, color, rectified, type_image).",
             source="upstream_code",
             ref="zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:65"),
        Fact("The pinned changelog records the renamed RGB topic literal \"~/rgb/color/rect/image\".",
             source="vendor_doc", ref=_IMAGE_SOURCE_REF),
        Fact("SlImageAdapter is a TypeAdapter from StampedSlMat to sensor_msgs::msg::Image, so the adapter "
             "publishes a standard Image message on that topic.",
             source="upstream_code",
             ref="zed_components/src/tools/include/sl_types.hpp:113-116"),
        Fact("The adapter copies the matrix height, width, row step and host byte order into the ROS "
             "Image message.",
             source="upstream_code",
             ref="zed_components/src/tools/include/sl_type_adapter.hpp:58-68"),
        Fact("The adapter maps U8_C3 matrices to BGR8 and U8_C4 matrices to BGRA8.",
             source="upstream_code",
             ref="zed_components/src/tools/include/sl_type_adapter.hpp:103-111"),
        Fact("The common stereo configuration defaults enable_24bit_output to false and documents that "
             "false selects BGRA 32-bit output.",
             source="upstream_code",
             ref="zed_wrapper/config/common_stereo.yaml:56"),
        Fact("The launch file defaults camera_name to zed and node_name to zed_node, and loads the "
             "composable node with namespace and name set from those values.",
             source="upstream_code",
             ref="zed_wrapper/launch/zed_camera.launch.py:459-520"),
        Fact("When the namespace launch argument is empty, the launch file sets the namespace to the "
             "camera name.",
             source="upstream_code",
             ref="zed_wrapper/launch/zed_camera.launch.py:252-253"),
        Fact("The video.publish_rgb parameter is read into the mPublishImgRgb topic-selection flag.",
             source="upstream_code",
             ref="zed_components/src/zed_camera/src/zed_camera_component_main.cpp:923-925"),
        Fact("initVideoDepthPublishers creates the RGB publisher pair only inside the mPublishImgRgb "
             "branch.",
             source="upstream_code",
             ref="zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:247-248"),
        Fact("The common stereo configuration sets video.publish_rgb to true.",
             source="upstream_code", ref="zed_wrapper/config/common_stereo.yaml:57"),
        Fact("The node creates reset_odometry and reset_pos_tracking std_srvs Trigger services and a "
             "zed_msgs SetPose service only when position tracking is enabled.",
             source="upstream_code",
             ref="zed_components/src/zed_camera/src/zed_camera_component_main.cpp:369-391"),
        Fact("callback_resetOdometry sets mResetOdomFromSrv and returns success; it performs no camera "
             "stream stop or power-off.",
             source="upstream_code",
             ref="zed_components/src/zed_camera/src/zed_camera_component_main.cpp:8516-8527"),
    ]
    commands = {
        "cap.sensing.image.v1": {
            "topic": _IMAGE_TOPIC,
            "type": "sensor_msgs/msg/Image",
            "operation": "subscribe",
            "source_name": _IMAGE_SOURCE_NAME,
            "source_ref": _IMAGE_SOURCE_REF,
            "type_ref": _IMAGE_TYPE_REF,
            # One decoded frame must fit both the rosbridge transport and this
            # converter's pixel and byte budgets.  BGR8 and BGRA8 are both
            # accepted by the local image codec; float depth encodings are not.
            "image": {
                "max_input_bytes": 16 * 1024 * 1024,
                "max_pixels": 4 * 1024 * 1024,
            },
        }
    }
