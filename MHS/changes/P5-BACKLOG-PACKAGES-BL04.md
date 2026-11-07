OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# P5-BACKLOG-PACKAGES-BL04 — item 12 on passing packages outside the ROS family

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 as unit BL-04 extended of p5-backlog-packages. Run id `ext-p5-backlog-packages--bl04-20261105`. `reviewed_by` stays null on every package. No hardware, ROS graph, Gazebo, PX4 or simulator run is claimed. Every gate result below is `contract_checked` on the package fake.

This unit applies REVIEW.md item 12 and `MHS/spec/04-safety.md` §2.1 to passing packages whose family is not `ros`. The served class publishes a motion command on a ROS topic, and no fact cites that only the simulator consumes that topic, so the device keeps the hazard of the physical robot that consumes the same topic (a mobile base or an arm: R2; a vehicle in flight: R2). A world service only the simulator serves stays R0. Mentioning a topic in a fact, while the served command writes an in-process actuator, stays at the author's risk. `derek-th-wang/quadruped_ctrl` is left to integrator v4. BL-12, BL-19 and BL-22 are other units and were not edited. The ROS-family item-12 audit in `BATCH/drafts/item12-audit-result.json` was not re-opened.

## Scan

Passing `RESULT.json` files outside family `ros` were scanned for a served publish of `cmd_vel`, `Twist`, `JointTrajectory`, a MAVROS or PX4 setpoint, or a motor-speed command. A second pass looked for `Publisher` and `create_publisher` facts in the remaining passing robot packages. MuJoCo `ctrl` and Gymnasium action arrays are in-process actuators and were not raised. Eight packages met the item-12 predicate. The keeps below are the ones a name in the brief, or a motion-topic mention, could be mistaken for a raise.

## Raised, R0 to R2

Each package keeps its `authored_by`. One `MODEL REVIEW (grok-4.7, ...)` paragraph was appended to `RESULT.json` notes. `reference.json` and `REFERENCE.md` were regenerated with `python3 -m mhs.driver reference`. `python3 -m mhs.driver check <dir> --backend fake` passed, and the stable digest matched the digest already stored in `RESULT.json` `gate.digest`. G9 ran the package tests.

| Package | Hazard | Evidence the served command publishes, and that a physical consumer is not excluded |
|---|---|---|
| `robots/anurye__gym-turtlebot` | mobile base | `Turtlebot4Env.step` publishes `TwistStamped` on `/cmd_vel` (`ros_gz.py:135-139`, `160-165`; `turtlebot4.py:331-346`). `docs/Tutorial.md:34` says a differential-drive robot can be used directly when its topics are `scan`, `odom` and `cmd_vel`. |
| `robots/jackvice__roboterrain` | mobile base | `RoverEnv` publishes `Twist` on `cmd_vel_topic` (default `/cmd_vel`) after a check that only waits for a `LaserScan` (`rover_env.py:257-265`, `808-816`). `step` sets `linear.x` and `angular.z` (`rover_env.py:393-406`). `README.md:14` models the Rover Zero, Clearpath Husky and Leo Rover. |
| `robots/erlerobot__gym-gazebo` | mobile base | `step` publishes `Twist` on `/mobile_base/commands/velocity` (`gazebo_circuit_turtlebot_lidar.py:21`, `60-74`). `GazeboCircuitTurtlebotLidar_v0.launch:3` defaults the base to kobuki and names create and roomba; lines 19-23 include that base launch. |
| `robots/saqib736__ros2-reinforcement-learning` | mobile base | `GazeboEnv.step` calls `_set_action`, which publishes `Twist` on `/cmd_vel` (`gazebo_env.py:44-47`, `95-103`; `gazebo_connections.py:36-39`, `47-51`). `td_robot.sdf:727-750` points `libgazebo_ros_diff_drive` at `command_topic` `cmd_vel` and does not say that only that plugin consumes it. |
| `robots/benykoz__gym_px4` | vehicle in flight | Publishers on `/mavros/setpoint_raw/attitude` and the other MAVROS setpoint topics (`gymPX4_env.py:105-109`); `step` publishes `AttitudeTarget.thrust` (`gymPX4_env.py:239-248`); `offb_arm` sets OFFBOARD and arms (`gymPX4_env.py:294-311`). `README.md:30-31` points `fcu_url` at SITL; the environment does not. |
| `robots/patmce__uav-drl-oa-gymnasium-ros-gazebo` | vehicle in flight | `forward` and `left_or_right` call `PX4Vehicle.set_pose2d` (`step1/new_drone_gym_gazebo_env.py:233-249`). `README.md:79-83` says `troiwill/mavros-px4-vehicle` communicates with the PX4 autopilot through MAVROS. The topic string lives in that external package and is not invented here. |
| `robots/acutronicrobotics__gym-gazebo2` | arm | `MARAEnv` publishes `JointTrajectory` on `/mara_controller/command` (`mara.py:99`, `149`). `MARARealEnv` uses the same topic (`mara_real.py:72-74`, `222-228`). `launchReal` starts the real cognition node (`ut_launch.py:158-168`). This package still serves `MARAEnv` only and declares no hardware backend. |
| `robots/ammar-n-abbas__sim2real-ur-gym-gazebo` | arm | `Arm` publishes `JointTrajectory` on `<ns>/scaled_pos_joint_traj_controller/command` (`arm.py:115-127`; `constants.py:4`). `ur5_controllers.yaml:5-25` defines that controller on the six UR joints. `get_robot_params` leaves `param_use_gazebo` False for every driver value (`ur5_task_space.py:74-81`). |

