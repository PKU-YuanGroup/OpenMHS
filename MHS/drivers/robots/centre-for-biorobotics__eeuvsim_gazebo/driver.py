"""OpenMHS rosbridge driver for the eeUVsim U-CAT AUV simulator (gh.centre-for-biorobotics/eeuvsim_gazebo).

The pinned repository is a ROS 2 AUV simulator.  ``AUVMotion.py`` integrates the
Fossen dynamics in Python and publishes a ``gazebo_msgs/EntityState`` on
``/ucat/state``; ``moveFins.py`` consumes ``eeuv_sim_interfaces/Flippers`` on
``/hw/flippers_cmd`` and publishes ``FlippersFeedbacks`` on
``/hw/flippers_feedback``.  The README states that Gazebo Classic 11 is used only
for visualization, without physics.  This package is a configuration-only
:class:`RosDriver` over rosbridge: it declares no Python native class, imports no
ROS, and launches neither ROS nor Gazebo.

Scope: the UCAT fin-oscillation interface described by the README quick start
and ``RL_UCAT.py``.  The selected surface is the four-flipper ``Flippers``
publication, the two observations above, and the ``/ucat/reset`` Bool
publication.  The RL script's default end-to-end topic
``/hw/flippers_cmd_e2e`` has no subscriber in this pin, so it is not exposed.

No acknowledged stop exists in the pinned clone.  The e-stop is a
sensed-confirmation stop (SAFE-049, simulated devices only): one zero-amplitude
``Flippers`` publication on ``/hw/flippers_cmd``.  ``/ucat/reset`` is not part
of it.  ``AUVMotion.reset`` zeroes velocity but does not clear the fin command
``moveFins`` stored, so a reset can leave a wrench command in place.
``/ucat/state`` is ``gazebo_msgs/EntityState`` and has no header, so freshness
is arrival from the volatile publisher.  Evidence is the fake backend's
contract check only.  ``connect_microCAT.launch.py`` is not a binding.

Every endpoint, type and fact cites the pinned clone at
``7276ed34215c6b75caf03d6d5144ee550aaf6600``.  The fake transport is ROS-free;
all of its values are placeholders, not device facts or limits.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references (paths are relative to the clone root)
# ---------------------------------------------------------------------------

#: README: the simulator and its ROS 2 pub-sub training environment.
_README_SIM_REF = "README.md:1-8"
#: README: Gazebo Classic is only used for visualization, without physics.
_README_GAZEBO_REF = "README.md:25"
#: README: the UCAT quick start and the RL training command.
_README_QUICK_START_REF = "README.md:30-37"

#: AUVMotion imports gazebo_msgs/EntityState and publishes it on /ucat/state.
_STATE_IMPORT_REF = "eeuv_sim/scripts/AUVMotion.py:16"
_STATE_PUBLISH_REF = "eeuv_sim/scripts/AUVMotion.py:113"
#: AUVMotion subscribes /ucat/reset with std_msgs/Bool.
_RESET_IMPORT_REF = "eeuv_sim/scripts/AUVMotion.py:14"
_RESET_SUBSCRIBE_REF = "eeuv_sim/scripts/AUVMotion.py:96"
#: AUVMotion integrates velocity and position in its timer callback.
_MOTION_LOOP_REF = "eeuv_sim/scripts/AUVMotion.py:295-311"
#: The reset callback and reset() zero the body state and set depth 5.
_RESET_CALLBACK_REF = "eeuv_sim/scripts/AUVMotion.py:417-429"
#: reset() publishes the EntityState and calls /gazebo/set_entity_state.
_RESET_SEND_REF = "eeuv_sim/scripts/AUVMotion.py:447-479"
#: AUVMotion creates the SetEntityState service client on /gazebo/set_entity_state.
_SET_ENTITY_REF = "eeuv_sim/scripts/AUVMotion.py:79"

#: moveFins imports the custom messages.
_FINS_IMPORT_REF = "eeuv_sim/scripts/actuator/moveFins.py:26"
#: moveFins subscribes /hw/flippers_cmd with Flippers and publishes /hw/flippers_feedback.
_FINS_SUBSCRIBE_REF = "eeuv_sim/scripts/actuator/moveFins.py:139"
_FINS_TOPIC_REF = "eeuv_sim/scripts/actuator/moveFins.py:135-139"
_FEEDBACK_PUBLISH_REF = "eeuv_sim/scripts/actuator/moveFins.py:135"
_RESET_JOINTS_REF = "eeuv_sim/scripts/actuator/moveFins.py:140"
#: flippersCallback copies the four per-fin fields without a bound check.
_FINS_CALLBACK_REF = "eeuv_sim/scripts/actuator/moveFins.py:163-169"
#: Internal fin velocity and acceleration clamps of the CPG.
_FINS_CLAMPS_REF = "eeuv_sim/scripts/actuator/moveFins.py:128-130"
#: moveFins sends each fin pose through /gazebo/set_entity_state.
_FINS_SET_STATE_REF = "eeuv_sim/scripts/actuator/moveFins.py:270-294"
#: reset_joints sends the four fins to their initial pose.
_RESET_JOINTS_BODY_REF = "eeuv_sim/scripts/actuator/moveFins.py:358-364"

#: RL_UCAT oscillation action space: amplitudes and zero directions.
_RL_ACTION_SPACE_REF = "eeuv_sim/scripts/RL/RL_UCAT.py:67-71"
#: RL_UCAT fixed frequency and phase offsets.
_RL_CONSTANTS_REF = "eeuv_sim/scripts/RL/RL_UCAT.py:90-91"
#: RL_UCAT publishes the Flippers command and observes state and feedback.
_RL_PUBSUB_REF = "eeuv_sim/scripts/RL/RL_UCAT.py:296-301"
#: pub_action_oci assembles the four flipper objects and publishes them.
_RL_OCI_REF = "eeuv_sim/scripts/RL/RL_UCAT.py:263-279"

#: Message definitions and their documented units.
_FLIPPERS_MSG_REF = "eeuv_sim_interfaces/msg/Flippers.msg:1-2"
_FLIPPER_MSG_REF = "eeuv_sim_interfaces/msg/Flipper.msg:1-14"
_FEEDBACK_MSG_REF = "eeuv_sim_interfaces/msg/FlippersFeedback.msg:1-3"
_FEEDBACKS_MSG_REF = "eeuv_sim_interfaces/msg/FlippersFeedbacks.msg:1-5"

# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------

_VECTOR3 = Field(
    "object",
    description="Three-component vector",
    properties={
        "x": Field("number", unit="1", description="x component"),
        "y": Field("number", unit="1", description="y component"),
        "z": Field("number", unit="1", description="z component"),
    },
)
_POSITION = Field(
    "object",
    description="Position in metres",
    properties={
        "x": Field("number", unit="m", description="Position x in the message frame"),
        "y": Field("number", unit="m", description="Position y in the message frame"),
        "z": Field("number", unit="m", description="Position z in the message frame"),
    },
)
_ORIENTATION = Field(
    "object",
    description="Quaternion orientation (x, y, z, w)",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)
_POSE = Field(
    "object",
    description="EntityState pose",
    properties={"position": _POSITION, "orientation": _ORIENTATION},
)
_LINEAR = Field(
    "object",
    description="Linear velocity in metres per second",
    properties={
        "x": Field("number", unit="m/s", description="Linear velocity x"),
        "y": Field("number", unit="m/s", description="Linear velocity y"),
        "z": Field("number", unit="m/s", description="Linear velocity z"),
    },
)
_ANGULAR = Field(
    "object",
    description="Angular velocity in radians per second",
    properties={
        "x": Field("number", unit="rad/s", description="Angular velocity x"),
        "y": Field("number", unit="rad/s", description="Angular velocity y"),
        "z": Field("number", unit="rad/s", description="Angular velocity z"),
    },
)
_TWIST = Field(
    "object",
    description="EntityState twist",
    properties={"linear": _LINEAR, "angular": _ANGULAR},
)
_ENTITY_STATE_FIELDS = {
    "name": Field("string", description="Entity name"),
    "pose": _POSE,
    "twist": _TWIST,
    "reference_frame": Field("string", description="Frame in which pose and twist are expressed"),
}
_ENTITY_STATE = Field(
    "object",
    description="gazebo_msgs/EntityState as published by AUVMotion",
    properties=_ENTITY_STATE_FIELDS,
)

_FLIPPER_FEEDBACK = Field(
    "object",
    description="One FlippersFeedback message",
    properties={
        "angular_pos": Field("number", unit="rad", description="Fin angular position"),
        "angular_vel": Field("number", unit="rad/s", description="Fin angular velocity"),
        "angular_acc": Field("number", unit="rad/s2", description="Fin angular acceleration"),
    },
)
_FEEDBACKS_FIELDS = {
    "flipper_fr": _FLIPPER_FEEDBACK,
    "flipper_br": _FLIPPER_FEEDBACK,
    "flipper_bl": _FLIPPER_FEEDBACK,
    "flipper_fl": _FLIPPER_FEEDBACK,
}
_FEEDBACKS = Field(
    "object",
    description="FlippersFeedbacks: the four fin feedbacks in FR, BR, BL, FL order",
    properties=_FEEDBACKS_FIELDS,
)

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the message to rosbridge"),
    "confirmed": Field("boolean", description="Always false: a rosbridge publication carries no execution, "
                                               "arrival or stop confirmation"),
}

#: The four fin commands.  The array order and the four fields mirror
#: Flipper.msg; the values are mapped to the Flippers message as-is.
_FIN_INPUT = Field(
    "array",
    length=4,
    description="Four flipper commands in upstream order FR, BR, BL, FL",
    items=Field(
        "object",
        description="One Flipper message: amplitude, frequency, zero direction and phase offset",
        properties={
            "amplitude": Field(
                "number", unit="rad",
                description="Fin oscillation amplitude in radians",
                limit=Limit.operator_required(
                    "no line of the clone bounds Flipper.amplitude: moveFins.py copies it into the CPG without a "
                    "check, and the RL 0..0.85 rad action space is a training envelope, not a runtime clamp; the "
                    "site supplies its fin amplitude envelope"),
            ),
            "frequency": Field(
                "number", unit="Hz",
                description="Fin oscillation frequency in hertz",
                limit=Limit.operator_required(
                    "no line of the clone bounds Flipper.frequency: moveFins.py uses it directly and the RL client's "
                    "2.0 Hz is a client constant, not a runtime clamp; the site supplies its frequency envelope"),
            ),
            "zero_direction": Field(
                "number", unit="rad",
                description="Fin zero direction in radians",
                limit=Limit.operator_required(
                    "no line of the clone bounds Flipper.zero_direction: moveFins.py copies it without a check and "
                    "the RL -pi..pi action space is a training envelope, not a runtime clamp; the site supplies its "
                    "direction envelope"),
            ),
            "phase_offset": Field(
                "number", unit="rad",
                description="Fin oscillation phase offset in radians",
                limit=Limit.operator_required(
                    "Flipper.msg comments the phase offset as 0...2 Pi but moveFins.py does not enforce that range; "
                    "the site supplies its phase offset envelope"),
            ),
        },
    ),
)

_STATE_TOPIC = {
    "topic": "/ucat/state",
    "type": "gazebo_msgs/msg/EntityState",
    "source_ref": _STATE_PUBLISH_REF,
    "type_ref": _STATE_IMPORT_REF,
}
_FEEDBACK_TOPIC = {
    "topic": "/hw/flippers_feedback",
    "type": "eeuv_sim_interfaces/msg/FlippersFeedbacks",
    "source_ref": _FEEDBACK_PUBLISH_REF,
    "type_ref": _FINS_IMPORT_REF,
}
_RESET_TOPIC = {
    "topic": "/ucat/reset",
    "type": "std_msgs/msg/Bool",
    "source_ref": _RESET_SUBSCRIBE_REF,
    "type_ref": _RESET_IMPORT_REF,
    "operation": "publish",
    "message": {"data": True},
}
_FINS_TOPIC = {
    "topic": "/hw/flippers_cmd",
    "type": "eeuv_sim_interfaces/msg/Flippers",
    "source_ref": _FINS_SUBSCRIBE_REF,
    "type_ref": _FINS_IMPORT_REF,
    "operation": "publish",
    "message": {
        "header": {},
        "flippers": [
            {"motor_number": 0, "frequency": 0.0, "zero_direction": 0.0,
             "amplitude": 0.0, "phase_offset": 0.0},
            {"motor_number": 1, "frequency": 0.0, "zero_direction": 0.0,
             "amplitude": 0.0, "phase_offset": 0.0},
            {"motor_number": 2, "frequency": 0.0, "zero_direction": 0.0,
             "amplitude": 0.0, "phase_offset": 0.0},
            {"motor_number": 3, "frequency": 0.0, "zero_direction": 0.0,
             "amplitude": 0.0, "phase_offset": 0.0},
        ],
    },
    "args": {"flippers": {"from": "input.flippers"}},
}

_NO_TWIST_BOUND = (
    "the clone states no at-rest bound for the body twist; the operator supplies the largest magnitude that "
    "counts as stopped"
)

#: Sensed-confirmation stop (SAFE-049).  Zero amplitude is not a stop by itself: moveFins stores the Flippers
#: message (moveFins.py:163-169) and AUVMotion keeps integrating.  /ucat/reset is omitted: reset() zeroes vel and U
#: (AUVMotion.py:423-429) but does not clear that stored fin command, so a reset is not a cleared stop (SAFE-042).
#: EntityState has no header.  The publisher at AUVMotion.py:113 is create_publisher(..., 10), which is volatile.
#: The shipped timer is dt/fast_forward with dt 0.01 (AUVMotion.py:75) and fast_forward 1.0 (rl_setting.yaml:2),
#: so the period is 10 ms.  Three counted samples then span two periods.  That span, compared in milliseconds,
#: lands just under 20, so min_span_ms is 19: a bound of 20 rejects the shipped period.  min_interval_ms 5
#: discards a burst tighter than that.  A fast_forward above 1 shortens the span below 19 ms and the stop fails
#: closed unless the operator lowers min_span_ms to match; a fast_forward above 2 also publishes faster than
#: min_interval_ms 5 and fails closed the same way.  Thresholds are operator_required placeholders.
_SENSED_STOP = {
    "request": [
        {"topic": "/hw/flippers_cmd", "type": "eeuv_sim_interfaces/msg/Flippers", "source_ref": _FINS_SUBSCRIBE_REF,
         "type_ref": _FINS_IMPORT_REF, "timeout_ms": 1000,
         "message": _FINS_TOPIC["message"],
         "description": "four flippers with amplitude 0; moveFins stores amplitude, frequency, zero_direction and phase_offset"},
    ],
    "sources": {
        "state": {
            "topic": "/ucat/state", "type": "gazebo_msgs/msg/EntityState", "source_ref": _STATE_PUBLISH_REF,
            "type_ref": _STATE_IMPORT_REF, "freshness": "arrival", "min_interval_ms": 5,
            "history": {"durability": "volatile", "ref": _STATE_PUBLISH_REF},
            "fill_refs": {
                "twist.linear": "eeuv_sim/scripts/AUVMotion.py:398-400",
                "twist.angular": "eeuv_sim/scripts/AUVMotion.py:401-403",
            },
        },
    },
    "predicate": [
        {"source": "state", "paths": ["twist.linear.x", "twist.linear.y", "twist.linear.z"],
         "name": "body_linear", "unit": "m/s", "norm_max": Limit.operator_required(_NO_TWIST_BOUND)},
        {"source": "state", "paths": ["twist.angular.x", "twist.angular.y", "twist.angular.z"],
         "name": "body_angular", "unit": "rad/s", "norm_max": Limit.operator_required(_NO_TWIST_BOUND)},
    ],
    "consecutive": 3,
    "min_span_ms": 19,
    "max_gap_ms": 500,
    "confirm_within_ms": 1500,
    "description": "zero-amplitude flippers published; body linear and angular twist within the operator's bounds "
                   "in three consecutive fresh samples",
}


class EeuvSimUcat(RosDriver):
    device_id = "eeuvsim-ucat"
    device_kind = "world.sim"
    mode = "simulated"
    # REVIEW.md item 12.  connect_microCAT.launch.py:13-19 starts executable microcatHardwareInterface.py
    # with serial_port /dev/ttyACM0.  That script is not in the clone, and the clone shows no subscriber inside
    # it.  The only /hw/flippers_cmd subscriber in the clone is the simulator (moveFins.py:139).  Whether a
    # physical micro-CAT consumes this topic is for the human reviewer.  The card floor is R0; a fin command
    # that a physical vehicle would also consume is R2.  This package does not bind that launch file.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeEeuvSimUcat"}
    vendor = "Centre for Biorobotics, TalTech"
    model = "U-CAT (UCAT) fin-actuated AUV in eeuv_sim"
    display_name = "eeUVsim U-CAT AUV simulator"
    tags = ["ros", "ros2", "simulation", "auv", "underwater", "ucat", "flipper", "fin", "gazebo"]
    facts = [
        Fact("The README describes eeUVsim as a Fossen-physics multi-platform AUV simulator with dynamics, "
             "reinforcement-learning scripts, robot models and actuator models, trained over ROS 2 pub-sub.",
             source="upstream_code", ref=_README_SIM_REF),
        Fact("The README states that Gazebo 11 Classic is only used for visualization without physics.",
             source="upstream_code", ref=_README_GAZEBO_REF),
        Fact("The UCAT quick start launches spawn_UCAT.launch.py and trains with 'ros2 run eeuv_sim RL_UCAT.py -o'.",
             source="upstream_code", ref=_README_QUICK_START_REF),
        Fact("AUVMotion imports gazebo_msgs/EntityState.", source="upstream_code", ref=_STATE_IMPORT_REF),
        Fact("AUVMotion creates a publisher for gazebo_msgs/EntityState on the absolute /ucat/state topic "
             "with queue size 10.", source="upstream_code", ref=_STATE_PUBLISH_REF),
        Fact("AUVMotion imports std_msgs/Bool.", source="upstream_code", ref=_RESET_IMPORT_REF),
        Fact("AUVMotion subscribes to the absolute /ucat/reset topic with std_msgs/Bool and calls "
             "reset_callback.", source="upstream_code", ref=_RESET_SUBSCRIBE_REF),
        Fact("AUVMotion creates a SetEntityState client on the absolute /gazebo/set_entity_state service.",
             source="upstream_code", ref=_SET_ENTITY_REF),
        Fact("AUVMotion's timer integrates body velocity and position every tick (vel += acc * dt, "
             "pos += pos_dot * dt) and then publishes the state; the loop has no stop or pause flag.",
             source="upstream_code", ref=_MOTION_LOOP_REF),
        Fact("reset_callback calls reset() when the current time differs from the previous reset time by more "
             "than 10000 ns; reset() zeroes pos, vel, acc and U and sets position z to 5.",
             source="upstream_code", ref=_RESET_CALLBACK_REF),
        Fact("reset() builds an EntityState, publishes it on /ucat/state and calls /gazebo/set_entity_state; it "
             "does not stop the moveFins timer or the fin command stream.", source="upstream_code",
             ref=_RESET_SEND_REF),
        Fact("moveFins subscribes to the absolute /hw/flippers_cmd topic with eeuv_sim_interfaces/Flippers "
             "and publishes FlippersFeedbacks on the absolute /hw/flippers_feedback topic.",
             source="upstream_code", ref=_FINS_TOPIC_REF),
        Fact("moveFins subscribes to the absolute /ucat/reset topic with std_msgs/Bool.",
             source="upstream_code", ref=_RESET_JOINTS_REF),
        Fact("moveFins.reset_joints sends the four fins to their initial poses but leaves the fin timer "
             "running.", source="upstream_code", ref=_RESET_JOINTS_BODY_REF),
        Fact("flippersCallback copies amplitude, frequency, zero_direction and phase_offset from each of the four "
             "Flipper messages without checking any bound.", source="upstream_code", ref=_FINS_CALLBACK_REF),
        Fact("The Flipper message comments motor_number as 0..3, frequency in Hz, zero_direction and amplitude "
             "in rad, and phase_offset as 0...2 Pi.", source="upstream_code", ref=_FLIPPER_MSG_REF),
        Fact("The Flippers message carries a std_msgs/Header and an array of Flipper messages.",
             source="upstream_code", ref=_FLIPPERS_MSG_REF),
        Fact("The FlippersFeedback message carries angular_pos, angular_vel and angular_acc.",
             source="upstream_code", ref=_FEEDBACK_MSG_REF),
        Fact("FlippersFeedbacks carries a Header and the four named feedbacks flipper_fr, flipper_br, "
             "flipper_bl and flipper_fl.", source="upstream_code", ref=_FEEDBACKS_MSG_REF),
        Fact("RL_UCAT's oscillation action space bounds the four amplitudes to 0..0.85 and the four zero "
             "directions to -pi..pi in the order FR, BR, BL, FL; this is the training action space, not a clamp "
             "in moveFins.", source="upstream_code", ref=_RL_ACTION_SPACE_REF),
        Fact("RL_UCAT uses a single frequency of 2.0 Hz and phase offsets [0.0, 3.14159, 0, 3.14159] for the four "
             "fins.", source="upstream_code", ref=_RL_CONSTANTS_REF),
        Fact("RL_UCAT's SendActionROS2 creates publishers on /ucat/reset, /hw/flippers_cmd_e2e and "
             "/hw/flippers_cmd, and subscribes /ucat/state, /hw/flippers_feedback and /ucat/depth_vel.",
             source="upstream_code", ref=_RL_PUBSUB_REF),
        Fact("pub_action_oci writes each Flipper's frequency, amplitude, zero_direction and phase_offset and "
             "publishes the Flippers message; it reads no acknowledgement.", source="upstream_code", ref=_RL_OCI_REF),
        Fact("moveFins clamps its internal fin velocity to pi * 16 rad/s and its internal acceleration to "
             "64 rad/s^2; these are simulation-loop clamps, not bounds on the Flippers command.",
             source="upstream_code", ref=_FINS_CLAMPS_REF),
        Fact("moveFins sends each fin pose through /gazebo/set_entity_state with reference_frame base_link.",
             source="upstream_code", ref=_FINS_SET_STATE_REF),
    ]
    #: One request step at timeout_ms 1000 plus confirm_within_ms 1500.
    estop_latency_ms = 2500
    safe_state = (
        "Simulated only: zero-amplitude flippers are on /hw/flippers_cmd and the /ucat/state linear and angular "
        "twist are inside the operator bounds for three fresh samples."
    )
    fidelity = {
        "engine": "analytic:ROS-free rosbridge contract stand-in (no dynamics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies with no Fossen integration, fin CPG, Gazebo scene or wall-clock "
                     "timer; placeholder state does not establish a trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free analytic contract stand-in, not the upstream simulator and not a recording of "
            "captured traffic: it answers the declared topics with placeholder messages and runs no Fossen "
            "dynamics, fin CPG, Gazebo scene, ROS graph or timer",
            "the /ucat/state pose and twist and all /hw/flippers_feedback values are placeholders and do not "
            "follow a fin command; the real pose comes from AUVMotion's integration",
            "AUVMotion's Python dynamics runs at 0.01 s divided by the configured fast_forward value "
            "(AUVMotion.py:75-76,295-311); the fake declares no timestep and no pacing",
            "the /ucat/reset Bool publication is recorded but not executed; the fake does not zero a simulated "
            "state, publish a reset EntityState or call /gazebo/set_entity_state",
            "the e-stop is a sensed-confirmation stop (SAFE-049, simulated only): zero-amplitude Flippers on "
            "/hw/flippers_cmd, confirmed only by three fresh /ucat/state twist samples (arrival freshness, "
            "min_interval_ms 5, publisher at AUVMotion.py:113); /ucat/reset is not a request step because reset() "
            "does not clear the fin command moveFins stored (AUVMotion.py:423-429, moveFins.py:163-169)",
            "the shipped timer is 10 ms (dt 0.01 at AUVMotion.py:75, fast_forward 1.0 at rl_setting.yaml:2). Three "
            "counted samples span two periods. That span, compared in milliseconds, lands just under 20, so "
            "min_span_ms is 19; a bound of 20 rejects the shipped period. A fast_forward above 1 shortens the span "
            "below 19 ms and the stop fails closed unless the operator lowers min_span_ms to match. A fast_forward "
            "above 2 also publishes faster than min_interval_ms 5 and fails closed. A replay spaced at or above "
            "5 ms is not distinguished from live samples",
            "the RL_UCAT default end-to-end topic /hw/flippers_cmd_e2e has no subscriber at this pin "
            "(moveFins.py:139 subscribes /hw/flippers_cmd only), so it is not exposed as a control capability",
            "the LAUV and Blue thruster/wing topics, /ucat/force_fins, /ucat/force_fins_debug, /ucat/depth_vel, "
            "/gazebo/set_entity_state, Gazebo, RViz and the RL training stack are NOT COVERED",
            "no ROS graph, Gazebo process or hardware is contacted; a live run needs the operator's ROS 2 graph "
            "and rosbridge endpoint",
        ],
    }

    # Resource state: the UCAT state and the four named fin feedbacks.
    parameters = {
        "name": Field("string", description="EntityState name as published by AUVMotion"),
        "pose": _POSE,
        "twist": _TWIST,
        "reference_frame": Field("string", description="EntityState reference frame"),
        "flipper_fr": _FLIPPER_FEEDBACK,
        "flipper_br": _FLIPPER_FEEDBACK,
        "flipper_bl": _FLIPPER_FEEDBACK,
        "flipper_fl": _FLIPPER_FEEDBACK,
    }
    reads = {
        "name": dict(_STATE_TOPIC, path="name", timeout_ms=2000),
        "pose": dict(_STATE_TOPIC, path="pose", timeout_ms=2000),
        "twist": dict(_STATE_TOPIC, path="twist", timeout_ms=2000),
        "reference_frame": dict(_STATE_TOPIC, path="reference_frame", timeout_ms=2000),
        "flipper_fr": dict(_FEEDBACK_TOPIC, path="flipper_fr", timeout_ms=2000),
        "flipper_br": dict(_FEEDBACK_TOPIC, path="flipper_br", timeout_ms=2000),
        "flipper_bl": dict(_FEEDBACK_TOPIC, path="flipper_bl", timeout_ms=2000),
        "flipper_fl": dict(_FEEDBACK_TOPIC, path="flipper_fl", timeout_ms=2000),
    }
    commands = {
        "x-cap.centre-for-biorobotics.fin_oscillation.v1": _FINS_TOPIC,
        "x-cap.centre-for-biorobotics.auv_state.v1": dict(
            _STATE_TOPIC, operation="subscribe", path="$",
            result={"map": {
                "name": "name",
                "pose": "pose",
                "twist": "twist",
                "reference_frame": "reference_frame",
            }},
        ),
        "x-cap.centre-for-biorobotics.fin_feedback.v1": dict(
            _FEEDBACK_TOPIC, operation="subscribe", path="$",
            result={"map": {
                "flipper_fr": "flipper_fr",
                "flipper_br": "flipper_br",
                "flipper_bl": "flipper_bl",
                "flipper_fl": "flipper_fl",
            }},
        ),
        "x-cap.centre-for-biorobotics.reset.v1": _RESET_TOPIC,
    }
    actions = {
        "x-cap.centre-for-biorobotics.fin_oscillation.v1": Action(
            name="set_fin_oscillation",
            verb="invoke",
            description="Publish one Flippers message with the four fin oscillation commands on /hw/flippers_cmd. "
                        "The receipt confirms only that rosbridge accepted the publication, not that moveFins "
                        "applied it or that the AUV moved or stopped.",
            input={"flippers": _FIN_INPUT},
            output=_PUBLISHED,
        ),
        "x-cap.centre-for-biorobotics.auv_state.v1": Action(
            name="read_auv_state",
            verb="read",
            description="Read one gazebo_msgs/EntityState sample published by AUVMotion on /ucat/state",
            output=_ENTITY_STATE_FIELDS,
        ),
        "x-cap.centre-for-biorobotics.fin_feedback.v1": Action(
            name="read_fin_feedback",
            verb="read",
            description="Read one FlippersFeedbacks sample published by moveFins on /hw/flippers_feedback",
            output=_FEEDBACKS_FIELDS,
        ),
        "x-cap.centre-for-biorobotics.reset.v1": Action(
            name="publish_reset",
            verb="invoke",
            description="Publish one std_msgs/Bool data=true reset request on /ucat/reset. This is an "
                        "unacknowledged publication: AUVMotion's reset callback and moveFins' reset_joints may be "
                        "triggered, but the driver receives no completion, and the fin timer is not stopped.",
            output=_PUBLISHED,
        ),
    }
    safety_bindings = {"sensed_stop": _SENSED_STOP}
