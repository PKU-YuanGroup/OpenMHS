OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# P5-GZ-TOPIC — justyx404/spot_gazebo_ros2

Repair of `gh.justyx404/spot_gazebo_ros2` only (unit `ext-p5-gz-topic--justyx404__spot_gazebo_ros2-20261105`). The other packages of item p5-gz-topic are other units. `authored_by` stays `deepseek-v4.1-flash:1017`, run `ros-wave-c-071`, 2026-11-04. `reviewed_by` stays null. This is not a re-author, so the package directory was not moved aside.

Round 1 of the same run removed the re-enable. The landed package pauses `simple_tunnel` and offers no unpause. Sections below that name `x-cap.justyx404.resume.v1` describe the withdrawn draft. The Round 1 section is the landed behavior.

## What changed

The package was blocked `HELPER_MISSING` (gate digest `sha256:fe3b0e79e17c747787577fa2e56d5e26e3d25d4ecb233605e42838a08bf80c2d`, G6 `ESTOP_FAILED` and G8 `SAFE-028`). It now passes on the fake backend (digest `sha256:00405e1fd63e857afcb676c589dda513c121f7a89fdd9a8b940c0f3538736961`). Evidence is `contract_checked` only. No hardware run, simulator run or human review is claimed.

The e-stop is a WorldControl request with `pause` true on `/world/simple_tunnel/control` (`ros_gz_interfaces/srv/ControlWorld`). ignition-gazebo 6.18.0 advertises that service (`SimulationRunner.cc:214`), queues it and replies true (`:1174-1176`), and `ProcessWorldControl` calls `SetPaused` (`:1239-1242`). ros_gz 0.244.27 maps the service (`ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:43-52`; README `:78`). The reply does not confirm the pause. Confirmation is the E2 read-back: `WorldStatistics.paused` equals true (`SimulationRunner.cc:430`) on `/world/simple_tunnel/stats` (publisher throttled to 10 Hz, `:649-651`), `fresh.after_request`, `discard_first`, `consecutive` 2, `min_interval_ms` 40, `within_ms` 600. `estop_latency_ms` is 1500, which covers the 400 ms control timeout and the 600 ms read-back bound. Both endpoints are `operator_bridges`. The clone's `spot_bridge.yaml` does not bridge them, so without the operator-run bridges the e-stop fails closed.

The declared re-enable `x-cap.justyx404.resume.v1` (`reenable=True`) publishes a zero Twist on `/cmd_vel` (`linear.x`, `linear.y`, `angular.z`) and sends `pause` false only when that publication reports `published` true. Otherwise it raises `DriverFailed("MHS.DEVICE.NOT_READY")` and does not unpause (SAFE-042). CHAMP stores the Twist in `req_vel_` (`quadruped_controller.cpp:116-121`) and a wall timer keeps applying it (`:49` `loop_rate` 200, `:94-97`). The zero is unacknowledged. `JointTrajectoryController::PreUpdate` returns while paused (`JointTrajectoryController.cc:438-441`) and a new trajectory resets then replaces the points (`:677-688`), so a stored trajectory is not a queue, but a few world steps after unpause can still apply the previous points until the wall timer publishes the replacement.

`/spot/odometry`, `/spot/joint_states` and `/clock` left the device resource. Odometry is silent while paused (`OdometryPublisher.cc:302-304`). The clock topic keeps publishing, unthrottled, with sim time taken from current info and system time from `IGN_SYSTEM_TIME` (`SimulationRunner.cc:444-453`); sim time does not advance while paused (`:345-350`). `JointStatePublisher::PostUpdate` stamps from sim time and has no paused return before that stamp (`JointStatePublisher.cc:140-189`). The fake silences only `/spot/odometry` while paused and keeps answering the other two. The velocity receipt reports `sent_linear_velocity`, `sent_lateral_velocity` and `sent_angular_velocity`. The three velocity limits stay `Limit.operator_required`. `site-limits.example.json` is unchanged. Risk stays R2. `publish_review` stays `not_required`.

