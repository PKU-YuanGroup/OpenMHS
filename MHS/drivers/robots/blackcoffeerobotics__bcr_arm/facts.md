# Facts and tags for gh.blackcoffeerobotics/bcr_arm

Facts about the package's own surface cite the pinned clone at commit `9bd3d60b306bb2ed22f5cb1fd588aca99081a711` (`path/in/clone:LINE`). Facts about the stop cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones fetched under `work/companions`, listed in its `LOCK.json`), written `companion:<alias>/<path>:<LINE>`: `ros2_control` (gh.ros-controls/ros2_control, fetched under work/companions as `ros-controls__ros2_control@2.54.4` at `7f26da889aa0898442d1c0a135ae001add1a9878`), `ros2_controllers` (gh.ros-controls/ros2_controllers, fetched under work/companions as `ros-controls__ros2_controllers@2.54.1` at `65db73628ebac1948833f0fbdc60973c74d6cd0e`) and `gz_ros2_control` (gh.ros-controls/gz_ros2_control, fetched under work/companions as `ros-controls__gz_ros2_control@0.7.21` at `3f341cd49ed579cfb17422582eb14920c203f269`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it, and for a fetched companion also its LOCK.json entry, untracked files and write bits. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The repository contains a Gazebo Fortress simulation for a 7-DOF robotic arm with ROS 2 Control integration and MoveIt motion planning. | vendor_doc | README.md:7 |
| The README calls bcr_arm.gazebo.launch.py the primary launch file and says it uses ROS 2 mock controllers for the arm. | vendor_doc | README.md:59-65 |
| ArmControllerCLI creates a FollowJointTrajectory ActionClient on the absolute /joint_trajectory_controller/follow_joint_trajectory endpoint. | upstream_code | bcr_arm_gazebo/scripts/control_arm_cli.py:21 |
| control_arm_cli.py imports control_msgs.action.FollowJointTrajectory. | upstream_code | bcr_arm_gazebo/scripts/control_arm_cli.py:6 |
| ArmControllerCLI lists the seven controlled joints as joint1 through joint7 in that order. | upstream_code | bcr_arm_gazebo/scripts/control_arm_cli.py:24-32 |
| ArmControllerCLI builds one JointTrajectoryPoint with positions and a time_from_start Duration, appends it to trajectory.points and sends the goal asynchronously. | upstream_code | bcr_arm_gazebo/scripts/control_arm_cli.py:87-99 |
| The MoveIt simple controller manager names joint_trajectory_controller, type FollowJointTrajectory, action_ns follow_joint_trajectory and default true. | upstream_code | bcr_arm_moveit_config/config/moveit_controllers.yaml:9-20 |
| ros2_controllers.yaml configures joint_trajectory_controller for joint1 through joint7, with a position command interface and position and velocity state interfaces. | upstream_code | bcr_arm_moveit_config/config/ros2_controllers.yaml:1-26 |
| ros2_control.urdf.xacro declares gz_ros2_control/GazeboSimSystem and a position command interface with position, velocity and effort state interfaces for each of the seven joints. | upstream_code | bcr_arm_description/urdf/control/ros2_control.urdf.xacro:4-50 |
| gazebo_sim_ros2_control.urdf.xacro loads the gz_ros2_control::GazeboSimROS2ControlPlugin with the controller YAML path. | upstream_code | bcr_arm_description/urdf/control/gazebo_sim_ros2_control.urdf.xacro:5-13 |
| The Gazebo bringup bridges /joint_states as sensor_msgs/msg/JointState. | upstream_code | bcr_arm_gazebo/launch/bringup.gazebo.launch.py:209 |
| The Gazebo bringup bridge also carries /clock and /tf and starts a separate image bridge for the camera topics. | upstream_code | bcr_arm_gazebo/launch/bringup.gazebo.launch.py:203-226 |
| The arm xacro gives joint1, joint3, joint5 and joint7 the revolute range -6.28..6.28 rad and joint2, joint4 and joint6 the range -2.0..2.0 rad. | upstream_code | bcr_arm_description/urdf/mech/bcr_arm_mech.urdf.xacro:141-356 |
| joint_limits.yaml sets max_velocity 2.0 for joint1 through joint4, 3.0 for joint5 and joint6, and 4.0 for joint7; max_acceleration is 1.0, 1.5 and 2.0 respectively. | upstream_code | bcr_arm_moveit_config/config/joint_limits.yaml:10-45 |
| initial_positions.yaml starts all seven joints at 0.0. | upstream_code | bcr_arm_moveit_config/config/initial_positions.yaml:1-10 |
| bcr_arm.gazebo.launch.py starts the Gazebo server and spawns the joint_state_broadcaster and joint_trajectory_controller controllers. | upstream_code | bcr_arm_gazebo/launch/bcr_arm.gazebo.launch.py:201-243 |
| The launch's spawners name the controller manager /controller_manager. | upstream_code | bcr_arm_gazebo/launch/bcr_arm.gazebo.launch.py:223-243 |
| The Gazebo launch's ros2_controllers_path defaults to bcr_arm_moveit_config's config/ros2_controllers.yaml. | upstream_code | bcr_arm_gazebo/launch/bcr_arm.gazebo.launch.py:118-130 |
| The launch starts gz_sim with the -r argument, so the simulation runs from the start. | upstream_code | bcr_arm_gazebo/launch/bcr_arm.gazebo.launch.py:201-206 |
| The controller manager creates the list_controllers service with the controller_manager_msgs::srv::ListControllers type under its private name. | upstream_code | companion:ros2_control/controller_manager/src/controller_manager.cpp:537-539 |
| The controller manager creates the switch_controller service with the controller_manager_msgs::srv::SwitchController type under its private name. | upstream_code | companion:ros2_control/controller_manager/src/controller_manager.cpp:557-560 |
| switch_controller_service_cb passes the request's controllers to activate and deactivate, its strictness, activate_asap and timeout to switch_controller and answers ok only when that returns OK. | upstream_code | companion:ros2_control/controller_manager/src/controller_manager.cpp:1980-2031 |
| switch_controller asks the realtime update loop for the switch and waits for it up to the request's timeout (1 s when it is zero); when the wait times out it clears the request and returns ERROR. | upstream_code | companion:ros2_control/controller_manager/src/controller_manager.cpp:1307-1331 |
| The controller manager's update loop performs a requested switch. | upstream_code | companion:ros2_control/controller_manager/src/controller_manager.cpp:2224-2228 |
| list_controllers fills each ControllerState with the controller's name, type, claimed interfaces and lifecycle state label. | upstream_code | companion:ros2_control/controller_manager/src/controller_manager.cpp:1748-1755 |
| SwitchController defines strictness STRICT as 2, under which the switch fails if anything goes wrong, and returns ok when the controllers were switched. | upstream_code | companion:ros2_control/controller_manager_msgs/srv/SwitchController.srv:5-33 |
| ControllerState's state field is unconfigured, inactive, active or finalized. | upstream_code | companion:ros2_control/controller_manager_msgs/msg/ControllerState.msg:1-2 |
| On deactivation the trajectory controller aborts an active goal, keeps each position command at its last value, releases its interfaces and drops its stored trajectory. | upstream_code | companion:ros2_controllers/joint_trajectory_controller/src/joint_trajectory_controller.cpp:1055-1106 |
| On activation the trajectory controller takes its current and last commanded state from the command interfaces when set_last_command_interface_value_as_state_on_activation is set and the command read succeeds, and otherwise reads both from the state interfaces. | upstream_code | companion:ros2_controllers/joint_trajectory_controller/src/joint_trajectory_controller.cpp:1004-1020 |
| set_last_command_interface_value_as_state_on_activation defaults to true: the last command interface value is then used as both the current state and the last commanded state on activation. | upstream_code | companion:ros2_controllers/joint_trajectory_controller/src/joint_trajectory_controller_parameters.yaml:75-79 |
| Reading the state from the command interfaces fails when the controller has a velocity state interface but no velocity command interface with values. | upstream_code | companion:ros2_controllers/joint_trajectory_controller/src/joint_trajectory_controller.cpp:498-510 |
| On activation the trajectory controller starts by holding the position of the state it starts from. | upstream_code | companion:ros2_controllers/joint_trajectory_controller/src/joint_trajectory_controller.cpp:1027-1029 |
| set_hold_position commands the positions of the controller's current state (state_current_). | upstream_code | companion:ros2_controllers/joint_trajectory_controller/src/joint_trajectory_controller.cpp:1617-1626 |
| The trajectory controller rejects a new action goal while it is inactive. | upstream_code | companion:ros2_controllers/joint_trajectory_controller/src/joint_trajectory_controller.cpp:1251-1262 |
| gz_ros2_control names its controller manager node controller_manager unless the SDF names another. | upstream_code | companion:gz_ros2_control/gz_ros2_control/src/gz_ros2_control_plugin.cpp:312-317 |
| gz_ros2_control creates the controller manager in the plugin node's namespace and adds it to its executor. | upstream_code | companion:gz_ros2_control/gz_ros2_control/src/gz_ros2_control_plugin.cpp:498-506 |
| gz_ros2_control writes the joint commands on every simulation step and reads and updates the controllers at the controller period. | upstream_code | companion:gz_ros2_control/gz_ros2_control/src/gz_ros2_control_plugin.cpp:529-581 |
| For a position-controlled joint the Gazebo system turns the error to the position command into a target velocity. | upstream_code | companion:gz_ros2_control/gz_ros2_control/src/gz_system.cpp:839-846 |