`safe_state` was rewritten only where it denied a physical effect or described the latch as if the command could not reach a physical consumer. Each new `safe_state` stays within the 500-character limit in `mhs/driver/model.py`. The latch still does not publish a zero command and does not stop the robot subscribed to the topic. Three package tests that asserted `safety.risk_class == "R0"` now expect `R2` (`anurye__gym-turtlebot/test_driver.py`, `erlerobot__gym-gazebo/test_driver.py`, `acutronicrobotics__gym-gazebo2/test_driver.py`). G9 passed on all eight.

## Kept

These passing packages were read and left unchanged. No `MODEL REVIEW` paragraph was added.

- `robots/blackcoffeerobotics__bcr_bot` stays R0. `driver.py:16-19` says the ROS layer (`/bcr_bot/cmd_vel`, twist stamper, diff-drive controller) is not covered. The served command is the MuJoCo scene. `driver.py:61-63` says no physical mobile-base command is exposed.
- `robots/enph353__gym-gazebo-sim` stays at its inherited R0. `step` publishes `std_msgs/Float64MultiArray` on `/cart_velocity_controller/commands` (`cartpole_env.py:41-50`, cited from the package fact). `cartpole_manager.yaml:9-17` is `forward_command_controller/ForwardCommandController` on joint `slider_to_cart` with interface `velocity`. The clone names no physical product driver for that topic.
- `robots/lionlai1989__stalkerdronerl` stays at its inherited R0. The environment publishes motor speeds on `/X3/ros/motor_speed` (`train_sac.py:189-201`). `LionQuadcopter` subscribes to that ROS topic (`lionquadcopter.cpp:281-284`, callback `322-329`) and republishes `gz.msgs.Actuators` on `/X3/gazebo/command/motor_speed` (`lionquadcopter.cpp:163-165`, `200-209`). `lion_quadcopter.sdf:17-28` sets the motor plugin `commandSubTopic` to `gazebo/command/motor_speed`. The consumer is the Gazebo motor model. The clone has no MAVROS or PX4 subscriber on this topic.
- `robots/geonhee-lee__ur5_ros_gym` stays R0. The served constructor publishes `std_msgs/Int8` on `/action_move` (`unscrewing_env.py:21-32`). `planning_script.py:116-128` subscribes and `group.go()` sends `follow_joint_trajectory`. The package gap at `driver.py:194-198` says that, as shipped, only a remap would move a real arm. The package's own publication is not the topic `ur_driver` consumes (`universal_robot/ur_driver/src/ur_driver/driver.py:649-651`).
- `robots/zhefan-xu__isaac-go2-ros2` stays at its inherited R0. The ROS bridge subscribes to `/unitree_go2/cmd_vel` (`README.md:64-80`). The Gym action is a `JointPositionAction` inside Isaac. This package does not publish that motion command.
- `robots/spencerfolk__rotorpy` stays at its inherited R0. `cmd_vel` is an in-process `Box` of shape `(3,)` (`driver.py` fact citing the environment action space), not a ROS topic.
- `robots/unitreerobotics__unitree_mujoco` stays at its author's risk. The served model is the MuJoCo H2 scene. The upstream Python simulator's `rt/lowcmd` fact (`driver.py` fact on the DDS bridge) is a DDS topic, not a ROS topic this driver publishes.
- Already R2, left untouched: `robots/rickstaa__ros-gazebo-gym`, `robots/mobile-robots-group-uc3m__adamsim`, `robots/jjshoots__crazyflyt`. ROS-family keeps from the earlier audit (`fazildgr8`, `goanywherenus`, `rlxai`) were not re-opened. `robots/derek-th-wang__quadruped_ctrl` was not opened.

