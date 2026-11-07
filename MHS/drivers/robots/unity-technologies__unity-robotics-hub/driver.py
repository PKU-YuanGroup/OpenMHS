"""OpenMHS rosbridge driver for the Niryo One pick-and-place planner of
gh.unity-technologies/unity-robotics-hub (plans only; nothing executes them).

The pinned tutorial serves ``niryo_moveit`` (``niryo_moveit/MoverService``). The callback
``plan_pick_and_place`` builds a local ``MoveGroupCommander("arm")`` and returns four
``moveit_msgs/RobotTrajectory`` plans (pre-grasp, grasp, pick-up, place). It does not call
execute. Unity's ``TrajectoryPlanner`` runs the returned points itself, and only as the
callback of its own request (``TrajectoryPlanner.cs:147-152``, ``:171-207``).

SCOPE: this package calls that planning service over rosbridge and returns the four plans.
``executed`` is always false. A rosbridge answer is not Unity's callback, so it does not
start ``ExecuteTrajectories``. The grasp stage inside the callback lowers a copy of the
pick pose by 0.05 m (``mover.py:90-92``); that edit stays inside the ROS callback and is
not a joint command of this package. The fake records the request poses unchanged and
does not apply the offset to joint points.

NOT COVERED: the Unity arm and gripper, the ROS-TCP endpoint on port 10000
(``part_3.launch:5-8``), the ``/niryo_joints`` publisher (``SourceDestinationPublisher.cs:18``),
and the part-4 node ``sim_real_pnp.py``, which sends goals to
``niryo_one/commander/robot_action``. This package never binds that topic or that script.
The submodule ``niryo_one_ros`` is the real-robot driver and is not cited.

STOP: verb invoke, exclusive, matching the accepted plan-only shape. The ROS binding stays
an observational call (``operation`` ``read``): the service returns trajectories only, and
an effectful ROS surface without an acknowledged stop would leave e-stop unreached. The
software latch is the whole stop. There is no unpause and no re-enable. A plan already
sent is not awaited. A pick-and-place Unity started from its own button is not reached.

RISK: R0, the card floor. This package commands no arm and does not publish a joint
command or ``cmd_vel``. ``demo.launch`` passes ``simulation_mode`` true into the
controllers (``demo.launch:5-7``). ``move_group.launch`` still defaults
``allow_trajectory_execution`` to true (``:15-16``); the callback only calls ``plan()``.

The commander is a local variable of the callback (``mover.py:75-76``). ``rospy.spin``
only waits (``mover.py:130``). It does not serialise service callbacks: another client
of ``/niryo_moveit`` can be inside ``plan_pick_and_place`` at the same time, each with
its own commander, both talking to the shared MoveIt ``move_group`` node. Plan only
while Unity is not calling the service. Exclusive covers this endpoint's locally
active invocations. A deadline or an e-stop does not retire a plan already sent, so
remote planning can continue and overlap the next request.

Written by Grok (grok-4.7, a model and not a human) as
ext-p5-reauthor--unity-technologies__unity-robotics-hub-20261105. Codex reviews it.
``reviewed_by`` stays null. Every endpoint, type and fact cites the pinned clone at
b8d1e1d4c76c9ce75fc145cdbf55a9072cc77364. Facts that name ``moveit_msgs`` or
``ros_tcp_endpoint`` cite those git submodules at their gitlink commits. The fake is a
ROS-free recording transport. No Unity, ROS, MoveIt or rosbridge was run.
"""

import math

from mhs.driver import Action, DriverFailed, Fact, Field, Limit, RosDriver

