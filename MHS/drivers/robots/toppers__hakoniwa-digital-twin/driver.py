"""OpenMHS rosbridge driver for the Hakoniwa infra-sensor position publisher.

The pinned upstream repository is a digital-twin demo.  Its concrete sensor
runtime is the ROS 2 ``infra_sensor_urg`` node ``lidar_subscriber``: the node
consumes a ``sensor_msgs/msg/LaserScan`` and a ``sensor_msgs/msg/Imu``, runs
the circle/centre-of-mass estimator, and publishes one
``geometry_msgs/msg/Twist`` on the absolute ``/TB3RoboAvatar_cmd_pos`` topic.
The README documents that topic as the robot-position estimate.

The node's ``act_mode`` parameter defaults to ``sim`` (the simulator's LiDAR
and IMU topics); the README starts it with ``act_mode:=real``, where it reads a
real URG LiDAR and the TurtleBot3 IMU.  Its x and y are 0.0, not an estimate,
while the estimator's initial environment scan runs and, after the one message
that completes the scan, until an operator enters ``s`` at the node's terminal
prompt.  The clone's
``infra_sensor_tg15`` node publishes on the same topic, and the clone's
``tb3_controller_node`` subscribes to it as its position input.  This package
only subscribes; it never publishes on that topic.

This package is a configuration-only :class:`RosDriver` over rosbridge.  It
declares no Python native class and it imports, launches or executes nothing
from the clone.  The primary interface exposed here is the node's published
estimate, one fresh ``cap.sensing.read.v1`` observation per call.  The node has
no ROS service, action or subscriber that accepts a position command, so the
input scan and IMU streams are not bound and the estimator is not stepped by
this package.  A deployment must run the upstream node; the canned fake only
stands in for its declared publication.

Every endpoint, type and fact cites the pinned clone at
1a2c15b8aade01696a81207c8f28a77013497384.  The fake transport is ROS-free; no
ROS graph, LiDAR, Unity simulator or hardware is contacted.
"""

from datetime import datetime, timezone
import math

from mhs.driver import Action, DriverFailed, Fact, Field, RosDriver

#: The catalogue class served by this read-only sensor package.
_POSE_CAP = "cap.sensing.read.v1"

#: The node's publisher is created on this absolute topic with queue size 10.
_POSE_TOPIC = "/TB3RoboAvatar_cmd_pos"

#: ROS 2 spelling of the geometry_msgs/Twist message.
_POSE_TYPE = "geometry_msgs/msg/Twist"

#: ``from geometry_msgs.msg import Twist`` names the published message type.
_TYPE_REF = "real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:5"

#: ``create_publisher(Twist, '/TB3RoboAvatar_cmd_pos', 10)`` names the endpoint.
_PUBLISHER_REF = "real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:78"

#: The callback that fills and publishes the Twist (whole body: no early return).
_CALLBACK_REF = "real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:121-142"

#: The constructor declares and reads the startup-only act_mode parameter.
_MODE_REF = "real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:66-73"

#: The node's input subscriptions and their QoS profile.
_INPUT_REF = "real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:80-92"

#: The act_mode topic selection and the two subscriptions that use the selected names.
_SELECT_REF = "real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:66-92"

#: The constructor's scan_mode flag.
_SCAN_FLAG_REF = "real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:63-103"

#: listener_callback's estimator branches and the 0.0 fallback.
_BRANCH_REF = "real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:121-133"

#: listener_imu and the node's own quaternion conversion.
_IMU_CALLBACK_REF = "real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:105-116"
_EULER_REF = "real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:20-38"

#: The estimator's initial averages, its scan phase and run's early return.
_AVERAGE_INIT_REF = "real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/pos_estimator.py:65"
_SCAN_PHASE_REF = "real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/pos_estimator.py:227-242"
_RUN_REF = "real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/pos_estimator.py:249-252"

#: The estimator's filtered x output adds a fixed offset when a result is supplied.
_ESTIMATOR_REF = "real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/pos_estimator.py:121-141"

