# Facts and tags for gh.szenergy/duro_gps_driver

Every fact cites the pinned clone at commit `d09c1f33aa07ba89d082c3e213282e2bbdbbe725`:
`vendor_doc` for README text and `upstream_code` for C++ source or launch XML. The same facts are
written into `driver.py` (`facts = [...]`); the generated reference comes from the driver, not from
this page.

## Facts

| fact | source | ref |
|---|---|---|
| README documents the topics `/gps/duro/current_pose` (`geometry_msgs/PoseStamped`), `/gps/duro/fix` (`sensor_msgs/NavSatFix`), `/gps/duro/imu` (`sensor_msgs/Imu`), `/gps/duro/mag` (`sensor_msgs/MagneticField`), `/gps/duro/odom` (`nav_msgs/Odometry`), `/gps/duro/rollpitchyaw` (`geometry_msgs/Vector3`), `/gps/duro/status_flag` (`std_msgs/UInt8`), `/gps/duro/status_string` (`std_msgs/String`) and `/gps/duro/time_ref` (`sensor_msgs/TimeReference`). | vendor_doc | README.md:91-103 |
| `main` advertises the relative publisher names `odom`, `current_pose`, `current_pose_fake_orientation`, `fix`, `mag`, `imu`, `rollpitchyaw`, `rollpitchyaw_fake`, `status_flag`, `status_string`, `time_ref`, `time_diff` and `time_gps_str` on the default node handle. | upstream_code | src/duro.cpp:467-484 |
| The advertise calls declare the message types `nav_msgs::Odometry`, `geometry_msgs::PoseStamped`, `sensor_msgs::NavSatFix`, `sensor_msgs::MagneticField`, `sensor_msgs::Imu`, `geometry_msgs::Vector3`, `std_msgs::UInt8`, `std_msgs::String`, `sensor_msgs::TimeReference` and `std_msgs::Float64`. | upstream_code | src/duro.cpp:472-484 |
| `ros::init` initializes a ROS 1 node named `duro` and the publishers are created on a default `ros::NodeHandle`. | upstream_code | src/duro.cpp:470-471 |
| The example launch starts package `duro_ros` executable `duronode` with node name `duro_driver` and sets `ip_address`, `port`, `gps_receiver_frame_id`, `imu_frame_id`, `utm_frame_id`, `orientation_source` and `z_coord_ref_switch` parameters. | upstream_code | launch/duro_example.launch:3-23 |
| The comment says the first three flag bits are the fix mode (`FIX_MODE_POSITION` 0, `FIX_MODE_MASK` 7), and the `fix_modes` enum sets `INVALID = 0` followed by `SINGLE_POINT_POSITION`, `DIFFERENTIAL_GNSS`, `FLOAT_RTK`, `FIXED_RTK`, `DEAD_RECKONING` and `SBAS_POSITION` in that order. | upstream_code | src/duro.cpp:105-121 |
| `pos_ll_callback` masks `fix_mode` out of the position flags, sets the status text to Invalid and publishes `fix_mode` as `std_msgs::UInt8` with `status_flag_pub` before the `fix_mode > fix_modes::INVALID` check; the comment maps 0 Invalid, 1 SPP, 2 DGNSS, 3 Float RTK, 4 Fixed RTK, 5 Dead Reckoning and 6 SBAS. | upstream_code | src/duro.cpp:136-154 |
| In `pos_ll_callback` the `odom_pub`, `fake_pub`, `pose_pub` and `nav_fix_pub` publications are inside the `fix_mode > fix_modes::INVALID` branch, and `status_stri_pub` publishes after that branch closes as the callback's last statement. | upstream_code | src/duro.cpp:136-271 |
| The `NavSatFix` covariance conversion interprets `h_accuracy` and `v_accuracy` as millimetres, converts them to metres and squares them for entries 0, 4 and 8, and sets `position_covariance_type` to `COVARIANCE_TYPE_DIAGONAL_KNOWN`. | upstream_code | src/duro.cpp:159-165 |
| The fix status switch maps `DEAD_RECKONING` and its default case (a mode it does not implement) to `NavSatStatus::STATUS_NO_FIX`, and `nav_fix_pub.publish(fix)` follows the switch. | upstream_code | src/duro.cpp:253-268 |
| `pose_msg` gets the x and y that `LatLonToUTMXY` computes from latitude and longitude, the `utm_frame_id` frame and a z chosen by `z_coord_ref_switch` (zero, exact, zero_based or orig). | upstream_code | src/duro.cpp:167-209 |
| When `euler_based_orientation` is false, `orientation_callback` scales the SBP quaternion by 2^-31, rotates it by -pi/2 about z and writes swapped and negated components into `pose_msg.pose.orientation`; the comments call this a left-handed/right-handed conversion. | upstream_code | src/duro.cpp:273-294 |
| `orientation_euler_callback` publishes the roll, pitch and yaw vector with `euler_pub` and, when `euler_based_orientation` is true, writes the quaternion of roll, pitch and pi/2 minus yaw into `pose_msg.pose.orientation`. | upstream_code | src/duro.cpp:326-347 |
| `fake_pose_msg` copies the header and position of `pose_msg` with a yaw-only orientation from `fake_ori.getOri() + pi` and is published by `fake_pub`; `pose_pub` publishes `pose_msg` when `orientation_source` is gps, `fake_pose_msg` when it is odom, and nothing for any other value. | upstream_code | src/duro.cpp:210-227 |
| `pos_ll_callback` assigns the `odom` header stamp and `utm_frame_id` frame, `child_frame_id` `gps_receiver_frame_id` and `pose.pose.position` (UTM x and y, height as z) before `odom_pub` publishes it; it assigns no odometry orientation, twist or covariance. | upstream_code | src/duro.cpp:136-271 |
| The IMU callback converts raw acceleration to m/s2 by dividing by `linear_acc_conf` and multiplying by 9.80665, and raw gyro to rad/s by dividing by `angular_vel_conf` and multiplying by 0.01745. | upstream_code | src/duro.cpp:349-365 |
| `imu_callback` builds and publishes an IMU message only when `linear_acc_conf > 0`, and copies that message's orientation from `pose_msg.pose.orientation`. | upstream_code | src/duro.cpp:351-373 |
| `linear_acc_conf` and `angular_vel_conf` start at -1.0. | upstream_code | src/duro.cpp:74-75 |
| `imu_aux_callback` sets `linear_acc_conf` to 16384, 8192, 4096 or 2048 and `angular_vel_conf` to 16.4, 32.8, 65.6, 131.2 or 262.4 according to the accelerometer and gyro mode bits of `imu_conf`. | upstream_code | src/duro.cpp:403-441 |
| `mag_callback` multiplies each raw magnetic component by 1e-6 and the comment labels the body-frame value in microteslas. | upstream_code | src/duro.cpp:449-459 |
| `orientation_euler_callback` divides raw roll, pitch and yaw by 57292374; the comment states the constant converts raw values from microdegrees to radians. | upstream_code | src/duro.cpp:326-334 |
| `time_callback` sets the `TimeReference` header frame to `ros_time`, computes `time_ref.sec` from the GPS week and time-of-week plus 315964782 and `time_ref.nsec` from the millisecond remainder and `ns_residual`, and labels the source `gps_duro`. | upstream_code | src/duro.cpp:296-311 |
| The `status_string` switch assigns Invalid, Single Point Position (SPP), Differential GNSS (DGNSS), Float RTK, Fixed RTK, Dead Reckoning (DR), SBAS Position or Not implemented. | upstream_code | src/duro.cpp:230-265 |
| `main` advertises topic publishers and then registers SBP callbacks and enters the socket loop; it creates no ROS service server or subscriber for commands. | upstream_code | src/duro.cpp:467-516 |
| `setup_socket` creates an `AF_INET` TCP socket and connects to `tcp_ip_addr:tcp_ip_port`. | upstream_code | src/duro.cpp:78-96 |
| The repository's debug script subscribes to `/gps/duro/time_ref`. | upstream_code | src/debug_time_drift.py:18 |

