"""OpenMHS rosbridge driver for the pinned uthiras SCARA/RRP ROS 2 simulation.

The upstream is a ROS 2 + Gazebo teaching project, not a hardware device.  Its
shipped Python entry points are:

* ``service``/``listener`` -> ``py_srvcli.traj_follow``: a ``q_ref`` service
  that stores a three-joint position reference, a ``joint_states``
  subscription, and a PD controller that publishes ``Float64MultiArray``
  efforts on ``/forward_effort_controller/commands``;
* ``control`` -> ``py_srvcli.control_velocity``: ``Fvel`` and ``Ivel``
  services plus a joint-state PID loop that publishes the same effort topic;
* ``ros2 run FK listener`` -> ``FK.end_pose``: a ``joint_states`` subscriber
  that publishes the homogeneous matrix as a ``std_msgs/String`` on ``h_mat``.

This package is a configuration-only ``RosDriver``; it declares no Python
native class and never imports the clone.  The high-level ``q_ref`` and
``Ivel`` services are not bound: their callbacks return no success/failure
field (``traj_follow.py:72`` and ``control_velocity.py:239-241``) and the
``RosDriver`` requires an explicit application predicate for an effectful
service.  The driver binds the underlying effort command topic (the actuator
input that both upstream controllers publish to) and the kinematic
observations.

The clone exposes no acknowledged stop, pause, cancel or safe-state service or
action of its own.  The e-stop is the Gazebo world pause of the simulator's own
repository, cited as a reviewed companion source fetched at a pinned commit
(user decision and authorisation of 2026-11-05; ``task.json`` ``companions``
with ``lock``): gazebo_ros 3.9.0 (ROS 2 Humble) ``/pause_physics``, which
``rrbot_world.launch.py`` includes through ``gazebo.launch.py``.  ROS 2
gazebo_ros has no service that reports the paused flag, so the stop is
confirmed by a stall read-back (E1): two ``/get_model_list`` answers 250 ms
apart whose ``header.stamp``, the world's sim time, did not advance.  That
pair is the whole confirmation window.  While paused, ``World::Step`` still
advances sim time and calls ``Update`` when a step is pending or a reset is
due (``World.cc:835-841``); a WorldControl step or multi_step can schedule
that (``World.cc:1630-1639``), and gazebo_ros2_control writes joint commands
on each such update (``gazebo_ros2_control_plugin.cpp:433-436``).
``safety_status`` returns the cached confirmation from that window and does
not call ``/get_model_list`` again.  It is a frozen sim time for those two
samples, not a measured standstill.

No unpause is offered (the orchestrator's SAFE-042 condition): traj_follow and
control_velocity publish a new effort on every ``joint_states`` message, and
their joint3 effort carries a constant -9.8 term, so this package cannot clear
the effort the controller would apply when the world resumes, and a zero
effort is not what the upstream controllers hold joint3 with.  After
``mhs.safety.reset`` the world stays paused and the operator recovers outside
MHS (see ``safe_state``).  The device resource reads no topic: the launch also
starts a standalone ``ros2_control_node`` beside the controller manager inside
gzserver, so which node publishes ``/joint_states`` while the world is paused
is not settled by the source (Claude Sonnet verifier, phase-5 triage); the
joint states stay an explicit read, and the effort receipt reports the three
efforts it sent.

The fake is a ROS-free analytic contract stand-in, not a recording of captured
traffic.  Every endpoint and Fact of the package's own surface cites the pinned
clone at ece3e91727b0922b336dadf803afaefbcc405e28; the stop cites the
companions.  No ROS graph, Gazebo instance, controller, real arm or hardware
was run while writing this package.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# -- Companion sources (task.json companions; user decision 2026-11-05) -----------------------------------------
#: gazebo_ros 3.9.0 (ROS 2 Humble, Gazebo 11) at ae6e5793, fetched under work/companions: the pause and its stall
#: read-back.  ROS 2 gazebo_ros has no service that reports the paused flag, so the read-back is get_model_list,
#: whose header.stamp is the world's sim time: two answers 250 ms apart with the same stamp (E1, a stall read-back).
_INIT = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_init.cpp"
_FACTORY = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_factory.cpp"
_GZSERVER = "companion:gazebo_ros_pkgs/gazebo_ros/launch/gzserver.launch.py"
_GAZEBO_LAUNCH = "companion:gazebo_ros_pkgs/gazebo_ros/launch/gazebo.launch.py"
#: Gazebo classic 11.15.1 at b22c6e15 (the corpus clone): the world step the pause gates.
_WORLD = "companion:gazebo_classic/gazebo/physics/World.cc"
#: gazebo_ros2_control 0.4.12 (Humble) at 42d875b4, fetched under work/companions: the controller update.
_GZ_ROS2_CONTROL = "companion:gazebo_ros2_control/gazebo_ros2_control/src/gazebo_ros2_control_plugin.cpp"
_GAZEBO_SYSTEM = "companion:gazebo_ros2_control/gazebo_ros2_control/src/gazebo_system.cpp"

#: The e-stop: pause_physics (std_srvs/srv/Empty) sets the world's paused flag.
_PAUSE = {
    "service": "/pause_physics",
    "type": "std_srvs/srv/Empty",
    "source_name": "pause_physics",
    "source_ref": _INIT + ":267-271",
    "type_ref": _INIT + ":267",
    "state_ref": _INIT + ":328-333",
    "description": "Pause the Gazebo world (gazebo_ros pause_physics: World::SetPaused(true))",
    "request": {},
    "success": {"path": "$", "equals": {}},
    "timeout_ms": 400,
}
#: The stall read-back that confirms it: get_model_list stamps its answer with the world's sim time, which advances
#: only while the world steps; the e-stop is confirmed only when two answers 250 ms apart carry the same stamp.
_READBACK = {
    "service": "/get_model_list",
    "type": "gazebo_msgs/srv/GetModelList",
    "source_name": "get_model_list",
    "source_ref": _FACTORY + ":139-143",
    "type_ref": _FACTORY + ":139",
    "state_ref": _FACTORY + ":168",
    "description": "Read the world's sim time twice, 250 ms apart; the e-stop is confirmed only when it did not advance",
    "request": {},
    "success": {"path": "success", "equals": True},
    "stall": {"path": "header.stamp", "samples": 2, "interval_ms": 250, "unchanged": True},
    "timeout_ms": 300,
}

#: Facts about the companions, each one clause on its cited range.
_COMPANION_FACTS = [
    Fact("gazebo.launch.py includes gzserver.launch.py unless its server argument is false.", source="upstream_code",
         ref=_GAZEBO_LAUNCH + ":32-38"),
    Fact("gzserver.launch.py adds the init and factory gazebo_ros system plugins to the server command.",
         source="upstream_code", ref=_GZSERVER + ":55-56"),
    Fact("gzserver.launch.py defaults its init and factory arguments to true.", source="upstream_code",
         ref=_GZSERVER + ":186-193"),
    Fact("The init plugin takes the shared gazebo_ros node from gazebo_ros::Node::Get().", source="upstream_code",
         ref=_INIT + ":150-154"),
    Fact("gazebo_ros::Node::Get creates the shared node named gazebo with an empty namespace.",
         source="upstream_code", ref="companion:gazebo_ros_pkgs/gazebo_ros/src/node.cpp:159-171"),
    Fact("The gazebo_ros executor spins its nodes on a thread of its own.", source="upstream_code",
         ref="companion:gazebo_ros_pkgs/gazebo_ros/src/executor.cpp:22-23"),
    Fact("The init plugin creates the pause_physics and unpause_physics services with the std_srvs::srv::Empty "
         "type.", source="upstream_code", ref=_INIT + ":266-277"),
    Fact("OnPause calls world_->SetPaused(true).", source="upstream_code", ref=_INIT + ":328-333"),
    Fact("OnUnpause calls world_->SetPaused(false).", source="upstream_code", ref=_INIT + ":335-340"),
    Fact("The init plugin publishes the simulation clock from a world-update-begin callback.",
         source="upstream_code", ref=_INIT + ":206-207"),
    Fact("The factory plugin creates the get_model_list service with the gazebo_msgs::srv::GetModelList type.",
         source="upstream_code", ref=_FACTORY + ":139-143"),
    Fact("GetModelList sets header.stamp to the world's simulation time, lists the model names and sets success "
         "true.", source="upstream_code", ref=_FACTORY + ":164-174"),
    Fact("The GetModelList response documents header.stamp as the simulation time when the data was collected.",
         source="upstream_code", ref="companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetModelList.srv:2-5"),
    Fact("World::Step advances simulation time and calls Update only when the world is not paused, a step increment "
         "is pending or a reset is due; otherwise it adds the step to the pause time.", source="upstream_code",
         ref=_WORLD + ":835-854"),
    Fact("World::Step holds worldUpdateMutex while it steps the world.", source="upstream_code",
         ref=_WORLD + ":824-827"),
    Fact("World::SetPaused stores the paused flag under worldUpdateMutex.", source="upstream_code",
         ref=_WORLD + ":1585-1593"),
    Fact("World::IsPaused returns the stored paused flag.", source="upstream_code", ref=_WORLD + ":1579-1582"),
    Fact("World::Update fires the worldUpdateBegin event and then updates every model.", source="upstream_code",
         ref=_WORLD + ":920-929"),
    Fact("World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed "
         "on every step, paused or not.", source="upstream_code", ref=_WORLD + ":835-863"),
    Fact("A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the "
         "number of steps to run while paused.", source="upstream_code", ref=_WORLD + ":1630-1640"),
    Fact("The gazebo_ros2_control plugin creates its controller manager node with the name controller_manager.",
         source="upstream_code", ref=_GZ_ROS2_CONTROL + ":362-370"),
    Fact("The gazebo_ros2_control plugin calls GazeboSystem::initSim with the model the plugin is loaded for.",
         source="upstream_code", ref=_GZ_ROS2_CONTROL + ":337-346"),
    Fact("gazebo_ros2_control spins its controller manager's executor on a thread of its own.",
         source="upstream_code", ref=_GZ_ROS2_CONTROL + ":400-407"),
    Fact("gazebo_ros2_control connects its Update to the world-update begin event.", source="upstream_code",
         ref=_GZ_ROS2_CONTROL + ":409-414"),
    Fact("gazebo_ros2_control's Update reads the simulation time, updates the controllers and writes their "
         "commands to the joints.", source="upstream_code", ref=_GZ_ROS2_CONTROL + ":419-437"),
    Fact("GazeboSystem::initSim creates the system's private data and stores the parent model.",
         source="upstream_code", ref=_GAZEBO_SYSTEM + ":134-144"),
    Fact("GazeboSystem::write reads the simulation time from the parent model's world.", source="upstream_code",
         ref=_GAZEBO_SYSTEM + ":818-825"),
]

_EFFORT_ID = "x-cap.uthiras.effort_command.v1"


class _SentReceipt:
    """The receipt of an effort publication also reports the three efforts it handed to rosbridge.

    The device resource reads no topic (who publishes /joint_states while the world is paused is not settled by the
    source), so the receipt is where a caller sees what a publication sent; it is the transmitted request, not a
    measurement. Every other call, the e-stop and the reset included, goes to the SDK bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id != _EFFORT_ID:
            return output
        output = dict(output)
        output["sent_efforts"] = [float(value) for value in dict(args or {})["efforts"]]
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


