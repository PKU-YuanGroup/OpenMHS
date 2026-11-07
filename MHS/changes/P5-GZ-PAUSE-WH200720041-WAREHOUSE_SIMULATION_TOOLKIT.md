OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# P5-GZ-PAUSE: wh200720041/warehouse_simulation_toolkit

The warehouse Gazebo package now passes with a companion-cited world pause and a paused-flag read-back. It offers no unpause. This is a repair of the existing package: `authored_by` stays `deepseek-v4.1-flash:1017`, run `ros-wave-c-059`, date 2026-11-04. `reviewed_by` stays null.

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 as the package unit `ext-p5-gz-pause--wh200720041__warehouse_simulation_toolkit`. No hardware, Gazebo process, ROS graph or human review is involved. The gate evidence is `contract_checked` on the fake only.

## Why there is no unpause

The stop is gazebo_ros 2.9.3 `/gazebo/pause_physics` (`std_srvs/Empty`). `pausePhysics` calls `world_->SetPaused(true)` (`gazebo_ros/src/gazebo_ros_api_plugin.cpp:1725-1729`). The read-back is `/gazebo/get_physics_properties`, and the e-stop is confirmed only when `pause` is true (`res.pause = world_->IsPaused()`, `gazebo_ros_api_plugin.cpp:1489`). `getPhysicsProperties` returns false for a physics engine other than ODE (`gazebo_ros_api_plugin.cpp:1496-1528`). `warehouse.world` sets the physics type to `ode` (`worlds/warehouse.world:67`).

`World::Step` advances simulation time and calls `Update` only when the world is not paused, a step increment is pending or a reset is due (`gazebo/physics/World.cc:835-854`). `GazeboRosDiffDrive` sets wheel joint velocities from `UpdateChild` on the world-update begin event (`gazebo_plugins/src/gazebo_ros_diff_drive.cpp:177-179`, `:269-289`) using speeds derived from the stored `x_` and `rot_` (`:324-333`). `cmdVelCallback` stores `linear.x` and `angular.z` with no timeout (`:335-340`). `QueueThread` serves that queue with a 0.01 s wall-clock wait while the plugin is alive (`:342-349`), so a command received while the world is paused is stored and applied on the next world update.

A zero Twist can replace the stored `x_` and `rot_`. The publication is unacknowledged and is not proof those fields are clear. Stopping publishers does not clear them: `cmdVelCallback` only writes them when a Twist arrives (`gazebo_ros_diff_drive.cpp:335-340`), and `UpdateChild` applies them again when updates resume (`:269-289`, speeds from `:324-333`). The shipped launch also starts `move_base` at the root namespace with `respawn` true and no remap (`launch/warehouse_simulation.launch:45-60`). This package does not command `move_base`: the clone declares no `move_base` cancel, and `move_base`'s velocity topic is set outside the clone, so it is not cited as a fact. `MHS/handoff/REVIEW.md` item 13 and the orchestrator's SAFE-042 condition forbid an unpause that resumes a stored motion command this package cannot clear first. The verifier's primary path was a zero Twist and then `/gazebo/unpause_physics`, with the no-unpause path as the safer alternative. This unit takes the safer alternative. `unpausePhysics` (`gazebo_ros_api_plugin.cpp:1731-1735`) is a fact about that function and is not bound. After `mhs.safety.reset` the latch is released and the world stays paused. Before any manual unpause the operator prevents publisher respawn, including `move_base`, and clears or reinitializes the retained command outside MHS. Round-1 review (Codex) found the earlier sentence, which told the operator to stop publishers and then unpause, and that sentence is withdrawn.

`World::Step` still calls `Update` while paused when `stepInc` is greater than 0 or `needsReset` is set (`World.cc:835-837`). `OnWorldControl` with `multi_step` sets pause true and stores that step count (`World.cc:1633-1639`). The read-back assigns `res.pause` from `IsPaused()` only (`gazebo_ros_api_plugin.cpp:1489`), so `safe_state` says the paused flag and the suspension of ordinary updates, with those exceptions. Another client can unpause the world. MHS does not read the flag again after the e-stop. The GUI that the launch opens (`gui` true, `launch/warehouse_simulation.launch:8-12`) is one such client. The deployment must be the pinned gazebo_ros 2.9.3 (ROS 1 Noetic) and Gazebo 11. rosbridge cannot read those versions.

