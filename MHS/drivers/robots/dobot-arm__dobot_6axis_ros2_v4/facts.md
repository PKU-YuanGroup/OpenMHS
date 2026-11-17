# Facts and limits for gh.dobot-arm/dobot_6axis_ros2_v4

Every fact and limit cites the pinned clone at commit `ec201c40d5db63185a3593ec9c39f80fe25aa527`.
The same facts are written into `driver.py` (`facts = [...]`); `reference.json` is generated from the driver.

## Endpoints and types

| fact | source | ref |
|---|---|---|
| The node declares robot_ip_address, robot_type, trajectory_duration, robot_node_name (default dobot_bringup_ros2) and robot_number (default 1) as ROS parameters. | upstream_code | `dobot_bringup_v4/src/cr_robot_ros2.cpp:14-19` |
| When robotNumber > 1 the node assigns kRobotName = robotNodeName + '/'. | upstream_code | `dobot_bringup_v4/src/cr_robot_ros2.cpp:31-34` |
| The node names the EnableRobot service '/dobot_bringup_ros2/srv/EnableRobot'. | upstream_code | `dobot_bringup_v4/src/cr_robot_ros2.cpp:36` |
| The node names the Stop service '/dobot_bringup_ros2/srv/Stop'. | upstream_code | `dobot_bringup_v4/src/cr_robot_ros2.cpp:57` |
| The node names the MovJ service '/dobot_bringup_ros2/srv/MovJ'. | upstream_code | `dobot_bringup_v4/src/cr_robot_ros2.cpp:115` |
| The node names the MovL service '/dobot_bringup_ros2/srv/MovL'. | upstream_code | `dobot_bringup_v4/src/cr_robot_ros2.cpp:116` |
| The node registers the MovJ service with the generated type dobot_msgs_v4::srv::MovJ. | upstream_code | `dobot_bringup_v4/src/cr_robot_ros2.cpp:241` |
| The EnableRobot request formatter returns the dashboard text EnableRobot(). | upstream_code | `dobot_bringup_v4/src/parseTool.cpp:7-13` |
| The Stop request formatter returns the dashboard text Stop(). | upstream_code | `dobot_bringup_v4/src/parseTool.cpp:153-159` |
| The MovJ parser formats a..f with three decimals, sends joint={...} when mode is true and pose={...} when it is false, and appends any non-empty param_value strings. | upstream_code | `dobot_bringup_v4/src/parseTool.cpp:553-579` |
| The MovL parser uses the same mode switch and formatting as MovJ. | upstream_code | `dobot_bringup_v4/src/parseTool.cpp:580-606` |
| MovJ is a queue command: the controller answers ErrorID,{ResultID},MovJ(...); and ResultID is the algorithm queue id. | vendor_doc | `V4新增指令/README.md:2605-2655` |
| MovL is a queue command: the controller answers ErrorID,{ResultID},MovL(...); and ResultID is the algorithm queue id. | vendor_doc | `V4新增指令/README.md:2670-2720` |
| Stop() is documented to stop motion (or a script); it can stop jogging, script execution, joint motion and a series of motions. | vendor_doc | `V4新增指令/README.md:1012-1030` |
| EnableRobot() enables the robot. | vendor_doc | `V4新增指令/README.md:373-380` |
| A dashboard reply has the form ErrorID,{...},Command(...); the error id is the number before the first brace. | vendor_doc | `V4新增指令/README.md:395-397` |
| The reply parser stores the integer before the first '{' in res and, for a _f command, the first brace-delimited payload in robot_return. | upstream_code | `dobot_bringup_v4/src/command.cpp:164-212` |
| The dashboard command loop reads until it sees ';', passes timeout=0 to tcpRecv and calls sleep(0.01) on a false return; it has no overall deadline of its own. | upstream_code | `dobot_bringup_v4/src/command.cpp:112-160` |
| TcpClient::tcpRecv returns false when select returns zero (no ready descriptor); when select is positive it proceeds to read. | upstream_code | `dobot_bringup_v4/src/tcp_socket.cpp:91-104` |
| doTcpCmd catches TcpClientException and logs the error without assigning err_id in the catch block. | upstream_code | `dobot_bringup_v4/src/command.cpp:157-160` |
| callRosService calls doTcpCmd and then returns true. | upstream_code | `dobot_bringup_v4/src/command.cpp:221-228` |
| The Stop callback passes response->res to callRosService. | upstream_code | `dobot_bringup_v4/src/cr_robot_ros2.cpp:699-702` |
| The node opens a dashboard TcpClient to port 29999 and a feedback TcpClient to port 30004. | upstream_code | `dobot_bringup_v4/src/command.cpp:11-12` |
| The README states the robot control port is 29999 and the feedback port is 30004. | vendor_doc | `README.md:34-36` |
| The node publishes sensor_msgs/msg/JointState on the relative topic 'joint_states'. | upstream_code | `dobot_bringup_v4/src/main.cpp:22` |
| The JointState message carries six positions copied from getJointState. | upstream_code | `dobot_bringup_v4/src/main.cpp:50-66` |
| When the feedback connection is down the node copies the last valid joint positions, or zeros before any valid data. | upstream_code | `dobot_bringup_v4/src/main.cpp:50-59` |
| The node publishes dobot_msgs_v4/msg/ToolVectorActual on the relative topic dobot_msgs_v4/msg/ToolVectorActual. | upstream_code | `dobot_bringup_v4/src/main.cpp:30` |
| The ToolVectorActual publisher fills x, y, z, rx, ry, rz from getToolVectorActual and publishes only while connected. | upstream_code | `dobot_bringup_v4/src/main.cpp:69-78` |
| The node creates a dobot_msgs_v4/msg/RobotStatus publisher on the relative topic dobot_msgs_v4/msg/RobotStatus. | upstream_code | `dobot_bringup_v4/src/main.cpp:27` |
| The RobotStatus publisher fills is_enable and is_connected from the node's connection state. | upstream_code | `dobot_bringup_v4/src/main.cpp:81-83` |
| isEnable() returns robot_mode == 5; isConnected() returns the dashboard TCP connect state && the feedback TCP connect state. | upstream_code | `dobot_bringup_v4/src/command.cpp:266-289` |
| The publisher rate is the JointStatePublishRate ROS parameter, default 10 Hz. | upstream_code | `dobot_bringup_v4/src/main.cpp:39` |
| The MovJ service request has bool mode, float64 a..f and string[] param_value; the response has string robot_return and int32 res. | upstream_code | `dobot_msgs_v4/srv/MovJ.srv:1-11` |
| The MovL service request has the same fields as MovJ and the same response. | upstream_code | `dobot_msgs_v4/srv/MovL.srv:1-11` |
| The Stop service has an empty request and returns int32 res. | upstream_code | `dobot_msgs_v4/srv/Stop.srv:1-2` |
| The EnableRobot service has an empty request and returns int32 res. | upstream_code | `dobot_msgs_v4/srv/EnableRobot.srv:1-2` |
| ToolVectorActual declares float64 x, y, z, rx, ry, rz. | upstream_code | `dobot_msgs_v4/msg/ToolVectorActual.msg:1-6` |
| RobotStatus declares bool is_enable and bool is_connected. | upstream_code | `dobot_msgs_v4/msg/RobotStatus.msg:1-2` |
| The README lists the supported models as CR3, CR5, CR7, CR10, CR12, CR16, CR20, CR30H, CR10AF, E6/ME6, Nova2 and Nova5. | vendor_doc | `README.md:269-278` |
| The README instructs the user to ensure the robot is in a safe position, that ports 29999 and 30004 are free, and that the robot is in remote TCP/IP control mode. | vendor_doc | `README.md:303-307` |