## Scope

The selected interface is the controller's acknowledged ROS 2
`control_msgs/action/FollowJointTrajectory` action at
`/joint_trajectory_controller/follow_joint_trajectory` and the bridged
`sensor_msgs/msg/JointState` observation at `/joint_states`.  The action goal carries the
seven joint names in `joint1..joint7` order and an array of `JointTrajectoryPoint`
messages; the driver exposes one input array of point objects with the same
`positions` and `time_from_start` shape.  The action terminal result is the
controller's `error_code` and `error_string`; it is a controller result, not a
measured stopped state.

The clone also contains a fire-and-forget publisher on
`/joint_trajectory_controller/joint_trajectory`
(`bcr_arm_gazebo/scripts/test_arm_movement.py:13-15,31-45`).  This package does not
expose that publication as a command: the RosDriver documentation treats a topic
publication as transmission only, and the acknowledged action is the primary
control path used by the shipped CLI.

The controller and joint-state bridge are started by the upstream launch; the
operator runs the ROS graph and rosbridge separately.  No namespace, remapping or
endpoint is claimed beyond the absolute names shown in the clone.  A deployment
that namespaces the controller or remaps `/joint_states` must expose the same
absolute endpoints, or the operator must change the package binding.

## Limits

The seven revolute travel ranges come from the model xacro: joint1, joint3,
joint5 and joint7 are `-6.28..6.28 rad`; joint2, joint4 and joint6 are
`-2.0..2.0 rad`.  These are the installed model's bounds, not a measurement of a
delivered arm.

