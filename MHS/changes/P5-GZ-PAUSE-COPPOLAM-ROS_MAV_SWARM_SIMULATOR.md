OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Gazebo pause for coppolam/ros_mav_swarm_simulator

The coppolam/ros_mav_swarm_simulator package now pauses the Gazebo world with `/gazebo/pause_physics` and confirms it by reading `/gazebo/get_physics_properties` with `pause == true`. It does not unpause. The fake-backend gate passes (evidence `contract_checked` only). Risk stays R2, and `publish_review` stays required because the licence is NOASSERTION.

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 as unit `ext-p5-gz-pause--coppolam__ros_mav_swarm_simulator-20261105`. This is a repair: `authored_by` stays `deepseek-v4.1-flash:1017` (`ros-wave-c-134`). `reviewed_by` stays null.

- **Where:** this unit's copy of snapshot-6. No other package directory was edited.
- **From:** the triage entry and the Claude Sonnet verifier in `work/handoff-runs/claude-20261104/drafts/retriage-result.json`, and the accepted pause shape in `MHS/changes/COMPANION-LOCKS.md` (erdalpekel/panda_simulation, profile `ros1-melodic-gazebo9`).
- **Status:** not integrated. Codex (gpt-6.1-sol) reviews safety and correctness afterwards.
- **What was run:** no hardware, Gazebo, ROS graph, network fetch or human review. The evidence is the fake backend.

## Why this package was blocked

`RESULT.json` was `blocked` on `HELPER_MISSING` after the previous model review removed the hector landing action as the e-stop. That review (kept intact in the notes) cites `pose_action.cpp:56-58`: a landing goal starts a pose goal that calls `enableMotors(true)`. `takeoff_action.cpp:59` does the same. Landing is an ordinary command again.

## The stop

`driver.py` binds `estop` to `/gazebo/pause_physics` (`std_srvs/Empty`, success path `$` equals `{}`) and `safe_state` to `/gazebo/get_physics_properties` with `pause` equals true. Companion lines, gazebo_ros 2.8.7 at `0667c5e52e8afa1f478955d8a2569b473a5acdf1`:

- advertise `pause_physics`: `gazebo_ros_api_plugin.cpp:462-468`
- `pausePhysics` calls `world_->SetPaused(true)` and returns true: `:1662-1666`
- `getPhysicsProperties` sets `res.pause` from `world_->IsPaused()`: `:1426`
- `unpausePhysics` exists at `:1668-1672` and is not bound

`getPhysicsProperties` sets success true only for the ODE engine (`:1433-1465`). A non-ODE read-back fails closed. The world's own `normal.world` uses ODE.

Version evidence uses the token `ROS Melodic` (`README.md:5`). `README.md:6` says other versions should also work, and the fidelity gap says so. The package starts `pkg="gazebo_ros"` itself from `src/mav_controller/worlds/normal.launch:32` (included by `3mavs.launch:11`). It does not include `gazebo_ros` `empty_world.launch`.

## No unpause (SAFE-042)

`velocity_controller.cpp:169` assigns `twist_command_.twist = *command`. `update()` applies `twist_limiter_(twist_command_.twist)` at `:207` and stamps the attitude, yawrate and thrust commands with the stored `twist_command_.header.stamp` at `:265-267`. That stamp does not advance. The attitude controller's `command_timeout` is 0.5 s (`params.yaml:4`, `attitude_controller.cpp:154-157`), so those outputs can drop after 0.5 s of simulation time, and the timeout does not clear `twist_command_`. `reset()` at `:110-118` empties the twist only when the motors are not running (`:196-199`).

`behaviour.cpp:577` publishes `cmd_vel` again, and `:591-592` sleeps on `ros::Rate`. `use_sim_time` is true, so that loop waits on the paused clock and publishes again when simulation time resumes. The behaviour node also calls `system("pkill -f ros")` at `:586-588`.

`safe_state` names the recovery: an operator stops the behaviour nodes and clears the stored twist outside MHS, then unpauses. This driver offers no `/gazebo/unpause_physics` binding. `mhs.safety.reset` releases the latch only and leaves the world paused.

## What else changed in the package

- The resource read is `{}`. `/uav1/ground_truth/state` (gazebo_ros p3d, silent while `World::Step` is paused, `World.cc:691-710`) stays the explicit read `x-cap.coppolam.odometry.v1`. The fake returns no odometry sample while paused.
- The `x-cap.coppolam.cmd_vel.v1` receipt adds `sent_linear_x`, `sent_linear_y`, `sent_linear_z` and `sent_angular_z` (`driver.py` `_SentReceipt`). They are the values handed to rosbridge, not a measurement. Limits stay `Limit.operator_required`. `site-limits.example.json` is an operator overlay, not a device fact.
- `enable_motors` stays ordinary. `enableMotorsCallback` (`quadrotor_hardware_gazebo.cpp:274-278`) returns true, and `enableMotors` sets `motor_status_.running` at `:280-283`. `writeSim` applies a wrench only while `motor_status_.on` and `motor_status_.running` (`:247`). That write runs from the gazebo_ros_control world-update begin hook, which does not run while the world is paused. The API plugin's `AsyncSpinner` (`gazebo_ros_api_plugin.cpp:149-151`) can still answer the service on wall time. The fake answers `enable_motors` while paused and does not move the placeholder pose.
- Landing while paused returns action status 4 and does not set `landed` or disable the motors. It is not a stop.
- Absolute `/uav1/...` names are the driver's deployment choice. `3mavs.launch` places the vehicle in group `ns` `uav1`. The hector sources use relative names.