Risk stays R2. `/cmd_vel` is the generic root topic (`REVIEW.md` item 12). The clone states no physical unit, so both inputs stay unit `1` and `Limit.operator_required`. `keyLoop` assigns the per-key literals 0.7, 0.3, 0.0, -0.3 and -0.0 (`src/key_control.cpp:232-253`) and multiplies them by `scale_linear` and `scale_angular` (`:263-264`). The earlier "key-code constant" wording was wrong. The key code only selects the branch. The scales are still not device bounds.

## Companions

Corpus clones, not `work/companions` lock entries. `driver.lock.json` lists them in card order:

- `gh.ros-simulation/gazebo_ros_pkgs` at `cd9cc952402375be5f274f39b29399c4087aa839` (`robots/ros-simulation/gazebo_ros_pkgs`, licence `NOASSERTION`)
- `gh.gazebosim/gazebo-classic` at `b22c6e15e52299865b31093b8feebc9ca19e26e8` (`robots/gazebosim/gazebo-classic`, licence `Apache-2.0`)

Profile `ros1-noetic-gazebo11`. Package pin `18df8ce6dde61711e0705f3bd872465a01bd01a2`. `python3 MHS/handoff/tools/show_refs.py` on this package exited 0: both companion HEADs equal those pins, every version-evidence token is shown, and the output contains no `!!`.

The reviewed override is one object appended to `MHS/registry/overrides/companion-sources.json` (seven entries, still sorted by `package_id`). Round-1 review (Grok) asked to qualify the file-level `description`, which said every entry adds the `unpause_physics` re-enable. The description now says that re-enable is on every entry except `gh.wh200720041/warehouse_simulation_toolkit`, which binds the pause and the paused-flag read-back only. The warehouse object's own reason was already limited to the pause and the read-back.

## What was taken from the stopped attempts

`development/p5-gz-pause/project` and `development/ext-p5-gz-pause.fast-stopped/project` had the same bytes for this package's `driver.py`, `fake.py` and `test_driver.py`. Those three files were the starting point, then checked against the clones. Edits after that copy:

- The `UpdateChild` fact no longer says that hook publishes odometry. It says `UpdateChild` calls `getWheelVelocities` and sets both wheel joint velocities when `wheel_accel` is 0 or a wheel is within 0.01 of its target (`gazebo_ros_diff_drive.cpp:269-289`).
- The plugin fact includes `wheelAcceleration` 0 and `updateRate` 100.0 (`urdf/pioneer3dx_body.xacro:320-341`).
- The fidelity gap names the drive plugin's `updateRate` 100.0, the 5 Hz laser and the 10 Hz IMU with its 20 Hz plugin.
- The fake read-back returns `values` `{}` when `fail_readback` is set, and on success uses `status_message` `GetPhysicsProperties: got properties`.

The override object's shape follows those trees. The justification names `grok-4.7`. The rest of those trees' override files was not copied. `facts.md`, `RESULT.json` and the lock companions were written here. The inferred "rather than a hardware node" clause is gone from the launch fact, and the launch fact for `move_base` at the root namespace is present, which is what the Claude review of 2026-11-05 asked the next author to disclose. That Claude paragraph in `RESULT.json` is unchanged.

## Package surface

`WarehouseSimulationToolkit` stays config-only `RosDriver`, ROS 1, mode `simulated`, `device_kind` `world.sim`, risk R2, device id `warehouse-simulation`, fake `.fake:FakeWarehouseSimulationToolkit`. One command, `x-cap.wh200720041.cmd_vel.v1`, publishes `geometry_msgs/Twist` on `/cmd_vel`. The bridge wrapper adds `sent_linear_velocity` and `sent_angular_velocity` for that command only. `safety_bindings` is `estop` `/gazebo/pause_physics` and `safe_state` `/gazebo/get_physics_properties` with `pause` true. There is no `reenable`. The fake's negative switches are `fail_pause`, `fail_readback` and `ignore_pause`. The device resource reads no topic.

## Evidence

`python3 -m mhs.driver check MHS/drivers/robots/wh200720041__warehouse_simulation_toolkit --backend fake` passed G1 through G9 with `failed` `[]`. Stable digest `sha256:95511d814f776a28f1e16ba63f18a0325684edcb1692ab8e3776900dc3b9b737`. The package unit tests in `test_driver.py` passed (8 cases, then again as gate G9). No SDK file was changed, so there is no mutant run.

