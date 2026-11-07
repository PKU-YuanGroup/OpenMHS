# P5-MIXED-ROBIN-SHAUN-XTDRONE — world-pause e-stop for the XTDrone position subset

Repair of `robots/robin-shaun__xtdrone` (`gh.robin-shaun/xtdrone`, pin
`671f3d45b22bfe4b7f2b23ae8d4251f3172781b3`) by grok-4.7, a model and
not a human, on 2026-11-05, run id `ext-p5-mixed--robin-shaun__xtdrone-20261105`.
This is a repair. `authored_by` stays the existing model record
(`deepseek-v4.1-flash:1017`, run `mhs-ros-continuation-20261102-b-retry1-019`,
date 2026-11-04) in `driver.lock.json`. `reviewed_by` stays null. Evidence is
`contract_checked` on the ROS-free fake. No hardware run, no simulator run, and
no human review is claimed.

The pre-edit package directory is copied at
`development/ext-p5-mixed--robin-shaun__xtdrone/originals/packages/robots/robin-shaun__xtdrone/`.

## What changed

Before: status `blocked`, `blocked_on` `HELPER_MISSING`, gate failure
`G6.ESTOP_FAILED`, digest
`sha256:e0aa3aada3663d2fab85115aa7dcdf97f2b2911ccc03dda0ec0badc0cec7ffad`.

After: status `pass`, `blocked_on` empty, G1-G9 pass on `--backend fake`, digest
`sha256:1edf366c664cae548b4550cdb7c0982ddb847a175fe827ba7b70ddb0c41353e3`.
The digest move is intended (rule 14): the package was blocked and now passes
this stop. `collect.py --strict` on this package printed
`PASS gh.robin-shaun/xtdrone RESULT.json=pass` and `1 of 1 package(s) pass the gate; 0 with warnings`.
A later recompute of `mhs.driver.check.stable_digest` on the collect-rewritten
`check-report.json` matched the recorded digest.

The accepted surface is the typhoon_h480_0 position-setpoint subset plus the
vendored gazebo_ros 2.8.7 world pause.

- E-stop: `/gazebo/pause_physics` (`std_srvs/Empty`). Advertised at
  `sitl_config/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:508-514`.
  Handler `pausePhysics` calls `World::SetPaused(true)` and returns true at
  `:1738-1742`. Type at
  `sitl_config/gazebo_ros_pkgs/gazebo_ros/test/ros_network/gazebo_network_api.yaml:85-86`.
  Binding: `driver.py` `_PAUSE` (lines 42-53). `timeout_ms` 500. Success is an
  empty `std_srvs/Empty` response (`path` `$` equals `{}`).
- Read-back: `/gazebo/get_physics_properties` (`gazebo_msgs/GetPhysicsProperties`).
  Advertised at `gazebo_ros_api_plugin.cpp:389-395`. `res.pause = world_->IsPaused()`
  at `:1484`. Type at `gazebo_network_api.yaml:55-56`. Field `bool pause` at
  `gazebo_msgs/srv/GetPhysicsProperties.srv:4`. Binding: `driver.py` `_READBACK`
  (lines 55-66). Confirmed only when `pause` is true. `timeout_ms` 500.
- `safety_bindings` is exactly `estop` and `safe_state` (`driver.py:397`). There
  is no reset binding, no re-enable, no stall, no fresh window, and no
  `estop_latency_ms`. `safe_state` is the 310-character string at `driver.py:270-274`.
- No unpause. `unpause_physics` exists at `gazebo_ros_api_plugin.cpp:517-523`
  and `:1744-1748` and is not bound. SAFE-042: `communication/multirotor_communication.py:55-61`
  republishes `target_motion` until shutdown, and `:149-151` ignores the exact
  string `stop controlling` and the empty string. This package cannot clear that
  retained target. `mhs.safety.reset` releases the MHS latch and leaves the
  world paused (`test_driver.py` `test_the_reset_keeps_the_world_paused_and_a_new_setpoint_is_not_observed`).
  The operator recovers outside MHS.
- Pose and target left the device resource (`driver.py:334-351`). They remain
  explicit subscribe reads. A paused lockstep world may publish nothing
  (`sitl_config/models/typhoon_h480/typhoon_h480.sdf:1270-1288` sets
  `enable_lockstep` true). The fake's silence while paused is that assumption,
  not a measured PX4 trace.
- The setpoint receipt adds `sent_x`, `sent_y`, and `sent_z` after the inner
  bridge call (`driver.py` `_SentReceipt`, lines 119-139, `make_bridge` at
  399-400). Those fields are the values handed to rosbridge. `confirmed` stays
  false. This is the TCAP-003 effect once the resource reads no topic.
