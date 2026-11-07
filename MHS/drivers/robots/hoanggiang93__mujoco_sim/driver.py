"""OpenMHS rosbridge declaration for the MuJoCo ROS 1 simulator (gh.hoanggiang93/mujoco_sim).

The pinned upstream is a Catkin ROS 1 workspace.  Its ``mujoco_sim`` node is a
C++ process that steps MuJoCo continuously on its own thread, publishes object
and joint state topics, and advertises four ``std_srvs``/``mujoco_msgs``
services.  This package is a configuration-only :class:`RosDriver` over
rosbridge; it declares no Python native class and neither imports nor launches
the simulator or ROS.

Scope: the acknowledged ``/mujoco/reset`` service (``std_srvs/Trigger``) and
the two state publications ``/mujoco/object_states``
(``mujoco_msgs/ObjectStateArray``) and ``/mujoco/robot_joint_states``
(``sensor_msgs/JointState``).  The shipped ``src/config/robot.yaml`` sets all
object-state and joint-state publisher rates to 0.0, so a deployment must set
the relevant rate parameter above zero before either observation can receive a
sample.

The package is deliberately not a completed control integration.  The reset
callback restores robot joint positions and zeroes joint/odometry velocities,
but the independent simulation thread keeps stepping and the callback restarts
the effort controllers it stopped.  The clone advertises no pause, stop or
e-stop service, so no genuine acknowledged safe state can be declared for this
effectful profile.  ``RESULT.json`` records the concrete blocker; the fake
below is a ROS-free contract stand-in, not a stopped simulator.

Every endpoint, type and fact cites the pinned clone at
dd1cf9096a043589f338374f4c67a675c34a57b0.  No ROS graph, simulator process or
hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: MjRos::init advertises the absolute reset service with the Trigger callback.
_RESET = {
    "service": "/mujoco/reset",
    "type": "std_srvs/Trigger",
    "source_name": "/mujoco/reset",
    "source_ref": "src/mujoco_sim/mj_ros.cpp:540",
    "type_ref": "include/mujoco_sim/mj_ros.h:36",
    "success": {"path": "success", "equals": True},
    "result": {"map": {"success": "success", "message": "message"}},
}

#: MjRos::init advertises the object-state array on an absolute topic.
_OBJECT_STATES = {
    "topic": "/mujoco/object_states",
    "type": "mujoco_msgs/ObjectStateArray",
    "source_name": "/mujoco/object_states",
    "source_ref": "src/mujoco_sim/mj_ros.cpp:560",
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"objects": "object_states"}},
}

#: MjRos::init advertises the robot joint-state topic on an absolute topic.
_JOINT_STATES = {
    "topic": "/mujoco/robot_joint_states",
    "type": "sensor_msgs/JointState",
    "source_name": "/mujoco/robot_joint_states",
    "source_ref": "src/mujoco_sim/mj_ros.cpp:561",
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"names": "name", "positions": "position",
                        "velocities": "velocity", "efforts": "effort"}},
}

_VECTOR3 = Field(
    "object",
    description="Three-component vector from the simulator message; the clone declares no unit field",
    properties={
        "x": Field("number", description="x component"),
        "y": Field("number", description="y component"),
        "z": Field("number", description="z component"),
    },
)

_QUATERNION = Field(
    "object",
    description="Orientation quaternion from the simulator message",
    properties={
        "x": Field("number", description="Quaternion x"),
        "y": Field("number", description="Quaternion y"),
        "z": Field("number", description="Quaternion z"),
        "w": Field("number", description="Quaternion w"),
    },
)

_OBJECT_STATE = Field(
    "object",
    description="One mujoco_msgs/ObjectState entry",
    properties={
        "name": Field("string", description="MuJoCo body name"),
        "pose": Field(
            "object",
            description="Body pose in the published frame",
            properties={"position": _VECTOR3, "orientation": _QUATERNION},
        ),
        "velocity": Field(
            "object",
            description="Body velocity; populated only for free bodies with six degrees of freedom",
            properties={"linear": _VECTOR3, "angular": _VECTOR3},
        ),
    },
)

_OBJECTS = Field(
    "array",
    items=_OBJECT_STATE,
    description="mujoco_msgs/ObjectStateArray.object_states in message order",
)

_JOINT_VECTOR = Field(
    "array",
    items=Field("number"),
    description="Joint quantity in message order; the native unit follows each joint type in the loaded MJCF",
)


class MujocoSim(RosDriver):
    device_id = "mujoco_sim"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeMujocoSim"}
    tags = ["ros", "ros1", "simulation", "mujoco", "reset", "object-states", "joint-states"]
    display_name = "MuJoCo ROS 1 simulator"
    vendor = "HoangGiang93"
    facts = [
        Fact("MjRos::init advertises /mujoco/reset with the reset_robot_service callback.",
             source="upstream_code", ref="src/mujoco_sim/mj_ros.cpp:540"),
        Fact("reset_robot_service takes a std_srvs/Trigger request, stops running effort controllers, "
             "resets the robot data, sleeps 100 model timesteps, sets response.success from an error_sum "
             "threshold and then restarts the controllers it stopped.",
             source="upstream_code", ref="src/mujoco_sim/mj_ros.cpp:779-856"),
        Fact("reset_robot creates new mjData, writes each robot joint qpos from joint_inits or zero, zeroes "
             "the joint qvel and qacc, zeroes the odometry velocities and calls mj_forward.",
             source="upstream_code", ref="src/mujoco_sim/mj_ros.cpp:569-609"),
        Fact("The simulate loop calls mj_step1 and mj_step2 continuously while ros::ok and adjusts the model "
             "timestep toward real time; it has no pause, stop or step-request branch.",
             source="upstream_code", ref="src/mj_main.cpp:76-164"),
        Fact("main starts the simulate function on its own thread, next to three ROS setup threads.",
             source="upstream_code", ref="src/mj_main.cpp:198-203"),
        Fact("MjRos::init advertises /mujoco/object_states as mujoco_msgs/ObjectStateArray.",
             source="upstream_code", ref="src/mujoco_sim/mj_ros.cpp:560"),
        Fact("MjRos::init advertises /mujoco/robot_joint_states as sensor_msgs/JointState.",
             source="upstream_code", ref="src/mujoco_sim/mj_ros.cpp:561"),
        Fact("publish_object_state_array returns without publishing when the configured rate is below 1E-9.",
             source="upstream_code", ref="src/mujoco_sim/mj_ros.cpp:1770-1773"),
        Fact("publish_joint_states returns without publishing when the configured rate is below 1E-9.",
             source="upstream_code", ref="src/mujoco_sim/mj_ros.cpp:1812-1815"),
        Fact("The shipped src/config/robot.yaml sets the object-state and joint-state publication rates to "
             "0.0 for robot, world and spawned-object bodies.",
             source="upstream_code", ref="src/config/robot.yaml:74-83"),
        Fact("MjRos::init advertises exactly the /mujoco/screenshot, /mujoco/reset, /mujoco/spawn_objects and "
             "/mujoco/destroy_objects services; no pause, stop or e-stop service is advertised.",
             source="upstream_code", ref="src/mujoco_sim/mj_ros.cpp:537-546"),
        Fact("The per-robot /<robot>/cmd_vel subscription is created only when at least one odometry joint is "
             "configured for that robot.",
             source="upstream_code", ref="src/mujoco_sim/mj_ros.cpp:522-533"),
        Fact("CmdVelCallback::callback writes the robot's six odometry velocity entries from the Twist, 0.0 for "
             "an axis without an odometry joint.",
             source="upstream_code", ref="src/mujoco_sim/mj_ros.cpp:193-200"),
        Fact("publish_object_state_array starts one thread each for robot, world and spawned-object bodies; each "
             "thread fills its own array and publishes it through the one object_state_array_pub publisher at "
             "its own rate.",
             source="upstream_code", ref="src/mujoco_sim/mj_ros.cpp:1757-1792"),
    ]
    #: The deployed fake is a ROS-free recording transport, not MuJoCo and not a ROS node.
    fidelity = {
        "engine": "analytic:ROS recording fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven recording fake with no physics step or pacing; the placeholder object and "
                     "joint samples do not establish trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free RecordingRosTransport: it answers the declared reset service and the two "
            "subscriptions with placeholder messages and runs no MuJoCo engine, ros_control loop, ROS node or "
            "wall-clock pacing",
            "the fake reset only increments a counter and returns a placeholder Trigger response; it does not "
            "reset mjData, restart controllers or reproduce the upstream error_sum check",
            "the shipped src/config/robot.yaml sets all object-state and joint-state publisher rates to 0.0, so "
            "a live deployment must raise the relevant rate parameter before either observation can receive a "
            "fresh sample",
            "the object and joint samples are placeholders and do not describe any loaded MJCF model; the real "
            "array sizes and body/joint names are scene-dependent",
            "upstream publishes robot, world and spawned-object bodies as separate arrays on the same "
            "/mujoco/object_states topic at their own rates, so one live sample holds one body category; the "
            "fake always returns the same one-body placeholder array",
            "the clone advertises no acknowledged pause, stop or e-stop; the effectful reset callback leaves "
            "the independent simulation thread stepping and restarts the effort controllers, so this package "
            "cannot claim a confirmed safe state",
            "the package does not expose /mujoco/screenshot, /mujoco/spawn_objects, /mujoco/destroy_objects, "
            "the /<robot>/cmd_vel input, TF, marker arrays, base pose odometry or /mujoco/sensors_3D",
        ],
    }

    # The reset service is effectful: it mutates joint state.  The two topics
    # are explicit observation capabilities, not an automatic resource
    # snapshot, because their publishers can be configured off.
    commands = {
        "x-cap.hoanggiang93.reset.v1": _RESET,
        "x-cap.hoanggiang93.object_states.v1": _OBJECT_STATES,
        "x-cap.hoanggiang93.robot_joint_states.v1": _JOINT_STATES,
    }
    actions = {
        "x-cap.hoanggiang93.reset.v1": Action(
            name="reset",
            verb="invoke",
            description="Call the acknowledged /mujoco/reset Trigger service; this is not a stop",
            output={
                "success": Field("boolean",
                                 description="Trigger response success flag from the reset callback"),
                "message": Field("string",
                                 description="Trigger response message, including the callback error_sum text"),
            },
        ),
        "x-cap.hoanggiang93.object_states.v1": Action(
            name="read_object_states",
            verb="read",
            description="Read one mujoco_msgs/ObjectStateArray sample from /mujoco/object_states",
            output={"objects": _OBJECTS},
        ),
        "x-cap.hoanggiang93.robot_joint_states.v1": Action(
            name="read_robot_joint_states",
            verb="read",
            description="Read one sensor_msgs/JointState sample from /mujoco/robot_joint_states",
            output={
                "names": Field("array", items=Field("string"),
                               description="JointState.name in message order"),
                "positions": _JOINT_VECTOR,
                "velocities": _JOINT_VECTOR,
                "efforts": _JOINT_VECTOR,
            },
        ),
    }
