# P5-GZ-PAUSE for gh.ad-sdl/sdl-simulation

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 as the external unit `ext-p5-gz-pause--ad-sdl__sdl-simulation` (run id `ext-p5-gz-pause--ad-sdl__sdl-simulation-20261105`). This is a repair of the package authored by deepseek-v4.1-flash:1017 (run ros-wave-c-144, 2026-11-05). `authored_by` is unchanged. `reviewed_by` stays null. No hardware, Gazebo world, ROS graph or human review is involved: the gate evidence is `contract_checked` on the fake only.

Please confirm this widening: `needed_by` of the already-fetched clones `ros-simulation__gazebo_ros_pkgs@2.8.7` (line `melodic-devel`) and `gazebosim__gazebo-classic@gazebo9_9.19.0` (line `gazebo9`) gains `gh.ad-sdl/sdl-simulation` only. The 2026-11-05 companion-clone authorisation names the 12 version-mismatch packages, and sdl-simulation is not among them. No network fetch. The real `work/companions/LOCK.json` was not written; the edited copy is `DEV/companions-root/LOCK.json`.

## What changed

The package was blocked `HELPER_MISSING` (G6 and G8, SAFE-028) because the clone advertises no stop service. The repair uses the same two Melodic lock companions as `gh.erdalpekel/panda_simulation`. The e-stop is `/gazebo/pause_physics` (`std_srvs/Empty`). It is confirmed only when `/gazebo/get_physics_properties` reports `pause` true. No unpause and no re-enable are offered (SAFE-042). Risk stays R2. The card `risk_floor` stays R0. `publish_review` stays required. Licence stays NOASSERTION. Rank stays 87. `generated_at` was not updated.

Files: `MHS/drivers/labs/ad-sdl__sdl-simulation/` (`driver.py`, `fake.py`, `test_driver.py`, `driver.lock.json`, `facts.md`, `reference.json`, `REFERENCE.md`, `task.json`, `RESULT.json`), `MHS/registry/overrides/companion-sources-lock.json` (one new first entry), and `MHS/registry/tasks/labs/ad-sdl__sdl-simulation.json`. `site-limits.example.json` is unchanged. The SDK is unchanged. Copies taken before the edit are under `DEV/originals/`.

## Stop and read-back

`gazebo_ros` 2.8.7, commit `0667c5e52e8afa1f478955d8a2569b473a5acdf1`:

- `gazebo_ros/scripts/gzserver:20-24` adds `libgazebo_ros_api_plugin` unless the arguments already name it.
- `gazebo_ros/launch/empty_world.launch:46` names the server node `gazebo`. The API plugin's node handle is the private namespace `~` (`gazebo_ros/src/gazebo_ros_api_plugin.cpp:147`), so the services are `/gazebo/pause_physics` and `/gazebo/get_physics_properties`.
- `pause_physics` is advertised at `gazebo_ros_api_plugin.cpp:462-468`. `pausePhysics` calls `world_->SetPaused(true)` and returns true (`:1662-1666`). `unpausePhysics` calls `SetPaused(false)` and returns true (`:1668-1672`). This package does not bind unpause.
- `get_physics_properties` is advertised at `:364-370`. `getPhysicsProperties` sets `res.pause = world_->IsPaused()` at `:1426`, before the ODE check. A non-ODE engine sets `success` false and returns false (`:1433-1465`). `gazebo_msgs/srv/GetPhysicsProperties.srv:4` says `pause` is true if the physics engine is paused.
- `lab_ar.world:67` sets physics type `ode`. `empty_world.launch:15` defaults `physics` to `ode`.

Gazebo 9.19.0, commit `e4400ae7e04e4859eec392ac67b813402703bab0`, `gazebo/physics/World.cc`:

