# Facts and tags for gh.coppolam/ros_mav_swarm_simulator

Every fact cites the pinned clone at commit `eca05eaaecc05242493b176f2f2656f21b14c250`, or a companion
clone named in `task.json` (`companion:<alias>/<path>:<LINE>`). A bounded range is used where the statement
spans adjacent lines. The same facts are written into `driver.py` (`facts = [...]`); the reference files are
generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The behaviour node derives name as the literal uav concatenated with the id parameter, builds cmdtopic as '/' + name + '/cmd_vel' and advertises geometry_msgs/Twist on it. | upstream_code | src/mav_controller/src/behaviour.cpp:400-413 |
| The behaviour node builds its own state topic as '/' + name + '/ground_truth/state' and subscribes to it with the statetracker callback. | upstream_code | src/mav_controller/src/behaviour.cpp:416-420 |
| The velocity controller subscribes the relative command/twist topic with geometry_msgs/TwistStamped and the relative cmd_vel topic with geometry_msgs/Twist. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/velocity_controller.cpp:101-105 |
| The cmd_vel callback stores the received Twist, stamps it with the current ROS time and sets its header frame_id to base_stabilized_frame_. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/velocity_controller.cpp:161-171 |
| The velocity controller transforms base_stabilized linear x and y into the world frame using the current yaw, while linear z passes through unchanged. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/velocity_controller.cpp:216-224 |
| The velocity controller uses command.angular.z as the yaw-rate command and ignores angular.x and angular.y in its control update. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/velocity_controller.cpp:256-262 |
| The velocity controller initializes its linear limiter with the controller node handle and its angular limiter with the yawrate field. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/velocity_controller.cpp:92-93 |
| FieldLimiter starts unbounded; when its max or min parameter exists it reads max (default infinity) and min (default -max). | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_interface/include/hector_quadrotor_interface/limiters.h:52-62 |
| Vector3Limiter::limit clamps each axis, then scales x, y and z together when the xy magnitude exceeds max_xy and again when the full magnitude exceeds max. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_interface/include/hector_quadrotor_interface/limiters.h:121-143 |
| Vector3Limiter initializes x, y and z FieldLimiters and reads max and max_xy from its node handle. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_interface/include/hector_quadrotor_interface/limiters.h:108-119 |
| The shipped controller YAML sets velocity max_xy 10.0 and velocity z max 5.0 (both commented m/s) and, in the attitude section, yawrate max 3.14. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/params/controller.yaml:16-45 |
| The 3mavs launch runs the uav1 spawn and behaviour node inside the uav1 group namespace with id 1. | upstream_code | src/mav_controller/launch/3mavs.launch:13-24 |
| The p3d ground-truth plugin is named quadrotor_groundtruth_sim, uses libgazebo_ros_p3d.so, publishes topicName ground_truth/state at updateRate 100.0 and sets gaussianNoise 0.0. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_gazebo/urdf/quadrotor_sensors.gazebo.xacro:56-61 |
| The statetracker header includes nav_msgs/Odometry.h and declares its callback with a nav_msgs::Odometry ConstPtr. | upstream_code | src/mav_controller/src/trackers/statetracker.h:17-53 |
| The spawn launch passes the relative ground_truth/state name to the message_to_tf odometry_topic parameter. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_gazebo/launch/spawn_quadrotor.launch:38-40 |
| The actions launch starts the pose_action, landing_action and takeoff_action nodes. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_actions/launch/actions.launch:1-5 |
| The landing action server is constructed on the relative action/landing name and its pose client on the relative action/pose name. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_actions/src/landing_action.cpp:42-44 |
| The landing action reads action_frequency 10.0, landing_height 0.3, connection_timeout 10.0 and the misspelled action_timout 30.0 as defaults. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_actions/src/landing_action.cpp:45-53 |
| The landing callback uses the current pose when landing_zone.header.frame_id is empty, sets the target z to min(landing_height, current z), sends the PoseGoal and waits for its result for action_timeout. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_actions/src/landing_action.cpp:56-67 |
| The landing callback sets the action succeeded only when the pose client state is SUCCEEDED and enableMotors(false) returns true; otherwise it sets aborted. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_actions/src/landing_action.cpp:69-78 |
| The Landing action goal carries a geometry_msgs/PoseStamped landing_zone, its result is empty, and the comment says an empty landing zone lands directly below. | upstream_code | src/hector/hector_quadrotor/hector_uav_msgs/action/Landing.action:1-6 |
| The shipped controller params set action_timeout 30.0, command_timeout 0.5, dist_tolerance 0.1, yaw_tolerance 0.35, time_in_tolerance 1.0, landing_height 0.1, takeoff_height 0.1 and estop_deceleration 1.0. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/params/params.yaml:1-13 |
| The controller launch loads controller.yaml under the controller namespace and params.yaml into the launching namespace. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/launch/controller.launch:10-11 |
| The hardware sim advertises the relative enable_motors service with the hector_uav_msgs/EnableMotors type. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controller_gazebo/src/quadrotor_hardware_gazebo.cpp:108 |
| The EnableMotors callback stores the request enable flag in motor_status_.running, returns true and sets the response success flag. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controller_gazebo/src/quadrotor_hardware_gazebo.cpp:274-283 |
| BaseActionServer::enableMotors sends an EnableMotors request and returns the result of the service call, not the response success field. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_actions/include/hector_quadrotor_actions/base_action.h:74-79 |
| The controller launch relays the absolute /estop topic to the relative estop topic. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/launch/controller.launch:16 |
| The attitude controller subscribes the relative estop topic with its estopCb callback. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/attitude_controller.cpp:107 |
| While the motors run and command_timeout is non-zero, an attitude, yawrate or thrust command stamp older than command_timeout sets command_estop_. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/attitude_controller.cpp:153-168 |
| When estop_ or command_estop_ is set, the attitude controller zeroes the roll, pitch and yawrate commands and lowers the thrust by estop_deceleration times mass times the period, not below zero. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/attitude_controller.cpp:181-186 |
| The attitude controller's estop callback only stores the Bool and, on a false-to-true transition, caches the current thrust command; it sends no acknowledgement. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/attitude_controller.cpp:221-231 |
| The behaviour node creates an EnableMotors client on the relative enable_motors name and waits until enableMotors(true) succeeds before its control loop. | upstream_code | src/mav_controller/src/behaviour.cpp:468-469 |
| The behaviour node's collisionchecker calls system("pkill -f ros") when the planar distance is at most 0.3; this is not a ROS stop service. | upstream_code | src/mav_controller/src/behaviour.cpp:110-117 |
| The behaviour loop also calls system("pkill -f ros") once t_elps reaches 5000. | upstream_code | src/mav_controller/src/behaviour.cpp:586-588 |
| The behaviour node defines H_DES 1.0 as the desired level height, STARTTIME 30.0 simulation seconds and ros_rate 10. | upstream_code | src/mav_controller/src/behaviour.cpp:64-77 |
| Each behaviour loop iteration publishes a cmd_vel whose linear.z is a PID output on H_DES minus the current height. | upstream_code | src/mav_controller/src/behaviour.cpp:573-577 |
| A cmd_vel with any non-zero component makes the velocity controller preempt the position controller's twist input. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/velocity_controller.cpp:173-181 |
| The velocity controller stamps its attitude, yawrate and thrust outputs with the stamp of the twist command it used. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/velocity_controller.cpp:264-267 |
| When its twist output was preempted or the motors are not running, the position controller drops its pose command, resets and stops its twist output. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/position_controller.cpp:178-198 |
| The position controller ignores a PoseStamped command whose frame_id is not its world_frame_. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/position_controller.cpp:273-283 |
| The pose action callback begins by calling enableMotors(true). | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_actions/src/pose_action.cpp:56-58 |
| Each pose action iteration publishes the target pose; the goal succeeds after the current pose has stayed within dist_tolerance and yaw_tolerance for time_in_tolerance and aborts after action_timeout. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_actions/src/pose_action.cpp:80-101 |
| writeSim applies the limited controller wrench only while motor_status_.on and running are true; otherwise it publishes a zero wrench. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controller_gazebo/src/quadrotor_hardware_gazebo.cpp:242-270 |
| normal.launch defaults paused to false, use_sim_time to true, gui to true and physics to ode. | upstream_code | src/mav_controller/worlds/normal.launch:6-12 |
| When use_sim_time is true, normal.launch sets the parameter /use_sim_time to true. | upstream_code | src/mav_controller/worlds/normal.launch:17-18 |
| normal.launch starts the node named gazebo of package gazebo_ros, and its type is gzserver unless debug is true. | upstream_code | src/mav_controller/worlds/normal.launch:28-32 |
| When gui is true, normal.launch starts the node gazebo_gui of package gazebo_ros and type gzclient. | upstream_code | src/mav_controller/worlds/normal.launch:35-36 |
| The 3mavs launch includes $(find mav_controller)/worlds/normal.launch. | upstream_code | src/mav_controller/launch/3mavs.launch:11 |
| normal.world sets the world physics type to ode. | upstream_code | src/mav_controller/worlds/normal.world:6 |
| The README says other versions should also work. | upstream_code | README.md:6 |
| The quadrotor_controller macro loads libgazebo_ros_control.so with controlPeriod 0.01 and robotSimType hector_quadrotor_controller_gazebo/QuadrotorHardwareSim. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_gazebo/urdf/quadrotor_controller.gazebo.xacro:5-7 |
| The behaviour node's main constructs ros::Rate loop_rate(ros_rate). | upstream_code | src/mav_controller/src/behaviour.cpp:387 |
| The behaviour loop calls ros::spinOnce() and then loop_rate.sleep(). | upstream_code | src/mav_controller/src/behaviour.cpp:591-592 |
| The takeoff action callback calls enableMotors(true). | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_actions/src/takeoff_action.cpp:59 |
| The velocity controller's reset assigns an empty TwistStamped to twist_command_. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/velocity_controller.cpp:110-118 |
| When the motors are not running, the velocity controller's update calls reset(). | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/velocity_controller.cpp:196-199 |
| The velocity controller's update passes twist_command_.twist through twist_limiter_ and uses that result as its command. | upstream_code | src/hector/hector_quadrotor/hector_quadrotor_controllers/src/velocity_controller.cpp:206-207 |
| The gazebo_ros gzserver wrapper adds libgazebo_ros_api_plugin to the server's plugins unless the arguments already name it. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24 |
| The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:127-128 |
| The API plugin creates its node handle in the private namespace ~ and advertises its topics and services there. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:147 |
| The API plugin starts a ros::AsyncSpinner. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:149-151 |
| The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback queue gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:462-468 |
| The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties type on gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:364-370 |
| gazeboQueueThread serves gazebo_queue_ in a loop with a 0.001 s wall-clock wait while the node handle is ok. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:235-242 |
| pausePhysics calls world_->SetPaused(true) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1662-1666 |
| unpausePhysics calls world_->SetPaused(false) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1668-1672 |
| getPhysicsProperties sets res.pause to world_->IsPaused(). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1426 |
| getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it sets success false and returns false. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1433-1465 |
| The GetPhysicsProperties response field pause is true if the physics engine is paused. | upstream_code | companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4 |
| Among the world-update begin hooks that its comment says apply forces and publish sim time on /clock, the API plugin connects publishSimTime. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:224-227 |
| gazebo_ros_control connects its Update to the world-update begin event. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp:196-199 |
| gazebo_ros_control's Update reads the simulation time, updates the controllers and calls writeSim. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp:211-257 |
| GazeboRosP3D connects UpdateChild to the world-update begin event. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_p3d.cpp:207-208 |
| GazeboRosP3D::UpdateChild pushes pose_msg_ onto its publish queue. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_p3d.cpp:350-351 |
| World::Step advances simulation time and calls Update only when the world is not paused, a step increment is pending or a reset is due; otherwise it adds the step to the pause time. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:691-710 |
| World::Step holds worldUpdateMutex while it steps the world. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:683 |
| World::SetPaused stores the paused flag under worldUpdateMutex. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1428-1436 |
| World::IsPaused returns the stored paused flag. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1422-1425 |
| World::Update fires the worldUpdateBegin event and then updates every model. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:776-782 |
| World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed on every step, paused or not. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:691-718 |
| A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the number of steps to run while paused. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1462-1477 |

