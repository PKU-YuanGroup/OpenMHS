OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# rodriguesrenato/warehouse_robot_simulation: Gazebo world pause with a paused-flag read-back

`robots/rodriguesrenato__warehouse_robot_simulation` moves from `blocked` (`HELPER_MISSING`) to `pass`. The stop is the already fetched Melodic companion service `/gazebo/pause_physics`, confirmed only when `/gazebo/get_physics_properties` reads `pause` true. The package offers no unpause. Evidence is `contract_checked` on the fake backend. No Gazebo process, ROS graph, hardware run or human review is claimed. `reviewed_by` stays null.

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 as a repair of the package authored by `deepseek-v4.1-flash:1017` (run `ros-wave-c-084`, date 2026-11-05). `authored_by` is unchanged (`driver.lock.json:37-42`). This repair's run id is `ext-p5-gz-pause--rodriguesrenato__warehouse_robot_simulation-20261105`. The package directory was not moved aside.

## Decision

The user's decision of 2026-11-05 (decision 1) allows a stop to cite a locally cloned companion at a pinned commit. Both clones were already fetched under `work/companions` and listed in `LOCK.json`. This unit widens `needed_by` for those existing clones. It fetches nothing.

The triage verifier (`BATCH/drafts/retriage-result.json`, directory `robots/rodriguesrenato__warehouse_robot_simulation`) kept the in-clone block and pointed at the companion pause already accepted for the Melodic Gazebo packages, with the same locks as `erdalpekel/panda_simulation`. The safer path is that pause plus the paused-flag read-back, with no unpause.

## Stop

`driver.py:417` sets `safety_bindings` to `estop` = `/gazebo/pause_physics` (`std_srvs/Empty`, `driver.py:75-86`) and `safe_state` = `/gazebo/get_physics_properties` with `pause` equal to true (`driver.py:88-99`). The stop's `state_ref` is `gazebo_ros_api_plugin.cpp:1662-1666`. The read-back's `state_ref` is line 1426.

Cited companion lines, checked by `show_refs.py` (0 bad citations, 705 lines of output):

- `gazebo_ros_api_plugin.cpp:462-468` advertises `pause_physics` as `std_srvs::Empty` (`:464`). `:364-370` advertises `get_physics_properties` as `gazebo_msgs::GetPhysicsProperties` (`:366`).
- `pausePhysics` calls `world_->SetPaused(true)` and returns true (`:1662-1666`). `unpausePhysics` calls `world_->SetPaused(false)` and returns true (`:1668-1672`). This package does not call the unpause.
- The read-back assigns `res.pause = world_->IsPaused()` (`:1426`). That value is the world's paused flag.
- `getPhysicsProperties` sets success true only for the ODE engine and returns false otherwise (`:1433-1465`). `worlds/warehouse.world:67` sets the physics type to `ode`. `empty_world.launch:15` also defaults `physics` to `ode`. A non-ODE engine leaves the e-stop unconfirmed and the latch held.
- Gazebo 9.19.0 `World::IsPaused` returns the stored flag (`World.cc:1422-1425`). `World::SetPaused` stores it under `worldUpdateMutex` (`:1428-1436`). `World::Step` calls `Update` when the world is not paused, when `stepInc` is greater than zero, or when a reset is due (`:691-702`). While paused and `stepInc` is greater than zero, it calls `Update` and then decrements `stepInc` (`:701-702`). `ProcessMessages` still runs (`:718`). `OnStep` sets `stepInc` to 1 (`:1364-1366`). `OnControl` with `has_step` calls `OnStep` (`:1467-1468`), and with `has_multi_step` calls `SetPaused(true)` and sets `stepInc` (`:1470-1476`).

`safe_state` (`driver.py:312-318`) is one sentence of 428 characters. It says the stopped state is the paused flag, that no unpause is offered, and that a pending `move_base` goal and the last diff-drive `cmd_vel` resume on unpause and on a single-step or multi-step while `pause` stays true, including a pending `stepInc`, and during an outside-MHS unpause followed by CTRL+C. The GUI can unpause or step, and MHS does not watch the flag after the e-stop. The read-back stays true during that step, so `pause` true does not prove a standstill.

