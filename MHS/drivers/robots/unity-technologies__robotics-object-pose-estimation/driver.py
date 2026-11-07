"""OpenMHS rosbridge driver for the UR3 pick-and-place planning service of
gh.unity-technologies/robotics-object-pose-estimation (plans only; nothing executes them).

The repository is a Unity tutorial: a Unity scene renders a UR3 arm with a Robotiq gripper and a cube; a ROS Noetic
workspace (``ROS/src``) serves two rospy services that the scene calls over the ROS-TCP endpoint. Its pipeline is
image -> pose -> plan -> execute, and only the middle two steps run in ROS:

* ``pose_estimation_service`` (``ur3_moveit/PoseEstimationService``) estimates the cube's pose from a full
  ``sensor_msgs/Image`` that Unity renders and sends inside the request;
* ``ur3_moveit`` (``ur3_moveit/MoverService``) plans five MoveIt trajectories (pre-grasp, grasp, pick-up, place,
  post-place) from a start joint configuration and a pick and a place pose, and returns them;
* Unity executes the returned trajectories itself, in a coroutine started only by the response to its *own*
  request (``TrajectoryPlanner.cs:255-264``, ``:288-333``), writing ArticulationBody joint targets with fixed waits
  and opening and closing the gripper. No Unity script subscribes to a ROS topic or implements a service, so nothing
  outside Unity can command, own or stop that execution; the editor's Play mode is the only control over it.

SCOPE: this package serves the planning service only. A planning call through rosbridge is answered to this
endpoint, never to Unity, so it starts no Unity coroutine and executes nothing; the receipt certifies a plan, never
executed motion (output ``executed`` is always false). The callback adds the same "table" box to MoveIt's planning
scene and sleeps 2 s before planning (``mover.py:112-126``). One indirect effect remains: the node keeps its
MoveGroupCommander in a module global that every call replaces (``mover.py:112-116``), and rospy serves calls from
different clients in parallel, so a call that overlaps Unity's own planning call can mix this package's start state
or targets into the plan that Unity then executes in its simulation; plan only while the scene is not planning.
NOT COVERED: the Unity arm and gripper (no external interface), the pose estimation service (its
image exists only inside Unity's button handler, ``TrajectoryPlanner.cs:105-120``, ``:168-176``, so the endpoint
has no producer for it; see the RESULT notes), the ROS-TCP endpoint itself (Unity's transport; this package uses
rosbridge, which the upstream Docker image installs, ``docker/Dockerfile:5``), and the vendored universal_robot and
robotiq driver stacks (real-hardware drivers that the upstream launch does not start).

STOP: the plan call is a command (verb invoke, exclusive; integrator v4, 2026-11-05) whose ROS binding stays an
observational call, so the runtime's software latch is the whole safety path: after an e-stop the endpoint refuses
further planning requests. Every input bound is the operator's (operator_required), and a zero or non-finite
quaternion and a non-finite angle or position are refused before the call. Nothing this package sends executes a plan,
so there is nothing native to stop; a pick-and-place that Unity started from its own button is not reached by it.

RISK: R1, the card's floor (G3 refuses lower). The package commands no arm, simulated or real: by the hazard table
it would be R0. Its plans are for a UR3; the deployed MoveIt is configured to execute through
``/follow_joint_trajectory`` (``config/ros_controllers.yaml:1-11``), which no node of the upstream launch serves,
and the planning callback never asks it to execute.

Written by Claude (claude-opus-5-5, a model and not a human) as phase-4 agent p4-unity; by the user's decision of
2026-11-05 a Claude Sonnet model reviews it. Every endpoint, type and fact cites the pinned clone at
45156479bee5d308085022aa8f20edc0c6a3bccc (four facts cite the moveit_msgs and ros_tcp_endpoint git submodules, read
at their gitlink commits). The fake is a ROS-free recording transport; no Unity, ROS, MoveIt or rosbridge was run.
"""

import math

from mhs.driver import Action, DriverFailed, Fact, Field, Limit, RosDriver

