"""OpenMHS rosbridge driver for the UWSim underwater simulator.

The pinned repository is a C++ ROS 1 simulator.  Its executable interface is
the rosInterfaces block of a scene file: the simulator subscribes to a
geometry_msgs/TwistStamped velocity reference and publishes arm joint state and
range observations.  This package binds the default ``cirs.xml`` scene's
vehicle twist topic, its joint-state and range topics, and a ROS-free recording
fake.

The clone exposes no ROS service or action that acknowledges a stop.  uwsim's
only service is the SpawnMarker scene service; the optional
underwater_vehicle_dynamics node adds /dynamics/reset, which restores pose and
velocity but keeps the thruster setpoint; and the simulator's ``stopAll`` path
is a process shutdown reached from SIGTERM or after the viewer loop.  Each
TwistStamped moves the vehicle once, by its twist times the wall time since the
previous message (zero for the first message and after a gap above 1 s), so
the vehicle moves only while messages arrive and nothing acknowledges a stop
(model review, 2026-11-05).  The package therefore declares no fabricated stop
binding and documents the blocked control surface instead of claiming a safe
state.

Every endpoint and fact cites the pinned clone at
7f4a276c55f34524e418f56a6da401172943f886.  No ROS graph, simulator or
hardware is contacted by the fake.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The default scene is data/scenes/cirs.xml and the node is initialized as UWSim.
_DEFAULT_SCENE_REF = "uwsim/src/main.cpp:157-164"
_LOOP_REF = "uwsim/src/main.cpp:195-244"
_STOP_REF = "uwsim/src/main.cpp:31-50"

#: The default scene declares the control and observation interfaces.
_TWIST_SCENE_REF = "uwsim/data/scenes/cirs.xml:359-362"
_POSE_SCENE_REF = "uwsim/data/scenes/cirs.xml:368-371"
_JOINT_COMMAND_SCENE_REF = "uwsim/data/scenes/cirs.xml:350-353"
_JOINT_STATE_SCENE_REF = "uwsim/data/scenes/cirs.xml:346-349"
_RANGE_SCENE_REF = "uwsim/data/scenes/cirs.xml:363-367"
_IMU_SCENE_REF = "uwsim/data/scenes/cirs.xml:372-376"
_DEPTH_SCENE_REF = "uwsim/data/scenes/cirs.xml:377-381"
_CAMERA_SCENE_REF = "uwsim/data/scenes/cirs.xml:354-358"

#: The subscriber/publisher implementations and their ROS types.
_TWIST_SUB_REF = "uwsim/src/ROSInterface.cpp:150-154"
_TWIST_CALLBACK_REF = "uwsim/src/ROSInterface.cpp:156-190"
_MAX_ELAPSED_REF = "uwsim/include/uwsim/ROSInterface.h:64-65"
_POSE_SUB_REF = "uwsim/src/ROSInterface.cpp:212-232"
_JOINT_SUB_REF = "uwsim/src/ROSInterface.cpp:409-432"
_JOINT_STATE_PUB_REF = "uwsim/src/ROSInterface.cpp:691-714"
_RANGE_PUB_REF = "uwsim/src/ROSInterface.cpp:941-960"
_IMU_PUB_REF = "uwsim/src/ROSInterface.cpp:576-600"
_DEPTH_PUB_REF = "uwsim/src/ROSInterface.cpp:612-630"
_CAMERA_PUB_REF = "uwsim/src/ROSInterface.cpp:755-796"
#: The only advertised service in the clone.
_ONLY_SERVICE_REF = "uwsim/src/ROSSceneBuilder.cpp:34"

#: The pressure message is named "pressure", but PressureSensor returns a
#: localized z coordinate (a length), not a pressure in Pa.
_DEPTH_MEASURE_REF = "uwsim/src/PressureSensor.cpp:18-29"

_VELOCITY_REASON = (
    "the clone's ROSTwistToPAT subscribes to geometry_msgs/TwistStamped and applies "
    "the six twist components without any numeric velocity bound; the operator "
    "supplies the signed velocity envelope"
)


def _velocity_limit(axis: str) -> Limit:
    return Limit.operator_required(f"{_VELOCITY_REASON} ({axis})")


_JOINT_NAMES = Field(
    "array",
    description="Joint names selected from sensor_msgs/JointState.name",
    items=Field("string", description="One joint name"),
)

_JOINT_POSITIONS = Field(
    "array",
    unit="rad",
    description="Joint positions selected from sensor_msgs/JointState.position",
    items=Field("number", unit="rad", description="One joint position"),
)

_RANGE = Field(
    "number",
    unit="m",
    description="Range from sensor_msgs/Range.range",
)

#: The primary control: one geometry_msgs/TwistStamped publication.  The
#: ROSTwistToPAT subscriber integrates it over wall time; no reply acknowledges
#: motion, arrival or stopping.
_TWIST = {
    "topic": "/g500/twist",
    "type": "geometry_msgs/TwistStamped",
    "operation": "publish",
    "source_ref": _TWIST_SCENE_REF,
    "type_ref": _TWIST_SUB_REF,
    "message": {
        "twist": {
            "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
    },
    "args": {
        "twist.linear.x": {"from": "input.linear_x"},
        "twist.linear.y": {"from": "input.linear_y"},
        "twist.linear.z": {"from": "input.linear_z"},
        "twist.angular.x": {"from": "input.angular_x"},
        "twist.angular.y": {"from": "input.angular_y"},
        "twist.angular.z": {"from": "input.angular_z"},
    },
}

#: ArmToROSJointState advertises sensor_msgs/JointState on the absolute
#: /uwsim/joint_state topic and fills name and position (effort is pushed as
#: zero; velocity is left empty).
_JOINT_STATE = {
    "topic": "/uwsim/joint_state",
    "type": "sensor_msgs/JointState",
    "source_ref": _JOINT_STATE_SCENE_REF,
    "type_ref": _JOINT_STATE_PUB_REF,
    "path": "$",
}

#: RangeSensorToROSRange advertises sensor_msgs/Range on the absolute
#: /uwsim/g500/range topic.
_RANGE_READ = {
    "topic": "/uwsim/g500/range",
    "type": "sensor_msgs/Range",
    "source_ref": _RANGE_SCENE_REF,
    "type_ref": _RANGE_PUB_REF,
    "path": "range",
}


class UnderwaterSimulation(RosDriver):
    device_id = "underwater-simulation"
    device_kind = "world.sim"
    mode = "simulated"
    # The primary capability publishes a vehicle velocity reference.  The
    # catalogue's mobile-base class is R2 and the package follows the higher
    # hazard of the motion it exposes even though the state is simulated.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeUnderwaterSimulation"}
    tags = ["ros", "ros1", "simulation", "underwater", "uwsim", "twist", "joint-state", "range"]
    display_name = "UWSim underwater simulator"
    vendor = "uji-ros-pkg"
    model = "UWSim cirs.xml scene with girona500 vehicle"
    facts = [
        Fact("The simulator defaults to data/scenes/cirs.xml and initializes the ROS node as UWSim.",
             source="upstream_code", ref=_DEFAULT_SCENE_REF),
        Fact("The main loop runs at 60 Hz, sets the ROS interface time from ros::Time::now(), spins callbacks, "
             "steps physics when enabled and draws a frame every iteration.", source="upstream_code",
             ref=_LOOP_REF),
        Fact("The default scene declares ROSTwistToPAT for the girona500 vehicle on the absolute "
             "/g500/twist topic.", source="upstream_code", ref=_TWIST_SCENE_REF),
        Fact("ROSTwistToPAT subscribes to geometry_msgs/TwistStamped on its configured topic.",
             source="upstream_code", ref=_TWIST_SUB_REF),
        Fact("ROSTwistToPAT::processData translates and rotates the vehicle by linear and angular twist "
             "times the wall-clock elapsed time since the previous message.",
             source="upstream_code", ref=_TWIST_CALLBACK_REF),
        Fact("ROSInterface.h defines MAX_ELAPSED as 1, commented as the maximum time in seconds between two "
             "consecutive control references.", source="upstream_code", ref=_MAX_ELAPSED_REF),
        Fact("processData uses zero elapsed time for the first message and whenever more than 1 s of wall time "
             "passed since the previous message, and applies one translation and rotation of twist times that "
             "elapsed time per message.", source="upstream_code", ref="uwsim/src/ROSInterface.cpp:156-190"),
        Fact("The default scene also declares ROSPoseToPAT on /g500/pose for the girona500 vehicle.",
             source="upstream_code", ref=_POSE_SCENE_REF),
        Fact("ROSPoseToPAT subscribes to geometry_msgs/Pose and sets position and orientation directly.",
             source="upstream_code", ref=_POSE_SUB_REF),
        Fact("The default scene declares ROSJointStateToArm on /uwsim/joint_state_command for the girona500 "
             "vehicle.", source="upstream_code", ref=_JOINT_COMMAND_SCENE_REF),
        Fact("ROSJointStateToArm subscribes to sensor_msgs/JointState and calls setJointPosition or "
             "setJointVelocity depending on which array is nonempty.",
             source="upstream_code", ref=_JOINT_SUB_REF),
        Fact("The default scene declares ArmToROSJointState on the absolute /uwsim/joint_state topic.",
             source="upstream_code", ref=_JOINT_STATE_SCENE_REF),
        Fact("ArmToROSJointState advertises sensor_msgs/JointState, fills name and position, pushes effort 0 "
             "for every joint and leaves velocity empty.", source="upstream_code",
             ref=_JOINT_STATE_PUB_REF),
        Fact("ROSSceneBuilder advertises the relative SpawnMarker service.", source="upstream_code",
             ref=_ONLY_SERVICE_REF),
        Fact("The underwater_vehicle_dynamics dynamics node advertises the /dynamics/reset std_srvs/Empty service.",
             source="upstream_code", ref="underwater_vehicle_dynamics/src/dynamics.py:323"),
        Fact("The /dynamics/reset callback sets velocity and pose back to their initial values and returns; it "
             "does not touch the thruster setpoint u.", source="upstream_code",
             ref="underwater_vehicle_dynamics/src/dynamics.py:249-252"),
        Fact("UWSim_g500_dynamics.launch starts the g500 dynamics node, uwsim with the cirs.xml scene and "
             "keyboard.py publishing to /g500/thrusters_input.", source="upstream_code",
             ref="underwater_vehicle_dynamics/launch/UWSim_g500_dynamics.launch:1-12"),
        Fact("dynamics.launch passes /<namespace>/pose as the dynamics node's default output topic.",
             source="upstream_code", ref="underwater_vehicle_dynamics/launch/dynamics.launch:7-10"),
        Fact("The dynamics node publishes the vehicle pose from a rospy.Timer every uwsim_period.",
             source="upstream_code", ref="underwater_vehicle_dynamics/src/dynamics.py:314-315"),
        Fact("dynamics_g500.yaml sets g500/dynamics/uwsim_period to 0.001.", source="upstream_code",
             ref="underwater_vehicle_dynamics/config/dynamics_g500.yaml:5"),
        Fact("keyboard.py publishes a five-element thruster array every 0.1 s, zeros unless a key is pressed, "
             "and calls /dynamics/reset on the space key.", source="upstream_code",
             ref="underwater_vehicle_dynamics/src/keyboard.py:29-66"),
        Fact("stopROS calls ros::shutdown while ROS is ok, and stopAll flushes the network simulator log and "
             "calls stopROS.", source="upstream_code", ref=_STOP_REF),
        Fact("The SIGTERM callback calls stopAll.", source="upstream_code", ref="uwsim/src/main.cpp:206-209"),
        Fact("The default scene declares RangeSensorToROSRange on the absolute /uwsim/g500/range topic at "
             "rate 10.", source="upstream_code", ref=_RANGE_SCENE_REF),
        Fact("RangeSensorToROSRange advertises sensor_msgs/Range and publishes the measured distance in range "
             "and the configured sensor range in max_range.", source="upstream_code", ref=_RANGE_PUB_REF),
        Fact("The default scene declares ImuToROSImu on the relative g500/imu topic.",
             source="upstream_code", ref=_IMU_SCENE_REF),
        Fact("ImuToROSImu advertises sensor_msgs/Imu and fills the orientation quaternion and the orientation "
             "covariance diagonal; angular_velocity and linear_acceleration remain the message defaults.",
             source="upstream_code", ref=_IMU_PUB_REF),
        Fact("The default scene declares PressureSensorToROS on the relative g500/pressure topic.",
             source="upstream_code", ref=_DEPTH_SCENE_REF),
        Fact("PressureSensor::getMeasurement returns the z translation in the localized world frame plus "
             "Gaussian noise.", source="upstream_code", ref=_DEPTH_MEASURE_REF),
        Fact("PressureSensorToROS::publish copies getMeasurement() into the pressure field of an "
             "underwater_sensor_msgs/Pressure message.", source="upstream_code",
             ref="uwsim/src/ROSInterface.cpp:618-631"),
        Fact("The default scene declares VirtualCameraToROSImage for camera bowtech1 on /uwsim/camera1 and "
             "/uwsim/camera1_info.", source="upstream_code", ref=_CAMERA_SCENE_REF),
        Fact("VirtualCameraToROSImage advertises an image_transport image and a sensor_msgs/CameraInfo and "
             "sets the image encoding to 32FC1 for a depth camera, mono8 for a black-and-white one and rgb8 "
             "otherwise.", source="upstream_code", ref=_CAMERA_PUB_REF),
        Fact("The uwsim package declares the licence GPL.", source="upstream_code", ref="uwsim/package.xml:15"),
        Fact("uwsim/license.txt is the GNU General Public License version 3.", source="upstream_code",
             ref="uwsim/license.txt:1-2"),
    ]
    safe_state = (
        "No acknowledged stop: uwsim has no stop, pause or reset service or action, and the optional "
        "dynamics node's /dynamics/reset restores pose and velocity but keeps the thruster setpoint. "
        "Each /g500/twist message moves the vehicle once (twist times the wall time since the previous "
        "message), so after the latch no MHS message moves it, but nothing acknowledges that, and other "
        "publishers on /g500/twist, /g500/pose and the arm command topic are not fenced."
    )
    fidelity = {
        "engine": "analytic:ROS recording fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven rosbridge fake with no physics step, integration, wall-clock pacing "
                     "or state-hash replay; the observations are canned placeholders",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it answers the declared /g500/twist publication "
            "and the /uwsim/joint_state and /uwsim/g500/range subscriptions, but runs no UWSim, OSG, "
            "Bullet physics, scene or wall-clock loop",
            "the twist publication is transmission only; the fake does not integrate it and cannot show "
            "that the simulated vehicle moved or stopped",
            "the joint names, joint positions and range values are placeholders; a live run must receive "
            "them from the operator's UWSim scene and pinned uwsim node",
            "the default cirs.xml scene has no PATToROSOdom output, so no vehicle pose or odometry topic "
            "is bound from that scene",
            "the /g500/pose and /uwsim/joint_state_command control inputs are NOT COVERED; this package "
            "binds only the vehicle twist control",
            "the camera image and CameraInfo topics, range camera, IMU, pressure/depth, DVL, GPS, "
            "multibeam LaserScan, force, echo, contact and TF outputs are NOT COVERED",
            "the IMU and pressure topics are configured as relative names (g500/imu and g500/pressure) "
            "in the scene XML; this package does not invent a resolved absolute spelling for them",
            "uwsim's only ROS service is SpawnMarker (scene markers, not a stop); the optional "
            "underwater_vehicle_dynamics node adds /dynamics/reset, which keeps the thruster setpoint "
            "(dynamics.py:249-252, :323) and is not a stop either",
            "model review: a single publication moves nothing when it is the first message on /g500/twist or "
            "comes more than 1 s after the previous one (ROSInterface.cpp:166-176), so isolated MHS "
            "invocations do not move the vehicle; in the shipped UWSim_g500_dynamics.launch the dynamics node "
            "publishes /g500/pose every 1 ms, which ROSPoseToPAT applies directly, and keyboard.py publishes "
            "thrusters every 0.1 s, both competing with the twist input",
            "the main loop has no pause flag; closing the viewer or SIGTERM calls stopAll and shuts down "
            "ROS, which is process shutdown, not a source-backed ROS stop binding",
        ],
    }

    parameters = {
        "joint_names": _JOINT_NAMES,
        "joint_positions": _JOINT_POSITIONS,
        "range": _RANGE,
    }
    reads = {
        "joint_names": dict(_JOINT_STATE, path="name", timeout_ms=2000),
        "joint_positions": dict(_JOINT_STATE, path="position", timeout_ms=2000),
        "range": dict(_RANGE_READ, timeout_ms=2000),
    }
    commands = {
        "x-cap.uji-ros-pkg.vehicle_twist.v1": _TWIST,
        "x-cap.uji-ros-pkg.joint_state.v1": dict(
            _JOINT_STATE, operation="subscribe",
            result={"map": {"names": "name", "positions": "position"}},
        ),
        "x-cap.uji-ros-pkg.range.v1": dict(
            _RANGE_READ, operation="subscribe", result={"map": {"range": "output.$"}},
        ),
    }
    actions = {
        "x-cap.uji-ros-pkg.vehicle_twist.v1": Action(
            name="publish_vehicle_twist",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one geometry_msgs/TwistStamped velocity reference to /g500/twist. The receipt "
                "confirms only that rosbridge accepted the publication, not motion, arrival or stopping."
            ),
            input={
                "linear_x": Field("number", unit="m/s", description="twist.linear.x",
                                  limit=_velocity_limit("linear.x")),
                "linear_y": Field("number", unit="m/s", description="twist.linear.y",
                                  limit=_velocity_limit("linear.y")),
                "linear_z": Field("number", unit="m/s", description="twist.linear.z",
                                  limit=_velocity_limit("linear.z")),
                "angular_x": Field("number", unit="rad/s", description="twist.angular.x",
                                   limit=_velocity_limit("angular.x")),
                "angular_y": Field("number", unit="rad/s", description="twist.angular.y",
                                   limit=_velocity_limit("angular.y")),
                "angular_z": Field("number", unit="rad/s", description="twist.angular.z",
                                   limit=_velocity_limit("angular.z")),
            },
            output={
                "published": Field("boolean", description="True when rosbridge accepted the publication"),
                "confirmed": Field("boolean", description="Always false: a publication has no execution "
                                                         "or stop confirmation"),
            },
            examples=[{"linear_x": 0.0, "linear_y": 0.0, "linear_z": 0.0,
                       "angular_x": 0.0, "angular_y": 0.0, "angular_z": 0.0}],
        ),
        "x-cap.uji-ros-pkg.joint_state.v1": Action(
            name="read_joint_state",
            verb="read",
            description="Read one sensor_msgs/JointState sample from /uwsim/joint_state",
            output={"names": _JOINT_NAMES, "positions": _JOINT_POSITIONS},
        ),
        "x-cap.uji-ros-pkg.range.v1": Action(
            name="read_range",
            verb="read",
            description="Read one sensor_msgs/Range sample from /uwsim/g500/range",
            output={"range": _RANGE},
        ),
    }
    # The clone exposes no ROS service or action that could acknowledge a stop.
    # A zero-twist publication is not a stop, and process shutdown is not a
    # source-backed stop binding, so no fabricated safety binding is declared.
    safety_bindings = {}
