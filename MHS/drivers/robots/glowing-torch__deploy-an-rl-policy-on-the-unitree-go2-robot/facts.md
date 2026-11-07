# Facts and tags for gh.glowing-torch/deploy-an-rl-policy-on-the-unitree-go2-robot

Pinned commit: `dbb7b3112cef08ffc9f6f2c63412144d20341222`. This package is a configuration-only ROS 2
`RosDriver` over the MuJoCo simulator node's topics. Declarations, citations and fake receipts are not native
execution: no ROS graph, MuJoCo model, policy or hardware was run.

| fact | source | ref |
|---|---|---|
| The simulation node sets xml_path to resources/go2/scene_terrain.xml under the project root and loads it with mujoco.MjModel.from_xml_path. | upstream_code | src/deploy_rl_policy/scripts/mujoco_simulator.py:27-45 |
| scene_terrain.xml includes go2.xml. | upstream_code | resources/go2/scene_terrain.xml:2 |
| The simulator declares a LowState publisher on /mujoco/lowstate, a Float32MultiArray publisher on /mujoco/pos, a Float32MultiArray publisher on /mujoco/torque and a LowCmd subscription on /mujoco/lowcmd. | upstream_code | src/deploy_rl_policy/scripts/mujoco_simulator.py:20-24 |
| The simulation node imports LowState and LowCmd from unitree_go.msg. | upstream_code | src/deploy_rl_policy/scripts/mujoco_simulator.py:8 |
| The simulation node imports Float32MultiArray from std_msgs.msg. | upstream_code | src/deploy_rl_policy/scripts/mujoco_simulator.py:11 |
| target_torque_callback sets recieve_data true on every LowCmd, then copies motor_cmd[i].q, .kp and .kd for i in 0..11 into target_dof_pos, kps and kds; no other MotorCmd field is read. | upstream_code | src/deploy_rl_policy/scripts/mujoco_simulator.py:55-60 |
| update_tau returns until recieve_data is true and then computes tau[i] with pd_control from target_dof_pos[i], qpos[7+i], kps[i], qvel[6+i] and kds[i] for each of the twelve motors. | upstream_code | src/deploy_rl_policy/scripts/mujoco_simulator.py:62-66 |
| pd_control returns (target_q - q) * kp - dq * kd. | upstream_code | src/deploy_rl_policy/scripts/mujoco_simulator.py:111-115 |
| The node creates a 2 ms timer for publish_sensor_data and a 1 ms timer for update_tau, and starts step_simulation in its own thread. | upstream_code | src/deploy_rl_policy/scripts/mujoco_simulator.py:33-40 |
| step_simulation loops while the viewer runs and running is true; until recieve_data is true it continues without sleeping, and afterwards it copies tau into d.ctrl, publishes it on /mujoco/torque, calls mujoco.mj_step and sleeps for the rest of the model timestep, with no check for a fresh LowCmd. | upstream_code | src/deploy_rl_policy/scripts/mujoco_simulator.py:68-84 |
| publish_sensor_data copies motor_state[i].q and .dq for i in 0..11 from qpos[7+i] and qvel[6+i], copies qpos[3:7] into imu_state.quaternion and sensordata[40:43] into imu_state.gyroscope. | upstream_code | src/deploy_rl_policy/scripts/mujoco_simulator.py:91-98 |
| publish_sensor_data publishes d.qpos[:19] as the Float32MultiArray data on /mujoco/pos. | upstream_code | src/deploy_rl_policy/scripts/mujoco_simulator.py:99-101 |
| The node sets the MuJoCo timestep to 0.005 s. | upstream_code | src/deploy_rl_policy/scripts/mujoco_simulator.py:45-47 |
| stop_simulation sets running false and joins the simulation thread. | upstream_code | src/deploy_rl_policy/scripts/mujoco_simulator.py:86-88 |
| main() calls stop_simulation and viewer.close() only in its finally block after rclpy.spin. | upstream_code | src/deploy_rl_policy/scripts/mujoco_simulator.py:120-128 |
| The MuJoCo model declares per-class joint ranges: abduction -1.0472 to 1.0472 rad, front hip -1.5708 to 3.4907 rad, back hip -0.5236 to 4.5379 rad and knee -2.7227 to -0.83776 rad. | upstream_code | resources/go2/go2.xml:12-23 |
| The model's actuator block lists the twelve motors in FR, FL, RR, RL leg order, three joints per leg. | upstream_code | resources/go2/go2.xml:232-243 |
| The go2 default class sets the motor ctrlrange to -23.7 to 23.7, and the knee class overrides it to -45.43 to 45.43. | upstream_code | resources/go2/go2.xml:10-24 |
| low_level_ctrl declares is_simulation with default true; in simulation mode it publishes LowCmd on /mujoco/lowcmd and subscribes to LowState on /mujoco/lowstate, and otherwise it uses /lowcmd and /lowstate. | upstream_code | src/deploy_rl_policy/src/low_level_ctrl.cpp:42-57 |
| low_level_ctrl creates a 5 ms wall timer that runs state_machine. | upstream_code | src/deploy_rl_policy/src/low_level_ctrl.cpp:63 |
| state_machine's hold branch sets mode 0x01 and the standing or lay-down target angles with kp and kd for the twelve motors, computes the CRC and publishes the LowCmd. | upstream_code | src/deploy_rl_policy/src/low_level_ctrl.cpp:147-170 |
| low_level_ctrl's run_policy writes the target positions with kp 30 and kd 0.75 for all twelve motors. | upstream_code | src/deploy_rl_policy/src/low_level_ctrl.cpp:184-189 |
| target_pos_callback calls run_policy only while is_standing_ and should_run_policy_ are both true; otherwise it only stores the received target vector. | upstream_code | src/deploy_rl_policy/src/low_level_ctrl.cpp:91-97 |
| joy_callback calls rclcpp::shutdown() when joystick axes 2 and 5 are both -1. | upstream_code | src/deploy_rl_policy/src/low_level_ctrl.cpp:120-121 |
| rl_policy.py subscribes to /mujoco/lowstate when args.simulation is set and to /lowstate otherwise. | upstream_code | src/deploy_rl_policy/scripts/rl_policy.py:36-41 |
| rl_policy.py publishes its target joint positions as a Float32MultiArray on /rl/target_pos. | upstream_code | src/deploy_rl_policy/scripts/rl_policy.py:46 |
| rl_policy.py reorders the measured joint vectors with sequence [3, 4, 5, 0, 1, 2, 9, 10, 11, 6, 7, 8]; the comment above the two reorder lines says to comment them out for simulation. | upstream_code | src/deploy_rl_policy/scripts/rl_policy.py:62-66 |
| The shipped policy configuration sets num_actions 12 and action_scale 0.25. | upstream_code | src/deploy_rl_policy/configs/go2.yaml:8-10 |
| The README runs the MuJoCo simulator with ros2 run deploy_rl_policy mujoco_simulator.py. | vendor_doc | README.md:44 |
| The README describes low_level_control as the 3-state machine that sends lowcmd to the simulator or the real robot. | vendor_doc | README.md:86-89 |
| The README maps joystick B, A and LB+RB to stand up, lay down and execute the RL policy. | vendor_doc | README.md:59-61 |
| The README instructs the operator to turn down the robot's sport mode service before deploying a policy on the real robot; that service is not implemented in this clone. | vendor_doc | README.md:68 |

