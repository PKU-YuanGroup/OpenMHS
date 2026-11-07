# Facts and tags for gh.fazildgr8/ros_autonomous_slam

Every fact cites the pinned clone at commit `997c968cb64f544b913e72debcceaad0ed2faea9`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README describes a ROS package that uses the Navigation Stack, GMAPPING and a Gazebo TurtleBot3 Waffle Pi to explore an unknown environment and build a map. | vendor_doc | README.md:3 |
| The autonomous explorer launch includes the SLAM launch, the turtlebot3_navigation move_base launch and the selected explorer launch. | upstream_code | launch/autonomous_explorer.launch:6-18 |
| The RRT launch passes /map as map_topic to both RRT detectors and to filter.py, and passes /filtered_points as frontiers_topic to assigner.py. | upstream_code | launch/RRT.launch:9-38 |
| The RRT explorer imports nav_msgs/Odometry and nav_msgs/OccupancyGrid. | upstream_code | nodes/autonomous_rrt.py:10 |
| The RRT explorer subscribes to the absolute /odom and /map topics with those message types. | upstream_code | nodes/autonomous_rrt.py:178-180 |
| filter.py imports the package's PointArray message from ros_autonomous_slam.msg. | upstream_code | scripts/filter.py:14 |
| filter.py creates a PointArray publisher on the relative topic 'filtered_points' with queue size 10. | upstream_code | scripts/filter.py:112 |
| PointArray.msg defines the message as an array of geometry_msgs/Point named points. | upstream_code | msg/PointArray.msg:3 |
| filter.py appends the clustered centroids to arraypoints and publishes the PointArray on filterpub. | upstream_code | scripts/filter.py:221-226 |
| assigner.py subscribes to frontiers_topic as a PointArray. | upstream_code | scripts/assigner.py:57 |
| The assigner sends the winning centroid with robots[id_record[winner_id]].sendGoal. | upstream_code | scripts/assigner.py:145 |
| wall_follow.py creates a LaserScan subscriber on the absolute /scan topic and a Twist publisher on the absolute /cmd_vel topic. | upstream_code | nodes/wall_follow.py:60-61 |
| wall_follow.py copies the LaserScan ranges into x and loops over 360 bins. | upstream_code | nodes/wall_follow.py:36-37 |
| After its control loop exits, wall_follow.py publishes a zero Twist and prints 'Turtlebot stopped'. | upstream_code | nodes/wall_follow.py:97-103 |
| The RRT explorer creates an actionlib SimpleActionClient for move_base and sends a MoveBaseGoal; this is an internal navigation call, not an upstream command server. | upstream_code | nodes/autonomous_rrt.py:126-141 |
| The README tells the operator to define the exploration region with boundary and start points using the RVIZ Publish Points option. | vendor_doc | README.md:34-35 |
| The global RRT detector subscribes to the absolute /clicked_point topic. | upstream_code | src/global_rrt_detector.cpp:81 |
| The global RRT detector includes geometry_msgs/PointStamped.h. | upstream_code | src/global_rrt_detector.cpp:13 |
| The global RRT detector waits until five clicked points have been collected, then uses points 0, 2 and 4 as the region corners and start point. | upstream_code | src/global_rrt_detector.cpp:132-175 |

## Scope

The pinned repository is a ROS 1 task environment: it launches SLAM, move_base and an
RRT or wall-following explorer for a TurtleBot3 in Gazebo. Its own nodes subscribe to
`/map`, `/odom` and `/scan`, publish `/filtered_points` and `/cmd_vel`, and call the
external `/move_base` action. No upstream service or action accepts an operator motion
request, and the wall-following node's only stop-shaped action is a zero-Twist
publication after its loop exits (`nodes/wall_follow.py:97-103`); that is not an
acknowledged stop binding.

This package therefore binds five explicit observations and no actuation:
`/map` (`nav_msgs/OccupancyGrid`), `/filtered_points`
(`ros_autonomous_slam/PointArray`), `/clicked_point`
(`geometry_msgs/PointStamped`), `/odom` (`nav_msgs/Odometry`) and `/scan`
(`sensor_msgs/LaserScan`). Each is a fresh subscription action, not an automatic
resource snapshot, so the main resource snapshot is empty and a silent topic fails
only the observation that asked for it. The internal `/cmd_vel` publication is not
bound as a command: a rosbridge publication is transmission-only and a zero-velocity
publication is not an acknowledged stop. The five `/clicked_point` messages that
start RRT exploration are likewise not published by this package, because the
explorer has no acknowledged stop once it starts. Operator motion control is outside
this profile.

`filter.py` publishes `filtered_points` as a relative name and the shipped RRT launch
runs the filter node in the root namespace, so the configured endpoint is
`/filtered_points`; a deployment that namespaces the node must expose the resolved
name. `filter.py` defaults its map topic to the relative name `map`
(`scripts/filter.py:55`), but the RRT launch passes the absolute `/map`;
`wall_follow.py` itself uses the absolute `/scan` and `/cmd_vel`
(`nodes/wall_follow.py:60-61`); the author's text said both default to relative
names (corrected by the model review of 2026-11-05). The
`PointArray` message has no header, so the frontiers observation has no sample time.

Each observation subscribes with the 2 s wire default. `/clicked_point` is
published only when an operator publishes a point in RViz (`README.md:34-35`),
so that observation fails unless a point arrives within 2 s. The bridge refuses
non-finite JSON numbers, so a live `/scan` whose no-return ranges arrive as
non-finite values fails instead of returning a substituted number (a package
case covers it). Messages are bounded by the 1 MiB rosbridge default; a live
map whose JSON exceeds it is refused, not truncated (model review 2026-11-05).

## Fidelity contract

`driver.py` describes the deployed fake: engine `canned:ROS-free topic stand-in (no physics)`,
level F0, determinism `none`, `timestep_ms: 0` (event-driven canned replies with no
physics step), `realtime_factor: 0` (not paced), reset `none`, and no snapshot/restore.
The fake returns a 4 by 3 occupancy grid with 12 cells and 3 frontier points, and 8
LaserScan ranges. The live map size is the `OccupancyGrid` width times height, the live
frontier count is the filtered cluster count, and `wall_follow.py` loops over 360 scan
bins (`nodes/wall_follow.py:36-37`); the RRT nodes allocate 384 by 384 map buffers
(`nodes/autonomous_rrt.py:24`). These are code assumptions, not bounds, and the smaller
fake arrays are test data. No Gazebo physics, GMAPPING, SLAM, RRT, wall-following, TF,
move_base, ROS graph or wall-clock loop is reproduced.

## Safety

The device is a simulated task environment at R0. The profile exposes only observations
and no actuation, stop or reset binding. A stock e-stop is the runtime software latch
and is reported as `software_only`; the extension read actions are not granted a
catalogue-read exemption and remain latched until an operator reset. No physical e-stop,
native stop, world pause or hardware safe state is claimed. The upstream `/cmd_vel`
publisher and `/move_base` client are internal autonomy paths, not an operator interface.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `turtlebot3`, `slam`, `exploration`, `rrt`
