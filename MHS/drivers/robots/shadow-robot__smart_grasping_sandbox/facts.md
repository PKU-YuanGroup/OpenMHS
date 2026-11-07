# Facts and tags for gh.shadow-robot/smart_grasping_sandbox

Every fact cites the pinned clone at commit `6f8de0600126bcbd38c38c1fcc8b97c6a868ad8d`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| SmartGrasper subscribes to /joint_states as sensor_msgs/JointState with queue_size=1. | upstream_code | smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:44-45 |
| SmartGrasper waits for /gazebo/get_model_state and proxies it with gazebo_msgs/GetModelState. | upstream_code | smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:47-50 |
| get_object_pose returns the pose field obtained from /gazebo/get_model_state for the current model in the world frame. | upstream_code | smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:115-120 |
| SmartGrasper waits for /gazebo/reset_world and proxies it with std_srvs/Empty. | upstream_code | smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:48-49 |
| SmartGrasper waits for /gazebo/pause_physics and /gazebo/unpause_physics and proxies each with std_srvs/Empty. | upstream_code | smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:52-55 |
| SmartGrasper waits for /gazebo/set_model_configuration and proxies it with gazebo_msgs/SetModelConfiguration. | upstream_code | smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:58-59 |
| SmartGrasper.reset_world stops the hand, arm and joint_state controllers with BEST_EFFORT strictness, pauses physics, calls /gazebo/set_model_configuration, runs __start_ctrl on a zero-delay threading.Timer, sleeps 0.1 s, unpauses physics and calls /gazebo/reset_world, using none of the call results. | upstream_code | smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:92-113 |
| __start_ctrl starts hand_controller, arm_controller and joint_state_controller through /controller_manager/switch_controller. | upstream_code | smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:394-397 |
| The SmartGrasper constructor ends by calling reset_world. | upstream_code | smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:86 |
| open_hand and close_hand set the MoveIt named targets open and close on the hand group, plan, and execute the plan. | upstream_code | smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:209-229 |
| The reset configuration names the 15 joints shoulder_pan_joint, shoulder_lift_joint, elbow_joint, wrist_1_joint, wrist_2_joint, wrist_3_joint, H1_F1J1, H1_F1J2, H1_F1J3, H1_F2J1, H1_F2J2, H1_F2J3, H1_F3J1, H1_F3J2, H1_F3J3 and the positions 1.2, 0.3, -1.5, -0.5, -1.5, 0.0, 0.0, -0.3, 0.0, 0.0, -0.3, 0.0, 0.0, -0.3, 0.0. | upstream_code | smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:97-100 |
| The MoveIt SRDF assigns the arm group six joints (shoulder_pan_joint through wrist_3_joint) and the hand group nine joints (H1_F1J1 through H1_F3J3). | upstream_code | smart_grasp_moveit_config/config/ur10.srdf:12-30 |
| The MoveIt SRDF defines hand group state open with 0.0, -0.3, 0.0 for each finger and hand group state close with 0.0, 0.25, 0.4 for each finger. | upstream_code | smart_grasp_moveit_config/config/ur10.srdf:32-53 |
| The launch file starts Gazebo from fh_desc/launch_simulation.launch, then MoveIt move_group, gazebo2rviz and optionally RViz. | upstream_code | smart_grasping_sandbox/launch/smart_grasping_sandbox.launch:7-20 |
| The MoveIt controller list gazebo_controllers.yaml names arm_controller and hand_controller with follow_joint_trajectory action namespaces; the arm lists six joints and the hand nine. | upstream_code | smart_grasp_moveit_config/config/gazebo_controllers.yaml:1-24 |
| SmartGrasper initializes its current model name to cricket_ball. | upstream_code | smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:33-34 |
| The fh_desc launch sets the robot_description parameter and spawns the model as smart_grasping_sandbox with -param robot_description. | upstream_code | fh_desc/launch/launch_simulation.launch:22-27 |
| The Docker base image is osrf/ros:indigo-desktop-full, a ROS 1 Indigo environment. | upstream_code | docker/base/Dockerfile:1 |
| The helper uses Python 2 print statements (print fraction) at lines 370 and 390. | upstream_code | smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:370-390 |
| The helper's header states 'Copyright (C) 2018 Shadow Robot Company Ltd - All Rights Reserved. Proprietary and Confidential.' | upstream_code | smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:1-2 |
| The repository LICENSE file is the GNU General Public License, version 3. | upstream_code | LICENSE:1-2 |
| The smart_grasping_sandbox package.xml declares the licence GPLv3. | upstream_code | smart_grasping_sandbox/package.xml:9 |
| The six UR10 arm joints declare PositionJointInterface transmissions. | upstream_code | fh_desc/model.urdf:230-283 |
| The model loads libgazebo_ros_control with gazebo_ros_control/DefaultRobotHWSim. | upstream_code | fh_desc/model.urdf:329-333 |
| The hand joint H1_F1J1 declares an EffortJointInterface transmission. | upstream_code | fh_desc/model.urdf:531-539 |
| hand_controller is an effort_controllers/JointTrajectoryController over the nine hand joints. | upstream_code | fh_desc/config/hand_H_gazebo_trajectory.yaml:21-22 |
| launch_simulation.launch defaults gui to true and paused to false. | upstream_code | fh_desc/launch/launch_simulation.launch:2-5 |
| launch_simulation.launch loads ur_gazebo's arm_controller_ur10.yaml, spawns arm_controller and spawns hand_controller. | upstream_code | fh_desc/launch/launch_simulation.launch:43-50 |
| The world declares ODE physics with gravity -9.81 and max_contacts 5. | upstream_code | smart_grasping_sandbox/world/smart_grasping.world:6-12 |

