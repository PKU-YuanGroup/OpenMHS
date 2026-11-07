OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.universalrobots/universal_robots_ros2_driver

Every fact cites the pinned clone at commit `7e031424bc7a3e590d65fe297214ac21e1f9ffdd`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used when the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Scope

The package exposes two private ROS 2 services of the upstream `dashboard_client`
node: `~/stop` and `~/program_running`. Stop means stopping dashboard program
execution; it is not a physical emergency stop, does not sense zero velocity and
does not isolate power. The following upstream services are deliberately not
exposed: play, resume, brake release, power on/off, unlock protective stop, clear
operational mode, restart safety, raw request, shutdown and every motion, joint or
cartesian command. The node also exposes protected-mode and configuration services
that this package does not bind.

The node registers private names, so `source_name` records the exact upstream tokens
`~/stop` and `~/program_running`. The configured endpoints `/dashboard_client/stop`
and `/dashboard_client/program_running` assume the node is launched with the
`dashboard_client` name from `ur_robot_driver/launch/ur_dashboard_client.launch.py:69`
in the root namespace. A deployment that namespaces or remaps the node must expose
the same absolute endpoints; this package does not discover the graph.

## Facts

| fact | source | ref |
|---|---|---|
| DashboardClientROS::initServices registers the private `~/stop` service and binds it to commandStopWithResponse; the accompanying comment calls it a stop of program execution. | upstream_code | ur_robot_driver/src/dashboard_client_ros.cpp:217-219 |
| createDashboardTriggerSrv creates a std_srvs::srv::Trigger service and maps response.ok to resp->success; an UrException sets resp->success to false. | upstream_code | ur_robot_driver/include/ur_robot_driver/dashboard_client_ros.hpp:118-134 |
| initServices registers the private `~/program_running` service with the ur_dashboard_msgs::srv::IsProgramRunning type. | upstream_code | ur_robot_driver/src/dashboard_client_ros.cpp:227-230 |
| handleRunningQuery calls commandRunningWithResponse through dashboardCallWithChecks and sets resp->program_running from the acknowledged `running` value only when resp->success is true. | upstream_code | ur_robot_driver/src/dashboard_client_ros.cpp:567-575 |
| dashboardCallWithChecks assigns resp->success from the dashboard response and resp->answer from its message; both exception paths set resp->success to false. | upstream_code | ur_robot_driver/include/ur_robot_driver/dashboard_client_ros.hpp:140-162 |
| IsProgramRunning.srv declares exactly answer, program_running and success, and no request fields. | upstream_code | ur_dashboard_msgs/srv/IsProgramRunning.srv:1-4 |
| The dashboard client launch entry names the node `dashboard_client`. | upstream_code | ur_robot_driver/launch/ur_dashboard_client.launch.py:66-69 |
| The dashboard_client_node executable creates the node with the base name `ur_dashboard_client`. | upstream_code | ur_robot_driver/src/dashboard_client_node.cpp:48 |

## Service contract

`~/stop` is a `std_srvs::srv::Trigger` service. The request is empty. The response
carries `success` and `message`; `success` is the application result, separate from
the rosbridge `service_response.result` transport flag. The driver requires
`success == true` before reporting an acknowledged stop, and maps that same boolean
to its `acknowledged` output.

`~/program_running` is an `ur_dashboard_msgs::srv::IsProgramRunning` service. The
request is empty. The response carries `answer`, `program_running` and `success`.
The upstream callback fills `program_running` only when `success` is true, so the
driver requires `success == true` and returns only the `program_running` boolean.
A missing `success` or a false `success` is a failure; it is never reported as a
stopped or not-running state.

## Limits

The package exposes no numeric input: the stop service has a fixed empty request and
the program-running query has an empty request. There is therefore no device bound to
declare and no `Limit`; the absence is not an unset operator bound. The rosbridge
client timeout and message-size values are client execution bounds, not device
limits.

## Safety

The device is hardware at R2 because the dashboard controls a robot arm. The
`x-cap.universalrobots.dashboard_stop.v1` action is input-free,
`Action(safe_state=True)` and is also the fixed-request native stop binding on the
same acknowledged `~/stop` service. The stop service acknowledges a dashboard program
stop, not a safety-rated physical stop, zero velocity, power isolation or a
hardware safety certification. No independent hardware e-stop line is cited from
the clone, so `estop_physical_ref` is not claimed. The latch is software in the
runtime; the physical e-stop, if one is installed on the robot, stays authoritative.
This package is model-authored and `reviewed_by` stays null, so the ROS hardware
backend is refused until a human signs the lock.

## Tags

`ros`, `ros2`, `universal-robots`, `ur`, `dashboard`, `program-stop`
