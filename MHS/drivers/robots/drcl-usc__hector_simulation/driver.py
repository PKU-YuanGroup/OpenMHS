"""OpenMHS rosbridge driver for the HECTOR humanoid Gazebo simulation.

The pinned repository is a ROS 1 / Gazebo simulation for the HECTOR humanoid.
``hector_control`` runs a 1 kHz walking controller whose ``CheatIO`` publishes
``unitree_legged_msgs/MotorCmd`` messages to ten ``UnitreeJointController``
command topics.  Each controller subscribes to the relative ``command`` topic
and publishes a ``MotorState`` on ``<controller>/state``.  The shipped launch
starts Gazebo, the robot model and the ten joint controllers under
``/hector_gazebo``; the operator runs ``rosrun hector_control hector_ctrl``
separately.

Scope: the ten joint ``MotorCmd`` publications and the ``/gazebo/model_states``
observation used by ``CheatIO`` for its cheated base state.  The per-joint
state publishers are built from a controller namespace at run time and the
clone has no quoted absolute literal for those topics, so this package does not
bind them.  The clone registers no ROS service or action stop, and a ``BRAKE``
``MotorCmd`` is still an unacknowledged topic publication.

The e-stop is the Gazebo world pause of the simulator's own repository, cited
as a reviewed companion source (user decision of 2026-11-05; ``task.json``
``companions``): gazebo_ros 2.9.3 (ROS 1 Noetic) ``/gazebo/pause_physics``,
confirmed by reading ``/gazebo/get_physics_properties`` back until ``pause`` is
true.  The ten joint controllers compute and apply torque only inside
gazebo_ros_control's world update, which a paused world does not run.  The
pause is the paused flag, not a measured standstill; any client or the Gazebo
GUI can unpause or step the world.

No unpause is offered (the orchestrator's SAFE-042 condition, the same rule as
the seven lock-companion Gazebo packages).  Each joint controller keeps the
last ``MotorCmd`` (``setCommandCB``, ``joint_controller.cpp:33-45``) and
applies it in ``update`` (``139-185``).  This package cannot clear that
command before an unpause: ``BRAKE`` (``158-164``) removes the position
stiffness and applies damping only; a ``PMSM`` command sets the position it
names (``142-145``) and the package reads no joint position; ``starting()``
(``117-129``) holds the current position, but gazebo_ros_control runs the
controller manager only from the world update
(``gazebo_ros_control_plugin.cpp:196-199, 251``), which a paused world does
not run; and ``hector_ctrl``, when it runs, republishes all ten ``MotorCmd``
messages from the main loop (``main.cpp:80-83`` calls ``CheatIO::sendRecv``,
and ``CheatIO.cpp:44-58`` publishes them).  The FSM loop (``main.cpp:22-30``)
is a different thread.  A Gazebo world reset clears the control
plugin's timing only (``GazeboRosControlPlugin::Reset``, ``260-266``), not
``lastCmd``.  After ``mhs.safety.reset`` the world stays paused.  The operator
recovers outside MHS: stop ``hector_ctrl`` (``main.cpp:16-20`` ends it on
SIGINT; the README's terminate step is ``Readme.md:67-68``), relaunch
``biped.launch`` so the controllers are constructed again
(``joint_controller.cpp:15-18`` zeros ``lastCmd``; ``biped.launch:7`` starts
the world paused), then press the simulator start button (``Readme.md:67``).
The earlier re-enable ``x-cap.drcl-usc.resume.v1`` was removed for that reason.

Every endpoint, type and fact of the package's own surface cites the pinned
clone at ``edfdc7b1a9855c71887ac2cf2ebe0bb5dee5ea49``; the stop, its read-back
and the facts about them cite the companions at their pins.  The fake
transport is ROS-free; no ROS graph, Gazebo process or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: ``hector_control`` initializes this node and hard-codes the robot name.
_MAIN_REF = "Hector_ROS_Simulation/hector_control/src/main.cpp:35-38"

#: ``CheatIO`` constructs the ten MotorCmd publishers with a robot-name prefix.
_PUBLISH_REF = "Hector_ROS_Simulation/hector_control/src/interface/CheatIO.cpp:77-88"

#: ``CheatIO::sendCmd`` fills mode 0x0A and copies q/dq/tau/Kd/Kp before publishing.
_SEND_REF = "Hector_ROS_Simulation/hector_control/src/interface/CheatIO.cpp:44-58"

#: The joint controller subscribes to the relative literal "command".
_COMMAND_REF = "Hector_ROS_Simulation/unitree_ros/unitree_legged_control/src/joint_controller.cpp:90"

#: The joint controller declares its MotorCmd/MotorState message includes.
_TYPE_REF = "Hector_ROS_Simulation/unitree_ros/unitree_legged_control/include/joint_controller.h:21-22"

#: The controller's update loop consumes the MotorCmd gains and torque.
_UPDATE_REF = "Hector_ROS_Simulation/unitree_ros/unitree_legged_control/src/joint_controller.cpp:135-164"

#: ``stopping()`` is empty: the controller has no stop callback that could be a
#: safety binding.
_STOPPING_REF = "Hector_ROS_Simulation/unitree_ros/unitree_legged_control/src/joint_controller.cpp:207-208"

#: The only process shutdown path is SIGINT; it is local to the controller.
_SIGINT_REF = "Hector_ROS_Simulation/hector_control/src/main.cpp:14-20"

#: ``CheatIO`` subscribes to the absolute Gazebo model-state topic.
_MODEL_STATES_REF = "Hector_ROS_Simulation/hector_control/src/interface/CheatIO.cpp:91"

#: The declared ModelStates type include.
_MODEL_STATES_TYPE_REF = "Hector_ROS_Simulation/hector_control/include/interface/CheatIO.h:12"

#: The launch selects the robot name and starts the ten controllers under
#: /hector_gazebo; the optional unitree servo node is commented out.
_LAUNCH_REF = "Hector_ROS_Simulation/unitree_ros/unitree_gazebo/launch/biped.launch:46-51"
_SERVO_COMMENT_REF = "Hector_ROS_Simulation/unitree_ros/unitree_gazebo/launch/biped.launch:60"

#: The README tells the operator to run the controller and to pause/reset the
#: simulator manually; neither action is a ROS stop service.
_README_REF = "Readme.md:61-68"

#: The robot description loads gazebo_ros_control with the /hector_gazebo namespace; the controller stores each
#: MotorCmd it receives and applies the stored command in its update loop.
_ROS_CONTROL_XACRO_REF = "Hector_ROS_Simulation/hector_description/xacro/gazebo.xacro:4-8"
_SET_COMMAND_REF = "Hector_ROS_Simulation/unitree_ros/unitree_legged_control/src/joint_controller.cpp:33-45"
_BRAKE_MODE_REF = "Hector_ROS_Simulation/unitree_ros/unitree_legged_control/include/joint_controller.h:26-27"

# -- Companion sources (task.json companions; user decision 2026-11-05) -----------------------------------------
#: gazebo_ros 2.9.3 (ROS 1 Noetic) at cd9cc952: the API plugin serves the pause and its read-back.
_API = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
_LAUNCH = "companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch"
#: Gazebo classic 11.15.1 at b22c6e15: the world step the pause gates.
_WORLD = "companion:gazebo_classic/gazebo/physics/World.cc"

#: The e-stop: pause_physics (std_srvs/Empty) sets the world's paused flag.
_PAUSE = {
    "service": "/gazebo/pause_physics",
    "type": "std_srvs/Empty",
    "source_name": "pause_physics",
    "source_ref": _API + ":492-498",
    "type_ref": _API + ":494",
    "state_ref": _API + ":1725-1729",
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
    "source_ref": _API + ":383-389",
    "type_ref": _API + ":385",
    "state_ref": _API + ":1489",
    "description": "Read the world's paused flag back; the e-stop is confirmed only when pause is true",
    "request": {},
    "success": {"path": "pause", "equals": True},
    "timeout_ms": 500,
}
#: Facts about the companions, each one clause on its cited range.
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
    Fact("The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet.",
         source="upstream_code", ref=_API + ":125-126"),
    Fact("The API plugin creates its node handle in the private namespace ~ and advertises its topics and services "
         "there.", source="upstream_code", ref=_API + ":145"),
    Fact("The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback "
         "queue gazebo_queue_.", source="upstream_code", ref=_API + ":492-498"),
    Fact("The API plugin advertises the service unpause_physics with the std_srvs::Empty type on gazebo_queue_.",
         source="upstream_code", ref=_API + ":501-507"),
    Fact("The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties "
         "type on gazebo_queue_.", source="upstream_code", ref=_API + ":383-389"),
    Fact("gazeboQueueThread serves gazebo_queue_ in a loop with a 0.001 s wall-clock wait while the node handle is "
         "ok.", source="upstream_code", ref=_API + ":257-264"),
    Fact("pausePhysics calls world_->SetPaused(true) and returns true.", source="upstream_code",
         ref=_API + ":1725-1729"),
    Fact("unpausePhysics calls world_->SetPaused(false) and returns true.", source="upstream_code",
         ref=_API + ":1731-1735"),
    Fact("getPhysicsProperties sets res.pause to world_->IsPaused().", source="upstream_code", ref=_API + ":1489"),
    Fact("getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it "
         "sets success false and returns false.", source="upstream_code", ref=_API + ":1496-1528"),
    Fact("The GetPhysicsProperties response field pause is true if the physics engine is paused.",
         source="upstream_code", ref="companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4"),
    Fact("Among the world-update begin hooks that its comment says apply forces and publish sim time on /clock, the "
         "API plugin connects publishSimTime.", source="upstream_code", ref=_API + ":219-222"),
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
]
#: gazebo_ros_control (gazebo_ros_pkgs) runs the controller manager only from the world-update event.
_ROS_CONTROL = "companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp"
_HECTOR_COMPANION_FACTS = [
    Fact("GazeboRosControlPlugin connects its Update method to the world-update begin event.",
         source="upstream_code", ref=_ROS_CONTROL + ":196-199"),
    Fact("GazeboRosControlPlugin::Update reads the simulated robot state, runs the controller manager update and "
         "writes the resulting commands to the Gazebo model.", source="upstream_code", ref=_ROS_CONTROL + ":211-258"),
    Fact("The API plugin advertises the model_states topic (gazebo_msgs::ModelStates) with onModelStatesConnect as "
         "its connect callback.", source="upstream_code", ref=_API + ":400-407"),
    Fact("When the first subscriber of the model states connects, the API plugin connects publishModelStates to the "
         "world-update begin event.", source="upstream_code", ref=_API + ":571-576"),
]

#: Joint geometry and limits in the xacro.  These are configuration values for
#: the shipped model; the URDF converts the degrees to radians.
_HIP_LIMITS = "Hector_ROS_Simulation/hector_description/xacro/const.xacro:37-40"
_HIP2_LIMITS = "Hector_ROS_Simulation/hector_description/xacro/const.xacro:84-87"
_THIGH_LIMITS = "Hector_ROS_Simulation/hector_description/xacro/const.xacro:123-126"
_CALF_LIMITS = "Hector_ROS_Simulation/hector_description/xacro/const.xacro:185-188"
_TOE_LIMITS = "Hector_ROS_Simulation/hector_description/xacro/const.xacro:213-216"

#: ``(capability name, controller, position limit deg, xacro velocity_max,
#: xacro torque_max, limit citation)`` for the ten active joints.  Only the
#: position bounds are used as sourced limits: the xacro states them in degrees
#: with both signs.  The velocity_max and torque_max values are the URDF limits
#: the joint controller clamps dq and tau to (velocity in the unit of dq, rad/s,
#: not deg/s) and the clone states no negative number for them, so velocity and
#: torque are operator_required (reviewer correction).
_JOINTS = (
    ("left_hip", "L_hip_controller", 45, 21, 33.5, _HIP_LIMITS),
    ("left_hip2", "L_hip2_controller", 45, 21, 33.5, _HIP2_LIMITS),
    ("left_thigh", "L_thigh_controller", 100, 21, 33.5, _THIGH_LIMITS),
    ("left_calf", "L_calf_controller", 100, 14, 67.0, _CALF_LIMITS),
    ("left_toe", "L_toe_controller", 100, 21, 33.5, _TOE_LIMITS),
    ("right_hip", "R_hip_controller", 45, 21, 33.5, _HIP_LIMITS),
    ("right_hip2", "R_hip2_controller", 45, 21, 33.5, _HIP2_LIMITS),
    ("right_thigh", "R_thigh_controller", 100, 21, 33.5, _THIGH_LIMITS),
    ("right_calf", "R_calf_controller", 100, 14, 67.0, _CALF_LIMITS),
    ("right_toe", "R_toe_controller", 100, 21, 33.5, _TOE_LIMITS),
)

#: MotorCmd mode 0x0A (PMSM) is forced by CheatIO::sendCmd.
_MODE_PMSM = 10

_PUBLISHED = {
    "published": Field(
        "boolean",
        description="True when the driver handed the MotorCmd publication to rosbridge",
    ),
    "confirmed": Field(
        "boolean",
        description="Always false: a rosbridge publication carries no controller or motion acknowledgement",
    ),
    "sent_position": Field("number", unit="deg", description="The position input of the MotorCmd sent, in "
                                                              "degrees (radians on the wire); the request, not a "
                                                              "measurement"),
    "sent_velocity": Field("number", unit="deg/s", description="The velocity input of the MotorCmd sent, in "
                                                                "degrees per second (rad/s on the wire); the "
                                                                "request"),
    "sent_torque": Field("number", unit="N.m", description="The torque input of the MotorCmd handed to rosbridge "
                                                            "(the transmitted request)"),
    "sent_position_stiffness": Field("number", unit="1", description="The Kp input handed to rosbridge"),
    "sent_velocity_stiffness": Field("number", unit="1", description="The Kd input handed to rosbridge"),
}
#: The inputs a MotorCmd receipt echoes (the device resource reads no topic: a paused world publishes none).
_SENT = ("position", "velocity", "torque", "position_stiffness", "velocity_stiffness")

_VELOCITY_LIMIT = Limit.operator_required(
    "the joint controller clamps dq to plus or minus the URDF velocity limit in rad/s (the xacro's "
    "velocity_max) and the clone states no negative bound; the operator supplies the deg/s envelope"
)
_TORQUE_LIMIT = Limit.operator_required(
    "the joint controller clamps tau to plus or minus the URDF effort limit (the xacro's torque_max) and "
    "the clone states no negative bound; the operator supplies the envelope"
)
_STIFFNESS_LIMIT = Limit.operator_required(
    "the clone sets MotorCmd Kp from the walking controller's computed gains and states no numeric "
    "stiffness bound; the operator supplies the reviewed envelope"
)
_DAMPING_LIMIT = Limit.operator_required(
    "the clone sets MotorCmd Kd from the walking controller's computed gains and states no numeric "
    "damping bound; the operator supplies the reviewed envelope"
)


def _command(joint: str, controller: str) -> dict:
    """One MotorCmd publication on the controller's relative command topic."""
    return {
        "topic": f"/hector_gazebo/{controller}/command",
        "type": "unitree_legged_msgs/MotorCmd",
        "operation": "publish",
        "source_name": "command",
        "source_ref": _COMMAND_REF,
        "type_ref": _TYPE_REF,
        "message": {"mode": _MODE_PMSM, "q": 0.0, "dq": 0.0, "tau": 0.0, "Kp": 0.0, "Kd": 0.0},
        "args": {
            "q": {"from": "input.position", "unit": {"from": "deg", "to": "rad"}},
            "dq": {"from": "input.velocity", "unit": {"from": "deg/s", "to": "rad/s"}},
            "tau": {"from": "input.torque"},
            "Kp": {"from": "input.position_stiffness"},
            "Kd": {"from": "input.velocity_stiffness"},
        },
    }