#: The clone paths used by the declarations and the Facts.
_TRAJ = "src/Foundation_Project/py_srvcli/py_srvcli/traj_follow.py"
_CONTROL = "src/Foundation_Project/py_srvcli/py_srvcli/control_velocity.py"
_IK = "src/Foundation_Project/py_srvcli/py_srvcli/service_member_function.py"
_FK = "src/FK/FK/end_pose.py"
_SETUP = "src/Foundation_Project/py_srvcli/setup.py"
_URDF = ("src/rrbot_simulation_files/rrbot_simulation_files/rrbot_description/urdf/"
         "rrbot_description.urdf.xacro")
_ROS2_CONTROL = ("src/rrbot_simulation_files/rrbot_simulation_files/rrbot_description/"
                 "ros2_control/rrbot.ros2_control.xacro")
_LAUNCH = ("src/rrbot_simulation_files/rrbot_simulation_files/rrbot_gazebo/launch/"
           "rrbot_world.launch.py")
_GAZEBO_CFG = ("src/rrbot_simulation_files/rrbot_simulation_files/rrbot_gazebo/config/"
               "gazebo_controllers.yaml")
_SWITCH = ("src/rrbot_simulation_files/rrbot_simulation_files/rrbot_gazebo/src/"
           "controller_switch.cpp")
