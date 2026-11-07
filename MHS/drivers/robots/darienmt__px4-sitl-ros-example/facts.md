# Facts and tags for gh.darienmt/px4-sitl-ros-example

Every fact cites the pinned clone at commit `60dc45513f635ca9a53a0bf1883ea76c25a0eb3f`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the statement spans
adjacent lines. The same facts are written into `driver.py` (`facts = [...]`); `reference.json` is
generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| offb_node subscribes the relative mavros/state topic with mavros_msgs::State and queue size 10. | upstream_code | src/offb/src/offb_node.cpp:23-24 |
| offb_node includes the generated mavros_msgs/State header. | upstream_code | src/offb/src/offb_node.cpp:11 |
| offb_node advertises geometry_msgs::PoseStamped on the relative mavros/setpoint_position/local topic with queue size 10. | upstream_code | src/offb/src/offb_node.cpp:25-26 |
| offb_node includes the generated geometry_msgs/PoseStamped header. | upstream_code | src/offb/src/offb_node.cpp:8 |
| offb_node declares a geometry_msgs::PoseStamped pose, sets only pose.pose.position.x, y and z, to 0, 0 and 2, and publishes that pose unchanged. | upstream_code | src/offb/src/offb_node.cpp:41-80 |
| The offb node's comment states the setpoint publishing rate must be faster than 2 Hz and constructs ros::Rate(20.0). | upstream_code | src/offb/src/offb_node.cpp:32-33 |
| offb_node publishes the pose 100 times, spinning and sleeping on the rate each time, under the comment 'send a few setpoints before starting'. | upstream_code | src/offb/src/offb_node.cpp:46-51 |
| offb_node creates a mavros_msgs::CommandBool client on the relative mavros/cmd/arming name and a mavros_msgs::SetMode client on the relative mavros/set_mode name. | upstream_code | src/offb/src/offb_node.cpp:27-30 |
| In its loop offb_node sends the custom_mode OFFBOARD request when the reported mode is not OFFBOARD and more than 5 s have passed since the last request, otherwise sends the arming request with value true when the vehicle is not armed and more than 5 s have passed, and publishes the pose on every cycle. | upstream_code | src/offb/src/offb_node.cpp:53-84 |
| offb.launch includes px4's mavros_posix_sitl.launch and starts the offb node (type offb_node). | upstream_code | src/offb/launch/offb.launch:3-5 |
| offb_velocity.launch includes px4's mavros_posix_sitl.launch and starts the offb_velocity node (type node). | upstream_code | src/offb_velocity/launch/offb_velocity.launch:3-5 |
| Drone::Drone advertises mavros_msgs::PositionTarget on the relative mavros/setpoint_raw/local topic with queue size 10. | upstream_code | src/offb_velocity/src/drone_offboard.cpp:11 |
| Drone::Drone creates a mavros_msgs::CommandTOL client on /mavros/cmd/takeoff. | upstream_code | src/offb_velocity/src/drone_offboard.cpp:12 |
| Drone::Drone creates a mavros_msgs::SetMode client on the relative mavros/set_mode name. | upstream_code | src/offb_velocity/src/drone_offboard.cpp:13 |
| Drone::Drone creates a mavros_msgs::CommandTOL client on /mavros/cmd/land. | upstream_code | src/offb_velocity/src/drone_offboard.cpp:14 |
| Drone::Drone includes the generated mavros_msgs/PositionTarget header. | upstream_code | src/offb_velocity/src/drone_offboard.cpp:5 |
| Drone::arm creates a mavros_msgs::CommandBool client on /mavros/cmd/arming, sets request.value to true and returns the response success flag. | upstream_code | src/offb_velocity/src/drone_offboard.cpp:29-35 |
| Drone::setOffboardMode sets request.custom_mode to OFFBOARD and returns the response mode_sent flag. | upstream_code | src/offb_velocity/src/drone_offboard.cpp:73-80 |
| Drone::land returns false without a call while home_set_ is false; otherwise it sends an empty mavros_msgs::CommandTOL request to the land client and returns the response success flag. | upstream_code | src/offb_velocity/src/drone_offboard.cpp:57-71 |
| Drone::setOffboardVelocityBody sets coordinate_frame FRAME_BODY_NED and the type_mask IGNORE_PX, IGNORE_PY, IGNORE_PZ, IGNORE_AFX, IGNORE_AFY, IGNORE_AFZ, FORCE and IGNORE_YAW, sets velocity x, y and z and yaw_rate, and publishes the message count times with a rate_.sleep() after each. | upstream_code | src/offb_velocity/src/drone_offboard.cpp:128-147 |
| Drone::setOffboardVelocityNED sets coordinate_frame FRAME_LOCAL_NED and the type_mask IGNORE_PX, IGNORE_PY, IGNORE_PZ, IGNORE_AFX, IGNORE_AFY, IGNORE_AFZ, FORCE and IGNORE_YAW_RATE, sets velocity x, y and z and yaw, and publishes the message count times with a rate_.sleep() after each. | upstream_code | src/offb_velocity/src/drone_offboard.cpp:149-167 |
| The velocity example logs 'NED: Move towards South' before a setOffboardVelocityNED call with vy -2 and 'NED: Go Up' before one with vz 2. | upstream_code | src/offb_velocity/src/offb_velocity_node.cpp:145-152 |
| The velocity example logs 'Body: Turn around yaw clockwise and climb' before a setOffboardVelocityBody call with vz 1 and yaw_rate -60, and 'Body: Turn yaw anti-clockwise' before one with yaw_rate 60. | upstream_code | src/offb_velocity/src/offb_velocity_node.cpp:116-120 |
| Drone::toRadFromDeg returns deg / 180 * M_PI as a float. | upstream_code | src/offb_velocity/src/drone_offboard.cpp:123-126 |
| Drone::getAltitude subscribes /mavros/altitude with mavros_msgs::Altitude and spins while altitude_received_ is false. | upstream_code | src/offb_velocity/src/drone_offboard.cpp:105-114 |
| The drone_offboard header includes the generated mavros_msgs/Altitude header. | upstream_code | src/offb_velocity/include/drone_offboard.h:5 |
| The velocity node arms, takes off, runs the NED and body velocity sequences and then calls land. | upstream_code | src/offb_velocity/src/offb_velocity_node.cpp:16-66 |
| After the land service call the velocity node sleeps for five seconds, shuts ROS down and returns; it reads no landed state and sends no disarm request. | upstream_code | src/offb_velocity/src/offb_velocity_node.cpp:59-70 |
| offb_node waits in a loop while current_state.connected is false before it sends setpoints. | upstream_code | src/offb/src/offb_node.cpp:35-39 |
| Drone::getAltitudeCB stores the message and copies altitude_.amsl into altitude_in_amsl_. | upstream_code | src/offb_velocity/src/drone_offboard.cpp:116-121 |
| drone_offboard.cpp includes the generated mavros_msgs/CommandBool and mavros_msgs/CommandTOL headers. | upstream_code | src/offb_velocity/src/drone_offboard.cpp:2-3 |

