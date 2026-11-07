# Facts and tags for gh.epfl-lasa/kuka-rviz-simulation

Every fact cites the pinned clone at commit
`66448f9e8995b557335b6b51c9ab6ed6c5afd99d`.  `upstream_code` refs name
`path/in/clone:LINE`; `vendor_doc` refs name text in the clone.  The same facts
are written into `driver.py` (`facts = [...]`); `reference.json` and
`REFERENCE.md` are generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README states that the simulation offers a joint velocity/position-resolved interface, that commands are sent to it, and that no dynamics or physics simulation is included. | vendor_doc | README.md:39 |
| The README names /r_arm_vel/command as the topic to publish and says the current robot state is published on /joint_states with type sensor_msgs/JointState. | vendor_doc | README.md:56 |
| lwr_sim_vel_controllers.launch loads the controller configuration and starts the pr2_controller_manager spawner with the r_arm_vel controller. | upstream_code | kuka_lwr_bringup/launch/controllers/lwr_sim_vel_controllers.launch:3-7 |
| The velocity-controller configuration names r_arm_vel, its iai_robot_mechanism_controllers/MultiJointVelocityImpedanceController type and the seven right_arm_0_joint through right_arm_6_joint joints. | upstream_code | kuka_lwr_bringup/config/lwr_sim_vel_controllers.yaml:1-10 |
| MultiJointVelocityImpedanceController subscribes the relative command topic with queue size 1 and creates a state publisher on the relative state topic. | upstream_code | iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/src/multi_joint_velocity_impedance_controller.cpp:124-130 |
| The controller header includes pr2_controllers_msgs/JointTrajectoryControllerState.h. | upstream_code | iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/include/iai_robot_mechanism_controllers/multi_joint_velocity_impedance_controller.h:53 |
| When loop_count_ % 10 == 0 and the state publisher trylocks, the update assigns header.stamp from the update time, desired.velocities[j] from command[j], actual.positions[j] from position_, actual.velocities[j] from velocity_ and error.velocities[j] from error[j]. | upstream_code | iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/src/multi_joint_velocity_impedance_controller.cpp:192-203 |
| The command callback takes an iai_control_msgs::MultiJointVelocityImpedanceCommand; only when its velocity array length equals the configured joint count does it copy the velocities and set watchdog_time_, otherwise it logs an error. | upstream_code | iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/src/multi_joint_velocity_impedance_controller.cpp:211-227 |
| The iai_control_msgs/MultiJointVelocityImpedanceCommand definition declares velocity as a float32 array in rad/s; stiffness, damping and add_torque are also declared. | upstream_code | iai_stuff/iai_common_msgs/iai_control_msgs/msg/MultiJointVelocityImpedanceCommand.msg:4-10 |
| The controller constructor initializes watchdog_period to 0.1. | upstream_code | iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/src/multi_joint_velocity_impedance_controller.cpp:44-46 |
| The controller header declares watchdog_time_ as ros::Time and watchdog_period as ros::Duration. | upstream_code | iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/include/iai_robot_mechanism_controllers/multi_joint_velocity_impedance_controller.h:95-96 |
| The controller update replaces every desired velocity with zero when the time since watchdog_time_ exceeds watchdog_period. | upstream_code | iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/src/multi_joint_velocity_impedance_controller.cpp:169-177 |
| lwr_loopback_sim_controllers.launch sets /use_sim_time false, requests a 250 Hz joint-state publish rate, starts the loopback_controller_manager node and sets dt 0.004 s, damping 0.0 and mass 0.01. | upstream_code | kuka_lwr_bringup/launch/controllers/lwr_loopback_sim_controllers.launch:7-22 |
| LoopbackControllerManager's init creates a pr2_controller_manager::ControllerManager, reads dt, damping and mass parameters (defaults 0.01, 0.1 and 0.1) and subscribes the private desired_joints topic, whose callback writes the received joint positions into the joint states. | upstream_code | iai_stuff/iai_control_pkgs/loopback_controller_manager/loopback_controller_manager.cpp:103-138 |
| LoopbackControllerManager::simulateJoints integrates commanded effort, damping, mass and dt into joint velocity and then joint position; a comment says KDL should be used for correct dynamics. | upstream_code | iai_stuff/iai_control_pkgs/loopback_controller_manager/loopback_controller_manager.cpp:210-226 |
| kdl_arm_kinematics advertises the private services get_fk, get_ik, get_ik_solver_info, get_fk_solver_info and get_weighted_ik. | upstream_code | iai_stuff/iai_control_pkgs/kdl_arm_kinematics/src/arm_kinematics.cpp:142-147 |
| urdf_management's service.lisp registers an alter_urdf service. | upstream_code | iai_stuff/iai_control_pkgs/urdf_management/src/service.lisp:56 |
| lasa_to_iai.py subscribes /KUKA/joint_imp_cmd as a JointStateImpedance and publishes /r_arm_pos_controller/command and /r_arm_vel/command. | upstream_code | lasa_to_iai_parser/scripts/lasa_to_iai.py:25-27 |
| lasa_to_iai.py republishes the velocity of every /KUKA/joint_imp_cmd message that carries num_dof velocities as a MultiJointVelocityImpedanceCommand on /r_arm_vel/command. | upstream_code | lasa_to_iai_parser/scripts/lasa_to_iai.py:59-70 |
| The arm xacro declares joint 0 as revolute with limit lower -170 * M_PI / 180, upper 170 * M_PI / 180, effort 204 and velocity arm_velocity_scale_factor * 110 * M_PI / 180 (an unsigned magnitude). | upstream_code | kuka_lwr_description/urdf/kuka_lwr_arm_lasa.urdf.xacro:55-59 |
| lwr_start_config.yaml lists the seven right-arm joint names and their positions under joints/name and joints/position. | upstream_code | kuka_lwr_bringup/config/lwr_start_config.yaml:1-17 |
| lwr_simulation.launch includes lwr_realtime.launch with realtime false, the loopback, velocity and position controller launch files, and starts the lasa_to_iai_parser node. | upstream_code | kuka_lwr_bringup/launch/lwr_simulation.launch:8-29 |
| lwr_sim_pos_controllers.launch starts r_arm_state_separator with ~in_joint_states remapped to /joint_states and ~out_joint_states to /r_arm_pos_controller/joint_states, and r_arm_pos_controller (joint_p_ctrl.py) with ~vel_command_out remapped to /r_arm_vel/command. | upstream_code | kuka_lwr_bringup/launch/controllers/lwr_sim_pos_controllers.launch:6-14 |
| JController.control_tick returns without publishing when more than rospy.Duration(0.1) has passed since last_command_time, and otherwise publishes the P-controller velocity clipped to max_speed on ~vel_command_out while that publisher has connections. | upstream_code | iai_stuff/iai_control_pkgs/iai_control_utils/src/iai_control_utils/jcontroller.py:118-145 |
| lwr_sim_vel_controllers.yaml gives every r_arm_vel joint the gains p 2.5, i 0.0 and d 0.0 under the comment 'for perfect sim: chose p=m/dt with damping=0'. | upstream_code | kuka_lwr_bringup/config/lwr_sim_vel_controllers.yaml:11-22 |
| lwr_realtime.launch defaults realtime to true and then starts joint_state_publisher with source_list /KUKA/joint_states and rate 500. | upstream_code | kuka_lwr_bringup/launch/lwr_realtime.launch:8-26 |
| lwr2_realtime.launch starts joint_state_publisher with source_list /KUKA/joint_states and rate 500 without a realtime condition. | upstream_code | kuka_lwr_bringup/launch/lwr2_realtime.launch:16-21 |
| lwr2_simulation.launch includes lwr2_realtime.launch, the loopback, velocity and position controller launch files, and starts the lasa_to_iai_parser node. | upstream_code | kuka_lwr_bringup/launch/lwr2_simulation.launch:9-27 |
| The README's simulation quick start runs roslaunch kuka_lwr_bringup lwr2_alone_simulation.launch. | vendor_doc | README.md:24-28 |
| The README's realtime visualization starts lwr2_alone_realtime.launch with the kuka_fri_bridge and says the kuka_fri_bridge will be publishing the /joint_states topic. | vendor_doc | README.md:61-67 |