- `World::Step` (`:691-710`) advances simulation time and calls `Update` only when the world is not paused, `stepInc > 0` or a reset is due. Otherwise it adds the step to `pauseTime`.
- `ProcessMessages` (`:718`) sits outside that branch and outside the wall-time test that ends at `:711`, so a step still processes messages while paused.
- `SetPaused` (`:1428-1436`) returns when the flag already equals the argument and otherwise stores it under `worldUpdateMutex`. `IsPaused` (`:1422-1425`) returns the stored flag.
- `OnControl` (`:1462-1477`) calls `OnStep` for `step`, and for `multi_step` pauses the world and sets `stepInc`. A GUI step or a `WorldControl` `multi_step` can advance a paused world. `empty_world.launch:8` defaults `gui` to true. This is the paused flag, not a measured standstill. MHS does not watch the flag after the e-stop.

The driver bindings are `driver.py:59-83` and `safety_bindings` at `:658`. `safe_state` is one sentence at `:466-472` (under the 500-character check).

## What this package does not claim

The Sonnet verifier's limits are kept:

- The clone's only `<plugin` filename is `libgazebo_ros_openni_kinect.so` (`sdl_robot_description/urdf/camera.urdf.xacro:47`). `gazebo_controller.yaml:1-2` names `gazebo_ros_control` as a `pid_gains` key. UR and MiR descriptions are external. This package does not claim that `gazebo_ros_control` or the actionlib status timers stop.
- `/move_group/status` and `/move_base/status` stay explicit reads (`x-cap.ad-sdl.arm_status.v1`, `x-cap.ad-sdl.nav_status.v1`). They are not the device resource. The fake still answers them while its paused flag is set (`fake.py` starts at `paused = False` so a stop sets the flag; status replies do not depend on that flag). Moving them off the resource is so a reset does not wait on them. It is not a claim that they go silent.
- `table_1_smach.py:8-10` (`Idle.execute`) logs `Executing state BAR` and returns `outcome2`. A search of the clone's `*smach*` files found no `Publisher` and no command topic. This package does not claim the smach nodes publish the arm, gripper or navigation topics. The earlier model-review sentence that says they do is not what those lines show. That paragraph is left as written.

## SAFE-042

No unpause, no re-enable and no reset binding.

- Arm: `sdl_moveit_node.py:114` calls `set_pose_target`, `:117` blocks in `self.group.go(wait=True)`, and `:119` calls `self.group.stop()` only after `go` returns. That stop is not a ROS service or action. An in-flight MoveIt goal cannot be cleared by this package. The fact cites `:114-122` and names `go(wait=True)`, matching line 117.
- Navigation: `can_demo_no_camera.py:18` publishes a `PoseStamped` to `move_base_simple/goal`. `sdl_nav_moveit_combined.launch:36-38` includes external `mir_navigation` `move_base.xml`. The clone declares no cancel.
- Grippers: `gripper_control.yaml:1-6` names `position_controllers/JointPositionController` for `finger_joint` and `right_outer_knuckle_joint`. `can_demo_no_camera.py:20-21` publishes `Float64`. `ros_controllers.launch:6-11` loads the yaml and spawns both controllers. The controller source is not in this clone, so this package does not claim it stores the last command.

`mhs.safety.reset` releases the latch only. The fake paused flag stays true, and a following command is recorded while the world stays paused. Recovery stays paused. The pending MoveIt goal, navigation goal and gripper publications cannot be shown to have been discarded (`sdl_moveit_node.py:114-119` clears its target only after `group.go(wait=True)` returns), so the affected simulation stack is restarted before any manual resume. `README.md:57-62` tells the operator to press play at startup; that sentence is not the e-stop recovery.

The launch this package serves is the default. `sdl_nav_moveit_combined.launch` defaults `tf_prefix` to empty and includes `lab_world.launch`. `lab_world.launch:12` defaults `namespace` to `tf_prefix`. The empty-namespace branch (`:44-55`) passes `paused=true` (`:53`). The namespaced branch (`:14-23`) passes `paused=false` (`:23`) and is not served. In both branches the Gazebo include is outside the `ns` group (that group starts at `:31` in the namespaced branch), so the service names stay `/gazebo/...`. The fake starts unpaused; the real no-namespace launch starts paused, so a read-back can already be true at startup. `README.md:6` says `ROS Melodic`.

