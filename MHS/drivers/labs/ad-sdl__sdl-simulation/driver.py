"""OpenMHS rosbridge driver for gh.ad-sdl/sdl-simulation (ROS 1 / Gazebo / MoveIt).

The pinned repository is a ROS Melodic simulation stack: a UR5e arm with a
Robotiq 2F140 gripper on a MiR base, spawned into Gazebo and planned through
MoveIt.  The executable wire surface is a ROS 1 topic graph:

* ``/ur_arm/moveit/goal_pose`` carries ``geometry_msgs/Pose`` arm goals to the
  clone's ``sdl_moveit_node.py`` bridge node;
* ``/move_base_simple/goal`` carries ``geometry_msgs/PoseStamped`` navigation
  goals toward the external MIR/move_base stack the launch includes;
* ``/left_gripper_position_controller/command`` and
  ``/right_gripper_position_controller/command`` carry ``std_msgs/Float64``
  gripper position commands;
* ``/move_group/status`` and ``/move_base/status`` publish
  ``actionlib_msgs/GoalStatusArray``.  They stay explicit reads.  They are not
  the device resource, and this package does not claim they go silent while
  the world is paused.

The e-stop is the Gazebo world pause of the simulator's own repositories,
cited as reviewed companion sources fetched at pinned commits (user decision
of 2026-11-05; ``task.json`` ``companions`` with ``lock``).  A reviewed
``LOCK.json`` edit adds ``gh.ad-sdl/sdl-simulation`` to ``needed_by`` of the
two Melodic clones already on disk.  No network fetch is done.
gazebo_ros 2.8.7 (ROS 1 Melodic) ``/gazebo/pause_physics`` is confirmed by
reading ``/gazebo/get_physics_properties`` back until ``pause`` is true.
Gazebo 9.19.0 ``World::Step`` is cited for what a paused world does not
advance.  This is the paused flag, not a measured standstill of the arm, the
base or the grippers.  The clone does not load a gazebo_ros_control plugin
(``gazebo_controller.yaml`` only names that key for PID gains), so this
package does not claim that plugin or the actionlib status timers stop.

No unpause is offered.  ``go_to_pose_goal`` blocks in ``group.go(wait=True)``
and calls ``group.stop()`` only after that returns; the stop is not a ROS
endpoint (sdl_moveit_node.py:114-119).  The package also cannot clear the
navigation goal or the gripper position publications.  After
``mhs.safety.reset`` the latch releases and the world stays paused.  Recovery
stays paused: those pending requests cannot be shown to have been discarded,
so the affected simulation stack is restarted before any manual resume.

The default launch (empty ``tf_prefix``) takes the no-namespace branch, which
starts the world paused.  The namespaced branch passes ``paused=false`` and
is not the launch this package serves.  The Gazebo include sits outside the
namespace group in both branches, so the service names stay ``/gazebo/...``.

Every publication receipt reports the values it handed to rosbridge.  The
fake is ROS-free.  No ROS graph, Gazebo, MoveIt or hardware is contacted.
Evidence is ``contract_checked`` only.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# -- Companion sources (task.json companions; user decision 2026-11-05) -----------------------------------------
#: gazebo_ros 2.8.7 (ROS 1 Melodic) at 0667c5e5, fetched under work/companions: the pause and its read-back.
_API = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
_LAUNCH = "companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch"
#: Gazebo classic 9.19.0 at e4400ae7, fetched under work/companions: the world step the pause gates.
_WORLD = "companion:gazebo_classic/gazebo/physics/World.cc"

#: The e-stop: pause_physics (std_srvs/Empty) sets the world's paused flag.
_PAUSE = {
    "service": "/gazebo/pause_physics",
    "type": "std_srvs/Empty",
    "source_name": "pause_physics",
    "source_ref": _API + ":462-468",
    "type_ref": _API + ":464",
    "state_ref": _API + ":1662-1666",
    "description": "Pause the Gazebo world (gazebo_ros pause_physics: World::SetPaused(true))",
    "request": {},
    "success": {"path": "$", "equals": {}},
    "timeout_ms": 500,
}
#: The read-back that confirms it: get_physics_properties reports the paused flag (res.pause = IsPaused()).
_READBACK = {
    "service": "/gazebo/get_physics_properties",
    "type": "gazebo_msgs/GetPhysicsProperties",
    "source_name": "get_physics_properties",
    "source_ref": _API + ":364-370",
    "type_ref": _API + ":366",
    "state_ref": _API + ":1426",
    "description": "Read the world's paused flag back; the e-stop is confirmed only when pause is true",
    "request": {},
    "success": {"path": "pause", "equals": True},
    "timeout_ms": 500,
}

#: Facts about the companions, each one clause on its cited range.  No gazebo_ros_control fact: this clone does
#: not load that plugin.
_COMPANION_FACTS = [
    Fact("The gazebo_ros gzserver wrapper adds libgazebo_ros_api_plugin to the server's plugins unless the "
         "arguments already name it.", source="upstream_code",
         ref="companion:gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24"),
    Fact("empty_world.launch starts the Gazebo server as the node named gazebo of package gazebo_ros, with the "
         "physics engine argument -e $(arg physics).", source="upstream_code", ref=_LAUNCH + ":46-48"),
    Fact("empty_world.launch defaults its physics argument to ode.", source="upstream_code", ref=_LAUNCH + ":15"),
    Fact("empty_world.launch defaults its gui argument to true.", source="upstream_code", ref=_LAUNCH + ":8"),
    Fact("When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient.",
         source="upstream_code", ref=_LAUNCH + ":51-54"),
    Fact("When its paused argument is true, empty_world.launch sets command_arg1 to -u.",
         source="upstream_code", ref=_LAUNCH + ":30-31"),
    Fact("The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet.",
         source="upstream_code", ref=_API + ":127-128"),
    Fact("The API plugin creates its node handle in the private namespace ~ and advertises its topics and services "
         "there.", source="upstream_code", ref=_API + ":147"),
    Fact("The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback "
         "queue gazebo_queue_.", source="upstream_code", ref=_API + ":462-468"),
    Fact("The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties "
         "type on gazebo_queue_.", source="upstream_code", ref=_API + ":364-370"),
    Fact("gazeboQueueThread serves gazebo_queue_ in a loop with a 0.001 s wall-clock wait while the node handle is "
         "ok.", source="upstream_code", ref=_API + ":235-242"),
    Fact("pausePhysics calls world_->SetPaused(true) and returns true.", source="upstream_code",
         ref=_API + ":1662-1666"),
    Fact("unpausePhysics calls world_->SetPaused(false) and returns true.", source="upstream_code",
         ref=_API + ":1668-1672"),
    Fact("getPhysicsProperties sets res.pause to world_->IsPaused().", source="upstream_code", ref=_API + ":1426"),
    Fact("getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it "
         "sets success false and returns false.", source="upstream_code", ref=_API + ":1433-1465"),
    Fact("The GetPhysicsProperties response field pause is true if the physics engine is paused.",
         source="upstream_code", ref="companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4"),
    Fact("Among the world-update begin hooks that its comment says apply forces and publish sim time on /clock, the "
         "API plugin connects publishSimTime.", source="upstream_code", ref=_API + ":224-227"),
    Fact("World::Step advances simulation time and calls Update only when the world is not paused, a step increment "
         "is pending or a reset is due; otherwise it adds the step to the pause time.", source="upstream_code",
         ref=_WORLD + ":691-710"),
    Fact("World::Step holds worldUpdateMutex while it steps the world.", source="upstream_code",
         ref=_WORLD + ":683"),
    Fact("World::SetPaused returns when the paused flag already equals its argument and otherwise stores the flag "
         "under worldUpdateMutex.", source="upstream_code", ref=_WORLD + ":1428-1436"),
    Fact("World::IsPaused returns the stored paused flag.", source="upstream_code", ref=_WORLD + ":1422-1425"),
    Fact("World::Update fires the worldUpdateBegin event and then updates every model.", source="upstream_code",
         ref=_WORLD + ":776-782"),
    Fact("World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed "
         "on every step, paused or not.", source="upstream_code", ref=_WORLD + ":691-718"),
    Fact("A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the "
         "number of steps to run while paused.", source="upstream_code", ref=_WORLD + ":1462-1477"),
]

#: The arm bridge node subscribes to the absolute goal-pose topic with the
#: fully qualified geometry_msgs.msg.Pose type.
_ARM_TOPIC = "/ur_arm/moveit/goal_pose"
_ARM_REF = "sdl_gazebo/src/sdl_moveit_node.py:136"

#: The callback sets the pose target, blocks in group.go(wait=True), calls the
#: local group.stop() and clears the target.  This is the clone's only stop
#: call and it is not a ROS service or action.
_ARM_CALLBACK_REF = "sdl_gazebo/src/sdl_moveit_node.py:114-122"
_ARM_NODE_LAUNCH_REF = "sdl_gazebo/launch/sdl_nav_moveit_combined.launch:32"

#: The navigation and gripper publishers are created in the demo node.
_BASE_TOPIC = "/move_base_simple/goal"
_BASE_REF = "sdl_gazebo/python-nodes/can_demo_no_camera.py:18"
_LEFT_TOPIC = "/left_gripper_position_controller/command"
_LEFT_REF = "sdl_gazebo/python-nodes/can_demo_no_camera.py:20"
_RIGHT_TOPIC = "/right_gripper_position_controller/command"
_RIGHT_REF = "sdl_gazebo/python-nodes/can_demo_no_camera.py:21"

#: Message-type imports that prove the declared ROS types.
_GEOMETRY_IMPORT_REF = "sdl_gazebo/python-nodes/can_demo_no_camera.py:1"
_FLOAT64_IMPORT_REF = "sdl_gazebo/python-nodes/can_demo_no_camera.py:7"
_ACTIONLIB_IMPORT_REF = "sdl_gazebo/python-nodes/can_demo.py:2"

#: The demo subscribes to the arm action status with GoalStatusArray.
_ARM_STATUS_TOPIC = "/move_group/status"
_ARM_STATUS_REF = "sdl_gazebo/python-nodes/can_demo.py:20"

#: The navigation demo subscribes to the move_base action status.  The name is
#: relative in the node (no namespace) and resolves to the absolute topic.
_NAV_STATUS_TOPIC = "/move_base/status"
_NAV_STATUS_SOURCE_NAME = "move_base/status"
_NAV_STATUS_REF = "sdl_gazebo/python-nodes/can_demo_no_camera.py:29"

#: README statements that describe the same control surface.
_README_ARM_REF = "README.md:79-91"
_README_BASE_REF = "README.md:99"
_README_GRIPPER_REF = "README.md:107"
_README_PAUSED_REF = "README.md:57-62"

#: The launch file leaves the empty-namespace Gazebo world paused. README.md:57-62
#: tells the operator to press play at startup, before planning. That startup
#: instruction is not the e-stop recovery.
_WORLD_PAUSED_REF = "sdl_gazebo/launch/lab_world.launch:44-55"

#: The MoveIt controller configuration names the arm controller and the
#: short FollowJointTrajectory type, not a fully qualified ROS action type.
_CONTROLLERS_REF = "sdl_moveit_config/config/ros_controllers.yaml:29-40"
_MOVE_GROUP_LAUNCH_REF = "sdl_moveit_config/launch/move_group.launch:67-68"

#: The repository has no root licence file; these package manifests disagree.
_LICENSE_BSD_REF = "sdl_moveit_config/package.xml:11"
_LICENSE_TODO_REF = "sdl_gazebo/package.xml:16"

_ARM_ID = "x-cap.ad-sdl.arm_pose_goal.v1"
_BASE_ID = "x-cap.ad-sdl.base_pose_goal.v1"
_LEFT_ID = "x-cap.ad-sdl.left_gripper_position.v1"
_RIGHT_ID = "x-cap.ad-sdl.right_gripper_position.v1"

_PUBLISH_OUTPUT = {
    "published": Field("boolean", description="True when rosbridge accepted the publication"),
    "confirmed": Field("boolean", description="Always false: a topic publication has no execution acknowledgement"),
}
_POSE_SENT = {
    "x": Field("number", unit="m", description="Transmitted x"),
    "y": Field("number", unit="m", description="Transmitted y"),
    "z": Field("number", unit="m", description="Transmitted z"),
    "qx": Field("number", unit="1", description="Transmitted quaternion x"),
    "qy": Field("number", unit="1", description="Transmitted quaternion y"),
    "qz": Field("number", unit="1", description="Transmitted quaternion z"),
    "qw": Field("number", unit="1", description="Transmitted quaternion w"),
}
_ARM_OUTPUT = {
    **_PUBLISH_OUTPUT,
    "sent": Field(
        "object",
        description="The pose values handed to rosbridge; a transmitted request, not a measured pose",
        properties=dict(_POSE_SENT),
    ),
}
_BASE_OUTPUT = {
    **_PUBLISH_OUTPUT,
    "sent": Field(
        "object",
        description="The PoseStamped values handed to rosbridge; a transmitted request, not a measured pose",
        properties={
            "frame_id": Field("string", description="Transmitted header frame id"),
            **_POSE_SENT,
        },
    ),
}
_GRIPPER_OUTPUT = {
    **_PUBLISH_OUTPUT,
    "sent": Field(
        "object",
        description="The position handed to rosbridge; a transmitted request, not a measured joint position",
        properties={
            "position": Field("number", unit="1", description="Transmitted position command"),
        },
    ),
}

_STATUS_STAMP = Field(
    "object",
    description="actionlib time stamp of a goal id",
    properties={
        "secs": Field("integer", unit="s", description="Whole seconds"),
        "nsecs": Field("integer", unit="ns", description="Nanoseconds within the second"),
    },
)
_STATUS_GOAL_ID = Field(
    "object",
    description="actionlib goal identifier",
    properties={
        "id": Field("string", description="Goal id string"),
        "stamp": _STATUS_STAMP,
    },
)
_STATUS_ENTRY = Field(
    "object",
    description="One actionlib_msgs/GoalStatus entry",
    properties={
        "goal_id": _STATUS_GOAL_ID,
        "status": Field("integer", description="actionlib status code"),
        "text": Field("string", description="Status text supplied by the action server"),
    },
)
_STATUS_OUTPUT = {
    "statuses": Field("array", description="GoalStatus entries from the observed status_list",
                      items=_STATUS_ENTRY),
}

#: Numeric fields of each publication, echoed on the receipt.  frame_id stays a string.
_SENT_KEYS = {
    _ARM_ID: ("x", "y", "z", "qx", "qy", "qz", "qw"),
    _BASE_ID: ("frame_id", "x", "y", "z", "qx", "qy", "qz", "qw"),
    _LEFT_ID: ("position",),
    _RIGHT_ID: ("position",),
}
_PUBLISH_RESULT = {"map": {"published": "published", "confirmed": "confirmed"}}


class _SentReceipt:
    """The receipt of a command publication also reports the values it handed to rosbridge.

    The device resource reads no topic, so the receipt is where a caller sees what a publication sent.  It is the
    transmitted request, not a measurement.  Status reads, the e-stop and the reset go to the SDK bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        keys = _SENT_KEYS.get(capability_id)
        if keys is None:
            return output
        body = dict(args or {})
        sent = {}
        for key in keys:
            value = body[key]
            sent[key] = value if key == "frame_id" else float(value)
        output = dict(output)
        output["sent"] = sent
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _arm_limit(axis: str) -> Limit:
    return Limit.operator_required(
        f"the clone states no reachable {axis} coordinate envelope for {_ARM_TOPIC}; "
        "the operator supplies the deployment workspace bound")


