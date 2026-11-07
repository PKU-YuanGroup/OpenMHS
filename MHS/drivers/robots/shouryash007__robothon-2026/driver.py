"""OpenMHS rosbridge driver for the SO-101 Gazebo pick-and-place simulation.

The pinned repository is a ROS 2 Gazebo simulation of an SO-101 follower arm
with a MoveIt configuration.  The repository's own pick-and-place script
publishes ``trajectory_msgs/msg/JointTrajectory`` messages to the absolute
``/arm_controller/joint_trajectory`` topic.  The so101_gazebo controllers.yaml
configures that controller as a six-joint
``joint_trajectory_controller/JointTrajectoryController`` with open-loop
control, but the MoveIt xacro the follower launch spawns loads a five-joint
arm_controller and a separate gripper_controller; which configuration runs is
not established from the clone (model review, 2026-11-05).  This is a
configuration-only :class:`RosDriver`: it declares no
Python native class and never imports ROS, starts Gazebo, MoveIt or a
controller.

The selected primary control is the six-joint trajectory publication used by
``object_detector.py``; the action reports only that rosbridge transmitted the
message (``published`` true, ``confirmed`` false).  It does not prove that a
controller received it, interpolated it, moved an arm or stopped.

The pinned clone exposes no stop, pause, cancellation or safe-state service or
action for this control surface.  ``so101_gazebo_bridge.stop()`` only stops the
teleop bridge's UDP listener and closes its socket; it does not stop a
published trajectory.  The Gazebo world-control service and the
controller-manager switch service are outside the clone and are not bridged by
the upstream launch.  This package therefore declares no e-stop or safe-state
binding and is blocked rather than presenting a software latch or a
fire-and-forget publication as a stopped state.

Every endpoint, type and Fact cites the pinned clone at
32a2722fda7758d5ea85101a240b11aa55f4e3f0.  The fake is a ROS-free recording
transport; no ROS graph, Gazebo world, controller, MoveIt node or hardware was
contacted while writing this package.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: object_detector.py creates the six-joint trajectory publisher on this
#: absolute topic; the same literal is used by palletizing_fetch.py.
_ARM_TOPIC_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/object_detector.py:14"
)

#: The trajectory message and point types are imported here.
_ARM_TYPE_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/object_detector.py:5"
)

#: The six joint names, in the order the script puts them in the message.
_ARM_JOINTS_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/object_detector.py:30-38"
)

#: The scanning pose is published ten times at 0.1 s intervals, then the
#: script waits 5 s and starts detection.  This is the upstream script's
#: timing, not a controller or device bound.
_SCAN_PUBLISH_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/object_detector.py:41-48"
)

#: The grasp sequence publishes one message with nine points at 3 s..20 s.
_GRASP_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/object_detector.py:77-138"
)

#: The camera subscription in the same script (not exposed by this package).
_CAMERA_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/object_detector.py:27"
)

#: The so101_gazebo arm controller configuration (one of two in the clone; model review).
_CONTROLLER_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/config/controllers.yaml:9-20"
)
_OPEN_LOOP_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/config/controllers.yaml:25"
)

#: The launch loads that controller file and spawns the controllers.
_LAUNCH_CONTROLLERS_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/launch/so101_gazebo.launch.py:204-211"
)
_LAUNCH_SPAWN_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/launch/so101_gazebo.launch.py:271-282"
)

#: The SO-101 model and its revolute joint travel limits.
_URDF_MODEL_REF = "hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:4"
_SHOULDER_PAN_REF = "hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:495-500"
_SHOULDER_LIFT_REF = "hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:474-479"
_ELBOW_REF = "hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:453-458"
_WRIST_FLEX_REF = "hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:431-436"
_WRIST_ROLL_REF = "hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:410-415"
_GRIPPER_REF = "hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:389-394"

#: The teleop bridge publishes the five arm joints and the gripper
#: separately; its stop method only ends the UDP listener.
_BRIDGE_PUBLISHERS_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/so101_gazebo_bridge.py:18-26"
)
_BRIDGE_JOINTS_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/so101_gazebo_bridge.py:30-31"
)
_BRIDGE_PROCESS_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/so101_gazebo_bridge.py:72-106"
)
_BRIDGE_STOP_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/so101_gazebo_bridge.py:108-110"
)

#: MoveIt names FollowJointTrajectory controllers but the clone never writes
#: the resolved action endpoint or its message type.
_MOVEIT_CONTROLLERS_REF = (
    "hackathon_ws/hackathon_ws/src/so101_moveit_config/config/moveit_controllers.yaml:10-25"
)

#: The MoveIt test script builds a MoveGroup goal but never sends it.
_PICK_PLACE_TEST_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/pick_place_test.py:20-51"
)

#: The two ROS packages carry different licence statements and the repository
#: has no top-level LICENSE file; the card's NOASSERTION is retained.
_LICENSE_GAZEBO_REF = (
    "hackathon_ws/hackathon_ws/src/so101_gazebo/package.xml:8"
)
_LICENSE_MOVEIT_REF = (
    "hackathon_ws/hackathon_ws/src/so101_moveit_config/package.xml:11"
)

#: The controller config fixes this joint order (the gripper is the sixth
#: joint in the launched Gazebo path).
_JOINTS = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]

#: Each position uses the revolute travel range written in the pinned URDF.
#: A trajectory outside these ranges is refused before the publication.
_POSITION_LIMITS = [
    Limit(
        min=-1.91986,
        max=1.91986,
        path="[0]",
        unit="rad",
        source="upstream_code",
        ref=_SHOULDER_PAN_REF,
    ),
    Limit(
        min=-1.74533,
        max=1.74533,
        path="[1]",
        unit="rad",
        source="upstream_code",
        ref=_SHOULDER_LIFT_REF,
    ),
    Limit(
        min=-1.69,
        max=1.69,
        path="[2]",
        unit="rad",
        source="upstream_code",
        ref=_ELBOW_REF,
    ),
    Limit(
        min=-1.65806,
        max=1.65806,
        path="[3]",
        unit="rad",
        source="upstream_code",
        ref=_WRIST_FLEX_REF,
    ),
    Limit(
        min=-2.74385,
        max=2.84121,
        path="[4]",
        unit="rad",
        source="upstream_code",
        ref=_WRIST_ROLL_REF,
    ),
    Limit(
        min=-0.174533,
        max=1.74533,
        path="[5]",
        unit="rad",
        source="upstream_code",
        ref=_GRIPPER_REF,
    ),
]

#: The clone states the script's individual trajectory times (3 s..20 s) but
#: no controller or site bound for a Duration; the operator supplies it.
_TIME_SEC_LIMIT = Limit.operator_required(
    "the pinned clone states no maximum JointTrajectoryPoint time_from_start.sec; "
    "the operator supplies the deployed controller and site motion envelope"
)
_TIME_NSEC_LIMIT = Limit.operator_required(
    "the pinned clone states no nanosecond range for a JointTrajectoryPoint "
    "Duration; the operator supplies the deployed controller and site motion envelope"
)

_POSITIONS = Field(
    "array",
    unit="rad",
    length=6,
    description="Six target joint angles.",
    items=Field("number", unit="rad", description="One joint angle."),
    limit=_POSITION_LIMITS,
)

_TIME_FROM_START = Field(
    "object",
    description="Point offset from the trajectory start.",
    properties={
        "sec": Field(
            "integer",
            unit="s",
            description="Whole seconds.",
            limit=_TIME_SEC_LIMIT,
        ),
        "nanosec": Field(
            "integer",
            unit="ns",
            description="Nanoseconds.",
            limit=_TIME_NSEC_LIMIT,
        ),
    },
)

_POINT = Field(
    "object",
    description="One trajectory_msgs/JointTrajectoryPoint",
    properties={
        "positions": _POSITIONS,
        "time_from_start": _TIME_FROM_START,
    },
)

_ARM_COMMAND = {
    "topic": "/arm_controller/joint_trajectory",
    "type": "trajectory_msgs/msg/JointTrajectory",
    "operation": "publish",
    "source_ref": _ARM_TOPIC_REF,
    "type_ref": _ARM_TYPE_REF,
    "message": {"joint_names": _JOINTS, "points": []},
    "args": {"points": {"from": "input.points"}},
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
}

_PUBLISHED = Field(
    "boolean",
    description=(
        "True when the driver handed the JointTrajectory to rosbridge; this is "
        "not a controller acknowledgement"
    ),
)
_CONFIRMED = Field(
    "boolean",
    description=(
        "Always false: the upstream joint_trajectory topic has no acknowledgement, "
        "motion, arrival or stop result"
    ),
)


class So101Gazebo(RosDriver):
    device_id = "so101_gazebo"
    device_kind = "robot.arm"
    mode = "simulated"
    # A robot arm is at least R2 (MHS/spec/04-safety.md); the trajectory
    # commands move the simulated arm even though no hardware is attached.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeSo101Gazebo"}
    tags = ["ros", "ros2", "gazebo", "simulation", "robot-arm", "trajectory"]
    display_name = "SO-101 Gazebo pick-and-place simulation"
    vendor = "shouryash007"
    model = "SO-101 follower"
    facts = [
        Fact(
            "The README's primary command launches so101_gazebo.launch.py with moveit:=follower.",
            source="vendor_doc",
            ref="README.md:2",
        ),
        Fact(
            "The README runs object_detector.py against the Gazebo graph with use_sim_time:=true.",
            source="vendor_doc",
            ref="README.md:6",
        ),
        Fact(
            "The README bridges /d435i/image as sensor_msgs/msg/Image from a Gazebo Image message.",
            source="vendor_doc",
            ref="README.md:4",
        ),
        Fact(
            "object_detector.py imports JointTrajectory and JointTrajectoryPoint from trajectory_msgs.msg.",
            source="upstream_code",
            ref=_ARM_TYPE_REF,
        ),
        Fact(
            "object_detector.py creates a publisher on the absolute "
            "/arm_controller/joint_trajectory topic with queue size 10.",
            source="upstream_code",
            ref=_ARM_TOPIC_REF,
        ),
        Fact(
            "The scanning message names shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, "
            "wrist_roll and gripper in that order and sets six positions and a "
            "time_from_start.sec of 4.",
            source="upstream_code",
            ref=_ARM_JOINTS_REF,
        ),
        Fact(
            "move_to_scanning_pose publishes the same message ten times with 0.1 s sleeps, "
            "then sleeps 5.0 s before setting scanning_complete.",
            source="upstream_code",
            ref=_SCAN_PUBLISH_REF,
        ),
        Fact(
            "execute_grasp builds nine trajectory points with time_from_start.sec values from 3 "
            "through 20 and publishes the message once.",
            source="upstream_code",
            ref=_GRASP_REF,
        ),
        Fact(
            "object_detector.py subscribes to /d435i/image as sensor_msgs/Image.",
            source="upstream_code",
            ref=_CAMERA_REF,
        ),
        Fact(
            "so101_gazebo config/controllers.yaml defines arm_controller as a "
            "joint_trajectory_controller/JointTrajectoryController over shoulder_pan, "
            "shoulder_lift, elbow_flex, wrist_flex, wrist_roll and gripper.",
            source="upstream_code",
            ref=_CONTROLLER_REF,
        ),
        Fact(
            "so101.urdf declares a ros2_control system with the gazebo_ros2_control/GazeboSystem "
            "plugin and loads libgazebo_ros2_control with the so101_gazebo config/controllers.yaml.",
            source="upstream_code",
            ref="hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:515-549",
        ),
        Fact(
            "The MoveIt so101_new_calib.urdf.xacro includes so101.urdf, instantiates its ros2_control "
            "macro as GazeboSimSystem and loads libgz_ros2_control-system with "
            "so101_moveit_config config/ros2_controllers.yaml.",
            source="upstream_code",
            ref="hackathon_ws/hackathon_ws/src/so101_moveit_config/config/so101_new_calib.urdf.xacro:5-35",
        ),
        Fact(
            "ros2_controllers.yaml gives arm_controller the five joints shoulder_pan through wrist_roll "
            "and a separate gripper_controller the gripper joint.",
            source="upstream_code",
            ref="hackathon_ws/hackathon_ws/src/so101_moveit_config/config/ros2_controllers.yaml:23-44",
        ),
        Fact(
            "With moveit:=follower the launch includes the MoveIt rsp and move_group launches with "
            "use_sim_time true.",
            source="upstream_code",
            ref="hackathon_ws/hackathon_ws/src/so101_gazebo/launch/so101_gazebo.launch.py:245-260",
        ),
        Fact(
            "The arm_controller configuration sets open_loop_control true.",
            source="upstream_code",
            ref=_OPEN_LOOP_REF,
        ),
        Fact(
            "The launch resolves robot_controllers to the so101_gazebo config/controllers.yaml path.",
            source="upstream_code",
            ref="hackathon_ws/hackathon_ws/src/so101_gazebo/launch/so101_gazebo.launch.py:118-119",
        ),
        Fact(
            "The launch starts controller_manager/ros2_control_node with the robot_controllers "
            "parameter file.",
            source="upstream_code",
            ref=_LAUNCH_CONTROLLERS_REF,
        ),
        Fact(
            "The launch spawns joint_state_broadcaster, arm_controller and gripper_controller with "
            "the robot_controllers parameter file.",
            source="upstream_code",
            ref=_LAUNCH_SPAWN_REF,
        ),
        Fact(
            "The URDF names the model so101_new_calib.",
            source="upstream_code",
            ref=_URDF_MODEL_REF,
        ),
        Fact(
            "The URDF gives shoulder_pan a revolute range of -1.91986..1.91986 rad.",
            source="upstream_code",
            ref=_SHOULDER_PAN_REF,
        ),
        Fact(
            "The URDF gives shoulder_lift a revolute range of -1.74533..1.74533 rad.",
            source="upstream_code",
            ref=_SHOULDER_LIFT_REF,
        ),
        Fact(
            "The URDF gives elbow_flex a revolute range of -1.69..1.69 rad.",
            source="upstream_code",
            ref=_ELBOW_REF,
        ),
        Fact(
            "The URDF gives wrist_flex a revolute range of -1.65806..1.65806 rad.",
            source="upstream_code",
            ref=_WRIST_FLEX_REF,
        ),
        Fact(
            "The URDF gives wrist_roll a revolute range of -2.74385..2.84121 rad.",
            source="upstream_code",
            ref=_WRIST_ROLL_REF,
        ),
        Fact(
            "The URDF gives gripper a revolute range of -0.174533..1.74533 rad.",
            source="upstream_code",
            ref=_GRIPPER_REF,
        ),
        Fact(
            "so101_gazebo_bridge.py publishes to /arm_controller/joint_trajectory and "
            "/gripper_controller/joint_trajectory with JointTrajectory messages.",
            source="upstream_code",
            ref=_BRIDGE_PUBLISHERS_REF,
        ),
        Fact(
            "The teleop bridge names five arm joints and one gripper joint separately.",
            source="upstream_code",
            ref=_BRIDGE_JOINTS_REF,
        ),
        Fact(
            "process_command fills a missing arm joint with 0.0, publishes the arm only when at "
            "least one arm key was present, and publishes the gripper independently.",
            source="upstream_code",
            ref=_BRIDGE_PROCESS_REF,
        ),
        Fact(
            "So101GazeboBridge.stop only clears its running flag and closes the UDP socket; it has "
            "no controller or trajectory stop call.",
            source="upstream_code",
            ref=_BRIDGE_STOP_REF,
        ),
        Fact(
            "MoveIt's simple controller configuration names arm_controller and gripper_controller "
            "with type FollowJointTrajectory and action_ns follow_joint_trajectory, but writes no "
            "resolved ROS action endpoint or type.",
            source="upstream_code",
            ref=_MOVEIT_CONTROLLERS_REF,
        ),
        Fact(
            "pick_place_test.py builds a MoveGroup goal in send_goal but never calls an asynchronous "
            "send method, and run_test only calls send_goal.",
            source="upstream_code",
            ref=_PICK_PLACE_TEST_REF,
        ),
        Fact(
            "The so101_gazebo package manifest declares Apache-2.0.",
            source="upstream_code",
            ref=_LICENSE_GAZEBO_REF,
        ),
        Fact(
            "The so101_moveit_config package manifest declares BSD.",
            source="upstream_code",
            ref=_LICENSE_MOVEIT_REF,
        ),
    ]
    safe_state = (
        "No source-backed stop, pause, cancellation or safe-state service or action exists in the "
        "pinned clone: the runtime's software latch refuses new publications, but it does not "
        "interrupt a trajectory the external joint_trajectory_controller has already accepted. "
        "This package is blocked rather than claiming a stopped state."
    )

    # The fake is an event-driven ROS-free recording transport, not Gazebo.
    fidelity = {
        "engine": "analytic:ROS recording fake (no Gazebo physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": (
                "Event-driven recording stand-in with no physics step, controller interpolation, "
                "trajectory execution or wall-clock pacing; the placeholder published messages do "
                "not establish motion or state-hash replay"
            ),
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake records the declared /arm_controller/joint_trajectory publication and "
            "runs no Gazebo, controller manager, MoveIt or ROS graph",
            "a publication is recorded and returned as published=true, confirmed=false; no "
            "controller receives it, no arm moves and no trajectory is interpolated",
            "the fake performs no joint interpolation, timing, dynamics, gravity, collision, "
            "controller error or feedback behavior",
            "/d435i/image, the object detector, /joint_states, TF, /clock and the MoveIt "
            "planning interface are out of scope",
            "no source-backed stop or safe-state action is declared; the software latch does "
            "not interrupt an accepted trajectory",
            "model review: the follower path's robot description carries two ros2_control systems "
            "and two controller plugins (so101.urdf:515-549 with controllers.yaml; the MoveIt xacro "
            ":5-35 with ros2_controllers.yaml, five-joint arm_controller plus gripper_controller), "
            "and the launch also starts a standalone ros2_control_node with controllers.yaml and "
            "spawns a gripper_controller that file does not define (launch :204-211, :271-282); "
            "the six-joint trajectories of object_detector.py and of this package do not match the "
            "five-joint arm_controller, and the teleop bridge's five-joint ones do not match the "
            "six-joint one",
        ],
    }

    commands = {
        "x-cap.shouryash007.arm_trajectory.v1": _ARM_COMMAND,
    }
    actions = {
        "x-cap.shouryash007.arm_trajectory.v1": Action(
            name="send_arm_trajectory",
            verb="invoke",
            cancellable=False,
            description=(
                "Publish one JointTrajectory; transmission only, not a controller acknowledgement"
            ),
            input={
                "points": Field(
                    "array",
                    min_items=1,
                    description="Trajectory points in order.",
                    items=_POINT,
                ),
            },
            output={
                "published": _PUBLISHED,
                "confirmed": _CONFIRMED,
            },
            examples=[
                {
                    "points": [
                        {
                            "positions": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                            "time_from_start": {"sec": 1, "nanosec": 0},
                        }
                    ]
                }
            ],
        ),
    }
    # No source-proven stop exists: the clone exposes only trajectory
    # publications and a UDP bridge stop that does not stop the controller.
    # A software latch is not an e-stop and no safe-state action is claimed.
    safety_bindings = {}
