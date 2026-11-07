# Facts and tags for gh.strands-labs/robots

Every fact and every bound below cites its source at commit `f19439bf8c80e7ae6f0fdc0f003d850d638dd97d`
(`upstream_code`: a code or comment line of the read-only clone). The driver's `facts = [...]` and `Limit`s carry the
same text and refs; the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The M3 Pro is a mecanum chassis carrying the DOFBOT-Pro arm; its motors sit behind an STM32 expansion board running micro-ROS firmware, reached through ROS 2 Humble and micro_ros_agent. | upstream_code | `strands_robots/drivers/yahboom_m3pro.py:3-8` |
| The base is `/cmd_vel` (`geometry_msgs/Twist`): `linear.x` forward, `linear.y` strafe, `angular.z` yaw, SI units. | upstream_code | `strands_robots/drivers/yahboom_m3pro.py:10-11` |
| The firmware zeroes the motors after roughly 200-500 ms without a fresh Twist, so a held move is a stream at the publish rate followed by an explicit zero. | upstream_code | `strands_robots/drivers/yahboom_m3pro.py:12-14` |
| The arm is `/arm6_joints` (`arm_msgs/ArmJoints`): all six servos at once as `joint1..joint6` in integer degrees plus `time` in milliseconds. | upstream_code | `strands_robots/drivers/yahboom_m3pro.py:15-17` |
| Joints 1-4 travel 0-180 degrees, joint 5 travels 0-270, and joint 6 is the gripper from 30 (closed) to 180 (open). | upstream_code | `strands_robots/drivers/yahboom_m3pro.py:17-19` |
| The board holds a commanded arm pose, so one `/arm6_joints` message is enough. | upstream_code | `strands_robots/drivers/yahboom_m3pro.py:18-19` |
| The servo travel table is 1-4: 0-180, 5: 0-270, 6: 30-180 degrees, the vendor limits every Yahboom teleop node clamps to. | upstream_code | `strands_robots/drivers/yahboom_m3pro_wire.py:61-71` |
| The model joint q maps to servo degrees as `deg = 90 + degrees(q)`, so +-pi/2 maps onto 0-180 for joints 1-4 and -pi/2..pi onto 0-270 for joint 5. | upstream_code | `strands_robots/drivers/yahboom_m3pro.py:58-60` |
| The gripper crank `rlink1` travels -1.54 (closed) to 0 (open), mapped linearly onto 30-180 degrees. | upstream_code | `strands_robots/drivers/yahboom_m3pro.py:61-62` |
| The vendor keyboard-teleop ceilings are a linear speed limit of 1.0 m/s and an angular speed limit of 5.0 rad/s. | upstream_code | `strands_robots/drivers/yahboom_m3pro_wire.py:92-98` |
| The longest one move may hold a twist is `MAX_MOVE_DURATION_S = 10.0` s; a longer run is repeated calls. | upstream_code | `strands_robots/drivers/yahboom_m3pro_wire.py:103-105` |
| The board publishes no arm joint-state topic this driver can verify: `get_observation` returns `{}` on the robot rather than echoing the last command as a reading. | upstream_code | `strands_robots/drivers/yahboom_m3pro.py:67-70` |
| The arm holds its pose on its own; only the base can be moving. | upstream_code | `strands_robots/drivers/yahboom_m3pro.py:673-677` |
| `stop_task` sends a zero Twist, and it is not exempt from the `/cmd_vel` operator gate: the halt needs a pre-approved `/cmd_vel` or an approving operator. | upstream_code | `strands_robots/drivers/yahboom_m3pro.py:966-973` |
| `set_arm_degrees` refuses an angle outside each servo's travel rather than clamping it. | upstream_code | `strands_robots/drivers/yahboom_m3pro_wire.py:156-180` |

## Limits

| binding | path | bound | source | ref |
|---|---|---|---|---|
| `cap.motion.joint_position.v1` | `joint_positions` | per joint: joint1..joint4 -pi/2..pi/2 rad, joint5 -pi/2..pi rad, joint6 -1.54..0 rad | upstream_code | `strands_robots/drivers/yahboom_m3pro.py:58-63` |
| `x-cap.strands-labs.mobile-base.v1` | `linear_x`, `linear_y` | -1.0..1.0 m/s | upstream_code | `strands_robots/drivers/yahboom_m3pro_wire.py:92-98` |
| `x-cap.strands-labs.mobile-base.v1` | `angular_z` | -5.0..5.0 rad/s | upstream_code | `strands_robots/drivers/yahboom_m3pro_wire.py:92-98` |
| `x-cap.strands-labs.mobile-base.v1` | `duration_s` | 0.0..10.0 s | upstream_code | `strands_robots/drivers/yahboom_m3pro_wire.py:103-105` |

The gripper extension and the home extension take a boolean or no input, so they declare no numeric bound.

## Safety

- Risk is R2: this is a robot arm and a mobile base (MHS/spec/04-safety.md). The card floor is R1; the driver raises
  it to the hazard.
- `stop_task` is the native stop. `cap.motion.stop.v1` is bound as `safe_state=True`, so `safe_state.achieved_by` is
  non-empty (SAFE-045). The upstream documents no independent physical e-stop for this chassis, so
  `estop_physical_ref` is not claimed.
- The upstream `stop_task` goes through the shared `/cmd_vel` operator gate. On hardware, a zero Twist that the gate
  refuses still ends when the firmware watchdog zeroes the base after roughly 200-500 ms; the arm holds its commanded
  pose on its own.
- `get_observation` is empty on the robot (no verified arm joint-state topic). The last commanded pose is exposed
  separately as `commanded_arm_pose`; it is a command record, not a measurement.

Tags: `robot arm`, `mobile base`, `mecanum`, `gripper`, `ros2`, `yahboom`, `m3pro`.
