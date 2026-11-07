"""XTDrone typhoon_h480_0 position bridge with a Gazebo world-pause e-stop.

This package is a configuration-only :class:`RosDriver`. Its accepted surface
is one ``geometry_msgs/PoseStamped`` publication on
``/typhoon_h480_0/mavros/setpoint_position/local``, explicit reads of the
MAVROS local target and local pose, and the vendored gazebo_ros 2.8.7 world
pause. The publication is transmission only. The receipt reports the values
handed to rosbridge. It does not report arrival, arming, or a stop.

The e-stop calls ``/gazebo/pause_physics`` and is confirmed only when
``/gazebo/get_physics_properties`` reports ``pause`` true. That flag is the
world's paused bit. It is not a measured standstill and it does not disarm
the vehicle. No unpause is offered (SAFE-042): the multirotor communication
node republishes ``target_motion`` until shutdown and ignores the string
``stop controlling``, and this package cannot clear that retained target.
``mhs.safety.reset`` releases the latch only. The world stays paused. The
operator recovers outside MHS.

Arming and OFFBOARD stay outside MHS. The communication nodes build
``CommandBool`` and ``SetMode`` proxies, and this package does not bind them.
Velocity, acceleration, landing, and state remain outside the accepted
surface. The device resource reads no topic, because a paused lockstep world
may publish nothing. Evidence is ``contract_checked`` on the ROS-free fake.
No hardware run and no simulator run is claimed.

Every endpoint and type cites the pinned clone at
671f3d45b22bfe4b7f2b23ae8d4251f3172781b3. gazebo_ros is vendored in that
clone, so these citations are clone paths.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

_GAZEBO = "sitl_config/gazebo_ros_pkgs"
_API = _GAZEBO + "/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
_YAML = _GAZEBO + "/gazebo_ros/test/ros_network/gazebo_network_api.yaml"
_EMPTY = _GAZEBO + "/gazebo_ros/launch/empty_world.launch"
_SRV = _GAZEBO + "/gazebo_msgs/srv/GetPhysicsProperties.srv"
_LAUNCH = "sitl_config/launch/multi_vehicle.launch"
_COMM = "communication/multirotor_communication.py"

#: Pause the world. The relative name is the quoted literal in the advertiser.
_PAUSE = {
    "service": "/gazebo/pause_physics",
    "type": "std_srvs/Empty",
    "source_name": "pause_physics",
    "source_ref": _API + ":508-514",
    "type_ref": _YAML + ":85-86",
    "state_ref": _API + ":1738-1742",
    "description": "Pause the Gazebo world (vendored gazebo_ros pause_physics: World::SetPaused(true))",
    "request": {},
    "success": {"path": "$", "equals": {}},
    "timeout_ms": 500,
}
#: Confirm the paused flag. A non-ODE engine returns false and the e-stop stays unconfirmed.
_READBACK = {
    "service": "/gazebo/get_physics_properties",
    "type": "gazebo_msgs/GetPhysicsProperties",
    "source_name": "get_physics_properties",
    "source_ref": _API + ":389-395",
    "type_ref": _YAML + ":55-56",
    "state_ref": _API + ":1484",
    "description": "Read the world's paused flag back; the e-stop is confirmed only when pause is true",
    "request": {},
    "success": {"path": "pause", "equals": True},
    "timeout_ms": 500,
}

_TARGET = {
    "topic": "/typhoon_h480_0/mavros/setpoint_raw/target_local",
    "type": "mavros_msgs/PositionTarget",
    "source_ref": "contributer_demo/demo1/doc/rostopic list:123",
    "type_ref": _COMM + ":2",
}
_POSE = {
    "topic": "/typhoon_h480_0/mavros/local_position/pose",
    "type": "geometry_msgs/PoseStamped",
    "source_ref": "contributer_demo/demo1/doc/rostopic list:84",
    "type_ref": _COMM + ":4",
}
_SETPOINT = {
    "topic": "/typhoon_h480_0/mavros/setpoint_position/local",
    "type": "geometry_msgs/PoseStamped",
    "operation": "publish",
    "source_ref": "contributer_demo/demo1/doc/rostopic list:117",
    "type_ref": _COMM + ":4",
    "message": {
        "header": {"frame_id": "map", "stamp": {"secs": 0, "nsecs": 0}},
        "pose": {
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
    },
    "args": {
        "pose.position.x": {"from": "input.x"},
        "pose.position.y": {"from": "input.y"},
        "pose.position.z": {"from": "input.z"},
    },
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
}

_POSITION_REASON = (
    "the clone states no safe local-position envelope for the vehicle; the "
    "operator supplies the deployment bound"
)
_SETPOINT_ID = "x-cap.robin-shaun.setpoint_position.v1"

_TARGET_FIELDS = {
    "target_x": Field("number", unit="m", description="MAVROS local target x"),
    "target_y": Field("number", unit="m", description="MAVROS local target y"),
    "target_z": Field("number", unit="m", description="MAVROS local target z"),
}
_POSE_FIELDS = {
    "position_x": Field("number", unit="m", description="Current local position x"),
    "position_y": Field("number", unit="m", description="Current local position y"),
    "position_z": Field("number", unit="m", description="Current local position z"),
}


class _SentReceipt:
    """Add the three values a position publication handed to rosbridge.

    The device resource reads no topic, so the receipt is where a caller sees
    what was sent. The fields are the transmitted request, not a measurement.
    Every other call, including the e-stop and the reset, goes to the SDK
    bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id != _SETPOINT_ID:
            return output
        output = dict(output)
        values = dict(args or {})
        for key in ("x", "y", "z"):
            output["sent_" + key] = float(values[key])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


