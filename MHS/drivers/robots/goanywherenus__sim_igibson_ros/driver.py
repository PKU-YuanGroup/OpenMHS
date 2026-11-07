"""OpenMHS rosbridge driver for the iGibson TurtleBot RGB camera.

The pinned repository is the ROS 1 (noetic) wrapper around an iGibson
simulation.  Its ``turtlebot_rgbd.py`` node publishes a TurtleBot camera image
on ``/gibson_ros/camera/rgb/image`` as ``sensor_msgs/Image`` and converts the
iGibson ``obs["rgb"]`` array with ``encoding="rgb8"``.

The chosen device is that simulated RGB camera stream.  This package is a
configuration-only :class:`RosDriver` over rosbridge: it declares no Python
native class, never imports ROS, and never launches iGibson, roslaunch or the
upstream node.  A complete Image packet is captured through the SDK's fixed
ROS image path as a bounded local PNG artifact.  The receipt describes the
packet that was observed; it makes no exposure, frame-age, depth, calibration
or physics claim.

The same upstream node has effectful inputs (the ``/mobile_base/commands/
velocity`` Twist motion command and the ``/reset_pose`` PoseStamped teleport)
and other outputs (depth Image, PointCloud2, odometry and CameraInfo).  They
are NOT bound here: the clone declares no acknowledged ROS service or action
that stops the simulator, and a zero-velocity topic publication or node
shutdown is not an acknowledged stop.  This passive camera package therefore
claims neither motion control nor simulator stepping.

As pinned, ``turtlebot_rgbd.py`` cannot start: its main block calls
``SimNode(args)`` while ``SimNode.__init__`` takes no argument, and every launch
file of the clone starts that script.  A live capture therefore times out until
the operator repairs the node or runs ``turtlebot_env.py``, which publishes the
same topic with the same encoding but is started by no launch file.

Every endpoint, type and fact cites the pinned clone at
cf9a546437e00bce59237571e0a1b5b7e2ba3e05.  The fake transport is ROS-free and
all of its sample values are placeholders.
"""

from mhs.driver import Action, Fact, RosDriver

#: The node creates the Image publisher on the absolute RGB camera topic.
_IMAGE_SOURCE_REF = "igibson-ros/turtlebot_rgbd.py:35"

#: The same file imports sensor_msgs/Image as ImageMsg.
_IMAGE_TYPE_REF = "igibson-ros/turtlebot_rgbd.py:16"

#: Client conversion bounds, not device limits.  They admit the pinned
#: 256x256 rgb8 frame (196608 bytes) with room for the JSON envelope.
_IMAGE = {"max_input_bytes": 1024 * 1024, "max_pixels": 1024 * 1024}


