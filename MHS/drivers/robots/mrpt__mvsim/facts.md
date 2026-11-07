# Facts and tags for gh.mrpt/mvsim

Every fact cites the pinned clone at commit `cfaf9f28f57fe5798a6b1defa65a435402bd38d0` as `path/in/clone:LINE` (or a
bounded range). The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the
driver, not from this page.

Tags: `mvsim`, `simulation`, `mobile-base`, `zmq`, `protobuf`, `twist`.

## Facts

| fact | source | ref |
|---|---|---|
| srv_set_controller_twist locks simulationStepRunningMtx_, answers success false with an error message when the object is not found, is not a VehicleBase or has no controller, passes the requested vx, vy and wz to the controller's setTwistCommand, and answers success true only when the controller accepted the twist. | upstream_code | modules/simulator/src/World_services.cpp:124-170 |
| srv_get_pose answers success with the pose, the twist (vx, vy and omega; vz, wx and wy written as 0) and whether copy_of_objects_had_collision_ holds the object, or success false when the object is unknown; after answering it adds the object to reset_collision_flags_. | upstream_code | modules/simulator/src/World_services.cpp:78-122 |
| In its post-step processing, which copies every object's dynamic state for service calls, the simulator adds each object whose hadCollision flag is set to copy_of_objects_had_collision_, then calls resetCollisionFlag on every object in reset_collision_flags_ and clears that set. | upstream_code | modules/simulator/src/World_simul.cpp:224-269 |
| Simulable::hadCollision reports whether a collision occurred since the flag was last reset, and resetCollisionFlag resets it to false. | upstream_code | modules/simulator/include/mvsim/Simulable.h:136-142 |
| The ROS node reads a vehicle's hadCollision flag, calls resetCollisionFlag and publishes the value it read on that vehicle's collision publisher. | upstream_code | mvsim_node_src/mvsim_node.cpp:1120-1130 |
| World::internal_advertiseServices advertises set_pose, get_pose, set_controller_twist, shutdown, set_light_state and get_light_state on the simulator's ZMQ client. | upstream_code | modules/simulator/src/World_services.cpp:251-273 |
| ControllerBaseInterface::setTwistCommand takes setpoints for linear (vx) velocity in m/s and angular (omega) velocity in rad/s, ignores vy, and returns false (twist commands unsupported) unless a controller overrides it. | upstream_code | modules/simulator/include/mvsim/ControllerBase.h:44-54 |
| The differential drive's twist_pid controller stores the twist setpoint and returns true. | upstream_code | modules/simulator/include/mvsim/VehicleDynamics/VehicleDifferential.h:151-158 |
| The differential drive's twist_ideal controller sets the vehicle twist to the setpoint perfectly and instantaneously; its setTwistCommand stores the setpoint and returns true. | upstream_code | modules/simulator/include/mvsim/VehicleDynamics/VehicleDifferential.h:179-203 |
| The differential drive's trajectory controller does not override setTwistCommand. | upstream_code | modules/simulator/include/mvsim/VehicleDynamics/VehicleDifferential.h:243-262 |
| SrvSetControllerTwist carries the required objectId (field 1) and twistSetPoint (field 2). | upstream_code | modules/msgs/proto/SrvSetControllerTwist.proto:7-11 |
| Twist carries the required doubles vx, vy, vz, wx, wy and wz as fields 1 to 6. | upstream_code | modules/msgs/proto/Twist.proto:5-12 |
| SrvSetControllerTwistAnswer carries the required success (field 1) and an optional errorMessage (field 2). | upstream_code | modules/msgs/proto/SrvSetControllerTwistAnswer.proto:5-10 |
| SrvGetPoseAnswer carries success (1), errorMessage (2), pose (3), objectIsInCollision (4) and twist (5). | upstream_code | modules/msgs/proto/SrvGetPoseAnswer.proto:8-18 |
| The generated Python binding of mvsim::Client exposes callService, which passes a serialised request as bytes to Client::callService and returns the serialised answer as bytes; the binding does not release the GIL around the call. | upstream_code | modules/comms/python/generated-sources-pybind/mvsim/Comms/Client.cpp:74-87 |
| Client::doCallService asks the server for the service's endpoint, then sends a CallService message to it and waits for the reply. | upstream_code | modules/comms/src/Comms/Client.cpp:735-808 |
| mvsim::receiveMessage waits on the ZMQ socket's recv with no timeout argument. | upstream_code | modules/comms/src/Comms/common.cpp:63-73 |
| The client's service thread answers a request for an unknown service with a GenericAnswer whose success is false. | upstream_code | modules/comms/src/Comms/Client.cpp:565-580 |
| mvsim-teleop.py builds a SrvSetControllerTwist for robot 'r1' with vx and vy in m/s and w in rad/s and sends it with callService('set_controller_twist', ...). | upstream_code | examples_python/mvsim-teleop.py:17-40 |
| The tutorial world demo_2robots names its first vehicle r1. | upstream_code | mvsim_tutorial/demo_2robots.world.xml:47 |
| The ROS node's cmd_vel callback also calls the vehicle controller's setTwistCommand. | upstream_code | mvsim_node_src/mvsim_node.cpp:934-942 |
| The ROS node zeroes a vehicle's twist with setTwistCommand({0, 0, 0}) once its last ROS cmd_vel is older than MAX_CMD_VEL_AGE_SECONDS, tracked only for vehicles that received a ROS cmd_vel. | upstream_code | mvsim_node_src/mvsim_node.cpp:525-540 |
| The default server port is 23700, or MVSIM_SERVER_PORT when it holds a valid port number. | upstream_code | modules/comms/include/mvsim/Comms/ports.h:20-49 |

