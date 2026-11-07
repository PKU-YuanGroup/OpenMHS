"""OpenMHS rosbridge driver for the pinned NASA Astrobee ROS 1 interfaces.

Astrobee is a free-flying robot.  This package is a configuration-only
``RosDriver`` over rosbridge; it declares no Python native class and does not
start ROS, Gazebo or the operator's simulation.  The primary interface is the
choreographer's ``mob/motion`` MotionAction: this package exposes its MOVE
command with a raw ``geometry_msgs/PoseStamped[]`` state sequence.  The
independently acknowledged safe stop is the GNC controller's ``gnc/control``
ControlAction STOP, which commands ``MODE_STOP`` and reports SUCCESS only
after its EKF velocity and omega magnitudes fall below the configured
stopping thresholds.

Every endpoint, type and fact cites the pinned clone at
bf43a42d5f89bf0679e51ab25e7a9b7800313e9c.  The fake transport is ROS-free.
No ROS graph, simulator or hardware is contacted, and the package makes no
physical emergency-stop claim.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: ACTION_MOBILITY_MOTION and ACTION_GNC_CTL_CONTROL are relative ROS names.
_MOTION_REF = "shared/ff_common/include/ff_common/ff_names.h:230"
_CONTROL_REF = "shared/ff_common/include/ff_common/ff_names.h:133"

#: The generated action headers prove both wrapper types.
_MOTION_TYPE_REF = "mobility/choreographer/src/choreographer_nodelet.cc:54"
_CONTROL_TYPE_REF = "gnc/ctl/include/ctl/ctl_ros.h:36"

#: geometry_msgs/PoseStamped[] for the Motion MOVE command.
_POSITION_REASON = "Supply installed world-axis limits."
_POSITION = Field(
    "object",
    description="World-frame position",
    properties={
        "x": Field("number", unit="m", description="X world position",
                   limit=Limit.operator_required(_POSITION_REASON)),
        "y": Field("number", unit="m", description="Y world position",
                   limit=Limit.operator_required(_POSITION_REASON)),
        "z": Field("number", unit="m", description="Z world position",
                   limit=Limit.operator_required(_POSITION_REASON)),
    },
)
_ORIENTATION = Field(
    "object",
    description="World-frame orientation quaternion",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)
_STATE = Field(
    "object",
    description="One geometry_msgs/PoseStamped pose",
    properties={"pose": Field(
        "object",
        description="Pose inside the clone's world frame",
        properties={"position": _POSITION, "orientation": _ORIENTATION},
    )},
)

#: The choreographer publishes its last segment as a latched nav_msgs/Path; its
#: header stamp is a real observation that changes with each move publication.
_COMMANDED_SEGMENT = {
    "topic": "/mob/choreographer/segment",
    "type": "nav_msgs/Path",
    "source_name": "mob/choreographer/segment",
    "source_ref": "shared/ff_common/include/ff_common/ff_names.h:261",
    "type_ref": "mobility/choreographer/src/choreographer_nodelet.cc:1167",
    "path": "header.stamp.nsecs",
}

_MOVE = {
    "action": "/mob/motion",
    "type": "ff_msgs/MotionAction",
    "profile": "ros1-actionlib",
    "source_name": "mob/motion",
    "source_ref": _MOTION_REF,
    "type_ref": _MOTION_TYPE_REF,
    # MOVE = 3 in Motion.action:25.  An empty flight_mode keeps the current
    # flight mode (choreographer_nodelet.cc:1308-1315); an empty
    # reference_frame avoids a TF lookup (choreographer_nodelet.cc:1358).
    "request": {"command": 3, "flight_mode": ""},
    "args": {"states": {"from": "input.states"}},
    "result": {"map": {"response": "response", "fsm_result": "fsm_result"}},
    "success": {"path": "response", "equals": 1},
}

#: ControlAction STOP = 0 (Control.action:21).  Its SUCCESS response is 1
#: (Control.action:30), and it is only sent after sensed quiescence
#: (ctl_ros.cc:245-259).
_STOP = {
    "action": "/gnc/control",
    "type": "ff_msgs/ControlAction",
    "profile": "ros1-actionlib",
    "source_name": "gnc/control",
    "source_ref": _CONTROL_REF,
    "type_ref": _CONTROL_TYPE_REF,
    "request": {"command": 0},
    "result": {"stopped": {"value": True}},
    "success": {"path": "response", "equals": 1},
}


class Astrobee(RosDriver):
    device_id = "astrobee"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeAstrobee"}
    tags = ["ros", "ros1", "simulation", "astrobee", "free-flyer", "motion", "action", "stop"]
    display_name = "Astrobee free-flyer (ROS 1)"
    vendor = "NASA"
    facts = [
        Fact("The pinned name header defines ACTION_MOBILITY_MOTION as the relative ROS name "
             "mob/motion.", source="upstream_code", ref=_MOTION_REF),
        Fact("The pinned name header defines ACTION_GNC_CTL_CONTROL as the relative ROS name "
             "gnc/control.", source="upstream_code", ref=_CONTROL_REF),
        Fact("The choreographer source includes the generated ff_msgs/MotionAction header.",
             source="upstream_code", ref=_MOTION_TYPE_REF),
        Fact("ChoreographerNodelet binds the owned MotionAction server to ACTION_MOBILITY_MOTION.",
             source="upstream_code",
             ref="mobility/choreographer/src/choreographer_nodelet.cc:578-584"),
        Fact("The Motion action defines STOP, IDLE, EXEC, MOVE and PREP commands; MOVE is "
             "'Move through a given set of poses'.",
             source="upstream_code",
             ref="communications/ff_msgs/action/Motion.action:22-26"),
        Fact("The Motion action carries a geometry_msgs/PoseStamped array in states and a "
             "reference_frame string.", source="upstream_code",
             ref="communications/ff_msgs/action/Motion.action:47-50"),
        Fact("The Motion result defines ALREADY_THERE and SUCCESS response codes.",
             source="upstream_code",
             ref="communications/ff_msgs/action/Motion.action:56-57"),
        Fact("GoalCallback rejects a new Motion goal unless the choreographer FSM is IDLE or "
             "STOPPED, aborting with NOT_IN_WAITING_MODE.", source="upstream_code",
             ref="mobility/choreographer/src/choreographer_nodelet.cc:1295-1305"),
        Fact("GoalCallback rejects a MOVE goal with an empty states vector with "
             "UNEXPECTED_EMPTY_STATES.", source="upstream_code",
             ref="mobility/choreographer/src/choreographer_nodelet.cc:1347-1353"),
        Fact("The STOP transition from STOPPED or IDLE calls Control(STOP), enters STOPPING, "
             "and reports SUCCESS only on CONTROL_SUCCESS.", source="upstream_code",
             ref="mobility/choreographer/src/choreographer_nodelet.cc:353-367"),
        Fact("The CONTROLLING/GOAL_CANCEL transition returns CANCELLED rather than sending a "
             "Control STOP goal.", source="upstream_code",
             ref="mobility/choreographer/src/choreographer_nodelet.cc:311-317"),
        Fact("Result() handles CANCELLED and PREEMPTED by calling client_c_.CancelGoal() in "
             "CONTROLLING; it does not command a stop there.", source="upstream_code",
             ref="mobility/choreographer/src/choreographer_nodelet.cc:807-826"),
        Fact("SetStateCallback for mob/set_state calls fsm_.SetState(req.state) and then sets "
             "res.success true without calling Control().", source="upstream_code",
             ref="mobility/choreographer/src/choreographer_nodelet.cc:605-610"),
        Fact("The choreographer transforms MOVE states from a non-empty reference_frame into "
             "the world frame before planning.", source="upstream_code",
             ref="mobility/choreographer/src/choreographer_nodelet.cc:1354-1375"),
        Fact("The pinned name header defines the world frame name as world.",
             source="upstream_code",
             ref="shared/ff_common/include/ff_common/ff_names.h:37"),
        Fact("The pinned name header defines TOPIC_MOBILITY_SEGMENT as mob/choreographer/segment.",
             source="upstream_code",
             ref="shared/ff_common/include/ff_common/ff_names.h:261"),
        Fact("The choreographer advertises a latched nav_msgs/Path on TOPIC_MOBILITY_SEGMENT.",
             source="upstream_code",
             ref="mobility/choreographer/src/choreographer_nodelet.cc:520-522"),
        Fact("The choreographer publishes the segment Path with the world frame and its current "
             "timestamp.", source="upstream_code",
             ref="mobility/choreographer/src/choreographer_nodelet.cc:1167-1169"),
        Fact("The Control action defines STOP, IDLE and NOMINAL commands and the SUCCESS "
             "response code.", source="upstream_code",
             ref="communications/ff_msgs/action/Control.action:20-30"),
        Fact("The control source includes the generated ff_msgs/ControlAction header.",
             source="upstream_code", ref=_CONTROL_TYPE_REF),
        Fact("On a Control STOP goal, Ctl::GoalCallback calls Command(MODE_STOP) and then "
             "updates the FSM with GOAL_STOP.", source="upstream_code",
             ref="gnc/ctl/src/ctl_ros.cc:397-403"),
        Fact("The WAITING/GOAL_STOP transition calls Command(MODE_STOP) and returns STOPPING.",
             source="upstream_code", ref="gnc/ctl/src/ctl_ros.cc:84-90"),
        Fact("Ctl checks the EKF velocity and omega magnitudes against stopping thresholds "
             "and only then updates GOAL_COMPLETE.", source="upstream_code",
             ref="gnc/ctl/src/ctl_ros.cc:245-259"),
        Fact("The STOPPING/GOAL_COMPLETE transition returns SUCCESS.",
             source="upstream_code", ref="gnc/ctl/src/ctl_ros.cc:92-96"),
        Fact("Ctl::Result sends a SUCCESS native action result when response is SUCCESS.",
             source="upstream_code", ref="gnc/ctl/src/ctl_ros.cc:169-171"),
    ]
    safe_state = (
        "The fixed gnc/control STOP action commands the GNC controller's MODE_STOP and reports "
        "SUCCESS only after its EKF velocity and omega magnitudes fall below the configured "
        "stopping thresholds; this is an acknowledged native software stop, not a physical "
        "emergency stop."
    )
    #: The fake is a ROS-free analytic stand-in for actionlib traffic, not a recording of
    #: captured traffic and not the upstream Gazebo simulator.  F0 only.
    fidelity = {
        "engine": "analytic:ROS action contract stand-in (no free-flyer dynamics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies; no physics step, pacing or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake answers the declared actionlib goal/result/status wrapper topics and runs "
            "no Gazebo, free-flyer dynamics, propulsion, localization, mapper/planner, TF or ROS graph",
            "the MOVE result is immediate and canned; it does not model planning, validation, "
            "replanning, trajectory timing or the ALREADY_THERE response",
            "the STOP result does not model the controller's configured stopping thresholds, "
            "latency or the EKF updates that establish sensed quiescence",
            "the package does not launch or configure the upstream simulator, rosbridge, TF, "
            "flight modes or keep-in/keep-out zones; those remain deployment requirements",
            "the MOVE position leaves require an operator workspace overlay; the supplied example "
            "contains fake test values only, not flight-mode hard limits or installed keep-in zones",
            "native namespace and flight-mode selection, EKF/use_truth settings, child-controller "
            "ordering and overlap with retained Motion work remain unverified deployment blockers",
            "the package exposes only Motion MOVE and the Control STOP safety action; IDLE, EXEC, "
            "PREP, mob/set_state, validate, reset and the other mobility services are out of scope",
            "the fake's replies and state values are test data, not measurements or timings",
        ],
    }
    parameters = {
        "commanded_segment_stamp_nsecs": Field(
            "number",
            unit="ns",
            description="Nanoseconds of the last latched choreographer segment publication",
        ),
    }
    reads = {"commanded_segment_stamp_nsecs": _COMMANDED_SEGMENT}
    commands = {
        "x-cap.nasa.astrobee.move.v1": _MOVE,
        # safe_state=True makes this fixed action the capability the server may invoke during
        # the latch; the same binding is the native estop below.
        "x-cap.nasa.astrobee.stop.v1": dict(_STOP, safe_state=True),
    }
    actions = {
        "x-cap.nasa.astrobee.move.v1": Action(
            name="move",
            verb="invoke",
            description="Move through world-frame poses; return the Motion action's application result",
            input={"states": Field(
                "array",
                description="World-frame poses; no frame transformation",
                items=_STATE,
                min_items=1,
            )},
            output={
                "response": Field("integer", unit="1",
                                  description="Motion result response code; SUCCESS is 1 and "
                                              "ALREADY_THERE is 2"),
                "fsm_result": Field("string", description="Human-readable choreographer result"),
            },
            cancellable=True,
        ),
        "x-cap.nasa.astrobee.stop.v1": Action(
            name="stop",
            description="Command the GNC controller's STOP and confirm only after the native "
                        "Control action reports SUCCESS",
            safe_state=True,
            cancellable=False,
            output={"stopped": Field(
                "boolean",
                description="True only after the fixed Control STOP action returned SUCCESS",
            )},
        ),
    }
    # The independent native stop is an action, not the Motion goal's own cancel or preempt
    # path.  It is a separate action server on gnc/control and is invoked before ordinary
    # cancellation during an e-stop.
    safety_bindings = {"estop": _STOP}
