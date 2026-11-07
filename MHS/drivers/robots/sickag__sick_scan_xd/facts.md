# Facts and tags for gh.sickag/sick_scan_xd

Every fact cites its source at commit `ed157563f1fdc3a2ea4ba6a6cac7e45ba3ab6e36`: `vendor_doc` (a text
file of the clone such as README.md) or `upstream_code` (`path/in/clone:LINE`). Copy each fact into
`facts = [Fact(text, source=..., ref=...)]` in `driver.py`; the reference file is generated from the
driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README describes the project as a ROS 2 driver and tools for SICK LiDAR and RADAR devices. | vendor_doc | README.md:7 |
| The README says the project provides a driver for SICK LiDARs and Radar sensors and supports ROS 2. | vendor_doc | README.md:19 |
| The ROS 2 build uses ament_cmake. | upstream_code | package.xml:16 |
| The ROS 2 build depends on rclcpp. | upstream_code | package.xml:27 |
| The ROS 2 wrapper includes sensor_msgs/msg/laser_scan.hpp. | upstream_code | include/sick_scan/sick_ros_wrapper.h:261 |
| For ROS 2 the wrapper defines ros_sensor_msgs as sensor_msgs::msg. | upstream_code | include/sick_scan/sick_ros_wrapper.h:279 |
| The scan topic defaults to nodename + "/scan" and is then read from the laserscan_topic parameter. | upstream_code | driver/src/sick_scan_common.cpp:542-544 |
| The node advertises ros_sensor_msgs::LaserScan on the configured laserscan_topic with queue size 1000. | upstream_code | driver/src/sick_scan_common.cpp:687 |
| The LMS5xx launch example defaults laserscan_topic to scan and nodename to sick_lms_5xx. | upstream_code | launch/sick_lms_5xx.launch:15-18 |
| The LaserScan header stamp is the receive time plus the configured time offset, and the header frame_id is the configured frame_id. | upstream_code | driver/src/sick_scan_common.cpp:4681-4682 |
| The scan telegram parser fills angle_min, angle_increment and angle_max from the reported start angle and angular step. | upstream_code | driver/src/sick_lmd_scandata_parser.cpp:156-158 |
| The parser copies the configured range_min and range_max into the LaserScan. | upstream_code | driver/src/sick_lmd_scandata_parser.cpp:323-324 |
| When min_intensity is greater than zero, scan ranges whose intensity is below that threshold are replaced with positive infinity. | upstream_code | driver/src/sick_scan_common.cpp:5025-5032 |
| The LMS5xx launch example sets min_intensity to its default 0.0. | upstream_code | launch/sick_lms_5xx.launch:71 |
| The range filter header documents that the range filter applies only to PointCloud messages, not to LaserScan messages. | upstream_code | include/sick_scan/sick_range_filter.h:68-70 |
| SickScanExit is documented as stopping the scanner and exiting sick_generic_caller. | upstream_code | srv/SickScanExitSrv.srv:1-3 |
| The exit path calls stopScanData, moves the run state to scanner_finalize and joins the generic laser driver. | upstream_code | driver/src/sick_generic_laser.cpp:193-206 |
| For the non-NAV350 profile, stop_scanner sends a SOPAS LMDscandata stop command; it is a C++ method, not a ROS service. | upstream_code | driver/src/sick_scan_common.cpp:762-807 |

Tags (short lowercase keywords):
`ros`, `ros2`, `lidar`, `laser-scan`, `sick`, `sick-scan-xd`

## Scope and evidence limits

The package is a configuration-only `RosDriver` over rosbridge. It observes the launch-default
`/scan` topic and returns one `sensor_msgs/msg/LaserScan`-shaped sample, including the
`ranges` and `intensities` arrays. It publishes no ROS command, service or action. The ROS2 constructor uses an
empty namespace (driver/src/sick_generic_caller.cpp:150). The Python launch
passes the XML parameters, which set laserscan_topic=scan before publisher
creation; nodename + /scan is only the overwritten fallback. The ROS1 private
NodeHandle branch has different name resolution and is outside this profile.

The fake is a ROS-free recording transport. Its five sample ranges and all geometry values are
placeholders, not device facts, limits or a real scan. The live scan length is the point count in the
received message and depends on the selected scanner and its configured angular window/resolution; no
fixed length or per-point bound is invented.

A non-zero `min_intensity` can put positive infinity into `ranges`. The SDK's live rosbridge transport
rejects non-finite JSON numbers and the output mapping does not convert them to null or a validity mask,
so such a message fails the observation instead of being reported as a finite distance. The package tests include a controlled non-finite range and require refusal
without a fabricated finite sample. The observed recording-peer result is an
unknown outcome; no live rosbridge outcome is inferred.

`SickScanExit` stops the scanner and exits the caller, and `stop_scanner` is a native SOPAS command, not
a ROS service. Neither is exposed as a stop, safe state or reset. Closing a subscription is not scanner
power-off. No ROS graph, rosbridge connection, scanner or hardware run is claimed; `reviewed_by` stays
null.
