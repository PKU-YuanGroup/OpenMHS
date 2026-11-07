"""OpenMHS rosbridge driver for the pinned UR5LegoVision ROS 1 control surface.

The upstream Python node ``UR5Controller`` hosts three absolute ROS services
(``/ur5/move_joints``, ``/ur5/move_to`` and ``/ur5/move_gripper``), subscribes
to ``/ur5/joint_states`` and publishes ``/ur5/ee_pose``.  This package is a
configuration-only :class:`RosDriver`; it declares no Python native class and
does not start the node, MoveIt or Gazebo.

The scope is joint-space motion, gripper diameter commands, and explicit
joint-state and end-effector observations.  The service replies are the
upstream boolean acknowledgements; they are not measured arrival.  The
simulated safe state is the Gazebo ``/gazebo/pause_physics`` service, which the
clone declares but never calls; the clone cancels no pending motion callback
and provides no stopped-state measurement.  The motion loops sleep on a
simulated-time ``ros.Rate``, so a paused world holds them and an unpause lets
an interrupted motion continue; ``mhs.safety.reset`` therefore does not unpause
(SAFE-042), and only the explicit resume command does.  With ``real_robot`` set
in the upstream parameters the same node drives a real UR5, where this
Gazebo-only stop cannot be reached.

Every endpoint, type and fact cites the pinned clone at
7cf487fbadcfd42e2fe09f75c7345d24920a1e3d.  The fake is a ROS-free analytic
contract transport; no ROS graph, Gazebo, MoveIt or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: UR5Controller registers the three absolute motion services.
_MOVE_JOINTS_REF = "motion/ur5_controller.py:308"
_MOVE_TO_REF = "motion/ur5_controller.py:309"
_MOVE_GRIPPER_REF = "motion/ur5_controller.py:310"

#: The service types are imported from ros_impedance_controller.srv.
_SRV_IMPORT_REF = "motion/ur5_controller.py:72"
_GRIPPER_SRV_IMPORT_REF = "motion/ur5_controller.py:71"

#: UR5Controller declares the Gazebo physics pause/resume proxies as
#: std_srvs/Empty; the clone contains no call to either proxy.
_PAUSE_REF = "motion/ur5_controller.py:237"
_RESUME_REF = "motion/ur5_controller.py:238"
_EMPTY_IMPORT_REF = "motion/ur5_controller.py:63"

#: The joint-state subscriber and the end-effector pose publisher.
_JOINT_STATE_REF = "motion/ur5_controller.py:244-246"
_JOINT_STATE_TYPE_REF = "motion/ur5_controller.py:64"
_EE_POSE_REF = "motion/ur5_controller.py:302"

#: The configured arm joint order and simulated client timing.
_JOINT_ORDER_REF = "locosim/robot_control/base_controllers/params.py:17"
_DT_REF = "locosim/robot_control/base_controllers/params.py:12"
_SIM_SPEED_REF = "motion/main.py:53-56"
_CONTROLLER_SPEED_REF = "motion/ur5_controller.py:108-115"

#: The joint travel limits used by the launch's UR5e limit file.
_JOINT_LIMITS_REF = "locosim/robot_descriptions/ur_description/config/ur5e/joint_limits.yaml:10-80"

#: Request fields and response fields of the three services.
_MOVE_JOINTS_SRV_REF = "locosim/ros_impedance_controller/srv/MoveJoints.srv:1-5"
_MOVE_TO_SRV_REF = "locosim/ros_impedance_controller/srv/MoveTo.srv:1-5"
_MOVE_GRIPPER_SRV_REF = "locosim/ros_impedance_controller/srv/generic_float.srv:1-3"

#: The motion loop has no cancellation or timeout check, and the gripper
#: loop still carries a TODO for a timeout.
_MOVE_LOOP_REF = "motion/ur5_controller.py:635-644"
_GRIPPER_LOOP_REF = "motion/ur5_controller.py:589-604"
_MOVE_RATE_REF = "motion/ur5_controller.py:621-644"
_SIM_LAUNCH_REF = "locosim/ros_impedance_controller/launch/ros_impedance_controller_ur5.launch:58-67"
_LIMIT_FILE_ARG_REF = "locosim/ros_impedance_controller/launch/ros_impedance_controller_ur5.launch:26"
_REAL_FLAG_REF = "locosim/robot_control/base_controllers/params.py:20"
_REAL_START_REF = "motion/ur5_controller.py:141-164"
_REAL_GRIPPER_REF = "locosim/robot_control/base_controllers/components/gripper_manager.py:64-100"
_MOTION_CLIENT_REF = "motion/main.py:67-72"

_JOINT_NAMES = [
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
]
_JOINT_MIN = [-6.14, -3.14, -3.14, -6.28, -6.28, -6.28]
_JOINT_MAX = [6.14, 0.0, 3.14, 6.28, 6.28, 6.28]

#: One explicit joint-space service call.  ``dt`` 0.001 s and ``v_des`` 0.6
#: are the upstream simulated client's deployed values, not device limits;
#: they are fixed request fields and are recorded in facts below.
_MOVE_JOINTS = {
    "service": "/ur5/move_joints",
    "type": "ros_impedance_controller/MoveJoints",
    "source_ref": _MOVE_JOINTS_REF,
    "type_ref": _SRV_IMPORT_REF,
    "request": {"dt": 0.001, "v_des": 0.6},
    "timeout_ms": 120000,
    "args": {"q_des": {"from": "input.joint_positions"}},
    "result": {"map": {"success": "success"}},
    "success": {"path": "success", "equals": True},
}

#: One explicit gripper-diameter service call.  The upstream request field is
#: ``data`` and the response field is ``ack``.
_MOVE_GRIPPER = {
    "service": "/ur5/move_gripper",
    "type": "ros_impedance_controller/generic_float",
    "source_ref": _MOVE_GRIPPER_REF,
    "type_ref": _GRIPPER_SRV_IMPORT_REF,
    "timeout_ms": 30000,
    "args": {"data": {"from": "input.diameter_mm"}},
    "result": {"map": {"moved": "ack"}},
    "success": {"path": "ack", "equals": True},
}

#: Fixed, input-free Gazebo simulator pause/resume calls.
_PAUSE = {
    "service": "/gazebo/pause_physics",
    "type": "std_srvs/Empty",
    "source_ref": _PAUSE_REF,
    "type_ref": _EMPTY_IMPORT_REF,
    "description": "Pause the Gazebo simulation with the acknowledged empty service",
    "timeout_ms": 5000,
    "success": {"path": "$", "equals": {}},
}

_RESUME = {
    "service": "/gazebo/unpause_physics",
    "type": "std_srvs/Empty",
    "source_ref": _RESUME_REF,
    "type_ref": _EMPTY_IMPORT_REF,
    "description": "Resume the Gazebo simulation with the acknowledged empty service",
    "timeout_ms": 5000,
    "success": {"path": "$", "equals": {}},
}

_JOINT_STATE = {
    "topic": "/ur5/joint_states",
    "type": "sensor_msgs/JointState",
    "source_ref": _JOINT_STATE_REF,
    "type_ref": _JOINT_STATE_TYPE_REF,
    "operation": "subscribe",
    "timeout_ms": 2000,
    "path": "$",
    "result": {
        "map": {
            "joint_names": "name",
            "joint_positions": "position",
            "joint_velocities": "velocity",
            "joint_efforts": "effort",
        }
    },
}

_EE_POSE = {
    "topic": "/ur5/ee_pose",
    "type": "geometry_msgs/Pose",
    "source_ref": _EE_POSE_REF,
    "operation": "subscribe",
    "timeout_ms": 2000,
    "path": "$",
    "result": {"map": {"position": "position", "orientation": "orientation"}},
}

_JOINT_POSITIONS = Field(
    "array",
    unit="rad",
    description="Six target joint positions in the upstream order: shoulder_pan, shoulder_lift, "
                "elbow, wrist_1, wrist_2, wrist_3",
    items=Field("number", unit="rad"),
    length=6,
    limit=Limit(
        min=_JOINT_MIN,
        max=_JOINT_MAX,
        names=_JOINT_NAMES,
        source="upstream_code",
        ref=_JOINT_LIMITS_REF,
        reason="The launch selects the UR5e joint_limit_params file; these are its stated "
               "per-joint position bounds for the six arm joints.",
    ),
)

_DIAMETER_LIMIT = Limit.operator_required(
    "the clone maps a diameter through atan2(0.5 * (diameter - 40), 60) but states no "
    "mechanical opening or closing bound; the operator must supply the reviewed gripper envelope"
)

_POSITION = Field(
    "object",
    description="Tool-centre position in the reported frame",
    properties={
        "x": Field("number", unit="m", description="Position x"),
        "y": Field("number", unit="m", description="Position y"),
        "z": Field("number", unit="m", description="Position z"),
    },
)

_ORIENTATION = Field(
    "object",
    description="Orientation as a unit quaternion",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)


class _GripperReceipts:
    """Production receipt adapter: echo the acknowledged gripper request value.

    The upstream ``generic_float`` response contains only ``ack``.  The
    requested diameter is added to the output so a caller can distinguish two
    acknowledged commands; it is a requested value, not a measured opening.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id == "x-cap.anhtuduong.move_gripper.v1" and isinstance(output, dict):
            output = dict(output)
            output["diameter_mm"] = float(dict(args or {})["diameter_mm"])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


