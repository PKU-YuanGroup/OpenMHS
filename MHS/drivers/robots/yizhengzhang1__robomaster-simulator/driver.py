"""OpenMHS rosbridge driver for the ICRA RoboMaster AI Challenge simulator.

The pinned repository is a ROS 1 Gazebo simulator with its own referee node,
turret controller and mecanum base controller.  This package is a
configuration-only :class:`RosDriver`; it declares no Python native class and
neither imports nor starts the upstream code.

Scope is the concrete ROS interface of the simulator:

* ``/gazebo/pause_physics`` and ``/gazebo/unpause_physics``
  (``std_srvs/Empty``) are the pause/unpause pair used by the openai_ros
  ``MultiRobotGazeboEnv.step`` around every action.  Pausing is the declared
  simulated safe state and the e-stop binding.
* ``/jackal0/cmd_vel`` (``geometry_msgs/Twist``) is the mecanum base command.
* ``/jackal0/turret_position`` (``std_msgs/Float32``) is the turret angle
  consumed by the turret controller.
* ``/start_game`` (``rm_simulator/GameState``) starts or stops the referee
  game loop.
* ``/refer_system_info`` (``rm_simulator/ReferSystemInfo``) is the referee
  state observation.

The gym registration ``AiChallengeEnv-v1`` is not used as the driver shape:
its ``_get_obs`` is a ``pass``, its reward is 0 and its task is not a
completed Gymnasium contract.  The ROS endpoints above are the concrete
interface the clone ships.

Every endpoint, type and fact cites the pinned clone at
ff085e4109a980e482a388f135e9fefcee92becc.  The fake transport is ROS-free;
no ROS graph, Gazebo simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The openai_ros multi-robot Gazebo connection creates both service proxies.
_PAUSE_REF = "src/openai_ros/openai_ros/src/openai_ros/multi_robot_gazebo_connection.py:21"
_UNPAUSE_REF = "src/openai_ros/openai_ros/src/openai_ros/multi_robot_gazebo_connection.py:20"
_EMPTY_TYPE_REF = "src/openai_ros/openai_ros/src/openai_ros/multi_robot_gazebo_connection.py:4"

#: The referee node advertises the relative start game service and state topic.
_START_REF = "src/rm_simulator/src/refer_system.cpp:37"
_STATE_REF = "src/rm_simulator/src/refer_system.cpp:38"
_REFEREE_TYPE_REF = "src/rm_simulator/src/refer_system.cpp:7"
_GAME_STATE_TYPE_REF = "src/rm_simulator/src/refer_system.cpp:8"

#: The turret controller subscribes to the relative Float32 command topic.
_TURRET_REF = "src/rm_simulator/src/turret_controller.cpp:13"
_TURRET_TYPE_REF = "src/rm_simulator/src/turret_controller.cpp:3"

#: The mecanum base controller subscribes to the relative Twist command topic.
_CMD_VEL_REF = "src/ridgeback/ridgeback_control/src/mecanum_drive_controller.cpp:183"
_TWIST_TYPE_REF = "src/ridgeback/ridgeback_control/include/mecanum_drive_controller/mecanum_drive_controller.h:169"

#: Lower and upper travel of the turret joint in the pinned URDF.
_TURRET_LIMIT_REF = "src/ridgeback/ridgeback_description/urdf/accessories/camera_mount.urdf.xacro:53"

_PAUSE = {
    "service": "/gazebo/pause_physics",
    "type": "std_srvs/Empty",
    "source_ref": _PAUSE_REF,
    "type_ref": _EMPTY_TYPE_REF,
    "success": {"path": "$", "equals": {}},
}

_UNPAUSE = {
    "service": "/gazebo/unpause_physics",
    "type": "std_srvs/Empty",
    "source_ref": _UNPAUSE_REF,
    "type_ref": _EMPTY_TYPE_REF,
    "success": {"path": "$", "equals": {}},
}

_START_GAME = {
    "service": "/start_game",
    "type": "rm_simulator/GameState",
    "source_name": "start_game",
    "source_ref": _START_REF,
    "type_ref": _GAME_STATE_TYPE_REF,
    "request": {"start": False},
    "args": {"start": {"from": "input.start"}},
    "success": {"path": "received", "equals": True},
    "result": {"map": {"received": "output.received"}},
}

_REFEREE_STATE = {
    "topic": "/refer_system_info",
    "type": "rm_simulator/ReferSystemInfo",
    "source_name": "refer_system_info",
    "source_ref": _STATE_REF,
    "type_ref": _REFEREE_TYPE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {
        "game_time": "gameTime",
        "robot_health": "robotHealth",
        "remain_bullet": "remain_bullet",
        "robot_shoot": "robotShoot",
        "robot_move": "robotMove",
        "cell_state_number": "cellStateNumber",
        "cell_x": "cellX",
        "cell_y": "cellY",
        "robot_pose": "robotPose",
    }},
}

_TURRET = {
    "topic": "/jackal0/turret_position",
    "type": "std_msgs/Float32",
    "source_name": "turret_position",
    "source_ref": _TURRET_REF,
    "type_ref": _TURRET_TYPE_REF,
    "operation": "publish",
    "message": {"data": 0.0},
    "args": {"data": {"from": "input.position"}},
}

_CMD_VEL = {
    "topic": "/jackal0/cmd_vel",
    "type": "geometry_msgs/Twist",
    "source_name": "cmd_vel",
    "source_ref": _CMD_VEL_REF,
    "type_ref": _TWIST_TYPE_REF,
    "operation": "publish",
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "args": {
        "linear.x": {"from": "input.linear_x"},
        "linear.y": {"from": "input.linear_y"},
        "angular.z": {"from": "input.angular_z"},
    },
}

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the publication to rosbridge"),
    "confirmed": Field("boolean", description="Always false: a rosbridge publication carries no execution confirmation"),
}

_TURRET_OUTPUT = dict(_PUBLISHED)
_TURRET_OUTPUT["position"] = Field(
    "number", unit="rad", description="The turret angle this receipt published, echoed from the input")

_CMD_VEL_OUTPUT = dict(_PUBLISHED)
_CMD_VEL_OUTPUT["linear_x"] = Field(
    "number", unit="m/s", description="The body forward velocity this receipt published, echoed from the input")
_CMD_VEL_OUTPUT["linear_y"] = Field(
    "number", unit="m/s", description="The body lateral velocity this receipt published, echoed from the input")
_CMD_VEL_OUTPUT["angular_z"] = Field(
    "number", unit="rad/s", description="The body yaw rate this receipt published, echoed from the input")

_ACKNOWLEDGED = Field("boolean", description="True when the upstream service acknowledged the request")

_ROBOT_POSE = Field(
    "object",
    description="One RobotPose entry from the referee message",
    properties={
        "x": Field("number", description="Raw RobotPose.x coordinate from the referee message"),
        "y": Field("number", description="Raw RobotPose.y coordinate from the referee message"),
        "yaw": Field("number", description="Raw RobotPose.yaw angle from the referee message"),
    },
)

_REFEREE_OUTPUT = {
    "robot_pose": Field("array", items=_ROBOT_POSE, length=4,
                        description="Four robot poses in jackal index order"),
    "game_time": Field("number", unit="s",
                       description="Elapsed game time computed from ros::Time::now().toSec() minus start_secs"),
    "robot_health": Field("array", items=Field("integer", description="One robotHealth entry"),
                          length=4, description="Four robot health values in jackal index order"),
    "remain_bullet": Field("array", items=Field("integer", description="One remain_bullet entry"),
                           length=4, description="Four remaining-bullet values in jackal index order"),
    "robot_shoot": Field("array", items=Field("integer", description="One robotShoot enable flag"),
                         length=4, description="Four shoot-enable flags in jackal index order"),
    "robot_move": Field("array", items=Field("integer", description="One robotMove enable flag"),
                        length=4, description="Four move-enable flags in jackal index order"),
    "cell_state_number": Field("array", items=Field("integer", description="One cellStateNumber entry"),
                               length=6, description="Six decoded bonus-cell state numbers"),
    "cell_x": Field("array", items=Field("number", description="One cellX coordinate"),
                    length=6, description="Six fixed bonus-cell x coordinates"),
    "cell_y": Field("array", items=Field("number", description="One cellY coordinate"),
                    length=6, description="Six fixed bonus-cell y coordinates"),
}

_CMD_VEL_LIMIT_X = Limit.operator_required(
    "the pinned mecanum controller's linear x maximum is a controller configuration value, not a device constant; "
    "the operator supplies the deployed linear x envelope")
_CMD_VEL_LIMIT_Y = Limit.operator_required(
    "the pinned mecanum controller's linear y maximum is a controller configuration value, not a device constant; "
    "the operator supplies the deployed linear y envelope")
_CMD_VEL_LIMIT_Z = Limit.operator_required(
    "the pinned mecanum controller's angular z maximum is a controller configuration value, not a device constant; "
    "the operator supplies the deployed angular z envelope")


class RobomasterSimulator(RosDriver):
    device_id = "robomaster-simulator"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeRobomasterSimulator"}
    tags = ["ros", "ros1", "simulation", "gazebo", "robomaster", "referee", "turret", "mobile-base"]
    display_name = "ICRA RoboMaster AI Challenge simulator"
    vendor = "Living Machine Lab, ShanghaiTech University"
    facts = [
        Fact("MultiRobotGazeboConnection creates /gazebo/unpause_physics and /gazebo/pause_physics "
             "std_srvs/Empty service proxies.",
             source="upstream_code",
             ref="src/openai_ros/openai_ros/src/openai_ros/multi_robot_gazebo_connection.py:20-21"),
        Fact("pauseSim waits for /gazebo/pause_physics and calls it; unpauseSim does the same for "
             "/gazebo/unpause_physics.",
             source="upstream_code",
             ref="src/openai_ros/openai_ros/src/openai_ros/multi_robot_gazebo_connection.py:33-49"),
        Fact("MultiRobotGazeboEnv.step unpauses physics, calls _set_action, then pauses physics before "
             "reading observations.",
             source="upstream_code",
             ref="src/openai_ros/openai_ros/src/openai_ros/multi_robot_gazebo_env.py:42-46"),
        Fact("MultiRobotGazeboEnv._reset_sim calls pauseSim, _set_init_gazebo_pose, unpauseSim, "
             "_check_all_systems_ready and _set_init_ros in that order.",
             source="upstream_code",
             ref="src/openai_ros/openai_ros/src/openai_ros/multi_robot_gazebo_env.py:71-80"),
        Fact("ReferSystem advertises the relative start_game service and a latched rm_simulator/ReferSystemInfo "
             "publisher with queue size 1 on the relative refer_system_info topic.",
             source="upstream_code", ref="src/rm_simulator/src/refer_system.cpp:37-38"),
        Fact("isGameStart is a global flag that starts false.",
             source="upstream_code", ref="src/rm_simulator/src/refer_system.cpp:29"),
        Fact("ReferSystem advertises a geometry_msgs/Twist publisher on /jackal0/cmd_vel to /jackal3/cmd_vel and "
             "subscribes to each robot's /jackalN/cmd_vel_acc topic.",
             source="upstream_code", ref="src/rm_simulator/src/refer_system.cpp:40-54"),
        Fact("cmdCallback0 republishes the twist of each roborts_msgs/TwistAccel message through cmd_pub[0] while "
             "robotMove[0] is 1.",
             source="upstream_code", ref="src/rm_simulator/src/refer_system.cpp:207-214"),
        Fact("startGame stores req.start in isGameStart, sets res.received = true, and returns true; "
             "initialize() runs only when the requested start is true.",
             source="upstream_code", ref="src/rm_simulator/src/refer_system.cpp:93-101"),
        Fact("The referee main loop runs at 120 Hz and calls game_spin only while isGameStart is true.",
             source="upstream_code", ref="src/rm_simulator/src/refer_system.cpp:426-442"),
        Fact("game_spin ends by publishing refer_system_msg through state_pub.",
             source="upstream_code", ref="src/rm_simulator/src/refer_system.cpp:398-399"),
        Fact("The ReferSystemInfo message defines robotHealth[4], remain_bullet[4], robotShoot[4], "
             "robotShootDebuffTime[4], robotMove[4], robotMoveDebuffTime[4], cellState[6], "
             "cellStateNumber[6], cellX[6], cellY[6], robotPose[4] and gameTime.",
             source="upstream_code", ref="src/rm_simulator/msg/ReferSystemInfo.msg:1-13"),
        Fact("GameState.srv carries bool start in the request and bool received in the response.",
             source="upstream_code", ref="src/rm_simulator/srv/GameState.srv:1-3"),
        Fact("The turret controller subscribes to the relative turret_position std_msgs/Float32 topic and "
             "copies msg->data into the first JointTrajectory position for front_camera_pivot_joint.",
             source="upstream_code", ref="src/rm_simulator/src/turret_controller.cpp:13-27"),
        Fact("The front_camera_pivot_joint URDF limit is lower -1.5707 and upper 1.5707 rad with velocity "
             "10 and effort 2.",
             source="upstream_code",
             ref="src/ridgeback/ridgeback_description/urdf/accessories/camera_mount.urdf.xacro:46-53"),
        Fact("The mecanum drive controller subscribes to the relative cmd_vel geometry_msgs/Twist topic.",
             source="upstream_code",
             ref="src/ridgeback/ridgeback_control/src/mecanum_drive_controller.cpp:183"),
        Fact("control.launch (namespace argument ns, default jackal0) spawns ridgeback_velocity_controller and "
             "relays the namespace's cmd_vel topic to ridgeback_velocity_controller/cmd_vel with topic_tools relay.",
             source="upstream_code", ref="src/ridgeback/ridgeback_control/launch/control.launch:3-30"),
        Fact("one_ridgeback.launch includes control.launch and teleop.launch for the robot namespace and starts "
             "the RoboRTS local planner with /cmd_vel_acc remapped to the namespace's cmd_vel_acc.",
             source="upstream_code", ref="src/rm_simulator/launch/one_ridgeback.launch:28-90"),
        Fact("The mecanum drive controller brakes the last command when the cmd_vel age exceeds "
             "cmd_vel_timeout_ and then applies the configured velocity and acceleration limiters.",
             source="upstream_code",
             ref="src/ridgeback/ridgeback_control/src/mecanum_drive_controller.cpp:245-261"),
        Fact("The ridgeback controller config sets cmd_vel_timeout 0.25 s and enables linear x, linear y "
             "and angular z velocity and acceleration limits.",
             source="upstream_code",
             ref="src/ridgeback/ridgeback_control/config/control.yaml:24-56"),
        Fact("The mecanum drive controller loads min_velocity and min_acceleration as the negative of the "
             "configured maximum when the parameters are absent.",
             source="upstream_code",
             ref="src/ridgeback/ridgeback_control/src/mecanum_drive_controller.cpp:152-169"),
        Fact("The README documents /jackal0/turret_position as an angle in radians and /start_game as a "
             "service that is not used currently.",
             source="vendor_doc", ref="README.md:115-125"),
        Fact("The training environment registers AiChallengeEnv-v1 for MultiAgentAiChallengeEnv, which "
             "inherits MultiRobotGazeboEnv.",
             source="upstream_code",
             ref="src/competition_rl/scripts/multiAgentChallengeTaskEnv.py:15-21"),
        Fact("MultiAgentAiChallengeEnv._get_obs is a pass, _compute_reward returns 0 and _is_done returns "
             "False; the gym registration is a scaffold, not a completed observation/step contract.",
             source="upstream_code",
             ref="src/competition_rl/scripts/multiAgentChallengeTaskEnv.py:60-86"),
    ]
    safe_state = (
        "Simulated physics is paused through the acknowledged /gazebo/pause_physics service, so the Gazebo "
        "world stops stepping until any client calls /gazebo/unpause_physics (an openai_ros environment step "
        "does); the referee node, the planners and their retained commands are not stopped."
    )
    #: The deployed fake is a ROS-free recording transport, so it claims F0
    #: and no dynamics.  The upstream simulator is a Gazebo world, but this
    #: package does not start or drive it.
    fidelity = {
        "engine": "analytic:ROS recording fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven recording fake with no physics step or pacing; placeholder referee, "
                     "turret and base samples do not establish trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it answers the declared pause, unpause, "
            "start_game, referee, turret and cmd_vel endpoints and runs no Gazebo physics, controllers, "
            "robot dynamics, sensors or wall-clock loop",
            "the referee, turret and base values are placeholders; a live run must receive them from the "
            "operator's simulator and ROS nodes",
            "the /gazebo/pause_physics and /gazebo/unpause_physics implementations are in gazebo_ros, "
            "outside the pinned clone; the clone proves the client endpoints and their use in the "
            "openai_ros step/reset lifecycle, not the callback body",
            "pausing physics freezes the Gazebo world but does not terminate the referee node, its game "
            "loop or the controllers; unpausing can resume motion from retained controller state, and any "
            "other client's /gazebo/unpause_physics call, including MultiRobotGazeboEnv.step and _reset_sim of "
            "a running openai_ros training script, undoes the stop",
            "/jackal0/cmd_vel reaches ridgeback_velocity_controller/cmd_vel through the topic_tools relay of "
            "control.launch; in the shipped launch the referee node also publishes there, forwarding the RoboRTS "
            "local planner's /jackal0/cmd_vel_acc while robotMove[0] is 1, so this package's publications share "
            "the topic with other publishers",
            "a cmd_vel publication is transmission-only; the mecanum controller's 0.25 s stale-command "
            "brake is a controller timeout, not an acknowledged stop",
            "a turret_position publication is transmission-only; the turret controller republishes a "
            "JointTrajectory and neither the driver nor the source confirms that the joint reached the "
            "requested angle",
            "isGameStart starts false and game_spin publishes the latched /refer_system_info topic only while "
            "it is true: before a /start_game true no sample exists and a live read times out, and after "
            "start:false a new subscription receives the last latched sample, which is stale; the fake answers "
            "regardless and marks no game state",
            "with /use_sim_time true (ridgeback_robots.launch passes use_sim_time true to gazebo_ros's "
            "empty_world.launch) the referee loop's ros::Rate sleeps on simulated time, so while physics is paused "
            "it neither services /start_game nor publishes: a start_game call made then can time out (unknown "
            "outcome) and a read returns the last latched sample",
            "the AiChallengeEnv-v1 gym registration is a scaffold: _get_obs returns None, _compute_reward "
            "returns 0 and _is_done returns False; this package does not claim an environment-step contract",
            "NOT COVERED: the ReferSystemInfo header, cellState and debuff-time fields; the /jackal0/shoot, "
            "/jackal0/debuff, /jackal0/cmd_vel_acc, /jackal0/obstacle_filtered, camera, laser and TF "
            "surfaces; the multi-robot jackal1..3 namespaces",
        ],
    }

    commands = {
        "x-cap.yizhengzhang1.pause_physics.v1": dict(
            _PAUSE, result={"acknowledged": {"value": True}}),
        "x-cap.yizhengzhang1.unpause_physics.v1": dict(
            _UNPAUSE, result={"acknowledged": {"value": True}}),
        "x-cap.yizhengzhang1.start_game.v1": _START_GAME,
        "x-cap.yizhengzhang1.referee_state.v1": _REFEREE_STATE,
        "x-cap.yizhengzhang1.turret_position.v1": _TURRET,
        "x-cap.yizhengzhang1.cmd_vel.v1": _CMD_VEL,
    }
    actions = {
        "x-cap.yizhengzhang1.pause_physics.v1": Action(
            name="pause_physics",
            verb="invoke",
            safe_state=True,
            description="Pause Gazebo physics with the acknowledged /gazebo/pause_physics service",
            output={"acknowledged": _ACKNOWLEDGED},
        ),
        "x-cap.yizhengzhang1.unpause_physics.v1": Action(
            name="unpause_physics",
            verb="invoke",
            risk="R2",
            description="Resume Gazebo physics with the acknowledged /gazebo/unpause_physics service",
            output={"acknowledged": _ACKNOWLEDGED},
        ),
        "x-cap.yizhengzhang1.start_game.v1": Action(
            name="start_game",
            verb="invoke",
            risk="R1",
            description="Ask the referee node to start or stop its game loop; the response only "
                        "acknowledges receipt of the request",
            input={"start": Field("boolean", description="True to start the referee game loop, false to stop it")},
            output={"received": Field("boolean",
                                      description="True when the referee service callback accepted the request")},
            examples=[{"start": True}],
        ),
        "x-cap.yizhengzhang1.referee_state.v1": Action(
            name="read_referee_state",
            verb="read",
            description="Read one rm_simulator/ReferSystemInfo sample published by the referee node",
            output=_REFEREE_OUTPUT,
        ),
        "x-cap.yizhengzhang1.turret_position.v1": Action(
            name="command_turret",
            verb="invoke",
            risk="R1",
            description="Publish one turret angle in radians on /jackal0/turret_position; the "
                        "publication carries no execution acknowledgement",
            input={"position": Field(
                "number", unit="rad",
                description="Turret angle published as std_msgs/Float32 data",
                limit=Limit(min=-1.5707, max=1.5707, unit="rad", source="upstream_code",
                            ref=_TURRET_LIMIT_REF),
            )},
            output=_TURRET_OUTPUT,
            examples=[{"position": 0.0}],
        ),
        "x-cap.yizhengzhang1.cmd_vel.v1": Action(
            name="command_base_velocity",
            verb="invoke",
            risk="R2",
            description="Publish one body twist on /jackal0/cmd_vel; the mecanum controller applies "
                        "its own velocity and acceleration limits and has no execution acknowledgement",
            input={
                "linear_x": Field("number", unit="m/s",
                                  description="Body forward velocity in the Twist linear.x field",
                                  limit=_CMD_VEL_LIMIT_X),
                "linear_y": Field("number", unit="m/s",
                                  description="Body lateral velocity in the Twist linear.y field",
                                  limit=_CMD_VEL_LIMIT_Y),
                "angular_z": Field("number", unit="rad/s",
                                   description="Body yaw rate in the Twist angular.z field",
                                   limit=_CMD_VEL_LIMIT_Z),
            },
            output=_CMD_VEL_OUTPUT,
            examples=[{"linear_x": 0.0, "linear_y": 0.0, "angular_z": 0.0}],
        ),
    }
    # The acknowledged pause service is the simulator's stop.  The runtime
    # latches first; this freezes simulated physics and does not command a
    # zero velocity or stop the referee process.
    safety_bindings = {"estop": _PAUSE}

    def call(self, capability_id, args=None, ctx=None):
        """Echo the published command fields into the receipt.

        A rosbridge topic publication has no native result, so the bridge can
        only report that it transmitted the message.  Reporting the exact
        fields that were sent makes the receipt an observable function of the
        input; it still does not claim execution, reach or motion.
        """
        output = super().call(capability_id, args, ctx)
        payload = dict(args or {})
        if capability_id == "x-cap.yizhengzhang1.turret_position.v1":
            return {**dict(output), "position": payload.get("position")}
        if capability_id == "x-cap.yizhengzhang1.cmd_vel.v1":
            return {**dict(output),
                    "linear_x": payload.get("linear_x"),
                    "linear_y": payload.get("linear_y"),
                    "angular_z": payload.get("angular_z")}
        return output
