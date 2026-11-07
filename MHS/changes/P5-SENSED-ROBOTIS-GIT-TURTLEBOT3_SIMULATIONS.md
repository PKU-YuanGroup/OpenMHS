# Sensed-confirmation stop for robotis-git/turtlebot3_simulations

Repair of `MHS/drivers/robots/robotis-git__turtlebot3_simulations` only (SAFE-049, CORE-088). The package was blocked `HELPER_MISSING`: the pinned `turtlebot3_fake_node` has no acknowledged stop. It now declares `safety_bindings["sensed_stop"]` for the fake node in simulated mode. `RESULT.json` status is `pass`. Evidence is fake `contract_checked` only. No ROS graph, simulator process, or hardware was run.

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 in this unit's copy. Run id `ext-p5-sensed--robotis-git__turtlebot3_simulations-20261105`. This is a repair, so `driver.lock.json` keeps `authored_by` (`deepseek-v4.1-flash:1017`, run `ros-wave-c-055`, date `2026-11-04`, lines 21-26). `reviewed_by` stays null (line 27). No human reviewed it.

## What changed

- `driver.py`: class risk `R2` (line 264) and `publish_velocity` risk `R2` (line 444). `device_kind` stays `world.sim` (line 259). `safety_bindings = {"sensed_stop": _SENSED_STOP}` (line 487). `estop_latency_ms = 3500` (line 346). `watchdog_ms` stays 1000 (line 272).
- The request (`driver.py` lines 222-227) is one all-zero `geometry_msgs/msg/Twist` on `/cmd_vel`, with `source_name` `cmd_vel` and `source_ref` `turtlebot3_fake_node.cpp:48-50`. The callback stores `linear.x` and `angular.z` and returns void (`cpp:135-146`). The publication is transmission only.
- The source is `/odom` (`driver.py` lines 229-236): `source_name` `odom`, `source_ref` `cpp:43`, `type_ref` `hpp:49`, `stamp_path` `header.stamp` (`cpp:165-166`), `throttle_ms` 50, `fill_refs` for `pose.pose.position` (`cpp:228-230`) and `pose.pose.orientation` (`cpp:235-238`). History is `{"durability": "volatile", "ref": "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:40-43"}`. Those lines assign `KeepLast(10)` and pass it to the odom `create_publisher`. The span has no `transient_local`. The fixture has no `history` key; the citation is the declaration.
- The predicate (`driver.py` lines 237-246) is pose-only `span_max` on `pose.pose.position.x`, `pose.pose.position.y`, `pose.pose.orientation.z`, and `pose.pose.orientation.w` (`rest_x`, `rest_y`, `rest_qz`, `rest_qw`). Each threshold is `Limit.operator_required` (`_NO_REST_BOUND`, lines 85-87). Units are `m` for x and y and `1` for the quaternion components. `consecutive` 5, `min_span_ms` 200, `max_gap_ms` 500, `confirm_within_ms` 1500 (lines 247-250). `(5 - 1) * 50 ms = 200 ms`, and the span check is a strict less-than, so 200 ms meets 200 ms. Five samples at the node's 10 ms timer (`cpp:59`) span 40 ms and cannot.
- `safe_state` (lines 338-343) names only that window. The zero Twist proves nothing. Another `/cmd_vel` publisher can move the base again. Nothing is claimed past the window.
- Ten facts were added (`driver.py` lines 314-336) and copied into `facts.md`. They cover the QoS span, the stamp, the pose writes, the odometry step, the wheel defaults of 0.0 (`cpp:88-89`), `burger.yaml:3-5`, the fake-node launch (`launch.py:60-75`), and `turtlebot3_drive.cpp:42` and `:98-104`.
- `fake.py`: `FakeTurtlebot3Simulations` starts at a placeholder 0.2 m/s. A publish records the Twist and does not store a new pose. An `/odom` burst emits the stored sample first, then steps a placeholder unicycle only while the goal is non-zero, and stores the rest only when both goal components are 0 and no competing publisher is set. Stamps advance by `throttle_rate` when the subscribe sets it. Switches cover a competing publisher, an ignored zero, a silent stream, a missing twist, a bad pose type, silent joint states, frozen stamps, a null pose field, and NaN joint velocities (`nan_wheel_velocity`, `fake.py` lines 64-67 and 102-103). Every number is marked `# placeholder`.
- `fixtures/estop-confirmation.json`: placeholders `rest_x` 0.01, `rest_y` 0.01, `rest_qz` 0.001, `rest_qw` 0.001. No `history` key.
- `reference.json` and `REFERENCE.md` were regenerated with `python3 -m mhs.driver reference` after the `source_name` edit and again after the wheel-geometry correction, each time before the passing gate.
- `RESULT.json`: status `pass`, `blocked_on` `[]`, `gate.failed` `[]`, `gate.digest` `sha256:0c6c4c0eab3325aeb324be3f162e34025be77380de9b27643d7d6ac723ae8251`. Notes are 7999 characters. The author's text before the first `MODEL REVIEW` was shortened at a word boundary and ends ` [...]`. The earlier paragraph, from its `MODEL REVIEW (claude-opus-5-5` head through the end of that paragraph, is 2036 characters and byte-equal to the pre-edit paragraph. One new paragraph was appended, headed `MODEL REVIEW (grok-4.7, a model and not a human, 2026-11-05; reviewed_by stays null): `. The round-1 gate printed the same digest, so that paragraph was not rewritten.
- `task.json` is unchanged. `package_status` stays `blocked` (line 25). The card `expected_mode` is `simulated` (line 50) and `risk_floor` is `R0` (line 51), so declaring R2 is inside the floor. `site-limits.example.json` and `driver.lock.json` are unchanged.
- The passing `python3 -m mhs.driver check ... --backend fake` wrote `check-report.json` in the package. That file is not part of the tree. It was moved to `moved-aside/robotis-git__turtlebot3_simulations-check-report.json` (relative to this unit directory, outside `project`). `collect.py` calls the gate with `--no-report` (`MHS/handoff/tools/collect.py` line 83) and did not write it back.