## Scope

The package is a configuration-only `RosDriver` for the ROS 1 Indigo wire graph of the simulator.
It serves `/gazebo/pause_physics`, `/gazebo/unpause_physics`, `/gazebo/reset_world`, `/joint_states`,
`/gazebo/get_model_state` and fixed `/gazebo/set_model_configuration` requests. The fixed home
request uses the 15 joint positions that `SmartGrasper.reset_world` itself writes
(`smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py:97-105`); the hand open/close
requests use the SRDF `open` and `close` group states
(`smart_grasp_moveit_config/config/ur10.srdf:32-53`). Model review (2026-11-05): the helper sets that
configuration only between stopping its controllers and pausing physics and restarting both
(`smart_grasper.py:92-113`), and it opens and closes the hand by MoveIt planning
(`smart_grasper.py:209-229`). This package sends the configuration request alone while the arm
(PositionJointInterface) and hand (effort JointTrajectoryController) controllers keep running, so
they can drive the teleported joints back toward their held setpoints; `applied` reports only
Gazebo's success flag.

Licence: the repository's `LICENSE` is GPL-3.0 and `package.xml` says GPLv3, but the helper this
package cites (`smart_grasper.py:1-2`), `nodes/grasp_quality.py` and `jupyter_notebook_config.py`
carry a "Proprietary and Confidential ... All Rights Reserved" header. The package copies no code
from them (service names, joint names and the reset configuration are cited, not copied as code).

Arbitrary Cartesian arm motion, MoveIt planning/execution, `pick`, `move_tip`, object spawn/delete,
planning-scene collision changes, TF and camera topics are **NOT COVERED**. The static rosbridge
mapping grammar cannot express the nested `moveit_msgs/MoveGroupAction` constraints or the
multi-step helper routines, and the upstream Python 2 helper cannot be imported by this Python 3
package. Those interfaces need a dedicated Python 2-side bridge or a direct driver with a
deployment-validated native factory.

`/gazebo/pause_physics` is the simulator stop. It is an input-free safe-state action and the native
e-stop binding. A paused Gazebo physics engine does not cancel a MoveIt plan, a queued ROS action
goal or an external ROS client; the service acknowledgement is not sensed quiescence and this
package makes no physical emergency-stop claim. Any client can resume physics: the Gazebo GUI that
the launch starts by default, and `SmartGrasper()` itself, whose constructor calls `reset_world`,
which unpauses (`smart_grasper.py:86, 111`); the controllers then continue their goals.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS contract fake (no physics)`,
level F0, determinism `none`, `timestep_ms: 0` (event-driven state transitions with no physics
step), `realtime_factor: 0` (not paced), reset `none`, and no snapshot/restore. The fake's
joint-state and object-pose payloads are placeholders. It runs no Gazebo, ODE, ros_control,
MoveIt, TF, camera, controller or contact simulation; a live deployment must supply those.

## Safety

The device is a simulated robot arm and is declared R2 because it exposes arm and hand
configuration commands. `/gazebo/pause_physics` is an input-free `safe_state=True` action and is
also the acknowledged service bound as the simulator stop; the runtime latches in software before
calling it. After an e-stop the unpause, home and hand commands are refused until `mhs.safety.reset`
clears the latch and the operator calls unpause. The fake has no physical stop and makes no
hardware-safety claim. `driver.lock.json` keeps `reviewed_by: null`; the hardware backend of a
model-written ROS package additionally requires a human hardware review.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `moveit`, `ur10`, `shadow-hand`, `grasping`
