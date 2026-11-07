# Facts and tags for gh.realsenseai/realsense-ros

Every fact cites the pinned clone at commit `7a87097c499e3b0b69518d54a8e7a9ac1924e87c` (source version 4.59.1):
`vendor_doc` for README text and `upstream_code` for C++ source, launch files or message definitions. The same
facts are written into `driver.py` (`facts = [...]`); the generated reference comes from the driver, not from this
page. The first thirteen facts are the original author's; the rest were added by the model review that implemented
the default image profile (see `RESULT.json`).

## Facts

| fact | source | ref |
|---|---|---|
| The launch file declares the default `camera_name` `camera` and `camera_namespace` `camera`. | upstream_code | realsense2_camera/launch/rs_launch.py:23-24 |
| README's default-behavior example lists node `/camera/camera`, topic `/camera/camera/color/camera_info`, and service `/camera/camera/device_info`. | vendor_doc | README.md:379-404 |
| README lists `/camera/camera/color/camera_info` and `/camera/camera/color/metadata` among the published topics of the default node. | vendor_doc | README.md:631-633 |
| The node constructs each stream's camera_info topic as `~/<stream_name>/camera_info`. | upstream_code | realsense2_camera/src/rs_node_setup.cpp:283 |
| The node creates a `sensor_msgs::msg::CameraInfo` publisher on that topic for non-SC streams. | upstream_code | realsense2_camera/src/rs_node_setup.cpp:306-310 |
| The node creates the private `~/device_info` service of type `realsense2_camera_msgs::srv::DeviceInfo`. | upstream_code | realsense2_camera/src/rs_node_setup.cpp:573-574 |
| The DeviceInfo service response carries seven strings: `device_name`, `serial_number`, `firmware_version`, `usb_type_descriptor`, `firmware_update_id`, `sensors` and `physical_port`. | upstream_code | realsense2_camera_msgs/srv/DeviceInfo.srv:2-8 |
| `getDeviceInfo` fills the response from the live device's name, serial number, firmware version, USB type descriptor, firmware update id, physical port and available ROS sensor names. | upstream_code | realsense2_camera/src/rs_node_setup.cpp:640-657 |
| README documents `device_info` as retrieving the device serial number, firmware version and the other DeviceInfo fields. | vendor_doc | README.md:877-880 |
| The node constructs each stream's metadata topic as `~/<stream_name>/metadata` and publishes `realsense2_camera_msgs::msg::Metadata` there. | upstream_code | realsense2_camera/src/rs_node_setup.cpp:368-370 |
| `realsense2_camera_msgs/msg/Metadata` carries a `std_msgs/Header` and a `json_data` string. | upstream_code | realsense2_camera_msgs/msg/Metadata.msg:1-2 |
| README says the metadata messages store the camera's available metadata in JSON format. | vendor_doc | README.md:805 |
| `handleHWReset` stops every available ROS sensor and calls `_dev.hardware_reset()`; it catches exceptions and only warns, and its `std_srvs/Empty` response carries no failure status. | upstream_code | realsense2_camera/src/rs_node_setup.cpp:614-637 |
| The launch file enables the color stream by default with the RGB8 color format. | upstream_code | realsense2_camera/launch/rs_launch.py:36-38 |
| The launch file enables the depth stream by default with the Z16 depth format; the infra, infra1 and infra2 streams default to false. | upstream_code | realsense2_camera/launch/rs_launch.py:40-45 |
| README's default topic list shows `/camera/camera/color/image_raw`, `/camera/camera/depth/camera_info`, `/camera/camera/depth/image_rect_raw` and `/camera/camera/depth/metadata`. | vendor_doc | README.md:387-393 |
| The node names each image topic `~/<stream_name>/image_raw`, with `image_rect_raw` for the rectified depth stream. | upstream_code | realsense2_camera/src/rs_node_setup.cpp:276-282 |
| The image publisher is a `sensor_msgs::msg::Image` publisher. | upstream_code | realsense2_camera/src/image_publisher.cpp:24 |
| The node maps the Z16 format to the `16UC1` image encoding and RGB8 to `rgb8`. | upstream_code | realsense2_camera/src/base_realsense_node.cpp:215-216 |
| Each image message gets the stream's optical frame id, the frame stamp, height, width, `is_bigendian` false and `step = width * element size`. | upstream_code | realsense2_camera/src/base_realsense_node.cpp:1246-1251 |
| `fix_depth_scale` passes 16-bit depth samples through when the device depth scale is 0.001 m and otherwise rescales every sample to that unit. | upstream_code | realsense2_camera/src/base_realsense_node.cpp:272-309 |
| Without stream intrinsics the node uses zeroed intrinsics; CameraInfo then gets the stream width, height and optical frame, K and P from fx, fy, ppx and ppy, an identity R and `plumb_bob` (5) or `equidistant` (4) distortion coefficients. | upstream_code | realsense2_camera/src/base_realsense_node.cpp:800-859 |
| CameraInfo is stamped with the frame time and published only while it has subscribers. | upstream_code | realsense2_camera/src/base_realsense_node.cpp:1397-1411 |
| Metadata JSON holds `frame_number`, `clock_domain`, `frame_timestamp` and every metadata key the frame supports; the message is published only while it has subscribers. | upstream_code | realsense2_camera/src/base_realsense_node.cpp:1479-1508 |
| The launch file defaults `pointcloud.enable` to false, `pointcloud.stream_filter` to 2, `pointcloud.ordered_pc` to false and `align_depth.enable` to false. | upstream_code | realsense2_camera/launch/rs_launch.py:77-82 |
| README says the pointcloud filter adds the topic `/camera/camera/depth/color/points`. | vendor_doc | README.md:827 |
| The pointcloud filter creates its `sensor_msgs::msg::PointCloud2` publisher on `~/depth/color/points` only while it is enabled. | upstream_code | realsense2_camera/src/pointcloud_filter.cpp:67-79 |
| An unordered cloud gets width = valid point count, height 1 and `is_dense` true. | upstream_code | realsense2_camera/src/pointcloud_filter.cpp:242-247 |
| The launch file defaults `enable_rgbd`, `enable_gyro`, `enable_accel` and `enable_motion` to false. | upstream_code | realsense2_camera/launch/rs_launch.py:62-65 |
| IMU info is published once with the latched QoS profile, and the extrinsics publishers use the same latched profile. | upstream_code | realsense2_camera/src/rs_node_setup.cpp:358-382 |
| The latched QoS profile is keep-last 1, reliable and transient-local. | upstream_code | realsense2_camera/include/constants.h:94-105 |

