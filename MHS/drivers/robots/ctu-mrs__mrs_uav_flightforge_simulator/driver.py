"""OpenMHS rosbridge driver for the MRS FlightForge simulator endpoint.

The pinned upstream is a ROS 2 C++ package: the ``FlightforgeSimulator``
``rclcpp`` component bridges the external FlightForge binary (an Unreal Engine
game that the node reaches through ``ueds_connector`` on localhost port 8551)
to ROS, and the ``mrs_uav_flightforge_hw_api_plugin::Api`` plugin bridges the
MRS hardware API to the simulator.  This package is a configuration-only
:class:`RosDriver` over rosbridge; it declares no Python native class and
neither imports, launches nor builds the upstream code.  The operator runs the
upstream nodes, the FlightForge binary and rosbridge separately.

The exposed surface is the part of the simulator node that the pinned launch
publishes once the node has connected to the FlightForge binary: the simulated
clock and the UAV pose array.  The node's per-UAV flight-command subscriptions
are created by the ``mrs_multirotor_simulator::UavSystemRos`` objects it
constructs (library code outside the clone); this clone's hw_api plugin
publishes to them under ``/flightforge_simulator/<uav_name>/``.  The pinned
clone creates no ROS service or action server for a command, pause, reset or
stop.  The only pause path is the dynamic parameter
``mrs_uav_flightforge_simulator/paused``, whose callback cancels the main and
status timers; ROS parameter access is not a rosbridge opcode, and the clone
does not declare the parameter-service type.  This observation-only profile
therefore declares no native stop: the stock e-stop latches it and reports the
software-only safe state instead of inventing a stopped simulator.

Every endpoint, type and fact cites the pinned clone at
e4715a8c75aac70a9bcd7f75113746b938139117.  The fake transport is ROS-free;
no ROS graph, FlightForge binary or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: The launch starts the component in an empty namespace under this name, so a
#: private topic ``~/<name>`` resolves below ``/flightforge_simulator``.
_NODE_NAME_REF = "launch/flightforge_simulator.launch.py:110-111"

#: The simulator publishes the clock on a private topic and the launch remaps
#: it to the absolute /clock topic used by use_sim_time.
_CLOCK_PUBLISHER_REF = "src/flightforge_simulator.cpp:1185"
_CLOCK_REMAP_REF = "launch/flightforge_simulator.launch.py:120"
_CLOCK_TYPE_REF = "src/flightforge_simulator.cpp:7"

#: The pose array is published on a private topic; the launch remaps it to
#: another private topic under the same node name.
_POSES_PUBLISHER_REF = "src/flightforge_simulator.cpp:1187"
_POSES_REMAP_REF = "launch/flightforge_simulator.launch.py:121"
_POSES_TYPE_REF = "src/flightforge_simulator.cpp:9"

#: ROS 2 rosgraph_msgs/Clock carries builtin_interfaces/Time sec and nanosec.
_CLOCK_TIME = Field(
    "object",
    description="Simulated ROS time from one rosgraph_msgs/Clock sample",
    properties={
        "sec": Field("integer", unit="s", description="Whole seconds of simulated time"),
        "nanosec": Field("integer", unit="ns", description="Nanoseconds within the simulated second"),
    },
)

#: geometry_msgs/PoseArray poses are geometry_msgs/Pose (position and orientation).
_POSE = Field(
    "object",
    description="One geometry_msgs/Pose from the simulator pose array",
    properties={
        "position": Field(
            "object",
            description="Pose position in the PoseArray header frame",
            properties={
                "x": Field("number", unit="m", description="Position x component"),
                "y": Field("number", unit="m", description="Position y component"),
                "z": Field("number", unit="m", description="Position z component"),
            },
        ),
        "orientation": Field(
            "object",
            description="Pose orientation quaternion (unitless components)",
            properties={
                "x": Field("number", unit="1", description="Quaternion x component"),
                "y": Field("number", unit="1", description="Quaternion y component"),
                "z": Field("number", unit="1", description="Quaternion z component"),
                "w": Field("number", unit="1", description="Quaternion w component"),
            },
        ),
    },
)

#: A fixed subscription to the remapped simulated clock.
_CLOCK = {
    "topic": "/clock",
    "type": "rosgraph_msgs/msg/Clock",
    "source_name": "/clock",
    "source_ref": _CLOCK_REMAP_REF,
    "type_ref": _CLOCK_TYPE_REF,
    "operation": "subscribe",
    "path": "clock",
    "result": {"map": {"sim_time": "output.$"}},
    "timeout_ms": 2000,
}

#: A fixed subscription to the remapped UAV pose array.
_POSES = {
    "topic": "/flightforge_simulator/uav_poses",
    "type": "geometry_msgs/msg/PoseArray",
    "source_name": "~/uav_poses",
    "source_ref": _POSES_REMAP_REF,
    "type_ref": _POSES_TYPE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"stamp": "output.header.stamp",
                       "frame_id": "output.header.frame_id",
                       "poses": "output.poses"}},
    "timeout_ms": 2000,
}


class FlightforgeSimulator(RosDriver):
    device_id = "flightforge-simulator"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeFlightforge"}
    tags = ["ros", "ros2", "simulation", "flightforge", "uav", "clock", "pose"]
    display_name = "MRS FlightForge simulator endpoint"
    vendor = "ctu-mrs"
    model = "FlightforgeSimulator"
    facts = [
        Fact("The FlightforgeSimulator component passes the node name "
             "'mrs_uav_flightforge_simulator' to its rclcpp::Node constructor.",
             source="upstream_code", ref="src/flightforge_simulator.cpp:663"),
        Fact("The shipped launch starts the component in an empty namespace with the node name "
             "'flightforge_simulator'.",
             source="upstream_code", ref=_NODE_NAME_REF),
        Fact("The node publishes rosgraph_msgs::msg::Clock on the private topic ~/clock_out.",
             source="upstream_code", ref=_CLOCK_PUBLISHER_REF),
        Fact("The shipped launch remaps ~/clock_out to the absolute /clock topic.",
             source="upstream_code", ref=_CLOCK_REMAP_REF),
        Fact("timerMain advances sim_time_ by one clock step (1/clock_rate) and publishes a "
             "rosgraph_msgs::msg::Clock message on every main-timer tick.",
             source="upstream_code", ref="src/flightforge_simulator.cpp:1320-1333"),
        Fact("The shipped config sets simulation_rate to 100.0 Hz and clock_rate to 400.0 Hz, with a comment that "
             "clock_rate should be at least simulation_rate.",
             source="upstream_code", ref="config/flightforge_simulator.yaml:4-7"),
        Fact("timerMain calls publishPoses after stepping every UAV that has not crashed, once at least one "
             "simulation step of sim time has passed since the last step.",
             source="upstream_code", ref="src/flightforge_simulator.cpp:1361-1377"),
        Fact("The node publishes geometry_msgs::msg::PoseArray on the private topic ~/uav_poses_out.",
             source="upstream_code", ref=_POSES_PUBLISHER_REF),
        Fact("The shipped launch remaps ~/uav_poses_out to the private topic ~/uav_poses.",
             source="upstream_code", ref=_POSES_REMAP_REF),
        Fact("publishPoses writes the current sim_time_ into the PoseArray header stamp, the configured "
             "world frame name into frame_id, and one pose per UAV from its position and attitude.",
             source="upstream_code", ref="src/flightforge_simulator.cpp:2412-2441"),
        Fact("The shipped config names the world frame 'simulator_origin'.",
             source="upstream_code", ref="config/flightforge_simulator.yaml:268-271"),
        Fact("The shipped uav list contains one UAV named uav1.",
             source="upstream_code", ref="config/uavs.yaml:1-3"),
        Fact("The node registers yaml_prefix + 'paused' through dynparam_mgr_->register_param with "
             "&drs_params_.paused, the literal false and callbackPause.",
             source="upstream_code", ref="src/flightforge_simulator.cpp:740"),
        Fact("timerInit sets drs_params_.paused to false.",
             source="upstream_code", ref="src/flightforge_simulator.cpp:864"),
        Fact("callbackPause cancels timer_main_ and timer_status_ when the paused parameter is true, "
             "and recreates both timers when it is false.",
             source="upstream_code", ref="src/flightforge_simulator.cpp:2111-2129"),
        Fact("timerInit constructs one mrs_multirotor_simulator::UavSystemRos on this node for every name in "
             "uav_names.",
             source="upstream_code", ref="src/flightforge_simulator.cpp:872-888"),
        Fact("timerInit creates a GameModeController for LOCALHOST port 8551 and, while rclcpp::ok(), retries "
             "Connect() every second, logging an error about Unreal's game mode controller.",
             source="upstream_code", ref="src/flightforge_simulator.cpp:894-905"),
        Fact("timerInit creates the ~/clock_out and ~/uav_poses_out publisher handlers and then the main wall "
             "timer with period 1 / (clock_rate * realtime_factor).",
             source="upstream_code", ref="src/flightforge_simulator.cpp:1183-1196"),
        Fact("The hw_api launch remaps the plugin's simulator command outputs (actuators, control group, "
             "attitude rate, attitude, acceleration, velocity, position and tracker commands) to "
             "/flightforge_simulator/<uav_name>/ topics.",
             source="upstream_code", ref="launch/hw_api.launch.py:110-124"),
        Fact("The hw_api plugin's callbackArming stores armed_ and returns success for both an arm and a "
             "disarm request.",
             source="upstream_code", ref="src/hw_api_plugin.cpp:360-380"),
        Fact("The LICENSE file is the GNU General Public License, version 2.",
             source="vendor_doc", ref="LICENSE:1-2"),
        Fact("package.xml declares the licence 'BSD 3-Clause'.",
             source="upstream_code", ref="package.xml:12"),
    ]
    safe_state = (
        "No acknowledged ROS service or action stop exists in the pinned clone: this observation-only "
        "profile has no native stop, and the stock e-stop only latches it (software-only) without "
        "claiming that the simulator node, its UAV models or the external FlightForge (Unreal Engine) "
        "process stopped."
    )
    #: The deployed backend is a ROS-free recording transport with canned
    #: placeholder replies; it is not the FlightForge simulator and not a
    #: capture of live traffic.
    fidelity = {
        "engine": "analytic:ROS-free contract fake with canned placeholder replies (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies; no FlightForge (Unreal Engine) process, physics step, "
                     "sensor renderer, wall-clock pacing or state-hash replay. The fake is not a capture of "
                     "live ROS traffic.",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free RecordingRosTransport: it answers the declared /clock and "
            "/flightforge_simulator/uav_poses subscriptions with placeholder constants and runs no "
            "FlightForge process, simulation step, physics, sensors, renderer or ROS graph",
            "the clock and pose values are placeholders and do not advance or move; a live run must "
            "receive the upstream node's own samples",
            "the upstream node creates the clock and pose publishers only after timerInit has connected to "
            "the FlightForge binary on localhost port 8551, which it retries every second without a limit "
            "(src/flightforge_simulator.cpp:894-905, 1183-1196); without the running binary, and while the "
            "paused parameter is true, both topics are silent and both reads time out",
            "the per-UAV command topics under /flightforge_simulator/<uav_name>/ (actuators, attitude, "
            "velocity, position and tracker commands), which the node's UavSystemRos objects (outside the "
            "clone) consume and the hw_api plugin publishes, are NOT COVERED; a ROS topic publication would "
            "be transmission-only and the clone has no acknowledged stop for it",
            "the dynamic parameter mrs_uav_flightforge_simulator/paused is NOT COVERED: ROS parameter "
            "access is not a rosbridge opcode and the clone does not declare the parameter-service "
            "type for a source-cited binding",
            "the hw_api plugin and its arming/offboard callbacks (callbackArming only stores a flag and "
            "answers success), per-UAV odom/imu/rangefinder topics, lidar and camera topics, camera_info, TF "
            "and the external FlightForge binary are NOT COVERED",
            "the package declares no native stop; the stock e-stop latches this observation profile "
            "and reports software_only, not a stopped simulator",
            "no live ROS 2 graph, rosbridge connection, simulator execution or hardware run has been "
            "performed; the fake evidence remains contract_checked",
        ],
    }

    # Both capabilities are fixed subscriptions; there is no resource snapshot
    # topic, so a paused or silent simulator does not hold an automatic read.
    commands = {
        "x-cap.ctu-mrs.clock.v1": _CLOCK,
        "x-cap.ctu-mrs.uav_poses.v1": _POSES,
    }
    actions = {
        "x-cap.ctu-mrs.clock.v1": Action(
            name="read_sim_clock",
            verb="read",
            description="Read one simulated clock sample published by the FlightForge node",
            output={"sim_time": _CLOCK_TIME},
        ),
        "x-cap.ctu-mrs.uav_poses.v1": Action(
            name="read_uav_poses",
            verb="read",
            description="Read one UAV pose array published by the FlightForge node",
            output={
                "stamp": Field(
                    "object",
                    description="PoseArray header stamp",
                    properties={
                        "sec": Field("integer", unit="s", description="Whole seconds of simulated time"),
                        "nanosec": Field("integer", unit="ns",
                                         description="Nanoseconds within the simulated second"),
                    },
                ),
                "frame_id": Field("string", description="PoseArray header frame_id"),
                "poses": Field("array", description="Poses in the PoseArray, one per configured UAV",
                               items=_POSE),
            },
        ),
    }
