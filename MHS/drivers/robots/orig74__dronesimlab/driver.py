"""OpenMHS rosbridge driver for the DroneSimLab UE4 camera bridge (gh.orig74/dronesimlab).

The upstream ``ue4_bridge`` is a Python ROS 1 node that receives rendered frames
from the Unreal Engine proxy over ZMQ and republishes them as
``sensor_msgs/Image`` topics.  This package is a configuration-only
``RosDriver`` over rosbridge; it declares no Python native class and never
imports or starts the upstream code.

Scope: the fixed RGB stream that the node republishes on ``rgb_camera_0`` and
the metric depth stream on ``rgb_camera_0depth_range_mm``.  Both are bound as
the selector profile of ``cap.sensing.image.v1`` and return bounded local PNG
artifacts.  The bridge creates its ROS publishers lazily from the deployment's
ZMQ topic template, so a live endpoint must wait for the UE4 proxy to publish.
The depth CameraInfo topic is not used: the clone hardcodes 320x240 geometry
that does not describe the received image shape.  The ``rgb_camera_0down``
stream is not covered because the clone contains no resolved literal name for
it.  The node exposes no stop, pause, reset or stepping path; closing an image
subscription stops observation only, not the UE4 renderer.

Every endpoint, type and fact cites the pinned clone at
211c94319c52b3090ec4e2c0c96fe0147a2a4ac7.  The fake transport is ROS-free; no
ROS graph, Unreal Engine renderer or hardware is contacted.
"""

from mhs.driver import Action, Fact, RosDriver

#: The ROS 1 bridge node: it receives ZMQ frames and republishes them.
_BRIDGE = "ros/catkin_ws/src/ue4_bridge/scripts/ue4_bridge.py"

#: A shipped deployment config defines the camera topic template.
_CONFIG = "demos/bluerov/unreal_proxy/config.py"

#: A shipped launch remaps image_view to the resolved RGB and depth topics.
_LAUNCH = "demos/px4_gazebo/image_view.launch"

#: A shipped RGB-D SLAM node subscribes to the resolved depth topics.
_RGBD = "demos/px4_gazebo/orb_slam_ros/ORB_SLAM2/src/ros_rgbd.cc"

#: The demo topic template is "rgb_camera_%d"; the bridge formats index 0.
_COLOR_TOPIC = "/rgb_camera_0"
_DEPTH_TOPIC = "/rgb_camera_0depth_range_mm"

#: Client conversion bounds, not device limits.  The UE4 render-target size is
#: deployment-configured; these caps admit a 1920x1080 bgr8 frame (6.2 MB) and
#: a 1920x1080 mono16 depth frame (4.1 MB).
_IMAGE = {"max_input_bytes": 8 * 1024 * 1024, "max_pixels": 4 * 1024 * 1024}


