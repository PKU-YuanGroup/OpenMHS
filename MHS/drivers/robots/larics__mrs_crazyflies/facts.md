OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of an Anthropic research preview.

# Facts and tags for gh.larics/mrs_crazyflies

Every fact cites the pinned clone at commit `234ac04745a558601e539ce9aa33b72b4e760243`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the statement spans
adjacent lines. The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README documents velocity commands on /cf_x/cmd_vel, pose on /cf_x/pose, and velocity on /cf_x/velocity as the custom LogDataGeneric message whose elements are v_x, v_y and v_z in a world frame. | vendor_doc | README.md:69 |
| The README documents takeoff and land services /cf_x/takeoff and /cf_x/land and says the current vel_mux takes off automatically after the first cmd_vel command. | vendor_doc | README.md:70 |
| The README teleop example remaps cmd_vel to the concrete topic /cf_1/cmd_vel. | vendor_doc | README.md:120 |
| The simulation is Gazebo Ignition and uses ROS 2 packages based on CrazySwarm2. | vendor_doc | README.md:4 |
| The configuration enables cf_1 as type cf_sim with a UDP URI and initial_position [-0.5, -4.0, 0.0]. | upstream_code | config/crazyflies_mrs.yaml:14-18 |
| The launch file starts one vel_mux node per robot index from 1 to NUM_ROBOTS (default 4); the first runs in namespace cf_1 with incoming_twist_topic cmd_vel and robot_prefix /cf_1. | upstream_code | launch/cf_velmux_launch.py:64-75 |
| The Dockerfile removes the crazyswarm2 crazyflie_server.py and copies to_copy/crazyflie_server.py in its place. | upstream_code | Dockerfile:176-179 |
| A commented template robot entry in the configuration uses the URI radio://0/80/2M/E7E7E7E7E7 with type cf. | upstream_code | config/crazyflies_mrs.yaml:3-9 |
| The copied server maps the default log name pose to PoseStamped. | upstream_code | to_copy/crazyflie_server.py:93 |
| The copied server creates a default log publisher on cf_name + "/" + prefix only when logging is enabled for that prefix and for the robot; otherwise it stores "empty". | upstream_code | to_copy/crazyflie_server.py:403-407 |
| The pose callback builds a PoseStamped from stateEstimate.x, stateEstimate.y, stateEstimate.z and a quaternion derived from the stabilizer angles. | upstream_code | to_copy/crazyflie_server.py:598-623 |
| The copied server creates a LogDataGeneric publisher on cf_name + "/" + log_group_name for custom log topics. | upstream_code | to_copy/crazyflie_server.py:510-512 |
| The cf_sim type defines a custom topic named velocity at 10 Hz with the variables kalman.statePX, kalman.statePY and kalman.statePZ. | upstream_code | config/crazyflies_mrs.yaml:181-184 |
| The copied server creates an Empty service on name + "/emergency" for each Crazyflie. | upstream_code | to_copy/crazyflie_server.py:290-293 |
| The copied server creates the swarm-wide all/emergency Empty service. | upstream_code | to_copy/crazyflie_server.py:360 |
| The emergency callback calls loc.send_emergency_stop() for every selected Crazyflie URI and returns the service response. | upstream_code | to_copy/crazyflie_server.py:888-895 |
| The pose callback sets pose.position x, y and z from stateEstimate.x, y and z. | upstream_code | to_copy/crazyflie_server.py:606-619 |
| The pose callback stamps the PoseStamped header with the node clock. | upstream_code | to_copy/crazyflie_server.py:615 |
| The cf_sim robot type enables firmware logging with the default pose topic at frequency 10. | upstream_code | config/crazyflies_mrs.yaml:165-180 |

The PoseStamped name mapping is at `to_copy/crazyflie_server.py:93`; the concrete publisher is
built as `self.cf_dict[link_uri] + "/" + prefix` at `to_copy/crazyflie_server.py:403-407`. The
`pose` read binding uses the literal relative name from line 93, so a deployment that changes the
Crazyflie name or namespace must expose the resolved `/cf_1/pose` endpoint. The launch file
already places vel_mux in the `cf_1` namespace (`launch/cf_velmux_launch.py:64-75`), and the README
teleop example names the resolved `/cf_1/cmd_vel` (`README.md:120`).

## Scope

The pinned repository is an ament_cmake ROS 2 package of Gazebo/CrazySim launch and configuration
files. It installs its Python transform node, launch files and config
(`CMakeLists.txt:32-43`); the running `crazyflie_server` and `vel_mux` nodes are provided by the
external `crazyflie` package (`launch/cf_velmux_launch.py:47-78`). The clone carries a copy of the
server source under `to_copy/`; this package's CMakeLists does not install it, but the recommended
Docker image replaces the crazyswarm2 server with it (`Dockerfile:176-179`), so in that deployment
the copy is the running server. This package integrates the documented ROS 2 wire interface, not a
local node implementation. A commented configuration template uses a Crazyradio URI with the `cf`
robot type (`config/crazyflies_mrs.yaml:3-9`): with such an entry named `cf_1` the same server,
topics and service drive a real Crazyflie.

