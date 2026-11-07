# Facts and tags for gh.tfly6/opendrone

Every fact cites the pinned clone at commit `3cf7779c7c8abe0cec01b7f24673ad9d4e455e4d`.
`upstream_code` refs name `path/in/clone:LINE`; bounded ranges are used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| BasePositionController subscribes /mavros/state as mavros_msgs/State and /mavros/local_position/pose as geometry_msgs/PoseStamped. | upstream_code | opendrone/src/base.cpp:19-22 |
| BasePositionController subscribes /planner/output as opendrone/PlannerOutput. | upstream_code | opendrone/src/base.cpp:23-24 |
| BasePositionController advertises geometry_msgs/PoseStamped on /mavros/setpoint_position/local and std_msgs/Int8 on /flight_state. | upstream_code | opendrone/src/base.cpp:26-28 |
| BasePositionController advertises the std_srvs/SetBool service /land. | upstream_code | opendrone/src/base.cpp:32 |
| The land callback takes std_srvs/SetBool requests and responses. | upstream_code | opendrone/src/base.cpp:277-289 |
| plannerOutputCallback ignores an empty points array, selects the first point whose valid_mask has VALID_POSITION, applies its position and, when VALID_YAW is set, its yaw; later points are ignored. | upstream_code | opendrone/src/base.cpp:291-315 |
| PlannerOutputPoint defines VALID_POSITION as 1 and VALID_YAW as 32. | upstream_code | opendrone/msg/PlannerOutputPoint.msg:3-9 |
| PlannerOutput declares a Header, trajectory_id, is_horizon, trajectory_start_time and a PlannerOutputPoint points array. | upstream_code | opendrone/msg/PlannerOutput.msg:1-7 |
| The land callback, when request.data is true, sets landing_locked_ and flight_state_ to LANDING and returns success true with the message 'base position baseline landing requested' without calling MAVROS; for false it returns success false. | upstream_code | opendrone/src/base.cpp:277-289 |
| The LANDING state calls requestAutoLand. | upstream_code | opendrone/src/base.cpp:162-164 |
| requestAutoLand sets landing_locked_, enters LANDED at once when the reported mode is already AUTO.LAND, and otherwise calls /mavros/set_mode with custom_mode AUTO.LAND and enters LANDED when the call succeeds and reports mode_sent. | upstream_code | opendrone/src/base.cpp:259-275 |
| The LANDED branch of the control loop only logs once the vehicle reports disarmed. | upstream_code | opendrone/src/base.cpp:166-170 |
| In WAITING_FOR_OFFBOARD the control loop publishes the target pose, calls trySetOffboard and tryArm, and moves to TAKEOFF (or MISSION_EXECUTION without auto_takeoff) once the vehicle reports OFFBOARD and armed; TAKEOFF and MISSION_EXECUTION keep publishing the target pose. | upstream_code | opendrone/src/base.cpp:133-160 |
| The control loop calls publishTargetPose only in WAITING_FOR_OFFBOARD, TAKEOFF and MISSION_EXECUTION; LANDING calls requestAutoLand, LANDED only logs a disarm and EMERGENCY switches to LANDING. | upstream_code | opendrone/src/base.cpp:124-176 |
| publishTargetPose stamps and publishes target_pose_ to /mavros/setpoint_position/local. | upstream_code | opendrone/src/base.cpp:179-183 |
| The base node reads geo_fence/x, geo_fence/y and geo_fence/z as private parameters with defaults 10.0, 10.0 and 7.0. | upstream_code | opendrone/src/base.cpp:43-45 |
| sitl_base_controller.launch defaults enable_sim, enable_auto_offboard, enable_auto_arm and auto_takeoff to true and sets geo_fence/x, geo_fence/y and geo_fence/z to 50.0, 50.0 and 7.0. | upstream_code | opendrone/launch/sitl_base_controller.launch:2-24 |
| poseCallback switches flight_state_ to EMERGENCY, unless it is LANDING or LANDED, when /x/ exceeds geo_fence_x_, /y/ exceeds geo_fence_y_, z exceeds geo_fence_z_ or z is below -0.2. | upstream_code | opendrone/src/base.cpp:341-348 |
| The FlightState enum numbers WAITING_FOR_CONNECTED 0, WAITING_FOR_OFFBOARD 1, TAKEOFF 2, MISSION_EXECUTION 3, LANDING 4, LANDED 5 and EMERGENCY 6. | upstream_code | opendrone/src/base.cpp:73-81 |
| The base node creates a mavros_msgs/CommandBool client on /mavros/cmd/arming and a mavros_msgs/SetMode client on /mavros/set_mode. | upstream_code | opendrone/src/base.cpp:30-31 |
| trySetOffboard returns without a mode request while landing_locked_ is set or auto-offboard is disabled. | upstream_code | opendrone/src/base.cpp:209-213 |
| tryArm returns without an arming request while landing_locked_ is set or auto-arm is disabled. | upstream_code | opendrone/src/base.cpp:234-238 |
| In WAITING_FOR_CONNECTED the control loop waits for current_state_.connected. | upstream_code | opendrone/src/base.cpp:125-131 |
| poseCallback stores the pose and reads current_pose_.pose.position x, y and z for the fence check. | upstream_code | opendrone/src/base.cpp:332-343 |
| sitl_config/px4.launch declares the fcu_url argument with the default /dev/ttyACM0:57600. | upstream_code | opendrone/sitl_config/px4.launch:5 |

