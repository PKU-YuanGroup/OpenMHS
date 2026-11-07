# P5-GZ-TOPIC: will0103/ros2-mobile-manipulator world-pause read-back

Repair of `MHS/drivers/robots/will0103__ros2-mobile-manipulator` only. The e-stop is the gz-sim world pause, confirmed by a fresh `WorldStatistics.paused` read-back (E2), and the two ros_gz bridges the operator must run are declared (E3). No unpause is offered.

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 as the unit `ext-p5-gz-topic--will0103__ros2-mobile-manipulator`. This is a repair. `authored_by` stays `deepseek-v4.1-flash:1017`, run `ros-wave-c-148`, date 2026-11-05. `reviewed_by` stays null.

- **Where:** `development/ext-p5-gz-topic--will0103__ros2-mobile-manipulator/project`, a copy of snapshot-6.
- **From:** `MHS/changes/COMPANION-TOPIC-READBACK.md`, the triage entry and the verifier's safer alternative for `robots/will0103__ros2-mobile-manipulator` in `drafts/retriage-result.json` (offer no unpause re-enable).
- **Status:** not integrated. Codex reviews safety and correctness; a separate Grok session reviews evidence and honesty. No human has signed.
- **What was run:** no hardware, Gazebo, ROS graph, network fetch or human review. The fake gate passed. Evidence is `contract_checked` only.

## What changed

The package was blocked `HELPER_MISSING` (gate digest `sha256:fc9b6c5305d416d499c7a30b265c489751ffce88ced1bf3a427c0b44be7f7bf7`, G6 and G8). It now passes on the fake backend. The gate digest is `sha256:7e5f57c8cb8679587a29f393c1864badd8850d781cc8bc25cac8fc9fa2a95eae`. A round-1 re-run, after the claim corrections below, printed that same digest. Risk stays R2. The primary capability stays `x-cap.will0103.move-robot.v1`.

The stop is `WorldControl` pause true on `/world/empty/control` (`ros_gz_interfaces/srv/ControlWorld`, timeout 400 ms). gz-sim answers true when it queues the request (`SimulationRunner.cc:1375-1377`) and applies it later with `SetPaused` (`:1443`). That reply confirms nothing. Confirmation is the E2 read-back: `WorldStatistics.paused` on `/world/empty/stats` (`PublishStats` copies `currentInfo.paused` at `:534`), after discarding the first sample, two samples at least 40 ms apart, within 600 ms. `estop_latency_ms` is 1500. The statistics publisher is limited to 10 messages per second (`:806-808`).

`project_world.sdf:2` names the only world `empty`. The bringup launch runs that world with `-r` (`project_robot_gazebo.launch.xml:10-12`) and starts `parameter_bridge` from `gazebo_bridge.yaml` (`:19-21`). That file names `/clock`, `/joint_states`, `/tf`, `/cmd_vel`, the camera topics and the two joint commands (`gazebo_bridge.yaml:1-47`). It does not name `/world/empty/control` or `/world/empty/stats`. Those two are `operator_bridges`. The package never starts them. Without them the e-stop fails closed. The launch does not start `move_robot` (`project_robot_gazebo.launch.xml:1-27`).

## No unpause

`safety_bindings` has `estop` and `safe_state` and no `reenable`. `mhs.safety.reset` releases the latch and leaves the world paused.

DiffDrive stores the Twist in `targetVel` while enabled (`DiffDrive.cc:637-644`). Configure sets `enabled` true (`:358`). `PreUpdate` returns while paused (`:451-453`) and `PostUpdate` returns while paused before `UpdateVelocity` (`:501-505`), which reads the stored linear x and angular z (`:614-615`). The stored twist resumes when the world runs. The xacro sets no command topic (`mobile_base_gazebo.xacro:10-20`). DiffDrive subscribes once, to the topic `validTopic` returns from an optional SDF topic and then `/model/<name>/cmd_vel` (`DiffDrive.cc:335-344`). `validTopic` returns the first candidate `AsValidTopic` accepts (`Util.cc:623-640`), so this model subscribes only to `/model/<name>/cmd_vel`. The bridge maps ROS `/cmd_vel` to `/model/my_robot/cmd_vel` (`gazebo_bridge.yaml:19-23`).