## Scope

The package binds one velocity publication on `/r_arm_vel/command`
(`iai_control_msgs/MultiJointVelocityImpedanceCommand`) and one explicit
observation on `/joint_states` (`sensor_msgs/JointState`).  The controller
configuration names `r_arm_vel` and the seven right-arm joints, and the
controller subscribes the relative `command` name; the resolved endpoint is a
deployment assumption, not an upstream Fact.  The observation is an explicit
subscribe capability, so the empty resource snapshot never waits for a topic
that the external controller may stop publishing.

The README's `/KUKA/joint_imp_cmd` path is served by the `lasa_to_iai` parser
with the external `kuka_fri_bridge/JointStateImpedance` type.  That type is not
in the pinned clone, so this package does not bind it; it binds the parser's
`/r_arm_vel/command` output, which the README also names as the command topic.
The arm and position-controller outputs are not exposed as separate MHS
capabilities.

## Safety

The device is simulated but moves a robot arm, so `risk` is R2.  The pinned
clone advertises no stop, pause, cancel, controller-switch or reset service or
action.  The kdl_arm_kinematics queries (`arm_kinematics.cpp:142-147`) and
`urdf_management`'s Lisp `alter_urdf` service (`service.lisp:56`) are not
stops.  The velocity controller's update zeroes the desired velocity when its
command watchdog is active
(`multi_joint_velocity_impedance_controller.cpp:169-177`), but the watchdog is
a timeout on the command stream: it is reached by silence, not by an
acknowledged stop request, and its period is a constructor default (`:44-46`).