_MOVER = "tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py"
_SRV = "tutorials/pick_and_place/ROS/src/niryo_moveit/srv/MoverService.srv"
_MSG = "tutorials/pick_and_place/ROS/src/niryo_moveit/msg/NiryoMoveitJoints.msg"
_LAUNCH = "tutorials/pick_and_place/ROS/src/niryo_moveit/launch"
_CONFIG = "tutorials/pick_and_place/ROS/src/niryo_moveit/config"
_URDF = "tutorials/pick_and_place/ROS/src/niryo_one_urdf/niryo_one.urdf.xacro"
_PNP = "tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/sim_real_pnp.py"
_UNITY = "tutorials/pick_and_place/Scripts/TrajectoryPlanner.cs"
_PUB = "tutorials/pick_and_place/Scripts/SourceDestinationPublisher.cs"
_PART4 = "tutorials/pick_and_place/Scripts_Part4/RealSimPickAndPlace.cs"
_DOCKER = "tutorials/pick_and_place/docker/Dockerfile"
_MOVEIT_MSGS = "tutorials/pick_and_place/ROS/src/moveit_msgs"
_TCP = "tutorials/pick_and_place/ROS/src/ros_tcp_endpoint"
_PKG = "tutorials/pick_and_place/ROS/src/niryo_moveit/package.xml"

#: Planner order (mover.py:23). Unity copies ArticulationBody jointPosition[0] in the same index order.
JOINTS = ("joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6")

_ARGS = {"joints_input.joints": {"from": "input.start_joints_rad"}}
for _pose in ("pick", "place"):
    for _index, _axis in enumerate(("x", "y", "z")):
        _ARGS[f"{_pose}_pose.position.{_axis}"] = {"from": f"input.{_pose}_position[{_index}]", "type": "number"}
    for _index, _axis in enumerate(("x", "y", "z", "w")):
        _ARGS[f"{_pose}_pose.orientation.{_axis}"] = {"from": f"input.{_pose}_orientation[{_index}]",
                                                     "type": "number"}

_PLAN = {
    "service": "/niryo_moveit",
    "type": "niryo_moveit/MoverService",
    "source_name": "niryo_moveit",
    "source_ref": _MOVER + ":128",
    "type_ref": _MOVER + ":21",
    # The callback plans and returns (mover.py:36-55, 72-121). It has no application success
    # predicate (MoverService.srv:1-5 answers trajectories only). operation "read" is the
    # bridge term for a call that confirms nothing and needs no acknowledged stop. The
    # capability is still a command: verb invoke, exclusive.
    "operation": "read",
    "args": _ARGS,
    "result": {
        "joint_names": {"from": "trajectories[*].joint_trajectory.joint_names"},
        "points": {"from": "trajectories[*].joint_trajectory.points"},
        "executed": {"const": False},
    },
    # A client bound, not a device limit: four MoveIt plans. The server default deadline is 30 s.
    "timeout_ms": 30000,
}

#: Cited URDF travel, from the xacro properties (the joint XML only names those properties).
#: Elbow index 2 is operator_required: its upper attribute is ``${PI/2}``, which the gate
#: does not evaluate. demo.launch:19-21 allows a 0.3 rad start error past these limits;
#: this package still enforces the URDF travel and does not add 0.3.
_JOINT_LIMITS = [
    Limit(min=-3.05433, max=3.05433, path="[0]", unit="rad", source="upstream_code", ref=_URDF + ":39-40"),
    Limit(min=-1.91986, max=0.640187, path="[1]", unit="rad", source="upstream_code", ref=_URDF + ":41-42"),
    Limit.operator_required(
        "elbow upper is the xacro expression ${PI/2}, which is not a cited number; the operator sets both ends",
        path="[2]"),
    Limit(min=-3.05433, max=3.05433, path="[3]", unit="rad", source="upstream_code", ref=_URDF + ":45-46"),
    Limit(min=-1.74533, max=1.91986, path="[4]", unit="rad", source="upstream_code", ref=_URDF + ":47-48"),
    Limit(min=-2.57436, max=2.57436, path="[5]", unit="rad", source="upstream_code", ref=_URDF + ":49-50"),
]
_POSITION_LIMIT = Limit.operator_required("the clone states no workspace bound", path="[*]")
_ORIENTATION_LIMIT = Limit.operator_required("the clone states no quaternion bound", path="[*]")


