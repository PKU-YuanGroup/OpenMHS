# Facts and tags for gh.larics/decentralized_multi_robot_exploration

Every fact cites the pinned clone at `e7c9c304a4072b5b7177a91ce6383397525ac66a`. `vendor_doc` is text documentation of
the clone; `upstream_code` is source or a comment in the clone. The same list is in `driver.py`; this page records the
evidence for review.

| fact | source | ref |
|---|---|---|
| The repository sets up a decentralised multi-robot exploration simulation with the 2D Stage simulator and a map from Google Cartographer. | vendor_doc | README.md:1-2 |
| The Stage launch starts the package's private stageros node against the shipped pioneer3dx-sick world file. | upstream_code | frontier_exploration/launch/stage-pioneer-3dx-sick.launch:17-19 |
| The shipped world places three pioneer3dx models named pioneer0, pioneer1 and pioneer2, each with a fixed pose and a fancysicklaser. | upstream_code | frontier_exploration/stage-worlds/pioneer3dx-sick.world:296-319 |
| The shipped sicklaser ranger declares range [ 0.0 20.0 ], fov 365.0 and 1081 samples. | upstream_code | frontier_exploration/stage-worlds/pioneer3dx-sick.world:235-243 |
| robot_assigner.launch sets the assigner's n_robots parameter to 2. | upstream_code | frontier_exploration/launch/robot_assigner.launch:6-10 |
| The multi-robot assigner launch includes robot_assigner.launch for robot index 0 and robot index 1. | upstream_code | frontier_exploration/launch/multi_robot_assigner.launch:1-10 |
| StageNode::mapName returns the relative name robot_<id>/<name> when more than one position model is present, unless use_model_names is set and the model token has no colon. | upstream_code | stage_ros_private/src/stageros.cpp:181-224 |
| SubscribeModels advertises nav_msgs/Odometry on the mapName(ODOM) topic for each position model, with queue length 10. | upstream_code | stage_ros_private/src/stageros.cpp:371 |
| SubscribeModels creates a geometry_msgs/Twist subscription on the mapName(CMD_VEL) topic for each position model. | upstream_code | stage_ros_private/src/stageros.cpp:373 |
| SubscribeModels advertises a sensor_msgs/LaserScan on the mapName(BASE_SCAN) topic for each laser model. | upstream_code | stage_ros_private/src/stageros.cpp:378 |
| SubscribeModels advertises rosgraph_msgs/Clock on the absolute /clock topic. | upstream_code | stage_ros_private/src/stageros.cpp:402 |
| SubscribeModels advertises the relative reset_positions service with std_srvs/Empty. | upstream_code | stage_ros_private/src/stageros.cpp:405 |
| cmdvelReceived passes the Twist linear.x, linear.y and angular.z to ModelPosition::SetSpeed and records the simulated time of the last command. | upstream_code | stage_ros_private/src/stageros.cpp:273-280 |
| WorldCallback zeroes every position model's speed only when base_watchdog_timeout is greater than 0 and the simulated time since the last command reaches that timeout. | upstream_code | stage_ros_private/src/stageros.cpp:443-448 |
| WorldCallback sets odometry pose.pose.position.x and position.y from est_pose, twist.twist.linear.x, linear.y and angular.z from GetVelocity, and header.stamp from sim_time, then publishes the message. | upstream_code | stage_ros_private/src/stageros.cpp:539-554 |
| base_watchdog_timeout is a ROS parameter whose default is 0.2 s when the parameter is not set. | upstream_code | stage_ros_private/src/stageros.cpp:288-291 |
| cb_reset_srv sets every position model to its stored initial pose and clears SetStall, then returns true; it does not set the commanded speed to zero. | upstream_code | stage_ros_private/src/stageros.cpp:260-268 |
| frontier_filter publishes the relative filtered_frontiers topic as frontier_exploration/PointArray. | upstream_code | frontier_exploration/scripts/frontier_filter.py:24 |
| The exploration launch reads /filtered_frontiers as the assigner's frontier topic. | upstream_code | frontier_exploration/launch/robot_assigner.launch:9 |
| multi_robot_navigation.launch includes navigation.launch with robot_name robot_0 and with robot_name robot_1. | upstream_code | frontier_exploration/launch/multi_robot_navigation.launch:1-10 |
| navigation.launch starts move_base in the namespace given by robot_name. | upstream_code | frontier_exploration/launch/navigation.launch:3-6 |
| MoveBase advertises a geometry_msgs::Twist publisher on the relative cmd_vel topic. | upstream_code | navigation/move_base/src/move_base.cpp:91-92 |
| The assigner calls sendGoal. | upstream_code | frontier_exploration/scripts/decent_robot_assigner.py:246 |
| The shipped pioneer3dx-sick world sets interval_sim 100. | upstream_code | frontier_exploration/stage-worlds/pioneer3dx-sick.world:321 |
| A Stage world file in the clone comments that interval_sim 100 is a simulation timestep in milliseconds. | upstream_code | stage_ros_private/world/willow-erratic.world:61 |

