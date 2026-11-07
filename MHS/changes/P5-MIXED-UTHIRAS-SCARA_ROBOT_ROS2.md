OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# P5 mixed: uthiras/scara_robot_ros2 E1 stall read-back

Repair of `gh.uthiras/scara_robot_ros2` only. `authored_by` stays `deepseek-v4.1-flash:1017`, run `ros-wave-c-118`, date 2026-11-05. `reviewed_by` stays null. This note is by Grok (grok-4.7, a model and not a human) on 2026-11-05. No hardware, Gazebo, ROS graph or human review was run. The passing evidence is the fake gate, `contract_checked`.

## What changed

The package was blocked on `HELPER_MISSING` because it declared no stop. It now pauses the Gazebo world and confirms that pause with an E1 stall read-back, the same shape as `atharva-05/unitree_ros2_sim`.

- E-stop: `/pause_physics` (`std_srvs/srv/Empty`). Companion `gazebo_ros_init.cpp:267-271` creates the service; `:328-333` is `OnPause`, which calls `world_->SetPaused(true)`.
- Read-back: `/get_model_list` (`gazebo_msgs/srv/GetModelList`), success `success == true`, stall `{path: header.stamp, samples: 2, interval_ms: 250, unchanged: true}`. Companion `gazebo_ros_factory.cpp:139-143` creates the service; `:168` sets `header.stamp` from the world sim time.
- `estop_latency_ms` is 1500 (pause 400 ms, two read-backs of 300 ms, interval 250 ms).
- Fact for Gazebo classic `World.cc:835-854`: while paused, with no step increment and no reset due, `World::Step` does not advance sim time.
- No unpause and no re-enable. `mhs.safety.reset` releases the latch only. The world stays paused.
- The device resource reads no topic. `/joint_states` stays the explicit read `x-cap.uthiras.joint_states.v1`. The effort publication receipt adds `sent_efforts`, the three values handed to rosbridge.
- Risk stays R2 (`robot.arm`). Mode stays simulated.
- Three companions, profile `ros2-humble-gazebo11`: gazebo_ros_pkgs at `ae6e5793a31f5927df89cb58007d2a5eb567baa8` (lock `ros-simulation__gazebo_ros_pkgs@3.9.0`), gazebo_ros2_control at `42d875b482f0b254d9032950a91b2c5cbd7d1c3d` (lock `ros-controls__gazebo_ros2_control@0.4.12`), and corpus gazebo-classic at `b22c6e15e52299865b31093b8feebc9ca19e26e8`.

The fake keeps a paused flag. `get_model_list` advances a placeholder sim time by 1 ms unless that flag is set. `/joint_states` is silent while paused unless `wall_clock_joint_states` is set. That switch still returns a sample, because silence is not guaranteed.

## Verifier caveat

The phase-5 verifier said not to claim that `/joint_states` is silent while the world is paused. `rrbot_world.launch.py:69-75` starts a standalone `controller_manager` executable `ros2_control_node` beside the gazebo_ros2_control plugin. Lines 62-67 are `robot_state_publisher`, not that node. `GazeboSystem::initSim` stores `parent_model_` at `gazebo_system.cpp:144`, and the plugin calls `initSim` at `gazebo_ros2_control_plugin.cpp:337-346`. `GazeboSystem::write` reads `parent_model_->GetWorld()->SimTime()` at `gazebo_system.cpp:823`. Which process publishes `/joint_states` while the world is paused is not settled by those lines. The facts, the fidelity gaps and the fake say so. The stop itself is the pause plus the sim-time stall, and does not depend on `/joint_states` going quiet.

## Why there is no unpause

`traj_follow.py:25-66` publishes an effort on every `joint_states` callback, and line 47 sets `tau3=-9.8` plus a PD term. `control_velocity.py:65-164` does the same: line 124 adds `-9.8` to the joint3 effort and line 164 publishes. gazebo_ros2_control writes joint commands from its world-update callback (`gazebo_ros2_control_plugin.cpp:419-437`, the write at `:433-436`). While paused, with no step pending and no reset due, that callback does not run. A pending step or a reset still calls `Update` (`World.cc:835-841`), and an unpause applies the last command. The controller's stored setpoint is not in a declared companion, so this package does not clear it. A zero effort is not what those nodes hold joint3 with. The operator stops `traj_follow` and `control_velocity`, decides the effort, and unpauses outside MHS.

Two older facts said the constructors create no stop service on ranges that did not show the whole constructor. They now cite `traj_follow.py:13-24` and `control_velocity.py:14-64`, which are the constructors. The `controller_switch.cpp:17-21` fact says only what those lines do: the client targets `/controller_manager/switch_controller`, activates `forward_velocity_controller` and deactivates `forward_position_controller`.

## Distro evidence

The clone has no README line that names Humble. The package-side distro tokens are committed colcon artifacts:

- `install/setup.bash:22` is `COLCON_CURRENT_PREFIX="/opt/ros/humble"`.
- `build/rrbot_description/colcon_command_prefix_build.sh.env:37` is `ROS_DISTRO=humble`.
- The same env file, line 13, contains `gazebo-11` in `GAZEBO_RESOURCE_PATH`.