## Scope

The package covers the `opendrone` `base` node: its `/planner/output` input, its
`/mavros/setpoint_position/local` and `/flight_state` publications, and its `/land`
service. The node is launched as `base` by
`opendrone/launch/sitl_base_controller.launch:12`. The rest of the repository (the
`planner_adapter`, the PX4/Gazebo SITL, MAVROS, controllers, planners, camera/LiDAR
streams, worlds and RViz configurations) is outside this package.

`/planner/output` is a publication with no acknowledgement. Its receipt reports
`published=true, confirmed=false`; it does not prove that the node received the message,
selected a point, or moved. The node publishes the latched target as a position
setpoint at a rate configured by the `publish_rate` ROS parameter. The setpoint topic
is exposed as the explicit observation `x-cap.tfly6.setpoint.v1`, not as an automatic
resource field: the base node publishes it only in WAITING_FOR_OFFBOARD, TAKEOFF and
MISSION_EXECUTION (`opendrone/src/base.cpp:133-170`), so the observation may time out
after a landing request. It is a wire observation of the last target, not proof of
arrival. The node's geo fence is built from ROS parameters `geo_fence/x`,
`geo_fence/y` and `geo_fence/z` (`opendrone/src/base.cpp:43-45`), so this driver
declares no workspace limit; an operator must configure the fence for the deployment.

## Stop semantics

The node offers no acknowledged stop. Its only landing path is the `/land` service: the callback sets
`landing_locked_ = true` and `flight_state_ = LANDING` and returns success without calling MAVROS
(`opendrone/src/base.cpp:277-289`); the control loop then asks MAVROS for `AUTO.LAND` and enters `LANDED`
on `mode_sent` alone (`base.cpp:162-170, 259-275`). That acknowledgement alone is not a stop (model review
of 2026-11-04).

Sensed-confirmation stop (SAFE-049, the user's decision of 2026-11-05, simulated devices only): the e-stop
sends `/land` (`{data: true}`) and a `/mavros/cmd/arming` disarm request (`{value: false}`, the node's own
arming client, `base.cpp:30`; PX4 refuses it in the air and the retry repeats it after touchdown), then
reads `/mavros/state` (`connected` true, `armed` false; consumed at `base.cpp:127` and `:167`) and
`/mavros/local_position/pose` (z below the landed band, x, y and z still over the window; consumed at
`base.cpp:341-343`). The landing lock stops the node's own OFFBOARD and arming requests
(`base.cpp:209-213, 234-238`). `/flight_state` is never a source (it reports `LANDED` on `mode_sent`
alone). The request steps prove nothing by themselves. The e-stop is achieved only when every source delivers three consecutive fresh samples (new subscriptions opened after the request; the first sample of each discarded; strictly increasing producer stamps; every predicate term holding; an arrival gap above `max_gap_ms` or a repeated stamp restarts the count) within `confirm_within_ms` of the first transmission. Otherwise the e-stop is `failed` `MHS.SAFETY.SAFE_STATE_UNREACHED` (`details.sensed.reason`), the latch holds and the background retry sends the request again. Thresholds are `operator_required` (the fake's placeholders are in `fixtures/estop-confirmation.json`; a live simulation supplies them in `simulation_deployment['estop_confirmation']`); the client bounds (`consecutive` 3, `min_span_ms` 200, `max_gap_ms` 500, `confirm_within_ms` 1500) are fake-scale, and a live deployment sets its own. The SDK cannot prove that the ROS graph is simulated; only a simulated device may use this profile.

Dual use: `sitl_config/px4.launch` defaults the MAVROS `fcu_url` to the serial device
`/dev/ttyACM0:57600` (`opendrone/sitl_config/px4.launch:5`); with it MAVROS drives a real PX4. That path
is out of scope: this package is a simulated device and never served as hardware.

## Safety

The device is simulated at R2 because the controller commands a flying vehicle's
position target. No hardware backend is declared, no hardware is attached, and
`driver.lock.json` keeps `reviewed_by: null`. Neither the software latch nor the `/land`
request is a stop, and neither replaces an operator's physical stop or a PX4 failsafe.
The selected `sitl_base_controller.launch` enables automatic OFFBOARD, arming and
takeoff (`opendrone/launch/sitl_base_controller.launch:2-24`); the node itself does not
check that MAVROS is connected to a simulator rather than a real flight controller. The fake's
`confirmed=false` publication result and its canned `/land` reply are contract
evidence only.

## Fidelity contract

`driver.py` describes the deployed fake: engine
`analytic:ROS-free protocol fake for the opendrone base node (no PX4 or Gazebo physics)`,
level F0, determinism `none`, `timestep_ms: 0` (event-driven replies with no physics
step), `realtime_factor: 0` (not paced), reset `none`, and no snapshot/restore. The
state, pose, target and flight-state samples are placeholders. The gaps disclose the
absent PX4/Gazebo/MAVROS execution, the transmission-only publication, the landing
request that is not a touchdown, the unenforced configurable fence, and the
uncovered trajectory/velocity/camera/LiDAR surface. The fake snaps its placeholder
local pose to the published target so the resource changes; that is a placeholder
effect, not integrated motion or arrival.

## Tags

`ros`, `ros1`, `px4`, `sitl`, `uav`, `position-controller`, `simulation`
