OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.sqrt81/src_dog

Every fact cites the pinned clone at commit `1399108d258e964ef04850ddbfb6865dbd117000`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this
page.

## Facts

| fact | source | ref |
|---|---|---|
| The dog_ros launch remaps the node's private imu, joint_state and joint_cmd endpoints to /dog/imu, /dog/joint_states and /dog/gazebo_pve_controller/command. | upstream_code | dog_ros/launch/control.launch:10-12 |
| SimulatedHardware uses a private node handle, subscribes to the relative imu and joint_state topics and advertises joint_cmd as std_msgs/Float64MultiArray. | upstream_code | dog_ros/src/hardware/SimulatedHardware.cpp:14-20 |
| SimulatedHardware::PublishCommand resizes the Float64MultiArray data to 60 and writes five twelve-element blocks: desired positions, kp, desired velocities, kd and feed-forward torque. | upstream_code | dog_ros/src/hardware/SimulatedHardware.cpp:59-75 |
| GazeboPVEController::commandCB rejects a message whose data size is not joint_cnt_ * 5 and otherwise copies the five blocks into its joint commands. | upstream_code | gazebo_pve_controller/src/gazebo_pve_controller.cpp:288-310 |
| GazeboPVEController::update clamps pos_err * kp + vel_err * kd + torque for each joint to plus or minus that joint's joint_torque_limit_ entry. | upstream_code | gazebo_pve_controller/src/gazebo_pve_controller.cpp:241-254 |
| GazeboPVEController::init accepts only revolute joints and fills joint_torque_limit_ from each joint's URDF effort limit. | upstream_code | gazebo_pve_controller/src/gazebo_pve_controller.cpp:108-122 |
| The default controllers.yaml lists twelve actuated leg joints in the order fl_hip_x, fl_hip_y, fl_knee, fr_hip_x, fr_hip_y, fr_knee, bl_hip_x, bl_hip_y, bl_knee, br_hip_x, br_hip_y and br_knee. | upstream_code | dog_model/config/controllers.yaml:7-19 |
| motor.lua maps the same twelve joint names to motor indices zero through eleven. | upstream_code | dog_control/config/motor.lua:8-21 |
| SimulatedHardware::JointStateCb rejects a JointState unless its name, position, velocity and effort arrays each have twelve entries, and derives joint velocity from the position difference. | upstream_code | dog_ros/src/hardware/SimulatedHardware.cpp:94-120 |
| SimulatedHardware::JointStateCb finds each entry's motor index by its joint name and logs an error for an unknown name. | upstream_code | dog_ros/src/hardware/SimulatedHardware.cpp:103-121 |
| The libgazebo_ros_p3d.so plugin is configured with updateRate 1000.0, bodyName torso, topicName ground_truth/state and frameName world. | upstream_code | dog_model/urdf/dog.gazebo:41-49 |
| The dog_world launch remaps the odom_to_tf subscriber's odom name to /ground_truth/state. | upstream_code | dog_model/launch/dog_world.launch:52-53 |
| The Odom2TF.py script imports nav_msgs.msg.Odometry and subscribes to its odom topic with that type. | upstream_code | dog_model/scripts/Odom2TF.py:9-15 |
| The Gazebo IMU sensor plugin publishes on /dog/imu for the torso body at an update rate of 500 Hz. | upstream_code | dog_model/urdf/dog.gazebo:59-62 |
| The leg macro declares hip_x limits of -3.00 to 3.00. | upstream_code | dog_model/urdf/leg.xacro:58-60 |
| The leg macro declares hip_y limits of -3.89 to 1.50. | upstream_code | dog_model/urdf/leg.xacro:106-108 |
| The leg macro declares knee limits of -2.70 to 2.70. | upstream_code | dog_model/urdf/leg.xacro:155-157 |
| defines.xacro sets MOTOR_TORQUE_MAX to 17 and MOTOR_VELOCITY_MAX to 40. | upstream_code | dog_model/urdf/defines.xacro:22-23 |
| The motor joint macro writes MOTOR_TORQUE_MAX and MOTOR_VELOCITY_MAX as the URDF limit effort and velocity. | upstream_code | dog_model/urdf/defines.xacro:76-80 |
| The dog_ros main function casts argc and argv to void and calls only test_DynamicsDiff(argc, argv). | upstream_code | dog_ros/src/main.cpp:1-8 |
| CMakeLists.txt globs every src/*.cpp file, including the test sources, into ALL_SRCS and leaves the removal of TEST_SRCS commented out. | upstream_code | dog_ros/CMakeLists.txt:27-29 |
| The package adds one dog_ros_node executable from ALL_SRCS. | upstream_code | dog_ros/CMakeLists.txt:158 |

## Scope

The package serves the primary wire surface of the Gazebo quadruped: one flat
`std_msgs/Float64MultiArray` on `/dog/gazebo_pve_controller/command`, with the
five twelve-element blocks written by `SimulatedHardware::PublishCommand`
(`dog_ros/src/hardware/SimulatedHardware.cpp:59-75`). The same frame is checked by
`GazeboPVEController::commandCB`; a length other than `joint_cnt_ * 5` is
rejected (`gazebo_pve_controller/src/gazebo_pve_controller.cpp:288-310`). The
command order is the twelve joints of `dog_model/config/controllers.yaml:7-19`.

Observations are `sensor_msgs/JointState` on `/dog/joint_states`,
`sensor_msgs/Imu` on `/dog/imu` and `nav_msgs/Odometry` on
`/ground_truth/state`. The joint-state message carries twelve names and twelve
positions; `JointStateCb` derives velocity from the position difference
(`dog_ros/src/hardware/SimulatedHardware.cpp:94-120`), so the driver reads the
published positions rather than claiming the message's velocity channel is
used by the controller. `JointStateCb` maps each entry to a motor by its name
(`SimulatedHardware.cpp:103-121`); the read returns the positions in the
message's own name order without the names, which need not be the
`controllers.yaml` order (model review, 2026-11-05: the author's description
claimed the controller order).

The default `controllers.yaml` has twelve joints. The optional tail
configuration (`controllers_tail.yaml`) adds two tail joints and is not served
by this package.

## Limits

No source in the clone states a kp or kd bound: the controller clamps only the
resulting torque to the URDF effort limit
(`gazebo_pve_controller/src/gazebo_pve_controller.cpp:241-254`, filled at 108-122). The flat frame
also mixes four units (rad, rad/s, N.m and the two PD gains), so a single
sourced scalar cannot bound it. The command input therefore declares
`Limit.operator_required`; without an operator overlay every command is refused
with `MHS.SAFETY.LIMITS_UNSET`. The URDF statements of joint travel (-3.00 to
3.00, -3.89 to 1.50 and -2.70 to 2.70) and the effort 17 and velocity 40 that
`defines.xacro:22-23` sets and `defines.xacro:76-80` writes into each joint limit
are source facts, not a substitute for the per-element operator envelope (model
review, 2026-11-05: the author cited `defines.xacro:29-30`, which holds collision
sizes).

`site-limits.example.json` is an illustrative fake-only overlay. It fills the
operator-required limit so the in-process conformance run can exercise the
publication path; it is not a device bound and must be replaced at deployment.

## Safety

The device is simulated at R2 because the command drives a mobile quadruped.
The pinned clone has no ROS stop, pause or reset service and no action. A
zero-valued command frame removes the PD hold and is not a safe state, and a
rosbridge publication proves only that the message was transmitted. The package
declares no e-stop or safe-state binding; the runtime still latches in software,
and an e-stop reports `MHS.SAFETY.SAFE_STATE_UNREACHED` while the latch stays
engaged. No hardware emergency stop is claimed, and `reviewed_by` stays null.

The shipped `dog_ros_node` calls only `test_DynamicsDiff` (`main.cpp:1-8`) and
constructs no `SimulatedHardware`; the control loop and publisher exist only in
the test source files, which the launch file does not start. A live run
therefore needs a controller process outside this package, and no live ROS
graph or Gazebo run has been performed.

## Fidelity contract

The fake is a ROS-free `RecordingRosTransport`, not a capture of Gazebo traffic.
It claims F0: engine `analytic:ROS contract fake (no Gazebo physics)`,
determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`, reset `none`, no
snapshot/restore. Topic samples are fixed placeholders and do not advance with
simulation time. The gaps disclose the absent Gazebo world, ODE solver,
contacts, controller update, the optional tail configuration and the missing
stop path.

## Tags

`ros`, `ros1`, `gazebo`, `simulation`, `quadruped`, `mobile-base`,
`joint-command`, `motor-command`
