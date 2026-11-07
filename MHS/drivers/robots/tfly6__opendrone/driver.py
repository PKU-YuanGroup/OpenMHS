"""OpenMHS rosbridge driver for the tfly6/opendrone PX4 SITL base controller.

The pinned repository is a ROS 1 PX4/Gazebo SITL environment.  This package is
a configuration-only :class:`RosDriver` over rosbridge; it declares no Python
native class and neither imports nor starts the upstream code.  The operator
runs ``sitl_base_controller.launch`` (and the rest of the PX4 SITL stack) and a
rosbridge endpoint separately.

Scope: the ``opendrone`` ``base`` node's position-target input and its
published state.  ``/planner/output`` (``opendrone/PlannerOutput``) is the
node's mission input; the node latches the first point whose ``valid_mask``
has ``VALID_POSITION`` and republishes that target as
``geometry_msgs/PoseStamped`` on ``/mavros/setpoint_position/local`` at its
configured timer rate.  Resource snapshots read the MAVROS state and local
pose and the node's ``/flight_state`` output; the setpoint topic is an
explicit observation because the node stops publishing it in
LANDING/LANDED.  The only upstream landing path is the ``/land``
``std_srvs/SetBool`` service, whose callback stores a landing lock and the
LANDING state and returns success at once; the control loop then asks MAVROS
for ``AUTO.LAND`` and treats ``mode_sent`` as LANDED without sensing the mode
change, touchdown or disarm.  That callback acknowledgement alone is not a
stop.  This simulated package therefore declares a sensed-confirmation stop
(SAFE-049, the user's decision of 2026-11-05, simulated devices only): the
e-stop sends ``/land`` and a ``/mavros/cmd/arming`` disarm request, and it is
achieved only when ``/mavros/state`` reports connected and disarmed and the
local pose is low and at rest in three consecutive fresh samples within the
bound; otherwise it fails ``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the latch
held and is retried in the background.  ``/land`` also stays an ordinary
command.  MAVROS can drive a real PX4 with another ``fcu_url``: that path is
out of scope and never served.

Every endpoint, type and fact cites the pinned clone at
3cf7779c7c8abe0cec01b7f24673ad9d4e455e4d.  The fake transport is ROS-free and
all of its state values are placeholders.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# Pinned source references.
_STATE = "opendrone/src/base.cpp:19-20"                 # /mavros/state, mavros_msgs/State
_POSE = "opendrone/src/base.cpp:21-22"                  # /mavros/local_position/pose
_PLANNER = "opendrone/src/base.cpp:23-24"               # /planner/output, opendrone/PlannerOutput
_SETPOINT = "opendrone/src/base.cpp:26-27"              # /mavros/setpoint_position/local
_FLIGHT_STATE = "opendrone/src/base.cpp:28"             # /flight_state, std_msgs/Int8
_LAND_ENDPOINT = "opendrone/src/base.cpp:32"            # advertiseService("/land", ...)
_LAND_TYPE = "opendrone/src/base.cpp:12"                # #include <std_srvs/SetBool.h>
_PLANNER_CALLBACK = "opendrone/src/base.cpp:291-315"    # first VALID_POSITION point, then yaw
_LAND_CALLBACK = "opendrone/src/base.cpp:277-289"       # response is queued before AUTO.LAND runs
_LAND_LOOP = "opendrone/src/base.cpp:162-164"           # LANDING calls requestAutoLand
_LAND_REQUEST = "opendrone/src/base.cpp:259-275"        # /mavros/set_mode AUTO.LAND
_STATE_MACHINE = "opendrone/src/base.cpp:133-160"       # OFFBOARD/arming, takeoff and mission
_TARGET_PUBLISH = "opendrone/src/base.cpp:179-183"      # publishTargetPose
_FENCE = "opendrone/src/base.cpp:341-348"               # out-of-fence -> EMERGENCY
_FLIGHT_VALUES = "opendrone/src/base.cpp:73-81"         # FlightState enum values 0..6
_ARMING_CLIENT = "opendrone/src/base.cpp:30"            # /mavros/cmd/arming client
_ARMING_TYPE = "opendrone/src/base.cpp:5"               # #include <mavros_msgs/CommandBool.h>
_STATE_TYPE = "opendrone/src/base.cpp:7"                # #include <mavros_msgs/State.h>
_POSE_TYPE = "opendrone/src/base.cpp:4"                 # #include <geometry_msgs/PoseStamped.h>
_CONNECTED_READ = "opendrone/src/base.cpp:127"          # current_state_.connected (consumer)
_ARMED_READ = "opendrone/src/base.cpp:167"              # !current_state_.armed in LANDED (consumer)
_POSITION_READ = "opendrone/src/base.cpp:341-343"       # current_pose_.pose.position x, y, z (consumer)
_OFFBOARD_LOCK = "opendrone/src/base.cpp:209-213"       # trySetOffboard returns while landing_locked_
_ARM_LOCK = "opendrone/src/base.cpp:234-238"            # tryArm returns while landing_locked_
_FCU_URL = "opendrone/sitl_config/px4.launch:5"         # fcu_url default /dev/ttyACM0:57600

#: ``PlannerOutputPoint``: ``valid_mask`` bit 1 is position, bit 32 is yaw.
_VALID_POSITION = "opendrone/msg/PlannerOutputPoint.msg:3-9"
#: ``PlannerOutput``: header, trajectory fields and the point array.
_PLANNER_MESSAGE = "opendrone/msg/PlannerOutput.msg:1-7"

_POSITION = Field(
    "object",
    description="position field of a PlannerOutputPoint, in metres",
    properties={
        "x": Field("number", unit="m", description="Position x in the message frame"),
        "y": Field("number", unit="m", description="Position y in the message frame"),
        "z": Field("number", unit="m", description="Position z in the message frame"),
    },
)

_SETPOINT_POSITION = Field(
    "object",
    description="position field of geometry_msgs/PoseStamped, in metres",
    properties={
        "x": Field("number", unit="m", description="Setpoint position x"),
        "y": Field("number", unit="m", description="Setpoint position y"),
        "z": Field("number", unit="m", description="Setpoint position z"),
    },
)

_POINT = Field(
    "object",
    description="One opendrone/PlannerOutputPoint; the base node selects the first point with the "
                "VALID_POSITION bit set and ignores later points",
    properties={
        "position": _POSITION,
        "yaw": Field("number", unit="rad",
                     description="Yaw applied only when valid_mask also has VALID_YAW (32)"),
        "valid_mask": Field("integer", unit="1", enum=[1, 33],
                            description="Bitmask count: 1 = VALID_POSITION; 33 = VALID_POSITION | VALID_YAW"),
    },
)

_PUBLISHED = {
    "published": Field("boolean", description="True when rosbridge accepted the publication"),
    "confirmed": Field("boolean",
                       description="Always false: a ROS topic publication has no execution acknowledgement"),
}

_LAND_OUTPUT = {
    "success": Field("boolean", description="The upstream std_srvs/SetBool response success flag"),
    "message": Field("string", description="The upstream std_srvs/SetBool response message text"),
}

#: Fixed, input-free landing request, an ordinary command.  The callback sets
#: landing_locked_ and LANDING and returns success without calling MAVROS
#: (base.cpp:277-289); the control loop later requests AUTO.LAND and enters
#: LANDED on mode_sent alone (base.cpp:162-164, 259-275).  A callback
#: acknowledgement of a LAND mode request does not certify a stop, so this is
#: neither the e-stop binding nor a safe-state action.
_LAND = {
    "service": "/land",
    "type": "std_srvs/SetBool",
    "source_ref": _LAND_ENDPOINT,
    "type_ref": _LAND_TYPE,
    "request": {"data": True},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"success": "success", "message": "message"}},
    "description": "Fixed std_srvs/SetBool(true) request to the base node's /land service; the "
                   "response acknowledges the landing request, not touchdown or disarm",
}

#: PlannerOutput has exactly header, trajectory_id, is_horizon,
#: trajectory_start_time and points (PlannerOutput.msg:1-7); time_from_start
#: is a PlannerOutputPoint field (PlannerOutputPoint.msg:1), so it is not set
#: here (a rosbridge publish with a field the type lacks is refused).
_TARGET_MESSAGE = {
    "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": "map"},
    "trajectory_id": 0,
    "is_horizon": False,
    "trajectory_start_time": {"secs": 0, "nsecs": 0},
    "points": [],
}

_SETPOINT_OBSERVATION = {
    "topic": "/mavros/setpoint_position/local",
    "type": "geometry_msgs/PoseStamped",
    "source_ref": _SETPOINT,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"position": "output.pose.position"}},
}

_TARGET = {
    "topic": "/planner/output",
    "type": "opendrone/PlannerOutput",
    "source_ref": _PLANNER,
    "operation": "publish",
    "message": _TARGET_MESSAGE,
    "args": {"points": {"from": "input.points"}},
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
}


#: Sensed-confirmation stop (SAFE-049): the request steps prove nothing by themselves.  /land stores the
#: landing lock and LANDING (base.cpp:277-289); the lock stops the node's own OFFBOARD and arming requests
#: (base.cpp:209-213, 234-238).  The disarm request is refused by PX4 in the air and repeats harmlessly after
#: touchdown; the background retry sends both again.  The confirmation reads MAVROS's state and local pose
#: (stamped, filled by MAVROS outside the clone; base.cpp consumes the fields cited in fill_refs).  /flight_state
#: is never a source: the node reports LANDED on mode_sent alone (base.cpp:269-271).  Every threshold is
#: operator_required: the clone states no landed band and no at-rest bound (the fence's z < -0.2 at base.cpp:345 is
#: not one).  The client bounds are fake-scale; a live deployment sets them in its estop_confirmation.
_NO_LANDED_BOUND = ("the clone states no landed altitude band: the geo-fence lower bound z < -0.2 (base.cpp:345) "
                    "is a fence, and touchdown is sensed by PX4 outside the clone; the operator supplies the band")
_NO_REST_BOUND = ("the clone states no at-rest position bound; the operator supplies the largest position change "
                  "over the confirmation window that counts as at rest")

_SENSED_STOP = {
    "request": [
        {"service": "/land", "type": "std_srvs/SetBool", "source_ref": _LAND_ENDPOINT, "type_ref": _LAND_TYPE,
         "request": {"data": True}, "success": {"path": "success", "equals": True}, "timeout_ms": 1000,
         "description": "the base node's landing request (stores the landing lock and LANDING)"},
        {"service": "/mavros/cmd/arming", "type": "mavros_msgs/CommandBool", "source_ref": _ARMING_CLIENT,
         "type_ref": _ARMING_TYPE, "request": {"value": False}, "success": {"path": "success", "equals": True},
         "timeout_ms": 1000, "description": "a disarm request (refused in the air; succeeds after touchdown)"},
    ],
    "sources": {
        "state": {"topic": "/mavros/state", "type": "mavros_msgs/State", "source_ref": _STATE,
                  "type_ref": _STATE_TYPE, "fill_refs": {"connected": _CONNECTED_READ, "armed": _ARMED_READ}},
        "pose": {"topic": "/mavros/local_position/pose", "type": "geometry_msgs/PoseStamped", "source_ref": _POSE,
                 "type_ref": _POSE_TYPE, "fill_refs": {"pose.position": _POSITION_READ}},
    },
    "predicate": [
        {"source": "state", "path": "connected", "equals": True},
        {"source": "state", "path": "armed", "equals": False},
        {"source": "pose", "path": "pose.position.z", "name": "landed_z", "unit": "m",
         "range": {"max": Limit.operator_required(_NO_LANDED_BOUND)}},
        {"source": "pose", "path": "pose.position.x", "name": "rest_x", "unit": "m",
         "span_max": Limit.operator_required(_NO_REST_BOUND)},
        {"source": "pose", "path": "pose.position.y", "name": "rest_y", "unit": "m",
         "span_max": Limit.operator_required(_NO_REST_BOUND)},
        {"source": "pose", "path": "pose.position.z", "name": "rest_z", "unit": "m",
         "span_max": Limit.operator_required(_NO_REST_BOUND)},
    ],
    "consecutive": 3,
    "min_span_ms": 200,
    "max_gap_ms": 500,
    "confirm_within_ms": 1500,
    "description": "landing requested and locked in the base node; connected and disarmed on /mavros/state and the "
                   "local pose low and at rest, sensed in three consecutive fresh samples within the bound",
}


class Opendrone(RosDriver):
    device_id = "opendrone"
    device_kind = "world.sim"
    mode = "simulated"
    #: A UAV position controller commands a flying vehicle, so this simulated
    #: device carries at least the R2 motion floor even though no hardware is
    #: attached.  The driver has no hardware backend.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeOpendrone"}
    tags = ["ros", "ros1", "px4", "sitl", "uav", "position-controller", "simulation"]
    display_name = "OpenDrone PX4 SITL base position controller"
    vendor = "tfly6"
    model = "opendrone base position controller"
    facts = [
        Fact("BasePositionController subscribes /mavros/state as mavros_msgs/State and "
             "/mavros/local_position/pose as geometry_msgs/PoseStamped.",
             source="upstream_code", ref="opendrone/src/base.cpp:19-22"),
        Fact("BasePositionController subscribes /planner/output as opendrone/PlannerOutput.",
             source="upstream_code", ref=_PLANNER),
        Fact("BasePositionController advertises geometry_msgs/PoseStamped on "
             "/mavros/setpoint_position/local and std_msgs/Int8 on /flight_state.",
             source="upstream_code", ref="opendrone/src/base.cpp:26-28"),
        Fact("BasePositionController advertises the std_srvs/SetBool service /land.",
             source="upstream_code", ref=_LAND_ENDPOINT),
        Fact("The land callback takes std_srvs/SetBool requests and responses.",
             source="upstream_code", ref="opendrone/src/base.cpp:277-289"),
        Fact("plannerOutputCallback ignores an empty points array, selects the first point whose "
             "valid_mask has VALID_POSITION, applies its position and, when VALID_YAW is set, its "
             "yaw; later points are ignored.",
             source="upstream_code", ref=_PLANNER_CALLBACK),
        Fact("PlannerOutputPoint defines VALID_POSITION as 1 and VALID_YAW as 32.",
             source="upstream_code", ref=_VALID_POSITION),
        Fact("PlannerOutput declares a Header, trajectory_id, is_horizon, trajectory_start_time and a "
             "PlannerOutputPoint points array.",
             source="upstream_code", ref=_PLANNER_MESSAGE),
        Fact("The land callback, when request.data is true, sets landing_locked_ and "
             "flight_state_ to LANDING and returns success true with the message "
             "'base position baseline landing requested' without calling MAVROS; for false it "
             "returns success false.",
             source="upstream_code", ref=_LAND_CALLBACK),
        Fact("The LANDING state calls requestAutoLand.",
             source="upstream_code", ref=_LAND_LOOP),
        Fact("requestAutoLand sets landing_locked_, enters LANDED at once when the reported mode is "
             "already AUTO.LAND, and otherwise calls /mavros/set_mode with custom_mode AUTO.LAND and "
             "enters LANDED when the call succeeds and reports mode_sent.",
             source="upstream_code", ref=_LAND_REQUEST),
        Fact("The LANDED branch of the control loop only logs once the vehicle reports disarmed.",
             source="upstream_code", ref="opendrone/src/base.cpp:166-170"),
        Fact("In WAITING_FOR_OFFBOARD the control loop publishes the target pose, calls trySetOffboard "
             "and tryArm, and moves to TAKEOFF (or MISSION_EXECUTION without auto_takeoff) once the "
             "vehicle reports OFFBOARD and armed; TAKEOFF and MISSION_EXECUTION keep publishing the "
             "target pose.",
             source="upstream_code", ref=_STATE_MACHINE),
        Fact("The control loop calls publishTargetPose only in WAITING_FOR_OFFBOARD, TAKEOFF and "
             "MISSION_EXECUTION; LANDING calls requestAutoLand, LANDED only logs a disarm and "
             "EMERGENCY switches to LANDING.",
             source="upstream_code", ref="opendrone/src/base.cpp:124-176"),
        Fact("publishTargetPose stamps and publishes target_pose_ to "
             "/mavros/setpoint_position/local.",
             source="upstream_code", ref=_TARGET_PUBLISH),
        Fact("The base node reads geo_fence/x, geo_fence/y and geo_fence/z as private parameters "
             "with defaults 10.0, 10.0 and 7.0.",
             source="upstream_code", ref="opendrone/src/base.cpp:43-45"),
        Fact("sitl_base_controller.launch defaults enable_sim, enable_auto_offboard, enable_auto_arm "
             "and auto_takeoff to true and sets geo_fence/x, geo_fence/y and geo_fence/z to 50.0, "
             "50.0 and 7.0.",
             source="upstream_code", ref="opendrone/launch/sitl_base_controller.launch:2-24"),
        Fact("poseCallback switches flight_state_ to EMERGENCY, unless it is LANDING or LANDED, when "
             "|x| exceeds geo_fence_x_, |y| exceeds geo_fence_y_, z exceeds geo_fence_z_ or z is "
             "below -0.2.",
             source="upstream_code", ref=_FENCE),
        Fact("The FlightState enum numbers WAITING_FOR_CONNECTED 0, WAITING_FOR_OFFBOARD 1, "
             "TAKEOFF 2, MISSION_EXECUTION 3, LANDING 4, LANDED 5 and EMERGENCY 6.",
             source="upstream_code", ref=_FLIGHT_VALUES),
        Fact("The base node creates a mavros_msgs/CommandBool client on /mavros/cmd/arming and a "
             "mavros_msgs/SetMode client on /mavros/set_mode.",
             source="upstream_code", ref="opendrone/src/base.cpp:30-31"),
        Fact("trySetOffboard returns without a mode request while landing_locked_ is set or auto-offboard is "
             "disabled.", source="upstream_code", ref=_OFFBOARD_LOCK),
        Fact("tryArm returns without an arming request while landing_locked_ is set or auto-arm is disabled.",
             source="upstream_code", ref=_ARM_LOCK),
        Fact("In WAITING_FOR_CONNECTED the control loop waits for current_state_.connected.",
             source="upstream_code", ref="opendrone/src/base.cpp:125-131"),
        Fact("poseCallback stores the pose and reads current_pose_.pose.position x, y and z for the fence check.",
             source="upstream_code", ref="opendrone/src/base.cpp:332-343"),
        Fact("sitl_config/px4.launch declares the fcu_url argument with the default /dev/ttyACM0:57600.",
             source="upstream_code", ref=_FCU_URL),
    ]
    safe_state = (
        "Simulated only: landing requested and locked in the base node, and the vehicle sensed landed, at rest "
        "and disarmed: /mavros/state connected and not armed, and /mavros/local_position/pose below the "
        "operator's landed band and still, in three consecutive fresh stamped samples within the confirmation "
        "bound. The /land response alone proves nothing; nothing is claimed beyond the confirmation window."
    )
    #: The request steps' timeouts (1000 + 1000 ms) plus confirm_within_ms (1500 ms): the e-stop's budget.
    estop_latency_ms = 3500
    fidelity = {
        "engine": "analytic:ROS-free protocol fake for the opendrone base node (no PX4 or Gazebo "
                  "physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies with no physics step or wall-clock pacing; "
                     "placeholder state does not establish trajectory replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an SDK ros_transport handler (RecordingRosTransport) with no ROS graph: "
            "it answers the declared subscriptions and the /land service and records the "
            "/planner/output publication, but it runs no PX4 SITL, Gazebo, MAVROS, controller loop "
            "or wall-clock timer",
            "the state, pose, flight-state and target samples are placeholders; a live run must "
            "receive the clone's own topics and a working MAVROS/PX4 graph",
            "the fake snaps its placeholder local pose to the published target so the resource "
            "changes; it integrates no motion and the receipt makes no arrival claim",
            "/mavros/setpoint_position/local is an explicit observation, not a resource field: the "
            "base node stops publishing it in LANDING/LANDED, so that observation may time out",
            "the /planner/output publication is transmission-only: the fake cannot prove that the "
            "base node received it, selected a point or changed its latched target",
            "the /land response acknowledges only that the callback stored the landing request; the fake "
            "models the landing as a placeholder descent of 0.5 m per sample and a disarm at touchdown (PX4's "
            "land detector and auto-disarm are configured outside this clone), not PX4 or Gazebo",
            "the e-stop is a sensed-confirmation stop (SAFE-049, simulated only): it sends /land and a "
            "/mavros/cmd/arming disarm request and is achieved only on three consecutive fresh samples of "
            "/mavros/state (connected, not armed) and /mavros/local_position/pose (below the landed band and at "
            "rest) within the bound; the thresholds are operator_required (fake placeholders in "
            "fixtures/estop-confirmation.json) and the client bounds are fake-scale, so a live deployment sets "
            "both in simulation_deployment['estop_confirmation']",
            "without PX4 auto-disarm the first e-stop stays unconfirmed (the disarm request is refused in the "
            "air) and the background retry's disarm after touchdown confirms it; another MAVROS client or the "
            "shipped offboard nodes can re-arm the vehicle after the stop, which a reset's re-confirmation "
            "refuses but nothing prevents",
            "MAVROS reaches a real PX4 with another fcu_url (sitl_config/px4.launch defaults to a serial "
            "device): this package is a simulated device only and that path is out of scope",
            "the driver does not enforce the node's configurable geo_fence and declares no "
            "workspace bound; an operator must configure and verify the fence",
            "trajectory following, velocity/acceleration/yaw-rate fields, the remaining controllers "
            "and planners, the camera/LiDAR streams, ROS parameters, QoS, namespaces and "
            "remapping are NOT COVERED",
        ],
    }
    parameters = {
        "flight_state": Field("integer", unit="1",
                              description="Last std_msgs/Int8 data from /flight_state (0..6)"),
        "armed": Field("boolean", description="Last mavros_msgs/State.armed observed on /mavros/state"),
        "mode": Field("string", description="Last mavros_msgs/State.mode observed on /mavros/state"),
        "connected": Field("boolean",
                           description="Last mavros_msgs/State.connected observed on /mavros/state"),
        "position": Field("object", description="Last local position from /mavros/local_position/pose",
                          properties={
                              "x": Field("number", unit="m", description="Local position x"),
                              "y": Field("number", unit="m", description="Local position y"),
                              "z": Field("number", unit="m", description="Local position z"),
                          }),
    }
    reads = {
        "flight_state": {
            "topic": "/flight_state",
            "type": "std_msgs/Int8",
            "source_ref": _FLIGHT_STATE,
            "path": "data",
            "timeout_ms": 2000,
        },
        "armed": {
            "topic": "/mavros/state",
            "type": "mavros_msgs/State",
            "source_ref": _STATE,
            "path": "armed",
            "timeout_ms": 2000,
        },
        "mode": {
            "topic": "/mavros/state",
            "type": "mavros_msgs/State",
            "source_ref": _STATE,
            "path": "mode",
            "timeout_ms": 2000,
        },
        "connected": {
            "topic": "/mavros/state",
            "type": "mavros_msgs/State",
            "source_ref": _STATE,
            "path": "connected",
            "timeout_ms": 2000,
        },
        "position": {
            "topic": "/mavros/local_position/pose",
            "type": "geometry_msgs/PoseStamped",
            "source_ref": _POSE,
            "path": "pose.position",
            "timeout_ms": 2000,
        },
    }
    commands = {
        "x-cap.tfly6.target_pose.v1": _TARGET,
        "x-cap.tfly6.land.v1": _LAND,
        "x-cap.tfly6.setpoint.v1": _SETPOINT_OBSERVATION,
    }
    actions = {
        "x-cap.tfly6.target_pose.v1": Action(
            name="send_target_pose",
            verb="invoke",
            risk="R2",
            description="Publish one opendrone/PlannerOutput to /planner/output. The base node "
                        "latches the first point whose valid_mask has VALID_POSITION and republishes "
                        "it as the position setpoint; the receipt confirms transmission only, not "
                        "reception, arrival or motion.",
            input={
                "points": Field(
                    "array",
                    description="PlannerOutputPoint array; the base node uses the first point with "
                                "the VALID_POSITION bit and ignores the rest",
                    min_items=1,
                    items=_POINT,
                ),
            },
            output=_PUBLISHED,
        ),
        "x-cap.tfly6.setpoint.v1": Action(
            name="read_setpoint",
            verb="read",
            description="Read one explicit /mavros/setpoint_position/local sample. The base node "
                        "publishes this topic only in WAITING_FOR_OFFBOARD, TAKEOFF and "
                        "MISSION_EXECUTION, so the observation may time out after a landing request; "
                        "it is not an automatic resource field.",
            output={"position": _SETPOINT_POSITION},
        ),
        "x-cap.tfly6.land.v1": Action(
            name="request_landing",
            verb="invoke",
            risk="R2",
            description="Fixed, input-free std_srvs/SetBool(true) request to the base node's "
                        "/land service, an ordinary command: the callback stores the landing "
                        "request and returns success before the node asks MAVROS for AUTO.LAND; "
                        "the response proves neither the mode change nor touchdown, and the "
                        "e-stop latch refuses it",
            output=_LAND_OUTPUT,
        ),
    }
    #: The /land callback acknowledgement alone does not certify a stop (base.cpp:277-289, 259-275): the e-stop is
    #: the sensed-confirmation stop above (SAFE-049), never an acknowledged binding.
    safety_bindings = {"sensed_stop": _SENSED_STOP}