## Digests

A risk change adds no gate finding (COMPANION-LOCKS.md edit I6). After reference regeneration, each stable digest matched the value already in `RESULT.json`. The first `anurye__gym-turtlebot` check printed a different digest because `python3 -m py_compile` had written `__pycache__` and G1 warned `G1.BYTECODE`. Those bytecode files were moved to `DEV/moved-aside/pyc-bl04/`. The second check, with `PYTHONDONTWRITEBYTECODE=1` and no bytecode in the package, matched `sha256:b7ee74aed3b9c6bef345e6a5d806e2d56715ab56068ac6ac2ef9b6cf2f4a389c`. The other seven checks matched on the first run. Gate-written `check-report.json` files were not in the base manifest; they were moved aside after the gates so the patch does not add timestamped reports.

## Stopped attempts

The fast-stopped Grok tree (`development/ext-p5-backlog-packages.fast-stopped/project`) has no file under `MHS/drivers`, `MHS/changes`, `MHS/sdk`, `MHS/handoff`, `MHS/spec` or `MHS/registry/overrides` whose sha256 differs from its base manifest. Nothing was taken from it.

The stopped Claude tree (`development/p5-backlog-packages/project`) differs in five files. `anurye__gym-turtlebot/driver.py` only replaces `risk = "R0"` with `risk = "R2"`, and `test_driver.py` expects `R2`. It has no item-12 citation, no `facts.md` sentence, no `safe_state` correction, no `MODEL REVIEW` paragraph and no regenerated reference. `drcl-usc__hector_simulation/driver.py` is BL-22 and was not used. Nothing was copied from that tree. The gym-turtlebot test expectation `R2` matches the decision made here and was written again with the rest of the repair.

## What was not run

No full SDK suite, no registry rebuild, no `prepare.py --sync`, no network, no install, no hardware and no simulator. Shared files (SDK, `REVIEW.md`, spec, registry overrides) were not edited. No lock companion was edited.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/acutronicrobotics__gym-gazebo2/RESULT.json`
- `MHS/drivers/robots/acutronicrobotics__gym-gazebo2/driver.py`
- `MHS/drivers/robots/acutronicrobotics__gym-gazebo2/facts.md`
- `MHS/drivers/robots/acutronicrobotics__gym-gazebo2/test_driver.py`
- `MHS/drivers/robots/ammar-n-abbas__sim2real-ur-gym-gazebo/RESULT.json`
- `MHS/drivers/robots/ammar-n-abbas__sim2real-ur-gym-gazebo/driver.py`
- `MHS/drivers/robots/ammar-n-abbas__sim2real-ur-gym-gazebo/facts.md`
- `MHS/drivers/robots/anurye__gym-turtlebot/RESULT.json`
- `MHS/drivers/robots/anurye__gym-turtlebot/driver.py`
- `MHS/drivers/robots/anurye__gym-turtlebot/facts.md`
- `MHS/drivers/robots/anurye__gym-turtlebot/test_driver.py`
- `MHS/drivers/robots/benykoz__gym_px4/RESULT.json`
- `MHS/drivers/robots/benykoz__gym_px4/driver.py`
- `MHS/drivers/robots/benykoz__gym_px4/facts.md`
- `MHS/drivers/robots/erlerobot__gym-gazebo/RESULT.json`
- `MHS/drivers/robots/erlerobot__gym-gazebo/driver.py`
- `MHS/drivers/robots/erlerobot__gym-gazebo/facts.md`
- `MHS/drivers/robots/erlerobot__gym-gazebo/test_driver.py`
- `MHS/drivers/robots/jackvice__roboterrain/RESULT.json`
- `MHS/drivers/robots/jackvice__roboterrain/driver.py`
- `MHS/drivers/robots/jackvice__roboterrain/facts.md`
- `MHS/drivers/robots/patmce__uav-drl-oa-gymnasium-ros-gazebo/RESULT.json`
- `MHS/drivers/robots/patmce__uav-drl-oa-gymnasium-ros-gazebo/driver.py`
- `MHS/drivers/robots/patmce__uav-drl-oa-gymnasium-ros-gazebo/facts.md`
- `MHS/drivers/robots/saqib736__ros2-reinforcement-learning/RESULT.json`
- `MHS/drivers/robots/saqib736__ros2-reinforcement-learning/driver.py`
- `MHS/drivers/robots/saqib736__ros2-reinforcement-learning/facts.md`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