`python3 MHS/registry/build_registry.py --jobs 4` cannot start a process pool in this sandbox (`PermissionError` on `SemLock`). The rebuild that was kept used `--jobs 1` and wrote the canonical cards. It moves this package from wave 5, rank 45, to wave 3, rank 194, because `blocked_on` is empty and the card is dispatchable (`taskcards.py` `base_wave`). Rank is the position within the wave, so the packages that sort after it in wave 3 have a rank one higher, and the same shift appears in `families/gazebo.md`, `families/tag-bridge.md`, `families/pylabrobot.md` and `families/qcodes.md`. Those rank edits are the generator's output and were kept. `coverage.md` and `README.md` now count 730 `contract_checked` packages and 409 wave-3 cards. The repo record's evidence state is `contract_checked`, the adapter state is `runnable`, and `x-vendor.overlay.gate_digest` is the digest above. `prepare.py --sync gh.wh200720041/warehouse_simulation_toolkit` copied that card onto `task.json`. A second gate run after the sync printed the same stable digest.

## Round 1 review

Codex (high): `safe_state` no longer says that no world update runs whenever `pause` is true, and it no longer tells the operator to stop publishers and then unpause. It states the observed `pause` flag, suspension of ordinary `World::Step` updates except `stepInc > 0` or `needsReset` (`World.cc:835-837`), that other clients can unpause, and that MHS does not read the flag again. It also says that before any manual unpause the operator prevents publisher respawn, including `move_base`, and clears or reinitializes stored `x_` and `rot_`, and that publishing zero is unacknowledged. The same correction is in the fidelity gaps, `facts.md`, the module docstring, and the grok paragraph of `RESULT.json` notes. Unpause stays unbound. `safe_state` is 484 characters (the schema limit is 500).

Grok (low): the teleop fact, the `Limit.operator_required` reasons, and `facts.md` now say `keyLoop` assigns the per-key literals 0.7, 0.3, 0.0, -0.3 and -0.0 (`src/key_control.cpp:232-253`) and multiplies them by the scales (`:263-264`). The clone still states no numeric `cmd_vel` range, so the inputs stay `operator_required` with unit `1`. The same clause in the author's `RESULT.json` notes was corrected. The file-level description of `companion-sources.json` now excepts this package from the `unpause_physics` re-enable.

`reference.json` and `REFERENCE.md` were regenerated. `python3 -m unittest MHS.drivers.robots.wh200720041__warehouse_simulation_toolkit.test_driver.WarehouseSimulationCases` ran 8 tests in 0.601s, OK. The fake gate passed G1-G9 again and printed the same stable digest `sha256:95511d814f776a28f1e16ba63f18a0325684edcb1692ab8e3776900dc3b9b737`. The check report records gate results, not this prose, so the digest did not move. No registry rebuild was run. Notes are 7992 characters. The author's text before the first MODEL REVIEW paragraph was shortened at a word boundary, after "not the fake's timing.", and ends with ` [...]`, because the corrected grok paragraph would otherwise pass 8000 characters. The Claude review paragraph was not edited.

## Out of scope

`/scan`, `/odom`, `/imu`, `/tf`, `/map`, `/clock`, the `move_base` action, and the Gazebo reset and spawn services. `move_base`'s velocity topic is outside the clone.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/wh200720041__warehouse_simulation_toolkit/RESULT.json`
- `MHS/drivers/robots/wh200720041__warehouse_simulation_toolkit/driver.lock.json`
- `MHS/drivers/robots/wh200720041__warehouse_simulation_toolkit/driver.py`
- `MHS/drivers/robots/wh200720041__warehouse_simulation_toolkit/facts.md`
- `MHS/drivers/robots/wh200720041__warehouse_simulation_toolkit/fake.py`
- `MHS/drivers/robots/wh200720041__warehouse_simulation_toolkit/test_driver.py`
- `MHS/registry/overrides/companion-sources.json`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.

The registry suite counted six shipped companion-source overrides. This package's override makes seven. The integrator updated that count in `MHS/registry/tests/test_companion_overrides.py`. The shape checks are the same. The copy from before that edit is in `development/ext-integrator-A/originals/`.
