# Facts and tags for gh.rumaisaabdulhai/quad_sim

Every fact cites the pinned clone at `01d02f6e2fad8060d6522b7bca01cb82aa038c2a`:
`upstream_code` for source or comments of the clone, `vendor_doc` for text such as
`README.md` or `docs/*.md`. The ref is the clone-relative `path:LINE` (a bounded
start-end line range where the statement spans several lines). The `facts = [...]`
list in `driver.py` is the source of truth; `reference.json` and `REFERENCE.md`
are generated from it.

| fact | source | ref |
|---|---|---|
| The `Results` constructor calls `rospy.init_node('quad_results')` and creates subscribers on `/ground_truth_to_tf/pose` (`PoseStamped`), `/move_base/status` (`GoalStatusArray`) and `/results_saver` (`Empty`). | upstream_code | `quadcopter_results/src/quadcopter_results.py:50-76` |
| The `Results` module imports `geometry_msgs` `PoseStamped` and `actionlib_msgs` `GoalStatusArray`. | upstream_code | `quadcopter_results/src/quadcopter_results.py:17-19` |
| `pose_cb` stores the previous and current `PoseStamped` samples and calls `set_total_dist` only while `isActive` is true. | upstream_code | `quadcopter_results/src/quadcopter_results.py:226-237` |
| `get_delta_dist` computes the planar Euclidean distance from the previous and current pose position x and y. | upstream_code | `quadcopter_results/src/quadcopter_results.py:94-110` |
| `set_total_dist` adds the `get_delta_dist` result to `total_dist`. | upstream_code | `quadcopter_results/src/quadcopter_results.py:174-176` |
| `status_cb` reads `status_list[0]`, records its `goal_id` stamp seconds as `init_time`, sets `isActive` when the status is not 3 and sets `isComplete` when the status is 3. | upstream_code | `quadcopter_results/src/quadcopter_results.py:201-216` |
| After completion `status_cb` calls `set_elapsed_time`, `set_avg_speed`, `append_df` and `reset_params`, then increments `GOAL_NUM`. | upstream_code | `quadcopter_results/src/quadcopter_results.py:218-224` |
| `set_elapsed_time` subtracts `init_time` from `final_time` and `set_avg_speed` divides `total_dist` by `elapsed_time`. | upstream_code | `quadcopter_results/src/quadcopter_results.py:178-196` |
| `create_df` declares the columns `Goal`, `Final Position`, `Elapsed Time`, `Distance Traveled` and `Average Speed`. | upstream_code | `quadcopter_results/src/quadcopter_results.py:31-36` |
| `append_df` writes the rounded final position, elapsed time, total distance and average speed into the dataframe. | upstream_code | `quadcopter_results/src/quadcopter_results.py:154-170` |
| `save_results_cb` writes the dataframe to the literal path `~/catkin_ws/src/quadcopter_sim/quadcopter_results/src/Results.csv` when `/results_saver` receives an `Empty` message. | upstream_code | `quadcopter_results/src/quadcopter_results.py:239-249` |
| The `Results` constructor creates `rospy.Subscriber` objects, creates a `rospy.Rate(5)` and then calls `rospy.spin`; it creates no ROS service server. | upstream_code | `quadcopter_results/src/quadcopter_results.py:45-79` |
| The take-off/land node subscribes to `/move_base/feedback`, `/cmd_vel`, `/ground_truth_to_tf/pose` and `/quadcopter_land`, and creates a `Twist` publisher on `/cmd_vel`. | upstream_code | `quadcopter_takeoff_land/src/quadcopter_takeoff_land.py:31-38` |
| The take-off/land node advertises a `Twist` publisher on `/cmd_vel` with queue size 1. | upstream_code | `quadcopter_takeoff_land/src/quadcopter_takeoff_land.py:38` |
| The teleoperation node advertises a `Twist` publisher on `/cmd_vel` with queue size 5. | upstream_code | `quadcopter_teleop/src/quadcopter_teleop.py:92` |
| The results launch starts `quadcopter_results.py` as the `quad_results` node. | upstream_code | `quadcopter_results/launch/quadcopter_results.launch:3` |
| The quadcopter launch includes `gazebo_ros/launch/empty_world.launch` with the school world and spawns the hector quadrotor model. | upstream_code | `quadcopter_gazebo/launch/quadcopter.launch:11-29` |
| The navigation documentation instructs the operator to publish `/quadcopter_land` at 5 Hz as `std_msgs/Empty`. | vendor_doc | `docs/navigation.md:56` |
| The project index describes mapping with gmapping or cartographer and autonomous navigation with move_base. | vendor_doc | `docs/index.md:21-26` |

Tags (short lowercase keywords): `ros`, `ros1`, `simulation`, `gazebo`,
`quadcopter`, `results`, `pose`, `move-base`.

Model review (2026-11-05): the `append_df` and constructor facts now cite the
lines that show the rounding (154-163) and the whole constructor (45-79); the
take-off/land fact says the node creates a `/cmd_vel` publisher. The
`rospy.Rate(5)` is never slept on, so the results node has no 5 Hz pacing.
