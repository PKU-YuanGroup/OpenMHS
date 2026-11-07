"""OpenMHS rosbridge driver for the ENPS-DWA social-navigation simulator (gh.rgnc/enps_dwa).

The upstream ``enps_dwa_node`` is a C++ ROS 1 node that runs a self-contained
social-force pedestrian simulation and an ENPS/DWA robot planner.  It advances
the world on its own ``ros::Rate`` loop and publishes observations; the pinned
node registers no subscriber, service server or action server.  This package is
therefore a configuration-only :class:`RosDriver` over rosbridge that observes
the robot odometry and the simulated 360-degree laser scan.  It declares no
Python native class and it imports, launches or executes nothing from the clone.

An environment-step or velocity-command capability is deliberately absent: the
pinned simulator has no such input, and inventing one would misstate the device.
A live deployment runs the upstream node and rosbridge separately; this package
opens no connection, starts no ROS graph and runs no physics.

Review note (model review of wave C, not the author's text): the node's robot
drives itself under the ENPS/DWA planner, so an MHS e-stop is a software latch
on this package's reads only and the simulation keeps running.  At start-up
the node calls map_server's ``static_map`` once and aborts if it is not yet
served (see the facts and gaps).

Every endpoint, type and fact cites the pinned clone at
ce876244db34e9684b0517253d5adf83bc04cc7c.  The fake transport is ROS-free; no
ROS graph, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: The node declares the odom topic parameter with the default absolute name
#: ``/odom`` on this line.
_ODOM_REF = "src/enps_dwa_node.cpp:545"

#: The same node advertises nav_msgs::Odometry on the configured topic.
_ODOM_TYPE_REF = "src/enps_dwa_node.cpp:553"

#: The node declares the scan topic parameter with the default absolute name
#: ``/scan360`` on this line.
_SCAN_REF = "src/enps_dwa_node.cpp:549"

#: The same node advertises sensor_msgs::LaserScan on the configured topic.
_SCAN_TYPE_REF = "src/enps_dwa_node.cpp:556"

_ODOM_CAP = "x-cap.rgnc.enps_dwa_odometry.v1"
_SCAN_CAP = "x-cap.rgnc.enps_dwa_scan.v1"


def _position(description: str) -> Field:
    return Field("object", description=description, properties={
        "x": Field("number", unit="m", description="x component in the message frame"),
        "y": Field("number", unit="m", description="y component in the message frame"),
        "z": Field("number", unit="m", description="z component in the message frame"),
    })


def _vector3(description: str, unit: str) -> Field:
    return Field("object", description=description, properties={
        "x": Field("number", unit=unit, description="x component"),
        "y": Field("number", unit=unit, description="y component"),
        "z": Field("number", unit=unit, description="z component"),
    })


def _stamp() -> Field:
    return Field("object", description="ROS header stamp of the observed message", properties={
        "secs": Field("integer", unit="s", description="Whole seconds"),
        "nsecs": Field("integer", unit="ns", description="Nanoseconds within the second"),
    })


_ODOMETRY_OUTPUT = {
    "pose": Field("object", description="Robot pose from nav_msgs/Odometry pose.pose", properties={
        "position": _position("Position in the odometry frame"),
        "orientation": Field("object", description="Orientation quaternion", properties={
            "x": Field("number", description="Quaternion x"),
            "y": Field("number", description="Quaternion y"),
            "z": Field("number", description="Quaternion z"),
            "w": Field("number", description="Quaternion w"),
        }),
    }),
    "twist": Field("object", description="Robot velocity from nav_msgs/Odometry twist.twist", properties={
        "linear": _vector3("Linear velocity", "m/s"),
        "angular": _vector3("Angular velocity", "rad/s"),
    }),
    "frame_id": Field("string", description="Frame in which the odometry pose is expressed"),
    "child_frame_id": Field("string", description="Child frame in which the odometry twist is expressed"),
    "stamp": _stamp(),
}

_SCAN_MESSAGE = Field(
    "object",
    description="One sensor_msgs/LaserScan message as published by the simulator",
    properties={
        "header": Field("object", description="ROS header of the scan", properties={
            "seq": Field("integer", description="ROS 1 header sequence number"),
            "stamp": _stamp(),
            "frame_id": Field("string", description="Frame of the laser scan"),
        }),
        "angle_min": Field("number", unit="rad", description="Start angle of the first range reading"),
        "angle_max": Field("number", unit="rad", description="End angle of the last range reading"),
        "angle_increment": Field("number", unit="rad",
                                 description="Angular distance between adjacent readings"),
        "time_increment": Field("number", unit="s", description="Time between adjacent readings"),
        "scan_time": Field("number", unit="s", description="Time between scans"),
        "range_min": Field("number", unit="m", description="Minimum reported range"),
        "range_max": Field("number", unit="m", description="Maximum reported range"),
        "ranges": Field("array", items=Field("number", unit="m"),
                        description="Range reading per angular step; the count follows the configured reading count"),
        "intensities": Field("array", items=Field("number"),
                             description="Per-reading intensity; the simulator never sets it, so it is empty"),
    },
)

_SCAN_OUTPUT = {"scan": _SCAN_MESSAGE}


class EnpsDwa(RosDriver):
    """Configuration-only ROS 1 rosbridge driver for the ENPS-DWA simulator."""

    device_id = "enps_dwa"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeEnpsDwa"}
    tags = ["ros", "ros1", "simulation", "enps-dwa", "social-navigation", "odometry", "laser-scan"]
    display_name = "ENPS-DWA social navigation simulator"
    vendor = "RGNC"
    model = "ENPS_DWA"
    safe_state = (
        "No native stop exists: the MHS latch only refuses this package's own reads, while the simulator keeps "
        "advancing at its freq rate with its robot driving under the ENPS/DWA planner and its pedestrians "
        "walking until the node is killed; this package commands no motion."
    )

    facts = [
        Fact("The node reads the odom_id parameter with the default absolute name /odom and advertises a "
             "nav_msgs::Odometry publisher on it.",
             source="upstream_code", ref="src/enps_dwa_node.cpp:545-553"),
        Fact("publishOdom converts agent 0's map pose into the odom frame with transformPose and returns false "
             "without publishing when transformPose fails; otherwise it publishes the pose with frame odom, child "
             "frame base_link and agent 0's linearVelocity and angularVelocity.", source="upstream_code",
             ref="src/enps_dwa_node.cpp:191-221"),
        Fact("transformPose returns false when the tf listener's transformPose throws.",
             source="upstream_code", ref="src/enps_dwa_node.cpp:445-464"),
        Fact("main constructs the node with a public handle n and the private handle pn('~').",
             source="upstream_code", ref="src/enps_dwa_node.cpp:623-630"),
        Fact("The node sleeps 0.5 s and then uses sfm::MAP.",
             source="upstream_code", ref="src/enps_dwa_node.cpp:564-565"),
        Fact("MAP is defined as RosMap::getInstance(), which returns a function-local static RosMap.",
             source="upstream_code", ref="include/lightsfm/rosmap.hpp:63-68"),
        Fact("The RosMap constructor calls the static_map service once and stops with ROS_FATAL and ROS_BREAK "
             "when the call fails.",
             source="upstream_code", ref="include/lightsfm/rosmap.hpp:102-121"),
        Fact("After simulator::run the loop sets agent 0's linearVelocity and angularVelocity to the "
             "simulator's selectedLinVel and selectedAngVel.",
             source="upstream_code", ref="src/enps_dwa_node.cpp:605-608"),
        Fact("The node opens metrics.txt and writes its header line.",
             source="upstream_code", ref="src/enps_dwa_node.cpp:501-502"),
        Fact("Once a second the loop appends each agent's velocity and nearest-person and nearest-obstacle "
             "distances to metrics.txt.",
             source="upstream_code", ref="src/enps_dwa_node.cpp:590-597"),
        Fact("The node reads the scan360_id parameter with the default absolute name /scan360 and "
             "advertises a sensor_msgs::LaserScan publisher on it.",
             source="upstream_code", ref="src/enps_dwa_node.cpp:549-556"),
        Fact("The scan geometry is built from the configured reading count, robot radius and maximum scan "
             "range: the angular limits are -M_PI and M_PI and the increment is 2*M_PI/scan360_readings.",
             source="upstream_code", ref="src/enps_dwa_node.cpp:569-577"),
        Fact("The scan loop ray-casts from the robot pose, treats an intersecting person as scan_range_max, "
             "and clamps every reported range to at least robot_radius and at most scan_range_max.",
             source="upstream_code", ref="src/enps_dwa_node.cpp:263-284"),
        Fact("The node reads its parameters through pn and advertises six publishers; it registers no "
             "subscriber, service server or action server in this block.",
             source="upstream_code", ref="src/enps_dwa_node.cpp:538-558"),
        Fact("The main loop broadcasts the map-to-odom transform, calls publishOdom and publishScan360 on every "
             "iteration and sleeps on a ros::Rate built from freq until the node handle shuts down.",
             source="upstream_code", ref="src/enps_dwa_node.cpp:562-614"),
        Fact("The launch file starts map_server with maps/temple.yaml, the enps_dwa_node executable and RViz.",
             source="upstream_code", ref="launch/temple.launch:5-9"),
        Fact("The README states that the software simulates human agents and a dual-wheeled non-holonomic "
             "robot, that the simulation runs until the user kills the process, and that the ENPS model "
             "selects motion commands with DWA.", source="vendor_doc", ref="README.md:11"),
        Fact("The README documents ROS Noetic, compilation with catkin_make and starting the example with "
             "roslaunch enps_dwa temple.launch.", source="vendor_doc", ref="README.md:21-32"),
    ]

    # The two observation bindings subscribe to one fresh message each time.
    # A subscription is not a command: the upstream node accepts no input.
    commands = {
        _ODOM_CAP: {
            "topic": "/odom",
            "type": "nav_msgs/Odometry",
            "source_ref": _ODOM_REF,
            "type_ref": _ODOM_TYPE_REF,
            "operation": "subscribe",
            "path": "$",
            "result": {"map": {
                "pose": "pose.pose",
                "twist": "twist.twist",
                "frame_id": "header.frame_id",
                "child_frame_id": "child_frame_id",
                "stamp": "header.stamp",
            }},
        },
        _SCAN_CAP: {
            "topic": "/scan360",
            "type": "sensor_msgs/LaserScan",
            "source_ref": _SCAN_REF,
            "type_ref": _SCAN_TYPE_REF,
            "operation": "subscribe",
            "path": "$",
            "result": {"map": {"scan": "$"}},
        },
    }
    actions = {
        _ODOM_CAP: Action(
            name="read_odometry",
            verb="read",
            max_duration_ms=2000,
            description=(
                "Subscribe to one fresh nav_msgs/Odometry sample on the simulator's /odom topic and return "
                "the robot pose, twist, header frame and stamp. No motion is commanded."
            ),
            output=_ODOMETRY_OUTPUT,
        ),
        _SCAN_CAP: Action(
            name="read_laser_scan",
            verb="read",
            max_duration_ms=2000,
            description=(
                "Subscribe to one fresh sensor_msgs/LaserScan sample on the simulator's /scan360 topic and "
                "return the message under scan, including its header, scan geometry, range limits and ranges. "
                "No motion is commanded."
            ),
            output=_SCAN_OUTPUT,
        ),
    }

    # The deployed fake is a ROS-free event-driven transport, not a physics
    # engine: it returns placeholder sample messages on subscription.
    fidelity = {
        "engine": "analytic: ROS-free transport fake (no physics, no planner)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "The fake returns fixed placeholder samples per subscription; it runs no social-force "
                     "or ENPS/DWA step and does not reproduce a trajectory or state hash.",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free transport fake: it answers the declared subscribe operations with "
            "placeholder messages and runs no simulation loop, social-force model, ENPS membrane model, DWA "
            "selection, map ray-casting or physics",
            "the fake's scan has eight placeholder ranges; the upstream default scan360_readings is 1440 and "
            "is overridable, so the deployed array length follows the operator's configuration and is not a "
            "fixed contract of this package",
            "the upstream /odom publication depends on a map-to-odom transform; the fake always answers a "
            "fresh subscription and does not reproduce the transform-failure path except through its "
            "documented negative switches",
            "the package exposes only the /odom and /scan360 observations; the upstream /people, "
            "/detections, /trajectories and /forces MarkerArray topics, TF broadcasts, metrics.txt output and "
            "all private ROS parameters are NOT COVERED",
            "the upstream node advances its own world at the freq parameter rate (default 30 Hz); there is no "
            "environment-step, velocity-command, pause or reset endpoint in the pinned clone, so the driver "
            "cannot step or reset the simulation",
            "review: an MHS e-stop is a software latch only; the node keeps running, its robot keeps driving "
            "under the planner and its pedestrians keep walking until the process is killed",
            "review: at start-up the node calls map_server's static_map service once, 0.5 s after it starts, "
            "and stops with ROS_BREAK when the call fails, so if map_server (started by the same launch file) "
            "is not yet serving, /odom and /scan360 never appear; /odom also stays silent until the node's tf "
            "listener has its own map-to-odom broadcast",
            "review: the node writes metrics.txt into its working directory and the shipped launch file also "
            "starts RViz; neither is part of this package's contract",
        ],
    }
