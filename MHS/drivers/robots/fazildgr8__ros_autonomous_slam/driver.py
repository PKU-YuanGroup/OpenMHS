"""OpenMHS rosbridge driver for the fazildgr8 ROS 1 exploration stack.

The pinned repository is a ROS 1 catkin package that runs a TurtleBot3 in
Gazebo, explores with GMAPPING and RRT or wall-following, and asks the
Navigation Stack's ``move_base`` action to reach frontier goals.  It is a task
environment, not a device with an operator-facing command service: its nodes
publish ``/cmd_vel`` and call ``/move_base`` internally, while no upstream
service or action accepts an operator motion request and no acknowledged stop
is registered.

This package therefore binds observations only: the occupancy grid the
explorer consumes (``/map``), the clustered frontier targets it publishes
(``/filtered_points``), the odometry it consumes (``/odom``), the laser scan
used by wall following (``/scan``), and the operator's region points on
``/clicked_point`` as they are published.  Each is an explicit subscription
action, not an automatic resource snapshot.  The internal ``/cmd_vel``
publication is not bound as a command: a rosbridge publication is
transmission-only and a zero-velocity publication is not an acknowledged stop.
The five ``/clicked_point`` messages that start RRT exploration are likewise
not published by this package, because no acknowledged stop exists once the
explorer starts.  A deployment that needs operator motion control is outside
this profile.

The upstream is C++/Python ROS 1 without a Python native class.  This is a
configuration-only :class:`RosDriver`; it declares no ``native`` class, does
not import ROS, and does not launch Gazebo or the upstream nodes.  Every
endpoint, type and fact cites the pinned clone at
997c968cb64f544b913e72debcceaad0ed2faea9.  The fake transport is ROS-free and
all of its message values are placeholders.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: The RRT explorer subscribes to the SLAM map on the absolute /map topic.
_MAP_SOURCE_REF = "nodes/autonomous_rrt.py:180"

#: The same file imports nav_msgs/Odometry and nav_msgs/OccupancyGrid.
_MAP_TYPE_REF = "nodes/autonomous_rrt.py:10"

#: The RRT explorer subscribes to odometry on the absolute /odom topic.
_ODOM_SOURCE_REF = "nodes/autonomous_rrt.py:179"

#: The same nav_msgs import names the Odometry type.
_ODOM_TYPE_REF = "nodes/autonomous_rrt.py:10"

#: filter.py publishes the clustered frontier points on relative "filtered_points".
_FRONTIERS_SOURCE_REF = "scripts/filter.py:112"

#: filter.py imports the package's PointArray message.
_FRONTIERS_TYPE_REF = "scripts/filter.py:14"

#: wall_follow.py subscribes to the absolute /scan topic.
_SCAN_SOURCE_REF = "nodes/wall_follow.py:61"

#: The same file imports sensor_msgs/LaserScan.
_SCAN_TYPE_REF = "nodes/wall_follow.py:11"

#: The global RRT detector subscribes to the operator's /clicked_point topic.
_REGION_SOURCE_REF = "src/global_rrt_detector.cpp:81"

#: The same file includes the geometry_msgs/PointStamped header.
_REGION_TYPE_REF = "src/global_rrt_detector.cpp:13"

_STAMP = Field(
    "object",
    description="ROS time or header stamp",
    properties={
        "secs": Field("integer", unit="s", description="Whole seconds of the ROS stamp"),
        "nsecs": Field("integer", unit="ns", description="Nanoseconds within the ROS second"),
    },
)

_HEADER = Field(
    "object",
    description="ROS 1 message header",
    properties={
        "seq": Field("integer", unit="1", description="Message sequence number"),
        "stamp": _STAMP,
        "frame_id": Field("string", description="Coordinate frame of the message"),
    },
)

_POSITION = Field(
    "object",
    description="Position in the ROS message frame",
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

_POINT = Field(
    "object",
    description="One geometry_msgs/Point",
    properties={
        "x": Field("number", unit="m", description="Point x"),
        "y": Field("number", unit="m", description="Point y"),
        "z": Field("number", unit="m", description="Point z"),
    },
)

_MAP_MESSAGE = Field(
    "object",
    description="One nav_msgs/OccupancyGrid message",
    properties={
        "header": _HEADER,
        "info": Field(
            "object",
            description="nav_msgs/MapMetaData",
            properties={
                "map_load_time": _STAMP,
                "resolution": Field("number", unit="m", description="Metres per grid cell"),
                "width": Field("integer", unit="1", description="Grid width in cells"),
                "height": Field("integer", unit="1", description="Grid height in cells"),
                "origin": Field(
                    "object",
                    description="geometry_msgs/Pose of the grid origin",
                    properties={"position": _POSITION, "orientation": _ORIENTATION},
                ),
            },
        ),
        "data": Field(
            "array",
            description="Occupancy values in row-major order: -1 unknown, 0 free, 100 occupied",
            items=Field("integer", unit="1", description="One occupancy value"),
        ),
    },
)

_FRONTIERS_MESSAGE = Field(
    "object",
    description="One ros_autonomous_slam/PointArray message",
    properties={
        "points": Field(
            "array",
            description="Frontier target points in the filter's global map frame; PointArray has no header",
            items=_POINT,
        ),
    },
)

_REGION_MESSAGE = Field(
    "object",
    description="One geometry_msgs/PointStamped message",
    properties={
        "header": _HEADER,
        "point": _POINT,
    },
)

_ODOM_MESSAGE = Field(
    "object",
    description="One nav_msgs/Odometry message",
    properties={
        "header": _HEADER,
        "child_frame_id": Field("string", description="Child coordinate frame"),
        "pose": Field(
            "object",
            description="geometry_msgs/PoseWithCovariance",
            properties={
                "pose": Field(
                    "object",
                    description="geometry_msgs/Pose",
                    properties={"position": _POSITION, "orientation": _ORIENTATION},
                ),
                "covariance": Field(
                    "array",
                    unit="1",
                    description="Row-major 6 by 6 pose covariance",
                    items=Field("number", unit="1", description="One covariance entry"),
                    length=36,
                ),
            },
        ),
        "twist": Field(
            "object",
            description="geometry_msgs/TwistWithCovariance",
            properties={
                "twist": Field(
                    "object",
                    description="geometry_msgs/Twist",
                    properties={
                        "linear": Field(
                            "object",
                            description="Linear velocity in the ROS Twist convention",
                            properties={
                                "x": Field("number", unit="m/s", description="Linear x"),
                                "y": Field("number", unit="m/s", description="Linear y"),
                                "z": Field("number", unit="m/s", description="Linear z"),
                            },
                        ),
                        "angular": Field(
                            "object",
                            description="Angular velocity in the ROS Twist convention",
                            properties={
                                "x": Field("number", unit="rad/s", description="Angular x"),
                                "y": Field("number", unit="rad/s", description="Angular y"),
                                "z": Field("number", unit="rad/s", description="Angular z"),
                            },
                        ),
                    },
                ),
                "covariance": Field(
                    "array",
                    unit="1",
                    description="Row-major 6 by 6 twist covariance",
                    items=Field("number", unit="1", description="One covariance entry"),
                    length=36,
                ),
            },
        ),
    },
)

_SCAN_MESSAGE = Field(
    "object",
    description="One sensor_msgs/LaserScan message",
    properties={
        "header": _HEADER,
        "angle_min": Field("number", unit="rad", description="Start angle of the first range sample"),
        "angle_max": Field("number", unit="rad", description="End angle of the last range sample"),
        "angle_increment": Field("number", unit="rad", description="Angular distance between samples"),
        "time_increment": Field("number", unit="s", description="Time between samples"),
        "scan_time": Field("number", unit="s", description="Time between scans"),
        "range_min": Field("number", unit="m", description="Minimum sensor range"),
        "range_max": Field("number", unit="m", description="Maximum sensor range"),
        "ranges": Field(
            "array",
            description=("Measured ranges in metres; a scan carrying a non-finite range is refused by the "
                         "bridge, never reported with a substituted number"),
            items=Field("number", unit="m", description="One range"),
        ),
        "intensities": Field(
            "array",
            description="Per-sample intensities as published by the sensor",
            items=Field("number", unit="1", description="One intensity"),
        ),
    },
)


class RosAutonomousSlam(RosDriver):
    """Configuration-only ROS 1 rosbridge observations for the exploration stack."""

    device_id = "ros_autonomous_slam"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeRosAutonomousSlam"}
    tags = ["ros", "ros1", "simulation", "gazebo", "turtlebot3", "slam", "exploration", "rrt"]
    display_name = "ros_autonomous_slam TurtleBot3 exploration stack"
    vendor = "fazildgr8"
    model = "TurtleBot3 Waffle Pi in Gazebo with GMAPPING and RRT exploration"

    facts = [
        Fact(
            "The README describes a ROS package that uses the Navigation Stack, GMAPPING and a Gazebo "
            "TurtleBot3 Waffle Pi to explore an unknown environment and build a map.",
            source="vendor_doc",
            ref="README.md:3",
        ),
        Fact(
            "The autonomous explorer launch includes the SLAM launch, the turtlebot3_navigation move_base "
            "launch and the selected explorer launch.",
            source="upstream_code",
            ref="launch/autonomous_explorer.launch:6-18",
        ),
        Fact(
            "The RRT launch passes /map as map_topic to both RRT detectors and to filter.py, and passes "
            "/filtered_points as frontiers_topic to assigner.py.",
            source="upstream_code",
            ref="launch/RRT.launch:9-38",
        ),
        Fact(
            "The RRT explorer imports nav_msgs/Odometry and nav_msgs/OccupancyGrid.",
            source="upstream_code",
            ref="nodes/autonomous_rrt.py:10",
        ),
        Fact(
            "The RRT explorer subscribes to the absolute /odom and /map topics with those message types.",
            source="upstream_code",
            ref="nodes/autonomous_rrt.py:178-180",
        ),
        Fact(
            "filter.py imports the package's PointArray message from ros_autonomous_slam.msg.",
            source="upstream_code",
            ref="scripts/filter.py:14",
        ),
        Fact(
            "filter.py creates a PointArray publisher on the relative topic 'filtered_points' with queue "
            "size 10.",
            source="upstream_code",
            ref="scripts/filter.py:112",
        ),
        Fact(
            "PointArray.msg defines the message as an array of geometry_msgs/Point named points.",
            source="upstream_code",
            ref="msg/PointArray.msg:3",
        ),
        Fact(
            "filter.py appends the clustered centroids to arraypoints and publishes the PointArray on "
            "filterpub.",
            source="upstream_code",
            ref="scripts/filter.py:221-226",
        ),
        Fact(
            "assigner.py subscribes to frontiers_topic as a PointArray.",
            source="upstream_code",
            ref="scripts/assigner.py:57",
        ),
        Fact(
            "The assigner sends the winning centroid with robots[id_record[winner_id]].sendGoal.",
            source="upstream_code",
            ref="scripts/assigner.py:145",
        ),
        Fact(
            "wall_follow.py creates a LaserScan subscriber on the absolute /scan topic and a Twist "
            "publisher on the absolute /cmd_vel topic.",
            source="upstream_code",
            ref="nodes/wall_follow.py:60-61",
        ),
        Fact(
            "wall_follow.py copies the LaserScan ranges into x and loops over 360 bins.",
            source="upstream_code",
            ref="nodes/wall_follow.py:36-37",
        ),
        Fact(
            "After its control loop exits, wall_follow.py publishes a zero Twist and prints "
            "'Turtlebot stopped'.",
            source="upstream_code",
            ref="nodes/wall_follow.py:97-103",
        ),
        Fact(
            "The RRT explorer creates an actionlib SimpleActionClient for move_base and sends a "
            "MoveBaseGoal; this is an internal navigation call, not an upstream command server.",
            source="upstream_code",
            ref="nodes/autonomous_rrt.py:126-141",
        ),
        Fact(
            "The README tells the operator to define the exploration region with boundary and "
            "start points using the RVIZ Publish Points option.",
            source="vendor_doc",
            ref="README.md:34-35",
        ),
        Fact(
            "The global RRT detector subscribes to the absolute /clicked_point topic.",
            source="upstream_code",
            ref="src/global_rrt_detector.cpp:81",
        ),
        Fact(
            "The global RRT detector includes geometry_msgs/PointStamped.h.",
            source="upstream_code",
            ref="src/global_rrt_detector.cpp:13",
        ),
        Fact(
            "The global RRT detector waits until five clicked points have been collected, then uses "
            "points 0, 2 and 4 as the region corners and start point.",
            source="upstream_code",
            ref="src/global_rrt_detector.cpp:132-175",
        ),
    ]

    safe_state = (
        "No actuation is bound: the upstream nodes publish /cmd_vel and call the external /move_base action "
        "internally, while this package only subscribes to /map, /filtered_points, /clicked_point, /odom and "
        "/scan, so an e-stop is the runtime software latch and no physical safe state is claimed."
    )

    #: The fake is a ROS-free canned topic stand-in.  It replays no captured
    #: traffic and runs no Gazebo physics, GMAPPING, RRT, wall-following or
    #: move_base loop.
    fidelity = {
        "engine": "canned:ROS-free topic stand-in (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned responses with no physics step, pacing or state-hash replay; the "
                     "same placeholder messages are returned on every subscription",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free canned transport: it answers the declared /map, /filtered_points, /odom "
            "and /scan subscriptions and runs no Gazebo physics, GMAPPING, SLAM, RRT, wall-following, TF, "
            "move_base or wall-clock loop",
            "all map, frontier, odometry and scan values are placeholders and do not establish a trajectory, "
            "sensor frame, collision state or timing",
            "the fake returns a 4 by 3 map with 12 occupancy cells and 3 frontier points; the live map size "
            "is the OccupancyGrid width times height and the live frontier count is the filtered cluster "
            "count, neither of which is fixed by the clone",
            "the fake returns 8 LaserScan ranges; wall_follow.py loops over 360 bins (wall_follow.py:36-37) "
            "and the RRT nodes allocate 384 by 384 map buffers (autonomous_rrt.py:24), but these are code "
            "assumptions, not a universal live array size",
            "the upstream publishes /cmd_vel internally and calls the external /move_base action; this "
            "package does not bind either as a command and does not simulate motion, navigation, a stop "
            "service or an emergency stop",
            "the /clicked_point observation shows one operator point at a time; the RRT detectors "
            "accumulate five points in order (src/global_rrt_detector.cpp:132-175), and this package does "
            "not publish them or start exploration",
            "the upstream filtered_points message has no header, so the frontiers observation carries no "
            "sample time",
            "no world step, reset, snapshot, Gazebo service, ROS graph, TF or QoS configuration is exposed "
            "or validated; the operator runs the upstream nodes and rosbridge separately",
            "the bridge refuses non-finite JSON numbers, so a live LaserScan whose ranges carry a no-return "
            "value encoded as a non-finite number fails the scan observation instead of returning it; the fake "
            "publishes finite placeholder ranges except in its non-finite test case",
            "every observation subscribes with the 2 s wire default; /clicked_point is published only when an "
            "operator publishes a point in RViz (README.md:34-35), so that read fails unless a point arrives "
            "within 2 s",
            "messages are bounded by the 1 MiB rosbridge default; a live OccupancyGrid whose JSON exceeds it is "
            "refused, not truncated, and the clone does not fix the live map size",
        ],
    }

    # Each observation is an explicit subscription.  The main resource has no
    # automatic reads, so a silent topic cannot block the stock resource
    # snapshot and the snapshot stays empty.
    commands = {
        "x-cap.fazildgr8.occupancy_map.v1": {
            "topic": "/map",
            "type": "nav_msgs/OccupancyGrid",
            "operation": "subscribe",
            "source_name": "/map",
            "source_ref": _MAP_SOURCE_REF,
            "type_ref": _MAP_TYPE_REF,
            "result": {"map": {"map": "$"}},
        },
        "x-cap.fazildgr8.frontiers.v1": {
            "topic": "/filtered_points",
            "type": "ros_autonomous_slam/PointArray",
            "operation": "subscribe",
            "source_name": "filtered_points",
            "source_ref": _FRONTIERS_SOURCE_REF,
            "type_ref": _FRONTIERS_TYPE_REF,
            "result": {"map": {"frontiers": "$"}},
        },
        "x-cap.fazildgr8.exploration_region.v1": {
            "topic": "/clicked_point",
            "type": "geometry_msgs/PointStamped",
            "operation": "subscribe",
            "source_name": "/clicked_point",
            "source_ref": _REGION_SOURCE_REF,
            "type_ref": _REGION_TYPE_REF,
            "result": {"map": {"region_point": "$"}},
        },
        "x-cap.fazildgr8.odometry.v1": {
            "topic": "/odom",
            "type": "nav_msgs/Odometry",
            "operation": "subscribe",
            "source_name": "/odom",
            "source_ref": _ODOM_SOURCE_REF,
            "type_ref": _ODOM_TYPE_REF,
            "result": {"map": {"odometry": "$"}},
        },
        "x-cap.fazildgr8.scan.v1": {
            "topic": "/scan",
            "type": "sensor_msgs/LaserScan",
            "operation": "subscribe",
            "source_name": "/scan",
            "source_ref": _SCAN_SOURCE_REF,
            "type_ref": _SCAN_TYPE_REF,
            "result": {"map": {"scan": "$"}},
        },
    }

    actions = {
        "x-cap.fazildgr8.occupancy_map.v1": Action(
            name="read_occupancy_map",
            verb="read",
            description="Read one fresh nav_msgs/OccupancyGrid publication from the exploration stack's /map topic.",
            output={"map": _MAP_MESSAGE},
        ),
        "x-cap.fazildgr8.frontiers.v1": Action(
            name="read_frontiers",
            verb="read",
            description="Read one fresh PointArray of clustered frontier targets from /filtered_points.",
            output={"frontiers": _FRONTIERS_MESSAGE},
        ),
        "x-cap.fazildgr8.exploration_region.v1": Action(
            name="read_exploration_region",
            verb="read",
            description=(
                "Read one fresh operator-published geometry_msgs/PointStamped from /clicked_point. The RRT "
                "detectors accumulate five such points; this action shows one point and does not publish "
                "the region or start exploration."
            ),
            output={"region_point": _REGION_MESSAGE},
        ),
        "x-cap.fazildgr8.odometry.v1": Action(
            name="read_odometry",
            verb="read",
            description="Read one fresh nav_msgs/Odometry publication from the exploration stack's /odom topic.",
            output={"odometry": _ODOM_MESSAGE},
        ),
        "x-cap.fazildgr8.scan.v1": Action(
            name="read_scan",
            verb="read",
            description="Read one fresh sensor_msgs/LaserScan publication from the exploration stack's /scan topic.",
            output={"scan": _SCAN_MESSAGE},
        ),
    }