## Worlds and the initial pause

Only `simple_tunnel` is bound (`simple_tunnel.sdf:3`; launch default `spot.gazebo.launch.py:14-18`). `edgar_mine.sdf:3` and `electrical_substation.sdf:3` name other worlds, so those endpoints are absent and the e-stop fails closed. The launch's `gz_args` is only the world path (`spot.gazebo.launch.py:40-45`) and passes no `-r`. `cmdgazebo.rb.in:229` defaults `run` to 0 and `:262-263` sets it to 1 for `-r`. `gz.cc:408` calls `server.Run(true, _iterations, _run == 0)`. `Server::Run`'s third argument defaults to true (`Server.hh:150-152`) and is applied with `SetPaused` (`Server.cc:174-179`). A real server therefore starts paused. The simple_tunnel GUI plugin sets `start_paused` false (`simple_tunnel.sdf:101-103`); edgar_mine sets it true (`edgar_mine.sdf:95`); `electrical_substation.sdf` contains no `start_paused` property. That GUI property is not the server flag. The fake starts unpaused so the gate's explicit reads succeed before an e-stop, and so `ignore_pause` cannot look like a stop on a world that was already paused. The declared re-enable is also the normal first unpause.

The README names `spot_navigation` launches (`README.md:105`, `:110`) and `far_planner.launch.py:82` names package `spot_navigation`. The clone's top-level directories are `assets`, `champ`, `champ_base`, `champ_config`, `champ_msgs`, `spot_bringup`, `spot_description` and `spot_gazebo`. Any other publisher of `/cmd_vel` changes `req_vel_`. The WorldControl GUI and a `multi_step` request can unpause or step (`SimulationRunner.cc:1244-1251`).

## Lock companions

Profile `ros2-humble-gzsim6`, the same pins TortoiseBot uses: `gazebosim__gz-sim@ignition-gazebo6_6.18.0` (`b90cd2c41a193102d6951857c2d83e13f59bb64b`) and `gazebosim__ros_gz@0.244.27` (`856e319ee4da713609b3f6e58c74ac8db7662482`). `MHS/registry/overrides/companion-sources-lock.json` gained one entry. The registry task card and the package `task.json` were hand-set to the same document, with `package_status` `pass`, `blocked_on` `[]`, wave 5 and rank 51 left as they were. `build_registry.py` was not run. The registry record `MHS/registry/repos/robots/justyx404__spot_gazebo_ros2.json` was hand-set to the passing overlay: `adapter.state` `runnable`, `blocked_on` `[]`, `ring` 1, `evidence.state` `contract_checked`, `evidence.read_by` `runtime`, provenance `RESULT.json`, `HELPER_MISSING` removed from `integration.blockers`, and `x-vendor.overlay` equal to `overlays.Overlay.to_vendor()` (`build_registry.py` `complete_record`, lines 1647-1661, and `next_action_for` for a pass, lines 1452-1457). `NO_ENTRY_SYMBOL` and `NO_INSTALL_FILE` stay. `python3 MHS/registry/build_index.py` then rewrote `index.json`, `index.jsonl` and `records.csv` (2967 records). `python3 MHS/registry/validate.py --no-corpus` reported errors 0. A validate that reads the real `work/companions/LOCK.json` still rejects the `needed_by` widening until the orchestrator applies it. `driver.lock.json` `companions` repeat `{package_id, commit, lock}` in that order.

`DEV/companions-root/` holds a copy of `LOCK.json` with `gh.justyx404/spot_gazebo_ros2` added to `needed_by` of those two aliases (TortoiseBot kept), a README note, symlinks for the other clone directories, and copy-on-write copies of the two clones this package cites. A symlink root fails `G1.COMPANION_WRITABLE`: `writable_entries` uses `os.lstat` on the clone root (`upstream.py:542-544`) and a macOS symlink is mode `0777`. The copies preserve the read-only work-tree mode. The real `work/companions/LOCK.json` was not modified. `validate.py` against that real file will reject the needed_by widening until the orchestrator applies it.

