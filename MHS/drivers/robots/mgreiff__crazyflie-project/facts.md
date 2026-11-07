OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.mgreiff/crazyflie-project

Every fact cites the pinned clone at commit `4b7f8281e86d6eb72952242577350bb2c4efd181`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the statement
spans adjacent lines. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| Master creates a rospy.Publisher on the absolute /crazyflie/cmd_vel topic with geometry_msgs/Twist and queue size 1. | upstream_code | crazyflie_trajectory/scripts/master.py:29 |
| Master creates a rospy.Publisher on the absolute /crazyflie/trajectory_packet topic with crazyflie_trajectory/TrajectoryPacket and queue size 100. | upstream_code | crazyflie_trajectory/scripts/master.py:30 |
| Master creates a rospy.Publisher on the absolute /crazyflie/synchronization_packet topic with crazyflie_trajectory/SynchronizationPacket and queue size 100. | upstream_code | crazyflie_trajectory/scripts/master.py:32 |
| Master creates a rospy.ServiceProxy on the absolute /crazyflie/update_params service with crazyflie_trajectory/UpdateParams. | upstream_code | crazyflie_trajectory/scripts/master.py:35 |
| Master creates a rospy.ServiceProxy on the absolute /crazyflie/emergency service with std_srvs/Empty. | upstream_code | crazyflie_trajectory/scripts/master.py:36 |
| The transfer loop sends every packet in data['packets'] twenty times, sleeping 5 ms between publications. | upstream_code | crazyflie_trajectory/scripts/master.py:107-117 |
| synchronize_trajectory copies circular and number from the trajectory and fills all four SynchronizationPacket time slots with the same float start delay. | upstream_code | crazyflie_trajectory/scripts/master.py:54-60 |
| The master help text identifies 'q' as 'Calls emergency service' and 't' as 'Transfer a trajectory file to the UAV'. | upstream_code | crazyflie_trajectory/scripts/master.py:130-133 |
| TrajectoryPacket declares float32[6] data, float32 time and the uint8 fields index, dimension, number and type. | upstream_code | crazyflie_trajectory/msg/TrajectoryPacket.msg:1-6 |
| SynchronizationPacket declares uint8 synchronize, uint8[4] circular, uint8[4] number and float32[4] time. | upstream_code | crazyflie_trajectory/msg/SynchronizationPacket.msg:1-4 |
| UpdateParams has a string[] params request and an empty response. | upstream_code | crazyflie_trajectory/srv/UpdateParams.srv:1-2 |
| Converter subscribes to the absolute /crazyflie/log_ref topic with crazyflie_trajectory/GenericLogData | upstream_code | crazyflie_trajectory/scripts/converter.py:24 |
| Trajectory sets nDim to 4 and timeStep to 0.02, evaluating at 50 Hz as in the firmware. | upstream_code | crazyflie_trajectory/modules/trajectorylib.py:37-40 |
| trajectoryExample.launch defaults the uri argument to radio://0/35/2M, includes the external crazyflie_driver crazyflie_server.launch and starts crazyflie_add with that uri in the crazyflie namespace. | upstream_code | crazyflie_trajectory/launch/trajectoryExample.launch:7-19 |
| trajectoryExample.launch configures crazyflie_add with the generic log topics log_ref, log_pos, log_errors and log_cacheB at 10 each, log_ref carrying the reference x, y, z, roll, pitch and yaw variables. | upstream_code | crazyflie_trajectory/launch/trajectoryExample.launch:21-23 |
| trajectoryExample.launch starts the master node of crazyflie_trajectory. | upstream_code | crazyflie_trajectory/launch/trajectoryExample.launch:30-35 |
| The README lists a Crazyflie driver modified from the original for communicating with the crazyflie and a Crazyflie firmware modified to support SE(3) control as dependencies. | upstream_code | README.md:9-10 |
| The master command loop calls the emergency service proxy for the q keyword. | upstream_code | crazyflie_trajectory/scripts/master.py:174-176 |

