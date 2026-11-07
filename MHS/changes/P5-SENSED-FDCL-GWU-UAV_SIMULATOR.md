# P5 sensed-confirmation stop for fdcl-gwu/uav_simulator

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 in this package unit's copy. This is a repair of the existing package. `authored_by` stays `deepseek-v4.1-flash:1017` (run `ros-wave-c-025`, date 2026-11-04). `reviewed_by` stays null. No hardware, ROS graph, Gazebo process, simulator run or human review is claimed. The gate evidence is `contract_checked` on the ROS-free fake.

## What changed

`MHS/drivers/robots/fdcl-gwu__uav_simulator` was blocked on `HELPER_MISSING` because it declared no stop (gate failed G6 and G8, digest `sha256:a5eff26e9bc3ac3376200849e073eb5ad78ad526c17f8f062033e07c67c9cd28`). It now declares `safety_bindings["sensed_stop"]` only (SAFE-049, CORE-088).

The request is one fixed `std_msgs/Bool` false on `/uav/motors_on` (`control.py:537-541`, import `control.py:11`, `timeout_ms` 2000). ControlNode stores `motor_on` from `msg.data` (`control.py:585-586`) and assigns a zero force and a zero torque when `motor_on` is false or `mode` is below 2 (`control.py:245-251`). That publication proves nothing.

The source is `/uav/gps` (`nav_msgs/Odometry`, `estimator.py:289-293`, import `estimator.py:12`). The predicate reads Gazebo-frame `pose.pose.position.x`, `y` and `z`. `gps_callback` reads `pose.pose.position` at `estimator.py:333` and `twist.twist.linear` at `estimator.py:334`, then converts to NED at `estimator.py:337-338`. The predicate does not use the NED values. Three fresh samples must have `z` at or below the operator's landed band and `x`, `y` and `z` still. Client bounds: `consecutive` 3, `min_span_ms` 200, `max_gap_ms` 500, `confirm_within_ms` 4000. `estop_latency_ms` is 6000, the request timeout plus the confirmation window.

`/uav/states` is not a source. `publish_states` (`estimator.py:350-361`) assigns position, velocity, acceleration, angular velocity and attitude and does not assign `header.stamp`.

History is `operator_required`. The publisher is `libgazebo_ros_p3d`, outside the clone. `uav.urdf.xacro:53-61` remaps `odom` to `uav/gps` and sets `frame_name` world, `gaussian_noise` 0.01 and `update_rate` 10, and it states no QoS. `README.md:61` names Ubuntu 22.04 and ROS 2 Iron. No Iron `gazebo_ros` companion is fetched, and the fetched companion of another release is not cited.

Both thresholds are `operator_required`. `trajectory.py:62` `landing_motor_cutoff_height` -0.25 is an NED desired height, not a `/uav/gps` z bound. The spawn `z` 0.2 (`uav_gazebo.launch.py:47-52`) is a start pose. `gaussian_noise` 0.01 is sensor noise, and the URDF does not say which p3d fields it applies to. Placeholders for the fake only are in `fixtures/estop-confirmation.json`: `landed_z.max` 0.5, `rest_x`, `rest_y` and `rest_z` 0.05, history `volatile`. They are not a device fact or a recommendation.

`x-cap.fdcl-gwu.motors_on.v1` (a Bool input) is replaced by input-free `x-cap.fdcl-gwu.motors_off.v1`, which publishes the same Bool false. Its receipt confirms transmission only. The mode command stays (`trajectory.py:153-162`, modes 0..5) and does not turn the motors on. Both invoke actions are risk R2. The device stays `mode` simulated, `device_kind` world.sim, risk R2.

Fact lines the previous review marked were rewritten to what the cited lines say, including the GUI publish order (`gui.py:363-371` and `gui.py:378-391`), the trajectory split (`trajectory.py:80-90` and `93-98`), `set_desired_states_to_zero` (`trajectory.py:193-202`, `b1d` is `[1, 0, 0]`), and `mark_traj_start` (`trajectory.py:168-183`) separate from `update_initial_state` (`trajectory.py:217-222`).

`task.json` and the registry card are unchanged, so they still say blocked. G1 compares those two files. The integrator rebuilds the registry.

## Why there is no re-enable

The triage's preferred shape was an input-free motors-off plus a motors-on re-enable that disclosed the GUI's 100 ms mode. The verifier's fallback, if model validation refused sensed-stop plus re-enable, was to keep motors-on as an ordinary action. This repair does neither.

