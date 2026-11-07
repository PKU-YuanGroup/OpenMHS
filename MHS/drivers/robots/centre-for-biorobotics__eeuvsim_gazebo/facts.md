# eeUVsim U-CAT AUV simulator: source facts and scope

Pinned clone: `robots/centre-for-biorobotics/eeuvsim_gazebo` at
`7276ed34215c6b75caf03d6d5144ee550aaf6600`.  All paths below are relative to
the clone root.  The driver is a configuration-only `RosDriver` over
rosbridge; it declares no Python native class and starts no ROS node.

## What the clone says

| Fact | Source and ref |
|---|---|
| eeUVsim is a Fossen-physics multi-platform AUV simulator with dynamics, reinforcement-learning scripts, robot models and actuator models, trained over ROS 2 pub-sub. | `upstream_code`, `README.md:1-8` |
| Gazebo 11 Classic is used only for visualization, without physics. | `upstream_code`, `README.md:25` |
| The UCAT quick start launches `spawn_UCAT.launch.py`; the RL client is `ros2 run eeuv_sim RL_UCAT.py -o`. | `upstream_code`, `README.md:30-37` |
| `AUVMotion` imports `gazebo_msgs/EntityState`. | `upstream_code`, `eeuv_sim/scripts/AUVMotion.py:16` |
| `AUVMotion` publishes `EntityState` on the absolute `/ucat/state` topic with queue size 10. | `upstream_code`, `eeuv_sim/scripts/AUVMotion.py:113` |
| `AUVMotion` subscribes to the absolute `/ucat/reset` topic with `std_msgs/Bool` and calls `reset_callback`. | `upstream_code`, `eeuv_sim/scripts/AUVMotion.py:96` |
| `AUVMotion` creates a `SetEntityState` client on the absolute `/gazebo/set_entity_state` service. | `upstream_code`, `eeuv_sim/scripts/AUVMotion.py:79` |
| The `AUVMotion` timer integrates body velocity and position every tick (`vel += acc * dt`, `pos += pos_dot * dt`) and then publishes the state; the loop has no stop or pause flag. | `upstream_code`, `eeuv_sim/scripts/AUVMotion.py:295-311` |
| `reset_callback` calls `reset()` when the current time differs from the previous reset time by more than 10000 ns; `reset()` zeroes `pos`, `vel`, `acc` and `U` and sets position z to 5. | `upstream_code`, `eeuv_sim/scripts/AUVMotion.py:417-429` |
| `reset()` builds an `EntityState`, publishes it on `/ucat/state` and calls `/gazebo/set_entity_state`; it does not stop the `moveFins` timer or a fin command stream. | `upstream_code`, `eeuv_sim/scripts/AUVMotion.py:447-479` |
| `moveFins` subscribes to the absolute `/hw/flippers_cmd` topic with `eeuv_sim_interfaces/Flippers` and publishes `FlippersFeedbacks` on the absolute `/hw/flippers_feedback` topic. | `upstream_code`, `eeuv_sim/scripts/actuator/moveFins.py:135-139` |
| `moveFins` subscribes to the absolute `/ucat/reset` topic with `std_msgs/Bool`. | `upstream_code`, `eeuv_sim/scripts/actuator/moveFins.py:140` |
| `moveFins.reset_joints` sends the four fins to their initial poses but leaves the fin timer running. | `upstream_code`, `eeuv_sim/scripts/actuator/moveFins.py:358-364` |
| `flippersCallback` copies `amplitude`, `frequency`, `zero_direction` and `phase_offset` from each of the four `Flipper` messages without checking a bound. | `upstream_code`, `eeuv_sim/scripts/actuator/moveFins.py:163-169` |
| `Flipper` comments `motor_number` as 0..3, `frequency` in Hz, `zero_direction` and `amplitude` in rad, and `phase_offset` as 0...2 Pi. | `upstream_code`, `eeuv_sim_interfaces/msg/Flipper.msg:1-14` |
| `Flippers` carries a `std_msgs/Header` and a `Flipper[] flippers` array. | `upstream_code`, `eeuv_sim_interfaces/msg/Flippers.msg:1-2` |
| `FlippersFeedback` carries `angular_pos`, `angular_vel` and `angular_acc`. | `upstream_code`, `eeuv_sim_interfaces/msg/FlippersFeedback.msg:1-3` |
| `FlippersFeedbacks` carries a header and the four named feedbacks `flipper_fr`, `flipper_br`, `flipper_bl` and `flipper_fl`. | `upstream_code`, `eeuv_sim_interfaces/msg/FlippersFeedbacks.msg:1-5` |
| `RL_UCAT`'s oscillation action space bounds the four amplitudes to 0..0.85 and the four zero directions to -pi..pi in FR, BR, BL, FL order; it is the training action space, not a clamp in `moveFins`. | `upstream_code`, `eeuv_sim/scripts/RL/RL_UCAT.py:67-71` |
| `RL_UCAT` uses a single frequency of 2.0 Hz and phase offsets `[0.0, 3.14159, 0, 3.14159]`. | `upstream_code`, `eeuv_sim/scripts/RL/RL_UCAT.py:90-91` |
| `RL_UCAT` creates publishers on `/ucat/reset`, `/hw/flippers_cmd_e2e` and `/hw/flippers_cmd`, and subscribes `/ucat/state`, `/hw/flippers_feedback` and `/ucat/depth_vel`. | `upstream_code`, `eeuv_sim/scripts/RL/RL_UCAT.py:296-301` |
| `pub_action_oci` writes each flipper's frequency, amplitude, zero direction and phase offset and publishes the `Flippers` message; it reads no acknowledgement. | `upstream_code`, `eeuv_sim/scripts/RL/RL_UCAT.py:263-279` |
| `moveFins` clamps its internal fin velocity to `pi * 16` rad/s and its internal acceleration to `64` rad/s^2; these are simulation-loop clamps, not bounds on the `Flippers` command. | `upstream_code`, `eeuv_sim/scripts/actuator/moveFins.py:128-130` |
| `moveFins` sends each fin pose through `/gazebo/set_entity_state` with `reference_frame` `base_link`. | `upstream_code`, `eeuv_sim/scripts/actuator/moveFins.py:270-294` |

