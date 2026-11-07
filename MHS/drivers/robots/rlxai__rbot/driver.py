"""OpenMHS rosbridge driver for the simulated rbot 2-D LiDAR stream.

The pinned rbot repository is a ROS 2 Jazzy / Gazebo Harmonic autonomous mobile
robot simulation workspace.  The selected device is the Gazebo ``gpu_lidar``
sensor mounted as the 2-D LiDAR, bridged to ROS 2 as
``sensor_msgs/msg/LaserScan`` on the absolute ``/scan`` topic.  This package is
a configuration-only :class:`RosDriver` over rosbridge: it declares no Python
native class, imports no ROS and launches no simulator.

The primary interface is one fresh ``/scan`` subscription.  The scan is a
passive range observation: this package publishes no velocity, accepts no
motion command and declares no stop or safe-state binding.  The simulator's
``/e_stop`` service is a toggle convenience, not an idempotent stop, so it is
deliberately not exposed.  The mobile base (``/cmd_vel`` or the Nav2 actions)
is outside this sensor package; exposing it at its R2 motion risk would need an
independent stop that the pinned clone does not provide.

Every endpoint, type and fact cites the pinned clone at
47af3fc3780bd582837f48ce3785d3d68834a1b7.  The fake transport is ROS-free and
all scan values are placeholders.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: The ROS-Gazebo bridge maps the absolute /scan topic in the GZ_TO_ROS direction.
_SCAN_REF = "src/simulation/rlai_gazebo/config/ros_gz_bridge.yaml:18-22"

#: The same bridge entry names the ROS message type.
_SCAN_TYPE_REF = "src/simulation/rlai_gazebo/config/ros_gz_bridge.yaml:20"

#: The 2-D LiDAR mount comment names the /scan topic and LaserScan type.
_MOUNT_REF = "src/robot/rlai_description/urdf/sensors/lidar_2d.urdf.xacro:5-8"

#: The architecture overview lists /scan as the 2D lidar signal.
_ARCH_REF = "docs/architecture/overview.md:103"

#: The sensor testing guide echoes /scan once.
_TEST_REF = "docs/sensors/testing-in-rich-worlds.md:21-25"

#: The README lists 2-D LiDAR among the simulated sensors.
_README_REF = "README.md:50"

#: The top-level launch exposes the lidar_2d_enabled switch with default true.
_LAUNCH_REF = "src/bringup/rlai_bringup/launch/simulation.launch.py:75"

#: A fixed ROS 2 LaserScan subscription.  The result mapping selects the
#: message fields the explicit output schema carries.
_SCAN = {
    "topic": "/scan",
    "type": "sensor_msgs/msg/LaserScan",
    "source_name": "/scan",
    "source_ref": _SCAN_REF,
    "type_ref": _SCAN_TYPE_REF,
    "operation": "subscribe",
    "timeout_ms": 2000,
    "path": "$",
    "result": {
        "map": {
            "frame_id": "output.header.frame_id",
            "stamp": "output.header.stamp",
            "angle_min": "output.angle_min",
            "angle_max": "output.angle_max",
            "angle_increment": "output.angle_increment",
            "time_increment": "output.time_increment",
            "scan_time": "output.scan_time",
            "range_min": "output.range_min",
            "range_max": "output.range_max",
            "ranges": "output.ranges",
            "intensities": "output.intensities",
        },
    },
}

_SCAN_CAP = "x-cap.rlxai.scan.v1"

#: ROS 2 header stamp fields, preserved as the publisher sends them.
_STAMP = Field(
    "object",
    description="LaserScan header stamp in the ROS 2 sec/nanosec representation",
    properties={
        "sec": Field("integer", unit="s", description="Whole seconds of the scan header stamp"),
        "nanosec": Field("integer", unit="ns", description="Nanoseconds within the header second"),
    },
)


class RbotScan(RosDriver):
    device_id = "rbot_scan"
    device_kind = "sensor"
    mode = "simulated"
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeRbotScan"}
    resource_id = "scan"
    tags = ["ros", "ros2", "gazebo", "simulation", "lidar", "laser", "scan", "sensor"]
    display_name = "rbot simulated 2-D LiDAR"
    vendor = "rlxai"
    model = "RPLIDAR A3 / Hokuyo UST-20LX 2-D LiDAR (Gazebo gpu_lidar)"
    facts = [
        Fact("The 2-D LiDAR is a Gazebo gpu_lidar sensor named lidar_2d on the absolute /scan "
             "topic with update rate 15 Hz.",
             source="upstream_code",
             ref="src/robot/rlai_description/urdf/gazebo/gazebo_sensors.urdf.xacro:39-44"),
        Fact("The sensor publishes 720 horizontal samples with resolution 1 and angle bounds "
             "-3.14159265 to 3.14159265 rad.",
             source="upstream_code",
             ref="src/robot/rlai_description/urdf/gazebo/gazebo_sensors.urdf.xacro:47-53"),
        Fact("The sensor range is 0.30 to 25.0 m with 0.01 resolution and Gaussian noise "
             "standard deviation 0.01.",
             source="upstream_code",
             ref="src/robot/rlai_description/urdf/gazebo/gazebo_sensors.urdf.xacro:55-63"),
        Fact("The sensor frame id is lidar_2d_link.",
             source="upstream_code",
             ref="src/robot/rlai_description/urdf/gazebo/gazebo_sensors.urdf.xacro:45"),
        Fact("The ros_gz_bridge maps the absolute /scan topic from gz.msgs.LaserScan to "
             "sensor_msgs/msg/LaserScan in the GZ_TO_ROS direction.",
             source="upstream_code",
             ref=_SCAN_REF),
        Fact("The 2-D LiDAR mount comment names the topic /scan (LaserScan).",
             source="upstream_code",
             ref=_MOUNT_REF),
        Fact("The architecture overview lists /scan as the 2D lidar signal consumed by the "
             "Nav2 costmaps and AMCL.",
             source="vendor_doc",
             ref=_ARCH_REF),
        Fact("The sensor testing guide checks laser data with 'ros2 topic echo /scan --once'.",
             source="vendor_doc",
             ref=_TEST_REF),
        Fact("The README lists 2-D LiDAR among the simulated sensors.",
             source="vendor_doc",
             ref=_README_REF),
        Fact("The top-level simulation launch exposes lidar_2d_enabled with default true.",
             source="upstream_code",
             ref=_LAUNCH_REF),
        Fact("The Gazebo launch starts the ros_gz_bridge node with config/ros_gz_bridge.yaml.",
             source="upstream_code",
             ref="src/simulation/rlai_gazebo/launch/gazebo.launch.py:235-246"),
    ]
    safe_state = (
        "The selected 2-D LiDAR is a passive range sensor with no actuator, stop or reset "
        "interface; this package commands no motion and declares no e-stop binding.  The "
        "simulator's /e_stop toggle is not an idempotent safe state and is not exposed."
    )
    fidelity = {
        "engine": "analytic:ROS-free recording fake for the rbot /scan stream (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned LaserScan replies with no Gazebo raycast, noise model, "
                     "physics step or wall-clock pacing; placeholder ranges do not replay a scan or "
                     "a trajectory",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free ros_transport handler: it answers the declared /scan "
            "subscription and records it, but runs no Gazebo Harmonic, ros_gz_bridge, sensor raycast, "
            "Gaussian noise model or 15 Hz wall-clock loop",
            "the scan values and the returned 8-range array are placeholders, not the pinned sensor's "
            "720 samples (src/robot/rlai_description/urdf/gazebo/gazebo_sensors.urdf.xacro:47-53); a "
            "live run must receive the operator's /scan from the Gazebo bridge",
            "one subscription reply is not the pinned 15 Hz stream; the fake does not model message "
            "timing, drops or transport fragmentation",
            "the package exposes only the 2-D LiDAR scan: the mobile base (/cmd_vel or Nav2 actions), "
            "IMU, depth/stereo cameras, 3-D LiDAR, GPS, TF and the simulator clock are NOT COVERED",
            "the upstream /e_stop service toggles a software zero-velocity publisher and is not an "
            "input-free safe state; no motion command is exposed here",
            "the bridge and sensor are Gazebo simulation interfaces; no hardware is attached and no "
            "live ROS graph is contacted",
            "the bridge refuses non-finite JSON numbers, so a live scan whose no-return or out-of-range samples "
            "arrive as non-finite values fails the observation instead of returning it; the fake publishes "
            "finite placeholder ranges except in its non-finite test case",
        ],
    }

    commands = {_SCAN_CAP: _SCAN}
    actions = {
        _SCAN_CAP: Action(
            name="read_scan",
            verb="read",
            max_duration_ms=2000,
            description="Subscribe to one fresh sensor_msgs/msg/LaserScan sample on the absolute "
                        "/scan topic and return its geometry, ranges and intensities",
            output={
                "frame_id": Field("string", description="LaserScan header.frame_id"),
                "stamp": _STAMP,
                "angle_min": Field("number", unit="rad",
                                   description="Start angle of the first range measurement"),
                "angle_max": Field("number", unit="rad",
                                   description="End angle of the last range measurement"),
                "angle_increment": Field("number", unit="rad",
                                         description="Angular distance between consecutive measurements"),
                "time_increment": Field("number", unit="s",
                                        description="Time between consecutive measurements"),
                "scan_time": Field("number", unit="s", description="Time between two complete scans"),
                "range_min": Field("number", unit="m", description="Minimum range value"),
                "range_max": Field("number", unit="m", description="Maximum range value"),
                "ranges": Field("array", items=Field("number", unit="m"),
                                description=("Range measurements in metres, in publisher order; a scan "
                                             "carrying a non-finite range is refused by the bridge, never "
                                             "reported with a substituted number")),
                "intensities": Field("array", items=Field("number", unit="1"),
                                     description="Intensity measurements in publisher order"),
            },
        ),
    }
    # A passive range sensor has no actuator, stop or reset path to bind.
    safety_bindings = {}
