# P5 backlog packages, BL-22: no unpause on three Gazebo simulations

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 for unit BL-22. `reviewed_by` stays null. This unit repairs three passing packages. It does not re-author them: `authored_by` is unchanged, and no package directory was moved aside.

The packages are `robots/drcl-usc__hector_simulation`, `robots/ipa320__cob_simulation` and `robots/nus-advanced-robotics-centre__me5413_final_project`. Each declared an unpause re-enable (`x-cap.<owner>.resume.v1` bound to `/gazebo/unpause_physics`, `reenable=True`) that would resume stored motion the package cannot clear. BL-22 applies the same rule as the seven p3-companion-2 packages (REVIEW.md item 13, the orchestrator's SAFE-042 condition): offer no unpause, as a re-enable or as an ordinary command, and say how the operator recovers outside MHS. The pause and its read-back stay. The companion facts that describe `unpausePhysics` stay, so the operator's recovery command is still cited. Risk is unchanged: Hector R2, Care-O-bot R0, ME5413 R0.

`safe_state` is at most 500 characters (`MHS/sdk/src/mhs/driver/model.py` rejects a longer value). The line-level account is in each package's fidelity gaps and `facts.md`.

## drcl-usc/hector_simulation

Removed `x-cap.drcl-usc.resume.v1`. The fake no longer serves `/gazebo/unpause_physics` and no longer has `fail_resume`. A MotorCmd published while the world is paused is stored and does not nudge the canned pose.

The joint controllers keep the last `MotorCmd` (`joint_controller.cpp:33-45`) and apply it in `update` (`139-185`). `BRAKE` (`158-164`) sets zero position stiffness, zero velocity, damping 20 and zero torque. `starting()` (`117-129`) writes the current position, zero velocity and zero torque into `lastCmd`. `gazebo_ros_control` connects the controller manager to the world-update hook (`gazebo_ros_control_plugin.cpp:196-199`) and calls `controller_manager_->update` from `Update` (`251`). `World::Step` runs that update only when the world is unpaused or a step was requested (`World.cc:835-854`). `GazeboRosControlPlugin::Reset` (`260-266`) clears timing variables. The constructor zeros `lastCmd` (`joint_controller.cpp:15-18`), and `biped.launch:7` starts the world paused.

When `hector_ctrl` runs, the main loop calls `CheatIO::sendRecv` (`main.cpp:41` builds `ros::Rate(1000)`; `main.cpp:80-83` is the loop) and `sendCmd` publishes all ten `MotorCmd` messages with mode forced to `0x0A` (`CheatIO.cpp:34-36`, `44-58`). The FSM loop (`main.cpp:22-30`) is a different thread. `signal(SIGINT, ShutDown)` is at `main.cpp:78`; `ShutDown` (`16-20`) sets `running` false. `Readme.md:68` tells the operator to terminate with `ctrl+\`, which is SIGQUIT. This record does not treat that key as `ShutDown`.

After `mhs.safety.reset` the world stays paused. The operator stops `hector_ctrl`, relaunches `biped.launch` and presses the simulator start button outside MHS (`Readme.md:61-68`). Restarting the ten controllers while the world stays paused is not the recovery: the manager update runs from the world-update hook.

## ipa320/cob_simulation

Removed `x-cap.ipa320.resume.v1`. The fake no longer serves `/gazebo/unpause_physics`. World edits still apply on a paused world after the latch is released. The e-stop still refuses them while latched.

This package publishes no controller command. `cob_gazebo/launch/robot.launch:12` includes `cob_bringup`, an `exec_depend` at `cob_gazebo/package.xml:18`. `cob_bringup` is not in this clone. `cob_bringup_sim` is a package in this clone; earlier review paragraphs that place it outside the clone are left as written. `component_test.py:78-81` addresses `JointTrajectory` topics `/<component>_controller/command`. The world launches spawn controllers this package does not command: position controllers at `ipa-apartment.xml:13-14`, and velocity controllers at `ipa-kitchen.xml:14` and `automotive-assembly-line.xml:15`. `elevator.py:64-66` publishes `Float64` 0, the close position, after the open position 0.87 (lines 51-55). That close publish moves the door.

After `mhs.safety.reset` the world stays paused. The operator stops those controller nodes outside MHS, then unpauses with the Gazebo GUI (`world.launch:14` defaults `gui` to true) or `rosservice call /gazebo/unpause_physics`.

## nus-advanced-robotics-centre/me5413_final_project

Removed `x-cap.nus-advanced-robotics-centre.resume.v1`. The fake no longer serves `/gazebo/unpause_physics`. Deleting `planar_box` still applies while paused.

`boxOdomCallback` publishes `linear.y` of plus or minus 2.0 on `/box_cmd_vel` (`object_spawner_gz_plugin.cpp:372-387`; the publisher is created at line 40). `gazebo_ros_planar_move` stores that twist (`242-249`) and applies it in `UpdateChild` (`198-208`). `planar_box.urdf.xacro:36-42` sets no `cmdTimeout`. The plugin default `cmd_timeout_` is -1 (`gazebo_ros_planar_move.cpp:117`), so the update leaves the stored velocity in place. `spawn_jackal.launch:23-26` includes `jackal_control`'s `control.launch` and `teleop.launch`. Those packages are not in this clone, so this record names no Jackal command topic. Deleting `planar_box` leaves the Jackal controller running.

After `mhs.safety.reset` the world stays paused. The operator deletes `planar_box` and stops those Jackal nodes outside MHS, then unpauses with the Gazebo GUI (`world.launch:9` sets `gui` true) or `rosservice call /gazebo/unpause_physics`. A respawn or unblock callback that is already running still completes its world edits (`object_spawner_gz_plugin.cpp:309-345`, `347-370`). That caveat is in the fidelity gap and, after the round-1 repair, in `safe_state`.

## Digests

`mhs.driver.check.stable_digest` hashes the check report without its clock (`MHS/sdk/src/mhs/driver/check.py`). On a tree with no `__pycache__`, the three passing reports have the same findings as before this repair, so the digests do not move:

| Package | Status | Digest |
|---|---|---|
| drcl-usc/hector_simulation | pass | `sha256:48e810fcd1a3dee0931ccfe795901d417a374c70770aaad861b9435b1ffc737a` |
| ipa320/cob_simulation | pass | `sha256:0ebe226fd300fb5c791c204a6de64139bdaa4f321683db2f70f18b6317d75c64` |
| nus-advanced-robotics-centre/me5413_final_project | pass | `sha256:6a44e194883ae4db214c3263be078efe135e130e696dddd76945702e5423121f` |

Care-O-bot and ME5413 still warn `G8.SAFE014_NOT_APPLICABLE`. That warning was already in the passing report. Hector's clean report has no warnings. A run that saw `__pycache__` under the packages warned `G1.BYTECODE` and produced different digests. Those directories were created while tests ran and were moved to `DEV/moved-aside/`. They are not part of the packages. `collect.py --strict` on the three directories then passed with the digests above (`3 of 3`, exit 0).

Each `RESULT.json` keeps `status: pass`, drops the resume row from `catalogue_requests`, and appends one MODEL REVIEW paragraph. The author's text before the first MODEL REVIEW paragraph was shortened at a word boundary and ends with ` [...]`. The three earlier review paragraphs are unchanged. `driver.lock.json` is unchanged.

## Tests

Package tests, after the citation corrections, from `DEV/project` with `PYTHONPATH=MHS/sdk/src` and `PYTHONDONTWRITEBYTECODE=1`:

- `python3 -m unittest discover -s MHS/drivers/robots/drcl-usc__hector_simulation -p 'test_*.py'`: 10 tests, OK
- `python3 -m unittest discover -s MHS/drivers/robots/ipa320__cob_simulation -p 'test_*.py'`: 9 tests, OK
- `python3 -m unittest discover -s MHS/drivers/robots/nus-advanced-robotics-centre__me5413_final_project -p 'test_*.py'`: 14 tests, OK

Each suite includes `check_driver`. The new cases assert that no command names an unpause service or topic, that no action has `reenable`, and that `mhs.safety.reset` returns no `reenable`, sets `resumed` false, and leaves the fake world paused.

No SDK file changed, so there is no SDK suite run and no mutant. No registry file changed. No `LOCK.json` `needed_by` edit: these packages use the corpus companions already on their cards.

## Round 1

Codex's high finding was that the shortened `safe_state` strings omitted limitations REVIEW.md item 13 requires them to state: a manual step, another client's or the GUI's resume, and continuing world edits. Each string now states the limitations that apply to that package, keeps the no-unpause policy, and keeps the operator recovery. Each is within the 500-character field limit.

- Hector, `driver.py` `safe_state`, 496 characters: the last MotorCmd stays (`joint_controller.cpp:33-45`) and this package cannot clear it; the Gazebo GUI or another client can unpause or step the world (a step advances it); spawn and delete still apply; after `mhs.safety.reset` the operator stops `hector_ctrl`, relaunches `biped.launch` and presses start (`Readme.md:61-68`).
- Care-O-bot, 497 characters: controllers this package does not command keep their last command (`robot.launch:12`, `ipa-apartment.xml:13-14`); the GUI or another client can unpause or step the world (a step advances it); world edits still act while paused; the operator stops those nodes, then unpauses outside MHS (`world.launch:14`).
- ME5413, 499 characters: the box velocity stays stored and `jackal_control` is outside the clone; the GUI or another client can unpause or step the world (a step advances it); a running respawn or unblock callback still completes its world edits; after `mhs.safety.reset`, delete `planar_box`, stop the Jackal nodes and unpause outside MHS (`world.launch:9`). The `gazebo_ros_planar_move.cpp:242-249` and `spawn_jackal.launch:23-26` citations remain in the fidelity gap and `facts.md`. They were left out of `safe_state` so the callback and step caveats fit.

Grok's low finding: `elevator.py:51-55` publishes the open position 0.87, and `elevator.py:64-66` publishes 0, the close position, after that open (`cob_gazebo_worlds/scripts/elevator.py`). The zero-publish sentences in the Care-O-bot module text, the fidelity gap, `facts.md`, the grok MODEL REVIEW paragraph and this record now cite 64-66 and say that 0 is that close position. The author's text before the first MODEL REVIEW paragraph was shortened again at a word boundary and still ends with ` [...]`. The three earlier review paragraphs are unchanged. Notes length is 7992. No second grok paragraph was added. `reviewed_by` stays null.

`python3 -m mhs.driver reference` regenerated `reference.json` and `REFERENCE.md` for all three packages. Package tests after that regeneration: Hector 10 OK (19.374s), Care-O-bot 9 OK (4.541s), ME5413 14 OK (8.955s). After the final Care-O-bot fidelity-gap wording, `reference` was regenerated again for that package and its tests were 9 OK (4.882s). The last `collect.py --strict` on the three directories passed 3 of 3 with 0 warnings. A stale `gate.digest` would have been reported as `RESULT_DIGEST_STALE`, so the digests in the table above are the digests of that run. No `__pycache__` and no `check-report.json` were left under the packages.

`DEV/originals/` still holds the package copies from before the first BL-22 edit. Round 1 added no new package file, so those copies were not replaced. Their hashes match `PATCH-INDEX.json` `before_sha256`.

## Taken from stopped attempts

The stopped Claude tree at `development/p5-backlog-packages/project` differs from the pre-edit snapshot in `drcl-usc__hector_simulation/driver.py` only. Care-O-bot and ME5413 drivers match the snapshot. That Hector edit was unfinished and unreviewed. This unit took the decision to drop Hector's resume, and the recovery shape of stopping `hector_ctrl`, relaunching `biped.launch` and pressing the GUI start button, after reading the clone. It did not copy that file. It did not use `joint_controller.cpp:110-124` for `starting()`: lines 110-114 are `getGains`, and `starting()` is 117-129. It does not offer "restart the ten controllers" while the world stays paused.

The fast-stopped tree at `development/ext-p5-backlog-packages.fast-stopped/project` matches the pre-edit drivers of all three packages. Nothing was taken from it.

Pre-edit copies of the three package directories are in `DEV/originals/`.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/drcl-usc__hector_simulation/RESULT.json`
- `MHS/drivers/robots/drcl-usc__hector_simulation/driver.py`
- `MHS/drivers/robots/drcl-usc__hector_simulation/facts.md`
- `MHS/drivers/robots/drcl-usc__hector_simulation/fake.py`
- `MHS/drivers/robots/drcl-usc__hector_simulation/test_driver.py`
- `MHS/drivers/robots/ipa320__cob_simulation/RESULT.json`
- `MHS/drivers/robots/ipa320__cob_simulation/driver.py`
- `MHS/drivers/robots/ipa320__cob_simulation/facts.md`
- `MHS/drivers/robots/ipa320__cob_simulation/fake.py`
- `MHS/drivers/robots/ipa320__cob_simulation/test_driver.py`
- `MHS/drivers/robots/nus-advanced-robotics-centre__me5413_final_project/RESULT.json`
- `MHS/drivers/robots/nus-advanced-robotics-centre__me5413_final_project/driver.py`
- `MHS/drivers/robots/nus-advanced-robotics-centre__me5413_final_project/facts.md`
- `MHS/drivers/robots/nus-advanced-robotics-centre__me5413_final_project/fake.py`
- `MHS/drivers/robots/nus-advanced-robotics-centre__me5413_final_project/test_driver.py`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
