"""OpenMHS rosbridge driver for the UUV Simulator underwater-current environment.

The upstream ``uuv_world_ros_plugins`` package contains the
``UnderwaterCurrentROSPlugin`` Gazebo world plugin.  It exposes the simulated
water-current environment through relative ROS services and a stamped flow
velocity topic.  This package is a configuration-only :class:`RosDriver` over
rosbridge; it declares no Python native class and does not launch ROS or
Gazebo.  The selected profile is the environment control surface:
``set_current_velocity``, ``set_current_horz_angle`` and
``set_current_vert_angle``, the ``current_velocity`` flow observation, and a
fixed zero-current safe-state action.

The zero-current action calls the same acknowledged service with a fixed
request that zeroes the three Gauss-Markov model means.  It is an
acknowledged software action on the simulated current model, not a physical
emergency stop, and it does not stop the vehicle or the Gazebo world.

Every endpoint, type and fact cites the pinned clone at
bfb40cb153684a0703173117b6bbf4258e8e71c5.  The fake transport is ROS-free;
no ROS graph, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

_CURRENT_ROS = ("uuv_world_plugins/uuv_world_ros_plugins/src/"
                "UnderwaterCurrentROSPlugin.cc")
_CURRENT_PLUGIN = ("uuv_world_plugins/uuv_world_plugins/src/"
                   "UnderwaterCurrentPlugin.cc")
_CURRENT_HEADER = ("uuv_world_plugins/uuv_world_ros_plugins/include/"
                   "uuv_world_ros_plugins/UnderwaterCurrentROSPlugin.hh")
_GAUSS_MARKOV = ("uuv_world_plugins/uuv_world_plugins/src/"
                 "GaussMarkovProcess.cc")
_WORLD = "uuv_gazebo_worlds/worlds/auv_underwater_world.world"

#: The service advertisement sites and the message-type includes.
_SET_VELOCITY_DECL = _CURRENT_ROS + ":110-114"
_SET_HORZ_DECL = _CURRENT_ROS + ":116-120"
_SET_VERT_DECL = _CURRENT_ROS + ":122-126"
_TWIST_TYPE = _CURRENT_HEADER + ":33"
_SET_VELOCITY_TYPE = _CURRENT_HEADER + ":36"
_SET_DIRECTION_TYPE = _CURRENT_HEADER + ":37"

#: The flow topic default and the publisher site.
_FLOW_DEFAULT = _CURRENT_PLUGIN + ":81-86"
_FLOW_PUBLISH = _CURRENT_ROS + ":70-72"

#: The namespace and node-handle setup of the plugin.
_NAMESPACE_SETUP = _CURRENT_ROS + ":62-68"

#: The callbacks and the model setter.
_SET_VELOCITY_CALLBACK = _CURRENT_ROS + ":170-193"
_FLOW_UPDATE = _CURRENT_ROS + ":133-148"
_PUBLISH_PERIOD = _CURRENT_ROS + ":21-25"
_SET_MEAN = _GAUSS_MARKOV + ":41-49"

#: The model bounds are SDF configuration, not a fixed device bound.
_VELOCITY_MODEL = _CURRENT_PLUGIN + ":91-116"
_HORZ_MODEL = _CURRENT_PLUGIN + ":122-153"
_VERT_MODEL = _CURRENT_PLUGIN + ":161-190"
_WORLD_EXAMPLE = _WORLD + ":78-105"

_VELOCITY_REASON = ("the current velocity range is configured per world in the SDF "
                    "constant_current block; the operator supplies this deployment's range")
_ANGLE_REASON = ("the horizontal and vertical angle ranges are configured per world in "
                 "the SDF constant_current block; the operator supplies this deployment's range")

_ACCEPTED = Field(
    "boolean",
    description="True when the current service returned success; the model means are updated, "
                "not the physical water",
)

_SET_VELOCITY = {
    "service": "/hydrodynamics/set_current_velocity",
    "type": "uuv_world_ros_plugins_msgs/SetCurrentVelocity",
    "source_name": "set_current_velocity",
    "source_ref": _SET_VELOCITY_DECL,
    "type_ref": _SET_VELOCITY_TYPE,
    "args": {
        "velocity": {"from": "input.velocity"},
        "horizontal_angle": {"from": "input.horizontal_angle"},
        "vertical_angle": {"from": "input.vertical_angle"},
    },
    "success": {"path": "success", "equals": True},
    "result": {"map": {"accepted": "output.success"}},
}

_SET_HORZ = {
    "service": "/hydrodynamics/set_current_horz_angle",
    "type": "uuv_world_ros_plugins_msgs/SetCurrentDirection",
    "source_name": "set_current_horz_angle",
    "source_ref": _SET_HORZ_DECL,
    "type_ref": _SET_DIRECTION_TYPE,
    "args": {"angle": {"from": "input.angle"}},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"accepted": "output.success"}},
}

_SET_VERT = {
    "service": "/hydrodynamics/set_current_vert_angle",
    "type": "uuv_world_ros_plugins_msgs/SetCurrentDirection",
    "source_name": "set_current_vert_angle",
    "source_ref": _SET_VERT_DECL,
    "type_ref": _SET_DIRECTION_TYPE,
    "args": {"angle": {"from": "input.angle"}},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"accepted": "output.success"}},
}

_FLOW = {
    "topic": "/hydrodynamics/current_velocity",
    "type": "geometry_msgs/TwistStamped",
    "source_name": "current_velocity",
    "source_ref": _FLOW_DEFAULT,
    "type_ref": _TWIST_TYPE,
    "operation": "subscribe",
    "result": {"map": {
        "linear_x": "output.twist.linear.x",
        "linear_y": "output.twist.linear.y",
        "linear_z": "output.twist.linear.z",
    }},
}

_FLOW_READ = {
    "topic": "/hydrodynamics/current_velocity",
    "type": "geometry_msgs/TwistStamped",
    "source_name": "current_velocity",
    "source_ref": _FLOW_DEFAULT,
    "type_ref": _TWIST_TYPE,
    "path": "twist.linear",
}

#: The fixed zero request succeeds only when all three configured model ranges
#: include zero; otherwise SetMean returns false and the e-stop fails closed.
_ZERO_CURRENT = {
    "service": "/hydrodynamics/set_current_velocity",
    "type": "uuv_world_ros_plugins_msgs/SetCurrentVelocity",
    "source_name": "set_current_velocity",
    "source_ref": _SET_VELOCITY_DECL,
    "type_ref": _SET_VELOCITY_TYPE,
    "request": {"velocity": 0.0, "horizontal_angle": 0.0, "vertical_angle": 0.0},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"zeroed": "output.success"}},
}


class UuvCurrent(RosDriver):
    device_id = "uuv-current"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R1"
    ros_version = 1
    backends = {"fake": ".fake:FakeUuvCurrent"}
    tags = ["ros", "ros1", "uuv", "underwater", "simulation", "current", "flow", "environment"]
    display_name = "UUV Simulator underwater current environment"
    vendor = "UUV Simulator"
    facts = [
        Fact("UnderwaterCurrentROSPlugin reads the optional namespace SDF element and creates its "
             "ROS node handle from it.", source="upstream_code", ref=_NAMESPACE_SETUP),
        Fact("UnderwaterCurrentROSPlugin advertises a geometry_msgs/TwistStamped flow velocity on "
             "the configured currentVelocityTopic.", source="upstream_code", ref=_FLOW_PUBLISH),
        Fact("UnderwaterCurrentPlugin defaults the flow topic name to current_velocity when the "
             "SDF topic element is absent.", source="upstream_code", ref=_FLOW_DEFAULT),
        Fact("UnderwaterCurrentROSPlugin advertises the relative services set_current_velocity, "
             "set_current_horz_angle and set_current_vert_angle.", source="upstream_code",
             ref=_CURRENT_ROS + ":110-126"),
        Fact("The plugin header includes geometry_msgs/TwistStamped, "
             "uuv_world_ros_plugins_msgs/SetCurrentVelocity and "
             "uuv_world_ros_plugins_msgs/SetCurrentDirection.", source="upstream_code",
             ref=_CURRENT_HEADER + ":33-37"),
        Fact("UpdateCurrentVelocity calls SetMean on the velocity, horizontal-angle and "
             "vertical-angle models and sets success true only when all three calls succeed.",
             source="upstream_code", ref=_SET_VELOCITY_CALLBACK),
        Fact("GaussMarkovProcess::SetMean returns false when the requested mean is outside the "
             "model's configured minimum and maximum.", source="upstream_code", ref=_SET_MEAN),
        Fact("GaussMarkovProcess::Reset sets the process state var to mean, and SetMean calls Reset "
             "after storing an in-range mean.", source="upstream_code", ref=_GAUSS_MARKOV + ":35-49"),
        Fact("GaussMarkovProcess::Update scales var by (1 - step * mu), adds noiseAmp times a uniform "
             "random number in [-0.5, 0.5] and clamps var to the configured min and max.",
             source="upstream_code", ref=_GAUSS_MARKOV + ":74-86"),
        Fact("The velocity model range is read from the constant_current SDF block; it is "
             "deployment configuration.", source="upstream_code", ref=_VELOCITY_MODEL),
        Fact("The horizontal-angle model range is read from the constant_current SDF block; it is "
             "deployment configuration.", source="upstream_code", ref=_HORZ_MODEL),
        Fact("The vertical-angle model range is read from the constant_current SDF block; it is "
             "deployment configuration.", source="upstream_code", ref=_VERT_MODEL),
        Fact("The shipped auv_underwater_world.world configures the current velocity range as 0 "
             "to 5 m/s and the angle ranges as -3.141592653589793238 to 3.141592653589793238 rad "
             "under the hydrodynamics namespace.", source="upstream_code", ref=_WORLD_EXAMPLE),
        Fact("OnUpdateCurrentVel publishes the current flow vector in the /world frame when the "
             "ROS publish period has elapsed.", source="upstream_code", ref=_FLOW_UPDATE),
        Fact("The ROS plugin constructor sets rosPublishPeriod to 0.05 s.", source="upstream_code",
             ref=_PUBLISH_PERIOD),
    ]
    safe_state = (
        "The fixed set_current_velocity request sets the velocity, horizontal-angle and "
        "vertical-angle model means to zero, and SetMean resets each process state to its mean, "
        "so the simulated flow is zero from the next world update while the velocity model's "
        "noiseAmp is zero (with noise it varies about zero within the configured range). It does "
        "not stop the vehicle or the Gazebo world. It is refused when any of the three configured "
        "ranges excludes zero; the velocity mean may then already be zero."
    )
    #: The fake answers the declared endpoints with canned replies and runs no Gazebo world,
    #: Gauss-Markov process, physics, current field or ROS graph.  It is an analytic stand-in, not
    #: a recording of captured traffic.
    fidelity = {
        "engine": "analytic:ROS current-environment contract stand-in (no world or physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies; no world update, Gauss-Markov process, physics or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake answers the declared services and flow topic and runs no ROS node, rosbridge, "
            "Gazebo world, Gauss-Markov process, ocean current field, physics or vehicle dynamics",
            "the real plugin updates the current models on world updates and publishes the flow "
            "vector at a 0.05 s period; the fake replies immediately with a canned vector",
            "the fake maps a commanded mean directly to its flow vector; the real current is the "
            "Gauss-Markov process output and may differ from the mean",
            "the zero-current request requires all three configured model ranges to include zero; "
            "otherwise the service returns success false and the e-stop fails with the latch held",
            "upstream UpdateCurrentVelocity calls SetMean on the velocity, horizontal and vertical "
            "models in that order and stops at the first refusal, so a refused request can leave an "
            "earlier mean changed; the fake checks all three ranges before changing any mean",
            "after SetMean the Gauss-Markov update adds noiseAmp noise and clamps to the configured "
            "range; the fake has no noise, so its zero-current flow is exactly zero",
            "while Gazebo is paused the plugin publishes no flow sample (it publishes on world "
            "updates), so the flow read is refused NOT_READY; the fake always answers",
            "the package exposes the current setters, the flow observation and the zero-current "
            "safe state; the model getter/setter services are out of scope",
            "the endpoint prefix /hydrodynamics is the namespace in the shipped world; the "
            "operator must configure or remap the actual namespace",
            "no live ROS graph, Gazebo world or hardware run was performed; the evidence is "
            "contract_checked only",
        ],
    }
    parameters = {
        "flow_velocity": Field(
            "object", description="Last published flow velocity in the world frame",
            properties={
                "x": Field("number", unit="m/s", description="X flow velocity"),
                "y": Field("number", unit="m/s", description="Y flow velocity"),
                "z": Field("number", unit="m/s", description="Z flow velocity"),
            }),
    }
    reads = {"flow_velocity": _FLOW_READ}
    commands = {
        "x-cap.uuvsimulator.set_current_velocity.v1": _SET_VELOCITY,
        "x-cap.uuvsimulator.set_horizontal_angle.v1": _SET_HORZ,
        "x-cap.uuvsimulator.set_vertical_angle.v1": _SET_VERT,
        "x-cap.uuvsimulator.current_velocity.v1": _FLOW,
        "x-cap.uuvsimulator.zero_current.v1": _ZERO_CURRENT,
    }
    actions = {
        "x-cap.uuvsimulator.set_current_velocity.v1": Action(
            name="set_current_velocity",
            description="Set the simulated current velocity and direction model means",
            input={
                "velocity": Field("number", unit="m/s", description="Current velocity mean",
                                  limit=Limit.operator_required(_VELOCITY_REASON)),
                "horizontal_angle": Field("number", unit="rad", description="Horizontal angle mean",
                                          limit=Limit.operator_required(_ANGLE_REASON)),
                "vertical_angle": Field("number", unit="rad", description="Vertical angle mean",
                                        limit=Limit.operator_required(_ANGLE_REASON)),
            },
            output={"accepted": _ACCEPTED},
            risk="R1",
        ),
        "x-cap.uuvsimulator.set_horizontal_angle.v1": Action(
            name="set_horizontal_angle",
            description="Set the horizontal current-angle model mean",
            input={"angle": Field("number", unit="rad", description="Horizontal angle mean",
                                  limit=Limit.operator_required(_ANGLE_REASON))},
            output={"accepted": _ACCEPTED},
            risk="R1",
        ),
        "x-cap.uuvsimulator.set_vertical_angle.v1": Action(
            name="set_vertical_angle",
            description="Set the vertical current-angle model mean",
            input={"angle": Field("number", unit="rad", description="Vertical angle mean",
                                  limit=Limit.operator_required(_ANGLE_REASON))},
            output={"accepted": _ACCEPTED},
            risk="R1",
        ),
        "x-cap.uuvsimulator.current_velocity.v1": Action(
            name="read_current_velocity",
            verb="read",
            description="Read one published flow-velocity sample",
            output={
                "linear_x": Field("number", unit="m/s", description="X flow velocity"),
                "linear_y": Field("number", unit="m/s", description="Y flow velocity"),
                "linear_z": Field("number", unit="m/s", description="Z flow velocity"),
            },
            risk="R0",
        ),
        "x-cap.uuvsimulator.zero_current.v1": Action(
            name="zero_current",
            description="Zero the three current model means through the fixed acknowledged service",
            safe_state=True,
            cancellable=False,
            output={"zeroed": Field(
                "boolean", description="True when the fixed service returned success")},
            risk="R1",
        ),
    }
    # The input-free fixed service is the acknowledged software stop for the
    # simulated current model; the server latches first and calls it during an e-stop.
    safety_bindings = {"estop": _ZERO_CURRENT}