## Scope

One device with two typed resources (package composition: `extra_resources` plus `Action(resource=...)`), one
rosbridge transport, one e-stop latch and one lifecycle. The profile is the launch file's default node
`/camera/camera` with its default streams (color RGB8, depth Z16).

Resource `camera` (`sensor.camera`):

* `cap.sensing.image.v1` with a finite selector `camera` = `color` (`/camera/camera/color/image_raw`, `rgb8`) or
  `depth` (`/camera/camera/depth/image_rect_raw`, `16UC1`). Every pixel becomes a lossless PNG artifact (16-bit for
  depth: the received integers, never converted to metres or rescaled again); the artifact carries the image's
  exact ROS 2 header. Row padding is removed, never the samples.
* `x-cap.realsenseai.color_camera_info.v1`, `x-cap.realsenseai.depth_camera_info.v1`: the complete CameraInfo
  message of each stream (header, geometry, distortion model, D, K, R, P, binning, ROI), with ROS 2 wire-range
  checks; zero or identity fallback calibration is returned unchanged and never called valid.
* `x-cap.realsenseai.color_metadata.v1`, `x-cap.realsenseai.depth_metadata.v1`: the complete Metadata message (header
  and the exact `json_data` text, never parsed or reordered).
* The original `x-cap.realsenseai.camera_info.v1` (color geometry summary), `x-cap.realsenseai.device_info.v1` and
  `x-cap.realsenseai.frame_metadata.v1` (color JSON text), and the read-only state `frame_id`, `width`, `height`,
  `device_name`, `serial_number`, `firmware_version`, unchanged.