## Scope

The driver exposes one UAV (`uav1`) through four declarations:

* an explicit read of `/uav1/ground_truth/state` (`nav_msgs/Odometry`); the topic is not a resource read, because the p3d plugin publishes it from the world update and it is silent while the world is paused;
* one `geometry_msgs/Twist` publication on `/uav1/cmd_vel`, whose receipt reports the four values sent;
* the acknowledged `hector_uav_msgs/EnableMotors` service on `/uav1/enable_motors` as an ordinary command;
* the `hector_uav_msgs/LandingAction` action on `/uav1/action/landing` as an ordinary command.

The e-stop is `/gazebo/pause_physics` (`std_srvs/Empty`), confirmed when `/gazebo/get_physics_properties` reads `pause` true. Both services are companion citations (gazebo_ros 2.8.7). No unpause is declared.

The upstream nodes use relative names. The 3mavs launch includes `mav_controller/worlds/normal.launch` and places the uav1 model and behaviour node inside the `uav1` group namespace (`3mavs.launch:13-24`). The resolved `/uav1` endpoints are a deployment configuration, not an upstream Fact. `normal.launch` starts the Gazebo server itself as the node named `gazebo` (`pkg="gazebo_ros"`); it does not include `gazebo_ros` `empty_world.launch`. `paused` defaults to false, so the world starts running. The operator runs Gazebo, the hector controllers, the action servers and rosbridge separately.

