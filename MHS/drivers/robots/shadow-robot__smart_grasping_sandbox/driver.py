"""OpenMHS rosbridge driver for the Shadow Smart Grasping Sandbox (gh.shadow-robot/smart_grasping_sandbox).

The upstream is a ROS 1 Indigo / Gazebo 7 simulation world with a UR10 arm, a
Shadow H1 hand and a MoveIt configuration.  The repository ships a Python 2
``SmartGrasper`` helper but no importable Python 3 device class; the concrete
runtime interface is the ROS graph that the helper calls.  This package is a
configuration-only ``RosDriver`` over rosbridge, so it imports no ROS and
declares no Python native class.

The served scope is the simulation hold/resume and reset services, joint-state
and object-pose observation, and three fixed ``/gazebo/set_model_configuration``
requests: the 15-joint reset configuration of ``SmartGrasper.reset_world`` and
the SRDF ``open``/``close`` hand group states.  The upstream helper sets that
configuration only with its controllers stopped and physics paused, and it opens
and closes the hand by MoveIt planning and execution; this package sends the
configuration request alone, so the running trajectory controllers can drive the
joints back toward their held setpoints (model review).
``/gazebo/pause_physics`` is the simulator stop; it is declared as an
input-free safe-state action and as the native e-stop binding.  It is not a
physical emergency stop, it does not cancel a MoveIt plan or an external ROS
action client, any client can unpause (``SmartGrasper()`` does), and an
acknowledgement alone is not sensed quiescence.

Every endpoint, type and fact cites the pinned clone at
6f8de0600126bcbd38c38c1fcc8b97c6a868ad8d.  The fake transport is ROS-free; no
ROS graph, Gazebo process or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

_GRASPER = "smart_grasping_sandbox/src/smart_grasping_sandbox/smart_grasper.py"

#: std_srvs/Empty is imported by the helper for the Gazebo services.
_EMPTY_IMPORT = f"{_GRASPER}:5"

#: gazebo_msgs service types are imported together on the next two lines.
_GAZEBO_IMPORT = f"{_GRASPER}:6-7"

#: sensor_msgs/JointState is imported by the helper.
_JOINT_IMPORT = f"{_GRASPER}:16"

_URDF = "fh_desc/model.urdf"
_SIM_LAUNCH = "fh_desc/launch/launch_simulation.launch"

_PAUSE = {
    "service": "/gazebo/pause_physics",
    "type": "std_srvs/Empty",
    "source_ref": f"{_GRASPER}:52-53",
    "type_ref": _EMPTY_IMPORT,
    "success": {"path": "$", "equals": {}},
    "result": {"acknowledged": {"value": True}},
}

_UNPAUSE = {
    "service": "/gazebo/unpause_physics",
    "type": "std_srvs/Empty",
    "source_ref": f"{_GRASPER}:54-55",
    "type_ref": _EMPTY_IMPORT,
    "success": {"path": "$", "equals": {}},
    "result": {"acknowledged": {"value": True}},
}

_RESET_WORLD = {
    "service": "/gazebo/reset_world",
    "type": "std_srvs/Empty",
    "source_ref": f"{_GRASPER}:48-49",
    "type_ref": _EMPTY_IMPORT,
    "success": {"path": "$", "equals": {}},
    "result": {"acknowledged": {"value": True}},
}

#: The first six names are the UR10 arm group and the last nine are the H1 hand
#: group, in the order used by SmartGrasper.reset_world.  The positions are that
#: method's own reset configuration, not a catalogue default.
_HOME_JOINTS = [
    "shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint",
    "wrist_1_joint", "wrist_2_joint", "wrist_3_joint",
    "H1_F1J1", "H1_F1J2", "H1_F1J3",
    "H1_F2J1", "H1_F2J2", "H1_F2J3",
    "H1_F3J1", "H1_F3J2", "H1_F3J3",
]
_HOME_POSITIONS = [
    1.2, 0.3, -1.5, -0.5, -1.5, 0.0,
    0.0, -0.3, 0.0,
    0.0, -0.3, 0.0,
    0.0, -0.3, 0.0,
]

_HAND_JOINTS = [
    "H1_F1J1", "H1_F1J2", "H1_F1J3",
    "H1_F2J1", "H1_F2J2", "H1_F2J3",
    "H1_F3J1", "H1_F3J2", "H1_F3J3",
]
_HAND_OPEN = [0.0, -0.3, 0.0, 0.0, -0.3, 0.0, 0.0, -0.3, 0.0]
_HAND_CLOSE = [0.0, 0.25, 0.4, 0.0, 0.25, 0.4, 0.0, 0.25, 0.4]


def _set_configuration(joint_names, joint_positions):
    """A fixed gazebo_msgs/SetModelConfiguration request for the spawned model."""
    return {
        "service": "/gazebo/set_model_configuration",
        "type": "gazebo_msgs/SetModelConfiguration",
        "source_ref": f"{_GRASPER}:58-59",
        "type_ref": _GAZEBO_IMPORT,
        "request": {
            "model_name": "smart_grasping_sandbox",
            "urdf_param_name": "robot_description",
            "joint_names": list(joint_names),
            "joint_positions": list(joint_positions),
        },
        "success": {"path": "success", "equals": True},
        "result": {"map": {"applied": "success"}},
    }


class SmartGraspingSandbox(RosDriver):
    device_id = "smart_grasping_sandbox"
    device_kind = "robot.arm"
    mode = "simulated"
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeSmartGraspingSandbox"}
    tags = ["ros", "ros1", "simulation", "gazebo", "moveit", "ur10", "shadow-hand", "grasping"]
    display_name = "Shadow Smart Grasping Sandbox"
    vendor = "Shadow Robot Company"
    facts = [
        Fact("SmartGrasper subscribes to /joint_states as sensor_msgs/JointState with queue_size=1.",
             source="upstream_code", ref=f"{_GRASPER}:44-45"),
        Fact("SmartGrasper waits for /gazebo/get_model_state and proxies it with "
             "gazebo_msgs/GetModelState.", source="upstream_code", ref=f"{_GRASPER}:47-50"),
        Fact("get_object_pose returns the pose field obtained from /gazebo/get_model_state for the "
             "current model in the world frame.", source="upstream_code", ref=f"{_GRASPER}:115-120"),
        Fact("SmartGrasper waits for /gazebo/reset_world and proxies it with std_srvs/Empty.",
             source="upstream_code", ref=f"{_GRASPER}:48-49"),
        Fact("SmartGrasper waits for /gazebo/pause_physics and /gazebo/unpause_physics and proxies "
             "each with std_srvs/Empty.", source="upstream_code", ref=f"{_GRASPER}:52-55"),
        Fact("SmartGrasper waits for /gazebo/set_model_configuration and proxies it with "
             "gazebo_msgs/SetModelConfiguration.", source="upstream_code", ref=f"{_GRASPER}:58-59"),
        Fact("SmartGrasper.reset_world stops the hand, arm and joint_state controllers with BEST_EFFORT "
             "strictness, pauses physics, calls /gazebo/set_model_configuration, runs __start_ctrl on a "
             "zero-delay threading.Timer, sleeps 0.1 s, unpauses physics and calls /gazebo/reset_world, "
             "using none of the call results.", source="upstream_code", ref=f"{_GRASPER}:92-113"),
        Fact("__start_ctrl starts hand_controller, arm_controller and joint_state_controller through "
             "/controller_manager/switch_controller.", source="upstream_code", ref=f"{_GRASPER}:394-397"),
        Fact("The SmartGrasper constructor ends by calling reset_world.", source="upstream_code",
             ref=f"{_GRASPER}:86"),
        Fact("open_hand and close_hand set the MoveIt named targets open and close on the hand group, plan, "
             "and execute the plan.", source="upstream_code", ref=f"{_GRASPER}:209-229"),
        Fact("The reset configuration names the 15 joints shoulder_pan_joint, shoulder_lift_joint, "
             "elbow_joint, wrist_1_joint, wrist_2_joint, wrist_3_joint, H1_F1J1, H1_F1J2, H1_F1J3, "
             "H1_F2J1, H1_F2J2, H1_F2J3, H1_F3J1, H1_F3J2, H1_F3J3 and the positions 1.2, 0.3, -1.5, "
             "-0.5, -1.5, 0.0, 0.0, -0.3, 0.0, 0.0, -0.3, 0.0, 0.0, -0.3, 0.0.",
             source="upstream_code", ref=f"{_GRASPER}:97-100"),
        Fact("The MoveIt SRDF assigns the arm group six joints (shoulder_pan_joint through "
             "wrist_3_joint) and the hand group nine joints (H1_F1J1 through H1_F3J3).",
             source="upstream_code",
             ref="smart_grasp_moveit_config/config/ur10.srdf:12-30"),
        Fact("The MoveIt SRDF defines hand group state open with 0.0, -0.3, 0.0 for each finger and "
             "hand group state close with 0.0, 0.25, 0.4 for each finger.", source="upstream_code",
             ref="smart_grasp_moveit_config/config/ur10.srdf:32-53"),
        Fact("The launch file starts Gazebo from fh_desc/launch_simulation.launch, then MoveIt "
             "move_group, gazebo2rviz and optionally RViz.", source="upstream_code",
             ref="smart_grasping_sandbox/launch/smart_grasping_sandbox.launch:7-20"),
        Fact("The MoveIt controller list gazebo_controllers.yaml names arm_controller and hand_controller with "
             "follow_joint_trajectory action namespaces; the arm lists six joints and the hand nine.",
             source="upstream_code",
             ref="smart_grasp_moveit_config/config/gazebo_controllers.yaml:1-24"),
        Fact("SmartGrasper initializes its current model name to cricket_ball.",
             source="upstream_code", ref=f"{_GRASPER}:33-34"),
        Fact("The fh_desc launch sets the robot_description parameter and spawns the model as "
             "smart_grasping_sandbox with -param robot_description.",
             source="upstream_code", ref="fh_desc/launch/launch_simulation.launch:22-27"),
        Fact("The Docker base image is osrf/ros:indigo-desktop-full, a ROS 1 Indigo environment.",
             source="upstream_code", ref="docker/base/Dockerfile:1"),
        Fact("The helper uses Python 2 print statements (print fraction) at lines 370 and 390.",
             source="upstream_code", ref=f"{_GRASPER}:370-390"),
        Fact("The helper's header states 'Copyright (C) 2018 Shadow Robot Company Ltd - All Rights Reserved. "
             "Proprietary and Confidential.'", source="upstream_code", ref=f"{_GRASPER}:1-2"),
        Fact("The repository LICENSE file is the GNU General Public License, version 3.",
             source="upstream_code", ref="LICENSE:1-2"),
        Fact("The smart_grasping_sandbox package.xml declares the licence GPLv3.",
             source="upstream_code", ref="smart_grasping_sandbox/package.xml:9"),
        Fact("The six UR10 arm joints declare PositionJointInterface transmissions.",
             source="upstream_code", ref=f"{_URDF}:230-283"),
        Fact("The model loads libgazebo_ros_control with gazebo_ros_control/DefaultRobotHWSim.",
             source="upstream_code", ref=f"{_URDF}:329-333"),
        Fact("The hand joint H1_F1J1 declares an EffortJointInterface transmission.",
             source="upstream_code", ref=f"{_URDF}:531-539"),
        Fact("hand_controller is an effort_controllers/JointTrajectoryController over the nine hand joints.",
             source="upstream_code", ref="fh_desc/config/hand_H_gazebo_trajectory.yaml:21-22"),
        Fact("launch_simulation.launch defaults gui to true and paused to false.",
             source="upstream_code", ref=f"{_SIM_LAUNCH}:2-5"),
        Fact("launch_simulation.launch loads ur_gazebo's arm_controller_ur10.yaml, spawns arm_controller and "
             "spawns hand_controller.", source="upstream_code", ref=f"{_SIM_LAUNCH}:43-50"),
        Fact("The world declares ODE physics with gravity -9.81 and max_contacts 5.",
             source="upstream_code", ref="smart_grasping_sandbox/world/smart_grasping.world:6-12"),
    ]
    #: Model review: says what holds and what does not after the pause.
    safe_state = (
        "Gazebo physics is paused with /gazebo/pause_physics, so the simulated UR10 and H1 hand hold still "
        "while it stays paused; the arm and hand trajectory controllers keep their goals and resume them "
        "when any client unpauses (SmartGrasper() and its reset_world do, as does the Gazebo GUI), the pause "
        "cancels no MoveIt plan or action goal, and the acknowledgement is not sensed quiescence"
    )
    #: The fake is a ROS-free recording transport, not the Gazebo simulator.  It
    #: claims F0 only and has no physics, controller manager or MoveIt planner.
    fidelity = {
        "engine": "analytic:ROS contract fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven recording fake with placeholder observations and no physics step, "
                     "controller update or wall-clock pacing",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake answers only the declared Gazebo services and the /joint_states observation; it "
            "runs no Gazebo, ODE, ros_control, MoveIt, TF, camera or contact simulation",
            "the joint-state and object-pose payloads are placeholders and do not advance with the "
            "simulator; a live run must receive them from the operator's Gazebo world",
            "arbitrary Cartesian arm motion, MoveIt planning/execution, pick/place routines, object "
            "spawn/delete and collision-matrix changes are NOT COVERED; the static rosbridge mapping "
            "cannot express the nested MoveGroup constraints or the multi-step helper routines",
            "the fixed home and hand open/close commands use gazebo_msgs/SetModelConfiguration, which "
            "sets the named joints directly; they are not trajectory execution and do not move the "
            "arm around obstacles",
            "unlike SmartGrasper.reset_world, these commands neither stop the controllers nor pause physics "
            "around the request, so the running arm (position) and hand (effort) JointTrajectoryControllers "
            "can drive the joints back toward their held setpoints; applied reports only Gazebo's success "
            "flag, and the helper's own open_hand/close_hand use MoveIt planning instead",
            "/gazebo/pause_physics holds the simulation but does not cancel a pending MoveIt goal or an "
            "external ROS action client; a deployment must reconcile that native work separately",
            "any ROS client can resume physics: the Gazebo GUI (launched by default), SmartGrasper() and "
            "its reset_world call /gazebo/unpause_physics, and the controllers then continue their goals",
            "the controllers and joint_state_controller run inside Gazebo's update loop (gazebo_ros_control, "
            "outside the clone), so /joint_states can stop while physics is paused; the fake keeps answering",
            "mhs.safety.reset calls /gazebo/reset_world and this package does not unpause on reset; physics "
            "resumes only through unpause_physics or another client",
            "every binding uses the bridge's default 2 s service timeout; a Gazebo that answers later makes "
            "the call fail, and for the e-stop that means SAFE_STATE_UNREACHED with the latch held",
            "the upstream is ROS 1 Indigo with Python 2 helpers; this package is Python 3 and speaks "
            "only the rosbridge JSON wire protocol, so live operation requires a rosbridge endpoint in "
            "that deployment",
        ],
    }

    commands = {
        "x-cap.shadow-robot.pause_physics.v1": dict(_PAUSE),
        "x-cap.shadow-robot.unpause_physics.v1": dict(_UNPAUSE),
        "x-cap.shadow-robot.reset_world.v1": dict(_RESET_WORLD),
        "x-cap.shadow-robot.joint_states.v1": {
            "topic": "/joint_states",
            "type": "sensor_msgs/JointState",
            "source_ref": f"{_GRASPER}:44-45",
            "type_ref": _JOINT_IMPORT,
            "operation": "subscribe",
            "path": "$",
            "result": {"map": {
                "names": "name",
                "positions": "position",
                "velocities": "velocity",
                "efforts": "effort",
            }},
        },
        "x-cap.shadow-robot.object_pose.v1": {
            "service": "/gazebo/get_model_state",
            "type": "gazebo_msgs/GetModelState",
            "source_ref": f"{_GRASPER}:47-50",
            "type_ref": _GAZEBO_IMPORT,
            "operation": "read",
            "request": {"model_name": "cricket_ball", "relative_entity_name": "world"},
            "success": {"path": "success", "equals": True},
            "result": {"map": {"position": "pose.position", "orientation": "pose.orientation"}},
        },
        "x-cap.shadow-robot.home_configuration.v1": _set_configuration(_HOME_JOINTS, _HOME_POSITIONS),
        "x-cap.shadow-robot.hand_open.v1": _set_configuration(_HAND_JOINTS, _HAND_OPEN),
        "x-cap.shadow-robot.hand_close.v1": _set_configuration(_HAND_JOINTS, _HAND_CLOSE),
    }
    actions = {
        "x-cap.shadow-robot.pause_physics.v1": Action(
            name="pause_physics",
            verb="invoke",
            safe_state=True,
            description="Pause the Gazebo simulation through /gazebo/pause_physics",
            output={"acknowledged": Field("boolean",
                                          description="True when the pause service acknowledged the request")},
        ),
        "x-cap.shadow-robot.unpause_physics.v1": Action(
            name="unpause_physics",
            verb="invoke",
            description="Resume the Gazebo simulation through /gazebo/unpause_physics",
            output={"acknowledged": Field("boolean",
                                          description="True when the unpause service acknowledged the request")},
        ),
        "x-cap.shadow-robot.reset_world.v1": Action(
            name="reset_world",
            verb="invoke",
            description="Reset the Gazebo world through /gazebo/reset_world",
            output={"acknowledged": Field("boolean",
                                          description="True when the reset service acknowledged the request")},
        ),
        "x-cap.shadow-robot.joint_states.v1": Action(
            name="read_joint_states",
            verb="read",
            description="Read one fresh /joint_states sample",
            output={
                "names": Field("array", items=Field("string"),
                               description="Joint names in message order"),
                "positions": Field("array", items=Field("number", unit="rad"),
                                   description="Joint positions in radians"),
                "velocities": Field("array", items=Field("number", unit="rad/s"),
                                    description="Joint velocities in radians per second"),
                "efforts": Field("array", items=Field("number", unit="N.m"),
                                 description="Joint efforts in newton metres"),
            },
        ),
        "x-cap.shadow-robot.object_pose.v1": Action(
            name="read_object_pose",
            verb="read",
            description="Read the current cricket_ball pose from /gazebo/get_model_state",
            output={
                "position": Field("object", description="Object position in the world frame",
                                  properties={
                                      "x": Field("number", unit="m"),
                                      "y": Field("number", unit="m"),
                                      "z": Field("number", unit="m"),
                                  }),
                "orientation": Field("object", description="Object orientation quaternion in the world frame",
                                     properties={
                                         "x": Field("number", unit="1"),
                                         "y": Field("number", unit="1"),
                                         "z": Field("number", unit="1"),
                                         "w": Field("number", unit="1"),
                                     }),
            },
        ),
        "x-cap.shadow-robot.home_configuration.v1": Action(
            name="home_configuration",
            verb="invoke",
            description=("Teleport the 15 UR10 and H1 joints to SmartGrasper.reset_world's fixed configuration "
                         "through /gazebo/set_model_configuration, without stopping the controllers or pausing "
                         "physics as reset_world does, so the running controllers can drive the joints back"),
            output={"applied": Field("boolean",
                                     description="True when /gazebo/set_model_configuration reported success")},
        ),
        "x-cap.shadow-robot.hand_open.v1": Action(
            name="open_hand",
            verb="invoke",
            description=("Teleport the nine H1 hand joints to the SRDF open group state through "
                         "/gazebo/set_model_configuration; the running hand controller can drive them back"),
            output={"applied": Field("boolean",
                                     description="True when /gazebo/set_model_configuration reported success")},
        ),
        "x-cap.shadow-robot.hand_close.v1": Action(
            name="close_hand",
            verb="invoke",
            description=("Teleport the nine H1 hand joints to the SRDF close group state through "
                         "/gazebo/set_model_configuration; the running hand controller can drive them back"),
            output={"applied": Field("boolean",
                                     description="True when /gazebo/set_model_configuration reported success")},
        ),
    }
    safety_bindings = {
        "estop": {
            "service": "/gazebo/pause_physics",
            "type": "std_srvs/Empty",
            "source_ref": f"{_GRASPER}:52-53",
            "type_ref": _EMPTY_IMPORT,
            "success": {"path": "$", "equals": {}},
        },
        "reset": {
            "service": "/gazebo/reset_world",
            "type": "std_srvs/Empty",
            "source_ref": f"{_GRASPER}:48-49",
            "type_ref": _EMPTY_IMPORT,
            "success": {"path": "$", "equals": {}},
        },
    }