## Why this shape

User decision 2 of 2026-11-05 allows a request plus sensed confirmation for simulators only. The card mode is simulated. There is no `estop_terminal`, no unpause, and no re-enable. The comment at `driver.py` lines 490-491 says reset re-confirms the `/odom` window and publishes nothing. That reset is the SDK's read-only path. `test_driver.py` `test_a_reset_reconfirms_without_a_request_and_resumes_nothing` checks a successful reset, and `test_a_reset_is_refused_while_another_publisher_moves_the_base` checks a refused reset. Neither resumes a stored motion command (SAFE-042).

Class risk and the publication are R2 because `/cmd_vel` is also a physical TurtleBot3 command topic (`driver.py` lines 261-264 and 449). `device_kind` stays `world.sim`. The other hardware repository is not cited as a `Fact`.

`turtlebot3_drive` is in this clone. It publishes Twist on `cmd_vel` (`turtlebot3_drive.cpp:42` and `:98-104`). No launch file in the clone starts it. A competing publisher, a teleop node, or Nav2 keeps the pose moving, and the confirmation fails closed (`driver.py` lines 384-388). The 1 s watchdog (`cpp:157-161`) is a second path. The confirmation does not read it and does not rely on it (`driver.py` lines 389-390).

Wheel geometry (`driver.py` lines 373-382, and the same text in `reference.json` `fidelity.gaps`): `cpp:194` divides each wheel speed by `wheel_radius_`. `cpp:204-210` replace a NaN wheel increment with 0. `cpp:215` multiplies by `wheel_radius_`. `cpp:216` multiplies by `wheel_radius_` and divides by `wheel_seperation_`. Both defaults still 0 and a zero command make `delta_theta` NaN, and the pose becomes non-finite. Radius 0 with separation 0.160 and a zero command keeps `delta_s` and `delta_theta` at 0, so the pose stays finite while the wheel velocities stay NaN. A non-zero command with radius 0 makes `delta_s` non-finite (`0 * inf` is NaN; `isnan(inf)` is false, so `cpp:204-210` do not replace an infinite increment). The pose-only confirmation does not read joint velocities and does not validate wheel geometry. A finite stationary pose still confirms. `test_driver.py` `test_zero_radius_with_a_nonzero_separation_stays_finite_and_still_confirms` restates `cpp:193-221` and then completes the e-stop while `fake.py` publishes NaN joint velocities.

