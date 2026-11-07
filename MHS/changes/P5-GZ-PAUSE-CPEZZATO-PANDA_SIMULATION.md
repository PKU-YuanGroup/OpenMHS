OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# cpezzato/panda_simulation: Gazebo world pause with a paused-flag read-back

`robots/cpezzato__panda_simulation` moves from `blocked` (`HELPER_MISSING`) to `pass`. The stop is the fetched Kinetic companion service `/gazebo/pause_physics`, confirmed only when `/gazebo/get_physics_properties` reads `pause` true. The package offers no unpause. Evidence is `contract_checked` on the fake backend. No Gazebo process, ROS graph, hardware run or human review is claimed. `reviewed_by` stays null.

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 as a repair of the package authored by `deepseek-v4.1-flash:1017` (run `ros-wave-c-070`, date 2026-11-04). `authored_by` is unchanged. This repair's run id is `ext-p5-gz-pause--cpezzato__panda_simulation-20261105`. The package directory was not moved aside.

## Decision

The user's decision of 2026-11-05 (decision 1) allows a stop to cite a locally cloned companion at a pinned commit. Both clones were already fetched under `work/companions` and listed in `LOCK.json` (the user's authorisation of 2026-11-05). This unit widens `needed_by` for those existing clones. It fetches nothing.

The triage verifier (`BATCH/drafts/retriage-result.json`, directory `robots/cpezzato__panda_simulation`) kept the in-clone block and pointed at the companion pause already accepted for the Kinetic Gazebo packages. The package README names Kinetic and also mentions Melodic. This package serves only the Kinetic pin.

## Stop

`driver.py:484` sets `safety_bindings` to `estop` = `/gazebo/pause_physics` (`std_srvs/Empty`, `driver.py:102-113`) and `safe_state` = `/gazebo/get_physics_properties` with `pause` equal to true (`driver.py:115-126`, `state_ref` line 1460).

Cited companion lines, checked by `show_refs.py` (0 bad citations):

- `gazebo_ros_api_plugin.cpp:469-475` advertises `pause_physics` as `std_srvs::Empty` (`:471`). `:360-366` advertises `get_physics_properties` as `gazebo_msgs::GetPhysicsProperties` (`:362`).
- `pausePhysics` calls `world_->SetPaused(true)` and returns true (`:1692-1696`; the call is `:1694`).
- The read-back assigns `res.pause = world_->IsPaused()` (`:1460`). That value is the world's paused flag.
- `getPhysicsProperties` sets `res.success` true only in the ODE branch (`:1489`) and false otherwise (`:1496`), and returns `res.success` (`:1499`). `empty_world.launch:15` defaults `physics` to `ode`. Another engine leaves the e-stop unconfirmed and the latch held.
- Gazebo 7.16.1 `World::IsPaused` returns the stored flag (`World.cc:1300-1303`). `World::SetPaused` stores it under the world update mutex (`:1306-1314`). `World::Step` updates the world only when it is not paused, a step is pending, or a reset is due (`:615-634`).

`safe_state` (`driver.py:388-394`) says a confirmed pause still lets `World::Step` update when a step is pending or a reset is due. Stopping `panda_control_AIC` does not clear retained joint effort or the AIC torque state `u`. The world stays paused until an operator-reviewed procedure has independently verified that those retained controller commands are cleared or reinitialized. This package does not provide that procedure.

## SAFE-042

There is no unpause binding and no `reenable`. `mhs.safety.reset` releases the latch and leaves the world paused (`test_driver.py:156` and `:187`).

`AIC::computeActions` starts at `panda_control/src/classes/AIC.cpp:152`. Line 153 is the comment "Compute control actions through gradient descent of F". Line 154 is `u = u-h*k_a*(SigmaP_yq1*(jointVel-mu_p)+SigmaP_yq0*(jointPos-mu));`. The torque state is the previous `u`. This package does not command that state and cannot clear it. A zero effort publication is overwritten on the next AIC cycle. An unpause would resume stored motion, so the package does not offer one.

The Gazebo GUI (`empty_world.launch:8` defaults `gui` true), a WorldControl message, or any other client can still unpause or step the world. `safety_status` returns the cached confirmation and does not call `get_physics_properties` again, so it cannot detect that external unpause or step (`driver.py:434-438`, `test_driver.py:174`). `RosBridge.safety_status` (`MHS/sdk/src/mhs/bridge/ros.py:2227-2232`) returns `achieved` from the cached confirmation and performs no ROS I/O.

## Receipts and observations

Effort outputs add `sent_effort`, the value handed to rosbridge (`driver.py:277-294`; the action field is at `:270`). The device resource reads no topic (`test_driver.py:96`). Joint-state and free-energy reads stay explicit subscribe actions. While the world is paused, `/robot1/joint_states` is silent because `joint_state_controller` publishes from the gazebo_ros_control world update, and the read fails `NOT_READY` after the 2 s wire default. Whether the AIC keeps publishing `/panda_free_energy` while `/clock` is silent is roscpp behaviour outside these clones. The fake still answers that subscription while paused, and it writes no effort to a joint (`fake.py:97`, `:112-114`).