## Scope

The package exposes the MAVROS interfaces the clone's `offb` and `offb_velocity` examples use. The
upstream nodes use relative names (`mavros/state`, `mavros/setpoint_position/local`,
`mavros/setpoint_raw/local`, `mavros/set_mode`) and absolute names (`/mavros/altitude`,
`/mavros/cmd/arming`, `/mavros/cmd/land`). The shipped launch files start both nodes without a
namespace, so the relative names resolve at the ROS root and the driver configures the resolved
absolute endpoints with `source_name` recording the upstream relative token. A deployment that
namespaces the MAVROS node differently must expose the same resolved endpoints or remap them; the
driver does not guess a namespace.

The shipped `offb.launch` and `offb_velocity.launch` each include px4's `mavros_posix_sitl.launch`
and also start one of the clone's nodes: `offb_node`, which streams the (0, 0, 2) hover setpoint at
20 Hz and requests OFFBOARD and arming again every 5 s whenever the vehicle is not in OFFBOARD or not
armed, or the velocity node, which runs its own arm, takeoff, velocity and land sequence. Both compete
with this driver for the same topics and services, so an MHS deployment starts PX4 SITL with MAVROS
only (model review of 2026-11-04).

The velocity inputs are written into the PositionTarget unchanged. The clone's examples use the
ROS-side signs MAVROS receives: its FRAME_LOCAL_NED sequence logs vz 2 as "Go Up" and vy -2 as "Move
towards South", and its body sequence logs vz 1 with yaw_rate -60 deg/s as "climb" and "clockwise".
MAVROS's frame conversion is outside the clone; the driver performs none.

