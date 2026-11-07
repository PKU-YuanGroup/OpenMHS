# Facts and tags for gh.dobot-arm/tcp-ip-python-v4

Every fact cites its source at commit `55ec1ec82201aaf2e6d54aa47b6272bbaa14c815`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The SDK is a TCP/IP client: it sends a command string over a socket and reads one text reply per command | upstream_code | dobot_sdk/core/connection.py:357-369 |
| A command line is sent with a newline appended and the reply is decoded as UTF-8 and stripped | upstream_code | dobot_sdk/core/connection.py:248-272 |
| The dashboard command port is 29999 and the feedback port is 30004 | vendor_doc | assets/SDK_API文档_完整版.md:99-108 |
| The reply to a command has the form 'ErrorID,{...},Command(...);', for example '0,{[1537,2048]},GetErrorID();' | vendor_doc | assets/SDK_API文档_完整版.md:1206-1218 |
| The error-code table lists 0 as no error and 1537 as the emergency stop triggered | vendor_doc | assets/SDK_API文档_完整版.md:2169-2170 |
| The SDK supports the CRA (CR3A, CR5, CR10, CR16), E6, CRAF and NovaLite families | vendor_doc | README.md:282-290 |
| The README warns to make sure the robot is in a safe position before running | vendor_doc | README.md:306 |
| The vendor text requires an easily reachable emergency stop button, a slow speed for the first run and a working range with no people in it | vendor_doc | assets/SDK_API文档_完整版.md:2382-2388 |
| MovJ takes a six-value pose and a coordinate type; with the joint type the pose is six joint angles in degrees and with the Cartesian type six values in millimetres and degrees | vendor_doc | assets/SDK_API文档_完整版.md:253-280 |
| The SDK formats every coordinate of a pose with six decimal places before sending it | upstream_code | dobot_sdk/api/motion.py:31-46 |
| MovJ and MovL are queue commands: they join the motion queue and are executed in order, unlike the immediate commands such as GetPose and Stop | vendor_doc | assets/SDK_API文档_完整版.md:2362-2365 |
| GetAngle answers with 'ErrorID,{j1,j2,j3,j4,j5,j6},GetAngle();' and GetPose with 'ErrorID,{x,y,z,rx,ry,rz},GetPose();' | vendor_doc | assets/SDK_API文档_完整版.md:1244-1267 |
| GetErrorID answers with 'ErrorID,{[error1,error2,...]},GetErrorID();' and 0 in the error-code table means no error | vendor_doc | assets/SDK_API文档_完整版.md:1206-1218 |
| RobotMode reports 1 initialising, 2 manual, 3 automatic, 4 remote and 9 error | vendor_doc | assets/SDK_API文档_完整版.md:1221-1235 |
| Stop stops the motion command queue the controller was given and any running script | upstream_code | dobot_sdk/api/robot_control.py:83-85 |
| EmergencyStop(mode) presses the emergency stop with mode 1 and releases it with mode 0 | vendor_doc | assets/SDK_API文档_完整版.md:893-910 |
| The upstream connection class exposes the command exchange as send_receive_text and the connection state as the is_connected property | upstream_code | dobot_sdk/core/connection.py:357-375 |
| The upstream SDK requests TCP control mode before it moves: every quick-start example calls RequestControl first | upstream_code | dobot_sdk/api/robot_control.py:22-34 |

Limits: the clone states no joint travel range and no workspace (the SDK serves several arm families with different
ranges, README.md:282-290), so every motion input is `Limit.operator_required`: the site declares the envelope in
`site-limits.json` and the package ships `site-limits.example.json` as a template. Until the operator fills it, every
move is refused with `MHS.SAFETY.LIMITS_UNSET`.

| capability | path | bound | source | ref |
|---|---|---|---|---|
| cap.motion.joint_position.v1 | joint_positions (per joint, rad) | operator_required: the clone states no joint travel range | | |
| cap.motion.cartesian_pose.v1 | position.x, .y, .z (mm) | operator_required: the clone states no workspace | | |
| cap.motion.cartesian_pose.v1 | orientation.roll, .pitch, .yaw (rad) | operator_required: the clone states no orientation range | | |

Safety: the native stop is `EmergencyStop(1)` (the controller's emergency stop, mode 1 presses it,
assets/SDK_API文档_完整版.md:893-910), reached through the connection the driver talks over. The driver declares
`risk = "R2"`, above the card's R1 floor, because a six-axis arm is moving machinery; the independent stop
(`estop_physical_ref`) is the controller's emergency-stop button, which the vendor's safety notes tell the user to keep
within reach (assets/SDK_API文档_完整版.md:2384). The two reach tolerances in `driver.py` (`JOINT_TOLERANCE_RAD`, `POSE_TOLERANCE_MM`) are the driver's
own criteria for "reached", not device specifications; they are reported in the action outputs.

Tags: robot arm, dobot, tcp ip, joint motion, cartesian motion, stop