def _action(joint: str, position: float, velocity: float, torque: float, limit_ref: str) -> Action:
    """The inline schema of one joint command capability."""
    return Action(
        name=f"send_{joint}_command",
        verb="invoke",
        risk="R2",
        description=(
            f"Publish one unitree_legged_msgs/MotorCmd for the simulated {joint} joint. "
            "The receipt proves only that rosbridge accepted the publication; it does not prove "
            "that the controller applied it, that the joint moved, or that the robot is stable."
        ),
        input={
            "position": Field(
                "number", unit="deg",
                description="MotorCmd.q target position in degrees; converted to radians",
                limit=Limit(min=-position, max=position, source="upstream_code", ref=limit_ref),
            ),
            "velocity": Field(
                "number", unit="deg/s",
                description="MotorCmd.dq target velocity in degrees per second; converted to rad/s",
                limit=_VELOCITY_LIMIT,
            ),
            "torque": Field(
                "number", unit="N.m",
                description="MotorCmd.tau target torque",
                limit=_TORQUE_LIMIT,
            ),
            "position_stiffness": Field(
                "number", unit="1",
                description="MotorCmd.Kp position stiffness; no numeric bound is stated upstream",
                limit=_STIFFNESS_LIMIT,
            ),
            "velocity_stiffness": Field(
                "number", unit="1",
                description="MotorCmd.Kd velocity damping; no numeric bound is stated upstream",
                limit=_DAMPING_LIMIT,
            ),
        },
        output=_PUBLISHED,
        examples=[{"position": 0.0, "velocity": 0.0, "torque": 0.0,
                   "position_stiffness": 0.0, "velocity_stiffness": 0.0}],
    )