The joint position controller stores the commanded position (`JointPositionController.cc:489-492`) and its `PreUpdate` returns while paused (`:395-397`). The arm description loads those controllers (`arm_gazebo.xacro:14-29`). Startup timers publish forearm and hand targets (`move_robot.cpp:33-68`).

The `move_robot` loop times the goal with `this->now()` (`move_robot.cpp:128-131`) and keeps publishing the goal Twist at 10 Hz (`:119-158`). A search of the clone finds no `use_sim_time`. A zero Twist published before unpause is overwritten while that queue is still running. Cancellation still cancels only the running goal (`:141-150`); queued goals remain (`:86-115`).

Operator recovery is outside MHS: zero the `/cmd_vel` stream, stop or let the `move_robot` queue drain, reset the arm targets, then unpause from the GUI or with a ControlWorld request whose pause flag is false. The world file embeds no GUI plugin (plugins at `project_world.sdf:8-14`; a search of the 237-line file finds no `gui` element). gz-sim's `defaultGuiConfigFile` uses `gui.config` unless the caller passes playback or a custom path (`Gui.cc:58-73`). That file's WorldControl plugin sets `play_pause` and `step` (`gui.config:138-140`). A `multi_step` control unpauses the world (`SimulationRunner.cc:1445-1452`). MHS does not watch the flag after the confirmation window. `safety_status` reports the retained confirmation and does not subscribe again or read a fresh statistics sample, so an external unpause is not observed. `sim_time` and the iteration count advance only while not paused (`SimulationRunner.cc:423-429`). `real_time` is assigned from the stopwatch on every update (`:418`), and `SetPaused` stops that stopwatch while the runner is running and paused (`:1282-1284`).

## Receipt

Two MoveRobot goals used to return the same `{success, message}`, so G8 TCAP-003 failed. `make_bridge` wraps the SDK bridge and adds `sent_linear_vel_x`, `sent_angular_vel_z` and `sent_duration` from the goal arguments. Those fields are the transmitted request, not a measurement. The resource still reads no topic.

## Companions and registry

The three companions are the pins already fetched for linorobot2 and VRX, profile `ros2-jazzy-gzsim8`: gz-sim `446a44335a45b704b4d36dabcc5508ee34eeb3d8`, ros_gz `b87d7523400a695a10d47ca7b8cb5fa86d5b8d9d`, gz-transport `35fef7ea10c2e133498e9010bd2e397a0ce0c3bf`. Package-side version evidence is `README.md:7` (`ROS 2 Jazzy`), `README.md:88`, `README.md:103` (`/opt/ros/jazzy`), `package.xml:10`, `:14` and `:16`, and the launch lines cited above.

`MHS/registry/overrides/companion-sources-lock.json` gains one entry, `gh.will0103/ros2-mobile-manipulator`, after the tortoisebot entry. The card and `task.json` carry the resolved companions. `package_status` is `pass` and `blocked_on` is empty. The record's evidence state is `contract_checked`, the adapter state is `runnable`, the ring is 1, and `HELPER_MISSING` is dropped from `integration.blockers`. `LICENSE_UNKNOWN`, `NO_ENTRY_SYMBOL` and `NO_INSTALL_FILE` remain. `publish_review` stays `required` and the licence stays `NOASSERTION` (`package.xml:8` is a TODO). Wave stays 5 and rank stays 90. A full `build_registry.py` was not run. `build_index.py` was run so the aggregates match the record. `validate.py --no-corpus` passed.