class XtdroneTyphoon(RosDriver):
    device_id = "xtdrone_typhoon_h480_0"
    # The existing card's vehicle resource. The R2 below is the MAVROS setpoint
    # (REVIEW.md item 12), which a real PX4 can consume (README.en.md:7).
    device_kind = "robot.mobile_base"
    resource_id = "vehicle"
    resource_title = "XTDrone typhoon_h480_0 simulated multirotor"
    mode = "simulated"
    # R2: the setpoint is a MAVROS topic a physical PX4 also consumes (README.en.md:7,
    # REVIEW.md item 12). The world pause itself is a simulator service.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeXtdrone"}
    tags = ["ros", "ros1", "simulation", "xtdrone", "px4", "mavros", "typhoon", "position", "gazebo"]
    display_name = "XTDrone typhoon_h480_0 position bridge"
    vendor = "XTDrone"
    model = "typhoon_h480 SITL"
    facts = [
        Fact("XTDrone is a UAV simulation platform based on PX4, ROS and Gazebo, and its README says algorithms "
             "can be deployed to real UAVs after simulation testing.",
             source="vendor_doc", ref="README.en.md:7"),
        Fact("The multi-vehicle launch places typhoon_h480_0 in the typhoon_h480_0 namespace and includes MAVROS "
             "inside that group.", source="upstream_code", ref=_LAUNCH + ":21-49"),
        Fact("The generated topic list records /typhoon_h480_0/mavros/local_position/pose.",
             source="vendor_doc", ref="contributer_demo/demo1/doc/rostopic list:84"),
        Fact("The generated topic list records /typhoon_h480_0/mavros/setpoint_position/local.",
             source="vendor_doc", ref="contributer_demo/demo1/doc/rostopic list:117"),
        Fact("The generated topic list records /typhoon_h480_0/mavros/setpoint_raw/target_local.",
             source="vendor_doc", ref="contributer_demo/demo1/doc/rostopic list:123"),
        Fact("The ground-control script publishes PoseStamped targets on the vehicle's relative "
             "setpoint_position/local topic.", source="upstream_code",
             ref="contributer_demo/demo1/src/formation/script/formation_gcs.py:74"),
        Fact("The iris_0 MAVROS config sets setpoint_position tf frame_id to map and mav_frame to LOCAL_NED.",
             source="upstream_code", ref="sitl_config/launch/px4/px4_config_iris_0.yaml:108-113"),
        Fact("The communication node publishes a MAVROS PositionTarget on the relative setpoint_raw/local topic.",
             source="upstream_code", ref=_COMM + ":45"),
        Fact("The communication node's start method republishes the last target in a loop until ROS shutdown.",
             source="upstream_code", ref=_COMM + ":55-61"),
        Fact("The module creates a 30 Hz ROS rate object.", source="upstream_code", ref=_COMM + ":10"),
        Fact("The cmd handler ignores the exact string 'stop controlling' and the empty string, as well as a "
             "repeat of the last command.", source="upstream_code", ref=_COMM + ":149-151"),
        Fact("The hover transition treats speeds within 0.02 and a yaw rate within 0.005 as a hover request and "
             "constructs a target from the cached current position and yaw.",
             source="upstream_code", ref=_COMM + ":141-148"),
        Fact("The hover method constructs its target from the cached current position and yaw.",
             source="upstream_code", ref=_COMM + ":194-198"),
        Fact("The target constructor signature names the acceleration components afx, afy and afz.",
             source="upstream_code", ref=_COMM + ":67"),
        Fact("The acceleration callbacks call the target constructor with ax, ay and az keywords, which the "
             "signature does not accept.", source="upstream_code", ref=_COMM + ":127-139"),
        Fact("The node's arm and disarm helpers test the whole CommandBool service response object rather than "
             "its success field.", source="upstream_code", ref=_COMM + ":180-192"),
        Fact("The flight mode helper tests the whole SetMode service response object rather than its mode_sent "
             "field.", source="upstream_code", ref=_COMM + ":200-209"),
        Fact("The multirotor communication node builds a CommandBool service proxy from vehicle_type, vehicle_id "
             "and the suffix /mavros/cmd/arming.", source="upstream_code", ref=_COMM + ":50"),
        Fact("The multirotor communication node builds a SetMode service proxy from vehicle_type, vehicle_id and "
             "the suffix /mavros/set_mode.", source="upstream_code", ref=_COMM + ":51"),
        Fact("The plane communication node builds a CommandBool service proxy from vehicle_type, vehicle_id "
             "and the suffix /mavros/cmd/arming, and a SetMode service proxy from vehicle_type, vehicle_id "
             "and the suffix /mavros/set_mode.",
             source="upstream_code", ref="communication/plane_communication.py:40-41"),
        Fact("The vendored gazebo_ros package.xml declares version 2.8.7.", source="upstream_code",
             ref=_GAZEBO + "/gazebo_ros/package.xml:4"),
        Fact("The vendored gazebo_ros package.xml declares a catkin buildtool dependency.", source="upstream_code",
             ref=_GAZEBO + "/gazebo_ros/package.xml:22"),
        Fact("The vendored gazebo_ros changelog header is 2.8.7 (2020-05-01).", source="upstream_code",
             ref=_GAZEBO + "/gazebo_ros/CHANGELOG.rst:5"),
        Fact("The vendored gazebo_ros_pkgs README links its sensors document on the melodic-devel branch.",
             source="vendor_doc", ref=_GAZEBO + "/README.md:11"),
        Fact("The vendored RELEASE.md lists ROS Melodic with Gazebo 9.", source="vendor_doc",
             ref=_GAZEBO + "/docs/RELEASE.md:19"),
        Fact("The API plugin member enable_ros_network_ is initialized true.", source="upstream_code",
             ref=_API + ":41"),
        Fact("The API plugin creates its node handle with ros::NodeHandle(\"~\").", source="upstream_code",
             ref=_API + ":148"),
        Fact("gazeboQueueThread calls gazebo_queue_.callAvailable with a 0.001 s wall duration while nh_->ok().",
             source="upstream_code", ref=_API + ":263-269"),
        Fact("advertiseServices returns without advertising when enable_ros_network_ is false.",
             source="upstream_code", ref=_API + ":274-277"),
        Fact("The API plugin connects wrenchBodySchedulerSlot, forceJointSchedulerSlot and publishSimTime to "
             "WorldUpdateBegin.", source="upstream_code", ref=_API + ":225-228"),
        Fact("The API plugin advertises the service get_physics_properties with type gazebo_msgs::GetPhysicsProperties.",
             source="upstream_code", ref=_API + ":389-395"),
        Fact("The API plugin advertises the service pause_physics with type std_srvs::Empty.",
             source="upstream_code", ref=_API + ":508-514"),
        Fact("The API plugin advertises the service unpause_physics with type std_srvs::Empty.",
             source="upstream_code", ref=_API + ":517-523"),
        Fact("getPhysicsProperties sets res.pause to world_->IsPaused().", source="upstream_code",
             ref=_API + ":1484"),
        Fact("When the physics engine type is not ode, getPhysicsProperties sets success false and returns false.",
             source="upstream_code", ref=_API + ":1516-1523"),
        Fact("pausePhysics calls world_->SetPaused(true) and returns true.", source="upstream_code",
             ref=_API + ":1738-1742"),
        Fact("unpausePhysics calls world_->SetPaused(false) and returns true.", source="upstream_code",
             ref=_API + ":1744-1748"),
        Fact("The gazebo network API test lists /gazebo/get_physics_properties with type gazebo_msgs/GetPhysicsProperties.",
             source="upstream_code", ref=_YAML + ":55-56"),
        Fact("The gazebo network API test lists /gazebo/pause_physics with type std_srvs/Empty.",
             source="upstream_code", ref=_YAML + ":85-86"),
        Fact("The GetPhysicsProperties response field pause is commented true if the physics engine is paused.",
             source="upstream_code", ref=_SRV + ":4"),
        Fact("empty_world.launch defaults its gui argument to true.", source="upstream_code", ref=_EMPTY + ":8"),
        Fact("empty_world.launch defaults its physics argument to ode.", source="upstream_code", ref=_EMPTY + ":15"),
        Fact("empty_world.launch defaults use_sim_time to true.", source="upstream_code", ref=_EMPTY + ":6"),
        Fact("empty_world.launch defaults enable_ros_network to true.", source="upstream_code", ref=_EMPTY + ":22"),
        Fact("empty_world.launch sets the parameter /use_sim_time to $(arg use_sim_time).", source="upstream_code",
             ref=_EMPTY + ":27"),
        Fact("empty_world.launch sets script_type to gzserver unless debug is true, in which case script_type is debug.",
             source="upstream_code", ref=_EMPTY + ":36-37"),
        Fact("empty_world.launch starts a node named gazebo from package gazebo_ros.", source="upstream_code",
             ref=_EMPTY + ":46-48"),
        Fact("When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient.",
             source="upstream_code", ref=_EMPTY + ":51-54"),
        Fact("multi_vehicle.launch defaults its world to $(find mavlink_sitl_gazebo)/worlds/empty.world.",
             source="upstream_code", ref=_LAUNCH + ":7"),
        Fact("multi_vehicle.launch defaults gui to true, debug to true and paused to false.",
             source="upstream_code", ref=_LAUNCH + ":9-12"),
        Fact("multi_vehicle.launch includes gazebo_ros empty_world.launch and passes gui, world_name, debug, "
             "verbose and paused.", source="upstream_code", ref=_LAUNCH + ":14-20"),
        Fact("multi_vehicle.launch includes $(find px4)/launch/single_vehicle_spawn_xtd.launch with vehicle "
             "typhoon_h480 inside the typhoon_h480_0 group.", source="upstream_code", ref=_LAUNCH + ":28-35"),
        Fact("multi_vehicle.launch opens a group whose namespace is typhoon_h480_1.", source="upstream_code",
             ref=_LAUNCH + ":51-52"),
        Fact("The typhoon_h480 mavlink_interface plugin sets enable_lockstep to true.", source="upstream_code",
             ref="sitl_config/models/typhoon_h480/typhoon_h480.sdf:1270-1288"),
    ]
    safe_state = (
        "Gazebo is paused and get_physics_properties read pause true. That flag covers every vehicle in the world. "
        "It is not a measured standstill or a disarm. No unpause is offered, because the communication node keeps "
        "republishing its retained target and ignores 'stop controlling'; the operator recovers outside MHS."
    )
    fidelity = {
        "engine": "analytic:ROS-free transport model (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Canned target and pose samples plus a recorded setpoint publish and a paused flag; "
                     "no physics step, PX4 process or wall-clock pacing",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic ROS-free transport: it answers the declared topics and the two Gazebo "
            "services and runs no XTDrone node, PX4 SITL, Gazebo, MAVROS or physics",
            "the pose sample is a placeholder and does not move, so the fake does not model arrival; the zero "
            "header stamp is a wire placeholder",
            "the fake does not model the communication node's 30 Hz loop, hover transition or PositionTarget "
            "publication; the acceleration callbacks pass ax/ay/az into a constructor that accepts afx/afy/afz "
            "and stay unsupported",
            "the position inputs are operator_required; site-limits.example.json is example test data only",
            "the stop is the vendored gazebo_ros pause flag: /gazebo/pause_physics sets it and "
            "/gazebo/get_physics_properties reports it; the fake runs no Gazebo World::Step, and the effect of "
            "SetPaused on the step loop is Gazebo's and is not in this clone",
            "no unpause is offered (SAFE-042): multirotor_communication.py:55-61 republishes target_motion until "
            "shutdown and :149-151 ignores 'stop controlling', and this package cannot clear that retained target; "
            "PX4 offboard setpoint retention is not traced in this clone because the PX4 launch is $(find px4)",
            "the Gazebo GUI (empty_world.launch starts gzclient when gui is true, and multi_vehicle.launch "
            "defaults gui to true) or any client of unpause_physics can unpause the world, and MHS does not watch "
            "the flag after the e-stop; safety_status returns the cached confirmation from the last successful "
            "read-back and does not call get_physics_properties again, so it cannot detect that unpause",
            "a non-ODE engine makes get_physics_properties return false, so the e-stop stays unconfirmed with the "
            "latch held; ODE is empty_world.launch's default physics argument, which multi_vehicle.launch does "
            "not override; the default world file $(find mavlink_sitl_gazebo)/worlds/empty.world is not in this clone",
            "the vendored gazebo_ros is 2.8.7 (changelog header 2020-05-01), catkin, with README links on "
            "melodic-devel and RELEASE.md listing ROS Melodic with Gazebo 9; this package claims no Noetic build, "
            "and rosbridge cannot read the running version",
            "pause_physics pauses the whole world, including typhoon_h480_1 (multi_vehicle.launch:51), which this "
            "package does not command; only typhoon_h480_0 is on the accepted surface",
            "the communication node publishes PositionTarget on setpoint_raw/local and formation_gcs publishes "
            "PoseStamped on setpoint_position/local, so either can overwrite a publication from this package",
            "arming and OFFBOARD stay outside MHS; the CommandBool and SetMode proxies at "
            "multirotor_communication.py:50-51 and plane_communication.py:40-41 are citable and are not bound",
            "typhoon_h480.sdf sets enable_lockstep true; the fake treats pose and target as silent while paused, "
            "which is an assumption of that flag and not a measured PX4 trace",
            "pose and target are explicit reads and are not on the device resource, so a command or a reset does "
            "not wait for them; the setpoint receipt reports sent_x, sent_y and sent_z, which are the values "
            "handed to rosbridge and not a measurement",
            "the full flight workflow (velocity, acceleration, arm, mode, land and state) is outside this package",
            "the map frame_id on the published PoseStamped follows the iris_0 MAVROS config in this clone; "
            "multi_vehicle.launch includes $(find mavros)/launch/px4.launch, which is not in this clone, so that "
            "iris file is not shown to be what the typhoon MAVROS launch loads",
            "if enable_ros_network is false, advertiseServices returns without advertising and the e-stop fails "
            "closed; the plugin member and empty_world.launch both default it to true",
            "multi_vehicle.launch defaults debug to true, and empty_world.launch then selects node type debug "
            "rather than gzserver",
            "the vehicle spawn include is $(find px4)/launch/single_vehicle_spawn_xtd.launch, which is not in "
            "this clone",
        ],
    }
    # Pose and target stay explicit reads. A paused lockstep world may publish
    # nothing, and a resource that waited on those topics would fail after reset.
    commands = {
        "x-cap.robin-shaun.target.v1": dict(
            _TARGET,
            operation="subscribe",
            path="$",
            result={"map": {"target_x": "position.x", "target_y": "position.y", "target_z": "position.z"}},
        ),
        "x-cap.robin-shaun.position.v1": dict(
            _POSE,
            operation="subscribe",
            path="$",
            result={"map": {"position_x": "pose.position.x", "position_y": "pose.position.y",
                            "position_z": "pose.position.z"}},
        ),
        _SETPOINT_ID: _SETPOINT,
    }
    actions = {
        "x-cap.robin-shaun.target.v1": Action(
            name="read_target",
            verb="read",
            description="Read the MAVROS local target setpoint, not vehicle arrival",
            output=_TARGET_FIELDS,
        ),
        "x-cap.robin-shaun.position.v1": Action(
            name="read_position",
            verb="read",
            description="Read the current MAVROS local position sample",
            output=_POSE_FIELDS,
        ),
        _SETPOINT_ID: Action(
            name="publish_position_setpoint",
            risk="R2",
            description="Publish one map-frame local position setpoint to MAVROS; the receipt reports the values "
                        "handed to rosbridge and is transmission only, not arrival or a stop",
            input={
                "x": Field("number", unit="m",
                           description="Forward local target in the map frame",
                           limit=Limit.operator_required(_POSITION_REASON)),
                "y": Field("number", unit="m",
                           description="Left local target in the map frame",
                           limit=Limit.operator_required(_POSITION_REASON)),
                "z": Field("number", unit="m",
                           description="Up local target in the map frame",
                           limit=Limit.operator_required(_POSITION_REASON)),
            },
            output={
                "published": Field("boolean",
                                   description="True when rosbridge transmitted the PoseStamped message"),
                "confirmed": Field("boolean",
                                   description="False: a publication is transmission only, not arrival"),
                "sent_x": Field("number", unit="m",
                                description="The x handed to rosbridge (the transmitted request, not a measurement)"),
                "sent_y": Field("number", unit="m",
                                description="The y handed to rosbridge (the transmitted request, not a measurement)"),
                "sent_z": Field("number", unit="m",
                                description="The z handed to rosbridge (the transmitted request, not a measurement)"),
            },
        ),
    }
    # Pause, then read pause back. No reset binding and no re-enable: reset
    # releases the latch and leaves the world paused (SAFE-042).
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _SentReceipt(super().make_bridge(native))
