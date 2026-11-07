# panda_gz_moveit2 stays blocked: the Galactic bridge cannot carry the Fortress pause

`andrejorsula/panda_gz_moveit2` stays `blocked` (`HELPER_MISSING`). The fetched lock companions were re-read. The Fortress world pause would hold physics while it is held, but the ROS 2 Galactic bridge this package pins cannot call that service or read `WorldStatistics.paused`. Deactivating the effort trajectory controller still writes the last effort, so it is not a stop. No unpause was added. No driver, lock, card or registry override changed. `reviewed_by` stays null.

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 as the package unit `ext-p5b-companions-new--andrejorsula__panda_gz_moveit2`. The orchestrator is Claude (claude-opus-5-5). Codex reviews afterwards. No hardware, Gazebo, ROS graph, network fetch or human review was run. The only evidence is the existing fake contract: the e-stop still ends `failed` with `MHS.SAFETY.SAFE_STATE_UNREACHED` and the latch held.

## What was asked

User decision 2 of `user-decisions-20261105b.json` allowed the companion clones this package needs. The re-triage entry (`drafts/retriage-result.json`, `robots/andrejorsula__panda_gz_moveit2`, class E) said to bind a Fortress `WorldControl` pause on `/world/default/control`, confirmed by `WorldStatistics.paused` (E2) through operator bridges (E3), with no unpause, because the effort controller keeps writing its last effort. Its note says that if the Galactic `parameter_bridge` cannot bridge `ControlWorld` and `WorldStatistics`, the package stays blocked. That entry has no separate verifier `verdict` object. `COMPANION-LOCKS.md` had already closed the controller-switch route: deactivating the effort controller leaves `ign_ros2_control` writing the last effort.

The package's own sources, read at the pin `8e5c6fd5d0d39ce2ad1d14968f86104f4ae0b9cb`:

- `README.md:11` and `Dockerfile:1`, `Dockerfile:16`: ROS 2 Galactic and Gazebo Fortress.
- `panda_ign_moveit2.repos:2-5`: `ros_ign` at `galactic`.
- `panda_moveit_config/launch/ex_ign_control.launch.py:41` starts Ignition Gazebo with `-r`. Lines 76-88 start `ros_ign_bridge` `parameter_bridge` for `/clock` only. Lines 101-105 default the world argument to `default.sdf`.
- `panda_moveit_config/config/controllers_effort.yaml` (cited by the existing driver) uses the effort command interface.

## The pause exists in ignition-gazebo 6, and this package cannot call it

`gazebosim__gz-sim@ignition-gazebo6_6.18.0` (`work/companions/LOCK.json`: profile `ros2-humble-gzsim6`, `needed_by` is tortoisebot only) is the Fortress simulator:

- `src/SimulationRunner.cc:214` advertises the `control` service.
- `OnWorldControl` at lines 1120-1177 copies the request onto a queue and sets the Boolean reply true immediately. The reply confirms nothing.
- `ProcessWorldControl` at line 1242 applies `pause`. Lines 1245-1249 unpause when `multi_step` is set, so a pause binding would have to send `pause` true and no step. Another client can still step the world.
- `PublishStats` at line 430 sets `WorldStatistics.paused`. The run loop still calls `Step` while paused (line 746). `PublishStats` (line 827) runs before `ProcessMessages` (line 868). Statistics are throttled to 10 per second (lines 643-651).
- `src/systems/physics/Physics.cc:855-856` steps only when the world is not paused.

That is a pause of the physics step, the same shape TortoiseBot binds through E2 and E3. It is not on this package's ROS graph.

The bridge the repos file names is the fetched clone `gazebosim__ros_gz@0.233.4` (ros_ign 0.233.4, profile `ros2-galactic-gzsim6`, already in `needed_by` for this package):

