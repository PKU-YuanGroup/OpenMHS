"""OpenMHS rosbridge driver for the saga0619 mujoco_ros_sim bridge.

The pinned repository is a ROS 1 catkin workspace: the C++ ``mujoco_ros`` node
loads a MuJoCo model, publishes joint states, sensor states and simulation
time, and consumes position/torque commands from ``mujoco_ros_msgs/JointSet``.
This package is a configuration-only :class:`RosDriver` over rosbridge.  It
declares no Python native class, imports no ROS, and launches neither ROS nor
MuJoCo.

Primary control is one ``mujoco_ros_msgs/JointSet`` publication on
``/mujoco_ros_interface/joint_set`` in position or torque mode.  A rosbridge
publish receipt is transmission evidence only: the upstream callback does not
publish an acknowledgement and uses a command only when its ``time`` is not
after ``mjData.time`` and at most 0.01 s older.  An older command is logged and
dropped while ``cmd_rcv`` stays set, so the previous command stays applied.
The callback's size check reads the node's own buffer, which it resized to the
model's actuator count, not the received array, so a shorter array is read
past its end.  The observation surface is the node's
``sensor_msgs/JointState``, ``mujoco_ros_msgs/SensorState`` and
``std_msgs/Float32`` publications.

The pinned clone has no ROS service or action.  Its only stop-like inputs are
the unacknowledged ``pause`` toggle and the ``mjreset`` keyframe reset on
``/mujoco_ros_interface/sim_command_con2sim``.  Neither can be an acknowledged
stop, so the RosDriver e-stop has no native stop path and the package is
reported blocked with HELPER_MISSING rather than claiming a safe state.  The
driver still declares the real control surface; a zero-command publication is
not treated as a stop.

Every endpoint, type and fact cites the pinned clone at
dcdfd09ac6a4f5fc03c4a0b1a83b3faaf41f94bd.  The fake transport is ROS-free; it is
an analytic contract fake, not a captured-traffic replay, and every value it
returns is a placeholder.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: The README lists each default endpoint together with its ROS type.
_JOINT_STATES_REF = "README.md:32"
_SENSOR_STATES_REF = "README.md:33"
_SIM_TIME_REF = "README.md:34"
_JOINT_SET_REF = "README.md:38"

#: The node builds the same names from the /mujoco_ros_interface prefix.
_PREFIX_REF = "mujoco_ros/src/main.cpp:138-162"

#: The publisher and subscriber registrations state queue sizes and types.
_REGISTRATION_REF = "mujoco_ros/src/main.cpp:164-172"

#: The command callback compares time and copies position/torque into command[].
_JOINT_SET_CALLBACK_REF = "mujoco_ros/src/mjros.cpp:47-96"

#: The message definition declares the mode and the two actuator arrays.
_JOINT_SET_MSG_REF = "mujoco_ros_msgs/msg/JointSet.msg:1-10"

#: The state publisher copies qpos, qvel and qacc into the JointState fields.
_STATE_PUBLISHER_REF = "mujoco_ros/src/mjros.cpp:270-336"

#: The initialization sizes every array from the loaded model.
_STATE_INIT_REF = "mujoco_ros/src/mjros.cpp:155-251"

#: The command callback has no acknowledgement, and pause toggles the run flag.
_SIM_COMMAND_CALLBACK_REF = "mujoco_ros/src/mjros.cpp:98-129"

#: mjreset sets reset_request; the event loop consumes it with c_reset.
_RESET_POLL_REF = "mujoco_ros/src/mjros.cpp:146-153"
_RESET_BODY_REF = "mujoco_ros/src/mjros.cpp:5-43"
_CONNECTOR_REF = "mujoco_ros/src/mjros.cpp:442-498"

#: mycontroller applies the cached command only while settings.run and cmd_rcv.
_CONTROLLER_REF = "mujoco_ros/src/mjros.cpp:500-618"
_SIMULATE_REF = "mujoco_ros/src/mjros.cpp:2233-2290"

#: mjData fields copied by the state publisher.
_TIME_FIELD_REF = "mujoco210/include/mjdata.h:155"
_STATE_FIELD_REF = "mujoco210/include/mjdata.h:167-178"

#: Manifest and build evidence.
_README_INSTALL_REF = "README.md:15"
_MANIFEST_REF = "mujoco_ros/package.xml:51-60"
_BUILD_REF = "mujoco_ros/CMakeLists.txt:6-19"
_LICENSE_REF = "mujoco_ros/package.xml:16"


# ---------------------------------------------------------------------------
# Message fields and outputs
# ---------------------------------------------------------------------------

_PUBLISHED = {
    "published": Field("boolean", description="True when rosbridge accepted the publication"),
    "confirmed": Field("boolean", description="Always false: a ROS topic publication carries no execution or "
                                               "stopping confirmation"),
}

_JOINT_NAMES = Field(
    "array",
    description="Joint names filled by state_publisher_init from the loaded model",
    items=Field("string", description="One joint name from m->names"),
)

_JOINT_VALUES = Field(
    "array",
    description="Raw MuJoCo generalized-coordinate values; the clone states no physical unit",
    items=Field("number", description="One qpos, qvel or qacc element"),
)

_JOINT_STATE_OUTPUT = {
    "names": _JOINT_NAMES,
    "positions": Field(
        "array",
        description="sensor_msgs/JointState position, copied from mjData.qpos; the clone states no unit",
        items=Field("number", description="One qpos element"),
    ),
    "velocities": Field(
        "array",
        description="sensor_msgs/JointState velocity, copied from mjData.qvel; the clone states no unit",
        items=Field("number", description="One qvel element"),
    ),
    "efforts": Field(
        "array",
        description="sensor_msgs/JointState effort, copied from mjData.qacc (an acceleration) by the upstream "
                    "publisher; it is not a torque",
        items=Field("number", description="One qacc element"),
    ),
}

_SENSOR_ENTRY = Field(
    "object",
    description="One mujoco_ros_msgs/SensorBase entry",
    properties={
        "name": Field("string", description="Sensor name from the loaded model, or 'user information'"),
        "data": Field("array", description="Raw mjData.sensordata values for this sensor",
                      items=Field("number", description="One sensor value")),
    },
)

_SENSOR_STATE_OUTPUT = {
    "sensors": Field("array", description="All sensors plus the trailing user-information entry",
                     items=_SENSOR_ENTRY),
}

_SIM_TIME_OUTPUT = {
    "sim_time": Field("number", unit="s",
                      description="Simulation time read from mjData.time by state_publisher"),
}

_JOINT_INPUT = {
    "sim_time": Field(
        "number", unit="s",
        description="Simulator time at which the controller built this command; the callback accepts it only "
                    "when it is not in the future and not more than 0.01 s older than mjData.time",
    ),
}

_POSITION_INPUT = dict(_JOINT_INPUT)
_POSITION_INPUT["positions"] = Field(
    "array",
    description="Actuator targets in the loaded model's m->nu order; the callback copies m->nu entries without "
                "checking the received length, so send exactly m->nu values",
    items=Field("number", description="One raw mjData.ctrl target in the loaded model's own units"),
)

_TORQUE_INPUT = dict(_JOINT_INPUT)
_TORQUE_INPUT["torques"] = Field(
    "array",
    description="Actuator torques in the loaded model's m->nu order; the callback copies m->nu entries without "
                "checking the received length, so send exactly m->nu values",
    items=Field("number", description="One raw mjData.ctrl target in the loaded model's own units"),
)

#: One position-mode JointSet publication.  MODE is the message's literal
#: mode value; the body time is mapped from the caller's simulation time.
_JOINT_POSITION = {
    "topic": "/mujoco_ros_interface/joint_set",
    "type": "mujoco_ros_msgs/JointSet",
    "operation": "publish",
    "source_ref": _JOINT_SET_REF,
    "message": {"header": {}, "time": 0.0, "MODE": 0, "position": [], "torque": []},
    "args": {
        "time": {"from": "input.sim_time"},
        "position": {"from": "input.positions"},
    },
}

#: One torque-mode JointSet publication.
_JOINT_TORQUE = {
    "topic": "/mujoco_ros_interface/joint_set",
    "type": "mujoco_ros_msgs/JointSet",
    "operation": "publish",
    "source_ref": _JOINT_SET_REF,
    "message": {"header": {}, "time": 0.0, "MODE": 1, "position": [], "torque": []},
    "args": {
        "time": {"from": "input.sim_time"},
        "torque": {"from": "input.torques"},
    },
}

#: One fresh JointState subscription per call; no cached sample is returned.
_JOINT_STATES = {
    "topic": "/mujoco_ros_interface/joint_states",
    "type": "sensor_msgs/JointState",
    "operation": "subscribe",
    "source_ref": _JOINT_STATES_REF,
    "path": "$",
    "result": {"map": {
        "names": "name",
        "positions": "position",
        "velocities": "velocity",
        "efforts": "effort",
    }},
}

#: One fresh SensorState subscription per call.
_SENSOR_STATES = {
    "topic": "/mujoco_ros_interface/sensor_states",
    "type": "mujoco_ros_msgs/SensorState",
    "operation": "subscribe",
    "source_ref": _SENSOR_STATES_REF,
    "path": "$",
    "result": {"map": {"sensors": "sensor"}},
}

#: One fresh Float32 simulation-time subscription per call.
_SIM_TIME = {
    "topic": "/mujoco_ros_interface/sim_time",
    "type": "std_msgs/Float32",
    "operation": "subscribe",
    "source_ref": _SIM_TIME_REF,
    "path": "data",
    "result": {"map": {"sim_time": "output.$"}},
}


class MujocoRosSim(RosDriver):
    device_id = "mujoco-ros-sim"
    device_kind = "world.sim"
    mode = "simulated"
    #: All commanded values are confined to mjData/mj_step in the simulator
    #: process; no binding in this package reaches physical equipment.
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeMujocoRosSim"}
    tags = ["ros", "ros1", "simulation", "mujoco", "joint-command", "joint-state", "sensor-state"]
    display_name = "MuJoCo ROS simulator interface"
    vendor = "saga0619"
    model = "mujoco_ros (MuJoCo 2.1 bridge)"
    facts = [
        Fact("The README states that MuJoCo sends joint and sensor data over ROS topics and receives torque or "
             "position command data over ROS topics.", source="vendor_doc", ref="README.md:5"),
        Fact("The documented publishers are /mujoco_ros_interface/joint_states (sensor_msgs/JointState), "
             "/mujoco_ros_interface/sensor_states (mujoco_ros_msgs/SensorState) and /mujoco_ros_interface/sim_time "
             "(std_msgs/Float32).", source="vendor_doc", ref="README.md:32-34"),
        Fact("The documented subscribers are /mujoco_ros_interface/sim_command_con2sim (std_msgs/String) and "
             "/mujoco_ros_interface/joint_set (mujoco_ros_msgs/JointSet).", source="vendor_doc",
             ref="README.md:37-38"),
        Fact("The README documents /mujoco_ros_interface/applied_ext_force (mujoco_ros_msgs/applyforce) with a "
             "link index, a force and a torque.", source="vendor_doc", ref="README.md:41-42"),
        Fact("main subscribes the sim_command_con2sim String command topic and the applied_ext_force topic, and "
             "advertises sim_command_sim2con.", source="upstream_code", ref="mujoco_ros/src/main.cpp:128-130"),
        Fact("The node builds topic names from the /mujoco_ros_interface prefix, inserts a non-root node namespace, "
             "and appends /joint_set, /joint_states, /sim_time and /sensor_states.",
             source="upstream_code", ref=_PREFIX_REF),
        Fact("joint_set is subscribed with queue size 1 and tcpNoDelay(true); joint_states, sim_time and "
             "sensor_states are advertised with queue size 1; pub_mode instead advertises SimStatus.",
             source="upstream_code", ref=_REGISTRATION_REF),
        Fact("jointset_callback compares msg->time with mjData.time, accepts it only when it is not in the future "
             "and its age is at most 0.01 s, then copies msg->torque when MODE is 1 or msg->position when MODE is 0 "
             "into command[] for the loaded model's m->nu actuators.", source="upstream_code",
             ref=_JOINT_SET_CALLBACK_REF),
        Fact("jointset_callback sets cmd_rcv before its time checks; a command older than 0.01 s only logs an error, "
             "so cmd_rcv stays true and command[] keeps the previous values.", source="upstream_code",
             ref="mujoco_ros/src/mjros.cpp:50-66"),
        Fact("In both modes the size check compares joint_set_msg_.torque.size(), the node's own message buffer, "
             "with m->nu before copying m->nu entries of the received array.", source="upstream_code",
             ref="mujoco_ros/src/mjros.cpp:71-94"),
        Fact("state_publisher_init resizes joint_set_msg_.position and joint_set_msg_.torque to m->nu.",
             source="upstream_code", ref="mujoco_ros/src/mjros.cpp:160-161"),
        Fact("JointSet.msg declares Header header, float64 time, int32 MODE, float64[] position and float64[] torque, "
             "with MODE 0 documented as POSITION and MODE 1 as TORQUE.", source="upstream_code",
             ref=_JOINT_SET_MSG_REF),
        Fact("state_publisher_init sizes the command arrays from m->nu and the JointState arrays from m->nu, m->njnt "
             "or the six virtual base entries, and creates an extra user-information sensor entry of two values.",
             source="upstream_code", ref=_STATE_INIT_REF),
        Fact("state_publisher sets sim_time.data from mjData.time, publishes JointState position, velocity and effort "
             "from qpos, qvel and qacc, and publishes SensorState values from mjData.sensordata; the trailing user "
             "information entry holds dif_time and com_time.", source="upstream_code", ref=_STATE_PUBLISHER_REF),
        Fact("The sim_command_callback handles RESET and INIT controller handshakes, toggles settings.run on "
             "'pause', sets reset_request on 'mjreset', and publishes no acknowledgement on sim_command_sim2con.",
             source="upstream_code", ref=_SIM_COMMAND_CALLBACK_REF),
        Fact("rosPollEvents calls c_reset when reset_request is true.", source="upstream_code",
             ref=_RESET_POLL_REF),
        Fact("c_reset calls mj_resetData, copies the selected keyframe time/qpos/qvel/act, and clears "
             "cmd_rcv.", source="upstream_code", ref=_RESET_BODY_REF),
        Fact("c_reset calls mujoco_ros_connector_init, which publishes RESET and waits up to 1.0 s for the "
             "controller's RESET reply, then publishes INIT and waits up to 1.0 s for its reply before restoring "
             "the control callback.", source="upstream_code", ref=_CONNECTOR_REF),
        Fact("mycontroller calls ros::spinOnce, publishes state only while settings.run, and copies the cached "
             "command into d->ctrl only when cmd_rcv is set.", source="upstream_code", ref=_CONTROLLER_REF),
        Fact("The simulate thread steps physics only inside the settings.run branch and otherwise runs the paused "
             "branch.", source="upstream_code", ref=_SIMULATE_REF),
        Fact("mjData.time is the simulation time.", source="upstream_code", ref=_TIME_FIELD_REF),
        Fact("mjData stores qpos as position (nq values), qvel as velocity (nv values) and qacc as acceleration "
             "(nv values).", source="upstream_code", ref=_STATE_FIELD_REF),
        Fact("The README installation step clones the repository into a catkin workspace src directory and builds "
             "it with catkin_make.", source="vendor_doc", ref=_README_INSTALL_REF),
        Fact("mujoco_ros/package.xml declares catkin build and exec dependencies on roscpp, std_msgs and "
             "mujoco_ros_msgs.", source="upstream_code", ref=_MANIFEST_REF),
        Fact("The CMake project finds roscpp, std_msgs, mujoco_ros_msgs and eigen_conversions and includes the "
             "vendored mujoco210 headers.", source="upstream_code", ref=_BUILD_REF),
        Fact("The mujoco_ros package manifest declares its license as TODO.", source="upstream_code",
             ref=_LICENSE_REF),
    ]
    safe_state = (
        "No acknowledged stop exists in the pinned clone: the only stop-like inputs are the unacknowledged 'pause' "
        "toggle and the 'mjreset' keyframe reset on /mujoco_ros_interface/sim_command_con2sim, so the MHS software "
        "latch cannot confirm that the simulator stopped. A zero JointSet publication is also only transmission."
    )
    #: The package is a ROS-free analytic contract fake: no MuJoCo step,
    #: controller, physics, sensor model or pacing is present.
    fidelity = {
        "engine": "analytic:ROS contract fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned transport; no simulation step, pacing, trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free analytic contract transport: it answers the declared joint_states, "
            "sensor_states and sim_time subscriptions and records joint_set publications; it runs no MuJoCo, "
            "mj_step, controller, actuator, contact, sensor or ROS graph",
            "joint names, positions, velocities, accelerations, sensor names and sensor data are fixed "
            "placeholders; the real arrays are sized by the loaded MJCF model (m->nu, m->njnt, m->nsensor and "
            "m->sensor_dim), and the fake returns smaller placeholder arrays",
            "the fake does not advance mjData.time, integrate a command or echo a measured response; a joint_set "
            "publication is recorded but produces no motion",
            "no wall-clock pacing; there is no reset, pause or snapshot/restore capability",
            "the package deliberately leaves /mujoco_ros_interface/sim_command_con2sim, "
            "/mujoco_ros_interface/applied_ext_force and the shared-memory mode out of scope",
            "a live run needs the operator's mujoco_ros node, loaded MJCF model and rosbridge; endpoint namespace, "
            "model dimensions, message sizes and the simulator build were not exercised",
            "upstream defects at the pin: the joint_set size check reads the node's own buffer (always m->nu), so a "
            "shorter received array is read past its end, and a command older than 0.01 s leaves cmd_rcv set, so "
            "the previously accepted command keeps being applied; the fake models neither",
            "the observation values carry no unit because the clone states none for the generalized coordinates "
            "and sensor data",
        ],
    }

    # The simulator publishes only while running, so joint_states and sim_time
    # are explicit observations, never automatic resource reads.  The empty
    # resource snapshot returns {} without waiting for a paused topic.
    commands = {
        "x-cap.saga0619.joint_position_command.v1": _JOINT_POSITION,
        "x-cap.saga0619.joint_torque_command.v1": _JOINT_TORQUE,
        "x-cap.saga0619.joint_states.v1": _JOINT_STATES,
        "x-cap.saga0619.sensor_states.v1": _SENSOR_STATES,
        "x-cap.saga0619.sim_time.v1": _SIM_TIME,
    }
    actions = {
        "x-cap.saga0619.joint_position_command.v1": Action(
            name="publish_joint_positions",
            verb="invoke",
            description="Publish one position-mode mujoco_ros_msgs/JointSet command. The callback copies the "
                        "positions into its actuator command buffer only when the message time is within 0.01 s of "
                        "mjData.time; rosbridge reports transmission only, never a reached position.",
            input=_POSITION_INPUT,
            output=_PUBLISHED,
            examples=[{"sim_time": 0.0, "positions": [0.0, 0.0]}],
        ),
        "x-cap.saga0619.joint_torque_command.v1": Action(
            name="publish_joint_torques",
            verb="invoke",
            description="Publish one torque-mode mujoco_ros_msgs/JointSet command. The callback copies the torques "
                        "into its actuator command buffer only when the message time is within 0.01 s of "
                        "mjData.time; rosbridge reports transmission only.",
            input=_TORQUE_INPUT,
            output=_PUBLISHED,
            examples=[{"sim_time": 0.0, "torques": [0.0, 0.0]}],
        ),
        "x-cap.saga0619.joint_states.v1": Action(
            name="read_joint_states",
            verb="read",
            description="Read one fresh sensor_msgs/JointState sample from the simulator's joint_states publisher.",
            output=_JOINT_STATE_OUTPUT,
        ),
        "x-cap.saga0619.sensor_states.v1": Action(
            name="read_sensor_states",
            verb="read",
            description="Read one fresh mujoco_ros_msgs/SensorState sample from the simulator's sensor_states "
                        "publisher.",
            output=_SENSOR_STATE_OUTPUT,
        ),
        "x-cap.saga0619.sim_time.v1": Action(
            name="read_sim_time",
            verb="read",
            description="Read one fresh std_msgs/Float32 simulation-time sample from the simulator's sim_time "
                        "publisher.",
            output=_SIM_TIME_OUTPUT,
        ),
    }
    #: No safety binding exists.  A topic publication cannot be an acknowledged
    #: stop, and the upstream pause message is a toggle rather than an idempotent
    #: stop request.
    safety_bindings = {}