`fdcl_uav_launch.py:24-29` starts GuiNode. `gui.py:86-88` starts a 100 ms timer, and `gui.py:302-306` republishes the selected `ModeData` on every tick. Default mode is 0 (`gui.py:75`) until a radio or key changes it (`gui.py:394-407`). Idle is radio index 0 (`gui.py:128-136`, `gui.py:394-403`). A mode this driver publishes does not stick while GuiNode runs on a non-Idle radio. ControlNode publishes a non-zero wrench only when `motor_on` is true and `mode` is at least 2 (`control.py:245-251`). `mode_callback` stores the mode and returns when it is unchanged (`control.py:544-549`). `motors_on_callback` only assigns `motor_on` (`control.py:585-586`). TrajectoryNode stores its mode independently (`trajectory.py:116-124`). Stopping GuiNode stops the 100 ms republish and does not publish mode 0, so both nodes keep the last mode. SAFE-042 and the orchestrator's condition forbid a motors-on that would resume that stored mode. This driver publishes no Bool true.

`estop_terminal` is not declared. A Bool true publication undoes the cut (`gui.py:378-391`, and the M key at `gui.py:410-413`). Claiming the stop cannot be undone would be false. Reset re-confirms the pose and publishes nothing. Recovery is outside MHS. Before any Bool true, ControlNode and TrajectoryNode must both hold mode 0. Set the GUI to Idle so GuiNode republishes ModeData 0. If GuiNode is stopped, publish mode 0 on `/uav/mode` first; one ModeData reaches both subscribers. Do not stop GuiNode and then publish Bool true while the stored mode is still at least 2. While the e-stop latch is held, this driver's mode action is refused, so the driver cannot clear the retained mode itself.

## Round 1 review

Codex (gpt-6.1-sol, a model and not a human) reported one high finding: the recovery text said to set the GUI to Idle or stop GuiNode, then publish Bool true. That second option resumes stored motion. The finding is fixed in `safe_state`, `facts.md`, this record, and the regenerated `reference.json` and `REFERENCE.md`. Grok (grok-4.7) reported no findings. `reviewed_by` stays null. No hardware, ROS graph, Gazebo process or simulator run is claimed.

The plugin's watchdog (`uav_control_plugin.cpp:68-88`, `reset_uav` at `137-141`) also zeros force and torque after more than 100 updates without `/uav/fm`. It is not the stop.

`confirm_within_ms` 4000 is a client bound sized for a fall from above the clone's about-1 m world-up takeoff target (`trajectory.py:57`, NED `takeoff_end_height` -1.0). The clone states no maximum altitude (`README.md:184`, the P key). A higher flight must raise the bound in `simulation_deployment['estop_confirmation']` or the latch stays and the request is retried. `min_span_ms` stays 200 with `consecutive` 3 because the p3d rate is 10 Hz (`uav.urdf.xacro:61`); three counted samples at 100 ms spacing span 200 ms, and a 300 ms minimum would not be reachable.

The check reports the pose at the end of the window. An already-landed still UAV can satisfy it. Samples from before the request are discarded. The fake starts at placeholder z 2.0 so the success path is not that trivial case.

## Fake

`fake.py` is still a `RecordingRosTransport`. `/uav/gps` returns a burst of 12 samples with stamps 100 ms apart. The first sample is the one the bridge discards. After Bool false, and only when no competing publisher is set, the pose falls 0.4 m per step to z 0.15 and then holds still. That fall is a placeholder, not Gazebo, and it does not also zero the wrench for mode below 2. Switches withhold the stream, repeat one stamp, null `position.x`, or keep the pose flying as a GUI re-arm. A live `/uav/motors_on` read waits for a GUI button or the M key; the fake answers at once.

## Checks

After the round 1 recovery correction, `python3 -m unittest test_driver.UavCases test_driver.SensedStopCases` from the package directory: 16 tests, ok, 18.219 s. `python3 -m mhs.driver reference` rewrote `reference.json` and `REFERENCE.md`. `python3 -m mhs.driver check MHS/drivers/robots/fdcl-gwu__uav_simulator --backend fake`: G1-G9 pass, evidence `contract_checked`, gate digest `sha256:c5b559bd6a8c4063392a4b6f3c1d482e7434fac06db46c363cc88fbf33331848`. That stable digest matches the previous passing run: it excludes the report clock, and the gate findings did not change. `python3 MHS/handoff/tools/collect.py --strict` on this package: 1 of 1 pass, 0 warnings. No SDK change, so no mutants. No lock companion.

## Stopped attempts

The package directory in `development/p5-sensed/project` and in `development/ext-p5-sensed.fast-stopped/project` matched this snapshot before the edit (`diff -q` reported no difference). Nothing was taken from either tree.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/fdcl-gwu__uav_simulator/RESULT.json`
- `MHS/drivers/robots/fdcl-gwu__uav_simulator/driver.py`
- `MHS/drivers/robots/fdcl-gwu__uav_simulator/facts.md`
- `MHS/drivers/robots/fdcl-gwu__uav_simulator/fake.py`
- `MHS/drivers/robots/fdcl-gwu__uav_simulator/test_driver.py`
- `MHS/drivers/robots/fdcl-gwu__uav_simulator/fixtures/estop-confirmation.json`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
