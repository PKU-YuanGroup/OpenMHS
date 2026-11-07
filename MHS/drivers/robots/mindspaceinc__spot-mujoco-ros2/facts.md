# Facts and tags for gh.mindspaceinc/spot-mujoco-ros2

Every fact cites the read-only clone at commit `1e07b87745ab623dab7ab79c4fbc61e62e4e829e`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| MuJoCoMessageHandler derives from rclcpp::Node named MuJoCoMessageHandler and sets name_prefix to the relative prefix simulation/. | upstream_code | simulation/mujoco/src/MuJoCoMessageHandler.cpp:8-9 |
| The node creates the relative sim_reset service with the communication/srv/SimulationReset type. | upstream_code | simulation/mujoco/src/MuJoCoMessageHandler.cpp:13-16 |
| The node creates the relative actuators_cmds subscription with the communication/msg/ActuatorCmds type and a KeepLast(1) sensor-data QoS. | upstream_code | simulation/mujoco/src/MuJoCoMessageHandler.cpp:18-51 |
| The node creates the relative joint_states publisher with the sensor_msgs/msg/JointState type. | upstream_code | simulation/mujoco/src/MuJoCoMessageHandler.cpp:21-22 |
| The reset callback rejects a request whose header.frame_id is not the model name m->names[0] and sets is_success false. | upstream_code | simulation/mujoco/src/MuJoCoMessageHandler.cpp:74-121 |
| The reset callback calls mj_resetData, writes qpos[0..2] and qpos[3..6] from base_pose.position and base_pose.orientation, writes each named joint's qpos entry and zeroes the cached kp, pos, kd, vel and torque entries. | upstream_code | simulation/mujoco/src/MuJoCoMessageHandler.cpp:74-121 |
| The reset callback performs those writes between sim_->mtx.lock() and unlock(), then sets is_success true; it does not change sim.run. | upstream_code | simulation/mujoco/src/MuJoCoMessageHandler.cpp:74-121 |
| While no model data exists the reset callback sleeps in one-second steps as long as rclcpp::ok() holds before it answers. | upstream_code | simulation/mujoco/src/MuJoCoMessageHandler.cpp:76-78 |
| PhysicsLoop locks the simulation mutex and, while sim.run is set, calls apply_ctrl and mj_step; while paused it only runs mj_forward. | upstream_code | simulation/mujoco/src/main.cc:356-463 |
| The node starts wall timers for imu_callback every 2.5 ms, joint_callback every 1 ms, odom_callback every 20 ms, touch_callback every 2 ms, img_callback every 20 ms and drop_old_message every 100 ms. | upstream_code | simulation/mujoco/src/MuJoCoMessageHandler.cpp:32-43 |
| The actuator callback stores the message time, resizes the cached arrays to the message sizes and copies each actuator name, kp, pos, kd, vel and torque entry. | upstream_code | simulation/mujoco/src/MuJoCoMessageHandler.cpp:240-260 |
| apply_ctrl computes data.ctrl as kp*(pos - jointpos sensordata) + kd*(vel - jointvel sensordata) + torque and clamps the resulting value to the interval [-100, 100]. | upstream_code | simulation/mujoco/src/main.cc:261-286 |
| The stale-command timer zeroes kp, pos, vel and torque and sets kd to 1.0 when the last command time is more than 0.2 s older than the node clock. | upstream_code | simulation/mujoco/src/MuJoCoMessageHandler.cpp:271-281 |
| joint_callback publishes one JointState entry per hinge joint: its name, qpos position, qvel velocity and qfrc_actuator effort. | upstream_code | simulation/mujoco/src/MuJoCoMessageHandler.cpp:203-222 |
| img_callback builds a depth-image header and a CvImage from an empty cv::Mat and publishes nothing. | upstream_code | simulation/mujoco/src/MuJoCoMessageHandler.cpp:224-238 |
| The simulation launch starts the mujoco package's simulation executable with the model-file parameter set to description/model/xml/spot_mini/spot_mini.xml. | upstream_code | simulation/mujoco/launch/simulation_launch.py:1-25 |
| The README lists the /simulation/actuators_cmds, /simulation/imu_data, /simulation/joint_states and /simulation/odom topics. | vendor_doc | README.md:44-53 |
| The MJCF is named spot and the base body's initial position is 0 0 0.7. | upstream_code | description/model/xml/spot_mini/spot_mini.xml:1-61 |
| The MJCF declares 12 hinge joints in four legs, each with a range; for example fl.hx spans -0.785398 to 0.785398 rad, fl.hy spans -0.898845 to 2.29511 rad and fl.kn spans -2.7929 to -0.254402 rad. | upstream_code | description/model/xml/spot_mini/spot_mini.xml:74-167 |
| The MJCF declares 12 motor actuators named after the 12 hinge joints with gear 1 and no ctrlrange. | upstream_code | description/model/xml/spot_mini/spot_mini.xml:230-243 |
| The MJCF option element sets timestep to 0.0005 s. | upstream_code | description/model/xml/spot_mini/spot_mini.xml:52 |