## SAFE-042

There is no unpause binding and no `reenable`. `mhs.safety.reset` releases the latch and leaves the world paused (`test_driver.py:134-143`). The fake answers `/gazebo/unpause_physics` with result false and does not clear `paused` (`fake.py:101-104`).

`Robot::Move` sends a `MoveBaseGoal` and calls `waitForResult()` with no timeout (`src/Robot.cpp:102-132`; the goal send and the wait are `:119-120`). `gazebo_ros_diff_drive.cpp:325-329` stores `linear.x` in `x_` and `angular.z` in `rot_`. `UpdateChild` applies those values from the world update (`:240-270`, `:314-319`). `QueueThread` uses `ros::WallDuration` (`:332-338`), so a `cmd_vel` can be stored while the world is paused. A zero Twist does not cancel the `move_base` goal, because `move_base` publishes `cmd_vel` again. This package commands neither the goal nor that Twist, and it cannot clear them. An unpause would resume stored motion, so the package does not offer one.

`main` calls `ros::init` with `ros::init_options::NoSigintHandler` (`src/WarehouseSimulation.cpp:223`; the comment is at `:221-222`) and then `signal(SIGINT, SigintHandler)` (`:274-275`). There is no roscpp SIGINT handler on this node for the custom handler to replace. The handler only sets `isShutdown` (`:35-42`). The loop is `while (ros::ok() && !isShutdown)` with `ros::spinOnce()` and `ros::Rate(10).sleep()` (`:278-282`). `launch/world.launch:9-14` sets `use_sim_time` true (`:10`) and `gui` true, and it does not pass `paused`. `publishSimTime` is connected to the world update (`gazebo_ros_api_plugin.cpp:224-227`). While the world is paused, `/clock` does not advance, so the loop does not observe `isShutdown` and does not parse orders until the world steps. That stall is an inference from those lines. It was not executed. Recovery outside MHS is to unpause and then send CTRL+C. Stored motion resumes during that unpause. Shutdown after the loop deletes spawned storages and dispatches and the products in the robots' cargo bins (`src/WarehouseSimulation.cpp:283-310`, `src/ModelController.cpp:103`). That path is not an MHS binding.

`empty_world.launch` defaults `paused` to false (`:5`; line 4 is the comment that shows the example `paused:=true`) and `gui` to true (`:8`), and it starts `gzclient` when `gui` is true (`:51-54`). Any client can unpause or step. MHS re-reads the flag only when the e-stop's read-back runs.

## Receipt and risk

The order receipt adds `sent_order`, the string handed to rosbridge (`driver.py:130-148` and the action output at `:411`). Two different order strings therefore differ in the receipt even though the device resource reads no topic. The publication stays transmission-only: `confirmed` is false, and the node offers no queue, parse, motion or stop acknowledgement (`src/OrderController.cpp:30-79`).

`risk` stays `R2` (`driver.py:161`). REVIEW.md item 12: the order starts an autonomous mobile-base task. The pause service on its own would be R0. The order sets the floor. No `Limit` is declared. The clone states no maximum length or quantity for the free-form order string (`facts.md:96-104`). G8 warns `SAFE014_NOT_APPLICABLE` and awards CL2 because there is no limit to probe. Every other CL3 test passed. This record does not claim CL3.

The earlier review's corrections stay: shutdown deletes only the products in the robots' cargo bins, and the queue condition is `GetProductList().bucket_count() > 0`, which is not an emptiness test (`src/Order.h:20`). This package uses `gazebo_ros_diff_drive`, not `gazebo_ros_control`.

## Profile