def _arm_quaternion_limit(component: str) -> Limit:
    return Limit.operator_required(
        f"the clone states no orientation envelope for {_ARM_TOPIC}; "
        f"the operator supplies the {component} quaternion bound")


def _base_limit(field: str) -> Limit:
    return Limit.operator_required(
        f"the clone states no map-frame navigation goal envelope for {_BASE_TOPIC}; "
        f"the operator supplies the {field} bound")


def _base_quaternion_limit(component: str) -> Limit:
    return Limit.operator_required(
        f"the clone states no orientation envelope for {_BASE_TOPIC}; "
        f"the operator supplies the {component} quaternion bound")


def _gripper_limit(side: str) -> Limit:
    return Limit.operator_required(
        f"the clone states no calibrated {side} gripper position range; the operator supplies the stroke "
        "envelope for the command topic")


#: The pose fields are all operator_required: the README gives one example pose,
#: not a workspace bound, and the arm goal is a Cartesian target.
_ARM_ARGS = {
    "position.x": {"from": "input.x"},
    "position.y": {"from": "input.y"},
    "position.z": {"from": "input.z"},
    "orientation.x": {"from": "input.qx"},
    "orientation.y": {"from": "input.qy"},
    "orientation.z": {"from": "input.qz"},
    "orientation.w": {"from": "input.qw"},
}
_ARM_INPUT = {
    "x": Field("number", unit="m", description="Goal x in the arm planning frame", limit=_arm_limit("x")),
    "y": Field("number", unit="m", description="Goal y in the arm planning frame", limit=_arm_limit("y")),
    "z": Field("number", unit="m", description="Goal z in the arm planning frame", limit=_arm_limit("z")),
    "qx": Field("number", unit="1", description="Goal quaternion x", limit=_arm_quaternion_limit("x")),
    "qy": Field("number", unit="1", description="Goal quaternion y", limit=_arm_quaternion_limit("y")),
    "qz": Field("number", unit="1", description="Goal quaternion z", limit=_arm_quaternion_limit("z")),
    "qw": Field("number", unit="1", description="Goal quaternion w", limit=_arm_quaternion_limit("w")),
}

