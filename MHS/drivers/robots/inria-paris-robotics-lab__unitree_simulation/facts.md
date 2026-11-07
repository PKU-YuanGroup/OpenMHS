# Facts and scope for gh.inria-paris-robotics-lab/unitree_simulation

Every fact cites the pinned clone at commit
`b53b31bc0757e3ff48ac1199227e0b144d4008d2`. `upstream_code` refs are
`path/in/clone:LINE`; the generated reference carries the same facts from
`driver.py`.

The e-stop is a sensed-confirmation stop for this simulated device only. It publishes twenty zero MotorCmd entries on `/lowcmd`. The node applies the first `n_dof` (12) (`simulation_node.py:79-95`). The node fill at `simulation_node.py:104-108` assigns `motor_state` mode, q and dq and does not assign a stamp. The LowState message definition is outside the clone (`robots_configuration.py:3` imports it from `unitree_go.msg`), so `/lowstate` joint velocities are fresh by arrival from the volatile publisher at `simulation_node.py:56`. `/odometry/filtered` is stamped at `:139` and its publisher is at `:57`. `Go2Configuration.high_level_period` is `1.0/500.0` (`robots_configuration.py:169-171`). Three counted samples at that rate span 4 ms, which is `min_span_ms`. Do not raise `min_span_ms` above 4 for this period. A stream closer than `min_interval_ms` 1 restarts the arrival count and the stop fails closed. A slower stream still confirms while the gap stays under `max_gap_ms` 500. Thresholds are operator-required. `fixtures/estop-confirmation.json` holds fake placeholders, not device limits. `/reset` is not the stop: `reset()` does not clear `last_cmd_msg`. `RESULT.json` status is pass on the fake backend. Evidence is `contract_checked`. The package is not claimed published.

