# Facts and tags for gh.andrejorsula/panda_gz_moveit2

Every fact cites the pinned clone at commit `8e5c6fd5d0d39ce2ad1d14968f86104f4ae0b9cb`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the statement spans
adjacent lines. The same facts are written into `driver.py` (`facts = [...]`); the reference files are
generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The repository provides Franka Emika Panda software packages that enable manipulation with MoveIt 2 inside Gazebo and use gz_ros2_control for control. | vendor_doc | README.md:3 |
| The branch targets ROS 2 Galactic and Gazebo Fortress. | vendor_doc | README.md:11 |
| panda_moveit_config's README says move_group.launch.py configures MoveIt 2 to plan motions inside a simulation and that the real robot is not yet supported. | vendor_doc | panda_moveit_config/README.md:9 |
| The README's ign_control example executes motions with simulated controllers. | vendor_doc | panda_moveit_config/README.md:33 |
| servo.yaml sets command_out_type to trajectory_msgs/JointTrajectory. | upstream_code | panda_moveit_config/config/servo.yaml:15 |
| servo.yaml sets command_out_topic to /joint_trajectory_controller/joint_trajectory. | upstream_code | panda_moveit_config/config/servo.yaml:50 |
| servo.yaml sets move_group_name to arm. | upstream_code | panda_moveit_config/config/servo.yaml:27 |
| servo.yaml sets incoming_command_timeout to 0.25, commented 'Stop servoing if X seconds elapse without a new command', and num_outgoing_halt_msgs_to_publish to 1. | upstream_code | panda_moveit_config/config/servo.yaml:35-38 |
| moveit_controller_manager.yaml lists joint_trajectory_controller and gripper_trajectory_controller as the controller names. | upstream_code | panda_moveit_config/config/moveit_controller_manager.yaml:1-3 |
| The joint_trajectory_controller entry uses action_ns follow_joint_trajectory, type FollowJointTrajectory and is the default controller. | upstream_code | panda_moveit_config/config/moveit_controller_manager.yaml:6-9 |
| controllers_effort.yaml configures the controller manager at 250 Hz with a joint_state_broadcaster and two joint_trajectory_controller instances. | upstream_code | panda_moveit_config/config/controllers_effort.yaml:1-12 |
| controllers_effort.yaml gives the arm joint_trajectory_controller the seven panda_joint names, the effort command interface and position and velocity state interfaces. | upstream_code | panda_moveit_config/config/controllers_effort.yaml:14-28 |
| panda.ros2_control declares a ros2_control system whose hardware plugin is fake_components/GenericSystem for the fake plugin and ign_ros2_control/IgnitionSystem for the ign plugin. | upstream_code | panda_description/urdf/panda.ros2_control:23-30 |
| panda.gazebo loads the ign_ros2_control-system plugin with the controller parameter file. | upstream_code | panda_description/urdf/panda.gazebo:11-14 |
| The generated URDF declares lower and upper position limits for the seven revolute panda_joint joints. | upstream_code | panda_description/urdf/panda.urdf:43-307 |
| initial_joint_positions.yaml starts the arm at joint1 0, joint2 -0.7853981633974483, joint3 0, joint4 -2.356194490192345, joint5 0, joint6 1.5707963267948966 and joint7 0.7853981633974483. | upstream_code | panda_description/config/initial_joint_positions.yaml:2-9 |
| The SRDF defines the arm chain from panda_link0 to panda_hand_tcp. | upstream_code | panda_moveit_config/srdf/panda.srdf:8-9 |
| move_group.launch.py starts moveit_servo's servo_node_main with the servo parameters when enable_servo is true. | upstream_code | panda_moveit_config/launch/move_group.launch.py:265-282 |
| move_group.launch.py declares ros2_control_command_interface with default effort and enable_servo with default true. | upstream_code | panda_moveit_config/launch/move_group.launch.py:426-439 |
| move_group.launch.py spawns every controller named in moveit_controller_manager.yaml plus joint_state_broadcaster. | upstream_code | panda_moveit_config/launch/move_group.launch.py:309-321 |
| ex_ign_control.launch.py launches Ignition Gazebo with the -r flag and includes move_group.launch.py with the ign ros2_control plugin and the effort command interface. | upstream_code | panda_moveit_config/launch/ex_ign_control.launch.py:30-56 |
| ex_ign_control.launch.py bridges /clock from Ignition to rosgraph_msgs/msg/Clock. | upstream_code | panda_moveit_config/launch/ex_ign_control.launch.py:76-82 |
| panda_ign_moveit2.repos pulls ros_ign galactic, ign_ros2_control devel and ros2_controllers jtc_effort from external repositories. | upstream_code | panda_ign_moveit2.repos:1-13 |
| panda_moveit_config/package.xml depends on control_msgs, controller_manager, joint_trajectory_controller, moveit_servo and moveit. | upstream_code | panda_moveit_config/package.xml:16-24 |

