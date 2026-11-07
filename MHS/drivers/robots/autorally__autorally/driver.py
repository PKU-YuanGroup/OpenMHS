"""OpenMHS rosbridge driver for the AutoRally Gazebo simulation (gh.autorally/autorally).

The pinned repository is a ROS 1 / Gazebo mobile-robot stack.  This package is a
configuration-only :class:`RosDriver`; it declares no Python native class, does
not launch Gazebo, and does not import or execute any upstream node.

The selected runtime surface is the Gazebo simulation controller
(``autorally_controller.py``) and the constant-speed controller nodelet:

* ``/constantSpeedController/speedCommand`` (``std_msgs/Float64``) is the
  documented target-velocity input in m/s.  The constant-speed controller stores
  it with no acknowledgement and turns it into a
  ``constantSpeedController/chassisCommand`` publication;
* ``/runstop`` (``autorally_msgs/runstop``) is the controller's motion-enable
  input.  The controller ANDs every received sender's ``motionEnabled``;
* ``/chassisState`` (``autorally_msgs/chassisState``) and ``/wheelSpeeds``
  (``autorally_msgs/wheelSpeeds``) are explicit fresh observations.

The clone registers no ROS service or action that stops the simulated base.
The e-stop is a sensed-confirmation stop (SAFE-049, simulated only): it publishes
a zero speedCommand, then ``/runstop`` with sender ``openmhs`` and
``motionEnabled`` false, and it is achieved only when fresh ``/wheelSpeeds``
samples sit at or below the operator's absolute bound.  The zero is
unacknowledged and another publisher can overwrite it (``README.md:170``), and a
false runstop forces throttle to 0 without clearing the stored Float64
(``autorally_controller.py:345-348``).  This package therefore offers no
re-enable (SAFE-042, REVIEW.md item 13).  The operator recovers outside MHS.

Every endpoint, type and fact cites the pinned clone at
48bae14fe4b2d56e5ca11fd2fec3d7dfac7a0e75.  The fake transport is ROS-free and
all of its state values are placeholders.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The controller subscribes to the vehicle-prefixed absolute /runstop topic;
#: the README names the absolute topic and the autorally_msgs/runstop type.
_RUNSTOP_REF = "README.md:151"
_RUNSTOP_SUB_REF = "autorally_gazebo/nodes/autorally_controller.py:310"
_RUNSTOP_AND_REF = "autorally_gazebo/nodes/autorally_controller.py:435-440"
_RUNSTOP_ZERO_REF = "autorally_gazebo/nodes/autorally_controller.py:345-348"
_RUNSTOP_STATE_REF = "autorally_gazebo/nodes/autorally_controller.py:325-327"
_PRIORITY_SORT_REF = "autorally_gazebo/nodes/autorally_controller.py:258-259"
_WHEEL_STAMP_REF = "autorally_gazebo/nodes/autorally_controller.py:571"
_WHEEL_FILL_REF = "autorally_gazebo/nodes/autorally_controller.py:575-583"

#: The physical run-stop box and the node that publishes its serial state.
_RUNSTOP_BOX_REF = "autorally_core/src/RunStop/RunStop.h:53-55"
_RUNSTOP_PUB_REF = "autorally_core/src/RunStop/RunStop.cpp:68"
_RUNSTOP_RATE_REF = "autorally_core/src/RunStop/RunStop.cpp:62-74"
_RUNSTOP_MAP_REF = "autorally_core/src/RunStop/RunStop.cpp:126-145"

#: ConstantSpeedController's relative speedCommand subscription and Float64 type.
_SPEED_REF = "autorally_control/src/ConstantSpeedController/ConstantSpeedController.cpp:71-72"
_SPEED_TYPE_REF = "autorally_control/src/ConstantSpeedController/ConstantSpeedController.h:89"
_SPEED_CALLBACK_REF = "autorally_control/src/ConstantSpeedController/ConstantSpeedController.cpp:100-107"
_SPEED_PUBLISH_REF = "autorally_control/src/ConstantSpeedController/ConstantSpeedController.cpp:109-155"
_SPEED_ZERO_REF = "autorally_control/src/ConstantSpeedController/ConstantSpeedController.cpp:149-153"
_INTEGRAL_INIT_REF = "autorally_control/src/ConstantSpeedController/ConstantSpeedController.cpp:55"
_INTEGRAL_UPDATE_REF = "autorally_control/src/ConstantSpeedController/ConstantSpeedController.cpp:120-138"

#: The Gazebo controller's chassisState and wheelSpeeds publications.
_STATE_REF = "autorally_gazebo/nodes/autorally_controller.py:302"
_STATE_TYPE_REF = "autorally_gazebo/nodes/autorally_controller.py:130"
_WHEEL_REF = "autorally_gazebo/nodes/autorally_controller.py:299"
_WHEEL_TYPE_REF = "autorally_gazebo/nodes/autorally_controller.py:132"
_WHEEL_COMPUTE_REF = "autorally_gazebo/nodes/autorally_controller.py:559-586"
_JOY_RUNSTOP_REF = "autorally_control/src/joystick/JoystickControl.cpp:55-56"
_JOY_PUB_REF = "autorally_control/src/joystick/JoystickControl.cpp:47-53"

#: The controller's steering/throttle/frontBrake acceptance and command timeout.
_COMMAND_GATE_REF = "autorally_gazebo/nodes/autorally_controller.py:350-391"
_TIMEOUT_REF = "autorally_gazebo/nodes/autorally_controller.py:80-84"
_TIMEOUT_IMPL_REF = "autorally_gazebo/nodes/autorally_controller.py:328-334"
_STEER_HOLD_REF = "autorally_gazebo/nodes/autorally_controller.py:497-515"
_LOOP_PUBLISH_REF = "autorally_gazebo/nodes/autorally_controller.py:328-412"

#: The simulation launch starts the controller and the joystick source.
_LAUNCH_REF = "autorally_gazebo/launch/autoRallyTrackGazeboSim.launch:73-79"
_LAUNCH_JOY_REF = "autorally_gazebo/launch/autoRallyTrackGazeboSim.launch:87-88"
_PRIORITY_FILE_REF = "autorally_util/config/chassisCommandPriorities.yaml:1-6"
_CONFIG_PATH_REF = "autorally_util/setupEnvVariables.sh:31"
_AXLE_EFFORT_REF = "autorally_gazebo/config/autoRallyPlatformJointCtrlrParams.yaml:34-48"

#: README statements for the run-stop source and the speed target.
_README_RUNSTOP_REF = "README.md:141-143"
_README_SPEED_REF = "README.md:165-170"

#: The wheel diameter is documented in meters; the speed callback uses it.
_DIAMETER_REF = "autorally_gazebo/nodes/autorally_controller.py:64-68"

#: The real platform's chassis nodelet and the launch that starts it.
_REAL_CHASSIS_REF = "autorally_core/src/autorally_chassis/AutoRallyChassis.cpp:64-101"
_REAL_LAUNCH_REF = "autorally_core/launch/autorally.launch:12"

#: The message definitions selected by the facts below.
_STATE_MSG_REF = "autorally_msgs/msg/chassisState.msg:1-14"
_WHEEL_MSG_REF = "autorally_msgs/msg/wheelSpeeds.msg:1-5"
_RUNSTOP_MSG_REF = "autorally_msgs/msg/runstop.msg:1-4"

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the topic publication to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge topic publication carries no execution confirmation"),
}


_CHASSIS_STATE_FIELDS = {
    "runstop_motion_enabled": Field("boolean",
                                    description="The controller's AND of every received runstop sender"),
    "autonomous_enabled": Field("boolean", description="chassisState.autonomousEnabled"),
    "steering": Field("number", unit="1", description="Normalized steering command selected by the controller"),
    "throttle": Field("number", unit="1", description="Normalized throttle command selected by the controller"),
    "front_brake": Field("number", unit="1",
                         description="Normalized front-brake command selected by the controller"),
    "steering_commander": Field("string", description="Sender selected for steering"),
    "throttle_commander": Field("string", description="Sender selected for throttle"),
    "front_brake_commander": Field("string", description="Sender selected for the front brake"),
}

_WHEEL_SPEED_FIELDS = {
    "lf_speed": Field("number", unit="m/s", description="Left-front wheel linear speed"),
    "rf_speed": Field("number", unit="m/s", description="Right-front wheel linear speed"),
    "lb_speed": Field("number", unit="m/s", description="Left-rear wheel linear speed"),
    "rb_speed": Field("number", unit="m/s", description="Right-rear wheel linear speed"),
}


def _state_read(path: str) -> dict:
    return {
        "topic": "/chassisState",
        "type": "autorally_msgs/chassisState",
        "source_name": "/chassisState",
        "source_ref": _STATE_REF,
        "type_ref": _STATE_TYPE_REF,
        "operation": "subscribe",
        "path": path,
        "timeout_ms": 2000,
    }


def _wheel_read(path: str) -> dict:
    return {
        "topic": "/wheelSpeeds",
        "type": "autorally_msgs/wheelSpeeds",
        "source_name": "/wheelSpeeds",
        "source_ref": _WHEEL_REF,
        "type_ref": _WHEEL_TYPE_REF,
        "operation": "subscribe",
        "path": path,
        "timeout_ms": 2000,
    }


_CHASSIS_READ = {
    "topic": "/chassisState",
    "type": "autorally_msgs/chassisState",
    "source_name": "/chassisState",
    "source_ref": _STATE_REF,
    "type_ref": _STATE_TYPE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {
        "map": {
            "runstop_motion_enabled": "output.runstopMotionEnabled",
            "autonomous_enabled": "output.autonomousEnabled",
            "steering": "output.steering",
            "throttle": "output.throttle",
            "front_brake": "output.frontBrake",
            "steering_commander": "output.steeringCommander",
            "throttle_commander": "output.throttleCommander",
            "front_brake_commander": "output.frontBrakeCommander",
        }
    },
}

_WHEEL_READ = {
    "topic": "/wheelSpeeds",
    "type": "autorally_msgs/wheelSpeeds",
    "source_name": "/wheelSpeeds",
    "source_ref": _WHEEL_REF,
    "type_ref": _WHEEL_TYPE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {
        "map": {
            "lf_speed": "output.lfSpeed",
            "rf_speed": "output.rfSpeed",
            "lb_speed": "output.lbSpeed",
            "rb_speed": "output.rbSpeed",
        }
    },
}

_SPEED_COMMAND = {
    "topic": "/constantSpeedController/speedCommand",
    "type": "std_msgs/Float64",
    "source_name": "constantSpeedController/speedCommand",
    "source_ref": _SPEED_REF,
    "type_ref": _SPEED_TYPE_REF,
    "operation": "publish",
    "message": {"data": 0.0},
    "args": {"data": {"from": "input.target_speed_mps"}},
}

_SPEED_LIMIT = Limit.operator_required(
    "the pinned README gives an example target speed but declares no numeric range, and the constant-speed "
    "controller has no range check; the operator supplies the deployment envelope"
)

#: The clone states no speed at which a wheel counts as stopped.  The fake's 0.05 m/s lives only in
#: fixtures/estop-confirmation.json.  A live simulation sets the four values in estop_confirmation.
_NO_WHEEL_BOUND = (
    "the clone states no at-rest wheel-speed bound; the operator supplies the largest absolute wheel speed "
    "that counts as stopped over the confirmation window"
)

#: Sensed-confirmation stop (SAFE-049).  The first step clears the Float64 this package commands
#: (ConstantSpeedController.cpp:100-107 stores it; :149-153 publishes throttle 0 on the next wheelSpeeds
#: callback when data is not greater than 0.1).  The second step is the package-owned runstop.  Neither
#: publication is a stop by itself: /wheelSpeeds must then show all four absolute speeds inside the operator
#: bound.  ROS 1 discards the first sample and declares no history.  Client bounds are fake-scale.
_SENSED_STOP = {
    "request": [
        {
            "topic": "/constantSpeedController/speedCommand",
            "type": "std_msgs/Float64",
            "source_name": "constantSpeedController/speedCommand",
            "source_ref": _SPEED_REF,
            "type_ref": _SPEED_TYPE_REF,
            "operation": "publish",
            "timeout_ms": 1000,
            "message": {"data": 0.0},
            "description": "clear the stored Float64 setpoint this package commands; the store sends no acknowledgement",
        },
        {
            "topic": "/runstop",
            "type": "autorally_msgs/runstop",
            "source_name": "/runstop",
            "source_ref": _RUNSTOP_REF,
            "operation": "publish",
            "timeout_ms": 1000,
            "message": {"sender": "openmhs", "motionEnabled": False},
            "description": "package-owned sender openmhs with motionEnabled false",
        },
    ],
    "sources": {
        "wheels": {
            "topic": "/wheelSpeeds",
            "type": "autorally_msgs/wheelSpeeds",
            "source_name": "/wheelSpeeds",
            "source_ref": _WHEEL_REF,
            "type_ref": _WHEEL_TYPE_REF,
            "throttle_ms": 100,
            "fill_refs": {
                "lfSpeed": _WHEEL_FILL_REF,
                "rfSpeed": _WHEEL_FILL_REF,
                "lbSpeed": _WHEEL_FILL_REF,
                "rbSpeed": _WHEEL_FILL_REF,
            },
        },
    },
    "predicate": [
        {"source": "wheels", "path": "lfSpeed", "name": "lf_speed", "unit": "m/s",
         "abs_max": Limit.operator_required(_NO_WHEEL_BOUND)},
        {"source": "wheels", "path": "rfSpeed", "name": "rf_speed", "unit": "m/s",
         "abs_max": Limit.operator_required(_NO_WHEEL_BOUND)},
        {"source": "wheels", "path": "lbSpeed", "name": "lb_speed", "unit": "m/s",
         "abs_max": Limit.operator_required(_NO_WHEEL_BOUND)},
        {"source": "wheels", "path": "rbSpeed", "name": "rb_speed", "unit": "m/s",
         "abs_max": Limit.operator_required(_NO_WHEEL_BOUND)},
    ],
    "consecutive": 3,
    "min_span_ms": 200,
    "max_gap_ms": 500,
    "confirm_within_ms": 2000,
    "description": (
        "zero speedCommand and /runstop motionEnabled false from sender openmhs, then all four wheel speeds "
        "at or below the operator bound in three consecutive fresh samples within the bound"
    ),
}


class AutoRallySimulation(RosDriver):
    device_id = "autorally-sim"
    device_kind = "world.sim"
    mode = "simulated"
    # The speed publication and the runstop both drive a mobile base, and the real AutoRallyChassis nodelet
    # consumes the same topics, so the binding is R2 (REVIEW.md item 12) even on the simulated card.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeAutorally"}
    tags = ["ros", "ros1", "simulation", "gazebo", "autorally", "runstop", "speed-command", "sensed-stop"]
    display_name = "AutoRally Gazebo simulation"
    vendor = "AutoRally"
    model = "autorally_gazebo autorally_controller.py and autorally_control ConstantSpeedController"

    facts = [
        Fact("RunStop advertises an autorally_msgs/runstop publisher on the relative topic runstop.",
             source="upstream_code", ref=_RUNSTOP_PUB_REF),
        Fact("RunStop publishes from a timer whose rate parameter defaults to 5.0 Hz.",
             source="upstream_code", ref=_RUNSTOP_RATE_REF),
        Fact("RunStop sets motionEnabled true only for the GREEN serial state; YELLOW and every other state set "
             "it false, and one second without serial data also sets it false.",
             source="upstream_code", ref=_RUNSTOP_MAP_REF),
        Fact("The 4-button run-stop box sets motionEnabled false when a red or yellow button is pressed; the "
             "green button is required for true.", source="upstream_code", ref=_RUNSTOP_BOX_REF),
        Fact("The Gazebo controller subscribes to the vehicle-prefixed /runstop topic.",
             source="upstream_code", ref=_RUNSTOP_SUB_REF),
        Fact("The Gazebo controller imports autorally_msgs.msg.chassisState, autorally_msgs.msg.runstop and "
             "autorally_msgs.msg.wheelSpeeds.", source="upstream_code",
             ref="autorally_gazebo/nodes/autorally_controller.py:129-132"),
        Fact("The Gazebo controller's getrunstop ANDs motionEnabled over every received sender and returns true "
             "when no sender has published.", source="upstream_code", ref=_RUNSTOP_AND_REF),
        Fact("When runstop motion is disabled, the controller forces throttle to 0 and labels the throttle "
             "commander runstop.", source="upstream_code", ref=_RUNSTOP_ZERO_REF),
        Fact("On the loop branch where delta_t is greater than 0, the controller publishes chassisState and "
             "the steering and axle joint commands. The cmd_timeout branch above that branch does not publish "
             "them.", source="upstream_code", ref=_LOOP_PUBLISH_REF),
        Fact("The controller sets chassisState.runstopMotionEnabled from getrunstop before selecting commands.",
             source="upstream_code", ref=_RUNSTOP_STATE_REF),
        Fact("The Gazebo controller publishes chassisState on the vehicle-prefixed /chassisState topic and "
             "wheelSpeeds on the vehicle-prefixed /wheelSpeeds topic.",
             source="upstream_code", ref="autorally_gazebo/nodes/autorally_controller.py:299-302"),
        Fact("The controller accepts steering and throttle only when the absolute value is at most 1.0 and "
             "frontBrake only within [0, 1], and only when the chassisCommand header stamp is less than 0.2 s "
             "old; otherwise that component is ignored.", source="upstream_code", ref=_COMMAND_GATE_REF),
        Fact("The controller documents a cmd_timeout default of 0.5 s and states that vehicle motion is paused "
             "until a command is received once the timeout expires.", source="upstream_code", ref=_TIMEOUT_REF),
        Fact("On cmd_timeout expiry the controller commands axle speed 0 through _ctrl_axles(0.0, 0.0, 0.0) and "
             "calls _ctrl_steering with the last steering angle and a zero velocity limit.",
             source="upstream_code", ref=_TIMEOUT_IMPL_REF),
        Fact("When steer_ang_vel_limit is not greater than 0, _ctrl_steering sets theta to the passed steer_ang "
             "and updates _last_steer_ang only when theta differs from it, so the timeout call leaves the "
             "steering angle unchanged.", source="upstream_code", ref=_STEER_HOLD_REF),
        Fact("The Gazebo controller sorts chassis commander priorities in ascending numeric order, so a lower "
             "number is considered first.", source="upstream_code", ref=_PRIORITY_SORT_REF),
        Fact("ConstantSpeedController subscribes to the relative constantSpeedController/speedCommand topic "
             "with std_msgs/Float64.", source="upstream_code", ref=_SPEED_REF),
        Fact("ConstantSpeedController stores the received Float64 value in m_mostRecentSpeedCommand and sends "
             "no acknowledgement.", source="upstream_code", ref=_SPEED_CALLBACK_REF),
        Fact("On every wheelSpeeds callback ConstantSpeedController publishes constantSpeedController/"
             "chassisCommand with header.stamp now, sender constantSpeedController, steering -5.0 and "
             "frontBrake 0.0; throttle is clamped to [0, 1].", source="upstream_code",
             ref=_SPEED_PUBLISH_REF),
        Fact("When the stored speed command is not greater than 0.1, ConstantSpeedController sets "
             "chassisCommand.throttle to 0.", source="upstream_code", ref=_SPEED_ZERO_REF),
        Fact("ConstantSpeedController initializes m_integralError to 0.",
             source="upstream_code", ref=_INTEGRAL_INIT_REF),
        Fact("m_integralError is updated only while m_mostRecentSpeedCommand.data is greater than 0.1.",
             source="upstream_code", ref=_INTEGRAL_UPDATE_REF),
        Fact("The README documents a /runstop topic of type autorally_msgs/runstop with sender and "
             "motionEnabled; motionEnabled true is required for the platform to move.",
             source="vendor_doc", ref=_RUNSTOP_REF),
        Fact("The README states the gamepad joystick node publishes runstop false at startup, that a button "
             "toggles it, and that runstopMotionEnabled in /chassisState shows the result.",
             source="vendor_doc", ref=_README_RUNSTOP_REF),
        Fact("The README documents constantSpeedController/speedCommand as a std_msgs/Float64 target velocity "
             "in m/s, states no numeric bound, and tells the operator to run a publisher on that topic at rate 10.",
             source="vendor_doc", ref=_README_SPEED_REF),
        Fact("The Gazebo simulation launch starts autorally_controller with the vehicle_prefix parameter taken "
             "from the namespace argument and loads the commander priorities from the operator's "
             "AR_CONFIG_PATH.", source="upstream_code", ref=_LAUNCH_REF),
        Fact("The simulation launch includes the joystickController launch.", source="upstream_code",
             ref=_LAUNCH_JOY_REF),
        Fact("setupEnvVariables.sh exports AR_CONFIG_PATH to the autorally_util config directory.",
             source="upstream_code", ref=_CONFIG_PATH_REF),
        Fact("The shipped chassisCommandPriorities.yaml gives constantSpeedController priority 2 and joystick "
             "priority 4.", source="upstream_code", ref=_PRIORITY_FILE_REF),
        Fact("JoystickControl advertises autorally_msgs/runstop on the relative runstop topic and "
             "autorally_msgs/chassisCommand on the relative joystick/chassisCommand topic.",
             source="upstream_code", ref=_JOY_PUB_REF),
        Fact("JoystickControl initializes its runstop sender to joystick and motionEnabled to false.",
             source="upstream_code", ref=_JOY_RUNSTOP_REF),
        Fact("The controller documents wheel diameters in meters.", source="upstream_code", ref=_DIAMETER_REF),
        Fact("wheelSpeedsCb stamps wheelSpeeds.header.stamp with rospy.Time.now() before assigning the speeds.",
             source="upstream_code", ref=_WHEEL_STAMP_REF),
        Fact("wheelSpeedsCb computes each wheel speed as joint velocity times half the configured wheel "
             "diameter and publishes the absolute value.", source="upstream_code", ref=_WHEEL_COMPUTE_REF),
        Fact("The four axle controllers in the Gazebo platform config are effort_controllers/JointEffortController.",
             source="upstream_code", ref=_AXLE_EFFORT_REF),
        Fact("chassisState carries runstopMotionEnabled, autonomousEnabled, the steering, throttle and "
             "frontBrake values and their commander strings.", source="upstream_code", ref=_STATE_MSG_REF),
        Fact("wheelSpeeds carries lfSpeed, rfSpeed, lbSpeed and rbSpeed.", source="upstream_code",
             ref=_WHEEL_MSG_REF),
        Fact("runstop carries a sender string and a motionEnabled boolean.", source="upstream_code",
             ref=_RUNSTOP_MSG_REF),
        Fact("The real platform's AutoRallyChassis nodelet advertises chassisState and wheelSpeeds, subscribes "
             "to <commander>/chassisCommand for each configured commander and subscribes to /runstop.",
             source="upstream_code", ref=_REAL_CHASSIS_REF),
        Fact("autorally.launch includes the autorally_chassis launch.", source="upstream_code",
             ref=_REAL_LAUNCH_REF),
    ]

    safe_state = (
        "Simulated only: zero speedCommand and /runstop motionEnabled false from sender openmhs, then all four "
        "/wheelSpeeds magnitudes within the operator bound on three consecutive fresh samples. This package does "
        "not re-enable motion. The operator recovers outside MHS, and only after every other speedCommand "
        "publisher has stopped, because a lost or overwritten zero leaves the stored target in place."
    )
    #: Two publish steps at 1000 ms each, plus confirm_within_ms 2000: the e-stop's budget.
    estop_latency_ms = 4000

    fidelity = {
        "engine": "canned:ROS fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned responses with no physics step, pacing, wheel integration or "
                     "state-hash replay; every state number is a placeholder",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free canned transport: it answers the declared /chassisState and /wheelSpeeds "
            "subscriptions and records /runstop and /constantSpeedController/speedCommand publications; it runs "
            "no Gazebo physics, controller loop, joystick node, constant-speed controller or wall-clock loop",
            "the fake's chassisState, wheelSpeeds and target-speed values are placeholders and do not establish "
            "motion, trajectory, contact, wheel slip or timing; while motion is enabled and the stored target "
            "is above 0.1 the placeholder wheel magnitude equals the absolute target (an echo, not the plant) "
            "and otherwise it decays by a placeholder factor and settles at 0",
            "the e-stop is a sensed-confirmation stop (SAFE-049, simulated only): it publishes data 0 on "
            "constantSpeedController/speedCommand and then /runstop {sender: openmhs, motionEnabled: false}, and "
            "it is achieved only on three consecutive fresh /wheelSpeeds samples whose four absolute speeds are "
            "within the operator bound, spanning min_span_ms inside confirm_within_ms; ROS 1 discards the first "
            "sample and the source declares no history; the thresholds are operator_required (fake placeholders "
            "in fixtures/estop-confirmation.json) and the client bounds, including throttle_ms 100, are "
            "fake-scale, so a live deployment sets them in simulation_deployment['estop_confirmation']",
            "the speed zero is unacknowledged (ConstantSpeedController.cpp:100-107) and is not a durable clear: "
            "README.md:170 tells the operator to run a speedCommand publisher at rate 10, which can overwrite the "
            "zero, and a lost zero is not stored. A false runstop forces throttle 0 (autorally_controller.py:"
            "345-348) without clearing the Float64, so wheel speeds under the bound do not prove the setpoint is "
            "0. This package publishes no motionEnabled true (SAFE-042, REVIEW.md item 13). The operator recovers "
            "outside MHS. m_integralError is not cleared (ConstantSpeedController.cpp:120-138)",
            "the direct chassisCommand input is not exposed: the Gazebo controller ignores a component whose "
            "header stamp is 0.2 s old or older, and this configuration-only helper has no ROS clock with which "
            "to stamp a publication; the declared speedCommand input has no header and no age check",
            "the declared speedCommand path requires the operator to run the constantSpeedController nodelet "
            "and its wheelSpeeds feedback; it publishes steering -5.0, which the Gazebo controller rejects as "
            "out of its [-1, 1] steering range, so joystick steering can still apply, and frontBrake 0 wins only "
            "while that chassisCommand is fresh; the shipped priority file lists constantSpeedController at 2 and "
            "joystick at 4 and the controller sorts ascending (autorally_controller.py:258-259)",
            "the four axle controllers are effort controllers, so effort 0 coasts and the runstop applies no "
            "brake; how long the wheels take to fall inside the bound depends on the world and the slope, which "
            "this package does not measure; a sample that is already inside the bound also confirms, so the "
            "predicate does not show that this stop caused the slowdown",
            "the default simulation launch starts the joystick node with runstop false; getrunstop ANDs every "
            "sender, so motion stays disabled while joystick or sender openmhs is false. This package never "
            "publishes motionEnabled true. After the stop, sender openmhs stays false until the operator "
            "publishes it from outside MHS",
            "the declaration assumes the controller's default empty vehicle_prefix and root namespace, and that "
            "the operator's AR_CONFIG_PATH is the shipped autorally_util config (setupEnvVariables.sh exports "
            "that path); multi-vehicle namespaces and remaps are not covered",
            "chassisState is published on the fresh-command branch of the controller loop and is not the "
            "confirmation source; /wheelSpeeds is stamped in wheelSpeedsCb from joint_states; a paused simulation "
            "clock produces no new stamps and the confirmation fails closed; this package does not unpause Gazebo",
            "/chassisState and /wheelSpeeds are fresh subscriptions, not held samples; if the controller or its "
            "Gazebo joint feedback is absent, the observation waits for its deadline and fails rather than "
            "returning cached state",
            "no live ROS graph, rosbridge connection, Gazebo process, simulator, or hardware was run; the fake "
            "does not establish a live deployment contract",
            "the real AutoRally platform's AutoRallyChassis nodelet (autorally.launch) serves the same /runstop, "
            "/chassisState and /wheelSpeeds contract and the same commander chassisCommand topics, so nothing in "
            "these bindings tells the simulation from the real 1:5-scale car; a live deployment against the real "
            "platform would drive real hardware and is out of scope for this simulated card",
        ],
    }

    parameters = {
        "runstop_motion_enabled": Field(
            "boolean", description="The controller's AND of every received runstop sender"),
        "steering": Field("number", unit="1", description="Normalized steering command selected by the controller"),
        "throttle": Field("number", unit="1", description="Normalized throttle command selected by the controller"),
        "front_brake": Field("number", unit="1",
                             description="Normalized front-brake command selected by the controller"),
        "lf_speed": Field("number", unit="m/s", description="Left-front wheel linear speed published on /wheelSpeeds"),
        "rf_speed": Field("number", unit="m/s", description="Right-front wheel linear speed published on /wheelSpeeds"),
        "lb_speed": Field("number", unit="m/s", description="Left-rear wheel linear speed published on /wheelSpeeds"),
        "rb_speed": Field("number", unit="m/s", description="Right-rear wheel linear speed published on /wheelSpeeds"),
    }
    reads = {
        "runstop_motion_enabled": _state_read("runstopMotionEnabled"),
        "steering": _state_read("steering"),
        "throttle": _state_read("throttle"),
        "front_brake": _state_read("frontBrake"),
        "lf_speed": _wheel_read("lfSpeed"),
        "rf_speed": _wheel_read("rfSpeed"),
        "lb_speed": _wheel_read("lbSpeed"),
        "rb_speed": _wheel_read("rbSpeed"),
    }
    commands = {
        "x-cap.autorally.speed_command.v1": _SPEED_COMMAND,
        "x-cap.autorally.chassis_state.v1": _CHASSIS_READ,
        "x-cap.autorally.wheel_speeds.v1": _WHEEL_READ,
    }
    actions = {
        "x-cap.autorally.speed_command.v1": Action(
            name="publish_speed_command",
            verb="invoke",
            description=(
                "Publish one std_msgs/Float64 target velocity on the constantSpeedController/speedCommand "
                "topic. It does not publish /runstop and does not enable motion. The constant-speed controller "
                "consumes it; the receipt is transmission evidence only, not measured speed, arrival or stopping."
            ),
            input={
                "target_speed_mps": Field(
                    "number", unit="m/s",
                    description="Target velocity for ConstantSpeedController; the README states the unit but "
                                "no numeric bound",
                    limit=_SPEED_LIMIT,
                ),
            },
            output=_PUBLISHED,
            risk="R2",
        ),
        "x-cap.autorally.chassis_state.v1": Action(
            name="read_chassis_state",
            verb="read",
            description="Read one fresh autorally_msgs/chassisState sample published by the Gazebo controller.",
            output=_CHASSIS_STATE_FIELDS,
        ),
        "x-cap.autorally.wheel_speeds.v1": Action(
            name="read_wheel_speeds",
            verb="read",
            description="Read one fresh autorally_msgs/wheelSpeeds sample published by the Gazebo controller.",
            output=_WHEEL_SPEED_FIELDS,
        ),
    }
    # Sensed-confirmation stop only.  Do not wrap make_bridge: a sensed stop commits on the SDK ROS route.
    safety_bindings = {"sensed_stop": _SENSED_STOP}
