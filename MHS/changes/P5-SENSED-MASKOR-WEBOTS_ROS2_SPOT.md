OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Sensed-confirmation stop for maskor/webots_ros2_spot

Repair of `gh.maskor/webots_ros2_spot` only. `authored_by` stays the deepseek record in `driver.lock.json` (`deepseek-v4.1-flash:1017`, `ros-wave-c-031`, 2026-11-04). `reviewed_by` stays null. This file was written by Grok (grok-4.7, a model and not a human) on 2026-11-05. No hardware run, Webots run, ROS graph, or human review is claimed. The gate evidence is `contract_checked` on the fake backend.

## What changed

The package was blocked `HELPER_MISSING` after the 2026-11-05 review removed an e-stop that treated `/Spot/lie_down` as a stop. User decision 2 of 2026-11-05 asks for a request plus sensed confirmation on simulated cards. The e-stop is now `safety_bindings["sensed_stop"]` (SAFE-049, CORE-088).

Request steps, fixed, with no `args` and no `result`:

1. `/Spot/float_mode` (`std_srvs/srv/SetBool`, `data: false`). The callback assigns `request.data` and returns `success` true for every request (`webots_spot/spot_driver.py:763-767`). The service is registered at `webots_spot/spot_driver.py:220`. Float mode must be cleared first: `step` runs `float_motion` whenever `float_mode` is set, before it checks `fixed_motion` (`webots_spot/spot_driver.py:943-944`), and `float_motion` applies `previous_cmd_vel` (`webots_spot/spot_driver.py:779-781`).
2. `/Spot/lie_down` (`webots_spot_msgs/srv/SpotMotion`, `override: true`). The callback sets `fixed_motion` and, with override, returns `lying down` (`webots_spot/spot_driver.py:662-672`). That string is the step's success predicate. It is not the stop. The ordinary `x-cap.maskor.lie_down.v1` command remains.

The source is `/Spot/odometry` (`nav_msgs/msg/Odometry`). `header.stamp` is a `builtin_interfaces/Time` built from Webots `getTime()` (`webots_spot/spot_driver.py:478-481`) and assigned at line 577. The predicate reads `pose.pose.position` (`webots_spot/spot_driver.py:579-581`) and `pose.pose.orientation` (`webots_spot/spot_driver.py:582-586`): `span_max` on x, y and each quaternion component, and a range on z. It does not read twist. The second publish in one step can carry a zero finite difference after `previous_rotation` is stored (`webots_spot/spot_driver.py:571-573`). Every threshold is `Limit.operator_required`. The clone states no at-rest bound and no lying height band. `fixtures/estop-confirmation.json` holds fake placeholders only (`lying_z` 0.05 to 0.25, `rest_x` and `rest_y` 0.05, and `still_qx` through `still_qw` at 0.05). Those quaternion numbers are component spans, not radians. History is volatile, cited at the publisher `create_publisher(Odometry, "/Spot/odometry", 1)` (`webots_spot/spot_driver.py:201`). The line shows integer depth 1 and does not say `transient_local`.

Client bounds, fake-scale, not device facts: `consecutive` 3, `min_span_ms` 200, `max_gap_ms` 500, `confirm_within_ms` 3000, `throttle_ms` 100, each step `timeout_ms` 2000, `estop_latency_ms` 7000. `min_span_ms` 200 matches the fake's 100 ms producer ticks, so three counted samples span 200 ms. A 32 ms producer (`webots_spot/spot_driver.py:161`) puts three one-step samples 64 ms apart and needs a lower `min_span_ms` in `simulation_deployment["estop_confirmation"]` (the floor is 0). A live simulation whose Webots step is slower than `max_gap_ms`, or whose one-second lie (`movement_decomposition(..., 1)` at `webots_spot/spot_driver.py:670`) outlasts `confirm_within_ms`, fails closed until the operator raises those two bounds there. `throttle_ms` stays on the declaration. The deployment and the fixture cannot replace it.

