# Facts and tags for gh.stevemacenski/ros2_ouster_drivers

Every fact cites the pinned clone at commit
`19c2523025e3e55a2fa803581e4e830e467a9d47`: `upstream_code` is C++ or Python
source of the clone and `vendor_doc` is text documentation of the clone.
The same facts are written into `driver.py` (`facts = [...]`); the reference
file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The package describes its supported sensors as all models of the OS-x from 16 to 128 beams running firmware 2.2-2.4. | vendor_doc | README.md:3 |
| PointcloudProcessor sizes the cloud from the sensor metadata's pixels_per_column and columns_per_frame fields. | upstream_code | ros2_ouster/include/ros2_ouster/processors/pointcloud_processor.hpp:66-67 |
| PointcloudProcessor creates a sensor_msgs::msg::PointCloud2 publisher on the relative topic name points with the configured QoS. | upstream_code | ros2_ouster/include/ros2_ouster/processors/pointcloud_processor.hpp:73-74 |
| PointcloudProcessor::process returns without publishing until the full-rotation accumulator reports a complete batch. | upstream_code | ros2_ouster/include/ros2_ouster/processors/pointcloud_processor.hpp:91-93 |
| PointcloudProcessor builds an XYZ lookup from the sensor metadata and, when a full rotation is ready, calls toCloud with that lookup, the accumulated scan and the cloud buffer. | upstream_code | ros2_ouster/include/ros2_ouster/processors/pointcloud_processor.hpp:68-97 |
| PointcloudProcessor publishes the selected cloud through the PointCloud2 publisher using the accumulated scan timestamp and the _frame member. | upstream_code | ros2_ouster/include/ros2_ouster/processors/pointcloud_processor.hpp:113-117 |
| The PointCloud2 conversion assigns its frame argument to header.frame_id and derives header.stamp from the timestamp and override timestamp arguments. | upstream_code | ros2_ouster/include/ros2_ouster/conversions.hpp:190-200 |
| OusterDriver::onActivate activates every data processor and starts the receive and process threads; onDeactivate clears the processing flag, joins both threads and deactivates the processors. | upstream_code | ros2_ouster/src/ouster_driver.cpp:141-177 |
| The upstream launch file names the lifecycle node ouster_driver and gives it the root namespace /. | upstream_code | ros2_ouster/launch/driver_launch.py:37-52 |
| OusterDriver creates its reset and get_metadata services on the private names ~/reset and ~/get_metadata. | upstream_code | ros2_ouster/src/ouster_driver.cpp:115-118 |
| OusterDriver creates the data processors with shared_from_this() and rclcpp::SensorDataQoS(), or with rclcpp::SystemDefaultsQoS() when use_system_default_qos is set. | upstream_code | ros2_ouster/src/ouster_driver.cpp:123-134 |

## Scope

The served interface is one fresh `sensor_msgs/msg/PointCloud2` publication on
the relative `points` topic, returned as one complete point-cloud artifact with
its actual point count and received frame. The upstream publisher creates the
topic on the lifecycle node
(`ros2_ouster/include/ros2_ouster/processors/pointcloud_processor.hpp:73-74`);
the processors receive the driver node itself (`shared_from_this()`,
`ros2_ouster/src/ouster_driver.cpp:123-134`), and the launch file's default
node is `ouster_driver` in namespace `/` (`ros2_ouster/launch/driver_launch.py:37-52`).
A relative ROS 2 name resolves against the node's namespace, not its name, so
the configured endpoint is `/points`; only the private `~/reset` and
`~/get_metadata` services resolve under `/ouster_driver/`
(`ros2_ouster/src/ouster_driver.cpp:115-118`). That resolution is a deployment
assumption: a node launched in another namespace, or a remapped topic, must have
the endpoint configured to the actual resolved topic. The declaration keeps the
upstream relative token as `source_name`. The publisher uses
`rclcpp::SensorDataQoS()` unless `use_system_default_qos` is set; the rosbridge
helper does not select QoS, so a subscriber QoS match is a deployment check.

The node publishes a cloud only while it is active and a full rotation has been
accumulated (`ros2_ouster/include/ros2_ouster/processors/pointcloud_processor.hpp:91-93`,
`ros2_ouster/src/ouster_driver.cpp:141-158`). The driver issues a new
subscription for every capture; it does not return a cached or held message and
does not change the lidar's configuration, lifecycle state or packet
processing.

The upstream node also publishes `scan`
(`ros2_ouster/include/ros2_ouster/processors/scan_processor.hpp:59`),
`range_image`, `intensity_image` and `ambient_image`
(`ros2_ouster/include/ros2_ouster/processors/image_processor.hpp:71-76`), and
`imu` (`ros2_ouster/include/ros2_ouster/processors/imu_processor.hpp:55`), and
offers the private `~/reset` and `~/get_metadata` services
(`ros2_ouster/src/ouster_driver.cpp:115-118`). Those outputs, the reset
reconfiguration and the metadata file write are not covered by this package.
The point cloud is the primary 3-D lidar output.

## Fidelity contract

The fake is a ROS-free recording transport at F0. It answers the declared
subscription with a one-point sample whose width, height, field layout and
timestamps are placeholders; the real width and height come from the connected
sensor's metadata (`pixels_per_column` times `columns_per_frame`,
`ros2_ouster/include/ros2_ouster/processors/pointcloud_processor.hpp:66-67`).
The fake runs no sensor, packet decoder, rotation accumulator or ROS graph.

The capture is subject to the SDK's bounded point-cloud path: the transport
message must fit the driver's `max_message_bytes` and the decoded message must
fit the declared `max_input_bytes`; the local artifact store also has its own
per-artifact limit. The SDK default per-artifact limit is 2 MiB, so a full-size
real cloud requires an operator-provided artifact store with a larger
per-artifact bound (up to the documented 16 MiB ceiling). The fake's one-point
sample avoids that cost and is not evidence of a real cloud's size.

## Safety

This is an observational R0 sensor package. It declares no writable state, no
command that actuates the lidar, and no stop, reset or safe-state binding. A
point-cloud capture only subscribes to the publisher; unsubscribing or closing
the rosbridge connection does not power off or stop the lidar, and the package
claims no such effect. The upstream `~/reset` service is deliberately not
exposed because it reconfigures the sensor connection and is not a stop.

## Tags

`ros`, `ros2`, `ouster`, `lidar`, `pointcloud`, `sensing`, `depth`
