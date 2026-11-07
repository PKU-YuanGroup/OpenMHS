"""OpenMHS rosbridge driver for the pinned Spot Mini MuJoCo ROS 2 simulator.

The upstream ``simulation/mujoco`` package is a C++ ROS 2 node.  It runs the
MuJoCo physics loop and exposes a joint-space actuator command subscription, a
joint-state publisher and an acknowledged simulation-reset service.  This
package is a configuration-only :class:`RosDriver` over rosbridge: it declares
no Python native class and does not launch, import or run the upstream node.

The primary control is one ``communication/msg/ActuatorCmds`` publication on
``/simulation/actuators_cmds``.  The node turns the received gains, targets and
feed-forward torques into ``data.ctrl`` and clamps each resulting control value
to the interval [-100, 100].  A rosbridge publication receipt is transmission
evidence only; it does not prove that the node received the message, that the
PD law ran or that the simulated robot moved.

The only acknowledged effectful upstream service is ``/simulation/sim_reset``.
Its callback, under the simulation mutex and before it answers, calls
``mj_resetData``, writes the requested base pose and named hinge positions and
zeroes the cached actuator command vectors that ``apply_ctrl`` reads before
every step.  The fixed input-free form of that service is this package's safe
state and native e-stop binding: it teleports the simulated robot back to the
start pose with zero velocities and leaves zero actuator commands, but it does
not pause the MuJoCo physics loop, so the limp robot then falls from 0.7 m and
settles.  It is a simulated reset, not a physical emergency stop.

Every endpoint, type and fact cites the read-only clone at commit
1e07b87745ab623dab7ab79c4fbc61e62e4e829e.  The fake transport is ROS-free; no
ROS graph, rosbridge, MuJoCo run or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

_HANDLER = "simulation/mujoco/src/MuJoCoMessageHandler.cpp"
_MAIN = "simulation/mujoco/src/main.cc"
_MODEL = "description/model/xml/spot_mini/spot_mini.xml"
_LAUNCH = "simulation/mujoco/launch/simulation_launch.py"
_README = "README.md"

#: The node prefixes every relative topic and service name with "simulation/".
_NAME_PREFIX_REF = f"{_HANDLER}:8-9"
#: The relative sim_reset service and its communication/srv/SimulationReset type.
_RESET_REF = f"{_HANDLER}:13-16"
#: The relative actuators_cmds subscription and its communication/msg/ActuatorCmds type.
_ACTUATOR_REF = f"{_HANDLER}:18-51"
#: The relative joint_states publisher and its sensor_msgs/msg/JointState type.
_JOINT_STATES_REF = f"{_HANDLER}:21-22"
#: The reset callback: frame check, mj_resetData, qpos writes, cached-command zeroing.
_RESET_CALLBACK_REF = f"{_HANDLER}:74-121"
#: The actuator callback: cached time and per-array resizing/copy.
_ACTUATOR_CALLBACK_REF = f"{_HANDLER}:240-260"
#: The joint callback: one entry per hinge joint with name, qpos, qvel and qfrc_actuator.
_JOINT_CALLBACK_REF = f"{_HANDLER}:203-222"
#: apply_ctrl: PD law and the hard clamp of every resulting ctrl value to [-100, 100].
_APPLY_CTRL_REF = f"{_MAIN}:261-286"
#: The stale-command timer: after 0.2 s without a command it zeroes all but kd, which becomes 1.0.
_STALE_COMMAND_REF = f"{_HANDLER}:271-281"
#: The image callback constructs a CvImage but publishes neither image topic.
_IMAGE_CALLBACK_REF = f"{_HANDLER}:224-238"
#: The launch starts the mujoco simulation executable with the model-file parameter.
_LAUNCH_REF = f"{_LAUNCH}:1-25"
#: The README lists the four published topic names.
_README_TOPICS_REF = f"{_README}:44-53"
#: The MJCF model is named spot and its base body starts at z = 0.7 m.
_MODEL_REF = f"{_MODEL}:1-61"
#: The 12 hinge joints and their joint ranges.
_JOINT_RANGE_REF = f"{_MODEL}:74-167"
#: The 12 motor actuators, named after the 12 hinge joints with gear 1.
_ACTUATOR_MODEL_REF = f"{_MODEL}:230-243"
#: The integration timestep.
_TIMESTEP_REF = f"{_MODEL}:52"
#: PhysicsLoop: apply_ctrl and mj_step under the mutex while sim.run is set; mj_forward while paused.
_PHYSICS_LOOP_REF = f"{_MAIN}:356-463"

#: The 12 actuator/joint names in MJCF order (fl, fr, hl, hr; hx, hy, kn per leg).
_JOINT_NAMES = (
    "fl.hx", "fl.hy", "fl.kn",
    "fr.hx", "fr.hy", "fr.kn",
    "hl.hx", "hl.hy", "hl.kn",
    "hr.hx", "hr.hy", "hr.kn",
)

#: One publication on the node's command subscription.  The actuator-name array
#: is fixed in MJCF order; the five numeric arrays travel with it unchanged.
_ACTUATOR_COMMAND = {
    "topic": "/simulation/actuators_cmds",
    "type": "communication/msg/ActuatorCmds",
    "source_name": "actuators_cmds",
    "source_ref": _ACTUATOR_REF,
    "operation": "publish",
    "message": {
        "header": {},
        "actuators_name": list(_JOINT_NAMES),
        "kp": [],
        "pos": [],
        "kd": [],
        "vel": [],
        "torque": [],
    },
    "args": {
        "kp": {"from": "input.kp"},
        "pos": {"from": "input.pos"},
        "kd": {"from": "input.kd"},
        "vel": {"from": "input.vel"},
        "torque": {"from": "input.torque"},
    },
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
}

#: The acknowledged reset service with caller-supplied base pose and hinge positions.
#: The fixed frame_id "spot" is the MJCF model name (spot_mini.xml:1); z = 0.7 is
#: the model's base-body start height (spot_mini.xml:60).
_RESET = {
    "service": "/simulation/sim_reset",
    "type": "communication/srv/SimulationReset",
    "source_name": "sim_reset",
    "source_ref": _RESET_REF,
    "request": {
        "header": {"frame_id": "spot"},
        "base_pose": {
            "position": {"x": 0.0, "y": 0.0, "z": 0.7},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
        "joint_state": {"name": list(_JOINT_NAMES), "position": []},
    },
    "args": {
        "base_pose.position.x": {"from": "input.base_x", "default": 0.0},
        "base_pose.position.y": {"from": "input.base_y", "default": 0.0},
        "base_pose.position.z": {"from": "input.base_z", "default": 0.7},
        "base_pose.orientation.x": {"from": "input.base_qx", "default": 0.0},
        "base_pose.orientation.y": {"from": "input.base_qy", "default": 0.0},
        "base_pose.orientation.z": {"from": "input.base_qz", "default": 0.0},
        "base_pose.orientation.w": {"from": "input.base_qw", "default": 1.0},
        "joint_state.position": {"from": "input.joint_positions", "default": []},
    },
    "success": {"path": "is_success", "equals": True},
    "result": {"map": {"is_success": "is_success"}},
}

#: The same service with a fixed request: the only acknowledged action that can
#: put the simulated data and the cached actuator commands back to their defaults.
_SAFE_RESET = {
    "service": "/simulation/sim_reset",
    "type": "communication/srv/SimulationReset",
    "source_name": "sim_reset",
    "source_ref": _RESET_REF,
    "request": {
        "header": {"frame_id": "spot"},
        "base_pose": {
            "position": {"x": 0.0, "y": 0.0, "z": 0.7},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
        "joint_state": {"name": [], "position": []},
    },
    "success": {"path": "is_success", "equals": True},
    "result": {"map": {"is_success": "is_success"}},
}

#: One fresh joint-state subscription; the node publishes it from a 1 ms timer.
_JOINT_STATES = {
    "topic": "/simulation/joint_states",
    "type": "sensor_msgs/msg/JointState",
    "source_name": "joint_states",
    "source_ref": _JOINT_STATES_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {
        "frame_id": "header.frame_id",
        "name": "name",
        "position": "position",
        "velocity": "velocity",
        "effort": "effort",
    }},
}

#: The resource snapshot is the same live joint-state topic's position vector.
_JOINT_POSITIONS_READ = {
    "topic": "/simulation/joint_states",
    "type": "sensor_msgs/msg/JointState",
    "source_name": "joint_states",
    "source_ref": _JOINT_STATES_REF,
    "operation": "subscribe",
    "path": "position",
}

_PUBLISHED = {
    "published": Field("boolean", description="True when rosbridge accepted the publication"),
    "confirmed": Field("boolean", description="Always false: publication is transmission only, not execution"),
}

_RESET_OUTPUT = {
    "is_success": Field("boolean", description="The reset service's own is_success response, not a stopped-state "
                                              "measurement"),
}

_JOINT_NUMBERS = Field("array", length=12, unit="rad", items=Field("number", unit="rad",
                                                                  description="One hinge joint value"),
                       description="Twelve hinge positions in MJCF order")
_TORQUE_LIMIT = Limit(min=-100.0, max=100.0, unit="N.m", source="upstream_code", ref=f"{_MAIN}:284-285")


class SpotMujocoRos2(RosDriver):
    device_id = "spot-mujoco-ros2"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    #: The actuator command drives a legged mobile base; the hazard class is R2
    #: even though the only pinned runtime is a simulator.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeSpotMujocoRos2"}
    tags = ["ros", "ros2", "mujoco", "spot", "quadruped", "simulation", "joint", "actuator", "reset"]
    display_name = "MindSpaceInc Spot Mini MuJoCo ROS 2 simulator"
    vendor = "MindSpaceInc"
    model = "Spot Mini quadruped in MuJoCo"
    facts = [
        Fact("MuJoCoMessageHandler derives from rclcpp::Node named MuJoCoMessageHandler and sets name_prefix to "
             "the relative prefix simulation/.", source="upstream_code", ref=_NAME_PREFIX_REF),
        Fact("The node creates the relative sim_reset service with the communication/srv/SimulationReset type.",
             source="upstream_code", ref=_RESET_REF),
        Fact("The node creates the relative actuators_cmds subscription with the communication/msg/ActuatorCmds "
             "type and a KeepLast(1) sensor-data QoS.", source="upstream_code", ref=_ACTUATOR_REF),
        Fact("The node creates the relative joint_states publisher with the sensor_msgs/msg/JointState type.",
             source="upstream_code", ref=_JOINT_STATES_REF),
        Fact("The reset callback rejects a request whose header.frame_id is not the model name m->names[0] and "
             "sets is_success false.", source="upstream_code", ref=_RESET_CALLBACK_REF),
        Fact("The reset callback calls mj_resetData, writes qpos[0..2] and qpos[3..6] from base_pose.position and "
             "base_pose.orientation, writes each named joint's qpos entry and zeroes the cached kp, pos, kd, vel "
             "and torque entries.", source="upstream_code", ref=_RESET_CALLBACK_REF),
        Fact("The reset callback performs those writes between sim_->mtx.lock() and unlock(), then sets "
             "is_success true; it does not change sim.run.", source="upstream_code", ref=_RESET_CALLBACK_REF),
        Fact("While no model data exists the reset callback sleeps in one-second steps as long as rclcpp::ok() "
             "holds before it answers.", source="upstream_code", ref=f"{_HANDLER}:76-78"),
        Fact("PhysicsLoop locks the simulation mutex and, while sim.run is set, calls apply_ctrl and mj_step; "
             "while paused it only runs mj_forward.", source="upstream_code", ref=_PHYSICS_LOOP_REF),
        Fact("The node starts wall timers for imu_callback every 2.5 ms, joint_callback every 1 ms, "
             "odom_callback every 20 ms, touch_callback every 2 ms, img_callback every 20 ms and "
             "drop_old_message every 100 ms.", source="upstream_code", ref=f"{_HANDLER}:32-43"),
        Fact("The actuator callback stores the message time, resizes the cached arrays to the message sizes and "
             "copies each actuator name, kp, pos, kd, vel and torque entry.", source="upstream_code",
             ref=_ACTUATOR_CALLBACK_REF),
        Fact("apply_ctrl computes data.ctrl as kp*(pos - jointpos sensordata) + kd*(vel - jointvel sensordata) + "
             "torque and clamps the resulting value to the interval [-100, 100].", source="upstream_code",
             ref=_APPLY_CTRL_REF),
        Fact("The stale-command timer zeroes kp, pos, vel and torque and sets kd to 1.0 when the last command time "
             "is more than 0.2 s older than the node clock.", source="upstream_code", ref=_STALE_COMMAND_REF),
        Fact("joint_callback publishes one JointState entry per hinge joint: its name, qpos position, qvel "
             "velocity and qfrc_actuator effort.", source="upstream_code", ref=_JOINT_CALLBACK_REF),
        Fact("img_callback builds a depth-image header and a CvImage from an empty cv::Mat and publishes "
             "nothing.", source="upstream_code", ref=_IMAGE_CALLBACK_REF),
        Fact("The simulation launch starts the mujoco package's simulation executable with the model-file "
             "parameter set to description/model/xml/spot_mini/spot_mini.xml.", source="upstream_code",
             ref=_LAUNCH_REF),
        Fact("The README lists the /simulation/actuators_cmds, /simulation/imu_data, /simulation/joint_states and "
             "/simulation/odom topics.", source="vendor_doc", ref=_README_TOPICS_REF),
        Fact("The MJCF is named spot and the base body's initial position is 0 0 0.7.", source="upstream_code",
             ref=_MODEL_REF),
        Fact("The MJCF declares 12 hinge joints in four legs, each with a range; for example fl.hx spans "
             "-0.785398 to 0.785398 rad, fl.hy spans -0.898845 to 2.29511 rad and fl.kn spans -2.7929 to "
             "-0.254402 rad.", source="upstream_code", ref=_JOINT_RANGE_REF),
        Fact("The MJCF declares 12 motor actuators named after the 12 hinge joints with gear 1 and no "
             "ctrlrange.", source="upstream_code", ref=_ACTUATOR_MODEL_REF),
        Fact("The MJCF option element sets timestep to 0.0005 s.", source="upstream_code", ref=_TIMESTEP_REF),
    ]
    safe_state = (
        "Simulated reset, acknowledged after the writes: /simulation/sim_reset calls mj_resetData, puts the base "
        "at (0, 0, 0.7) with the model-default hinge positions and zero velocities, and zeroes every cached "
        "actuator command, so apply_ctrl writes zero control (joint damping kd 1.0 once the 0.2 s stale timer "
        "fires). Physics keeps running unless paused in the GUI: the limp robot falls and settles on the floor. "
        "A later actuators_cmds message from any client re-commands it. Not a physical emergency stop."
    )
    #: The deployed fake is a ROS-free analytic transport, not a captured recording.
    fidelity = {
        "engine": "analytic:ROS-free rosbridge contract stand-in (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven fake with no physics step, PD law, contact or pacing; placeholder arrays do "
                     "not establish trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "partial",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free analytic rosbridge contract stand-in, not a recording of captured traffic "
            "and not the upstream simulation executable; it runs no MuJoCo physics, PD law, contact, actuator "
            "dynamics, sensor or wall-clock loop",
            "the joint-state arrays are 12 placeholder hinge entries; the live node publishes one entry per hinge "
            "joint from a 1 ms timer, and the fake does not reproduce that rate",
            "the actuator publication is recorded as a wire message; the fake computes no data.ctrl, applies no "
            "real PD law, contact or integration, and only nudges its placeholder joint-position sample by a "
            "fixed small factor of the PD expression so a command has an observable contract effect",
            "the resource snapshot subscribes to /simulation/joint_states for each read; the live node publishes "
            "it from a 1 ms timer with the model's current qpos, while the fake returns its last placeholder "
            "sample",
            "the reset response is modelled; the fake only overwrites placeholder base-pose and joint arrays and "
            "clears recorded commands, with no mj_resetData, contact, warm-start or integration state",
            "the 0.0005 s timestep, the 0.2 s stale-command zeroing and the 1 ms/20 ms timers are source facts; "
            "the fake has no physics timestep, watchdog or timer behaviour",
            "the depth_image and rgb_image publishers are declared upstream but their callback publishes "
            "neither; images, IMU, odometry and touch are NOT COVERED by this package",
            "the reset callback only resets data and cached commands; it does not pause the MuJoCo physics loop, "
            "so the simulated bodies continue to step and can fall after the reset",
            "every e-stop calls /simulation/sim_reset twice (the estop binding, then the input-free safe-state "
            "action; reviewer probe) and the safety reset binding calls it again; each call teleports the robot "
            "back to the start pose; the callback waits in one-second sleeps while no model is loaded, and an "
            "unanswered reset makes the e-stop report SAFE_STATE_UNREACHED after its 1 s budget with the latch "
            "held (reviewer probe)",
            "kp, pos, kd and vel carry no Limit: the only bound the clone states is the [-100, 100] clamp of the "
            "summed control (main.cc:284-285), which the torque Limit applies to the feed-forward term alone; "
            "the motors themselves declare no ctrlrange",
            "no live ROS 2 graph, rosbridge endpoint, MuJoCo run or hardware was contacted; the fake is "
            "contract_checked evidence only",
        ],
    }

    parameters = {
        "joint_positions": Field("array", length=12, unit="rad",
                                 items=Field("number", unit="rad", description="One hinge joint position"),
                                 description="Current hinge joint positions from the live joint-state topic"),
    }
    reads = {"joint_positions": _JOINT_POSITIONS_READ}

    commands = {
        "x-cap.mindspaceinc.actuator_cmds.v1": _ACTUATOR_COMMAND,
        "x-cap.mindspaceinc.sim_reset.v1": _RESET,
        "x-cap.mindspaceinc.safe_reset.v1": _SAFE_RESET,
        "x-cap.mindspaceinc.joint_states.v1": _JOINT_STATES,
    }
    actions = {
        "x-cap.mindspaceinc.actuator_cmds.v1": Action(
            name="publish_actuator_cmds",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one communication/msg/ActuatorCmds message on /simulation/actuators_cmds with the 12 "
                "actuator names fixed in MJCF order. The node applies the PD expression and clamps each "
                "resulting ctrl to [-100, 100]; a publication receipt is transmission only, not motion."
            ),
            input={
                "kp": Field("array", length=12, unit="N.m/rad",
                            items=Field("number", unit="N.m/rad", description="One position gain"),
                            description="Position gains for the 12 actuators in fixed MJCF order"),
                "pos": Field("array", length=12, unit="rad",
                             items=Field("number", unit="rad", description="One position target"),
                             description="Position targets for the 12 actuators in fixed MJCF order"),
                "kd": Field("array", length=12, unit="N.m.s/rad",
                            items=Field("number", unit="N.m.s/rad", description="One velocity gain"),
                            description="Velocity gains for the 12 actuators in fixed MJCF order"),
                "vel": Field("array", length=12, unit="rad/s",
                             items=Field("number", unit="rad/s", description="One velocity target"),
                             description="Velocity targets for the 12 actuators in fixed MJCF order"),
                "torque": Field("array", length=12, unit="N.m",
                                items=Field("number", unit="N.m", description="One feed-forward torque"),
                                limit=_TORQUE_LIMIT,
                                description="Feed-forward torques for the 12 actuators in fixed MJCF order"),
            },
            output=_PUBLISHED,
            examples=[{
                "kp": [0.0] * 12, "pos": [0.0] * 12, "kd": [0.0] * 12,
                "vel": [0.0] * 12, "torque": [0.0] * 12,
            }],
        ),
        "x-cap.mindspaceinc.sim_reset.v1": Action(
            name="reset_simulation",
            risk="R0",
            description=(
                "Call the acknowledged /simulation/sim_reset service with the fixed frame_id spot, an optional "
                "base pose and optional 12 hinge positions. The callback calls mj_resetData, zeroes cached "
                "commands and returns is_success; it does not pause the physics loop."
            ),
            input={
                "base_x": Field("number", unit="m", required=False,
                                description="Base position x written after mj_resetData"),
                "base_y": Field("number", unit="m", required=False,
                                description="Base position y written after mj_resetData"),
                "base_z": Field("number", unit="m", required=False,
                                description="Base position z written after mj_resetData"),
                "base_qx": Field("number", unit="1", required=False,
                                 description="Base orientation quaternion x written after mj_resetData"),
                "base_qy": Field("number", unit="1", required=False,
                                 description="Base orientation quaternion y written after mj_resetData"),
                "base_qz": Field("number", unit="1", required=False,
                                 description="Base orientation quaternion z written after mj_resetData"),
                "base_qw": Field("number", unit="1", required=False,
                                 description="Base orientation quaternion w written after mj_resetData"),
                "joint_positions": _JOINT_NUMBERS,
            },
            output=_RESET_OUTPUT,
            examples=[{"base_z": 0.7, "base_qw": 1.0, "joint_positions": [0.0] * 12}],
        ),
        "x-cap.mindspaceinc.safe_reset.v1": Action(
            name="reset_safe_state",
            safe_state=True,
            risk="R0",
            description=(
                "Reset simulated data to the model defaults plus the fixed base pose with the acknowledged "
                "/simulation/sim_reset service. The callback calls mj_resetData and zeroes every cached actuator "
                "command; the MuJoCo physics loop keeps running."
            ),
            output=_RESET_OUTPUT,
        ),
        "x-cap.mindspaceinc.joint_states.v1": Action(
            name="read_joint_states",
            verb="read",
            risk="R0",
            description=(
                "Read one fresh /simulation/joint_states sample: the hinge joint names and their position, "
                "velocity and actuator effort. The subscription is explicit, not an automatic state snapshot."
            ),
            output={
                "frame_id": Field("string", description="Frame id from the JointState header"),
                "name": Field("array", items=Field("string", description="One joint name"),
                              description="Joint names in published order"),
                "position": Field("array", unit="rad", items=Field("number", unit="rad",
                                                                  description="One joint position"),
                                  description="Joint positions in published order"),
                "velocity": Field("array", unit="rad/s", items=Field("number", unit="rad/s",
                                                                    description="One joint velocity"),
                                  description="Joint velocities in published order"),
                "effort": Field("array", unit="N.m", items=Field("number", unit="N.m",
                                                                 description="One actuator effort"),
                                description="qfrc_actuator effort in published order"),
            },
        ),
    }
    #: The fixed-input reset is both the independent simulated safe state and the
    #: native service the runtime invokes after engaging the software latch.
    safety_bindings = {"estop": _SAFE_RESET, "reset": _SAFE_RESET}