class _CheckedPlan:
    """Refuse a non-finite number or a zero-norm quaternion before the service is called."""

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        if capability_id == "x-cap.unity-technologies.niryo_pick_place_plan.v1":
            values = dict(args or {})
            for name in ("start_joints_rad", "pick_position", "place_position", "pick_orientation",
                         "place_orientation"):
                items = values.get(name)
                if isinstance(items, (list, tuple)) and not all(
                        isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item)
                        for item in items):
                    raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", f"{name} must hold finite numbers")
            for name in ("pick_orientation", "place_orientation"):
                items = values.get(name)
                if isinstance(items, (list, tuple)) and math.sqrt(sum(float(item) ** 2 for item in items)) < 1e-6:
                    raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                                       f"{name} is a zero quaternion, which describes no orientation")
        return self._inner.call(capability_id, args, ctx)

    def __getattr__(self, name):
        return getattr(self._inner, name)


_POINT = Field(
    "object",
    description="One trajectory point as MoveIt returns it",
    properties={
        "positions": Field("array", items=Field("number"), unit="rad", length=6,
                           description="Joint positions in joint_names order"),
        "velocities": Field("array", items=Field("number"), unit="rad/s", max_items=6,
                            description="Joint velocities, empty when the planner gives none"),
        "accelerations": Field("array", items=Field("number"), unit="rad/s2", max_items=6,
                               description="Joint accelerations, empty when the planner gives none"),
        "effort": Field("array", items=Field("number"), max_items=6,
                        description="Joint efforts as returned"),
        "time_from_start": Field("object", description="Time of the point from the trajectory start",
                                 properties={"secs": Field("integer", unit="s"),
                                             "nsecs": Field("integer", unit="ns")}),
    })


