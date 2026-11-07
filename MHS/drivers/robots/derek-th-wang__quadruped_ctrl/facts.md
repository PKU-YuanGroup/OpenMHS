# Facts and tags for gh.derek-th-wang/quadruped_ctrl

Pinned commit: `6e1093c1d67ff835c02d66d0ad611d2c67d912ad`. Every fact cites a text file of the clone; the same
facts are written into `driver.py` and the generated `reference.json`, not copied from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The launch file starts the Python node walking_simulation.py as quadruped_simulator. | upstream_code | launch/quadruped_ctrl.launch:8-9 |
| The node registers the relative gait_type and robot_mode services with the quadruped_ctrl/QuadrupedCmd type and subscribes to the relative cmd_vel topic with geometry_msgs/Twist. | upstream_code | scripts/walking_simulation.py:64-66 |
| The gait_type callback calls set_gait_type(req.cmd) and returns QuadrupedCmdResponse(0, "get the gait"). | upstream_code | scripts/walking_simulation.py:386-388 |
| The robot_mode callback calls set_robot_mode(req.cmd) and returns QuadrupedCmdResponse(0, "get the mode"). | upstream_code | scripts/walking_simulation.py:390-392 |
| The cmd_vel callback builds [msg.linear.x, msg.linear.y, msg.angular.x] and passes it to set_robot_vel; it does not read linear.z, angular.y or angular.z. | upstream_code | scripts/walking_simulation.py:394-396 |
| GaitCtrller::SetGaitType stores the integer gait type in _gaitType and prints it. | upstream_code | src/GaitCtrller.cpp:65-68 |
| GaitCtrller::SetRobotMode stores the integer mode in _robotMode and prints it; it performs no actuation or stop. | upstream_code | src/GaitCtrller.cpp:70-73 |
| The C wrapper comment defines robot mode 0 as high performance and 1 as low power. | upstream_code | src/GaitCtrller.h:84-85 |
| GaitCtrller::SetRobotVel zeroes a velocity component whose magnitude is below 0.03 and otherwise stores the component unchanged. | upstream_code | src/GaitCtrller.cpp:75-93 |
| The desired-state setup clamps the filtered x velocity to [-1.0, 2.0] m/s and the filtered y velocity to [-0.6, 0.6] m/s; the yaw-rate channel is filtered but not clamped. | upstream_code | src/MPC_Ctrl/ConvexMPCLocomotion.cpp:89-101 |
| The README lists gait type values 0 through 11. | vendor_doc | README.md:69-80 |
| The standing gait is constructed with a zero swing schedule for all four legs and a 14-step stance schedule. | upstream_code | src/MPC_Ctrl/ConvexMPCLocomotion.cpp:35 |
| The desired world-position integration is skipped while the selected gait is standing. | upstream_code | src/MPC_Ctrl/ConvexMPCLocomotion.cpp:276-280 |
| ConvexMPCLocomotion::run maps the gait number to a gait only when robotMode is 0; when robotMode is 1 it uses the adaptive aio gait and sets the gait from the commanded body speed and yaw rate. | upstream_code | src/MPC_Ctrl/ConvexMPCLocomotion.cpp:148-185 |
| __reset_robot sets robot mode 1 and then calls run(), which the upstream comment marks as blocking, before the line that sets robot mode 0. | upstream_code | scripts/walking_simulation.py:194-198 |
| The node's run loop continues until rospy.is_shutdown() and executes one simulation step per rospy.Rate(freq) period. | upstream_code | scripts/walking_simulation.py:205-222 |
| Each simulation step calls the odometry, IMU, joint-state and whole-body-state publishers. | upstream_code | scripts/walking_simulation.py:229-232 |
| The /robot_odom publisher uses nav_msgs/Odometry and fills pose.pose.position from the pybullet base position and pose.pose.orientation from the base quaternion. | upstream_code | scripts/walking_simulation.py:413 |
| The /imu0 publisher uses sensor_msgs/Imu and fills linear_acceleration, angular_velocity and orientation in the body frame. | upstream_code | scripts/walking_simulation.py:433 |
| The simulator connects pybullet in GUI mode and sets the physics timestep to 1.0/freq. | upstream_code | scripts/walking_simulation.py:83-86 |
| A separate camera thread starts only when the /simulation/camera parameter is true. | upstream_code | scripts/walking_simulation.py:45-47 |
| The camera thread publishes /generated_pc as sensor_msgs/PointCloud2 and /cam0/image_raw as sensor_msgs/Image at 20 Hz. | upstream_code | scripts/walking_simulation.py:246-257 |
| The odometry publisher stamps the header with rospy.Time.now() and sets pose.pose.position x, y and z from the base position. | upstream_code | scripts/walking_simulation.py:414-420 |
| The IMU publisher sets angular_velocity x, y and z from imu_data[7], imu_data[8] and imu_data[9] and stamps the header with rospy.Time.now(). | upstream_code | scripts/walking_simulation.py:438-445 |
| The desired x, y and yaw-rate commands pass through first-order filters with coefficients 0.01, 0.006 and 0.03 per controller step. | upstream_code | src/MPC_Ctrl/ConvexMPCLocomotion.cpp:82-91 |
| The shipped configuration sets the simulation frequency to 500.0. | upstream_code | config/quadruped_ctrl_config.yaml:1-6 |