The seven effort catalogue requests now say the extension reports the sent effort, not an applied torque.

## Risk and limits

`risk` stays `R2` (`driver.py:316`). REVIEW.md item 12: the seven joint effort topics are commands a real arm behind the same bridge would act on. The pause service on its own would be R0. The command topics set the floor.

Effort inputs stay `Limit.operator_required` (`driver.py:187`). The xacro effort attributes are unsigned (87 on joints 1-4, 12 on joints 5-7, `franka_description/robots/panda_arm.xacro:103-259`). `site-limits.example.json` is an example overlay only. The earlier signed -87..87 limits stay removed.

## Profile

Profile `ros1-kinetic-gazebo7`. The token `kinetic` is on the package (`README.md:41` `ros-kinetic-desktop-full`, `README.md:54` `/opt/ros/kinetic/setup.bash`) and on the companion (`gazebo_ros/CHANGELOG.rst:130-136`). `panda_simulation/package.xml:18` is catkin and `:21` depends on `gazebo_ros`. `simulation.launch:13` includes `$(find gazebo_ros)/launch/empty_world.launch`.

`README.md:73` says Melodic and Gazebo 9 are usable. That pin is gazebo_ros 2.8.7, and its line numbers differ. This package does not serve it (`driver.py:334` and the fidelity gap at `:441-443`).

Companions, both already fetched:

- `gh.ros-simulation/gazebo_ros_pkgs` at `98bb3d0a0afc65725deaa1633e21ff6f5322b564`, lock `ros-simulation__gazebo_ros_pkgs@2.5.21`. `license_spdx` is `NOASSERTION`, with `licence_note` `Apache-2.0 AND BSD (per package.xml; no licence file in the repository)`.
- `gh.gazebosim/gazebo-classic` at `6fea5977c4518f6d722855c0e342e1e5acf64bac`, lock `gazebosim__gazebo-classic@gazebo7_7.16.1`, `license_spdx` `Apache-2.0`.

`driver.lock.json` repeats `{package_id, commit, lock}` for those two. `authored_by` and `reviewed_by` (null) are unchanged.

## Registry

`MHS/registry/overrides/companion-sources-lock.json` gains one override, `gh.cpezzato/panda_simulation`, between `gh.blackcoffeerobotics/bcr_arm` and `gh.erdalpekel/panda_simulation`. The `package_id` list stays sorted. `companion-sources.json` was not edited.

The registry card and `task.json` are the same bytes. `package_status` is `pass` and `blocked_on` is `[]`. The companion objects use the resolved card shape (alias, package_id, commit, profile, reason, version_evidence, lock, ref, local_path, repo_url, license_spdx, and `licence_note` on gazebo_ros). `build_registry.py` was not run. It reads the real `work/companions/LOCK.json`, which does not yet list this package in `needed_by`, and a full rebuild would also rewrite `generated_at`.

The registry record now has `adapter.state` `runnable`, `blocked_on` `[]`, `ring` 1, `evidence.state` `contract_checked`, `evidence.read_by` `runtime`, and `provenance_refs` pointing at this package's `RESULT.json`. `HELPER_MISSING` was removed from `integration.blockers`. `NO_ENTRY_SYMBOL` and `NO_INSTALL_FILE` stay. `next_action` is the maintain-the-passed-package sentence. `index.json`, `index.jsonl` and `records.csv` were rebuilt with `python3 MHS/registry/build_index.py`. `python3 MHS/registry/validate.py --no-corpus` then printed `errors: 0` and `RESULT: PASS`.

## Lock widening, not yet applied

`work/companions` is read only. `DEV/companions-root/` holds one symlink per clone directory of the real companions tree, plus edited copies of `LOCK.json` and `README.txt`. Against the lock this copy was taken from, the only semantic change is `needed_by` of `ros-simulation__gazebo_ros_pkgs@2.5.21` and `gazebosim__gazebo-classic@gazebo7_7.16.1`. Each list is `gh.cpezzato/panda_simulation`, `gh.ethz-asl/rotors_simulator`, `gh.gsilano/crazys`, `gh.lihuang3/ur5_ros-gazebo`. The file was rewritten with `json.dumps` indent 2. `README.txt` keeps the text it was copied from and appends the widening note. The live `work/companions/LOCK.json` now has 23 clones and `total_size_bytes` 884083159, including `micro-manager__mmCoreAndDevices@ce92a47dc1b0`. This copy has 22 clones and `total_size_bytes` 752731997. Do not replace the live file with this copy. Merge only those two `needed_by` additions into the current lock, preserving newer entries, and append the widening note to the current `README.txt`.

The gate's writable check `lstat`s the clone path (`mhs.driver.upstream.UpstreamTree.writable_entries`). A symlink whose mode is `0755` is reported as `G1.COMPANION_WRITABLE` on `.`. Each symlink was changed with `chmod -h 555`. The real clone directories stay mode `0555`. The gate, `show_refs.py` and `collect.py` were pointed at this directory with `--companions-root`.

