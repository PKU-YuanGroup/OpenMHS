OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.ubi-agni/mujoco_ros_pkgs

Every fact cites the pinned clone at commit `9304ca7ec254ac1aaa0c2f556513a9a51d28530e`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| RosAPI::SetupServices advertises the relative set_pause service through the node's private node handle. | upstream_code | mujoco_ros/src/ros_one/ros_api.cpp:55 |
| RosAPI::SetPauseCB takes a mujoco_ros_msgs::SetPause request and response and sets response.success from TogglePaused(req.paused, req.admin_hash). | upstream_code | mujoco_ros/src/ros_one/ros_api.cpp:409-417 |
| SetPause.srv declares request fields bool paused and string admin_hash and response field bool success. | upstream_code | mujoco_ros_msgs/srv/SetPause.srv:1-4 |
| MujocoEnv::TogglePaused refuses a paused=true request when VerifyAdminHash fails, before calling SetPaused, and returns false. | upstream_code | mujoco_ros/src/interface.cpp:57-66 |
| MujocoEnv::VerifyAdminHash compares the supplied hash with settings_.admin_hash only when eval_mode is set; outside eval mode it returns true. | upstream_code | mujoco_ros/src/mujoco_env.cpp:1211-1220 |
| SimulationControlState::SetPaused stores running_ = !paused and notifies the physics condition. | upstream_code | mujoco_ros/include/mujoco_ros/simulation_control_state.hpp:88-95 |
| The physics loop calls SimPausedPhysics while the control snapshot is not running and SimUnpausedPhysics otherwise. | upstream_code | mujoco_ros/src/physics.cpp:297-302 |
| SimPausedPhysics executes requested manual steps through WrappedStep; without a pending step it runs mj_forward and publishes simulation time. | upstream_code | mujoco_ros/src/physics.cpp:314-340 |
| MujocoEnv::GetSimInfo reports paused as the negation of the control snapshot's running flag. | upstream_code | mujoco_ros/src/interface.cpp:1211-1220 |
| RosAPI::SetupServices advertises the relative get_sim_info service through the node's private node handle. | upstream_code | mujoco_ros/src/ros_one/ros_api.cpp:72 |
| RosAPI::GetSimInfoCB takes a mujoco_ros_msgs::GetSimInfo request and response, calls MujocoEnv::GetSimInfo and assigns res.state.paused. | upstream_code | mujoco_ros/src/ros_one/ros_api.cpp:791-802 |
| GetSimInfo.srv has an empty request and response field mujoco_ros_msgs/SimInfo state. | upstream_code | mujoco_ros_msgs/srv/GetSimInfo.srv:1-2 |
| SimInfo.msg declares bool paused. | upstream_code | mujoco_ros_msgs/msg/SimInfo.msg:5 |
| The ROS 1 MujocoEnv constructor creates the private node handle "~" and passes it to RosAPI, so relative service names resolve under the node's private namespace. | upstream_code | mujoco_ros/src/mujoco_env.cpp:200-201 |
| The pinned launch file starts the mujoco_node executable as a node named mujoco_server; the node tag carries no ns attribute. | upstream_code | mujoco_ros/launch/launch_server.launch:55 |

## Namespace and scope

The two services are advertised with relative names on a private node handle
(`mujoco_ros/src/mujoco_env.cpp:200-201`, `mujoco_ros/src/ros_one/ros_api.cpp:55`
and `:72`). The pinned launch file names the node `mujoco_server` without an
`ns` attribute (`mujoco_ros/launch/launch_server.launch:55`), so this package
configures the absolute endpoints `/mujoco_server/set_pause` and
`/mujoco_server/get_sim_info` and records the upstream tokens as
`source_name`. A deployment that names or namespaces the node differently
must expose the services at those endpoints or the operator must change the
driver's endpoints deliberately; the gate does not prove ROS graph resolution.

Only two operations are exposed. `pause` sends a fixed request with
`paused=true` and `admin_hash=""`; it is not a general boolean toggle and this
package does not expose resume. The empty hash is accepted by the fake and by
an unauthenticated deployment outside eval mode; `TogglePaused` returns false
when `eval_mode` is set and the supplied hash does not match
(`mujoco_ros/src/interface.cpp:60-62`, `mujoco_ros/src/mujoco_env.cpp:1213-1219`),
and the driver preserves that rejection as a failure. `get_sim_info` is an
observational service action mapped to `state.paused`
(`mujoco_ros/src/ros_one/ros_api.cpp:800`); the rest of the `SimInfo` response
is not used. Model reload, world step, gravity, robot actuation and shutdown
are not exposed.

## Safety and fidelity

`pause` disables continuous simulator running. `SetPaused` stores `running_ = !paused`
(`mujoco_ros/include/mujoco_ros/simulation_control_state.hpp:88-95`), the
physics loop selects `SimPausedPhysics` when the control snapshot is not
running (`mujoco_ros/src/physics.cpp:297-302`), and `GetSimInfo` derives
`paused` from the same flag (`mujoco_ros/src/interface.cpp:1219`). It is not a
physical emergency stop, and the package makes no robot-velocity or
hardware-safe-state claim. Pausing does not cancel pending manual steps, and the
paused branch can execute pending or externally requested steps through `WrappedStep`
(`mujoco_ros/src/physics.cpp:314-333`); otherwise it runs `mj_forward` and publishes
time (:334-340). A pause acknowledgement therefore does not establish quiescent
physics or a frozen clock. The fake does not model that external step queue.
The e-stop path latches in software before calling the service. Normal invocation
of the same input-free `safe_state=True` action does not itself latch.

The deployed backend is a ROS-free `RecordingRosTransport`, so the fidelity is
`engine: recording`, level F0, determinism `none`, `timestep_ms: 0` and
`realtime_factor: 0` (no wall-clock pacing). There is no MuJoCo engine, physics step, ROS node,
rosbridge connection, simulator process or hardware validation. The fake's
paused flag is placeholder test state, and it returns only `state.paused`
rather than the full `SimInfo` response. `driver.lock.json` keeps
`reviewed_by: null`.

## Tags

`ros`, `ros1`, `simulation`, `mujoco`, `pause`, `sim-info`
