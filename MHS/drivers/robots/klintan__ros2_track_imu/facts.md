# Facts and tags for gh.klintan/ros2_track_imu

Every fact cites the pinned clone at `21741c413ceec1104c62276a6d00deddb95fec4c`:
`upstream_code` for source or comments of the clone, `vendor_doc` for text such as README.md.
The ref is the clone-relative `path:LINE` (a bounded start-end line range where the
statement spans several lines). The `facts = [...]` list in `driver.py` is the
source of truth; `reference.json` and `REFERENCE.md` are generated from it.

| fact | source | ref |
|---|---|---|
| `Ros2TrackIMUDriver` is an `rclpy` Node constructed with the name `track_imu_driver`. | upstream_code | `ros2_track_imu/driver.py:15-17` |
| The node imports the ROS 2 `sensor_msgs.msg.Imu` message. | upstream_code | `ros2_track_imu/driver.py:3` |
| The constructor creates a publisher for `Imu` on the relative topic name `imu` with queue size 10. | upstream_code | `ros2_track_imu/driver.py:20` |
| The constructor also creates a `DiagnosticArray` publisher on the relative topic name `diagnostics` with queue size 10. | upstream_code | `ros2_track_imu/driver.py:22` |
| The node declares a `frame_id` parameter whose default is the string `base_imu_link`. | upstream_code | `ros2_track_imu/driver.py:28` |
| The constructor fills the orientation, angular-velocity and linear-acceleration covariance diagonals with 0.0025, 0.02 and 0.04 based on the comments' noise estimates. | upstream_code | `ros2_track_imu/driver.py:30-64` |
| `publish_imu_data` decodes a UTF-8 line, strips the `ypr,` prefix and tab characters, and splits the remaining text on commas. | upstream_code | `ros2_track_imu/driver.py:159-162` |
| For a line with more than two comma-separated fields, the node negates yaw, adds `imu_yaw_calibration`, wraps yaw to `[-180, 180]`, negates pitch, and converts yaw, pitch and roll from degrees to radians. | upstream_code | `ros2_track_imu/driver.py:163-174` |
| `publish_imu_data` assigns the local yaw, pitch and roll only when the line has more than two comma-separated fields, and calls `quaternion_from_euler` with them after that branch. | upstream_code | `ros2_track_imu/driver.py:163-189` |
| The node imports `transforms3d.euler.euler2quat` under the name `quaternion_from_euler`. | upstream_code | `ros2_track_imu/driver.py:9` |
| The node converts roll, pitch and yaw with `quaternion_from_euler` and assigns `q[0]`, `q[1]`, `q[2]` and `q[3]` to orientation x, y, z and w. | upstream_code | `ros2_track_imu/driver.py:189-193` |
| The node stamps the Imu header from its clock, sets the configured `frame_id`, increments a sequence counter and publishes the message on `imu`. | upstream_code | `ros2_track_imu/driver.py:196-199` |
| The `linear_acceleration` and `angular_velocity` assignment lines in `publish_imu_data` are commented out. | upstream_code | `ros2_track_imu/driver.py:179-187` |
| The node publishes a `DiagnosticArray` named `Track_IMU` at level OK with message `Received AHRS measurement`, roll/yaw/pitch in degrees and the sequence number. | upstream_code | `ros2_track_imu/driver.py:201-233` |
| `imu_node.main` declares the `port` parameter with default `/dev/tty.usbmodemHIDFH1` and the `baud` parameter with default 115200, then opens `serial.Serial` with a one-second timeout. | upstream_code | `ros2_track_imu/nodes/imu_node.py:43-47` |
| The main loop flushes the first 200 serial lines, reads one line per iteration and calls `publish_imu_data` until `rclpy` is no longer OK. | upstream_code | `ros2_track_imu/nodes/imu_node.py:65-73` |
| The calls to `configure_imu` and to start the datastream with `#o1` are commented out in `main`. | upstream_code | `ros2_track_imu/nodes/imu_node.py:56-60` |
| The README documents `ros2 run ros2_track_imu imu_node` as the usage command. | vendor_doc | `README.md:13` |
| The README's launch section says ROS 2 launch is not implemented yet. | vendor_doc | `README.md:30` |
| The publisher launch file `track-imu-pub.py` is a commented-out ROS 1 launch snippet. | upstream_code | `launch/track-imu-pub.py:1-6` |
| `package.xml` declares an `ament_python` package with exec dependencies `rclpy`, `python-serial`, `sensor_msgs` and `diagnostics_msgs`. | upstream_code | `package.xml:19-27` |
| `setup.py` registers the console script `ros2_track_imu = ros2_track_imu.nodes.imu_node:main`. | upstream_code | `setup.py:20-22` |
| The accelerometer, magnetometer, gyroscope and yaw-calibration values are declared ROS parameters with constructor defaults. | upstream_code | `ros2_track_imu/driver.py:75-100` |

Model review 2026-11-04: transforms3d, outside the clone, documents its quaternions as w first while the node copies `q[0..3]` into x, y, z, w, so the published component order must be checked on the device; and a serial line with two or fewer fields (including the empty line `readline` returns after its one-second timeout) reaches `euler2quat` with unbound locals, which the unguarded main loop does not catch.

Tags (short lowercase keywords): `ros`, `ros2`, `imu`, `sensor`, `trackimu`, `serial`.
