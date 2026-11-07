# Sensed-confirmation stop for autorally/autorally

Repair of `MHS/drivers/robots/autorally__autorally` (`gh.autorally/autorally`), simulated card only (SAFE-049, CORE-088). `driver.lock.json` keeps `authored_by` `deepseek-v4.1-flash:1017`, run `ros-wave-c-133`, and `reviewed_by` null. The package directory was not moved aside. This file is the repair record, not a second authorship.

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05, run id `ext-p5-sensed--autorally__autorally-20261105`. No ROS graph, Gazebo process, simulator, hardware, network, install, or human review was run. The evidence is the fake backend only: `contract_checked`.

## Starting point

`RESULT.json` was `blocked` on `HELPER_MISSING`. The recorded gate digest was `sha256:a52070034ed5fba49e959d327f79a606944a908db15a2ba72fbdc9b9bfe1e6ff`, with G6 and G8 failed on `SAFE_STATE_UNREACHED`. The clone has no stop service or action. `/runstop` with `motionEnabled` false is an unacknowledged publication. The Gazebo controller ANDs every sender (`autorally_gazebo/nodes/autorally_controller.py:435-440`) and forces throttle to 0 while the AND is false (`:345-348`).

The verifier's correction for this package (retriage, not refuted) is the sensed-confirmation stop: request, then confirmation on `/wheelSpeeds`. The safer alternative for the old free-sender runstop capability is an input-free re-enable with the sender fixed, replacing that capability.

## Stop request (SAFE-049 and SAFE-042)

`safety_bindings` is only `sensed_stop` (`driver.py:546`). The request is two fixed publications, in order (`driver.py:231-252`):

1. `std_msgs/Float64` `data` 0.0 on `/constantSpeedController/speedCommand` (`driver.py:233-241`). `ConstantSpeedController.cpp:100-107` stores that Float64 and sends no acknowledgement. When the stored value is not greater than 0.1, the next wheelSpeeds callback sets `chassisCommand.throttle` to 0 (`ConstantSpeedController.cpp:149-153`). This step is the clear of the setpoint this package commands. It runs before confirmation, so a later re-enable does not resume the setpoint this stop replaced.
2. `autorally_msgs/runstop` `{sender: openmhs, motionEnabled: false}` on `/runstop` (`driver.py:243-251`).

The triager's note describes one publication. The second step is the package-owned runstop. The first step is added so the re-enable below does not resume a stored speed this driver can clear. Both steps are fixed, idempotent, and have `timeout_ms` 1000. There is no `history` field: this is ROS 1, and a history key would be a definition error. The bridge discards the first sample of a ROS 1 subscription.

Confirmation reads `/wheelSpeeds` (`autorally_msgs/wheelSpeeds`, publisher `autorally_controller.py:299`, stamp `rospy.Time.now()` at `:571`, `lfSpeed` / `rfSpeed` / `lbSpeed` / `rbSpeed` assigned at `:575-583`). The predicate is `abs_max` on all four fields, each `Limit.operator_required` (`driver.py:270-279`). Client bounds (`driver.py:280-283`): `consecutive` 3, `min_span_ms` 200, `max_gap_ms` 500, `confirm_within_ms` 2000. `estop_latency_ms` is 4000 (`driver.py:403`), the two step timeouts plus `confirm_within_ms`. `throttle_ms` on the source is 100 (`driver.py:261`). These numbers are fake-scale. A live simulation supplies thresholds and client bounds in `simulation_deployment['estop_confirmation']`. Consecutive may only rise. The fake placeholders are `fixtures/estop-confirmation.json` (`lf_speed`, `rf_speed`, `lb_speed`, `rb_speed` at 0.05). They are not device facts.

`safe_state` (`driver.py:397-400`) states the same simulated contract. `chassisState` is not the confirmation source.

## Re-enable (CORE-086)