The request step sets no `timeout_ms`, so it uses `RosDriver.timeout_s` (2.0 s). `estop_latency_ms` 3500 covers 2000 ms plus `confirm_within_ms` 1500 (`driver.py` lines 344-346).

The pose-only window follows the same kind of `span_max` stop used for `karthik0497/ros2-amr-simulation`. That package's driver declares `operator_required` history (`driver.py` line 231). Its fixture fills a volatile placeholder (`fixtures/estop-confirmation.json` lines 9-13). This package cites volatile history, so its fixture has no history key. That name is only in this record.

## Taken from the stopped attempts

From the stopped Grok draft at `development/ext-p5-sensed.fast-stopped/project`, after checking the clone lines: the pose-only predicate and the `cpp:40-43` history citation. That draft's `throttle_ms` 100 with `consecutive` 3 was not used. From the stopped Claude draft at `development/p5-sensed/project`: nothing. Its twist `abs_max` terms and `min_span_ms` 150 were not used. No file was copied verbatim.

## Gate

`python3 -m mhs.driver check MHS/drivers/robots/robotis-git__turtlebot3_simulations --backend fake` exited 0. G1 through G9 passed. The printed line was `gate digest (RESULT.json gate.digest): sha256:0c6c4c0eab3325aeb324be3f162e34025be77380de9b27643d7d6ac723ae8251` and then `PASS: evidence contract_checked`. The same command after the wheel-geometry correction exited 0 with the same digest. The digest is the stable check report. The gap text is not a finding, so correcting it did not move the digest. G9 ran `test_driver.py`, including `test_zero_radius_with_a_nonzero_separation_stays_finite_and_still_confirms`. A direct run of that test was `Ran 1 test in 0.097s OK`.

`python3 MHS/handoff/tools/collect.py --strict MHS/drivers/robots/robotis-git__turtlebot3_simulations` exited 0 and printed `PASS gh.robotis-git/turtlebot3_simulations RESULT.json=pass` and `1 of 1 package(s) pass the gate; 0 with warnings`.

The digest before this repair, while the package was blocked on G6, was `sha256:6f917dd7ccd6b2997ffc4d6b911ced4dd951124bf951443aca8f52c8197a5124`. The change from blocked to pass is intended. The earlier note `sha256:196b478cc338ff0c78bab8ecca38f9ae995749c78f1e5054dd6afaae7e578f2b` is a clocked report digest from the blocked run, not `gate.digest`.

Package tests that failed and were fixed before the passing run: a subscribe assertion read `throttle_rate` from the last `/odom` subscribe, which is an unthrottled post-stop read (`KeyError`); the test now requires exactly one `/odom` subscribe whose `throttle_rate` is 50. The first full module run then failed G7 `ROS_ENDPOINT_NOT_UPSTREAM` because the request step had no `source_name` and the cited lines show the relative name `cmd_vel`. `source_name` `cmd_vel` was added (`driver.py` line 223) and the reference files were regenerated. The following importlib run of `test_driver.py` was `Ran 20 tests in 25.077s OK`.

No SDK file, registry override, or lock companion was edited. The pre-edit package directory is in `originals/packages/robotis-git__turtlebot3_simulations` under this unit directory.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/robotis-git__turtlebot3_simulations/RESULT.json`
- `MHS/drivers/robots/robotis-git__turtlebot3_simulations/driver.py`
- `MHS/drivers/robots/robotis-git__turtlebot3_simulations/facts.md`
- `MHS/drivers/robots/robotis-git__turtlebot3_simulations/fake.py`
- `MHS/drivers/robots/robotis-git__turtlebot3_simulations/test_driver.py`
- `MHS/drivers/robots/robotis-git__turtlebot3_simulations/fixtures/estop-confirmation.json`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