## Tags

`ros`, `ros1`, `stage`, `simulation`, `multi-robot`, `exploration`, `laser`

## Limits and safety notes

- Both `cmd_vel` inputs use `Limit.operator_required`: the pinned clone forwards the Twist to
  `ModelPosition::SetSpeed` and states no signed velocity or yaw-rate bound. The operator supplies the envelope in
  `site-limits.json`; `site-limits.example.json` is illustrative test data, not an upstream fact.
- The e-stop is a sensed-confirmation stop (SAFE-049, simulated only). It publishes a zero Twist on
  `/robot_0/cmd_vel` and `/robot_1/cmd_vel` and is achieved only when both odometry streams then stay at rest for
  three consecutive fresh samples. The publication proves nothing by itself. Every threshold is
  `Limit.operator_required`. `fixtures/estop-confirmation.json` holds placeholder values for the fake only, not a
  device fact. The client bounds (`consecutive` 3, `min_span_ms` 200, `max_gap_ms` 500, `confirm_within_ms` 1500)
  are a package choice; a live simulation sets its own in `simulation_deployment['estop_confirmation']`.
- This is ROS 1. The odometry advertise call passes queue length 10 and no latch argument, the bridge discards the
  first sample, and the declaration has no history.
- `WorldCallback` zeroes every position model once `base_watchdog_timeout` (default 0.2 s when unset, skipped when
  the parameter is 0) elapses without a command. The confirmation can therefore see robots at rest without the zero
  Twist having been applied. A publisher that refreshes `cmd_vel` keeps the watchdog from firing, and the stop
  fails closed.
- The shipped world has three position models. This stop commands and senses only `robot_0` and `robot_1`.
  `pioneer2` is zeroed only by the watchdog.
- With `multi_robot_navigation.launch` running, `move_base` publishes `cmd_vel` in each robot namespace
  (`move_base.cpp:91-92`). The assigners call `sendGoal` (`decent_robot_assigner.py:246`); they do not publish
  `cmd_vel`. Those goals keep `move_base` commanding, and the confirmation then fails closed. Nothing watches the
  robots after the confirmation window.
- `cb_reset_srv` teleports every position model to its initial pose and clears stall without zeroing the commanded
  speed (`stageros.cpp:260-268`). It is not bound as the reset and is not offered as a re-enable (SAFE-042). The
  MHS reset re-confirms the sensed stop and changes nothing on the Stage models.
- The device risk is R2 (REVIEW.md item 12): `cmd_vel` is a topic a physical mobile base would also consume. The
  card's risk floor stays R0. The fake is a ROS-free contract transport. Every value in `fake.py` is test data and
  carries a `# placeholder` comment; none is a Fact or a Limit.
- `robot_0_twist` and `robot_1_twist` are read-only resource fields. Each is `twist.twist` from the first sample
  of a new subscription of that robot's odometry topic. The fake stores the last Twist it accepted on that
  robot's `cmd_vel` and reports it there. That echo is not `GetVelocity` and not a Stage measurement. A live
  subscriber receives the next `WorldCallback` publish, and the `cmd_vel` command does not wait for that publish.
  The command receipt stays `{published, confirmed}` because a rosbridge publication carries no execution result.