Profile `ros1-melodic-gazebo9`. The token `melodic` is on the package (`README.md:16`, "ROS Melodic") and on the companion (`docs/RELEASE.md:19`, "ROS Melodic: Gazebo 9"). `package.xml:11` is catkin and `:14` depends on `gazebo_ros`. `launch/world.launch:9` includes `$(find gazebo_ros)/launch/empty_world.launch`.

`README.md:11` states Ubuntu 18.04.5 LTS. `README.md:17` states Gazebo 9.17.0. The companion pin is Gazebo 9.19.0 (`Changelog.md:3`, `CMakeLists.txt:16` `GAZEBO_MAJOR_VERSION 9`), the same major. `README.md:40` says to adjust the apt commands to the ROS version, and the example commands at `:43-49` name ros-noetic packages. Line 41 is blank. Those lines are examples, not the stated environment. The fact cites `README.md:40-49` (`driver.py:186-188`). The paused-default fact cites `empty_world.launch:5` (`driver.py:237-238`).

Companions, both already fetched:

- `gh.ros-simulation/gazebo_ros_pkgs` at `0667c5e52e8afa1f478955d8a2569b473a5acdf1`, lock `ros-simulation__gazebo_ros_pkgs@2.8.7`, `gazebo_ros/package.xml:4` version 2.8.7. `license_spdx` is `NOASSERTION`, with `licence_note` `Apache-2.0 AND BSD (per package.xml; no licence file in the repository)`.
- `gh.gazebosim/gazebo-classic` at `e4400ae7e04e4859eec392ac67b813402703bab0`, lock `gazebosim__gazebo-classic@gazebo9_9.19.0`, `license_spdx` `Apache-2.0`.

`driver.lock.json:10-21` repeats `{package_id, commit, lock}` for those two.

## Registry

`MHS/registry/overrides/companion-sources-lock.json` gains one override, `gh.rodriguesrenato/warehouse_robot_simulation`, after `gh.rigbetellabs/tortoisebot` (`companion-sources-lock.json:1205`). The `package_id` list stays sorted. The justification is 189 characters, the gazebo_ros reason 164, and the gazebo-classic reason 196. `companion-sources.json` was not edited.

The registry card and the package `task.json` are the same 4829 bytes. `package_status` is `pass`, `blocked_on` is `[]`, `wave` is 3 and `rank` stays 57. The companion objects use the resolved card shape. `build_registry.py` was not run. It reads the real `work/companions/LOCK.json`, which does not yet list this package in `needed_by`, and a full rebuild would also rewrite `generated_at`.

The registry record now has `adapter.state` `runnable` (`repos/...json:6`), `blocked_on` `[]`, `ring` 1, `wave` 3, `rank` 57, `evidence.state` `contract_checked`, `evidence.read_by` `runtime`, and `provenance_refs` pointing only at this package's `RESULT.json`. `HELPER_MISSING` was removed from `integration.blockers`. `NO_ENTRY_SYMBOL` stays (`:40`). `next_action` is the maintain-the-passed-package sentence (`:43`). The description's wave token is 3. `x-vendor.overlay` matches the passing overlay, with `gate_digest` equal to the stable digest below and `reviewed` false. `index.json`, `index.jsonl` and `records.csv` were rebuilt with `python3 MHS/registry/build_index.py`. `python3 MHS/registry/validate.py --no-corpus` on the final tree printed `errors: 0` and `RESULT: PASS` (2967 records, aggregates ok, corpus skipped).

The site page `MHS/site/_site/registry/repo/rodriguesrenato__warehouse_robot_simulation.html` was not regenerated.

## Lock widening, not yet applied

`work/companions` is read only. `DEV/companions-root/` holds one symlink per clone directory of the real companions tree, plus edited copies of `LOCK.json` and `README.txt`. `.empty-hooks` is not a clone and is not linked.

