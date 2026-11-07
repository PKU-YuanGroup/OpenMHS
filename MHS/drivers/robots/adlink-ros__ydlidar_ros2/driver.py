"""OpenMHS rosbridge driver for the YDLIDAR ROS 2 package (gh.adlink-ros/ydlidar_ros2).

The upstream package builds a C++ ROS 2 node named ``ydlidar_node`` that
publishes one ``sensor_msgs/msg/LaserScan`` message on the relative ``scan``
topic.  This package is a configuration-only :class:`RosDriver` over
rosbridge; it declares no Python native class and never imports, launches or
runs the upstream node.

Scope: one fresh complete ``sensor_msgs/msg/LaserScan`` sample from the
resolved endpoint ``/scan``, returned as a bounded JSON observation with the
message's header stamp/frame and all scan fields.  The node exposes no
application service, action, lifecycle transition, stop or reset interface in the
pinned source; this package therefore binds only the publication.  The launch file's
default namespace is ``/``; an operator that starts the node under another
namespace or remaps the topic must configure the corresponding resolved
endpoint.

Every endpoint, type and fact cites the pinned clone at
482c76acf5c0a563909e1249051c751011ae74c1.  The fake transport is ROS-free; no
ROS graph, serial port, lidar or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: README lists the published topic: ``scan`` with type sensor_msgs/LaserScan.
_SCAN_README_REF = "README.md:76-78"

#: The source includes sensor_msgs/msg/laser_scan.hpp for the LaserScan type.
_SCAN_TYPE_REF = "src/ydlidar_node.cpp:25"

#: The node creates the publisher on the relative name ``scan`` with
#: SensorDataQoS; the launch default namespace ``/`` resolves it to ``/scan``.
_SCAN_SOURCE_REF = "src/ydlidar_node.cpp:179"

#: The launch file gives the node the root namespace.
_LAUNCH_NAMESPACE_REF = "launch/ydlidar_launch.py:44"

#: The node is constructed as a plain rclcpp::Node with the name ydlidar_node.
_NODE_REF = "src/ydlidar_node.cpp:60"

_SCAN_OUTPUT = {
    "frame_id": Field(
        "string",
        description="TF frame id carried in the LaserScan header",
    ),
    "stamp_sec": Field(
        "integer", unit="s",
        description="Whole seconds of the LaserScan header stamp",
    ),
    "stamp_nanosec": Field(
        "integer", unit="ns",
        description="Nanoseconds within the LaserScan header stamp second",
    ),
    "angle_min": Field(
        "number", unit="rad",
        description="Minimum scan angle reported by the device",
    ),
    "angle_max": Field(
        "number", unit="rad",
        description="Maximum scan angle reported by the device",
    ),
    "angle_increment": Field(
        "number", unit="rad",
        description="Angular distance between consecutive range samples",
    ),
    "scan_time": Field(
        "number", unit="s",
        description="Time taken for one complete scan",
    ),
    "time_increment": Field(
        "number", unit="s",
        description="Time between consecutive range samples",
    ),
    "range_min": Field(
        "number", unit="m",
        description="Minimum range reported by the device",
    ),
    "range_max": Field(
        "number", unit="m",
        description="Maximum range reported by the device",
    ),
    "ranges": Field(
        "array",
        items=Field("number", unit="m", description="One range sample in metres"),
        description="Complete range array of the LaserScan sample, in message order",
    ),
    "intensities": Field(
        "array",
        items=Field("number", unit="1", description="One intensity sample"),
        description="Complete intensity array of the LaserScan sample, in message order",
    ),
}

_SCAN_RESULT = {"map": {
    "frame_id": "output.header.frame_id",
    "stamp_sec": "output.header.stamp.sec",
    "stamp_nanosec": "output.header.stamp.nanosec",
    "angle_min": "output.angle_min",
    "angle_max": "output.angle_max",
    "angle_increment": "output.angle_increment",
    "scan_time": "output.scan_time",
    "time_increment": "output.time_increment",
    "range_min": "output.range_min",
    "range_max": "output.range_max",
    "ranges": "output.ranges",
    "intensities": "output.intensities",
}}


class YdlidarRos(RosDriver):
    """Configuration-only ROS 2 rosbridge driver for the YDLIDAR node."""

    device_id = "ydlidar"
    device_kind = "sensor.depth"
    mode = "hardware"
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeYdlidarRos2"}
    tags = ["ros", "ros2", "lidar", "laser-scan", "ydlidar", "sensor"]
    display_name = "YDLIDAR ROS 2 laser scanner"
    vendor = "EAI"
    resource_id = "laser"

    safe_state = (
        "The node is a passive LaserScan publisher: this package only observes its scan topic and exposes "
        "no actuation, stop or reset path."
    )

    facts = [
        Fact("README lists the published 'scan' topic with type sensor_msgs/LaserScan and describes it as the "
             "2D laser scan of the 0-angle ring.",
             source="vendor_doc", ref=_SCAN_README_REF),
        Fact("The source includes the generated sensor_msgs/msg/laser_scan.hpp header.",
             source="upstream_code", ref=_SCAN_TYPE_REF),
        Fact("The main function constructs a plain rclcpp::Node named 'ydlidar_node'.",
             source="upstream_code", ref=_NODE_REF),
        Fact("The node creates a sensor_msgs::msg::LaserScan publisher on the relative topic name 'scan' with "
             "rclcpp::SensorDataQoS().",
             source="upstream_code", ref=_SCAN_SOURCE_REF),
        Fact("ret holds the result of laser.initialize() and then laser.turnOn(); the main loop runs while ret and "
             "rclcpp::ok() hold, calls laser.doProcessSimple(scan, hardError), and publishes a LaserScan on every "
             "successful sample.",
             source="upstream_code", ref="src/ydlidar_node.cpp:174-216"),
        Fact("After the main loop ends the node prints a stopping message, calls laser.turnOff() and "
             "laser.disconnecting(), and shuts rclcpp down.",
             source="upstream_code", ref="src/ydlidar_node.cpp:230-236"),
        Fact("The published header stamp splits scan.stamp into seconds and nanoseconds, and header.frame_id is "
             "set from the local frame_id value.",
             source="upstream_code", ref="src/ydlidar_node.cpp:194-196"),
        Fact("The range and intensity arrays are sized as int((max_angle - min_angle) / angle_increment + 1); each "
             "point is written at the std::ceil index of its angle offset, and a point whose index falls outside "
             "the array is dropped.",
             source="upstream_code", ref="src/ydlidar_node.cpp:205-213"),
        Fact("The vendored SDK's doProcessSimple sets the range to 0.0 for an ignored angle, and the range and "
             "intensity to 0.0 for a range that is not valid.",
             source="upstream_code", ref="sdk/src/CYdLidar.cpp:250-258"),
        Fact("The node's local frame_id defaults to 'laser_frame' in source and is then read from the declared "
             "frame_id parameter.",
             source="upstream_code", ref="src/ydlidar_node.cpp:63-82"),
        Fact("The launch file passes the node a root namespace '/'.",
             source="upstream_code", ref=_LAUNCH_NAMESPACE_REF),
        Fact("README shows the resolved topic name '/scan' in the ros2 topic echo example.",
             source="vendor_doc", ref="README.md:36"),
        Fact("package.xml declares the licence 'Apache License 2.0'.",
             source="upstream_code", ref="package.xml:10"),
        Fact("The launch file carries an Apache License 2.0 header with Copyright 2020, EAIBOT.",
             source="upstream_code", ref="launch/ydlidar_launch.py:2-3"),
        Fact("The vendored SDK's licence file is a BSD licence text of the YDLIDAR Team.",
             source="vendor_doc", ref="sdk/license:1-4"),
    ]

    commands = {
        "x-cap.adlink-ros.laserscan.v1": {
            "topic": "/scan",
            "type": "sensor_msgs/msg/LaserScan",
            "operation": "subscribe",
            "source_name": "scan",
            "source_ref": _SCAN_SOURCE_REF,
            "type_ref": _SCAN_TYPE_REF,
            "result": _SCAN_RESULT,
        },
    }
    actions = {
        "x-cap.adlink-ros.laserscan.v1": Action(
            name="read_scan",
            verb="read",
            description="Read one fresh complete LaserScan sample from the YDLIDAR node",
            output=_SCAN_OUTPUT,
            risk="R0",
        ),
    }
