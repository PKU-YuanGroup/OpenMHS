# Facts and tags for gh.zayfod/pycozmo

Every fact cites its source at commit `1b6dcd9b869a3784f1d8b02e820bb033f95fd13a`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Client is the protocol client and high-level API class of the library | upstream_code | pycozmo/client.py:41 |
| The client starts with the head at its minimum angle and the lift at its minimum height | upstream_code | pycozmo/client.py:70-73 |
| RobotState packets update the reported pose, head angle, wheel speeds, lift position, battery voltage, acceleration, gyro and status | upstream_code | pycozmo/client.py:278-295 |
| robot_picked_up and robot_moving follow the picked-up and wheels-moving events the client handles | upstream_code | pycozmo/client.py:315-327 |
| set_head_angle sends a SetHeadAngle packet with the angle in radians | upstream_code | pycozmo/client.py:364-368 |
| set_lift_height sends a SetLiftHeight packet with the height in millimetres | upstream_code | pycozmo/client.py:374-378 |
| stop_all_motors sends a StopAllMotors packet | upstream_code | pycozmo/client.py:394-396 |
| The minimum head angle is -25 degrees and the maximum is 44.5 degrees | upstream_code | pycozmo/robot.py:33-36 |
| The minimum lift height is 32.0 mm and the maximum is 92.0 mm | upstream_code | pycozmo/robot.py:38-41 |
| The lift arm is 66.0 mm long and its pivot point is 45.0 mm above the ground | upstream_code | pycozmo/robot.py:43-46 |
| The minimum and maximum lift arm angles are asin((height - pivot) / arm length) of the minimum and maximum heights | upstream_code | pycozmo/robot.py:48-51 |
| LiftPosition builds a height from an arm angle as sin(angle) * arm length + pivot height and reports the angle of a height back | upstream_code | pycozmo/robot.py:146-171 |
| The head is controlled with the DriveHead and SetHeadAngle messages and its angle is read from the head_angle_rad field of RobotState, whose head_in_pos status flag says whether it is in position | vendor_doc | docs/functions.md:150-154 |
| The lift is controlled with the DriveLift and SetLiftHeight messages and its height is read from the lift_height_mm field of RobotState, whose lift_inpos status flag says whether it is in position | vendor_doc | docs/functions.md:169-173 |
| The head motor is stopped with the StopAllMotors message | vendor_doc | docs/functions.md:156 |
| The README connects a robot with Client(), start(), connect() and wait_for_robot(), and disconnects and stops it afterwards | vendor_doc | README.md:35-43 |
| The README warns that the project is a tool for exploring the robot, unstable and heavily under development | vendor_doc | README.md:12-13 |

Limits: one, on the `joint_positions` input of `cap.motion.joint_position.v1`, and it is `Limit.operator_required`.
The clone states the head travel as -25 to 44.5 degrees (`pycozmo/robot.py:33-36`) and the lift travel as the heights
32.0 to 92.0 mm (`pycozmo/robot.py:38-41`); the class requires radians, and a lift height becomes the arm angle
`asin((height - pivot) / arm length)` with the arm 66.0 mm long and the pivot 45.0 mm high (`pycozmo/robot.py:43-51`).
That angle is shown on no line of the clone, so the site states both ranges: `site-limits.example.json` carries the
converted values, and until an overlay is loaded every move is refused (`MHS.SAFETY.LIMITS_UNSET`).

Safety: the e-stop calls `Client.stop_all_motors` (`pycozmo/client.py:394-396`), the message the clone documents as
stopping the head and lift motors (`docs/functions.md:156, 175`); `safe_state` says the same. The driver is R1
(hardware, the card's floor, and the risk class of the joint_position class), so it needs an e-stop and a safe-state
sentence but no independent hardware stop: no text of the clone documents one for the robot.

Not exposed: the wheel motors, the lights, the display, the speaker, the camera stream, the animations, the procedural
face, the behaviour engine and the IR LED. The client is asynchronous: the joint action sends both commands and waits
a bounded time for the reported state to reach the targets, so `reached` can be false when a move takes longer than
that wait. The hardware backend (`native.py`) was never run.

Tags: robot, cozmo, head, lift, joint control, pycozmo