_GAZEBO_XACRO = ("src/rrbot_simulation_files/rrbot_simulation_files/rrbot_description/gazebo/"
                 "rrbot.gazebo.xacro")
_README = "README.md"

#: Evidence lines for the wire declarations.
_JOINT_STATES_REF = f"{_TRAJ}:22"
_JOINT_STATE_TYPE_REF = f"{_TRAJ}:8"
_EFFORT_REF = f"{_TRAJ}:23"
_FLOAT64_TYPE_REF = f"{_TRAJ}:7"
_H_MAT_REF = f"{_FK}:18"
_STRING_TYPE_REF = f"{_FK}:8"
_FVEL_REF = f"{_CONTROL}:60"
_FVEL_TYPE_REF = f"{_CONTROL}:6"

#: A publication carries no application success.  These two output fields are
#: the transport's honest raw result and are never a motion/stop claim.
_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the message to rosbridge"),
    "confirmed": Field(
        "boolean",
        description=("Always false: a rosbridge publication carries no controller acknowledgement, "
                     "joint-motion confirmation or stop confirmation"),
    ),
}

#: The effort command is one Float64MultiArray in the controller's joint order.
_EFFORTS = Field(
    "array",
    unit="1",
    length=3,
    description=("Three joint effort commands in controller order joint1, joint2, joint3. "
                 "joint1 and joint2 are revolute efforts in N*m; joint3 is a prismatic effort "
                 "in N. The pinned ros2_control description bounds every effort command "
                 "interface at -100..100."),
    items=Field(
        "number",
        unit="1",
        description="One joint effort command; the ros2_control effort interface is bounded at -100..100",
    ),
    limit=[
        Limit(
            min=-100, max=100, path="[0]", unit="1",
            source="upstream_code", ref=f"{_ROS2_CONTROL}:25-27",
            reason=("the joint1 effort command interface declares min -100 and max 100; the "
                    "upstream controller does not clamp a command itself"),
        ),
        Limit(
            min=-100, max=100, path="[1]", unit="1",
            source="upstream_code", ref=f"{_ROS2_CONTROL}:42-44",
            reason=("the joint2 effort command interface declares min -100 and max 100; the "
                    "upstream controller does not clamp a command itself"),
        ),
        Limit(
            min=-100, max=100, path="[2]", unit="1",
            source="upstream_code", ref=f"{_ROS2_CONTROL}:59-61",
            reason=("the joint3 effort command interface declares min -100 and max 100; the "
                    "upstream controller does not clamp a command itself"),
        ),
    ],
)

