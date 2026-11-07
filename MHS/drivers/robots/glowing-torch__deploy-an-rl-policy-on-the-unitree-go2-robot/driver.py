"""OpenMHS rosbridge driver for the MuJoCo Go2 simulator (gh.glowing-torch/deploy-an-rl-policy-on-the-unitree-go2-robot).

The pinned upstream is a ROS 2 framework for low-level control of a Unitree Go2.
Its simulation runtime is ``scripts/mujoco_simulator.py``: a Python ROS 2 node that
loads ``resources/go2/scene_terrain.xml``, subscribes to ``unitree_go/msg/LowCmd``
on ``/mujoco/lowcmd``, publishes ``unitree_go/msg/LowState`` on ``/mujoco/lowstate``
and the MuJoCo ``qpos[:19]`` vector on ``/mujoco/pos``, and advances the model in
its own thread.  This package is a configuration-only :class:`RosDriver` over
rosbridge; it declares no Python native class and never starts ROS, MuJoCo or
rosbridge.

Scope: the simulator node's command topic and its two state topics.  A published
LowCmd is transmission evidence only.  The e-stop is a sensed-confirmation stop
(SAFE-049, simulated devices only): the passive LowCmd that ``init_cmd`` writes
(``low_level_ctrl.cpp:66-79``) published once on ``/mujoco/lowcmd``.  While
``state_machine`` runs it overwrites that command every 5 ms.  The confirmation
watches ``/mujoco/lowcmd`` after the request and refuses a later command
with a nonzero ``kp`` or ``kd``, including a stationary hold, and a sample
the exclusion ring drops.  The keep branch publishes nothing when that
controller is absent, so this package has no source-backed controller stop.
With ``is_simulation`` false the same node publishes ``/lowcmd``, the real Go2
topic, which this package does not bind.  Evidence is the fake backend's
contract check only.

Every endpoint, type and fact cites the pinned clone at
dbb7b3112cef08ffc9f6f2c63412144d20341222.  No ROS graph, MuJoCo model, simulator,
policy or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

_SIM = "src/deploy_rl_policy/scripts/mujoco_simulator.py"
_CTRL = "src/deploy_rl_policy/src/low_level_ctrl.cpp"
_POLICY = "src/deploy_rl_policy/scripts/rl_policy.py"
_MODEL = "resources/go2/go2.xml"
_SCENE = "resources/go2/scene_terrain.xml"
_YAML = "src/deploy_rl_policy/configs/go2.yaml"
_README = "README.md"

#: The simulator's declared endpoints.  ``mujoco_simulator.py:20-24`` shows the
#: publishers and the LowCmd subscription; ``:8`` and ``:11`` import the types.
_LOWSTATE_REF = f"{_SIM}:20"
_POS_REF = f"{_SIM}:21"
_LOWCMD_REF = f"{_SIM}:24"
_UNITREE_TYPE_REF = f"{_SIM}:8"
_STD_TYPE_REF = f"{_SIM}:11"

#: The LowCmd callback reads only q, kp and kd from each of the first 12 motor
#: commands; the PD law and the MuJoCo step are the node's own.
_CALLBACK_REF = f"{_SIM}:55-60"
_PD_REF = f"{_SIM}:62-66"
_STEP_REF = f"{_SIM}:68-84"
_STATE_REF = f"{_SIM}:91-98"
_QPOS_REF = f"{_SIM}:99-101"

#: The model file the simulator loads and the joint/motor declarations it holds.
_SCENE_JOIN_REF = f"{_SCENE}:2"
_TIMESTEP_REF = f"{_SIM}:45-47"
_JOINT_RANGE_REF = f"{_MODEL}:12-23"
_ACTUATOR_REF = f"{_MODEL}:232-243"
_CTRL_RANGE_REF = f"{_MODEL}:10-24"

#: The policy/control pipeline that writes the same LowCmd topic.
_CTRL_TOPIC_REF = f"{_CTRL}:42-57"
_POLICY_GAIN_REF = f"{_CTRL}:184-189"
_POLICY_GATE_REF = f"{_CTRL}:91-97"
_JOY_SHUTDOWN_REF = f"{_CTRL}:120-121"

#: The RL policy node's own topics and joint-order reordering.
_POLICY_SUB_REF = f"{_POLICY}:36-41"
_POLICY_PUB_REF = f"{_POLICY}:46"
_POLICY_ORDER_REF = f"{_POLICY}:62-66"
_POLICY_CONFIG_REF = f"{_YAML}:8-10"

#: The README documents the simulation run command and the three-node split.
_README_SIM_REF = f"{_README}:44"
_README_NODES_REF = f"{_README}:86-89"
_README_MODES_REF = f"{_README}:59-61"
_README_SPORT_REF = f"{_README}:68"

#: One LowCmd publication.  rosbridge maps the JSON ``motor_cmd`` array onto the
#: fixed-size MotorCmd array of unitree_go/msg/LowCmd; the simulator reads the
#: first twelve entries.  Other LowCmd fields keep their ROS defaults.
_LOWCMD = {
    "topic": "/mujoco/lowcmd",
    "type": "unitree_go/msg/LowCmd",
    "operation": "publish",
    "source_name": "/mujoco/lowcmd",
    "source_ref": _LOWCMD_REF,
    "type_ref": _UNITREE_TYPE_REF,
    "message": {"motor_cmd": []},
    "args": {"motor_cmd": {"from": "input.motor_cmd"}},
}

#: One LowState observation.  The simulator fills the first twelve motor_state
#: entries and the IMU quaternion and gyroscope; the remaining motor_state slots
#: keep their ROS defaults and are returned as published.
_LOWSTATE = {
    "topic": "/mujoco/lowstate",
    "type": "unitree_go/msg/LowState",
    "operation": "subscribe",
    "source_name": "/mujoco/lowstate",
    "source_ref": _LOWSTATE_REF,
    "type_ref": _UNITREE_TYPE_REF,
    "path": "$",
    "result": {"map": {
        "quaternion": "imu_state.quaternion",
        "gyroscope": "imu_state.gyroscope",
    }},
}

#: One qpos observation.  The simulator publishes d.qpos[:19] on each 2 ms timer
#: tick: base position (3), base quaternion (4) and the twelve joint angles.
_QPOS = {
    "topic": "/mujoco/pos",
    "type": "std_msgs/msg/Float32MultiArray",
    "operation": "subscribe",
    "source_name": "/mujoco/pos",
    "source_ref": _POS_REF,
    "type_ref": _STD_TYPE_REF,
    "path": "$",
    "result": {"map": {"qpos": "data"}},
}

#: PosStopF and VelStopF are the header literals (src/deploy_rl_policy/include/common/motor_crc.h:18-19).
#: init_cmd writes them, with kp, kd and tau 0 and mode 0x01, into all 20 motor_cmd slots (low_level_ctrl.cpp:71-78).
_POS_STOP = 2146000000.0
_VEL_STOP = 16000.0
_PASSIVE_CMD = [
    {"mode": 1, "q": _POS_STOP, "dq": _VEL_STOP, "kp": 0.0, "kd": 0.0, "tau": 0.0} for _ in range(20)
]
_NO_MOTION_BOUND = (
    "the clone states no at-rest bound for joint velocity or for how far the base position may move during the "
    "confirmation window; the operator supplies it"
)

#: Sensed-confirmation stop (SAFE-049).  The passive command is not a stop by itself.  pd_control is
#: (target_q - q) * kp - dq * kd (mujoco_simulator.py:112-114), so kp and kd at zero make the torque zero.
#: state_machine's keep branch republishes nonzero kp and kd every 5 ms (low_level_ctrl.cpp:148-167).  The
#: exclusion subscription opens after the request.  A sample whose first twelve kp or kd fields are not all zero,
#: and a sample the exclusion ring drops, each refuse the attempt.  A stationary hold is not proof the controller
#: stopped.  Both sensed topics
#: are published from the 2 ms publish_sensor_data timer (mujoco_simulator.py:33; the 1 ms timer at :34 is
#: update_tau and does not publish them).  Three samples at 2 ms span 4 ms, which is min_span_ms.  A slower
#: timer still meets the arrival window while the gap stays under max_gap_ms.  A stream closer than min_interval_ms 1 restarts
#: the count.  The lowstate fill does not assign a stamp (mujoco_simulator.py:92-98) and /mujoco/pos is a
#: Float32MultiArray (:99-101).  Both publishers are volatile (create_publisher depth 10 at :20-21), so freshness
#: is arrival.  The base check is the span of qpos data[0], data[1] and data[2] (free-joint xyz;
#: the node publishes qpos[:19] at :100).  Joint velocity is motor_state dq, filled at :95.  Thresholds are
#: operator_required placeholders.
_SENSED_STOP = {
    "request": [
        {"topic": "/mujoco/lowcmd", "type": "unitree_go/msg/LowCmd", "source_ref": _LOWCMD_REF,
         "type_ref": _UNITREE_TYPE_REF, "timeout_ms": 1000,
         "message": {"motor_cmd": _PASSIVE_CMD},
         "description": "the init_cmd passive LowCmd: mode 0x01, q PosStopF, dq VelStopF, kp kd tau 0, twenty slots"},
    ],
    "sources": {
        "lowstate": {
            "topic": "/mujoco/lowstate", "type": "unitree_go/msg/LowState", "source_ref": _LOWSTATE_REF,
            "type_ref": _UNITREE_TYPE_REF, "freshness": "arrival", "min_interval_ms": 1,
            "history": {"durability": "volatile", "ref": _LOWSTATE_REF},
            "fill_refs": {"motor_state": f"{_SIM}:95"},
        },
        "pos": {
            "topic": "/mujoco/pos", "type": "std_msgs/msg/Float32MultiArray", "source_ref": _POS_REF,
            "type_ref": _STD_TYPE_REF, "freshness": "arrival", "min_interval_ms": 1,
            "history": {"durability": "volatile", "ref": _POS_REF},
            "fill_refs": {"data": f"{_SIM}:100"},
        },
    },
    "predicate": [
        {"source": "lowstate", "path": f"motor_state.{index}.dq", "name": f"joint_dq_{index}", "unit": "rad/s",
         "abs_max": Limit.operator_required(_NO_MOTION_BOUND)}
        for index in range(12)
    ] + [
        {"source": "pos", "path": f"data.{index}", "name": f"base_{axis}", "unit": "m",
         "span_max": Limit.operator_required(_NO_MOTION_BOUND)}
        for index, axis in ((0, "x"), (1, "y"), (2, "z"))
    ],
    "consecutive": 3,
    "min_span_ms": 4,
    "max_gap_ms": 500,
    "confirm_within_ms": 1500,
    "description": "passive LowCmd published; twelve joint velocities at rest and the base position span within "
                   "the operator's bounds in three consecutive fresh samples; a nonzero kp or kd, and a LowCmd the "
                   "exclusion ring drops, each refuse the confirmation",
    "exclusion": {
        "topic": "/mujoco/lowcmd", "type": "unitree_go/msg/LowCmd", "source_ref": f"{_CTRL}:160-167",
        "type_ref": _UNITREE_TYPE_REF,
        "description": "the keep branch publishes nonzero kp and kd on the request topic after init_cmd",
        "paths": [f"motor_cmd.{index}.{gain}" for index in range(12) for gain in ("kp", "kd")],
    },
}

#: The LowCmd MotorCmd entries this driver sends.  The simulator reads exactly
#: these three fields; dq, tau and mode are not read by the node.
_NO_ACTUATION_BOUND = (
    "the clone states no numeric bound for MotorCmd q, kp or kd; the operator supplies the limit for this "
    "deployment"
)
_MOTOR_CMD = Field(
    "object",
    description="One MotorCmd entry; the simulator reads q, kp and kd only",
    properties={
        "q": Field("number", unit="rad", description="Target joint position",
                   limit=Limit.operator_required(_NO_ACTUATION_BOUND)),
        "kp": Field("number", unit="N.m/rad", description="Position gain applied by the node's PD law",
                    limit=Limit.operator_required(_NO_ACTUATION_BOUND)),
        "kd": Field("number", unit="N.m.s/rad", description="Velocity gain applied by the node's PD law",
                    limit=Limit.operator_required(_NO_ACTUATION_BOUND)),
    },
)

_PUBLISHED_OUTPUT = {
    "published": Field("boolean", description="True when the driver handed the LowCmd to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution confirmation"),
}

_QUATERNION = Field("array", length=4, unit="1",
                    description="IMU orientation quaternion copied from qpos[3:7]")
_GYROSCOPE = Field("array", length=3, unit="rad/s",
                   description="IMU gyroscope copied from MuJoCo sensordata[40:43]")


class Go2MujocoSim(RosDriver):
    """The ROS 2 MuJoCo simulator node's low-level command and state topics."""

    device_id = "go2-mujoco-sim"
    device_kind = "world.sim"
    mode = "simulated"
    #: REVIEW.md item 12.  The card floor is R0.  This package publishes a joint-level LowCmd, and low_level_ctrl
    #: publishes that same shape on /lowcmd when is_simulation is false (low_level_ctrl.cpp:52-54).  R2.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeGo2MujocoSim"}
    display_name = "Unitree Go2 MuJoCo simulator (ROS 2)"
    vendor = "glowing-torch"
    model = "Unitree Go2"
    tags = ["ros", "ros2", "simulation", "mujoco", "quadruped", "unitree", "go2",
            "joint position", "lowcmd", "lowstate"]
    facts = [
        Fact("The simulation node sets xml_path to resources/go2/scene_terrain.xml under the project root and "
             "loads it with mujoco.MjModel.from_xml_path.", source="upstream_code", ref=f"{_SIM}:27-45"),
        Fact("scene_terrain.xml includes go2.xml.", source="upstream_code", ref=_SCENE_JOIN_REF),
        Fact("The simulator declares a LowState publisher on /mujoco/lowstate, a Float32MultiArray publisher "
             "on /mujoco/pos, a Float32MultiArray publisher on /mujoco/torque and a LowCmd subscription on "
             "/mujoco/lowcmd.", source="upstream_code", ref=f"{_SIM}:20-24"),
        Fact("The simulation node imports LowState and LowCmd from unitree_go.msg.",
             source="upstream_code", ref=_UNITREE_TYPE_REF),
        Fact("The simulation node imports Float32MultiArray from std_msgs.msg.",
             source="upstream_code", ref=_STD_TYPE_REF),
        Fact("target_torque_callback sets recieve_data true on every LowCmd, then copies motor_cmd[i].q, .kp and "
             ".kd for i in 0..11 into target_dof_pos, kps and kds; no other MotorCmd field is read.",
             source="upstream_code", ref=_CALLBACK_REF),
        Fact("update_tau returns until recieve_data is true and then computes tau[i] with pd_control from "
             "target_dof_pos[i], qpos[7+i], kps[i], qvel[6+i] and kds[i] for each of the twelve motors.",
             source="upstream_code", ref=_PD_REF),
        Fact("pd_control returns (target_q - q) * kp - dq * kd.", source="upstream_code", ref=f"{_SIM}:111-115"),
        Fact("The node creates a 2 ms timer for publish_sensor_data and a 1 ms timer for update_tau, and starts "
             "step_simulation in its own thread.", source="upstream_code", ref=f"{_SIM}:33-40"),
        Fact("step_simulation loops while the viewer runs and running is true; until recieve_data is true it "
             "continues without sleeping, and afterwards it copies tau into d.ctrl, publishes it on "
             "/mujoco/torque, calls mujoco.mj_step and sleeps for the rest of the model timestep, with no check "
             "for a fresh LowCmd.", source="upstream_code", ref=_STEP_REF),
        Fact("publish_sensor_data copies motor_state[i].q and .dq for i in 0..11 from qpos[7+i] and qvel[6+i], "
             "copies qpos[3:7] into imu_state.quaternion and sensordata[40:43] into imu_state.gyroscope.",
             source="upstream_code", ref=_STATE_REF),
        Fact("publish_sensor_data publishes d.qpos[:19] as the Float32MultiArray data on /mujoco/pos.",
             source="upstream_code", ref=_QPOS_REF),
        Fact("The node sets the MuJoCo timestep to 0.005 s.", source="upstream_code", ref=_TIMESTEP_REF),
        Fact("stop_simulation sets running false and joins the simulation thread.",
             source="upstream_code", ref=f"{_SIM}:86-88"),
        Fact("main() calls stop_simulation and viewer.close() only in its finally block after rclpy.spin.",
             source="upstream_code", ref=f"{_SIM}:120-128"),
        Fact("The MuJoCo model declares per-class joint ranges: abduction -1.0472 to 1.0472 rad, front hip "
             "-1.5708 to 3.4907 rad, back hip -0.5236 to 4.5379 rad and knee -2.7227 to -0.83776 rad.",
             source="upstream_code", ref=_JOINT_RANGE_REF),
        Fact("The model's actuator block lists the twelve motors in FR, FL, RR, RL leg order, three joints per leg.",
             source="upstream_code", ref=_ACTUATOR_REF),
        Fact("The go2 default class sets the motor ctrlrange to -23.7 to 23.7, and the knee class overrides it "
             "to -45.43 to 45.43.", source="upstream_code", ref=_CTRL_RANGE_REF),
        Fact("low_level_ctrl declares is_simulation with default true; in simulation mode it publishes LowCmd on "
             "/mujoco/lowcmd and subscribes to LowState on /mujoco/lowstate, and otherwise it uses /lowcmd and "
             "/lowstate.", source="upstream_code", ref=_CTRL_TOPIC_REF),
        Fact("low_level_ctrl creates a 5 ms wall timer that runs state_machine.", source="upstream_code",
             ref=f"{_CTRL}:63"),
        Fact("state_machine's hold branch sets mode 0x01 and the standing or lay-down target angles with kp and kd "
             "for the twelve motors, computes the CRC and publishes the LowCmd.", source="upstream_code",
             ref=f"{_CTRL}:147-170"),
        Fact("low_level_ctrl's run_policy writes the target positions with kp 30 and kd 0.75 for all twelve "
             "motors.", source="upstream_code", ref=_POLICY_GAIN_REF),
        Fact("target_pos_callback calls run_policy only while is_standing_ and should_run_policy_ are both true; "
             "otherwise it only stores the received target vector.", source="upstream_code", ref=_POLICY_GATE_REF),
        Fact("joy_callback calls rclcpp::shutdown() when joystick axes 2 and 5 are both -1.",
             source="upstream_code", ref=_JOY_SHUTDOWN_REF),
        Fact("rl_policy.py subscribes to /mujoco/lowstate when args.simulation is set and to /lowstate otherwise.",
             source="upstream_code", ref=_POLICY_SUB_REF),
        Fact("rl_policy.py publishes its target joint positions as a Float32MultiArray on /rl/target_pos.",
             source="upstream_code", ref=_POLICY_PUB_REF),
        Fact("rl_policy.py reorders the measured joint vectors with sequence [3, 4, 5, 0, 1, 2, 9, 10, 11, 6, 7, "
             "8]; the comment above the two reorder lines says to comment them out for simulation.",
             source="upstream_code", ref=_POLICY_ORDER_REF),
        Fact("The shipped policy configuration sets num_actions 12 and action_scale 0.25.",
             source="upstream_code", ref=_POLICY_CONFIG_REF),
        Fact("The README runs the MuJoCo simulator with ros2 run deploy_rl_policy mujoco_simulator.py.",
             source="vendor_doc", ref=_README_SIM_REF),
        Fact("The README describes low_level_control as the 3-state machine that sends lowcmd to the simulator or "
             "the real robot.", source="vendor_doc", ref=_README_NODES_REF),
        Fact("The README maps joystick B, A and LB+RB to stand up, lay down and execute the RL policy.",
             source="vendor_doc", ref=_README_MODES_REF),
        Fact("The README instructs the operator to turn down the robot's sport mode service before deploying a "
             "policy on the real robot; that service is not implemented in this clone.",
             source="vendor_doc", ref=_README_SPORT_REF),
    ]
    #: The deployed fake is a ROS-free recording transport with placeholder
    #: samples, not a replay of captured traffic and not the upstream simulator.
    fidelity = {
        "engine": "analytic:ROS contract fake (canned replies; no MuJoCo physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies with no physics step, no PD integration and no wall-clock "
                     "pacing; placeholder samples do not establish trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free RecordingRosTransport: it answers the declared endpoints with placeholder "
            "messages and runs no MuJoCo model, no PD law, no contacts, no ROS node and no wall-clock loop",
            "the LowCmd publication is recorded only; the fake does not compute torque, integrate the model or "
            "prove that a command was received, executed or stopped",
            "the published /mujoco/lowstate and /mujoco/pos samples are placeholders; a live run must receive "
            "the simulator's actual 500 Hz LowState and 2 ms qpos publications",
            "the fake returns the full 20-slot motor_state arrays and the 4-value quaternion that the ROS "
            "message declares; only the first twelve motor slots are filled by the simulator",
            "the upstream model timestep is 0.005 s and the node timers are 2 ms and 1 ms; these are source "
            "facts, not fake timing",
            "the node declares /mujoco/force but never publishes it (the publish call is commented out); that "
            "topic is not bound",
            "the e-stop is a sensed-confirmation stop (SAFE-049, simulated only): one passive LowCmd on "
            "/mujoco/lowcmd, confirmed only by twelve /mujoco/lowstate joint velocities and the span of "
            "/mujoco/pos data[0..2], both arrival freshness with min_interval_ms 1 (publishers at "
            "mujoco_simulator.py:20-21). Both topics are on the 2 ms timer at :33, so three samples span 4 ms "
            "(min_span_ms 4). The 1 ms timer at :34 does not publish them. A slower timer still meets the "
            "arrival window while the gap stays under max_gap_ms 500; a stream closer than 1 ms restarts the count",
            "low_level_ctrl's 5 ms state machine overwrites /mujoco/lowcmd (low_level_ctrl.cpp:63, 148-167). "
            "Silence, a subscription error, nonzero holding gains, and a sample the exclusion ring drops each "
            "refuse the confirmation. The keep branch publishes nothing when that controller is absent, so this "
            "stop has no source-backed controller stop. With is_simulation false the same node publishes "
            "/lowcmd, which this package does not bind",
            "the first /mujoco/pos sample sets data[2] from the publication count so a LowCmd has an observable "
            "effect; counted confirmation samples use a fixed rest pose, not that echo",
            "the /rl/target_pos policy path, the joystick /joy input and the C++ low_level_ctrl state machine are "
            "not bound; they are cited as source facts only",
            "low_level_ctrl, which the README runs next to the simulator, publishes LowCmd on /mujoco/lowcmd every "
            "5 ms from its state machine, so while it runs any LowCmd from this package is overwritten within "
            "5 ms; with is_simulation false the same node commands /lowcmd, the README's real-robot path, which "
            "this package never binds",
            "the sensed-stop request sends twenty MotorCmd slots, matching init_cmd (low_level_ctrl.cpp:71-78). "
            "The invoke input is twelve MotorCmd entries. q, kp and kd are Limit.operator_required: the clone "
            "states no numeric bound. unitree_go/msg/LowCmd is defined outside the clone",
            "no ROS graph, rosbridge connection, MuJoCo simulator, policy run or hardware run occurred",
        ],
    }

    #: One request step at timeout_ms 1000 plus confirm_within_ms 1500.
    estop_latency_ms = 2500
    safe_state = (
        "Simulated only: the passive LowCmd is on /mujoco/lowcmd and twelve joint velocities plus the base "
        "position span are inside the operator bounds for three fresh samples."
    )
    #: The resource snapshot is the floating base's z coordinate from qpos.  The fake's first sample echoes the
    #: publication count into data[2]; that echo is a contract effect, not the simulated height.
    parameters = {
        "base_height": Field("number", unit="m",
                             description="Z coordinate of the floating base in the simulator's qpos vector"),
    }
    reads = {
        "base_height": {
            "topic": "/mujoco/pos",
            "type": "std_msgs/msg/Float32MultiArray",
            "source_name": "/mujoco/pos",
            "source_ref": _POS_REF,
            "type_ref": _STD_TYPE_REF,
            "path": "data.2",
            "timeout_ms": 2000,
        },
    }
    commands = {
        "x-cap.glowing-torch.lowcmd.v1": _LOWCMD,
        "x-cap.glowing-torch.lowstate.v1": _LOWSTATE,
        "x-cap.glowing-torch.qpos.v1": _QPOS,
    }
    actions = {
        "x-cap.glowing-torch.lowcmd.v1": Action(
            name="publish_joint_command",
            verb="invoke",
            description=(
                "Publish one unitree_go/msg/LowCmd on /mujoco/lowcmd with twelve MotorCmd entries carrying q, kp "
                "and kd; the receipt confirms only that rosbridge accepted the publication"
            ),
            input={
                "motor_cmd": Field(
                    "array", length=12,
                    description="Twelve MotorCmd entries in the simulator's actuator order FR, FL, RR, RL",
                    items=_MOTOR_CMD,
                ),
            },
            output=_PUBLISHED_OUTPUT,
        ),
        "x-cap.glowing-torch.lowstate.v1": Action(
            name="read_low_state",
            verb="read",
            description="Read one unitree_go/msg/LowState sample published on /mujoco/lowstate",
            output={
                "quaternion": _QUATERNION,
                "gyroscope": _GYROSCOPE,
            },
        ),
        "x-cap.glowing-torch.qpos.v1": Action(
            name="read_qpos",
            verb="read",
            description="Read one Float32MultiArray qpos sample published on /mujoco/pos",
            output={"qpos": Field(
                "array", length=19, unit="1",
                description="MuJoCo qpos[:19]: base position, base quaternion and twelve joint angles in model "
                            "units (m and rad)"),
            },
        ),
    }
    safety_bindings = {"sensed_stop": _SENSED_STOP}
