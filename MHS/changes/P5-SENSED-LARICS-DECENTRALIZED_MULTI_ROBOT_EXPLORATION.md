OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# P5 sensed stop: larics/decentralized_multi_robot_exploration

Repair of the blocked package `gh.larics/decentralized_multi_robot_exploration` to a sensed-confirmation stop (SAFE-049, CORE-088). This unit is that package only. `authored_by` stays `deepseek-v4.1-flash:1017`, run `ros-wave-c-114`, date 2026-11-05. `reviewed_by` stays null. Written by Grok (grok-4.7, a model and not a human) on 2026-11-05, run `ext-p5-sensed--larics__decentralized_multi_robot_exploration-20261105`. Evidence is fake `contract_checked` only. No ROS graph, Stage process, simulator or hardware was run.

## Decision

User decision 2 of 2026-11-05 (`work/handoff-runs/claude-20261104/user-decisions-20261105.json`) allows a request plus a sensed confirmation for simulators only. The decision's own list does not name this package. The orchestrator assigned the package to this unit, and that assignment is the coverage used here.

## What changed

The package was blocked `HELPER_MISSING` because `cmdvelReceived` forwards a Twist to `ModelPosition::SetSpeed` and publishes nothing back (`stage_ros_private/src/stageros.cpp:273-280`). The e-stop is now `safety_bindings["sensed_stop"]` only:

- Two fixed zero Twists, on `/robot_0/cmd_vel` and `/robot_1/cmd_vel`. The relative name is `#define CMD_VEL "cmd_vel"` (`stageros.cpp:68`). The subscription is `stageros.cpp:373`.
- Two sources, `/robot_0/odom` and `/robot_1/odom` (`#define ODOM "odom"` at `stageros.cpp:65`). `SubscribeModels` advertises them with queue length 10 and no latch argument (`stageros.cpp:371`).
- ROS 1, so no history. The bridge discards the first sample of a sensed source.
- Ten terms, all `Limit.operator_required`: per robot, `abs_max` of `twist.twist.linear.x`, `linear.y` and `angular.z`, and `span_max` of `pose.pose.position.x` and `position.y`. `WorldCallback` assigns those fields at `stageros.cpp:539-545`.
- Client bounds, a package choice for the fake: `consecutive` 3, `min_span_ms` 200, `max_gap_ms` 500, `confirm_within_ms` 1500. Each request step times out at 1000 ms. `estop_latency_ms` is 3500.
- `fixtures/estop-confirmation.json` holds placeholder thresholds (speeds 0.05, spans 0.02). They are not device facts. A live simulation sets its own in `simulation_deployment['estop_confirmation']`.

`interval_sim 100` is at `frontier_exploration/stage-worlds/pioneer3dx-sick.world:321` and that line states no unit. `stage_ros_private/world/willow-erratic.world:61` comments that `interval_sim 100` is a simulation timestep in milliseconds. `max_gap_ms` 500 sits above one such update. A slower-than-realtime run fails closed until the operator raises `max_gap_ms`.

## What the stop does not prove

The zero Twist proves nothing. `WorldCallback` zeroes every position model only when `base_watchdog_timeout` is greater than 0 and the simulated time since the last command reaches it (`stageros.cpp:443-448`). The parameter defaults to 0.2 s when unset (`stageros.cpp:288-291`). A value of 0 disables the clamp. The confirmation can therefore succeed without the zero Twist having been applied. The fake's `watchdog_rest` switch shows that case: the samples report rest while the stored speed stays nonzero.

The shipped world has three position models, `pioneer0`, `pioneer1` and `pioneer2` (`pioneer3dx-sick.world:296-319`). This stop commands and senses only `robot_0` and `robot_1`. `pioneer2` is zeroed only by the watchdog.

`MoveBase` advertises `geometry_msgs::Twist` on the relative `cmd_vel` topic (`navigation/move_base/src/move_base.cpp:91-92`). `navigation.launch` starts `move_base` in the robot namespace. The assigner calls `sendGoal` (`frontier_exploration/scripts/decent_robot_assigner.py:246`); that line does not publish `cmd_vel`. A competing publisher fails the confirmation closed. Nothing watches the robots after the window.

