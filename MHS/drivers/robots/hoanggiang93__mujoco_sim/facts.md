# Facts and tags for gh.hoanggiang93/mujoco_sim

Every fact cites the pinned clone at commit `dd1cf9096a043589f338374f4c67a675c34a57b0`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the statement
spans adjacent lines. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| MjRos::init advertises /mujoco/reset with the reset_robot_service callback. | upstream_code | src/mujoco_sim/mj_ros.cpp:540 |
| reset_robot_service takes a std_srvs/Trigger request, stops running effort controllers, resets the robot data, sleeps 100 model timesteps, sets response.success from an error_sum threshold and then restarts the controllers it stopped. | upstream_code | src/mujoco_sim/mj_ros.cpp:779-856 |
| reset_robot creates new mjData, writes each robot joint qpos from joint_inits or zero, zeroes the joint qvel and qacc, zeroes the odometry velocities and calls mj_forward. | upstream_code | src/mujoco_sim/mj_ros.cpp:569-609 |
| The simulate loop calls mj_step1 and mj_step2 continuously while ros::ok and adjusts the model timestep toward real time; it has no pause, stop or step-request branch. | upstream_code | src/mj_main.cpp:76-164 |
| main starts the simulate function on its own thread, next to three ROS setup threads. | upstream_code | src/mj_main.cpp:198-203 |
| MjRos::init advertises /mujoco/object_states as mujoco_msgs/ObjectStateArray. | upstream_code | src/mujoco_sim/mj_ros.cpp:560 |
| MjRos::init advertises /mujoco/robot_joint_states as sensor_msgs/JointState. | upstream_code | src/mujoco_sim/mj_ros.cpp:561 |
| publish_object_state_array returns without publishing when the configured rate is below 1E-9. | upstream_code | src/mujoco_sim/mj_ros.cpp:1770-1773 |
| publish_joint_states returns without publishing when the configured rate is below 1E-9. | upstream_code | src/mujoco_sim/mj_ros.cpp:1812-1815 |
| The shipped src/config/robot.yaml sets the object-state and joint-state publication rates to 0.0 for robot, world and spawned-object bodies. | upstream_code | src/config/robot.yaml:74-83 |
| MjRos::init advertises exactly the /mujoco/screenshot, /mujoco/reset, /mujoco/spawn_objects and /mujoco/destroy_objects services; no pause, stop or e-stop service is advertised. | upstream_code | src/mujoco_sim/mj_ros.cpp:537-546 |
| The per-robot /<robot>/cmd_vel subscription is created only when at least one odometry joint is configured for that robot. | upstream_code | src/mujoco_sim/mj_ros.cpp:522-533 |
| CmdVelCallback::callback writes the robot's six odometry velocity entries from the Twist, 0.0 for an axis without an odometry joint. | upstream_code | src/mujoco_sim/mj_ros.cpp:193-200 |
| publish_object_state_array starts one thread each for robot, world and spawned-object bodies; each thread fills its own array and publishes it through the one object_state_array_pub publisher at its own rate. | upstream_code | src/mujoco_sim/mj_ros.cpp:1757-1792 |

## Scope

The package binds the absolute `/mujoco/reset` service (`std_srvs/Trigger`,
`src/mujoco_sim/mj_ros.cpp:540`, type include at `include/mujoco_sim/mj_ros.h:36`) and reads
two absolute observation topics: `/mujoco/object_states`
(`mujoco_msgs/ObjectStateArray`, `src/mujoco_sim/mj_ros.cpp:560`) and
`/mujoco/robot_joint_states` (`sensor_msgs/JointState`, `src/mujoco_sim/mj_ros.cpp:561`).
The message types are declared by the includes in `include/mujoco_sim/mj_ros.h:24-36`;
the node uses an absolute `ros::NodeHandle`, so these names need no namespace remapping,
although the operator must still expose the same names through rosbridge.

The two observations are explicit capabilities, not an automatic resource snapshot. The
shipped `src/config/robot.yaml:74-83` sets every object-state and joint-state publisher rate
to 0.0, and each publisher returns immediately below 1E-9
(`src/mujoco_sim/mj_ros.cpp:1770-1773`, `1812-1815`). A live deployment must set the
relevant `pub_object_state_array/*` or `pub_joint_states/*` rate above zero before either
read can receive a fresh sample; the fake always answers. The robot, world and spawned-object
bodies are published as separate arrays on the same `/mujoco/object_states` topic, each at its
own rate (`src/mujoco_sim/mj_ros.cpp:1757-1792`), so one live sample holds one body category.

NOT COVERED: `/mujoco/screenshot`, `/mujoco/spawn_objects`, `/mujoco/destroy_objects`, the
per-robot `/<robot>/cmd_vel` input, TF, marker arrays, base-pose odometry and
`/mujoco/sensors_3D`. The clone has no world-step service or seed service; the simulation
loop steps continuously on its own thread (`src/mj_main.cpp:76-164`,
`src/mj_main.cpp:198-203`) with a timestep that is adjusted toward real time, so
`cap.world.step.v1` and `cap.world.seed.v1` cannot bind this ROS surface. The reset
service is not `cap.world.reset.v1`: the Trigger response carries only `success` and
`message`, not the catalogue class's required `observation` and `seed`, and the callback
does not seed a random number generator.

## Safety blocker

This package is blocked with `HELPER_MISSING` rather than claimed as a completed control
integration. The only effectful endpoint it binds is `/mujoco/reset`. The callback stops
running effort controllers, calls `reset_robot` (joint positions from `joint_inits` or zero,
zero joint velocities and accelerations, zero odometry velocities, `mj_forward`) and then
restarts the controllers it stopped (`src/mujoco_sim/mj_ros.cpp:779-856`,
`src/mujoco_sim/mj_ros.cpp:569-609`). It never stops the independent simulation thread,
which keeps calling `mj_step1`/`mj_step2` (`src/mj_main.cpp:76-164`).

The clone advertises no pause, stop, abort or e-stop service; its four services are
screenshot, reset, spawn and destroy (`src/mujoco_sim/mj_ros.cpp:537-546`). A rosbridge
topic publication is transmission-only and cannot serve as a safe-state binding, and a
zero-velocity `/cmd_vel` publication is not an acknowledged stop. The reset service
therefore cannot be declared as a safe-state action: a completed reset acknowledgement does
not establish quiescent physics, and the controllers restart before the callback returns.
The RosDriver bridge also reports an effectful ROS profile without an acknowledged stop as
an unconfirmed safe state, so a stock e-stop fails with
`MHS.SAFETY.SAFE_STATE_UNREACHED` rather than claiming a stop that did not happen.

The fake models the wire contract only. It does not model MuJoCo, the ros_control loop, the
upstream controller switch or a stopped state. No hardware, ROS graph, simulator process or
rosbridge connection is claimed.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS recording fake (no physics)`,
level F0, determinism `none`, `timestep_ms: 0` (event-driven responses with no physics
step), `realtime_factor: 0` (not paced), reset `none`, and no snapshot/restore. The gaps
disclose that the fake reset only increments a counter, the observation samples are
placeholders and scene-dependent in size, the shipped publisher rates disable both live
observations, and the package exposes no stop, step, seed or spawn/destroy path.

## Tags

`ros`, `ros1`, `simulation`, `mujoco`, `reset`, `object-states`, `joint-states`