## Scope

The package exposes nine read-only rosbridge subscriptions, each returning one complete ROS 1 message
under the capability output field `sample`:

* `x-cap.szenergy.fix.v1` observes `/fix` (`sensor_msgs/NavSatFix`, `src/duro.cpp:475`).
* `x-cap.szenergy.imu.v1` observes `/imu` (`sensor_msgs/Imu`, `src/duro.cpp:477`).
* `x-cap.szenergy.mag.v1` observes `/mag` (`sensor_msgs/MagneticField`, `src/duro.cpp:476`).
* `x-cap.szenergy.time_reference.v1` observes `/time_ref` (`sensor_msgs/TimeReference`, `src/duro.cpp:482`).
* `x-cap.szenergy.fix_status.v1` observes `/status_flag` (`std_msgs/UInt8`, `src/duro.cpp:480`).
* `x-cap.szenergy.fix_status_text.v1` observes `/status_string` (`std_msgs/String`, `src/duro.cpp:481`).
* `x-cap.szenergy.pose.v1` observes `/current_pose` (`geometry_msgs/PoseStamped`, `src/duro.cpp:473`).
* `x-cap.szenergy.odometry.v1` observes `/odom` (`nav_msgs/Odometry`, `src/duro.cpp:472`).
* `x-cap.szenergy.attitude.v1` observes `/rollpitchyaw` (`geometry_msgs/Vector3`, `src/duro.cpp:478`).