Publication receipts report the values sent (`driver.py` `_SentReceipt`), because a constant `{published, confirmed}` receipt would fail TCAP-003 once the status topics leave the device resource.

## Lock and cards

`driver.lock.json` `companions` lists the two pins (`package_id`, `commit`, `lock` only). The override entry is the first object in `MHS/registry/overrides/companion-sources-lock.json`. Its `version_evidence` tokens were checked against the clone and the two companions (package `README.md:6` `ROS Melodic`, `sdl_gazebo/package.xml:51` `catkin`, `lab_world.launch:50` the `empty_world.launch` include; companion `gazebo_ros/package.xml:4` `2.8.7`, `:22` `catkin`, `gazebo_dev/package.xml:22` `libgazebo9-dev`, `docs/RELEASE.md:19` `ROS Melodic: Gazebo 9`; Gazebo `CMakeLists.txt:16` `GAZEBO_MAJOR_VERSION 9`, `Changelog.md:3` `Gazebo 9.19.0`). The `companion:gazebo_ros_pkgs` side on the Gazebo entry supplies the profile token `melodic`.

`DEV/companions-root/` has one symlink per clone directory of the real `work/companions`, plus `README.txt` and the edited `LOCK.json`. Each clone symlink is mode `0555` (`chmod` with `follow_symlinks=False`). The real clone directories were not chmod'd. `writable_entries` lstats the clone root, so a symlink left at the default `0755` is reported as `G1.COMPANION_WRITABLE` on `.` even when the target is `0555`. `test_driver.py:51-52` forwards `MHS_DRIVER_GATE_COMPANIONS` and does not hardcode this path. The gate and `collect.py` were pointed at `DEV/companions-root`.

Both task cards (`task.json` and `MHS/registry/tasks/labs/ad-sdl__sdl-simulation.json`) carry the resolved companion fields in `attach_companions` order, `package_status` `pass` and `blocked_on` `[]`. The registry repo record and the site HTML were not edited. A registry rebuild should refresh them. `python3 MHS/registry/build_registry.py` was not run.

## Taken from the stopped attempts

From the stopped Claude tree `development/p5-gz-pause/project`, the version-evidence list shape for `gh.ad-sdl/sdl-simulation` in `companion-sources-lock.json` was used after each token above was checked. That tree's driver files matched snapshot-6 and were not copied. Its `gazebo_classic` reason, which said the pause gates every model and controller update, was not used. From `development/ext-p5-gz-pause.fast-stopped/project`, the six-package `needed_by` widening was not used. Neither stopped tree had a change record for this unit.

## Gate

`python3 -m mhs.driver check MHS/drivers/labs/ad-sdl__sdl-simulation --backend fake --json --no-report --companions-root <DEV>/companions-root` passed G1-G9. `mhs.driver.check.stable_digest` is `sha256:4f6421828b0c0861675d6a79f3cf82a7ad354fa35f5636eba16213048a9fe478`. A one-token fact edit (`go(True)` to `go(wait=True)`, matching `sdl_moveit_node.py:117`) was made after an earlier pass of the same digest; the re-run still passed and the digest did not move, because the report's pass/fail set did not change. `python3 -m mhs.driver show_refs` is not a command of this CLI (`check`, `reference`, `new`, `export`, `catalog` only). `RESULT.json` records the stable digest, keeps the six `catalogue_requests`, keeps the earlier model-review paragraph, and appends one review headed `MODEL REVIEW (grok-4.7, a model and not a human, 2026-11-05; reviewed_by stays null): `. The author's text before that earlier paragraph was shortened at a word boundary, ending ` [...]`, so the notes stay within 8,000 characters. The earlier review paragraph was not edited.

