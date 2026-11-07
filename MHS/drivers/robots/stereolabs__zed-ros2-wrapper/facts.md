# Facts and tags for gh.stereolabs/zed-ros2-wrapper

Every fact cites the pinned clone at commit `b19902daf0136b6e841b5e415c2d01f425411c45`:
`vendor_doc` for documentation text and `upstream_code` for C++ source or configuration. The same facts are written
into `driver.py` (`facts = [...]`); the generated reference comes from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The camera component stores its private topic root as the literal `~/`. | upstream_code | zed_components/src/zed_camera/include/zed_camera_component.hpp:449 |
| `initVideoDepthPublishers` names the RGB sensor prefix `rgb/`, the color mode `color/`, the rectified variant `rect/` and the image suffix `image`. | upstream_code | zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:41-50 |
| `make_topic` concatenates the private root with those parts and resolves the result through the node's topic interface, so `~/` acquires the deployed node name and namespace. | upstream_code | zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:53-58 |
| The RGB image topic is built with `make_topic(sens_rgb, color, rectified, type_image)`. | upstream_code | zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:65 |
| The pinned changelog records the renamed RGB topic literal `~/rgb/color/rect/image`. | vendor_doc | CHANGELOG.rst:164 |
| `SlImageAdapter` is a TypeAdapter from `StampedSlMat` to `sensor_msgs::msg::Image`, so the adapter publishes a standard Image message on that topic. | upstream_code | zed_components/src/tools/include/sl_types.hpp:113-116 |
| The adapter copies the matrix height, width, row step and host byte order into the ROS Image message. | upstream_code | zed_components/src/tools/include/sl_type_adapter.hpp:58-68 |
| The adapter maps `U8_C3` matrices to BGR8 and `U8_C4` matrices to BGRA8. | upstream_code | zed_components/src/tools/include/sl_type_adapter.hpp:103-111 |
| The common stereo configuration defaults `enable_24bit_output` to false and documents that false selects BGRA 32-bit output. | upstream_code | zed_wrapper/config/common_stereo.yaml:56 |
| The launch file defaults `camera_name` to `zed` and `node_name` to `zed_node`, and loads the composable node with namespace and name set from those values. | upstream_code | zed_wrapper/launch/zed_camera.launch.py:459-520 |
| When the namespace launch argument is empty, the launch file sets the namespace to the camera name. | upstream_code | zed_wrapper/launch/zed_camera.launch.py:252-253 |
| The `video.publish_rgb` parameter is read into the `mPublishImgRgb` topic-selection flag. | upstream_code | zed_components/src/zed_camera/src/zed_camera_component_main.cpp:923-925 |
| `initVideoDepthPublishers` creates the RGB publisher pair only inside the `mPublishImgRgb` branch. | upstream_code | zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:247-248 |
| The common stereo configuration sets `video.publish_rgb` to true. | upstream_code | zed_wrapper/config/common_stereo.yaml:57 |
| The node creates reset_odometry and reset_pos_tracking `std_srvs` Trigger services and a `zed_msgs` SetPose service only when position tracking is enabled. | upstream_code | zed_components/src/zed_camera/src/zed_camera_component_main.cpp:369-391 |
| `callback_resetOdometry` sets `mResetOdomFromSrv` and returns success; it performs no camera stream stop or power-off. | upstream_code | zed_components/src/zed_camera/src/zed_camera_component_main.cpp:8516-8527 |

## Scope

The package exposes one capability, `cap.sensing.image.v1`, as a fixed subscription to
`/zed/zed_node/rgb/color/rect/image` with type `sensor_msgs/msg/Image`. The endpoint resolves the private `~/` root
with the launch defaults `camera_name=zed` and `node_name=zed_node`; the operator must expose that graph name or
change the declaration for a different deployment. A captured frame is converted by the local image codec into a
lossless PNG artifact and the receipt reports the actual width, height and media type. The resource state is the
documented empty action-only snapshot; no image array is returned as a resource field.

The RGB image is the primary camera output and the only stream this package covers. Raw and rectified left/right
gray streams, depth (`MONO16`/`32FC1`), disparity, confidence, the point cloud, camera information, settings and
position-tracking services are not covered. The package issues no command, publishes no topic and calls no service
or action. The camera is observational, so the declared risk is R0 and the package claims no stop, no safe state and
no independent hardware e-stop; closing a rosbridge subscription is not camera power-off.

## Tags

`ros`, `ros2`, `camera`, `stereolabs`, `zed`, `image`, `rgb`
