"""OpenMHS rosbridge driver for the patilunmesh CBF drone simulator.

The pinned repository is a ROS 2 UAV simulation framework.  The selected
runtime is the CBF demo node ``drone_cbf_sim``: it advances a precomputed
3-DOF trajectory on a 10 Hz ROS timer, publishes the true pose as
``nav_msgs/msg/Odometry`` and exposes the ``tutorial_interfaces/srv/ResetSim``
service used by the demo client to reset the simulation and select a new CBF
parameter.  This package is a configuration-only :class:`RosDriver`; it
declares no Python native class and neither imports nor runs the clone.

The node has no pause or stop service or action.  ``ResetSim`` resets the
trajectory and recreates the timer, so it is an ordinary reset and not a safe
state.  The package therefore declares no e-stop binding: a stock e-stop
reports the safe state unreached and latches, which is recorded in
``RESULT.json`` as a helper/safety gap rather than fabricated.

Every endpoint, type and fact cites the pinned clone at
a9d0857f1ad4fe57df0250659b107cfc72f44023.  The fake transport is ROS-free; no
ROS graph, simulator, timer or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references (paths are relative to the clone root)
# ---------------------------------------------------------------------------

#: The CBF node imports the custom ResetSim service.
_RESET_IMPORT_REF = "drone_simulation/CBF_Demo/cbf_sim.py:33"

#: create_service(ResetSim, "/drone<my_id>/ResetSim", reset_callback).
_RESET_CREATE_REF = "drone_simulation/CBF_Demo/cbf_sim.py:74-77"

#: reset_callback resets i, replans, zeros tru_pose, destroys/recreates the timer
#: and sets response.done = True.
_RESET_CALLBACK_REF = "drone_simulation/CBF_Demo/cbf_sim.py:194-232"

#: The launch file runs drone_cbf_sim in namespace drone1 with my_id 1.
_LAUNCH_REF = "drone_simulation/launch/single_agent_cbf_launch.py:17-25"

#: The node declares cbf_param and reads it as a double; 15.0 is the launch
#: parameter default, not a numeric bound.
_CBF_PARAM_REF = "drone_simulation/CBF_Demo/cbf_sim.py:41-50"

#: The node creates a nav_msgs/Odometry publisher on the relative true_pose topic.
_POSE_PUBLISHER_REF = "drone_simulation/CBF_Demo/cbf_sim.py:53-54"

#: The node imports nav_msgs/Odometry.
_POSE_TYPE_REF = "drone_simulation/CBF_Demo/cbf_sim.py:18"

#: The node creates a 10 Hz timer and its callback advances the trajectory.
_TIMER_REF = "drone_simulation/CBF_Demo/cbf_sim.py:71-72"
_TIMER_CALLBACK_REF = "drone_simulation/CBF_Demo/cbf_sim.py:125-159"

#: The custom service request/response declarations.
_RESET_SRV_REF = "tutorial_interfaces/srv/ResetSim.srv:1-4"

#: The README describes changing the CBF parameter and resetting the demo.
_CBF_README_REF = "drone_simulation/CBF_Demo/README.md:27-33"

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_POSITION = Field(
    "object",
    description="nav_msgs/Odometry pose.pose.position selected from the true_pose topic",
    properties={
        "x": Field("number", unit="m", description="Pose position x in the odometry frame"),
        "y": Field("number", unit="m", description="Pose position y in the odometry frame"),
        "z": Field("number", unit="m", description="Pose position z in the odometry frame"),
    },
)
_ORIENTATION = Field(
    "object",
    description="nav_msgs/Odometry pose.pose.orientation selected from the true_pose topic",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)
_POSE = Field(
    "object",
    description="nav_msgs/Odometry pose selected from the true_pose topic",
    properties={"position": _POSITION, "orientation": _ORIENTATION},
)
_LINEAR = Field(
    "object",
    description="nav_msgs/Odometry twist.twist.linear selected from the true_pose topic",
    properties={
        "x": Field("number", unit="m/s", description="Linear velocity x"),
        "y": Field("number", unit="m/s", description="Linear velocity y"),
        "z": Field("number", unit="m/s", description="Linear velocity z"),
    },
)
_ANGULAR = Field(
    "object",
    description="nav_msgs/Odometry twist.twist.angular selected from the true_pose topic",
    properties={
        "x": Field("number", unit="rad/s", description="Angular velocity x"),
        "y": Field("number", unit="rad/s", description="Angular velocity y"),
        "z": Field("number", unit="rad/s", description="Angular velocity z"),
    },
)
_TWIST = Field(
    "object",
    description="nav_msgs/Odometry twist selected from the true_pose topic",
    properties={"linear": _LINEAR, "angular": _ANGULAR},
)

_CBF_PARAM = Limit.operator_required(
    "the CBF node declares cbf_param 15.0 as a configurable ROS parameter and states no numeric "
    "range for it; the operator supplies the deployed cautiousness bound"
)

_RESET_OUTPUT = {
    "done": Field("boolean", description="True when the ResetSim callback returned done=true"),
}

# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------

#: ResetSim service.  The node constructs the name as /drone<my_id>/ResetSim;
#: the launch file uses namespace drone1 and my_id 1, so a deployment resolves
#: it to /drone1/ResetSim.  This declaration uses the /ResetSim token shown in
#: the source; the operator must remap /drone1/ResetSim to /ResetSim (or expose
#: the same root name) for this exact endpoint.  The remap is a deployment
#: assumption, not an upstream fact.
_RESET = {
    "service": "/ResetSim",
    "type": "tutorial_interfaces/srv/ResetSim",
    "source_ref": _RESET_CREATE_REF,
    "type_ref": _RESET_IMPORT_REF,
    "args": {
        "reset": {"from": "input.reset"},
        "cbf_param": {"from": "input.cbf_param"},
    },
    "success": {"path": "done", "equals": True},
    "result": {"map": {"done": "done"}},
    "timeout_ms": 5000,
    "description": "Call the ResetSim service; done is the callback's own response flag, not a stopped state",
}

_POSE_READ = {
    "topic": "/drone1/true_pose",
    "type": "nav_msgs/msg/Odometry",
    "source_name": "true_pose",
    "source_ref": _POSE_PUBLISHER_REF,
    "type_ref": _POSE_TYPE_REF,
    "path": "pose.pose",
    "timeout_ms": 2000,
}

_TWIST_READ = {
    "topic": "/drone1/true_pose",
    "type": "nav_msgs/msg/Odometry",
    "source_name": "true_pose",
    "source_ref": _POSE_PUBLISHER_REF,
    "type_ref": _POSE_TYPE_REF,
    "path": "twist.twist",
    "timeout_ms": 2000,
}


class DroneCbfSim(RosDriver):
    device_id = "drone-cbf-sim"
    device_kind = "world.sim"
    mode = "simulated"
    #: The card floor is R1.  The selected surface resets a simulated trajectory
    #: and reads simulated state; it cannot affect physical equipment.
    risk = "R1"
    ros_version = 2
    backends = {"fake": ".fake:FakeDroneCbfSim"}
    tags = ["ros", "ros2", "simulation", "uav", "drone", "cbf", "reset", "odometry"]
    display_name = "patilunmesh CBF UAV simulator"
    vendor = "patilunmesh"
    model = "DroneCBFSim CBF demo node"
    facts = [
        Fact("The CBF node declares start_pose, my_id and cbf_param ROS parameters and reads cbf_param as a "
             "double; the launch value 15.0 is a configurable parameter, not a numeric bound.",
             source="upstream_code", ref=_CBF_PARAM_REF),
        Fact("The CBF node imports ResetSim from tutorial_interfaces.srv.",
             source="upstream_code", ref=_RESET_IMPORT_REF),
        Fact("The CBF node creates a ResetSim service on the constructed relative name "
             "/drone<my_id>/ResetSim.", source="upstream_code", ref=_RESET_CREATE_REF),
        Fact("ResetSim.srv declares request fields reset (bool), cbf_param (float32) and response field done "
             "(bool).", source="upstream_code", ref=_RESET_SRV_REF),
        Fact("reset_callback resets i, updates cbf_param when the request differs, regenerates the trajectory "
             "and LQR sequence, zeros tru_pose, destroys and recreates the timer, and sets response.done=True.",
             source="upstream_code", ref=_RESET_CALLBACK_REF),
        Fact("The launch file runs drone_cbf_sim in namespace drone1 with start_pose [0, 0, 0], my_id 1 and "
             "cbf_param 15.0.", source="upstream_code", ref=_LAUNCH_REF),
        Fact("The CBF node creates a nav_msgs/Odometry publisher on the relative true_pose topic with queue "
             "size 1.", source="upstream_code", ref=_POSE_PUBLISHER_REF),
        Fact("The CBF node imports nav_msgs/Odometry.", source="upstream_code", ref=_POSE_TYPE_REF),
        Fact("The CBF node creates a 10 Hz timer, and its callback reads the precomputed trajectory, publishes "
             "the pose and increments the trajectory index.", source="upstream_code", ref=_TIMER_CALLBACK_REF),
        Fact("The CBF README says the CBF parameter controls cautiousness, the default is 15, and running the "
             "client resets the simulation to the initial state.", source="vendor_doc", ref=_CBF_README_REF),
    ]
    safe_state = (
        "No acknowledged stop is declared: ResetSim resets the CBF trajectory and recreates the 10 Hz timer, "
        "so the simulated drone resumes; the node exposes no pause or stop service or action and no safe state "
        "is claimed."
    )
    #: The deployed fake is an event-driven rosbridge stand-in, not the CBF
    #: simulator.  It models one reset transition and a fixed pose; it has no
    #: trajectory integration, CBF solve, timer or physics.
    fidelity = {
        "engine": "analytic:ROS recording fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned-response fake with a placeholder pose and one reset transition; "
                     "no trajectory generation, LQR integration, CBF solve, timer pacing or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "partial",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free rosbridge contract stand-in, not a recording of captured traffic: it runs "
            "no CBF node, trajectory generator, LQR controller, obstacle detector, 10 Hz timer, RViz or ROS graph",
            "the pose and twist are placeholder values; the fake changes the pose on ResetSim but integrates "
            "no trajectory and makes no arrival or motion claim",
            "the real node steps on a 10 Hz timer; the fake does not advance between observations",
            "the node exposes no pause or stop service or action: ResetSim resets the trajectory and recreates "
            "the timer and is not a safe state; a stock e-stop cannot be confirmed and remains latched",
            "the CBF optimization, obstacle/remote-id paths, multi-drone launch, LQR dynamics and trajectory "
            "generation are NOT COVERED",
            "ResetSim is advertised under /drone<my_id>/ResetSim; the launch uses /drone1/ResetSim while this "
            "binding configures /ResetSim, so a deployment must remap the service (a deployment assumption, "
            "not an upstream fact)",
        ],
    }
    parameters = {"pose": _POSE, "twist": _TWIST}
    reads = {"pose": _POSE_READ, "twist": _TWIST_READ}
    commands = {"x-cap.patilunmesh.reset.v1": _RESET}
    actions = {
        "x-cap.patilunmesh.reset.v1": Action(
            name="reset_sim",
            verb="invoke",
            risk="R1",
            description=(
                "Reset the CBF demo simulation through the ResetSim service: the node returns to its initial "
                "position, replans the trajectory and recreates its 10 Hz timer. The done flag acknowledges "
                "the callback, not a stopped state."
            ),
            input={
                "reset": Field(
                    "boolean",
                    description="ResetSim request field; the pinned callback is invoked for either value",
                ),
                "cbf_param": Field(
                    "number",
                    unit="1",
                    description="CBF cautiousness parameter passed to ResetSim; the clone states no numeric range",
                    limit=_CBF_PARAM,
                ),
            },
            output=_RESET_OUTPUT,
        ),
    }
    #: No e-stop binding: ResetSim is a reset, not a stop, and the node exposes
    #: no acknowledged pause/stop.  The runtime keeps its software latch and
    #: reports the safe state unreached rather than pretending the reset is one.
    safety_bindings = {}