`rrbot_gazebo/package.xml:19` is `ament_cmake` and `:25` is `gazebo_ros2_control`. `rrbot_world.launch.py:44` names `gazebo.launch.py`. `rrbot.gazebo.xacro:12` loads `libgazebo_ros2_control.so`. Companion tokens are the same lines the accepted E1 cards use (`gazebo_ros/package.xml:5` is `3.9.0`, `gazebo_dev/package.xml:23` is `libgazebo11-dev`, `gazebo_msgs-extras.cmake:4-5` contains `humble`, `gazebo_ros2_control/package.xml:4` is `0.4.12`, that repo's `README.md:22` contains `Humble`, `CMakeLists.txt:20` is `GAZEBO_MAJOR_VERSION 11`, `Changelog.md:3` is `Gazebo 11.15.1`). Gate G1 accepted them. The colcon artifact is recorded for reviewer acceptance. The env file also contains a developer home path; this record cites only the three token lines.

## Lock view

`work/companions/LOCK.json` does not list this package in `needed_by`. This unit does not edit that file. `DEV/companions-root/` has one symlink per clone directory, a copy of `README.txt` with a note about this view, and a copy of `LOCK.json` whose `needed_by` for `ros-simulation__gazebo_ros_pkgs@3.9.0` and `ros-controls__gazebo_ros2_control@0.4.12` also includes `gh.uthiras/scara_robot_ros2` (sorted). Symlink modes are `0555` (`chmod -h a-w`). Gate G1 uses `lstat` on the clone root, and a `0755` symlink is reported as `COMPANION_WRITABLE`. The targets were left at `0555`. The gate and `collect.py` were pointed at this view. `project/work/companions` was not retargeted.

The reviewed override is `MHS/registry/overrides/companion-sources-lock.json`. The registry card and `task.json` carry the resolved companions and `package_status: pass`. `build_registry.py` was not run: it reads the workspace lock and would reject the missing `needed_by`, and it would rewrite the rest of the registry. The repo record's evidence, overlay, ring, blockers and triage were set to what a passing overlay produces, and `build_index.py` rewrote `index.json`, `index.jsonl` and `records.csv`. `validate.py --no-corpus` passed (0 errors).

## What was taken from the stopped attempts

The stopped Claude tree `development/p5-mixed/scratch/scara/` was read as notes and checked against the clone and the companions.

- Taken, after that check: the driver, the fake and the tests, and the override's companion list and version-evidence refs (the tokens were read again on 2026-11-05 and matched).
- Changed after taking them: `*_COMPANION_FACTS` is included in `facts` (the scratch defined that list and did not use it). The standalone `ros2_control_node` fact cites `rrbot_world.launch.py:69-75`, not `:60-75` (lines 60-67 are the yaml path and `robot_state_publisher`). The controller-switch fact no longer says the effort controller is stopped or not stopped. `test_gate` passes `companions_root` when `MHS_DRIVER_GATE_COMPANIONS` is set, because `check_driver` reads that variable only for the gate's own inner run. The test comment no longer says the controller stored the effort.
- Not taken: `scratch/scara/facts.md` (it was the old blocked page). The scratch justification named claude-opus-5-5; this override's justification names this Grok repair instead. The scratch's `companions-view` and its scripts were not copied.

The earlier stopped Grok tree `development/ext-p5-mixed.fast-stopped/project` has the same bytes as snapshot-6 for this package's driver files, the companion-sources lock and the registry card. Nothing was taken from it.

## Gate

`python3 -m mhs.driver check MHS/drivers/robots/uthiras__scara_robot_ros2 --backend fake --companions-root <DEV>/companions-root` passed G1 through G9. Stable digest `sha256:fb99a21e8440d800ca56c9a878bc06cc476ee580e293dc81c00dee0645cea96d`. The blocked digest was `sha256:fdc2188f32dca6b9421fb98725a31e7b730d8f698e0eb5b401376bb9987aec8d`. `collect.py --strict` on this package passed with no warnings. A second gate run, inside collect, produced the same stable digest.

`RESULT.json` notes keep the author's text up to a sentence boundary, then ` [...]`, then the existing Claude review paragraph, then one new MODEL REVIEW paragraph. The notes are 7725 characters.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/uthiras__scara_robot_ros2/RESULT.json`
- `MHS/drivers/robots/uthiras__scara_robot_ros2/driver.lock.json`
- `MHS/drivers/robots/uthiras__scara_robot_ros2/driver.py`
- `MHS/drivers/robots/uthiras__scara_robot_ros2/facts.md`
- `MHS/drivers/robots/uthiras__scara_robot_ros2/fake.py`
- `MHS/drivers/robots/uthiras__scara_robot_ros2/test_driver.py`
- `MHS/registry/overrides/companion-sources-lock.json (entry merged)`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.

Round 2, 2026-11-06, same author line: the safe-state text, the fidelity gap, `facts.md` and the gazebo_classic companion reason now say the confirmation is the two `/get_model_list` samples 250 ms apart, and that `safety_status` returns that cached confirmation (`mhs/bridge/ros.py:2227-2232`) with no later read-back. `World.cc:835-841` still steps a paused world when `stepInc` is pending or a reset is due, `World.cc:1630-1639` can schedule that, and `gazebo_ros2_control_plugin.cpp:433-436` writes joint commands on the update. No unpause remains: reset releases the latch only, and the operator stops `traj_follow` and `control_velocity`, decides the effort, and unpauses outside MHS. Nineteen package tests passed, including an external-resume probe that kept `confirmed` true with no further service call. The stable digest stayed `sha256:fb99a21e8440d800ca56c9a878bc06cc476ee580e293dc81c00dee0645cea96d`. `reviewed_by` stays null. No simulator or hardware run is claimed.
