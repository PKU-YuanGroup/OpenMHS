"""OpenMHS rosbridge driver for the DAVE underwater simulation environment.

The pinned repository is the Gazebo/ROS 1 DAVE simulation stack.  This package
is a configuration-only :class:`RosDriver` over rosbridge; it declares no
Python native class, imports no ROS, starts no Gazebo world and neither
imports nor runs upstream code.  The operator runs a DAVE world and rosbridge
separately.

Scope: the ocean-current environment published by DAVE's
``dave_gazebo_ros_plugins`` world plugin.  The plugin publishes a stamped
current vector and exposes relative services that read and set the
Gauss-Markov current model in the world namespace.  The package observes the
current vector, reads the velocity and horizontal-angle model parameters, sets
the velocity and both angle means, and offers an input-free zero-current
safe-state action.  The zero-current service sets each global constant-current
model mean (and resets its process variable) to zero; it does not change the
stratified-database and tidal current from which vehicles carrying DAVE's
transient-current model plugin take their flow, pause Gazebo, stop a robot,
keep another ROS client from setting a new current, or prove that the next
world update has run (model review of 2026-11-04).

Every endpoint, type and fact cites the pinned clone at
e54ea16bdaf7d6dbb466cf141846a03f284a44dd.  The fake transport is ROS-free and
all of its state values are placeholders.  This is a model-authored,
unreviewed package: the fake backend is the only backend it can exercise.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references (paths are relative to the clone root)
# ---------------------------------------------------------------------------

_PLUGIN_CPP = "gazebo/dave_gazebo_ros_plugins/src/ocean_current_plugin.cpp"
_PLUGIN_H = "gazebo/dave_gazebo_ros_plugins/include/dave_gazebo_ros_plugins/ocean_current_plugin.h"
_WORLD_CPP = "gazebo/dave_gazebo_world_plugins/src/ocean_current_world_plugin.cc"
_GAUSS_CPP = "gazebo/dave_gazebo_world_plugins/src/gauss_markov_process.cc"
_WORLD = "models/dave_worlds/worlds/dave_ocean_waves_dvl_current_profiling.world"
_SET_CURRENT_SRV = "gazebo/dave_gazebo_ros_plugins/srv/SetCurrentVelocity.srv"
_GET_MODEL_SRV = "gazebo/dave_gazebo_ros_plugins/srv/GetCurrentModel.srv"
_MODEL_CPP = "gazebo/dave_gazebo_model_plugins/src/ocean_current_model_plugin.cc"
_TRANSIENT_XACRO = "urdf/robots/rexrov_description/urdf/rexrov_oberon7_transient_current.xacro"
_STANDARD_XACRO = "urdf/robots/rexrov_description/urdf/rexrov_oberon7.xacro"

#: The plugin publishes the current on the relative currentVelocityTopic, read
#: from the SDF constant_current element.
_TOPIC_REF = f"{_WORLD_CPP}:167-175"
_TOPIC_TYPE_REF = f"{_PLUGIN_H}:36"

#: The ROS plugin's load guard, namespace and node handle.
_ROS_LOAD_REF = f"{_PLUGIN_CPP}:63-77"

#: What the zero-current request does and does not reach (model review of
#: 2026-11-04): the process update, the plugin's other setters, the
#: stratified-database models and their publication, and the per-vehicle
#: transient-current plugin that derives its own current from that database.
_GM_UPDATE_REF = f"{_GAUSS_CPP}:75-87"
_OTHER_SETTERS_REF = f"{_PLUGIN_CPP}:93-163"
_DATABASE_PUB_REF = f"{_PLUGIN_CPP}:170-254"
_STRAT_MODELS_REF = f"{_WORLD_CPP}:376-411"
_GZ_TOPIC_REF = f"{_WORLD_CPP}:291-296"
_ENU_LOG_REF = f"{_WORLD_CPP}:94-96"
_TRANSIENT_SUB_REF = f"{_MODEL_CPP}:209-213"
_TRANSIENT_DEPTH_REF = f"{_MODEL_CPP}:309-336"

#: The get services and their GetCurrentModel type.
_GET_VELOCITY_MODEL_REF = f"{_PLUGIN_CPP}:99-103"
_GET_HORZ_MODEL_REF = f"{_PLUGIN_CPP}:112-115"
_GET_MODEL_TYPE_REF = f"{_PLUGIN_H}:25"

#: The set-current service and its SetCurrentVelocity type.
_SET_CURRENT_REF = f"{_PLUGIN_CPP}:129-133"
_SET_CURRENT_TYPE_REF = f"{_PLUGIN_H}:26"

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_ACK = {
    "success": Field("boolean",
                     description="Native service success flag for the current request"),
}

_CURRENT_VECTOR = Field(
    "object",
    description="Global ocean current vector as published (the clone names both NED and ENU)",
    properties={
        "x": Field("number", unit="m/s", description="World-frame x component"),
        "y": Field("number", unit="m/s", description="World-frame y component"),
        "z": Field("number", unit="m/s", description="World-frame z component"),
    },
)

_CURRENT_OUTPUT = {
    "velocity": _CURRENT_VECTOR,
    "frame_id": Field("string", description="Header frame_id of the TwistStamped sample"),
}


def _model_schema(unit: str, label: str) -> Field:
    return Field(
        "object",
        description=f"Configured Gauss-Markov {label} model",
        properties={
            "mean": Field("number", unit=unit, description=f"Configured {label} mean"),
            "min": Field("number", unit=unit, description=f"Configured {label} lower limit"),
            "max": Field("number", unit=unit, description=f"Configured {label} upper limit"),
            "noise": Field("number", unit=unit, description=f"Configured {label} noise amplitude"),
            "mu": Field("number", unit="1", description="Gauss-Markov process constant"),
        },
    )


_VELOCITY_MODEL = _model_schema("m/s", "velocity")
_ANGLE_MODEL = _model_schema("rad", "horizontal-angle")

# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------

_CURRENT_TOPIC = {
    "topic": "/hydrodynamics/current_velocity",
    "type": "geometry_msgs/TwistStamped",
    "source_name": "current_velocity",
    "source_ref": _TOPIC_REF,
    "type_ref": _TOPIC_TYPE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"velocity": "twist.linear", "frame_id": "header.frame_id"}},
}

_GET_VELOCITY_MODEL = {
    "service": "/hydrodynamics/get_current_velocity_model",
    "type": "dave_gazebo_ros_plugins/GetCurrentModel",
    "source_name": "get_current_velocity_model",
    "source_ref": _GET_VELOCITY_MODEL_REF,
    "type_ref": _GET_MODEL_TYPE_REF,
    "operation": "read",
    "path": "$",
}

_GET_HORZ_MODEL = {
    "service": "/hydrodynamics/get_current_horz_angle_model",
    "type": "dave_gazebo_ros_plugins/GetCurrentModel",
    "source_name": "get_current_horz_angle_model",
    "source_ref": _GET_HORZ_MODEL_REF,
    "type_ref": _GET_MODEL_TYPE_REF,
    "operation": "read",
    "path": "$",
}

_SET_CURRENT = {
    "service": "/hydrodynamics/set_current_velocity",
    "type": "dave_gazebo_ros_plugins/SetCurrentVelocity",
    "source_name": "set_current_velocity",
    "source_ref": _SET_CURRENT_REF,
    "type_ref": _SET_CURRENT_TYPE_REF,
    "success": {"path": "success", "equals": True},
    "args": {
        "velocity": {"from": "input.velocity"},
        "horizontal_angle": {"from": "input.horizontal_angle"},
        "vertical_angle": {"from": "input.vertical_angle"},
    },
}

_ZERO_CURRENT = {
    "service": "/hydrodynamics/set_current_velocity",
    "type": "dave_gazebo_ros_plugins/SetCurrentVelocity",
    "source_name": "set_current_velocity",
    "source_ref": _SET_CURRENT_REF,
    "type_ref": _SET_CURRENT_TYPE_REF,
    "success": {"path": "success", "equals": True},
    "request": {"velocity": 0.0, "horizontal_angle": 0.0, "vertical_angle": 0.0},
}

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

#: The service asks the model to accept a mean inside the configured range.
#: That range is world SDF configuration, not a fixed device bound, so the
#: operator supplies the deployed envelope.
_VELOCITY_LIMIT = Limit.operator_required(
    "the clone reads the velocity model min and max from the world SDF and states no fixed device "
    "bound; the operator supplies the deployed current-speed envelope")
_HORZ_ANGLE_LIMIT = Limit.operator_required(
    "the clone reads the horizontal-angle model min and max from the world SDF and states no fixed "
    "device bound; the operator supplies the deployed horizontal-angle envelope")
_VERT_ANGLE_LIMIT = Limit.operator_required(
    "the clone reads the vertical-angle model min and max from the world SDF and states no fixed "
    "device bound; the operator supplies the deployed vertical-angle envelope")


class Dave(RosDriver):
    device_id = "dave"
    device_kind = "world.sim"
    resource_id = "current"
    resource_title = "DAVE ocean-current environment"
    mode = "simulated"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeDave"}
    tags = ["ros", "ros1", "simulation", "gazebo", "dave", "underwater", "ocean-current"]
    display_name = "DAVE underwater simulation ocean current"
    vendor = "Field Robotics Lab"
    model = "dave_gazebo_ros_plugins ocean current"
    facts = [
        Fact("CMakeLists builds the shared library dave_ocean_current_plugin from "
             "src/ocean_current_plugin.cpp.",
             source="upstream_code",
             ref="gazebo/dave_gazebo_ros_plugins/CMakeLists.txt:81-84"),
        Fact("A shipped world loads libdave_ocean_current_plugin.so with namespace hydrodynamics and "
             "current topic current_velocity.",
             source="upstream_code", ref=f"{_WORLD}:85-88"),
        Fact("The ROS plugin returns without loading when ROS is not initialized, reads the namespace "
             "from the SDF (empty when absent) and builds ros::NodeHandle(ns).",
             source="upstream_code", ref=_ROS_LOAD_REF),
        Fact("The ROS plugin advertises geometry_msgs::TwistStamped on currentVelocityTopic with queue "
             "size 10.",
             source="upstream_code", ref=f"{_PLUGIN_CPP}:79-81"),
        Fact("The world plugin reads constant_current/topic from the SDF and defaults it to the literal "
             "current_velocity.",
             source="upstream_code", ref=_TOPIC_REF),
        Fact("The constructor sets rosPublishPeriod to 0.05 s.",
             source="upstream_code", ref=f"{_PLUGIN_CPP}:27-31"),
        Fact("ConnectWorldUpdateBegin calls OnUpdateCurrentVel, which publishes only after "
             "rosPublishPeriod, stamps frame_id /world and copies the current vector into "
             "twist.linear x, y and z.",
             source="upstream_code", ref=f"{_PLUGIN_CPP}:165-184"),
        Fact("The world plugin's Update sets the current vector to magnitude * cos(h) * cos(v), "
             "magnitude * sin(h) * cos(v) and magnitude * sin(v) from the velocity, horizontal-angle and "
             "vertical-angle processes, under a comment that names the NED frame.",
             source="upstream_code", ref=f"{_WORLD_CPP}:114-129"),
        Fact("The world plugin's Load logs 'WARNING: Current velocity calculated in the ENU frame'.",
             source="upstream_code", ref=_ENU_LOG_REF),
        Fact("The world plugin advertises the Gazebo msgs::Vector3d topic ns/currentVelocityTopic.",
             source="upstream_code", ref=_GZ_TOPIC_REF),
        Fact("The ROS plugin advertises the relative get_current_velocity_model service with the "
             "GetCurrentVelocityModel callback.",
             source="upstream_code", ref=_GET_VELOCITY_MODEL_REF),
        Fact("GetCurrentVelocityModel takes dave_gazebo_ros_plugins::GetCurrentModel and replies with "
             "the velocity model mean, min, max, noise and mu.",
             source="upstream_code", ref=f"{_PLUGIN_CPP}:384-394"),
        Fact("The ROS plugin advertises the relative get_current_horz_angle_model service with the "
             "GetCurrentHorzAngleModel callback.",
             source="upstream_code", ref=_GET_HORZ_MODEL_REF),
        Fact("GetCurrentHorzAngleModel takes GetCurrentModel and replies with the horizontal-angle "
             "model mean, min, max, noise and mu.",
             source="upstream_code", ref=f"{_PLUGIN_CPP}:397-407"),
        Fact("The get_current_vert_angle_model service is advertised with the "
             "GetCurrentHorzAngleModel callback.",
             source="upstream_code", ref=f"{_PLUGIN_CPP}:123-127"),
        Fact("The ROS plugin advertises the relative set_current_velocity service with the "
             "UpdateCurrentVelocity callback.",
             source="upstream_code", ref=_SET_CURRENT_REF),
        Fact("UpdateCurrentVelocity calls SetMean on the velocity, horizontal-angle and vertical-angle "
             "models in a short-circuit && chain and sets success true only when all three calls "
             "return true.",
             source="upstream_code", ref=f"{_PLUGIN_CPP}:319-341"),
        Fact("SetMean returns false when the requested mean is outside the configured min and max; on "
             "success it stores the mean and resets the process variable to it.",
             source="upstream_code", ref=f"{_GAUSS_CPP}:36-50"),
        Fact("GaussMarkovProcess::Update multiplies the process variable by (1 - step * mu), adds "
             "noiseAmp times a uniform draw in [-0.5, 0.5] and clamps the result to [min, max].",
             source="upstream_code", ref=_GM_UPDATE_REF),
        Fact("The ROS plugin also advertises set_current_velocity_model, set_current_horz_angle_model, "
             "set_current_vert_angle_model, set_stratified_current_velocity, set_current_horz_angle, "
             "set_stratified_current_horz_angle, set_current_vert_angle and "
             "set_stratified_current_vert_angle.",
             source="upstream_code", ref=_OTHER_SETTERS_REF),
        Fact("For each stratified-database row the world plugin creates magnitude, horizontal-angle and "
             "vertical-angle Gauss-Markov models whose means come from the row (vertical 0).",
             source="upstream_code", ref=_STRAT_MODELS_REF),
        Fact("Each publish period the ROS plugin also publishes the stratified-database rows with the "
             "tidal harmonic or tidal-table data and the ebb and flood directions.",
             source="upstream_code", ref=_DATABASE_PUB_REF),
        Fact("The transient-current model plugin subscribes to the stratified-current database topic.",
             source="upstream_code", ref=_TRANSIENT_SUB_REF),
        Fact("The transient-current model plugin picks the database row for the vehicle's depth from "
             "the model's world pose.",
             source="upstream_code", ref=_TRANSIENT_DEPTH_REF),
        Fact("rexrov_oberon7_transient_current.xacro loads libdave_ocean_current_model_plugin.so with "
             "flow_velocity_topic hydrodynamics/current_velocity/$(arg namespace) and tide_oscillation "
             "true, and gives libuuv_underwater_object_ros_plugin.so the same flow_velocity_topic.",
             source="upstream_code", ref=f"{_TRANSIENT_XACRO}:82-104"),
        Fact("rexrov_oberon7.xacro gives libuuv_underwater_object_ros_plugin.so the flow_velocity_topic "
             "hydrodynamics/current_velocity.",
             source="upstream_code", ref=f"{_STANDARD_XACRO}:82-84"),
        Fact("For the constant-current velocity model the world plugin reads mean, min, max, mu and "
             "noiseAmp from the SDF and asserts min < max, mean within min and max, mu in [0, 1) and "
             "noiseAmp in [0, 1).",
             source="upstream_code", ref=f"{_WORLD_CPP}:180-204"),
        Fact("The shipped current-profiling world configures the velocity model with mean 0, min 0 and "
             "max 5.0 and both angle models with mean 0, min -3.141592653589793 and max "
             "3.141592653589793, each with mu 0.0 and noiseAmp 0.0.",
             source="upstream_code", ref=f"{_WORLD}:89-111"),
        Fact("SetCurrentVelocity.srv declares float64 velocity, horizontal_angle and vertical_angle "
             "requests and a bool success response.",
             source="upstream_code", ref=f"{_SET_CURRENT_SRV}:16-20"),
        Fact("GetCurrentModel.srv declares float64 mean, min, max, noise and mu response fields.",
             source="upstream_code", ref=f"{_GET_MODEL_SRV}:17-21"),
        Fact("The shipped integrated demo includes gazebo_ros empty_world.launch with use_sim_time "
             "true.",
             source="upstream_code",
             ref="examples/dave_demo_launch/launch/dave_integrated_demo.launch:17-26"),
    ]
    safe_state = (
        "The fixed set_current_velocity(0, 0, 0) request zeroes the global constant-current means and "
        "SetMean resets each process to its mean, so the global current is zero from the next world "
        "update while the velocity noiseAmp is 0; it is refused when a configured range excludes zero "
        "(the velocity mean may then already be zero). Transient-current vehicles keep their "
        "stratified and tidal current, Gazebo keeps running and any ROS client can set a new current."
    )
    fidelity = {
        "engine": "analytic:ROS canned-response fake (no Gazebo physics or current model)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned-response fake with placeholder current vectors and model "
                     "values; it does not advance a Gauss-Markov process, Gazebo world clock or "
                     "trajectory, so it establishes no seeded or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free protocol transport: it answers the declared current topic, the two "
            "get-model services and the set-current service and runs no Gazebo world, DAVE plugin, "
            "physics, sensor or wall-clock loop",
            "the current vector and model values are placeholders; the fake computes the TwistStamped "
            "vector from placeholder magnitude and angles and does not advance the Gauss-Markov process",
            "the set-current fake updates the model means and mirrors the native short-circuit partial "
            "application, but it does not prove that a later world update publishes the requested "
            "current or that the stochastic model remains there",
            "the zero-current request and the e-stop change only the global constant-current models: the "
            "stratified-database models and the tidal data, from which the transient-current model "
            "plugin (rexrov_oberon7_transient_current, smilodon_gazebo_transient_current) computes each "
            "vehicle's own flow topic, are unchanged, so such vehicles keep their current after an "
            "e-stop",
            "after the e-stop any ROS client can set a new current or model through this plugin's "
            "set_current_velocity, set_current_velocity_model, angle and stratified setters; the MHS "
            "latch refuses only this driver's commands",
            "with a non-zero velocity noiseAmp the process random-walks away from zero again within the "
            "configured range after the request; the shipped current-profiling world sets noiseAmp 0",
            "the clone is inconsistent about the frame of the current vector (Update's comment names "
            "NED, Load and the set services log ENU); the driver passes twist.linear through unchanged",
            "the clone publishes /hydrodynamics/current_velocity from the world update callback; the "
            "topic can be silent while the Gazebo world is paused, and the fake instead answers a "
            "subscription immediately",
            "the clone advertises get_current_vert_angle_model with the horizontal-angle callback; the "
            "driver does not expose that broken vertical read, and the vertical angle is visible only "
            "through the current vector",
            "the driver does not expose the stratified-current topics and services, the "
            "spherical-coordinate interface, robot dynamics, Gazebo stepping, pause or reset; those are "
            "NOT COVERED",
            "the upstream namespace hydrodynamics is a shipped world setting; a deployment that uses a "
            "different namespace or remapping must expose the resolved endpoints recorded here",
            "the service request ranges are world configuration; no live site envelope is supplied by "
            "this package",
        ],
    }
    parameters = {
        "current_velocity_model": _VELOCITY_MODEL,
        "horizontal_angle_model": _ANGLE_MODEL,
    }
    reads = {
        "current_velocity_model": _GET_VELOCITY_MODEL,
        "horizontal_angle_model": _GET_HORZ_MODEL,
    }
    commands = {
        "x-cap.field-robotics-lab.current.v1": _CURRENT_TOPIC,
        "x-cap.field-robotics-lab.set_current.v1": dict(
            _SET_CURRENT, result={"map": {"success": "success"}}),
        "x-cap.field-robotics-lab.zero_current.v1": dict(
            _ZERO_CURRENT, result={"map": {"success": "success"}}),
    }
    actions = {
        "x-cap.field-robotics-lab.current.v1": Action(
            name="read_current",
            verb="read",
            description="Read one ocean-current vector sample from the DAVE world",
            output=_CURRENT_OUTPUT,
        ),
        "x-cap.field-robotics-lab.set_current.v1": Action(
            name="set_current",
            description="Set the ocean-current velocity and direction means",
            input={
                "velocity": Field("number", unit="m/s", limit=_VELOCITY_LIMIT,
                                  description="Requested current mean speed"),
                "horizontal_angle": Field("number", unit="rad", limit=_HORZ_ANGLE_LIMIT,
                                          description="Requested horizontal-angle mean"),
                "vertical_angle": Field("number", unit="rad", limit=_VERT_ANGLE_LIMIT,
                                        description="Requested vertical-angle mean"),
            },
            output=_ACK,
        ),
        "x-cap.field-robotics-lab.zero_current.v1": Action(
            name="zero_current",
            safe_state=True,
            description="Set the global constant-current model means to zero with the acknowledged "
                        "service; stratified, tidal and per-vehicle transient currents are unchanged",
            output=_ACK,
        ),
    }
    #: The upstream service sets the three global model means and resets their
    #: process variables.  The runtime latches first; this only removes the
    #: global constant-current forcing from the next world update, not the
    #: stratified or tidal current of transient-current vehicles.
    safety_bindings = {"estop": _ZERO_CURRENT}
