# Facts and tags for gh.sahilrajpurkar03/nlp-pnp-robotic-arm

Every fact cites the pinned clone at commit `79156f61c770f7dbf9373a45c62faecac3d67d81`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The C++ node creates a std_msgs::msg::String publisher on the absolute /pick_place_status topic with queue size 10. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:383-384 |
| The C++ node creates a std_msgs::msg::Float64 publisher on /gripper_joint/command with queue size 10. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:388-389 |
| The C++ node subscribes to /target_point with std_msgs::msg::Float64MultiArray and rejects a message with fewer than four numbers. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:403-411 |
| The /target_point callback reads data[0], data[1], data[2] and data[3] as x, y, yaw and box and marks a new target available when any value differs from the last accepted value or the box changes. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:414-429 |
| The target callback updates target_x, target_y, target_yaw, target_box and new_target_available under a mutex. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:424-433 |
| The main loop takes the pending target under the mutex, clears new_target_available and calls executePickAndPlace; a target received during the sequence is only queued for the next loop iteration. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:466-482 |
| executePickAndPlace publishes ACTIVE, opens the gripper, moves in XY, rotates yaw, moves down 0.255 m, closes the gripper, moves up 0.255 m, moves to the box, moves down 0.255 m, opens, moves up 0.255 m and moves to the arm_ready named pose, sleeping between the steps. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:297-346 |
| When executePickAndPlace fails, the main loop logs the failure, publishes ERROR, breaks out of the loop, cancels the executor, joins the spinner thread and calls rclcpp::shutdown(). | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:480-497 |
| The node initialises target_box to -1.0 and last_x, last_y and last_yaw to 0.0. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:374-380 |
| The main loop declares a local delay of 2 seconds. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:453-456 |
| For box 1 the node assigns x 0.4 and y -0.53; for box 2 it assigns x 0.4 and y 0.53; there is no other branch and box_x and box_y are otherwise uninitialized. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:319-330 |
| moveToWorldXY calls move_group.execute(trajectory) and returns true without checking the execute result. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:79-83 |
| rotateGripperYaw calls move_group.execute(trajectory) and returns true without checking the execute result. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:123-127 |
| moveDownZ calls move_group.execute(trajectory) and returns true without checking the execute result. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:157-161 |
| moveUpZ calls move_group.execute(trajectory) and returns true without checking the execute result. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:213-217 |
| moveToNamedPose calls move_group.execute(plan), then reads the current pose and returns true without checking the execute result. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:35-48 |
| closeGripper calls gripper_group.execute(plan) and returns true without checking the execute result. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:179-184 |
| openGripper calls gripper_group.execute(plan) and returns true without checking the execute result. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:267-272 |
| The status timer publishes current_status every 200 ms. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:394-400 |
| The node declares MoveGroupInterface planning groups arm and gripper and a node named ur5_xy_yaw_approach. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:356-362 |
| The node declares pos_tol 0.001 and yaw_tol 0.01 as configurable ROS parameters with those defaults. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:367-372 |
| The node uses a SingleThreadedExecutor on a spinner thread and a separate main loop for the motion sequence. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:447-452 |
| The only cancel call in the C++ node is executor.cancel() after the main loop, followed by spinner.join() and rclcpp::shutdown(). | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:495-497 |
| The target publisher creates a Float64MultiArray publisher on /target_point with queue size 10 and a String subscription on /target_class_cmd. | upstream_code | pick_place_chatbot_ui/target_publisher.py:26-32 |
| The target publisher writes [x, y, yaw, box] into Float64MultiArray.data and uses -1.0 when no box is set. | upstream_code | pick_place_chatbot_ui/target_publisher.py:109-117 |
| The target publisher publishes only when a detection's class_name equals the requested target class and then sets published true. | upstream_code | pick_place_chatbot_ui/target_publisher.py:79-124 |
| CMake builds the ur5_pick_place_cpp_r executable. | upstream_code | src/ur5_moveit_config/CMakeLists.txt:16-22 |
| CMake also builds a second executable, ur5_pick_place_cpp_s, from src/ur5_pick_place_cpp_s.cpp. | upstream_code | src/ur5_moveit_config/CMakeLists.txt:24-30 |
| ur5_pick_place_cpp_s subscribes to /target_point with std_msgs::msg::Float64MultiArray. | upstream_code | src/ur5_moveit_config/src/ur5_pick_place_cpp_s.cpp:359-362 |
| CMake installs ur5_pick_place_cpp_r under lib/ur5_moveit_config. | upstream_code | src/ur5_moveit_config/CMakeLists.txt:32-37 |
| The README runs ros2 run ur5_moveit_config ur5_pick_place_cpp_r after the MoveIt demo launch. | vendor_doc | README.md:99-107 |
| moveit_controllers.yaml declares arm_controller type FollowJointTrajectory with action_ns follow_joint_trajectory and gripper_controller type GripperCommand with action_ns gripper_cmd. | upstream_code | src/ur5_moveit_config/config/moveit_controllers.yaml:5-27 |
| ros2_controllers.yaml declares arm_controller as joint_trajectory_controller/JointTrajectoryController and gripper_controller as position_controllers/GripperActionController. | upstream_code | src/ur5_moveit_config/config/ros2_controllers.yaml:1-15 |
| yolov8obb_object_detection/package.xml still has the text 'TODO: License declaration'. | upstream_code | src/yolov8obb_object_detection/package.xml:8 |
| yolov8obb_object_detection/setup.py declares license='Apache License 2.0'. | upstream_code | src/yolov8obb_object_detection/setup.py:27 |
| ur5_moveit_config/package.xml declares BSD. | upstream_code | src/ur5_moveit_config/package.xml:11 |
| robot_description/package.xml declares BSD. | upstream_code | src/robot_description/package.xml:12 |

