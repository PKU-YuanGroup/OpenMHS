# Facts and tags for gh.intel/ros2_intel_realsense

Every fact cites the pinned clone at commit `74efb28ba4c4c41d5aaf588c969372616d6f5928`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines.  The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The node class is RealSenseCameraNode and its constructor passes `Node("RealSenseCameraNode", ...)` to `rclcpp::Node`. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:98-103 |
| The node includes `sensor_msgs/msg/image.hpp`. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:27 |
| publishFrame assigns a `sensor_msgs::msg::Image::SharedPtr` from `cv_bridge::CvImage(...).toImageMsg()`. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:1295-1296 |
| The constructor maps the color stream to `RS2_FORMAT_RGB8` and the ROS encoding to `sensor_msgs::image_encodings::RGB8`. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:144-146 |
| getParameters reads `enable_color` with `ENABLE_COLOR` as its default. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:230 |
| `ENABLE_COLOR` is true. | upstream_code | realsense_ros2_camera/include/realsense_ros2_camera/constants.hpp:67 |
| setupPublishers creates the color image_transport publisher on the relative topic `camera/color/image_raw` inside the enable-color branch. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:408-410 |
| setupPublishers creates a `sensor_msgs::msg::CameraInfo` publisher on the relative topic `camera/color/camera_info` with queue depth 1. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:411-412 |
| publishFrame sets width, height, `is_bigendian=false` and `step=width*bpp`, stamps the header, then publishes CameraInfo and the image. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:1295-1308 |
| The README lists the Color image topic as `/camera/color/image_raw` with a `sensor_msgs/msg/Image` message link. | vendor_doc | README.md:82-85 |
| getParameters reads `color_width` and `color_height` with `COLOR_WIDTH` and `COLOR_HEIGHT` as defaults. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:227-228 |
| `COLOR_WIDTH` is 640 and `COLOR_HEIGHT` is 480; these are ROS parameter defaults, not device bounds. | upstream_code | realsense_ros2_camera/include/realsense_ros2_camera/constants.hpp:48-49 |
| updateStreamCalibData copies the intrinsic width and height and the configured optical frame id into CameraInfo. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:717-719 |
| The constructor maps the depth stream to `sensor_msgs::image_encodings::TYPE_16UC1`. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:125 |
| setupPublishers creates the depth image transporter on the relative topic `camera/depth/image_rect_raw` inside the enable-depth branch. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:370-372 |
| The constructor maps the infra1 stream and the infra2 stream to `sensor_msgs::image_encodings::TYPE_8UC1`. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:128-141 |
| setupPublishers creates the infra1 image transporter on the relative topic `camera/infra1/image_rect_raw`. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:394-396 |
| setupPublishers creates the aligned point-cloud publisher on the relative topic `camera/aligned_depth_to_color/color/points` when aligned point cloud and aligned depth are enabled. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:388-390 |
| The signalHandler function stops and closes every queried sensor and calls `rclcpp::shutdown`; it is a process signal handler body, not a ROS service. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:77-86 |
| The constructor registers signalHandler for SIGINT. | upstream_code | realsense_ros2_camera/src/realsense_camera_node.cpp:113 |
| The README states that Intel ceased maintenance and no longer accepts patches for the project. | vendor_doc | README.md:1-9 |
| The README's known issues state that the node provides no dynamic reconfigure support for camera properties or presets. | vendor_doc | README.md:114-116 |

## Scope

The primary interface is the node's fixed `sensor_msgs/msg/Image` color stream.
The constructor's default namespace makes the relative publisher
`camera/color/image_raw` resolve to `/camera/color/image_raw`, which the README
also lists.  The package binds that stream as a fixed `cap.sensing.image.v1`
subscription; the image bytes become a bounded local PNG artifact.  The
relative publisher name is recorded as `source_name`, and a deployment that
remaps or re-namespaces the node is outside this package's upstream facts and
must expose the same absolute endpoint.

The color CameraInfo topic is exposed as read-only `frame_id`, `width` and
`height` resource fields.  It is geometry metadata, not an image snapshot and
not a camera control.  The image capability takes no input and exposes no
camera setting, exposure or resolution control; the node's parameters are not
bound as writes, and the README states there is no dynamic reconfigure support
(`README.md:114-116`).

Depth, infrared and fisheye image streams, the PointCloud2 streams, IMU data,
TF and extrinsics are not exposed.  The depth stream is encoded `16UC1`
(`realsense_ros2_camera/src/realsense_camera_node.cpp:125`) and the infrared
streams use `TYPE_8UC1` (`...:132`); this package covers neither them nor the
aligned point cloud.  CameraInfo alone would not have been a completed camera
integration, so the fixed color image subscription is the covered primary
output.

## Safety

The device is a passive camera observation endpoint at R0.  The pinned node
declares no ROS service (`create_service` does not appear in the clone); its
only stop-like path is the SIGINT signalHandler body, which is a process signal
handler rather than a requestable stop (`...:77-86`, registered at
`...:113`).  The package therefore declares no e-stop or safe state and claims
no physical stop.  Closing a subscription or shutting down the driver does not
power off the camera or prove physical quiescence.

## Deployment limits

The upstream README records that Intel ceased maintenance (`README.md:1-9`).
The node was verified with ROS 2 Dashing on Ubuntu 18.04 and depends on
librealsense2, cv_bridge, image_transport, tf2 and related ROS packages
(`README.md:19`, `README.md:24-27`).  The rosbridge deployment, node namespace,
ROS domain, QoS remapping and camera resolution are operator configuration,
not upstream facts.  The color width and height are ROS parameters whose
defaults are 640 and 480 (`constants.hpp:48-49`), so a deployment may configure
a different supported profile.  The fake is an event-driven protocol responder,
not a replay of captured ROS traffic; it returns a 4x2 placeholder RGB frame
while the node's configured default is 640x480.

The 16 MiB rosbridge frame bound, 16 MiB decoded-image bound, 4-Mi-pixel
conversion bound and 10-second subscription timeout are client execution
bounds, not sourced device limits.  The SDK's default local artifact store
holds at most 2 MiB per image; a larger PNG at a large configured resolution is
refused by that store, and a programmatic deployment can raise the per-image
bound to at most 16 MiB.

## Tags

`ros`, `ros2`, `camera`, `image`, `realsense`, `rgb`, `depth`
