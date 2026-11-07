# Source facts for gh.robin-shaun/xtdrone

Pinned commit: `671f3d45b22bfe4b7f2b23ae8d4251f3172781b3`. Each row is one Fact on the driver class. Source declarations and controlled fake results are not native execution.

| Fact | Source | Reference |
|---|---|---|
| XTDrone is a UAV simulation platform based on PX4, ROS and Gazebo, and its README says algorithms can be deployed to real UAVs after simulation testing. | vendor_doc | `README.en.md:7` |
| The multi-vehicle launch places typhoon_h480_0 in the typhoon_h480_0 namespace and includes MAVROS inside that group. | upstream_code | `sitl_config/launch/multi_vehicle.launch:21-49` |
| The generated topic list records /typhoon_h480_0/mavros/local_position/pose. | vendor_doc | `contributer_demo/demo1/doc/rostopic list:84` |
| The generated topic list records /typhoon_h480_0/mavros/setpoint_position/local. | vendor_doc | `contributer_demo/demo1/doc/rostopic list:117` |
| The generated topic list records /typhoon_h480_0/mavros/setpoint_raw/target_local. | vendor_doc | `contributer_demo/demo1/doc/rostopic list:123` |
| The ground-control script publishes PoseStamped targets on the vehicle's relative setpoint_position/local topic. | upstream_code | `contributer_demo/demo1/src/formation/script/formation_gcs.py:74` |
| The iris_0 MAVROS config sets setpoint_position tf frame_id to map and mav_frame to LOCAL_NED. | upstream_code | `sitl_config/launch/px4/px4_config_iris_0.yaml:108-113` |
| The communication node publishes a MAVROS PositionTarget on the relative setpoint_raw/local topic. | upstream_code | `communication/multirotor_communication.py:45` |
| The communication node's start method republishes the last target in a loop until ROS shutdown. | upstream_code | `communication/multirotor_communication.py:55-61` |
| The module creates a 30 Hz ROS rate object. | upstream_code | `communication/multirotor_communication.py:10` |
| The cmd handler ignores the exact string 'stop controlling' and the empty string, as well as a repeat of the last command. | upstream_code | `communication/multirotor_communication.py:149-151` |
| The hover transition treats speeds within 0.02 and a yaw rate within 0.005 as a hover request and constructs a target from the cached current position and yaw. | upstream_code | `communication/multirotor_communication.py:141-148` |
| The hover method constructs its target from the cached current position and yaw. | upstream_code | `communication/multirotor_communication.py:194-198` |
| The target constructor signature names the acceleration components afx, afy and afz. | upstream_code | `communication/multirotor_communication.py:67` |
| The acceleration callbacks call the target constructor with ax, ay and az keywords, which the signature does not accept. | upstream_code | `communication/multirotor_communication.py:127-139` |
| The node's arm and disarm helpers test the whole CommandBool service response object rather than its success field. | upstream_code | `communication/multirotor_communication.py:180-192` |
| The flight mode helper tests the whole SetMode service response object rather than its mode_sent field. | upstream_code | `communication/multirotor_communication.py:200-209` |
| The multirotor communication node builds a CommandBool service proxy from vehicle_type, vehicle_id and the suffix /mavros/cmd/arming. | upstream_code | `communication/multirotor_communication.py:50` |
| The multirotor communication node builds a SetMode service proxy from vehicle_type, vehicle_id and the suffix /mavros/set_mode. | upstream_code | `communication/multirotor_communication.py:51` |
| The plane communication node builds a CommandBool service proxy from vehicle_type, vehicle_id and the suffix /mavros/cmd/arming, and a SetMode service proxy from vehicle_type, vehicle_id and the suffix /mavros/set_mode. | upstream_code | `communication/plane_communication.py:40-41` |
| The vendored gazebo_ros package.xml declares version 2.8.7. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/package.xml:4` |
| The vendored gazebo_ros package.xml declares a catkin buildtool dependency. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/package.xml:22` |
| The vendored gazebo_ros changelog header is 2.8.7 (2020-05-01). | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/CHANGELOG.rst:5` |
| The vendored gazebo_ros_pkgs README links its sensors document on the melodic-devel branch. | vendor_doc | `sitl_config/gazebo_ros_pkgs/README.md:11` |
| The vendored RELEASE.md lists ROS Melodic with Gazebo 9. | vendor_doc | `sitl_config/gazebo_ros_pkgs/docs/RELEASE.md:19` |
| The API plugin member enable_ros_network_ is initialized true. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:41` |
| The API plugin creates its node handle with ros::NodeHandle("~"). | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:148` |
| gazeboQueueThread calls gazebo_queue_.callAvailable with a 0.001 s wall duration while nh_->ok(). | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:263-269` |
| advertiseServices returns without advertising when enable_ros_network_ is false. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:274-277` |
| The API plugin connects wrenchBodySchedulerSlot, forceJointSchedulerSlot and publishSimTime to WorldUpdateBegin. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:225-228` |
| The API plugin advertises the service get_physics_properties with type gazebo_msgs::GetPhysicsProperties. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:389-395` |
| The API plugin advertises the service pause_physics with type std_srvs::Empty. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:508-514` |
| The API plugin advertises the service unpause_physics with type std_srvs::Empty. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:517-523` |
| getPhysicsProperties sets res.pause to world_->IsPaused(). | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1484` |
| When the physics engine type is not ode, getPhysicsProperties sets success false and returns false. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1516-1523` |
| pausePhysics calls world_->SetPaused(true) and returns true. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1738-1742` |
| unpausePhysics calls world_->SetPaused(false) and returns true. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1744-1748` |
| The gazebo network API test lists /gazebo/get_physics_properties with type gazebo_msgs/GetPhysicsProperties. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/test/ros_network/gazebo_network_api.yaml:55-56` |
| The gazebo network API test lists /gazebo/pause_physics with type std_srvs/Empty. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/test/ros_network/gazebo_network_api.yaml:85-86` |
| The GetPhysicsProperties response field pause is commented true if the physics engine is paused. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4` |
| empty_world.launch defaults its gui argument to true. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:8` |
| empty_world.launch defaults its physics argument to ode. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:15` |
| empty_world.launch defaults use_sim_time to true. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:6` |
| empty_world.launch defaults enable_ros_network to true. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:22` |
| empty_world.launch sets the parameter /use_sim_time to $(arg use_sim_time). | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:27` |
| empty_world.launch sets script_type to gzserver unless debug is true, in which case script_type is debug. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:36-37` |
| empty_world.launch starts a node named gazebo from package gazebo_ros. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:46-48` |
| When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient. | upstream_code | `sitl_config/gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:51-54` |
| multi_vehicle.launch defaults its world to $(find mavlink_sitl_gazebo)/worlds/empty.world. | upstream_code | `sitl_config/launch/multi_vehicle.launch:7` |
| multi_vehicle.launch defaults gui to true, debug to true and paused to false. | upstream_code | `sitl_config/launch/multi_vehicle.launch:9-12` |
| multi_vehicle.launch includes gazebo_ros empty_world.launch and passes gui, world_name, debug, verbose and paused. | upstream_code | `sitl_config/launch/multi_vehicle.launch:14-20` |
| multi_vehicle.launch includes $(find px4)/launch/single_vehicle_spawn_xtd.launch with vehicle typhoon_h480 inside the typhoon_h480_0 group. | upstream_code | `sitl_config/launch/multi_vehicle.launch:28-35` |
| multi_vehicle.launch opens a group whose namespace is typhoon_h480_1. | upstream_code | `sitl_config/launch/multi_vehicle.launch:51-52` |
| The typhoon_h480 mavlink_interface plugin sets enable_lockstep to true. | upstream_code | `sitl_config/models/typhoon_h480/typhoon_h480.sdf:1270-1288` |

## Scope

The accepted surface is the typhoon_h480_0 position-setpoint subset plus the vendored gazebo_ros 2.8.7 world pause, confirmed only when get_physics_properties reports pause true. No unpause is offered: the multirotor communication node republishes its retained target and ignores 'stop controlling', and this package cannot clear that target (SAFE-042). Arming and OFFBOARD stay outside MHS. The CommandBool and SetMode proxies are cited above and are not bound. Velocity, acceleration, landing and state stay outside. The acceleration keyword mismatch stays unsupported.

The device resource reads no topic. Pose and target are explicit reads. The setpoint receipt reports the values handed to rosbridge. Risk is R2 because that MAVROS topic is one a real PX4 can consume. Position bounds are operator_required and the example overlay is test data. The zero timestamp is a wire placeholder.

The pause covers every vehicle in the world, including typhoon_h480_1. A GUI or any other client can unpause, and MHS does not watch the flag. safety_status returns the cached confirmation from the last successful read-back and does not call get_physics_properties again, so it cannot detect that unpause. A non-ODE engine makes the read-back return false, so the e-stop stays unconfirmed with the latch held. The effect of World::SetPaused on the step loop is Gazebo's and is not in this clone. The fake's silence while paused is an assumption from enable_lockstep, not a measured PX4 trace.

Version evidence is vendored 2.8.7, catkin, the changelog header 2.8.7 (2020-05-01), README links on melodic-devel, and RELEASE.md listing ROS Melodic with Gazebo 9. The changelog line does not name a distro. This package claims no Noetic build. See NATIVE-BLOCKERS.md.
