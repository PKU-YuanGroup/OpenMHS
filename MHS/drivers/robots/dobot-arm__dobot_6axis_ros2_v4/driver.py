"""OpenMHS driver for gh.dobot-arm/dobot_6axis_ros2_v4: a Dobot V4 six-axis arm through the
pinned C++ ROS 2 node's services and feedback topics.

The upstream device interface is a ROS 2 graph, not a Python object: the ``dobot_bringup_v4_node``
(``CRRobotRos2``) owns one dashboard TCP connection to port 29999 and one feedback connection to
port 30004, and exposes the dashboard commands as services under
``/dobot_bringup_ros2/srv/<Name>`` (``dobot_bringup_v4/src/cr_robot_ros2.cpp:36-116`` and
``:165-286``).  This package is therefore a configuration-only :class:`RosDriver` over rosbridge.
It declares no Python native class.  The Python demo in the card's entry symbol
(``dobot_demo/dobot_demo/demo.py:10-13``) is only an rclpy client of those same services and has no
stop, fault or state method; wrapping it would not express the device.

Scope and limits:

* Reads: the six joint positions in radians and the tool pose from the node's feedback publishers,
  plus the enabled/connected flags.  The node publishes the last valid joint positions (or zeros)
  when the feedback connection is down (``main.cpp:50-59``), so a stale-looking read is an
  observation, not proof that the arm is still.
* Moves: ``MovJ`` with ``mode=true`` (joint target, degrees) and ``MovL`` with ``mode=false``
  (Cartesian pose, mm and degrees).  Both are *queue* commands: the controller answers with an
  algorithm queue id as soon as it accepted the command (``V4新增指令/README.md:2605-2655``), the raw brace payload is returned as ``result_id``. A callback res=0 alone does not prove acceptance.
* Model review blocks the stop with NO_HARDWARE_FREE_PATH. Although Stop() is documented to stop
  motion, doTcpCmd catches TCP exceptions without setting the response error, and callRosService
  then returns true (command.cpp:157-160, 221-228). The same res=0 response can describe an
  acknowledged Stop or a failed exchange. No safe-state binding is retained. The ordinary Stop
  action reports only that its ROS service returned res=0; it certifies no controller state.
* The one re-enable action is the input-free ``EnableRobot`` service (the vendor command that
  enables the robot, ``V4新增指令/README.md:373-380``).  There is no reset hook; a reset only
  releases the MHS latch (SAFE-042) and the operator calls the re-enable when the native state
  needs it.

The joint-travel, Cartesian and orientation envelopes are ``Limit.operator_required``: the clone
serves CR3/CR5/CR7/CR10/CR12/CR16/CR20/CR30H, CR10AF, E6/ME6, Nova2 and Nova5 with different
envelopes (``README.md:269-278``) and states no numbers.  ``site-limits.example.json`` is an
example overlay only; until an operator supplies ``site-limits.json`` every move input is refused.

This package is model-authored and unreviewed.  Nothing here ran on an arm or against a live ROS
graph; the loader refuses the hardware backend (R2) until a human signs ``reviewed_by``, and every
``RosDriver`` hardware backend additionally requires that human hardware review.

DEVIATION FROM THE CARD: the card names the ``PythonObjectDriver`` family and the demo entry
``dobot_demo.demo:adderClient``.  That Python class has only ``initialization``, ``point`` and
``set_do`` and no stop, fault or state route, so it cannot express the device's safe stop.  The
pinned ROS 2 service interface does, and the SDK's RosDriver is the matching helper.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# --- pinned source references ---------------------------------------------------------------

#: The node's default name and the parameters that select the robot and the service prefix.
_PARAMS_REF = "dobot_bringup_v4/src/cr_robot_ros2.cpp:14-19"
#: ``robot_number > 1`` adds ``robot_node_name + "/"`` to every service name.
_ROBOT_NUMBER_REF = "dobot_bringup_v4/src/cr_robot_ros2.cpp:31-34"
#: Service name literals (the default single-robot branch leaves ``kRobotName`` empty).
_ENABLE_ENDPOINT_REF = "dobot_bringup_v4/src/cr_robot_ros2.cpp:36"
_STOP_ENDPOINT_REF = "dobot_bringup_v4/src/cr_robot_ros2.cpp:57"
_MOVJ_ENDPOINT_REF = "dobot_bringup_v4/src/cr_robot_ros2.cpp:115"
_MOVL_ENDPOINT_REF = "dobot_bringup_v4/src/cr_robot_ros2.cpp:116"
#: Service registrations, which also name the generated service types.
_ENABLE_TYPE_REF = "dobot_bringup_v4/src/cr_robot_ros2.cpp:165"
_STOP_TYPE_REF = "dobot_bringup_v4/src/cr_robot_ros2.cpp:186"
_MOVJ_TYPE_REF = "dobot_bringup_v4/src/cr_robot_ros2.cpp:241"
_MOVL_TYPE_REF = "dobot_bringup_v4/src/cr_robot_ros2.cpp:242"
#: The callbacks and the wire commands they build.
_ENABLE_WIRE_REF = "dobot_bringup_v4/src/parseTool.cpp:7-13"
_STOP_WIRE_REF = "dobot_bringup_v4/src/parseTool.cpp:153-159"
_MOVJ_WIRE_REF = "dobot_bringup_v4/src/parseTool.cpp:553-579"
_MOVL_WIRE_REF = "dobot_bringup_v4/src/parseTool.cpp:580-606"
#: The reply parser: the integer before the first '{' becomes res; the brace payload becomes robot_return.
_REPLY_REF = "dobot_bringup_v4/src/command.cpp:164-212"
#: The command exchange and its unbounded wait.
_SEND_REF = "dobot_bringup_v4/src/command.cpp:112-160"
_TCP_WAIT_REF = "dobot_bringup_v4/src/tcp_socket.cpp:91-104"
_TCP_CONNECT_REF = "dobot_bringup_v4/src/command.cpp:11-12"
#: Publishers in main.cpp.
_JOINTS_REF = "dobot_bringup_v4/src/main.cpp:22"
_JOINTS_ASSIGN_REF = "dobot_bringup_v4/src/main.cpp:50-66"
_JOINTS_STALE_REF = "dobot_bringup_v4/src/main.cpp:50-59"
_TOOL_REF = "dobot_bringup_v4/src/main.cpp:30"
_TOOL_ASSIGN_REF = "dobot_bringup_v4/src/main.cpp:69-78"
_STATUS_REF = "dobot_bringup_v4/src/main.cpp:27"
_STATUS_ASSIGN_REF = "dobot_bringup_v4/src/main.cpp:81-83"
_PUBLISH_RATE_REF = "dobot_bringup_v4/src/main.cpp:39"
#: Vendor documentation in the clone.
_DOC = "V4新增指令/README.md"
_README = "README.md"
_MOVJ_DOC_REF = f"{_DOC}:2605-2655"
_MOVL_DOC_REF = f"{_DOC}:2670-2720"
_STOP_DOC_REF = f"{_DOC}:1012-1030"
_ENABLE_DOC_REF = f"{_DOC}:373-380"
_REPLY_DOC_REF = f"{_DOC}:395-397"
_PORTS_REF = f"{_README}:34-36"
_MODELS_REF = f"{_README}:269-278"
_SAFETY_NOTE_REF = f"{_README}:303-307"
#: The service and topic definitions.
_MOVJ_SRV_REF = "dobot_msgs_v4/srv/MovJ.srv:1-11"
_MOVL_SRV_REF = "dobot_msgs_v4/srv/MovL.srv:1-11"
_STOP_SRV_REF = "dobot_msgs_v4/srv/Stop.srv:1-2"
_ENABLE_SRV_REF = "dobot_msgs_v4/srv/EnableRobot.srv:1-2"
_TOOL_MSG_REF = "dobot_msgs_v4/msg/ToolVectorActual.msg:1-6"
_STATUS_MSG_REF = "dobot_msgs_v4/msg/RobotStatus.msg:1-2"

#: The six joints of this repository's robot family; the publishers name joint1..joint6.
_JOINT_COUNT = 6

#: Ordinary Stop service request. The upstream response cannot certify a native stop.
_STOP = {
    "service": "/dobot_bringup_ros2/srv/Stop",
    "type": "dobot_msgs_v4/srv/Stop",
    "source_ref": _STOP_ENDPOINT_REF,
    "type_ref": _STOP_TYPE_REF,
    "request": {},
    "success": {"path": "res", "equals": 0},
}

#: The input-free re-enable.  `EnableRobot()` takes no request fields.
_ENABLE = {
    "service": "/dobot_bringup_ros2/srv/EnableRobot",
    "type": "dobot_msgs_v4/srv/EnableRobot",
    "source_ref": _ENABLE_ENDPOINT_REF,
    "type_ref": _ENABLE_TYPE_REF,
    "request": {},
    "success": {"path": "res", "equals": 0},
}

#: `MovJ` joint mode: `mode=true` selects `joint={a..f}`; the node formats six values with three
#: decimals (parseTool.cpp:553-579).  Joint values are sent in degrees.
_MOVE_JOINT = {
    "service": "/dobot_bringup_ros2/srv/MovJ",
    "type": "dobot_msgs_v4/srv/MovJ",
    "source_ref": _MOVJ_ENDPOINT_REF,
    "type_ref": _MOVJ_TYPE_REF,
    "request": {"mode": True, "param_value": []},
    "args": {
        "a": {"from": "input.joint_positions[0]", "unit": {"from": "rad", "to": "deg"}},
        "b": {"from": "input.joint_positions[1]", "unit": {"from": "rad", "to": "deg"}},
        "c": {"from": "input.joint_positions[2]", "unit": {"from": "rad", "to": "deg"}},
        "d": {"from": "input.joint_positions[3]", "unit": {"from": "rad", "to": "deg"}},
        "e": {"from": "input.joint_positions[4]", "unit": {"from": "rad", "to": "deg"}},
        "f": {"from": "input.joint_positions[5]", "unit": {"from": "rad", "to": "deg"}},
    },
    "result": {
        "service_returned": {"value": True},
        "result_id": {"from": "robot_return", "default": ""},
    },
    "success": {"path": "res", "equals": 0},
}

#: `MovL` Cartesian mode: `mode=false` selects `pose={x,y,z,rx,ry,rz}`; position is mm and
#: orientation is degrees.  The command omits `user`/`tool`, so the controller keeps its last
#: global frame selection (the vendor text states those are optional and default to the last set
#: value, V4新增指令/README.md:2663-2664).
_MOVE_POSE = {
    "service": "/dobot_bringup_ros2/srv/MovL",
    "type": "dobot_msgs_v4/srv/MovL",
    "source_ref": _MOVL_ENDPOINT_REF,
    "type_ref": _MOVL_TYPE_REF,
    "request": {"mode": False, "param_value": []},
    "args": {
        "a": {"from": "input.position.x"},
        "b": {"from": "input.position.y"},
        "c": {"from": "input.position.z"},
        "d": {"from": "input.orientation.roll", "unit": {"from": "rad", "to": "deg"}},
        "e": {"from": "input.orientation.pitch", "unit": {"from": "rad", "to": "deg"}},
        "f": {"from": "input.orientation.yaw", "unit": {"from": "rad", "to": "deg"}},
    },
    "result": {
        "service_returned": {"value": True},
        "result_id": {"from": "robot_return", "default": ""},
    },
    "success": {"path": "res", "equals": 0},
}

_JOINT_REASON = (
    "the clone serves several arm families with different joint travel (README.md:269-278) and "
    "states no range in this repository; the site supplies each joint's travel"
)
_POSITION_REASON = (
    "the clone states no Cartesian workspace; the reachable envelope depends on the arm and the "
    "cell, so the site supplies this bound"
)
_ORIENTATION_REASON = (
    "the clone states no wrist or tool orientation range; the site supplies this bound"
)

_SERVICE_RETURNED = Field(
    "boolean",
    description="The ROS callback returned res == 0; upstream suppresses transport errors, so "
                "this proves neither controller acknowledgement nor motion completion",
)
_RESULT_ID = Field(
    "string",
    description="The brace payload the pinned reply parser extracts from robot_return, for a queue "
                "command the controller's algorithm queue id; empty when the reply carried none",
)


class Dobot6AxisRos2(RosDriver):
    device_id = "dobot-arm"
    device_kind = "robot.arm"
    mode = "hardware"
    #: A six-axis arm is moving machinery: R2, above the card floor R0.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeDobot6AxisRos2"}
    tags = ["robot arm", "dobot", "ros2", "joint motion", "cartesian motion", "stop"]
    display_name = "Dobot V4 six-axis arm (ROS 2 bringup node)"
    vendor, model = "Dobot", "CR / Nova / E6 V4 six-axis family"
    facts = [
        Fact("The node declares robot_ip_address, robot_type, trajectory_duration, robot_node_name "
             "(default dobot_bringup_ros2) and robot_number (default 1) as ROS parameters.",
             source="upstream_code", ref=_PARAMS_REF),
        Fact("When robotNumber > 1 the node assigns kRobotName = robotNodeName + '/'.",
             source="upstream_code", ref=_ROBOT_NUMBER_REF),
        Fact("The node names the EnableRobot service '/dobot_bringup_ros2/srv/EnableRobot'.",
             source="upstream_code", ref=_ENABLE_ENDPOINT_REF),
        Fact("The node names the Stop service '/dobot_bringup_ros2/srv/Stop'.",
             source="upstream_code", ref=_STOP_ENDPOINT_REF),
        Fact("The node names the MovJ service '/dobot_bringup_ros2/srv/MovJ'.",
             source="upstream_code", ref=_MOVJ_ENDPOINT_REF),
        Fact("The node names the MovL service '/dobot_bringup_ros2/srv/MovL'.",
             source="upstream_code", ref=_MOVL_ENDPOINT_REF),
        Fact("The node registers the MovJ service with the generated type "
             "dobot_msgs_v4::srv::MovJ.", source="upstream_code", ref=_MOVJ_TYPE_REF),
        Fact("The EnableRobot request formatter returns the dashboard text EnableRobot().",
             source="upstream_code", ref=_ENABLE_WIRE_REF),
        Fact("The Stop request formatter returns the dashboard text Stop().",
             source="upstream_code", ref=_STOP_WIRE_REF),
        Fact("The MovJ parser formats a..f with three decimals, sends joint={...} when mode is true "
             "and pose={...} when it is false, and appends any non-empty param_value strings.",
             source="upstream_code", ref=_MOVJ_WIRE_REF),
        Fact("The MovL parser uses the same mode switch and formatting as MovJ.",
             source="upstream_code", ref=_MOVL_WIRE_REF),
        Fact("MovJ is a queue command: the controller answers ErrorID,{ResultID},MovJ(...); and "
             "ResultID is the algorithm queue id.", source="vendor_doc", ref=_MOVJ_DOC_REF),
        Fact("MovL is a queue command: the controller answers ErrorID,{ResultID},MovL(...); and "
             "ResultID is the algorithm queue id.", source="vendor_doc", ref=_MOVL_DOC_REF),
        Fact("Stop() is documented to stop motion (or a script); it can stop jogging, script "
             "execution, joint motion and a series of motions.", source="vendor_doc",
             ref=_STOP_DOC_REF),
        Fact("EnableRobot() enables the robot.", source="vendor_doc", ref=_ENABLE_DOC_REF),
        Fact("A dashboard reply has the form ErrorID,{...},Command(...); the error id is the number "
             "before the first brace.", source="vendor_doc", ref=_REPLY_DOC_REF),
        Fact("The reply parser stores the integer before the first '{' in res and, for a _f "
             "command, the first brace-delimited payload in robot_return.",
             source="upstream_code", ref=_REPLY_REF),
        Fact("The dashboard command loop reads until it sees ';', passes timeout=0 to tcpRecv and "
             "calls sleep(0.01) on a false return; it has no overall deadline of its own.",
             source="upstream_code", ref=_SEND_REF),
        Fact("TcpClient::tcpRecv returns false when select returns zero (no ready descriptor); "
             "when select is positive it proceeds to read.", source="upstream_code", ref=_TCP_WAIT_REF),
        Fact("doTcpCmd catches TcpClientException and logs the error without assigning err_id in "
             "the catch block.", source="upstream_code", ref="dobot_bringup_v4/src/command.cpp:157-160"),
        Fact("callRosService calls doTcpCmd and then returns true.", source="upstream_code",
             ref="dobot_bringup_v4/src/command.cpp:221-228"),
        Fact("The Stop callback passes response->res to callRosService.", source="upstream_code",
             ref="dobot_bringup_v4/src/cr_robot_ros2.cpp:699-702"),
        Fact("The node opens a dashboard TcpClient to port 29999 and a feedback TcpClient to port "
             "30004.", source="upstream_code", ref=_TCP_CONNECT_REF),
        Fact("The README states the robot control port is 29999 and the feedback port is 30004.",
             source="vendor_doc", ref=_PORTS_REF),
        Fact("The node publishes sensor_msgs/msg/JointState on the relative topic 'joint_states'.",
             source="upstream_code", ref=_JOINTS_REF),
        Fact("The JointState message carries six positions copied from getJointState.",
             source="upstream_code", ref=_JOINTS_ASSIGN_REF),
        Fact("When the feedback connection is down the node copies the last valid joint "
             "positions, or zeros before any valid data.",
             source="upstream_code", ref=_JOINTS_STALE_REF),
        Fact("The node publishes dobot_msgs_v4/msg/ToolVectorActual on the relative topic "
             "dobot_msgs_v4/msg/ToolVectorActual.", source="upstream_code", ref=_TOOL_REF),
        Fact("The ToolVectorActual publisher fills x, y, z, rx, ry, rz from getToolVectorActual and "
             "publishes only while connected.", source="upstream_code", ref=_TOOL_ASSIGN_REF),
        Fact("The node creates a dobot_msgs_v4/msg/RobotStatus publisher on the relative topic "
             "dobot_msgs_v4/msg/RobotStatus.",
             source="upstream_code", ref=_STATUS_REF),
        Fact("The RobotStatus publisher fills is_enable and is_connected from the node's connection "
             "state.", source="upstream_code", ref=_STATUS_ASSIGN_REF),
        Fact("isEnable() returns robot_mode == 5; isConnected() returns the dashboard TCP connect "
             "state && the feedback TCP connect state.", source="upstream_code",
             ref="dobot_bringup_v4/src/command.cpp:266-289"),
        Fact("The publisher rate is the JointStatePublishRate ROS parameter, default 10 Hz.",
             source="upstream_code", ref=_PUBLISH_RATE_REF),
        Fact("The MovJ service request has bool mode, float64 a..f and string[] param_value; the "
             "response has string robot_return and int32 res.", source="upstream_code",
             ref=_MOVJ_SRV_REF),
        Fact("The MovL service request has the same fields as MovJ and the same response.",
             source="upstream_code", ref=_MOVL_SRV_REF),
        Fact("The Stop service has an empty request and returns int32 res.", source="upstream_code",
             ref=_STOP_SRV_REF),
        Fact("The EnableRobot service has an empty request and returns int32 res.",
             source="upstream_code", ref=_ENABLE_SRV_REF),
        Fact("ToolVectorActual declares float64 x, y, z, rx, ry, rz.", source="upstream_code",
             ref=_TOOL_MSG_REF),
        Fact("RobotStatus declares bool is_enable and bool is_connected.", source="upstream_code",
             ref=_STATUS_MSG_REF),
        Fact("The README lists the supported models as CR3, CR5, CR7, CR10, CR12, CR16, CR20, "
             "CR30H, CR10AF, E6/ME6, Nova2 and Nova5.", source="vendor_doc", ref=_MODELS_REF),
        Fact("The README instructs the user to ensure the robot is in a safe position, that ports "
             "29999 and 30004 are free, and that the robot is in remote TCP/IP control mode.",
             source="vendor_doc", ref=_SAFETY_NOTE_REF),
    ]
    safe_state = (
        "Unconfirmed: no native e-stop is bound because the upstream Stop response can retain "
        "res=0 after a failed TCP exchange. The latch blocks new MHS commands but neither sends "
        "a dashboard Stop nor establishes a stopped arm; motion already running may continue. "
        "The ordinary Stop service and an explicit latch reset confirm no hardware state. "
        "A reviewed stop/confirmation path and independent physical stop are required outside "
        "this blocked package."
    )

    parameters = {
        "joint_positions": Field(
            "array",
            unit="rad",
            description="Six joint positions from the node's JointState feedback; the publisher "
                        "copies them from the port-30004 feedback without a per-joint name check",
            items=Field("number", unit="rad", description="One joint position in radians"),
            length=_JOINT_COUNT,
        ),
        "tcp_pose": Field(
            "object",
            description="Tool pose from ToolVectorActual: position in mm and orientation in degrees; "
                        "it stops updating while the feedback connection is down",
            properties={
                "x": Field("number", unit="mm", description="Tool X position in mm"),
                "y": Field("number", unit="mm", description="Tool Y position in mm"),
                "z": Field("number", unit="mm", description="Tool Z position in mm"),
                "rx": Field("number", unit="deg", description="Tool rotation about X in degrees"),
                "ry": Field("number", unit="deg", description="Tool rotation about Y in degrees"),
                "rz": Field("number", unit="deg", description="Tool rotation about Z in degrees"),
            },
        ),
        "enabled": Field("boolean",
                         description="RobotStatus is_enable; true only when the feedback "
                                     "robot_mode is 5"),
        "connected": Field("boolean",
                           description="RobotStatus is_connected; true only while both the "
                                       "dashboard and feedback TCP connections are up"),
    }
    reads = {
        "joint_positions": {
            "topic": "/joint_states",
            "type": "sensor_msgs/msg/JointState",
            "source_name": "joint_states",
            "source_ref": _JOINTS_REF,
            "path": "position",
            "timeout_ms": 2000,
        },
        "tcp_pose": {
            "topic": "/dobot_msgs_v4/msg/ToolVectorActual",
            "type": "dobot_msgs_v4/msg/ToolVectorActual",
            "source_name": "dobot_msgs_v4/msg/ToolVectorActual",
            "source_ref": _TOOL_REF,
            "path": "$",
            "timeout_ms": 2000,
        },
        "enabled": {
            "topic": "/dobot_msgs_v4/msg/RobotStatus",
            "type": "dobot_msgs_v4/msg/RobotStatus",
            "source_name": "dobot_msgs_v4/msg/RobotStatus",
            "source_ref": _STATUS_REF,
            "path": "is_enable",
            "timeout_ms": 2000,
        },
        "connected": {
            "topic": "/dobot_msgs_v4/msg/RobotStatus",
            "type": "dobot_msgs_v4/msg/RobotStatus",
            "source_name": "dobot_msgs_v4/msg/RobotStatus",
            "source_ref": _STATUS_REF,
            "path": "is_connected",
            "timeout_ms": 2000,
        },
    }
    commands = {
        "x-cap.dobot-arm.move_joint.v1": _MOVE_JOINT,
        "x-cap.dobot-arm.move_pose.v1": _MOVE_POSE,
        "x-cap.dobot-arm.stop.v1": dict(_STOP, result={"service_returned": {"value": True}}),
        "x-cap.dobot-arm.enable.v1": dict(_ENABLE, result={"service_returned": {"value": True}}),
    }
    actions = {
        "x-cap.dobot-arm.move_joint.v1": Action(
            name="move_joint",
            description=(
                "Enqueue a MovJ point-to-point joint move; the receipt confirms that the pinned "
                "node returned res == 0 and reports its raw queue payload, not "
                "that the joints reached the target"
            ),
            input={
                "joint_positions": Field(
                    "array",
                    unit="rad",
                    description="Target angles of joints 1 to 6 in radians, in the publisher's "
                                "joint1..joint6 order; the node sends them as degrees",
                    items=Field("number", unit="rad",
                                description="One target joint angle in radians"),
                    length=_JOINT_COUNT,
                    limit=Limit.operator_required(_JOINT_REASON),
                ),
            },
            output={"service_returned": _SERVICE_RETURNED, "result_id": _RESULT_ID},
        ),
        "x-cap.dobot-arm.move_pose.v1": Action(
            name="move_pose",
            description=(
                "Request a MovL Cartesian move; the receipt reports callback res == 0 and the "
                "raw queue payload, not arrival or verified acceptance. User/tool are omitted."
            ),
            input={
                "position": Field(
                    "object",
                    description="Target position, current user frame",
                    properties={
                        "x": Field("number", unit="mm",
                                   description="X, mm",
                                   limit=Limit.operator_required(_POSITION_REASON)),
                        "y": Field("number", unit="mm",
                                   description="Y, mm",
                                   limit=Limit.operator_required(_POSITION_REASON)),
                        "z": Field("number", unit="mm",
                                   description="Z, mm",
                                   limit=Limit.operator_required(_POSITION_REASON)),
                    },
                ),
                "orientation": Field(
                    "object",
                    description="Target orientation, current tool frame",
                    properties={
                        "roll": Field("number", unit="rad",
                                      description="About X, rad",
                                      limit=Limit.operator_required(_ORIENTATION_REASON)),
                        "pitch": Field("number", unit="rad",
                                       description="About Y, rad",
                                       limit=Limit.operator_required(_ORIENTATION_REASON)),
                        "yaw": Field("number", unit="rad",
                                     description="About Z, rad",
                                     limit=Limit.operator_required(_ORIENTATION_REASON)),
                    },
                ),
            },
            output={"service_returned": _SERVICE_RETURNED, "result_id": _RESULT_ID},
        ),
        "x-cap.dobot-arm.stop.v1": Action(
            name="stop",
            verb="invoke",
            description=(
                "Call the fixed, input-free Stop() dashboard service; it is the native stop and "
                "reports only a ROS response res == 0, which may survive a suppressed TCP error; "
                "this is not an e-stop or stopped-state confirmation"
            ),
            output={"service_returned": _SERVICE_RETURNED},
        ),
        "x-cap.dobot-arm.enable.v1": Action(
            name="enable",
            verb="invoke",
            reenable=True,
            description=(
                "Call the input-free EnableRobot dashboard service after a safety reset when the "
                "native state needs it; this is the one re-enable action and reports only the "
                "ROS callback response; controller delivery is unverified"
            ),
            output={"service_returned": _SERVICE_RETURNED},
        ),
    }
    # Stop.srv exposes no field distinguishing delivery from a suppressed TCP failure.
    safety_bindings = {}