- Class risk and the setpoint action are R2 (`driver.py:155` and `:367`).
  REVIEW.md item 12: a MAVROS setpoint is R2. `README.en.md:7` says algorithms
  can be deployed to real UAVs. The pause service itself is the simulator world
  pause. `device_kind` stays `robot.mobile_base`. `resource_id` stays `vehicle`.
  Position bounds stay `Limit.operator_required`. `site-limits.example.json` is
  unchanged example test data.
- The previous `open_native` refusal of every non-fake backend was removed so
  the sim backend falls through to `RosDriver.open_native`, as other RosDrivers
  do. A hardware backend still requires a human signature in `driver.lock.json`.
  This package does not claim that signature. Tests do not call
  `load_driver(..., "sim")`.

## Scope (verifier's safer alternative)

The 2026-11-05 verifier called the repair feasible, with one scope caveat, and
named a documentation path: record that arming and OFFBOARD are done outside
MHS, and do not add arm or mode actions. This repair takes that path.

The services are citable and are not bound:

- `communication/multirotor_communication.py:50` builds
  `vehicle_type+'_'+vehicle_id+"/mavros/cmd/arming"` (`CommandBool`).
- `:51` builds `.../mavros/set_mode` (`SetMode`).
- `communication/plane_communication.py:40-41` builds the same
  `vehicle_type+'_'+vehicle_id` prefix and the same `/mavros/cmd/arming` and
  `/mavros/set_mode` suffixes.
- `sitl_config/launch/multi_vehicle.launch:22` fixes namespace `typhoon_h480_0`.

The earlier claim that G7 cannot cite those services is dropped. Velocity,
acceleration, landing, and state stay outside the accepted surface. The
acceleration callbacks pass `ax`/`ay`/`az` into a constructor that accepts
`afx`/`afy`/`afz` (`multirotor_communication.py:67` and `:127-139`) and stay
unsupported.

The 2026-11-04 gpt-6 MODEL REVIEW paragraph is kept verbatim in `RESULT.json`.
Its instruction not to accept a position-only surface is superseded for this
stop by the 2026-11-05 verifier's safer alternative. The command surface stays
the position subset. The stop is the world pause, not a claim that the position
subset is a full flight workflow. `NATIVE-BLOCKERS.md` is rewritten in place as
that scope record.

## Fail closed

The fake (`fake.py`, class `FakeXtdrone`) answers the two services immediately.
`fail_pause` returns no pause reply. `fail_readback` returns `result` false.
That is the non-ODE path: `gazebo_ros_api_plugin.cpp:1484` sets `res.pause`
from `world_->IsPaused()`, and `:1516-1523` sets `res.success` false and
returns false without assigning `pause`. The SDK rejects a service response
whose `result` is not true before it reads `pause`
(`MHS/sdk/src/mhs/bridge/ros.py:1028-1029`). `ignore_pause` is only another
client leaving `pause` false. Each leaves the e-stop `failed` with `SAFE_STATE_UNREACHED` and a
later setpoint `ESTOP_ENGAGED`
(`test_driver.py:131-140`). `fail_publish` raises `ConnectionError` in `send`
before the transport records the publish. An unknown service, including
`/gazebo/unpause_physics`, returns `result` false and is never called by the
package.

`empty_world.launch` defaults `physics` to `ode` (`:15`). `multi_vehicle.launch:14-20`
includes that file and does not pass `physics`. The default world
`$(find mavlink_sitl_gazebo)/worlds/empty.world` (`multi_vehicle.launch:7`) is
not in this clone. If `enable_ros_network` is false, `advertiseServices` returns
without advertising (`gazebo_ros_api_plugin.cpp:274-277`) and the e-stop fails
closed. The member and `empty_world.launch:22` default that flag to true.

The pause covers every vehicle in the world, including `typhoon_h480_1`
(`multi_vehicle.launch:51-52`). This package commands only `typhoon_h480_0`.
The Gazebo GUI (`empty_world.launch:51-54` starts `gzclient` when `gui` is true;
`multi_vehicle.launch:9` defaults `gui` to true) or any client of
`unpause_physics` can unpause, and MHS does not watch the flag after the e-stop.
`safety_status` returns the cached confirmation from the last successful
read-back and does not call `get_physics_properties` again
(`MHS/sdk/src/mhs/bridge/ros.py:2199-2232`), so it cannot detect that unpause.
The read-back runs inside the e-stop (`ros.py:2099`) and inside `safe_state`
(`ros.py:2110-2115`).

Version evidence in the clone: vendored gazebo_ros 2.8.7 (`package.xml:4`),
changelog header `2.8.7 (2020-05-01)` (`CHANGELOG.rst:5`, which does not name a
distro), catkin (`package.xml:22`), README link on `melodic-devel`
(`gazebo_ros_pkgs/README.md:11`), and `docs/RELEASE.md:19` listing ROS Melodic
with Gazebo 9. This package claims no Noetic build. The deployment must run a
ROS 1 gazebo_ros that serves these services, such as this vendored 2.8.7.
gazebo_ros is inside the clone, so the citations are ordinary clone paths. No
lock companion and no `LOCK.json` edit.