`x-cap.autorally.runstop.v1` is removed from `commands` and `actions` (`driver.py:492-497`). `x-cap.autorally.release_runstop.v1` (`driver.py:518-530`) is `Action(reenable=True)` with no input. It publishes only `{sender: openmhs, motionEnabled: true}` (`driver.py:204-211`). The latch refuses it. Reset does not run it: a reset of this sensed stop re-reads `/wheelSpeeds` and refuses `MHS.SAFETY.RESET_REFUSED` when the predicate no longer holds. The re-enable publishes no second speed zero.

Residual, disclosed in the fidelity gaps (`driver.py:432-436`) and in the re-enable description (`driver.py:522-527`):

- The speed zero is unacknowledged. Wheel speeds under the bound do not prove the stored setpoint is still 0, because a false runstop forces throttle 0 even if a later `speedCommand` arrived. A speed published after the stop's zero is applied when sender `openmhs` becomes true.
- `m_integralError` is initialized to 0 (`ConstantSpeedController.cpp:55`) and updated only while `data` is greater than 0.1 (`:120-138`). This stop does not clear it.
- `chassisCommandPriorities.yaml:1-6` gives `constantSpeedController` priority 2 and `joystick` priority 4. The controller sorts ascending (`autorally_controller.py:258-259`), so a fresh constant-speed command is considered before joystick.
- `JoystickControl.cpp:55-56` starts `motionEnabled` false, and `README.md:141-143` says the gamepad node publishes that false at startup. `getrunstop` ANDs every sender, so releasing `openmhs` leaves motion disabled while joystick is false. The default simulation launch includes that joystick node.
- The constant-speed controller publishes steering `-5`, which the controller rejects (`abs` greater than 1), so joystick steering can still apply.
- The four axle controllers are `effort_controllers/JointEffortController` (`autoRallyPlatformJointCtrlrParams.yaml:34-48`). Effort 0 coasts. The runstop applies no brake. Samples that are already inside the bound also confirm, so the predicate does not show that this stop caused the slowdown.
- `AutoRallyChassis.cpp:64-101` and `autorally.launch` serve the same topics on the real car. Risk stays R2 (`driver.py:295-297`). The real platform is out of scope. `publish_review` stays required; the lock licence is `NOASSERTION`.
- `setupEnvVariables.sh:31` exports `AR_CONFIG_PATH`. The launch file loads whatever path the operator exported. The declaration assumes the shipped `autorally_util` config and an empty `vehicle_prefix`.

If a reviewer rejects the unacknowledged zero as a clear, the fail-closed alternative is to remove the re-enable and leave recovery outside this package. This repair keeps the re-enable and states that limit.

## Fake, resource state, and tests

`fake.py` is a ROS-free `RecordingRosTransport`. An empty sender set means enabled, matching `getrunstop`. While the runstop AND is false, or the stored target is not above 0.1, the placeholder wheel magnitude decays and then stays at 0 (`fake.py:122-124`) so two later resource reads hash the same. While motion is enabled and the target is above 0.1, the magnitude equals `abs(target)` (`fake.py:115-116`). That echo is a placeholder, not the Gazebo plant. It exists so two speed commands change resource state (G8 TCAP-003). `competing_speed` holds the wheels at a coast magnitude even after the stop. The four wheel speeds are resource fields and reads (`driver.py:477-490`) as well as the confirmation source. `task.json` is unchanged, so the registry card stays the blocked input until the integrator rebuilds it.

`test_driver.py` keeps `check_driver`. The local cases cover the chassis and wheel reads, the speed publication, absence of the free-sender capability, `LIMITS_UNSET` without an overlay, a latched speed command, withheld chassis and wheel samples, a confirmed estop (both publications, then the speed command refused), a read-only reset, a reset refused while the wheels stay fast, a competing publisher, a silent source (`sensed_missing`), a repeated stamp (`sensed_stale`), a null `lfSpeed` (`sensed_invalid`), the re-enable refused while latched and input-free after reset, a joystick sender that keeps the AND false, a speed stored during the hold and applied after re-enable, and wheels that are already still.

