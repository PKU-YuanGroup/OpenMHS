"""OpenMHS rosbridge driver for the Webots gym_env bridge (gh.alexanderkeijzer/ros-gym-env-webots).

The pinned upstream is the C++ ROS 1 node ``gym_env_webots_node``.  It is the
ROS side of the external ``gym_env`` environment: it subscribes normalized
joint actions on ``/joint_actuators/value``, publishes nine joint positions on
``/joint_sensors/value``, advances Webots through the ``/webots/step`` service,
resets through ``/webots/reset`` and computes the environment reward through
``/reward``.  The shipped launch file starts the Webots world and this node;
this package only declares the rosbridge surface.  The operator runs the
Webots world, the node and rosbridge separately.

The primary command is one environment step as the node's gym_env client
performs it: publish the action vector, call ``/webots/step``, then read a
fresh joint sample (a RosDriver publish-then-step command, ``then``).  The
publication alone changes nothing visible: the world advances only on a
time_step call.

Every endpoint, type and fact cites the pinned clone at
6cc613bdee4bad0adb157230df51a9bacdf621e4.  The fake transport is ROS-free;
no ROS graph, Webots engine or hardware is contacted by this package.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references
# ---------------------------------------------------------------------------

_NODE = "src/gym_env_webots_node.cpp"

#: The node includes the gym_env message/service headers (lines 15-21) and the
#: webots_ros service/header types used by its clients.
_TYPES_REF = f"{_NODE}:9-21"

#: The sensor publisher is advertised on the absolute /joint_sensors/value topic.
_SENSOR_PUB_REF = f"{_NODE}:259"
#: The sensor callback fills observations and publishes the SensorMessage.
_SENSOR_CALLBACK_REF = f"{_NODE}:58-63"

#: The action subscriber is on the absolute /joint_actuators/value topic.
_ACTION_SUB_REF = f"{_NODE}:258"
#: The actuator callback consumes actions[i] as a normalized increment.
_ACTION_CALLBACK_REF = f"{_NODE}:117-125"
#: The registered action space is -1.0 .. 1.0 for the nine motors.
_ACTION_SPACE_REF = f"{_NODE}:108-113"

#: The environment step service.
_STEP_REF = f"{_NODE}:253"
_STEP_CALLBACK_REF = f"{_NODE}:144-164"

#: The reset service and its callback.
_RESET_REF = f"{_NODE}:255"
_RESET_CALLBACK_REF = f"{_NODE}:171-195"

#: The reward service and its callback.
_REWARD_REF = f"{_NODE}:256"
_REWARD_CALLBACK_REF = f"{_NODE}:197-208"

#: The close service is a log-only callback: it is not a stop path.
_CLOSE_CALLBACK_REF = f"{_NODE}:166-169"

#: Number and order of the motors.
_MOTOR_NUMBER_REF = f"{_NODE}:25"
_MOTOR_NAMES_REF = f"{_NODE}:44-46"

#: Clients and step request set in main().
_CLIENTS_REF = f"{_NODE}:241-243"

#: The service and topic advertisements in main().
_SERVICES_REF = f"{_NODE}:250-256"
_TOPICS_REF = f"{_NODE}:258-259"

#: The shipped launch starts Webots in realtime mode on the Panda world.
_LAUNCH_REF = "launch/webots_p-rob3.launch:5-13"

#: The Panda world fixes the Webots basic time step and uses the "ros" controller.
_WORLD_REF = "worlds/panda.wbt:8-64"

#: The package declares the external gym_env/webots_ros dependencies.
_PACKAGE_REF = "package.xml:52-63"

#: The Panda PROTO declares the two finger joints as LinearMotor devices.
_FINGER_MOTOR_REF = "protos/Panda.proto:1348-1351"

# ---------------------------------------------------------------------------
# Units and limits
# ---------------------------------------------------------------------------

#: actuatorSpacesCallback registers a nine-element action space whose low is
#: -1.0 and high is 1.0.  The callback itself scales each value by
#: motorRange/20 and clamps the resulting joint setpoint, so these are the
#: normalized action bounds the node advertises to the gym_env client.
_ACTION_LIMIT = Limit(
    min=-1.0,
    max=1.0,
    source="upstream_code",
    ref=_ACTION_SPACE_REF,
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_ACTIONS = Field(
    "array",
    unit="1",
    length=9,
    description="Nine normalized joint action increments in panda_joint1..7, panda_finger_joint1..2 order",
    items=Field(
        "number",
        unit="1",
        description="One normalized action increment; the node adds motorRange*action/20 to its setpoint",
        limit=_ACTION_LIMIT,
    ),
)

#: Seven RotationalMotor arm joints and two LinearMotor finger joints: the
#: elements do not share one unit, so the array declares none.
_POSITIONS = Field(
    "array",
    length=9,
    description=("Nine joint positions in panda_joint1..7, panda_finger_joint1..2 order: seven arm joint "
                 "angles (RotationalMotor, radians) and two finger joint positions (LinearMotor)"),
    items=Field("number", description="One joint position as the node's SensorMessage carries it"),
)

_OBSERVATIONS = {"observations": _POSITIONS}

_ACTED = {
    "published": Field("boolean", description="True when the driver handed the action message to rosbridge"),
    "confirmed": Field("boolean",
                       description=("Always false: the action publication itself has no execution acknowledgement, "
                                    "and neither the step reply nor the observation proves that the node applied "
                                    "it before the step")),
    "stepped": Field("boolean",
                     description="True when the /webots/step callback acknowledged one time_step after the action"),
    "observations": _POSITIONS,
}

_STEPPED = {
    "stepped": Field("boolean",
                     description="True when the /webots/step callback returned success for one time_step request"),
}

_RESET_DONE = {
    "reset": Field("boolean",
                   description="True when the /webots/reset callback returned success after simulation_reset"),
}

_REWARD = {
    "reward": Field("number", unit="1",
                    description="The /reward callback's negative sum of joint distances from range midpoints"),
}

# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------

#: Nine joint positions arrive on the node's own SensorMessage publisher.  The
#: message field is ``observations`` (the callback builds the vector there).
_JOINT_STATE = {
    "topic": "/joint_sensors/value",
    "type": "gym_env/SensorMessage",
    "source_name": "/joint_sensors/value",
    "source_ref": _SENSOR_PUB_REF,
    "type_ref": _TYPES_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"observations": "output.observations"}},
    "timeout_ms": 2000,
}

#: One Webots time_step request.  stepCallback returns true only after the
#: robot/time_step client reports response.success (the callback retries until
#: then).  The gym_env StepEnv response fields are not defined in this clone;
#: the empty application predicate is the declared empty-response contract.
_STEP = {
    "service": "/webots/step",
    "type": "gym_env/StepEnv",
    "source_name": "/webots/step",
    "source_ref": _STEP_REF,
    "type_ref": _TYPES_REF,
    "request": {},
    "success": {"path": "$", "equals": {}},
    "result": {"stepped": {"value": True}},
}

#: One environment step as the gym_env client performs it: the action vector
#: is published on /joint_actuators/value (actuatorCommandCallback updates the
#: node's setpoints and calls each joint's set_position), the /webots/step
#: service is called once (the Panda controller runs with --synchronize, so the
#: world advances only on time_step calls) and a fresh /joint_sensors/value
#: sample is read after the step was acknowledged.  The whole sequence shares
#: this command's 5 s budget (a package choice); each stage keeps its own bound.
#: rosbridge forwards the publication and the step call over different ROS
#: connections, and the node serves both from ros::spin() (253, 258, 265), so
#: the node may run the step before the action callback (model review).
_ACTION_STEP = {
    "topic": "/joint_actuators/value",
    "type": "gym_env/ActuatorMessage",
    "source_name": "/joint_actuators/value",
    "source_ref": _ACTION_SUB_REF,
    "type_ref": _TYPES_REF,
    "operation": "publish",
    "message": {"actions": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
    "args": {"actions": {"from": "input.actions"}},
    "timeout_ms": 5000,
    "then": {
        "step": {
            "service": "/webots/step",
            "type": "gym_env/StepEnv",
            "source_name": "/webots/step",
            "source_ref": _STEP_REF,
            "type_ref": _TYPES_REF,
            "request": {},
            "success": {"path": "$", "equals": {}},
            "timeout_ms": 2000,
        },
        "observe": {
            "topic": "/joint_sensors/value",
            "type": "gym_env/SensorMessage",
            "source_name": "/joint_sensors/value",
            "source_ref": _SENSOR_PUB_REF,
            "type_ref": _TYPES_REF,
            "path": "observations",
            "timeout_ms": 2000,
        },
    },
    "result": {"map": {"published": "output.published", "confirmed": "output.confirmed",
                       "stepped": "output.stepped", "observations": "output.observation"}},
}

#: One Webots supervisor simulation_reset followed by at least two 8 ms
#: time_step calls and sensor re-initialization.  The callback returns false
#: when the reset client reports failure; the service transport result then
#: fails the call.  It never clears motorSetPoints (model review).
_RESET = {
    "service": "/webots/reset",
    "type": "gym_env/ResetEnv",
    "source_name": "/webots/reset",
    "source_ref": _RESET_REF,
    "type_ref": _TYPES_REF,
    "request": {},
    "success": {"path": "$", "equals": {}},
    "result": {"reset": {"value": True}},
}

#: The reward callback returns response.reward, a float computed from the
#: cached sensor_values array.
_REWARD_READ = {
    "service": "/reward",
    "type": "gym_env/GetReward",
    "source_name": "/reward",
    "source_ref": _REWARD_REF,
    "type_ref": _TYPES_REF,
    "operation": "read",
    "request": {},
    "result": {"map": {"reward": "reward"}},
}


class RosGymEnvWebots(RosDriver):
    device_id = "ros-gym-env-webots"
    device_kind = "world.sim"
    mode = "simulated"
    #: A joint-action capability on a robot arm is at least R2 even when the
    #: target is an isolated Webots world; the card floor is R0.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeRosGymEnvWebots"}
    display_name = "Webots gym_env Panda bridge"
    vendor = "alexanderkeijzer"
    model = "Panda in Webots"
    tags = ["ros", "ros1", "webots", "simulation", "gym", "panda", "robot-arm", "joint-action"]
    facts = [
        Fact("The node includes the gym_env RegisterSpaces, SensorMessage, ActuatorMessage, CloseEnv, "
             "ResetEnv, StepEnv and GetReward headers together with the webots_ros get_bool, get_float, "
             "set_int, set_float and Float64Stamped headers.", source="upstream_code", ref=_TYPES_REF),
        Fact("MOTOR_NUMBER is 9.", source="upstream_code", ref=_MOTOR_NUMBER_REF),
        Fact("The motor_names array names the seven Panda arm joints and the two finger joints in the order "
             "panda_joint1 through panda_joint7 followed by panda_finger_joint1 and panda_finger_joint2.",
             source="upstream_code", ref=_MOTOR_NAMES_REF),
        Fact("sensorCallback stores each Float64Stamped value in sensor_values and publishes a SensorMessage "
             "carrying all nine values.", source="upstream_code", ref=_SENSOR_CALLBACK_REF),
        Fact("initSensors calls each <model>/<joint>_sensor/enable service with value 80 and, when the call "
             "succeeds, subscribes to that sensor's Float64Stamped value topic and busy-waits until the "
             "subscription has a publisher.", source="upstream_code", ref=f"{_NODE}:65-79"),
        Fact("sensorSpacesCallback returns motorMin-2e-5 as low, motorMax+2e-5 as high and the topic "
             "/joint_sensors/value.", source="upstream_code", ref=f"{_NODE}:94-99"),
        Fact("actuatorSpacesCallback returns a nine-element action space with low -1.0 and high 1.0 and the "
             "topic /joint_actuators/value.", source="upstream_code", ref=_ACTION_SPACE_REF),
        Fact("actuatorCommandCallback adds motorRange[i]*actions[i]/20 to each setpoint, clamps the setpoint "
             "to [motorMin[i], motorMax[i]] and calls the joint set_position service.",
             source="upstream_code", ref=_ACTION_CALLBACK_REF),
        Fact("initActuators reads each joint's get_max_position and get_min_position, stores max-1e-5 and "
             "min+1e-5, and computes range as max-min.", source="upstream_code", ref=f"{_NODE}:127-142"),
        Fact("stepCallback calls the stepEnv client with no retry limit until a call succeeds with "
             "response.success, and then returns true.", source="upstream_code", ref=_STEP_CALLBACK_REF),
        Fact("resetCallback returns false unless the resetEnv get_bool call succeeds with value true; it then "
             "calls stepEnv with value 8 once, ignoring the result, calls it again until one call succeeds, "
             "sleeping 0.5 s after each failure, calls initSensors and returns true.",
             source="upstream_code", ref=_RESET_CALLBACK_REF),
        Fact("closeCallback logs Close and returns true without calling any device method.",
             source="upstream_code", ref=_CLOSE_CALLBACK_REF),
        Fact("rewardCallback computes the negative sum over the nine joints of the distance from each joint "
             "position to the middle of its range and returns it in response.reward.",
             source="upstream_code", ref=_REWARD_CALLBACK_REF),
        Fact("main creates the reset client on <model>/supervisor/simulation_reset and the step client on "
             "<model>/robot/time_step, and sets the step request value to 80 ms.",
             source="upstream_code", ref=_CLIENTS_REF),
        Fact("The node advertises /joint_sensors, /joint_actuators, /webots/step, /webots/close, "
             "/webots/reset and /reward.", source="upstream_code", ref=_SERVICES_REF),
        Fact("The node subscribes /joint_actuators/value and advertises /joint_sensors/value.",
             source="upstream_code", ref=_TOPICS_REF),
        Fact("main subscribes /joint_actuators/value with a queue size of 1, advertises /joint_sensors/value with a "
             "queue size of 1 and then calls ros::spin().", source="upstream_code", ref=f"{_NODE}:258-265"),
        Fact("The launch file includes webots_ros webots.launch in realtime mode with the panda.wbt world "
             "and starts the gym_env_webots_node executable.", source="upstream_code", ref=_LAUNCH_REF),
        Fact("The Panda world fixes basicTimeStep to 8 ms and instantiates the Panda robot with controller "
             "\"ros\".", source="upstream_code", ref=_WORLD_REF),
        Fact("The Panda robot runs the ros controller with the --synchronize controller argument and "
             "supervisor TRUE.", source="upstream_code", ref="worlds/panda.wbt:61-68"),
        Fact("The Panda PROTO declares synchronization with the default TRUE.", source="upstream_code",
             ref="protos/Panda.proto:15"),
        Fact("motorSetPoints is a global array initialised to zero.", source="upstream_code",
             ref=f"{_NODE}:31"),
        Fact("The Panda PROTO declares panda_finger_joint1 as a LinearMotor with maxPosition 0.04.",
             source="upstream_code", ref=_FINGER_MOTOR_REF),
        Fact("The Panda PROTO declares panda_finger_joint2 as a LinearMotor with maxPosition 0.04.",
             source="upstream_code", ref="protos/Panda.proto:1413-1416"),
        Fact("package.xml declares build/exec dependencies on gym_env, roscpp, std_msgs and webots_ros.",
             source="upstream_code", ref=_PACKAGE_REF),
    ]
    #: The reset restores the initial simulated world and is the declared
    #: input-free safe-state action.  It is not a Webots process stop and it
    #: does not fence other ROS clients.
    safe_state = (
        "The safe-state action is the fixed /webots/reset service: its reply acknowledges that the Webots "
        "supervisor accepted simulation_reset and that a later 8 ms time_step succeeded (at least two run). The "
        "Panda's ros controller runs with --synchronize, the configuration in which the world advances only on "
        "time_step calls; MHS sends none after the latch, but other ROS clients are not fenced. motorSetPoints "
        "is not cleared, and what Webots restores is outside the clone."
    )
    #: The fake is an event-driven ROS-free stand-in, not a Webots run.
    fidelity = {
        "engine": "analytic:ROS-free fake of the node's setpoint arithmetic (no Webots physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Canned service replies and an analytic setpoint model; no Webots engine, Panda physics, "
                     "joint controller, contact, sensor, clock or wall-clock pacing, and no trajectory replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free transport: it answers the declared endpoints from placeholder state and "
            "runs no Webots engine, Panda model, joint controller, contacts, sensors or pacing",
            "an action publication updates the fake's copy of the node's setpoints exactly as "
            "actuatorCommandCallback does (motorRange*action/20, clamped to the joint range); the joint limits "
            "are placeholders copied from the Panda PROTO (finger minimum 0, not stated), not values read "
            "through get_min_position/get_max_position",
            "a fake /webots/step moves every fake joint to its last set_position target in one step; real "
            "Webots joints move under their motor velocity and force limits over many 8 ms steps, so a real "
            "observation after one 80 ms step need not equal the setpoint",
            "a fake /joint_sensors/value subscription answers at once; whether the live node publishes a "
            "sample after a step's reply depends on the webots_ros controller (outside the clone), and the "
            "act-and-step receipt is unknown when none arrives within its 2 s observation bound",
            "the fake applies an action publication before it answers the next step (unless its "
            "action_after_step switch is set); live, rosbridge forwards the publication and the /webots/step "
            "call over different ROS connections and the node serves both from ros::spin() (253, 258, 265), so "
            "the step may run before actuatorCommandCallback, and the first action after rosbridge advertises "
            "/joint_actuators/value may be lost before the node's subscription connects: a completed "
            "act-and-step receipt's observation need not reflect the action",
            "the /webots/step and /webots/reset replies are immediate; the upstream calls the Webots "
            "robot/time_step client and the supervisor simulation_reset client, which the fake does not model",
            "model review: resetCallback retries its time_step call every 0.5 s and initSensors busy-waits for "
            "publishers without a bound (171-195, 65-79), so a reset can outlast the 2 s default binding "
            "timeout and the e-stop then reports SAFE_STATE_UNREACHED; motorSetPoints (31, 117-125) survives "
            "the reset, so the first action after it jumps back toward the pre-reset setpoints",
            "the upstream basicTimeStep is 8 ms and the node requests an 80 ms step; the fake has no physics "
            "timestep and runs no wall-clock loop",
            "the upstream /reward callback uses cached sensor_values and does not itself step the simulation; "
            "the fake returns a fixed placeholder reward",
            "/joint_sensors and /joint_actuators RegisterSpaces calls, /webots/close, the model_name topic, "
            "the external gym_env package and ROS namespace remapping are outside this package's declared "
            "surface",
            "no Webots engine, ROS graph, rosbridge deployment or hardware was contacted by this package; the "
            "only evidence is the fake backend",
        ],
    }

    #: The environment reset is an ordinary x-cap action; it is not a safety
    #: binding because the callback does not stop the Webots process or fence
    #: other ROS clients.
    commands = {
        "x-cap.alexanderkeijzer.joint_observation.v1": _JOINT_STATE,
        "x-cap.alexanderkeijzer.action_step.v1": _ACTION_STEP,
        "x-cap.alexanderkeijzer.step.v1": _STEP,
        "x-cap.alexanderkeijzer.reset.v1": _RESET,
        "x-cap.alexanderkeijzer.reward.v1": _REWARD_READ,
    }
    actions = {
        "x-cap.alexanderkeijzer.joint_observation.v1": Action(
            name="read_joint_positions",
            verb="read",
            description="Read one fresh gym_env/SensorMessage joint-position sample",
            output=_OBSERVATIONS,
        ),
        "x-cap.alexanderkeijzer.action_step.v1": Action(
            name="act_and_step",
            verb="invoke",
            risk="R2",
            description=("Publish one normalized nine-joint action vector, request one Webots time_step and read "
                         "the joint positions after it; a failure after the publication is an unknown outcome, and "
                         "the observation does not prove that the node applied the action before the step"),
            input={"actions": _ACTIONS},
            output=_ACTED,
        ),
        "x-cap.alexanderkeijzer.step.v1": Action(
            name="step_simulation",
            verb="invoke",
            description="Request one Webots robot/time_step advance through the gym_env step service",
            output=_STEPPED,
        ),
        "x-cap.alexanderkeijzer.reset.v1": Action(
            name="reset_simulation",
            verb="invoke",
            safe_state=True,
            description="Reset the Webots simulation through the gym_env reset service",
            output=_RESET_DONE,
        ),
        "x-cap.alexanderkeijzer.reward.v1": Action(
            name="read_reward",
            verb="read",
            description="Read the gym_env reward scalar computed from the cached joint positions",
            output=_REWARD,
        ),
    }
    #: The safe state is the input-free reset Action in ``actions``; no
    #: safety_bindings service is declared because the node has no stop path.
    safety_bindings = {}