_MOVER = "ROS/src/ur3_moveit/scripts/mover.py"
_SRV = "ROS/src/ur3_moveit/srv"
_MSG = "ROS/src/ur3_moveit/msg"
_LAUNCH = "ROS/src/ur3_moveit/launch"
_CONFIG = "ROS/src/ur3_moveit/config"
_ENDPOINT = "ROS/src/ur3_moveit/scripts/server_endpoint.py"
_POSE = "ROS/src/ur3_moveit/scripts/pose_estimation_script.py"
_UNITY = "PoseEstimationDemoProject/Assets/TutorialAssets/Scripts/TrajectoryPlanner.cs"
_DOC = "Documentation/4_pick_and_place.md"
_TCP = "ROS/src/ros_tcp_endpoint"  # git submodule (ROS-TCP-Endpoint), read at its gitlink commit
_MOVEIT_MSGS = "ROS/src/moveit_msgs"  # git submodule (moveit_msgs), read at its gitlink commit

#: The six arm joints in the order the planner's start state uses them (mover.py:21) and Unity writes them
#: (TrajectoryPlanner.cs:298-306).
JOINTS = ("shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint", "wrist_1_joint", "wrist_2_joint",
          "wrist_3_joint")

#: One request leaf per rule: the six start angles (degrees, as UR3MoveitJoints carries them) and the position and
#: orientation of the two geometry_msgs/Pose fields.
_ARGS = {f"joints_input.joint_0{index}": {"from": f"input.start_joints_deg[{index}]", "type": "number"}
         for index in range(6)}
for _pose in ("pick", "place"):
    for _index, _axis in enumerate(("x", "y", "z")):
        _ARGS[f"{_pose}_pose.position.{_axis}"] = {"from": f"input.{_pose}_position[{_index}]", "type": "number"}
    for _index, _axis in enumerate(("x", "y", "z", "w")):
        _ARGS[f"{_pose}_pose.orientation.{_axis}"] = {"from": f"input.{_pose}_orientation[{_index}]",
                                                     "type": "number"}

_PLAN = {
    "service": "/ur3_moveit",
    "type": "ur3_moveit/MoverService",
    "source_name": "ur3_moveit",
    "source_ref": _MOVER + ":141",
    "type_ref": _MOVER + ":19",
    # The callback plans and returns; it executes nothing (mover.py:35-46, 61-110). Its state changes are MoveIt's
    # planning scene (the "table" box, re-added identically on every call, mover.py:118-126) and the module-global
    # MoveGroupCommander it replaces (mover.py:112-116); see the concurrency gap below. The capability is therefore a
    # command (verb invoke, exclusive; integrator v4, 2026-11-05), not a read. The ROS binding stays an observational
    # call ("operation": "read" is the bridge's term for a call that confirms nothing and needs no stop): RosBridge
    # refuses an effectful service command without an application success predicate (MoverService.srv:1-5 answers
    # trajectories only), and an effectful ROS surface without an acknowledged stop leaves every e-stop unreached,
    # while nothing this call starts executes on any arm.
    "operation": "read",
    "args": _ARGS,
    "result": {
        "joint_names": {"from": "trajectories[*].joint_trajectory.joint_names"},
        "points": {"from": "trajectories[*].joint_trajectory.points"},
        "executed": {"const": False},
    },
    # A client execution bound, not a device limit: the callback sleeps 2 s and runs five MoveIt plans
    # (mover.py:61-121); the server's default command deadline is the same 30 s.
    "timeout_ms": 30000,
}


#: No source states an envelope for the request (integrator v4, 2026-11-05; REVIEW.md item 3): the operator overlay
#: supplies every bound before a call is accepted (MHS.SAFETY.LIMITS_UNSET otherwise). The clone states the UR3 joint
#: limits only in radians, -3.14159265359 to 3.14159265359 for each arm joint (ROS/src/ur3_moveit/URDF/
#: ur3_with_gripper.urdf:361, 389, 417, 445, 473, 501), while the request takes degrees; it states no workspace bound
#: for the pick and place positions and no bound for a target quaternion (whose unit components lie in -1..1).
#: The reasons are short because the MCP tool carries them (G8 TOOL_SIZE).
_ANGLE_LIMIT = Limit.operator_required("the clone states the joint limits in radians only (URDF :361)", path="[*]")
_POSITION_LIMIT = Limit.operator_required("the clone states no workspace bound", path="[*]")
_ORIENTATION_LIMIT = Limit.operator_required("the clone states no quaternion bound", path="[*]")