## Scope

This is a configuration-only ROS 1 `RosDriver` over rosbridge. The selected interface is the simulator's
motion-control surface and two observations:

* `x-cap.derek-th-wang.cmd_vel.v1` publishes one `geometry_msgs/Twist` on `/cmd_vel`. The callback reads
  `linear.x`, `linear.y` and `angular.x` into the controller's `[x, y, yaw]` command vector. A publish receipt is
  transmission evidence only; it does not prove arrival, execution, motion or stopping.
* `x-cap.derek-th-wang.gait_type.v1` and `x-cap.derek-th-wang.robot_mode.v1` call the two relative services
  through their resolved root endpoints. Both callbacks return `result: 0` unconditionally after storing the value.
* `x-cap.derek-th-wang.odometry.v1` and `x-cap.derek-th-wang.imu.v1` subscribe to the two relative/absolute
  observations and return the selected message fields.

The node's relative names are recorded as `source_name`; a deployment that namespaces the node must expose the
same absolute endpoints through rosbridge remapping. The package does not start ROS, rosbridge or pybullet.

Not covered: the optional camera path (`/generated_pc`, `/cam0/image_raw`), `joint_states`, `wb_state`, TF,
the pybullet GUI reset/debug parameters, `cap.world.step.v1`/`cap.world.reset.v1`/`cap.world.seed.v1` (the node
exposes no service for them), and the upstream gamepad node. The camera is disabled by default in the shipped
config; image and point-cloud artifacts are outside this profile.

## Limits and units

The controller clamps the filtered x desired velocity to `[-1.0, 2.0]` m/s and the filtered y desired velocity
to `[-0.6, 0.6]` m/s (`src/MPC_Ctrl/ConvexMPCLocomotion.cpp:89-101`). These controller clamps are declared as
the x/y input bounds. `SetRobotVel` also zeroes a component below `0.03` (`src/GaitCtrller.cpp:75-93`), so a
small nonzero command is stored as zero; the driver does not hide that deadband.

The yaw-rate channel is filtered but has no source-stated bound, so `yaw_rate` is `Limit.operator_required`.
`site-limits.example.json` is an illustrative fake-only overlay, not an upstream range or a physical
recommendation. Without an operator overlay, a `cmd_vel` command that carries `yaw_rate` is refused with
`MHS.SAFETY.LIMITS_UNSET`, as the runtime requires.

Gait values `0` through `11` are the README's list (`README.md:69-80`); the C++ code also accepts `20 + n` to
select omni mode (`src/MPC_Ctrl/ConvexMPCLocomotion.cpp:129-131`), but that extended range is not exposed here.
Robot mode `0`/`1` is the C wrapper's documented pair (`src/GaitCtrller.h:84-85`); other integers reach the
`err robot mode!!!` branch (`src/MPC_Ctrl/ConvexMPCLocomotion.cpp:234-236`). Both service bounds narrow the
service's unconstrained `int16 cmd` field; they do not change the wire syntax.

## Sensed-confirmation stop (SAFE-049)

