# Facts and tags for gh.jackymao1999/webots_demo

Every fact cites the pinned clone at commit `1c45e4bdefb30b8ebbe8e1c4af9b59e22cb0c17f`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The pinned package.xml licence tag is TODO. | upstream_code | package.xml:16 |
| The README requires Webots R2021a on Ubuntu 20.04. | vendor_doc | README.md:3 |
| The world Robot uses the ros controller with the controller arguments --use-sim-time, --clock and --name=robot. | upstream_code | worlds/webots_map.wbt:173-177 |
| webots.launch includes the webots_ros webots.launch with mode realtime and the webots_map world. | upstream_code | launch/webots.launch:12-16 |
| The world declares an InertialUnit, a GPS and a SickLms291 device on the Robot. | upstream_code | worlds/webots_map.wbt:20-25 |
| The world declares left_motor and right_motor RotationalMotors on the two wheel hinge joints. | upstream_code | worlds/webots_map.wbt:92-130 |
| The Webots helper creates a client for the relative service robot/robot/time_step of type webots_ros::set_int and sets the request value to TIME_STEP. | upstream_code | include/webots_ros.h:59-61 |
| The set_int service response is a single bool success field. | upstream_code | srv/set_int.srv:3 |
| The demo controller constant TIME_STEP is 32. | upstream_code | src/demo_2dnav_move.cpp:15 |
| Webots::ChecktimeStep calls the time_step service and reports failure when the call or the service success flag fails. | upstream_code | include/webots_ros.h:128-132 |
| Webots::Quit deletes the node handle, sets the time_step request value to 0, calls the service without checking the result, then calls ros::shutdown() and exit(0). | upstream_code | include/webots_ros.h:135-141 |
| The demo controller loop calls ChecktimeStep while ros::ok() and breaks when it returns nonzero. | upstream_code | src/demo_2dnav_move.cpp:104-107 |
| The demo controller's /cmd_vel callback converts linear.x and angular.z into left and right wheel speeds and calls updateSpeed(). | upstream_code | src/demo_2dnav_move.cpp:72-87 |
| The gmapping broadcaster includes geometry_msgs/PointStamped and sensor_msgs/Imu headers. | upstream_code | src/robot_broadcaster_gmapping.cpp:10-11 |
| The gmapping broadcaster enables the gps service and subscribes to gps/values. | upstream_code | src/robot_broadcaster_gmapping.cpp:123-126 |
| The GPS callback reads point.x and point.z into the demo's planar state. | upstream_code | src/robot_broadcaster_gmapping.cpp:85-89 |
| The amcl launch starts the gmapping broadcaster and demo_2dnav_move. | upstream_code | launch/amcl_demo.launch:15-17 |
| The amcl launch also starts move_base with cmd_vel remapped to cmd_vel. | upstream_code | launch/amcl_demo.launch:60-66 |
| The amcl launch remaps the laser scan to robot/Sick_LMS_291/laser_scan/layer0. | upstream_code | launch/amcl_demo.launch:27 |
| The package CMakeLists builds the demo controller and broadcaster executables. | upstream_code | CMakeLists.txt:161-179 |

## Scope

The package serves the Webots controller's `robot/robot/time_step` service, a
ROS 1 `webots_ros/set_int` service. The service name in the clone is relative;
the driver records the upstream token `robot/robot/time_step` as `source_name`
and configures the resolved root endpoint `/robot/robot/time_step`. A
deployment that namespaces the controller differently must expose the service
at that resolved endpoint or change the driver deliberately.

One call with the fixed request `value: 32` is the environment step: it
advances the controller by the demo's `TIME_STEP` constant. The service returns
only `success`; it returns no observation, tick count or state hash, so the
package cannot bind `cap.world.step.v1`, whose contract requires an
observation, a tick and a state hash. The fixed step is an extension capability
with an explicit output schema.

The 0-value request is the same request `Webots::Quit` sends, unchecked, just
before `ros::shutdown()` and `exit(0)`. The clone shows only the Quit path, not
the service implementation, so what the request does is not shown. Since the
model review of 2026-11-05 it is an ordinary action (`send_zero_time_step`), not
a safe-state action and not an e-stop binding.

The only observation is `/robot/gps/values` (`geometry_msgs/PointStamped`). The
Webots controller publishes it, and the pinned gmapping broadcaster enables
the gps service and subscribes to the relative `gps/values` name. The callback
in the clone reads `point.x` and `point.z`; this package returns the whole
point plus the header frame id. The clone states no physical unit for the
point, so the output fields carry no unit. In the clone only the robot
broadcasters call the gps enable service before they subscribe; a deployment
without one may leave the topic silent, and the read then fails NOT_READY.

Everything else is outside this package: the laser scan, camera, wheel velocity
services, `/cmd_vel`, `/vel`, `robot/odom`, TF, keyboard, joystick and the
navigation stack. The package does not start or validate a ROS graph, Webots,
rosbridge, parameters, QoS, authentication or reconnection.

## Safety

The device is simulated at R0. The package declares **no e-stop binding and no
safe-state action** (model review, 2026-11-05): the clone does not contain the
`time_step` service implementation, the demo controller keeps requesting 32 ms
steps in its own loop (`src/demo_2dnav_move.cpp:104-107`), Webots runs in
realtime mode (`launch/webots.launch:12-16`), and the wheel velocities that
the demo controller sets from `/cmd_vel` (`src/demo_2dnav_move.cpp:72-87`;
move_base publishes it in the amcl launch) stay in effect. An MHS e-stop
therefore latches the driver, refusing the step and the 0-value request, sends
nothing and reports `MHS.SAFETY.SAFE_STATE_UNREACHED`; the gate fails
G6.ESTOP_FAILED and the package is blocked (`HELPER_MISSING`). No physical
e-stop exists and no hardware-safety claim is made.

## Fidelity contract

`driver.py` describes the deployed fake: engine `canned:ROS-free rosbridge
fake (no physics)`, level F0, determinism `none`, `timestep_ms: 0`,
`realtime_factor: 0` (no pacing), reset `none` and no snapshot/restore. The
fake answers the declared service calls and the GPS subscription with canned
values. It runs no Webots physics, controller loop or simulator, and the GPS
sample is a placeholder, not a replay of captured traffic; its header carries
the ROS 1 fields `seq`, `stamp.secs`/`nsecs` and `frame_id`.

## Tags

`ros`, `ros1`, `webots`, `simulation`, `time-step`, `gps`
