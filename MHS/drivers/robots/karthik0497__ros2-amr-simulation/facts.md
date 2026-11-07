# Facts and tags for gh.karthik0497/ros2-amr-simulation

Every fact cites the pinned clone at commit `202aad5cac8842dcf94385be4ed186fdd8b29718`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The ros_gz_bridge configuration declares /clock with rosgraph_msgs/msg/Clock, bridged GZ_TO_ROS. | upstream_code | src/robot_description/config/ros_gz_bridge.yaml:11-15 |
| The ros_gz_bridge configuration declares /cmd_vel with geometry_msgs/msg/Twist, bridged ROS_TO_GZ. | upstream_code | src/robot_description/config/ros_gz_bridge.yaml:17-21 |
| The ros_gz_bridge configuration declares /odom with nav_msgs/msg/Odometry, bridged GZ_TO_ROS. | upstream_code | src/robot_description/config/ros_gz_bridge.yaml:23-27 |
| The ros_gz_bridge configuration bridges the Gazebo topic /joint_states (gz.msgs.Model) to the ROS 2 topic /joint_states with sensor_msgs/msg/JointState, GZ_TO_ROS. | upstream_code | src/robot_description/config/ros_gz_bridge.yaml:35-39 |
| The gz-sim DiffDrive plugin configures left_wheel_joint and right_wheel_joint, wheel_separation 0.34 m, wheel_radius 0.05 m, the cmd_vel command topic and the odom odometry topic. | upstream_code | src/robot_description/urdf/gazebo.xacro:183-216 |
| The DiffDrive plugin declares max_linear_acceleration 1.0, max_angular_acceleration 2.0, max_linear_velocity 2.0 and max_angular_velocity 2.0 after a comment stating that these are velocity limits preventing simulation instability. | upstream_code | src/robot_description/urdf/gazebo.xacro:195-199 |
| The DiffDrive plugin publishes odometry at 50 Hz and names odom and base_footprint as its frame ids. | upstream_code | src/robot_description/urdf/gazebo.xacro:211-216 |
| AMRController creates a publisher for geometry_msgs/Twist on the absolute /cmd_vel topic with queue size 10. | upstream_code | amr_menu.py:21 |
| AMRController.publish_velocity publishes the same Twist at 10 Hz for a caller-computed duration, and stop() publishes one all-zero Twist and sleeps; neither reads a reply or checks that the robot stopped. | upstream_code | amr_menu.py:31-54 |
| move_forward and move_backward compute a duration from the local speed attribute, call publish_velocity and then stop. | upstream_code | amr_menu.py:58-72 |
| The README drives the robot with one geometry_msgs/msg/Twist publication on /cmd_vel. | vendor_doc | README.md:1916 |
| The README instructs the operator to stop the robot by publishing one Twist with linear.x 0.0 and angular.z 0.0 on /cmd_vel. | vendor_doc | README.md:1921-1923 |
| The README describes /cmd_vel as a ROS 2 to Gazebo only bridge and says Gazebo never sends velocity commands back to ROS 2. | vendor_doc | README.md:2395-2397 |
| The JointStatePublisher plugin is declared without a <topic> element, after a comment saying it publishes to the /world/*/model/*/joint_state Gazebo topic. | upstream_code | src/robot_description/urdf/gazebo.xacro:221-236 |
| robot.launch.py includes display.launch.py with use_rsp false. | upstream_code | src/robot_description/launch/robot.launch.py:24-31 |
| display.launch.py starts joint_state_publisher_gui without a condition; its comment says the sliders publish to /joint_states and that the node is only for testing. | upstream_code | src/robot_description/launch/display.launch.py:96-133 |
| The LICENSE file is the MIT License. | vendor_doc | LICENSE:1 |
| The robot_description package.xml declares the licence Apache-2.0. | upstream_code | src/robot_description/package.xml:9 |
| The README says the DiffDrive plugin publishes /odom (nav_msgs/Odometry) with the estimated robot position. | vendor_doc | README.md:1179-1186 |
| The README says the DiffDrive plugin calculates the robot position by integrating wheel rotations and that /odom contains position x, y, z, orientation and velocity. | vendor_doc | README.md:2404-2407 |
| AMRController.stop() publishes one default-constructed (all-zero) Twist with its publisher and sleeps. | upstream_code | amr_menu.py:50-54 |

## Scope

The integration is the simulated mobile base's bridged ROS 2 topic graph, not the
interactive `amr_menu.py` client and not the Gazebo physics. The bridge configuration
maps `/cmd_vel` from ROS 2 to Gazebo (`src/robot_description/config/ros_gz_bridge.yaml:17-21`)
and maps `/odom`, `/clock`, `/joint_states` and `/tf` from Gazebo to ROS 2
(`src/robot_description/config/ros_gz_bridge.yaml:11-15`, `23-27`, `29-33`, `35-39`). The
gz-sim DiffDrive plugin names the command and odometry topics and declares the two wheel
joints and their geometry (`src/robot_description/urdf/gazebo.xacro:183-216`).

The package declares one effectful capability, `x-cap.karthik0497.cmd_vel.v1`, which
publishes one geometry_msgs/Twist to `/cmd_vel`. The receipt returns
`{"published": true, "confirmed": false}`: a rosbridge publication proves transmission,
not that the diff-drive plugin moved the base, reached a pose or stopped. Pose and twist
reads subscribe to `/odom`; the clock and joint-state capabilities subscribe to `/clock`
and `/joint_states`. `NOT COVERED: /tf, the Gazebo world, the DiffDrive plugin's physics,
the warehouse collisions, RViz, Nav2 and any live ROS graph.`

