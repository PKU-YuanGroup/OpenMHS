"""OpenMHS rosbridge driver for the USV_SIM_LSA differential USV simulator.

The pinned repository is a ROS 1 Gazebo/UWSim simulator.  This package is a
configuration-only :class:`RosDriver`; it declares no Python native class and
neither imports nor starts the upstream code.  The selected device is the
differential-boat heading controller and the Gazebo world it commands:

* ``/diffboat/move_usv/goal`` (``nav_msgs/Odometry``) is the controller goal
  input; the controller is ``usv_base_ctrl/scripts/diff_control_heading.py``
  in the ``diffboat`` namespace;
* ``/diffboat/state`` (``nav_msgs/Odometry``) is the simulator odometry;
* ``/diffboat/move_usv/result`` (``std_msgs/Float64``) is the controller's
  distance flag, not a stopped-state signal;
* ``/diffboat/thruster_command`` (``sensor_msgs/JointState``) is the
  controller thruster output observed here, not a command input.

The acknowledged stop path is the Gazebo ``/gazebo/pause_physics`` service
(``std_srvs/Empty``); the scenario scripts in the clone use that service and
call ``/gazebo/unpause_physics`` and ``/gazebo/reset_simulation`` separately.
Pausing physics is a simulator stop, not a physical emergency stop.  The
service implementation is in ``gazebo_ros``, outside the pinned clone; the
clone proves the client endpoints and the separate pause/reset/unpause calls,
not the callback body.  The heading controller is not terminated and keeps
its retained target, so unpausing can resume motion toward that target.

Every endpoint, type and fact cites the pinned clone at
61e8f4a5f78f18c01dac0d4eea7f4c3c416e6cb8.  The fake transport is ROS-free and
all of its numbers are placeholders.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The heading controller subscriptions and publications in the diffboat namespace.
_CONTROL_REF = "usv_base_ctrl/scripts/diff_control_heading.py:87-94"

#: Type imports in the heading controller.
_JOINT_TYPE_REF = "usv_base_ctrl/scripts/diff_control_heading.py:7"
_ODOM_TYPE_REF = "usv_base_ctrl/scripts/diff_control_heading.py:9"
_FLOAT64_TYPE_REF = "usv_base_ctrl/scripts/diff_control_heading.py:12"

#: Separate source sites for the goal, result and thruster declarations.
_GOAL_REF = "usv_base_ctrl/scripts/diff_control_heading.py:94"
_STATE_REF = "usv_base_ctrl/scripts/diff_control_heading.py:93"
_RESULT_REF = "usv_base_ctrl/scripts/diff_control_heading.py:88"
_THRUSTER_REF = "usv_base_ctrl/scripts/diff_control_heading.py:87"

#: The scenario script creates the Gazebo std_srvs/Empty service proxies.
_PAUSE_REF = "usv_navigation/scripts/patrol_pid_scene1.py:42"
_UNPAUSE_REF = "usv_navigation/scripts/patrol_pid_scene1.py:41"
_RESET_REF = "usv_navigation/scripts/patrol_pid_scene1.py:43"
_EMPTY_TYPE_REF = "usv_navigation/scripts/patrol_pid_scene1.py:7"
_PAUSE_RESET_SEQUENCE_REF = "usv_navigation/scripts/patrol_pid_scene1.py:63-71"

#: The goal area is a deployment choice; the clone states no fixed world extent.
_GOAL_REASON = ("the valid goal area is defined by the loaded scenario and Gazebo world, "
                "not by the heading controller; the operator supplies the deployment's planar "
                "x/y bounds in site-limits.json")

_PAUSE = {
    "service": "/gazebo/pause_physics",
    "type": "std_srvs/Empty",
    "source_ref": _PAUSE_REF,
    "type_ref": _EMPTY_TYPE_REF,
    "success": {"path": "$", "equals": {}},
}

_UNPAUSE = {
    "service": "/gazebo/unpause_physics",
    "type": "std_srvs/Empty",
    "source_ref": _UNPAUSE_REF,
    "type_ref": _EMPTY_TYPE_REF,
    "success": {"path": "$", "equals": {}},
}

_RESET = {
    "service": "/gazebo/reset_simulation",
    "type": "std_srvs/Empty",
    "source_ref": _RESET_REF,
    "type_ref": _EMPTY_TYPE_REF,
    "success": {"path": "$", "equals": {}},
}

_GOAL = {
    "topic": "/diffboat/move_usv/goal",
    "type": "nav_msgs/Odometry",
    "source_name": "move_usv/goal",
    "source_ref": _GOAL_REF,
    "type_ref": _ODOM_TYPE_REF,
    "operation": "publish",
    "args": {
        "header.frame_id": {"value": "world"},
        "pose.pose.position.x": {"from": "input.x_m"},
        "pose.pose.position.y": {"from": "input.y_m"},
        "pose.pose.position.z": {"value": 0.0},
    },
    "result": {"map": {"published": "output.published", "confirmed": "output.confirmed"}},
}

_STATE = {
    "topic": "/diffboat/state",
    "type": "nav_msgs/Odometry",
    "source_name": "state",
    "source_ref": _STATE_REF,
    "type_ref": _ODOM_TYPE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {
        "position_x": "output.pose.pose.position.x",
        "position_y": "output.pose.pose.position.y",
        "position_z": "output.pose.pose.position.z",
        "orientation_x": "output.pose.pose.orientation.x",
        "orientation_y": "output.pose.pose.orientation.y",
        "orientation_z": "output.pose.pose.orientation.z",
        "orientation_w": "output.pose.pose.orientation.w",
        "frame_id": "output.header.frame_id",
        "child_frame_id": "output.child_frame_id",
    }},
}

_RESULT = {
    "topic": "/diffboat/move_usv/result",
    "type": "std_msgs/Float64",
    "source_name": "move_usv/result",
    "source_ref": _RESULT_REF,
    "type_ref": _FLOAT64_TYPE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"proximity_flag": "output.data"}},
}

_THRUSTER = {
    "topic": "/diffboat/thruster_command",
    "type": "sensor_msgs/JointState",
    "source_name": "thruster_command",
    "source_ref": _THRUSTER_REF,
    "type_ref": _JOINT_TYPE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"names": "output.name", "positions": "output.position"}},
}

_PUBLISHED = {
    "published": Field("boolean", description="True once rosbridge accepted the publication"),
    "confirmed": Field("boolean", description="Always false: a ROS topic publication has no execution acknowledgement"),
}

_ACKNOWLEDGED = {
    "acknowledged": Field("boolean", description="True when the std_srvs/Empty service returned success"),
}

_ODOMETRY_OUTPUT = {
    "position_x": Field("number", unit="m", description="Model position x in the world frame"),
    "position_y": Field("number", unit="m", description="Model position y in the world frame"),
    "position_z": Field("number", unit="m", description="Model position z in the world frame"),
    "orientation_x": Field("number", unit="1", description="Pose quaternion x"),
    "orientation_y": Field("number", unit="1", description="Pose quaternion y"),
    "orientation_z": Field("number", unit="1", description="Pose quaternion z"),
    "orientation_w": Field("number", unit="1", description="Pose quaternion w"),
    "frame_id": Field("string", description="Odometry header frame as published"),
    "child_frame_id": Field("string", description="Odometry child frame as published"),
}

_FLOAT64_OUTPUT = {
    "proximity_flag": Field(
        "number",
        unit="1",
        description=("Value of move_usv/result data: 1 when the controller target_distance is below "
                     "desired_distance and 0 otherwise; it is not a stopped-state signal"),
    ),
}

_THRUSTER_OUTPUT = {
    "names": Field(
        "array",
        items=Field("string", description="JointState name entry"),
        description="JointState name entries published by the heading controller",
    ),
    "positions": Field(
        "array",
        items=Field("number", unit="1", description="Native JointState position entry"),
        description=("JointState position entries published by the heading controller; the first two are "
                     "fwd_left and fwd_right in the pinned controller"),
    ),
}


class UsvSimLsa(RosDriver):
    device_id = "usv-sim"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeUsvSimLsa"}
    tags = ["ros", "ros1", "simulation", "gazebo", "uwsim", "usv", "marine", "heading-control"]
    display_name = "USV_SIM_LSA differential USV simulator"
    vendor = "Disaster Robotics Proalertas"
    facts = [
        Fact("The spawn_diffboat launch defaults the model namespace to diffboat and runs "
             "diff_control_heading.py inside that namespace.",
             source="upstream_code", ref="usv_sim/launch/models/spawn_diffboat.launch:6-25"),
        Fact("diff_control_heading.py publishes thruster_command (sensor_msgs/JointState) and "
             "move_usv/result (std_msgs/Float64), and subscribes to state and move_usv/goal as "
             "nav_msgs/Odometry.",
             source="upstream_code", ref=_CONTROL_REF),
        Fact("thruster_ctrl_msg names the two thruster entries fwd_left and fwd_right and sets their "
             "JointState positions to rudder_ctrl() + 100 and -rudder_ctrl() + 100, clamping only values "
             "below zero.",
             source="upstream_code", ref="usv_base_ctrl/scripts/diff_control_heading.py:43-58"),
        Fact("verify_result updates only result.data from the target_distance and desired_distance "
             "comparison; the thruster message is built separately in thruster_ctrl_msg.",
             source="upstream_code", ref="usv_base_ctrl/scripts/diff_control_heading.py:38-67"),
        Fact("The heading controller loop runs at rate_value 10 Hz and publishes both topics every "
             "iteration until ROS shutdown.",
             source="upstream_code", ref="usv_base_ctrl/scripts/diff_control_heading.py:83-100"),
        Fact("The diffboat controller configuration selects the thruster body control type, the state "
             "body-state topic and the body_command command topic.",
             source="upstream_code", ref="usv_sim/config/diffboat.yaml:2-7"),
        Fact("The patrol script creates std_srvs/Empty service proxies for /gazebo/unpause_physics, "
             "/gazebo/pause_physics and /gazebo/reset_simulation.",
             source="upstream_code",
             ref="usv_navigation/scripts/patrol_pid_scene1.py:38-43"),
        Fact("The patrol script calls pause, then resetSimulation, then unpause as separate service "
             "calls.",
             source="upstream_code", ref=_PAUSE_RESET_SEQUENCE_REF),
        Fact("The diffboat scenario launch runs the patrol node in namespace diffboat.",
             source="upstream_code",
             ref="usv_sim/launch/scenarios_launchs/diffboat_scenario1.launch:30"),
        Fact("The patrol node publishes move_usv/goal as nav_msgs/Odometry and subscribes to "
             "move_usv/result as std_msgs/Float64.",
             source="upstream_code",
             ref="usv_navigation/scripts/patrol_pid_scene1.py:34-37"),
        Fact("The shipped diffboat_scenario1 scene places the diffboat at x=240, y=95, z=1.",
             source="upstream_code", ref="usv_sim/scenes/diffboat_scenario1.xml:63-72"),
        Fact("The patrol script builds its goal Odometry with header.frame_id 'world' and position z=0.",
             source="upstream_code", ref="usv_navigation/scripts/patrol_pid_scene1.py:21-25"),
        Fact("The control documentation describes the forward-propulsion distance thresholds in meters "
             "and applies the same condition set to the differential boat.",
             source="vendor_doc", ref="docs/control.md:13-23"),
    ]
    safe_state = (
        "Gazebo physics is paused through the acknowledged /gazebo/pause_physics service, so the "
        "simulated world stops stepping until /gazebo/unpause_physics is called; the service does not "
        "terminate the heading controller or clear its retained goal."
    )
    fidelity = {
        "engine": "analytic:ROS recording fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": ("Event-driven recording stand-in with no physics step or pacing; placeholder state, "
                      "thruster and result samples do not establish trajectory or state-hash replay"),
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "partial",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it answers the declared goal, state, result, "
            "thruster, pause, unpause and reset endpoints and runs no Gazebo/UWSim physics, waves, wind, "
            "water current, buoyancy, thruster or boat dynamics",
            "the state, result and thruster samples are placeholders; a live run must receive them from the "
            "operator's simulator and heading controller",
            "the /gazebo/pause_physics, /gazebo/unpause_physics and /gazebo/reset_simulation service "
            "implementations are in gazebo_ros, outside the pinned clone; the clone proves the client "
            "endpoints and their separate use, not the callback body",
            "the pause service freezes world stepping but does not terminate the heading controller or clear "
            "its retained target; unpausing can resume motion toward that target",
            "the real /diffboat/state publisher belongs to the simulator deployment and may stop producing "
            "fresh samples while physics is paused; the fake still answers placeholder samples",
            "the laser scan, camera, TF, water-current and wind-current surfaces are out of scope",
            "mhs.safety.reset calls /gazebo/reset_simulation (gazebo_ros, outside the clone), which the "
            "shipped patrol script uses between runs to restart the scenario, so clearing the latch also "
            "resets the simulated world; the script calls unpause separately, and the heading controller "
            "keeps its retained goal",
        ],
    }

    # The resource snapshot is intentionally empty: the observations are explicit
    # topic reads and a paused simulator may stop publishing them.  Reading a state
    # topic as an automatic resource snapshot would wait during a stop.
    commands = {
        "x-cap.disaster-robotics-proalertas.move_usv_goal.v1": _GOAL,
        "x-cap.disaster-robotics-proalertas.simulator_state.v1": _STATE,
        "x-cap.disaster-robotics-proalertas.goal_result.v1": _RESULT,
        "x-cap.disaster-robotics-proalertas.thruster_command.v1": _THRUSTER,
        "x-cap.disaster-robotics-proalertas.pause_physics.v1": dict(
            _PAUSE, result={"acknowledged": {"value": True}}),
        "x-cap.disaster-robotics-proalertas.unpause_physics.v1": dict(
            _UNPAUSE, result={"acknowledged": {"value": True}}),
    }
    actions = {
        "x-cap.disaster-robotics-proalertas.move_usv_goal.v1": Action(
            name="move_usv_goal",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one nav_msgs/Odometry goal to the heading controller's move_usv/goal "
                "subscription; the controller publishes the two thruster commands without an "
                "acknowledgement. The receipt proves only that rosbridge accepted the publication, "
                "not that the boat moved or reached the goal."
            ),
            input={
                "x_m": Field(
                    "number",
                    unit="m",
                    description="Goal x in the controller's world frame",
                    limit=Limit.operator_required(_GOAL_REASON),
                ),
                "y_m": Field(
                    "number",
                    unit="m",
                    description="Goal y in the controller's world frame",
                    limit=Limit.operator_required(_GOAL_REASON),
                ),
            },
            output=_PUBLISHED,
            examples=[{"x_m": 240.0, "y_m": 95.0}],
        ),
        "x-cap.disaster-robotics-proalertas.simulator_state.v1": Action(
            name="read_simulator_state",
            verb="read",
            description="Read one nav_msgs/Odometry sample published on /diffboat/state",
            output=_ODOMETRY_OUTPUT,
        ),
        "x-cap.disaster-robotics-proalertas.goal_result.v1": Action(
            name="read_goal_result",
            verb="read",
            description=(
                "Read one move_usv/result Float64 sample; the value is the controller's distance "
                "comparison and does not show that thrust stopped"
            ),
            output=_FLOAT64_OUTPUT,
        ),
        "x-cap.disaster-robotics-proalertas.thruster_command.v1": Action(
            name="read_thruster_command",
            verb="read",
            description=(
                "Read one thruster_command JointState sample published by the heading controller; "
                "the entries are the controller output, not a command from this driver"
            ),
            output=_THRUSTER_OUTPUT,
        ),
        "x-cap.disaster-robotics-proalertas.pause_physics.v1": Action(
            name="pause_physics",
            verb="invoke",
            safe_state=True,
            description=(
                "Call the acknowledged /gazebo/pause_physics std_srvs/Empty service; this is the "
                "declared simulated safe state and the native e-stop binding"
            ),
            output=_ACKNOWLEDGED,
        ),
        "x-cap.disaster-robotics-proalertas.unpause_physics.v1": Action(
            name="unpause_physics",
            verb="invoke",
            risk="R2",
            description=(
                "Call the acknowledged /gazebo/unpause_physics std_srvs/Empty service; an ordinary "
                "command, refused while the e-stop latch is engaged"
            ),
            output=_ACKNOWLEDGED,
        ),
    }
    # The pause service is an acknowledged simulated stop, not a physical e-stop.
    # The reset service resets the Gazebo world; the script calls unpause separately.
    safety_bindings = {"estop": _PAUSE, "reset": _RESET}
