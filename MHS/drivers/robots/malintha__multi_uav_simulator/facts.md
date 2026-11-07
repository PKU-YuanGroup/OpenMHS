# Facts and tags for gh.malintha/multi_uav_simulator

Every fact cites the pinned clone at commit `f2cc09b22e4752c057cb8cc29c47e6fecfe04dde`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| Quadrotor constructs its node name as "robot_" + to_string(robot_id) and computes dt = 1.0 / frequency. | upstream_code | include/mavswarm2/quadrotor.hpp:59-64 |
| The constructor logs dt and creates a wall timer with period dt that runs iteration. | upstream_code | include/mavswarm2/quadrotor.hpp:68-72 |
| The constructor creates one subscription to a per-robot desired_state topic of type geometry_msgs::msg::Point with queue size 10; the adjacent comment names /mavswarm2/robot_3/desired_state as the example. | upstream_code | include/mavswarm2/quadrotor.hpp:93-97 |
| desired_pos_cb converts the received Point to (x, y, z), returns without action when the new target is within 0.2 m of target_pos, otherwise stores it and calls scp_planner_->set_goal(p1, ss.position, ss.velocity). | upstream_code | include/mavswarm2/quadrotor.hpp:215-223 |
| The comment above desired_pos_cb names the goal handoff as the NED frame. | upstream_code | include/mavswarm2/quadrotor.hpp:212-223 |
| publish_words.py states that goals are in the controller's NED frame (x North, y East, z Down; negative z is up). | upstream_code | publish_words.py:17-19 |
| publish_words.py imports geometry_msgs.msg.Point. | upstream_code | publish_words.py:30 |
| publish_words.py creates one Point publisher per robot on /mavswarm2/robot_{i}/desired_state with queue size 10. | upstream_code | publish_words.py:217-221 |
| The helper's assignment log reports the total distance in metres. | upstream_code | publish_words.py:247-248 |
| The constructor creates a visualization_msgs::msg::Marker publisher on the per-robot trajectory topic with queue size 10; the adjacent comment names /mavswarm2/robot_3/trajectory as the example. | upstream_code | include/mavswarm2/quadrotor.hpp:104-107 |
| The trajectory marker is a LINE_STRIP in frame map with namespace trajectory, id robot_id and action ADD. | upstream_code | include/mavswarm2/quadrotor.hpp:112-116 |
| publish_path samples every fifth timer tick, appends state_space.position (NWU/map frame) to the marker points, keeps at most 200 points, and publishes the marker. | upstream_code | include/mavswarm2/quadrotor.hpp:279-304 |
| set_state_space converts the internal NED state to the map frame with ned_nwu_rotation before broadcasting. | upstream_code | include/mavswarm2/quadrotor.hpp:325-332 |
| The constructor creates a tf2_ros::TransformBroadcaster, sets the world frame to map and the child frame to robot_<id>/base_link. | upstream_code | include/mavswarm2/quadrotor.hpp:85-88 |
| main spins the Quadrotor node and calls rclcpp::shutdown() after spin returns. | upstream_code | src/quadrotor.cpp:23-33 |
| The launch file starts the mavswarm2 executable as node robot_3 in namespace mavswarm2. | upstream_code | launch/quadrotor.launch:42-47 |
| The launch's controller_frequency argument defaults to 100. | upstream_code | launch/quadrotor.launch:3 |
| The README documents colcon build and ros2 launch mavswarm2 quadrotor.launch. | vendor_doc | readme.md:39-47 |
| package.xml declares ament_cmake and the rclcpp, simulator_interfaces, std_msgs, geometry_msgs, sensor_msgs, visualization_msgs, tf2 and tf2_ros dependencies. | upstream_code | package.xml:10-21 |
| CMakeLists.txt builds the mavswarm2 executable from src/quadrotor.cpp, links GSL and glog, and installs the launch, config and cf_description directories. | upstream_code | CMakeLists.txt:21-45 |
| The repository LICENSE file is the GNU General Public License, version 3. | upstream_code | LICENSE:1-2 |
| The header of quadrotor.hpp states that the file is licensed under the Apache License, Version 2.0. | upstream_code | include/mavswarm2/quadrotor.hpp:2-4 |
| package.xml declares the licence as 'TODO: License declaration'. | upstream_code | package.xml:8 |

## Scope

The package binds the upstream's own per-vehicle endpoints for `robot_3`, which is one of
the ten instances started by `launch/quadrotor.launch`:

* `x-cap.malintha.desired_state.v1` publishes one `geometry_msgs/msg/Point` to
  `/mavswarm2/robot_3/desired_state`. The source comment names that exact absolute example
  (`include/mavswarm2/quadrotor.hpp:93`), and `publish_words.py:220` confirms the
  `/mavswarm2/robot_<i>/desired_state` topic and the `Point` type. The goal is in the
  controller's NED frame; the helper documents x North, y East, z Down and reports distances
  in metres (`publish_words.py:17-19`, `publish_words.py:247-248`). The callback's 0.2 m
  deadband (`include/mavswarm2/quadrotor.hpp:218`) is a behaviour threshold, not a numeric
  input envelope.