_VECTOR3 = Field(
    "object",
    description="Three-component ROS vector; the clone does not state a physical unit for the pose/twist fields",
    properties={
        "x": Field("number", unit="1", description="x component"),
        "y": Field("number", unit="1", description="y component"),
        "z": Field("number", unit="1", description="z component"),
    },
)

_QUATERNION = Field(
    "object",
    description="Orientation quaternion from gazebo_msgs/ModelStates",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)

_MODEL_POSE = Field(
    "object",
    description="One gazebo_msgs/ModelStates pose entry",
    properties={"position": _VECTOR3, "orientation": _QUATERNION},
)

_MODEL_TWIST = Field(
    "object",
    description="One gazebo_msgs/ModelStates twist entry",
    properties={"linear": _VECTOR3, "angular": _VECTOR3},
)

_MODEL_NAMES = Field("array", description="Model names in /gazebo/model_states",
                     items=Field("string", description="A model name"))
_MODEL_POSES = Field("array", description="Poses in /gazebo/model_states, same order as the names",
                     items=_MODEL_POSE)
_MODEL_TWISTS = Field("array", description="Twists in /gazebo/model_states, same order as the names",
                      items=_MODEL_TWIST)

#: The explicit observation capability over the same Gazebo topic.  A topic
#: subscription is an observation, not a stop or an automatic resource snapshot.
_MODEL_STATES_COMMAND = {
    "topic": "/gazebo/model_states",
    "type": "gazebo_msgs/ModelStates",
    "operation": "subscribe",
    "source_name": "/gazebo/model_states",
    "source_ref": _MODEL_STATES_REF,
    "type_ref": _MODEL_STATES_TYPE_REF,
    "result": {
        "map": {
            "model_names": "name",
            "model_poses": "pose",
            "model_twists": "twist",
        },
    },
}



