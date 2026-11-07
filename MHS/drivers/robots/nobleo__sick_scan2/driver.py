"""OpenMHS rosbridge driver for the SICK scan2 ROS 2 laser scanner driver.

The upstream ``sick_generic_caller`` node is a C++ ROS 2 node.  This package is
a configuration-only :class:`RosDriver`; it declares no Python native class and
does not import or run the upstream code.  The served scope is one fresh
``sensor_msgs/msg/LaserScan`` publication from the node's relative ``scan``
topic: scan geometry, ranges and intensities.  The node also publishes a
``PointCloud2`` cloud and an ``Imu`` topic; those outputs are outside this
package.  The clone contains a native SOPAS stream-disable method, but it is
not advertised as a ROS service or action, so this package exposes no command,
stop or reset binding and claims none.

Every endpoint, type, fact and schema bound cites the pinned clone at
8e851e7f728e5cfb1a68a721bff833c1b50e4410.  The fake backend is a ROS-free
recording transport; no ROS graph, scanner, rosbridge connection or hardware is
contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: The ROS 2 node is constructed with the literal node name "sick_scan2".
_NODE_NAME_REF = "driver/src/sick_generic_caller.cpp:152"

#: SickScanCommon creates the ROS 2 LaserScan publisher on the relative name "scan".
_SCAN_REF = "driver/src/sick_scan_common.cpp:420"

#: The LaserScan message type is named by the publisher and by this include.
_SCAN_TYPE_REF = "driver/src/sick_scan_common.cpp:86"

#: The empty node namespace resolves the relative scan topic at the root; node name adds no prefix.
_SCAN_TOPIC = "/scan"

#: The largest per-model number-of-shots validation bound in the pinned parser.
_MAX_SCAN_SAMPLES = 7201

#: LaserScan message geometry as carried by the ROS 2 type.
_FRAME_ID = Field("string", description="Transform frame id carried by the LaserScan header")
_STAMP_SEC = Field("integer", unit="s", description="Whole seconds of the scan header stamp")
_STAMP_NANOSEC = Field("integer", unit="ns", description="Nanoseconds within the scan stamp second")
_ANGLE_MIN = Field("number", unit="rad", description="Start angle of the first range sample")
_ANGLE_MAX = Field("number", unit="rad", description="End angle of the last range sample")
_ANGLE_INCREMENT = Field("number", unit="rad", description="Angular distance between adjacent range samples")
_TIME_INCREMENT = Field("number", unit="s", description="Time between adjacent range samples")
_SCAN_TIME = Field("number", unit="s", description="Time between two complete scans")
_RANGE_MIN = Field("number", unit="m", description="Minimum range value reported by the message")
_RANGE_MAX = Field("number", unit="m", description="Maximum range value reported by the message")
_RANGES = Field(
    "array",
    unit="m",
    items=Field("number", description="One measured range in metres"),
    min_items=0,
    max_items=_MAX_SCAN_SAMPLES,
    description="Measured ranges in metres; length follows the scanner datagram's sample count",
)
_INTENSITIES = Field(
    "array",
    unit="1",
    items=Field("number", description="One raw RSSI intensity sample"),
    min_items=0,
    max_items=_MAX_SCAN_SAMPLES,
    description="Optional raw intensity samples; empty when the scanner sends no RSSI block",
)


class SickScan2(RosDriver):
    device_id = "sick-scan2"
    device_kind = "sensor"
    mode = "hardware"
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeSickScan2"}
    tags = ["ros", "ros2", "sick", "laser-scanner", "laserscan", "scan", "ranges"]
    display_name = "SICK scan2 ROS 2 laser scanner"
    vendor = "SICK"
    resource_id = "scanner"
    facts = [
        Fact("The ROS 2 node is constructed with the literal name sick_scan2.",
             source="upstream_code", ref=_NODE_NAME_REF),
        Fact("SickScanCommon creates a ROS 2 publisher for sensor_msgs::msg::LaserScan on the relative "
             "topic name scan with queue size 10.",
             source="upstream_code", ref=_SCAN_REF),
        Fact("The same constructor creates ROS 2 publishers for sensor_msgs::msg::PointCloud2 on cloud and "
             "sensor_msgs::msg::Imu on imu.",
             source="upstream_code", ref="driver/src/sick_scan_common.cpp:423-424"),
        Fact("The scan path assigns the configured frame_id into the LaserScan header.",
             source="upstream_code", ref="driver/src/sick_scan_common.cpp:2928"),
        Fact("The scan path assigns the received timestamp into the LaserScan header before publication.",
             source="upstream_code", ref="driver/src/sick_scan_common.cpp:2972-2975"),
        Fact("The node declares the frame_id parameter with the default string world.",
             source="upstream_code", ref="driver/src/sick_generic_caller.cpp:201"),
        Fact("The ASCII datagram parser derives angle_min from the datagram start angle, angle_increment "
             "from the angular step width, and angle_max from the sample count.",
             source="upstream_code", ref="driver/src/sick_generic_parser.cpp:1021-1029"),
        Fact("The ASCII datagram parser converts each raw distance value with iRange / 1000.0.",
             source="upstream_code", ref="driver/src/sick_generic_parser.cpp:721"),
        Fact("The binary scan path derives angle_min, angle_increment and angle_max from the start angle and "
             "angular step width, and writes each range as data[i] * 0.001 * scaleFactor + scaleFactorOffset.",
             source="upstream_code", ref="driver/src/sick_scan_common.cpp:2643-2657"),
        Fact("The parser rejects a scan whose number of data points is below 1 or above the scanner model's "
             "number of shots.",
             source="upstream_code", ref="driver/src/sick_generic_parser.cpp:909-912"),
        Fact("The LRS_4XXX scanner configuration sets the parser's number-of-shots validation bound to 7201.",
             source="upstream_code", ref="driver/src/sick_generic_parser.cpp:564"),
        Fact("SickGenericParser initializes its range_min and range_max overrides to 0.05 and 100.0 in its "
             "constructor.",
             source="upstream_code", ref="driver/src/sick_generic_parser.cpp:391-392"),
        Fact("SickScanCommon::stop_scanner sends the SOPAS stream-disable command sEN LMDscandata 0 and "
             "returns its error code.",
             source="upstream_code", ref="driver/src/sick_scan_common.cpp:431-448"),
    ]
    commands = {
        "x-cap.nobleo.laser_scan.v1": {
            "topic": _SCAN_TOPIC,
            "type": "sensor_msgs/msg/LaserScan",
            "source_name": "scan",
            "source_ref": _SCAN_REF,
            "type_ref": _SCAN_TYPE_REF,
            "operation": "subscribe",
            "path": "$",
            "result": {"map": {
                "ranges": "output.ranges",
                "intensities": "output.intensities",
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
            }},
        },
    }
    actions = {
        "x-cap.nobleo.laser_scan.v1": Action(
            name="read_laser_scan",
            verb="read",
            description="Read one fresh LaserScan publication from the scan topic",
            output={
                "ranges": _RANGES,
                "intensities": _INTENSITIES,
                "frame_id": _FRAME_ID,
                "stamp_sec": _STAMP_SEC,
                "stamp_nanosec": _STAMP_NANOSEC,
                "angle_min": _ANGLE_MIN,
                "angle_max": _ANGLE_MAX,
                "angle_increment": _ANGLE_INCREMENT,
                "time_increment": _TIME_INCREMENT,
                "scan_time": _SCAN_TIME,
                "range_min": _RANGE_MIN,
                "range_max": _RANGE_MAX,
            },
        ),
    }