* `x-cap.malintha.trajectory.v1` subscribes to the node's own
  `visualization_msgs/msg/Marker` on `/mavswarm2/robot_3/trajectory` and returns the last
  LINE_STRIP point in the marker header frame. The marker is a visualisation trail in the
  `map` frame (`include/mavswarm2/quadrotor.hpp:104-116`, `:279-304`), not TF and not an
  acknowledged state or stopped-state measurement.

The resource state also exposes `last_goal`, the last `Point` observed on the command topic.
It is a wire observation of the publication, not execution feedback: it does not prove that
the SCP planner accepted the goal or that the simulated vehicle moved. The command topic is
volatile, so in a live deployment a fresh subscription receives a message only when one is
published while it waits; the fake's echo of the last recorded publication is a disclosed
fidelity gap, not a claim that the live resource read replays the last goal. Model review
(2026-11-05): because only clients publish that topic, in a live graph every command waits the
2 s `last_goal` read timeout and `mhs.resource.read` fails `MHS.DEVICE.NOT_READY` unless a goal is
published meanwhile (probe with the topic silent: the publish completed after 2.01 s and the
resource read failed `NOT_READY`). The read is kept because the gate's TCAP-003 needs an observable
effect of the publication; whoever unblocks the package should replace it with real feedback.

Licence: the repository `LICENSE` is GPL-3.0 (the card's licence), while the headers of
`include/mavswarm2/quadrotor.hpp` and `src/quadrotor.cpp` state Apache-2.0 and `package.xml` says
`TODO: License declaration`.

The TF broadcast `map -> robot_<id>/base_link` (`include/mavswarm2/quadrotor.hpp:85-88`,
`:229-251`) and the helper's TF listener are upstream context; they are **NOT COVERED** because
the clone does not declare a `/tf` subscription and the helper only uses it. The SCP path and
neighbour traffic (`robot_<id>/scp_path`), the other nine robots, ROS parameters, camera,
sensors, RViz, world step, reset, snapshot and restore are also **NOT COVERED**. This package
binds one vehicle, not a swarm-level orchestration interface.

## Stop path

The clone creates no ROS service or action server. A search of `include/`, `src/`, `launch/`
and `publish_words.py` found no `create_service`, `create_action_server`, `rclcpp_action`,
`ros::Service` or actionlib declaration. The constructor's ROS interfaces are the wall timer,
the `desired_state` subscription and the `trajectory` publisher
(`include/mavswarm2/quadrotor.hpp:70-107`); the `desired_pos_cb` path only accepts a new
goal, and `publish_path` only publishes the trail. `main` calls `rclcpp::spin(...)` and then
`rclcpp::shutdown()` after spin returns (`src/quadrotor.cpp:23-33`); that shutdown is a process
path, not a ROS service or action. A `desired_state` publication close to the current target
can make the planner hold, but a ROS topic publication carries no acknowledgement and the
clone reports no measured quiescence. The package therefore declares no `safety_bindings` and
no `safe_state.achieved_by` action. The stock e-stop latches this driver and reports
`MHS.SAFETY.SAFE_STATE_UNREACHED`; an operator must stop the ROS process or publish a hover
goal outside the latched driver path. No physical e-stop exists or is claimed.

## Limits and deployment

The clone states no numeric goal envelope. The SCP planner's `v_max` and `a_max` are internal
trajectory-solver defaults, the launch `initial_conditions` and the `publish_words.py` glyph
constants are configured layouts, and the callback's 0.2 m deadband is a behaviour threshold.
The `x`, `y` and `z` inputs therefore use `Limit.operator_required`: every goal is refused until
the operator supplies the deployment's NED workspace bounds in `site-limits.json`.
`site-limits.example.json` is illustrative example data only, not a device fact.

The operator runs the clone's `colcon build` and `ros2 launch mavswarm2 quadrotor.launch`
(`readme.md:39-47`) and a rosbridge endpoint in an isolated simulation environment. The
package does not start, build or validate the ROS graph. The clone depends on the external
`simulator_interfaces` package and on GSL/Eigen (`package.xml:12-21`,
`CMakeLists.txt:8-36`); those were not installed or built here.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS contract fake (canned replies;
no Mavswarm2 node or physics)`, level F0, determinism `none`, `timestep_ms: 0` (event-driven
canned replies with no physics step), `realtime_factor: 0` (not paced), reset `none`, and no
snapshot/restore. The fake answers the declared trajectory subscription and records the
declared desired_state publication. It does not replay captured traffic, run the SCP planner,
the geometric controller, GSL dynamics or TF, or apply a goal. Its marker points are
placeholders and do not advance; a live run must receive the node's own samples.

## Tags

`ros`, `ros2`, `simulation`, `mavswarm2`, `multi-uav`, `quadrotor`, `trajectory`