class Ur5LegoVision(RosDriver):
    device_id = "ur5legovision"
    device_kind = "robot.arm"
    mode = "simulated"
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeUr5Legovision"}
    tags = ["ros", "ros1", "ur5", "robot-arm", "lego", "gazebo", "moveit", "joint-state"]
    display_name = "UR5LegoVision UR5 ROS 1 arm"
    vendor = "Anh Tu Duong"
    facts = [
        Fact("UR5Controller imports MoveJoints and MoveTo from ros_impedance_controller.srv.",
             source="upstream_code", ref=_SRV_IMPORT_REF),
        Fact("UR5Controller imports generic_float from ros_impedance_controller.srv.",
             source="upstream_code", ref=_GRIPPER_SRV_IMPORT_REF),
        Fact("UR5Controller registers the absolute service /ur5/move_joints with the MoveJoints type.",
             source="upstream_code", ref=_MOVE_JOINTS_REF),
        Fact("UR5Controller registers the absolute service /ur5/move_to with the MoveTo type.",
             source="upstream_code", ref=_MOVE_TO_REF),
        Fact("UR5Controller registers the absolute service /ur5/move_gripper with the generic_float type.",
             source="upstream_code", ref=_MOVE_GRIPPER_REF),
        Fact("MoveJoints.srv declares request fields dt, v_des and q_des and response field bool success.",
             source="upstream_code", ref=_MOVE_JOINTS_SRV_REF),
        Fact("MoveTo.srv declares request fields pose_target, dt and v_des and response field bool success.",
             source="upstream_code", ref=_MOVE_TO_SRV_REF),
        Fact("generic_float.srv declares request field data and response field bool ack.",
             source="upstream_code", ref=_MOVE_GRIPPER_SRV_REF),
        Fact("The move_joints callback gets a MoveIt trajectory and calls move_joints for every trajectory "
             "point, returning False when planning fails and True after the loop.",
             source="upstream_code", ref="motion/ur5_controller.py:523-542"),
        Fact("The move_joints loop advances q_des by dt * v_ref * e / ||e|| and stops only when ||e|| is "
             "below 0.001; the loop has no cancellation, deadline or operator-stop check.",
             source="upstream_code", ref=_MOVE_LOOP_REF),
        Fact("The move_gripper callback creates ros.Rate(1/self.dt), then loops, sending the arm reference and "
             "sleeping on the rate, until any filtered desired gripper joint is within 0.0001 of the target; a "
             "TODO to handle a timeout follows the loop.",
             source="upstream_code", ref=_GRIPPER_LOOP_REF),
        Fact("move_joints creates ros.Rate(1/dt) and sleeps on it in every loop iteration.",
             source="upstream_code", ref=_MOVE_RATE_REF),
        Fact("UR5Controller creates ServiceProxy objects for /gazebo/pause_physics and "
             "/gazebo/unpause_physics with the std_srvs/Empty type.",
             source="upstream_code", ref="motion/ur5_controller.py:237-238"),
        Fact("UR5Controller imports Empty from std_srvs.srv.",
             source="upstream_code", ref=_EMPTY_IMPORT_REF),
        Fact("UR5Controller subscribes to /ur5/joint_states with the JointState type.",
             source="upstream_code", ref=_JOINT_STATE_REF),
        Fact("UR5Controller imports JointState from sensor_msgs.msg.",
             source="upstream_code", ref=_JOINT_STATE_TYPE_REF),
        Fact("UR5Controller publishes /ur5/ee_pose with the geometry_msgs.msg.Pose type.",
             source="upstream_code", ref=_EE_POSE_REF),
        Fact("The configured arm joint order is shoulder_pan_joint, shoulder_lift_joint, elbow_joint, "
             "wrist_1_joint, wrist_2_joint, wrist_3_joint.",
             source="upstream_code", ref=_JOINT_ORDER_REF),
        Fact("The UR5e joint_limit_params file states per-joint min_position and max_position for the six "
             "arm joints: [-6.14, 6.14], [-3.14, 0], [-3.14, 3.14], [-6.28, 6.28], [-6.28, 6.28], "
             "[-6.28, 6.28].",
             source="upstream_code", ref=_JOINT_LIMITS_REF),
        Fact("The configured control period dt is 0.001 s.", source="upstream_code", ref=_DT_REF),
        Fact("The simulated motion client sets v_des to 0.6.", source="upstream_code", ref=_SIM_SPEED_REF),
        Fact("The controller's simulated v_des branch sets 0.6; the real-robot branch sets 0.2.",
             source="upstream_code", ref=_CONTROLLER_SPEED_REF),
        Fact("ros_impedance_controller_ur5.launch includes gazebo_ros empty_world.launch with paused default "
             "true and use_sim_time default true.", source="upstream_code", ref=_SIM_LAUNCH_REF),
        Fact("ros_impedance_controller_ur5.launch defaults joint_limit_params to the ur5e joint_limits.yaml.",
             source="upstream_code", ref=_LIMIT_FILE_ARG_REF),
        Fact("The shipped UR5 parameters set real_robot to False.", source="upstream_code", ref=_REAL_FLAG_REF),
        Fact("startRealRobot kills rviz, gzserver and gzclient, logs STARTING REAL ROBOT and exits unless the ROS "
             "master is online and '/' + robot_name + '/ur_hardware_interface' is a running node.",
             source="upstream_code", ref=_REAL_START_REF),
        Fact("For the real robot the gripper manager opens a TCP socket to 192.168.0.100 port 30002 to send a "
             "gripper script; for the simulated robot it only sets the desired finger joints.",
             source="upstream_code", ref=_REAL_GRIPPER_REF),
        Fact("The upstream motion client in motion/main.py creates service clients for /ur5/move_joints, "
             "/ur5/move_to and /ur5/move_gripper, after waiting for /ur5/move_joints, /ur5/move_to and the "
             "relative move_gripper.",
             source="upstream_code", ref=_MOTION_CLIENT_REF),
    ]
    safe_state = (
        "Gazebo physics paused by the acknowledged /gazebo/pause_physics service: the simulated arm and its "
        "controller freeze, and a running /ur5/move_joints or /ur5/move_gripper callback is held in its "
        "simulated-time rate.sleep(), not cancelled; nothing senses quiescence. mhs.safety.reset clears only "
        "the latch and leaves Gazebo paused; the explicit resume command unpauses it, and an interrupted "
        "motion then continues. With real_robot set there is no Gazebo and this stop fails."
    )
    fidelity = {
        "engine": "analytic:ROS contract fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven contract fake with no physics step, controller, MoveIt planner or "
                     "wall-clock pacing; placeholder observations do not establish trajectory replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free analytic transport: it answers the declared topics and services with "
            "canned values and runs no Gazebo, MoveIt, ros_impedance_controller, physics, contacts or "
            "wall-clock loop",
            "joint positions, end-effector pose, gripper state and service acknowledgements are placeholder "
            "test data; they do not prove motion, arrival, grasp or stopped state",
            "the fake's /gazebo/pause_physics handler flips a local flag; it does not pause a simulator, "
            "does not cancel a pending motion service callback and provides no stopped-state measurement",
            "the clone declares /gazebo/pause_physics and /gazebo/unpause_physics but contains no call to "
            "either proxy; mhs.safety.reset does not unpause (SAFE-042), only the explicit resume command "
            "does, and live pause semantics must be confirmed against the operator's Gazebo",
            "while Gazebo is paused, every /ur5/move_joints and /ur5/move_gripper callback waits in its "
            "simulated-time rate.sleep() (the shipped launch sets use_sim_time) and answers only after a "
            "resume or the binding timeout; the fake answers at once and does not model that wait; after a "
            "resume an interrupted callback continues its old motion, because the loops have no "
            "cancellation, and overlapping calls from several clients all write the shared q_des",
            "the shipped launch starts Gazebo paused and nothing in the clone's main path unpauses it",
            "the upstream motion client (motion/main.py) calls the same motion services; running it beside "
            "MHS adds a second commander that the MHS latch does not fence",
            "with real_robot set in params.py the same node drives a real UR5 through ur_robot_driver and "
            "sends gripper scripts to 192.168.0.100:30002; no Gazebo exists there, so the e-stop fails "
            "SAFE_STATE_UNREACHED with the latch held and nothing upstream stops the arm",
            "the service callbacks return bare True/False values while the .srv files declare response "
            "objects; a live ROS deployment must confirm the serialized service response before relying on "
            "the acknowledgement",
            "the fake always answers /ur5/joint_states and /ur5/ee_pose; a paused live topic may go silent, "
            "so these are explicit observations, not an automatic resource snapshot",
            "the package exposes /ur5/move_joints, /ur5/move_gripper, /ur5/joint_states, /ur5/ee_pose, "
            "/gazebo/pause_physics and /gazebo/unpause_physics only; /ur5/move_to, the ZED camera topics, "
            "MoveIt planning, force/torque and the other Gazebo model services are NOT COVERED",
            "a live /ur5/joint_states may include additional gripper joints; the observation returns the "
            "published arrays unfiltered and the fake's six-element arrays are placeholders",
            "no real ROS graph, Gazebo, MoveIt, simulator or hardware was contacted; evidence is F0 "
            "contract_checked only",
        ],
    }

    commands = {
        "x-cap.anhtuduong.move_joints.v1": _MOVE_JOINTS,
        "x-cap.anhtuduong.move_gripper.v1": _MOVE_GRIPPER,
        "x-cap.anhtuduong.pause.v1": dict(_PAUSE, result={"paused": {"value": True}}),
        "x-cap.anhtuduong.resume.v1": dict(_RESUME, result={"resumed": {"value": True}}),
        "x-cap.anhtuduong.joint_state.v1": _JOINT_STATE,
        "x-cap.anhtuduong.ee_pose.v1": _EE_POSE,
    }
    actions = {
        "x-cap.anhtuduong.move_joints.v1": Action(
            name="move_joints",
            verb="invoke",
            description="Command six joint positions through the upstream /ur5/move_joints service; the "
                        "boolean acknowledgement does not establish measured arrival",
            input={
                "joint_positions": _JOINT_POSITIONS,
            },
            output={
                "success": Field("boolean",
                                 description="The upstream service success flag; not a measured arrival"),
            },
        ),
        "x-cap.anhtuduong.move_gripper.v1": Action(
            name="move_gripper",
            verb="invoke",
            description="Command the soft-gripper opening diameter through /ur5/move_gripper; the ack means "
                        "the upstream loop finished, not that an object was grasped",
            input={
                "diameter_mm": Field("number", unit="mm", description="Requested gripper opening diameter",
                                     limit=_DIAMETER_LIMIT),
            },
            output={
                "moved": Field("boolean",
                               description="The upstream ack flag; not a grasp or object-detection result"),
                "diameter_mm": Field("number", unit="mm",
                                     description="Requested diameter echoed after the ack; not a measured "
                                                 "opening"),
            },
        ),
        "x-cap.anhtuduong.pause.v1": Action(
            name="pause",
            safe_state=True,
            description="Pause the Gazebo simulation with the acknowledged /gazebo/pause_physics service",
            output={"paused": Field("boolean",
                                    description="True once the pause service acknowledged; not a "
                                                "stopped-state measurement")},
        ),
        "x-cap.anhtuduong.resume.v1": Action(
            name="resume",
            description="Resume the Gazebo simulation with the acknowledged /gazebo/unpause_physics service; "
                        "an interrupted motion callback then continues its old motion",
            output={"resumed": Field("boolean",
                                     description="True once the resume service acknowledged")},
        ),
        "x-cap.anhtuduong.joint_state.v1": Action(
            name="read_joint_state",
            verb="read",
            description="Read one /ur5/joint_states sample; the subscription is explicit and is not the "
                        "automatic resource snapshot",
            output={
                "joint_names": Field("array", items=Field("string"),
                                     description="Joint names in the published message order"),
                "joint_positions": Field("array", unit="rad", items=Field("number", unit="rad"),
                                         description="Joint positions in the published message order"),
                "joint_velocities": Field("array", unit="rad/s", items=Field("number", unit="rad/s"),
                                          description="Joint velocities in the published message order"),
                "joint_efforts": Field("array", unit="N.m", items=Field("number", unit="N.m"),
                                       description="Joint efforts in the published message order"),
            },
        ),
        "x-cap.anhtuduong.ee_pose.v1": Action(
            name="read_ee_pose",
            verb="read",
            description="Read one /ur5/ee_pose sample; the subscription is explicit and is not the "
                        "automatic resource snapshot",
            output={"position": _POSITION, "orientation": _ORIENTATION},
        ),
    }
    # The runtime latches first, then calls the Gazebo pause service.  The
    # same input-free pause action is the declared safe_state.achieved_by path.
    # No reset binding: unpausing lets an interrupted motion loop continue, so
    # mhs.safety.reset clears only the latch (SAFE-042) and the explicit resume
    # command unpauses Gazebo.
    safety_bindings = {"estop": _PAUSE}

    def make_bridge(self, native):
        return _GripperReceipts(super().make_bridge(native))