#: JointState observation fields.  The pinned URDF has joint1/joint2 revolute
#: and joint3 prismatic, so the position/velocity arrays are heterogeneous.
_JOINT_NAMES = Field(
    "array",
    unit="1",
    length=3,
    description="Joint names in the publisher's order: joint1, joint2, joint3",
    items=Field("string", description="One joint name"),
)
_JOINT_POSITIONS = Field(
    "array",
    unit="1",
    length=3,
    description=("Joint positions in the publisher's order: joint1 and joint2 in rad, "
                 "joint3 in m"),
    items=Field("number", unit="1", description="One joint position; see the array description for its unit"),
)
_JOINT_VELOCITIES = Field(
    "array",
    unit="1",
    length=3,
    description=("Joint velocities in the publisher's order: joint1 and joint2 in rad/s, "
                 "joint3 in m/s"),
    items=Field("number", unit="1", description="One joint velocity; see the array description for its unit"),
)
_JOINT_STAMP_SECS = Field("integer", unit="s", description="Whole seconds of the JointState header stamp")
_JOINT_STAMP_NSECS = Field("integer", unit="ns", description="Nanoseconds of the JointState header stamp")
_JOINT_STATE_OUTPUT = {
    "names": _JOINT_NAMES,
    "positions": _JOINT_POSITIONS,
    "velocities": _JOINT_VELOCITIES,
    "stamp_secs": _JOINT_STAMP_SECS,
    "stamp_nsecs": _JOINT_STAMP_NSECS,
}

#: Forward kinematics is a String carrying a four-line homogeneous matrix.
_H_MAT_OUTPUT = {
    "homogeneous_matrix": Field(
        "string",
        description=("The String.data value published by the FK node: four lines, each a "
                     "space-separated row of the 4x4 homogeneous transform; a text "
                     "representation, not a measured pose"),
    ),
}

#: Forward velocity kinematics inputs.  The clone does not range-check Fvel;
#: the source-backed envelope is the ros2_control velocity command interface.
_FVEL_JOINT1 = Field(
    "number",
    unit="rad/s",
    description="Joint1 velocity input for the Jacobian product",
    limit=Limit(
        min=-10, max=10, unit="rad/s", source="upstream_code",
        ref=f"{_ROS2_CONTROL}:21-24",
        reason=("the joint1 velocity command interface is bounded at -10..10 rad/s; the Fvel "
                "callback itself does not range-check its request"),
    ),
)
_FVEL_JOINT2 = Field(
    "number",
    unit="rad/s",
    description="Joint2 velocity input for the Jacobian product",
    limit=Limit(
        min=-10, max=10, unit="rad/s", source="upstream_code",
        ref=f"{_ROS2_CONTROL}:38-40",
        reason=("the joint2 velocity command interface is bounded at -10..10 rad/s; the Fvel "
                "callback itself does not range-check its request"),
    ),
)
_FVEL_JOINT3 = Field(
    "number",
    unit="m/s",
    description="Joint3 prismatic velocity input for the Jacobian product",
    limit=Limit(
        min=-10, max=10, unit="m/s", source="upstream_code",
        ref=f"{_ROS2_CONTROL}:55-57",
        reason=("the joint3 velocity command interface is bounded at -10..10; the Fvel callback "
                "itself does not range-check its request"),
    ),
)
_FVEL_OUTPUT = {
    "endeff_vel_x": Field("number", unit="m/s", description="End-effector x velocity computed by the Fvel callback"),
    "endeff_vel_y": Field("number", unit="m/s", description="End-effector y velocity computed by the Fvel callback"),
    "endeff_vel_z": Field("number", unit="m/s", description="End-effector z velocity computed by the Fvel callback"),
}

#: One explicit effort publication on the controller's command topic.
_EFFORT_COMMAND = {
    "topic": "/forward_effort_controller/commands",
    "type": "std_msgs/msg/Float64MultiArray",
    "operation": "publish",
    "source_ref": _EFFORT_REF,
    "type_ref": _FLOAT64_TYPE_REF,
    "message": {"data": []},
    "args": {"data": {"from": "input.efforts"}},
}