class _SentValues:
    """A MotorCmd receipt also reports the five inputs it handed to rosbridge (the transmitted request).

    /gazebo/model_states is published only while the world runs, so the device resource reads no topic and the
    receipt is where a caller sees what a publication sent.  Every other call, the e-stop and the reset
    included, goes to the SDK bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id.endswith("_command.v1") and isinstance(output, dict):
            output = dict(output)
            values = dict(args or {})
            for key in _SENT:
                output["sent_" + key] = float(values[key])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


class HectorSimulation(RosDriver):
    device_id = "hector-simulation"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeHectorSimulation"}
    display_name = "HECTOR humanoid Gazebo simulation"
    vendor = "USC Dynamic Robotics and Control Laboratory"
    model = "HECTOR humanoid (ten-joint Gazebo model)"
    resource_id = "simulation"
    tags = ["ros", "ros1", "gazebo", "simulation", "humanoid", "biped", "hector", "joint-command"]

    facts = [
        Fact("hector_control initializes ROS with the node name 'hector_control' and the AnonymousName "
             "option, and hard-codes the robot name to 'hector'.",
             source="upstream_code", ref=_MAIN_REF),
        Fact("CheatIO::initSend advertises ten unitree_legged_msgs/MotorCmd publishers whose names are "
             "'/' + _robot_name + '_gazebo/<joint>_controller/command'.",
             source="upstream_code", ref=_PUBLISH_REF),
        Fact("CheatIO::sendCmd sets every MotorCmd.mode to 0x0A and copies q, dq, tau, Kd and Kp before "
             "publishing each of the ten messages.",
             source="upstream_code", ref=_SEND_REF),
        Fact("UnitreeJointController::init subscribes to the relative literal 'command' and publishes "
             "unitree_legged_msgs/MotorState on name_space + '/state'.",
             source="upstream_code", ref="Hector_ROS_Simulation/unitree_ros/unitree_legged_control/src/"
                                        "joint_controller.cpp:88-95"),
        Fact("The joint controller includes unitree_legged_msgs/MotorCmd.h and MotorState.h.",
             source="upstream_code", ref=_TYPE_REF),
        Fact("UnitreeJointController::update applies the received q/Kp, dq/Kd and tau when mode is PMSM; "
             "while mode is BRAKE it sets zero position stiffness, zero velocity, damping 20 and zero torque.",
             source="upstream_code", ref=_UPDATE_REF),
        Fact("UnitreeJointController::stopping is an empty function.",
             source="upstream_code", ref=_STOPPING_REF),
        Fact("main.cpp's ShutDown handler prints 'stop' and sets the global running flag to false.",
             source="upstream_code", ref=_SIGINT_REF),
        Fact("CheatIO subscribes to the absolute /gazebo/model_states topic with a queue size of 1.",
             source="upstream_code", ref=_MODEL_STATES_REF),
        Fact("CheatIO.h includes gazebo_msgs/ModelStates.h, the declared message type of "
             "/gazebo/model_states.",
             source="upstream_code", ref=_MODEL_STATES_TYPE_REF),
        Fact("CheatIO::StateCallback selects the model named '<robot_name>_gazebo' and copies its pose and "
             "twist into the controller's cheated high state.",
             source="upstream_code", ref="Hector_ROS_Simulation/hector_control/src/interface/CheatIO.cpp:104-126"),
        Fact("biped.launch starts the ten named joint controllers inside controller_manager with "
             "ns='/hector_gazebo'.",
             source="upstream_code", ref=_LAUNCH_REF),
        Fact("biped.launch leaves the unitree_gazebo servo node commented out.",
             source="upstream_code", ref=_SERVO_COMMENT_REF),
        Fact("The README tells the operator to launch biped.launch, run 'rosrun hector_control hector_ctrl' "
             "and click the simulator's start button, and, when the controller does not start, to terminate it, "
             "pause and reset the simulator (ctrl + R) and rerun it.",
             source="vendor_doc", ref=_README_REF),
        Fact("The shipped xacro sets hip_max 45, hip_min -45, hip_velocity_max 21 and hip_torque_max 33.5.",
             source="upstream_code", ref=_HIP_LIMITS),
        Fact("The shipped xacro sets hip2_max 45, hip2_min -45, hip2_velocity_max 21 and hip2_torque_max "
             "33.5.",
             source="upstream_code", ref=_HIP2_LIMITS),
        Fact("The shipped xacro sets thigh_max 100, thigh_min -100, thigh_velocity_max 21 and "
             "thigh_torque_max 33.5.",
             source="upstream_code", ref=_THIGH_LIMITS),
        Fact("The shipped xacro sets calf_max 100, calf_min -100, calf_velocity_max 14 and calf_torque_max 67.",
             source="upstream_code", ref=_CALF_LIMITS),
        Fact("The shipped xacro sets toe_max 100, toe_min -100, toe_velocity_max 21 and toe_torque_max 33.5.",
             source="upstream_code", ref=_TOE_LIMITS),
        Fact("leg.xacro passes hip_torque_max and hip_velocity_max unchanged to the URDF limit's effort and "
             "velocity attributes and converts hip_min and hip_max with PI/180 for its lower and upper "
             "attributes.",
             source="upstream_code",
             ref="Hector_ROS_Simulation/hector_description/xacro/leg.xacro:16"),
        Fact("positionLimits clamps a revolute or prismatic joint's commanded position to the URDF lower and "
             "upper limits, velocityLimits its velocity to plus or minus the URDF velocity limit, and "
             "effortLimits its torque to plus or minus the URDF effort limit.",
             source="upstream_code",
             ref="Hector_ROS_Simulation/unitree_ros/unitree_legged_control/src/joint_controller.cpp:210-226"),
        Fact("runFSMController runs the FSM controller in a loop paced by ros::Rate(1000) while the running "
             "flag is true.",
             source="upstream_code", ref="Hector_ROS_Simulation/hector_control/src/main.cpp:22-30"),
        Fact("biped.launch declares the paused argument with default true and passes it to gazebo_ros's "
             "empty_world.launch.",
             source="upstream_code",
             ref="Hector_ROS_Simulation/unitree_ros/unitree_gazebo/launch/biped.launch:7-19"),
        Fact("The repository is licensed under the BSD 3-Clause license.",
             source="vendor_doc", ref="License.md:1-4"),
        Fact("The vendored unitree_legged_control joint controller states that it is Unitree Robotics code "
             "governed by the MPL-2.0 license.",
             source="upstream_code",
             ref="Hector_ROS_Simulation/unitree_ros/unitree_legged_control/src/joint_controller.cpp:1-4"),
        Fact("gazebo.xacro loads the gazebo_ros_control plugin libgazebo_ros_control.so with robotNamespace "
             "/hector_gazebo.", source="upstream_code", ref=_ROS_CONTROL_XACRO_REF),
        Fact("UnitreeJointController::setCommandCB copies mode, q, Kp, dq, Kd and tau of the received MotorCmd into "
             "lastCmd and writes it to the realtime command buffer.", source="upstream_code", ref=_SET_COMMAND_REF),
        Fact("joint_controller.h defines PMSM as 0x0A and BRAKE as 0x00.", source="upstream_code",
             ref=_BRAKE_MODE_REF),
        Fact("biped.launch includes gazebo_ros's empty_world.launch.", source="upstream_code",
             ref="Hector_ROS_Simulation/unitree_ros/unitree_gazebo/launch/biped.launch:15"),
        *_COMPANION_FACTS,
        *_HECTOR_COMPANION_FACTS,
    ]

    safe_state = (
        "The Gazebo world is paused and get_physics_properties read pause true back; the paused flag, not a measured "
        "standstill. No unpause is offered: the last MotorCmd stays (joint_controller.cpp:33-45) and this package "
        "cannot clear it. The Gazebo GUI or another client can unpause or step the world (a step advances it). "
        "Spawn and delete still apply. After mhs.safety.reset the world stays paused; the operator stops hector_ctrl, "
        "relaunches biped.launch and presses start outside MHS (Readme.md:61-68)."
    )

    #: The primary actuator surface is ten topic publications.  The controller has
    #: no service/action stop; a MotorCmd publication is transmission-only and
    #: cannot prove that the joint controller applied it or that the robot stopped.
    #: The package is therefore blocked with HELPER_MISSING and declares no
    #: safety_bindings rather than inventing an acknowledgement.
    commands = {
        **{f"x-cap.drcl-usc.{joint}_command.v1": _command(joint, controller)
           for joint, controller, _pos, _vel, _torque, _ref in _JOINTS},
        "x-cap.drcl-usc.model_states.v1": _MODEL_STATES_COMMAND,
    }
    actions = {
        **{f"x-cap.drcl-usc.{joint}_command.v1": _action(joint, pos, vel, torque, ref)
           for joint, _controller, pos, vel, torque, ref in _JOINTS},
        "x-cap.drcl-usc.model_states.v1": Action(
            name="read_model_states",
            verb="read",
            description=(
                "Observe one gazebo_msgs/ModelStates sample. The values are the simulator's model "
                "states; the caller selects the hector_gazebo entry by name."
            ),
            output={
                "model_names": _MODEL_NAMES,
                "model_poses": _MODEL_POSES,
                "model_twists": _MODEL_TWISTS,
            },
        ),
    }
    # The e-stop pauses the Gazebo world and reads the paused flag back (companion gazebo_ros); a failed pause or a
    # read-back other than pause true leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    # No unpause is offered (SAFE-042: the stored MotorCmds cannot be cleared first).
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}
    #: The device resource reads no topic: /gazebo/model_states is published only while the world runs, and a
    #: resource that waited for it would fail NOT_READY after every reset and delay every command by its timeout.
    #: The model states stay the explicit read capability above.

    def make_bridge(self, native):
        return _SentValues(super().make_bridge(native))

    #: The fake is a ROS-free, event-driven transport with canned model state;
    #: it runs no Gazebo, no physics and no controller.
    fidelity = {
        "engine": "analytic:ROS-free protocol fake (no Gazebo physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned ModelStates replies; no physics step, controller loop or "
                     "state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free protocol transport: it answers the /gazebo/model_states subscription, "
            "the ten MotorCmd publications and the two companion Gazebo services but runs no Gazebo, joint "
            "controllers, contacts, sensors or the hector_control walking loop",
            "the model names, poses and twists are placeholders and the pose nudge after a command is a "
            "canned effect, not simulated physics",
            "the package does not bind the per-joint MotorState publishers because the clone composes "
            "those names at run time; joint position/velocity feedback is not exposed",
            "the stop is the companion gazebo_ros world pause: the fake keeps a paused flag that "
            "/gazebo/pause_physics sets and /gazebo/get_physics_properties reports, and it does not serve "
            "/gazebo/unpause_physics; it runs no Gazebo World::Step or gazebo_ros_control update, and its "
            "GetPhysicsProperties numbers are placeholders; the BRAKE mode and the optional unitree_gazebo servo "
            "node are not safe-state bindings",
            "while paused, a live Gazebo runs no world update, so gazebo_ros_control applies no torque and "
            "/gazebo/model_states and /clock are silent; the fake silences /gazebo/model_states while its flag is "
            "set, and the device resource reads no topic (the MotorCmd receipts report the values they sent)",
            "a live world can be unpaused or stepped by the Gazebo GUI that biped.launch opens by default, by a "
            "WorldControl message or by any ROS client; MHS does not watch the flag after the e-stop",
            "the read-back needs the ODE engine (empty_world.launch's default): with another engine "
            "get_physics_properties returns false and the e-stop stays unconfirmed with the latch held; a graph "
            "without gazebo_ros has neither service",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.9.3 (Noetic) and 11 releases the companion "
            "citations name; rosbridge cannot read their versions",
            "no unpause is offered (SAFE-042): the joint controllers keep their stored MotorCmd "
            "(joint_controller.cpp:33-45) and apply it in update (139-185); the package cannot clear it first. "
            "BRAKE (158-164) sets zero position stiffness, zero velocity, damping 20 and zero torque, so it removes "
            "the position stiffness and applies damping only. A PMSM command sets the position target it names "
            "(142-145), and the package reads no joint position. starting() (117-129) holds the current position "
            "with zero velocity and torque, but gazebo_ros_control calls the controller manager only from its "
            "world-update hook (gazebo_ros_control_plugin.cpp:196-199, 251), and World::Step does not run that "
            "hook while paused (World.cc:835-854). When hector_ctrl runs, the main loop calls CheatIO::sendRecv "
            "(main.cpp:80-83; ros::Rate(1000) at main.cpp:41) and sendCmd publishes all ten MotorCmd messages "
            "with mode forced to 0x0A (CheatIO.cpp:34-36, 44-58). The FSM loop (main.cpp:22-30) is a different "
            "thread. GazeboRosControlPlugin::Reset (260-266) clears timing, not lastCmd. The constructor "
            "zeros lastCmd (joint_controller.cpp:15-18) and biped.launch starts paused (biped.launch:7). "
            "ShutDown on SIGINT sets running false (main.cpp:16-20, 78); the README's ctrl+\\ (Readme.md:68) "
            "is SIGQUIT and is not that handler. After mhs.safety.reset the world stays paused; the operator "
            "stops hector_ctrl, relaunches biped.launch and presses the simulator start button outside MHS "
            "(Readme.md:61-68)",
            "while hector_ctrl runs (the README's operator step), the main loop calls CheatIO::sendRecv "
            "(main.cpp:80-83) and sendCmd publishes all ten MotorCmd topics with mode forced to 0x0A "
            "(CheatIO.cpp:44-58), so an MHS publication is overwritten by the controller's next message; "
            "the bound topics have a competing publisher",
            "the xacro's velocity_max values are the URDF velocity limits that the joint controller clamps dq "
            "to in rad/s (21, and 14 for the calves; joint_controller.cpp:149-150, 216-220); the author's "
            "plus or minus 21 deg/s bound was a unit error, and velocity and torque are now operator_required "
            "because the clone shows no negative bound",
            "biped.launch starts Gazebo paused by default (biped.launch:7-19) and the README has the operator "
            "press start, so the stopped state is also the start state; while physics is paused "
            "/gazebo/model_states is silent (and, on simulated time, the 1 kHz controller loop waits), so the "
            "explicit model-state read fails NOT_READY after its timeout; the device resource no longer reads it",
        ],
    }
