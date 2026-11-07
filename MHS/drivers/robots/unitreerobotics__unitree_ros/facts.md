# Facts and tags for gh.unitreerobotics/unitree_ros

Every fact cites its source at commit `5994d4faef0a9cadd3287f8de0199a67eeb2a259`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone:LINE`). The same facts are declared in
`facts = [Fact(text, source=..., ref=...)]` in `driver.py`; the reference file is generated from the driver.

The selected device is the A1 Gazebo joint-controller interface of this Catkin workspace. The README states that
the workspace is a Gazebo simulation for low-level joint control, not high-level walking, and that physical robots
use the separate `unitree_ros_to_real` project. The twelve `UnitreeJointController` instances subscribe to the
relative `command` topic (`MotorCmd`) and publish the relative `state` topic (`MotorState`). The aggregate
`LowState` is published by `unitree_servo`.

| fact | source | ref |
|---|---|---|
| The README limits this package to Gazebo simulation of low-level torque, position and angular velocity control and says Gazebo cannot do high-level walking; physical robots use the separate `unitree_ros_to_real` project. | `vendor_doc` | `README.md:2-3` |
| `normal.launch` spawns the twelve A1 joint controllers under the `/a1_gazebo` namespace. | `upstream_code` | `unitree_gazebo/launch/normal.launch:36-45` |
| `servo.cpp` subscribes to the twelve `/<robot>_gazebo/<joint>_controller/state` `MotorState` topics and to `/trunk_imu` and the four `/visual/*_foot_contact/the_force` topics. | `upstream_code` | `unitree_controller/src/servo.cpp:32-48` |
| `servo.cpp` creates the twelve `/<robot>_gazebo/<joint>_controller/command` `MotorCmd` publishers with queue size 1. | `upstream_code` | `unitree_controller/src/servo.cpp:224-235` |
| `UnitreeJointController` subscribes to the relative `command` topic and publishes the relative `state` topic with a realtime publisher. | `upstream_code` | `unitree_legged_control/src/joint_controller.cpp:88-95` |
| The controller's update loop reads `command.readFromRT()` on every cycle, so the last `MotorCmd` continues to be applied until another command replaces it. | `upstream_code` | `unitree_legged_control/src/joint_controller.cpp:136-161` |
| `BRAKE` mode sets zero position stiffness, zero velocity, damping 20 and zero torque; it is a damping command, not an acknowledged stop of the controller or the Gazebo world. | `upstream_code` | `unitree_legged_control/src/joint_controller.cpp:156-162` |
| `UnitreeJointController::stopping()` has an empty body; the controller lifecycle reports no stop action. | `upstream_code` | `unitree_legged_control/src/joint_controller.cpp:205-206` |
| The `MotorCmd` and `MotorState` message types are included from the `unitree_legged_msgs` package by the joint-controller header. | `upstream_code` | `unitree_legged_control/include/joint_controller.h:21-22` |
| The A1 URDF states revolute position, velocity and effort limits for the twelve leg joints. | `upstream_code` | `robots/a1_description/urdf/a1.urdf:369-895` |
| The aggregate `/<robot>_gazebo/lowState/state` `LowState` publisher is created in the servo main loop. | `upstream_code` | `unitree_controller/src/servo.cpp:223` |

## Limits

The A1 URDF `<limit>` lines state the per-joint limits used by the twelve command actions:

| joint | position (rad) | velocity (rad/s) | effort (N.m) | ref |
|---|---|---|---|---|
| FR/FL/RR/RL hip | -0.802851455917 to 0.802851455917 | -21 to 21 | -33.5 to 33.5 | `robots/a1_description/urdf/a1.urdf:369,521,673,825` |
| FR/FL/RR/RL thigh | -1.0471975512 to 4.18879020479 | -21 to 21 | -33.5 to 33.5 | `robots/a1_description/urdf/a1.urdf:411,563,715,867` |
| FR/FL/RR/RL calf | -2.69653369433 to -0.916297857297 | -21 to 21 | -33.5 to 33.5 | `robots/a1_description/urdf/a1.urdf:439,591,743,895` |

The position and damping gains (`kp`, `kd`) are `Limit.operator_required`: no pinned text states a device gain
bound. `body.cpp:18-37` calls its gains reference values that need debugging, and the `robot_control.yaml` PID block
is controller configuration, not a device limit. Every command carrying those fields is refused with
`MHS.SAFETY.LIMITS_UNSET` until an operator supplies `site-limits.json`.

## Stop-path finding

This package is blocked. There is no acknowledged stop service or action in the pinned clone. The only native
stop-like command is the `BRAKE` `MotorCmd` on each of the same twelve command topics; a rosbridge publication is
transmission-only and RosDriver's safe-state binding accepts only a fixed acknowledged service or action call. The
controller's `stopping()` method is empty, and the last `MotorCmd` remains in the realtime buffer, so the runtime
latch cannot stop the simulated physics. The package does not claim a stop it cannot deliver. See `RESULT.json`.

Tags: `ros`, `ros1`, `gazebo`, `unitree`, `a1`, `joint-control`, `low-state`, `simulated`.