The user's decision of 2026-11-05 allows a request plus a sensed confirmation as the stop of a simulated
device. The e-stop publishes a zero Twist on `cmd_vel` (the callback reads `linear.x`, `linear.y`,
`angular.x`, `scripts/walking_simulation.py:394-396`; in robot mode 1 the adaptive gait stands once the
filtered speed decays, `src/MPC_Ctrl/ConvexMPCLocomotion.cpp:173-185`) and requests gait 4 on `gait_type`
(standing in robot mode 0, `:150-158`), then reads `/robot_odom` (x and y still, z within the standing
band; filled at `walking_simulation.py:418-420`) and `/imu0` (angular rate below a bound; filled at
`:438-440`). The odometry twist is never filled and no term reads it. Both sources are throttled to 20 ms
(the node publishes every simulation step, 500 Hz in the shipped config). The request steps prove nothing by themselves. The e-stop is achieved only when every source delivers three consecutive fresh samples (new subscriptions opened after the request; the first sample of each discarded; strictly increasing producer stamps; every predicate term holding; an arrival gap above `max_gap_ms` or a repeated stamp restarts the count) within `confirm_within_ms` of the first transmission. Otherwise the e-stop is `failed` `MHS.SAFETY.SAFE_STATE_UNREACHED` (`details.sensed.reason`), the latch holds and the background retry sends the request again. Thresholds are `operator_required` (the fake's placeholders are in `fixtures/estop-confirmation.json`; a live simulation supplies them in `simulation_deployment['estop_confirmation']`); the client bounds (`consecutive` 3, `min_span_ms` 200, `max_gap_ms` 500, `confirm_within_ms` 1500) are fake-scale, and a live deployment sets its own. The SDK cannot prove that the ROS graph is simulated; only a simulated device may use this profile.

The pybullet GUI buttons switch the robot mode and another `/cmd_vel` publisher can move the robot after a
confirmed stop; a failed controller safety check zeroes all torques and the robot collapses below the
standing band, which keeps the stop unconfirmed (fail closed).

## Safety

The driver is `mode = "simulated"`, `device_kind = "world.sim"` and `risk = "R2"`; it has no hardware backend.
The risk follows REVIEW.md item 12 (integrator v4, 2026-11-05): the package publishes a velocity setpoint on the
root `/cmd_vel` (`geometry_msgs/Twist`) that a physical mobile base behind the same bridge would act on, and
`/gait_type` and `/robot_mode` select the gait of the locomotion controller (`scripts/walking_simulation.py:64-66`);
mobile-base transit is R2 (`MHS/spec/04-safety.md`), however simulated the deployment. The card's
`safety.risk_floor` is R0; the package's risk is above it.

The node registers no stop service or action. `robot_mode` only stores `_robotMode` (`src/GaitCtrller.cpp:70-73`);
`gait_type` only stores `_gaitType` (`src/GaitCtrller.cpp:65-68`). The run loop continues until
`rospy.is_shutdown()` (`scripts/walking_simulation.py:205-222`). The fixed `stand` command calls `/gait_type`
with `cmd=4`; in robot mode 0 gait 4 selects the standing gait, whose schedule is all stance
(`src/MPC_Ctrl/ConvexMPCLocomotion.cpp:35`) and whose branch skips desired-position integration
(`src/MPC_Ctrl/ConvexMPCLocomotion.cpp:276-280`).

Model review (2026-11-04): the controller honours the gait type only in robot mode 0. In robot mode 1 it uses the
adaptive `aio` gait and chooses the gait from the commanded body speed and yaw rate
(`src/MPC_Ctrl/ConvexMPCLocomotion.cpp:148-185`). The node sets robot mode 1 in `__reset_robot` and then calls
`run()`, whose loop lasts until shutdown, so the following `set_robot_mode(0)` is not reached
(`scripts/walking_simulation.py:194-198`, `205`): after start-up the node runs in robot mode 1 and a standing-gait
request does not stop a walking robot. Neither request is a stop by itself; the e-stop is the sensed-confirmation stop above. No physical
emergency stop or hardware-safety claim is made.

## Fidelity contract

The deployed fake is a ROS-free `RecordingRosTransport` with canned replies. It is an analytic contract
stand-in, not a recording of captured traffic and not the upstream simulator. Engine
`analytic:ROS contract fake (canned replies; no pybullet or physics)`, level F0, determinism `none`,
`timestep_ms: 0`, `realtime_factor: 0`, reset `none`, no snapshot/restore. The upstream node's 500 Hz config
frequency, pybullet GUI mode, controller and physics loop are source facts only, not fake timing. All odometry
and IMU samples are placeholders and do not advance. The fake's `/robot_odom` position echoes the last `/cmd_vel`
linear x/y as a placeholder; the live node publishes the pybullet base pose, not the command setpoint.

## Tags

`ros`, `ros1`, `simulation`, `quadruped`, `pybullet`, `cmd-vel`, `odometry`, `imu`