## Limits

The MJCF joint ranges bound the model's joint positions, not the `motor_cmd[i].q` target or the `kp`/`kd` gains.
The `ctrlrange` values bound the torque MuJoCo applies inside `mj_step`, not those message fields. The clone
states no numeric bound for MotorCmd `q`, `kp` or `kd`, so each is `Limit.operator_required`. Until the operator
supplies `site-limits.json`, every `/mujoco/lowcmd` publication is refused with `MHS.SAFETY.LIMITS_UNSET` and
nothing is sent. `site-limits.example.json` holds example values only. They are not a device limit and must be
replaced. The joint ranges and motor control ranges above stay facts.

## Sensed stop

The simulator registers no stop service and no stop action. `stop_simulation()` is reachable only from the node's
own `main()` after `rclpy.spin` returns. The joystick shutdown in `low_level_ctrl.cpp:120-121` shuts that node down
and leaves the simulator applying the last target. The package declares a sensed-confirmation stop (SAFE-049,
simulated only) at risk R2. The request is the twenty-slot `init_cmd` on `/mujoco/lowcmd`: mode `0x01`, `q`
`PosStopF`, `dq` `VelStopF`, `kp`, `kd` and `tau` 0 (`low_level_ctrl.cpp:71-78`). `PosStopF` (`2.146E+9f`) and
`VelStopF` (`16000.0f`) are `src/deploy_rl_policy/include/common/motor_crc.h:18-19`. The invoke input stays twelve
MotorCmd entries of `q`, `kp` and `kd`. `unitree_go/msg/LowCmd` is defined outside the clone.