## Records and checks

`RESULT.json` notes keep the earlier `MODEL REVIEW (claude-opus-5-5, ...)` paragraph whole. The author's text before that paragraph was shortened at a word boundary, ending ` [...]`, so the notes stay within 8,000 characters after the new review paragraph. `show_refs.py --companions-root` reported 0 bad citations. `collect.py --strict` on this package reported pass and 0 warnings. The package cases in `test_driver.py` passed (12 tests, 6.403 s) before the gate; the gate's G9 ran them again, including `test_gate`. `validate.py --no-corpus`, after the record and index update above, reported errors 0.

Nothing was taken from `development/p5-gz-topic/project` or `development/ext-p5-gz-topic.fast-stopped/project`. For this package and for `companion-sources-lock.json`, those trees matched the snapshot bytes.

## Rule deviations

The two cited companion directories under `DEV/companions-root/` are copy-on-write copies rather than symlinks, for the `lstat` reason above. A read-only `git --no-optional-locks rev-parse HEAD` and `status --porcelain` was run on those copies, not on the real clones, to confirm the copy was clean before the gate. The gate's own git reads also ran. No `__pycache__` was left, `PYTHONDONTWRITEBYTECODE=1` was set, and nothing was written outside `DEV` except the SDK's own temporary files under the default `TMPDIR`. No network, install, Docker or deletion. The real `LOCK.json` was not edited.

## Round 1

Codex (gpt-6.1-sol) blocked the submitted re-enable. `REVIEW.md` item 13 (lines 146-151) requires no unpause when a stored motion command cannot be cleared first. The `/cmd_vel` callback keeps `req_vel_` (`quadruped_controller.cpp:116-121`) and a wall timer republishes trajectories (`:94-97`). `JointTrajectoryController::PreUpdate` returns while paused (`JointTrajectoryController.cc:438-441`) and, once the world runs, `SetTarget` applies the stored trajectory point and `Update` runs (`:498-519`). A zero Twist is unacknowledged and does not clear those joint targets before an unpause. Disclosure of that window does not meet the rule.

`x-cap.justyx404.resume.v1`, the pause-false binding and `_ZeroBeforeResume` are removed. `_VelocityReceipt` only copies the three Twist components of a caller publication onto the receipt. `safe_state` (445 characters, one sentence) says the operator zeros `/cmd_vel` and unpauses outside MHS. A fact cites `JointTrajectoryController.cc:498-519`. `mhs.safety.reset` leaves the world paused. The catalogue request for the resume id is removed. The earlier `MODEL REVIEW (claude-opus-5-5, ...)` paragraph is unchanged. The grok review paragraph now records the removal. Author notes before the first MODEL REVIEW were shortened again at a word boundary and still end ` [...]`. Notes are 7891 characters.

`SpotCases` then ran 11 tests in 6.271s, OK. The gate passed G1-G9. `show_refs.py` reported 0 bad citations. `collect.py --strict` reported pass and 0 warnings. `stable_digest` of the new `check-report.json` is still `sha256:00405e1fd63e857afcb676c589dda513c121f7a89fdd9a8b940c0f3538736961`. `check.py` `stable_digest` (lines 3125-3144) hashes the report without the clock and durations, and the gate results, findings, backend, pin and SDK version did not change, so the passing digest did not move. The registry record was left as the passing overlay. `build_registry.py` was not run again.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/justyx404__spot_gazebo_ros2/RESULT.json`
- `MHS/drivers/robots/justyx404__spot_gazebo_ros2/driver.lock.json`
- `MHS/drivers/robots/justyx404__spot_gazebo_ros2/driver.py`
- `MHS/drivers/robots/justyx404__spot_gazebo_ros2/facts.md`
- `MHS/drivers/robots/justyx404__spot_gazebo_ros2/fake.py`
- `MHS/drivers/robots/justyx404__spot_gazebo_ros2/test_driver.py`
- `MHS/registry/overrides/companion-sources-lock.json (entry merged)`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
