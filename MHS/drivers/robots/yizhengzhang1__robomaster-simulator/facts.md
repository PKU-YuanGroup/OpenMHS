# Facts and tags for gh.yizhengzhang1/robomaster-simulator

Every fact cites the pinned clone at commit `ff085e4109a980e482a388f135e9fefcee92becc`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); `reference.json` is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| MultiRobotGazeboConnection creates /gazebo/unpause_physics and /gazebo/pause_physics std_srvs/Empty service proxies. | upstream_code | src/openai_ros/openai_ros/src/openai_ros/multi_robot_gazebo_connection.py:20-21 |
| pauseSim waits for /gazebo/pause_physics and calls it; unpauseSim does the same for /gazebo/unpause_physics. | upstream_code | src/openai_ros/openai_ros/src/openai_ros/multi_robot_gazebo_connection.py:33-49 |
| MultiRobotGazeboEnv.step unpauses physics, calls _set_action, then pauses physics before reading observations. | upstream_code | src/openai_ros/openai_ros/src/openai_ros/multi_robot_gazebo_env.py:42-46 |
| MultiRobotGazeboEnv._reset_sim calls pauseSim, _set_init_gazebo_pose, unpauseSim, _check_all_systems_ready and _set_init_ros in that order. | upstream_code | src/openai_ros/openai_ros/src/openai_ros/multi_robot_gazebo_env.py:71-80 |
| ReferSystem advertises the relative start_game service and a latched rm_simulator/ReferSystemInfo publisher with queue size 1 on the relative refer_system_info topic. | upstream_code | src/rm_simulator/src/refer_system.cpp:37-38 |
| isGameStart is a global flag that starts false. | upstream_code | src/rm_simulator/src/refer_system.cpp:29 |
| ReferSystem advertises a geometry_msgs/Twist publisher on /jackal0/cmd_vel to /jackal3/cmd_vel and subscribes to each robot's /jackalN/cmd_vel_acc topic. | upstream_code | src/rm_simulator/src/refer_system.cpp:40-54 |
| cmdCallback0 republishes the twist of each roborts_msgs/TwistAccel message through cmd_pub[0] while robotMove[0] is 1. | upstream_code | src/rm_simulator/src/refer_system.cpp:207-214 |
| startGame stores req.start in isGameStart, sets res.received = true, and returns true; initialize() runs only when the requested start is true. | upstream_code | src/rm_simulator/src/refer_system.cpp:93-101 |
| The referee main loop runs at 120 Hz and calls game_spin only while isGameStart is true. | upstream_code | src/rm_simulator/src/refer_system.cpp:426-442 |
| game_spin ends by publishing refer_system_msg through state_pub. | upstream_code | src/rm_simulator/src/refer_system.cpp:398-399 |
| The ReferSystemInfo message defines robotHealth[4], remain_bullet[4], robotShoot[4], robotShootDebuffTime[4], robotMove[4], robotMoveDebuffTime[4], cellState[6], cellStateNumber[6], cellX[6], cellY[6], robotPose[4] and gameTime. | upstream_code | src/rm_simulator/msg/ReferSystemInfo.msg:1-13 |
| GameState.srv carries bool start in the request and bool received in the response. | upstream_code | src/rm_simulator/srv/GameState.srv:1-3 |
| The turret controller subscribes to the relative turret_position std_msgs/Float32 topic and copies msg->data into the first JointTrajectory position for front_camera_pivot_joint. | upstream_code | src/rm_simulator/src/turret_controller.cpp:13-27 |
| The front_camera_pivot_joint URDF limit is lower -1.5707 and upper 1.5707 rad with velocity 10 and effort 2. | upstream_code | src/ridgeback/ridgeback_description/urdf/accessories/camera_mount.urdf.xacro:46-53 |
| The mecanum drive controller subscribes to the relative cmd_vel geometry_msgs/Twist topic. | upstream_code | src/ridgeback/ridgeback_control/src/mecanum_drive_controller.cpp:183 |
| control.launch (namespace argument ns, default jackal0) spawns ridgeback_velocity_controller and relays the namespace's cmd_vel topic to ridgeback_velocity_controller/cmd_vel with topic_tools relay. | upstream_code | src/ridgeback/ridgeback_control/launch/control.launch:3-30 |
| one_ridgeback.launch includes control.launch and teleop.launch for the robot namespace and starts the RoboRTS local planner with /cmd_vel_acc remapped to the namespace's cmd_vel_acc. | upstream_code | src/rm_simulator/launch/one_ridgeback.launch:28-90 |
| The mecanum drive controller brakes the last command when the cmd_vel age exceeds cmd_vel_timeout_ and then applies the configured velocity and acceleration limiters. | upstream_code | src/ridgeback/ridgeback_control/src/mecanum_drive_controller.cpp:245-261 |
| The ridgeback controller config sets cmd_vel_timeout 0.25 s and enables linear x, linear y and angular z velocity and acceleration limits. | upstream_code | src/ridgeback/ridgeback_control/config/control.yaml:24-56 |
| The mecanum drive controller loads min_velocity and min_acceleration as the negative of the configured maximum when the parameters are absent. | upstream_code | src/ridgeback/ridgeback_control/src/mecanum_drive_controller.cpp:152-169 |
| The README documents /jackal0/turret_position as an angle in radians and /start_game as a service that is not used currently. | vendor_doc | README.md:115-125 |
| The training environment registers AiChallengeEnv-v1 for MultiAgentAiChallengeEnv, which inherits MultiRobotGazeboEnv. | upstream_code | src/competition_rl/scripts/multiAgentChallengeTaskEnv.py:15-21 |
| MultiAgentAiChallengeEnv._get_obs is a pass, _compute_reward returns 0 and _is_done returns False; the gym registration is a scaffold, not a completed observation/step contract. | upstream_code | src/competition_rl/scripts/multiAgentChallengeTaskEnv.py:60-86 |