The real `LOCK.json` gained `micro-manager__mmCoreAndDevices@ce92a47dc1b0` (`fetched_utc` `2026-11-06T04:18:37Z`, `needed_by` `gh.rplab/wil_pycro_control_app`) after the first copy of this directory was made. The DEV copy was refreshed from that real file. The only semantic difference from the real lock is `needed_by` of `ros-simulation__gazebo_ros_pkgs@2.8.7` and `gazebosim__gazebo-classic@gazebo9_9.19.0`. Each list is `gh.erdalpekel/panda_simulation`, `gh.rodriguesrenato/warehouse_robot_simulation`. The Micro-Manager entry is unchanged. The file was rewritten with `json.dumps` indent 2. `count` is 23. `README.txt` is the current real text plus one paragraph that says this copy is not the reviewed lock.

The gate's writable check `lstat`s the clone path before it skips symlinks (`mhs.driver.upstream.UpstreamTree.writable_entries`, `upstream.py:543-544`). A symlink whose mode has a write bit is `G1.COMPANION_WRITABLE` on `.`. Each symlink was set to mode `0555` with `os.chmod(path, 0o555, follow_symlinks=False)`. The real clone directories were not chmod'd. The gate, `show_refs.py` and `collect.py` were pointed at this directory with `--companions-root`.

`ShippedLockSourcesTests.test_the_shipped_entries_meet_the_shape_and_lock_rules` reads the real `work/companions/LOCK.json` and fails for this package until the orchestrator applies the widening. The failure names both Melodic aliases. The test was not edited. `validate.py --no-corpus` does not check `needed_by`, so it passed.

The card's acceptance command does not include `--companions-root`. Against the real lock it fails `G1.COMPANION_LOCK` until `needed_by` is widened. `test_driver.py:29-32` passes `companions_root` into `check_driver` only when `MHS_DRIVER_GATE_COMPANIONS` is set. `check_driver` does not write `check-report.json` (`mhs.testing.check_driver`, `write_report` false).

## What was taken from the stopped attempts

Nothing. `development/p5-gz-pause/project` and `development/ext-p5-gz-pause.fast-stopped/project` both still have this package's `RESULT.json` at status `blocked` with digest `sha256:08a68796ebf544becc147ba11cd2d4bbbaf9256ca6e2eea1a902ec1ae5b7fca3`. Neither `driver.py` contains `pause_physics` or `safety_bindings`.

## Gate

`RESULT.json` records status `pass`, `blocked_on` `[]`, `failed` `[]` and digest `sha256:c7c74bd36f4265bf420c0306564cfc385e65e90a316225bd7d85535abe3152a1`. The author's text before the first `MODEL REVIEW` paragraph was shortened at a word boundary and ends with ` [...]`. The Claude review paragraph is unchanged. A second paragraph, headed `MODEL REVIEW (grok-4.7, a model and not a human, 2026-11-05; reviewed_by stays null): `, was appended. The notes length is 7841 characters.

`show_refs.py --companions-root ../companions-root` exited 0 and printed `0 bad citation(s)`. That run was before the `fake.py` docstring edit below. The edit does not change a citation. `driver.py` was not edited after it.

`collect.py --strict --companions-root ../companions-root` then passed this package (`1 of 1 package(s) pass the gate; 0 with warnings`), with a G8 note and two `COMPANION_SOURCE` notes (23 gazebo_ros_pkgs fact citations, 7 gazebo_classic fact citations). After that run, one docstring sentence in `fake.py` was corrected: a call of `/gazebo/unpause_physics` is answered with result false and does not clear the flag (`fake.py:8-9`). The handler at `fake.py:101-104` already did that. The module sentence had said the fake does not answer the service.

`python3 -m mhs.driver check MHS/drivers/robots/rodriguesrenato__warehouse_robot_simulation --backend fake --companions-root ../companions-root` after that edit passed G1 through G7 and G9, and G8 warned `SAFE014_NOT_APPLICABLE`. The printed digest is the same `sha256:c7c74bd36f4265bf420c0306564cfc385e65e90a316225bd7d85535abe3152a1`. That check wrote `check-report.json` (`generated_at` `2026-11-06T04:26:12.312Z`, `report_digest` `sha256:53a7d2cd711b90e7c1d65b7a3cdcf5e0bbc4b3ea11b33eb51847bf1f89beb495`, `passed` true, `failed` `[]`). `collect.py --strict` was run again on that tree and printed the same PASS line. `collect.py` uses `--no-report` (`collect.py:83`), so it did not replace `check-report.json`. The stable digest does not include the report clock.

