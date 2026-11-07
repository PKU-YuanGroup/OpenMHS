"""OpenMHS rosbridge driver for the pinned SPARC pick-and-place ROS 2 graph.

The upstream C++ node ``ur5_pick_place_cpp_r`` is the actuator of this
repository.  It subscribes to the absolute ``/target_point`` topic
(``std_msgs/msg/Float64MultiArray``), reads four numbers as ``[x, y, yaw,
box]``, runs a blocking MoveIt pick-and-place sequence through
``MoveGroupInterface`` and publishes ``/pick_place_status``
(``std_msgs/msg/String``).  This package is a configuration-only
``RosDriver``; it declares no Python native class and does not start the
node, MoveIt, Isaac Sim or the ROS graph.

The clone exposes no acknowledged stop service or action for this control
surface.  The node has no cancellation check in its multi-step sequence, its
motion helpers call ``move_group.execute(...)`` and return true without
checking the result, and a second ``/target_point`` received during a sequence
is only queued for the next main-loop iteration.  The driver therefore
declares no safety binding and no safe-state action; ``RESULT.json`` records
the package as blocked instead of presenting a software latch or a target
publication as a stop.  The fake is a ROS-free analytic contract stand-in, not
a recording of captured traffic.

Every endpoint and Fact cites the pinned clone at
79156f61c770f7dbf9373a45c62faecac3d67d81.  No hardware, Isaac Sim, MoveIt or
ROS graph was run while writing this package.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The C++ node publishes status and declares the target subscription.
_STATUS_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:383-384"
_STATUS_TYPE_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:12"
_TARGET_POINT_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:403-405"
_TARGET_POINT_TYPE_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:10"

#: The C++ sequence, its target acceptance and its only cancel call.
_SEQUENCE_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:297-346"
_BOX_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:319-330"
_ACCEPT_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:414-429"
_MAIN_LOOP_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:466-482"
_CANCEL_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:495-497"
_EXECUTE_XY_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:79-83"
_EXECUTE_YAW_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:123-127"
_EXECUTE_DOWN_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:157-161"
_EXECUTE_UP_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:213-217"
_EXECUTE_NAMED_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:35-48"
_EXECUTE_CLOSE_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:179-184"
_EXECUTE_OPEN_REF = "src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:267-272"

#: The target publisher is the upstream producer of /target_point.
_TARGET_PUBLISHER_REF = "pick_place_chatbot_ui/target_publisher.py:26-32"
_TARGET_DATA_REF = "pick_place_chatbot_ui/target_publisher.py:109-117"
_TARGET_CALLBACK_REF = "pick_place_chatbot_ui/target_publisher.py:79-124"

#: The executable and the controller configuration.
_CMAKE_BUILD_REF = "src/ur5_moveit_config/CMakeLists.txt:16-22"
_CMAKE_INSTALL_REF = "src/ur5_moveit_config/CMakeLists.txt:32-37"
_README_RUN_REF = "README.md:99-107"
_CONTROLLERS_REF = "src/ur5_moveit_config/config/moveit_controllers.yaml:5-27"
_ROS2_CONTROLLERS_REF = "src/ur5_moveit_config/config/ros2_controllers.yaml:1-15"

#: The repository has no top-level LICENSE; the package metadata is mixed.
_LICENSE_TODO_REF = "src/yolov8obb_object_detection/package.xml:8"
_LICENSE_APACHE_REF = "src/yolov8obb_object_detection/setup.py:27"
_LICENSE_BSD_UR5_REF = "src/ur5_moveit_config/package.xml:11"
_LICENSE_BSD_ROBOT_REF = "src/robot_description/package.xml:12"

#: The four numbers are published as one Float64MultiArray.data array.
#: The field is heterogeneous (metres, metres, radians, a box number), so the
#: array carries the dimensionless unit "1" and the description states the
#: per-element units instead of pretending one unit fits all four.
_TARGET_POINT = Field(
    "array",
    unit="1",
    description=(
        "Four numbers published in data order: x in metres, y in metres, yaw in radians and box "
        "(1 or 2). The C++ callback reads data[0..3] as x, y, yaw and box."
    ),
    length=4,
    items=Field("number", unit="1", description="One element of the four-number target"),
    limit=[
        Limit.operator_required(
            "the clone states no reachable workspace bound for x; the C++ node passes the value to "
            "computeCartesianPath without a range check (ur5_pick_place_cpp_r.cpp:58-89) and the "
            "operator must supply the reviewed table envelope",
            path="[0]",
        ),
        Limit.operator_required(
            "the clone states no reachable workspace bound for y; the C++ node passes the value to "
            "computeCartesianPath without a range check (ur5_pick_place_cpp_r.cpp:58-89) and the "
            "operator must supply the reviewed table envelope",
            path="[1]",
        ),
        Limit.operator_required(
            "the clone states no yaw envelope; rotateGripperYaw passes the value to "
            "computeCartesianPath without a range check (ur5_pick_place_cpp_r.cpp:92-134) and the "
            "operator must supply the reviewed wrist envelope",
            path="[2]",
        ),
        Limit(
            allowed=[1, 2],
            path="[3]",
            unit="1",
            source="upstream_code",
            ref=_BOX_REF,
            reason=(
                "the pick-and-place sequence only handles box == 1 and box == 2; any other value "
                "leaves box_x and box_y uninitialized before moveToWorldXY (lines 319-330)"
            ),
        ),
    ],
)

_PUBLISHED_OUTPUT = {
    "published": Field("boolean", description="True when the driver handed the message to rosbridge"),
    "confirmed": Field(
        "boolean",
        description=(
            "Always false: a rosbridge publication carries no planning, execution, arrival or stop "
            "confirmation"
        ),
    ),
}

_STATUS_OUTPUT = {
    "status": Field(
        "string",
        description=(
            "The String.data value published by the C++ node: IDLE, ACTIVE or ERROR in the upstream "
            "code; a fresh subscription sample, not a stopped-state measurement"
        ),
    ),
}

#: One explicit four-number target publication on the C++ node's input topic.
_TARGET_POINT_COMMAND = {
    "topic": "/target_point",
    "type": "std_msgs/msg/Float64MultiArray",
    "operation": "publish",
    "source_ref": _TARGET_POINT_REF,
    "type_ref": _TARGET_POINT_TYPE_REF,
    "message": {"data": []},
    "args": {"data": {"from": "input.target_point"}},
}

#: One explicit fresh subscription sample of the status topic.
_STATUS_COMMAND = {
    "topic": "/pick_place_status",
    "type": "std_msgs/msg/String",
    "operation": "subscribe",
    "source_ref": _STATUS_REF,
    "type_ref": _STATUS_TYPE_REF,
    "path": "data",
    "result": {"map": {"status": "output.$"}},
}

#: The status is also the main resource state.  The C++ node republishes it
#: every 200 ms, so a target publication has an observable status transition
#: from IDLE to ACTIVE.  It is not a stopped-state measurement.
_STATUS_READ = {
    "topic": "/pick_place_status",
    "type": "std_msgs/msg/String",
    "operation": "subscribe",
    "source_ref": _STATUS_REF,
    "type_ref": _STATUS_TYPE_REF,
    "path": "data",
    "timeout_ms": 2000,
}

_STATUS_PARAMETER = Field(
    "string",
    description=(
        "Current /pick_place_status String.data value published by the C++ node; IDLE, ACTIVE or "
        "ERROR in the upstream code, not a stopped-state measurement"
    ),
)

#: The main resource also records the last four-number target observed on the
#: shared /target_point topic.  It is the command bus, not a measured pose and
#: not proof that the C++ node planned, moved or stopped.
_TARGET_POINT_STATE = Field(
    "array",
    unit="1",
    description=(
        "Last four-number [x, y, yaw, box] value observed on the shared /target_point command topic; "
        "x and y are metres, yaw is radians, box is 1 or 2. This is the last command, not a measured pose"
    ),
    length=4,
    items=Field("number", unit="1", description="One target element"),
)

_TARGET_POINT_READ = {
    "topic": "/target_point",
    "type": "std_msgs/msg/Float64MultiArray",
    "operation": "subscribe",
    "source_ref": _TARGET_POINT_REF,
    "type_ref": _TARGET_POINT_TYPE_REF,
    "path": "data",
    "timeout_ms": 2000,
}


class SparcPickPlace(RosDriver):
    """SPARC UR5 pick-and-place through the pinned ROS 2 topic surface."""

    device_id = "nlp-pnp-robotic-arm"
    device_kind = "robot.arm"
    mode = "simulated"
    # A robot arm is at least R2 (MHS/spec/04-safety.md); the card floor is R0.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeNlpPnpRoboticArm"}
    tags = ["ros", "ros2", "moveit", "ur5", "pick-and-place", "isaac-sim", "sparc"]
    display_name = "SPARC UR5 pick-and-place"
    vendor = "sahilrajpurkar03"
    model = "UR5 with a Robotiq 85 gripper in the SPARC Isaac Sim scene"

    facts = [
        Fact(
            "The C++ node creates a std_msgs::msg::String publisher on the absolute /pick_place_status "
            "topic with queue size 10.",
            source="upstream_code",
            ref=_STATUS_REF,
        ),
        Fact(
            "The C++ node creates a std_msgs::msg::Float64 publisher on /gripper_joint/command with "
            "queue size 10.",
            source="upstream_code",
            ref="src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:388-389",
        ),
        Fact(
            "The C++ node subscribes to /target_point with std_msgs::msg::Float64MultiArray and rejects "
            "a message with fewer than four numbers.",
            source="upstream_code",
            ref="src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:403-411",
        ),
        Fact(
            "The /target_point callback reads data[0], data[1], data[2] and data[3] as x, y, yaw and "
            "box and marks a new target available when any value differs from the last accepted value "
            "or the box changes.",
            source="upstream_code",
            ref=_ACCEPT_REF,
        ),
        Fact(
            "The target callback updates target_x, target_y, target_yaw, target_box and "
            "new_target_available under a mutex.",
            source="upstream_code",
            ref="src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:424-433",
        ),
        Fact(
            "The main loop takes the pending target under the mutex, clears new_target_available and "
            "calls executePickAndPlace; a target received during the sequence is only queued for the "
            "next loop iteration.",
            source="upstream_code",
            ref=_MAIN_LOOP_REF,
        ),
        Fact(
            "executePickAndPlace publishes ACTIVE, opens the gripper, moves in XY, rotates yaw, moves "
            "down 0.255 m, closes the gripper, moves up 0.255 m, moves to the box, moves down 0.255 m, "
            "opens, moves up 0.255 m and moves to the arm_ready named pose, sleeping between the steps.",
            source="upstream_code",
            ref=_SEQUENCE_REF,
        ),
        Fact(
            "When executePickAndPlace fails, the main loop logs the failure, publishes ERROR, breaks out of "
            "the loop, cancels the executor, joins the spinner thread and calls rclcpp::shutdown().",
            source="upstream_code",
            ref="src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:480-497",
        ),
        Fact(
            "The node initialises target_box to -1.0 and last_x, last_y and last_yaw to 0.0.",
            source="upstream_code",
            ref="src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:374-380",
        ),
        Fact(
            "The main loop declares a local delay of 2 seconds.",
            source="upstream_code",
            ref="src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:453-456",
        ),
        Fact(
            "For box 1 the node assigns x 0.4 and y -0.53; for box 2 it assigns x 0.4 and y 0.53; "
            "there is no other branch and box_x and box_y are otherwise uninitialized.",
            source="upstream_code",
            ref=_BOX_REF,
        ),
        Fact(
            "moveToWorldXY calls move_group.execute(trajectory) and returns true without checking the "
            "execute result.",
            source="upstream_code",
            ref=_EXECUTE_XY_REF,
        ),
        Fact(
            "rotateGripperYaw calls move_group.execute(trajectory) and returns true without checking "
            "the execute result.",
            source="upstream_code",
            ref=_EXECUTE_YAW_REF,
        ),
        Fact(
            "moveDownZ calls move_group.execute(trajectory) and returns true without checking the "
            "execute result.",
            source="upstream_code",
            ref=_EXECUTE_DOWN_REF,
        ),
        Fact(
            "moveUpZ calls move_group.execute(trajectory) and returns true without checking the "
            "execute result.",
            source="upstream_code",
            ref=_EXECUTE_UP_REF,
        ),
        Fact(
            "moveToNamedPose calls move_group.execute(plan), then reads the current pose and returns "
            "true without checking the execute result.",
            source="upstream_code",
            ref=_EXECUTE_NAMED_REF,
        ),
        Fact(
            "closeGripper calls gripper_group.execute(plan) and returns true without checking the "
            "execute result.",
            source="upstream_code",
            ref=_EXECUTE_CLOSE_REF,
        ),
        Fact(
            "openGripper calls gripper_group.execute(plan) and returns true without checking the "
            "execute result.",
            source="upstream_code",
            ref=_EXECUTE_OPEN_REF,
        ),
        Fact(
            "The status timer publishes current_status every 200 ms.",
            source="upstream_code",
            ref="src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:394-400",
        ),
        Fact(
            "The node declares MoveGroupInterface planning groups arm and gripper and a node named "
            "ur5_xy_yaw_approach.",
            source="upstream_code",
            ref="src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:356-362",
        ),
        Fact(
            "The node declares pos_tol 0.001 and yaw_tol 0.01 as configurable ROS parameters with those "
            "defaults.",
            source="upstream_code",
            ref="src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:367-372",
        ),
        Fact(
            "The node uses a SingleThreadedExecutor on a spinner thread and a separate main loop for "
            "the motion sequence.",
            source="upstream_code",
            ref="src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:447-452",
        ),
        Fact(
            "The only cancel call in the C++ node is executor.cancel() after the main loop, followed by "
            "spinner.join() and rclcpp::shutdown().",
            source="upstream_code",
            ref=_CANCEL_REF,
        ),
        Fact(
            "The target publisher creates a Float64MultiArray publisher on /target_point with queue size "
            "10 and a String subscription on /target_class_cmd.",
            source="upstream_code",
            ref=_TARGET_PUBLISHER_REF,
        ),
        Fact(
            "The target publisher writes [x, y, yaw, box] into Float64MultiArray.data and uses -1.0 "
            "when no box is set.",
            source="upstream_code",
            ref=_TARGET_DATA_REF,
        ),
        Fact(
            "The target publisher publishes only when a detection's class_name equals the requested "
            "target class and then sets published true.",
            source="upstream_code",
            ref=_TARGET_CALLBACK_REF,
        ),
        Fact(
            "CMake builds the ur5_pick_place_cpp_r executable.",
            source="upstream_code",
            ref=_CMAKE_BUILD_REF,
        ),
        Fact(
            "CMake also builds a second executable, ur5_pick_place_cpp_s, from src/ur5_pick_place_cpp_s.cpp.",
            source="upstream_code",
            ref="src/ur5_moveit_config/CMakeLists.txt:24-30",
        ),
        Fact(
            "ur5_pick_place_cpp_s subscribes to /target_point with std_msgs::msg::Float64MultiArray.",
            source="upstream_code",
            ref="src/ur5_moveit_config/src/ur5_pick_place_cpp_s.cpp:359-362",
        ),
        Fact(
            "CMake installs ur5_pick_place_cpp_r under lib/ur5_moveit_config.",
            source="upstream_code",
            ref=_CMAKE_INSTALL_REF,
        ),
        Fact(
            "The README runs ros2 run ur5_moveit_config ur5_pick_place_cpp_r after the MoveIt demo "
            "launch.",
            source="vendor_doc",
            ref=_README_RUN_REF,
        ),
        Fact(
            "moveit_controllers.yaml declares arm_controller type FollowJointTrajectory with action_ns "
            "follow_joint_trajectory and gripper_controller type GripperCommand with action_ns "
            "gripper_cmd.",
            source="upstream_code",
            ref=_CONTROLLERS_REF,
        ),
        Fact(
            "ros2_controllers.yaml declares arm_controller as "
            "joint_trajectory_controller/JointTrajectoryController and gripper_controller as "
            "position_controllers/GripperActionController.",
            source="upstream_code",
            ref=_ROS2_CONTROLLERS_REF,
        ),
        Fact(
            "yolov8obb_object_detection/package.xml still has the text 'TODO: License declaration'.",
            source="upstream_code",
            ref=_LICENSE_TODO_REF,
        ),
        Fact(
            "yolov8obb_object_detection/setup.py declares license='Apache License 2.0'.",
            source="upstream_code",
            ref=_LICENSE_APACHE_REF,
        ),
        Fact(
            "ur5_moveit_config/package.xml declares BSD.",
            source="upstream_code",
            ref=_LICENSE_BSD_UR5_REF,
        ),
        Fact(
            "robot_description/package.xml declares BSD.",
            source="upstream_code",
            ref=_LICENSE_BSD_ROBOT_REF,
        ),
    ]

    safe_state = (
        "No acknowledged stop is exposed by the pinned clone: the node only consumes /target_point "
        "and runs a blocking, open-loop MoveIt sequence; the software latch refuses later publications "
        "but does not stop the active sequence or the external MoveIt controller, so no safe state is "
        "claimed."
    )

    fidelity = {
        "engine": "analytic:ROS publication/subscription fake (no Isaac Sim, MoveIt or physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": (
                "Event-driven rosbridge fake with canned status and a target echo; no physics step, "
                "motion planning, trajectory execution or wall-clock pacing"
            ),
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free analytic contract stand-in, not a recording of captured traffic: it "
            "runs no Isaac Sim scene, no MoveIt move_group, no controller, no YOLOv8 detector and no ROS "
            "graph",
            "the /target_point publication is transmission-only; the fake's ACTIVE status and the "
            "resource target_point are placeholder echoes of the last command on the shared topic, not "
            "proof that the C++ node accepted, planned or moved",
            "the /pick_place_status values are placeholders; the real node republishes current_status "
            "every 200 ms (ur5_pick_place_cpp_r.cpp:395-399)",
            "the upstream pick-and-place sequence is open loop: it sleeps between blocking "
            "move_group.execute calls, ignores their return values (lines 81-82, 125-126, 159-160, "
            "215-216) and has no stop or cancel service or action",
            "/target_point is a command topic that only clients publish (the chatbot target publisher once "
            "per requested target, target_publisher.py:79-124); the fake answers its subscription at once, but "
            "in a real graph each target publication waits about 2 s for the receipt's resource snapshot and "
            "mhs.resource.read fails NOT_READY (probe with the topic silent)",
            "after any failed step the node publishes ERROR once, leaves its main loop and shuts down "
            "(ur5_pick_place_cpp_r.cpp:480-497); /pick_place_status is silent afterwards and every status "
            "read fails NOT_READY",
            "the upstream chatbot path publishes box -1.0 when no box is named (target_publisher.py:109-117), "
            "which leaves box_x and box_y uninitialised before the place move (lines 319-330); this package "
            "refuses any box other than 1 or 2, but another client on /target_point can still send -1",
            "the clone also builds and installs ur5_pick_place_cpp_s, a variant on the same /target_point "
            "that publishes no /pick_place_status and moves 0.233 m in z (ur5_pick_place_cpp_s.cpp:287, 293, "
            "359-362); if an operator runs it, every status read fails NOT_READY",
            "NOT COVERED: /Yolov8_Inference, /rgb, /inference_result, /inference_result_cv2, "
            "/target_class_cmd, the MoveIt move_group and controller actions, the gripper, Isaac Sim "
            "physics, collision checking, the physical UR5 and the target publisher's camera calibration",
        ],
    }

    commands = {
        "x-cap.sahilrajpurkar03.target_point.v1": _TARGET_POINT_COMMAND,
        "x-cap.sahilrajpurkar03.pick_place_status.v1": _STATUS_COMMAND,
    }
    parameters = {"status": _STATUS_PARAMETER, "target_point": _TARGET_POINT_STATE}
    reads = {"status": _STATUS_READ, "target_point": _TARGET_POINT_READ}
    actions = {
        "x-cap.sahilrajpurkar03.target_point.v1": Action(
            name="publish_target_point",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one four-number [x, y, yaw, box] target to the C++ node's /target_point input; "
                "the receipt confirms only that rosbridge accepted the publication, not planning, "
                "motion, grasp, placement or stopping"
            ),
            input={"target_point": _TARGET_POINT},
            output=_PUBLISHED_OUTPUT,
        ),
        "x-cap.sahilrajpurkar03.pick_place_status.v1": Action(
            name="read_pick_place_status",
            verb="read",
            description=(
                "Read one fresh /pick_place_status sample published by the C++ node; the status is not a "
                "stopped-state measurement"
            ),
            output=_STATUS_OUTPUT,
        ),
    }
    # The clone exposes no acknowledged stop for this actuator.  Declaring a
    # binding here would invent an endpoint the pinned source does not contain.
    safety_bindings = {}