## Limits

Both inputs of `x-cap.karthik0497.cmd_vel.v1` are `Limit.operator_required`. The clone states
only the DiffDrive plugin clamps `<max_linear_velocity>2.0</max_linear_velocity>` and
`<max_angular_velocity>2.0</max_angular_velocity>` (`src/robot_description/urdf/gazebo.xacro:198-199`)
and no reverse or negative bound. A plugin clamp is not a command envelope, and the earlier
one-sided `Limit(max=2.0)` left every negative command unbounded (a review probe published
`linear.x` -1000 m/s). `site-limits.example.json` (-0.5..0.5 m/s, -1.0..1.0 rad/s) is an example
operator overlay, not a source; without an overlay the server refuses the publication with
`MHS.SAFETY.LIMITS_UNSET`. The menu's local 0.30 m/s and 0.50 rad/s constructor defaults
(`amr_menu.py:24-25`) and its input prompts are client-side settings, not device bounds,
and are not cited as Limits.

## Sensed-confirmation stop (SAFE-049)

The user's decision of 2026-11-05 allows a request plus a sensed confirmation as the stop of a simulated
device. The e-stop publishes the zero Twist the README prescribes (`README.md:1921-1923`) on `/cmd_vel`
(`ros_gz_bridge.yaml:17-21`), then reads the bridged `/odom` pose (`ros_gz_bridge.yaml:23-27`; position
and orientation still over the window; the README states that `/odom` carries position, orientation and
velocity, `README.md:2405-2407`). The predicate reads the pose only: the twist fields are filled by the
gz-sim DiffDrive plugin outside the clone, and the local gz-sim clone is not the Harmonic version the clone
uses. `/joint_states` is never a source (`display.launch.py` also starts `joint_state_publisher_gui` on it).
The request steps prove nothing by themselves. The e-stop is achieved only when every source delivers three consecutive fresh samples (new subscriptions opened after the request; what a new subscription may receive from before it existed never counts: the history of the `/odom` publisher, ros_gz_bridge's parameter_bridge, is `operator_required`, because its source is outside the clone and the clone's bridge entry (`src/robot_description/config/ros_gz_bridge.yaml:23-27`) and launch parameters (`src/robot_description/launch/gazebo.launch.py:144-153`) set no QoS; a live simulation states it in `simulation_deployment['estop_confirmation']['history']` and the bridge discards that many samples, at least the first; strictly increasing producer stamps; every predicate term holding; an arrival gap above `max_gap_ms` or a repeated stamp restarts the count) within `confirm_within_ms` of the first transmission. Otherwise the e-stop is `failed` `MHS.SAFETY.SAFE_STATE_UNREACHED` (`details.sensed.reason`), the latch holds and the background retry sends the request again. Thresholds are `operator_required` (the fake's placeholders are in `fixtures/estop-confirmation.json`; a live simulation supplies them in `simulation_deployment['estop_confirmation']`); the client bounds (`consecutive` 3, `min_span_ms` 200, `max_gap_ms` 500, `confirm_within_ms` 1500) are fake-scale, and a live deployment sets its own. The SDK cannot prove that the ROS graph is simulated; only a simulated device may use this profile. At the 50 Hz odometry rate a live deployment raises `consecutive` so that its samples span
`min_span_ms`.

`amr_menu.py` and `drive_pattern.py` also publish `/cmd_vel` and can move the base after a confirmed stop; a
reset re-confirms without a request and is refused then, but nothing prevents it.

## Safety

The declaration is `mode = "simulated"` and `device_kind = "robot.mobile_base"`, with
`risk = "R2"` because the catalogue class for a mobile base is R2 and the card floor is
R1. No acknowledged stop exists. The clone creates no ROS service or action server; the
DiffDrive plugin only consumes `/cmd_vel`. `AMRController.stop()` publishes one zero
Twist and sleeps (`amr_menu.py:50-54`), and the README's stop instruction is another
single zero-Twist publication (`README.md:1921-1923`). Neither carries an application
acknowledgement, and the bridge direction is ROS 2 to Gazebo only
(`README.md:2395-2397`). Neither is a stop by itself; the e-stop is the sensed-confirmation stop above. No physical emergency stop exists in this simulation repository and no hardware
run is claimed.

A live `/joint_states` read may time out or return GUI slider values: the JointStatePublisher
plugin declares no `<topic>` and its comment names the `/world/*/model/*/joint_state` Gazebo topic,
while the bridge reads the Gazebo topic `/joint_states`; `robot.launch.py` also starts
`joint_state_publisher_gui` through `display.launch.py`, which publishes slider positions on
`/joint_states`.

Licence: the card records MIT and `publish_review: not_required`, but `LICENSE` is the MIT License
while `src/robot_description/package.xml` declares Apache-2.0; the owner decides.

`driver.lock.json` keeps `reviewed_by: null`; this is a model-authored, unreviewed
package. The fake is not a recording of captured traffic and claims F0 only.

## Tags

`ros`, `ros2`, `gazebo`, `simulation`, `mobile-base`, `cmd-vel`, `odometry`,
`differential-drive`
