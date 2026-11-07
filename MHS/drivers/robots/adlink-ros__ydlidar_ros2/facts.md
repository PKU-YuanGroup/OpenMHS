# Facts and tags for gh.adlink-ros/ydlidar_ros2

OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a
reimplementation or compatible dialect of Anthropic's MHS research preview.

Every fact cites its source at commit `482c76acf5c0a563909e1249051c751011ae74c1`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.cpp:LINE`). The same facts are copied into
`facts = [Fact(...)]` in `driver.py`; `reference.json` is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| README lists the published `scan` topic with type `sensor_msgs/LaserScan` and describes it as the 2D laser scan of the 0-angle ring. | vendor_doc | README.md:76-78 |
| The source includes the generated `sensor_msgs/msg/laser_scan.hpp` header. | upstream_code | src/ydlidar_node.cpp:25 |
| The main function constructs a plain `rclcpp::Node` named `ydlidar_node`. | upstream_code | src/ydlidar_node.cpp:60 |
| The node creates a `sensor_msgs::msg::LaserScan` publisher on the relative topic name `scan` with `rclcpp::SensorDataQoS()`. | upstream_code | src/ydlidar_node.cpp:179 |
| `ret` holds the result of `laser.initialize()` and then `laser.turnOn()`; the main loop runs while `ret` and `rclcpp::ok()` hold, calls `laser.doProcessSimple(scan, hardError)`, and publishes a LaserScan on every successful sample. | upstream_code | src/ydlidar_node.cpp:174-216 |
| After the main loop ends the node prints a stopping message, calls `laser.turnOff()` and `laser.disconnecting()`, and shuts rclcpp down. | upstream_code | src/ydlidar_node.cpp:230-236 |
| The published header stamp splits `scan.stamp` into seconds and nanoseconds, and `header.frame_id` is set from the local `frame_id` value. | upstream_code | src/ydlidar_node.cpp:194-196 |
| The range and intensity arrays are sized as `int((max_angle - min_angle) / angle_increment + 1)`; each point is written at the `std::ceil` index of its angle offset, and a point whose index falls outside the array is dropped. | upstream_code | src/ydlidar_node.cpp:205-213 |
| The vendored SDK's `doProcessSimple` sets the range to 0.0 for an ignored angle, and the range and intensity to 0.0 for a range that is not valid. | upstream_code | sdk/src/CYdLidar.cpp:250-258 |
| The node's local `frame_id` defaults to `laser_frame` in source and is then read from the declared `frame_id` parameter. | upstream_code | src/ydlidar_node.cpp:63-82 |
| The launch file passes the node a root namespace `/`. | upstream_code | launch/ydlidar_launch.py:44 |
| README shows the resolved topic name `/scan` in the `ros2 topic echo /scan` example. | vendor_doc | README.md:36 |
| `package.xml` declares the licence `Apache License 2.0`. | upstream_code | package.xml:10 |
| The launch file carries an Apache License 2.0 header with Copyright 2020, EAIBOT. | upstream_code | launch/ydlidar_launch.py:2-3 |
| The vendored SDK's licence file is a BSD licence text of the YDLIDAR Team. | vendor_doc | sdk/license:1-4 |

Tags: `ros`, `ros2`, `lidar`, `laser-scan`, `ydlidar`, `sensor`.

## Scope and deployment notes

The pinned node publishes a `sensor_msgs/msg/LaserScan` on the relative topic `scan`. The launch file gives the
node the root namespace `/`, so the launch default endpoint is `/scan`. A deployment that starts the node under
another namespace or remaps the topic must configure the corresponding resolved endpoint; the driver does not
invent one.

The launch file uses the old `LifecycleNode` action with `node_executable`, but the pinned node source constructs a
plain `rclcpp::Node` (`src/ydlidar_node.cpp:60`). This package therefore binds no lifecycle transition service and
does not claim that the node is a managed lifecycle node.

The node exposes no application service, action, stop or reset interface in the pinned source. The only ROS interface in scope
is the scan publication. The driver's capability is an extension capability `x-cap.adlink-ros.laserscan.v1`
because the catalogue has no class for a ROS 2 `LaserScan` sample: `cap.sensing.point_cloud.v1` requires a
`sensor_msgs/msg/PointCloud2` artifact and this node publishes no PointCloud2.

The scan array length is not a constant of the package or the device. It is computed at run time from the
configured angle span and the device's angular increment (`src/ydlidar_node.cpp:205`). Every value in `fake.py` is
placeholder test data; the fake returns a five-element array only to keep the contract test small.

A range of 0.0 in a returned scan is not a measured distance: array slots that receive no point keep the value
`resize` gave them, and the vendored SDK writes 0.0 for ignored angles and invalid ranges
(`sdk/src/CYdLidar.cpp:250-258`). Consumers must discard values outside `[range_min, range_max]`; the driver passes
the array through unchanged. When `laser.initialize()` or `laser.turnOn()` fails, the node never enters its publish
loop and shuts down (`src/ydlidar_node.cpp:174-185`, `230-236`), so every read times out.

Licence: the card records NOASSERTION and requires the owner's publication decision. The clone has no top-level
licence file; `package.xml` declares Apache License 2.0, the launch file carries an Apache-2.0 header, and the
vendored `sdk/` carries a BSD licence text. The owner decides.