The package does not cover the 3mavs/4mavs/9mavs/10mavs launches as a swarm, the autonomous `behaviour` node, the state-action matrix, inter-UAV collision avoidance, takeoff, the pose action as a public command, or the `/estop` topic. The `behaviour` node also publishes `/uav1/cmd_vel` and enables motors at startup; running it beside this driver gives the vehicle competing commanders, and on an unpause it publishes again.

## Limits

The four `cmd_vel` inputs (`linear_x`, `linear_y`, `linear_z`, `angular_z`) are `operator_required`. The clone states no per-axis command envelope: `controller.yaml:18` is the velocity controller's combined xy magnitude `max_xy` 10.0 (`Vector3Limiter` scales x, y and z together when it is exceeded, `limiters.h:121-143`); `controller.yaml:27-28` is a z clamp of 5.0 whose negative side `FieldLimiter` derives in code (`limiters.h:52-62`); and the 3.14 `yawrate` maximum at `controller.yaml:44-45` belongs to the attitude controller's clamp, not to the velocity controller that reads `cmd_vel`. Without an overlay every `cmd_vel` call is refused with `MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` is an illustrative operator overlay only; it is not a device fact, flight envelope or approval.

## Safety

The device is simulated. The package keeps risk R2 (a velocity command for a simulated multirotor; the card floor is R0). The e-stop pauses the Gazebo world and reads the paused flag back (`res.pause = world_->IsPaused()` at `gazebo_ros_api_plugin.cpp:1426`). The flag is not a measured standstill.