class Dronesimlab(RosDriver):
    device_id = "dronesimlab"
    device_kind = "sensor.camera"
    mode = "simulated"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeDronesimlab"}
    tags = ["ros", "ros1", "simulation", "camera", "image", "depth", "unreal-engine"]
    display_name = "DroneSimLab UE4 camera bridge"
    vendor = "orig74"
    resource_id = "camera"
    # One encoded frame must fit the rosbridge text message; the default 1 MiB
    # client limit would reject a real 1920x1080 bgr8 frame after base64.
    max_message_bytes = 16 * 1024 * 1024
    facts = [
        Fact("README says Unreal Engine 4 provides imagery and depth sensor data.",
             source="vendor_doc", ref="README.md:5"),
        Fact("The listener initializes a ROS 1 node named 'ue4_bridge' with rospy.init_node and "
             "anonymous=True.",
             source="upstream_code", ref=f"{_BRIDGE}:32"),
        Fact("The bridge imports its deployment config from UNREAL_PROXY_PATH and reads "
             "config.zmq_pub_unreal_proxy and config.topic_unreal_drone_rgb_camera.",
             source="upstream_code", ref=f"{_BRIDGE}:15-22"),
        Fact("The shipped demo config sets topic_unreal_drone_rgb_camera to b'rgb_camera_%d'.",
             source="upstream_code", ref=f"{_CONFIG}:10"),
        Fact("The bridge formats the camera topic template with index 0 and subscribes on its ZMQ "
             "socket to that name plus the literal suffixes b'down' and b'depth'.",
             source="upstream_code", ref=f"{_BRIDGE}:22-26"),
        Fact("For a non-depth ZMQ topic not yet in its publisher map the bridge creates a "
             "sensor_msgs/Image publisher on the same relative topic with queue_size 2.",
             source="upstream_code", ref=f"{_BRIDGE}:43-45"),
        Fact("For a non-depth topic the bridge reshapes the uint8 payload to the received shape and "
             "publishes it with cv2_to_imgmsg as a bgr8 sensor_msgs/Image without setting its header.",
             source="upstream_code", ref=f"{_BRIDGE}:52-55"),
        Fact("For a depth ZMQ topic not yet in its publisher map the bridge creates sensor_msgs/Image "
             "publishers on <topic>_rgb8 and <topic>_range_mm and a sensor_msgs/CameraInfo publisher "
             "on <topic>_cam_info, each with queue_size 2.",
             source="upstream_code", ref=f"{_BRIDGE}:43-49"),
        Fact("For a depth topic the bridge reads the A channel of the float16 RGBA payload as depth "
             "in centimetres, maps the 65504 error sample to zero, multiplies by 10 to millimetres, "
             "casts to uint16 and publishes a mono16 sensor_msgs/Image with frame_id camera_depth on "
             "<topic>_range_mm.",
             source="upstream_code", ref=f"{_BRIDGE}:57-76"),
        Fact("The bridge creates the publishers of a ZMQ topic only when the first message on that "
             "topic arrives.",
             source="upstream_code", ref=f"{_BRIDGE}:43-49"),
        Fact("The depth CameraInfo sets height 240 and width 320 as constants.",
             source="upstream_code", ref=f"{_BRIDGE}:92-93"),
        Fact("The shipped image_view launch remaps image to rgb_camera_0 and "
             "rgb_camera_0depth_range_mm.",
             source="upstream_code", ref=f"{_LAUNCH}:3-8"),
        Fact("The shipped RGB-D SLAM node subscribes to /rgb_camera_0depth_rgb8 and "
             "/rgb_camera_0depth_range_mm as sensor_msgs::Image.",
             source="upstream_code", ref=f"{_RGBD}:68-69"),
    ]

    #: Both streams are fixed subscriptions.  The selector profile closes the
    #: catalogue input to exactly {"camera": "<declared name>"}; the bridge
    #: changes no exposure, resolution or encoding.
    commands = {
        "cap.sensing.image.v1": {
            "cameras": {
                "color": {
                    "topic": _COLOR_TOPIC,
                    "type": "sensor_msgs/Image",
                    "operation": "subscribe",
                    "source_name": "rgb_camera_0",
                    "source_ref": f"{_LAUNCH}:4",
                    "type_ref": f"{_BRIDGE}:6",
                    "image": dict(_IMAGE),
                    "timeout_ms": 10000,
                },
                "depth": {
                    "topic": _DEPTH_TOPIC,
                    "type": "sensor_msgs/Image",
                    "operation": "subscribe",
                    "source_ref": f"{_RGBD}:69",
                    "type_ref": f"{_BRIDGE}:6",
                    "image": dict(_IMAGE),
                    "timeout_ms": 10000,
                },
            },
            "description": "Capture one fixed UE4 stream: the bgr8 RGB image or the mono16 "
                           "range_mm depth image.",
        },
    }
    actions = {
        "cap.sensing.image.v1": Action(
            name="capture_image",
            description="Capture one image from the UE4 color stream or the metric depth stream",
        ),
    }
    #: No numeric device bound is declared.  The only inputs are the two closed
    #: camera names; the bridge publishes whatever render-target shape and
    #: depth samples the deployment produces.
    fidelity = {
        "engine": "synthetic:ROS-free protocol fake (no UE4 renderer)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned image frames with no renderer or physics step; the "
                     "same request returns the same placeholder bytes, which is not trajectory "
                     "or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free protocol transport: it answers the two declared image "
            "subscriptions and runs no UE4 renderer, ZMQ proxy, drone physics or ROS graph",
            "the fake returns a 2x2 placeholder frame; the deployment's UE4 render-target size "
            "is configured outside the clone and is not a fixed device bound",
            "depth samples in the fake are placeholders; the clone's conversion yields "
            "millimetre integers, but the driver preserves the mono16 samples and makes no "
            "calibration or accuracy claim",
            "the clone multiplies the float16 centimetre depth by 10 before the uint16 cast "
            "(ue4_bridge.py:69-72); a sample outside that representable range is not repaired "
            "by the bridge or by this driver",
            "the bridge publishes the color stream without setting its header (empty frame_id, "
            "zero stamp; ue4_bridge.py:53-55), unlike the stamped depth stream; the fake mirrors "
            "the empty frame_id",
            "the rgb_camera_0down stream, the CameraInfo topic and the ZMQ control channels "
            "are not exposed",
            "the bridge creates its publishers lazily after the first ZMQ frame; a live "
            "subscription can time out until the UE4 proxy starts publishing",
        ],
    }
