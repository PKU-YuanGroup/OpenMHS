# Facts and tags for gh.christianrauch/multiwii_ros2

Every fact cites the pinned clone at commit `fa8586ce453149273e20735b86e213b789458060`. All citations are
`upstream_code` `path/in/clone:LINE`; the repository has no README, docs directory or other vendor text, so no
`vendor_doc` fact is declared. The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| MultiWiiNode is an rclcpp::Node constructed with the node name "multiwii". | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:12 |
| main initializes rclcpp, spins one MultiWiiNode and shuts rclcpp down. | upstream_code | multiwii2_node/src/multiwii_node.cpp:3-7 |
| The constructor declares device_path (default /dev/ttyUSB0) and baud (default 115200), constructs fcu::FlightController and calls connect(device_path, baud). | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:14-27 |
| The constructor advertises eight relative-name SensorDataQoS publishers: imu/data_raw (sensor_msgs::msg::Imu), imu/mag (MagneticField), local_position/pose (PoseStamped), rc/in (mavros_msgs::msg::RCIn), motors (mavros_msgs::msg::RCOut), battery (BatteryState), global_position/rel_alt (std_msgs::msg::Float64) and state (mavros_msgs::msg::State). | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:29-36 |
| The constructor subscribes to the relative topics rc/override and rc/override/raw with mavros_msgs::msg::OverrideRCIn and SystemDefaultsQoS. | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:40-45 |
| The constructor block that registers the RC override subscriptions contains no service server registration. | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:38-47 |
| rc_override_AERT1234 forwards channels 0 through 7 to fcu->setRc in AERT (Aileron, Elevator, Rudder, Throttle) or RPYT (Roll, Pitch, Yaw, Throttle) order. | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:227-233 |
| rc_override_raw copies every received channel into std::vector<uint16_t> and calls fcu->setRc(channels). | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:235-239 |
| The constructor creates a 100 ms wall timer that calls onState. | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:47 |
| onState publishes state.armed from fcu->isArmed() on the state topic; the other State fields are left at their defaults. | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:221-225 |
| onRc publishes the received rc.channels on rc/in. | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:163-170 |
| onMotor copies every motor.motor value into the motors RCOut channels. | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:172-180 |
| onAttitude converts roll, pitch and yaw from degrees to radians, builds a quaternion from them, publishes the orientation in local_position/pose and broadcasts a TF child frame attitude. | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:137-160 |
| onAltitude publishes altitude.altitude on global_position/rel_alt; the code comments that the value is in meters. | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:192-204 |
| onImu constructs ImuSI(imu, 512.0, 1/4.096, 0.092, 9.80665), publishes imu_si.acc as linear_acceleration and deg2rad(imu_si.gyro) as angular_velocity in imu/data_raw, and publishes imu_si.mag * 1e-6 in imu/mag. | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:110-134 |
| onAnalog copies analog.vbat and analog.amperage into battery.voltage and battery.current. | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:182-190 |
| The only flight-controller writes in this range are the two RC override callbacks' fcu->setRc calls; onState only reads fcu->isArmed(). | upstream_code | multiwii2_node/src/MultiWiiNode.cpp:221-239 |
| The multiwii_msgs package generates SendMSPRawMessage and ReceiveMSPRawMessage service definitions. | upstream_code | multiwii_msgs/CMakeLists.txt:21-26 |

## Scope

The node is a C++ ROS 2 node; this package is a configuration-only `RosDriver` over rosbridge and has no Python
`native` class. The configured endpoints are the absolute names the node's relative names resolve to at the root
namespace: `/state`, `/rc/in`, `/motors`, `/local_position/pose`, `/global_position/rel_alt`, `/imu/data_raw`,
`/rc/override` and `/rc/override/raw`. The `source_name` of every binding is the upstream literal. A deployment
that launches the node in a namespace must expose those exact absolute endpoints; remapping is deployment
configuration and is not an upstream fact.

The primary control is a publication, not a call. `rc_override_AERT1234` indexes `channels[0]` through
`channels[7]` without a length check, so this driver declares an eight-element AERT1234 input. It also exposes the
separate raw-vector path, whose channel count is a deployment property: the callback copies every received element
and the clone states no count or value range. Both inputs carry `Limit.operator_required`; the example overlay
`site-limits.example.json` is an operator example, not a device bound. The channel unit is `1` because the clone
does not state a pulse width, normalized range or other physical unit.

The published observations are:
`/state` (armed flag only), `/rc/in` (raw channel vector), `/motors` (raw motor vector),
`/local_position/pose` (quaternion derived from roll, pitch and yaw), `/global_position/rel_alt` (meters, as the
comment states) and `/imu/data_raw` (linear acceleration and angular velocity). The node also publishes
`/imu/mag` and `/battery`, but this package does not expose them: the clone scales `imu_si.mag` by `1e-6` without
stating the source unit, and it copies `analog.vbat` and `analog.amperage` into `sensor_msgs/BatteryState` without
showing the external `msp::msg::Analog` unit. No physical unit is invented for either topic.

## Safety and blocker

The device is a multirotor flight-controller bridge at R2: the two RC override callbacks write flight-controller
channels through `fcu->setRc`. The node registers no service server in the cited constructor block, and the
`multiwii_msgs` Send/ReceiveMSPRawMessage service definitions have no server in this node. There is no arm,
disarm, stop or reset endpoint in the clone. A ROS topic publication is transmission only; it does not
acknowledge execution, target attainment or stopping. Therefore no `safety_bindings` entry is declared and no
`safe_state=True` action is claimed: the bridge refuses a topic as a safe-state stop, and inventing a service
would not exist in the pinned node. The stock e-stop latches in software and reports that no acknowledged stop
is available (`safe_state_achieved` false); it never claims that the flight controller stopped. This is the
concrete blocker recorded in `RESULT.json` as `NO_HARDWARE_FREE_PATH`.

No hardware, ROS graph or native deployment has been run or validated. `driver.lock.json` keeps
`reviewed_by: null`; the package is model-authored.

## Fake fidelity

The fake is a ROS-free `RecordingRosTransport` (`fake.py`), not the upstream node and not a flight simulator. It
answers only the six observation topics this driver reads and records the two outbound override publications. It
runs no ROS graph, no wall-clock timer and no flight dynamics; its timing is event-driven with no pacing
(`F0`). Every canned channel value, altitude, acceleration and orientation is a placeholder for the wire
contract, not a measured value and not a device fact. The fake's negative switches model a silent topic, an
unrelated event id and a broken publication link; none of them is a safety proof.

## Tags

`ros`, `ros2`, `multiwii`, `flight`, `msp`, `rc`, `telemetry`