## Round 1 review

Codex and Grok both asked for two citation corrections, and Codex asked for an explicit disclosure that a step runs while `pause` stays true (REVIEW.md item 13: a fact must be what the cited line says, and the stop's `safe_state` must say what the device is left in).

`empty_world.launch:4` is the comment `paused:=true`. The default `false` is line 5, `<arg name="paused" default="false"/>`. The fact now cites `:5` (`driver.py:237-238`, `facts.md`). The fidelity gap cites `:5` as well.

`README.md:41` is blank. Line 40 contains "Make sure to adjust the following commands to you ROS version". Lines 43-49 are the ros-noetic apt examples. The fact now cites `README.md:40-49` (`driver.py:186-188`).

`World::Step` calls `Update` when `!IsPaused() || stepInc > 0 || needsReset` (`World.cc:691-693`) and, while paused with `stepInc > 0`, decrements `stepInc` after that update (`:701-702`). `World::OnStep` sets `stepInc` to 1 (`:1364-1366`). A `WorldControl` with `has_multi_step` calls `SetPaused(true)` and then sets `stepInc` (`:1470-1476`). `has_step` calls `OnStep` (`:1467-1468`). That `Update` applies the stored diff-drive `x_` and `rot_`. `get_physics_properties` still reads `pause` true. `safe_state` (`driver.py:312-318`, 428 characters) now says stored motion resumes on a single-step or multi-step while pause stays true, including a pending `stepInc`. The fidelity gap at `driver.py:348-353` and the safety prose in `facts.md` say the same. Two facts record the lines: `driver.py:293-295` and `driver.py:309-310`.

`python3 -m mhs.driver reference` rewrote `reference.json` and `REFERENCE.md`. The fake gate then passed G1 through G7 and G9, with the same G8 warning, and printed the same digest `sha256:c7c74bd36f4265bf420c0306564cfc385e65e90a316225bd7d85535abe3152a1`. `check.py:3125-3144` hashes the report without its clock, so a run that finds the same gate results keeps the digest. That check wrote `check-report.json` at `generated_at` `2026-11-06T04:45:01.033Z`, `report_digest` `sha256:cea99f498ae5decf25e28cd8454323b729768cf5c2c7ed415f5ad727ed01d2e6`. `show_refs.py` printed 727 lines and `0 bad citation(s)`, including `README.md:40`, `empty_world.launch:5`, `World.cc:691-702` and `World.cc:1364-1366`. The 11 repository tests passed in 7.641s. `collect.py --strict` printed `PASS` and `1 of 1 package(s) pass the gate; 0 with warnings`, with 23 gazebo_ros_pkgs fact citations and 9 gazebo_classic fact citations. The notes length is now 7999 characters. The Claude review paragraph is unchanged. The grok paragraph now cites `:5` and `README.md:40-49` and names the step. `authored_by` and `reviewed_by` are unchanged. `DEV/originals/` still holds the snapshot-6 copies taken before the repair.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/rodriguesrenato__warehouse_robot_simulation/RESULT.json`
- `MHS/drivers/robots/rodriguesrenato__warehouse_robot_simulation/driver.lock.json`
- `MHS/drivers/robots/rodriguesrenato__warehouse_robot_simulation/driver.py`
- `MHS/drivers/robots/rodriguesrenato__warehouse_robot_simulation/facts.md`
- `MHS/drivers/robots/rodriguesrenato__warehouse_robot_simulation/fake.py`
- `MHS/drivers/robots/rodriguesrenato__warehouse_robot_simulation/test_driver.py`
- `MHS/registry/overrides/companion-sources-lock.json (entry merged)`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
