"""OpenMHS rosbridge driver for the SICK sick_scan_xd LaserScan stream (gh.sickag/sick_scan_xd).

The upstream node is a C++ ROS 2 driver (``sick_generic_caller``) for SICK
LiDAR and RADAR devices.  This package is a configuration-only ``RosDriver``
over rosbridge: it declares no Python native class and never imports,
launches or runs the node.  The scope is one passive
``sensor_msgs/msg/LaserScan`` subscription on the launch-default
``/scan`` topic.  The scan arrays and the message geometry are
returned as one bounded read-only observation.

The driver publishes no command, service or action.  Closing a subscription
is not scanner power-off, and the repository's terminal ``SickScanExit``
service stops the scanner and exits the node, so it is not exposed as a stop
or reset.  The device is observed only; the package claims no safe state.

Every endpoint, type and fact cites the pinned clone at
ed157563f1fdc3a2ea4ba6a6cac7e45ba3ab6e36.  The fake is a ROS-free recording
transport; no ROS graph, rosbridge connection, scanner or hardware is
contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: The ROS 2 wrapper includes the LaserScan message header.
_SCAN_TYPE_REF = "include/sick_scan/sick_ros_wrapper.h:261"

#: For ROS 2 the wrapper aliases ros_sensor_msgs to sensor_msgs::msg.
_SCAN_ALIAS_REF = "include/sick_scan/sick_ros_wrapper.h:279"

#: The LMS5xx launch selects scan; the ROS2 root namespace makes it /scan.
_SCAN_TOPIC_REF = "launch/sick_lms_5xx.launch:15-18"

#: The scan publisher uses the configured laserscan_topic and LaserScan type.
_SCAN_PUBLISH_REF = "driver/src/sick_scan_common.cpp:687"

#: The scan topic is built from the nodename parameter, then the parameter wins.
_SCAN_TOPIC_DEFAULT_REF = "driver/src/sick_scan_common.cpp:542-544"

#: Scan header frame id and stamp are filled from the configured frame and receive time.
_SCAN_HEADER_REF = "driver/src/sick_scan_common.cpp:4681-4682"

#: The scan telegram supplies the angular window and angular increment.
_SCAN_ANGLE_REF = "driver/src/sick_lmd_scandata_parser.cpp:156-158"

#: The range limits are the configured parser limits, not message constants.
_SCAN_RANGE_REF = "driver/src/sick_lmd_scandata_parser.cpp:323-324"

#: A non-zero min_intensity threshold rewrites low-intensity ranges to infinity.
_SCAN_INF_REF = "driver/src/sick_scan_common.cpp:5025-5032"

#: The LMS5xx launch example keeps min_intensity at its default 0.0.
_SCAN_INF_DEFAULT_REF = "launch/sick_lms_5xx.launch:71"

#: The range filter enum documents that it applies only to PointCloud messages.
_SCAN_FILTER_REF = "include/sick_scan/sick_range_filter.h:68-70"

#: The exit service is documented as stopping the scanner and exiting the caller.
_EXIT_REF = "srv/SickScanExitSrv.srv:1-3"

#: The exit path stops scan data, finalizes the state and joins the driver.
_EXIT_IMPL_REF = "driver/src/sick_generic_laser.cpp:193-206"

#: The stop method is a native SOPAS command, not a ROS service.
_STOP_NATIVE_REF = "driver/src/sick_scan_common.cpp:762-807"

#: A full scan observation is returned as one ROS-free JSON-safe object.  The
#: array lengths are the point count of the received message; no model-specific
#: length or per-point limit is invented here.
_RANGES = Field(
    "array",
    items=Field("number", unit="m"),
    description="LaserScan ranges in metres, in the publisher's point order",
)
_INTENSITIES = Field(
    "array",
    items=Field("number", unit="1"),
    description="LaserScan intensities in the publisher's point order, when the device publishes them",
)


class SickScanXd(RosDriver):
    device_id = "sick-scan-xd"
    device_kind = "sensor"
    mode = "hardware"
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeSickScanXd"}
    tags = ["ros", "ros2", "lidar", "laser-scan", "sick", "sick-scan-xd"]
    display_name = "SICK sick_scan_xd LaserScan sensor"
    vendor = "SICK AG"
    resource_id = "scan"
    facts = [
        Fact("The README describes the project as a ROS 2 driver and tools for SICK LiDAR "
             "and RADAR devices.", source="vendor_doc", ref="README.md:7"),
        Fact("The README says the project provides a driver for SICK LiDARs and Radar sensors "
             "and supports ROS 2.", source="vendor_doc", ref="README.md:19"),
        Fact("The ROS 2 build uses ament_cmake.", source="upstream_code", ref="package.xml:16"),
        Fact("The ROS 2 build depends on rclcpp.", source="upstream_code", ref="package.xml:27"),
        Fact("The ROS 2 wrapper includes sensor_msgs/msg/laser_scan.hpp.",
             source="upstream_code", ref=_SCAN_TYPE_REF),
        Fact("For ROS 2 the wrapper defines ros_sensor_msgs as sensor_msgs::msg.",
             source="upstream_code", ref=_SCAN_ALIAS_REF),
        Fact("The scan topic defaults to nodename + \"/scan\" and is then read from the "
             "laserscan_topic parameter.", source="upstream_code", ref=_SCAN_TOPIC_DEFAULT_REF),
        Fact("The node advertises ros_sensor_msgs::LaserScan on the configured laserscan_topic "
             "with queue size 1000.", source="upstream_code", ref=_SCAN_PUBLISH_REF),
        Fact("The LMS5xx launch example defaults laserscan_topic to scan and nodename to "
             "sick_lms_5xx.", source="upstream_code", ref=_SCAN_TOPIC_REF),
        Fact("The LaserScan header stamp is the receive time plus the configured time offset, "
             "and the header frame_id is the configured frame_id.",
             source="upstream_code", ref=_SCAN_HEADER_REF),
        Fact("The scan telegram parser fills angle_min, angle_increment and angle_max from the "
             "reported start angle and angular step.", source="upstream_code", ref=_SCAN_ANGLE_REF),
        Fact("The parser copies the configured range_min and range_max into the LaserScan.",
             source="upstream_code", ref=_SCAN_RANGE_REF),
        Fact("When min_intensity is greater than zero, scan ranges whose intensity is below "
             "that threshold are replaced with positive infinity.",
             source="upstream_code", ref=_SCAN_INF_REF),
        Fact("The LMS5xx launch example sets min_intensity to its default 0.0.",
             source="upstream_code", ref=_SCAN_INF_DEFAULT_REF),
        Fact("The range filter header documents that the range filter applies only to "
             "PointCloud messages, not to LaserScan messages.",
             source="upstream_code", ref=_SCAN_FILTER_REF),
        Fact("SickScanExit is documented as stopping the scanner and exiting sick_generic_caller.",
             source="upstream_code", ref=_EXIT_REF),
        Fact("The exit path calls stopScanData, moves the run state to scanner_finalize "
             "and joins the generic laser driver.", source="upstream_code", ref=_EXIT_IMPL_REF),
        Fact("For the non-NAV350 profile, stop_scanner sends a SOPAS LMDscandata stop command; it is a "
             "C++ method, not a ROS service.", source="upstream_code", ref=_STOP_NATIVE_REF),
    ]

    #: No automatic resource read: a LaserScan is an explicit observation.  The
    #: stock server can still snapshot the empty resource before and after the
    #: action without waiting for a scan sample.
    commands = {
        "x-cap.sickag.scan.v1": {
            "topic": "/scan",
            "type": "sensor_msgs/msg/LaserScan",
            "operation": "subscribe",
            "source_name": "scan",
            "source_ref": _SCAN_TOPIC_REF,
            "type_ref": _SCAN_TYPE_REF,
            "timeout_ms": 5000,
            "result": {
                "map": {
                    "frame_id": "output.header.frame_id",
                    "stamp_sec": "output.header.stamp.sec",
                    "stamp_nanosec": "output.header.stamp.nanosec",
                    "angle_min": "output.angle_min",
                    "angle_max": "output.angle_max",
                    "angle_increment": "output.angle_increment",
                    "time_increment": "output.time_increment",
                    "scan_time": "output.scan_time",
                    "range_min": "output.range_min",
                    "range_max": "output.range_max",
                    "ranges": "output.ranges",
                    "intensities": "output.intensities",
                }
            },
        },
    }
    actions = {
        "x-cap.sickag.scan.v1": Action(
            name="capture_scan",
            verb="invoke",
            description="Read one LaserScan sample from the running sick_scan_xd node",
            output={
                "frame_id": Field("string", description="Header frame id of the received scan"),
                "stamp_sec": Field("integer", unit="s", description="Whole seconds of the scan header stamp"),
                "stamp_nanosec": Field("integer", unit="ns", description="Nanoseconds of the scan header stamp"),
                "angle_min": Field("number", unit="rad", description="First scan angle"),
                "angle_max": Field("number", unit="rad", description="Last scan angle"),
                "angle_increment": Field("number", unit="rad", description="Angular distance between samples"),
                "time_increment": Field("number", unit="s", description="Time between samples"),
                "scan_time": Field("number", unit="s", description="Time for one scan cycle"),
                "range_min": Field("number", unit="m", description="Minimum range reported by the configured parser"),
                "range_max": Field("number", unit="m", description="Maximum range reported by the configured parser"),
                "ranges": _RANGES,
                "intensities": _INTENSITIES,
            },
        ),
    }
