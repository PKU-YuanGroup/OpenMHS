OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# p5b-dualmode: cambel/ur3 served only as the ur_gripper_gz simulation

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05. `reviewed_by` stays null. No hardware was attached, no Gazebo or ROS graph was started, and no human review is claimed. The passing evidence is the fake backend, `contract_checked`.

This unit is cambel/ur3 only. The parallel ardupilot unit is untouched.

## Decision

User decision 1 of `user-decisions-20261105b.json` (2026-11-05): cambel/ur3 may be served only in its simulated form. The hardware path stays blocked. The route is the clone's `ur_gripper_gz` gz-sim bringup (ROS 2 Jazzy, Gazebo Harmonic / gz-sim 8). The fetched gz-sim 8, ros_gz Jazzy and gz-transport 13 lock companions may serve the stop. Risk follows REVIEW.md item 12 for an arm: R2.

The previous package was a blocked hardware driver (`status` blocked, `blocked_on` `NO_HARDWARE_FREE_PATH`, gate failed G3, digest `sha256:480f4181f9d18e8a79751cedf17e957389388428fd8d970ece2638c940b2431f`, `authored_by` deepseek-v4.1-flash:1017). That directory was moved to `DEV/moved-aside/cambel__ur3/` before this package was written. A copy of it, and of the registry sources this unit edits, is in `DEV/originals/`.

## How the card serves simulation while the record keeps hardware

A modes override cannot drop scanned hardware (SAFE-045). A simulated driver on a hardware card fails G3 `MODE_MISMATCH`. The new override field is `served_mode`, and the only accepted value is `simulated`, and only on a dispatchable strategy (`triage.py` `check_override`). `Decision.served_mode` is not written by `to_json` (same as `modes` and `companions`).

`build_registry.py` `finalize_record` writes `x-vendor.classification.served_mode` only when the record's modes keep `hardware` first and also contain `simulated`. Anything else raises. `taskcards.expected_mode` returns `simulated` only under that same condition (`taskcards.py` around the `served_mode` branch). Otherwise the card still serves the record's first mode. `validate.py` `check_served_mode` and the override loop require the record marker and `safety.expected_mode` to match the override.

The cambel override moved from `MHS/registry/overrides/robots.json` into `companion-sources-lock.json`, in `package_id` order, after `gh.blackcoffeerobotics/bcr_arm` and before `gh.erdalpekel/panda_simulation`. Strategy `family-config`, role `device-driver`, family `ros`, `reason_code` `override:recon`, `served_mode` `simulated`. Entry symbols stay `ur_control.arm:Arm` (`arm.py:49`) and `ur_control.fzi_cartesian_compliance_controller:CompliantController` (`fzi_cartesian_compliance_controller.py:90`). Companions, in card order: gz-sim `446a44335a45b704b4d36dabcc5508ee34eeb3d8` (`gazebosim__gz-sim@gz-sim8_8.15.0`), ros_gz `b87d7523400a695a10d47ca7b8cb5fa86d5b8d9d` (`gazebosim__ros_gz@1.0.25`), gz-transport `35fef7ea10c2e133498e9010bd2e397a0ce0c3bf` (`gazebosim__gz-transport@gz-transport13_13.6.0`). Profile `ros2-jazzy-gzsim8`.

After the rebuild the record `MHS/registry/repos/robots/cambel__ur3.json` still has `modes` `["hardware", "simulated"]`. The card `MHS/registry/tasks/robots/cambel__ur3.json` has `safety.expected_mode` `simulated`, `safety.risk_floor` `R1`, `package_status` `pass`, `blocked_on` `[]`. `needs_recon` keeps `install` because the lock's install commands are empty; `limit_sources` dropped because the served mode is not hardware (`taskcards.py` adds that need only when `mode == "hardware"`). `publish_review` stays `not_required`. `LICENSE:1` is the MIT License. `ur_gripper_gz/package.xml:14` says BSD. The card licence stays the repository MIT.