Resource `pointcloud` (`sensor.depth`):

* `cap.sensing.point_cloud.v1` on `/camera/camera/depth/color/points`: one complete PointCloud2 (every field, byte,
  padding, endianness and density flag, exact header) as the SDK's lossless ZIP artifact. The node publishes this
  topic only after its operator sets `pointcloud.enable` (default false); otherwise a capture fails
  `MHS.DEVICE.NOT_READY` after its 5 s wait and grants nothing. The state reads as `{}` without a transport request.

Every capture is one independent subscription: two captures never form a synchronized RGB-D pair, and no producer
age, frame rate or freshness is claimed. Host budgets (not device limits): 16 MiB per rosbridge message (base64
data), 8 MiB of image or cloud data, 4 Mi pixels, 1,048,576 points, 64 fields; a larger sample is refused whole
with no artifact. The 8 MiB cloud budget admits about 524,000 points at 16 bytes per point, fewer at a wider point
step (the xyz-plus-texture stride comes from the deployed `sensor_msgs` build, not from this pin), so a full 1280x720
cloud (921,600 points, at least 14.7 MB at 16 bytes per point, ordered or unordered) is refused: serving it needs a
reviewed package change that raises this budget and the 16 MiB rosbridge message bound together, plus a larger
operator-supplied artifact store. The default 2 MiB artifact store refuses a full 1280x720 color frame; an operator
supplies a larger store explicitly.

## NOT COVERED (open profile rows)

Infrared streams (`infra`, `infra1`, `infra2`), aligned depth (`align_depth`), the custom `rgbd` message (one packet
with two images and two CameraInfo: an atomic RGB-D pair needs separate support), IMU (`gyro`, `accel`, `motion`,
`imu`) and `imu_info`, `extrinsics/depth_to_*` and `/tf_static` (latched transient-local QoS: delivery to a late
rosbridge subscriber is unqualified, so they are not claimed), `/diagnostics`, the labeled point cloud and
occupancy outputs of D5xx devices, other image formats (YUYV, UYVY, RAW8/RAW10, Y16) and colorized depth, ROS
parameter reads or writes (stream enable, profile, exposure, emitter, filters), `hw_reset`, `calib_config_read`,
`calib_config_write`, the `triggered_calibration` action (its cancellation is callback-only), the safety services,
and every motion or stop path. The rosbridge subscription QoS, the deployed namespace (the README's absolute
`/camera/camera` names are used, no remapping is guessed), camera model, firmware, librealsense build and native
behaviour are deployment qualifications this package does not establish.

`hw_reset` is not a safety stop. Its `std_srvs/Empty` callback stops the sensors and calls `hardware_reset()`,
catches exceptions with a warning, and returns an empty response with no application success predicate
(`realsense2_camera/src/rs_node_setup.cpp:614-637`). This package therefore exposes no e-stop and claims no safe
state.

## Limits and safety

No numeric input, unit bound, range or writable field is exposed: every capability is an observation (the image
selector is a finite enum, the cloud takes no input), so there is no `Limit` and no `site-limits.example.json`. The
package is mode `hardware` at risk `R0` (the card floor): camera capture is the R0 example in
`MHS/spec/04-safety.md`, and nothing here actuates. Every ROS hardware backend needs a human `reviewed_by`
signature with scope `hardware` before it may start; none exists. The fake backend is a ROS-free recording
transport served as a simulated F0 view: contract evidence only, not a camera, ROS graph or hardware validation.

## Tags

`ros`, `ros2`, `camera`, `realsense`, `camera-info`, `metadata`, `device-info`, `image`, `depth`, `point-cloud`
