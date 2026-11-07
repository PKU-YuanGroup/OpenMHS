OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a
reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.viviancremerkalempa/swarm_stage_ros

Every fact cites the pinned clone at commit `f365595f5fa947340f64bc8f017820846096661c`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the statement spans
adjacent lines. The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| README describes the package as a ROS package that automatically configures a swarm robot simulator and says the documented start command is roslaunch swarm_stage_ros swarm_stage.launch. | vendor_doc | README.md:3-16 |
| README says that at the end of processing custom.world and controller.launch are generated, and that controller.launch starts the environment. | vendor_doc | README.md:20-46 |
| The generated controller.launch starts the external stage_ros/stageros node with custom.world, one posctrl node per robot, and one controller node with argument 3 in the shipped file. | upstream_code | launch/controller.launch:6-10 |
| The shipped swarm.yaml sets formation no, robots 3, position_controller yes, reference global and run yes; these are operator configuration values, not device bounds. | upstream_code | yaml/swarm.yaml:1-17 |
| swarm_stage writes a controller.launch header that starts the ROS master and the stage_ros stageros node with launch/custom.world and respawn true. | upstream_code | src/swarm_stage.cpp:66-71 |
| The shipped controller.launch starts stageros with respawn true. | upstream_code | launch/controller.launch:6 |
| When the run parameter is yes, swarm_stage calls system(" killall stageros") and then system("roslaunch swarm_stage_ros controller.launch"). | upstream_code | src/swarm_stage.cpp:421-425 |
| robot() writes one Stage model line per robot and, when position_controller is yes, writes a posctrl node with args="robot_<number>". | upstream_code | src/swarm_stage.cpp:709-712 |
| MainController::mainControl runs four loops of n/4 robots; each iteration advertises turtlesim::Pose on /robot_<i> with queue size 1000, sleeps 10 s and publishes that robot's target pose. | upstream_code | src/MainController.cpp:28-51 |
| MainController::setPositions computes the target pose array from the requested robot count; it does not publish a feedback or stop topic. | upstream_code | src/MainController.cpp:54-91 |
| PositionController::setTopics sets the subscription to /<nodeName> and the command publication to /<nodeName>/cmd_vel. | upstream_code | src/PositionController.cpp:42-45 |
| PositionController::mainControl advertises geometry_msgs::Twist on topicPub_ and subscribes to topicSub_ with queue size 15000. | upstream_code | src/PositionController.cpp:33-35 |
| PositionController::subCallback loops while the distance to the target is greater than 0.3 m, publishes Twist commands, and has no ROS cancellation, pause or stop check inside the loop. | upstream_code | src/PositionController.cpp:54-75 |
| PositionController::subCallback reads only msg->x and msg->y and computes the heading with atan2(msg->y - feedback_.y, msg->x - feedback_.x); it never reads the Pose theta field. | upstream_code | src/PositionController.cpp:56-57 |
| robotTransformed looks up the map to <node>/base_link transform and retries every second on a transform exception while ros::ok(). | upstream_code | src/PositionController.cpp:80-93 |
| posctrl takes argv[1] as the node name, initialises the ROS node with it and passes it to setTopics. | upstream_code | src/posctrl.cpp:10-21 |
| The generated map include sets quit_time 3600 and paused 1 as static world properties. | upstream_code | launch/include/map.inc:1-3 |
| CMakeLists builds the swarm_stage, controller and posctrl executables. | upstream_code | CMakeLists.txt:204-219 |

## Scope

This package binds one runtime control: the `turtlesim/Pose` target publication on `/robot_0`. The
generated launch starts `posctrl` for `robot_0` with argument `robot_0` (`launch/controller.launch:7`,
`src/posctrl.cpp:10-21`), and `MainController::mainControl` constructs the topic `/robot_<i>` and
advertises `turtlesim::Pose` on it (`src/MainController.cpp:28-32`). The follower subscribes to
`/robot_0` and publishes `geometry_msgs/Twist` on `/robot_0/cmd_vel`
(`src/PositionController.cpp:42-45`, `src/PositionController.cpp:33-35`).

The generated launch also starts `posctrl` for `robot_1` and `robot_2`, and a `controller` formation
node (`launch/controller.launch:7-10`). A RosDriver binding has one fixed endpoint, so this package
binds only the explicit `robot_0` namespace. The other robots and the formation publisher are not
proxied; a deployment that wants a different robot must expose the same target topic for that robot
and configure the driver accordingly.

The built-in formation controller publishes only when `n/4` is positive: all four loops in
`MainController::mainControl` divide the requested count by four (`src/MainController.cpp:28-50`).
With the shipped `robots: 3` (`yaml/swarm.yaml:3`) and `args="3"` (`launch/controller.launch:10`),
`mainControl(3)` enters none of the loops, so the target must come from another ROS client or from a
robot count that the controller handles. This is an upstream configuration behavior, not a driver
limit.

Stage's own topics (`/odom`, `/base_scan`, `/base_pose_ground_truth`, `/clock`, and the `map`
transform) are produced by the external `stage_ros/stageros` package named in the generated launch
(`launch/controller.launch:6`). The pinned clone declares none of those endpoints, so this package
does not invent bindings for them. The `turtlesim/Pose` target is the only control endpoint that the
clone's own controller code consumes.

## Limits

The clone computes target poses from runtime formation parameters, robot counts and a generated world
(`src/MainController.cpp:54-91`, `src/swarm_stage.cpp:709-712`) and states no numeric arena or x/y
bound. The Pose `theta` field is not an operator input: the follower computes its heading from the
target x/y direction with `atan2` and never reads `msg->theta` (`src/PositionController.cpp:56-57`), so
the driver sends `theta: 0.0` and exposes only x and y. The driver therefore declares x and y as
`Limit.operator_required`; the operator supplies a site envelope in `site-limits.json` and every target
write is refused with `MHS.SAFETY.LIMITS_UNSET` until then. The shipped `3`/`5`/`0.5` values and the
map size are configuration and layout defaults, not device bounds, and are not copied into a Limit.

## Safety

The target starts an autonomous mobile-base position controller in the simulated Stage world, so the
driver is R2 even though the effect is simulated. There is no acknowledged stop to bind: the clone's
only C++ nodes create publishers and subscribers (no `advertiseService`, action server or
`dynamic_reconfigure` server), the follower loop has no cancellation check
(`src/PositionController.cpp:54-75`), and the only process stop is
`system(" killall stageros")` in the generator's run branch (`src/swarm_stage.cpp:421-425`). A
zero-Twist publication would be overwritten by the follower's own loop and proves only transmission;
`killall stageros` is a process-level command, not a ROS service or action. The package therefore
declares `safety_bindings = {}`, claims no safe state and does not present either path as an e-stop.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS recording fake (no physics)`, level F0,
determinism `none`, `timestep_ms: 0` (event-driven recording with no physics step), `realtime_factor:
0` (not paced), reset `none`, and no snapshot/restore. The gaps disclose the absent Stage world,
stageros, posctrl follower, TF lookup, multi-robot namespaces and live deployment. The fake records
only the `/robot_0` advertise and publish messages; its pose values are test data, not observations.
Live ROS, rosbridge, `catkin_make`, Stage and hardware are not run or validated.

## Tags

`ros`, `ros1`, `simulation`, `stage`, `swarm`, `mobile-base`, `position-control`
