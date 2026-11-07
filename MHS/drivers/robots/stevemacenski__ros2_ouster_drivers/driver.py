"""OpenMHS rosbridge driver for the Ouster OS-x lidar ROS 2 package.

The pinned repository is a C++ ROS 2 lifecycle driver for Ouster OS-x lidars.
This package is a configuration-only :class:`RosDriver` over rosbridge; it
declares no Python native class and never imports, launches or runs the
upstream node.  The served scope is one fresh, complete
``sensor_msgs/msg/PointCloud2`` publication on the node's relative ``points``
topic, returned as one bounded point-cloud artifact.  Scan, image and IMU
topics, the reset service and the metadata service are outside this package.

Every endpoint, type and fact cites the pinned clone at
19c2523025e3e55a2fa803581e4e830e467a9d47.  The fake transport is ROS-free;
no ROS graph, rosbridge connection, lidar or hardware is contacted.
"""

from mhs.driver import Action, Fact, RosDriver

#: The launch file names the lifecycle node ``ouster_driver`` in namespace
#: ``/``.  The processors receive that node itself and create the publisher on
#: the relative (not private ``~/``) name ``points``, which ROS 2 resolves
#: against the node's namespace, not its name: the launch default is
#: ``/points``.  Only the node's ``~/reset`` and ``~/get_metadata`` services
#: resolve under ``/ouster_driver/``.  A deployment that changes the namespace
#: or remaps the topic must configure the resolved endpoint.
_POINTS_ENDPOINT = "/points"

#: PointcloudProcessor creates the publisher for sensor_msgs::msg::PointCloud2
#: on the relative name ``points``.  The cited span shows both the endpoint
#: literal and the fully qualified message type.
_POINTS_REF = "ros2_ouster/include/ros2_ouster/processors/pointcloud_processor.hpp:73-74"

#: The node and namespace of the upstream launch file.
_LAUNCH_REF = "ros2_ouster/launch/driver_launch.py:37-52"


class OusterLidar(RosDriver):
    device_id = "ouster-lidar"
    device_kind = "sensor.depth"
    mode = "hardware"
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeOusterLidar"}
    tags = ["ros", "ros2", "ouster", "lidar", "pointcloud", "sensing", "depth"]
    display_name = "Ouster OS-x lidar ROS 2 driver"
    vendor = "Ouster"
    resource_id = "lidar"

    # A full rotation is one large PointCloud2.  The default 1 MiB rosbridge
    # frame bound is smaller than a typical 64- or 128-beam cloud once its
    # uint8 data field is base64 encoded.  The point-cloud helper accepts up
    # to 16 MiB of raw message data, whose base64 form is at least 21.3 MiB
    # plus the other JSON members.  The 24 MiB value is a client execution
    # bound for that worst case, not a device limit.
    max_message_bytes = 24 * 1024 * 1024

    facts = [
        Fact("The package describes its supported sensors as all models of the OS-x from 16 to 128 "
             "beams running firmware 2.2-2.4.",
             source="vendor_doc", ref="README.md:3"),
        Fact("PointcloudProcessor sizes the cloud from the sensor metadata's pixels_per_column and "
             "columns_per_frame fields.",
             source="upstream_code",
             ref="ros2_ouster/include/ros2_ouster/processors/pointcloud_processor.hpp:66-67"),
        Fact("PointcloudProcessor creates a sensor_msgs::msg::PointCloud2 publisher on the relative "
             "topic name points with the configured QoS.",
             source="upstream_code", ref=_POINTS_REF),
        Fact("PointcloudProcessor::process returns without publishing until the full-rotation "
             "accumulator reports a complete batch.",
             source="upstream_code",
             ref="ros2_ouster/include/ros2_ouster/processors/pointcloud_processor.hpp:91-93"),
        Fact("PointcloudProcessor builds an XYZ lookup from the sensor metadata and, when a full "
             "rotation is ready, calls toCloud with that lookup, the accumulated scan and the cloud "
             "buffer.",
             source="upstream_code",
             ref="ros2_ouster/include/ros2_ouster/processors/pointcloud_processor.hpp:68-97"),
        Fact("PointcloudProcessor publishes the selected cloud through the PointCloud2 publisher using "
             "the accumulated scan timestamp and the _frame member.",
             source="upstream_code",
             ref="ros2_ouster/include/ros2_ouster/processors/pointcloud_processor.hpp:113-117"),
        Fact("The PointCloud2 conversion assigns its frame argument to header.frame_id and derives "
             "header.stamp from the timestamp and override timestamp arguments.",
             source="upstream_code",
             ref="ros2_ouster/include/ros2_ouster/conversions.hpp:190-200"),
        Fact("OusterDriver::onActivate activates every data processor and starts the receive and "
             "process threads; onDeactivate clears the processing flag, joins both threads and "
             "deactivates the processors.",
             source="upstream_code", ref="ros2_ouster/src/ouster_driver.cpp:141-177"),
        Fact("The upstream launch file names the lifecycle node ouster_driver and gives it the root "
             "namespace /.",
             source="upstream_code", ref=_LAUNCH_REF),
        Fact("OusterDriver creates its reset and get_metadata services on the private names ~/reset and "
             "~/get_metadata.",
             source="upstream_code", ref="ros2_ouster/src/ouster_driver.cpp:115-118"),
        Fact("OusterDriver creates the data processors with shared_from_this() and rclcpp::SensorDataQoS(), "
             "or with rclcpp::SystemDefaultsQoS() when use_system_default_qos is set.",
             source="upstream_code", ref="ros2_ouster/src/ouster_driver.cpp:123-134"),
    ]

    commands = {
        "cap.sensing.point_cloud.v1": {
            "topic": _POINTS_ENDPOINT,
            "type": "sensor_msgs/msg/PointCloud2",
            "source_name": "points",
            "source_ref": _POINTS_REF,
            "operation": "subscribe",
            "point_cloud": {"max_input_bytes": 16 * 1024 * 1024},
        },
    }
    actions = {
        "cap.sensing.point_cloud.v1": Action(
            name="capture_point_cloud",
            description="Capture one complete PointCloud2 rotation from the Ouster driver",
        ),
    }