## Limits

The clone states no joint travel, Cartesian workspace or orientation range; it serves several arm
families (README.md:269-278). All motion inputs are therefore `Limit.operator_required`: every move
is refused with `MHS.SAFETY.LIMITS_UNSET` until a site supplies `site-limits.json`.
`site-limits.example.json` is an example overlay only, not a device fact.

| capability | path | bound |
|---|---|---|
| x-cap.dobot-arm.move_joint.v1 | `joint_positions` | operator_required: the clone states no joint travel |
| x-cap.dobot-arm.move_pose.v1 | `position.x`, `position.y`, `position.z` | operator_required: the clone states no workspace |
| x-cap.dobot-arm.move_pose.v1 | `orientation.roll`, `orientation.pitch`, `orientation.yaw` | operator_required: the clone states no orientation range |

## Safety

Risk remains R2 for the arm motion hazard. Model review blocks this package on
`NO_HARDWARE_FREE_PATH`: the native Stop response cannot distinguish a successful exchange from a
suppressed TCP exception or malformed brace-less reply. `doTcpCmd` catches the exception without
setting the error id (command.cpp:157-160); `callRosService` then returns true (:221-228).
A ROS response with default `res=0` is therefore not evidence of a controller acknowledgement.
The e-stop binding and the `safe_state=True` declaration were removed. An e-stop fails with
`MHS.SAFETY.SAFE_STATE_UNREACHED` and leaves the latch held; it does not send Stop automatically
or establish the arm's state. An explicit reset releases only the latch and resumes nothing.
The ordinary Stop action reports `service_returned`, not a stopped arm. Move and EnableRobot
outputs use the same term because their response path also suppresses errors. Nonzero native
codes remain failures. The fake models the indistinguishable default-zero failure and its
Stop/EnableRobot responses contain only the fields in those service definitions.

The node's command wait has no overall deadline and runs through the main thread's spin_some;
a lost reply can prevent later service callbacks. The reported `sleep(0.01)` is the literal call,
not an established 10 ms wait. A zero select timeout polls readiness; it does not prevent a read
when the descriptor is ready. Joint feedback may be stale or zero while disconnected and
ToolVectorActual then goes silent. These topics do not establish a safe stopped state.
No independent physical emergency-stop reference is provided. A corrected, reviewed native
stop/confirmation path is needed before this package can be unblocked. No live ROS graph or
hardware was run, and reviewed_by remains null.

Tags: robot arm, dobot, ros2, joint motion, cartesian motion, stop
