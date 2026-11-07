"""OpenMHS rosbridge driver for the MRS Crazyflie ROS 2 simulation interface.

The pinned repository is a ROS 2 ament package of Gazebo/CrazySim launch and
configuration files for the LARICS MRS Crazyflie exercise.  The running
CrazySwarm2 ``crazyflie_server`` and ``vel_mux`` nodes come from the external
``crazyflie`` package; this clone documents their user-facing endpoints and
carries a copy of the server source under ``to_copy``.  This package is a
configuration-only :class:`RosDriver` over rosbridge.  It declares no Python
native class, imports nothing from the clone, starts no ROS node and runs no
Gazebo world or Crazyflie.

The served scope is one configured simulated Crazyflie, ``cf_1``: one
geometry_msgs/Twist publication on ``/cf_1/cmd_vel``, the PoseStamped pose
observation on ``/cf_1/pose``, and the swarm-wide ``/all/emergency``
std_srvs/Empty service as an ordinary request.  The emergency callback only
asks cflib to send an emergency-stop (motor cut) packet to each Crazyflie and
returns, so the Empty response alone is a callback acknowledgement that
nothing in the clone confirms.  This simulated package therefore declares a
sensed-confirmation stop (SAFE-049, the user's decision of 2026-11-05,
simulated devices only): the e-stop calls ``/all/emergency`` and is achieved
only when ``/cf_1/pose`` shows the vehicle on the ground and at rest in three
consecutive fresh samples within the bound; otherwise it fails
MHS.SAFETY.SAFE_STATE_UNREACHED with the latch held and is retried in the
background.  The motor cut cannot be undone without restarting the simulated
firmware, so the e-stop is declared terminal (CORE-087).  The service is
swarm-wide: every enabled simulated Crazyflie falls.  A Crazyradio URI drives
a real Crazyflie with the same server: that path is out of scope.

Every endpoint, type and fact cites the pinned clone at
234ac04745a558601e539ce9aa33b72b4e760243.  The fake transport is ROS-free;
no ROS graph, rosbridge peer, Gazebo simulation or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references (paths are relative to the clone root)
# ---------------------------------------------------------------------------

#: README documents the user-facing topic family.
_README_TOPICS_REF = "README.md:69"
_README_SERVICES_REF = "README.md:70"

#: The teleop example names the concrete cf_1 velocity endpoint.
_CMD_VEL_REF = "README.md:120"

#: Imports prove the fully qualified message and service types.
_TWIST_TYPE_REF = "to_copy/crazyflie_server.py:35"
_POSE_TYPE_REF = "to_copy/crazyflie_server.py:36"
_EMPTY_TYPE_REF = "to_copy/crazyflie_server.py:33"

#: The copied server maps the default log name pose to PoseStamped and builds
#: each publisher as cf_name + "/" + prefix.
_POSE_NAME_REF = "to_copy/crazyflie_server.py:93"
_POSE_PUBLISH_REF = "to_copy/crazyflie_server.py:403-407"
_POSE_CALLBACK_REF = "to_copy/crazyflie_server.py:598-623"
#: The pose publisher's QoS: create_publisher with the integer depth 10, so rclpy's default durability, volatile (a
#: new subscription receives nothing published before it).
_POSE_QOS_REF = "to_copy/crazyflie_server.py:404-405"

#: The copied server advertises a per-drone emergency Empty service and a
#: swarm-wide all/emergency service; the callback calls the Crazyflie
#: emergency-stop send path.
_EMERGENCY_PER_DRONE_REF = "to_copy/crazyflie_server.py:290-293"
_EMERGENCY_REF = "to_copy/crazyflie_server.py:360"
_EMERGENCY_CALLBACK_REF = "to_copy/crazyflie_server.py:888-895"

#: The custom velocity log topic uses LogDataGeneric and the cf_sim type
#: configures it with the kalman state velocity variables.
_CUSTOM_LOG_REF = "to_copy/crazyflie_server.py:510-512"
_CUSTOM_LOG_CONFIG_REF = "config/crazyflies_mrs.yaml:181-184"

#: The launch file places vel_mux in the cf_1 namespace and gives it the
#: relative cmd_vel input topic.
_VEL_MUX_REF = "launch/cf_velmux_launch.py:64-75"

#: The configured first simulated Crazyflie.
_CF1_REF = "config/crazyflies_mrs.yaml:14-18"

#: The pose callback writes stateEstimate x, y and z into pose.position and stamps the header with the node clock.
_POSE_FILL_REF = "to_copy/crazyflie_server.py:617-619"
_POSE_STAMP_REF = "to_copy/crazyflie_server.py:615"
#: The cf_sim robot type enables firmware logging with the default pose topic at 10 Hz.
_POSE_LOGGING_REF = "config/crazyflies_mrs.yaml:165-180"

#: The package is a ROS 2 Gazebo Ignition simulation configuration.
_README_SIM_REF = "README.md:4"

#: The Dockerfile replaces the crazyswarm2 server with the to_copy version.
_DOCKER_SERVER_REF = "Dockerfile:176-179"

#: A commented template robot entry uses a Crazyradio URI with type cf.
_RADIO_TEMPLATE_REF = "config/crazyflies_mrs.yaml:3-9"

# ---------------------------------------------------------------------------
# Limits: the clone declares a geometry_msgs/Twist command but no numeric
# velocity envelope.  The operator supplies the deployment envelope.
# ---------------------------------------------------------------------------

_VELOCITY_LIMIT = Limit.operator_required(
    "the clone declares geometry_msgs/Twist velocity commands but states no numeric bound for their "
    "linear or angular components; the deployed site supplies the accepted velocity envelope")

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
                      description="True when the Empty response arrived: the server callback returned after asking "
                                  "cflib to send the packets; not a confirmed stop"),
}

# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------

_TWIST_INPUT = {
    "linear": Field("object", description="Linear velocity command",
                    properties={
                        "x": Field("number", unit="m/s", description="Linear x velocity",
                                   limit=_VELOCITY_LIMIT),
                        "y": Field("number", unit="m/s", description="Linear y velocity",
                                   limit=_VELOCITY_LIMIT),
                        "z": Field("number", unit="m/s", description="Linear z velocity",
                                   limit=_VELOCITY_LIMIT),
                    }),
    "angular": Field("object", description="Angular velocity command",
                     properties={
                         "x": Field("number", unit="rad/s", description="Angular x velocity",
                                    limit=_VELOCITY_LIMIT),
                         "y": Field("number", unit="rad/s", description="Angular y velocity",
                                    limit=_VELOCITY_LIMIT),
                         "z": Field("number", unit="rad/s", description="Angular z velocity",
                                    limit=_VELOCITY_LIMIT),
                     }),
}

# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------

_CMD_VEL = {
    "topic": "/cf_1/cmd_vel",
    "type": "geometry_msgs/msg/Twist",
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
    "description": "Publish one geometry_msgs/Twist on /cf_1/cmd_vel; transmission only",
}

_POSE_READ = {
    "topic": "/cf_1/pose",
    "type": "geometry_msgs/msg/PoseStamped",
    "source_name": "pose",
    "source_ref": _POSE_NAME_REF,
    "type_ref": _POSE_TYPE_REF,
    "path": "pose.position",
    "timeout_ms": 2000,
}

_EMERGENCY = {
    "service": "/all/emergency",
    "type": "std_srvs/srv/Empty",
    "source_name": "all/emergency",
    "source_ref": _EMERGENCY_REF,
    "type_ref": _EMPTY_TYPE_REF,
    "success": {"path": "$", "equals": {}},
}

_EMERGENCY_COMMAND = dict(
    _EMERGENCY,
    operation="call",
    result={"accepted": {"value": True}},
    description="Call the swarm-wide /all/emergency Empty service (motor-cut request; callback acknowledgement only)",
)


#: Sensed-confirmation stop (SAFE-049): the swarm-wide emergency request proves nothing by itself; only fresh
#: stamped /cf_1/pose samples that show the vehicle on the ground and still achieve the stop.  The pose callback
#: fills pose.position from the state estimate and stamps it with the node clock (crazyflie_server.py:614-619).
#: The per-drone name + "/emergency" service (crazyflie_server.py:290-293) is not used: its endpoint literal is a
#: concatenation that gate G7 cannot match, so the clone's citable stop is /all/emergency.  The thresholds are
#: operator_required (the configured initial_position z 0.0 is a reference, not a bound); the client bounds are
#: fake-scale and a live deployment sets them in its estop_confirmation.
_NO_GROUND_BOUND = ("the clone states no on-ground band; the configured initial_position z 0.0 "
                    "(config/crazyflies_mrs.yaml:17) is a reference, not a bound, so the operator supplies it")
_NO_REST_BOUND = ("the clone states no at-rest position bound; the operator supplies the largest position change "
                  "over the confirmation window that counts as at rest")

_SENSED_STOP = {
    "request": [dict(_EMERGENCY, timeout_ms=1000,
                     description="the swarm-wide emergency service: cflib send_emergency_stop() for every "
                                 "enabled Crazyflie (callback acknowledgement only)")],
    "sources": {
        "pose": {"topic": "/cf_1/pose", "type": "geometry_msgs/msg/PoseStamped", "source_name": "pose",
                 "source_ref": _POSE_NAME_REF, "type_ref": _POSE_TYPE_REF,
                 "fill_refs": {"pose.position": _POSE_FILL_REF},
                 "history": {"durability": "volatile", "ref": _POSE_QOS_REF}},
    },
    "predicate": [
        {"source": "pose", "path": "pose.position.z", "name": "ground_z", "unit": "m",
         "range": {"max": Limit.operator_required(_NO_GROUND_BOUND)}},
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
    "description": "rotors cut by the firmware emergency stop of every enabled simulated Crazyflie; cf_1 sensed on "
                   "the ground and still on /cf_1/pose in three consecutive fresh samples within the bound",
}


class MrsCrazyflies(RosDriver):
    device_id = "mrs-crazyflies-cf1"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    #: A velocity-controlled UAV transit is a mobile-base motion at R2 even in
    #: simulation.  The card floor is R0.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeMrsCrazyflies"}
    tags = ["ros", "ros2", "crazyflie", "uav", "simulation", "gazebo", "crazyswarm2", "larics"]
    display_name = "MRS Crazyflies cf_1 velocity interface"
    vendor = "LARICS"
    model = "CrazySwarm2 crazyflie_server with the mrs_crazyflies cf_1 configuration"
    facts = [
        Fact("The README documents velocity commands on /cf_x/cmd_vel, pose on /cf_x/pose, and velocity on "
             "/cf_x/velocity as the custom LogDataGeneric message whose elements are v_x, v_y and v_z in a "
             "world frame.", source="vendor_doc", ref=_README_TOPICS_REF),
        Fact("The README documents takeoff and land services /cf_x/takeoff and /cf_x/land and says the current "
             "vel_mux takes off automatically after the first cmd_vel command.",
             source="vendor_doc", ref=_README_SERVICES_REF),
        Fact("The README teleop example remaps cmd_vel to the concrete topic /cf_1/cmd_vel.",
             source="vendor_doc", ref=_CMD_VEL_REF),
        Fact("The simulation is Gazebo Ignition and uses ROS 2 packages based on CrazySwarm2.",
             source="vendor_doc", ref=_README_SIM_REF),
        Fact("The configuration enables cf_1 as type cf_sim with a UDP URI and initial_position "
             "[-0.5, -4.0, 0.0].", source="upstream_code", ref=_CF1_REF),
        Fact("The launch file starts one vel_mux node per robot index from 1 to NUM_ROBOTS (default 4); the "
             "first runs in namespace cf_1 with incoming_twist_topic cmd_vel and robot_prefix /cf_1.",
             source="upstream_code", ref=_VEL_MUX_REF),
        Fact("The Dockerfile removes the crazyswarm2 crazyflie_server.py and copies to_copy/crazyflie_server.py "
             "in its place.", source="upstream_code", ref=_DOCKER_SERVER_REF),
        Fact("A commented template robot entry in the configuration uses the URI radio://0/80/2M/E7E7E7E7E7 "
             "with type cf.", source="upstream_code", ref=_RADIO_TEMPLATE_REF),
        Fact("The copied server maps the default log name pose to PoseStamped.",
             source="upstream_code", ref=_POSE_NAME_REF),
        Fact("The copied server creates a default log publisher on cf_name + \"/\" + prefix only when logging "
             "is enabled for that prefix and for the robot; otherwise it stores \"empty\".",
             source="upstream_code", ref=_POSE_PUBLISH_REF),
        Fact("The pose callback builds a PoseStamped from stateEstimate.x, stateEstimate.y, stateEstimate.z "
             "and a quaternion derived from the stabilizer angles.", source="upstream_code",
             ref=_POSE_CALLBACK_REF),
        Fact("The copied server creates a LogDataGeneric publisher on cf_name + \"/\" + log_group_name for "
             "custom log topics.", source="upstream_code", ref=_CUSTOM_LOG_REF),
        Fact("The cf_sim type defines a custom topic named velocity at 10 Hz with the variables "
             "kalman.statePX, kalman.statePY and kalman.statePZ.", source="upstream_code",
             ref=_CUSTOM_LOG_CONFIG_REF),
        Fact("The copied server creates an Empty service on name + \"/emergency\" for each Crazyflie.",
             source="upstream_code", ref=_EMERGENCY_PER_DRONE_REF),
        Fact("The copied server creates the swarm-wide all/emergency Empty service.",
             source="upstream_code", ref=_EMERGENCY_REF),
        Fact("The emergency callback calls loc.send_emergency_stop() for every selected Crazyflie URI and "
             "returns the service response.", source="upstream_code", ref=_EMERGENCY_CALLBACK_REF),
        Fact("The pose callback sets pose.position x, y and z from stateEstimate.x, y and z.",
             source="upstream_code", ref="to_copy/crazyflie_server.py:606-619"),
        Fact("The pose callback stamps the PoseStamped header with the node clock.",
             source="upstream_code", ref=_POSE_STAMP_REF),
        Fact("The cf_sim robot type enables firmware logging with the default pose topic at frequency 10.",
             source="upstream_code", ref=_POSE_LOGGING_REF),
    ]
    safe_state = (
        "Simulated only: rotors cut by the firmware emergency stop of every enabled simulated Crazyflie, and cf_1 "
        "sensed on the ground and still on /cf_1/pose in three consecutive fresh stamped samples within the "
        "confirmation bound. The Empty response alone proves nothing; nothing is claimed beyond the confirmation "
        "window, and the stop is terminal on this endpoint."
    )
    #: The request step's timeout (1000 ms) plus confirm_within_ms (1500 ms): the e-stop's budget.
    estop_latency_ms = 2500
    #: CORE-087: nothing in the clone re-enables a Crazyflie after send_emergency_stop() (crazyflie_server.py:888-895).
    estop_terminal = ("the e-stop asks each Crazyflie's firmware for an emergency stop that nothing in the clone "
                      "undoes; only a restart of the simulated firmware and server, a new native session, recovers it")
    fidelity = {
        "engine": "analytic:ROS-free contract fake for the mrs_crazyflies ROS 2 endpoints (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven placeholder pose updates and canned service acknowledgements; no quadrotor "
                     "dynamics, controller, Gazebo world, CrazySwarm2 node or wall-clock pacing",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free contract stand-in, not a recording of captured traffic and not the upstream "
            "simulator: it runs no Gazebo Ignition world, CrazySim firmware, CrazySwarm2 crazyflie_server, "
            "vel_mux node or UAV",
            "the fake updates a placeholder pose by a fixed offset per Twist publication and emits it on a "
            "subscribe; that is not quadrotor dynamics, a measured pose or a trajectory replay",
            "the /cf_1/cmd_vel publication is transmission-only; the clone does not contain vel_mux.py, so the "
            "conversion to a hover command and its consumption by the external server are NOT COVERED",
            "the e-stop is a sensed-confirmation stop (SAFE-049, simulated only): the /all/emergency "
            "acknowledgement proves only that the copied Python callback returned after calling "
            "loc.send_emergency_stop() (cflib, outside the clone); the stop is achieved only on three consecutive "
            "fresh /cf_1/pose samples on the ground and still within the bound; the thresholds are "
            "operator_required (fake placeholders in fixtures/estop-confirmation.json) and the client bounds are "
            "fake-scale, so a live deployment sets both in simulation_deployment['estop_confirmation']",
            "the stop is swarm-wide: /all/emergency cuts the motors of every enabled simulated Crazyflie (cf_1 to "
            "cf_4 by default), which fall; the per-drone emergency service is not used because gate G7 cannot "
            "match its concatenated endpoint literal; the e-stop is terminal on the endpoint (CORE-087)",
            "the fake starts hovering at a placeholder 1 m and models the motor cut as a placeholder fall per "
            "sample to the ground; whether the simulated firmware keeps logging pose after an emergency stop is "
            "outside the clone, and a silent pose stream leaves the stop unconfirmed (fail closed)",
            "a commented configuration template uses a Crazyradio URI and the cf robot type; with such an entry "
            "named cf_1 the same server, topics and service drive a real Crazyflie",
            "the per-drone /cf_1/takeoff, /cf_1/land, /cf_1/velocity, /cf_1/scan, /cf_1/odom and /cf_1/status "
            "endpoints and the TF broadcasts are NOT COVERED",
            "the real /cf_1/pose publisher depends on firmware logging being enabled and on the external "
            "CrazySwarm2 server; the fake emits a pose without that graph",
            "no live ROS graph, rosbridge peer, Gazebo simulation, colcon build or hardware was run",
        ],
    }

    # The pose observation supplies the observable resource state used by the
    # conformance effect check; its values come from the topic, not a cache.
    parameters = {
        "pose": Field("object", description="Latest reported world-frame position",
                      properties={
                          "x": Field("number", unit="m", description="World x position"),
                          "y": Field("number", unit="m", description="World y position"),
                          "z": Field("number", unit="m", description="World z position"),
                      }),
    }
    reads = {"pose": _POSE_READ}
    commands = {
        "x-cap.larics.cmd_vel.v1": _CMD_VEL,
        "x-cap.larics.emergency.v1": _EMERGENCY_COMMAND,
    }
    actions = {
        "x-cap.larics.cmd_vel.v1": Action(
            name="publish_cmd_vel",
            verb="invoke",
            risk="R2",
            description="Publish one geometry_msgs/Twist velocity command on /cf_1/cmd_vel; transmission only",
            input=_TWIST_INPUT,
            output=_PUBLISHED,
        ),
        "x-cap.larics.emergency.v1": Action(
            name="request_emergency_stop",
            verb="invoke",
            risk="R2",
            description="Call the swarm-wide /all/emergency Empty service, a motor-cut request whose response "
                        "means only that the server callback returned; not a confirmed stop",
            output=_ACCEPTED,
        ),
    }
    #: The /all/emergency callback acknowledgement alone does not certify a stop (to_copy/crazyflie_server.py:
    #: 888-895): the e-stop is the sensed-confirmation stop above (SAFE-049), never an acknowledged binding.
    safety_bindings = {"sensed_stop": _SENSED_STOP}