`task.json` is a byte copy of that card. `prepare.py --sync` only refreshes an existing `task.json` and does not create one; the other prepare path calls git, which this unit does not run. After the copy, `python3 MHS/handoff/tools/prepare.py gh.cambel/ur3 --sync` refreshed nothing.

`build_registry.py --companions-root` is passed only into `read_companion_lock`. Clone paths in the registry stay `work/companions/...` through the workspace symlink. The real `$R/work/companions/LOCK.json` was not modified.

## The driver

`UrGripperGz` (`MHS/drivers/robots/cambel__ur3/driver.py`) is a `RosDriver`. `device_id` `ur-gripper-gz`, `device_kind` `robot.arm`, `mode` `simulated`, `risk` `R2`, `ros_version` 2, backend `fake` only (`FakeUrGripperGz`). There is no hardware backend and no `native.py`. The driver does not import the clone.

The one observation is `x-cap.cambel.joint-states.v1`: subscribe `/joint_states`, type `sensor_msgs/msg/JointState`, `source_name` `joint_states`, `source_ref` `ur_control/ur_control/controllers.py:64` (`create_subscription(JointState, 'joint_states', ...)`), `type_ref` `controllers.py:21`. The result map is `name`, `position`, `velocity`. No length and no unit: the clone states none. The six `JOINT_ORDER` names in the fake (`constants.py:49-52`) are placeholders. The launch starts a spawner named `joint_state_broadcaster` (`ur_gz_control.launch.py:106-113`); that line is not a topic literal, so the package does not claim the broadcaster publishes `/joint_states`. A withheld sample is a timeout. The retry at `controllers.py:71` builds the namespace plus `joint_states` and is not the served endpoint.

The trajectory topic is not published. See the open question below.

The served launch is `ur_gripper_gz/launch/ur_gz_control.launch.py` only (Hand-E). Its `gz_args` contain `empty.sdf`, `-r` and `gz-physics-bullet-featherstone-plugin` and it includes `ros_gz_sim`'s `gz_sim.launch.py` (`ur_gz_control.launch.py:87-95`). The companion file `examples/worlds/empty.sdf:63` is `<world name="empty">`. The spawn name is the `ur_type` argument (`:102`), which defaults to `ur3e` (`:174-175`). `ur3` is in the argument description. `ur_2f85_gz_control.launch.py` defaults `ur_type` to `ur5e` and is not served. The served launch's only `parameter_bridge` argument is `/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock` (`:65-68`). `/clock` is not an operator bridge.

### Stop

The e-stop is the gz-sim WorldControl pause on `/world/empty/control`, type `ros_gz_interfaces/srv/ControlWorld`, request `world_control.pause` true, timeout 400 ms. `source_ref` `SimulationRunner.cc:325` (`Advertise("control", &SimulationRunner::OnWorldControl, ...)`). `type_ref` `ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:43-52`. `state_ref` `SimulationRunner.cc:1443` (`SetPaused(control.pause)`). The Boolean reply is true when the control is queued (`SimulationRunner.cc:1375-1377`). `ControlWorld.srv:3` comments that success means the control was successful; that comment is the ROS reply text. Confirmation is the E2 read-back, not the reply.

The read-back is `/world/empty/stats`, type `ros_gz_interfaces/msg/WorldStatistics`, `success` path `paused` equals true, fresh `after_request`, `discard_first`, `consecutive` 2, `within_ms` 600, `min_interval_ms` 40. `PublishStats` copies `currentInfo.paused` (`SimulationRunner.cc:534`). `Step` calls `PublishStats` (`:1023-1024`) before `ProcessMessages` (`:1063-1064`), so the sample that applies a queued pause can still report the previous flag. The fake applies the pause after it builds the stats sample. `estop_latency_ms` is 1500.

Operator bridges (E3), both cited from `ros_gz_bridge/README.md`:

- `/world/empty/control@ros_gz_interfaces/srv/ControlWorld` (`README.md:86`)
- `/world/empty/stats@ros_gz_interfaces/msg/WorldStatistics[gz.msgs.WorldStatistics` (`README.md:52`)