The `trajectory` packages contain a bare node skeleton and launch/world files; they expose no
additional control contract and are not integrated. `takeoff` is not exposed because the clone's
`Drone::takeoff` copies the live AMSL altitude and home latitude/longitude into the request, and no
text states a fixed takeoff altitude or a numeric takeoff envelope.

## Sensed-confirmation stop (SAFE-049)

The user's decision of 2026-11-05 allows a request plus a sensed confirmation as the stop of a simulated
device. The e-stop sends the clone's default-constructed `CommandTOL` land request (`drone_offboard.cpp:65-67`)
and a `CommandBool` disarm request (`{value: false}` on the clone's arming endpoint, `drone_offboard.cpp:29`;
PX4 refuses it in the air and the retry repeats it after touchdown), then reads `mavros/state` (`connected`
true, `armed` false; consumed at `offb_node.cpp:36` and `:70`) and `/mavros/altitude` (AMSL still over the
window; consumed at `drone_offboard.cpp:120`). The request steps prove nothing by themselves. The e-stop is achieved only when every source delivers three consecutive fresh samples (new subscriptions opened after the request; the first sample of each discarded; strictly increasing producer stamps; every predicate term holding; an arrival gap above `max_gap_ms` or a repeated stamp restarts the count) within `confirm_within_ms` of the first transmission. Otherwise the e-stop is `failed` `MHS.SAFETY.SAFE_STATE_UNREACHED` (`details.sensed.reason`), the latch holds and the background retry sends the request again. Thresholds are `operator_required` (the fake's placeholders are in `fixtures/estop-confirmation.json`; a live simulation supplies them in `simulation_deployment['estop_confirmation']`); the client bounds (`consecutive` 3, `min_span_ms` 200, `max_gap_ms` 500, `confirm_within_ms` 1500) are fake-scale, and a live deployment sets its own. The SDK cannot prove that the ROS graph is simulated; only a simulated device may use this profile.

A running `offb_node` requests OFFBOARD and arming again every 5 s (`offb_node.cpp:59-84`) and undoes a
confirmed stop; a reset re-confirms without a request and is refused then, but nothing prevents it. MAVROS
drives a real PX4 with another `fcu_url`: that path is out of scope and never served.

## Safety

The device is a simulated PX4 SITL multirotor commanded through MAVROS. The driver is declared at R2
because its setpoint and arming commands can move a flying vehicle. The clone's only landing path is
the acknowledged `/mavros/cmd/land` `CommandTOL` request; its success flag acknowledges a LAND request,
not touchdown, disarm or sensed quiescence. The clone's own post-land path only sleeps for five seconds,
shuts ROS down and returns (`offb_velocity_node.cpp:59-70`); it reads no landed state and sends no
disarm request, and a running `offb_node` would request OFFBOARD again within 5 s
(`offb_node.cpp:53-84`).

Model review of 2026-11-04: a LAND request alone is not a stop, so `/mavros/cmd/land` stays an ordinary
command and no `safe_state=True` action exists; the e-stop is the sensed-confirmation stop above.

No `site_limits` value in `site-limits.example.json` is a device fact. Without an operator overlay
every numeric setpoint is refused with `MHS.SAFETY.LIMITS_UNSET`, because the clone states no numeric
workspace or velocity envelope.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS-free recording fake for the
MAVROS/PX4 SITL contract (no physics)`, level F0, determinism `none`, `timestep_ms: 0`,
`realtime_factor: 0`, reset `none`, and no snapshot/restore. The fake answers the declared
subscriptions and services and records the publications; it runs no PX4 SITL, Gazebo, MAVROS,
controller loop or timer. It snaps its placeholder AMSL altitude to the z of a published position
setpoint so the resource state changes, but it integrates no motion and makes no arrival claim. A
single rosbridge publication is not the clone's continuous 20 Hz or 10 Hz setpoint stream.

## Tags

`ros`, `ros1`, `px4`, `sitl`, `gazebo`, `mavros`, `uav`, `simulation`
