OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of an Anthropic MHS research preview.

# Facts and tags for gh.rgnc/enps_dwa

Every fact cites the pinned clone at commit `ce876244db34e9684b0517253d5adf83bc04cc7c`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The node reads the odom_id parameter with the default absolute name /odom and advertises a nav_msgs::Odometry publisher on it. | upstream_code | src/enps_dwa_node.cpp:545-553 |
| publishOdom converts agent 0's map pose into the odom frame with transformPose and returns false without publishing when transformPose fails; otherwise it publishes the pose with frame odom, child frame base_link and agent 0's linearVelocity and angularVelocity. | upstream_code | src/enps_dwa_node.cpp:191-221 |
| transformPose returns false when the tf listener's transformPose throws. | upstream_code | src/enps_dwa_node.cpp:445-464 |
| main constructs the node with a public handle n and the private handle pn('~'). | upstream_code | src/enps_dwa_node.cpp:623-630 |
| The node sleeps 0.5 s and then uses sfm::MAP. | upstream_code | src/enps_dwa_node.cpp:564-565 |
| MAP is defined as RosMap::getInstance(), which returns a function-local static RosMap. | upstream_code | include/lightsfm/rosmap.hpp:63-68 |
| The RosMap constructor calls the static_map service once and stops with ROS_FATAL and ROS_BREAK when the call fails. | upstream_code | include/lightsfm/rosmap.hpp:102-121 |
| After simulator::run the loop sets agent 0's linearVelocity and angularVelocity to the simulator's selectedLinVel and selectedAngVel. | upstream_code | src/enps_dwa_node.cpp:605-608 |
| The node opens metrics.txt and writes its header line. | upstream_code | src/enps_dwa_node.cpp:501-502 |
| Once a second the loop appends each agent's velocity and nearest-person and nearest-obstacle distances to metrics.txt. | upstream_code | src/enps_dwa_node.cpp:590-597 |
| The node reads the scan360_id parameter with the default absolute name /scan360 and advertises a sensor_msgs::LaserScan publisher on it. | upstream_code | src/enps_dwa_node.cpp:549-556 |
| The scan geometry is built from the configured reading count, robot radius and maximum scan range: the angular limits are -M_PI and M_PI and the increment is 2*M_PI/scan360_readings. | upstream_code | src/enps_dwa_node.cpp:569-577 |
| The scan loop ray-casts from the robot pose, treats an intersecting person as scan_range_max, and clamps every reported range to at least robot_radius and at most scan_range_max. | upstream_code | src/enps_dwa_node.cpp:263-284 |
| The node reads its parameters through pn and advertises six publishers; it registers no subscriber, service server or action server in this block. | upstream_code | src/enps_dwa_node.cpp:538-558 |
| The main loop broadcasts the map-to-odom transform, calls publishOdom and publishScan360 on every iteration and sleeps on a ros::Rate built from freq until the node handle shuts down. | upstream_code | src/enps_dwa_node.cpp:562-614 |
| The launch file starts map_server with maps/temple.yaml, the enps_dwa_node executable and RViz. | upstream_code | launch/temple.launch:5-9 |
| The README states that the software simulates human agents and a dual-wheeled non-holonomic robot, that the simulation runs until the user kills the process, and that the ENPS model selects motion commands with DWA. | vendor_doc | README.md:11 |
| The README documents ROS Noetic, compilation with catkin_make and starting the example with roslaunch enps_dwa temple.launch. | vendor_doc | README.md:21-32 |

## Scope

The pinned node is an autonomous simulator. It reads private parameters, advertises
`/odom`, `/detections`, `/trajectories`, `/scan360`, `/people` and `/forces`, and
publishes them from its own `ros::Rate` loop. It registers no subscriber, service
server or action server. The package therefore exposes the two primary robot
observations — `nav_msgs/Odometry` on `/odom` and `sensor_msgs/LaserScan` on
`/scan360` — as read-only extension capabilities. It does not expose an
environment-step, velocity-command, pause, reset or stop endpoint because the clone
has none. The `/people`, `/detections`, `/trajectories` and `/forces` MarkerArray
topics, the TF broadcasts, the `metrics.txt` output and the private ROS parameters
are NOT COVERED.

The topic names are ROS parameters with defaults `/odom` and `/scan360`
(`src/enps_dwa_node.cpp:545`, `:549`). A deployment that remaps them must expose
those resolved endpoints to rosbridge; the package cannot discover the graph and
does not invent a remapping. `publishOdom` returns without publishing when
`transformPose` fails (`src/enps_dwa_node.cpp:191-221`, `:445-464`), so an odom
observation can time out while the node's tf listener does not yet have the
map-to-odom transform the node broadcasts itself. At start-up the node calls
map_server's `static_map` service once, 0.5 s after it starts, and stops with
`ROS_BREAK` when the call fails (`include/lightsfm/rosmap.hpp:102-121`), so if
map_server is not yet serving, neither topic ever appears.

No `Limit` is declared: both capabilities take an empty input (a subscription is
not a command). The numeric values in the clone's parameter declarations are
configurable defaults, not device limits, and none of them is a bound on a caller
input. Consequently `site-limits.example.json` is not needed.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic: ROS-free transport fake
(no physics, no planner)`, level F0, determinism `none`, `timestep_ms: 0` (event-driven
samples with no physics step), `realtime_factor: 0` (not paced), reset `none`, and no
snapshot/restore. The fake returns fixed placeholder messages on each subscription.
Its scan has eight placeholder ranges; the upstream default `scan360_readings` is
1440 and is overridable, so the deployed array length follows the operator's
configuration. Upstream timing and size defaults remain source facts, not claims
about the fake's fidelity. The gaps disclose the absent simulation, planner,
ray-casting and transform-failure behaviour.

## Safety

The device is simulated at R0 and the package binds only observation topics. The
upstream node has no command, stop or reset service, so there is no native stop to
call and no independent stop binding. The runtime's software latch is the only
stop for these observations; an e-stop receipt reports `software_only`, not a
native or physical stop. The simulation itself does not stop: the node keeps
advancing at its `freq` rate, its robot keeps driving under the ENPS/DWA planner
(`src/enps_dwa_node.cpp:605-608`) and its pedestrians keep walking until the
process is killed. The driver lock keeps `reviewed_by: null`; no human has
reviewed the package and no hardware or live ROS run is claimed.

## Tags

`ros`, `ros1`, `simulation`, `enps-dwa`, `social-navigation`, `odometry`, `laser-scan`

## Model review (wave C)

A model review (not a human review; `reviewed_by` stays null) removed a "so ..."
inference from the odom fact, narrowed the publishOdom and parameter facts to their
lines, widened the main-loop fact to the `ros::Rate` it cites, rewrote `safe_state`
to say that the simulation and its self-driving robot keep running after an MHS
e-stop, and added source facts and gaps for the `static_map` start-up abort, the
tf dependency of `/odom`, the velocity source and the `metrics.txt` output.