## Scope

The package exposes the simulator's pause/unpause services, the mecanum base
command, the turret angle command, the referee start_game service and one
`/refer_system_info` observation. The `pause_physics` action is input-free with
`safe_state=True`; the same `/gazebo/pause_physics` service is the e-stop
binding. The runtime latches in software first. Pausing Gazebo physics is a
simulator stop, not a physical emergency stop and not a zero-velocity command.
The referee node, its 120 Hz loop and the controllers are not terminated; after
`unpause_physics` they can resume from retained state, and any other client's
unpause call (an openai_ros `MultiRobotGazeboEnv.step` or `_reset_sim` of a
running training script does one) undoes the stop.

The pause and unpause services are advertised by `gazebo_ros`, outside the
pinned clone. The clone proves the client endpoints and their role in the
openai_ros `MultiRobotGazeboEnv.step`/`_reset_sim` lifecycle, not the service
callback body. `start:false` stops only the referee `game_spin` path; it does
not pause physics and does not stop the base controller. The turret and base
command topics are transmission-only: a successful receipt says rosbridge
accepted the publication, not that the joint or base reached a state. The
mecanum controller's `cmd_vel_timeout` brake is a controller timeout, not an
acknowledged stop. `/jackal0/cmd_vel` reaches the controller through the
`topic_tools` relay of `control.launch`; in the shipped launch the referee node
also publishes there, forwarding the RoboRTS local planner's
`/jackal0/cmd_vel_acc` while `robotMove[0]` is 1, so this package is not the
topic's only publisher.

`isGameStart` starts false and `/refer_system_info` is latched: before a
`/start_game` request with `start: true` no sample exists and a live read times
out, and after `start: false` a new subscription receives the last latched
sample, which is stale. With `/use_sim_time` true (the `ridgeback_robots.launch`
default) the referee loop sleeps on simulated time, so while physics is paused it
neither services `/start_game` nor publishes.

The README's `/jackal0/debuff` topic is documented as "Not use currently" and
has no subscriber in the clone; it is not exposed. The `/jackalN/shoot`,
`/jackalN/cmd_vel_acc`, `/jackalN/obstacle_filtered`, camera, laser and TF
surfaces are not exposed. Only jackal0's namespaced base and turret topics are
declared. The gym registration `AiChallengeEnv-v1` is a scaffold: `_get_obs`
returns None, `_compute_reward` returns 0 and `_is_done` returns False. The
package therefore does not claim a Gymnasium or environment-step contract; it
integrates the concrete ROS endpoints the clone ships.

The card's entry symbols name classes in the vendored `openai_ros` tree
(including the `MyRobotEnv` template, whose task hooks raise
`NotImplementedError`) and unrelated example task environments. Those are not
the RoboMaster simulator's concrete interface. The RoboMaster-specific
`MultiAgentAiChallengeEnv` registration exists, but its observation, reward and
done paths are placeholders. The selected endpoints above are the concrete
interfaces of the simulator nodes; this deviation from the card is recorded in
`RESULT.json`.

## Units and limits

The turret angle is published in radians. The README states the unit and the
turret controller copies the Float32 value into the joint trajectory position
without conversion. The URDF gives the joint's lower and upper travel as
-1.5707 and 1.5707 rad; that is the only numeric command bound the clone
states, and it is declared on `position`.

The base command uses `geometry_msgs/Twist` body linear x/y (m/s) and angular
z (rad/s). The pinned mecanum controller configuration gives maximum values
(3.0, 2.0 and 2.0) and accelerations (5, 5 and 1.0), but these are controller
configuration values loaded by `controller_nh.param`, not device constants; a
deployment can select another configuration. The driver therefore declares
each velocity input `operator_required`; `site-limits.example.json` shows an
example narrowing overlay. The examples in the overlay are test data, not
device facts.

The `ReferSystemInfo` fields are read as raw values. `gameTime` is seconds
because `game_spin` computes it as `ros::Time::now().toSec() - start_secs`.
The pose and cell coordinates have no unit stated in the clone and are not
assigned one.

## Safety

The device is a simulated world and is declared `R2` because the package
exposes a simulated mobile-base velocity command and an unpause command that
can resume retained motion. The independent stop is the acknowledged
`/gazebo/pause_physics` service: it is both the `safety_bindings.estop` and the
input-free `safe_state=True` action. `mhs.resource.read`, catalogued read
capabilities and declared safe-state actions remain permitted after the latch;
`unpause_physics`, `start_game`, the turret publish and the base publish are
refused. The fake has no physical stop and makes no hardware-safety claim. No
hardware backend, ROS graph or Gazebo process is run by the gate.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `robomaster`, `referee`, `turret`, `mobile-base`