## Scope

The only command endpoint fully declared in the pinned repository is the MoveIt Servo outgoing topic
`/joint_trajectory_controller/joint_trajectory` with type `trajectory_msgs/JointTrajectory`
(`panda_moveit_config/config/servo.yaml:15,50`). The repository's controllers are also driven through
MoveIt's `FollowJointTrajectory` actions (`panda_moveit_config/config/moveit_controller_manager.yaml:6-9`),
but the clone only states the short type name and an `exec_depend` on `control_msgs`; the exact
`control_msgs/action/FollowJointTrajectory` wire type is not declared at this pin. A G7 citation therefore
cannot prove that action endpoint, and this package does not expose it. The `/joint_states` observation is
referenced by name in `servo.yaml:48` but its `sensor_msgs/msg/JointState` type is likewise not declared in
the clone, so it is not exposed either.

A publication on the Servo output topic is a real command path for the shipped configuration: the Servo
node is launched with this `command_out_topic` (`move_group.launch.py:265-282`) and publishes
`trajectory_msgs/JointTrajectory` there (`servo.yaml:15`). It bypasses Servo's input processing, smoothing,
collision checks and `incoming_command_timeout` (those apply to Servo's incoming command topics, not to a
third-party publisher on the output topic). Because `move_group.launch.py` declares `enable_servo` with
default true (`move_group.launch.py:426-439`), Servo itself publishes on the same topic in a default launch,
and `move_group` executes plans through the same controller's `follow_joint_trajectory` action; neither is
fenced by the MHS latch. `ex_ign_control.launch.py` starts Gazebo running (`-r`), so an accepted trajectory
keeps executing in the free-running simulation after an e-stop.

## Limits

The seven arm-joint travel bounds come from the generated URDF (`panda_description/urdf/panda.urdf:43-307`):
joint1/3/5/7 are -2.897246558310587..2.897246558310587 rad, joint2 is
-1.7627825445142729..1.7627825445142729 rad, joint4 is -3.07177948351002..-0.06981317007977318 rad and
joint6 is -0.017453292519943295..3.752457891787808 rad. The clone states no trajectory-duration envelope
for the output topic, so `time_from_start.sec` and `time_from_start.nanosec` are
`Limit.operator_required`; the deployed site supplies their bounds in `site-limits.json`. The example
overlay in this package is test data only.

## Safety

The device is simulated at R2 because it is a robot arm. No source-backed stop, pause, controller-switch or
safe-state endpoint is declared in the pinned clone. The runtime latches in software and refuses further
publications, but a publication already sent may still be executed by the external
`joint_trajectory_controller`; nothing in this package senses or confirms a stopped state. The package
therefore declares no `estop_physical_ref`, no safe-state action and no `safety_bindings`, and it is
blocked rather than claiming a safe stop. This is not a physical emergency stop and no hardware run is
claimed.

## Fidelity

The fake is an F0 ROS-free recording transport. It records the advertised and published
`trajectory_msgs/msg/JointTrajectory` messages and runs no Gazebo, MoveIt, Servo or controller. Its stored
trajectory is placeholder test data. The publication is not acknowledged, so the fake cannot show
controller acceptance, interpolation, execution, feedback, collision behaviour or stopping. The
acknowledged `FollowJointTrajectory` action, `/joint_states`, `/move_action`, the gripper controller,
`/clock` and the Gazebo physics are out of scope.

## Tags

`ros`, `ros2`, `gazebo`, `fortress`, `moveit2`, `servo`, `panda`, `robot-arm`, `trajectory`, `simulation`,
`ros2-control`