## Scope

The selected device is the UR5 pick-and-place actuator executed by
`src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp`. Its executable is built
and installed by `src/ur5_moveit_config/CMakeLists.txt:16-22` and `:32-37` and
run by `README.md:99-107`. The node consumes the absolute `/target_point`
topic (`std_msgs/msg/Float64MultiArray`) and publishes the absolute
`/pick_place_status` topic (`std_msgs/msg/String`). The package exposes one
effectful publication action for the four-number target and one explicit
fresh-sample status observation. The main resource state reads the status topic
and the last four-number target observed on the shared `/target_point` command
topic; the target value is the last command, not a measured pose, and neither
field is a stopped-state measurement. This is not a world step or a robot-state
snapshot.

The target producer is `pick_place_chatbot_ui/target_publisher.py`: it
subscribes to `/target_class_cmd` and `/Yolov8_Inference`, computes a pixel
centre from the detection and publishes `[x, y, yaw, box]` to `/target_point`.
The driver accepts the resolved four-number target; it does not claim the
natural-language label or the camera calibration. NOT COVERED:
`/Yolov8_Inference`, `/rgb`, `/inference_result`, `/inference_result_cv2`,
`/target_class_cmd`, the MoveIt `move_group` and controller actions, the
gripper, Isaac Sim physics, collision checking and the physical UR5.

Model review (2026-11-05): `/target_point` is a command topic that only clients
publish (the target publisher once per requested target), so in a real graph
the main resource's `target_point` subscription normally gets no sample: each
target publication waits about 2 s for the receipt's snapshot and
`mhs.resource.read` fails `NOT_READY` (the fake's `silent_target` case shows
it). After any failed step the node publishes `ERROR` once and shuts down
(`:480-497`), so `/pick_place_status` is silent afterwards. The chatbot path
publishes box `-1.0` when no box is named (`target_publisher.py:109-117`),
which leaves `box_x` and `box_y` uninitialised before the place move
(`:319-330`); this package refuses any box other than 1 or 2, but another
client on `/target_point` is not bound by that. The clone also builds and installs
`ur5_pick_place_cpp_s` (`CMakeLists.txt:24-37`), a variant on the same `/target_point` that publishes
no `/pick_place_status` and moves 0.233 m in z; if an operator runs it, status reads fail `NOT_READY`.