The read-only `work/companions/LOCK.json` was not edited. `companions-root/` in this unit (not under `project/`) symlinks each clone directory and holds a copy of `LOCK.json` whose three jazzy `needed_by` lists also name `gh.will0103/ros2-mobile-manipulator`. The gate and `collect.py --strict` were pointed at that directory. Symlink modes were set with `chmod -h a-w` because `lstat` of a symlink is writable and G1 treats that as `COMPANION_WRITABLE`. The clone targets were not modified.

## Notes budget

`RESULT.json` notes are at most 8000 characters. The author's text before the first `MODEL REVIEW` was shortened at a word boundary and ends with ` [...]`. The existing Claude (`claude-opus-5-5`) `MODEL REVIEW` paragraph is unchanged. One Grok paragraph is appended. Its head is `MODEL REVIEW (grok-4.7, a model and not a human, 2026-11-05; reviewed_by stays null): `.

## Stopped attempts

Nothing was taken from either stopped attempt. The Claude tree at `development/p5-gz-topic/project` had not edited this package. Its lock edit added this package to gz-sim and ros_gz only, omitted gz-transport, and also widened other packages' entries. That file was not copied. The fast-stopped tree at `development/ext-p5-gz-topic.fast-stopped/project` had no diffs from its base manifest.

## Round 1

Codex and a separate Grok session both returned `fix_needed`. Three claims were wrong and are corrected. The gate digest did not change.

`safety_status` reports the retained confirmation. `RosBridge.safety_status` (`MHS/sdk/src/mhs/bridge/ros.py:2199-2232`) returns `_safe_state_achieved` when the stamp still matches. It does not subscribe and it does not read `/world/empty/stats`. A package test pauses the world, sets the fake `paused` flag back to false, and calls `client.safety_status`. The fake `sent` list does not grow, `estop.confirmed` stays true, and the nested bridge field `status.safe_state.achieved` stays true.

DiffDrive builds a candidate list (an optional SDF topic, then `/model/<name>/cmd_vel`) and subscribes once to the string `validTopic` returns (`DiffDrive.cc:335-344`). `validTopic` returns the first candidate `AsValidTopic` accepts (`Util.cc:623-640`). `mobile_base_gazebo.xacro:10-20` has no `topic` element, so this model subscribes only to `/model/<name>/cmd_vel`.

`UpdateCurrentInfo` advances `sim_time` and the iteration count only while not paused (`SimulationRunner.cc:423-429`). It assigns `real_time` from the stopwatch on every update (`:418`). `SetPaused` stops that stopwatch while the runner is running and paused (`:1282-1284`).

## Checks

`python3 -m unittest discover -s MHS/drivers/robots/will0103__ros2-mobile-manipulator -p test_driver.py -k MoveRobotCases` ran 10 tests, all ok, including the pause, the four negative switches, a reset that stays paused, and two goals whose receipts differ. The fake gate then passed G1 through G9 with the digest above. A second gate, after `RESULT.json` and the card were set to pass, printed the same digest. `collect.py --strict` on this package exited 0 with no warnings. No SDK file was changed, so there are no mutants.

After the round-1 corrections the same discovery ran 11 tests, all ok, including the retained-confirmation case. The fake gate again passed G1 through G9 and printed `sha256:7e5f57c8cb8679587a29f393c1864badd8850d781cc8bc25cac8fc9fa2a95eae`. `reference.json` and `REFERENCE.md` were regenerated. `collect.py --strict` on this package again exited 0 with 0 warnings. The record's gate digest was already that value, so the index was not rebuilt.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/will0103__ros2-mobile-manipulator/RESULT.json`
- `MHS/drivers/robots/will0103__ros2-mobile-manipulator/driver.lock.json`
- `MHS/drivers/robots/will0103__ros2-mobile-manipulator/driver.py`
- `MHS/drivers/robots/will0103__ros2-mobile-manipulator/facts.md`
- `MHS/drivers/robots/will0103__ros2-mobile-manipulator/fake.py`
- `MHS/drivers/robots/will0103__ros2-mobile-manipulator/test_driver.py`
- `MHS/registry/overrides/companion-sources-lock.json (entry merged)`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