The served primary control is one geometry_msgs/Twist publication on `/cf_1/cmd_vel`. The README
says the current vel_mux takes off automatically after the first cmd_vel command and that vel_mux
converts the incoming Twist. The clone does not contain `vel_mux.py`, so the conversion and the
external node's consumption of the message are NOT COVERED. The pose observation on `/cf_1/pose`
is a PoseStamped position extracted from `pose.position`; orientation, TF, odometry, scan, status,
per-drone takeoff/land, logging configuration and the velocity custom log topic are NOT COVERED.
The takeoff and land services documented in `README.md:70` are not bound: the copied server builds
their per-drone names as `name + "/takeoff"` and `name + "/land"`, and this package does not invent
a concrete citation for those constructed literals.

## Limits

The clone declares geometry_msgs/Twist velocity commands but states no numeric operating envelope
for their linear or angular components. Every velocity component is therefore
`Limit.operator_required`: without an operator overlay each call is refused
`MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` is an illustrative operator overlay only,
not a device fact, a flight envelope or a recommendation; a real site must replace it with its own
assessed values. `fixtures/conformance.json` supplies the gate's valid, alternate and
out-of-envelope inputs. No bound was copied from a catalogue class default or an upstream
constructor default.

## Sensed-confirmation stop (SAFE-049)

The user's decision of 2026-11-05 allows a request plus a sensed confirmation as the stop of a simulated
device. The e-stop calls the swarm-wide `/all/emergency` service (`to_copy/crazyflie_server.py:360`, callback
`:888-895`), then reads `/cf_1/pose` (z below the on-ground band, x, y and z still over the window; filled
from the state estimate at `:617-619`, stamped at `:615`; the cf_sim type logs pose at 10 Hz,
`config/crazyflies_mrs.yaml:176-180`). The request steps prove nothing by themselves. The e-stop is achieved only when every source delivers three consecutive fresh samples (new subscriptions opened after the request; what a new subscription may receive from before it existed never counts: the `/cf_1/pose` publisher is created with the integer depth 10 and so rclpy's default volatile durability (`to_copy/crazyflie_server.py:404-405`, the declared `history`), which keeps nothing for a late subscriber, and the first sample is discarded all the same; strictly increasing producer stamps; every predicate term holding; an arrival gap above `max_gap_ms` or a repeated stamp restarts the count) within `confirm_within_ms` of the first transmission. Otherwise the e-stop is `failed` `MHS.SAFETY.SAFE_STATE_UNREACHED` (`details.sensed.reason`), the latch holds and the background retry sends the request again. Thresholds are `operator_required` (the fake's placeholders are in `fixtures/estop-confirmation.json`; a live simulation supplies them in `simulation_deployment['estop_confirmation']`); the client bounds (`consecutive` 3, `min_span_ms` 200, `max_gap_ms` 500, `confirm_within_ms` 1500) are fake-scale, and a live deployment sets its own. The SDK cannot prove that the ROS graph is simulated; only a simulated device may use this profile.

The stop is swarm-wide: every enabled simulated Crazyflie (cf_1 to cf_4 by default) is asked to cut its
motors and falls. The per-drone `name + "/emergency"` service (`:290-293`) is not used because gate G7
cannot match its concatenated endpoint literal. Nothing in the clone undoes the motor cut, so the e-stop is
terminal (`estop_terminal`, CORE-087): every later reset on the endpoint is refused. A Crazyradio URI in
the configuration (`config/crazyflies_mrs.yaml:3-9`) drives a real Crazyflie with the same server: that
path is out of scope and never served.

## Safety

Mode is `simulated`, device kind `robot.mobile_base`, risk `R2`: the command surface is a
velocity-controlled UAV transit, which is a mobile-base motion at R2 even in simulation, and a
configuration change makes it a real Crazyflie; the card floor is R0. The package declares no acknowledged e-stop binding and no safe-state action (model review, 2026-11-05);
its e-stop is the sensed-confirmation stop above. The only stop-like path in the
copied server is the `/all/emergency` `std_srvs/Empty` service, whose callback calls
`loc.send_emergency_stop()` (cflib, outside the clone) for each selected URI and returns the
response (`to_copy/crazyflie_server.py:888-895`). That response is a callback acknowledgement of a
motor-cut request: nothing in the clone confirms that a packet arrived or what the firmware does
with it, and a motor cut in flight drops the vehicle. A callback acknowledgement alone does not certify a stop. `request_emergency_stop` remains an ordinary action whose output
`accepted` means only that the response arrived. No independent hardware e-stop is documented in
the clone, and `estop_physical_ref` is not set.

## Fidelity

`driver.py` describes the deployed fake: engine `analytic:ROS-free contract fake for the
mrs_crazyflies ROS 2 endpoints (no physics)`, level F0, determinism `none`, `timestep_ms: 0`,
`realtime_factor: 0`, reset `none`, no snapshot/restore. The fake is a ROS-free
`RecordingRosTransport`, not a recording of captured traffic and not the upstream simulator. It
runs no Gazebo Ignition world, CrazySim firmware, CrazySwarm2 node, vel_mux or UAV. The fake
updates a placeholder pose by a fixed offset per Twist publication and emits it on each
subscription; that is event-driven placeholder behavior with no physics step, controller or
wall-clock pacing. All state and reply values are placeholders, and the pose header uses the
ROS 2 stamp fields `sec`/`nanosec`. The `/all/emergency` acknowledgement is not a stop proof, and no live ROS graph, rosbridge peer, Gazebo simulation,
colcon build or hardware was run.

## Tags

`ros`, `ros2`, `crazyflie`, `uav`, `simulation`, `gazebo`, `crazyswarm2`, `larics`
