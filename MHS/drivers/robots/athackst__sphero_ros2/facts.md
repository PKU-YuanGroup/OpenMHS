# Facts and tags for gh.athackst/sphero_ros2

Every fact cites its source at commit `bcbb7e12172c559eaa298484c94c1c6ed0ebcd14`: `upstream_code`
(`path/in/clone.py:LINE`). The clone contains no vendor manual or other prose that states a device bound, so no
`vendor_doc` citation is used. The reference file is generated from `driver.py`, not from this page.

## Scope

The upstream `sphero_node` is a Python ROS 2 (`rclpy`) node. It wraps the BLE `sphero_driver` package but exposes
only ROS topics: publishers `odom`, `imu`, `collision` and `/diagnostics`, and subscriptions `cmd_vel`,
`set_color`, `set_back_led`, `disable_stabilization`, `set_heading` and `set_angular_velocity`. It registers no ROS
service or action. This package is therefore a configuration-only `RosDriver` over rosbridge; it declares no Python
native class and does not import the clone.

The primary control is the `geometry_msgs/Twist` publication on `/cmd_vel`. The callback uses only
`twist.linear.x` and `twist.linear.y`: `speed = hypot(x, y)` and `heading = atan2(x, y)`, both truncated to `int`
and passed to the native `roll` command. `twist.angular.z` is ignored, so it is not exposed. The source states no
physical unit for the Twist components; the input descriptions say "raw" and use the dimension `1`, while the native
speed count is documented as 0..255.

## Stop and safety status

There is no acknowledged ROS stop. The node's timer rolls zero after 0.6 s without a command, and its shutdown-only
`stop()` method rolls zero, sets shutdown, sleeps, disconnects and joins. Neither is registered as a ROS service or
action, and neither is an independent hardware e-stop. A zero-velocity `Twist` publication is transmission-only: it
proves that rosbridge accepted the message, not that the ball stopped. This package therefore declares
`safety_bindings = {}` and `risk = "R2"` (mobile-base transit per `MHS/spec/04-safety.md`); G3 refuses the missing
independent stop as `NO_HARDWARE_FREE_PATH`. No hardware backend is run, and `driver.lock.json` keeps
`reviewed_by: null`.

## Facts

| fact | source | ref |
|---|---|---|
| `SpheroNode` is an `rclpy` `Node` subclass constructed with the node name `sphero`. | upstream_code | `sphero_node/sphero.py:23-46` |
| `_init_pubsub` creates the four publishers and six subscriptions and no service or action. | upstream_code | `sphero_node/sphero.py:65-75` |
| The `odom` publisher is `nav_msgs/Odometry` on the relative name `odom`. | upstream_code | `sphero_node/sphero.py:66` |
| The `imu` publisher is `sensor_msgs/Imu` on the relative name `imu`. | upstream_code | `sphero_node/sphero.py:67` |
| The `collision` publisher is `sphero_msgs/SpheroCollision` on the relative name `collision`. | upstream_code | `sphero_node/sphero.py:68` |
| The `/diagnostics` publisher is `diagnostic_msgs/DiagnosticArray`. | upstream_code | `sphero_node/sphero.py:69` |
| The `cmd_vel` subscriber is `geometry_msgs/Twist` on the relative name `cmd_vel`. | upstream_code | `sphero_node/sphero.py:70` |
| The `set_color` subscriber is `std_msgs/ColorRGBA` on the relative name `set_color`. | upstream_code | `sphero_node/sphero.py:71` |
| The `set_back_led` subscriber is `std_msgs/Float32` on the relative name `set_back_led`. | upstream_code | `sphero_node/sphero.py:72` |
| The `disable_stabilization` subscriber is `std_msgs/Bool` on the relative name `disable_stabilization`. | upstream_code | `sphero_node/sphero.py:73` |
| The `set_heading` subscriber is `std_msgs/Float32` on the relative name `set_heading`. | upstream_code | `sphero_node/sphero.py:74` |
| The `set_angular_velocity` subscriber is `std_msgs/Float32` on the relative name `set_angular_velocity`. | upstream_code | `sphero_node/sphero.py:75` |
| The `cmd_vel` callback uses `atan2(linear.x, linear.y)` for heading, `hypot(linear.x, linear.y)` for speed, truncates both, calls `roll`, ignores `twist.angular.z` and publishes no motion acknowledgement. | upstream_code | `sphero_node/sphero.py:209-214` |
| The `cmd_vel` timeout is set to 0.6 s. | upstream_code | `sphero_node/sphero.py:81` |
| The timer rolls zero when the timeout elapsed and the last heading or speed was nonzero, then publishes diagnostics once per second. | upstream_code | `sphero_node/sphero.py:115-126` |
| The only `stop()` method is the node shutdown path: roll zero, set shutdown, sleep one second, disconnect and join; it is not a ROS service or action. | upstream_code | `sphero_node/sphero.py:128-134` |
| `set_color` multiplies ColorRGBA r, g and b by 255 and calls `set_rgb_led` with save=0. | upstream_code | `sphero_node/sphero.py:216-218` |
| `set_back_led` passes Float32 data unchanged to `set_back(data, False)`. | upstream_code | `sphero_node/sphero.py:220-222` |
| `set_stabilization` passes 1 when the Bool is false and 0 when it is true. | upstream_code | `sphero_node/sphero.py:224-229` |
| `set_heading` normalizes Float32 radians, converts to whole degrees and calls `set_heading`. | upstream_code | `sphero_node/sphero.py:231-234` |
| `set_angular_velocity` converts Float32 rad/s to `int((value*180/pi)/0.784)` and calls `set_rotation_rate`. | upstream_code | `sphero_node/sphero.py:236-241` |
| The native `roll` command documents speed 0..255 and heading 0..359 degrees and clamps speed. | upstream_code | `sphero_driver/src/sphero_driver/sphero_driver.py:675-690` |
| The native `set_rgb_led` command clamps red, green and blue each to 0..255. | upstream_code | `sphero_driver/src/sphero_driver/sphero_driver.py:640-654` |
| The native `set_back_led` command documents brightness 0..255 and clamps it. | upstream_code | `sphero_driver/src/sphero_driver/sphero_driver.py:656-664` |
| The native `set_heading` command documents a heading range of 0..359 degrees. | upstream_code | `sphero_driver/src/sphero_driver/sphero_driver.py:471-482` |
| The native `set_stablization` command documents 00h for off and 01h for on. | upstream_code | `sphero_driver/src/sphero_driver/sphero_driver.py:484-494` |
| The native `set_rotation_rate` command documents 0.784 degrees/s units, 255 maximum, 1 minimum and clamps to 0..255. | upstream_code | `sphero_driver/src/sphero_driver/sphero_driver.py:496-509` |
| `SpheroCollision` declares one `std_msgs/Header` and eight `int32` fields with no unit annotations. | upstream_code | `sphero_msgs/msg/SpheroCollision.msg:1-9` |

## Tags

`ros`, `ros2`, `sphero`, `mobile-base`, `cmd-vel`, `led`, `imu`, `odometry`

## Limits

The clone states no site envelope for the ROS `Twist` components, the `ColorRGBA` components, the heading radians or
the angular-velocity radians per second. Those inputs use `Limit.operator_required`; `site-limits.example.json`
supplies example narrow bounds. The only sourced numeric bound is the native back-LED brightness 0..255 from the
`set_back_led` docstring. Native clamping is not treated as a ROS input bound.