#: One fresh joint-state sample.  The result mapping is explicit; no held or
#: cached sample is returned by the bridge.
_JOINT_STATES_COMMAND = {
    "topic": "/joint_states",
    "type": "sensor_msgs/msg/JointState",
    "operation": "subscribe",
    "source_name": "joint_states",
    "source_ref": _JOINT_STATES_REF,
    "type_ref": _JOINT_STATE_TYPE_REF,
    "path": "$",
    "result": {"map": {
        "names": "name",
        "positions": "position",
        "velocities": "velocity",
        "stamp_secs": "header.stamp.sec",
        "stamp_nsecs": "header.stamp.nanosec",
    }},
}

#: The FK node's String publication.
_H_MAT_COMMAND = {
    "topic": "/h_mat",
    "type": "std_msgs/msg/String",
    "operation": "subscribe",
    "source_name": "h_mat",
    "source_ref": _H_MAT_REF,
    "type_ref": _STRING_TYPE_REF,
    "path": "data",
    "result": {"map": {"homogeneous_matrix": "output.$"}},
}

#: Fvel is an observational service: its callback computes and returns values
#: and does not write the controller's reference globals.
_FVEL_COMMAND = {
    "service": "/Forward_Velocity_Kinematics",
    "type": "ikinterface/srv/Fvel",
    "operation": "read",
    "source_name": "Forward_Velocity_Kinematics",
    "source_ref": _FVEL_REF,
    "type_ref": _FVEL_TYPE_REF,
    "args": {
        "joint1_vel": {"from": "input.joint1_vel"},
        "joint2_vel": {"from": "input.joint2_vel"},
        "joint3_vel": {"from": "input.joint3_vel"},
    },
    "result": {"map": {
        "endeff_vel_x": "endeff_vel_x",
        "endeff_vel_y": "endeff_vel_y",
        "endeff_vel_z": "endeff_vel_z",
    }},
}