## Native reads, writes and actions

- Reads: `/ucat/state` (`gazebo_msgs/EntityState`) supplies `name`, `pose`,
  `twist` and `reference_frame`; `/hw/flippers_feedback`
  (`eeuv_sim_interfaces/FlippersFeedbacks`) supplies the four named flipper
  feedbacks.
- Write/action: `/hw/flippers_cmd`
  (`eeuv_sim_interfaces/Flippers`) carries four `Flipper` objects.  This is the
  UCAT oscillation interface the RL client uses (`RL_UCAT.py:263-279`).
- Action: `/ucat/reset` (`std_msgs/Bool`) is a reset request publication.
- Not exposed: `/hw/flippers_cmd_e2e` is published by `RL_UCAT.py:297` but has
  no subscriber in this pin; `moveFins.py:139` subscribes only to
  `/hw/flippers_cmd`.  The LAUV/Blue thruster and wing topics, the force
  topics, `/ucat/depth_vel` and `/gazebo/set_entity_state` are outside this
  UCAT fin package.

## Units and ranges

- `Flipper.amplitude`: rad, no runtime clamp in `moveFins`; the RL training
  action space uses 0..0.85 rad (`RL_UCAT.py:70-71`).
- `Flipper.frequency`: Hz, no runtime clamp in `moveFins`; `RL_UCAT` uses
  2.0 Hz (`RL_UCAT.py:90`).
- `Flipper.zero_direction`: rad, no runtime clamp in `moveFins`; the RL
  training action space uses -pi..pi (`RL_UCAT.py:70-71`).
- `Flipper.phase_offset`: rad, the message comment says 0...2 Pi
  (`Flipper.msg:13-14`); `moveFins` does not enforce it.
- `EntityState` position: m; orientation: quaternion; linear velocity: m/s;
  angular velocity: rad/s (ROS message definitions, used as published).