_BASE_ARGS = {
    "header.frame_id": {"from": "input.frame_id"},
    "pose.position.x": {"from": "input.x"},
    "pose.position.y": {"from": "input.y"},
    "pose.position.z": {"from": "input.z"},
    "pose.orientation.x": {"from": "input.qx"},
    "pose.orientation.y": {"from": "input.qy"},
    "pose.orientation.z": {"from": "input.qz"},
    "pose.orientation.w": {"from": "input.qw"},
}
_BASE_INPUT = {
    "frame_id": Field("string", description="Frame id carried by the PoseStamped header"),
    "x": Field("number", unit="m", description="Goal x in the map frame", limit=_base_limit("x")),
    "y": Field("number", unit="m", description="Goal y in the map frame", limit=_base_limit("y")),
    "z": Field("number", unit="m", description="Goal z in the map frame", limit=_base_limit("z")),
    "qx": Field("number", unit="1", description="Goal quaternion x", limit=_base_quaternion_limit("x")),
    "qy": Field("number", unit="1", description="Goal quaternion y", limit=_base_quaternion_limit("y")),
    "qz": Field("number", unit="1", description="Goal quaternion z", limit=_base_quaternion_limit("z")),
    "qw": Field("number", unit="1", description="Goal quaternion w", limit=_base_quaternion_limit("w")),
}