## Scope

The primary control is one `communication/msg/ActuatorCmds` publication on the
absolute `/simulation/actuators_cmds` topic. The upstream node applies
`kp*(pos - qpos) + kd*(vel - qvel) + torque` to each named actuator and clamps
the resulting `data.ctrl` to [-100, 100] (`main.cc:261-286`). The driver fixes
the actuator-name array to the 12 MJCF actuator names in MJCF order
(`spot_mini.xml:230-243`) and accepts the five numeric arrays. A rosbridge
publication receipt reports transmission only; it does not establish receipt,
the PD law, motion or arrival.

The only acknowledged effectful service is `/simulation/sim_reset`
(`communication/srv/SimulationReset`). Its callback checks that
`header.frame_id` is the model name `spot`, calls `mj_resetData`, writes the
base pose and named hinge positions, zeroes the cached actuator command arrays
and returns `is_success` (`MuJoCoMessageHandler.cpp:74-121`). The fixed-input
form of that service is the package's safe state and native e-stop binding. It
resets simulated data and cached commands under the simulation mutex before it
answers; it does not pause the MuJoCo physics loop (`main.cc:356-463`), so the
simulated bodies continue to step after it returns.

The main resource state is one live `sensor_msgs/msg/JointState` subscription's
`position` vector from `/simulation/joint_states`
(`MuJoCoMessageHandler.cpp:203-222`). The same topic is also exposed as an
explicit read capability with names, positions, velocities and efforts. IMU,
odometry, touch and the two image publishers are NOT COVERED: the image
callback builds a `CvImage` from an empty matrix and publishes nothing
(`MuJoCoMessageHandler.cpp:224-238`).

The relative ROS names are `sim_reset`, `actuators_cmds` and `joint_states`
under the node's `simulation/` prefix (`MuJoCoMessageHandler.cpp:8-9`). The
driver declares the resolved absolute endpoints `/simulation/...`; a deployment
that namespaces the node must expose the same absolute names through
rosbridge. Namespace and remapping are deployment configuration, not upstream
facts.

## Fidelity contract

`driver.py` describes the deployed fake, not the upstream simulator: engine
`analytic:ROS-free rosbridge contract stand-in (no physics)`, level F0,
determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`, reset `partial`,
no snapshot/restore. The fake answers only the declared wire endpoints (its
JointState header uses the ROS 2 stamp fields `sec`/`nanosec`). It
records the actuator publication and nudges its placeholder joint-position
sample by a fixed small factor of the PD expression so a command has an
observable contract effect; it computes no real `data.ctrl`, applies no physics
or contact, does not reproduce the 1 ms joint-state timer and does not replay
captured traffic. The upstream 0.0005 s timestep, 0.2 s stale-command zeroing
and 1 ms/20 ms timers remain source facts, not fake behavior. No live ROS graph,
rosbridge or MuJoCo run is claimed.

## Safety

The device is simulated at R2 because the actuator command drives a legged
mobile base. The runtime latches in software, then calls the fixed
`/simulation/sim_reset` service and the input-free `safe_reset` action; both
reach the acknowledged reset service (two calls per e-stop, and the safety
reset binding calls it once more). Under the simulation mutex and before it
answers, the callback calls `mj_resetData`, puts the base at (0, 0, 0.7) with the
model-default hinge positions and zero velocities, and zeroes every cached
actuator command, so `apply_ctrl` then writes zero control; the stale-command
timer adds joint damping (kd 1.0) 0.2 s after the last command. The reset is an
acknowledged simulated state reset that clears the commanded state, accepted as
the simulated stop by the model review of 2026-11-05; it is not a physical
emergency stop and not a pause: the MuJoCo physics loop keeps running (unless
paused in the GUI), so each call teleports the robot back to the start pose and
the limp robot falls and settles on the floor. Nothing in the clone publishes
`actuators_cmds`, but a later message from any client re-commands the
actuators. While no model is loaded the callback sleeps in one-second steps; an
unanswered reset makes the e-stop report `SAFE_STATE_UNREACHED` after its 1 s
budget with the latch held. A normal call of the safe-state action does not
itself engage the latch. `mhs.resource.read` remains permitted while latched;
the explicit `joint_states` extension action is an observation but carries an
extension id, so the server keeps it latched after an e-stop rather than
granting it a read exemption. The PD inputs kp, pos, kd and vel carry no Limit;
the only bound in the clone is the [-100, 100] clamp of the summed control
(`main.cc:284-285`), which the torque Limit applies to the feed-forward term.
The fake has no physical stop and makes no hardware claim; no hardware backend
is declared.

## Tags

`ros`, `ros2`, `mujoco`, `spot`, `quadruped`, `simulation`, `joint`, `actuator`, `reset`