## Lock companions

Both clones were already fetched. This unit did not write `$R/work/companions/LOCK.json`. `DEV/companions-root/` holds one symlink per clone directory, plus copies of `LOCK.json` and `README.txt`. The copy adds `gh.coppolam/ros_mav_swarm_simulator` to `needed_by` of `ros-simulation__gazebo_ros_pkgs@2.8.7` and `gazebosim__gazebo-classic@gazebo9_9.19.0` only. Symlinks are mode `0555` (`chmod -h a-w`) because the gate's writable check uses `lstat` and does not follow them. The clone targets were already `0555` and were not chmod'd.

The reviewed override `MHS/registry/overrides/companion-sources-lock.json` gains one entry for this package, inserted before `gh.erdalpekel/panda_simulation`. Its `justification` is one line of 176 characters (the override schema allows 240). The registry card and `task.json` carry the resolved companions and now say `package_status` `pass` with `blocked_on` `[]`. They are byte-identical. The repo record's evidence state is `contract_checked`, the adapter state is `runnable`, and the overlay digest is the gate digest below. Chinese catalogue fields were not rewritten. `python3 MHS/registry/build_registry.py` was not run: it reads the real `LOCK.json`, which does not list this package in `needed_by`.

## Tests and digest

`python3 -m unittest test_driver.MavSwarmCases` from the package directory: 17 cases, OK. The fake gate:

`python3 -m mhs.driver check MHS/drivers/robots/coppolam__ros_mav_swarm_simulator --backend fake --companions-root <DEV>/companions-root`

G1-G9 passed with no findings. Stable digest `sha256:f75f94e399327fd7d59fd607a4fc5bac4d5bbcab4a68745e7218ba6c2351eaa9`. The same digest was printed again after the card, `task.json` and `RESULT.json` were flipped to `pass`. `collect.py --strict` then passed this package with no warnings.

`RESULT.json` notes append one `MODEL REVIEW (grok-4.7, ...)` paragraph after the existing Claude paragraph. The author text before the first `MODEL REVIEW` was shortened at a word boundary and ends with ` [...]`. The Claude paragraph was not edited.

## Stopped attempts

Nothing was taken. The package trees under `development/p5-gz-pause/project` and `development/ext-p5-gz-pause.fast-stopped/project` matched snapshot-6. An unfinished override elsewhere used the README token `Install ROS Melodic`; this repair uses `ROS Melodic` (`README.md:5`).

## Round 1 review

Codex (high): the fidelity gap said `safety_status` re-reads the pause flag on request. `RosBridge.safety_status` (`mhs/bridge/ros.py:2227-2232`) returns the cached `_safe_state_achieved` flag and does not call a service. The gap and the facts.md Safety section now say that a status query cannot detect an external unpause or a WorldControl step. The e-stop test sets the fake `paused` flag false after a completed e-stop and checks that `safety_status` still reports `estop.confirmed` and `safe_state.achieved` with no new entry in `native.sent`. `reference.json` and `REFERENCE.md` were regenerated. The stable digest stayed `sha256:f75f94e399327fd7d59fd607a4fc5bac4d5bbcab4a68745e7218ba6c2351eaa9`: the gap text is not an input of that digest. G1-G9 passed again.

Grok (low): the `RESULT.json` prologue no longer states the author's earlier digest `sha256:4b3c429d4ab233140f881386868685bd9f1fe283832ef568851815abc676059d`, a resource read of `/uav1/ground_truth/state`, the landing action as the e-stop, or numeric `cmd_vel` bounds. Both `MODEL REVIEW` paragraphs are unchanged. The notes are 7395 characters.

## Not done

No SDK change. `REVIEW.md` was not edited. The full SDK suite was not run. `MHS/site/` was not regenerated. The real companions `LOCK.json` is unchanged until the orchestrator applies the `needed_by` widening after review.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/coppolam__ros_mav_swarm_simulator/RESULT.json`
- `MHS/drivers/robots/coppolam__ros_mav_swarm_simulator/driver.lock.json`
- `MHS/drivers/robots/coppolam__ros_mav_swarm_simulator/driver.py`
- `MHS/drivers/robots/coppolam__ros_mav_swarm_simulator/facts.md`
- `MHS/drivers/robots/coppolam__ros_mav_swarm_simulator/fake.py`
- `MHS/drivers/robots/coppolam__ros_mav_swarm_simulator/test_driver.py`
- `MHS/registry/overrides/companion-sources-lock.json (entry merged)`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
