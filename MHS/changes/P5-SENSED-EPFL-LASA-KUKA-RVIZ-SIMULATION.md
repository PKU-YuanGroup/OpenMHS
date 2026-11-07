OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# P5 sensed-confirmation stop: epfl-lasa/kuka-rviz-simulation

Repair of the simulated ROS 1 package `MHS/drivers/robots/epfl-lasa__kuka-rviz-simulation` (SAFE-049, CORE-088). The package stays a repair: `driver.lock.json` `authored_by` is still `deepseek-v4.1-flash:1017`, run `ros-wave-c-116`, date 2026-11-05, and `reviewed_by` stays null. One model-review paragraph was appended to `RESULT.json` notes. No human review is claimed.

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 in this unit's copy (`development/ext-p5-sensed--epfl-lasa__kuka-rviz-simulation/`). Nothing was taken from the stopped attempts under `development/p5-sensed/project` or `development/ext-p5-sensed.fast-stopped/project` (no `sensed_stop` for this package was found there). No hardware run, ROS graph, rosbridge session, simulator run, network, install or human review is involved. Evidence is `contract_checked` on the fake backend only.

## What changed

The package was blocked `HELPER_MISSING` because a zero-velocity publication is not an acknowledged stop. It now declares one `safety_bindings["sensed_stop"]` and no `estop` or `safe_state` binding and no safe-state action (`driver.py` `_SENSED_STOP` and `safety_bindings`).

The request is one fixed publication of seven zeros on `/r_arm_vel/command` (`iai_control_msgs/MultiJointVelocityImpedanceCommand`, `timeout_ms` 500). The request proves nothing by itself. The source is `/r_arm_vel/state` (`pr2_controllers_msgs/JointTrajectoryControllerState`). `ros_version` is 1, so the source declares no `history`; the bridge discards the first sample of the new subscription. Stamps are `header.stamp` `secs`/`nsecs` and must strictly increase.

The predicate is seven `abs_max` terms on `desired.velocities.0` through `desired.velocities.6` and one `norm_max` over `actual.velocities.0` through `actual.velocities.6`. Every threshold is `Limit.operator_required`. The clone assigns those fields and states no numeric tolerance and no at-rest bound:

- `multi_joint_velocity_impedance_controller.cpp:128-130` constructs the state publisher on the relative topic `"state"`.
- `multi_joint_velocity_impedance_controller.cpp:199` assigns `desired.velocities[j] = command[j]` (the applied command, after the watchdog at `:169-177`).
- `multi_joint_velocity_impedance_controller.cpp:201` assigns `actual.velocities[j] = joints_[j]->velocity_`.
- `multi_joint_velocity_impedance_controller.h:53` includes `pr2_controllers_msgs/JointTrajectoryControllerState.h`.
- `multi_joint_velocity_impedance_controller.h:52` includes the command type.

`desired.velocities` is the applied command, not a plant measurement. The watchdog zeroes that command after silence (`:169-177`, period `0.1` at `:44-46`). Silence is not this stop. The comment at `:172` ("set desired velocities to zero to stop joints") is the watchdog, not an acknowledgement.

Client bounds, fake-scale only: `consecutive` 2, `min_span_ms` 40, `max_gap_ms` 500, `confirm_within_ms` 800. `estop_latency_ms` is 1300, the 500 ms request timeout plus `confirm_within_ms`. A live simulation fills thresholds and bounds in `simulation_deployment["estop_confirmation"]`. `fixtures/estop-confirmation.json` is read by the fake backend only: `desired_v0` through `desired_v6` are 0.0 and `actual_norm` is 0.02. Those numbers are placeholders, not device facts.

`safe_state` states the same stop in one sentence under the 500-character field cap. The realtime `/joint_states` disclosure, the watchdog, and the competing publishers are in the fidelity gaps (`driver.py`) and in `facts.md` under Safety. There is no unpause and no re-enable (SAFE-042). A reset reconfirms the sensed state read-only. When that state no longer holds, reset is `MHS.SAFETY.RESET_REFUSED`.

`lwr_simulation.launch` also starts `lasa_to_iai_parser` (`lasa_to_iai.py:59-70`) and `r_arm_pos_controller` (`lwr_sim_pos_controllers.launch:6-14`, `jcontroller.py:118-145`). Either can publish on `/r_arm_vel/command` after this package's zeros. The fake's `competing_command` switch keeps desired and actual at a nonzero placeholder, so the stop stays `not_confirmed` with the latch held. This package does not clear a command those nodes store. Operator recovery is outside MHS.

`lwr_realtime.launch` (realtime defaults to true) and `lwr2_realtime.launch` republish a real arm's `/KUKA/joint_states` as `/joint_states`. The sensed source is `/r_arm_vel/state`, not `/joint_states`. Those realtime launches do not start this velocity controller. The SDK cannot prove a ROS graph is simulated. A real controller of this class behind `/r_arm_vel/command` would act on the same publication. Risk stays R2.

The loopback integrates `commanded_effort_` (`multi_joint_velocity_impedance_controller.cpp:180-188`, `loopback_controller_manager.cpp:210-226`). This clone does not show `commanded_effort_` being cleared each cycle, and whether the external `pr2_controller_manager` clears it is not in the pin. The comment `for perfect sim: chose p=m/dt with damping=0` (`lwr_sim_vel_controllers.yaml`) is cited as written. It is not treated as one-step tracking. The fake sets measured velocity equal to the commanded velocity at once and says so. That echo is not the loopback.

Existing `/joint_states` reads, the velocity publication, the operator-required velocity limit, the catalogue extension requests, the pin `66448f9e8995b557335b6b51c9ab6ed6c5afd99d` and the lock were left in place. `task.json` was not edited. The registry was not rebuilt, so the card, `records.csv` and the repo json can still say blocked / `HELPER_MISSING` until the integrator rebuilds. `RESULT.json` status is pass, `blocked_on` is empty, and `gate.digest` is the stable digest of the passing fake-backend check (`sha256:04dbf55a4717db0207b93eab59455254e6a22072719baa8f6bf79de6438c1a69` from the check report written before `collect.py`). The author's notes still open with the original BLOCKED text; the part after the limits sentence was shortened at a word boundary with ` [...]` so the new review paragraph fits the 8000-character notes cap. The earlier Claude review paragraph was not shortened.

## Tests

`test_driver.py` covers the declaration (sensed_stop only, no history, seven zero velocities, `estop_latency_ms` 1300), a confirmed stop that then refuses a velocity invoke with the latch held, a reset that reconfirms with no further publication and `resumed` false, a reset refused while a competing publisher is on, an unconfirmed competing publisher (`last_reset` `term`) even though the recorded command is zeros, an unsettled actual velocity (`not_confirmed`), silence (`sensed_missing`), a repeated stamp (`sensed_stale`) and a null measured velocity (`sensed_invalid`). The gate's own sensed filters (withheld samples, frozen stamp, null predicate field) are G6, not a substitute for those cases.

No SDK change. No lock-companion change. No shared edit.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/epfl-lasa__kuka-rviz-simulation/RESULT.json`
- `MHS/drivers/robots/epfl-lasa__kuka-rviz-simulation/driver.py`
- `MHS/drivers/robots/epfl-lasa__kuka-rviz-simulation/facts.md`
- `MHS/drivers/robots/epfl-lasa__kuka-rviz-simulation/fake.py`
- `MHS/drivers/robots/epfl-lasa__kuka-rviz-simulation/test_driver.py`
- `MHS/drivers/robots/epfl-lasa__kuka-rviz-simulation/fixtures/estop-confirmation.json`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
