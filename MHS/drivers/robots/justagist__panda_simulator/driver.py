"""OpenMHS rosbridge driver for the gh.justagist/panda_simulator Franka Hand gripper.

The pinned repository is a ROS 1 Gazebo simulator for the Franka Emika
Panda.  This package serves the simulated Franka Hand gripper through the
``PandaGripperController`` that ``panda_sim_controllers.launch`` spawns.  Its
C++ constructor creates four ``franka_gripper`` action servers on the absolute
names ``/franka_gripper/homing``, ``/franka_gripper/stop``,
``/franka_gripper/move`` and ``/franka_gripper/grasp``; with the shipped
controller configuration it publishes latched ``sensor_msgs/JointState`` on
``/franka_gripper/joint_states``.

The served actions are ``move``, ``grasp`` and the fixed, input-free
``stop`` action, the native e-stop and safe-state action.  The stop handler
writes a hold of the measured opening with a zero speed target into the
controller's command buffers and acknowledges success before the controller
applies it at its next command update.  A move or grasp goal that is still
running ignores the stop and cancellation and keeps waiting for up to 5 s of
ROS time, so an e-stop during it stays unconfirmed
(``MHS.SAFETY.SAFE_STATE_UNREACHED``, latch held) until that goal ends.  The
``homing`` action is not bound: the pinned handler only logs that homing is not
implemented for the simulator and sets no goal status itself.

The arm's seven-joint trajectory interface is NOT COVERED.  The pinned clone
exposes no acknowledged arm stop service or fixed arm stop action, so a
whole-arm driver cannot satisfy the runtime e-stop contract without inventing
a stop.  The gripper is served because its upstream StopAction is an
acknowledged stop of the simulated gripper.

The endpoint names are those of franka_ros's real ``franka_gripper`` node
(franka_ros is listed in ``dependencies.rosinstall`` and is not part of the
clone): pointed at a real Franka ROS graph, these bindings would drive the real
hand.

This is a configuration-only :class:`RosDriver`; it declares no Python native
class and starts no ROS node, simulator or rosbridge.  Every endpoint, type,
fact and operator-required reason cites the pinned clone at
6cec91dcc739df105a845e2f29e361b6c608bb48.  The fake is an analytic ROS-free
stand-in, not a recording of captured traffic.  No hardware or live ROS run is
claimed.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The controller spawner loads the gripper controller configuration and
#: spawns panda_simulator/panda_gripper_controller when the gripper is loaded.
_LAUNCH_REF = "panda_sim_controllers/launch/panda_sim_controllers.launch:29-34"
_CONFIG_REF = "panda_sim_controllers/config/panda_gripper_controller.yaml:2-12"

#: The four action server initializations and their generated type includes.
_ACTION_SERVER_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:38-58"
_MOVE_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:51-53"
_MOVE_TYPE_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:30"
_GRASP_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:54-56"
_GRASP_TYPE_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:28"
_STOP_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:48-50"
_STOP_TYPE_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:31"

#: The state publisher (both branches) and the timer callback that fills it.
_STATE_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:153-164"
_STATE_FILL_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:170-185"

#: The move, grasp, stop and homing handlers, and the command path they feed.
_MOVE_BEHAVIOR_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:228-262"
_GRASP_BEHAVIOR_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:292-325"
_STOP_BEHAVIOR_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:273-288"
_HOMING_BEHAVIOR_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:269-271"
_UPDATE_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:187-225"
_FINGER_PID_REF = "panda_sim_controllers/src/panda_joint_position_controller.cpp:202-253"

#: The simulator's configurable gripper defaults; they are parameters, not bounds.
_DEFAULTS_REF = "panda_gazebo/config/robot_details.yaml:74-81"
_DEFAULT_READ_REF = "panda_sim_controllers/src/panda_gripper_controller.cpp:141-144"

#: The default world launch and the GripperCommand emulator it starts.
_WORLD_LAUNCH = "panda_gazebo/launch/panda_world.launch"
_GRIPPER_EMULATOR = "panda_sim_custom_action_server/src/panda_sim_custom_action_server/gripper_action_server.py"

_WIDTH_LIMIT = Limit.operator_required(
    "the clone clamps the finger command to the URDF joint limits (panda_gripper_controller.cpp:231-236) "
    "but states no numeric opening range; an operator supplies the installed hand's opening bound"
)
_SPEED_LIMIT = Limit.operator_required(
    "the clone clamps the finger speed to the URDF velocity limit (panda_gripper_controller.cpp:234-236) "
    "and the 0.1 m/s default_speed is a configurable ROS parameter, not a device bound; an operator "
    "supplies the site speed bound"
)

_SUCCESS = Field("boolean", description="True when the upstream action acknowledged success")

_MOVE = {
    "action": "/franka_gripper/move",
    "type": "franka_gripper/MoveAction",
    "profile": "ros1-actionlib",
    "source_name": "/franka_gripper/move",
    "source_ref": _MOVE_REF,
    "type_ref": _MOVE_TYPE_REF,
    "request": {},
    "args": {
        "width": {"from": "input.width"},
        "speed": {"from": "input.speed"},
    },
    "result": {"map": {"success": "success"}},
    "success": {"path": "success", "equals": True},
    "timeout_ms": 10000,
}

_GRASP = {
    "action": "/franka_gripper/grasp",
    "type": "franka_gripper/GraspAction",
    "profile": "ros1-actionlib",
    "source_name": "/franka_gripper/grasp",
    "source_ref": _GRASP_REF,
    "type_ref": _GRASP_TYPE_REF,
    # The pinned grasp callback uses only width and speed; force and epsilon are
    # required goal fields but are ignored by the C++ handler, so fixed zeroes
    # keep the request shape valid without inventing a force bound.
    "request": {"force": 0.0, "epsilon": {"inner": 0.0, "outer": 0.0}},
    "args": {
        "width": {"from": "input.width"},
        "speed": {"from": "input.speed"},
    },
    "result": {"map": {"success": "success"}},
    "success": {"path": "success", "equals": True},
    "timeout_ms": 10000,
}

_STOP = {
    "action": "/franka_gripper/stop",
    "type": "franka_gripper/StopAction",
    "profile": "ros1-actionlib",
    "source_name": "/franka_gripper/stop",
    "source_ref": _STOP_REF,
    "type_ref": _STOP_TYPE_REF,
    "request": {},
    "result": {"map": {"success": "success"}},
    "success": {"path": "success", "equals": True},
    "timeout_ms": 5000,
}

_FINGER_POSITIONS_READ = {
    "topic": "/franka_gripper/joint_states",
    "type": "sensor_msgs/JointState",
    "source_name": "/franka_gripper/joint_states",
    "source_ref": _STATE_REF,
    "type_ref": _STATE_REF,
    "path": "position",
}


class PandaGripper(RosDriver):
    device_id = "panda-gripper"
    device_kind = "robot.gripper"
    mode = "simulated"
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakePandaSimulator"}
    tags = ["ros", "ros1", "gazebo", "franka", "panda", "gripper", "simulation"]
    display_name = "Franka Emika Panda simulated hand"
    vendor = "justagist"
    model = "panda_simulator"
    facts = [
        Fact("The controllers launch loads the gripper controller configuration and spawns "
             "panda_simulator/panda_gripper_controller when load_gripper is true.",
             source="upstream_code", ref=_LAUNCH_REF),
        Fact("The gripper controller configuration uses type "
             "panda_sim_controllers/PandaGripperController, the pub_topic "
             "/franka_gripper/joint_states and the two finger joints panda_finger_joint1 and "
             "panda_finger_joint2.", source="upstream_code", ref=_CONFIG_REF),
        Fact("The controller constructor initializes the homing, stop, move and grasp action servers on "
             "/franka_gripper/homing, /franka_gripper/stop, /franka_gripper/move and "
             "/franka_gripper/grasp.", source="upstream_code", ref=_ACTION_SERVER_REF),
        Fact("init() starts the homing, stop, move and grasp action servers and creates a 0.1 s ROS timer "
             "that calls timerUpdate.", source="upstream_code",
             ref="panda_sim_controllers/src/panda_gripper_controller.cpp:146-166"),
        Fact("The controller includes franka_gripper/GraspAction.h, HomingAction.h, MoveAction.h and "
             "StopAction.h.", source="upstream_code",
             ref="panda_sim_controllers/src/panda_gripper_controller.cpp:28-31"),
        Fact("init() advertises sensor_msgs/JointState with queue size 1 and latch true on the pub_topic "
             "parameter through the private node handle when pub_topic is set, and otherwise on the absolute "
             "/franka_gripper/joint_states.", source="upstream_code", ref=_STATE_REF),
        Fact("timerUpdate copies the two finger positions into the JointState message, sets zero velocities "
             "and zero efforts, sets no header field and publishes it.",
             source="upstream_code", ref=_STATE_FILL_REF),
        Fact("The move handler clamps width/2 to the main finger joint's URDF lower and upper limits and the "
             "speed to plus or minus its URDF velocity limit, writes both command buffers, sets new_command_, "
             "then loops without sleeping for up to 5 s of ros::Time until the sum of the two absolute finger "
             "positions is within 0.01 of the goal width, and sets the goal succeeded or, on timeout, aborted.",
             source="upstream_code", ref=_MOVE_BEHAVIOR_REF),
        Fact("The grasp handler applies the same clamping, command-buffer writes and 5 s ros::Time wait as "
             "move, reads only the goal's width and speed (not force or epsilon), and sets the goal succeeded "
             "or aborted.", source="upstream_code", ref=_GRASP_BEHAVIOR_REF),
        Fact("The stop handler sets the position command buffer to half the sum of the two absolute measured "
             "finger positions and the speed command buffer to 0.0, sets new_command_, and then sets the goal "
             "succeeded with success true without any condition.",
             source="upstream_code", ref=_STOP_BEHAVIOR_REF),
        Fact("update() calls updateCommands() on every fifth call and updates both finger controllers on "
             "every call; updateCommands() returns at once unless new_command_ is set, and otherwise applies "
             "the buffered position and speed to the main finger and the URDF mimic multiplier and offset to "
             "the other finger.", source="upstream_code", ref=_UPDATE_REF),
        Fact("Each finger's JointPositionController computes its effort command on every update from the "
             "position error and, when the command carries a velocity, from the difference between that "
             "velocity and the joint velocity.", source="upstream_code", ref=_FINGER_PID_REF),
        Fact("The homing handler only logs 'Homing not implemented for simulator.' and sets no goal status "
             "itself.", source="upstream_code", ref=_HOMING_BEHAVIOR_REF),
        Fact("The move wait loop compares ros::Time::now() minus its start time with the 5 s timeout and "
             "the measured width with the goal width, and contains no is_preempt_requested check.",
             source="upstream_code", ref="panda_sim_controllers/src/panda_gripper_controller.cpp:242-258"),
        Fact("The grasp wait loop compares ros::Time::now() minus its start time with the 5 s timeout and "
             "the measured width with the goal width, and contains no is_preempt_requested check.",
             source="upstream_code", ref="panda_sim_controllers/src/panda_gripper_controller.cpp:306-321"),
        Fact("The simulator configuration declares default_speed 0.1 m/s and default_grasp_epsilon "
             "inner/outer 0.005 m.", source="upstream_code", ref=_DEFAULTS_REF),
        Fact("init() reads the default_speed parameter into a local variable initialized to 0.1 and logs it "
             "when the parameter is found.", source="upstream_code", ref=_DEFAULT_READ_REF),
        Fact("panda_world.launch declares load_gripper and use_custom_action_servers with default true.",
             source="upstream_code", ref=_WORLD_LAUNCH + ":5-6"),
        Fact("panda_world.launch declares use_sim_time with default true.",
             source="upstream_code", ref=_WORLD_LAUNCH + ":12"),
        Fact("panda_world.launch starts start_gripper_action_server.py as gripper_action_server_emulator when "
             "use_custom_action_servers and load_gripper are true.",
             source="upstream_code", ref=_WORLD_LAUNCH + ":76-81"),
        Fact("GripperActionServer serves control_msgs GripperCommandAction on the relative name "
             "franka_gripper/gripper_action and creates a franka_interface.GripperInterface for "
             "panda_finger_joint1 and panda_finger_joint2.",
             source="upstream_code", ref=_GRIPPER_EMULATOR + ":36-57"),
        Fact("While a GripperCommand goal runs, its callback calls GripperInterface.move_joints with twice the "
             "goal position at a 20 Hz rospy.Rate until the first finger reaches the goal, a preemption is "
             "requested or the timeout passes.", source="upstream_code", ref=_GRIPPER_EMULATOR + ":75-117"),
    ]
    safe_state = (
        "The /franka_gripper/stop action buffers a hold of the measured opening (half the sum of the absolute "
        "finger positions, zero speed target) and acknowledges success before the controller's next command "
        "update applies it; the finger PIDs then hold that opening while Gazebo and the arm keep running, a "
        "move or grasp goal still running ignores the stop for up to 5 s of ROS time (leaving the e-stop "
        "unconfirmed, latch held), and a later move or grasp goal from any ROS client replaces the hold."
    )
    #: The analytic fake is a ROS-free stand-in: no Gazebo, ros_control, franka_interface or physics.
    fidelity = {
        "engine": "analytic:ROS-free rosbridge stand-in (no Gazebo physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven ROS-free stand-in with no physics step or wall-clock pacing; its finger "
                     "positions and action results are placeholders, not captured traffic",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic ROS-free stand-in built on RecordingRosTransport: it answers the declared "
            "gripper action and joint-state wire traffic but runs no Gazebo, ros_control, franka_interface or "
            "physics",
            "the fake's finger positions and action results are placeholders; a successful move or grasp sets "
            "both placeholder finger positions to width/2 immediately, while the upstream handler waits up to "
            "5 s of ROS time and clamps to the URDF limits",
            "the upstream grasp handler ignores force and epsilon; the driver sends fixed zero values for those "
            "required goal fields and exposes no force input",
            "the upstream homing handler sets no goal status itself and is not bound",
            "the arm's seven-joint trajectory action, joint-command topic, arm state topics and MoveIt "
            "integration are NOT COVERED; the pinned clone has no acknowledged arm stop binding",
            "the fake's stop result is synthesized; it does not prove physical quiescence or a hardware stop",
            "the move and grasp waits run on ros::Time, which panda_world.launch makes simulated time by "
            "default: while Gazebo is paused a running goal does not end, and below a real-time factor of 0.5 "
            "an unreached goal can outlast the 10 s binding timeout and end as an unknown outcome",
            "a running move or grasp goal ignores cancellation and the stop, so an e-stop during it reports "
            "MHS.SAFETY.SAFE_STATE_UNREACHED with the latch held until the goal ends (reviewer probe and the "
            "hold_goals test case); the fake otherwise answers every goal at once",
            "the hold lasts only until the next move or grasp goal: a goal another ROS client queued behind a "
            "running goal in the same action server, or the gripper_action_server_emulator that "
            "panda_world.launch starts by default (it re-commands the fingers at 20 Hz while its GripperCommand "
            "goal runs), replaces it; the MHS latch fences only this driver",
            "the four action servers start in init() and keep answering while a controller switch has stopped "
            "the gripper controller, when update() applies no finger command; a stop is then acknowledged "
            "without effect",
            "/franka_gripper/joint_states is latched and published by a ROS timer: while Gazebo is paused no new "
            "sample is published, so reads can wait and fail MHS.DEVICE.NOT_READY and each command then waits "
            "for the resource read (reviewer probe with a silent topic: 2 s); the JointState header is never set",
            "the endpoint names are those of franka_ros's real franka_gripper node (franka_ros is listed in "
            "dependencies.rosinstall and is not in the clone): against a real Franka graph these bindings "
            "would drive the real hand, including grasps with the fixed zero force and epsilon",
            "no ROS graph, Gazebo process, simulator run or hardware was executed or validated",
        ],
    }

    parameters = {
        "finger_positions": Field(
            "array",
            unit="m",
            length=2,
            items=Field("number", unit="m"),
            description="Two finger positions from /franka_gripper/joint_states in the controller's "
                        "main/mimic order; the total opening is not computed here",
        ),
    }
    reads = {
        "finger_positions": _FINGER_POSITIONS_READ,
    }
    commands = {
        "x-cap.justagist.move.v1": _MOVE,
        "x-cap.justagist.grasp.v1": _GRASP,
        "x-cap.justagist.stop.v1": _STOP,
    }
    actions = {
        "x-cap.justagist.move.v1": Action(
            name="move_gripper",
            verb="invoke",
            risk="R2",
            long_running=True,
            cancellable=False,
            max_duration_ms=10000,
            description=(
                "Send one franka_gripper/MoveAction goal with a finger opening and speed; the receipt reports "
                "the upstream action's terminal success, not a separately measured contact force"
            ),
            input={
                "width": Field("number", unit="m", description="Requested total finger opening",
                               limit=_WIDTH_LIMIT),
                "speed": Field("number", unit="m/s", description="Requested finger speed",
                               limit=_SPEED_LIMIT),
            },
            output={"success": _SUCCESS},
        ),
        "x-cap.justagist.grasp.v1": Action(
            name="grasp_gripper",
            verb="invoke",
            risk="R2",
            long_running=True,
            cancellable=False,
            max_duration_ms=10000,
            description=(
                "Send one franka_gripper/GraspAction goal; the pinned handler performs the same position move "
                "as MoveAction and ignores force and epsilon"
            ),
            input={
                "width": Field("number", unit="m", description="Requested total finger opening",
                               limit=_WIDTH_LIMIT),
                "speed": Field("number", unit="m/s", description="Requested finger speed",
                               limit=_SPEED_LIMIT),
            },
            output={"success": _SUCCESS},
        ),
        "x-cap.justagist.stop.v1": Action(
            name="stop_gripper",
            safe_state=True,
            verb="invoke",
            risk="R2",
            cancellable=False,
            max_duration_ms=5000,
            description=(
                "Fixed, input-free franka_gripper/StopAction request; the upstream handler buffers a hold of the "
                "measured opening at zero speed and acknowledges success before the controller applies it"
            ),
            output={"success": _SUCCESS},
        ),
    }
    # The upstream fixed StopAction is the native e-stop and safe-state action.
    safety_bindings = {"estop": _STOP}