The bridge README's own service example uses `/world/shapes/control` (`README.md:261-265`). The example world is `shapes`.

### No unpause (SAFE-042)

There is no `reenable` and no reset binding. `mhs.safety.reset` releases the MHS latch and leaves the world paused. `JointTrajectoryController.stop` calls `cancel_goal_async` and does not wait (`controllers.py:493-498`). `SetPaused` stores `currentInfo.paused` (`SimulationRunner.cc:1290-1291`) and does not send that cancel. This package cannot show that an unpause clears a trajectory the launch's controller accepted, so it does not unpause. A queued `multi_step` greater than zero while paused calls `SetPaused(false)` (`SimulationRunner.cc:1445-1452`). `examples/worlds/empty.sdf:68-83` loads physics, user-commands, scene-broadcaster and contact. The GUI note is the statistics-publisher comment (`SimulationRunner.cc:800-805`). Operator recovery outside MHS is to cancel or let the goal finish, then use the GUI play control or a pause-false ControlWorld outside MHS.

While the latch is held, `client.invoke` of `x-cap.cambel.joint-states.v1` is rejected with `MHS.SAFETY.ESTOP_ENGAGED`. `server.py` `_is_read_capability` does not treat an `x-cap.*` id as a read. After reset the same invoke completes and the world stays paused. The package tests call `client.invoke`, not `driver.call`.

### Hardware path, disclosed and not served

`check_for_real_robot` returns true without calling the wrapped function when `use_real_robot` is false (`ur_services.py:16-24`). That parameter defaults false (`ur_services.py:38`). The dashboard stop client is a `std_srvs.srv.Trigger` (`ur_services.py:51`). `README.md:211` defers the Robotiq real-hardware driver. The `noetic-devel` branch named at `README.md:6-7` is not served. The dashboard Trigger is not revived.

### Risk

REVIEW.md item 12: a world service that only the simulator serves would stay R0, and a joint command that a physical driver also consumes follows the arm at R2. The served device is a simulated UR arm. The yaml names `scaled_joint_trajectory_controller` so `ur_control`'s Arm drives the simulated robot unchanged (`ur_gz_controllers.yaml:4-5`). This package publishes no joint command. The driver still declares `risk` `R2`, at or above the card floor `R1`. The read action's risk is unset. The R2 is the device class.

## Lock companions

`DEV/companions-root/` has one symlink per clone directory of `$R/work/companions`, plus copies of `LOCK.json` and `README.txt`. The three `needed_by` lists gained `gh.cambel/ur3` after `gh.osrf/vrx`. The backup lock files were not linked. The symlinks were `chmod -h a-w` (mode `0555`). The gate's `writable_entries` uses `lstat` on the clone path (`upstream.py`), and a `0755` symlink is reported as a writable `.`. The targets stay the read-only `0555` clones. The real lock file was not edited.

## Gate

`python3 -m mhs.driver check MHS/drivers/robots/cambel__ur3 --backend fake --companions-root DEV/companions-root` passes G1-G7 and G9. G8 warns `SAFE014_NOT_APPLICABLE`: the driver declares no limit on an actuating capability, so SAFE-014 has nothing to probe. That warning is a collect note, not a strict failure. Digest `sha256:ee9747232bb25c2314e366d1fea27f47e211f97666ebdc98543597988fb04b99`. `collect.py --strict` on this package reports pass, 0 warnings. `validate.py --no-corpus` reports 0 errors (2967 records, 2967 cards).

`reference.json` and `REFERENCE.md` were generated with `python3 -m mhs.driver reference` before the gate. `facts.md` is the driver's fact list (75 rows) plus the scope, limits, safety and fidelity prose. It opens with the independence sentence.

