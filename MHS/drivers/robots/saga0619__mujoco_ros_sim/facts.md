# Facts and tags for gh.saga0619/mujoco_ros_sim

Every fact cites the pinned clone at commit `dcdfd09ac6a4f5fc03c4a0b1a83b3faaf41f94bd`. The
`source` is `vendor_doc` for text documentation and `upstream_code` for a source or message
definition. `path/in/clone:LINE` is relative to the clone root as it is, including the
`mujoco_ros/` and `mujoco210/` directories. The same facts are written into `driver.py`
(`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not
from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README states that MuJoCo sends joint and sensor data over ROS topics and receives torque or position command data over ROS topics. | vendor_doc | README.md:5 |
| The documented publishers are /mujoco_ros_interface/joint_states (sensor_msgs/JointState), /mujoco_ros_interface/sensor_states (mujoco_ros_msgs/SensorState) and /mujoco_ros_interface/sim_time (std_msgs/Float32). | vendor_doc | README.md:32-34 |
| The documented subscribers are /mujoco_ros_interface/sim_command_con2sim (std_msgs/String) and /mujoco_ros_interface/joint_set (mujoco_ros_msgs/JointSet). | vendor_doc | README.md:37-38 |
| The README documents /mujoco_ros_interface/applied_ext_force (mujoco_ros_msgs/applyforce) with a link index, a force and a torque. | vendor_doc | README.md:41-42 |
| main subscribes the sim_command_con2sim String command topic and the applied_ext_force topic, and advertises sim_command_sim2con. | upstream_code | mujoco_ros/src/main.cpp:128-130 |
| The node builds topic names from the /mujoco_ros_interface prefix, inserts a non-root node namespace, and appends /joint_set, /joint_states, /sim_time and /sensor_states. | upstream_code | mujoco_ros/src/main.cpp:138-162 |
| joint_set is subscribed with queue size 1 and tcpNoDelay(true); joint_states, sim_time and sensor_states are advertised with queue size 1; pub_mode instead advertises SimStatus. | upstream_code | mujoco_ros/src/main.cpp:164-172 |
| jointset_callback compares msg->time with mjData.time, accepts it only when it is not in the future and its age is at most 0.01 s, then copies msg->torque when MODE is 1 or msg->position when MODE is 0 into command[] for the loaded model's m->nu actuators. | upstream_code | mujoco_ros/src/mjros.cpp:47-96 |
| jointset_callback sets cmd_rcv before its time checks; a command older than 0.01 s only logs an error, so cmd_rcv stays true and command[] keeps the previous values. | upstream_code | mujoco_ros/src/mjros.cpp:50-66 |
| In both modes the size check compares joint_set_msg_.torque.size(), the node's own message buffer, with m->nu before copying m->nu entries of the received array. | upstream_code | mujoco_ros/src/mjros.cpp:71-94 |
| state_publisher_init resizes joint_set_msg_.position and joint_set_msg_.torque to m->nu. | upstream_code | mujoco_ros/src/mjros.cpp:160-161 |
| JointSet.msg declares Header header, float64 time, int32 MODE, float64[] position and float64[] torque, with MODE 0 documented as POSITION and MODE 1 as TORQUE. | upstream_code | mujoco_ros_msgs/msg/JointSet.msg:1-10 |
| state_publisher_init sizes the command arrays from m->nu and the JointState arrays from m->nu, m->njnt or the six virtual base entries, and creates an extra user-information sensor entry of two values. | upstream_code | mujoco_ros/src/mjros.cpp:155-251 |
| state_publisher sets sim_time.data from mjData.time, publishes JointState position, velocity and effort from qpos, qvel and qacc, and publishes SensorState values from mjData.sensordata; the trailing user information entry holds dif_time and com_time. | upstream_code | mujoco_ros/src/mjros.cpp:270-336 |
| The sim_command_callback handles RESET and INIT controller handshakes, toggles settings.run on 'pause', sets reset_request on 'mjreset', and publishes no acknowledgement on sim_command_sim2con. | upstream_code | mujoco_ros/src/mjros.cpp:98-129 |
| rosPollEvents calls c_reset when reset_request is true. | upstream_code | mujoco_ros/src/mjros.cpp:146-153 |
| c_reset calls mj_resetData, copies the selected keyframe time/qpos/qvel/act, and clears cmd_rcv. | upstream_code | mujoco_ros/src/mjros.cpp:5-43 |
| c_reset calls mujoco_ros_connector_init, which publishes RESET and waits up to 1.0 s for the controller's RESET reply, then publishes INIT and waits up to 1.0 s for its reply before restoring the control callback. | upstream_code | mujoco_ros/src/mjros.cpp:442-498 |
| mycontroller calls ros::spinOnce, publishes state only while settings.run, and copies the cached command into d->ctrl only when cmd_rcv is set. | upstream_code | mujoco_ros/src/mjros.cpp:500-618 |
| The simulate thread steps physics only inside the settings.run branch and otherwise runs the paused branch. | upstream_code | mujoco_ros/src/mjros.cpp:2233-2290 |
| mjData.time is the simulation time. | upstream_code | mujoco210/include/mjdata.h:155 |
| mjData stores qpos as position (nq values), qvel as velocity (nv values) and qacc as acceleration (nv values). | upstream_code | mujoco210/include/mjdata.h:167-178 |
| The README installation step clones the repository into a catkin workspace src directory and builds it with catkin_make. | vendor_doc | README.md:15 |
| mujoco_ros/package.xml declares catkin build and exec dependencies on roscpp, std_msgs and mujoco_ros_msgs. | upstream_code | mujoco_ros/package.xml:51-60 |
| The CMake project finds roscpp, std_msgs, mujoco_ros_msgs and eigen_conversions and includes the vendored mujoco210 headers. | upstream_code | mujoco_ros/CMakeLists.txt:6-19 |
| The mujoco_ros package manifest declares its license as TODO. | upstream_code | mujoco_ros/package.xml:16 |

The `mujoco_ros_msgs` package declares `message_generation` and `message_runtime` and
builds the message definitions in `mujoco_ros_msgs/msg/`
(`mujoco_ros_msgs/package.xml:13-21`, `mujoco_ros_msgs/CMakeLists.txt:4-22`); the
`mujoco210` directory is a vendored MuJoCo 2.1 tree (`README.md:7`,
`mujoco_ros/CMakeLists.txt:19`), not a Python package. The clone is ROS 1 (`ros::init`,
catkin), not ROS 2.

## Scope

The served control is `mujoco_ros_msgs/JointSet` on the default absolute
`/mujoco_ros_interface/joint_set` topic. Position mode is MODE 0 and torque mode is MODE 1,
as documented in `mujoco_ros_msgs/msg/JointSet.msg:9-10`. The message body `time` must be
close to the simulator's current `mjData.time`; the callback rejects a future time, and a
command more than 0.01 s old is only logged: `cmd_rcv` was already set, so the previously
accepted command keeps being applied (`mujoco_ros/src/mjros.cpp:50-66`). The array must have
exactly the loaded model's actuator count `m->nu`, but the callback does not check the
received length: its size check compares the node's own `joint_set_msg_.torque` buffer, which
`state_publisher_init` resized to `m->nu` (`mujoco_ros/src/mjros.cpp:71-94, 160-161`), so a
shorter array is read past its end (corrected by the model review of 2026-11-05; earlier text
said the callback copies nothing). That count is a property of the operator's MJCF model, not a
number the clone states. The command and observation values carry no unit: the clone states
none for the model's generalized coordinates, controls and sensor data.

The served observations are one fresh `sensor_msgs/JointState` sample per call from
`/mujoco_ros_interface/joint_states`, one fresh `mujoco_ros_msgs/SensorState` sample from
`/mujoco_ros_interface/sensor_states`, and one fresh `std_msgs/Float32` sample from
`/mujoco_ros_interface/sim_time`. The upstream fills the `effort` field of JointState from
`mjData.qacc`, which is an acceleration, not a torque (`mujoco_ros/src/mjros.cpp:294,
304`); the reference describes that field as `qacc` rather than relabelling it. For a
floating-base model the publisher prepends six virtual base entries and writes an extra
position value (`mujoco_ros/src/mjros.cpp:178-200, 277-297`). The sensor publisher appends a
`user information` entry holding `dif_time` and `com_time` (`mujoco_ros/src/mjros.cpp:248-249,
315-316`).

The observed topics are explicit observation capabilities, not automatic resource reads.
`state_publisher` is called from `mycontroller` only while `settings.run` is true
(`mujoco_ros/src/mjros.cpp:504-508`), so a paused simulator may publish no fresh sample.
An observation then waits for its own subscription deadline and fails; it never returns a
cached sample. The resource snapshot is empty and does not wait for a paused topic.

Out of scope: `/mujoco_ros_interface/sim_command_con2sim`, `/mujoco_ros_interface/sim_command_sim2con`,
`/mujoco_ros_interface/applied_ext_force`, the `SimStatus` aggregate `pub_mode`, the
shared-memory (`use_shm`, `tocabi_ecat`) transport and the graphical UI. The package does
not launch the simulator, load a model or provide rosbridge.

## Limits

No numeric `Limit` is declared. The clone states no joint travel, velocity, torque, force
or sensor range for the loaded model; the model file is an operator choice. The only
numeric bound in the selected path is the command-age check `0.01` s
(`mujoco_ros/src/mjros.cpp:63`), which is a timestamp comparison in the callback, not a
joint limit or a site envelope. Since this is a simulated R0 package whose values are
confined to `mjData`, no hardware envelope is required; an operator who wants site bounds
can add them through the catalogue/site overlay for a future elevated binding, but this
package declares none.

## Stop and safety

The clone exposes no ROS service or action. `pause` toggles `settings.run` and `mjreset`
sets `reset_request`; both are payloads of an unacknowledged `std_msgs/String` publication
(`mujoco_ros/src/mjros.cpp:113-123`). A `pause` message is not idempotent: sending it twice
returns the simulator to running. `mjreset` makes the event loop call `c_reset`, which
re-runs the RESET/INIT controller handshake and waits up to 1.0 s for each reply
(`mujoco_ros/src/mjros.cpp:146-153, 442-498`). Neither publication reports that the
simulator stopped, and no `mujoco_ros` node publishes a pause acknowledgement.

The driver therefore declares no `safety_bindings` and no `safe_state=True` action. The
stock MHS e-stop engages the software latch, but the RosBridge cannot confirm a native
safe state for an effectful control surface and the receipt is
`MHS.SAFETY.SAFE_STATE_UNREACHED`; the latch stays engaged. A zero `JointSet` publication
is transmission-only and is not offered as a stop.

## Fidelity contract

`driver.py` describes the packaged analytic contract fake, not the upstream
simulator: engine `analytic:ROS contract fake (no physics)`, level F0, determinism
`none`, no timestep, `realtime_factor: 0`, no reset and no snapshot/restore. It
answers the three observation topics with fixed placeholder samples and records
`JointSet` publications; it is not a captured-traffic replay. It runs no MuJoCo,
`mj_step`, controller, actuator, contact, sensor or ROS graph. Upstream physics
timestep, dynamics and model dimensions are not claimed. The real arrays are
larger than the fake's placeholders, as disclosed in the fidelity gaps.

## Tags

`ros`, `ros1`, `simulation`, `mujoco`, `joint-command`, `joint-state`, `sensor-state`
