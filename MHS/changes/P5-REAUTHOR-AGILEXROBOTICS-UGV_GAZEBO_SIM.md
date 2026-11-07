OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# P5 re-author: agilexrobotics/ugv_gazebo_sim

Unit of item p5-reauthor. Author: grok-4.7 (a model, not a human), run `ext-p5-reauthor--agilexrobotics__ugv_gazebo_sim-20261105`, 2026-11-05. `reviewed_by` stays null. Nothing was taken from the stopped Claude tree or the stopped Grok tree; both had no file newer than their base manifests.

## What changed

The previous package served the `hunter/steer_drive_controller` rostest fixture and was blocked `HELPER_MISSING` because that fixture is not the repository's simulated robot. This package replaces it. The old directory is in `DEV/moved-aside/agilexrobotics__ugv_gazebo_sim/`. The new driver is `ScoutV2EmptyWorld` in `MHS/drivers/robots/agilexrobotics__ugv_gazebo_sim/`.

Served launch: `scout/scout_gazebo_sim/launch/scout_empty_world.launch` only (Scout V2). It includes gazebo_ros `empty_world.launch` (`scout_empty_world.launch:7-13`) and `spawn_scout_v2.launch` (`:16`).

## Verifier corrections

The triage said Scout V2 uses `libgazebo_ros_skid_steer_drive.so` and publishes odometry. Both are wrong on this pin (`27633a956c845903ee630538afeb17fe70afdd84`).

- `scout/scout_description/urdf/scout_v2.gazebo:43-63` names `libgazebo_ros_skid_steer_drive.so` inside an XML comment. Lines 65-73 name `libgazebo_ros_planar_move.so` inside an XML comment. The live plugin is `gazebo_ros_control` / `libgazebo_ros_control.so` at lines 26-30. This package does not bind odometry.
- `ScoutSkidSteer::TwistCmdCallback` (`scout/scout_gazebo_sim/src/scout_skid_steer.cpp:37-57`) reads `linear.x` and `angular.z`, sets `k` to 1.4, and publishes four `std_msgs/Float64` values. It stores no Twist. `SCOUT_WHEELBASE` 0.498 and `SCOUT_WHEEL_RADIUS` 0.16459 (`include/scout_gazebo/scout_skid_steer.hpp:33-34`) are kinematics, not velocity limits.

The command is `x-cap.agilexrobotics.cmd_vel.v1`: publish `geometry_msgs/Twist` on `/cmd_vel`. The constructor writes `robot_name_ + "/cmd_vel"` (`scout_skid_steer.cpp:22`). The launch default `robot_namespace` is `/` (`scout_empty_world.launch:3`), so the concatenated C++ string is `//cmd_vel`. The binding is the literal suffix `/cmd_vel`. This package does not cite a ROS name-cleaning function. If the private parameter is missing, the C++ default is `scout_default` (`scout_skid_steer_controller.cpp:18-20`); that relative topic is not bound. The shipped spawn sets the parameter (`spawn_scout_v2.launch:37-38`).

`linear_x` and `angular_z` use `Limit.operator_required`. The yaml PID gains and the wheel constants are not used as velocity limits. The receipt reports the values sent.

## Stop, and why there is no unpause

Profile `ros1-melodic-gazebo9`, the same pins panda_simulation uses:

- `ros-simulation__gazebo_ros_pkgs@2.8.7` at `0667c5e52e8afa1f478955d8a2569b473a5acdf1`
- `gazebosim__gazebo-classic@gazebo9_9.19.0` at `e4400ae7e04e4859eec392ac67b813402703bab0`

The e-stop calls `/gazebo/pause_physics` and confirms it only when `/gazebo/get_physics_properties` reports `pause` true (`gazebo_ros_api_plugin.cpp:462-468`, `:1662-1666`, `:364-370`, `:1426`). A non-ODE engine makes that read-back return false (`:1433-1465`). `empty_world.launch` defaults physics to ode.

No unpause and no re-enable. `scout_v2_control.yaml:11-40` names four `velocity_controllers/JointVelocityController` entries. Their implementation is `ros-controllers`, which this clone does not contain (`scout/README.md:36` installs `ros-melodic-ros-controllers`). A zero Twist does publish four zero Float64 values from the in-repo callback. That does not show that a held controller setpoint was replaced. SAFE-042 therefore refuses an unpause that would resume a command this package cannot clear. `mhs.safety.reset` releases the latch and leaves the world paused. The operator recovers outside MHS. `spawn_scout_v2.launch:25` passes `-unpause` to `spawn_model`; this package does not spawn.

The read-back is the paused flag at that call, not a measured standstill and not a promise that `World::Update` stays idle. `World::Step` still calls `Update` while paused when `stepInc` is positive or `needsReset` is true (`World.cc:691-697`). `SetPaused` stores the flag and does not clear pending steps (`:1428-1436`). `World::Step` still calls `ProcessMessages` while paused (`World.cc:691-718`). A `WorldControl` `multi_step` runs steps while paused (`:1462-1477`). The Gazebo GUI or any other client can unpause. MHS does not monitor the flag after the read-back. `scout_skid_steer_controller` calls `ros::spin` (`scout_skid_steer_controller.cpp:27`), so it can receive a Twist while Gazebo is paused. Whether the external controllers apply those Float64 publications is not in this clone.

## model_states