class _CheckedPlan:
    """The plan command's input check before the service is called (integrator v4, 2026-11-05; REVIEW.md item 3).

    A target quaternion with a zero or non-finite norm describes no orientation, and a non-finite angle or position
    no configuration: each is refused with MHS.CAPABILITY.INPUT_INVALID and nothing is sent. Everything else is the
    inner RosBridge's.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        if capability_id == "x-cap.unity-technologies.pick_place_plan.v1":
            values = dict(args or {})
            for name in ("start_joints_deg", "pick_position", "place_position", "pick_orientation",
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


_POINT = Field("object", description="One trajectory point as MoveIt returns it (trajectory_msgs/JointTrajectoryPoint)",
               properties={
                   "positions": Field("array", items=Field("number"), unit="rad", length=6,
                                      description="Joint positions in the order of the trajectory's joint_names"),
                   "velocities": Field("array", items=Field("number"), unit="rad/s", max_items=6,
                                       description="Joint velocities (empty when the planner gives none)"),
                   "accelerations": Field("array", items=Field("number"), unit="rad/s2", max_items=6,
                                          description="Joint accelerations (empty when the planner gives none)"),
                   "effort": Field("array", items=Field("number"), max_items=6,
                                   description="Joint efforts as returned (MoveIt leaves them empty when unset)"),
                   "time_from_start": Field("object", description="Time of the point from the trajectory start",
                                            properties={"secs": Field("integer", unit="s"),
                                                        "nsecs": Field("integer", unit="ns")}),
               })


class UnityUr3PickPlacePlanner(RosDriver):
    device_id = "unity-ur3-pick-place-planner"
    device_kind = "device"
    mode = "simulated"
    risk = "R1"
    ros_version = 1
    backends = {"fake": ".fake:FakeUr3MoverService"}
    tags = ["ros", "ros1", "noetic", "moveit", "unity", "ur3", "pick-and-place", "planning", "plan-only"]
    display_name = "UR3 pick-and-place planner (Unity object pose estimation demo)"
    vendor = "unity-technologies"
    model = "ur3_moveit MoverService (MoveIt, OMPL) of the Unity robotics object-pose-estimation demo"
    facts = [
        Fact("mover.py's moveit_server initialises moveit_commander and the ur3_moveit_server node and advertises "
             "the service ur3_moveit of type MoverService with the callback plan_pick_and_place.",
             source="upstream_code", ref=_MOVER + ":137-144"),
        Fact("MoverService takes UR3MoveitJoints joints_input, a geometry_msgs/Pose pick_pose and a "
             "geometry_msgs/Pose place_pose, and returns a moveit_msgs/RobotTrajectory[] named trajectories.",
             source="upstream_code", ref=_SRV + "/MoverService.srv:1-5"),
        Fact("UR3MoveitJoints carries six float64 joint values joint_00 to joint_05 and its own pick_pose and "
             "place_pose.", source="upstream_code", ref=_MSG + "/UR3MoveitJoints.msg:1-8"),
        Fact("moveit_msgs/RobotTrajectory holds a trajectory_msgs/JointTrajectory joint_trajectory and a "
             "trajectory_msgs/MultiDOFJointTrajectory multi_dof_joint_trajectory.",
             source="upstream_code", ref=_MOVEIT_MSGS + "/msg/RobotTrajectory.msg:1-2"),
        Fact("The planner's joint names are shoulder_pan_joint, shoulder_lift_joint, elbow_joint, wrist_1_joint, "
             "wrist_2_joint and wrist_3_joint.", source="upstream_code", ref=_MOVER + ":21"),
        Fact("plan_pick_and_place converts joint_00 to joint_05 of the request from degrees to radians with "
             "math.radians to form the start configuration.", source="upstream_code", ref=_MOVER + ":66-73"),
        Fact("plan_trajectory sets the start state to the given joint angles, sets the destination pose as the pose "
             "target and returns the result of move_group.plan().", source="upstream_code", ref=_MOVER + ":35-46"),
        Fact("Under Python 3, planCompat returns element 1 of the tuple that plan() returns.",
             source="upstream_code", ref=_MOVER + ":23-29"),
        Fact("plan_pick_and_place appends five plans, pre grasp, grasp, pick up, place and post place, each starting "
             "at the last point of the previous one, clears the pose targets and returns the response.",
             source="upstream_code", ref=_MOVER + ":75-110"),
        Fact("The grasp plan targets the pick pose lowered by 0.075 in z; the comment calls it a static value "
             "coming from Unity.", source="upstream_code", ref=_MOVER + ":81-84"),
        Fact("The post-place plan targets the place pose raised by 0.075 in z.",
             source="upstream_code", ref=_MOVER + ":101-104"),
        Fact("plan_pick_and_place first calls setup_scene.", source="upstream_code", ref=_MOVER + ":61-62"),
        Fact("setup_scene assigns a new MoveGroupCommander for the group arm to the module-global move_group, "
             "creates a PlanningSceneInterface and a RobotCommander, sleeps 2 s and adds a box named table of size "
             "(1.2, 1.8, 0.01) at z -0.02+0.77 in the planning frame.",
             source="upstream_code", ref=_MOVER + ":112-126"),
        Fact("The docstring says gripper behaviour is handled outside this trajectory planning: the gripper closes "
             "after the grasp position and opens after the place position.",
             source="upstream_code", ref=_MOVER + ":49-60"),
        Fact("The SRDF defines the group arm as the chain from base_link to ee_link.",
             source="upstream_code", ref=_CONFIG + "/ur3_with_gripper.srdf:12-14"),
        Fact("The SRDF's default group state of arm sets all six arm joints to 0.",
             source="upstream_code", ref=_CONFIG + "/ur3_with_gripper.srdf:42-49"),
        Fact("pose_est.launch loads params.yaml, includes demo.launch and starts server_endpoint.py, "
             "pose_estimation_script.py and mover.py.", source="upstream_code", ref=_LAUNCH + "/pose_est.launch:1-7"),
        Fact("demo.launch loads ur3_with_gripper.urdf as robot_description, includes ros_controllers.launch, spawns "
             "arm_controller and starts move_group.launch.", source="upstream_code", ref=_LAUNCH + "/demo.launch:3-18"),
        Fact("move_group.launch defaults allow_trajectory_execution to true and fake_execution to false.",
             source="upstream_code", ref=_LAUNCH + "/move_group.launch:16-17"),
        Fact("ros_controllers.yaml lists one controller with an empty name, action_ns follow_joint_trajectory, type "
             "FollowJointTrajectory and the six arm joints.", source="upstream_code",
             ref=_CONFIG + "/ros_controllers.yaml:1-11"),
        Fact("The documentation says the launch may report that the controller spawner process died and that this is "
             "safe to ignore once the final message is Ready to plan.", source="vendor_doc", ref=_DOC + ":211"),
        Fact("server_endpoint.py starts the ROS-TCP TcpServer with three routes: a UR3Trajectory subscriber, the "
             "ur3_moveit service as ur3_moveit, and the pose_estimation_service service as pose_estimation_srv.",
             source="upstream_code", ref=_ENDPOINT + ":9-21"),
        Fact("The ROS-TCP endpoint reads its ROS_IP, ROS_TCP_PORT (default 10000), UNITY_IP and UNITY_SERVER_PORT "
             "(default 5005) parameters.", source="upstream_code",
             ref=_TCP + "/src/ros_tcp_endpoint/server.py:43-55"),
        Fact("The ROS-TCP endpoint's client thread reads one message per connection, routes it by destination name "
             "and, for a service, sends the response back on that connection and closes it.",
             source="upstream_code", ref=_TCP + "/src/ros_tcp_endpoint/client.py:142-186"),
        Fact("The ROS-TCP endpoint's RosService calls the ROS service up to three times on a ServiceException and "
             "returns None after any other exception.", source="upstream_code",
             ref=_TCP + "/src/ros_tcp_endpoint/service.py:35-61"),
        Fact("Unity's PublishJoints builds the MoverService request from the arm's current joint targets, the "
             "estimated cube position plus a pick offset and the goal position plus a place offset, and sends it to "
             "rosServiceName with TrajectoryResponse as the callback.", source="upstream_code",
             ref=_UNITY + ":236-256"),
        Fact("TrajectoryPlanner's public field rosServiceName defaults to ur3_moveit.", source="upstream_code",
             ref=_UNITY + ":32"),
        Fact("Unity's CurrentJointConfig fills joint_00 to joint_05 from the xDrive targets of the six arm "
             "articulation bodies.", source="upstream_code", ref=_UNITY + ":222-234"),
        Fact("TrajectoryPlanner's fixed values are a 0.06 s joint assignment wait, a 0.5 s pose assignment wait, a "
             "gripper angle of 14, a pick offset of 0.255 and a place offset of 0.275 in Unity's y axis.",
             source="upstream_code", ref=_UNITY + ":20-25"),
        Fact("TrajectoryResponse starts the ExecuteTrajectories coroutine when the response holds trajectories and "
             "otherwise logs an error and re-enables the buttons.", source="upstream_code", ref=_UNITY + ":258-272"),
        Fact("ExecuteTrajectories writes each point's positions, converted with Rad2Deg, as the xDrive targets of the "
             "arm joints, waits after each point, closes the gripper after the grasp plan and opens it after the "
             "place plan.", source="upstream_code", ref=_UNITY + ":288-333"),
        Fact("The pose estimation button handler captures the camera image and invokes the pose estimation "
             "service.", source="upstream_code", ref=_UNITY + ":105-120"),
        Fact("InvokePoseEstimationService builds a sensor_msgs Image with encoding RGBA from the render texture and "
             "sends a PoseEstimationServiceRequest to pose_estimation_srv.", source="upstream_code",
             ref=_UNITY + ":168-176"),
        Fact("pose_estimation_script.py advertises pose_estimation_service of type PoseEstimationService.",
             source="upstream_code", ref=_POSE + ":102-109"),
        Fact("PoseEstimationService takes a sensor_msgs/Image image and returns a geometry_msgs/Pose estimated_pose.",
             source="upstream_code", ref=_SRV + "/PoseEstimationService.srv:1-3"),
        Fact("_save_image writes each request image as a numbered PNG (Input<count>.png) under the package's images "
             "directory, creating the directory when it is missing.", source="upstream_code", ref=_POSE + ":22-41"),
        Fact("The documentation runs roslaunch ur3_moveit pose_est.launch, then Play in Unity, then the Pose "
             "Estimation button; MoveIt returns trajectories to Unity, where the poses are executed.",
             source="vendor_doc", ref=_DOC + ":197-226"),
        Fact("The documented container publishes ports 10000 and 5005.", source="vendor_doc", ref=_DOC + ":77"),
        Fact("The Docker image builds from ros:noetic-ros-base.", source="upstream_code", ref="docker/Dockerfile:1"),
        Fact("The Docker image installs ros-noetic-moveit and ros-noetic-rosbridge-suite among its apt packages.",
             source="upstream_code", ref="docker/Dockerfile:5"),
        Fact("The Docker image copies the moveit_msgs, robotiq, ros_tcp_endpoint, universal_robot and ur3_moveit "
             "packages into the catkin workspace.", source="upstream_code", ref="docker/Dockerfile:14-18"),
        Fact("The repository is licensed under the Apache License, Version 2.0.", source="vendor_doc",
             ref="LICENSE:1-2"),
    ]
    safe_state = (
        "Plan-only package: it sends nothing that executes a plan or commands the Unity arm, its gripper or any "
        "controller. An e-stop latches this endpoint in software and refuses further planning requests; a planning "
        "request already sent is not awaited. It does not reach a pick-and-place that Unity started from its own "
        "Pose Estimation button: that runs in Unity's coroutine and stops only in the Unity editor."
    )
    fidelity = {
        "engine": "analytic:ROS recording fake of the ur3_moveit MoverService (no MoveIt, OMPL or Unity)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "The fake answers a fixed placeholder plan shape; MoveIt's OMPL planning in a live deployment "
                     "is randomized and its plans differ between calls",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "PLAN ONLY: the package never executes a plan",
            "the fake's trajectories are placeholders",
            "in the upstream pipeline only Unity executes trajectories, and only those answering its own request, so "
            "a receipt never shows motion of the simulated arm",
            "the fake's plans are straight joint-space segments through invented configurations; it models only the "
            "response shape, the five-plan order, the chaining of each plan's "
            "start to the previous plan's end, the start configuration taken from the request in degrees and "
            "returned in radians, and the service failures; it runs no MoveIt, OMPL, collision checking or "
            "time parameterization",
            "a live planning call first adds the same table box to MoveIt's planning scene and sleeps 2 s "
            "(mover.py:112-126); a plan that MoveIt cannot find makes the callback raise and the call fail",
            "concurrent planning calls (from Unity or another client) share the node's module-global "
            "MoveGroupCommander, which every call replaces (mover.py:112-116), so their start states and targets "
            "can interleave, and Unity executes whatever plan answers its own request: a call that overlaps "
            "Unity's own planning can change what the simulated arm does; the package serialises only its own "
            "calls and cannot see Unity's",
            "every input bound is operator_required (the clone states the UR3 joint limits only in radians and no "
            "workspace or quaternion bound): without the operator's overlay every call is refused LIMITS_UNSET; "
            "within it, a configuration MoveIt cannot reach still fails the plan, which is then a failed receipt",
            "the pose estimation service, the ROS-TCP endpoint, the Unity scene with its arm, gripper, cube and "
            "camera, and the vendored universal_robot and robotiq driver stacks are NOT COVERED",
            "the operator runs rosbridge (rosbridge_server's websocket, installed by the upstream image) next to "
            "pose_est.launch and publishes its port; the upstream documents only ports 10000 and 5005",
        ],
    }
    commands = {"x-cap.unity-technologies.pick_place_plan.v1": _PLAN}

    def make_bridge(self, native):
        return _CheckedPlan(super().make_bridge(native))
    actions = {
        "x-cap.unity-technologies.pick_place_plan.v1": Action(
            name="plan_pick_and_place",
            verb="invoke",
            exclusive=True,
            description=(
                "Plan (never execute) the five UR3 pick-and-place trajectories; executed is false. A command: it "
                "changes the node's shared planner, so never call while Unity plans; a zero quaternion is refused."
            ),
            input={
                "start_joints_deg": Field(
                    "array", items=Field("number"), unit="deg", length=6, limit=_ANGLE_LIMIT,
                    description="Start angles of the six arm joints, in planner order"),
                "pick_position": Field("array", items=Field("number"), unit="m", length=3, limit=_POSITION_LIMIT,
                                       description="Pick x, y, z in the planning frame"),
                "pick_orientation": Field("array", items=Field("number"), unit="1", length=4,
                                          limit=_ORIENTATION_LIMIT,
                                          description="Pick quaternion x, y, z, w"),
                "place_position": Field("array", items=Field("number"), unit="m", length=3, limit=_POSITION_LIMIT,
                                        description="Place x, y, z in the planning frame"),
                "place_orientation": Field("array", items=Field("number"), unit="1", length=4,
                                           limit=_ORIENTATION_LIMIT,
                                           description="Place quaternion x, y, z, w"),
            },
            output={
                "joint_names": Field(
                    "array", length=5,
                    items=Field("array", length=6, items=Field("string", enum=list(JOINTS))),
                    description="Each plan's joint names, in plan order (pre grasp, grasp, pick up, place, post place)"),
                "points": Field(
                    "array", length=5, items=Field("array", min_items=1, items=_POINT),
                    description="Each plan's trajectory points, in plan order; a plan starts where the previous ends"),
                "executed": Field("boolean", enum=[False],
                                  description="Always false: the package plans only and executes nothing"),
            },
        ),
    }
