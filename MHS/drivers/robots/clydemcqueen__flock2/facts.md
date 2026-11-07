# Facts and tags for gh.clydemcqueen/flock2

Every fact cites the pinned clone at commit `b6ee071c61189445f83b4a4dcc706726945b5090`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The drone_base header includes geometry_msgs/msg/twist.hpp, nav_msgs/msg/odometry.hpp, nav_msgs/msg/path.hpp and std_msgs/msg/empty.hpp. | upstream_code | include/drone_base.hpp:5-9 |
| DroneBase::DroneBase registers a relative cmd_vel publisher of geometry_msgs::msg::Twist with queue size 1. | upstream_code | src/drone_base.cpp:169 |
| DroneBase::DroneBase subscribes to the absolute /start_mission and /stop_mission topics of std_msgs::msg::Empty with queue size 10. | upstream_code | src/drone_base.cpp:180-181 |
| DroneBase::DroneBase subscribes to the relative base_odom nav_msgs::msg::Odometry and plan nav_msgs::msg::Path topics with queue size 10. | upstream_code | src/drone_base.cpp:185-186 |
| DroneBase::start_mission_callback only sets mission_ to true and returns; it publishes no acknowledgement and starts no takeoff. | upstream_code | src/drone_base.cpp:252-257 |
| DroneBase::stop_mission_callback logs and calls stop_mission(). | upstream_code | src/drone_base.cpp:259-264 |
| DroneBase::stop_mission clears mission_, calls all_stop(), and, only when the state is flight or flight_odom, calls start_action(Action::land). | upstream_code | src/drone_base.cpp:266-273 |
| DroneBase::all_stop publishes a zero velocity through the flight controller. | upstream_code | src/drone_base.cpp:428-432 |
| FlightControllerInterface::publish_velocity clamps throttle, strafe, vertical and yaw each to -1.0..1.0 and publishes them as a geometry_msgs::msg::Twist. | upstream_code | include/flight_controller_interface.hpp:60-68 |
| DroneBase::start_action drops the requested action when the action manager is busy; otherwise it calls action_mgr_->send(action, g_actions[action]). | upstream_code | src/drone_base.cpp:381-396 |
| The action manager sends a TelloAction service request with request->cmd set to the action string and then waits for the service future. | upstream_code | src/action_mgr.cpp:8-21 |
| The service response's rc is compared with OK, ERROR_BUSY and ERROR_NOT_CONNECTED; an OK response only marks the action as accepted and leaves state waiting_for_response. | upstream_code | src/action_mgr.cpp:23-48 |
| The action manager completes an action only when a later tello_response topic message reports success, failure or timeout. | upstream_code | src/action_mgr.cpp:50-70 |
| The action manager comment states that tello_driver uses a ROS service plus a ROS topic to simulate an action, and that only one action can be active at a time. | upstream_code | include/action_mgr.hpp:11-20 |
| TrajectoryVelocityFlyer.stop sends a zero four-component command when launching or running and explicitly does not try to land the flying drone. | upstream_code | src/flock_simple_path.py:202-215 |
| FlockSimplePath publishes the relative cmd_vel Twist topic and subscribes to absolute /start_mission, /stop_mission and /tf; it creates no service or action server. | upstream_code | src/flock_simple_path.py:347-367 |
| FlockSimplePath::flyer_cmd_callback passes the flyer's four velocity components through to a geometry_msgs::msg::Twist and publishes it. | upstream_code | src/flock_simple_path.py:430-440 |
| The shipped launch starts the drone_base controller and does not start the flock_simple_path script. | upstream_code | launch/launch_one.py:28-33 |
| The shipped single-drone launch starts drone_base with namespace 'solo'. | upstream_code | launch/launch_one.py:31-33 |

## Scope and deviations

The task card names `flock_simple_path:TrajectoryVelocityFlyer` as the entry
symbol. The symbol exists at `src/flock_simple_path.py:175` and is installed by
`CMakeLists.txt:129-130`, but no shipped launch starts that script; the launched
controller is `drone_base` (`launch/launch_one.py:28-33`). The card's
`family: ros` / `RosDriver` helper describes the production ROS graph, so this
package is a configuration-only RosDriver over `drone_base`'s topic contract.
It does not import or start the Python helper.

The exposed read is `base_odom` only, resolved as `/solo/base_odom` for the shipped single-drone namespace; the relative `cmd_vel` publication is resolved as `/solo/cmd_vel`. A deployment that renames the namespace must remap or reconfigure these endpoints. The `plan` input is not exposed: the
upstream `drone_base` receives a `nav_msgs/Path` from the planner, and the
pinned clone states no fixed waypoint fields, frame convention beyond REP-103,
or numeric travel envelope. Exposing a plan publisher would require inventing
a schema and bounds.

## Safety

The device is a flying mobile base at R2. The pinned clone exposes no ROS
service or action that stops it. `/stop_mission` is a topic publication:
the callback clears the mission and `all_stop()` publishes a zero Twist
(`src/drone_base.cpp:266-273`, `:428-432`); an asynchronous land request is
forwarded to the external `tello_action` service only when the node believes it
is flying and the action manager is free, and completion arrives later on the
`tello_response` topic (`include/action_mgr.hpp:11-20`, `src/action_mgr.cpp:50-70`).
A zero-velocity publication is not an acknowledged stop, and no independent
hardware e-stop is documented. The package therefore declares no e-stop binding
and no `safe_state=True` action; it is blocked rather than claiming a stop the
source cannot establish.

## Fake

`fake.py` is an in-memory contract stand-in, not a recording and not the
upstream simulator. All of its numbers are placeholders. It records the last
Twist, the mission flag and the published topics; it runs no ROS, no Tello
firmware, no flight dynamics and no landing sequence.

## Tags

`ros`, `ros2`, `flock2`, `tello`, `mobile-base`, `cmd-vel`, `odometry`