`/gazebo/model_states` is a fact, not a command. The clone never names that topic. `ros_check.py` allows a companion citation on the e-stop, its read-back, and a declared re-enable only (`ROS_COMPANION_SCOPE`). The API plugin advertises the relative name `model_states` (`gazebo_ros_api_plugin.cpp:382-388`) on the private node handle (`:147`). `onModelStatesConnect` hooks `publishModelStates` to `WorldUpdateBegin` on the first subscriber (`:554-558`). That callback runs from `World::Update`, which still runs while paused when `stepInc` is positive or `needsReset` is true (`World.cc:691-697`). `publishModelStates` fills name, pose and twist from `GetName`, `WorldPose`, `WorldLinearVel` and `WorldAngularVel` (`:2203-2244`). `ModelStates.msg:1-4` comments call pose and twist desired; the publisher uses the world pose and velocity. `joint_states` is not bound: the yaml names `joint_state_controller/JointStateController` and `publish_rate` 50 (`scout_v2_control.yaml:2-4`) and names no topic. The device resource reads no topic.

## Not covered

Product directories `autokit`, `bunker`, `hunter`, `hunter_se`, `limo`, `limo_s2`, `ranger`, `ranger_air`, `ranger_delta`, `ranger_mini`, `tracer` and `tracer_mini`, and every scout launch other than `scout_empty_world.launch`. Hunter 2.0 was not selected. Its odometry controller is also outside this clone, so an unpause still could not be shown to clear a stored command. `scout_empty_world.launch:6` writes `world_name` as `$(find scout_gazebo_sim)worlds/weston_robot_empty.world` with no slash after the package find. This package does not launch Gazebo and does not patch that line.

The card licence stays `NOASSERTION`. `scout_gazebo_sim/package.xml:10` says BSD. There is no root LICENSE file. `publish_review` stays `required`. The card's `mock_strategy.upstream_tests` is `hunter/steer_drive_controller/test`. `taskcards.mock_block` (`taskcards.py:862-863`) stores the first detected test directory, and a registry rebuild writes that same path. The directory exists in the clone and is a Hunter steerbot fixture. This package does not serve it and does not run it.

## Registry and lock

`MHS/registry/overrides/companion-sources-lock.json` gains one entry, `gh.agilexrobotics/ugv_gazebo_sim`, with the two Melodic companions. The task card and the package `task.json` are the same bytes, `package_status` `pass`, `blocked_on` `[]`. The repos record drops `HELPER_MISSING`, sets evidence `contract_checked`, adapter `runnable`, ring 1, and overlay status `pass`. `updated_at` is unchanged. `build_index.py` rewrote `index.json`, `index.jsonl` and `records.csv`.

`needed_by` for this package was added only in `DEV/companions-root/LOCK.json`, on `ros-simulation__gazebo_ros_pkgs@2.8.7` and `gazebosim__gazebo-classic@gazebo9_9.19.0`. The real `work/companions/LOCK.json` was not written. The two cited clone directories in `companions-root` are copies, not symlinks: gate G1 `lstat`s the clone root, and a symlink's mode has write bits, which `COMPANION_WRITABLE` rejects. The copies keep the source modes (`0555` on the root). The other clone directories are symlinks. The real clones were not chmod'd and were not edited.

## Evidence

`python3 -m mhs.driver check MHS/drivers/robots/agilexrobotics__ugv_gazebo_sim --backend fake` with `--companions-root` pointing at `DEV/companions-root` passes G1-G9. G1 warns `CLONE_NOTE` for the pre-existing case-only mesh pair `scout/pro/meshes/box_Link.STL` and `box_link.STL`. The stable digest is `sha256:1e21f0d61bc2ba5e788074144a585224df847cc0b76b731bbbc43083a5338b38`. It equals the digest on the previous blocked RESULT because `stable_digest` hashes the check report without the clock, and this report has the same identity, the same passing gates and the same `CLONE_NOTE` text. It does not hash `driver.py`. `collect.py --strict` on this package exits 0. `validate.py --no-corpus` exits 0.

## Round 1

Codex (gpt-6.1-sol) found that `safe_state` claimed a paused world runs no `World::Update` and updates no controller. `World.cc:691-697` calls `Update` while paused when `stepInc > 0` or `needsReset` is true, and `SetPaused` at `:1428-1436` does not clear `stepInc`. The safe-state sentence now reports only the pause flag observed at read-back, and it says that a pending step, a manual step, a reset or a callback can still run `Update`, that another client can resume the world, and that MHS does not monitor the flag afterwards. The same overclaim was removed from the module text, one fidelity gap, the gazebo-classic companion reason on this card only, and `RESULT.json` notes. `reference.json` and `REFERENCE.md` were regenerated. The re-run gate printed the same stable digest. Other packages' companion reasons were left as they were.

## Round 2

Codex (gpt-6.1-sol) found that setting `mock_strategy.upstream_tests` to null is not what `taskcards.mock_block` writes. That function keeps the first detected test directory (`taskcards.py:862-863`), which for this clone is `hunter/steer_drive_controller/test`, the same value as snapshot-6. A later registry rebuild would put that path back on the registry card only, and G1 would then report `CARD_EDITED`. Both task files now carry that path again. The notes say the fixture is outside the Scout V2 scope and that this driver does not run it. No SDK change was made.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/agilexrobotics__ugv_gazebo_sim/RESULT.json`
- `MHS/drivers/robots/agilexrobotics__ugv_gazebo_sim/driver.lock.json`
- `MHS/drivers/robots/agilexrobotics__ugv_gazebo_sim/driver.py`
- `MHS/drivers/robots/agilexrobotics__ugv_gazebo_sim/facts.md`
- `MHS/drivers/robots/agilexrobotics__ugv_gazebo_sim/fake.py`
- `MHS/drivers/robots/agilexrobotics__ugv_gazebo_sim/site-limits.example.json`
- `MHS/drivers/robots/agilexrobotics__ugv_gazebo_sim/test_driver.py`
- `MHS/registry/overrides/companion-sources-lock.json (entry merged)`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
