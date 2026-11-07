OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.fdcl-gwu/uav_simulator

Every fact cites the pinned clone at commit `7270fe4e274f2a5d84432336311da478d87d8d3d`.
`upstream_code` refs name `path/in/clone:LINE`; `vendor_doc` refs name a text file of the clone.
The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated
from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| TrajectoryNode subscribes to /uav/states as StateData and /uav/mode as ModeData, each with queue depth 1. | upstream_code | src/fdcl_uav/fdcl_uav/trajectory.py:80-90 |
| TrajectoryNode creates a DesiredData publisher on /uav/trajectory with queue depth 1. | upstream_code | src/fdcl_uav/fdcl_uav/trajectory.py:93-98 |
| calculate_trajectory calls set_desired_states_to_zero for mode 0 or 1, takeoff for mode 2, stay for mode 3, circle for mode 4 and land for mode 5, and otherwise logs Undefined mode. | upstream_code | src/fdcl_uav/fdcl_uav/trajectory.py:153-165 |
| The mode callback stores x_offset and yaw_offset from the message and, when the mode differs, stores the new mode and calls mark_traj_start. | upstream_code | src/fdcl_uav/fdcl_uav/trajectory.py:116-125 |
| mark_traj_start sets is_landed to False, clears x_offset and yaw_offset, resets the trajectory timers and calls update_initial_state. | upstream_code | src/fdcl_uav/fdcl_uav/trajectory.py:168-183 |
| update_initial_state copies self.x, self.v, self.a, self.R and self.W into the initial-state fields. | upstream_code | src/fdcl_uav/fdcl_uav/trajectory.py:217-222 |
| set_desired_states_to_zero sets desired position, velocity, acceleration, jerk and snap and the b1 derivatives to zero, and sets b1d to [1.0, 0.0, 0.0]. | upstream_code | src/fdcl_uav/fdcl_uav/trajectory.py:193-202 |
| takeoff copies self.x into xd and sets xd_dot[2] from takeoff_velocity; land sets is_landed True when self.x[2] is greater than landing_motor_cutoff_height. | upstream_code | src/fdcl_uav/fdcl_uav/trajectory.py:266-344 |
| EstimatorNode subscribes to /uav/imu as Imu with queue depth 1. | upstream_code | src/fdcl_uav/fdcl_uav/estimator.py:283-287 |
| EstimatorNode subscribes to /uav/gps as Odometry with queue depth 1. | upstream_code | src/fdcl_uav/fdcl_uav/estimator.py:289-293 |
| gps_callback reads pose.pose.position and twist.twist.linear and builds the NED vectors x_gps as [x, -y, -z] and v_gps as [x, -y, -z]. | upstream_code | src/fdcl_uav/fdcl_uav/estimator.py:333-338 |
| EstimatorNode creates a StateData publisher on /uav/states with queue depth 1. | upstream_code | src/fdcl_uav/fdcl_uav/estimator.py:347 |
| publish_states assigns position, velocity, acceleration, angular_velocity and attitude from the estimator state and publishes the StateData. | upstream_code | src/fdcl_uav/fdcl_uav/estimator.py:350-361 |
| ControlNode subscribes to /uav/states as StateData, /uav/trajectory as DesiredData, /uav/mode as ModeData and /uav/motors_on as Bool, each with queue depth 1. | upstream_code | src/fdcl_uav/fdcl_uav/control.py:517-541 |
| ControlNode creates publishers for DesiredData on /uav/desired, ErrorData on /uav/errors and WrenchStamped on /uav/fm, each with queue depth 1, and a timer of 0.005 s. | upstream_code | src/fdcl_uav/fdcl_uav/control.py:508-514 |
| ControlNode assigns a zero force and a zero torque when motor_on is false or mode is below 2. | upstream_code | src/fdcl_uav/fdcl_uav/control.py:245-251 |
| motors_on_callback sets motor_on from msg.data. | upstream_code | src/fdcl_uav/fdcl_uav/control.py:585-586 |
| GuiNode's radio buttons are labelled Idle, Warmup, Take-off, Stay, Circle and Land. | upstream_code | src/fdcl_uav/fdcl_uav/gui.py:128-136 |
| GuiNode creates a ModeData publisher on /uav/mode and a Bool publisher on /uav/motors_on, each with queue depth 1. | upstream_code | src/fdcl_uav/fdcl_uav/gui.py:261-263 |
| GuiNode creates a QTimer, connects it to update and starts it at 100. | upstream_code | src/fdcl_uav/fdcl_uav/gui.py:86-88 |
| update assigns mode, x_offset and yaw_offset on a ModeData and publishes it on /uav/mode. | upstream_code | src/fdcl_uav/fdcl_uav/gui.py:302-306 |
| The shutdown handler logs, sets motor_on to False and publishes that Bool. | upstream_code | src/fdcl_uav/fdcl_uav/gui.py:363-371 |
| The motor-toggle handler logs, stores the toggled self.motor_on, updates the button text and publishes that Bool. | upstream_code | src/fdcl_uav/fdcl_uav/gui.py:378-391 |
| The flight-mode callback logs the selected index, publishes ModeData.mode and then sets x_offset and yaw_offset to zero. | upstream_code | src/fdcl_uav/fdcl_uav/gui.py:394-407 |
| The M key calls the motor-toggle handler. | upstream_code | src/fdcl_uav/fdcl_uav/gui.py:410-413 |
| fdcl_uav_launch.py starts four fdcl_uav nodes named sim, with executables estimator, control, trajectory and gui in namespaces estimator, control, trajectory and gui. | upstream_code | src/fdcl_uav/launch/fdcl_uav_launch.py:6-29 |
| The Gazebo plugin creates a subscription of geometry_msgs::msg::WrenchStamped on topic_name_ with depth 1. | upstream_code | src/uav_plugins/src/uav_control_plugin.cpp:59-64 |
| update_fm copies wrench.force and wrench.torque into f and M and sets no_msg_counter to 0. | upstream_code | src/uav_plugins/src/uav_control_plugin.cpp:122-133 |
| The world-update callback increments no_msg_counter, calls reset_uav and returns when the counter exceeds 100, and otherwise calls SetForce and SetTorque. | upstream_code | src/uav_plugins/src/uav_control_plugin.cpp:68-88 |
| reset_uav calls SetForce and SetTorque with zero_fM. | upstream_code | src/uav_plugins/src/uav_control_plugin.cpp:137-141 |
| The URDF gazebo block for link sets gravity to true. | upstream_code | src/uav_gazebo/urdf/uav.urdf.xacro:30 |
| The URDF remaps the IMU plugin ~/out to uav/imu. | upstream_code | src/uav_gazebo/urdf/uav.urdf.xacro:38-40 |
| The URDF loads libgazebo_ros_p3d, remaps odom to uav/gps, and sets frame_name world, gaussian_noise 0.01 and update_rate 10. | upstream_code | src/uav_gazebo/urdf/uav.urdf.xacro:53-61 |
| The URDF sets the uav_control_plugin topic_name to /uav/fm. | upstream_code | src/uav_gazebo/urdf/uav.urdf.xacro:65-69 |
| The Gazebo launch joins the package path with worlds/simple.world. | upstream_code | src/uav_gazebo/launch/uav_gazebo.launch.py:29 |
| simple.world includes the model URI model://ground_plane. | upstream_code | src/uav_gazebo/worlds/simple.world:13-15 |
| The Gazebo launch spawns the entity named uav at x=0, y=0, z=0.2. | upstream_code | src/uav_gazebo/launch/uav_gazebo.launch.py:47-52 |
| The README says the current main branch has been tested on Ubuntu 22.04 running ROS2-Iron. | vendor_doc | README.md:61 |
| The README says that while the UAV is in manual the P key increases altitude and the L key decreases altitude. | vendor_doc | README.md:182-185 |
| The README documents the M key as kill motors and the 0-5 keys as flight mode selection. | vendor_doc | README.md:188-190 |