- `ros_ign_bridge/README.md:6-7` says there is no support for service calls. The type table that follows does not list `WorldControl` or `WorldStatistics`.
- `ros_ign_bridge/src/parameter_bridge.cpp:41-63` documents topic arguments only (`topic@ROS2_type` then `@`, `[` or `]` and an Ignition type). There is no service form.
- `ros_ign_bridge/src/factories/ros_ign_interfaces.cpp:31-85` converts `JointWrench`, `Entity`, `Contact`, `Contacts` and `Light`, then returns null.
- `ros_ign_interfaces/msg/` contains `WorldControl.msg` and does not contain `WorldStatistics.msg`. `ros_ign_interfaces/srv/ControlWorld.srv:1-3` exists and is not registered with the bridge.
- `ros_ign_gazebo` has no ROS service for world control. Its launch file `ros_ign_gazebo/launch/ign_gazebo.launch.py:31-35` only forwards `ign_args`.

`gazebosim__ros_gz@0.244.27` (Humble) does list `ros_gz_interfaces/msg/WorldStatistics` and `ros_gz_interfaces/srv/ControlWorld` (`ros_gz_bridge/README.md:55` and `:78`). Its LOCK profile is `ros2-humble-gzsim6`, and its `needed_by` is tortoisebot. This package's README and Dockerfile name Galactic. `MHS/handoff/REVIEW.md` item 13 requires the companion profile to be the distro the package serves. `needed_by` was not widened, and no `operator_bridges` entry was declared. A Humble bridge on a Galactic graph would also be a second bridge beside the launch's `ros_ign_bridge` clock bridge, with different message package names (`ros_gz_interfaces` against `ros_ign_interfaces`).

No unpause, as a re-enable or as an ordinary command. `ign_ros2_control` `PreUpdate` always calls `controller_manager_->write()` (`ign_ros2_control_plugin.cpp:467-469` in `AndrejOrsula__ign_ros2_control@devel`). `IgnitionSystem::write` copies `joint_effort_cmd` into `JointForceCmd` on every write (`ign_system.cpp:444-457`). An unpause would apply that stored effort again. The served command is an unacknowledged `JointTrajectory` publication. It cannot clear that effort before the world steps. `REVIEW.md` item 5 and the SAFE-042 condition forbid that unpause. Recovery, if an operator pauses the world outside MHS, stays outside MHS: stop Servo and move_group, then decide how the arm is held, then unpause. This package does not perform those steps.

The launch's world argument defaults to the string `default.sdf`. `examples/worlds/default.sdf:15` in the ignition-gazebo 6.18.0 clone names its world `default`. The Galactic launch file does not show that the string resolves to that file, so `/world/default/control` was not assumed. The missing bridge already closes the route.

## The effort switch is still not a stop

Read on the clones `LOCK.json` already lists for this package:

- `AndrejOrsula__ros2_controllers@jtc_effort`, `joint_trajectory_controller/src/joint_trajectory_controller.cpp:805-812`: `on_deactivate` comments "How to halt when using effort commands?" and writes each command interface's current value back. It does not zero the effort.
- `ros-controls__ros2_control@1.6.0`, `controller_manager/src/controller_manager.cpp:164-166`: `switch_controller` is served. Its effect on this controller is that deactivate.
- The hardware write above keeps applying `joint_effort_cmd` on every `PreUpdate`, including after the controller has released its interfaces.

That matches the earlier preflight. It was not reopened.

## What changed

`RESULT.json` `notes` only. `authored_by` stays `deepseek-v4.1-flash:1017` / `ros-wave-c-066`. One paragraph was appended, headed `MODEL REVIEW (grok-4.7, a model and not a human, 2026-11-05; reviewed_by stays null):`. The notes field is at most 8,000 characters. The author's text before the first `MODEL REVIEW` paragraph was shortened at a sentence boundary and ends with ` [...]`. The 2026-11-05 Claude review paragraph was not edited. Status stays `blocked`, `blocked_on` stays `HELPER_MISSING`, and `gate.digest` stays `sha256:f0129ee598b478af4e03506beb65dfeb636ac115d2be10449272b329b2fa040e`. The driver was not regenerated.

Nothing was taken from the stopped attempts. `development/p5b-companions-new/project` does not exist. The package files under `development/ext-p5b-companions-new.fast-stopped/project` match this unit's base copies.

No SDK change, so there are no new tests and no mutants. No `LOCK.json` edit and no `DEV/companions-root`. Risk stays R2 (an arm, `REVIEW.md` item 12). `publish_review` stays `not_required` (BSD-3-Clause).

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/andrejorsula__panda_gz_moveit2/RESULT.json`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