`ShippedLockSourcesTests.test_the_shipped_entries_meet_the_shape_and_lock_rules` still reads the real `work/companions/LOCK.json` and fails for this package until the orchestrator applies the widening. That failure is expected. The test was not edited.

## What was taken from the stopped attempts

`driver.py`, `fake.py` and `test_driver.py` were taken from `development/ext-p5-gz-pause.fast-stopped/project`. Those three files are byte-identical to the stopped Claude tree `development/p5-gz-pause/project`. One edit was applied after the copy: the torque-state fact cites `AIC.cpp:153-154`, not line 154 alone, because line 153 is the gradient comment and line 154 is the assignment. The companion override's pins match both stopped drafts. Its justification was rewritten for grok-4.7. Edits in those trees for `warehouse_simulation_toolkit` and `companion-sources.json` were not taken.

## Gate

`python3 -m mhs.driver check MHS/drivers/robots/cpezzato__panda_simulation --backend fake --companions-root ../companions-root` passed G1 through G9. The printed digest is `sha256:c28c71a3a1aa7665d4b945fea059591557594e90f48e44c13267795cf6944ae3`. `RESULT.json` records that digest, `status` `pass`, `blocked_on` `[]` and `failed` `[]`. The previous model-review paragraph is unchanged. A second paragraph, headed `MODEL REVIEW (grok-4.7, a model and not a human, 2026-11-05; reviewed_by stays null): `, was appended. Round 1 corrected that paragraph. The notes length is 7977 characters. The stable digest did not move: the check report records gate results, not the safe-state prose.

The card's acceptance command does not include `--companions-root`. Against the real lock it fails `G1.COMPANION_LOCK` until `needed_by` is widened. `check_driver` inside `test_driver.py` reads `MHS_DRIVER_GATE_COMPANIONS` only when `MHS_DRIVER_GATE_INNER` is set (`check.py` `run_check`, the `if inner` branch). The gate's G9 child sets both. A direct `python3 test_driver.py` with only the companions variable set fails `test_gate` and passes the other cases. With both variables set, all 14 tests pass.

## Round 1

The recovery sentence that said to stop `panda_control_AIC` and then press play or call `gazebo/unpause_physics` was removed from `safe_state`, the fidelity gaps, the module docstring, `facts.md`, and the generated reference. `AIC::~AIC` is empty (`AIC.cpp:43`) and main returns without clearing state (`AIC_controller.cpp:93`). `default_robot_hw_sim.cpp:315-316` applies the retained `joint_effort_command_` on the next update unless `e_stop_active_`. The world stays paused until an operator-reviewed procedure has independently verified that those retained controller commands are cleared or reinitialized.

`safety_status` does not re-read the paused flag. It returns the cached confirmation. `test_driver.py:174` completes the e-stop, sets the fake `paused` flag false, and checks that the service list stays `[/gazebo/pause_physics, /gazebo/get_physics_properties]` while `estop.confirmed` and the cached `safe_state.achieved` stay true. After reset, with the world still paused, the free-energy read completes and the joint-state read fails `MHS.DEVICE.NOT_READY`.

The spawned-model fact no longer says the model has the seven arm joints only. The hand instantiation is commented out, and `panda_arm.xacro:269-276` still declares `${arm_id}_joint8`. `safe_state` now matches `World::Step`: a pending step or a due reset still updates the world.

The first gate after those edits failed G9: the new case invoked free energy while the latch was still held, and the server rejected it with `MHS.SAFETY.ESTOP_ENGAGED`. The free-energy assertion moved to the reset case, which releases the latch and leaves the world paused. The next gate passed and printed the same digest `sha256:c28c71a3a1aa7665d4b945fea059591557594e90f48e44c13267795cf6944ae3`. `show_refs.py` reported 56 citations and 0 bad. Direct `test_driver.py` with `MHS_DRIVER_GATE_INNER=1` and the companions root ran 14 tests in 7.640s, OK. `collect.py --strict` exited 0: 1 of 1 pass, 0 warnings, and the same two `COMPANION_SOURCE` notes (19 gazebo_ros fact citations, 7 gazebo_classic fact citations). `authored_by` stays `deepseek-v4.1-flash:1017`. `reviewed_by` stays null. No simulator or hardware run is claimed.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/cpezzato__panda_simulation/RESULT.json`
- `MHS/drivers/robots/cpezzato__panda_simulation/driver.lock.json`
- `MHS/drivers/robots/cpezzato__panda_simulation/driver.py`
- `MHS/drivers/robots/cpezzato__panda_simulation/facts.md`
- `MHS/drivers/robots/cpezzato__panda_simulation/fake.py`
- `MHS/drivers/robots/cpezzato__panda_simulation/test_driver.py`
- `MHS/registry/overrides/companion-sources-lock.json (entry merged)`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