| fact | source | ref |
|---|---|---|
| The simulation node declares the string parameters simulator and robot and the boolean parameter unlock_base. | upstream_code | `unitree_simulation/simulation_node.py:17-19` |
| The launch file defaults simulator to pybullet and unlock_base to False; robot is a declared launch argument with no default. | upstream_code | `launch/launch_sim.launch.py:9-19` |
| The node selects Go2Configuration when robot is go2 and G1Configuration when it is g1. | upstream_code | `unitree_simulation/simulation_node.py:26-34` |
| UnitreeSimulation creates a publisher for the robot's LowState type on /lowstate with queue size 10 and a nav_msgs/Odometry publisher on /odometry/filtered. | upstream_code | `unitree_simulation/simulation_node.py:55-77` |
| The node imports Empty from std_msgs.msg and Odometry from nav_msgs.msg for its ROS 2 interface. | upstream_code | `unitree_simulation/simulation_node.py:3-4` |
| The robots configuration imports LowState and LowCmd from unitree_go.msg. | upstream_code | `unitree_simulation/robots_configuration.py:3` |
| Go2Configuration returns LowStateGo2 from lowstate_msgs_type and LowCmdGo2 from lowcmd_msgs_type. | upstream_code | `unitree_simulation/robots_configuration.py:193-199` |
| The node creates a subscription for the robot's LowCmd type on /lowcmd with queue size 10 and callback receive_cmd_cb, and initialises last_cmd_msg to a default-constructed LowCmd. | upstream_code | `unitree_simulation/simulation_node.py:61-62` |
| When unlock_base is false, the node subscribes std_msgs/Empty on /unlock_base with queue size 1 and its callback calls unlock_base(). | upstream_code | `unitree_simulation/simulation_node.py:69-74` |
| The node subscribes std_msgs/Empty on /reset with queue size 1 and its callback calls reset(). | upstream_code | `unitree_simulation/simulation_node.py:74` |
| The node creates a timer with the robot's high_level_period. | upstream_code | `unitree_simulation/simulation_node.py:77` |
| Go2Configuration returns high_level_period 1.0/500.0 and low_level_sub_step 12. | upstream_code | `unitree_simulation/robots_configuration.py:169-175` |
| n_dof is len(joint_names). | upstream_code | `unitree_simulation/robots_configuration.py:59-61` |
| Go2Configuration lists the 12 joint names in FR, FL, RR, RL order with three joints per leg. | upstream_code | `unitree_simulation/robots_configuration.py:151-164` |
| The timer callback reads q, dq, tau, kp and kd from the first n_dof motor_cmd entries of last_cmd_msg. | upstream_code | `unitree_simulation/simulation_node.py:79-95` |
| For each high-level step the node computes tau_cmd = tau_des - kp*(q_current - q_des) - kd*(v_current - v_des) and calls simulator.step once per low-level sub-step. | upstream_code | `unitree_simulation/simulation_node.py:79-95` |
| The callback publishes motor_state mode=1, q and dq for every Go2 joint. | upstream_code | `unitree_simulation/simulation_node.py:104-112` |
| Go2Configuration.foot_force_to_val returns 14.2 + 0.562 * force. | upstream_code | `unitree_simulation/robots_configuration.py:201-203` |
| When the robot has feet sensors, the callback publishes int(foot_force_to_val(force)) for every contact force in LowState.foot_force. | upstream_code | `unitree_simulation/simulation_node.py:104-112` |
| The callback rearranges the base quaternion from xyzw to wxyz, publishes gyroscope as the local angular velocity and accelerometer as local linear acceleration plus the rotated gravity vector 9.81; a comment on the gravity rotation says this seems wrong. | upstream_code | `unitree_simulation/simulation_node.py:114-132` |
| The callback fills Odometry with frame odom and child frame base, pose x/y/z and the xyzw quaternion and twist linear/angular values from the simulator state. | upstream_code | `unitree_simulation/simulation_node.py:137-155` |
| The receive callback only assigns the message to last_cmd_msg. | upstream_code | `unitree_simulation/simulation_node.py:177-178` |
| reset() calls simulator.reset() and, when unlock_base_default is true, also calls simulator.unlock_base(). | upstream_code | `unitree_simulation/simulation_node.py:180-183` |
| unlock_base() logs and calls simulator.unlock_base(). | upstream_code | `unitree_simulation/simulation_node.py:185-187` |
| The abstract wrapper documents unlock_base as releasing a base that was spawned fixed in the world and reset as resetting the simulation and re-locking the base. | upstream_code | `unitree_simulation/abstract_wrapper.py:24-37` |
| The node's constructor creates publishers, subscriptions and a timer only; it creates no ROS service server or action server. | upstream_code | `unitree_simulation/simulation_node.py:55-77` |
| reset() does not assign last_cmd_msg. | upstream_code | `unitree_simulation/simulation_node.py:180-183` |
| BulletWrapper.reset moves the base to q_start and every joint whose id passes 'if id:' (a joint at index 0 does not) to its q_start value, sets zero-force velocity control on the joints and creates a fixed constraint that locks the base when none exists. | upstream_code | `unitree_simulation/bullet_wrapper.py:70-99` |
| The README describes the package as a ROS 2 simulation of the Unitree Go2 that mimics its ROS 2 API by replicating the most-used topics. | vendor_doc | `README.md:1-3` |
| package.xml describes the package as a basic simulator wrapper that mimics the real Go2 ROS 2 control API. | vendor_doc | `package.xml:6` |

## Scope

The declared device is the Go2 variant. The node supports a G1 variant with
`unitree_hg` messages, 29 joints and a 1 kHz timer
(`unitree_simulation/robots_configuration.py:68-143`), but one static
rosbridge binding on `/lowcmd` cannot carry both message types. The G1
variant is therefore not covered.

The node's primary control interface is the `unitree_go/msg/LowCmd`
publication on `/lowcmd`; the primary feedback is `LowState` on `/lowstate`.
The driver also serves the two auxiliary `std_msgs/Empty` publications
(`/reset`, `/unlock_base`) and the `nav_msgs/msg/Odometry` feedback on
`/odometry/filtered`. The resource state reads the pose and twist sub-objects
of Odometry and the `motor_state` array of LowState.