There is no `estop_terminal`, no `reenable`, and no safe-state action. Reset re-confirms read-only and does not clear `previous_cmd_vel`. `/cmd_vel` stores that twist and clears `fixed_motion` (`webots_spot/spot_driver.py:361-363`). Gait input clears `fixed_motion` (`webots_spot/spot_driver.py:403-404`). Webots is not paused. SpotArm (`launch/spot_launch.py:20-88`) is not stopped. Risk stays R2. The licence stays AGPL-3.0 and `publish_review` stays required. This unit did not publish.

## The duplicate stamp

The verifier's missing piece: once `lie_down` sets `fixed_motion`, `defined_motions` calls `handle_transforms_and_odometry` (`webots_spot/spot_driver.py:701-702`) and `step` calls it again (`webots_spot/spot_driver.py:950`). There is no `robot.step` between those calls (`webots_spot/spot_driver.py:943-950`). The first call stores `previous_rotation` and `previous_translation` and skips the odometry publish (`webots_spot/spot_driver.py:558-560`). That call still publishes `/joint_states` (`webots_spot/spot_driver.py:613`). Once `previous_rotation` exists, both calls in one `step` publish `/Spot/odometry` (`webots_spot/spot_driver.py:575-593`) and assign `header.stamp` at line 577 from the `Time` built at `478-481`. This repair reads those two odometry publishes as one stamp. The clone has no line that says `getTime()` stays fixed inside one controller step. The plug-in timestep is 32 ms (`webots_spot/spot_driver.py:161`). The clone's Python contains no `robot.step`.

`throttle_ms` 100 is sent as rosbridge `throttle_rate` with `queue_length` 1 (`mhs/bridge/ros.py`). The SDK does not throttle. rosbridge `QueueMessageHandler` (`rosbridge_library/internal/subscription_modifiers.py`) overwrites a copy that is still queued and forwards a copy that arrives after the first was published, once `throttle_rate` milliseconds have elapsed. The fake models that clock. It does not run rosbridge. Copies that share an arrival time collapse to one sample, and the still-base burst then confirms. `straddle_publish` delivers the second copy after the first, and the equal stamp is `sensed_stale`. With `honor_throttle` false the window's `last_reset` is `duplicate` and the stop is `sensed_stale` (15 samples seen). That duplicate-stream regression stays.

`nav_launch.py` includes `nav2_bringup` (`launch/nav_launch.py:37-50`). Any publisher of `/cmd_vel` clears `fixed_motion`. This clone's `params/nav2_params.yaml` contains no `cmd_vel` string. This record does not state that nav2 publishes `/cmd_vel`.

## Checks

`python3 -m unittest MHS/drivers/robots/maskor__webots_ros2_spot/test_driver.py`: 21 tests, OK in 64.264s. `python3 -m mhs.driver check MHS/drivers/robots/maskor__webots_ros2_spot --backend fake` printed `gate digest (RESULT.json gate.digest): sha256:b7d0c44011e253aa069b5f5f2fa2463cd4ab4da16d821accd430b8d45bc4170c` and `PASS: evidence contract_checked` (`generated_at` 2026-11-06T04:21:12.069Z). Comments in `driver.py`, the safety prose in `facts.md`, and this repair's MODEL REVIEW paragraph were then tightened: the first `handle_transforms_and_odometry` call skips the odometry publish and still publishes `/joint_states`. The author notes before the first MODEL REVIEW paragraph were shortened at a word boundary, ending ` [...]`, so the notes are 7,993 characters. `python3 -m mhs.driver reference` left `reference.json` and `REFERENCE.md` byte-identical. A second check printed the same digest line and `PASS: evidence contract_checked` (`generated_at` 2026-11-06T04:32:44.915Z), G1-G9 pass, including repository tests. `python3 MHS/handoff/tools/collect.py --strict` on this package then passed, 1 of 1, 0 warnings. `python3 MHS/handoff/tools/show_refs.py` after that re-check reported 33 citations and 0 bad.

The digest equals the clean-pass digest named in the original author notes. `stable_digest` hashes the gate report without its clock, and both reports are a clean G1-G9 pass. The declaration is not that report. The blocked digest was `sha256:1f65691ec76b05d514a8084d736b91b012ac7f4561ca6ec17cbac2d65245f58c` (G6 and G8 failed).

