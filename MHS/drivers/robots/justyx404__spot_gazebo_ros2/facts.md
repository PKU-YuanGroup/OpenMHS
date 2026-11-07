# Facts and tags for gh.justyx404/spot_gazebo_ros2

Every fact cites the pinned clone at commit `23166d6efd67724edc1ce41e9ee4bb909cf9a2f9`, or a companion
clone named by `task.json` `companions` (prefix `companion:<alias>/`). The same list is declared in
`driver.py`. `reference.json` and `REFERENCE.md` are generated from the driver.

| fact | source | ref |
|---|---|---|
| The launch starts ros_gz_sim with the selected world file through the ros_gz_sim include. | upstream_code | `spot_bringup/launch/spot.gazebo.launch.py:33-48` |
| The launch's gz_args value is a path join of the spot_gazebo worlds directory and the world file. | upstream_code | `spot_bringup/launch/spot.gazebo.launch.py:40-45` |
| The launch starts the ros_gz_bridge parameter_bridge with spot_bridge.yaml as its config file. | upstream_code | `spot_bringup/launch/spot.gazebo.launch.py:50-61` |
| spot_bridge.yaml maps /clock, /spot/joint_states and /spot/odometry from Gazebo to ROS with rosgraph_msgs/msg/Clock, sensor_msgs/msg/JointState and nav_msgs/msg/Odometry. | upstream_code | `spot_bringup/config/spot_bridge.yaml:3-16` |
| The launch starts champ_base/quadruped_controller_node with gazebo true, publish_joint_states false, publish_joint_control true, joint_controller_topic /spot/joint_trajectory, and remaps /cmd_vel/smooth to /cmd_vel. | upstream_code | `spot_bringup/launch/spot.gazebo.launch.py:95-114` |
| The quadruped controller creates a geometry_msgs::msg::Twist subscription on the relative cmd_vel/smooth topic with queue size 10. | upstream_code | `champ_base/src/quadruped_controller.cpp:69-70` |
| The controller header includes geometry_msgs/msg/twist.hpp for the Twist subscription. | upstream_code | `champ_base/include/quadruped_controller.h:43` |
| The cmd_vel callback copies linear.x, linear.y and angular.z into the persistent req_vel_ member and stores no receive time or stale-command deadline. | upstream_code | `champ_base/src/quadruped_controller.cpp:116-121` |
| controlLoop_ calls leg_controller_.velocityCommand with the stored req_vel_, solves the inverse kinematics and calls publishJoints_. | upstream_code | `champ_base/src/quadruped_controller.cpp:101-113` |
| The constructor initialises loop_rate to 200.0. | upstream_code | `champ_base/src/quadruped_controller.cpp:49` |
| The constructor runs controlLoop_ from a wall timer whose period is 1000/loop_rate milliseconds. | upstream_code | `champ_base/src/quadruped_controller.cpp:94-97` |
| LegController::velocityCommand caps linear.x, linear.y and angular.z to the negated and positive configured gait maxima. | upstream_code | `champ/include/champ/leg_controller/leg_controller.h:95-98` |
| The gait configuration sets max_linear_velocity_x to 1.5, max_linear_velocity_y to 0.25 and max_angular_velocity_z to 1.0. | upstream_code | `champ_config/config/gait/gait.yaml:7-9` |
| The launch loads champ_config/config/gait/gait.yaml as the controller's gait ParameterFile. | upstream_code | `spot_bringup/launch/spot.gazebo.launch.py:90-91` |
| publishJoints_ builds a trajectory_msgs/msg/JointTrajectory with 12 positions and a zero header stamp. | upstream_code | `champ_base/src/quadruped_controller.cpp:145-160` |
| spot_bridge.yaml maps /spot/joint_trajectory from ROS to Gazebo with trajectory_msgs/msg/JointTrajectory. | upstream_code | `spot_bringup/config/spot_bridge.yaml:76-80` |
| The simple_tunnel world loads the Physics, Sensors, SceneBroadcaster and UserCommands systems. | upstream_code | `spot_gazebo/worlds/simple_tunnel.sdf:5-24` |
| simple_tunnel.sdf names its world simple_tunnel. | upstream_code | `spot_gazebo/worlds/simple_tunnel.sdf:3` |
| edgar_mine.sdf names its world edgar_mine. | upstream_code | `spot_gazebo/worlds/edgar_mine.sdf:3` |
| electrical_substation.sdf names its world electrical_substation_v3. | upstream_code | `spot_gazebo/worlds/electrical_substation.sdf:3` |
| The simple_tunnel world file loads a plugin named World control from filename WorldControl. | upstream_code | `spot_gazebo/worlds/simple_tunnel.sdf:84-85` |
| The simple_tunnel WorldControl GUI sets play_pause true, step true and start_paused false. | upstream_code | `spot_gazebo/worlds/simple_tunnel.sdf:101-103` |
| The edgar_mine world file sets play_pause true, step true and start_paused true. | upstream_code | `spot_gazebo/worlds/edgar_mine.sdf:93-95` |
| The Spot model loads a JointStatePublisher on model/spot/joint_state. | upstream_code | `spot_description/models/spot/model.sdf:1874-1878` |
| The Spot model loads an OdometryPublisher on /model/spot/odometry. | upstream_code | `spot_description/models/spot/model.sdf:1881-1886` |
| The Spot model loads a JointTrajectoryController on model/spot/joint_trajectory. | upstream_code | `spot_description/models/spot/model.sdf:1891-1894` |
| The README names a ROS 2 Humble simulation package. | vendor_doc | `README.md:3` |
| The README lists Gazebo Fortress among the install requirements. | vendor_doc | `README.md:53` |
| The README's navigation steps launch spot_navigation online_async_launch.py. | vendor_doc | `README.md:105` |
| The README's navigation steps launch spot_navigation localization_launch.py. | vendor_doc | `README.md:110` |
| far_planner.launch.py starts a node from package spot_navigation. | upstream_code | `spot_bringup/launch/far_planner.launch.py:82` |
| The README states that all body camera and depth sensors are not used and are disabled to save computation. | vendor_doc | `README.md:22` |
| SimulationRunner composes its transport namespace as /world/ followed by the world name. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:122` |
| SimulationRunner advertises the control service with OnWorldControl as its callback. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:214` |
| OnWorldControl copies the WorldControl request into a WorldControlState and calls OnWorldControlState. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:1120-1127` |
| OnWorldControlState appends the control to worldControls and sets the Boolean reply to true. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:1174-1176` |
| ProcessWorldControl calls SetPaused with the pause flag of each queued control. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:1239-1242` |
| A queued control with multi_step on a paused world adds the steps and unpauses the world so that stepping can occur. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:1244-1251` |
| SetPaused stores the pause state in currentInfo.paused. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:1088-1089` |
| Step publishes the world statistics. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:826-827` |
| Step processes the world control messages. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:867-868` |
| The Run loop calls Step on every iteration and counts a processed iteration only while not paused. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:732-746` |
| The statistics publisher on the stats topic is limited to 10 messages per second. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:649-651` |
| PublishStats copies currentInfo.paused into the WorldStatistics message. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:430` |
| UpdateCurrentInfo advances the simulation time and the iteration count only while not paused. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:345-350` |
| PublishStats publishes the clock message after the statistics, and the comment says the clock is not throttled. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:444-445` |
| PublishStats sets the clock message's sim time from the current info. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:449-450` |
| PublishStats sets the clock message's system time from IGN_SYSTEM_TIME. | upstream_code | `companion:gz_sim/src/SimulationRunner.cc:451-453` |
| The Physics system steps the physics only when not paused. | upstream_code | `companion:gz_sim/src/systems/physics/Physics.cc:855-859` |
| OdometryPublisher::PostUpdate returns immediately when paused. | upstream_code | `companion:gz_sim/src/systems/odometry_publisher/OdometryPublisher.cc:302-304` |
| JointTrajectoryController::PreUpdate returns when paused. | upstream_code | `companion:gz_sim/src/systems/joint_traj_control/JointTrajectoryController.cc:438-441` |
| PreUpdate calls SetTarget with the current trajectory point when a target update is required, and then Update on each actuated joint. | upstream_code | `companion:gz_sim/src/systems/joint_traj_control/JointTrajectoryController.cc:498-519` |
| A new JointTrajectory resets the stored trajectory and then copies the message's joint names and points. | upstream_code | `companion:gz_sim/src/systems/joint_traj_control/JointTrajectoryController.cc:677-688` |
| JointStatePublisher::PostUpdate stamps the model message from the simulation time. | upstream_code | `companion:gz_sim/src/systems/joint_state_publisher/JointStatePublisher.cc:186-189` |
| Server::Run's third argument _paused defaults to true. | upstream_code | `companion:gz_sim/include/gz/sim/Server.hh:150-152` |
| Server::Run calls SetPaused with _paused on each simulation runner. | upstream_code | `companion:gz_sim/src/Server.cc:174-179` |
| gz.cc calls server.Run with the third argument _run == 0. | upstream_code | `companion:gz_sim/src/gz.cc:408` |
| The ign gazebo usage text describes -r as run simulation on start. | upstream_code | `companion:gz_sim/src/cmd/cmdgazebo.rb.in:116` |
| The ign gazebo command defaults the run option to 0. | upstream_code | `companion:gz_sim/src/cmd/cmdgazebo.rb.in:229` |
| The -r option sets run to 1. | upstream_code | `companion:gz_sim/src/cmd/cmdgazebo.rb.in:262-263` |
| The ros_gz_sim launch declares gz_args with an empty default. | upstream_code | `companion:ros_gz/ros_gz_sim/launch/gz_sim.launch.py.in:167` |
| The bridge maps ros_gz_interfaces/srv/ControlWorld to an ignition.msgs.WorldControl request with an ignition.msgs.Boolean reply. | upstream_code | `companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:42-52` |
| The ControlWorld response's success is the Boolean reply's data. | upstream_code | `companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:134-141` |
| For a failed request the ControlWorld response's success is false. | upstream_code | `companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:170-178` |
| The service bridge converts each ROS request and sends it with Request and a callback that sends the ROS response. | upstream_code | `companion:ros_gz/ros_gz_bridge/src/service_factory.hpp:56-86` |
| The WorldStatistics conversion copies the Ignition header into the ROS header and copies paused. | upstream_code | `companion:ros_gz/ros_gz_bridge/src/convert/ros_gz_interfaces.cpp:823-827` |
| ros_gz_interfaces WorldStatistics carries a header, sim_time, pause_time, real_time and the paused flag. | upstream_code | `companion:ros_gz/ros_gz_interfaces/msg/WorldStatistics.msg:1-14` |
| ControlWorld takes a WorldControl request and answers bool success. | upstream_code | `companion:ros_gz/ros_gz_interfaces/srv/ControlWorld.srv:1-3` |
| WorldControl's fields include pause, step and multi_step. | upstream_code | `companion:ros_gz/ros_gz_interfaces/msg/WorldControl.msg:1-3` |
| The bridge README maps ros_gz_interfaces/msg/WorldStatistics to ignition.msgs.WorldStatistics. | vendor_doc | `companion:ros_gz/ros_gz_bridge/README.md:55` |
| The bridge README maps the ros_gz_interfaces/srv/ControlWorld service to ignition.msgs.WorldControl and ignition.msgs.Boolean. | vendor_doc | `companion:ros_gz/ros_gz_bridge/README.md:78` |
| The parameter_bridge usage shows a Gazebo-to-ROS argument with an opening bracket. | upstream_code | `companion:ros_gz/ros_gz_bridge/src/parameter_bridge.cpp:51-53` |
| The parameter_bridge usage shows a service bridge argument for ControlWorld. | upstream_code | `companion:ros_gz/ros_gz_bridge/src/parameter_bridge.cpp:57-61` |
| The bridge's publisher QoS is KeepLast with the queue size, and its depth, durability, history and reliability may be overridden. | upstream_code | `companion:ros_gz/ros_gz_bridge/src/factory.hpp:60-80` |

## Scope

The primary control is one persistent `geometry_msgs/msg/Twist` publication on `/cmd_vel`. The explicit
observations are `/spot/odometry`, `/spot/joint_states` and `/clock`. None of them is a device-resource read.
The e-stop pauses the Ignition world `simple_tunnel` through the operator-run ros_gz bridges and confirms
`WorldStatistics.paused` on fresh statistics samples. No unpause is offered: CHAMP keeps `req_vel_` and the
joint-trajectory controller keeps its targets, so the operator clears those and unpauses outside MHS.
The velocity envelope stays `Limit.operator_required`; `site-limits.example.json` is an example overlay.

## Tags

`ros`, `ros2`, `gazebo`, `ignition`, `simulation`, `spot`, `quadruped`, `mobile-base`, `cmd-vel`