- `FlippersFeedback.angular_pos`: rad; `angular_vel`: rad/s;
  `angular_acc`: rad/s^2 (`FlippersFeedback.msg:1-3`).

No text in the pinned clone states a runtime bound on
`Flipper.amplitude`, `frequency`, `zero_direction` or `phase_offset`; the
driver therefore uses `Limit.operator_required` for each.  The example
operator overlay in `site-limits.example.json` fills them with example values
(including the RL training envelope for amplitude and zero direction) and
states that those values are operator examples, not device facts.  Without an
overlay every fin command is refused with
`MHS.SAFETY.LIMITS_UNSET` and no publication is sent.

## Stop path

There is no acknowledged stop in the clone:

1. `/hw/flippers_cmd` is a topic publication.  `moveFins` receives it in
   `flippersCallback`, copies the values into its CPG arrays and keeps its
   timer running (`moveFins.py:137,163-169,303-344`).
2. `/ucat/reset` is a `Bool` publication.  `AUVMotion.reset_callback` calls
   `reset()`; `moveFins.reset_joints` moves the fins to their initial target,
   but neither stops the `moveFins` timer nor acknowledges the request.
3. The clone creates no pause, stop or reset service or action for the AUV.
   `/gazebo/set_entity_state` is a pose/twist setter used by the simulator's
   own loop; `AUVMotion` overwrites the entity state on its next timer tick,
   so a one-off set is not a stop.

The driver declares a sensed-confirmation stop (SAFE-049, simulated only).
The request is one zero-amplitude `Flippers` publication on `/hw/flippers_cmd`.
`/ucat/reset` is omitted: `reset()` zeroes `pos`, `vel`, `acc` and `U` and
sets position z to 5 (`AUVMotion.py:423-429`) and does not clear the fin
command stored at `moveFins.py:163-169`. Confirmation is three fresh
`/ucat/state` twist samples. The publisher at `AUVMotion.py:113` is volatile
and the message has no header, so freshness is arrival with `min_interval_ms`
5. The shipped period is 10 ms (`AUVMotion.py:75` `dt` 0.01,
`eeuv_sim/data/rl_setting/rl_setting.yaml:2` `fast_forward` 1.0). Three
counted samples span two periods. That span, compared in milliseconds, lands
just under 20, so `min_span_ms` is 19. A bound of 20 rejects the shipped
period. A `fast_forward` above 1 shortens the span below 19 ms and the stop
fails closed unless the operator lowers `min_span_ms`. A `fast_forward` above
2 also publishes faster than `min_interval_ms` 5 and fails closed. Thresholds
are operator-required. `fixtures/estop-confirmation.json` holds fake
placeholders.

## Mock path

`mock_strategy.preferred` is `upstream-sim`, but the upstream simulator needs
ROS 2 Humble, Gazebo Classic 11, the Python dynamics modules and the launch
stack; it is not installed or run here.  The package therefore ships a
ROS-free `RecordingRosTransport` fake in `fake.py`.  The fake is an analytic
contract stand-in, not a recording of captured traffic: it answers the two
subscriptions with placeholder messages and records the two declared
publications.  It runs no Fossen dynamics, fin CPG, Gazebo scene, ROS graph or
timer.  All fake numbers are marked `# placeholder`.

## Outcome

`RESULT.json` status is pass on the fake backend. Evidence is `contract_checked`.
No Gazebo, Fossen integration or hardware run is claimed. `reviewed_by` stays
null. Licence NOASSERTION; `publish_review` stays required, and this record
does not publish the package.

Risk is R2 under REVIEW.md item 12. `connect_microCAT.launch.py:13-19` starts
executable `microcatHardwareInterface.py` with `serial_port` `/dev/ttyACM0`.
That script is not in the clone, and the clone shows no subscriber inside it.
The only `/hw/flippers_cmd` subscriber in the clone is the simulator
(`moveFins.py:139`). Whether a physical micro-CAT consumes this topic is for
the human reviewer. This package does not bind that launch file. The card
floor is R0; a fin command that a physical vehicle would also consume is R2.