## Limits

The target is one heterogeneous four-element array. The field and every
element carry the dimensionless UCUM unit `1`; the field description states
the per-element units (x and y in metres, yaw in radians, box 1 or 2) rather
than pretending one physical unit fits all four.

* `target_point[0]` is `Limit.operator_required`: the clone states no
  reachable workspace bound for x. `moveToWorldXY` passes the value to
  `computeCartesianPath` without a range check
  (`src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:58-89`). The operator
  must supply the reviewed table envelope in `site-limits.json`; the example
  file contains clearly marked test values only.
* `target_point[1]` is `Limit.operator_required` for the same reason (y).
* `target_point[2]` is `Limit.operator_required`: `rotateGripperYaw` passes
  the value to `computeCartesianPath` without a yaw bound
  (`src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:92-134`).
* `target_point[3]` is `allowed=[1, 2]`, sourced to
  `src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:319-330`. The
  pick-and-place sequence only handles box 1 and box 2; any other value leaves
  `box_x` and `box_y` uninitialized before `moveToWorldXY` at line 330. The
  target publisher's `-1.0` "box not set" sentinel
  (`pick_place_chatbot_ui/target_publisher.py:115`) is therefore not admitted
  by this driver.

The node's `pos_tol` 0.001 and `yaw_tol` 0.01 (`:367-372`) are change-detection
defaults, not limits on the commanded target. The hardcoded 0.255 m
descend/lift distances and box coordinates are application constants, not
device bounds, and are not declared as Limits. The fixed values are recorded
as facts only.

## Safety

The declaration is `mode = "simulated"`, `device_kind = "robot.arm"` and
`risk = "R2"` because a robot arm is at least R2 in
`MHS/spec/04-safety.md`, above the card's R0 floor. The clone exposes no
acknowledged stop service or action for this control surface. The C++ node's
only ROS interfaces are the status and gripper publishers, the target
subscription and the status timer (`:383-405`); the only cancel call is
`executor.cancel()` after the main loop exits (`:495-497`), which stops the
executor, not a trajectory or a pending motion.

The sequence is open loop. It uses blocking `move_group.execute(...)` calls and
`rclcpp::sleep_for` between steps and never checks an execute result
(`:79-83`, `:123-127`, `:157-161`, `:213-217`, `:35-48`, `:179-184`,
`:267-272`). A target received while the sequence runs only sets
`new_target_available`; the main loop consumes it after the sequence
(`:414-433`, `:466-482`). The status timer reports `IDLE`, `ACTIVE` or `ERROR`
but is not a stopped-state measurement. The package therefore leaves
`safety_bindings` empty, declares no safe-state action and claims no safe
state. The stock e-stop latches in software and reports
`MHS.SAFETY.SAFE_STATE_UNREACHED`; that is the package blocker, not a
simulated stop. No physical emergency stop exists in this simulation
repository and no hardware run is claimed.

`driver.lock.json` keeps `reviewed_by: null`; this is a model-authored,
unreviewed package. The package also cannot be represented by the existing
acknowledged controller actions: the `FollowJointTrajectory` and
`GripperCommand` action names are composed by the MoveIt controller manager
from `moveit_controllers.yaml:5-27`, not declared as complete endpoints and
types by the clone, and the C++ node does not expose their cancellation to its
`/target_point` client.

## License

The repository has no top-level LICENSE file at the pinned commit. The
package metadata is mixed: `src/yolov8obb_object_detection/package.xml:8`
still says `TODO: License declaration`, `setup.py:27` says
`Apache License 2.0`, while `src/ur5_moveit_config/package.xml:11` and
`src/robot_description/package.xml:12` say BSD. The card records
`license_spdx: NOASSERTION` and `license_class: unknown`; this package does not
invent a different license.

## Tags

`ros`, `ros2`, `moveit`, `ur5`, `pick-and-place`, `isaac-sim`, `sparc`