The clone does not state a maximum trajectory duration or a nanosecond range for
a `builtin_interfaces/Duration`.  The `time_from_start.sec` and
`time_from_start.nanosec` inputs are therefore `Limit.operator_required`; every
call that sets them is refused with `MHS.SAFETY.LIMITS_UNSET` until the operator
supplies the site's trajectory time envelope in `site-limits.json`.
`site-limits.example.json` is example test data, not a device bound.

## Safety

The device is a robot arm and is declared R2. The pinned clone has no stop, pause or controller-switch binding of its
own; the e-stop is a controller switch served by the controller manager of ros2_control, a reviewed companion fetched
at a pinned commit (controller_manager 2.54.4 for ROS 2 Humble; the controller manager node is named
`controller_manager`, `gz_ros2_control_plugin.cpp:312-317`, and the launch's spawners address it as
`/controller_manager`, `bcr_arm.gazebo.launch.py:223-243`).

`/controller_manager/switch_controller` deactivates `joint_trajectory_controller` with strictness STRICT and a 0.4 s
wait for the controller manager's update loop (`controller_manager.cpp:557-560, 1980-2031, 1307-1331`). On
deactivation the controller aborts an active goal, keeps each position command at its last value, releases its
interfaces and drops its stored trajectory (joint_trajectory_controller 2.54.1, `joint_trajectory_controller.cpp:
1055-1106`); gz_ros2_control keeps writing that last position command (`gz_ros2_control_plugin.cpp:529-562`,
`gz_system.cpp:839-846`), so a joint still converges to the last commanded point of the dropped trajectory. The stop is
confirmed only by the read-back `/controller_manager/list_controllers` with a list-element predicate (E4): exactly one
element named `joint_trajectory_controller` must report the state `inactive` (`controller_manager.cpp:1748-1755`). A
switch that answers ok false (it times out when the update loop does not run, for example with the world paused), a
missing, duplicated or still active controller is `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held and a
background retry. The world, the `joint_state_broadcaster` and `/joint_states` keep running; it is the controller's
state, not a measured standstill, and MoveIt, a spawner or any other ROS 2 client of the switch service can
re-activate the controller after the e-stop (MHS does not watch it afterwards).

The declared re-enable `x-cap.blackcoffeerobotics.activate_controller.v1` (CORE-086) switches the controller on again
with the same service, so the trajectory the e-stop dropped is not resumed (the orchestrator's SAFE-042 condition:
cleared by the stop itself). On activation the controller holds the position of the state it starts from
(`joint_trajectory_controller.cpp:1027-1029, 1617-1626`): the last command-interface values when
`set_last_command_interface_value_as_state_on_activation` (true by default at the pin,
`joint_trajectory_controller_parameters.yaml:75-79`) holds and the command read succeeds, else the measured joint state
(`joint_trajectory_controller.cpp:1004-1020`). The command read fails when a velocity state interface has no velocity
command interface (`joint_trajectory_controller.cpp:498-510`), and this deployment's controller commands position only
and reads position and velocity (`ros2_controllers.yaml:1-26`, the Gazebo launch's default `ros2_controllers_path`,
`bcr_arm.gazebo.launch.py:118-130`), so the re-enable holds the measured position. A configuration that also commanded
velocity would hold the last position command instead, which can differ from the measured position (a joint that had
not reached it, was blocked, or whose command another controller changed while this one was inactive); this package
serves only the configuration it cites. It is refused while the latch is held and runs only on request after `mhs.safety.reset`;
the controller rejects trajectory goals while it is inactive (`joint_trajectory_controller.cpp:1251-1262`). The
deployment's controller_manager, joint_trajectory_controller and gz_ros2_control must be the pinned 2.54.4, 2.54.1 and
0.7.21 releases (Humble with Gazebo Fortress); the clone also documents Jazzy with Harmonic, which this package does
not serve.

## Fidelity contract

`driver.py` describes the deployed recording fake: engine
`analytic:ROS recording fake (no Gazebo physics)`, level F0, determinism `none`,
`timestep_ms: 0`, `realtime_factor: 0`, reset `none`, no snapshot/restore.  The
fake answers the declared action and `/joint_states` endpoints with placeholder
joint state and the two companion controller-manager services: it keeps the trajectory controller's
lifecycle state, which the switch sets and the list reports, and rejects goals while it is inactive.
It runs no Gazebo, `gz_ros2_control`, MoveIt or ROS graph.  The action
goal is applied instantly to the placeholder vector with no interpolation,
timing, dynamics, gravity, collision or controller error behavior.  The camera,
`/clock`, `/tf` and MoveIt planning surfaces are out of scope.

## Tags

`ros`, `ros2`, `gazebo`, `simulation`, `robot-arm`, `trajectory`, `joint-state`