## Sensed stop

The pinned node has no ROS service server and no ROS action server. The only
effectful inputs are topic publications. A rosbridge publication returns
`published: true, confirmed: false`. The sensed stop (SAFE-049, simulated only)
publishes twenty zero MotorCmd entries on `/lowcmd` and confirms from fresh
samples: twelve `/lowstate` joint velocities by arrival, and the stamped
`/odometry/filtered` linear and angular twist. The timer torque
`tau_cmd = tau_des - kp*(q - q_des) - kd*(v - v_des)` (`simulation_node.py:89-93`)
is zero when `kp`, `kd` and `tau` are zero. `reset()` does not assign
`last_cmd_msg` (`simulation_node.py:180-183`), so `/reset` and `/unlock_base`
stay ordinary commands. The launch default leaves the base hung
(`launch/launch_sim.launch.py:9-19`), so the predicate includes the twelve
joint velocities. `RESULT.json` status is pass. The gate evidence is the fake
backend's `contract_checked` record. No simulator or hardware run is claimed.

## Command limits

The clone reads the five `MotorCmd` values but states no numeric bound for
any of them. Joint limits and torque limits live in the external
`unitree_description`/URDF data, not in this repository. Every q, dq, tau, kp
and kd value is therefore declared `Limit.operator_required(...)`: until the
operator supplies the reviewed per-joint envelope in `site-limits.json`,
every `LowCmd` publication is refused with `MHS.SAFETY.LIMITS_UNSET`.
`site-limits.example.json` contains example values only; they are not a
statement about any deployment and must be replaced.

## Fidelity

The fake is a ROS-free event-driven contract stand-in at F0, not a recording
of captured traffic. It has no pybullet or Simple physics, no timer, no
contacts and no base constraint. Its `LowState` and `Odometry` samples are
placeholders. The `motor_state` q and dq entries in the fake echo the last
published `LowCmd` only as a contract effect so a publication changes the
resource state; they are not pybullet-measured joint state. A live run needs an
ament/colcon workspace, `rclpy`, `unitree_ros2` messages,
`unitree_description`, numpy, scipy and pybullet, and an operator-run
rosbridge, none of which is installed or validated here.

## Reviewer notes (model review of wave C)

- The `/lowstate` read does not fix the motor arrays at 12 entries. The node
  fills the first `n_dof` (12) entries of a default-constructed `LowState`
  (`unitree_simulation/simulation_node.py:98-108`) and does not assign a stamp.
  The LowState definition is outside the clone, so `motor_state` is a pre-sized
  array whose size that definition sets. The stop request sends twenty MotorCmd
  slots; the node applies `n_dof` 12 (`simulation_node.py:79-95`). The invoke
  input remains twelve entries. The `unitree_go` message definition is outside
  the clone and has to be checked against the deployed version before a live run.
- The node mimics the real Go2 ROS 2 API on the same absolute topics
  (`README.md:3`, `package.xml:6`): on a graph that also carries a real Go2's
  unitree_ros2 bridge, a `/lowcmd` publication of this package would reach the
  real robot.
- The node starts with a default `LowCmd` (`simulation_node.py:62`) and the
  timer applies the first 12 entries of `last_cmd_msg` on every tick
  (`:79-95`); `reset()` does not assign it (`:180-183`), so after
  `BulletWrapper.reset` returns the robot to `q_start` with the base locked
  (`bullet_wrapper.py:70-99`) the last command is applied again at once.
- The accelerometer adds a gravity vector rotated with the body-to-world matrix;
  the upstream comment on that line says this seems wrong
  (`simulation_node.py:123-129`).
- The fake's Odometry now has the ROS 2 header shape (`stamp.sec/nanosec`,
  `frame_id`) with `child_frame_id` at the top level.