`cb_reset_srv` sets every position model to its initial pose and clears `SetStall`, then returns true, and does not set the commanded speed to zero (`stageros.cpp:260-268`). `safety_bindings.reset` is not declared (SAFE-042). `fidelity.reset` is `"none"`. The MHS reset re-confirms the sensed stop and changes nothing on the models. `reset_positions` is not offered as a command or as a re-enable. The fake still answers the service and does not zero velocity, so the test can show the speed is left in place.

## Risk and publication

Device risk and both `cmd_vel` actions are R2. `MHS/handoff/REVIEW.md` item 12 (lines 117-123): a `cmd_vel` topic that a physical mobile base would also consume follows that mobile base's hazard, however simulated the deployment. `device_kind` stays `world.sim`. The card's `risk_floor` stays R0 (`task.json`). This unit does not edit the registry card or `task.json`. The card still says blocked until the integrator rebuilds it. `publish_review` is `required` and `license_spdx` is `NOASSERTION` (`task.json`). The owner decides publication.

The served manifest mode is what grants the stop. `MHSServer._sdk_ros_route_class` (`MHS/sdk/src/mhs/server.py:9692`) requires the SDK's `call`. This package does not override `call`, `make_bridge`, `inner`, `estop`, `safety_status` or `_run_safe_state`. The SDK does not prove that a live graph is simulated.

## The cmd_vel effect

An earlier draft of this repair overrode `DecentralizedMultiRobotExploration.call` to copy `linear_velocity` and `angular_velocity` into the receipt. That override is not the SDK ROS route, so the sensed report was dropped. It was removed. `RosBridge._invoke` returns `{"published": True, "confirmed": False}` for a publication with no `then` (`MHS/sdk/src/mhs/bridge/ros.py:1344`). The result map cannot read the command input. TCAP-003 therefore sees the effect in the resource state. `robot_0_twist` and `robot_1_twist` are read-only fields. Each is `twist.twist` from the first sample of a new subscription of that robot's odometry topic. The fake stores the last Twist it accepted on that robot's `cmd_vel` and reports it there. That echo is not `GetVelocity` and not a Stage measurement. A live subscriber receives the next `WorldCallback` publish, and the `cmd_vel` command does not wait for that publish.

## Gate

`python3 -m mhs.driver check MHS/drivers/robots/larics__decentralized_multi_robot_exploration --backend fake` passed G1-G9 with no findings. The digest is `sha256:0d1ee551989c0fae173005fd77e14934b0873a7c41376c746c4e22566d7bc1db` (before, while blocked: `sha256:31ea4480f079ed3ff2e5c12d311a2d0828913addcbf11c21d1dcd225230c1d71`). G6's withhold, frozen and null filters (`MHS/sdk/src/mhs/driver/behaviour.py:737-739`) are part of that pass: a fail-open stop would be `SENSED_FAIL_OPEN`. `collect.py --strict` on this package passed with no warnings. The package tests are the 21 tests in `test_driver.py`, including that gate.

Nothing was taken from `development/p5-sensed/project` or from `development/ext-p5-sensed.fast-stopped/project` in the phase-5 handoff run. Those trees were compared by hash; neither supplied a file copied into this package.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/larics__decentralized_multi_robot_exploration/RESULT.json`
- `MHS/drivers/robots/larics__decentralized_multi_robot_exploration/driver.py`
- `MHS/drivers/robots/larics__decentralized_multi_robot_exploration/facts.md`
- `MHS/drivers/robots/larics__decentralized_multi_robot_exploration/fake.py`
- `MHS/drivers/robots/larics__decentralized_multi_robot_exploration/test_driver.py`
- `MHS/drivers/robots/larics__decentralized_multi_robot_exploration/fixtures/estop-confirmation.json`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.

The integrator removed one absolute home-directory path from the Gate section. The sentence still names `development/p5-sensed/project` and `development/ext-p5-sensed.fast-stopped/project`. The copy from before this edit is in `development/ext-integrator-A/originals/`.