class ScaraRobotRos2(RosDriver):
    """SCARA/RRP Gazebo simulation through the pinned ROS 2 service/topic graph."""

    device_id = "scara-robot"
    device_kind = "robot.arm"
    mode = "simulated"
    # A robot arm is at least R2 (MHS/spec/04-safety.md); the card floor is R0.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeScaraRobotRos2"}
    tags = ["ros", "ros2", "scara", "rrp", "gazebo", "kinematics", "trajectory", "simulation"]
    display_name = "Uthira SCARA/RRP robot simulation"
    vendor = "uthiras"
    model = "RRBot-style 2-DOF revolute plus prismatic arm in a Gazebo world (URDF name 2dof_robot)"

    facts = [
        Fact(
            "The traj_follow node creates the q_ref service of type Ref.",
            source="upstream_code",
            ref=f"{_TRAJ}:21",
        ),
        Fact(
            "The traj_follow node creates a joint_states subscription with "
            "sensor_msgs/JointState and a publisher for std_msgs/Float64MultiArray on "
            "/forward_effort_controller/commands.",
            source="upstream_code",
            ref=f"{_TRAJ}:22-23",
        ),
        Fact(
            "The traj_follow listener reads positions 0..2 and velocities 0..2, uses fixed gains "
            "1, 1.5, 1 and 2.5, and computes tau1, tau2 and tau3 from qref1..3; tau3 adds a "
            "constant -9.8.",
            source="upstream_code",
            ref=f"{_TRAJ}:30-47",
        ),
        Fact(
            "The q_ref callback assigns qref1, qref2 and qref3 from request fields a, b and c and "
            "returns qref1 in response field i.",
            source="upstream_code",
            ref=f"{_TRAJ}:67-74",
        ),
        Fact(
            "The traj_follow constructor sets qref1, qref2 and qref3 to 0.0 and creates the q_ref service, "
            "the joint_states subscription and the effort publisher; it creates no other service, "
            "subscription or publisher.",
            source="upstream_code",
            ref=f"{_TRAJ}:13-24",
        ),
        Fact(
            "The traj_follow listener publishes the computed efforts on /forward_effort_controller/commands "
            "at the end of every joint_states callback.",
            source="upstream_code",
            ref=f"{_TRAJ}:25-66",
        ),
        Fact(
            "The control_velocity node creates the Forward_Velocity_Kinematics Fvel service and "
            "the Inverse_Velocity_Kinematics Ivel service, creates a joint_states subscription and "
            "a publisher for std_msgs/Float64MultiArray on /forward_effort_controller/commands.",
            source="upstream_code",
            ref=f"{_CONTROL}:60-63",
        ),
        Fact(
            "The Ivel callback assigns ev1, ev2 and ev3 from request endeff_vel_x, endeff_vel_y and "
            "endeff_vel_z.",
            source="upstream_code",
            ref=f"{_CONTROL}:214-216",
        ),
        Fact(
            "The control_velocity listener uses J_inv multiplied by the Ev globals to form "
            "desired_velocity and computes a PID effort on every joint_states message.",
            source="upstream_code",
            ref=f"{_CONTROL}:108-124",
        ),
        Fact(
            "The Fvel callback computes end-effector velocities from the requested joint "
            "velocities and returns endeff_vel_x, endeff_vel_y and endeff_vel_z.",
            source="upstream_code",
            ref=f"{_CONTROL}:195-204",
        ),
        Fact(
            "The control_velocity constructor initialises its globals and creates the Fvel and Ivel "
            "services, the joint_states subscription and the effort publisher; it creates no other "
            "service, subscription or publisher.",
            source="upstream_code",
            ref=f"{_CONTROL}:14-64",
        ),
        Fact(
            "The control_velocity listener adds -9.8 to the joint3 effort and publishes the efforts on "
            "/forward_effort_controller/commands at the end of every joint_states callback.",
            source="upstream_code",
            ref=f"{_CONTROL}:65-164",
        ),
        Fact(
            "The FK node creates a joint_states subscription with sensor_msgs/JointState and a "
            "publisher for the homogeneous matrix as a std_msgs/String on the relative topic h_mat.",
            source="upstream_code",
            ref=f"{_FK}:13-18",
        ),
        Fact(
            "The FK listener computes A1, A2, A3 and their product H, writes H into a four-line "
            "string and publishes it on h_mat.",
            source="upstream_code",
            ref=f"{_FK}:28-46",
        ),
        Fact(
            "The service_member_function node creates the Inverse_Kinematics service of type Ik.",
            source="upstream_code",
            ref=f"{_IK}:11",
        ),
        Fact(
            "The service_member_function IK callback assigns the five response fields from its "
            "four two-link solutions and the computed d3.",
            source="upstream_code",
            ref=f"{_IK}:70-74",
        ),
        Fact(
            "The py_srvcli console scripts run traj_follow for service and listener, "
            "control_velocity for control, and name a Velocity_Service module for vel; there is no "
            "console script for service_member_function.",
            source="upstream_code",
            ref=f"{_SETUP}:21-27",
        ),
        Fact(
            "The URDF declares joint1 and joint2 as continuous revolute joints and joint3 as a "
            "prismatic joint whose limit is lower -${height4-width}, upper 0, effort 1000 and "
            "velocity 0.2.",
            source="upstream_code",
            ref=f"{_URDF}:49-124",
        ),
        Fact(
            "The ros2_control description declares position and velocity command interfaces at "
            "-10..10 and effort command interfaces at -100..100 for joint1, joint2 and joint3.",
            source="upstream_code",
            ref=f"{_ROS2_CONTROL}:16-66",
        ),
        Fact(
            "The rrbot_world launch includes Gazebo, starts controller_manager, spawns the joint "
            "state broadcaster, spawns forward_position_controller and forward_velocity_controller "
            "stopped, and spawns forward_effort_controller active.",
            source="upstream_code",
            ref=f"{_LAUNCH}:33-106",
        ),
        Fact(
            "The rrbot_world launch includes gazebo_ros's gazebo.launch.py with the rrbot world.",
            source="upstream_code",
            ref=f"{_LAUNCH}:42-46",
        ),
        Fact(
            "The rrbot_world launch starts a Node with package controller_manager and executable "
            "ros2_control_node, and passes robot_description and robot_controllers as its parameters.",
            source="upstream_code",
            ref=f"{_LAUNCH}:69-75",
        ),
        Fact(
            "The launch description starts gazebo, spawn_entity, the standalone controller_manager node, "
            "robot_state_publisher, the joint_state_broadcaster spawner and the delayed controller spawners.",
            source="upstream_code",
            ref=f"{_LAUNCH}:130-139",
        ),
        Fact(
            "The spawners name the controller manager /controller_manager.",
            source="upstream_code",
            ref=f"{_LAUNCH}:82-106",
        ),
        Fact(
            "The rrbot Gazebo description loads the gazebo_ros2_control plugin (libgazebo_ros2_control.so) "
            "with the gazebo_controllers.yaml parameters.",
            source="upstream_code",
            ref=f"{_GAZEBO_XACRO}:11-15",
        ),
        Fact(
            "The rrbot ros2_control description uses the gazebo_ros2_control/GazeboSystem hardware plugin.",
            source="upstream_code",
            ref=f"{_ROS2_CONTROL}:13-15",
        ),
        Fact(
            "The controller_switch client creates /controller_manager/switch_controller and sets "
            "activate_controllers to forward_velocity_controller and deactivate_controllers to "
            "forward_position_controller.",
            source="upstream_code",
            ref=f"{_SWITCH}:17-21",
        ),
        Fact(
            "The gazebo_controllers configuration declares forward_effort_controller as a "
            "forward_command_controller/ForwardCommandController for joint1, joint2 and joint3 "
            "with the effort interface.",
            source="upstream_code",
            ref=f"{_GAZEBO_CFG}:11-54",
        ),
        Fact(
            "The README runs ros2 run FK listener.",
            source="vendor_doc",
            ref=f"{_README}:29-35",
        ),
        Fact(
            "The README runs py_srvcli service and calls q_ref, and runs py_srvcli control and "
            "calls Forward_Velocity_Kinematics and Inverse_Velocity_Kinematics.",
            source="vendor_doc",
            ref=f"{_README}:70-104",
        ),
        Fact(
            "The README calls Inverse_Kinematics after ros2 run py_srvcli service.",
            source="vendor_doc",
            ref=f"{_README}:47-51",
        ),
        Fact(
            "The py_srvcli package.xml declares Apache License 2.0.",
            source="upstream_code",
            ref="src/Foundation_Project/py_srvcli/package.xml:8",
        ),
        Fact(
            "The FK package manifest still contains the placeholder license text "
            "TODO: License declaration.",
            source="upstream_code",
            ref="src/FK/package.xml:8",
        ),
        Fact(
            "The ikinterface package manifest still contains the placeholder license text "
            "TODO: License declaration.",
            source="upstream_code",
            ref="src/Foundation_Project/ikinterface/package.xml:8",
        ),
        Fact(
            "The rrbot_gazebo package.xml declares BSD.",
            source="upstream_code",
            ref=("src/rrbot_simulation_files/rrbot_simulation_files/rrbot_gazebo/package.xml:11"),
        ),
        *_COMPANION_FACTS,
    ]

    safe_state = (
        "Two /get_model_list answers 250 ms apart share header.stamp in that confirmation window: a frozen "
        "sim time, not a measured standstill. A paused World::Step still updates when a step is pending or a "
        "reset is due (World.cc:835-841; WorldControl :1630-1639), and gazebo_ros2_control writes joint "
        "commands (gazebo_ros2_control_plugin.cpp:433-436). safety_status returns that cached confirmation. "
        "No unpause is offered: stop traj_follow and control_velocity, decide the effort, and unpause outside MHS."
    )

    fidelity = {
        "engine": "analytic:ROS-free recording transport for the pinned ROS 2 services and topics (no Gazebo)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": ("Event-driven rosbridge fake with canned service values and topic samples; "
                      "no physics step, controller loop, effort integration or wall-clock pacing"),
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free analytic contract stand-in, not a recording of captured "
            "traffic: it runs no Gazebo physics, ros2_control/controller_manager, traj_follow PD "
            "loop, control_velocity PID loop or FK/IK node",
            "every joint position, velocity, effort, homogeneous matrix and service answer in the "
            "fake is a # placeholder; a live deployment must receive them from the operator's ROS "
            "graph",
            "the effort publication is transmission-only: the receipt says published=true and "
            "confirmed=false and reports the three efforts it handed to rosbridge (the transmitted "
            "request, not a measurement); it does not prove that a controller consumed the message, "
            "that the simulated arm moved or that it stopped; the fake shifts its placeholder joint "
            "positions by a tiny amount on a publication, and that shift is not physics or motion "
            "evidence",
            "the high-level q_ref and Ivel services are not bound: their responses expose no "
            "success/failure field (traj_follow.py:72, control_velocity.py:239-241) and the "
            "RosDriver requires an application predicate for an effectful service; binding them as "
            "observations would hide their motion effect",
            "the Inverse_Kinematics service is not bound: setup.py does not register "
            "service_member_function (the service and listener entries run traj_follow), so the "
            "README's ros2 run command does not advertise that endpoint, and its inputs have no "
            "stated bounds",
            "the clone exposes no acknowledged stop, pause, cancel or safe-state service/action, and "
            "deactivating the effort controller with /controller_manager/switch_controller is not "
            "presented as a safe state; the stop is the companion gazebo_ros world pause, confirmed by "
            "the E1 stall read-back: the fake keeps a paused flag that /pause_physics sets and a sim-time "
            "stamp that /get_model_list reports and that advances on every answer unless paused; it runs "
            "no Gazebo World::Step",
            "a frozen get_model_list stamp is also what a hung but unpaused gzserver shows (nothing "
            "advances then either); a GUI step or a WorldControl multi_step between the two samples "
            "fails the check (fails closed); the e-stop declares estop_latency_ms 1500 because the pause "
            "(400 ms), two read-backs (300 ms each) and the 250 ms interval exceed the default 1000 ms "
            "budget",
            "no unpause is offered: traj_follow and control_velocity publish a new effort on every "
            "joint_states message and add a constant -9.8 to the joint3 effort (traj_follow.py:25-66, "
            "control_velocity.py:65-164), so this package cannot clear the effort the controller applies "
            "when the world resumes, and a zero effort is not what the upstream controllers command; the "
            "operator recovers outside MHS (stop traj_follow and control_velocity, decide the command on "
            "/forward_effort_controller/commands, then the Gazebo GUI play button or ros2 service call "
            "/unpause_physics)",
            "rrbot_world.launch.py starts a standalone controller_manager ros2_control_node "
            "(rrbot_world.launch.py:69-75) beside the controller manager that the gazebo_ros2_control "
            "plugin creates inside gzserver under the same name; only the plugin gives a GazeboSystem a "
            "model (gazebo_ros2_control_plugin.cpp:337-346, gazebo_system.cpp:134-144, 818-825), so the "
            "standalone node cannot act on the Gazebo world, but whether it runs, fails or publishes "
            "/joint_states on the system clock while the world is paused is not settled by the source; "
            "the device resource therefore reads no topic, and the explicit joint-state read may still "
            "answer while the world is paused (the fake's wall_clock_joint_states switch)",
            "while paused, the gzserver controller manager's joint_state_broadcaster and /clock come only "
            "from world updates; the fake silences /joint_states while paused unless its "
            "wall_clock_joint_states switch is set",
            "a live world can be unpaused or stepped by the Gazebo GUI, a WorldControl message "
            "(World.cc:1630-1639) or any ROS 2 client of /unpause_physics, and World::Step still advances "
            "sim time and calls Update while paused when a step is pending or a reset is due "
            "(World.cc:835-841), which makes gazebo_ros2_control write joint commands "
            "(gazebo_ros2_control_plugin.cpp:433-436); the two-sample stall is the whole confirmation "
            "window, and safety_status returns that cached confirmation and does not call /get_model_list "
            "again (RosBridge.safety_status, mhs/bridge/ros.py:2227-2232)",
            "the deployment's gazebo_ros, gazebo_ros2_control and Gazebo must be the pinned 3.9.0, 0.4.12 and "
            "11.15.1 releases the companion citations name; the clone's Humble and Gazebo 11 evidence is its "
            "committed colcon artifacts (install/setup.bash:22, "
            "build/rrbot_description/colcon_command_prefix_build.sh.env:13, 37), and rosbridge cannot read "
            "the deployed versions",
            "NOT COVERED: Gazebo physics and collisions, controller_manager/ros2_control, the "
            "real PD/PID timing and gains, joint-limit enforcement, the q_ref and Ivel control "
            "paths, the IK service, /tf, and hardware",
        ],
    }

    # The device resource reads no topic: which node publishes /joint_states while the e-stop holds the world paused
    # is not settled by the source (the launch's standalone ros2_control_node beside the gzserver controller
    # manager), and a resource that waited for it would fail NOT_READY after a reset when the Gazebo broadcaster is
    # silent.  The joint states stay the explicit read x-cap.uthiras.joint_states.v1.
    estop_latency_ms = 1500
    commands = {
        "x-cap.uthiras.effort_command.v1": _EFFORT_COMMAND,
        "x-cap.uthiras.joint_states.v1": _JOINT_STATES_COMMAND,
        "x-cap.uthiras.forward_kinematics.v1": _H_MAT_COMMAND,
        "x-cap.uthiras.forward_velocity.v1": _FVEL_COMMAND,
    }
    actions = {
        "x-cap.uthiras.effort_command.v1": Action(
            name="command_joint_efforts",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one three-element joint effort command on the controller's command "
                "topic; the receipt confirms only that rosbridge accepted the publication and "
                "reports the efforts sent, not that a controller applied them, that the arm moved, "
                "or that it can stop. After an e-stop and reset the world stays paused, and a "
                "command sent then acts only when the operator unpauses it"
            ),
            input={"efforts": _EFFORTS},
            output={**_PUBLISHED,
                    "sent_efforts": Field(
                        "array",
                        unit="1",
                        length=3,
                        description=("The three efforts handed to rosbridge in controller order joint1, "
                                     "joint2, joint3 (the transmitted request, not a measurement)"),
                        items=Field("number", unit="1", description="One effort sent"),
                    )},
        ),
        "x-cap.uthiras.joint_states.v1": Action(
            name="read_joint_states",
            verb="read",
            description=(
                "Read one fresh sensor_msgs/JointState sample from /joint_states; the positions "
                "and velocities are observations, not a stopped-state measurement, and which node "
                "publishes them while the world is paused is not settled by the source"
            ),
            output=_JOINT_STATE_OUTPUT,
        ),
        "x-cap.uthiras.forward_kinematics.v1": Action(
            name="read_forward_kinematics_matrix",
            verb="read",
            description=(
                "Read one fresh h_mat String sample published by the FK node; the text matrix is "
                "a computed transform, not a measured pose"
            ),
            output=_H_MAT_OUTPUT,
        ),
        "x-cap.uthiras.forward_velocity.v1": Action(
            name="forward_velocity_kinematics",
            verb="read",
            description=(
                "Call the observational Forward_Velocity_Kinematics service and return its "
                "end-effector velocity values; the service computes from the last joint state and "
                "does not command motion"
            ),
            input={
                "joint1_vel": _FVEL_JOINT1,
                "joint2_vel": _FVEL_JOINT2,
                "joint3_vel": _FVEL_JOINT3,
            },
            output=_FVEL_OUTPUT,
        ),
    }
    # The e-stop pauses the Gazebo world and confirms it by a sim time that no longer advances (companion gazebo_ros,
    # E1 stall read-back); anything else leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.  A
    # zero-effort publication, a q_ref hold or a controller switch is not bound as a stop.
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _SentReceipt(super().make_bridge(native))
