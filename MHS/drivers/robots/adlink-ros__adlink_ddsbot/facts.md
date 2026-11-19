# Facts and limits for gh.adlink-ros/adlink_ddsbot

Every fact below cites the clone at `6b077391af87b61f72b26f5046b04dd2b3576ab2`. The table matches driver.py; generated references come from that driver.

| fact | source | ref |
|---|---|---|
| The base node subscribes to cmd_vel (geometry_msgs/Twist) and publishes base_odom (nav_msgs/Odometry) | upstream_code | script/base_control.py:43-44 |
| The node sends the motor command as left,right,checksum, where the checksum is the sum of the character lengths of the two wheel-speed strings | upstream_code | script/base_control.py:121-125 |
| The node reads a reply line and splits it on ',' into two wheel speeds in deg/sec | upstream_code | script/base_control.py:68-74 |
| The body twist is converted to wheel speeds with VR = vx + wheelSep/2.0*wz and VL = vx - wheelSep/2.0*wz, then to deg/sec with 180.0/math.pi/wheelRad | upstream_code | script/base_control.py:117-120 |
| The node opens the serial port with a 10 s read timeout | upstream_code | script/base_control.py:30 |
| The node uses string.split(line, ',') to split the reply line (the Python 2 module-level split API) | upstream_code | script/base_control.py:69 |
| The shipped launch file configures the base node for /dev/uno at 57600 baud | upstream_code | launch/includes/adlink_ddsbot_base.launch.xml:7-8 |
| The launch file declares wheel_separation (0.15 m) and wheel_radius (0.0335 m) arguments | upstream_code | launch/includes/adlink_ddsbot_base.launch.xml:3-4 |
| The firmware parses the third field as the checksum and compares it with the command length minus 2 minus the checksum length | upstream_code | document/arduino/motor_control/motor_control.ino:109-118 |
| The firmware declares min_ref=110 and max_ref=350 | upstream_code | document/arduino/motor_control/motor_control.ino:59-60 |
| The firmware adjusts nonzero wheel references using max_ref, min_ref and a steering correction | upstream_code | document/arduino/motor_control/motor_control.ino:120-158 |
| When the left wheel-speed reference is exactly zero, the firmware sets the left PWM outputs to 0 | upstream_code | document/arduino/motor_control/motor_control.ino:281-286 |
| When the right wheel-speed reference is exactly zero, the firmware sets the right PWM outputs to 0 | upstream_code | document/arduino/motor_control/motor_control.ino:337-342 |
| The firmware reports the two wheel speeds as integers in deg/sec with a CRLF terminator | upstream_code | document/arduino/motor_control/motor_control.ino:387-390 |
| The firmware declares timer_period=20 ms, odom_pub_period=40 ms and their ratio as odom_pub_thres | upstream_code | document/arduino/motor_control/motor_control.ino:31-33 |
| The firmware's odom_pub compile-time flag is false | upstream_code | document/arduino/motor_control/motor_control.ino:20 |
| When odom_pub is false the firmware prints '0,0' instead of the measured wheel speeds | upstream_code | document/arduino/motor_control/motor_control.ino:392-394 |
| The firmware sets the serial read timeout to 50 ms | upstream_code | document/arduino/motor_control/motor_control.ino:93 |
| On a bad checksum the firmware returns without zeroing the wheel references; the assignments are commented out | upstream_code | document/arduino/motor_control/motor_control.ino:109-118 |
| When no serial input is available, the firmware loop only delays 50 ms | upstream_code | document/arduino/motor_control/motor_control.ino:160-162 |

## Bounds and telemetry

Body velocity, yaw rate and duration are operator_required. Launch geometry defaults and firmware reference constants are not body velocity limits. The firmware applies steering corrections as well as min_ref/max_ref; these constants are not presented as a symmetric physical speed envelope. Report timing is described by the actual timer and counter code, not the inconsistent upstream 20 Hz comment.

The pinned firmware has odom_pub=false and prints 0,0 regardless of movement. The fake returns those same placeholder zeros after a nonzero request; neither the wheel fields nor derived body velocities are sensed odometry in this profile. Action distance/heading integrate the requested twist and elapsed command time only.

## Blocked stop path

The zero-speed frame is an unacknowledged request. Firmware checksum failures return without clearing the previous references, and absent serial input only delays the main loop. If valid zeros reach the controller, its zero branches set the four PWM outputs to zero; this does not prove the request arrived or that a moving base reached standstill. No source-backed physical stop is documented.

The stop action is no longer safe_state=True. The e-stop attempts zero speed, then fails SAFE_STATE_UNREACHED and keeps the latch. NO_HARDWARE_FREE_PATH remains until an acknowledged stop and independent hardware stop evidence exist. The unchanged native Python 3 serial port also has no write timeout, ignores short write counts and can race concurrent commands; its source was inspected but it was not opened. Stock test_gate is retained and fails while the package is blocked.

The primary source and firmware carry Apache-2.0. Evidence is contract_checked only; reviewed_by remains null.