Mutant, then restored: `FakeWebotsRos2Spot.honor_throttle` default set to false. `test_the_estop_is_confirmed_on_throttled_odometry` failed with status `failed`, `MHS.SAFETY.SAFE_STATE_UNREACHED`, sensed reason `sensed_stale`, `last_reset` `duplicate`, `seen` 15. The default was restored to true before the digest run.

`task.json` and `MHS/registry/tasks/robots/maskor__webots_ros2_spot.json` were not edited. They still say `package_status` blocked and `blocked_on` `HELPER_MISSING`. The package `RESULT.json` says pass. PLAYBOOK leaves the card for the integrator. No SDK file, no registry override, and no companion `LOCK.json` was edited.

## Stopped attempts

Compared before any edit. `development/p5-sensed/project/MHS/drivers/robots/maskor__webots_ros2_spot` and `development/ext-p5-sensed.fast-stopped/project/MHS/drivers/robots/maskor__webots_ros2_spot` were byte-identical to this package. Nothing was taken from either.

## Round 1 review

Both high findings and the medium and low findings were fixed. The predicate adds `span_max` on `pose.pose.orientation.x/y/z/w` (`still_qx` through `still_qw`), each `Limit.operator_required`. Twist is not a predicate path. A rotating base stays `not_confirmed`, and reset is `MHS.SAFETY.RESET_REFUSED` both during that attempt and after a completed stop once rotation starts. The latch stays held.

The fake no longer drops one copy whenever `throttle_rate` is present. `forward_rosbridge_queue` follows rosbridge `QueueMessageHandler`: copies that share an arrival time are queued before the publish, so length 1 keeps the last; a copy that arrives after the first was published is forwarded after `throttle_rate` milliseconds. `straddle_publish` produces equal-stamp pairs and the stop is `sensed_stale`. `honor_throttle` false still delivers both copies and stays the duplicate regression. The confirming burst still uses one sample per stamp.

`min_span_ms` 200 is documented as the fake's 100 ms tick span. A 32 ms producer needs a lower `min_span_ms` in `simulation_deployment["estop_confirmation"]`. `max_gap_ms` and `confirm_within_ms` remain the two bounds for a slow step or the one-second lie. `throttle_ms` stays on the declaration. The fidelity gap no longer says the shared stamp is because Webots advances time in `robot.step`. It says this package reads the two publishes as one stamp and that the clone does not say `getTime()` stays fixed.

`python3 -m unittest MHS/drivers/robots/maskor__webots_ros2_spot/test_driver.py` before the final comment and notes edits: 25 tests, OK in 88.704s. After those edits, `python3 -m mhs.driver check MHS/drivers/robots/maskor__webots_ros2_spot --backend fake` printed `gate digest (RESULT.json gate.digest): sha256:b7d0c44011e253aa069b5f5f2fa2463cd4ab4da16d821accd430b8d45bc4170c` and `PASS: evidence contract_checked` (`generated_at` 2026-11-06T05:18:07.021Z). G1-G9 pass, including repository tests (G9). `python3 MHS/handoff/tools/show_refs.py` reported 34 citations and 0 bad. The digest is again the clean-pass digest, because `stable_digest` hashes the gate report without its clock. The notes are 7,999 characters. The author text before the first MODEL REVIEW was shortened again at a word boundary, ending ` [...]`. The first MODEL REVIEW paragraph is unchanged. `reviewed_by` stays null. No hardware, Webots, rosbridge, or human review is claimed. `python3 MHS/handoff/tools/collect.py --strict` on this package then passed, 1 of 1, 0 warnings.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/maskor__webots_ros2_spot/RESULT.json`
- `MHS/drivers/robots/maskor__webots_ros2_spot/driver.py`
- `MHS/drivers/robots/maskor__webots_ros2_spot/facts.md`
- `MHS/drivers/robots/maskor__webots_ros2_spot/fake.py`
- `MHS/drivers/robots/maskor__webots_ros2_spot/test_driver.py`
- `MHS/drivers/robots/maskor__webots_ros2_spot/fixtures/estop-confirmation.json`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