`task.json` is unchanged, so it still byte-matches the registry card. The card's
`package_status` stays `blocked` until a later registry rebuild. This unit did
not run `build_registry.py` or `prepare.py --sync`. No SDK file, registry
override, REVIEW.md text, or spec text was edited.

## Checks

Package cases, loaded with `SourceFileLoader` as `XtdroneTyphoonCases` only
(the gate file's `test_gate` was left to G9): 14 tests, OK in 2.170s, on the
first repair. Review round 1 added the cached-status case and the same loader
ran 15 tests, OK in 2.179s. During that run,
`test_target_observation_reflects_the_published_setpoint` printed an
evidence-log-closed traceback from server teardown and still reported ok.
That traceback is the SDK evidence log (`mhs/evidence.py:624`), not a failed
assertion. `python3 -m mhs.driver reference` rewrote `reference.json` and
`REFERENCE.md` again after the fidelity and plane-fact edits.
`python3 -m mhs.driver check ... --backend fake`: G1-G9 pass, evidence
`contract_checked`. The stable digest stayed
`sha256:1edf366c664cae548b4550cdb7c0982ddb847a175fe827ba7b70ddb0c41353e3`,
so `RESULT.json` `gate.digest` was not rewritten. `check-report.json` has no
severity warning. `python3 MHS/handoff/tools/show_refs.py` on this package:
exit 0, zero `!!` marks (`python3 -m mhs.driver show_refs` is not a subcommand
in this tree). `python3 MHS/handoff/tools/collect.py --strict` on this package
only: 1 of 1, 0 warnings, re-run after the round-1 edits. No SDK suite was
run. No SDK mutant was written. The three fail-closed switches above are
package tests.

## Stopped attempts

Nothing was taken. Both stopped trees exist. A search of each copy of this
package's `driver.py` for `pause_physics`, `safety_bindings`, and
`get_physics_properties` found no hits:

- `development/p5-mixed/project`
- `development/ext-p5-mixed.fast-stopped/project`

## Files

Changed in the package: `driver.py`, `fake.py`, `test_driver.py`, `facts.md`,
`NATIVE-BLOCKERS.md`, `RESULT.json`. Generated: `reference.json`, `REFERENCE.md`,
`check-report.json`. Unchanged: `driver.lock.json`, `task.json`,
`site-limits.example.json`. `RESULT.json` notes keep the author's BLOCKED
paragraph and the gpt-6 MODEL REVIEW paragraph, and append one paragraph whose
head is `MODEL REVIEW (grok-4.7, a model and not a human, 2026-11-05; reviewed_by stays null): `.
Review round 1 did not append another paragraph and did not edit the existing
ones: the digest did not move, and those paragraphs do not contain the
re-read claim.

## Review round 1 (2026-11-05)

Codex and a separate Grok session both marked the fidelity gap false.
`driver.py` had said `safety_status` re-reads the pause flag on request.
`RosBridge.safety_status` (`MHS/sdk/src/mhs/bridge/ros.py:2199-2232`) returns
`estop.native` and `safe_state.achieved` from `_safe_state_achieved`,
`_safe_stamp`, and the settled-effects check. It performs no service call.
The read-back runs inside `estop` (`ros.py:2099`, `_perform_safety` of
`estop` and `safe_state`) and inside `safe_state` (`ros.py:2110-2115`).
The gap now says the confirmation is the last successful read-back and that
`safety_status` cannot detect an external unpause. The same sentence is in
`facts.md` and `NATIVE-BLOCKERS.md`. `reference.json` and `REFERENCE.md`
were regenerated from the driver. `test_driver.py`
`test_safety_status_keeps_the_cached_confirmation_after_an_external_unpause`
sets the fake `paused` flag false after a completed e-stop and checks that
`safety_status` stays engaged, confirmed, and achieved, with no new wire
message.

The plane fact at `driver.py` and the matching `facts.md` row now state the
`vehicle_type` and `vehicle_id` prefix that
`communication/plane_communication.py:40-41` concatenates. The services stay
unbound.

`ignore_pause` is documented as another client leaving `pause` false.
`fail_readback` is the non-ODE `result` false return. Those lines do not
assign `pause` false (`gazebo_ros_api_plugin.cpp:1484` then `:1516-1523`).

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/robin-shaun__xtdrone/NATIVE-BLOCKERS.md`
- `MHS/drivers/robots/robin-shaun__xtdrone/RESULT.json`
- `MHS/drivers/robots/robin-shaun__xtdrone/driver.py`
- `MHS/drivers/robots/robin-shaun__xtdrone/facts.md`
- `MHS/drivers/robots/robin-shaun__xtdrone/fake.py`
- `MHS/drivers/robots/robin-shaun__xtdrone/test_driver.py`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