class UnityNiryoPickPlacePlanner(RosDriver):
    device_id = "unity-niryo-pick-place-planner"
    device_kind = "device"
    mode = "simulated"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeNiryoMoverService"}
    tags = ["ros", "ros1", "melodic", "moveit", "unity", "niryo", "pick-and-place", "planning", "plan-only"]
    display_name = "Niryo pick-and-place planner (Unity Robotics Hub)"
    vendor = "unity-technologies"
    model = "niryo_moveit MoverService (MoveIt) of the Unity Robotics Hub pick-and-place tutorial"
    facts = [
        Fact("moveit_server initialises moveit_commander, starts node niryo_moveit_server, advertises service "
             "niryo_moveit of type MoverService with callback plan_pick_and_place, and calls rospy.spin.",
             source="upstream_code", ref=_MOVER + ":124-130"),
        Fact("MoverService takes NiryoMoveitJoints joints_input, a geometry_msgs/Pose pick_pose and a "
             "geometry_msgs/Pose place_pose, and returns a moveit_msgs/RobotTrajectory[] named trajectories.",
             source="upstream_code", ref=_SRV + ":1-5"),
        Fact("NiryoMoveitJoints carries float64[6] joints and its own geometry_msgs/Pose pick_pose and place_pose.",
             source="upstream_code", ref=_MSG + ":1-3"),
        Fact("moveit_msgs/RobotTrajectory holds a trajectory_msgs/JointTrajectory joint_trajectory and a "
             "trajectory_msgs/MultiDOFJointTrajectory multi_dof_joint_trajectory.",
             source="upstream_code", ref=_MOVEIT_MSGS + "/msg/RobotTrajectory.msg:1-2"),
        Fact("The moveit_msgs package version is 0.11.1 and its license element is BSD.",
             source="upstream_code", ref=_MOVEIT_MSGS + "/package.xml:3-14"),
        Fact("The planner's joint names are joint_1, joint_2, joint_3, joint_4, joint_5 and joint_6.",
             source="upstream_code", ref=_MOVER + ":23"),
        Fact("plan_trajectory writes the given start angles into a JointState, sets that as the MoveIt start "
             "state, sets the destination pose, calls move_group.plan, raises Exception when the plan is false, "
             "and otherwise returns planCompat(plan).",
             source="upstream_code", ref=_MOVER + ":36-55"),
        Fact("planCompat returns plan[1] when sys.version_info is at least (3, 0), and otherwise returns plan.",
             source="upstream_code", ref=_MOVER + ":26-31"),
        Fact("plan_pick_and_place constructs a MoveGroupCommander for the group name arm as a local variable.",
             source="upstream_code", ref=_MOVER + ":75-76"),
        Fact("The start configuration is req.joints_input.joints.",
             source="upstream_code", ref=_MOVER + ":78"),
        Fact("The pre-grasp plan targets req.pick_pose from that start configuration.",
             source="upstream_code", ref=_MOVER + ":81"),
        Fact("When the pre-grasp trajectory has no points, plan_pick_and_place returns the still-empty response.",
             source="upstream_code", ref=_MOVER + ":84-85"),
        Fact("The grasp plan targets a copy of req.pick_pose whose position.z is reduced by 0.05; the comment "
             "calls that a static value coming from Unity.",
             source="upstream_code", ref=_MOVER + ":90-92"),
        Fact("When the grasp trajectory has no points, the callback returns the still-empty response.",
             source="upstream_code", ref=_MOVER + ":94-95"),
        Fact("The pick-up plan targets req.pick_pose from the grasp plan's last joint positions.",
             source="upstream_code", ref=_MOVER + ":100"),
        Fact("When the pick-up trajectory has no points, the callback returns the still-empty response.",
             source="upstream_code", ref=_MOVER + ":102-103"),
        Fact("The place plan targets req.place_pose.",
             source="upstream_code", ref=_MOVER + ":108"),
        Fact("When the place trajectory has no points, the callback returns the still-empty response.",
             source="upstream_code", ref=_MOVER + ":110-111"),
        Fact("When every stage has points, the callback appends the four plans and calls clear_pose_targets.",
             source="upstream_code", ref=_MOVER + ":113-119"),
        Fact("The docstring says gripper behaviour is handled outside this trajectory planning.",
             source="upstream_code", ref=_MOVER + ":66-68"),
        Fact("The SRDF group arm is the chain from base_link to tool_link.",
             source="upstream_code", ref=_CONFIG + "/niryo_one.srdf:32-34"),
        Fact("The SRDF file header says the program is free software under the GNU General Public License, "
             "either version 3 or any later version.",
             source="upstream_code", ref=_CONFIG + "/niryo_one.srdf:8-11"),
        Fact("part_3.launch starts server_endpoint from ros_tcp_endpoint, the mover node running mover.py, "
             "and includes demo.launch. The tcp_port argument defaults to 10000.",
             source="upstream_code", ref=_LAUNCH + "/part_3.launch:1-10"),
        Fact("demo.launch includes controllers.launch with simulation_mode true and includes move_group.launch.",
             source="upstream_code", ref=_LAUNCH + "/demo.launch:5-10"),
        Fact("controllers.launch defaults simulation_mode to false. Its comment says true makes the controller "
             "echo the position command and deactivates hardware. fake_communication is set from simulation_mode.",
             source="upstream_code", ref=_LAUNCH + "/controllers.launch:3-16"),
        Fact("controllers.launch spawns joint_state_controller and niryo_one_follow_joint_trajectory_controller.",
             source="upstream_code", ref=_LAUNCH + "/controllers.launch:31-34"),
        Fact("move_group.launch defaults allow_trajectory_execution to true and fake_execution to false.",
             source="upstream_code", ref=_LAUNCH + "/move_group.launch:15-16"),
        Fact("demo.launch sets /move_group/start_state_max_bounds_error to 0.3. The comment says this allows "
             "joints to be outside of min and max values when starting.",
             source="upstream_code", ref=_LAUNCH + "/demo.launch:19-21"),
        Fact("The xacro sets PI to 3.14159265359 and the rotation-limit properties shoulder -3.05433 to 3.05433, "
             "arm -1.91986 to 0.640187, elbow -1.397485 to ${PI/2}, forearm -3.05433 to 3.05433, wrist -1.74533 "
             "to 1.91986, and hand -2.57436 to 2.57436.",
             source="upstream_code", ref=_URDF + ":37-50"),
        Fact("joint_1 through joint_6 are revolute, and each limit lower and upper attribute names an xacro "
             "limit property.",
             source="upstream_code", ref=_URDF + ":174-220"),
        Fact("joint_limits.yaml says joint properties can be changed with the keys max_position, min_position, "
             "max_velocity and max_acceleration, and the joint_1 entry sets max_velocity 2.2 and max_acceleration 1.5.",
             source="upstream_code", ref=_CONFIG + "/joint_limits.yaml:1-9"),
        Fact("part_4.launch starts server_endpoint and the node sim_real_pnp running sim_real_pnp.py.",
             source="upstream_code", ref=_LAUNCH + "/part_4.launch:5-9"),
        Fact("listener subscribes to topic sim_real_pnp with type MoverServiceRequest and callback "
             "plan_pick_and_place.",
             source="upstream_code", ref=_PNP + ":170-173"),
        Fact("send_trajectory_goal sets RobotMoveGoal cmd.Trajectory and cmd.cmd_type to TRAJECTORY_COMMAND_ID, "
             "then calls send_goal and wait_for_result.",
             source="upstream_code", ref=_PNP + ":79-86"),
        Fact("sim_real_pnp plan_pick_and_place waits for the action server niryo_one/commander/robot_action.",
             source="upstream_code", ref=_PNP + ":123-124"),
        Fact("PICK_PLACE_HEIGHT_OFFSET is 0.065.",
             source="upstream_code", ref=_PNP + ":41"),
        Fact("TrajectoryPlanner's serialized field m_RosServiceName defaults to niryo_moveit.",
             source="upstream_code", ref=_UNITY + ":19"),
        Fact("CurrentJointConfig copies each ArticulationBody jointPosition[0] into joints.joints.",
             source="upstream_code", ref=_UNITY + ":105-113"),
        Fact("PublishJoints builds a MoverServiceRequest from CurrentJointConfig and the target and placement "
             "poses converted with To<FLU>, and sends it to m_RosServiceName with TrajectoryResponse.",
             source="upstream_code", ref=_UNITY + ":123-144"),
        Fact("TrajectoryResponse starts ExecuteTrajectories when response.trajectories.Length is greater than 0.",
             source="upstream_code", ref=_UNITY + ":147-152"),
        Fact("ExecuteTrajectories writes each point's positions, multiplied by Mathf.Rad2Deg, as ArticulationBody "
             "xDrive targets, calls CloseGripper when poseIndex equals Poses.Grasp, and calls OpenGripper after "
             "the plans.",
             source="upstream_code", ref=_UNITY + ":171-207"),
        Fact("SourceDestinationPublisher's m_TopicName defaults to /niryo_joints, and Start registers a publisher "
             "of NiryoMoveitJointsMsg on that topic.",
             source="upstream_code", ref=_PUB + ":18-38"),
        Fact("RealSimPickAndPlace's rosRobotCommandsTopicName defaults to niryo_one/commander/robot_action/goal.",
             source="upstream_code", ref=_PART4 + ":25"),
        Fact("RealSimPickAndPlace Start subscribes to rosRobotCommandsTopicName for RobotMoveActionGoal with "
             "ExecuteRobotCommands.",
             source="upstream_code", ref=_PART4 + ":69-73"),
        Fact("The pick-and-place Docker image starts FROM ros:melodic-ros-base.",
             source="upstream_code", ref=_DOCKER + ":1"),
        Fact("The Docker image installs ros-melodic-moveit and ros-melodic-rosbridge-suite.",
             source="upstream_code", ref=_DOCKER + ":5"),
        Fact("LICENSE.md says the software is made available under the Apache 2.0 license.",
             source="vendor_doc", ref="LICENSE.md:3"),
        Fact("The niryo_moveit package.xml license element is Apache 2.0.",
             source="upstream_code", ref=_PKG + ":10"),
        Fact("The ros_tcp_endpoint package version is 0.7.0 and its license element is Apache 2.0.",
             source="upstream_code", ref=_TCP + "/package.xml:3-9"),
    ]
    safe_state = (
        "Plan-only package: it sends nothing that executes a plan or commands the Unity arm, its gripper, "
        "or the Niryo action server. An e-stop latches this endpoint in software and refuses further planning "
        "requests. A request already sent is not awaited. There is no unpause. A pick-and-place that Unity "
        "started from its own button runs in Unity's coroutine and is not reached."
    )
    fidelity = {
        "engine": "analytic:ROS recording fake of the niryo_moveit MoverService (no MoveIt, OMPL or Unity)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "The fake answers a fixed placeholder plan shape. A live MoveIt plan is not replayed.",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "PLAN ONLY: the package never executes a plan",
            "the fake's trajectories are placeholders and do not apply the callback's 0.05 m grasp drop",
            "Unity executes trajectories only in the callback of its own request, so a receipt never shows "
            "motion of the simulated arm",
            "the fake records the requested radian vector unchanged as the first plan's start and chains each "
            "later plan to the previous placeholder goal; it runs no IK, MoveIt, OMPL or collision checking",
            "an empty trajectory list is a successful ROS response in the callback (mover.py:84-85 and the "
            "three later empty returns) and a failed receipt here, because the output contract requires four "
            "plans; a plan() that is false raises in plan_trajectory (mover.py:48-53) and is a failed call",
            "the MoveGroupCommander is local (mover.py:75-76). rospy.spin only waits (mover.py:130) and "
            "does not serialise callbacks, so another /niryo_moveit client can overlap this one on the "
            "shared move_group. Plan only while Unity is not calling the service. Exclusive covers this "
            "endpoint's active calls only; a deadline or e-stop does not retire a plan already sent",
            "joint travel for indexes 0, 1, 3, 4 and 5 is the xacro property pair. Elbow index 2 is "
            "operator_required because its upper is ${PI/2}. Pose components are operator_required. "
            "demo.launch allows 0.3 rad of start error past the URDF limits; this package does not add 0.3",
            "the Unity arm and gripper, the ROS-TCP endpoint, the /niryo_joints publisher, and sim_real_pnp "
            "are NOT COVERED. niryo_one_ros is not cited",
            "the operator runs rosbridge, which the tutorial image installs, next to part_3.launch. "
            "part_3.launch itself starts the ROS-TCP endpoint, not rosbridge",
        ],
    }
    commands = {"x-cap.unity-technologies.niryo_pick_place_plan.v1": _PLAN}

    def make_bridge(self, native):
        return _CheckedPlan(super().make_bridge(native))

    actions = {
        "x-cap.unity-technologies.niryo_pick_place_plan.v1": Action(
            name="plan_pick_and_place",
            verb="invoke",
            exclusive=True,
            description="Plan four trajectories. executed is always false. Exclusive.",
            input={
                "start_joints_rad": Field(
                    "array", items=Field("number"), unit="rad", length=6, limit=_JOINT_LIMITS,
                    description="joint_1..joint_6 start, rad"),
                "pick_position": Field("array", items=Field("number"), unit="m", length=3, limit=_POSITION_LIMIT,
                                       description="Pick x, y, z"),
                "pick_orientation": Field("array", items=Field("number"), unit="1", length=4,
                                          limit=_ORIENTATION_LIMIT,
                                          description="Pick x, y, z, w"),
                "place_position": Field("array", items=Field("number"), unit="m", length=3, limit=_POSITION_LIMIT,
                                        description="Place x, y, z"),
                "place_orientation": Field("array", items=Field("number"), unit="1", length=4,
                                           limit=_ORIENTATION_LIMIT,
                                           description="Place x, y, z, w"),
            },
            output={
                "joint_names": Field(
                    "array", length=4,
                    items=Field("array", length=6, items=Field("string", enum=list(JOINTS))),
                    description="Each plan's joint names, in order pre-grasp, grasp, pick-up, place"),
                "points": Field(
                    "array", length=4, items=Field("array", min_items=1, items=_POINT),
                    description="Each plan's points, in that order. A later plan starts where the previous ends"),
                "executed": Field("boolean", enum=[False],
                                  description="Always false: the package plans only"),
            },
        ),
    }
