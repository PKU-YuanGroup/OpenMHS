"""OpenMHS rosbridge driver for the UR ROS 2 dashboard client.

The upstream ``dashboard_client`` node is a C++ ROS 2 node; this package is a
configuration-only :class:`RosDriver` and declares no Python native class.
The scope is deliberately narrow: stop dashboard program execution through
the private ``~/stop`` Trigger service and observe the private
``~/program_running`` IsProgramRunning service.  It does not expose play,
resume, brake release, power-on, protective-stop unlock, fault clearing, raw
dashboard requests, joint/cartesian motion, or node shutdown.

Every endpoint, type and fact cites the pinned clone at
7e031424bc7a3e590d65fe297214ac21e1f9ffdd.  The fake transport is ROS-free;
no ROS graph or robot is contacted.  The stop service acknowledges a dashboard
program stop, not a physical emergency stop, sensed zero velocity or
power isolation.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: The node's private Trigger service is registered during initServices.  The
#: cited block also names commandStopWithResponse and calls the stop a program
#: execution stop.
_STOP_REF = "ur_robot_driver/src/dashboard_client_ros.cpp:217-219"

#: createDashboardTriggerSrv declares the std_srvs::srv::Trigger service type
#: and maps the upstream response's ok flag to resp->success.
_STOP_TYPE_REF = "ur_robot_driver/include/ur_robot_driver/dashboard_client_ros.hpp:118-123"

#: The node registers the private IsProgramRunning service at these lines; the
#: same block spells out the fully qualified type.
_PROGRAM_RUNNING_REF = "ur_robot_driver/src/dashboard_client_ros.cpp:227-230"

#: The launch file names the dashboard client node "dashboard_client".  The
#: configured endpoint suffix is an explicit deployment assumption: the node
#: must be launched in the root namespace (or remapped to this name).
_NODE_NAME_REF = "ur_robot_driver/launch/ur_dashboard_client.launch.py:66-69"

#: The Trigger request carries no arguments.  ``success`` is the application
#: result of the dashboard call; ``result`` below is only the ROS transport
#: status.  The output acknowledges that the dashboard accepted the stop; it
#: does not assert a stopped joint or a physical emergency stop.
_STOP = {
    "service": "/dashboard_client/stop",
    "type": "std_srvs/srv/Trigger",
    "source_name": "~/stop",
    "source_ref": _STOP_REF,
    "type_ref": _STOP_TYPE_REF,
    "success": {"path": "success", "equals": True},
    "result": {"map": {"acknowledged": "success"}},
}

#: An observation of the private IsProgramRunning service.  The upstream
#: callback sets program_running only when the dashboard call succeeded, so
#: the application success predicate is checked before the field is mapped.
_PROGRAM_RUNNING = {
    "service": "/dashboard_client/program_running",
    "type": "ur_dashboard_msgs/srv/IsProgramRunning",
    "source_name": "~/program_running",
    "source_ref": _PROGRAM_RUNNING_REF,
    "operation": "read",
    "success": {"path": "success", "equals": True},
    "result": {"map": {"program_running": "program_running"}},
}


class UniversalRobotsRos2Driver(RosDriver):
    device_id = "ur_dashboard"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeUniversalRobotsRos2Driver"}
    tags = ["ros", "ros2", "universal-robots", "ur", "dashboard", "program-stop"]
    display_name = "Universal Robots ROS 2 dashboard client"
    vendor = "Universal Robots"
    facts = [
        Fact("DashboardClientROS::initServices registers the private '~/stop' service and binds it to "
             "commandStopWithResponse; the accompanying comment calls it a stop of program execution.",
             source="upstream_code", ref=_STOP_REF),
        Fact("createDashboardTriggerSrv creates a std_srvs::srv::Trigger service and maps response.ok to "
             "resp->success; an UrException sets resp->success to false.",
             source="upstream_code", ref="ur_robot_driver/include/ur_robot_driver/dashboard_client_ros.hpp:118-134"),
        Fact("initServices registers the private '~/program_running' service with the "
             "ur_dashboard_msgs::srv::IsProgramRunning type.",
             source="upstream_code", ref=_PROGRAM_RUNNING_REF),
        Fact("handleRunningQuery calls commandRunningWithResponse through dashboardCallWithChecks and sets "
             "resp->program_running from the acknowledged 'running' value only when resp->success is true.",
             source="upstream_code", ref="ur_robot_driver/src/dashboard_client_ros.cpp:567-575"),
        Fact("dashboardCallWithChecks assigns resp->success from the dashboard response and resp->answer from "
             "its message; both exception paths set resp->success to false.",
             source="upstream_code", ref="ur_robot_driver/include/ur_robot_driver/dashboard_client_ros.hpp:140-162"),
        Fact("IsProgramRunning.srv declares exactly answer, program_running and success, and no request fields.",
             source="upstream_code", ref="ur_dashboard_msgs/srv/IsProgramRunning.srv:1-4"),
        Fact("The dashboard client launch entry names the node 'dashboard_client'.",
             source="upstream_code", ref=_NODE_NAME_REF),
        Fact("The dashboard_client_node executable creates the node with the base name 'ur_dashboard_client'.",
             source="upstream_code", ref="ur_robot_driver/src/dashboard_client_node.cpp:48"),
    ]
    safe_state = (
        "Dashboard program execution is stopped by the acknowledged UR dashboard stop service; this is not a "
        "physical emergency stop and does not prove zero velocity or power isolation."
    )

    # No automatic resource fields are declared: the runtime's empty snapshot
    # needs no dashboard service call, and the program-running state is read
    # explicitly through its own acknowledged service action.
    commands = {
        "x-cap.universalrobots.dashboard_stop.v1": _STOP,
        "x-cap.universalrobots.program_running.v1": _PROGRAM_RUNNING,
    }
    actions = {
        "x-cap.universalrobots.dashboard_stop.v1": Action(
            name="stop_dashboard_program",
            verb="invoke",
            safe_state=True,
            description=(
                "Stop the active dashboard program through the acknowledged UR dashboard stop service; "
                "this does not command joint motion or claim a physical emergency stop"
            ),
            output={
                "acknowledged": Field(
                    "boolean",
                    description="True when the dashboard server acknowledged the stop request",
                ),
            },
        ),
        "x-cap.universalrobots.program_running.v1": Action(
            name="read_program_running",
            verb="read",
            description="Read the dashboard program-running flag through the acknowledged IsProgramRunning service",
            output={
                "program_running": Field(
                    "boolean",
                    description="True when the dashboard reports a program running",
                ),
            },
        ),
    }
    # The same fixed-request service is the native stop binding.  The safe-state
    # permission comes from the Action(safe_state=True) declaration; the runtime
    # latches before the e-stop path. Normal safe-state invocation does not latch;
    # the same action remains callable during an existing latch.
    safety_bindings = {"estop": _STOP}
