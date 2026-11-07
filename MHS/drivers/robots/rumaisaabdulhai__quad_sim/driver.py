"""OpenMHS rosbridge driver for the rumaisaabdulhai/quad_sim ROS 1 simulator.

The pinned repository is an indoor quadcopter application built from ROS 1
packages: Gazebo worlds and a hector quadrotor model, PX4/MAVROS launch files,
teleoperation, mapping, move_base navigation and a results recorder.  The
``Results`` node subscribes to ``/ground_truth_to_tf/pose`` and
``/move_base/status``, accumulates planar distance, elapsed time and average
speed, and writes a pandas CSV when an ``Empty`` message arrives on
``/results_saver``.  It computes those metrics in process; no ROS service or
topic publishes them and no service accepts a stop, reset or step request.

This package is a configuration-only :class:`RosDriver` over rosbridge.  It
declares no Python native class and neither imports nor launches the clone.
It exposes the two observations that feed the results recorder and the
take-off/land node: one fresh ``geometry_msgs/PoseStamped`` sample from
``/ground_truth_to_tf/pose`` and one fresh ``actionlib_msgs/GoalStatusArray``
sample from ``/move_base/status``.  Each is an explicit subscription action;
the main resource snapshot is empty, so a silent topic fails only the
observation that asked for it.

The upstream motion surface (``/cmd_vel``, ``/quadcopter_land``, the
PX4/MAVROS setpoint and service calls, and move_base goals) is deliberately
not bound.  The results node and the take-off/land node expose no acknowledged
stop service or action, a zero-velocity publication is transmission-only, and
the repository has no world pause, step or reset endpoint.  A control profile
would therefore need a stop contract the pinned source does not provide; this
package claims only the read profile.  NOT COVERED: the in-process distance,
time and average-speed calculations, the CSV file written by the results node,
takeoff, landing, teleoperation, navigation, mapping, PX4/MAVROS and Gazebo
stepping.

Every endpoint, type and fact cites the pinned clone at
01d02f6e2fad8060d6522b7bca01cb82aa038c2a.  The fake transport is ROS-free;
no ROS graph, Gazebo process, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references (paths are relative to the clone root)
# ---------------------------------------------------------------------------

#: The Results constructor calls rospy.init_node and creates the three
#: subscribers: pose, move_base status and the Empty results-saver trigger.
_RESULTS_INIT_REF = "quadcopter_results/src/quadcopter_results.py:50-76"

#: The Results module imports geometry_msgs PoseStamped and actionlib_msgs
#: GoalStatusArray.
_RESULTS_TYPES_REF = "quadcopter_results/src/quadcopter_results.py:17-19"

#: The Results node subscribes to the absolute /ground_truth_to_tf/pose topic
#: with PoseStamped.
_POSE_SOURCE_REF = "quadcopter_results/src/quadcopter_results.py:74"

#: The Results node subscribes to the absolute /move_base/status topic with
#: GoalStatusArray.
_STATUS_SOURCE_REF = "quadcopter_results/src/quadcopter_results.py:75"

#: pose_cb stores the previous and current PoseStamped samples and accumulates
#: distance only while the recorder is active.
_POSE_CALLBACK_REF = "quadcopter_results/src/quadcopter_results.py:226-237"

#: get_delta_dist computes planar Euclidean distance from pose x and y.
_DELTA_DIST_REF = "quadcopter_results/src/quadcopter_results.py:94-110"

#: set_total_dist adds the measured delta to total_dist.
_SET_TOTAL_DIST_REF = "quadcopter_results/src/quadcopter_results.py:174-176"

#: status_cb reads status_list[0], records its goal_id stamp and uses status 3
#: as the completion value.
_STATUS_CALLBACK_REF = "quadcopter_results/src/quadcopter_results.py:201-216"

#: After completion, status_cb computes elapsed time and average speed, appends
#: a dataframe row, resets the recorder and increments GOAL_NUM.
_STATUS_COMPLETE_REF = "quadcopter_results/src/quadcopter_results.py:218-224"

#: set_elapsed_time and set_avg_speed define the in-process metrics.
_METRICS_REF = "quadcopter_results/src/quadcopter_results.py:178-196"

#: create_df declares the five recorded columns.
_COLUMNS_REF = "quadcopter_results/src/quadcopter_results.py:31-36"

#: append_df rounds the final position, elapsed time, total distance and
#: average speed (154-163) and writes them into the dataframe (165-170).
_APPEND_REF = "quadcopter_results/src/quadcopter_results.py:154-170"

#: save_results_cb writes the dataframe to a hard-coded home-directory path.
_SAVE_REF = "quadcopter_results/src/quadcopter_results.py:239-249"

#: The whole Results constructor: it creates subscribers and calls rospy.spin;
#: it creates no service server.
_SPIN_REF = "quadcopter_results/src/quadcopter_results.py:45-79"

#: The take-off/land node subscribes to move_base feedback, cmd_vel, the
#: ground-truth pose and the landing trigger, and publishes cmd_vel.
_TAKEOFF_LAND_REF = "quadcopter_takeoff_land/src/quadcopter_takeoff_land.py:31-38"

#: The take-off/land node advertises its Twist publisher on /cmd_vel.
_TAKEOFF_PUB_REF = "quadcopter_takeoff_land/src/quadcopter_takeoff_land.py:38"

#: The teleoperation node advertises a Twist publisher on /cmd_vel.
_TELEOP_PUB_REF = "quadcopter_teleop/src/quadcopter_teleop.py:92"

#: The results launch starts quadcopter_results.py as the quad_results node.
_RESULTS_LAUNCH_REF = "quadcopter_results/launch/quadcopter_results.launch:3"

#: The quadcopter launch includes gazebo_ros/empty_world.launch with the
#: school world and spawns the hector quadrotor model.
_GAZEBO_LAUNCH_REF = "quadcopter_gazebo/launch/quadcopter.launch:11-29"

#: The navigation documentation publishes /quadcopter_land at 5 Hz.
_LAND_DOC_REF = "docs/navigation.md:56"

#: The project index describes the mapping and move_base navigation scope.
_INDEX_REF = "docs/index.md:21-26"

# ---------------------------------------------------------------------------
# Wire schemas
# ---------------------------------------------------------------------------

_STAMP = Field(
    "object",
    description="ROS 1 time stamp as seconds and nanoseconds",
    properties={
        "secs": Field("integer", unit="s", description="Whole seconds of the ROS time stamp"),
        "nsecs": Field("integer", unit="ns", description="Nanoseconds within the ROS second"),
    },
)

_HEADER = Field(
    "object",
    description="ROS 1 std_msgs/Header",
    properties={
        "seq": Field("integer", unit="1", description="Message sequence number"),
        "stamp": _STAMP,
        "frame_id": Field("string", description="Coordinate frame of the message"),
    },
)

_POSITION = Field(
    "object",
    description="Position in the message frame",
    properties={
        "x": Field("number", unit="m", description="Position x"),
        "y": Field("number", unit="m", description="Position y"),
        "z": Field("number", unit="m", description="Position z"),
    },
)

_ORIENTATION = Field(
    "object",
    description="Orientation as an x, y, z, w quaternion",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)

_POSE = Field(
    "object",
    description="geometry_msgs/Pose",
    properties={"position": _POSITION, "orientation": _ORIENTATION},
)

_POSE_STAMPED = Field(
    "object",
    description="One geometry_msgs/PoseStamped message",
    properties={"header": _HEADER, "pose": _POSE},
)

_GOAL_ID = Field(
    "object",
    description="actionlib_msgs/GoalID",
    properties={
        "id": Field("string", description="Goal identifier as published"),
        "stamp": _STAMP,
    },
)

_GOAL_STATUS = Field(
    "object",
    description="One actionlib_msgs/GoalStatus entry",
    properties={
        "goal_id": _GOAL_ID,
        "status": Field(
            "integer",
            unit="1",
            description="uint8 status code as published; the Results node treats 3 as complete",
        ),
        "text": Field("string", description="Status text as published"),
    },
)

_GOAL_STATUS_ARRAY = Field(
    "object",
    description="One actionlib_msgs/GoalStatusArray message",
    properties={
        "header": _HEADER,
        "status_list": Field(
            "array",
            description="Goal status entries in the message's wire order",
            items=_GOAL_STATUS,
        ),
    },
)

# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------

#: Each observation opens a fresh subscription and waits for one matching
#: publication.  The endpoint literals and types are shown on the cited lines.
_POSE_COMMAND = {
    "topic": "/ground_truth_to_tf/pose",
    "type": "geometry_msgs/PoseStamped",
    "operation": "subscribe",
    "source_name": "/ground_truth_to_tf/pose",
    "source_ref": _POSE_SOURCE_REF,
    "type_ref": _RESULTS_TYPES_REF,
    "result": {"map": {"pose": "$"}},
}

_STATUS_COMMAND = {
    "topic": "/move_base/status",
    "type": "actionlib_msgs/GoalStatusArray",
    "operation": "subscribe",
    "source_name": "/move_base/status",
    "source_ref": _STATUS_SOURCE_REF,
    "type_ref": _RESULTS_TYPES_REF,
    "result": {"map": {"goal_status": "$"}},
}

_POSE_CAP = "x-cap.rumaisaabdulhai.ground_truth_pose.v1"
_STATUS_CAP = "x-cap.rumaisaabdulhai.goal_status.v1"


class QuadSim(RosDriver):
    """Configuration-only ROS 1 rosbridge observations for the quad_sim application."""

    device_id = "quad_sim"
    device_kind = "world.sim"
    mode = "simulated"
    #: The card's risk floor is R1.  This profile binds only topic observations:
    #: it commands no motion and exposes no stop, reset or stepping endpoint.
    risk = "R1"
    ros_version = 1
    backends = {"fake": ".fake:FakeQuadSim"}
    tags = ["ros", "ros1", "simulation", "gazebo", "quadcopter", "results", "pose", "move-base"]
    display_name = "quad_sim indoor quadcopter simulation"
    vendor = "rumaisaabdulhai"
    model = "ROS 1 Gazebo quadcopter application with a results recorder"

    facts = [
        Fact(
            "The Results constructor calls rospy.init_node('quad_results') and creates subscribers on "
            "/ground_truth_to_tf/pose (PoseStamped), /move_base/status (GoalStatusArray) and "
            "/results_saver (Empty).",
            source="upstream_code",
            ref=_RESULTS_INIT_REF,
        ),
        Fact(
            "The Results module imports geometry_msgs PoseStamped and actionlib_msgs GoalStatusArray.",
            source="upstream_code",
            ref=_RESULTS_TYPES_REF,
        ),
        Fact(
            "pose_cb stores the previous and current PoseStamped samples and calls set_total_dist only "
            "while isActive is true.",
            source="upstream_code",
            ref=_POSE_CALLBACK_REF,
        ),
        Fact(
            "get_delta_dist computes the planar Euclidean distance from the previous and current pose "
            "position x and y.",
            source="upstream_code",
            ref=_DELTA_DIST_REF,
        ),
        Fact(
            "set_total_dist adds the get_delta_dist result to total_dist.",
            source="upstream_code",
            ref=_SET_TOTAL_DIST_REF,
        ),
        Fact(
            "status_cb reads status_list[0], records its goal_id stamp seconds as init_time, sets "
            "isActive when the status is not 3 and sets isComplete when the status is 3.",
            source="upstream_code",
            ref=_STATUS_CALLBACK_REF,
        ),
        Fact(
            "After completion status_cb calls set_elapsed_time, set_avg_speed, append_df and "
            "reset_params, then increments GOAL_NUM.",
            source="upstream_code",
            ref=_STATUS_COMPLETE_REF,
        ),
        Fact(
            "set_elapsed_time subtracts init_time from final_time and set_avg_speed divides total_dist "
            "by elapsed_time.",
            source="upstream_code",
            ref=_METRICS_REF,
        ),
        Fact(
            "create_df declares the columns Goal, Final Position, Elapsed Time, Distance Traveled and "
            "Average Speed.",
            source="upstream_code",
            ref=_COLUMNS_REF,
        ),
        Fact(
            "append_df writes the rounded final position, elapsed time, total distance and average speed "
            "into the dataframe.",
            source="upstream_code",
            ref=_APPEND_REF,
        ),
        Fact(
            "save_results_cb writes the dataframe to the literal path "
            "~/catkin_ws/src/quadcopter_sim/quadcopter_results/src/Results.csv when /results_saver "
            "receives an Empty message.",
            source="upstream_code",
            ref=_SAVE_REF,
        ),
        Fact(
            "The Results constructor creates rospy.Subscriber objects, creates a rospy.Rate(5) and then "
            "calls rospy.spin; it creates no ROS service server.",
            source="upstream_code",
            ref=_SPIN_REF,
        ),
        Fact(
            "The take-off/land node subscribes to /move_base/feedback, /cmd_vel, "
            "/ground_truth_to_tf/pose and /quadcopter_land, and creates a Twist publisher on /cmd_vel.",
            source="upstream_code",
            ref=_TAKEOFF_LAND_REF,
        ),
        Fact(
            "The take-off/land node advertises a Twist publisher on /cmd_vel with queue size 1.",
            source="upstream_code",
            ref=_TAKEOFF_PUB_REF,
        ),
        Fact(
            "The teleoperation node advertises a Twist publisher on /cmd_vel with queue size 5.",
            source="upstream_code",
            ref=_TELEOP_PUB_REF,
        ),
        Fact(
            "The results launch starts quadcopter_results.py as the quad_results node.",
            source="upstream_code",
            ref=_RESULTS_LAUNCH_REF,
        ),
        Fact(
            "The quadcopter launch includes gazebo_ros/launch/empty_world.launch with the school world "
            "and spawns the hector quadrotor model.",
            source="upstream_code",
            ref=_GAZEBO_LAUNCH_REF,
        ),
        Fact(
            "The navigation documentation instructs the operator to publish /quadcopter_land at 5 Hz "
            "as std_msgs/Empty.",
            source="vendor_doc",
            ref=_LAND_DOC_REF,
        ),
        Fact(
            "The project index describes mapping with gmapping or cartographer and autonomous "
            "navigation with move_base.",
            source="vendor_doc",
            ref=_INDEX_REF,
        ),
    ]

    safe_state = (
        "No actuation is bound: the results and take-off/land nodes expose only ROS topics and no "
        "acknowledged stop service or action, so an MHS e-stop is the runtime software latch and "
        "commands no native stop. Gazebo and the simulated quadcopter keep running under whatever "
        "publishes /cmd_vel (the take-off/land hover loop, teleoperation or move_base)."
    )

    #: The checked backend is a ROS-free canned transport, not a replay of
    #: captured traffic and not the upstream Gazebo simulator.  It has no
    #: physics, pacing, ROS graph or world step.
    fidelity = {
        "engine": "canned:ROS-free topic stand-in (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned responses with no physics step, pacing or state-hash replay; "
                     "the same placeholder message is returned on every subscription",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free canned transport: it answers the declared /ground_truth_to_tf/pose "
            "and /move_base/status subscriptions and runs no Gazebo physics, PX4 SITL, MAVROS, "
            "gmapping, cartographer, move_base, TF or wall-clock loop",
            "all pose, orientation, stamp and goal-status values are placeholders and do not establish "
            "a trajectory, sensor frame, navigation outcome or timing",
            "the results node computes planar distance, elapsed time and average speed in process and "
            "writes a CSV to a hard-coded home-directory path; this package observes the input topics "
            "but does not read the CSV and does not reproduce those calculations",
            "the upstream status_list length is not fixed by the clone; the fake returns one "
            "placeholder GoalStatus entry",
            "the upstream Results constructor creates a rospy.Rate(5) that the node never sleeps on and "
            "then calls rospy.spin, so its callbacks run on message arrival; the fake answers each "
            "subscription once with one canned message",
            "no motion, takeoff, landing, teleoperation, navigation, mapping, PX4/MAVROS command or "
            "move_base goal is bound, and no acknowledged stop, pause, step or reset endpoint exists "
            "in the pinned source; /cmd_vel, /quadcopter_land and /results_saver are not exposed",
            "the fake does not model ROS parameters, QoS, namespaces, remapping, TF, the move_base "
            "action protocol, Gazebo contacts or the full live message arrays",
        ],
    }

    # Each observation is an explicit subscription.  The main resource has no
    # automatic reads, so a silent topic cannot block the stock resource
    # snapshot and the snapshot stays empty.
    commands = {
        _POSE_CAP: _POSE_COMMAND,
        _STATUS_CAP: _STATUS_COMMAND,
    }

    actions = {
        _POSE_CAP: Action(
            name="read_ground_truth_pose",
            verb="read",
            description=(
                "Read one fresh geometry_msgs/PoseStamped sample from the Results node's "
                "/ground_truth_to_tf/pose subscription. The action returns the wire pose and header; it "
                "does not compute distance and does not claim a trajectory."
            ),
            output={"pose": _POSE_STAMPED},
        ),
        _STATUS_CAP: Action(
            name="read_goal_status",
            verb="read",
            description=(
                "Read one fresh actionlib_msgs/GoalStatusArray sample from the Results node's "
                "/move_base/status subscription. The action returns the wire status list; it does not "
                "reach a goal and does not claim navigation completion."
            ),
            output={"goal_status": _GOAL_STATUS_ARRAY},
        ),
    }