## Scope

One vehicle of an MVSim simulation, named by the backend option `vehicle` (default `r1`, the name the clone's teleop
example and tutorial worlds use), through MVSim's own ZMQ/protobuf services rather than its ROS node:

- `x-cap.mrpt.mvsim_controller_twist.v1`: one twist setpoint (`vx` in m/s, `wz` in rad/s; `vy` is sent as 0, which the
  controllers ignore) through `set_controller_twist`. The receipt completes only when MVSim answered that the
  controller accepted the setpoint, and reports that setpoint; the setpoint persists until another command.
- `x-cap.mrpt.mvsim_pose.v1`: the vehicle's pose, twist and collision flag through `get_pose`. The read has a side
  effect on simulator state: after answering, `get_pose` queues the vehicle for a collision-flag reset
  (World_services.cpp:115-120), and the next simulation step calls its `resetCollisionFlag` (World_simul.cpp:260-269).
  The flag that `get_pose` reports is not the one it resets: `objectIsInCollision` says whether
  `copy_of_objects_had_collision_` holds the vehicle (World_services.cpp:108), a record that the step adds to
  (World_simul.cpp:254-256) and that no code in the clone removes from, so it stays true after the first recorded
  collision. The vehicle's own `hadCollision` flag, which the read resets, is the one the ROS node publishes on its
  collision topic and then resets (mvsim_node.cpp:1120-1130), and the one `set_pose` answers with
  (World_services.cpp:68-69): a pose read can therefore clear a collision before another client reports it.
- The e-stop: a zero twist through `set_controller_twist`, checked like any setpoint.

Not covered: `set_pose`, `shutdown`, the light services, MVSim topics, the ROS node, other vehicles and objects of the
world.

## Limits

MVSim states no bound for a twist setpoint, so `vx` and `wz` are `operator_required`: every setpoint is refused with
`MHS.SAFETY.LIMITS_UNSET` until the operator's `site-limits.json` bounds them. `site-limits.example.json` is example
operator data for the gate's conformance run, not a fact.

## Safety

The device is a simulated mobile base at R2, and so is its twist action: velocity setpoints are mobile-base transit,
which the hazard table of `MHS/spec/04-safety.md` places at R2, as the comparable simulated mobile-base packages
`karthik0497/ros2-amr-simulation`, `mindspaceinc/spot-mujoco-ros2`, `maskor/webots_ros2_spot` and
`linorobot/linorobot2` declare. The card floor is R0; risk follows the hazard table, not the floor (handoff rule 13;
review of 2026-11-05, the first draft said R0). MVSim has no hardware path. The e-stop sets a zero twist
through `set_controller_twist`, which MVSim applies under its simulation-step lock and answers with success only when
the controller accepted it (World_services.cpp:124-170). That commands zero velocity; it is not measured braking: a
twist_pid or Ackermann controller slows the vehicle over time, and twist_ideal sets the twist at once. A raw-force or
trajectory controller refuses twist commands (ControllerBase.h:44-54; the trajectory controller keeps following its
path), so the e-stop then fails and the runtime keeps the latch and reports `SAFE_STATE_UNREACHED`. The setpoint is not
fenced: ROS `cmd_vel` (mvsim_node.cpp:934-942), the GUI teleop and any other MVSim client can command the vehicle
again; the ROS node's 1 s age check zeroes only twists that came through ROS (mvsim_node.cpp:525-540).

## Live route

The `sim` backend (`sim.py`, with the client class in `mvsim_wire.py`) is the package's own client of MVSim's services:
it frames and encodes the messages itself and needs only pyzmq. The upstream Python client is not used because its
calls wait without a timeout (common.cpp:63-73) in a binding that does not release the GIL (generated Client.cpp:74-87).
Every call of this client is bounded (`timeout_s`, default 2 s): a call that does not finish in time is an unknown
outcome for a setpoint and an unreached safe state for the e-stop. The client calls only `set_controller_twist` and
`get_pose`, and passes on only an answer of the service's own type or a `GenericAnswer` whose success is false (the
answer to an unknown service, Client.cpp:565-580), so no other message can read as an accepted zero twist. It connects
to the configured host at the port the server reports for a service: the simulator binds its service socket to
`tcp://0.0.0.0:*` and reports that wildcard endpoint (Client.cpp:166-167, 462), which the upstream client connects to
verbatim (Client.cpp:775, 783); this client never follows a host the server names. It has not been run against an
MVSim server.