On 2026-11-05 the 19 cases other than `test_gate` passed (12.419 s). `python3 -m mhs.driver check MHS/drivers/robots/autorally__autorally --backend fake` then passed G1 through G9. The gate printed digest `sha256:9a772a3fbe7bb629e282cf6e0e5c22d226ac70a20605917a9aa3ee83f6f5a66e`. `reference.json` and `REFERENCE.md` were regenerated from that driver before the passing gate. `RESULT.json` records status `pass`, `blocked_on` `[]`, `failed` `[]`, and that digest. The catalogue entry `x-cap.autorally.runstop.v1` is replaced by `x-cap.autorally.release_runstop.v1`. The author's notes were shortened on a word boundary, still ending with ` [...]`, immediately before `LIMITS AND OVERLAY`. The Claude review paragraph of 2026-11-05 is unchanged. One new paragraph was appended, headed `MODEL REVIEW (grok-4.7, a model and not a human, 2026-11-05; reviewed_by stays null): `.

## What was not taken, and what was not edited

`development/p5-sensed/project` and `development/ext-p5-sensed.fast-stopped/project` were compared with `DEV/originals/packages/autorally__autorally` (`diff -q`, exit 0 both). Those trees matched the pre-edit package. Nothing was copied from them. The originals directory still matches `base-manifest.json` for this package.

Unchanged: `driver.lock.json`, `task.json`, `site-limits.example.json`, the SDK, `REVIEW.md`, registry overrides, and lock companions. No shared edit.

## Round 1 review (2026-11-06)

Codex blocked the re-enable. `x-cap.autorally.release_runstop.v1` published only `{sender: openmhs, motionEnabled: true}`. `ConstantSpeedController.cpp:100-107` keeps the last Float64 and sends no acknowledgement. `autorally_controller.py:345-348` forces throttle to 0 while the runstop AND is false and does not clear that Float64. `README.md:170` tells the operator to run a `speedCommand` publisher at rate 10, so another node can overwrite the stop's zero, and a lost zero is not stored. Wheel speeds can confirm while the old target remains. REVIEW.md item 13: where the stored command cannot be cleared before an unpause, the package offers no re-enable, and `safe_state` says how the operator recovers outside MHS. The capability, its action, and its catalogue entry are removed (`driver.py:493-497`, `driver.py:395-400`). A new speed command is still only a Float64 publication. It does not publish `/runstop`. `test_a_lost_speed_zero_still_holds_and_mhs_has_no_reenable` and `test_an_overwritten_speed_zero_stays_held_without_a_reenable` cover the two probes. The earlier test that accepted resumption after re-enable is gone.

The cmd_timeout fact no longer says the controller centers steering. `autorally_controller.py:328-334` calls `_ctrl_axles(0.0, 0.0, 0.0)` and `_ctrl_steering(self._last_steer_ang, 0.0, 0.001)`. `_ctrl_steering` (`:497-515`) sets `theta` to the passed angle when the velocity limit is not greater than 0, and it updates `_last_steer_ang` only when `theta` differs, so that call leaves the steering angle unchanged (`driver.py:330-334`). The publish fact no longer says every loop iteration. The publishes at `:399-412` are inside `elif delta_t > 0.0` (`:335`). The timeout branch does not publish them (`driver.py:317`, ref `:328-412`).

`reference.json` and `REFERENCE.md` were regenerated. The 20 package cases other than `test_gate` passed (12.436 s). The fake gate passed G1-G9 again and printed the same digest `sha256:9a772a3fbe7bb629e282cf6e0e5c22d226ac70a20605917a9aa3ee83f6f5a66e`: a passing report with no findings does not change that digest. `RESULT.json` stays `pass`. A second model-review paragraph, dated 2026-11-06, was appended. The Claude paragraph and the 2026-11-05 Grok paragraph were not edited. The author's notes were shortened again on a word boundary, still ending with ` [...]`. `reviewed_by` stays null. No ROS graph, Gazebo process, simulator, or hardware was run.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/autorally__autorally/RESULT.json`
- `MHS/drivers/robots/autorally__autorally/driver.py`
- `MHS/drivers/robots/autorally__autorally/facts.md`
- `MHS/drivers/robots/autorally__autorally/fake.py`
- `MHS/drivers/robots/autorally__autorally/test_driver.py`
- `MHS/drivers/robots/autorally__autorally/fixtures/estop-confirmation.json`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
