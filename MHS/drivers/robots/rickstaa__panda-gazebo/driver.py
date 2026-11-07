"""Source-backed ROS 1 driver for the pinned panda_gazebo Gazebo simulation.

The upstream ``panda_control_server`` wraps the Franka arm trajectory
controller and the gripper action client.  This package is a configuration-only
:class:`RosDriver` over rosbridge; it declares no Python native class, does not
import ROS, start Gazebo or launch the simulator.

The primary motion path is the wrapper's ROS 1 action
``/panda_control_server/panda_arm/follow_joint_trajectory`` (type
``panda_gazebo/FollowJointTrajectoryAction``), which forwards a
``trajectory_msgs/JointTrajectory`` to the simulated
``panda_arm_trajectory_controller`` and reports its terminal ``error_code``.
The hand path is the wrapper service
``/panda_control_server/panda_hand/set_gripper_width``.  The fixed safe-state
path is the Gazebo world plugin's ``/lock_unlock_panda_joints`` service, which
sets every Panda joint's lower and upper limit to its present position; it is
a simulated joint-limit freeze, not a measured zero-velocity state, and it
reports success only after the limit update.

The pinned control server's preempt callback cancels the forwarded goal and
immediately marks the wrapper goal preempted; that acknowledgement is not
evidence that the trajectory controller has stopped.  The lock service is the
independent simulated stop and is re-issued by the runtime after a terminal
action result.  No physical e-stop is claimed, and no hardware run has run.

The lock is not undone by this package: it declares no unlock, and every lock
request makes the plugin store the joint's present (already locked) limits as
the limits an unlock restores.  The runtime sends the lock more than once per
stop or cancellation, so after the first stop the simulated arm stays frozen
until the model is respawned or Gazebo restarts.

Every endpoint, type and fact cites the pinned clone at
113df8afa8de6c4342a99d3eb33b05084da644b9.  The fake transport is ROS-free and
F0; it replays the wire shapes with placeholder values and runs no Gazebo,
controller, MoveIt, physics or ROS graph.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: Module docstring lists the wrapper action and gripper service names.
_ACTION_NAME_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:17"
_GRIPPER_NAME_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:14"

#: The imports that establish the generated message and service types.
_TYPE_IMPORT_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:56"
_GRIPPER_TYPE_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:1458"
_JOINT_STATE_TYPE_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:40"

#: The action server is constructed on the node's relative name.
_ACTION_SERVER_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:376-386"

#: The forwarded goal goes to an action client on the controller's relative
#: action name.
_TRAJ_CLIENT_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:341-348"

#: The wrapper forwards the goal, waits with goal.timeout, and maps the
#: controller's terminal result.
_ACTION_FORWARD_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:1585-1610"

#: The preempt callback cancels the forwarded goal and immediately marks the
#: wrapper goal preempted, without waiting for a terminal controller result.
_PREEMPT_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:1624-1636"

#: The custom action declares its goal fields, timeout semantics and terminal
#: fields.
_ACTION_DECL_REF = "panda_gazebo/action/FollowJointTrajectory.action:5-58"

#: The gripper callback halves the requested width and clips the finger target
#: to [0, 0.08] m before sending the gripper action.
_GRIPPER_CLIP_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:1466-1472"

#: The clipped value becomes the GripperCommandGoal position, and the goal is
#: sent to the gripper action client.
_GRIPPER_GOAL_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:1466-1488"

#: The gripper callback waits only when the request says so, using the request
#: timeout; otherwise it reports the goal as sent.
_GRIPPER_WAIT_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:1486-1509"

#: The service request declares width, grasping, max_effort, wait and timeout.
_GRIPPER_DECL_REF = "panda_gazebo/srv/SetGripperWidth.srv:1-12"

#: The arm and hand joint names are stated in this order.
_JOINT_NAMES_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:79-90"

#: The joint-state subscriber is relative "joint_states".
_JOINT_STATE_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:317-320"

#: The Gazebo world plugin's absolute service-name constant.
_LOCK_SERVICE_REF = "panda_gazebo/src/panda_joint_locker_world_plugin.cpp:13"

#: Load advertises that constant on the plugin's node handle.
_LOCK_ADVERTISE_REF = "panda_gazebo/src/panda_joint_locker_world_plugin.cpp:47-51"

#: The callback refuses a missing model or joint without undoing the joints it
#: has already handled in the loop.
_LOCK_MISSING_REF = "panda_gazebo/src/panda_joint_locker_world_plugin.cpp:73-113"

#: Lock stores the present limits and sets both to the current position; unlock
#: restores the stored limits; both then report success.
_LOCK_BODY_REF = "panda_gazebo/src/panda_joint_locker_world_plugin.cpp:93-117"

#: The service fields are joint_names, lock, success and message.
_LOCK_DECL_REF = "panda_gazebo/srv/LockJoints.srv:1-6"

#: The locker plugin is loaded by the shipped world and the launch starts with
#: empty.world by default.
_WORLD_REF = "panda_gazebo/resources/worlds/empty.world:20-21"

#: The empty world and the trajectory control mode are the launch defaults; the
#: trajectory mode enables the wrapper action and disables the combined
#: set_joint_commands service.
_CONTROL_DEFAULT_REF = "panda_gazebo/launch/start_simulation.launch:7-15"
_CONTROL_SWITCH_REF = "panda_gazebo/launch/put_robot_in_world.launch:90-97"

#: The gripper force note in the server states the Panda force range.
_FORCE_NOTE_REF = "panda_gazebo/src/panda_gazebo/core/control_server.py:73-74"

#: The package's declared licence.
_LICENSE_REF = "panda_gazebo/package.xml:13"

_ARM_JOINTS = [
    "panda_joint1",
    "panda_joint2",
    "panda_joint3",
    "panda_joint4",
    "panda_joint5",
    "panda_joint6",
    "panda_joint7",
]
_ALL_JOINTS = _ARM_JOINTS + ["panda_finger_joint1", "panda_finger_joint2"]

#: The upstream callback takes the total gripper width, halves it and clips the
#: finger target to [0, 0.08] m, twice the finger travel the clone states
#: elsewhere (0.0 to 0.04 m in load_panda_joint_limits).  The binding accepts the
#: per-finger target and sends twice that value; the bound is the clone's finger
#: joint limit, not the over-wide clip (reviewer correction).
_FINGER_LIMITS_REF = "panda_gazebo/src/panda_gazebo/common/helpers.py:613-621"
_FINGER_WIDTH_LIMIT = Limit(
    min=0,
    max=0.04,
    unit="m",
    source="upstream_code",
    ref=_FINGER_LIMITS_REF,
    reason="the clone's finger joint limits are 0.0 to 0.04 m",
)

#: The clone's force comment states continuous force 70 N and maximum force
#: 140 N for the Panda.  The wrapper does not clamp to it; this is a cited
#: device bound and the runtime refuses a larger request before the service.
_GRASP_FORCE_LIMIT = Limit(
    min=0,
    max=140,
    unit="N",
    source="upstream_code",
    ref=_FORCE_NOTE_REF,
    reason="the server comment states continuous force 70 N and max_force 140 N",
)

_JOINT_POSITION_LIMIT = Limit.operator_required(
    "the pinned control_server loads arm joint limits from the ROS parameter server and the panda "
    "joint_limits.yaml lives in the franka_ros submodule, which is not part of the pinned top-level "
    "commit; the operator supplies the reviewed joint travel range"
)
_TIME_AXIS_LIMIT = Limit.operator_required(
    "the clone states no bound for the automatically generated trajectory time step; the operator supplies "
    "the reviewed motion timing"
)
_TIMEOUT_LIMIT = Limit.operator_required(
    "the action's timeout of 0 waits indefinitely; the operator supplies a bounded execution timeout"
)

_GRIPPER_COMMAND = {
    "service": "/panda_control_server/panda_hand/set_gripper_width",
    "type": "panda_gazebo/SetGripperWidth",
    "source_name": "panda_hand/set_gripper_width",
    "source_ref": _GRIPPER_NAME_REF,
    "type_ref": _GRIPPER_TYPE_REF,
    "request": {"grasping": True, "wait": False},
    "args": {
        "width": {"from": "input.finger_width", "scale": 2.0},
        "max_effort": {"from": "input.force"},
    },
    "success": {"path": "success", "equals": True},
    "result": {"map": {"accepted": "success", "message": "message"}},
}

_TRAJECTORY_POINT = Field(
    "object",
    description="One FollowJointTrajectory waypoint",
    properties={
        "positions": Field(
            "array",
            unit="rad",
            length=7,
            description="Seven arm joint positions in panda_joint1..panda_joint7 order",
            items=Field("number", unit="rad", description="One arm joint angle in radians"),
            limit=_JOINT_POSITION_LIMIT,
        ),
    },
)

_TRAJECTORY_ACTION = {
    "action": "/panda_control_server/panda_arm/follow_joint_trajectory",
    "type": "panda_gazebo/FollowJointTrajectoryAction",
    "profile": "ros1-actionlib",
    "source_name": "panda_arm/follow_joint_trajectory",
    "source_ref": _ACTION_NAME_REF,
    "type_ref": _TYPE_IMPORT_REF,
    "request": {
        "trajectory": {"joint_names": _ARM_JOINTS, "points": []},
        "create_time_axis": True,
        "timeout": {"secs": 0, "nsecs": 0},
    },
    "args": {
        "trajectory.points": {"from": "input.points"},
        "time_axis_step": {"from": "input.time_axis_step"},
        "timeout.secs": {"from": "input.timeout_s", "type": "integer"},
    },
    "success": {"path": "error_code", "equals": 0},
    "result": {"map": {"error_code": "error_code", "error_string": "error_string"}},
}

_LOCK_COMMAND = {
    "service": "/lock_unlock_panda_joints",
    "type": "panda_gazebo/LockJoints",
    "source_ref": _LOCK_SERVICE_REF,
    "type_ref": "panda_gazebo/src/panda_joint_locker_world_plugin.cpp:8",
    "request": {"joint_names": _ALL_JOINTS, "lock": True},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"locked": "success", "message": "message"}},
}

_JOINT_STATE_FIELD = Field(
    "object",
    description=(
        "One sensor_msgs/JointState sample from /joint_states in publisher order. The name, position, "
        "velocity and effort arrays are parallel. Arm joints use rad, rad/s and N.m; when the finger joints "
        "are present, their position and velocity use metres and metres per second."
    ),
    properties={
        "name": Field("array", description="Joint names in publisher order",
                      items=Field("string", description="One joint name")),
        "position": Field("array", description="Joint positions in publisher order",
                          items=Field("number", description="One joint position; unit depends on the joint")),
        "velocity": Field("array", description="Joint velocities in publisher order",
                          items=Field("number", description="One joint velocity; unit depends on the joint")),
        "effort": Field("array", description="Joint efforts in publisher order",
                        items=Field("number", description="One joint effort")),
    },
)

_JOINT_STATE_READ = {
    "topic": "/joint_states",
    "type": "sensor_msgs/JointState",
    "source_name": "joint_states",
    "source_ref": _JOINT_STATE_REF,
    "type_ref": _JOINT_STATE_TYPE_REF,
    "path": "$",
}


class PandaGazebo(RosDriver):
    device_id = "panda_gazebo"
    device_kind = "robot.arm"
    mode = "simulated"
    #: A moving robot arm is at least R2 even when the only backend exercised
    #: here is the F0 recording fake.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakePandaGazebo"}
    tags = ["ros", "ros1", "gazebo", "simulation", "panda", "franka", "arm", "trajectory", "gripper"]
    display_name = "Panda Gazebo arm"
    vendor = "Rick Staa"
    model = "Panda Emika Franka"
    facts = [
        Fact("The README describes a ROS Noetic package for a Panda Emika Franka Gazebo simulation that wraps "
             "the franka_ros and panda_moveit_config packages.",
             source="vendor_doc", ref="README.md:7-11"),
        Fact("start_simulation.launch defaults the world to empty.world and control_type to trajectory.",
             source="upstream_code", ref=_CONTROL_DEFAULT_REF),
        Fact("The launch starts a node named panda_control_server and, for trajectory control, loads the "
             "arm follow-joint-trajectory action instead of the set_joint_commands service.",
             source="upstream_code", ref=_CONTROL_SWITCH_REF),
        Fact("PandaControlServer creates a SimpleActionServer of type FollowJointTrajectoryAction on the "
             "relative name formed from the last component of its node name and "
             "'/panda_arm/follow_joint_trajectory'.",
             source="upstream_code", ref=_ACTION_SERVER_REF),
        Fact("The action goal declares trajectory, path_tolerance, goal_tolerance, goal_time_tolerance, "
             "create_time_axis, time_axis_step and timeout, whose comment says a timeout of 0 waits "
             "indefinitely; the result declares error_code and error_string.",
             source="upstream_code", ref=_ACTION_DECL_REF),
        Fact("The server connects a SimpleActionClient of type control_msgs FollowJointTrajectoryAction to the "
             "relative action name panda_arm_trajectory_controller/follow_joint_trajectory when that server "
             "exists.",
             source="upstream_code", ref=_TRAJ_CLIENT_REF),
        Fact("The execute callback sends the converted goal through that client, waits for the result with "
             "goal.timeout, and aborts with error_code -6 when the wait does not finish.",
             source="upstream_code", ref="panda_gazebo/src/panda_gazebo/core/control_server.py:1585-1598"),
        Fact("The wrapper succeeds only when its preempt flag is false and the forwarded controller result has "
             "error_code SUCCESSFUL; otherwise it aborts with the forwarded result.",
             source="upstream_code", ref="panda_gazebo/src/panda_gazebo/core/control_server.py:1601-1610"),
        Fact("The preempt callback cancels the forwarded controller goal when it is active or preempting and "
             "then marks the wrapper goal preempted, without waiting for the controller's terminal result.",
             source="upstream_code", ref=_PREEMPT_REF),
        Fact("PandaControlServer creates the SetGripperWidth service on the relative name formed from the last "
             "component of its node name and '/panda_hand/set_gripper_width' when the gripper is loaded.",
             source="upstream_code", ref="panda_gazebo/src/panda_gazebo/core/control_server.py:215-223"),
        Fact("The gripper callback halves the requested width, clips the result to [0, 0.08], puts it in a "
             "GripperCommandGoal's command.position with the request's max_effort (or GRASP_FORCE when that is "
             "0 and grasping is true, else 0), and sends the goal when the gripper client is connected.",
             source="upstream_code", ref=_GRIPPER_GOAL_REF),
        Fact("load_panda_joint_limits sets the finger joint limits of panda_finger_joint1 and "
             "panda_finger_joint2 to 0.0 and 0.04.",
             source="upstream_code", ref=_FINGER_LIMITS_REF),
        Fact("The gripper callback waits for the gripper action result only when wait is true, using the request "
             "timeout; otherwise it sets success true after sending the goal; without a connected gripper "
             "client it sets success false.",
             source="upstream_code", ref=_GRIPPER_WAIT_REF),
        Fact("SetGripperWidth.srv declares width, grasping, max_effort, wait and timeout, and returns success "
             "and message.",
             source="upstream_code", ref=_GRIPPER_DECL_REF),
        Fact("GRASP_FORCE is 10, and its comment states the Panda continuous force is 70 N and max_force is "
             "140 N.",
             source="upstream_code", ref=_FORCE_NOTE_REF),
        Fact("The arm joint names are panda_joint1 through panda_joint7 and the hand names are "
             "panda_finger_joint1 and panda_finger_joint2.",
             source="upstream_code", ref=_JOINT_NAMES_REF),
        Fact("PandaControlServer subscribes to the relative topic 'joint_states' with JointState messages.",
             source="upstream_code", ref=_JOINT_STATE_REF),
        Fact("The Gazebo world plugin's SERVICE_NAME constant is the absolute name /lock_unlock_panda_joints.",
             source="upstream_code", ref=_LOCK_SERVICE_REF),
        Fact("The plugin's Load creates a node handle named panda_joint_control_plugin and advertises "
             "SERVICE_NAME on it with the LockUnlockJoints callback.",
             source="upstream_code", ref=_LOCK_ADVERTISE_REF),
        Fact("The callback looks up the Gazebo model named by MODEL_NAME and returns success false when it is "
             "missing; it returns success false at the first missing joint without restoring the joints it "
             "has already handled.",
             source="upstream_code", ref=_LOCK_MISSING_REF),
        Fact("For lock true the callback stores each joint's present lower and upper limits and sets both "
             "limits to the joint's current position; for lock false it restores the stored limits when both "
             "exist; it then returns success true. It reads no joint velocity.",
             source="upstream_code", ref=_LOCK_BODY_REF),
        Fact("The plugin's MODEL_NAME constant is panda.",
             source="upstream_code", ref="panda_gazebo/src/panda_joint_locker_world_plugin.cpp:12"),
        Fact("LockJoints.srv declares joint_names and lock in the request and success and message in the "
             "response.",
             source="upstream_code", ref=_LOCK_DECL_REF),
        Fact("The shipped empty.world loads the panda_joint_locker plugin from libpanda_gazebo.so.",
             source="upstream_code", ref=_WORLD_REF),
        Fact("The package declares the MIT licence.",
             source="upstream_code", ref=_LICENSE_REF),
    ]
    safe_state = (
        "Every Panda arm and finger joint has its Gazebo lower and upper limits set to the position it had "
        "when the /lock_unlock_panda_joints callback ran. The service acknowledges that limit update, not a "
        "measured zero velocity; Gazebo keeps running, and the trajectory controller, MoveIt or any other ROS "
        "client may keep commanding the locked joints. The lock persists after mhs.safety.reset: no unlock is "
        "declared, and repeated lock requests overwrite the limits the plugin stores for an unlock."
    )
    #: The fake is an event-driven recording transport, not Gazebo or a controller.
    fidelity = {
        "engine": "analytic:ROS recording fake (no Gazebo physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": ("Event-driven wire stand-in with no physics step, no controller interpolation, no "
                      "action feedback and no wall-clock pacing; the placeholder joint values do not "
                      "establish state-hash replay"),
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake answers the declared /joint_states subscription, the wrapper trajectory action, the "
            "gripper width service and the lock service without Gazebo, franka_gazebo, ros_control, MoveIt "
            "or a ROS graph",
            "trajectory goals complete instantly with a canned error_code; there is no interpolation, "
            "controller latency, feedback, collision, gravity or controller error behavior",
            "gripper commands record the requested total width and force but run no franka_gripper action, "
            "contact or grasp; the accepted result only says the goal was sent",
            "the lock service records the request and reports success; it does not run Gazebo joint-limit "
            "enforcement, so a fake stop is not physical or measured quiescence",
            "all joint samples, widths, forces and goal identifiers are placeholders, not device facts or "
            "limits; a live run needs the operator's Gazebo, ros_control controllers, franka_gripper and "
            "rosbridge deployment",
            "the upstream /joint_states publisher order, the real joint travel limits (in the franka_ros "
            "submodule), controller timing and every physical stop latency are not established here",
            "every lock request stores the joint's present limits as the limits an unlock restores "
            "(panda_joint_locker_world_plugin.cpp:93-111); a reviewer probe of this fake showed the runtime "
            "sending the lock twice for an idle e-stop, four times for an e-stop with a trajectory goal in flight "
            "and three times for an ordinary trajectory cancellation, so an upstream unlock afterwards restores "
            "the locked limits and the simulated arm stays frozen until the model is respawned or Gazebo "
            "restarts; the package declares no unlock and mhs.safety.reset does not unlock",
            "the upstream gripper clip allows 0.08 m per finger (control_server.py:1466-1472), twice the finger "
            "joint limit the clone states (helpers.py:613-621); franka_gazebo's gripper simulation in the "
            "franka_ros submodule (outside the pinned object store) refuses a per-finger position above 0.04 m "
            "while the wrapper with wait false still reports success, so the finger_width limit is the clone's "
            "0.04 m finger limit rather than the clip; even with wait true the wrapper's success is the return of "
            "wait_for_result (control_server.py:1491-1494), which says the goal finished, not that it succeeded",
            "the shipped launch starts MoveIt (demo.launch with the simple controller manager), the "
            "panda_moveit_planner_server and RViz by default (put_robot_in_world.launch:10, 53-61, 80-86, "
            "101-105); they can command the same controllers outside MHS, the MHS latch does not fence them, "
            "and only the lock constrains them",
            "/joint_states comes from franka_ros's joint_state_publisher on simulated time (outside the pinned "
            "object store); while Gazebo is paused it is silent, and a reviewer probe with the topic silent "
            "showed mhs.resource.read failing MHS.DEVICE.NOT_READY after 2 s and each command waiting about "
            "2 s for that read before completing; the e-stop was not delayed",
            "the wrapper action and gripper service target the generic controller names "
            "panda_arm_trajectory_controller/follow_joint_trajectory and franka_gripper/gripper_action "
            "(control_server.py:266-277, 341-348), not a Gazebo-only interface; run against a real Franka graph "
            "(franka_control in the franka_ros submodule) they would move a real arm, while the lock service, "
            "a Gazebo world plugin, would be absent and every e-stop would fail with the latch held",
            "the lock relies on the Gazebo physics engine enforcing joint limits; the launch offers ode or dart "
            "physics (start_simulation.launch:11-12), and that enforcement is outside the clone and not "
            "verified here",
        ],
    }

    parameters = {"joint_state": _JOINT_STATE_FIELD}
    reads = {"joint_state": _JOINT_STATE_READ}
    commands = {
        "x-cap.rickstaa.follow_joint_trajectory.v1": _TRAJECTORY_ACTION,
        "x-cap.rickstaa.gripper_width.v1": _GRIPPER_COMMAND,
        "x-cap.rickstaa.lock_joints.v1": _LOCK_COMMAND,
    }
    actions = {
        "x-cap.rickstaa.follow_joint_trajectory.v1": Action(
            name="follow_joint_trajectory",
            description=(
                "Forward arm waypoints through /panda_control_server/panda_arm/follow_joint_trajectory and "
                "return the controller terminal error_code"
            ),
            long_running=True,
            cancellable=True,
            max_duration_ms=120000,
            input={
                "points": Field(
                    "array",
                    min_items=1,
                    description="Arm waypoints; joint_names is fixed to panda_joint1..panda_joint7",
                    items=_TRAJECTORY_POINT,
                ),
                "time_axis_step": Field(
                    "number",
                    unit="s",
                    description="Automatic time-axis step; the wrapper fills each waypoint's time_from_start",
                    limit=_TIME_AXIS_LIMIT,
                ),
                "timeout_s": Field(
                    "integer",
                    unit="s",
                    description="Forwarded goal timeout; 0 would wait indefinitely, so the operator supplies a bound",
                    limit=_TIMEOUT_LIMIT,
                ),
            },
            output={
                "error_code": Field("integer", description="Forwarded controller result error_code; 0 is SUCCESSFUL"),
                "error_string": Field("string", description="Forwarded controller result error_string"),
            },
            examples=[{"points": [{"positions": [0.0, -0.5, 0.0, -2.0, 0.0, 2.0, 0.0]}],
                       "time_axis_step": 0.1, "timeout_s": 10}],
        ),
        "x-cap.rickstaa.gripper_width.v1": Action(
            name="set_gripper_width",
            description=(
                "Send a per-finger width and max effort through the wrapper gripper service; wait is false, so "
                "accepted means the goal was sent, not that the fingers reached it"
            ),
            input={
                "finger_width": Field(
                    "number",
                    unit="m",
                    description="Per-finger target opening; the binding sends twice this value as the total width",
                    limit=_FINGER_WIDTH_LIMIT,
                ),
                "force": Field(
                    "number",
                    unit="N",
                    description="Gripper max effort; 0 selects the upstream 10 N default when grasping is true",
                    limit=_GRASP_FORCE_LIMIT,
                ),
            },
            output={
                "accepted": Field("boolean", description="True when the wrapper reported the goal was sent"),
                "message": Field("string", description="Upstream text; not a grasp measurement"),
            },
        ),
        "x-cap.rickstaa.lock_joints.v1": Action(
            name="lock_joints",
            safe_state=True,
            description=(
                "Freeze all Panda arm and finger joints at their present position through the world plugin's "
                "joint-limit update; the acknowledgement is not a velocity measurement, and no unlock is "
                "declared"
            ),
            output={
                "locked": Field("boolean", description="True when the plugin reported the limit update successful"),
                "message": Field("string", description="Upstream text"),
            },
        ),
    }
    #: The same acknowledged lock service is the native stop and the safe-state
    #: action.  Normal safe-state invocation does not itself engage the latch.
    safety_bindings = {"estop": _LOCK_COMMAND}
