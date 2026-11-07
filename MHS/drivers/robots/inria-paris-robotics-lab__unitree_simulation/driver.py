"""OpenMHS rosbridge driver for the pinned Unitree Go2 ROS 2 simulation.

The upstream ``unitree_simulation`` package is an ``ament_python`` ROS 2 node
that wraps a pybullet model of a Unitree Go2 and mimics the parts of the real
Go2 ROS 2 control interface that this repository uses:

* it subscribes ``unitree_go/msg/LowCmd`` on ``/lowcmd`` and applies the
  ``q``, ``dq``, ``tau``, ``kp`` and ``kd`` entries of the first 12 ``motor_cmd``
  entries in its 500 Hz timer callback (``unitree_simulation/simulation_node.py:61-95``);
* it publishes ``unitree_go/msg/LowState`` on ``/lowstate`` and
  ``nav_msgs/msg/Odometry`` on ``/odometry/filtered``
  (``unitree_simulation/simulation_node.py:55-57,104-155``);
* it subscribes ``std_msgs/msg/Empty`` on ``/unlock_base`` and ``/reset``
  (``unitree_simulation/simulation_node.py:69-74``).

This package is a configuration-only :class:`RosDriver` over rosbridge.  It
declares no Python native class, imports no ROS and starts no simulator.  A
Go2 deployment is served; the G1 variant is out of scope because the node
selects a different message package and a different joint count at run time
(``unitree_simulation/robots_configuration.py:68-143`` versus
``:149-199``).

The pinned node exposes no ROS service or action server.  A publication is
transmission evidence only.  The e-stop is a sensed-confirmation stop
(SAFE-049, simulated devices only): one ``/lowcmd`` whose twenty MotorCmd
entries are all zero.  The node applies the first ``n_dof`` (12); ``kp``,
``kd`` and ``tau`` at zero make the timer's torque zero.  ``/reset`` and
``/unlock_base`` are not the stop: ``reset()`` does not clear
``last_cmd_msg``.  The stop is achieved only when fresh ``/lowstate`` joint
velocities (the node fill does not assign a stamp and the LowState definition is outside
the clone, so freshness is arrival) and the stamped
``/odometry/filtered`` twist hold within the operator's bounds.  The node
uses the real Go2's topic names, so a live graph that also carries a real
Go2 bridge would route ``/lowcmd`` to the robot.  Evidence is the fake
backend's contract check only.

Every endpoint and fact cites the pinned clone at
``b53b31bc0757e3ff48ac1199227e0b144d4008d2``.  The fake transport is ROS-free;
no ROS graph, pybullet process, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references
# ---------------------------------------------------------------------------

_NODE = "unitree_simulation/simulation_node.py"
_ROBOTS = "unitree_simulation/robots_configuration.py"

#: The node's constructor creates the publishers, subscriptions and timer.
_NODE_SETUP_REF = _NODE + ":55-77"
#: The node's parameter declarations.
_NODE_PARAMS_REF = _NODE + ":17-19"
#: The node selects Go2Configuration or G1Configuration from the robot parameter.
_NODE_ROBOT_REF = _NODE + ":26-34"
#: The publisher and subscriber declarations used by this driver.
_LOWSTATE_PUB_REF = _NODE + ":56"
_ODOM_PUB_REF = _NODE + ":57"
_LOWCMD_SUB_REF = _NODE + ":61-62"
_UNLOCK_AND_RESET_REF = _NODE + ":69-74"
_RESET_SUB_REF = _NODE + ":74"
_TIMER_REF = _NODE + ":77"
#: The update callback reads the five MotorCmd values and steps the simulator.
_UPDATE_REF = _NODE + ":79-95"
#: The update callback fills LowState motor fields, foot forces and IMU.
_LOWSTATE_FILL_REF = _NODE + ":104-112"
_IMU_REF = _NODE + ":114-132"
#: The update callback fills the Odometry message and its frames.
_ODOM_FILL_REF = _NODE + ":137-155"
#: The callback only stores the last received command.
_RECEIVE_REF = _NODE + ":177-178"
#: reset() and unlock_base() in the node.
_RESET_IMPL_REF = _NODE + ":180-183"
_UNLOCK_IMPL_REF = _NODE + ":185-187"
_MAIN_REF = _NODE + ":190-199"

#: The ROS 2 message imports used by the node and the Go2 configuration.
_NODE_MSG_IMPORTS_REF = _NODE + ":3-4"
_EMPTY_TYPE_REF = _NODE + ":3"
_ODOM_TYPE_REF = _NODE + ":4"
_UNITREE_MSG_IMPORTS_REF = _ROBOTS + ":3"
#: Go2Configuration returns unitree_go LowState/LowCmd and lists its 12 joints.
_GO2_TYPES_REF = _ROBOTS + ":193-199"
_GO2_JOINTS_REF = _ROBOTS + ":151-164"
_GO2_PERIOD_REF = _ROBOTS + ":169-175"
_GO2_FOOT_REF = _ROBOTS + ":201-203"
#: n_dof is the length of the ordered joint-name list.
_N_DOF_REF = _ROBOTS + ":59-61"

#: The abstract simulator wrapper documents locking and reset semantics.
_WRAPPER_REF = "unitree_simulation/abstract_wrapper.py:24-37"

#: The launch file defaults simulator=pybullet and unlock_base=False and makes
#: robot a required launch argument.
_LAUNCH_REF = "launch/launch_sim.launch.py:9-19"

#: The README and package.xml state the Go2 ROS 2 API-mimicking scope.
_README_REF = "README.md:1-3"
_PACKAGE_REF = "package.xml:6"

# ---------------------------------------------------------------------------
# Operator-required command envelope
# ---------------------------------------------------------------------------

# The clone reads five motor fields but states no numeric bound for any of
# them.  Joint limits and torque limits live in the external
# unitree_description/URDF data, not in this pinned package.  Every value
# therefore remains operator_required until the deployment supplies a reviewed
# per-joint envelope; a bound copied from a catalogue default or from the
# node's starting configuration would not be a device limit.

_Q_LIMIT = Limit.operator_required(
    "the pinned node reads motor_cmd[i].q with no joint-position bound; the reviewed per-joint "
    "position envelope is supplied by the operator"
)
_DQ_LIMIT = Limit.operator_required(
    "the pinned node reads motor_cmd[i].dq with no joint-velocity bound; the reviewed per-joint "
    "velocity envelope is supplied by the operator"
)
_TAU_LIMIT = Limit.operator_required(
    "the pinned node reads motor_cmd[i].tau with no joint-torque bound; the reviewed per-joint "
    "torque envelope is supplied by the operator"
)
_KP_LIMIT = Limit.operator_required(
    "the pinned node reads motor_cmd[i].kp with no stiffness bound; the reviewed per-joint "
    "stiffness envelope is supplied by the operator"
)
_KD_LIMIT = Limit.operator_required(
    "the pinned node reads motor_cmd[i].kd with no damping bound; the reviewed per-joint "
    "damping envelope is supplied by the operator"
)

_MOTOR_CMD = Field(
    "object",
    description="One unitree_go MotorCmd entry read by the node",
    properties={
        "q": Field("number", unit="rad", description="Position setpoint q_des",
                   limit=_Q_LIMIT),
        "dq": Field("number", unit="rad/s", description="Velocity setpoint v_des",
                    limit=_DQ_LIMIT),
        "tau": Field("number", unit="N.m", description="Feed-forward torque tau_des",
                     limit=_TAU_LIMIT),
        "kp": Field("number", unit="N.m/rad", description="Position gain kp_des",
                    limit=_KP_LIMIT),
        "kd": Field("number", unit="N.m.s/rad", description="Velocity gain kd_des",
                    limit=_KD_LIMIT),
    },
)

#: Go2Configuration's ordered joint list has 12 entries and the node indexes
#: motor_cmd by range(n_dof); the array shape is a protocol fact, not a limit.
_MOTOR_CMD_VECTOR = Field(
    "array",
    description="Go2 motor commands in FR, FL, RR, RL order",
    items=_MOTOR_CMD,
    length=12,
)

#: A valid all-zero wire-shape example (test data, not a device state or bound).
_ZERO_MOTOR_CMD = [
    {"q": 0.0, "dq": 0.0, "tau": 0.0, "kp": 0.0, "kd": 0.0}  # placeholder test data
    for _ in range(12)
]

#: The stop request carries twenty zero MotorCmd entries, the length the triage
#: asks for.  This clone never states that length: the node indexes only
#: range(n_dof), which is 12 (robots_configuration.py:59-61, 151-164).  The
#: extra eight zeros are not a verified wire fact.
_ZERO_STOP_CMD = [
    {"q": 0.0, "dq": 0.0, "tau": 0.0, "kp": 0.0, "kd": 0.0}  # placeholder test data
    for _ in range(20)
]

_NO_MOTION_BOUND = (
    "the clone states no at-rest bound for a joint velocity or for the base twist; the operator supplies the "
    "largest magnitude that counts as stopped"
)

#: Sensed-confirmation stop (SAFE-049).  The zero-gain LowCmd is not a stop by itself: the 500 Hz timer applies
#: tau_cmd = tau_des - kp*(q - q_des) - kd*(v - v_des) (simulation_node.py:89-93), which is zero when kp, kd and
#: tau are zero, and keeps applying last_cmd_msg, which reset() does not clear (:177-183).  The node fill at
#: :104-108 assigns mode, q and dq and does not assign a stamp; the LowState message definition is outside the
#: clone, so /lowstate is fresh by arrival from the volatile publisher at :56.  Odometry is stamped at :139.
#: Go2Configuration.high_level_period is 1/500 s (robots_configuration.py:169-171).  Three samples at that rate
#: span 4 ms, which is min_span_ms.  A slower timer still confirms while the gap stays under max_gap_ms.  A
#: stream closer than min_interval_ms 1 restarts the arrival count.  Raising min_span_ms above 4 without a
#: matching slower period fails closed.  The default launch leaves the base hung (launch_sim.launch.py:9-19,
#: unlock_base false), so the predicate reads the twelve joint velocities and the base twist, not the base pose.
#: Thresholds are operator_required.  fixtures/estop-confirmation.json holds fake placeholders only.
_SENSED_STOP = {
    "request": [
        {"topic": "/lowcmd", "type": "unitree_go/msg/LowCmd", "source_ref": _LOWCMD_SUB_REF,
         "type_ref": _UNITREE_MSG_IMPORTS_REF, "timeout_ms": 1000,
         "message": {"motor_cmd": _ZERO_STOP_CMD},
         "description": "twenty zero MotorCmd entries on /lowcmd; the node applies the first n_dof (12)"},
    ],
    "sources": {
        "lowstate": {
            "topic": "/lowstate", "type": "unitree_go/msg/LowState", "source_ref": _LOWSTATE_PUB_REF,
            "type_ref": _UNITREE_MSG_IMPORTS_REF, "freshness": "arrival", "min_interval_ms": 1,
            "history": {"durability": "volatile", "ref": _LOWSTATE_PUB_REF},
            "fill_refs": {"motor_state": _NODE + ":108"},
        },
        "odom": {
            "topic": "/odometry/filtered", "type": "nav_msgs/msg/Odometry", "source_ref": _ODOM_PUB_REF,
            "type_ref": _ODOM_TYPE_REF, "stamp_path": "header.stamp",
            "history": {"durability": "volatile", "ref": _ODOM_PUB_REF},
            "fill_refs": {"twist.twist": _NODE + ":149-154"},
        },
    },
    "predicate": [
        {"source": "lowstate", "path": f"motor_state.{index}.dq", "name": f"joint_dq_{index}", "unit": "rad/s",
         "abs_max": Limit.operator_required(_NO_MOTION_BOUND)}
        for index in range(12)
    ] + [
        {"source": "odom", "paths": ["twist.twist.linear.x", "twist.twist.linear.y", "twist.twist.linear.z"],
         "name": "base_linear", "unit": "m/s", "norm_max": Limit.operator_required(_NO_MOTION_BOUND)},
        {"source": "odom", "paths": ["twist.twist.angular.x", "twist.twist.angular.y", "twist.twist.angular.z"],
         "name": "base_angular", "unit": "rad/s", "norm_max": Limit.operator_required(_NO_MOTION_BOUND)},
    ],
    "consecutive": 3,
    "min_span_ms": 4,
    "max_gap_ms": 500,
    "confirm_within_ms": 1500,
    "description": "zero-gain LowCmd published; twelve joint velocities and the base linear and angular twist "
                   "within the operator's bounds in three consecutive fresh samples",
}

# ---------------------------------------------------------------------------
# Output and observation fields
# ---------------------------------------------------------------------------

_PUBLISHED = {
    "published": Field("boolean", description="True when rosbridge transmitted the publish"),
    "confirmed": Field("boolean", description="False: no execution or stop confirmation"),
}

#: Reviewer change: no fixed length on the motor arrays.  The node fills the first n_dof (12) entries of a
#: default-constructed LowState (simulation_node.py:98-108), so motor_state is a pre-sized array whose size the
#: external unitree_go definition sets; a real message carrying more entries was refused as OUTPUT_INVALID.
_LOWSTATE_OUTPUT = {
    "motor_mode": Field("array", items=Field("integer"), unit="1",
                        description="LowState motor mode per motor_state entry; the node fills entries 0-11"),
    "motor_q": Field("array", items=Field("number"), unit="rad",
                     description="LowState motor q per motor_state entry; the node fills entries 0-11"),
    "motor_dq": Field("array", items=Field("number"), unit="rad/s",
                      description="LowState motor dq per motor_state entry; the node fills entries 0-11"),
    "foot_force": Field("array", items=Field("integer"), length=4, unit="1",
                        description="LowState foot_force values"),
    "imu_quaternion": Field("array", items=Field("number"), length=4, unit="1",
                            description="LowState quaternion in w, x, y, z order"),
    "imu_gyroscope": Field("array", items=Field("number"), length=3, unit="rad/s",
                           description="LowState local angular velocity"),
    "imu_accelerometer": Field("array", items=Field("number"), length=3, unit="m/s2",
                               description="LowState local acceleration plus gravity"),
}

_POSITION = Field(
    "object",
    description="Odometry pose.position published on /odometry/filtered",
    properties={
        "x": Field("number", unit="m", description="Position x in the odom frame"),
        "y": Field("number", unit="m", description="Position y in the odom frame"),
        "z": Field("number", unit="m", description="Position z in the odom frame"),
    },
)
_ORIENTATION = Field(
    "object",
    description="Odometry pose.orientation published on /odometry/filtered",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)
_POSE = Field(
    "object",
    description="Odometry pose selected from pose.pose",
    properties={"position": _POSITION, "orientation": _ORIENTATION},
)
_LINEAR = Field(
    "object",
    description="Odometry twist.twist.linear",
    properties={
        "x": Field("number", unit="m/s", description="Linear velocity x in the base frame"),
        "y": Field("number", unit="m/s", description="Linear velocity y in the base frame"),
        "z": Field("number", unit="m/s", description="Linear velocity z in the base frame"),
    },
)
_ANGULAR = Field(
    "object",
    description="Odometry twist.twist.angular",
    properties={
        "x": Field("number", unit="rad/s", description="Angular velocity x in the base frame"),
        "y": Field("number", unit="rad/s", description="Angular velocity y in the base frame"),
        "z": Field("number", unit="rad/s", description="Angular velocity z in the base frame"),
    },
)
_TWIST = Field(
    "object",
    description="Odometry twist selected from twist.twist",
    properties={"linear": _LINEAR, "angular": _ANGULAR},
)
_MOTOR_STATE = Field(
    "array",
    description="LowState motor_state entries the node publishes; each entry carries mode, q and dq",
    items=Field("object", description="One LowState motor_state entry"),
)

# ---------------------------------------------------------------------------
# Wire bindings
# ---------------------------------------------------------------------------

#: unitree_go/msg/LowCmd is the Go2 command message.  The node reads only these
#: five fields from each motor_cmd entry; the array is overlaid as a whole.
_LOWCMD = {
    "topic": "/lowcmd",
    "type": "unitree_go/msg/LowCmd",
    "source_ref": _LOWCMD_SUB_REF,
    "type_ref": _UNITREE_MSG_IMPORTS_REF,
    "operation": "publish",
    "message": {"motor_cmd": []},
    "args": {"motor_cmd": {"from": "input.motor_cmd"}},
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
}

#: LowState is the Go2 proprioceptive message.  The result map selects only the
#: fields the node fills; the real message may carry further vendor fields.
_LOWSTATE = {
    "topic": "/lowstate",
    "type": "unitree_go/msg/LowState",
    "source_ref": _LOWSTATE_PUB_REF,
    "type_ref": _UNITREE_MSG_IMPORTS_REF,
    "operation": "subscribe",
    "path": "$",
    "timeout_ms": 1000,
    "result": {"map": {
        "motor_mode": "motor_state[*].mode",
        "motor_q": "motor_state[*].q",
        "motor_dq": "motor_state[*].dq",
        "foot_force": "foot_force",
        "imu_quaternion": "imu_state.quaternion",
        "imu_gyroscope": "imu_state.gyroscope",
        "imu_accelerometer": "imu_state.accelerometer",
    }},
}

_RESET = {
    "topic": "/reset",
    "type": "std_msgs/msg/Empty",
    "source_ref": _RESET_SUB_REF,
    "type_ref": _EMPTY_TYPE_REF,
    "operation": "publish",
    "message": {},
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
}

_UNLOCK_BASE = {
    "topic": "/unlock_base",
    "type": "std_msgs/msg/Empty",
    "source_ref": _UNLOCK_AND_RESET_REF,
    "type_ref": _EMPTY_TYPE_REF,
    "operation": "publish",
    "message": {},
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
}

#: Odometry is a state read; the two parameters select the pose and twist
#: sub-objects from the same nav_msgs/msg/Odometry message.
_ODOMETRY = {
    "topic": "/odometry/filtered",
    "type": "nav_msgs/msg/Odometry",
    "source_ref": _ODOM_PUB_REF,
    "type_ref": _ODOM_TYPE_REF,
}

#: The LowState topic binding for the resource-state read.  A read selects a
#: message sub-path and cannot carry a result map; the full motor_state array
#: is the state field.
_LOWSTATE_TOPIC = {
    "topic": "/lowstate",
    "type": "unitree_go/msg/LowState",
    "source_ref": _LOWSTATE_PUB_REF,
    "type_ref": _UNITREE_MSG_IMPORTS_REF,
}


class UnitreeSimulation(RosDriver):
    device_id = "unitree-simulation"
    device_kind = "world.sim"
    mode = "simulated"
    # The package commands every joint of a simulated quadruped.  The Go2 is a
    # mobile base, whose catalogue class is R2; the card floor is R0 and the
    # higher class applies.  A simulated device has no physical effect, but the
    # published LowCmd is the same interface a real Go2 consumes.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeUnitreeSimulation"}
    tags = ["ros", "ros2", "simulation", "unitree", "go2", "quadruped", "lowcmd", "lowstate",
            "pybullet"]
    display_name = "Unitree Go2 ROS 2 pybullet simulation"
    vendor = "INRIA Paris Robotics Lab"
    model = "Unitree Go2"

    facts = [
        Fact("The simulation node declares the string parameters simulator and robot and the boolean "
             "parameter unlock_base.", source="upstream_code", ref=_NODE_PARAMS_REF),
        Fact("The launch file defaults simulator to pybullet and unlock_base to False; robot is a "
             "declared launch argument with no default.", source="upstream_code", ref=_LAUNCH_REF),
        Fact("The node selects Go2Configuration when robot is go2 and G1Configuration when it is g1.",
             source="upstream_code", ref=_NODE_ROBOT_REF),
        Fact("UnitreeSimulation creates a publisher for the robot's LowState type on /lowstate with "
             "queue size 10 and a nav_msgs/Odometry publisher on /odometry/filtered.",
             source="upstream_code", ref=_NODE_SETUP_REF),
        Fact("The node imports Empty from std_msgs.msg and Odometry from nav_msgs.msg for its ROS 2 "
             "interface.", source="upstream_code", ref=_NODE_MSG_IMPORTS_REF),
        Fact("The robots configuration imports LowState and LowCmd from unitree_go.msg.",
             source="upstream_code", ref=_UNITREE_MSG_IMPORTS_REF),
        Fact("Go2Configuration returns LowStateGo2 from lowstate_msgs_type and LowCmdGo2 from "
             "lowcmd_msgs_type.", source="upstream_code", ref=_GO2_TYPES_REF),
        Fact("The node creates a subscription for the robot's LowCmd type on /lowcmd with queue size 10 and "
             "callback receive_cmd_cb, and initialises last_cmd_msg to a default-constructed LowCmd.",
             source="upstream_code", ref=_LOWCMD_SUB_REF),
        Fact("When unlock_base is false, the node subscribes std_msgs/Empty on /unlock_base with queue "
             "size 1 and its callback calls unlock_base().", source="upstream_code",
             ref=_UNLOCK_AND_RESET_REF),
        Fact("The node subscribes std_msgs/Empty on /reset with queue size 1 and its callback calls "
             "reset().", source="upstream_code", ref=_RESET_SUB_REF),
        Fact("The node creates a timer with the robot's high_level_period.", source="upstream_code",
             ref=_TIMER_REF),
        Fact("Go2Configuration returns high_level_period 1.0/500.0 and low_level_sub_step 12.",
             source="upstream_code", ref=_GO2_PERIOD_REF),
        Fact("n_dof is len(joint_names).", source="upstream_code", ref=_N_DOF_REF),
        Fact("Go2Configuration lists the 12 joint names in FR, FL, RR, RL order with three joints per "
             "leg.", source="upstream_code", ref=_GO2_JOINTS_REF),
        Fact("The timer callback reads q, dq, tau, kp and kd from the first n_dof motor_cmd entries of "
             "last_cmd_msg.", source="upstream_code", ref=_UPDATE_REF),
        Fact("For each high-level step the node computes tau_cmd = tau_des - kp*(q_current - q_des) - "
             "kd*(v_current - v_des) and calls simulator.step once per low-level sub-step.",
             source="upstream_code", ref=_UPDATE_REF),
        Fact("The callback publishes motor_state mode=1, q and dq for every Go2 joint.",
             source="upstream_code", ref=_LOWSTATE_FILL_REF),
        Fact("Go2Configuration.foot_force_to_val returns 14.2 + 0.562 * force.",
             source="upstream_code", ref=_GO2_FOOT_REF),
        Fact("When the robot has feet sensors, the callback publishes int(foot_force_to_val(force)) "
             "for every contact force in LowState.foot_force.", source="upstream_code",
             ref=_LOWSTATE_FILL_REF),
        Fact("The callback rearranges the base quaternion from xyzw to wxyz, publishes gyroscope as the "
             "local angular velocity and accelerometer as local linear acceleration plus the rotated "
             "gravity vector 9.81; a comment on the gravity rotation says this seems wrong.",
             source="upstream_code", ref=_IMU_REF),
        Fact("The callback fills Odometry with frame odom and child frame base, pose x/y/z and the xyzw "
             "quaternion and twist linear/angular values from the simulator state.",
             source="upstream_code", ref=_ODOM_FILL_REF),
        Fact("The receive callback only assigns the message to last_cmd_msg.", source="upstream_code",
             ref=_RECEIVE_REF),
        Fact("reset() calls simulator.reset() and, when unlock_base_default is true, also calls "
             "simulator.unlock_base().", source="upstream_code", ref=_RESET_IMPL_REF),
        Fact("unlock_base() logs and calls simulator.unlock_base().", source="upstream_code",
             ref=_UNLOCK_IMPL_REF),
        Fact("The abstract wrapper documents unlock_base as releasing a base that was spawned fixed in "
             "the world and reset as resetting the simulation and re-locking the base.",
             source="upstream_code", ref=_WRAPPER_REF),
        Fact("The node's constructor creates publishers, subscriptions and a timer only; it creates no "
             "ROS service server or action server.", source="upstream_code", ref=_NODE_SETUP_REF),
        Fact("reset() does not assign last_cmd_msg.", source="upstream_code", ref=_RESET_IMPL_REF),
        Fact("BulletWrapper.reset moves the base to q_start and every joint whose id passes 'if id:' (a joint at "
             "index 0 does not) to its q_start value, sets zero-force velocity control on the joints and creates "
             "a fixed constraint that locks the base when none exists.",
             source="upstream_code", ref="unitree_simulation/bullet_wrapper.py:70-99"),
        Fact("The README describes the package as a ROS 2 simulation of the Unitree Go2 that mimics its "
             "ROS 2 API by replicating the most-used topics.", source="vendor_doc", ref=_README_REF),
        Fact("package.xml describes the package as a basic simulator wrapper that mimics the real Go2 "
             "ROS 2 control API.", source="vendor_doc", ref=_PACKAGE_REF),
    ]

    #: One request step at timeout_ms 1000 plus confirm_within_ms 1500.
    estop_latency_ms = 2500
    safe_state = (
        "Simulated only: a zero-gain LowCmd is on /lowcmd and twelve /lowstate joint velocities plus the "
        "/odometry/filtered linear and angular twist are inside the operator bounds for three fresh samples."
    )

    #: The fake is an event-driven rosbridge contract stand-in, not a physics
    #: engine and not a recording of captured traffic.  It runs no pybullet or
    #: Simple integration, no timer and no contacts.
    fidelity = {
        "engine": "analytic:ROS fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven rosbridge fake with no physics step, timer pacing, contact model or "
                     "state-hash replay; placeholder LowState and Odometry samples",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free rosbridge contract stand-in, not a recording of captured traffic: it "
            "runs no pybullet or Simple physics, timer, contacts, foot sensors or wall-clock loop",
            "the /lowstate and /odometry/filtered values are placeholders; the first sample of a subscription "
            "echoes the last LowCmd q/dq, and later samples are a placeholder stream (joint dq 0.4 until kp, kd "
            "and tau are zero, then 0) spaced on the wall clock, not pybullet and not the 500 Hz timer",
            "the motor_state q and dq entries are a placeholder echo of the last published LowCmd, used "
            "only as a contract effect; they are not pybullet-measured joint state",
            "the fake models one /lowcmd message as the node stores it, but it does not reproduce the "
            "500 Hz timer, the 12 low-level sub-steps per callback, the torque formula or the base lock",
            "/reset and /unlock_base are recorded only; the fake has no pybullet simulator to reset or "
            "unlock and no base constraint",
            "the G1 variant is out of scope: it uses unitree_hg messages, 29 joints and a 1 kHz period, "
            "which a single static rosbridge declaration on /lowcmd cannot also carry",
            "the fake returns exactly 12 motor entries and four foot-force entries for Go2; it does not "
            "carry the other LowState fields of the real unitree_go message",
            "the node has no stop service or action; the e-stop is a sensed-confirmation stop (SAFE-049, simulated "
            "only) that publishes twenty zero MotorCmd entries on /lowcmd and is achieved only when twelve "
            "/lowstate joint velocities (arrival freshness, min_interval_ms 1, publisher at simulation_node.py:56) "
            "and the stamped /odometry/filtered twist (:57, :139) hold for three samples spanning 4 ms within "
            "1500 ms, which is three samples at the 500 Hz timer; thresholds are operator_required placeholders "
            "in fixtures/estop-confirmation.json",
            "the Go2 timer period is 1/500 s (robots_configuration.py:169-171). Three samples span 4 ms "
            "(min_span_ms 4). A slower timer still confirms while the gap stays under max_gap_ms 500. A stream "
            "closer than min_interval_ms 1 restarts the arrival count. Raising min_span_ms above 4 without a "
            "matching slower period fails closed. A replay spaced at or above min_interval_ms is not distinguished "
            "from live samples (the same residual as a fresh topic read-back)",
            "/reset and /unlock_base are not the stop: reset() does not assign last_cmd_msg (simulation_node.py:"
            "180-183), so those publications stay ordinary commands",
            "the default launch sets unlock_base false (launch/launch_sim.launch.py:9-19), so the base can sit "
            "still while the legs move; the predicate therefore includes the twelve joint velocities",
            "the stop request sends 20 MotorCmd entries because that is the requested wire shape; this clone only "
            "shows n_dof 12, and the unitree_go array length is outside the clone",
            "a live run requires a colcon/ament workspace with rclpy, unitree_ros2 messages, "
            "unitree_description, numpy, scipy and pybullet, plus the operator's rosbridge; none of them "
            "is installed, started or validated here",
            "the node mimics the real Go2 ROS 2 API on the same absolute topics (/lowcmd, /lowstate; README.md:3, "
            "package.xml:6), so on a graph that also carries a real Go2's unitree_ros2 bridge a /lowcmd "
            "publication of this package would reach the real robot; nothing in the package can tell the two apart",
            "the unitree_go LowCmd and LowState definitions are outside the clone: the node indexes motor_cmd and "
            "motor_state of default-constructed messages (simulation_node.py:62, 81-85, 98-108), so both are "
            "pre-sized arrays, and unitree_ros2 declares them with 20 entries; rosbridge may then refuse this "
            "package's 12-entry motor_cmd publication, and a real LowState carries more motor_state entries than "
            "the 12 the node fills (the read no longer fixes their count)",
            "the fake's Odometry is a placeholder in the ROS 2 shape; its LowState carries only mode, q and dq per "
            "motor entry, not the other MotorState fields of the real message",
        ],
    }

    parameters = {"pose": _POSE, "twist": _TWIST, "motor_state": _MOTOR_STATE}
    reads = {
        "pose": dict(_ODOMETRY, path="pose.pose", timeout_ms=2000),
        "twist": dict(_ODOMETRY, path="twist.twist", timeout_ms=2000),
        "motor_state": dict(_LOWSTATE_TOPIC, path="motor_state", timeout_ms=2000),
    }

    commands = {
        "x-cap.inria-paris-robotics-lab.lowcmd.v1": _LOWCMD,
        "x-cap.inria-paris-robotics-lab.lowstate.v1": _LOWSTATE,
        "x-cap.inria-paris-robotics-lab.reset.v1": _RESET,
        "x-cap.inria-paris-robotics-lab.unlock_base.v1": _UNLOCK_BASE,
    }

    actions = {
        "x-cap.inria-paris-robotics-lab.lowcmd.v1": Action(
            name="publish_lowcmd",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one unitree_go/LowCmd on /lowcmd; the node applies it on its next timer tick. "
                "Transmission only: no execution, arrival or stop acknowledgement."
            ),
            input={"motor_cmd": _MOTOR_CMD_VECTOR},
            output=_PUBLISHED,
            examples=[{"motor_cmd": _ZERO_MOTOR_CMD}],
        ),
        "x-cap.inria-paris-robotics-lab.lowstate.v1": Action(
            name="read_lowstate",
            verb="read",
            description="Subscribe once to /lowstate; return the motor q/dq, foot-force and IMU values.",
            output=_LOWSTATE_OUTPUT,
        ),
        "x-cap.inria-paris-robotics-lab.reset.v1": Action(
            name="reset_simulation",
            verb="invoke",
            risk="R1",
            description=(
                "Publish Empty on /reset; the node calls simulator.reset() and may unlock the base. "
                "A reset is not a stop: last_cmd_msg is kept and the timer keeps stepping."
            ),
            output=_PUBLISHED,
        ),
        "x-cap.inria-paris-robotics-lab.unlock_base.v1": Action(
            name="unlock_base",
            verb="invoke",
            risk="R1",
            description=(
                "Publish Empty on /unlock_base; the callback releases the fixed base constraint. "
                "Not a stop and has no acknowledgement."
            ),
            output=_PUBLISHED,
        ),
    }

    # The pinned node has no ROS service or action server.  The stop is the sensed confirmation above.
    safety_bindings = {"sensed_stop": _SENSED_STOP}
