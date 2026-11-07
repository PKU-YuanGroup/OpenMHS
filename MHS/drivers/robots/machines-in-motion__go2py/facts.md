# Facts and limits for gh.machines-in-motion/go2py

Every reference is at commit `eff240b82b0ff6dae6ba5ee934a381f38fe64c0d`.  `upstream_code` is a file of the
clone; `vendor_doc` is documentation text of the clone.  The generated `reference.json` is built from the
`Fact`/`Limit` objects of `driver.py`; this page records where each one comes from.

## Facts

| fact | source | ref |
|---|---|---|
| GO2Real is the clone's user-facing robot interface class | upstream_code | `Go2Py/robot/interface.py:24` |
| GO2Real creates a CycloneDDS participant, a state DataReader and low- and high-command DataWriters | upstream_code | `Go2Py/robot/interface.py:59-70` |
| getJointStates returns q, dq, tau_est and motor temperature | upstream_code | `Go2Py/robot/interface.py:106-111` |
| getIMU returns acceleration, angular velocity, quaternion and IMU temperature | upstream_code | `Go2Py/robot/interface.py:94-99` |
| getFootContacts returns the raw foot contact forces | upstream_code | `Go2Py/robot/interface.py:101-104` |
| getBatteryState returns the battery percentage | upstream_code | `Go2Py/robot/interface.py:159-161` |
| setCommandsHigh writes v_x, v_y and omega_z | upstream_code | `Go2Py/robot/interface.py:163-171` |
| setCommandsLow asserts 12-element q_des, dq_des, kp, kd and tau_ff arrays and writes them | upstream_code | `Go2Py/robot/interface.py:173-190` |
| The bridge names the motor_state order FR, FL, RR, RL and copies it into go2py_state q, dq, tau and motor_temp | upstream_code | `deploy/ros2_nodes/go2py_bridge/src/bridge.cpp:188-219` |
| The wireless remote's R2 + L2 sets Estop = 1; L2 + A clears it | upstream_code | `deploy/ros2_nodes/go2py_bridge/src/bridge.cpp:234-243` |
| While Estop is set the bridge sends a damp request and a zero low-level command with kd 3 | upstream_code | `deploy/ros2_nodes/go2py_bridge/src/bridge.cpp:317-333` |
| The FSM tracking move uses kp 150 and kv 3; its damping mode uses kd 2 | upstream_code | `Go2Py/robot/fsm.py:15-18` |
| The URDF states the position range, effort and velocity of every leg joint | upstream_code | `Go2Py/assets/urdf/go2.urdf:99-597` |
| The MuJoCo model states the motor torque range as +-23.7 for hip/thigh motors and +-45.43 for calf motors | upstream_code | `Go2Py/assets/mujoco/go2.xml:10-24` |
| The README describes the C++ bridge as implementing a remote-controlled emergency stop | vendor_doc | `README.md:10` |

The clone's bridge also has a watchdog timer that runs every 10 ms and repeats the e-stop command while Estop is
set (`deploy/ros2_nodes/go2py_bridge/src/bridge.cpp:38`, `:317-333`).  It is a timer of the bridge, not a command
watchdog of the Python interface; the driver therefore declares no `watchdog_ms`.

## Limits

| limit | value | source | ref |
|---|---|---|---|
| `joint_positions[0]` FR hip, rad | -1.0472 .. 1.0472 | upstream_code | `Go2Py/assets/urdf/go2.urdf:245` |
| `joint_positions[1]` FR thigh, rad | -1.5708 .. 3.4907 | upstream_code | `Go2Py/assets/urdf/go2.urdf:275` |
| `joint_positions[2]` FR calf, rad | -2.7227 .. -0.83776 | upstream_code | `Go2Py/assets/urdf/go2.urdf:305` |
| `joint_positions[3]` FL hip, rad | -1.0472 .. 1.0472 | upstream_code | `Go2Py/assets/urdf/go2.urdf:99` |
| `joint_positions[4]` FL thigh, rad | -1.5708 .. 3.4907 | upstream_code | `Go2Py/assets/urdf/go2.urdf:129` |
| `joint_positions[5]` FL calf, rad | -2.7227 .. -0.83776 | upstream_code | `Go2Py/assets/urdf/go2.urdf:159` |
| `joint_positions[6]` RR hip, rad | -1.0472 .. 1.0472 | upstream_code | `Go2Py/assets/urdf/go2.urdf:537` |
| `joint_positions[7]` RR thigh, rad | -0.5236 .. 4.5379 | upstream_code | `Go2Py/assets/urdf/go2.urdf:567` |
| `joint_positions[8]` RR calf, rad | -2.7227 .. -0.83776 | upstream_code | `Go2Py/assets/urdf/go2.urdf:597` |
| `joint_positions[9]` RL hip, rad | -1.0472 .. 1.0472 | upstream_code | `Go2Py/assets/urdf/go2.urdf:391` |
| `joint_positions[10]` RL thigh, rad | -0.5236 .. 4.5379 | upstream_code | `Go2Py/assets/urdf/go2.urdf:421` |
| `joint_positions[11]` RL calf, rad | -2.7227 .. -0.83776 | upstream_code | `Go2Py/assets/urdf/go2.urdf:451` |
| `feedforward_torques` hip/thigh, N.m | -23.7 .. 23.7 | upstream_code | `Go2Py/assets/mujoco/go2.xml:10` |
| `feedforward_torques` calf, N.m | -45.43 .. 45.43 | upstream_code | `Go2Py/assets/mujoco/go2.xml:24` |
| `forward_velocity`, `lateral_velocity`, `yaw_rate` | operator_required | operator | filled by `site-limits.example.json` |

The driver declares one whole-array rule per joint array, citing `Go2Py/assets/urdf/go2.urdf:99-597` for the
positions and `Go2Py/assets/mujoco/go2.xml:10-24` for the torques; the per-joint rows above are the exact lines
that show each number.

The body-velocity envelope is only a constructor default of the clone (`vx_max=0.5`, `vy_max=0.4`, `wz_max=0.5`
at `Go2Py/robot/interface.py:29-31`, used by `clip_velocity` at `:195-204`); a deployment may configure different
values, so it is not a device bound and the driver publishes `operator_required` instead.  The joint order of the
action is the bridge's FR, FL, RR, RL order (`bridge.cpp:188-219`), not the FL, FR, RL, RR order of the URDF.

## Known inconsistency in the clone

The clone's own `sitting_q` uses a calf angle of -2.82826662 rad (`Go2Py/robot/interface.py:46`), below the URDF
calf lower bound of -2.7227 rad (`Go2Py/assets/urdf/go2.urdf:305`, `:451`, `:597`, and `go2.xml:24`).  The driver
enforces the URDF bound, so the low-level joint action refuses that sitting pose; the URDF is the only text of
the clone that states a joint range.

## Tags

`quadruped`, `mobile robot`, `unitree`, `go2`, `dds`, `joint control`, `velocity control`.