`pd_control` is `(target_q - q) * kp - dq * kd` (`mujoco_simulator.py:112-114`), so `kp` and `kd` at zero make
that torque zero. Confirmation reads twelve `/mujoco/lowstate` joint velocities and the span of `/mujoco/pos`
`data[0]`, `data[1]` and `data[2]`. Both publishers are volatile (`mujoco_simulator.py:20-21`) and the messages
do not carry a stamp this clone assigns (the lowstate fill at `mujoco_simulator.py:92-98` assigns q, dq and imu fields; `/mujoco/pos` is a Float32MultiArray at `:99-101`), so freshness is arrival with `min_interval_ms` 1. Both topics are published by the 2 ms
`publish_sensor_data` timer (`mujoco_simulator.py:33`). The 1 ms timer at `:34` is `update_tau` and does not
publish them. Three counted samples at 2 ms span 4 ms, which is `min_span_ms`. A slower timer still meets the
arrival window while the gap stays under `max_gap_ms` 500. A stream closer than 1 ms restarts the count. Thresholds are
operator-required. `fixtures/estop-confirmation.json` holds fake placeholders.

`low_level_ctrl`, which the README runs next to the simulator, publishes LowCmd on `/mujoco/lowcmd` every 5 ms
from its state machine (`low_level_ctrl.cpp:63`, `147-170`), so while it runs any LowCmd from this package is
overwritten within 5 ms. The confirmation subscribes to that topic after the request. Silence, a subscription
error, a sample whose watched `motor_cmd[0..11].kp` or `.kd` is not zero, and a sample the exclusion ring drops
each refuse the confirmation (`low_level_ctrl.cpp:160-167`). A dropped sample was not inspected, so a later
passive tail is an observer fault. A stationary hold is not proof the controller stopped: the keep branch
publishes nonzero gains, and it publishes nothing when that controller is absent. There is no source-backed
controller stop and no exclusive command route. `COMPETING_PUBLISHER` stays unresolved, and the package stays
blocked on `SDK_BUG`. With `is_simulation` false the same node commands `/lowcmd` and reads `/lowstate`
(`42-57`), the README's real-robot path, which this package does not bind.

`RESULT.json` status is blocked, `blocked_on` `SDK_BUG`. The gate fails G6 and G8. With the example overlay,
TSAFE-001 is `RESET_REFUSED`, SAFE-028 reports `safe_state_achieved` false, and the SAFE-014 probes return
`ESTOP_ENGAGED`. Evidence is `contract_checked`. No MuJoCo, policy or hardware run is claimed. `reviewed_by`
stays null. The licence is MIT. This record does not publish the package.

Tags: `ros`, `ros2`, `simulation`, `mujoco`, `quadruped`, `unitree`, `go2`, `joint position`, `lowcmd`, `lowstate`.