The e-stop is a sensed-confirmation stop (SAFE-049, simulated only).  The
request publishes seven zero joint velocities on `/r_arm_vel/command` and
proves nothing by itself.  The source is `/r_arm_vel/state`
(`pr2_controllers_msgs/JointTrajectoryControllerState`), the relative name
`state` at `multi_joint_velocity_impedance_controller.cpp:128-130`, with the
type include at `multi_joint_velocity_impedance_controller.h:53`.  This is ROS
1, so the source declares no publisher history; the bridge discards the first
sample of the new subscription.  The predicate reads `desired.velocities`
(`:199`, the applied command `command[j]` after the watchdog, not a plant
measurement) with one `abs_max` per element, and the norm of
`actual.velocities` (`:201`, `joints_[j]->velocity_`).  The clone states no
numeric tolerance and no at-rest bound, so every threshold is
`operator_required`.  The fake placeholders are in
`fixtures/estop-confirmation.json` (`desired_v0` through `desired_v6` at 0.0
and `actual_norm` at 0.02); they are not device facts.  The client bounds
(`consecutive` 2, `min_span_ms` 40, `max_gap_ms` 500, `confirm_within_ms` 800)
are fake-scale.  A live deployment sets thresholds and bounds in
`simulation_deployment['estop_confirmation']`.  `estop_latency_ms` is 1300,
the 500 ms request timeout plus `confirm_within_ms`.  Nothing is claimed after
the confirmation window.

`lwr_simulation.launch` also starts the `lasa_to_iai` parser, which republishes
every `/KUKA/joint_imp_cmd` velocity array on `/r_arm_vel/command`
(`lasa_to_iai.py:59-70`), and the `r_arm_pos_controller` P-controller, whose
velocity output is remapped to `/r_arm_vel/command` and which publishes while
position goals arrive (`lwr_sim_pos_controllers.launch:6-14`,
`jcontroller.py:118-145`).  Either keeps `desired.velocities` off zero, so the
stop stays unconfirmed and latched.  There is no unpause and no re-enable:
this package cannot clear a command those nodes store.  The operator stops
them outside MHS.  A reset re-confirms the sensed state read-only and is
refused when it no longer holds.

`lwr_realtime.launch` (realtime defaults to true) and `lwr2_realtime.launch`
start `joint_state_publisher`, which republishes the real arm's
`/KUKA/joint_states` as `/joint_states` at 500 Hz.  The sensed source is
`/r_arm_vel/state`, not `/joint_states`, and those realtime launches do not
start this controller.  The SDK cannot prove a ROS graph is simulated.  A real
controller of this class behind `/r_arm_vel/command` would act on the same
publication; that path is out of scope and stays R2.  The README's quick start
names `lwr2_alone_simulation.launch`, which is not in the pinned clone.

The controller adds PID effort onto `commanded_effort_` (`:180-188`).  The
loopback's `simulateJoints` integrates that effort (`loopback_controller_manager.cpp:210-226`).
The clone's loopback update does not show `commanded_effort_` being cleared
each cycle, and whether the external `pr2_controller_manager` clears it is not
in this clone.  The shipped comment `for perfect sim: chose p=m/dt with
damping=0` (`lwr_sim_vel_controllers.yaml:11-22`) is cited as written.  It is
not treated as a statement that one update sets joint velocity to the command.
The fake echoes the commanded velocity into `actual.velocities` at once and
does not integrate the loopback.

## Limits

The URDF states unsigned arm-velocity magnitudes (for example
`arm_velocity_scale_factor * 110 * M_PI / 180` on joint 0;
`kuka_lwr_arm_lasa.urdf.xacro:55-59`) and no signed command envelope
for `/r_arm_vel/command`.  The velocity input is therefore
`Limit.operator_required`; every velocity call is refused with
`MHS.SAFETY.LIMITS_UNSET` until an operator installs a reviewed
`site-limits.json`.  `site-limits.example.json` (-0.25..0.25 rad/s) is an
example overlay for the fake gate only, not a fact or a device bound.

## Tags

`ros`, `ros1`, `simulation`, `kuka`, `lwr`, `joint-state`, `velocity`, `rviz`
