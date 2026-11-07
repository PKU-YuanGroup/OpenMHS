"""OpenMHS rosbridge driver for the evronix quadruped ROS 2 Gazebo sim2sim stack.

The pinned repository is a ROS 2 (rclpy) sim-to-sim pipeline: three policy
controllers consume a ``geometry_msgs/PoseStamped`` velocity setpoint on
``/robot_velocity_command`` together with ``/imu_plugin/out`` and
``/joint_states``, and publish joint effort commands to the Gazebo effort
controller.  This package is a configuration-only :class:`RosDriver` over
rosbridge; it declares no Python native class and it imports, launches or
executes nothing from the clone.

Scope and honest limits:

* the primary control is one publication of the three velocity setpoints;
  rosbridge publication is transmission-only and proves neither motion nor a
  reached pose;
* the observations are explicit subscriptions, not an automatic resource
  snapshot, so a silent topic cannot block a velocity publication;
* the pinned nodes expose no stop service, stop action, pause service or
  reset service.  The e-stop is the Gazebo world pause of the simulator's own
  repository, cited as a reviewed companion source fetched at a pinned commit
  (user decision and authorisation of 2026-11-05; ``task.json``
  ``companions`` with ``lock``): gazebo_ros 3.9.0 (ROS 2 Humble)
  ``/pause_physics``, confirmed by a stall read-back (E1): two
  ``/get_model_list`` answers 250 ms apart whose ``header.stamp``, the
  world's sim time, did not advance.  It is a frozen sim time, not a measured
  standstill, and no physical stop is claimed;
* no unpause is offered: the policy node keeps its last setpoint (it starts at
  a non-zero 0.15) and, started with ``ros2 run`` and no parameter, computes
  joint efforts every 5 ms through the pause from stale joint and IMU samples;
  a learned policy at a zero setpoint still drives the legs, so this package
  cannot clear what they do when the world resumes (the orchestrator's
  SAFE-042 condition).  After ``mhs.safety.reset`` the world stays paused and
  the operator recovers outside MHS (see ``safe_state``);
* the clone's "Real Robot Integration" section is still "Coming soon", so this
  package is a simulated-world integration only.

Every endpoint, type and fact cites the pinned clone at
99040173a6ec16efb56e236d57fd088fdd61484a.  The fake transport is ROS-free; no
ROS graph, Gazebo server, policy checkpoint or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# -- Companion sources (task.json companions; user decision 2026-11-05) -----------------------------------------
#: gazebo_ros 3.9.0 (ROS 2 Humble, Gazebo 11) at ae6e5793, fetched under work/companions: the pause and its stall
#: read-back.  ROS 2 gazebo_ros has no service that reports the paused flag, so the read-back is get_model_list,
#: whose header.stamp is the world's sim time: two answers 250 ms apart with the same stamp (E1, a stall read-back).
_INIT = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_init.cpp"
_FACTORY = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_factory.cpp"
_GZSERVER = "companion:gazebo_ros_pkgs/gazebo_ros/launch/gzserver.launch.py"
#: Gazebo classic 11.15.1 at b22c6e15 (the corpus clone): the world step the pause gates.
_WORLD = "companion:gazebo_classic/gazebo/physics/World.cc"
#: gazebo_ros2_control 0.4.12 (Humble) at 42d875b4, fetched under work/companions: the controller update.
_ROS2_CONTROL = "companion:gazebo_ros2_control/gazebo_ros2_control/src/gazebo_ros2_control_plugin.cpp"

#: The e-stop: pause_physics (std_srvs/srv/Empty) sets the world's paused flag.
_PAUSE = {
    "service": "/pause_physics",
    "type": "std_srvs/srv/Empty",
    "source_name": "pause_physics",
    "source_ref": _INIT + ":267-271",
    "type_ref": _INIT + ":267",
    "state_ref": _INIT + ":328-333",
    "description": "Pause the Gazebo world (gazebo_ros pause_physics: World::SetPaused(true))",
    "request": {},
    "success": {"path": "$", "equals": {}},
    "timeout_ms": 400,
}
#: The stall read-back that confirms it: get_model_list stamps its answer with the world's sim time, which advances
#: only while the world steps; the e-stop is confirmed only when two answers 250 ms apart carry the same stamp.
_READBACK = {
    "service": "/get_model_list",
    "type": "gazebo_msgs/srv/GetModelList",
    "source_name": "get_model_list",
    "source_ref": _FACTORY + ":139-143",
    "type_ref": _FACTORY + ":139",
    "state_ref": _FACTORY + ":168",
    "description": "Read the world's sim time twice, 250 ms apart; the e-stop is confirmed only when it did not advance",
    "request": {},
    "success": {"path": "success", "equals": True},
    "stall": {"path": "header.stamp", "samples": 2, "interval_ms": 250, "unchanged": True},
    "timeout_ms": 300,
}

#: Facts about the companions, each one clause on its cited range.
_COMPANION_FACTS = [
    Fact("gzserver.launch.py adds the init and factory gazebo_ros system plugins to the server command.",
         source="upstream_code", ref=_GZSERVER + ":55-56"),
    Fact("gzserver.launch.py defaults its init and factory arguments to true.", source="upstream_code",
         ref=_GZSERVER + ":186-193"),
    Fact("The init plugin takes the shared gazebo_ros node from gazebo_ros::Node::Get().", source="upstream_code",
         ref=_INIT + ":150-154"),
    Fact("gazebo_ros::Node::Get creates the shared node named gazebo with an empty namespace.",
         source="upstream_code", ref="companion:gazebo_ros_pkgs/gazebo_ros/src/node.cpp:159-171"),
    Fact("The gazebo_ros executor spins its nodes on a thread of its own.", source="upstream_code",
         ref="companion:gazebo_ros_pkgs/gazebo_ros/src/executor.cpp:22-23"),
    Fact("The init plugin creates the pause_physics and unpause_physics services with the std_srvs::srv::Empty "
         "type.", source="upstream_code", ref=_INIT + ":266-277"),
    Fact("OnPause calls world_->SetPaused(true).", source="upstream_code", ref=_INIT + ":328-333"),
    Fact("OnUnpause calls world_->SetPaused(false).", source="upstream_code", ref=_INIT + ":335-340"),
    Fact("The init plugin publishes the simulation clock from a world-update-begin callback.",
         source="upstream_code", ref=_INIT + ":206-207"),
    Fact("The factory plugin creates the get_model_list service with the gazebo_msgs::srv::GetModelList type.",
         source="upstream_code", ref=_FACTORY + ":139-143"),
    Fact("GetModelList sets header.stamp to the world's simulation time, lists the model names and sets success "
         "true.", source="upstream_code", ref=_FACTORY + ":164-174"),
    Fact("The GetModelList response documents header.stamp as the simulation time when the data was collected.",
         source="upstream_code", ref="companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetModelList.srv:2-5"),
    Fact("World::Step advances simulation time and calls Update only when the world is not paused, a step increment "
         "is pending or a reset is due; otherwise it adds the step to the pause time.", source="upstream_code",
         ref=_WORLD + ":835-854"),
    Fact("World::Step holds worldUpdateMutex while it steps the world.", source="upstream_code",
         ref=_WORLD + ":824-827"),
    Fact("World::SetPaused stores the paused flag under worldUpdateMutex.", source="upstream_code",
         ref=_WORLD + ":1585-1593"),
    Fact("World::IsPaused returns the stored paused flag.", source="upstream_code", ref=_WORLD + ":1579-1582"),
    Fact("World::Update fires the worldUpdateBegin event and then updates every model.", source="upstream_code",
         ref=_WORLD + ":920-929"),
    Fact("World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed "
         "on every step, paused or not.", source="upstream_code", ref=_WORLD + ":835-863"),
    Fact("A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the "
         "number of steps to run while paused.", source="upstream_code", ref=_WORLD + ":1630-1640"),
    Fact("gazebo_ros2_control spins its controller manager's executor on a thread of its own.",
         source="upstream_code", ref=_ROS2_CONTROL + ":400-407"),
    Fact("gazebo_ros2_control connects its Update to the world-update begin event.", source="upstream_code",
         ref=_ROS2_CONTROL + ":409-414"),
    Fact("gazebo_ros2_control's Update reads the simulation time, updates the controllers and writes their "
         "commands to the joints.", source="upstream_code", ref=_ROS2_CONTROL + ":419-437"),
]

#: DreamWaQ registers the velocity subscription with this absolute name.
_VELOCITY_REF = "robot_controller/robot_controller/load_dreamwaq_policy.py:168-170"
_VELOCITY_TYPE_REF = "robot_controller/robot_controller/load_dreamwaq_policy.py:7"

#: DreamWaQ registers the IMU and joint-state subscriptions with these names.
_IMU_REF = "robot_controller/robot_controller/load_dreamwaq_policy.py:176-178"
_JOINT_STATE_REF = "robot_controller/robot_controller/load_dreamwaq_policy.py:179-181"
_SENSOR_TYPE_REF = "robot_controller/robot_controller/load_dreamwaq_policy.py:8"

#: The three velocity inputs have no numeric envelope in the clone.  The UI
#: labels are names and joystick scaling, not installed limits; the text
#: fields accept arbitrary values.  The operator must supply the envelope.
_FORWARD_LIMIT = Limit.operator_required(
    "the clone states no numeric forward-velocity bound; the UI label and joystick scale are not device limits"
)
_LATERAL_LIMIT = Limit.operator_required(
    "the clone states no numeric lateral-velocity bound; the UI label and joystick scale are not device limits"
)
_YAW_LIMIT = Limit.operator_required(
    "the clone states no numeric yaw-rate bound; the UI label and joystick scale are not device limits"
)

#: One explicit geometry_msgs/PoseStamped publication.  The callback reads only
#: pose.position x, y and z; the receipt is a transmission receipt.
_VELOCITY = {
    "topic": "/robot_velocity_command",
    "type": "geometry_msgs/msg/PoseStamped",
    "operation": "publish",
    "source_name": "/robot_velocity_command",
    "source_ref": _VELOCITY_REF,
    "type_ref": _VELOCITY_TYPE_REF,
    "message": {
        "header": {},
        "pose": {"position": {"x": 0.0, "y": 0.0, "z": 0.0}},
    },
    "args": {
        "pose.position.x": {"from": "input.forward_velocity"},
        "pose.position.y": {"from": "input.lateral_velocity"},
        "pose.position.z": {"from": "input.yaw_rate"},
    },
}

#: One explicit sensor_msgs/JointState subscription.  The wire arrays are
#: returned in the publisher's order with their attached names; the policy
#: controllers remap them separately and that remapping is not duplicated here.
_JOINT_STATES = {
    "topic": "/joint_states",
    "type": "sensor_msgs/msg/JointState",
    "operation": "subscribe",
    "source_name": "/joint_states",
    "source_ref": _JOINT_STATE_REF,
    "type_ref": _SENSOR_TYPE_REF,
    "path": "$",
    "timeout_ms": 5000,
    "result": {"map": {
        "name": "name",
        "position": "position",
        "velocity": "velocity",
        "effort": "effort",
    }},
}

#: One explicit sensor_msgs/Imu subscription.  The policy controllers read the
#: orientation quaternion and angular velocity; the linear-acceleration array
#: is passed through as published and no calibration is invented here.
_IMU = {
    "topic": "/imu_plugin/out",
    "type": "sensor_msgs/msg/Imu",
    "operation": "subscribe",
    "source_name": "/imu_plugin/out",
    "source_ref": _IMU_REF,
    "type_ref": _SENSOR_TYPE_REF,
    "path": "$",
    "timeout_ms": 5000,
    "result": {"map": {
        "orientation": "orientation",
        "angular_velocity": "angular_velocity",
        "linear_acceleration": "linear_acceleration",
        "stamp": "header.stamp",
        "frame_id": "header.frame_id",
    }},
}

_VELOCITY_OUTPUT = {
    "published": Field("boolean",
                       description="True when the driver handed the PoseStamped to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution confirmation"),
    "forward_velocity": Field("number", unit="m/s",
                              description="Pose.position.x carried in the published message"),
    "lateral_velocity": Field("number", unit="m/s",
                              description="Pose.position.y carried in the published message"),
    "yaw_rate": Field("number", unit="rad/s",
                      description="Pose.position.z carried in the published message"),
}

_STAMP = Field(
    "object",
    description="ROS header stamp carried by the sensor message",
    properties={
        "sec": Field("integer", unit="s", description="Whole seconds"),
        "nanosec": Field("integer", unit="ns", description="Nanoseconds within the second"),
    },
)

_ANGULAR_VELOCITY = Field(
    "object",
    description="Three-component ROS angular-velocity vector",
    properties={
        "x": Field("number", unit="rad/s", description="x component"),
        "y": Field("number", unit="rad/s", description="y component"),
        "z": Field("number", unit="rad/s", description="z component"),
    },
)

_LINEAR_ACCELERATION = Field(
    "object",
    description="Three-component ROS linear-acceleration vector",
    properties={
        "x": Field("number", unit="m/s2", description="x component"),
        "y": Field("number", unit="m/s2", description="y component"),
        "z": Field("number", unit="m/s2", description="z component"),
    },
)

_ORIENTATION = Field(
    "object",
    description="ROS orientation quaternion",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)

_JOINT_STATE_OUTPUT = {
    "name": Field("array", items=Field("string", description="Joint name from the message"),
                  description="Joint names in the publisher's order"),
    "position": Field("array", items=Field("number", unit="rad", description="Joint position"),
                      description="Joint positions in the publisher's order"),
    "velocity": Field("array", items=Field("number", unit="rad/s", description="Joint velocity"),
                      description="Joint velocities in the publisher's order"),
    "effort": Field("array", items=Field("number", unit="N", description="Joint effort"),
                    description="Joint efforts in the publisher's order"),
}

_IMU_OUTPUT = {
    "orientation": _ORIENTATION,
    "angular_velocity": _ANGULAR_VELOCITY,
    "linear_acceleration": _LINEAR_ACCELERATION,
    "stamp": _STAMP,
    "frame_id": Field("string", description="Header frame_id from the IMU message"),
}


class EvronixQuadrupedSim2sim(RosDriver):
    """Configuration-only ROS 2 rosbridge driver for the pinned sim2sim stack."""

    device_id = "evronix-quadruped-sim"
    device_kind = "world.sim"
    mode = "simulated"
    # R2, not R0 (integrator v4, claude-opus-5-5, 2026-11-05; REVIEW.md item 12 and the orchestrator's condition on
    # the Sonnet evidence lens's EP-2): a simulator package's command keeps the robot's hazard unless a cited line shows
    # that only the simulator consumes its topic. The velocity setpoint feeds the learned policy nodes, which publish
    # joint efforts to a ros2_control JointGroupEffortController (load_dreamwaq_policy.py publishers;
    # robot_gazebo/config/go1_ros_control.yaml:1-10, 31-53), the controller a real robot's ros2_control hardware would
    # serve as well; the only line about real robots says their integration is "Coming soon..." (README.md:113-115),
    # which is not a citation that the topic is simulator-only. A legged robot is R2 however simulated the deployment.
    # The e-stop stays the companion world pause (safety_bindings); no hardware emergency stop is claimed.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeQuadrupedSim2sim"}
    tags = ["ros", "ros2", "gazebo", "quadruped", "simulation", "policy", "velocity", "joint-state", "imu"]
    display_name = "evronix quadruped ROS 2 Gazebo sim2sim"
    vendor = "evronix"
    model = "Go1 sim2sim"
    safe_state = (
        "The Gazebo world is paused: two get_model_list answers 250 ms apart carried the same sim time, so no world "
        "update runs and gazebo_ros2_control applies no joint effort; it is a frozen sim time, not a measured "
        "standstill. No unpause is offered: an operator stops the policy node, then unpauses outside MHS."
    )

    facts = [
        Fact("README describes the repository as a Sim2Sim pipeline for RL quadruped policies in ROS 2 Gazebo.",
             source="vendor_doc", ref="README.md:9"),
        Fact("README says the stack is tested on ROS 2 Humble and Ubuntu 22.04.",
             source="vendor_doc", ref="README.md:41"),
        Fact("README lists the Gazebo launch, three policy controller executables and the UI executable.",
             source="vendor_doc", ref="README.md:74-101"),
        Fact("README says the UI controls the robot's command_velocity interactively.",
             source="vendor_doc", ref="README.md:104"),
        Fact("DreamWaQ creates a PoseStamped subscription on /robot_velocity_command with queue depth 10.",
             source="upstream_code", ref=_VELOCITY_REF),
        Fact("DreamWaQ imports PoseStamped from geometry_msgs.msg.",
             source="upstream_code", ref=_VELOCITY_TYPE_REF),
        Fact("DreamWaQ's velocity callback copies pose.position x, y and z into the command vector.",
             source="upstream_code", ref="robot_controller/robot_controller/load_dreamwaq_policy.py:185-189"),
        Fact("DreamWaQ creates Float64MultiArray publishers on /joint_effort_controller/commands and /policy.",
             source="upstream_code", ref="robot_controller/robot_controller/load_dreamwaq_policy.py:171-174"),
        Fact("DreamWaQ subscribes to Imu on /imu_plugin/out and JointState on /joint_states.",
             source="upstream_code", ref="robot_controller/robot_controller/load_dreamwaq_policy.py:176-181"),
        Fact("DreamWaQ imports Imu and JointState from sensor_msgs.msg.",
             source="upstream_code", ref=_SENSOR_TYPE_REF),
        Fact("DreamWaQ's joint-state callback requires at least 12 positions and reorders 12 indices; the "
             "controller does not verify the attached joint names.",
             source="upstream_code", ref="robot_controller/robot_controller/load_dreamwaq_policy.py:201-214"),
        Fact("DreamWaQ runs a 0.005 s timer and its comment labels the policy dt 0.02 and the PD controller dt 0.005.",
             source="upstream_code", ref="robot_controller/robot_controller/load_dreamwaq_policy.py:182"),
        Fact("HIM's command callback comment names x, y and yaw.",
             source="upstream_code", ref="robot_controller/robot_controller/load_him_policy.py:215-219"),
        Fact("HIM's observation builder comments the three command scales as lin_vel, lin_vel and ang_vel.",
             source="upstream_code", ref="robot_controller/robot_controller/load_him_policy.py:250-253"),
        Fact("Walk-These-Ways creates the same PoseStamped, Imu, JointState, effort publisher and timer interface.",
             source="upstream_code", ref="robot_controller/robot_controller/load_wtw_policy.py:103-113"),
        Fact("Walk-These-Ways clips policy actions to 10, scales by 0.25, reduces hip entries by 0.5 and uses "
             "proportional 20 and derivative 0.5 gains.",
             source="upstream_code", ref="robot_controller/robot_controller/load_wtw_policy.py:175-183"),
        Fact("HIM clips the computed torque command to -80 and 80.",
             source="upstream_code", ref="robot_controller/robot_controller/load_him_policy.py:321-322"),
        Fact("The Gazebo controller manager runs at 1000 Hz and declares a joint_state_broadcaster plus an "
             "effort_controllers/JointGroupEffortController.",
             source="upstream_code", ref="robot_gazebo/config/go1_ros_control.yaml:1-10"),
        Fact("The effort controller lists the FL, FR, RL and RR hip, thigh and calf joints and uses the effort "
             "command interface.",
             source="upstream_code", ref="robot_gazebo/config/go1_ros_control.yaml:31-53"),
        Fact("The Gazebo launch enables use_sim_time and spawns entity go1 at z 0.4.",
             source="upstream_code", ref="robot_gazebo/launch/go1_gazebo.launch.py:65-78"),
        Fact("The URDF declares the FR hip joint as revolute with effort 23.7, lower -0.863, upper 0.863 and "
             "velocity 30.1.",
             source="upstream_code", ref="robot_description/urdf/go1/go1.urdf.xacro:100-106"),
        Fact("The URDF declares the FR calf joint as revolute with effort 35.55, lower -2.818, upper -0.888 and "
             "velocity 20.06.",
             source="upstream_code", ref="robot_description/urdf/go1/go1.urdf.xacro:170-176"),
        Fact("README's Real Robot Integration section is still 'Coming soon...'.",
             source="vendor_doc", ref="README.md:113-115"),
        Fact("DreamWaQ starts with the command vector 0.15, 0.0, 0.0.", source="upstream_code",
             ref="robot_controller/robot_controller/load_dreamwaq_policy.py:167"),
        Fact("DreamWaQ's control loop runs the policy every fourth tick, then computes PD torques toward the "
             "policy's joint targets and publishes them on every tick.", source="upstream_code",
             ref="robot_controller/robot_controller/load_dreamwaq_policy.py:230-270"),
        Fact("The README starts the Gazebo simulation with ros2 launch and each policy controller with ros2 run and no "
             "argument.", source="vendor_doc", ref="README.md:72-96"),
        Fact("The Gazebo launch includes gazebo_ros's gazebo.launch.py.", source="upstream_code",
             ref="robot_gazebo/launch/go1_gazebo.launch.py:23-25"),
        *_COMPANION_FACTS,
    ]

    #: The fake is an analytic protocol stand-in, not the Gazebo simulator and
    #: not a replay of captured traffic.  It claims F0 with no physics or
    #: pacing; the upstream control-loop periods are facts above, not fake
    #: timing.  The real topics and controller timing require a live run.
    fidelity = {
        "engine": "synthetic:ROS-free protocol fake (no Gazebo, no policy controller)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned observations and a publication recorder; no physics step, "
                     "wall-clock pacing, policy inference or trajectory replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake answers the declared ROS endpoints only; it runs no Gazebo world, physics, contacts, "
            "IMU plugin, joint-state broadcaster, policy controller or ROS graph",
            "the fake's IMU and joint-state samples are placeholders and are not integrated with the velocity "
            "publication; a live run must supply the operator's Gazebo and controller processes",
            "the fake's publication receipt proves only that rosbridge accepted the PoseStamped, not that a "
            "controller consumed it, that the robot moved or that it stopped",
            "the pinned nodes expose no stop, pause or reset service and no action interface; the stop is the "
            "companion gazebo_ros world pause, confirmed by the E1 stall read-back: the fake keeps a paused flag "
            "that /pause_physics sets and a sim-time stamp that /get_model_list reports and that advances on every "
            "answer unless paused; it runs no Gazebo World::Step",
            "a frozen get_model_list stamp is also what a hung but unpaused gzserver shows (nothing advances then "
            "either); a GUI step or a WorldControl multi_step between the two samples fails the check (fails "
            "closed); the e-stop declares estop_latency_ms 1500 because the pause (400 ms), two read-backs (300 ms "
            "each) and the 250 ms interval exceed the default 1000 ms budget",
            "no unpause is offered: the policy node stores the last setpoint (initially 0.15, "
            "load_dreamwaq_policy.py:167) and publishes joint efforts every 5 ms (lines 182, 230-270); started with "
            "ros2 run and no parameter (README.md:86-90) its timer runs on the system clock through the pause on "
            "stale joint and IMU samples, so the package cannot clear what the legs do on an unpause; the operator "
            "recovers outside MHS (stop the policy node, then the Gazebo GUI play button or ros2 service call "
            "/unpause_physics)",
            "while paused, /joint_states (joint_state_broadcaster through gazebo_ros2_control), /imu_plugin/out and "
            "/clock come only from world updates, so the joint-state and IMU reads fail NOT_READY after their "
            "timeouts (the fake silences them while its flag is set)",
            "a live world can be unpaused or stepped by the Gazebo GUI, a WorldControl message or any ROS 2 client "
            "of /unpause_physics; MHS does not watch the sim time after the e-stop (safety_status re-reads it only "
            "on request)",
            "the deployment's gazebo_ros, gazebo_ros2_control and Gazebo must be the pinned 3.9.0, 0.4.12 and "
            "11.15.1 releases the companion citations name; rosbridge cannot read their versions",
            "the clone supports three alternative policy controllers and hard-coded checkpoint paths; this "
            "package binds the common topic interface, not a particular policy, checkpoint or launch namespace",
            "the clone's Real Robot Integration is not implemented, so no hardware interface is claimed",
        ],
    }

    # An action-only ROS driver: the explicit observation capabilities below
    # are not an automatic resource snapshot.
    commands = {
        "x-cap.evronix.velocity_command.v1": _VELOCITY,
        "x-cap.evronix.joint_states.v1": _JOINT_STATES,
        "x-cap.evronix.imu.v1": _IMU,
    }
    actions = {
        "x-cap.evronix.velocity_command.v1": Action(
            name="publish_velocity_command",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one PoseStamped velocity setpoint on /robot_velocity_command; the receipt confirms "
                "only that rosbridge accepted the publication, not motion, arrival or stopping"
            ),
            input={
                "forward_velocity": Field(
                    "number", unit="m/s",
                    description="Pose.position.x; HIM's callback comment names it x and the UI labels it X velocity",
                    limit=_FORWARD_LIMIT,
                ),
                "lateral_velocity": Field(
                    "number", unit="m/s",
                    description="Pose.position.y; HIM's callback comment names it y and the UI labels it Y velocity",
                    limit=_LATERAL_LIMIT,
                ),
                "yaw_rate": Field(
                    "number", unit="rad/s",
                    description="Pose.position.z; HIM's callback comment names it yaw and the UI labels it Angular "
                                "Z velocity",
                    limit=_YAW_LIMIT,
                ),
            },
            output=_VELOCITY_OUTPUT,
        ),
        "x-cap.evronix.joint_states.v1": Action(
            name="read_joint_states",
            verb="read",
            description=(
                "Subscribe to one fresh sensor_msgs/JointState sample on /joint_states and return the name, "
                "position, velocity and effort arrays in the publisher's order"
            ),
            output=_JOINT_STATE_OUTPUT,
        ),
        "x-cap.evronix.imu.v1": Action(
            name="read_imu",
            verb="read",
            description=(
                "Subscribe to one fresh sensor_msgs/Imu sample on /imu_plugin/out and return the orientation, "
                "angular velocity, linear acceleration, header stamp and frame_id as published"
            ),
            output=_IMU_OUTPUT,
        ),
    }
    # The e-stop pauses the Gazebo world and confirms it by a sim time that no longer advances (companion gazebo_ros,
    # E1 stall read-back); anything else leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    estop_latency_ms = 1500
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def call(self, capability_id, args=None, ctx=None):
        """Add the transmitted setpoints to the publication receipt.

        The base family driver performs the publication and returns its fixed
        transmission receipt.  Echoing the validated inputs makes the receipt
        describe what was sent; it still does not claim that a controller
        consumed the message or that the robot moved.
        """
        result = super().call(capability_id, args, ctx)
        if capability_id != "x-cap.evronix.velocity_command.v1":
            return result
        values = dict(args or {})
        return {
            "published": result.get("published"),
            "confirmed": result.get("confirmed"),
            "forward_velocity": values.get("forward_velocity"),
            "lateral_velocity": values.get("lateral_velocity"),
            "yaw_rate": values.get("yaw_rate"),
        }
