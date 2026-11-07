# Facts and tags for gh.nobleo/sick_scan2

Every fact cites the pinned clone at commit `8e851e7f728e5cfb1a68a721bff833c1b50e4410`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The ROS 2 node is constructed with the literal name sick_scan2. | upstream_code | driver/src/sick_generic_caller.cpp:152 |
| SickScanCommon creates a ROS 2 publisher for sensor_msgs::msg::LaserScan on the relative topic name scan with queue size 10. | upstream_code | driver/src/sick_scan_common.cpp:420 |
| The same constructor creates ROS 2 publishers for sensor_msgs::msg::PointCloud2 on cloud and sensor_msgs::msg::Imu on imu. | upstream_code | driver/src/sick_scan_common.cpp:423-424 |
| The scan path assigns the configured frame_id into the LaserScan header. | upstream_code | driver/src/sick_scan_common.cpp:2928 |
| The scan path assigns the received timestamp into the LaserScan header before publication. | upstream_code | driver/src/sick_scan_common.cpp:2972-2975 |
| The node declares the frame_id parameter with the default string world. | upstream_code | driver/src/sick_generic_caller.cpp:201 |
| The ASCII datagram parser derives angle_min from the datagram start angle, angle_increment from the angular step width, and angle_max from the sample count. | upstream_code | driver/src/sick_generic_parser.cpp:1021-1029 |
| The ASCII datagram parser converts each raw distance value with iRange / 1000.0. | upstream_code | driver/src/sick_generic_parser.cpp:721 |
| The binary scan path derives angle_min, angle_increment and angle_max from the start angle and angular step width, and writes each range as data[i] * 0.001 * scaleFactor + scaleFactorOffset. | upstream_code | driver/src/sick_scan_common.cpp:2643-2657 |
| The parser rejects a scan whose number of data points is below 1 or above the scanner model's number of shots. | upstream_code | driver/src/sick_generic_parser.cpp:909-912 |
| The LRS_4XXX scanner configuration sets the parser's number-of-shots validation bound to 7201. | upstream_code | driver/src/sick_generic_parser.cpp:564 |
| SickGenericParser initializes its range_min and range_max overrides to 0.05 and 100.0 in its constructor. | upstream_code | driver/src/sick_generic_parser.cpp:391-392 |
| SickScanCommon::stop_scanner sends the SOPAS stream-disable command sEN LMDscandata 0 and returns its error code. | upstream_code | driver/src/sick_scan_common.cpp:431-448 |

## Scope

The package observes one fresh `sensor_msgs/msg/LaserScan` publication on the
resolved `/scan` endpoint. The upstream node creates that publisher
with the relative name `scan` inside a node literally named `sick_scan2`
(`driver/src/sick_scan_common.cpp:420`, `driver/src/sick_generic_caller.cpp:152`).
The constructor's empty namespace resolves the relative topic to `/scan`; the
node name is not a namespace prefix. A namespaced deployment must explicitly
remap the fixed endpoint or supply a separately reviewed profile. The binding records `source_name` as `scan`, and the resolved endpoint
is the deployment's namespace-qualified suffix.

The output carries the header frame and stamp, scan geometry, ranges and
intensities. The ranges array is bounded by `max_items=7201`, the largest
per-model parser validation value at the pin
(`driver/src/sick_generic_parser.cpp:564`, enforced at 909-912). That value is a
schema ceiling, not a claimed physical measurement limit or safe range. The
parser's range defaults 0.05 and 100.0 are configuration values
(`driver/src/sick_generic_parser.cpp:391-392`); the driver reports the message's
own `range_min` and `range_max` and does not turn either into a command or a
safety limit.

The node also publishes `cloud` (`sensor_msgs/msg/PointCloud2`) and `imu`
(`sensor_msgs/msg/Imu`) at `driver/src/sick_scan_common.cpp:423-424`. Those
outputs, TF, ROS parameters and full point-cloud acquisition are NOT COVERED.

`SickScanCommon::stop_scanner()` is a native C++ method that sends a SOPAS
stream-disable command (`driver/src/sick_scan_common.cpp:431-448`). The pinned
clone does not advertise it as a ROS service or action, and unsubscribing from
a topic is not an acknowledged scanner stop, so the package declares no stop,
reset or safe-state binding. The scanner is a passive sensor at R0 and this
package makes no hardware stop or safety claim.

## Safety and provenance

This is a model-authored package; `driver.lock.json` keeps `reviewed_by` null.
The fake backend is a ROS-free recording transport at F0 evidence
(`contract_checked`), never a hardware run. No ROS graph, scanner, rosbridge
connection or hardware is contacted by the package. Non-finite JSON is not
representable in an MHS record; the pinned ASCII and binary conversion paths
above convert integer distances with floating-point scaling; this does not prove
that every possible packet is finite. Non-finite input is refused without a
fabricated distance. The controlled recording-peer case returns an unknown
outcome; the live transport/deployment error is not inferred from that case.

## Tags

`ros`, `ros2`, `sick`, `laser-scanner`, `laserscan`, `scan`, `ranges`
