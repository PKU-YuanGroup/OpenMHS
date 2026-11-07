"""Source-backed Franka Hand ROS 1 gripper control through rosbridge.

Four selected action servers expose grasp, move, homing and independent stop;
the additional GripperCommandAction alias is not bound. StopAction is a fixed
safe-state action and the native e-stop path. Its correlated terminal success
and success=true predicate do not settle older pending work: the bridge keeps
uncertain goals fenced and requires a fresh stop after their terminal result.

The pin is ddd2fffd9de44b02ad15b4bbb2bfa2cec4d60d98. The analytic fake proves
only an F0 software contract. No ROS graph or hardware was contacted. Hardware
requires the unchanged human-review and operator-envelope rules. Stopping grasp
force may release a load; the deployment must decide whether that is safe.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The node's action servers are constructed on the private node handle
#: ``~``; the launch file names the node ``franka_gripper``.
_NODE_REF = "franka_gripper/launch/franka_gripper.launch:6-13"

#: StopAction server registration and its generated type include.
_STOP_REF = "franka_gripper/src/franka_gripper_node.cpp:101-105"
_STOP_TYPE_REF = "franka_gripper/src/franka_gripper.cpp:16"

#: GraspAction server registration and its generated type include.
_GRASP_REF = "franka_gripper/src/franka_gripper_node.cpp:117-122"
_GRASP_TYPE_REF = "franka_gripper/src/franka_gripper.cpp:13"

#: MoveAction server registration and its generated type include.
_MOVE_REF = "franka_gripper/src/franka_gripper_node.cpp:109-113"
_MOVE_TYPE_REF = "franka_gripper/src/franka_gripper.cpp:15"

#: HomingAction server registration and its generated type include.
_HOME_REF = "franka_gripper/src/franka_gripper_node.cpp:92-96"
_HOME_TYPE_REF = "franka_gripper/src/franka_gripper.cpp:14"

#: The state publisher and its type include.
_STATE_REF = "franka_gripper/src/franka_gripper_node.cpp:174-175"
_STATE_TYPE_REF = "franka_gripper/src/franka_gripper_node.cpp:13"

#: The node's configurable defaults; these are deployment parameters, not
#: device bounds.
_CONFIG_REF = "franka_gripper/config/franka_gripper_node.yaml:1-5"
_NODE_PARAMS_REF = "franka_gripper/src/franka_gripper_node.cpp:57-88"

#: The two finger-position assignments use half of the total opening width.
_STATE_POSITION_REF = "franka_gripper/src/franka_gripper_node.cpp:185-186"

#: The documented StopAction and GraspAction semantics.
_STOP_DOC_REF = "franka_gripper/doc/index.rst:16-18"
_GRASP_DOC_REF = "franka_gripper/doc/index.rst:10-14"

#: The clone's only service-shaped stop is the Gazebo ``set_user_stop``
#: simulator hook, explicitly documented as simulation-only.
_GAZEBO_STOP_SERVICE_REF = "franka_gazebo/src/franka_hw_sim.cpp:405-411"
_GAZEBO_STOP_DOC_REF = "franka_gazebo/doc/index.rst:230-234"

_ACK = Field("boolean", description="True when the upstream action returned success=true")
_ERROR = Field("string", description="Upstream error text; empty on success")

#: The node's default speed and grasp epsilon are ROS parameters, so the
#: driver sends the documented defaults as fixed request fields rather than
#: treating them as device limits.
_DEFAULT_SPEED = 0.1       # franka_gripper_node.yaml:2 (placeholder request value)
_DEFAULT_EPSILON = 0.005   # franka_gripper_node.yaml:4-5 (placeholder request value)

_GRASP = {
    "action": "/franka_gripper/grasp",
    "type": "franka_gripper/GraspAction",
    "profile": "ros1-actionlib",
    "source_name": "grasp",
    "source_ref": _GRASP_REF,
    "type_ref": _GRASP_TYPE_REF,
    "args": {
        "width": {"from": "input.width", "unit": {"from": "mm", "to": "m"}},
        "force": {"from": "input.force"},
        "speed": {"value": _DEFAULT_SPEED},
        "epsilon.inner": {"value": _DEFAULT_EPSILON},
        "epsilon.outer": {"value": _DEFAULT_EPSILON},
    },
    "result": {"map": {"grasped": "success"}},
    "success": {"path": "error", "equals": ""},
}

_MOVE = {
    "action": "/franka_gripper/move",
    "type": "franka_gripper/MoveAction",
    "profile": "ros1-actionlib",
    "source_name": "move",
    "source_ref": _MOVE_REF,
    "type_ref": _MOVE_TYPE_REF,
    "args": {
        "width": {"from": "input.width", "unit": {"from": "mm", "to": "m"}},
        "speed": {"from": "input.speed"},
    },
    "result": {"map": {"success": "success", "error": "error"}},
    "success": {"path": "success", "equals": True},
}

_HOME = {
    "action": "/franka_gripper/homing",
    "type": "franka_gripper/HomingAction",
    "profile": "ros1-actionlib",
    "source_name": "homing",
    "source_ref": _HOME_REF,
    "type_ref": _HOME_TYPE_REF,
    "result": {"map": {"success": "success", "error": "error"}},
    "success": {"path": "success", "equals": True},
}

_STOP = {
    "action": "/franka_gripper/stop",
    "type": "franka_gripper/StopAction",
    "profile": "ros1-actionlib",
    "source_name": "stop",
    "source_ref": _STOP_REF,
    "type_ref": _STOP_TYPE_REF,
    "result": {"map": {"success": "success", "error": "error"}},
    "success": {"path": "success", "equals": True},
}

_JOINT_STATES = {
    "topic": "/franka_gripper/joint_states",
    "type": "sensor_msgs/JointState",
    "source_name": "joint_states",
    "source_ref": _STATE_REF,
    "type_ref": _STATE_TYPE_REF,
    "path": "position",
}

_WIDTH_LIMIT = Limit.operator_required(
    "the clone does not state a maximum finger opening; native GripperState has max_width, "
    "but this selected JointState route does not publish that device limit"
)
_FORCE_LIMIT = Limit.operator_required(
    "the clone does not state a grasp-force bound; an operator must supply the reviewed site envelope"
)
_SPEED_LIMIT = Limit.operator_required(
    "the clone's default_speed is a configurable ROS parameter (franka_gripper_node.yaml:2), not a "
    "device velocity bound"
)


class FrankaGripper(RosDriver):
    device_id = "franka_gripper"
    device_kind = "robot.gripper"
    mode = "hardware"
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeFrankaGripper"}
    tags = ["ros", "ros1", "franka", "panda", "gripper", "grasp", "homing", "stop"]
    display_name = "Franka Hand ROS 1 gripper"
    vendor = "Franka Robotics"
    facts = [
        Fact("The launch file names the franka_gripper_node process franka_gripper and loads "
             "config/franka_gripper_node.yaml through rosparam.",
             source="upstream_code", ref=_NODE_REF),
        Fact("The example node config sets publish_rate 30 Hz, default_speed 0.1 m/s and "
             "default_grasp_epsilon inner/outer 0.005 m; they are configurable ROS parameters, not "
             "device bounds.",
             source="upstream_code", ref=_CONFIG_REF),
        Fact("The node constructs SimpleActionServer<StopAction> on the relative name \"stop\".",
             source="upstream_code", ref=_STOP_REF),
        Fact("The node constructs SimpleActionServer<GraspAction> on the relative name \"grasp\".",
             source="upstream_code", ref=_GRASP_REF),
        Fact("The node constructs SimpleActionServer<MoveAction> on the relative name \"move\".",
             source="upstream_code", ref=_MOVE_REF),
        Fact("The node constructs SimpleActionServer<HomingAction> on the relative name \"homing\".",
             source="upstream_code", ref=_HOME_REF),
        Fact("The stop handler calls gripper.stop() and the homing handler calls gripper.homing().",
             source="upstream_code", ref="franka_gripper/src/franka_gripper.cpp:86-92"),
        Fact("The move handler calls gripper.move(goal->width, goal->speed).",
             source="upstream_code", ref="franka_gripper/src/franka_gripper.cpp:82-84"),
        Fact("The grasp handler calls gripper.grasp(goal->width, goal->speed, goal->force, "
             "goal->epsilon.inner, goal->epsilon.outer).",
             source="upstream_code", ref="franka_gripper/src/franka_gripper.cpp:94-96"),
        Fact("The node publishes sensor_msgs/JointState on the relative name \"joint_states\".",
             source="upstream_code", ref=_STATE_REF),
        Fact("The node fills each of the two finger positions from gripper_state.width * 0.5, so each "
             "value is half of the total opening width.",
             source="upstream_code", ref=_STATE_POSITION_REF),
        Fact("The node obtains robot_ip, default_speed and default_grasp_epsilon from ROS parameters.",
             source="upstream_code", ref=_NODE_PARAMS_REF),
        Fact("The node obtains publish_rate, joint_names and stop_at_shutdown from ROS parameters.",
             source="upstream_code", ref="franka_gripper/src/franka_gripper_node.cpp:139-159"),
        Fact("The gripper documentation says StopAction aborts a running action and can be used to stop "
             "applying forces after grasping.",
             source="vendor_doc", ref=_STOP_DOC_REF),
        Fact("The gripper documentation says GraspAction succeeds when the finger distance is within "
             "the inner and outer epsilon around the requested width.",
             source="vendor_doc", ref=_GRASP_DOC_REF),
        Fact("Grasp.action declares width in metres, speed in metres per second and force in newtons, "
             "and returns success and error.",
             source="upstream_code", ref="franka_gripper/action/Grasp.action:1-7"),
        Fact("Move.action declares width in metres and speed in metres per second, and returns success "
             "and error.",
             source="upstream_code", ref="franka_gripper/action/Move.action:1-6"),
        Fact("Stop.action declares no goal fields and returns success and error.",
             source="upstream_code", ref="franka_gripper/action/Stop.action:1-3"),
        Fact("The franka_gazebo plugin advertises the relative \"franka_control/set_user_stop\" "
             "std_srvs/SetBool service to simulate the user stop.",
             source="upstream_code", ref=_GAZEBO_STOP_SERVICE_REF),
        Fact("The franka_gazebo documentation calls set_user_stop a special service only available in "
             "franka_gazebo for simulating the user stop; it is not a hardware stop service.",
             source="vendor_doc", ref=_GAZEBO_STOP_DOC_REF),
    ]
    safe_state = (
        "The fixed StopAction acknowledges the native gripper.stop() result. Older pending goals "
        "must settle before a fresh stop can confirm safety. This is a software native stop, not a "
        "physical e-stop; stopping grasp force may release a load."
    )

    parameters = {
        "finger_positions": Field(
            "array",
            unit="m",
            description="Two finger-joint positions from /franka_gripper/joint_states; each is half of "
                        "the total opening width",
            items=Field("number", unit="m"),
            length=2,
        ),
    }
    reads = {"finger_positions": _JOINT_STATES}
    commands = {
        "cap.manipulation.grasp.v1": _GRASP,
        "x-cap.frankarobotics.move.v1": _MOVE,
        "x-cap.frankarobotics.home.v1": _HOME,
        "x-cap.frankarobotics.stop.v1": _STOP,
    }
    actions = {
        "cap.manipulation.grasp.v1": Action(
            name="grasp",
            description="Close the gripper on an object with the upstream GraspAction",
            input={
                "width": Field("number", unit="mm", description="Requested total finger opening",
                               limit=_WIDTH_LIMIT),
                "force": Field("number", unit="N", description="Requested grasp force",
                               limit=_FORCE_LIMIT),
            },
        ),
        "x-cap.frankarobotics.move.v1": Action(
            name="move_gripper",
            verb="invoke",
            description="Move the gripper fingers to a total opening width with the upstream MoveAction",
            input={
                "width": Field("number", unit="mm", description="Requested total finger opening",
                               limit=_WIDTH_LIMIT),
                "speed": Field("number", unit="m/s", description="Requested finger speed",
                               limit=_SPEED_LIMIT),
            },
            output={"success": _ACK, "error": _ERROR,
                    "requested_speed_m_s": Field("number", unit="m/s",
                                                  description="Submitted speed after successful native completion; not measured velocity")},
        ),
        "x-cap.frankarobotics.home.v1": Action(
            name="home_gripper",
            verb="invoke",
            description="Home the gripper with the upstream HomingAction",
            output={"success": _ACK, "error": _ERROR},
        ),
        "x-cap.frankarobotics.stop.v1": Action(
            name="stop_gripper",
            verb="invoke",
            description="Request the independent native StopAction and confirm only after all older "
                        "effects have settled and a fresh stop has succeeded",
            safe_state=True,
            output={"success": _ACK, "error": _ERROR},
        ),
    }
    safety_bindings = {"estop": _STOP}

    def make_bridge(self, native):
        from .receipt import GripperReceipts

        return GripperReceipts(super().make_bridge(native))

    @classmethod
    def _fill_model(cls, model, instance, problems):
        super()._fill_model(model, instance, problems)
        # The catalogue approach field is optional and the native gripper has
        # no approach motion. Keep the advertised binding closed to the two
        # supported fields instead of accepting and silently ignoring approach.
        for binding in model.bindings:
            if binding.capability_id == "cap.manipulation.grasp.v1":
                binding.input_schema["additionalProperties"] = False
