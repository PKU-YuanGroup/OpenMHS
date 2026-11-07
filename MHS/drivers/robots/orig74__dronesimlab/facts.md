# Facts and tags for gh.orig74/dronesimlab

Every fact cites the pinned clone at commit `211c94319c52b3090ec4e2c0c96fe0147a2a4ac7`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| README says Unreal Engine 4 provides imagery and depth sensor data. | vendor_doc | README.md:5 |
| The listener initializes a ROS 1 node named 'ue4_bridge' with rospy.init_node and anonymous=True. | upstream_code | ros/catkin_ws/src/ue4_bridge/scripts/ue4_bridge.py:32 |
| The bridge imports its deployment config from UNREAL_PROXY_PATH and reads config.zmq_pub_unreal_proxy and config.topic_unreal_drone_rgb_camera. | upstream_code | ros/catkin_ws/src/ue4_bridge/scripts/ue4_bridge.py:15-22 |
| The shipped demo config sets topic_unreal_drone_rgb_camera to b'rgb_camera_%d'. | upstream_code | demos/bluerov/unreal_proxy/config.py:10 |
| The bridge formats the camera topic template with index 0 and subscribes on its ZMQ socket to that name plus the literal suffixes b'down' and b'depth'. | upstream_code | ros/catkin_ws/src/ue4_bridge/scripts/ue4_bridge.py:22-26 |
| For a non-depth ZMQ topic not yet in its publisher map the bridge creates a sensor_msgs/Image publisher on the same relative topic with queue_size 2. | upstream_code | ros/catkin_ws/src/ue4_bridge/scripts/ue4_bridge.py:43-45 |
| For a non-depth topic the bridge reshapes the uint8 payload to the received shape and publishes it with cv2_to_imgmsg as a bgr8 sensor_msgs/Image without setting its header. | upstream_code | ros/catkin_ws/src/ue4_bridge/scripts/ue4_bridge.py:52-55 |
| For a depth ZMQ topic not yet in its publisher map the bridge creates sensor_msgs/Image publishers on `<topic>_rgb8` and `<topic>_range_mm` and a sensor_msgs/CameraInfo publisher on `<topic>_cam_info`, each with queue_size 2. | upstream_code | ros/catkin_ws/src/ue4_bridge/scripts/ue4_bridge.py:43-49 |
| For a depth topic the bridge reads the A channel of the float16 RGBA payload as depth in centimetres, maps the 65504 error sample to zero, multiplies by 10 to millimetres, casts to uint16 and publishes a mono16 sensor_msgs/Image with frame_id camera_depth on `<topic>_range_mm`. | upstream_code | ros/catkin_ws/src/ue4_bridge/scripts/ue4_bridge.py:57-76 |
| The bridge creates the publishers of a ZMQ topic only when the first message on that topic arrives. | upstream_code | ros/catkin_ws/src/ue4_bridge/scripts/ue4_bridge.py:43-49 |
| The depth CameraInfo sets height 240 and width 320 as constants. | upstream_code | ros/catkin_ws/src/ue4_bridge/scripts/ue4_bridge.py:92-93 |
| The shipped image_view launch remaps image to rgb_camera_0 and rgb_camera_0depth_range_mm. | upstream_code | demos/px4_gazebo/image_view.launch:3-8 |
| The shipped RGB-D SLAM node subscribes to /rgb_camera_0depth_rgb8 and /rgb_camera_0depth_range_mm as sensor_msgs::Image. | upstream_code | demos/px4_gazebo/orb_slam_ros/ORB_SLAM2/src/ros_rgbd.cc:68-69 |

## Scope

The package binds two fixed image streams of the `ue4_bridge` node:

- `color`: `/rgb_camera_0`, a bgr8 `sensor_msgs/Image` built by the non-depth
  branch from the ZMQ topic `rgb_camera_0`.
- `depth`: `/rgb_camera_0depth_range_mm`, a mono16 `sensor_msgs/Image` built by
  the depth branch from the ZMQ topic `rgb_camera_0depth`, with millimetre
  samples derived from the A channel of the float16 RGBA depth texture.

The bridge builds topic names from the deployment's `config.py` template at run
time (`ue4_bridge.py:22-26` and `demos/bluerov/unreal_proxy/config.py:10`). The
resolved literals are shown by the shipped `demos/px4_gazebo/image_view.launch:4,7`
remaps and by the shipped RGB-D node subscriptions at
`demos/px4_gazebo/orb_slam_ros/ORB_SLAM2/src/ros_rgbd.cc:68-69`. The bridge node
has no namespace argument (`rospy.init_node('ue4_bridge', anonymous=True)` at
`ue4_bridge.py:32`), so relative topic names resolve at the root namespace. A
deployment that remaps or namespaces the node must expose the declared absolute
endpoints.

`cap.sensing.image.v1` uses the ROS image selector profile: the input is exactly
`{"camera": "color" | "depth"}` and each call returns one bounded local PNG
artifact with its actual width and height. The ROS node changes no exposure,
resolution, encoding or depth calibration. The image conversion preserves the
mono16 depth samples but does not interpret their units or calibration; the
clone's `*10  #cm to mm` conversion (`ue4_bridge.py:72`) is what gives the
published stream its millimetre integer representation.

NOT COVERED: the `rgb_camera_0down` image stream. The bridge subscribes to
`rgb_camera_0down` (`ue4_bridge.py:25`) and republishes it as a bgr8 image, but
the clone contains no resolved literal name for that stream, so this package
does not declare it.

NOT COVERED: the `rgb_camera_0depth_cam_info` geometry topic. Its width and
height are hardcoded to 320 and 240 (`ue4_bridge.py:92-93`) and do not describe
the actual image shape, so the package does not expose it as resource geometry.

NOT COVERED: the ZMQ control channels, UE4 renderer configuration, drone
physics, SITL, MAVLink and the Docker/tmux deployment. The ROS node exposes no
stop, pause, reset or stepping service; its ROS surface is the image and
CameraInfo publishers created in `listener()` (`ue4_bridge.py:43-49`). Closing
the image subscription stops observation only and does not stop the UE4
renderer or the simulator.

## Fidelity contract

`driver.py` describes the fake backend: engine `synthetic:ROS-free protocol fake
(no UE4 renderer)`, level F0, determinism `none`, `timestep_ms: 0` (no renderer
or physics step), `realtime_factor: 0` (not paced), reset `none`, and no
snapshot/restore. The fake is a synthetic protocol stand-in, not a replay of
captured ROS traffic. It returns a 2x2 placeholder frame; the deployment's UE4
render-target size is configured outside the clone and is not a fixed device
bound. Depth sample values are placeholders and make no calibration or accuracy
claim. A live backend needs the operator's rosbridge endpoint and a running
`ue4_bridge` node fed by the UE4 proxy; neither runs here.

## Safety

The device is a simulated camera bridge at R0. It has no actuator, motion
command, heater, pump or laser. The driver declares no numeric input and no
`Limit`; the only inputs are the two closed camera names. An image subscription
is observational and the package declares no e-stop or safe-state binding,
because the clone offers no stop path that the helper could bind. Closing a
subscription is not a stop of the UE4 renderer or the simulator and is never
claimed as one. No hardware backend exists; the fake is contract evidence only.

## Tags

`ros`, `ros1`, `simulation`, `camera`, `image`, `depth`, `unreal-engine`