class SimIgibsonCamera(RosDriver):
    device_id = "igibson-turtlebot-camera"
    device_kind = "sensor.camera"
    mode = "simulated"
    # The selected device is a passive image stream: the package exposes no
    # actuator, motion command, stop or reset endpoint.
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeSimIgibsonRos"}
    resource_id = "camera"
    tags = ["ros", "ros1", "igibson", "turtlebot", "simulation", "camera", "image", "rgb"]
    display_name = "iGibson TurtleBot RGB camera"
    vendor = "goanywherenus"
    model = "TurtleBot RGB camera in iGibson"
    facts = [
        Fact("The node initializes as igibson_sim and loads the igibson-ros package configuration.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.py:26-30"),
        Fact("The node constructs a headless iGibsonEnv with action_timestep 1/30 and calls reset.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.py:49-52"),
        Fact("The node creates an Image publisher on the absolute topic /gibson_ros/camera/rgb/image "
             "with queue size 10.",
             source="upstream_code", ref=_IMAGE_SOURCE_REF),
        Fact("The run loop converts the iGibson rgb observation to uint8 and creates the ROS image "
             "with cv2_to_imgmsg using encoding rgb8.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.py:85-90"),
        Fact("The image header stamp is rospy.Time.now and the image frame_id is "
             "camera_depth_optical_frame.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.py:94-100"),
        Fact("turtlebot_rgbd.yaml sets image_width and image_height to 256 and vertical_fov to 90.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.yaml:61-63"),
        Fact("The configured sensor output list includes rgb, depth and scan.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.yaml:55"),
        Fact("The same configuration bounds depth with depth_low 0.8 and depth_high 3.5.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.yaml:65-66"),
        Fact("The node publishes depth images on /gibson_ros/camera/depth/image and "
             "/gibson_ros/camera/depth/image_raw.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.py:36-38"),
        Fact("The depth message is created from a float32 depth array with encoding passthrough.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.py:86-92"),
        Fact("The node publishes a PointCloud2 lidar cloud on the absolute topic "
             "/gibson_ros/lidar/points.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.py:37"),
        Fact("The node subscribes to the absolute topic /mobile_base/commands/velocity with a Twist "
             "callback and to /reset_pose with a PoseStamped callback.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.py:43-44"),
        Fact("cmd_callback stores data.linear.x in cmdx and the negated data.angular.z in cmdy.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.py:223-225"),
        Fact("tp_robot_callback calls reset_new_pose with the message position and orientation and "
             "records the teleport time.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.py:227-237"),
        Fact("The main loop calls iGibsonEnv.step with [cmdx, cmdy] until ROS shuts down.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.py:77-79"),
        Fact("The launch starts the igibson-ros turtlebot_rgbd.py node and remaps "
             "/mobile_base/commands/velocity to /cmd_vel.",
             source="upstream_code", ref="igibson-ros/launch/turtlebot_rgbd.launch:13-14"),
        Fact("The README states that the repository provides instructions and code to set up an "
             "iGibson environment with a ROS interface and ROS navigation stack.",
             source="vendor_doc", ref="README.md:3"),
        Fact("SimNode.__init__ of turtlebot_rgbd.py takes no argument besides self.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.py:24-26"),
        Fact("The main block of turtlebot_rgbd.py parses --enable_left_right_cams with argparse and then "
             "calls SimNode(args) and node.run(args).",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.py:240-248"),
        Fact("The run loop has no rate limiter: each pass steps iGibsonEnv once and publishes one image.",
             source="upstream_code", ref="igibson-ros/turtlebot_rgbd.py:77-221"),
        Fact("The README runs the simulation with roslaunch turtlebot_custom_nav.launch.",
             source="vendor_doc", ref="README.md:13"),
        Fact("turtlebot_custom_nav.launch starts turtlebot_rgbd.py as the node turtlebot_gibson_sim.",
             source="upstream_code", ref="igibson-ros/launch/turtlebot_custom_nav.launch:13-14"),
        Fact("turtlebot_env.py creates the same Image publisher on /gibson_ros/camera/rgb/image.",
             source="upstream_code", ref="igibson-ros/turtlebot_env.py:33"),
        Fact("turtlebot_env.py converts the rgb observation with cv2_to_imgmsg using encoding rgb8.",
             source="upstream_code", ref="igibson-ros/turtlebot_env.py:62"),
        Fact("The main block of turtlebot_env.py constructs SimNode() and calls node.run() without arguments.",
             source="upstream_code", ref="igibson-ros/turtlebot_env.py:187-190"),
    ]
    safe_state = (
        "The selected device is the simulated RGB camera stream; this package binds no actuator, "
        "motion command, stop, pause, reset or stepping endpoint. The upstream "
        "/mobile_base/commands/velocity Twist input, /reset_pose teleport input, depth images, "
        "PointCloud2, odometry and CameraInfo are not exposed. The pinned clone declares no "
        "acknowledged ROS stop service or action for the simulator, so a software e-stop latches "
        "and refuses new captures; it does not stop iGibson or the upstream node."
    )
    #: The fake answers the declared Image subscription with a canned packet and
    #: runs no iGibson renderer, physics step, ROS graph or 30 Hz loop.
    fidelity = {
        "engine": "analytic:ROS-free canned Image packets (no iGibson renderer or physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned image replies with no iGibson render, physics step, "
                     "sensor noise or wall-clock pacing",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free rosbridge contract stand-in: it answers the declared "
            "sensor_msgs/Image subscription and runs no iGibson environment, renderer, physics "
            "step, roslaunch or ROS graph",
            "the fake returns a 2x2 rgb8 placeholder frame, not the configured 256x256 image "
            "(igibson-ros/turtlebot_rgbd.yaml:61-62); the fake's dimensions are test data",
            "the fake's header seq, stamp and frame id are placeholders; a real capture carries "
            "the publisher's rospy.Time.now stamp and camera_depth_optical_frame "
            "(igibson-ros/turtlebot_rgbd.py:94-100)",
            "the depth Image (float passthrough), raw depth Image, PointCloud2 lidar cloud, "
            "/odom, /ground_truth_odom, CameraInfo and TF are NOT COVERED",
            "the /mobile_base/commands/velocity motion command and /reset_pose teleport are NOT "
            "COVERED; the clone has no acknowledged ROS stop service or action, so this package "
            "does not claim motion control or simulator stepping",
            "the fake does not model the node's run loop (one image per iGibsonEnv step of "
            "action_timestep 1/30, with no rate limiter, igibson-ros/turtlebot_rgbd.py:49-51, 77-221), "
            "message drops, transport fragmentation or image encoding errors that a live deployment may "
            "produce",
            "as pinned, turtlebot_rgbd.py cannot start: its main block calls SimNode(args) while "
            "SimNode.__init__ takes only self (igibson-ros/turtlebot_rgbd.py:25, 247), and every launch file "
            "of the clone starts that script; until the operator repairs it or runs turtlebot_env.py (same "
            "topic and encoding, igibson-ros/turtlebot_env.py:33, 62, 187-190), the topic stays silent and "
            "every live capture fails with a timeout",
            "the package does not render, simulate or validate iGibson physics; no live ROS "
            "graph, iGibson process, camera or hardware run was performed",
        ],
    }

    commands = {
        "cap.sensing.image.v1": {
            "cameras": {
                "color": {
                    "topic": "/gibson_ros/camera/rgb/image",
                    "type": "sensor_msgs/Image",
                    "operation": "subscribe",
                    "image": dict(_IMAGE),
                    "source_ref": _IMAGE_SOURCE_REF,
                    "type_ref": _IMAGE_TYPE_REF,
                },
            },
        },
    }
    actions = {
        "cap.sensing.image.v1": Action(
            name="capture",
            description=(
                "Capture one complete sensor_msgs/Image packet from the fixed iGibson TurtleBot RGB "
                "camera topic and return a bounded local PNG artifact. The receipt reports the "
                "observed pixels and header; it makes no exposure, depth, age or physics claim."
            ),
        ),
    }