The registry rebuild used `--jobs 1`. `--jobs 4` raised `PermissionError` on `multiprocessing` `SemLock` in this sandbox. `triage.scan_corpus` uses a process pool only when `jobs > 1` (`triage.py`). The scan cache was a hardlink of an existing `v11` cache, removed after the builds. `MHS_REGISTRY_DATE` was unset. The first rebuild wrote the card. The second, after `task.json`, the reference and the real digest were in place, wrote one file: the cambel record. Its overlay files are `RESULT.json`, `driver.lock.json`, `reference.json`, `task.json`. `gate_digest` is the digest above. `evidence.state` is `contract_checked`. The card bytes did not change, so `task.json` still matches.

Moving this package from wave 5 rank 2 to wave 3 rank 127 renumbered other cards. 370 other task cards and 370 other records differ from snapshot-6 only in `rank`. Eight family recipes differ only in those ranks or in gazebo wave counts (wave 3: 33 to 34, wave 5: 21 to 20). `README.md` and `coverage.md` move wave 3 from 408 to 409, wave 5 from 90 to 89, `contract_checked` from 729 to 730, and `static_scan` from 2186 to 2185. `index.json`, `index.jsonl` and `records.csv` follow. Those files are generated.

## Tests and mutants

`MHS/registry/tests/test_served_mode.py`: 9 tests, all passing. Two mutants were applied and reverted:

- `expected_mode` no longer returned `simulated` for `served_mode`. `test_dual_mode_card_serves_simulated_and_keeps_hardware_first` failed (`AssertionError`: `'hardware' != 'simulated'`). Reverted.
- `read_companion_lock` ignored `companions_root`. `test_companions_root_selects_lock_json_and_the_default_stays_under_the_workspace` failed (the selected lock was the workspace lock). Reverted.

Package `test_driver.py`: 9 tests, all passing, including the gate. `check_driver` does not read `MHS_DRIVER_GATE_COMPANIONS` unless the run is the gate's inner G9 (`check.py` `run_check`, the `inner` branch). The test passes `companions_root` itself.

No SDK file changed. The full SDK suite was not run.

## Stopped attempts

`development/p5b-dualmode` (the stopped Claude attempt) is not present. The stopped Grok tree `development/ext-p5b-dualmode.fast-stopped/project` was compared earlier in this unit: its cambel package and `triage.py` matched the pre-change originals. Nothing was copied from either tree.

## Open question

`JointTrajectoryController` builds the command topic as `self.ns + publisher_name + '/joint_trajectory'` (`controllers.py:377-382`, the concatenation is line 381). The quoted `'/joint_trajectory'` is not a G7 endpoint for `source_name` `joint_trajectory`. This package does not publish that topic. A later card could bind it only if a citable literal endpoint existed.

## Round 1 repair (2026-11-05)

Codex blocked the package. Grok accepted it and left two citation nits. `reviewed_by` stays null. `authored_by` stays `grok-4.7`. The pre-repair bytes of the files this round edited are in `DEV/originals/r1-before/`. The snapshot-6 copies in `DEV/originals/MHS/` were not overwritten.

The authorship finding is disputed. `logs/impl.prompt.md` lines 5-7 tell this unit to read "Claude authors" as "Grok authors" and "Claude Sonnet reviews" as "Codex reviews". `user-decisions-20261105b.json` line 7 still says "Claude authors, Claude Sonnet reviews"; that is the sentence the brief reinterprets. Relabelling the lock would hide who wrote the package. `driver.lock.json` lines 39-45 are unchanged.

`safe_state` (`driver.py` lines 343-349, 479 characters) now says the paused flag holds only for the confirmation window, the pause retains trajectory targets, `UserCommands` executes queued world edits, a `multi_step` control or the GUI or another client can resume the world, and recovery outside MHS follows after pending motion is cleared. The same limits are in the fidelity gaps and in `facts.md`. The citations read for that repair are `UserCommands.cc:669-699` (pending commands are copied and `Execute`d; the `UpdateInfo` parameter is unused), `SimulationRunner.cc:662-684` (`UpdateSystems` calls `PreUpdate`), `SimulationRunner.cc:896-911` (a paused run still calls `Step`), `SimulationRunner.cc:1445-1452` (`multi_step` calls `SetPaused(false)`), and `SimulationRunner.cc:1290-1291` (`SetPaused` stores `currentInfo.paused`). No unpause binding was added.