No unpause is offered. `velocity_controller.cpp:169` stores the last Twist in `twist_command_`, and `update()` applies it (`velocity_controller.cpp:207`) with the stamp stored at receipt (`velocity_controller.cpp:265-267`). `reset()` clears that command only when the motors are not running (`velocity_controller.cpp:117`, `:197-198`), and the controller update does not run while the world is paused. The behaviour loop publishes `cmd_vel` again when `loop_rate.sleep()` returns (`behaviour.cpp:573-577`, `:591-592`); `normal.launch` sets `/use_sim_time` true, so that sleep follows simulation time. Recovery is outside MHS: stop the behaviour nodes, clear the stored twist, then unpause (Gazebo GUI or `rosservice`). `mhs.safety.reset` releases the latch only and leaves the world paused.

The landing action is not a stop: its pose goal calls `enableMotors(true)` first (`pose_action.cpp:56-58`). `enable_motors` stays an ordinary command. Its callback sets `motor_status_.running` and returns true (`quadrotor_hardware_gazebo.cpp:274-283`) and is advertised without a custom queue (`:108`). The API plugin starts a `ros::AsyncSpinner` (`gazebo_ros_api_plugin.cpp:149-151`), so the service can be answered while the world is paused. `writeSim` applies a wrench only while the motors are on and running (`quadrotor_hardware_gazebo.cpp:242-270`) and is called from `gazebo_ros_control`'s Update on the world-update begin event, which does not run until the world steps.

The read-back succeeds only for the ODE engine (`gazebo_ros_api_plugin.cpp:1458-1465`). `normal.launch` defaults physics to ode and `normal.world` sets physics type ode. A Gazebo GUI (`normal.launch` defaults `gui` to true), a WorldControl `step` or `multi_step` (`World.cc:1462-1477`), or any other client can unpause or step the world. `safety_status` returns the cached e-stop confirmation and does not call `get_physics_properties` again (`RosBridge.safety_status`, `mhs/bridge/ros.py:2227-2232`), so it cannot detect that external unpause or step. The behaviour node's `system("pkill -f ros")` (near collision, or `t_elps` 5000) kills every host process whose command line contains `ros`, including rosbridge and an `mhs serve` process whose package path contains `ros`. The README says other versions should also work (`README.md:6`); the citations are pinned to gazebo_ros 2.8.7 and Gazebo 9.19.0. No physical e-stop, hardware run or live ROS validation is claimed. `driver.lock.json` keeps `reviewed_by` null. `publish_review` stays required (licence `NOASSERTION`).

## Fidelity contract

The deployed fake is an analytic ROS-free protocol stand-in, level F0, engine `analytic:ROS-free protocol fake (no physics)`, determinism `none`, `timestep_ms` 0, `realtime_factor` 0, reset `none`, no snapshot/restore. It answers the declared odometry subscription, records the `cmd_vel` publication, answers the arm service, completes the landing action at once while its paused flag is clear, and answers the two companion Gazebo services. While the flag is set, odometry is silent, a stored `cmd_vel` does not move the placeholder pose, the landing action is aborted, and `enable_motors` is still answered. It runs no Gazebo physics, controller loop, swarm behaviour or wall-clock pacing. Its odometry, action statuses, service replies and motor flags are placeholders. A completed `cmd_vel` receipt reports `confirmed=false` and the four values sent; it is not a motion or arrival claim.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `hector-quadrotor`, `uav`, `swarm`, `cmd-vel`, `stop`