## Scope

The served surface is the clone's own ROS 2 topic interface: `/uav/states` as the fused
state observation, `/uav/imu` as the raw simulated IMU observation, `/uav/mode` as the
flight-mode input, and `/uav/motors_on` as an input-free Bool false. The mode range 0..5
is the comparisons in `trajectory.py:153-162`. The resource snapshot reads the last
`ModeData.mode` and `Bool.data` on those topics. Those are wire observations, not
execution feedback.

`/uav/gps` is the sensed-confirmation source only. It is not a command. `/uav/trajectory`,
`/uav/desired`, `/uav/errors`, `/uav/fm`, the camera, laser, TF and Gazebo service surfaces
are **NOT COVERED**.

## Safety

The device is a simulated R2 multirotor. The e-stop publishes Bool false on `/uav/motors_on`
and is achieved only when three fresh `/uav/gps` samples show Gazebo-frame z at or below
the operator's landed band and x, y and z still. The Bool proves nothing. The package
publishes no Bool true and declares no re-enable. ControlNode keeps its mode
(`control.py:544-549`) and TrajectoryNode keeps its mode (`trajectory.py:116-124`).
`motors_on_callback` only sets `motor_on` (`control.py:585-586`). With mode at least 2,
Bool true permits a nonzero wrench (`control.py:245-251`). Stopping GuiNode does not
clear those modes. `estop_terminal` is not claimed, because a Bool true publication can
undo the cut. Recovery is outside MHS and must leave both nodes at mode 0 before any
Bool true: set the GUI to Idle so GuiNode republishes mode 0, or, if GuiNode is stopped,
publish mode 0 on `/uav/mode` first. Do not stop GuiNode and then publish Bool true while
the stored mode is still at least 2. No physical e-stop exists or is claimed.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS contract fake (canned replies;
no Gazebo physics)`, level F0, determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`,
reset `none`, and no snapshot/restore. The fake answers the declared observation topics,
records the declared publications, and answers `/uav/gps` with a placeholder fall after
Bool false. It does not replay captured traffic and it does not run Gazebo. Placeholder
thresholds and history live only in `fixtures/estop-confirmation.json`.

## Tags

`ros`, `ros2`, `simulation`, `gazebo`, `uav`, `quadrotor`, `trajectory`, `mode`