`test_driver.py` lines 22-32 read `MHS_DRIVER_GATE_COMPANIONS` when it is set and otherwise use `work/companions` under the directory that holds `MHS/sdk`. The module does not assign that variable. A direct `check_driver` call still receives `companions_root`, because `run_check` reads the variable only when `inner` is true (`check.py` lines 2957-2960). A real copy of the package under `DEV/relocated-r1/project` (not a symlink of the project) had no `companions-root` at `parents[4]`. `collect.py --strict` on that copy, with `--companions-root` pointing at `DEV/companions-root` and the variable unset in the parent, passed 1 of 1 with 0 warnings. The probe directory was removed after that run.

The joint-list fact now cites `ur_gz_controllers.yaml:45-55`, which includes `command_interfaces` / `position` (`driver.py` line 66). The `OnProcessExit` fact names only `jsb_spawner`, `fts_spawner`, `jtc_spawner`, `fvc_spawner`, `compliance_spawner` and `gripper_spawner` (launch lines 186-190). A separate fact cites launch line 124: `force_torque_sensor_broadcaster` is passed with `-c` and `/controller_manager`. `facts.md` has 78 fact rows and still round-trips `driver.facts`.

`python3 -m mhs.driver reference` and `--check` were run again. `show_refs.py` reported 0 bad citations. The package gate passes G1-G7 and G9, warns `G8.SAFE014_NOT_APPLICABLE`, and the stable digest is still `sha256:ee9747232bb25c2314e366d1fea27f47e211f97666ebdc98543597988fb04b99`. That digest is the check report without its clock fields (`check.py` `stable_digest`). The report does not embed `safe_state` or the facts, so this repair did not move it. `RESULT.json` keeps that digest and appends one MODEL REVIEW paragraph. The author-tree `collect.py --strict` passed 1 of 1 with 0 warnings. Companion citation notes are now gz_sim 23, ros_gz 16, gz_transport 3. No registry source changed, so the registry was not rebuilt and `task.json` still matches the card. No SDK file changed. The full SDK suite was not run.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/cambel__ur3/RESULT.json`
- `MHS/drivers/robots/cambel__ur3/driver.lock.json`
- `MHS/drivers/robots/cambel__ur3/driver.py`
- `MHS/drivers/robots/cambel__ur3/facts.md`
- `MHS/drivers/robots/cambel__ur3/fake.py`
- `MHS/drivers/robots/cambel__ur3/test_driver.py`
- `MHS/registry/build_registry.py`
- `MHS/registry/overrides/README.md`
- `MHS/registry/overrides/companion-sources-lock.json (entry merged)`
- `MHS/registry/overrides/robots.json`
- `MHS/registry/schema/overrides.schema.json`
- `MHS/registry/taskcards.py`
- `MHS/registry/triage.py`
- `MHS/registry/validate.py`
- `MHS/registry/tests/test_served_mode.py`

Round-1 review INT-001: the mandated applier is integrator-v4's `apply_delta.py`, and only its description may change. That applier adds a file, replaces a file, or moves a whole directory aside. It cannot remove three files inside a package directory that stays. `native.py`, `NATIVE-BLOCKERS.md` and `site-limits.example.json` are therefore kept at their snapshot-6 bytes (`289174695d8c`, `8e1a1fcadd1a`, `2a8f99ffed0a`). A gate with those files present passes. The stable digest is still `sha256:ee9747232bb25c2314e366d1fea27f47e211f97666ebdc98543597988fb04b99`. The package tests, 9 of them, pass. `native.py` raises `RuntimeError` before any ROS import. `site-limits.example.json` names `mhs://localhost/ur3/fake`, a device this endpoint does not serve, and the gate findings are unchanged. `reviewed_by` stays null.

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