_CHANNELS = ("x", "y", "z", "roll", "pitch", "yaw")
_LINEAR_CHANNELS = ("x", "y", "z")
_ANGULAR_CHANNELS = ("roll", "pitch", "yaw")


def _number(raw, label):
    """Return one finite Twist component or refuse the mapped output."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", f"Twist {label} is not a number")
    value = float(raw)
    if not math.isfinite(value):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", f"Twist {label} is not finite")
    return value


def _vector(raw, label):
    """Validate one geometry_msgs/Vector3 mapping and return x, y, z."""
    if not isinstance(raw, dict):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", f"Twist {label} is absent")
    return [_number(raw.get(axis), f"{label}.{axis}") for axis in _LINEAR_CHANNELS]


def _stamp():
    """The driver's receive stamp; geometry_msgs/Twist carries no header."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class HakoniwaInfraSensor(RosDriver):
    """Configuration-only ROS 2 rosbridge driver for the infra-sensor node."""

    device_id = "hakoniwa_infra_sensor"
    device_kind = "sensor"
    mode = "simulated"
    risk = "R1"
    ros_version = 2
    backends = {"fake": ".fake:FakeHakoniwaInfraSensor"}
    tags = ["ros", "ros2", "lidar", "position", "sensor", "hakoniwa", "simulation"]
    display_name = "Hakoniwa infra-sensor position publisher"
    vendor = "toppers"
    model = "infra_sensor_urg"

    facts = [
        Fact("LIDARSubscriber is an rclpy Node constructed with the name 'lidar_subscriber'.",
             source="upstream_code",
             ref="real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:62-64"),
        Fact("The constructor declares the ROS 2 parameter 'act_mode' with the default string 'sim' and reads "
             "it once through get_parameter.",
             source="upstream_code", ref=_MODE_REF),
        Fact("With act_mode == 'sim' the node subscribes to '/LiDARSensor2D_scan' and '/TB3RoboModel_imu'; "
             "otherwise it subscribes to '/scan' and '/tb3_imu'.",
             source="upstream_code", ref=_SELECT_REF),
        Fact("The constructor initialises the node's scan_mode flag to False.",
             source="upstream_code", ref=_SCAN_FLAG_REF),
        Fact("The node imports geometry_msgs.msg.Twist.",
             source="upstream_code",
             ref="real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:5"),
        Fact("The node creates a publisher for Twist on the absolute topic '/TB3RoboAvatar_cmd_pos' with "
             "queue size 10.",
             source="upstream_code", ref=_PUBLISHER_REF),
        Fact("The LaserScan and Imu subscriptions use one QoS profile with depth 10, BEST_EFFORT reliability "
             "and VOLATILE durability.",
             source="upstream_code", ref=_INPUT_REF),
        Fact("listener_callback runs the estimator while the estimator reports scan mode or the node's "
             "scan_mode flag is set, each time with scan_count_max=lidar_param_scan_count_max and "
             "value_threshold=lidar_param_segment_threshold; otherwise it sets x and y to 0.0.",
             source="upstream_code", ref=_BRANCH_REF),
        Fact("listener_callback then fills Twist linear.x and linear.y with x and y, linear.z with 0.0 and "
             "angular.x, angular.y and angular.z with the stored angle_x, angle_y and angle_z, and publishes "
             "the message at the end of every call.",
             source="upstream_code", ref=_CALLBACK_REF),
        Fact("listener_imu stores the roll, pitch and yaw that euler_from_quaternion computes from the Imu "
             "orientation as angle_x, angle_y and angle_z.",
             source="upstream_code", ref=_IMU_CALLBACK_REF),
        Fact("euler_from_quaternion computes roll and yaw with np.arctan2 and pitch with np.arcsin.",
             source="upstream_code", ref=_EULER_REF),
        Fact("The pinned lidar_params literals are lidar_param_scan_count_max = 50 and "
             "lidar_param_segment_threshold = 0.05.",
             source="upstream_code",
             ref="real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_params.py:4-5"),
        Fact("write_pos adds 0.075 to the filtered x average when a non-None result is supplied; with no "
             "result it returns the stored average without the offset.",
             source="upstream_code", ref=_ESTIMATOR_REF),
        Fact("The estimator constructor initialises average_x, average_y and average_r to 0.0.",
             source="upstream_code", ref=_AVERAGE_INIT_REF),
        Fact("is_scan_mode returns True until scan() sets finalized, which scan() does only after it has "
             "collected scan_count_max scans.",
             source="upstream_code", ref=_SCAN_PHASE_REF),
        Fact("run returns write_pos(None) while scan() reports that the environment scan has not finished.",
             source="upstream_code", ref=_RUN_REF),
        Fact("KeyboardMonitor maps the keyboard input 's' to True and 'p' to False.",
             source="upstream_code",
             ref="real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:148-157"),
        Fact("main connects the keyboard monitor's mode_changed signal to LIDARSubscriber.set_scan_mode.",
             source="upstream_code",
             ref="real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:173-176"),
        Fact("set_scan_mode only assigns self.scan_mode under the node lock; it does not create a ROS "
             "service or action endpoint.",
             source="upstream_code",
             ref="real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:144-146"),
        Fact("The README starts the node with 'ros2 run infra_sensor_urg lidar_subscriber --ros-args -p "
             "act_mode:=real' and says to pass act_mode:=sim for tests.",
             source="vendor_doc", ref="README.md:417-420"),
        Fact("The README says the robot-position estimate is delivered on RobotAvator_cmd_pos and shows a "
             "ros2 topic echo of /TB3RoboAvatar_cmd_pos with linear and angular components.",
             source="vendor_doc", ref="README.md:451-465"),
        Fact("The README asks the operator to wait about 30 seconds for the environment scan, then place the "
             "robot and enter s at the node's terminal.",
             source="vendor_doc", ref="README.md:434-443"),
        Fact("The infra_sensor_tg15 node also creates a Twist publisher on '/TB3RoboAvatar_cmd_pos'.",
             source="upstream_code",
             ref="real/sensors/workspace/src/infra_sensor_tg15/infra_sensor_tg15/lidar_subscriber.py:18"),
        Fact("tb3_controller_node subscribes to TB3RoboAvatar_cmd_pos with sensor_callback_pos.",
             source="upstream_code", ref="real/robot/workspace/src/tb3_controller/src/tb3_controller.cpp:92-94"),
        Fact("sensor_callback_pos takes linear.x as the robot position and, in the MOVE state between 0.5 and "
             "0.8, stops the motor unless the signal state is blue.",
             source="upstream_code", ref="real/robot/workspace/src/tb3_controller/src/tb3_controller.cpp:164-194"),
        Fact("tb3_controller_node publishes its Twist on /TB3RoboModel_cmd_vel when act_mode is 'sim' and on "
             "/tb3_cmd_vel otherwise.",
             source="upstream_code", ref="real/robot/workspace/src/tb3_controller/src/tb3_controller.cpp:57-76"),
        Fact("The README starts tb3_controller_node with act_mode:=real.",
             source="vendor_doc", ref="README.md:476"),
        Fact("The infra_sensor_urg package manifest declares the licence TOPPERS.",
             source="upstream_code", ref="real/sensors/workspace/src/infra_sensor_urg/package.xml:3-8"),
    ]

    safe_state = (
        "The upstream node is a passive position publisher and this package binds only its published estimate; "
        "it commands no motion, so the stock e-stop can only latch in software and no native stop is claimed."
    )

    #: The upstream Unity/Hakoniwa simulator is outside the clone and no ROS graph is
    #: started here.  The fake is a ROS-free canned transcript of the one declared
    #: publication, so it claims F0 and no estimator, LiDAR or physics.
    fidelity = {
        "engine": "canned:ROS 2 /TB3RoboAvatar_cmd_pos transcript (no estimator, LiDAR or physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned transport with no estimator loop, LiDAR scan processing, ROS graph "
                     "or wall-clock pacing; placeholder Twist samples do not establish position accuracy",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free canned transport: it answers the declared /TB3RoboAvatar_cmd_pos "
            "subscription with placeholder geometry_msgs/msg/Twist messages and runs no infra_sensor_urg "
            "node, LiDAR filter, circle fit, PyQt plotter or ROS graph",
            "the fake pose is placeholder test data and is not derived from a LiDAR scan; it does not "
            "establish estimation accuracy, target tracking or the robot's physical position",
            "the node's input topics /LiDARSensor2D_scan and /TB3RoboModel_imu (sim) or /scan and /tb3_imu "
            "(real) are not bound; this package observes only the node's published estimate and cannot step "
            "the estimator",
            "geometry_msgs/msg/Twist has no header or stamp, so sampled_at is the driver's local receive "
            "stamp, not the publisher's sample time",
            "after start-up x and y are 0.0 while the estimator collects its 50 environment scans; after "
            "the message that completes the scan they are 0.0 again until an operator enters 's' at the "
            "node's terminal prompt (KeyboardMonitor; 'p' returns to 0.0); this package sends no keyboard "
            "input and cannot tell such a 0.0 from an estimate at the sensor origin",
            "the clone's infra_sensor_tg15 node publishes on the same /TB3RoboAvatar_cmd_pos topic; with "
            "both running, a read returns whichever message arrives first",
            "roll, pitch and yaw come from the node's own euler_from_quaternion, whose np.arcsin returns "
            "NaN for an argument outside -1..1; such a sample never becomes a value: the SDK's rosbridge "
            "transport refuses non-finite JSON numbers and the driver refuses any non-finite component",
            "the topic is also the position input of the clone's tb3_controller_node, which the README "
            "runs with act_mode:=real against a TurtleBot3; this package only subscribes and never "
            "publishes on it",
            "the operator must run the pinned ROS 2 node and rosbridge; no ROS graph, simulator or hardware "
            "was started or validated here",
        ],
    }

    commands = {
        _POSE_CAP: {
            "topic": _POSE_TOPIC,
            "type": _POSE_TYPE,
            "source_ref": _PUBLISHER_REF,
            "type_ref": _TYPE_REF,
            "operation": "subscribe",
            "path": "$",
            "result": {"map": {"values": "output.$"}},
        },
    }
    actions = {
        _POSE_CAP: Action(
            name="read_position",
            description=(
                "Subscribe to one fresh geometry_msgs/msg/Twist on the upstream '/TB3RoboAvatar_cmd_pos' "
                "topic and return the published position estimate in 'values': x, y and z in metres and "
                "roll, pitch and yaw in radians. x and y are 0.0, not an estimate, during the node's "
                "initial environment scan and until its operator enters 's'; z is always 0.0. The upstream "
                "node has no acknowledgement or sample stamp on this message, so the receipt timestamp is the "
                "local observation time."
            ),
            input={
                "fields": Field(
                    "array",
                    items=Field("string", description="One channel name: x, y, z, roll, pitch or yaw"),
                    description=(
                        "Optional channel names to return; omit or pass an empty array for all six channels. "
                        "Only recognised names are returned and an unrecognised name is ignored. The channel "
                        "units are metres for x, y and z and radians for roll, pitch and yaw."
                    ),
                ),
            },
        ),
    }

    def call(self, capability_id, args=None, ctx=None):
        """Flatten the published Twist into the class's open ``values`` object."""
        result = super().call(capability_id, args, ctx)
        if capability_id != _POSE_CAP:
            return result
        raw = result.get("values") if isinstance(result, dict) else None
        if not isinstance(raw, dict):
            raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID",
                               "the Twist observation is not an object")
        linear = _vector(raw.get("linear"), "linear")
        angular = _vector(raw.get("angular"), "angular")
        values = dict(zip(_LINEAR_CHANNELS, linear))
        values.update(dict(zip(_ANGULAR_CHANNELS, angular)))
        selected = (args or {}).get("fields")
        if selected:
            values = {name: values[name] for name in _CHANNELS if name in selected}
        return {"values": values, "sampled_at": _stamp()}