The node advertises relative names. The example launch names the node `duro_driver` and does not set a
ROS namespace (`launch/duro_example.launch:3-23`), so the driver configures the root-resolved endpoints
`/fix`, `/imu`, `/mag`, `/time_ref`, `/status_flag`, `/status_string`, `/current_pose`, `/odom` and
`/rollpitchyaw`, and keeps the exact upstream relative token in `source_name`. The README's
`/gps/duro/...` table, and the repository's own `src/debug_time_drift.py:18`, use a `/gps/duro` namespace
(`README.md:91-103`). The configured root endpoints match only a node launched in the root namespace,
as the example launch does, or topics remapped to these root names; a deployment that follows the
README table publishes `/gps/duro/...`, which these bindings do not subscribe.
The bridge checks the pinned endpoint literal; it does not prove the operator's ROS graph.

Each capability opens its own short subscription. The nine observations are independent: a completed
read is one message arrival, not a synchronized multi-topic snapshot, a valid-fix decision, a fresh
source clock or an absolute-accuracy claim. `current_pose` orientation is whatever `orientation_source`
selects, including the odometry-derived fallback; the IMU orientation is copied from `pose_msg` and is
not synchronized with the raw IMU sample; the odometry pose orientation is never assigned by
`pos_ll_callback` and keeps the publisher default. The odometry sample keeps the native
`nav_msgs/Odometry` nesting (`pose.pose`, `pose.covariance`, `twist.twist`, `twist.covariance`).

`current_pose_fake_orientation`, `rollpitchyaw_fake`, `time_diff` and `time_gps_str` are not covered.
The first two are debug/derived orientation outputs, and the last two are time diagnostics outside the
README's topic table. `current_pose` orientation is whatever `orientation_source` selects, including the
odometry-derived fallback; the driver does not claim that it is a synchronized attitude measurement.

## Limits and safety

No numeric vendor bound, range or writable field is stated by the clone. The package exposes only
subscribing observations, so it declares no `Limit`, no `site-limits.example.json` overlay, no write, no
reset and no actuator control. Every value returned is the native ROS message value; the driver performs
no unit conversion and does not clamp a measurement. Fixed covariance lengths (9 or 36 elements), JSON
types and required header fields are enforced by the declared output schemas.

The node has no ROS service server, subscriber, action server or actuator command (`src/duro.cpp:467-516`).
It is an observational sensor, so no e-stop, safe-state action or reset is invented. The device is
`mode = "hardware"` at the card floor `risk = "R0"`; the fake backend is contract evidence only. A ROS
hardware backend remains refused without a human hardware review in `driver.lock.json`, and no ROS
graph, receiver or hardware was attached for this package.

## Fake

`fake.py` subclasses the SDK's ROS-free `RecordingRosTransport`. It answers each declared subscription
with one canned complete ROS 1 message, suppresses `/fix`, `/current_pose` and `/odom` when
`fix_mode <= 0`, suppresses `/imu` until `imu_ready` is true, preserves a `STATUS_NO_FIX` value for the
positive Dead Reckoning and unsupported modes, and models silent topics, mismatched subscription ids and
transport failures. All canned values, frame ids and covariance defaults are placeholders, not device
facts or physical limits. The fake runs no SBP decoder, navigation filter, ROS node or wall-clock loop;
its evidence level is F0.

## Tags

`ros`, `ros1`, `gps`, `gnss`, `ins`, `imu`, `magnetometer`, `navigation`, `sensor`
