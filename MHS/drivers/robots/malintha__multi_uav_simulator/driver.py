"""OpenMHS rosbridge driver for the Mavswarm2 multi-UAV simulator (gh.malintha/multi_uav_simulator).

The pinned clone is the ROS 2 ``mavswarm2`` C++ node: one ``Quadrotor``
process per vehicle.  This package is a configuration-only :class:`RosDriver`
over rosbridge; it declares no Python native class and neither imports nor
starts the upstream code.  The operator runs the clone's launch file and
rosbridge separately.

The selected bindings are the pinned node's own per-vehicle endpoints:

* ``/mavswarm2/robot_3/desired_state`` (``geometry_msgs/msg/Point``) is the
  goal input consumed by ``Quadrotor::desired_pos_cb``; the helper
  ``publish_words.py`` documents that these goals are in the controller's NED
  frame (x North, y East, z Down) and uses metres.
* ``/mavswarm2/robot_3/trajectory`` (``visualization_msgs/msg/Marker``) is the
  node's own LINE_STRIP trail in the ``map`` frame.  Read one sample and expose
  its last point as the vehicle position observation.

The clone creates no service or action server for control, reset or stop.  A
rosbridge publication is a transmission only (``published: true``,
``confirmed: false``); it never proves that the simulated vehicle moved or
stopped.  The node's only shutdown is ``rclcpp::shutdown()`` after
``rclcpp::spin()`` returns, which is not an acknowledged ROS stop.  The stock
e-stop therefore latches this driver and reports that the safe state was not
reached; RESULT.json records that concrete blocker instead of inventing a
stop service, a zero-velocity acknowledgement or a node-shutdown stop.

Every endpoint, type and fact cites the pinned clone at
f2cc09b22e4752c057cb8cc29c47e6fecfe04dde.  The fake transport is ROS-free;
no ROS graph, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: Comment in Quadrotor's constructor naming the exact per-robot goal endpoint
#: for robot_3; the code below builds the same name from the robot id.
_DESIRED_REF = "include/mavswarm2/quadrotor.hpp:93"

#: The subscription is declared with geometry_msgs::msg::Point and depth 10.
_DESIRED_DECL_REF = "include/mavswarm2/quadrotor.hpp:93-97"

#: The geometry_msgs Point include proves the ROS 2 message type.
_POINT_TYPE_REF = "include/mavswarm2/quadrotor.hpp:28"

#: Comment in Quadrotor's constructor naming the exact per-robot trajectory
#: endpoint for robot_3; the code below builds the same name from the robot id.
_TRAJECTORY_REF = "include/mavswarm2/quadrotor.hpp:105"

#: The publisher is declared with visualization_msgs::msg::Marker and depth 10.
_TRAJECTORY_DECL_REF = "include/mavswarm2/quadrotor.hpp:104-107"

#: The visualization_msgs Marker include proves the ROS 2 message type.
_MARKER_TYPE_REF = "include/mavswarm2/quadrotor.hpp:30"

#: The callback and the SCP planner handoff.
_CALLBACK_REF = "include/mavswarm2/quadrotor.hpp:212-223"

#: The marker's frame, namespace, id, type and action assignments.
_MARKER_FIELDS_REF = "include/mavswarm2/quadrotor.hpp:112-116"

#: The trail publisher samples and publishes the current map-frame position.
_PUBLISH_PATH_REF = "include/mavswarm2/quadrotor.hpp:279-304"

#: The helper's frame and metres documentation.
_HELPER_FRAME_REF = "publish_words.py:17-19"
_HELPER_DISTANCE_REF = "publish_words.py:247-248"

#: The helper's own Point publisher on the resolved absolute namespace.
_HELPER_PUBLISH_REF = "publish_words.py:217-221"
_HELPER_IMPORT_REF = "publish_words.py:30"

#: The launch and package/build facts for a deployment.
_LAUNCH_REF = "launch/quadrotor.launch:42-47"
_LAUNCH_FREQ_REF = "launch/quadrotor.launch:3"
_README_REF = "readme.md:39-47"
_PACKAGE_REF = "package.xml:10-21"
_CMAKE_REF = "CMakeLists.txt:21-45"

#: The frame conversion and TF broadcast.
_FRAME_REF = "include/mavswarm2/quadrotor.hpp:325-332"
_TF_REF = "include/mavswarm2/quadrotor.hpp:85-88"

#: main() spins and then shuts down; shutdown is not a ROS service or action.
_MAIN_REF = "src/quadrotor.cpp:23-33"

#: The clone states no numeric goal envelope.  The SCP planner's internal
#: v_max/a_max defaults constrain its trajectory solver, not the goal input;
#: the launch's initial_conditions and the helper's glyph constants are
#: configured layouts, not an input bound.  The operator supplies the NED
#: workspace envelope for this deployment.
_GOAL_LIMIT_REASON = (
    "the clone states no numeric position bound for the desired_state Point: the SCP planner's "
    "v_max and a_max are internal trajectory-solver defaults, the launch initial_conditions and "
    "the publish_words.py glyph constants are configured layouts, and the callback's 0.2 m "
    "deadband is a behaviour threshold, not an input envelope; the operator supplies the "
    "deployment's NED workspace bounds"
)

_POINT = Field(
    "object",
    description="Three-component Point from the simulator; the enclosing message/frame defines the frame",
    properties={
        "x": Field("number", unit="m", description="Point x component"),
        "y": Field("number", unit="m", description="Point y component"),
        "z": Field("number", unit="m", description="Point z component"),
    },
)

_POSITION = Field(
    "object",
    description="Last trajectory-marker point, interpreted in the marker header frame (map/NWU)",
    properties={
        "x": Field("number", unit="m", description="map-frame x component"),
        "y": Field("number", unit="m", description="map-frame y component"),
        "z": Field("number", unit="m", description="map-frame z component"),
    },
)

_TRAIL = Field(
    "array",
    description="Ordered map-frame LINE_STRIP points from the node's trajectory marker (at most 200)",
    items=_POINT,
)

_PUBLISHED = {
    "published": Field(
        "boolean",
        description="True when the rosbridge client handed the Point publication to the transport",
    ),
    "confirmed": Field(
        "boolean",
        description="Always false: a ROS topic publication has no execution acknowledgement",
    ),
}

_DESIRED_STATE = {
    "topic": "/mavswarm2/robot_3/desired_state",
    "type": "geometry_msgs/msg/Point",
    "source_name": "/mavswarm2/robot_3/desired_state",
    "source_ref": _DESIRED_REF,
    "type_ref": _POINT_TYPE_REF,
    "operation": "publish",
    "message": {"x": 0.0, "y": 0.0, "z": 0.0},
    "args": {
        "x": {"from": "input.x"},
        "y": {"from": "input.y"},
        "z": {"from": "input.z"},
    },
    "result": {"map": {"published": "output.published", "confirmed": "output.confirmed"}},
}

_TRAJECTORY = {
    "topic": "/mavswarm2/robot_3/trajectory",
    "type": "visualization_msgs/msg/Marker",
    "source_name": "/mavswarm2/robot_3/trajectory",
    "source_ref": _TRAJECTORY_REF,
    "type_ref": _MARKER_TYPE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"position": "output.points[-1]", "frame_id": "output.header.frame_id"}},
    "timeout_ms": 2000,
}

_TRAJECTORY_READ = {
    "topic": "/mavswarm2/robot_3/trajectory",
    "type": "visualization_msgs/msg/Marker",
    "source_name": "/mavswarm2/robot_3/trajectory",
    "source_ref": _TRAJECTORY_REF,
    "type_ref": _MARKER_TYPE_REF,
    "operation": "subscribe",
    "path": "points",
    "timeout_ms": 2000,
}

#: The command topic is also observable as a wire snapshot: the last Point that
#: this driver handed to rosbridge.  It is not execution feedback and it does
#: not prove that the SCP planner accepted or flew the goal.  Model review: in a
#: ROS graph the topic is volatile and only clients publish it, so this resource
#: read waits for the next publication (each command then waits the 2 s read
#: timeout and mhs.resource.read fails NOT_READY); the fake answers at once.
_LAST_GOAL_READ = {
    "topic": "/mavswarm2/robot_3/desired_state",
    "type": "geometry_msgs/msg/Point",
    "source_name": "/mavswarm2/robot_3/desired_state",
    "source_ref": _DESIRED_REF,
    "type_ref": _POINT_TYPE_REF,
    "operation": "subscribe",
    "path": "$",
    "timeout_ms": 2000,
}


class Mavswarm2Robot3(RosDriver):
    device_id = "mavswarm2-robot3"
    device_kind = "world.sim"
    mode = "simulated"
    #: The package only binds one simulated vehicle's goal topic and its own
    #: visualisation trail.  No physical equipment is controlled; SAFE-006
    #: classifies isolated simulated state/stepping as R0.  The card floor is R0.
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeMultiUavSimulator"}
    tags = ["ros", "ros2", "simulation", "mavswarm2", "multi-uav", "quadrotor", "trajectory"]
    display_name = "Mavswarm2 quadrotor (robot_3)"
    vendor = "malintha"
    model = "Mavswarm2 Quadrotor"
    facts = [
        Fact("Quadrotor constructs its node name as \"robot_\" + to_string(robot_id) and computes "
             "dt = 1.0 / frequency.", source="upstream_code", ref="include/mavswarm2/quadrotor.hpp:59-64"),
        Fact("The constructor logs dt and creates a wall timer with period dt that runs iteration.",
             source="upstream_code", ref="include/mavswarm2/quadrotor.hpp:68-72"),
        Fact("The constructor creates one subscription to a per-robot desired_state topic of type "
             "geometry_msgs::msg::Point with queue size 10; the adjacent comment names "
             "/mavswarm2/robot_3/desired_state as the example.",
             source="upstream_code", ref=_DESIRED_DECL_REF),
        Fact("desired_pos_cb converts the received Point to (x, y, z), returns without action when "
             "the new target is within 0.2 m of target_pos, otherwise stores it and calls "
             "scp_planner_->set_goal(p1, ss.position, ss.velocity).",
             source="upstream_code", ref="include/mavswarm2/quadrotor.hpp:215-223"),
        Fact("The comment above desired_pos_cb names the goal handoff as the NED frame.",
             source="upstream_code", ref=_CALLBACK_REF),
        Fact("publish_words.py states that goals are in the controller's NED frame (x North, y East, "
             "z Down; negative z is up).", source="upstream_code", ref=_HELPER_FRAME_REF),
        Fact("publish_words.py imports geometry_msgs.msg.Point.",
             source="upstream_code", ref=_HELPER_IMPORT_REF),
        Fact("publish_words.py creates one Point publisher per robot on "
             "/mavswarm2/robot_{i}/desired_state with queue size 10.",
             source="upstream_code", ref=_HELPER_PUBLISH_REF),
        Fact("The helper's assignment log reports the total distance in metres.",
             source="upstream_code", ref=_HELPER_DISTANCE_REF),
        Fact("The constructor creates a visualization_msgs::msg::Marker publisher on the per-robot "
             "trajectory topic with queue size 10; the adjacent comment names "
             "/mavswarm2/robot_3/trajectory as the example.",
             source="upstream_code", ref=_TRAJECTORY_DECL_REF),
        Fact("The trajectory marker is a LINE_STRIP in frame map with namespace trajectory, id "
             "robot_id and action ADD.", source="upstream_code", ref=_MARKER_FIELDS_REF),
        Fact("publish_path samples every fifth timer tick, appends state_space.position (NWU/map "
             "frame) to the marker points, keeps at most 200 points, and publishes the marker.",
             source="upstream_code", ref=_PUBLISH_PATH_REF),
        Fact("set_state_space converts the internal NED state to the map frame with "
             "ned_nwu_rotation before broadcasting.", source="upstream_code", ref=_FRAME_REF),
        Fact("The constructor creates a tf2_ros::TransformBroadcaster, sets the world frame to map and the "
             "child frame to robot_<id>/base_link.", source="upstream_code", ref=_TF_REF),
        Fact("main spins the Quadrotor node and calls rclcpp::shutdown() after spin returns.",
             source="upstream_code", ref=_MAIN_REF),
        Fact("The launch file starts the mavswarm2 executable as node robot_3 in namespace "
             "mavswarm2.", source="upstream_code", ref=_LAUNCH_REF),
        Fact("The launch's controller_frequency argument defaults to 100.",
             source="upstream_code", ref=_LAUNCH_FREQ_REF),
        Fact("The README documents colcon build and ros2 launch mavswarm2 quadrotor.launch.",
             source="vendor_doc", ref=_README_REF),
        Fact("package.xml declares ament_cmake and the rclcpp, simulator_interfaces, std_msgs, "
             "geometry_msgs, sensor_msgs, visualization_msgs, tf2 and tf2_ros dependencies.",
             source="upstream_code", ref=_PACKAGE_REF),
        Fact("CMakeLists.txt builds the mavswarm2 executable from src/quadrotor.cpp, links GSL and "
             "glog, and installs the launch, config and cf_description directories.",
             source="upstream_code", ref=_CMAKE_REF),
        Fact("The repository LICENSE file is the GNU General Public License, version 3.",
             source="upstream_code", ref="LICENSE:1-2"),
        Fact("The header of quadrotor.hpp states that the file is licensed under the Apache License, "
             "Version 2.0.", source="upstream_code", ref="include/mavswarm2/quadrotor.hpp:2-4"),
        Fact("package.xml declares the licence as 'TODO: License declaration'.",
             source="upstream_code", ref="package.xml:8"),
    ]
    #: The pinned node creates no service or action server; its only stop-like
    #: path is process shutdown or a hover goal, neither acknowledged.  The
    #: text states the missing contract instead of claiming a stop.
    safe_state = (
        "No acknowledged stop exists in the pinned clone: the only control input is the "
        "desired_state Point publication, and the node creates no service or action and reports no "
        "measured quiescence. The stock e-stop can only latch this driver's publications and reports "
        "that the simulated vehicle's safe state was not reached; an operator must stop the ROS "
        "process or publish a hover goal outside the latched driver path."
    )
    #: The deployed fake is a ROS-free contract stand-in, not a recording of
    #: captured traffic and not the Mavswarm2 simulator.
    fidelity = {
        "engine": "analytic:ROS contract fake (canned replies; no Mavswarm2 node or physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies with no SCP planner, controller, GSL dynamics, "
                     "wall-clock pacing or state-hash replay; the fake is not a recording of captured "
                     "traffic",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free RecordingRosTransport: it answers the declared trajectory "
            "subscription with a placeholder Marker and records publications to the desired_state "
            "topic; it runs no mavswarm2 node, SCP planner, geometric controller, GSL dynamics, TF "
            "broadcaster or RViz",
            "the marker points are placeholder constants and do not advance; a live run must "
            "receive the node's own /mavswarm2/robot_3/trajectory samples",
            "the desired_state publication is recorded only; the fake does not plan, fly or apply a "
            "goal and cannot claim that the simulated vehicle moved",
            "the last_goal resource observation echoes the last recorded publication; in a live "
            "deployment the command topic is volatile, so a fresh subscription receives a message only "
            "when one is published while it waits and the read is not a replay of the last goal",
            "because of that, in a live graph every command waits the 2 s last_goal read timeout and "
            "mhs.resource.read fails MHS.DEVICE.NOT_READY unless a goal is published meanwhile (model "
            "review probe with the topic silent); the fake answers the subscription at once with a "
            "placeholder or the last recorded goal",
            "the clone registers no control, reset or stop service/action; the package declares no "
            "safety binding and the stock e-stop reports SAFE_STATE_UNREACHED",
            "TF, SCP path, the other robots, parameter services, sensors, camera, RViz, world step, "
            "reset, snapshot and restore are NOT COVERED",
            "the upstream depends on the external simulator_interfaces package and GSL/Eigen; the "
            "clone was not built, launched or connected to a live ROS graph",
        ],
    }
    parameters = {"trail": _TRAIL, "last_goal": _POINT}
    reads = {
        "trail": _TRAJECTORY_READ,
        "last_goal": _LAST_GOAL_READ,
    }
    commands = {
        "x-cap.malintha.desired_state.v1": _DESIRED_STATE,
        "x-cap.malintha.trajectory.v1": _TRAJECTORY,
    }
    actions = {
        "x-cap.malintha.desired_state.v1": Action(
            name="publish_desired_state",
            description=(
                "Publish one geometry_msgs/Point goal to /mavswarm2/robot_3/desired_state. The "
                "receipt confirms transmission only; it does not prove that the SCP planner accepted "
                "the goal or that the simulated vehicle moved."
            ),
            input={
                "x": Field(
                    "number", unit="m",
                    description="Goal x in the controller's NED frame (North)",
                    limit=Limit.operator_required(_GOAL_LIMIT_REASON),
                ),
                "y": Field(
                    "number", unit="m",
                    description="Goal y in the controller's NED frame (East)",
                    limit=Limit.operator_required(_GOAL_LIMIT_REASON),
                ),
                "z": Field(
                    "number", unit="m",
                    description="Goal z in the controller's NED frame (Down; negative is up)",
                    limit=Limit.operator_required(_GOAL_LIMIT_REASON),
                ),
            },
            output=_PUBLISHED,
            examples=[{"x": 0.0, "y": 0.0, "z": 0.0}],
        ),
        "x-cap.malintha.trajectory.v1": Action(
            name="read_trajectory_position",
            verb="read",
            description=(
                "Read one visualization_msgs/Marker sample from "
                "/mavswarm2/robot_3/trajectory and return its last LINE_STRIP point in the marker "
                "header frame (map). This is a visualisation trail, not an acknowledged state or a "
                "stopped-state measurement."
            ),
            output={"position": _POSITION, "frame_id": Field("string", description="Marker header frame_id")},
        ),
    }
