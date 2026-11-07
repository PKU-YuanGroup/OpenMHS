"""OpenMHS rosbridge driver for the Crazyflie trajectory package (gh.mgreiff/crazyflie-project).

The pinned repository is a ROS 1 / Python 2 research package.  Its
``crazyflie_trajectory`` stack builds trajectory packets and sends them to a
Crazyflie through the external ``crazyflie_ros`` driver.  This package is a
configuration-only :class:`RosDriver` over rosbridge; it declares no Python
native class, does not import the upstream package, does not launch a ROS
node, and does not run Simulink or a UAV.

The exposed surface is the wire contract the clone's ``master.py`` uses:
one ``/crazyflie/trajectory_packet`` publication, one
``/crazyflie/synchronization_packet`` publication, one
``/crazyflie/cmd_vel`` publication, the acknowledged
``/crazyflie/update_params`` service and the acknowledged
``/crazyflie/emergency`` service.  One action publishes one ROS message; it
does not reproduce the upstream 20-times packet loop or upload a complete
trajectory.

These endpoints are the inputs of the external (modified) ``crazyflie_ros``
driver that the clone's launch files start with a Crazyradio URI for a real
Crazyflie; the clone contains no ROS simulator (its simulation is MATLAB/
Simulink).  The emergency service is the only stop path and its callback is
outside the clone, so nothing here shows what the vehicle is left in.  No
stop is bound: the package is blocked (NO_HARDWARE_FREE_PATH) and the e-stop
reports MHS.SAFETY.SAFE_STATE_UNREACHED with the latch held.

Every endpoint, type and Fact cites the pinned clone at
4b7f8281e86d6eb72952242577350bb2c4efd181.  The fake transport is ROS-free;
no ROS graph, simulator, external driver or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references (paths are relative to the clone root)
# ---------------------------------------------------------------------------

#: Publisher and service-proxy declarations of the master node.
_CMD_VEL_REF = "crazyflie_trajectory/scripts/master.py:29"
_TRAJECTORY_REF = "crazyflie_trajectory/scripts/master.py:30"
_SYNC_REF = "crazyflie_trajectory/scripts/master.py:32"
_PARAMS_REF = "crazyflie_trajectory/scripts/master.py:35"
_EMERGENCY_REF = "crazyflie_trajectory/scripts/master.py:36"

#: Explicit imports that prove the fully qualified message/service types.
_TWIST_TYPE_REF = "crazyflie_trajectory/scripts/master.py:9"
_PARAMS_TYPE_REF = "crazyflie_trajectory/scripts/master.py:10"
_SYNC_TYPE_REF = "crazyflie_trajectory/scripts/master.py:12"
_TRAJECTORY_TYPE_REF = "crazyflie_trajectory/scripts/master.py:13"
_EMPTY_TYPE_REF = "crazyflie_trajectory/scripts/master.py:15"
_LOG_REF_REF = "crazyflie_trajectory/scripts/converter.py:24"
_LOG_REF_TYPE_REF = "crazyflie_trajectory/scripts/converter.py:11"

#: Message and service definitions.
_TRAJECTORY_MSG_REF = "crazyflie_trajectory/msg/TrajectoryPacket.msg:1-6"
_SYNC_MSG_REF = "crazyflie_trajectory/msg/SynchronizationPacket.msg:1-4"
_PARAMS_SRV_REF = "crazyflie_trajectory/srv/UpdateParams.srv:1-2"

#: The transfer loop republishes every packet twenty times with a 5 ms sleep.
_TRANSFER_LOOP_REF = "crazyflie_trajectory/scripts/master.py:107-117"
_SYNC_BUILD_REF = "crazyflie_trajectory/scripts/master.py:54-60"
_HELP_REF = "crazyflie_trajectory/scripts/master.py:130-133"

# ---------------------------------------------------------------------------
# Limits: the clone states wire types and demonstration values, not a numeric
# operating envelope.  Every physical quantity and packet selector is
# operator_required; site-limits.example.json is only an example overlay.
# ---------------------------------------------------------------------------

_DATA_LIMIT = Limit.operator_required(
    "the clone declares float32[6] data but states no numeric bound for the spline coefficients; "
    "the deployed site supplies the accepted packet envelope")
_TIME_LIMIT = Limit.operator_required(
    "the clone declares float32 time but states no numeric bound for a trajectory packet duration; "
    "the deployed site supplies the accepted packet duration")
_SELECTOR_LIMIT = Limit.operator_required(
    "the clone declares uint8 index, dimension, number and type but states no numeric bound for the "
    "trajectory selectors; the deployed site supplies the accepted packet indices")
_SYNC_FLAG_LIMIT = Limit.operator_required(
    "the clone declares uint8 synchronize but states no numeric bound for the synchronization flag; "
    "the deployed site supplies the accepted flag values")
_SYNC_META_LIMIT = Limit.operator_required(
    "the clone declares uint8[4] circular and uint8[4] number but states no numeric bound for these "
    "trajectory metadata arrays; the deployed site supplies the accepted values")
_SYNC_TIME_LIMIT = Limit.operator_required(
    "the clone declares float32[4] time and sets all four entries to one start delay, but states no "
    "numeric bound for that delay; the deployed site supplies the accepted delay")
_VELOCITY_LIMIT = Limit.operator_required(
    "the clone never publishes on this Twist topic and states no meaning, unit or bound for its "
    "components; the consuming crazyflie_ros driver is external; the site supplies the envelope")

# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------

_PUBLISHED = {
    "published": Field("boolean", description="True when the rosbridge publication was transmitted"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication has no execution acknowledgement"),
}

_ACCEPTED = {
    "accepted": Field("boolean",
                      description="True when the acknowledged service response met the declared success predicate"),
}

# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------

_TRAJECTORY_INPUT = {
    "data": Field("array", unit="1", description="Six spline coefficients of one trajectory packet",
                  items=Field("number", unit="1", description="Spline coefficient"),
                  length=6, limit=_DATA_LIMIT),
    "time": Field("number", unit="s", description="Packet duration", limit=_TIME_LIMIT),
    "index": Field("integer", unit="1", description="Spline index within the dimension", limit=_SELECTOR_LIMIT),
    "dimension": Field("integer", unit="1", description="Flat-output dimension selector", limit=_SELECTOR_LIMIT),
    "number": Field("integer", unit="1", description="Number of splines in the dimension", limit=_SELECTOR_LIMIT),
    "type": Field("integer", unit="1", description="Spline type selector", limit=_SELECTOR_LIMIT),
}

_SYNC_INPUT = {
    "synchronize": Field("integer", unit="1", description="Synchronization flag", limit=_SYNC_FLAG_LIMIT),
    "circular": Field("array", unit="1", description="Circular flags for the four flat output dimensions",
                      items=Field("integer", unit="1", description="Circular flag"),
                      length=4, limit=_SYNC_META_LIMIT),
    "number": Field("array", unit="1", description="Spline counts for the four flat output dimensions",
                    items=Field("integer", unit="1", description="Spline count"),
                    length=4, limit=_SYNC_META_LIMIT),
    "time": Field("array", unit="s", description="Start delay replicated across the four dimensions",
                  items=Field("number", unit="s", description="Start delay"),
                  length=4, limit=_SYNC_TIME_LIMIT),
}

#: The clone creates the /crazyflie/cmd_vel publisher (master.py:29) but never publishes on it, so it
#: states no meaning or unit for these fields; the consumer is the external crazyflie_ros driver.
#: No unit is claimed (reviewer r20; the author's m/s and rad/s had no source).
_VELOCITY_INPUT = {
    "linear": Field("object", description="Twist linear part for the external driver",
                    properties={
                        "x": Field("number", description="Twist linear.x; unit unstated", limit=_VELOCITY_LIMIT),
                        "y": Field("number", description="Twist linear.y; unit unstated", limit=_VELOCITY_LIMIT),
                        "z": Field("number", description="Twist linear.z; unit unstated", limit=_VELOCITY_LIMIT),
                    }),
    "angular": Field("object", description="Twist angular part for the external driver",
                     properties={
                         "x": Field("number", description="Twist angular.x; unit unstated", limit=_VELOCITY_LIMIT),
                         "y": Field("number", description="Twist angular.y; unit unstated", limit=_VELOCITY_LIMIT),
                         "z": Field("number", description="Twist angular.z; unit unstated", limit=_VELOCITY_LIMIT),
                     }),
}

_PARAMS_INPUT = {
    "parameters": Field("array", description="ROS parameter names to update",
                        items=Field("string", description="Parameter name")),
}

# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------

_CMD_VEL = {
    "topic": "/crazyflie/cmd_vel",
    "type": "geometry_msgs/Twist",
    "source_ref": _CMD_VEL_REF,
    "type_ref": _TWIST_TYPE_REF,
    "operation": "publish",
    "args": {
        "linear.x": {"from": "input.linear.x"},
        "linear.y": {"from": "input.linear.y"},
        "linear.z": {"from": "input.linear.z"},
        "angular.x": {"from": "input.angular.x"},
        "angular.y": {"from": "input.angular.y"},
        "angular.z": {"from": "input.angular.z"},
    },
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
    "description": "Publish one geometry_msgs/Twist on /crazyflie/cmd_vel; transmission only",
}

_TRAJECTORY = {
    "topic": "/crazyflie/trajectory_packet",
    "type": "crazyflie_trajectory/TrajectoryPacket",
    "source_ref": _TRAJECTORY_REF,
    "type_ref": _TRAJECTORY_TYPE_REF,
    "operation": "publish",
    "args": {
        "data": {"from": "input.data"},
        "time": {"from": "input.time"},
        "index": {"from": "input.index"},
        "dimension": {"from": "input.dimension"},
        "number": {"from": "input.number"},
        "type": {"from": "input.type"},
    },
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
    "description": "Publish one TrajectoryPacket on /crazyflie/trajectory_packet; transmission only",
}

_SYNC = {
    "topic": "/crazyflie/synchronization_packet",
    "type": "crazyflie_trajectory/SynchronizationPacket",
    "source_ref": _SYNC_REF,
    "type_ref": _SYNC_TYPE_REF,
    "operation": "publish",
    "args": {
        "synchronize": {"from": "input.synchronize"},
        "circular": {"from": "input.circular"},
        "number": {"from": "input.number"},
        "time": {"from": "input.time"},
    },
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
    "description": "Publish one SynchronizationPacket on /crazyflie/synchronization_packet; transmission only",
}

_UPDATE_PARAMS = {
    "service": "/crazyflie/update_params",
    "type": "crazyflie_trajectory/UpdateParams",
    "source_ref": _PARAMS_REF,
    "type_ref": _PARAMS_TYPE_REF,
    "operation": "call",
    "args": {"params": {"from": "input.parameters"}},
    "success": {"path": "$", "equals": {}},
    "result": {"accepted": {"value": True}},
    "description": "Call the acknowledged /crazyflie/update_params service with a list of parameter names",
}

_EMERGENCY = {
    "service": "/crazyflie/emergency",
    "type": "std_srvs/Empty",
    "source_ref": _EMERGENCY_REF,
    "type_ref": _EMPTY_TYPE_REF,
    "success": {"path": "$", "equals": {}},
}

_EMERGENCY_COMMAND = dict(
    _EMERGENCY,
    operation="call",
    result={"accepted": {"value": True}},
    description="Call the acknowledged /crazyflie/emergency Empty service; the callback is external",
)


class CrazyflieTrajectory(RosDriver):
    device_id = "crazyflie-trajectory"
    device_kind = "device"
    mode = "simulated"
    #: The command surface publishes trajectory and velocity messages to a UAV
    #: driver; a mobile-base transit is at least R2 even in simulation.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeCrazyflieProject"}
    tags = ["ros", "ros1", "crazyflie", "uav", "trajectory", "simulation"]
    display_name = "Crazyflie trajectory master interface"
    vendor = "mgreiff"
    model = "crazyflie_trajectory ROS 1 master"
    facts = [
        Fact("Master creates a rospy.Publisher on the absolute /crazyflie/cmd_vel topic with "
             "geometry_msgs/Twist and queue size 1.", source="upstream_code", ref=_CMD_VEL_REF),
        Fact("Master creates a rospy.Publisher on the absolute /crazyflie/trajectory_packet topic with "
             "crazyflie_trajectory/TrajectoryPacket and queue size 100.",
             source="upstream_code", ref=_TRAJECTORY_REF),
        Fact("Master creates a rospy.Publisher on the absolute /crazyflie/synchronization_packet topic with "
             "crazyflie_trajectory/SynchronizationPacket and queue size 100.",
             source="upstream_code", ref=_SYNC_REF),
        Fact("Master creates a rospy.ServiceProxy on the absolute /crazyflie/update_params service with "
             "crazyflie_trajectory/UpdateParams.", source="upstream_code", ref=_PARAMS_REF),
        Fact("Master creates a rospy.ServiceProxy on the absolute /crazyflie/emergency service with "
             "std_srvs/Empty.", source="upstream_code", ref=_EMERGENCY_REF),
        Fact("The transfer loop sends every packet in data['packets'] twenty times, sleeping 5 ms between "
             "publications.", source="upstream_code", ref=_TRANSFER_LOOP_REF),
        Fact("synchronize_trajectory copies circular and number from the trajectory and fills all four "
             "SynchronizationPacket time slots with the same float start delay.",
             source="upstream_code", ref=_SYNC_BUILD_REF),
        Fact("The master help text identifies 'q' as 'Calls emergency service' and 't' as 'Transfer a "
             "trajectory file to the UAV'.", source="upstream_code", ref=_HELP_REF),
        Fact("TrajectoryPacket declares float32[6] data, float32 time and the uint8 fields index, dimension, "
             "number and type.", source="upstream_code", ref=_TRAJECTORY_MSG_REF),
        Fact("SynchronizationPacket declares uint8 synchronize, uint8[4] circular, uint8[4] number and "
             "float32[4] time.", source="upstream_code", ref=_SYNC_MSG_REF),
        Fact("UpdateParams has a string[] params request and an empty response.",
             source="upstream_code", ref=_PARAMS_SRV_REF),
        Fact("Converter subscribes to the absolute /crazyflie/log_ref topic with "
             "crazyflie_trajectory/GenericLogData", source="upstream_code", ref=_LOG_REF_REF),
        Fact("Trajectory sets nDim to 4 and timeStep to 0.02, evaluating at 50 Hz as in the firmware.",
             source="upstream_code", ref="crazyflie_trajectory/modules/trajectorylib.py:37-40"),
        Fact("trajectoryExample.launch defaults the uri argument to radio://0/35/2M, includes the external "
             "crazyflie_driver crazyflie_server.launch and starts crazyflie_add with that uri in the "
             "crazyflie namespace.",
             source="upstream_code", ref="crazyflie_trajectory/launch/trajectoryExample.launch:7-19"),
        Fact("trajectoryExample.launch configures crazyflie_add with the generic log topics log_ref, "
             "log_pos, log_errors and log_cacheB at 10 each, log_ref carrying the reference x, y, z, roll, "
             "pitch and yaw variables.",
             source="upstream_code", ref="crazyflie_trajectory/launch/trajectoryExample.launch:21-23"),
        Fact("trajectoryExample.launch starts the master node of crazyflie_trajectory.",
             source="upstream_code", ref="crazyflie_trajectory/launch/trajectoryExample.launch:30-35"),
        Fact("The README lists a Crazyflie driver modified from the original for communicating with the "
             "crazyflie and a Crazyflie firmware modified to support SE(3) control as dependencies.",
             source="upstream_code", ref="README.md:9-10"),
        Fact("The master command loop calls the emergency service proxy for the q keyword.",
             source="upstream_code", ref="crazyflie_trajectory/scripts/master.py:174-176"),
    ]
    safe_state = (
        "No acknowledged stop exists: the e-stop fails MHS.SAFETY.SAFE_STATE_UNREACHED with the latch held, "
        "which only refuses this driver's commands; /crazyflie/emergency is answered by the external "
        "crazyflie_ros driver (the clone defines only the proxy), so nothing shows what the Crazyflie is left "
        "in, and an uploaded trajectory or the last command stays with the external driver and firmware."
    )
    fidelity = {
        "engine": "analytic:ROS-free contract fake for the trajectory publication and service contract (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned acknowledgements with no quadrotor dynamics, controller, trajectory "
                     "replay or wall-clock pacing; every state value is a placeholder",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free contract transport: it runs no crazyflie_ros node, controller, Simulink "
            "model, Gazebo world or UAV",
            "the upstream transfer loop sends every packet twenty times with a 5 ms sleep; the fake reproduces "
            "neither the repetition nor the pacing",
            "one action publishes one ROS message; it does not upload a complete trajectory or guarantee that "
            "the external driver consumes the packet sequence",
            "the /crazyflie/emergency callback implementation is in the external crazyflie_ros repository, not "
            "in this clone; the fake acknowledgement is not a stop proof, and no stop is bound (blocked "
            "NO_HARDWARE_FREE_PATH)",
            "every bound topic and service is an input of the external crazyflie_ros driver that the clone's "
            "launch files start with a Crazyradio URI for a real Crazyflie; the clone has no ROS simulator, so "
            "mode simulated (from the registry record) does not describe the ROS route",
            "master.py creates the /crazyflie/cmd_vel publisher but never publishes on it, so the clone states "
            "no meaning or unit for the Twist fields; the external driver decides what they command",
            "the external driver publishes /crazyflie/log_ref with its own GenericLogData type; this package "
            "declares crazyflie_trajectory/GenericLogData from the clone's converter, and whether rosbridge "
            "accepts that type name for the live topic is unverified",
            "the fake copies the six trajectory-packet coefficients into a placeholder /crazyflie/log_ref state "
            "so the resource changes; that is not dynamics, a measured pose or a reference-pose model",
            "the clone's /crazyflie/log_pos observation and the converter's file output are NOT COVERED",
            "no live ROS graph, rosbridge peer, launch file, simulator or hardware was run",
        ],
    }
    commands = {
        "x-cap.mgreiff.cmd_vel.v1": _CMD_VEL,
        "x-cap.mgreiff.trajectory_packet.v1": _TRAJECTORY,
        "x-cap.mgreiff.synchronization_packet.v1": _SYNC,
        "x-cap.mgreiff.update_params.v1": _UPDATE_PARAMS,
        "x-cap.mgreiff.emergency.v1": _EMERGENCY_COMMAND,
    }
    #: The converter's /crazyflie/log_ref subscription supplies the observable
    #: resource state.  The fake's value is a placeholder effect only.
    parameters = {
        "log_ref": Field("array", unit="1", description="Last /crazyflie/log_ref values",
                         items=Field("number", unit="1", description="Logged reference value")),
    }
    reads = {
        "log_ref": {
            "topic": "/crazyflie/log_ref",
            "type": "crazyflie_trajectory/GenericLogData",
            "source_ref": _LOG_REF_REF,
            "type_ref": _LOG_REF_TYPE_REF,
            "path": "values",
            "timeout_ms": 2000,
        },
    }
    actions = {
        "x-cap.mgreiff.cmd_vel.v1": Action(
            name="publish_cmd_vel",
            verb="invoke",
            risk="R2",
            description="Publish one geometry_msgs/Twist on /crazyflie/cmd_vel; transmission only, no motion claim",
            input=_VELOCITY_INPUT,
            output=_PUBLISHED,
        ),
        "x-cap.mgreiff.trajectory_packet.v1": Action(
            name="publish_trajectory_packet",
            verb="invoke",
            risk="R2",
            description="Publish one TrajectoryPacket; transmission only, one packet is not a full trajectory",
            input=_TRAJECTORY_INPUT,
            output=_PUBLISHED,
        ),
        "x-cap.mgreiff.synchronization_packet.v1": Action(
            name="publish_synchronization_packet",
            verb="invoke",
            risk="R2",
            description="Publish one SynchronizationPacket start-delay message; transmission only",
            input=_SYNC_INPUT,
            output=_PUBLISHED,
        ),
        "x-cap.mgreiff.update_params.v1": Action(
            name="update_parameters",
            verb="invoke",
            risk="R2",
            description="Call the acknowledged UpdateParams service with ROS parameter names",
            input=_PARAMS_INPUT,
            output=_ACCEPTED,
        ),
        "x-cap.mgreiff.emergency.v1": Action(
            name="request_emergency",
            verb="invoke",
            risk="R2",
            description="Call the /crazyflie/emergency Empty service of the external driver; an ordinary "
                        "command, not a stop: the callback and its effect are outside the clone",
            output=_ACCEPTED,
        ),
    }
    #: The only stop path in the clone is the external emergency service: its callback and effect are
    #: outside the clone, so it is not bound as the e-stop (reviewer r20; blocked NO_HARDWARE_FREE_PATH).
    safety_bindings = {}