_LEFT_GRIPPER_INPUT = {
    "position": Field("number", unit="1", description="Joint position command for the left gripper controller",
                      limit=_gripper_limit("left")),
}
_RIGHT_GRIPPER_INPUT = {
    "position": Field("number", unit="1", description="Joint position command for the right gripper controller",
                      limit=_gripper_limit("right")),
}


class SdlSimulation(RosDriver):
    device_id = "sdl-simulation"
    device_kind = "robot.arm"
    mode = "simulated"
    # The clone controls a UR5e arm and a MiR mobile base in simulation; the
    # safety specification puts a robot arm and a mobile base at least at R2.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeSdlSimulation"}
    tags = ["ros", "ros1", "gazebo", "moveit", "simulation", "ur5e", "mobile-manipulator", "arm", "gripper"]
    display_name = "SDL Gazebo mobile manipulator (UR5e arm)"
    vendor = "AD-SDL (Argonne National Laboratory / University of Chicago)"
    model = "UR5e arm, Robotiq 2F140 gripper and MiR base in Gazebo"
    facts = [
        Fact("The README describes the repository as code for the SDL simulation project at Argonne National "
             "Laboratory/University of Chicago.", source="vendor_doc", ref="README.md:3"),
        Fact("The README says ROS Melodic is assumed installed.", source="vendor_doc", ref="README.md:6"),
        Fact("The README publishes geometry_msgs/Pose to /ur_arm/moveit/goal_pose to control the arm.",
             source="vendor_doc", ref=_README_ARM_REF),
        Fact("sdl_moveit_node.py subscribes to /ur_arm/moveit/goal_pose with the fully qualified "
             "geometry_msgs.msg.Pose type.", source="upstream_code", ref=_ARM_REF),
        Fact("go_to_pose_goal sets the pose target, blocks in self.group.go(wait=True), calls self.group.stop(), "
             "and clears the pose targets; the stop call is inside the callback after motion returns.",
             source="upstream_code", ref=_ARM_CALLBACK_REF),
        Fact("sdl_nav_moveit_combined.launch starts the ur_python_planner node from "
             "sdl_gazebo/src/sdl_moveit_node.py.", source="upstream_code", ref=_ARM_NODE_LAUNCH_REF),
        Fact("sdl_nav_moveit_combined.launch defaults tf_prefix to an empty string and includes lab_world.launch.",
             source="upstream_code", ref="sdl_gazebo/launch/sdl_nav_moveit_combined.launch:2-9"),
        Fact("The README tells the operator to press the play button in Gazebo after the paused launch.",
             source="vendor_doc", ref=_README_PAUSED_REF),
        Fact("lab_world.launch passes paused=true to the empty-world launch when no namespace is configured.",
             source="upstream_code", ref=_WORLD_PAUSED_REF),
        Fact("The branch that runs when namespace is not empty includes empty_world.launch with paused=false.",
             source="upstream_code", ref="sdl_gazebo/launch/lab_world.launch:14-23"),
        Fact("lab_ar.world sets the default physics element type to ode.", source="upstream_code",
             ref="sdl_gazebo/world/lab_ar.world:67"),
        Fact("The demo node creates a PoseStamped publisher on move_base_simple/goal, a Pose publisher on "
             "/ur_arm/moveit/goal_pose, and Float64 publishers on the left and right gripper command topics.",
             source="upstream_code", ref="sdl_gazebo/python-nodes/can_demo_no_camera.py:18-21"),
        Fact("can_demo.py publishes PoseStamped on move_base_simple/goal, Pose on /ur_arm/moveit/goal_pose and "
             "Float64 on both gripper command topics, and subscribes to /move_group/status.",
             source="upstream_code", ref="sdl_gazebo/python-nodes/can_demo.py:18-22"),
        Fact("The README says the MIR is navigated by publishing to /move_base_simple/goal.",
             source="vendor_doc", ref=_README_BASE_REF),
        Fact("sdl_nav_moveit_combined.launch includes mir_navigation's move_base.xml.",
             source="upstream_code", ref="sdl_gazebo/launch/sdl_nav_moveit_combined.launch:36-38"),
        Fact("The README says the 2F140 gripper is controlled by publishing to "
             "/left_gripper_position_controller/command and /right_gripper_position_controller/command.",
             source="vendor_doc", ref=_README_GRIPPER_REF),
        Fact("gripper_control.yaml declares left_gripper_position_controller and right_gripper_position_controller "
             "as position_controllers/JointPositionController for finger_joint and right_outer_knuckle_joint.",
             source="upstream_code", ref="sdl_gazebo/config/gripper_control.yaml:1-6"),
        Fact("ros_controllers.launch loads gazebo_controller.yaml and gripper_control.yaml with rosparam and "
             "spawns left_gripper_position_controller and right_gripper_position_controller.",
             source="upstream_code", ref="sdl_moveit_config/launch/ros_controllers.launch:6-11"),
        Fact("gazebo_controller.yaml names gazebo_ros_control as the key of a pid_gains map.",
             source="upstream_code", ref="sdl_moveit_config/config/gazebo_controller.yaml:1-2"),
        Fact("can_demo_no_camera.py imports PoseStamped and Pose from geometry_msgs.msg and Float64 from "
             "std_msgs.msg.", source="upstream_code", ref="sdl_gazebo/python-nodes/can_demo_no_camera.py:1-7"),
        Fact("can_demo.py subscribes to /move_group/status with actionlib_msgs.msg.GoalStatusArray.",
             source="upstream_code", ref=_ARM_STATUS_REF),
        Fact("can_demo_no_camera.py subscribes to move_base/status with "
             "actionlib_msgs.msg.GoalStatusArray.", source="upstream_code", ref=_NAV_STATUS_REF),
        Fact("The navigation demo's lock_control sends the arm, gripper and drive-away commands when "
             "status_list is empty or its first entry's text is 'Goal reached.', and otherwise sets locked.",
             source="upstream_code", ref="sdl_gazebo/python-nodes/can_demo_no_camera.py:32-45"),
        Fact("Idle.execute logs Executing state BAR and returns outcome2.", source="upstream_code",
             ref="sdl_gazebo/python-nodes/table_1_smach.py:8-10"),
        Fact("ros_controllers.yaml declares ur_arm_controller with action_ns follow_joint_trajectory and "
             "the short type FollowJointTrajectory, but no fully qualified ROS action type.",
             source="upstream_code", ref=_CONTROLLERS_REF),
        Fact("move_group.launch starts the moveit_ros_move_group move_group node, commented as the "
             "move_group node/action server.", source="upstream_code", ref=_MOVE_GROUP_LAUNCH_REF),
        Fact("sdl_moveit_config/package.xml declares the BSD licence.", source="upstream_code",
             ref=_LICENSE_BSD_REF),
        Fact("sdl_gazebo/package.xml still carries the licence placeholder TODO.", source="upstream_code",
             ref=_LICENSE_TODO_REF),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "The Gazebo world stays paused and get_physics_properties reads pause true: World::Step does not advance "
        "simulation time or call Update while the flag is set, unless a step is pending or a reset is due; this "
        "is the paused flag, not a measured standstill, and no unpause is offered, so recovery stays paused and "
        "the simulation stack is restarted before any manual resume, because the pending MoveIt goal, the "
        "navigation goal and the gripper publications cannot be shown to have been discarded."
    )
    #: The fake is a ROS-free, event-driven contract stand-in; it runs no Gazebo
    #: physics, MoveIt planner, controller or wall-clock loop.
    fidelity = {
        "engine": "analytic:ROS publication fake (no Gazebo or MoveIt physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven fake with a placeholder paused flag, placeholder status samples and recorded "
                     "publications; no physics step, controller, wall-clock pacing or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "external",
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free transport: it records publications, answers the two companion Gazebo services "
            "and answers status subscriptions with placeholder GoalStatusArray samples, including while its paused "
            "flag is set; it runs no Gazebo world, MoveIt planner, ros_control controller, MiR navigation stack or "
            "ROS graph",
            "the arm goal topic carries a target pose only; the clone publishes no completion, arrival or stopped "
            "acknowledgement for it, and the receipt reports the values handed to rosbridge with confirmed false",
            "the mobile-base goal is an unacknowledged PoseStamped publication; move_base status is an explicit "
            "read and is not correlated to a publication by this driver",
            "the two gripper command topics are Float64 publications; gripper_control.yaml names "
            "position_controllers/JointPositionController for finger_joint and right_outer_knuckle_joint, and the "
            "controller source is not in this clone, so the package does not claim that controller stores or "
            "resumes a command",
            "the stop is the companion gazebo_ros world pause: the fake keeps a paused flag that "
            "/gazebo/pause_physics sets and /gazebo/get_physics_properties reports; it runs no Gazebo World::Step, "
            "and the flag is not a measured standstill of the arm, base or grippers",
            "no unpause is offered: this package cannot clear the MoveIt goal group.go blocks on "
            "(sdl_moveit_node.py:114-119; group.stop runs only after go returns and is not a ROS endpoint), the "
            "navigation goal the launch hands to external mir_navigation move_base.xml, or the gripper position "
            "publications; mhs.safety.reset releases the latch only and the fake paused flag stays true; recovery "
            "stays paused, and the affected simulation stack is restarted before any manual resume, because those "
            "pending requests cannot be shown to have been discarded",
            "the fake starts unpaused so a stop demonstrably sets the flag; the default launch does not: "
            "sdl_nav_moveit_combined.launch defaults tf_prefix to empty and lab_world.launch then passes "
            "paused=true (lines 44-55); README.md:57-62 tells the operator to press play at startup, which is "
            "not the e-stop recovery; a read-back can already be true at startup",
            "the namespaced branch of lab_world.launch (lines 14-23) passes paused=false and is not the launch "
            "this package serves; the Gazebo include sits outside the ns group in both branches, so the service "
            "names stay /gazebo/pause_physics and /gazebo/get_physics_properties",
            "lab_ar.world sets physics type ode and empty_world.launch defaults physics to ode; with another "
            "engine get_physics_properties returns false and the e-stop stays unconfirmed with the latch held",
            "a GUI step or a WorldControl multi_step can advance a paused world (World.cc:1462-1477), and "
            "empty_world.launch defaults gui to true; MHS does not watch the flag after the e-stop",
            "the actionlib status topics stay explicit reads and the fake still answers them while paused; this "
            "package does not claim they go silent, and they are not the device resource, so a reset does not "
            "wait on them",
            "can_demo.py:18-22 and can_demo_no_camera.py:18-21 publish the same four command topics, so those "
            "demo nodes compete with an MHS client; table_1_smach.py Idle.execute only logs and returns an "
            "outcome (lines 8-10), and this package does not claim the smach nodes publish those topics",
            "gazebo_controller.yaml:1-2 names gazebo_ros_control as a pid_gains key, and ros_controllers.launch:6 "
            "loads that file with rosparam; the only plugin filename this clone's URDF names is "
            "libgazebo_ros_openni_kinect.so (sdl_robot_description/urdf/camera.urdf.xacro:47); UR and MiR "
            "descriptions are external, and this package does not claim those controllers stop",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.8.7 (Melodic) and 9.19.0 releases the "
            "companion citations name; rosbridge cannot read their versions",
            "NOT COVERED: the Kinect camera topics (/camera/color/image_raw, /camera/depth/image_raw, "
            "/camera/depth/points), AR tag poses on /ar_pose_marker, /tf, joint states, MoveIt planning and every "
            "hardware path",
        ],
    }

    # The device resource reads no topic.  The actionlib status topics stay explicit reads below.  Moving them
    # off the resource means a reset does not wait on them.  It is not a claim that they go silent while paused.
    commands = {
        _ARM_ID: {
            "topic": _ARM_TOPIC,
            "type": "geometry_msgs/Pose",
            "operation": "publish",
            "source_ref": _ARM_REF,
            # The message defaults are placeholders; every field is overlaid by args.
            "message": {
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},          # placeholder
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
            },
            "args": _ARM_ARGS,
            "result": _PUBLISH_RESULT,
        },
        _BASE_ID: {
            "topic": _BASE_TOPIC,
            "type": "geometry_msgs/PoseStamped",
            "operation": "publish",
            "source_ref": _BASE_REF,
            "source_name": "move_base_simple/goal",
            "type_ref": _GEOMETRY_IMPORT_REF,
            # The message defaults are placeholders; every field is overlaid by args.
            "message": {
                "header": {"frame_id": "map"},                       # placeholder
                "pose": {
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},      # placeholder
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                },
            },
            "args": _BASE_ARGS,
            "result": _PUBLISH_RESULT,
        },
        _LEFT_ID: {
            "topic": _LEFT_TOPIC,
            "type": "std_msgs/Float64",
            "operation": "publish",
            "source_ref": _LEFT_REF,
            "type_ref": _FLOAT64_IMPORT_REF,
            "message": {"data": 0.0},                                 # placeholder
            "args": {"data": {"from": "input.position"}},
            "result": _PUBLISH_RESULT,
        },
        _RIGHT_ID: {
            "topic": _RIGHT_TOPIC,
            "type": "std_msgs/Float64",
            "operation": "publish",
            "source_ref": _RIGHT_REF,
            "type_ref": _FLOAT64_IMPORT_REF,
            "message": {"data": 0.0},                                 # placeholder
            "args": {"data": {"from": "input.position"}},
            "result": _PUBLISH_RESULT,
        },
        "x-cap.ad-sdl.arm_status.v1": {
            "topic": _ARM_STATUS_TOPIC,
            "type": "actionlib_msgs/GoalStatusArray",
            "operation": "subscribe",
            "source_ref": _ARM_STATUS_REF,
            "type_ref": _ACTIONLIB_IMPORT_REF,
            "path": "$",
            "result": {"map": {"statuses": "output.status_list"}},
        },
        "x-cap.ad-sdl.nav_status.v1": {
            "topic": _NAV_STATUS_TOPIC,
            "type": "actionlib_msgs/GoalStatusArray",
            "operation": "subscribe",
            "source_ref": _NAV_STATUS_REF,
            "source_name": _NAV_STATUS_SOURCE_NAME,
            "type_ref": _ACTIONLIB_IMPORT_REF,
            "path": "$",
            "result": {"map": {"statuses": "output.status_list"}},
        },
    }
    actions = {
        _ARM_ID: Action(
            name="arm_pose_goal",
            description="Publish one geometry_msgs/Pose arm target; the receipt reports the values sent and no "
                        "execution acknowledgement is available",
            input=_ARM_INPUT,
            output=_ARM_OUTPUT,
        ),
        _BASE_ID: Action(
            name="base_pose_goal",
            description="Publish one PoseStamped navigation goal; the receipt reports the values sent and no "
                        "execution acknowledgement is available",
            input=_BASE_INPUT,
            output=_BASE_OUTPUT,
        ),
        _LEFT_ID: Action(
            name="left_gripper_position",
            description="Publish one Float64 position to the left gripper controller; the receipt reports the "
                        "value sent",
            input=_LEFT_GRIPPER_INPUT,
            output=_GRIPPER_OUTPUT,
        ),
        _RIGHT_ID: Action(
            name="right_gripper_position",
            description="Publish one Float64 position to the right gripper controller; the receipt reports the "
                        "value sent",
            input=_RIGHT_GRIPPER_INPUT,
            output=_GRIPPER_OUTPUT,
        ),
        "x-cap.ad-sdl.arm_status.v1": Action(
            name="read_arm_status",
            verb="read",
            description="Read one actionlib GoalStatusArray from the MoveIt move_group status topic",
            output=_STATUS_OUTPUT,
        ),
        "x-cap.ad-sdl.nav_status.v1": Action(
            name="read_nav_status",
            verb="read",
            description="Read one actionlib GoalStatusArray from the move_base status topic",
            output=_STATUS_OUTPUT,
        ),
    }
    # The e-stop pauses the Gazebo world and reads the paused flag back.  A failed pause, a false service result
    # (a non-ODE engine) or a read-back with pause false leaves the e-stop unconfirmed and the latch held.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _SentReceipt(super().make_bridge(native))