## Scope

The package exposes the `master.py` wire contract: one `TrajectoryPacket` publication, one
`SynchronizationPacket` publication, one `geometry_msgs/Twist` publication on
`/crazyflie/cmd_vel`, the acknowledged `/crazyflie/update_params` service and the acknowledged
`/crazyflie/emergency` `std_srvs/Empty` service. The three topics are absolute names in the
clone. The two service endpoints are also absolute in the clone; a namespaced deployment must
expose or remap the same resolved endpoints.

One action publishes one ROS message. The upstream `transfer_trajectory` path sends a
synchronization packet and then republishes every packet twenty times with a 5 ms sleep
(`crazyflie_trajectory/scripts/master.py:103-120`). The driver does not reproduce that loop, so
a complete trajectory upload is NOT COVERED. The driver exposes the converter's
`/crazyflie/log_ref` subscription as the read-only `log_ref` resource state, but it does not
expose the converter's `/crazyflie/log_pos` observation or its file output
(`crazyflie_trajectory/scripts/converter.py:23-25,37-46`); those are NOT COVERED. The fake copies
the six trajectory-packet coefficients into the placeholder `log_ref` values so the resource has
an observable effect; that is not dynamics, a measured pose or a reference-pose model.

The clone imports `geometry_msgs/Twist` but does not define the message; the standard
`linear`/`angular` `Vector3` layout is therefore used by the publication binding. This is a
message-layout convention, not an upstream numeric fact. `master.py` creates the `cmd_vel`
publisher but never publishes on it, so the clone states no meaning or unit for the Twist fields;
the external driver decides what they command, and the package claims no unit (reviewer r20).

Every bound topic and service is an input of the external, modified `crazyflie_ros` driver, which
`trajectoryExample.launch` starts (`crazyflie_server.launch` and `crazyflie_add` with the Crazyradio
URI `radio://0/35/2M`) for a real Crazyflie; the README lists that driver and a modified firmware
as dependencies. The clone contains no ROS simulator (its simulation is MATLAB/Simulink), so the
registry record's mode `simulated` does not describe this ROS route.

## Limits

No text file of the clone states a numeric operating envelope for the trajectory coefficients,
durations, selectors, synchronization metadata or velocity components. Every physical quantity
and packet selector is therefore `Limit.operator_required`: without an operator overlay each
call is refused `MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` is an illustrative
operator overlay, not a device fact and not a flight envelope; a real site must replace it with
its own assessed values. `fixtures/conformance.json` supplies the gate's valid, alternate and
out-of-envelope inputs.

## Safety

Mode is declared `simulated` (the card's mode; the ROS route is a real Crazyflie's, see Scope),
device kind `device`, risk `R2`. The package is blocked (`NO_HARDWARE_FREE_PATH`, reviewer r20):
the only stop path is the `/crazyflie/emergency` `std_srvs/Empty` service, whose callback is in the
external `crazyflie_ros` driver; the clone defines only the proxy (`master.py:36`) and calls it for
the `q` keyword. Nothing in the clone shows what the Crazyflie is left in, so the service is not
bound as the e-stop and `request_emergency` is an ordinary command. The e-stop fails
`MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held, which only refuses this driver's commands;
a transferred trajectory and the last command stay with the external driver and firmware. No
independent hardware e-stop is documented in the clone, and `estop_physical_ref` is not set.

## Fidelity

`driver.py` describes the deployed fake: engine `analytic:ROS-free recording fake ...`,
level F0, determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`, reset `none`, no
snapshot/restore. The fake is a ROS-free `RecordingRosTransport`, not a recording of captured
traffic and not the upstream simulator. It runs no `crazyflie_ros` node, controller, Simulink
model or UAV; it reproduces neither the 20-times packet loop nor the 5 ms pacing. All recorded
state and reply values are placeholders.

## Tags

`ros`, `ros1`, `crazyflie`, `uav`, `trajectory`, `simulation`