The first `DEV/companions-root/LOCK.json` was taken before `work/companions/LOCK.json` gained `micro-manager__mmCoreAndDevices@ce92a47dc1b0`. That copy was replaced from the current real file (sha256 `6f671bd50cb246b00ff868c751f4ece90256b0dd2b669080906380c68bc7d152`, which does not name `gh.ad-sdl/sdl-simulation`). The only difference after the replacement is the two `needed_by` additions above. The real file was not written. `README.txt` in `DEV/companions-root/` is a copy of the current real README, including its 2026-11-06 Micro-Manager paragraph; this unit did not author that paragraph. The missing clone symlink was added and set to mode `0555` without changing the target.

## Checks

`python3 -m mhs.driver show_refs` exits 2: this CLI accepts `check`, `reference`, `new`, `export` and `catalog`. The companion lines were read from the clones. `python3 MHS/handoff/tools/prepare.py --sync gh.ad-sdl/sdl-simulation` refreshed 0 task cards. Before round 1, `python3 MHS/registry/validate.py --no-corpus` failed on the two record comparisons below. `python3 MHS/handoff/tools/collect.py --strict` on this package, with `--companions-root` pointed at `DEV/companions-root`, passed with 0 warnings both before that lock refresh and again after it. The stable digest stayed `sha256:4f6421828b0c0861675d6a79f3cf82a7ad354fa35f5636eba16213048a9fe478`. No `check-report.json` was left in the package.

## Round 1 review

Codex, high: `safe_state` told the operator to press play while the MoveIt goal, the navigation goal and the gripper publications could still be pending. `driver.py:468-474` now says the world stays paused, no unpause is offered, and the simulation stack is restarted before any manual resume, because those pending requests cannot be shown to have been discarded. The string is 491 characters and one sentence. The same order is in the fidelity gap at `driver.py:506-511` and in `facts.md`. `README.md:57-62` remains the startup instruction (`driver.py:514-515`), not the e-stop recovery. `reference.json` and `REFERENCE.md` were regenerated. The 13 package cases passed (0.705s). The fake gate passed G1-G9 again. The stable digest did not move, because the report's pass/fail set did not change. `collect.py --strict` passed with 0 warnings after this edit.

Codex, medium: `validate.py` `check_card` (`MHS/registry/validate.py:585-587`) compares `card.blocked_on` with `record.blocked_on`, and `check_overlays` (`:751-753`) compares `record.evidence.state` with the package overlay. The record was updated to the passing overlay without `build_registry.py`, so ranks were not recomputed. `blocked_on` is `[]`. `evidence.state` is `contract_checked`, `read_by` is `runtime`, and `provenance_refs` names this package's `RESULT.json` (`build_registry.py:1654-1659`). `adapter.state` is `runnable` (`overlays.py:111-115`). `ring` is 1 (`build_registry.py:1660-1661`). `HELPER_MISSING` was removed from `integration.blockers`; the licence, entry-symbol and install blockers remain (`build_registry.py:1429-1442`). `next_action` is the pass sentence from `next_action_for` (`:1452-1457`). `x-vendor.overlay` is `status` `pass`, `evidence_state` `contract_checked`, and the stable digest, with `blocked_on` omitted (`overlays.py:133-154`). `rank` stays 87. `updated_at` and `x-vendor.mhs_registry.generated_at` stay `2026-10-20T00:00:00Z`. `python3 MHS/registry/build_index.py` rewrote `index.json`, `index.jsonl` and `records.csv`. `python3 MHS/registry/validate.py --no-corpus` then exited 0 with 0 errors. Description, tags and `device_plan` were not recomputed. Separate site HTML files were not edited. The copy of the record taken before this edit is `DEV/originals/registry-repos/labs/ad-sdl__sdl-simulation.json`.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/labs/ad-sdl__sdl-simulation/RESULT.json`
- `MHS/drivers/labs/ad-sdl__sdl-simulation/driver.lock.json`
- `MHS/drivers/labs/ad-sdl__sdl-simulation/driver.py`
- `MHS/drivers/labs/ad-sdl__sdl-simulation/facts.md`
- `MHS/drivers/labs/ad-sdl__sdl-simulation/fake.py`
- `MHS/drivers/labs/ad-sdl__sdl-simulation/test_driver.py`
- `MHS/registry/overrides/companion-sources-lock.json (entry merged)`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
