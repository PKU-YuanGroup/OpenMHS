OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.rickstaa/ros-gazebo-gym

Every fact cites its source at commit `157981585c26e7d252bc10e4deb527ca450775a0`, except the last eight, which cite
the reviewed companion source gazebo_ros 2.9.3 (ROS 1 Noetic) at its corpus pin
`cd9cc952402375be5f274f39b29399c4087aa839` (`task.json` `companions`; integrator v4, 2026-11-05). The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PandaReach-v1 is registered with entry point ros_gazebo_gym.task_envs.panda.panda_reach:PandaReachEnv and max_steps 500 | upstream_code | src/ros_gazebo_gym/task_envs/task_envs_list.py:21-24 |
| The PandaReachEnv constructor defaults control_type to 'effort' | upstream_code | src/ros_gazebo_gym/task_envs/panda/panda_reach.py:198-207 |
| The shipped panda_reach.yaml sets load_gripper False and lists the seven panda_joint values under controlled_joints | upstream_code | src/ros_gazebo_gym/task_envs/panda/config/panda_reach.yaml:10-33 |
| The shipped effort bounds are -87 to 87 for panda_joint1 through panda_joint4 and -12 to 12 for panda_joint5 through panda_joint7 | upstream_code | src/ros_gazebo_gym/task_envs/panda/config/panda_reach.yaml:209-227 |
| The action space is a Box built from the bounds of the configured control type, ordered by the action-space joints | upstream_code | src/ros_gazebo_gym/task_envs/panda/panda_reach.py:1157-1232 |
| The observation space is a Dict of observation, desired_goal and achieved_goal, each an unbounded Box shaped from a sample observation | upstream_code | src/ros_gazebo_gym/task_envs/panda/panda_reach.py:521-542 |
| The observation member concatenates the end-effector position with the finger joint positions and velocities selected by the panda_finger name | upstream_code | src/ros_gazebo_gym/task_envs/panda/panda_reach.py:1345-1379 |
| The shipped panda_reach.yaml selects the dense reward type | upstream_code | src/ros_gazebo_gym/task_envs/panda/config/panda_reach.yaml:159 |
| The non-sparse reward subtracts the goal distance and any enabled collision penalty, then uses its absolute value when positive_reward is true | upstream_code | src/ros_gazebo_gym/task_envs/panda/panda_reach.py:1295-1325 |
| The episode terminates when the goal distance is below distance_threshold, and with target_hold it requires hold_samples consecutive samples | upstream_code | src/ros_gazebo_gym/task_envs/panda/panda_reach.py:1470-1488 |
| The shipped config sets target_hold True, hold_samples 2 and distance_threshold 0.05 | upstream_code | src/ros_gazebo_gym/task_envs/panda/config/panda_reach.yaml:160-162 |
| A global target is drawn uniformly from the target sampling bounds of the environment's numpy generator | upstream_code | src/ros_gazebo_gym/task_envs/panda/panda_reach.py:1504-1517 |
| The shipped global target bounds are x 0.1 to 0.8, y -0.4 to 0.4 and z 0.1 to 1.0 | upstream_code | src/ros_gazebo_gym/task_envs/panda/config/panda_reach.yaml:139-146 |
| The info dictionary returns reference, state_of_interest and reference_error | upstream_code | src/ros_gazebo_gym/task_envs/panda/panda_reach.py:1381-1398 |
| reset() calls the parent gymnasium reset with the seed, resets the simulation and then re-initialises the episode variables | upstream_code | src/ros_gazebo_gym/robot_gazebo_goal_env.py:200-227 |
| The shipped panda_reach.yaml sets random_init_pose True | upstream_code | src/ros_gazebo_gym/task_envs/panda/config/panda_reach.yaml:64 |
| In the random end-effector sampling branch, reset calls _get_random_ee_pose when first-episode randomization is enabled or episode_num is not zero | upstream_code | src/ros_gazebo_gym/task_envs/panda/panda_reach.py:1602-1637 |
| The shipped config pauses the simulation after every step | upstream_code | src/ros_gazebo_gym/task_envs/panda/config/panda_reach.yaml:169 |
| The shipped config selects the ODE physics engine | upstream_code | src/ros_gazebo_gym/task_envs/panda/config/panda_reach.yaml:232 |
| The upstream close() calls ros_exit_gracefully with exit code 0 | upstream_code | src/ros_gazebo_gym/robot_gazebo_goal_env.py:229-236 |
| ros_exit_gracefully signals ROS shutdown and exits the interpreter | upstream_code | src/ros_gazebo_gym/core/helpers.py:325-339 |
| The environment keeps its GazeboConnection as the gazebo attribute | upstream_code | src/ros_gazebo_gym/robot_gazebo_goal_env.py:83 |
| GAZEBO_PAUSE_PHYSICS_TOPIC is /gazebo/pause_physics | upstream_code | src/ros_gazebo_gym/core/gazebo_connection.py:50 |
| GazeboConnection's constructor creates pause_proxy, a rospy ServiceProxy of GAZEBO_PAUSE_PHYSICS_TOPIC with the std_srvs Empty type | upstream_code | src/ros_gazebo_gym/core/gazebo_connection.py:136-148 |
| pause_sim() calls pause_proxy in a retry loop that stops once rospy is shut down and calls ros_exit_gracefully after max_retry failures | upstream_code | src/ros_gazebo_gym/core/gazebo_connection.py:328-356 |
| get_physics_properties() returns the physics_properties response and raises GetPhysicsPropertiesError when its success field is false | upstream_code | src/ros_gazebo_gym/core/gazebo_connection.py:562-580 |
| The physics_properties property calls the get_physics_proxy service proxy | upstream_code | src/ros_gazebo_gym/core/gazebo_connection.py:805-808 |
| get_physics_proxy is a rospy ServiceProxy of GAZEBO_GET_PHYSICS_PROPERTIES_TOPIC with the GetPhysicsProperties type | upstream_code | src/ros_gazebo_gym/core/gazebo_connection.py:286-288 |
| GAZEBO_GET_PHYSICS_PROPERTIES_TOPIC is /gazebo/get_physics_properties | upstream_code | src/ros_gazebo_gym/core/gazebo_connection.py:63 |
| The environment constructor ends by unpausing the simulation | upstream_code | src/ros_gazebo_gym/robot_gazebo_goal_env.py:125-128 |
| step() unpauses the simulation before it applies the action and pauses it after the observation only when pause_simulation is set | upstream_code | src/ros_gazebo_gym/robot_gazebo_goal_env.py:157-163 |
| reset() pauses the simulation at its end when pause_simulation is set | upstream_code | src/ros_gazebo_gym/robot_gazebo_goal_env.py:221-223 |
| PandaEnv passes pause_after_step on as pause_simulation | upstream_code | src/ros_gazebo_gym/robot_envs/panda_env.py:336-344 |
| The shipped config sets direct_control True: arm commands are published on the controller command topics | upstream_code | src/ros_gazebo_gym/task_envs/panda/config/panda_reach.yaml:7 |
| With direct control the arm effort commands are published as Float64MultiArray on the command topic of ARM_EFFORT_CONTROLLER | upstream_code | src/ros_gazebo_gym/robot_envs/panda_env.py:643-657 |
| ARM_EFFORT_CONTROLLER is panda_arm_joint_effort_controller | upstream_code | src/ros_gazebo_gym/robot_envs/panda_env.py:100 |
| _set_action calls ros_exit_gracefully when the action shape differs from the action space shape | upstream_code | src/ros_gazebo_gym/task_envs/panda/panda_reach.py:1406-1413 |
| The constructor calls ros_exit_gracefully when a Gazebo instance is already running | upstream_code | src/ros_gazebo_gym/task_envs/panda/panda_reach.py:280-289 |
| ROSLauncher.initialize starts roscore in a subprocess when no ROS master is online | upstream_code | src/ros_gazebo_gym/core/ros_launcher.py:37-43 |
| The constructor launches the panda_gazebo world launch file with paused set through ROSLauncher.launch | upstream_code | src/ros_gazebo_gym/task_envs/panda/panda_reach.py:307-317 |
| ROSLauncher.launch installs a missing launch package and its dependencies before launching it | upstream_code | src/ros_gazebo_gym/core/ros_launcher.py:133-139 |
| The launch command runs in a PopenAutoCleanup subprocess through /bin/bash with shell=True | upstream_code | src/ros_gazebo_gym/core/ros_launcher.py:176-184 |
| PopenAutoCleanup registers its process cleanup with atexit | upstream_code | src/ros_gazebo_gym/core/helpers.py:74 |
| The cleanup terminates the launched process's children and then the process | upstream_code | src/ros_gazebo_gym/core/helpers.py:88-107 |
| install_package clones a missing dependency into the workspace from the dependency index | upstream_code | src/ros_gazebo_gym/core/helpers.py:550-562 |
| is_repo_up_to_date fetches the repository's origin remote | upstream_code | src/ros_gazebo_gym/core/helpers.py:314 |
| Rebuilding the workspace asks whether to install the ROS system dependencies and runs sudo rosdep install only when the answer is yes | upstream_code | src/ros_gazebo_gym/core/helpers.py:358-377 |
| The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:125-126 |
| The API plugin creates its node handle in the private namespace ~ and advertises its topics and services there. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:145 |
| The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback queue gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:492-498 |
| The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties type on gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:383-389 |
| pausePhysics calls world_->SetPaused(true) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1725-1729 |
| getPhysicsProperties sets res.pause to world_->IsPaused(). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1489 |
| getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it sets success false and returns false. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1496-1528 |
| The GetPhysicsProperties response field pause is true if the physics engine is paused. | upstream_code | companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment's
`Box(7)` (`action.values` from `[-87, -87, -87, -87, -12, -12, -12]` to `[87, 87, 87, 87, 12, 12, 12]`, source
`upstream_code`, ref `src/ros_gazebo_gym/task_envs/panda/config/panda_reach.yaml:211-226`) and `ticks` (1 to
`max_ticks`, 10000 by default). The device is simulated, so no limit is `operator_required`.

Risk: R2, above the card floor R0 (REVIEW.md item 12). With the shipped `direct_control: True`
(`panda_reach.yaml:7`) a step publishes the seven joint efforts as `Float64MultiArray` on
`panda_arm_joint_effort_controller/command` (`robot_envs/panda_env.py:100`, `:643-657`), a ros_control command
topic that a physical Panda's control stack could also serve; a real arm behind the same ROS graph would act on it.
The stop (`/gazebo/pause_physics`) is a service only the simulator serves.

Process isolation: both backends run in an isolated simulator host (`process_by_backend`, SDK
`mhs.bridge.sim_host`, profile `isolated_process_v1`). A child process that the endpoint starts and owns imports the
backend entry (`.fake:FakePandaReachEnv` or `.host:make_env`), builds the environment on its main thread and serves
`step`, `reset`, `close`, the stop and the read-back over two private pipes; its standard streams are `/dev/null`.
Upstream code ends calls with `sys.exit` after a global `rospy.signal_shutdown` (`ros_exit_gracefully`,
`core/helpers.py:325-339`) in `close()` (`robot_gazebo_goal_env.py:229-236`), in `pause_sim()` after `max_retry`
failures (`core/gazebo_connection.py:328-356`), when the action shape is wrong (`panda_reach.py:1406-1413`) and when
Gazebo already runs at construction (`panda_reach.py:280-289`): in the host each of these ends the call, never the
endpoint; after one, only `close` is accepted. Construction starts roscore when no master runs
(`core/ros_launcher.py:37-43`) and launches the `panda_gazebo` world paused (`panda_reach.py:307-317`) as a shell
`roslaunch` subprocess (`core/ros_launcher.py:176-184`) whose cleanup is registered with `atexit`
(`core/helpers.py:74`, `:88-107`); the host's exit is an ordinary interpreter exit, so that cleanup runs,
unless the host has to be killed after its close bound (then launched processes can survive it). A missing
package is cloned into the workspace (`core/helpers.py:550-562`) and the remotes of cloned packages are fetched
(`core/helpers.py:314`); the rebuild asks before `sudo rosdep install` (`core/helpers.py:358-377`), and the host's
standard input is `/dev/null`. Prepare the catkin workspace before deployment.

Fidelity contract: engine `ros_gazebo_gym:PandaReach-v1 (package fake)` for the fake backend, level F0 (the fake is an
analytic stand-in with no arm, controller, contact or sensor dynamics), determinism `none` with partial seed control,
timestep 0 ms (the fake advances one transition per call without a physical clock),
`realtime_factor` 0, clock `lockstep`, reset `partial`, no snapshot and restore. The fake's action space is copied from
the upstream shipped configuration; its dynamics mapping is a placeholder. The fake also models the pause state the
stop and the read-back act on (construction ends unpaused, a step unpauses first and, with the shipped
`pause_after_step`, pauses after, a reset ends paused). The gaps say what is not modelled, that the upstream
simulation (ROS, Gazebo, MoveIt) was not run, and that one seed gives different episodes on the fake and the upstream
environment. Reset intentionally preserves the target-hold counter, as the pinned upstream does
(`panda_reach.py:1793-1800`); thus even the fake's terminal result can depend on prior history after an identically
seeded reset. A seed repeats the fake's sampled observation, not the complete episode. No replay equality is claimed.
A `sim`-backend instance publishes its own contract (`fidelity_by_backend["sim"]`: F1, Gazebo's own clock, timestep
not declared because the `panda_gazebo` world sets it outside the clone); the fake's contract is never projected
onto it.

Safety: on an e-stop the endpoint latches first and fences the host (no step or reset is sent, and the host refuses
one it receives after the stop); the host calls the environment's `gazebo.pause_proxy` (the
`/gazebo/pause_physics` service proxy, `core/gazebo_connection.py:136-148`) within 2 s on the fake and 5 s live;
a step or reset in flight is waited for (10 s fake, 60 s live) and the pause is sent again, because a step unpauses
the world before it applies its action (`robot_gazebo_goal_env.py:157-163`); the stop is confirmed only when
`gazebo.get_physics_properties()` (`core/gazebo_connection.py:562-580`, `:805-808`) returns `pause` exactly True.
`pause_sim()` is not used: it retries for seconds, then exits the interpreter, and it returns without pausing once
rospy is shut down (`:328-356`). A dead or unresponsive host, a failed or late pause or read-back, or another value is
`MHS.SAFETY.SAFE_STATE_UNREACHED`: the latch stays, the endpoint retries, and safety reset is refused until a stop
is confirmed. The safety reset lifts the host's fence and changes nothing in the simulator. The paused world keeps
the last effort command in its controllers; the next step unpauses the world before it applies its own action, so
that stored command acts for that interval (the upstream's own step order). Another ROS client or the Gazebo GUI can
unpause or step the world. That the real `/gazebo/pause_physics` sets the world's paused flag and that
`get_physics_properties` reports it is cited from the reviewed companion source gazebo_ros 2.9.3 (ROS 1 Noetic, the
release of the clone's CI image `osrf/ros:noetic-desktop-full`, `.ci/Dockerfile.noetic:1`) at its corpus pin
`cd9cc952` (`task.json` `companions`; integrator v4, 2026-11-05): the API plugin's node `gazebo` advertises both
services in its private namespace, `pausePhysics` calls `World::SetPaused(true)`, and `getPhysicsProperties` sets
`pause` to `IsPaused()` and succeeds only with the ODE engine, which the shipped config selects. What a paused Gazebo
world still runs is Gazebo classic's and is not cited here. No physical stop is claimed, and there is no hardware
backend.

Live use: the `sim` backend (`host.py`) is a deployment route that was never run here: it needs ROS Noetic, Gazebo,
MoveIt and a catkin workspace with `panda_gazebo` and `panda_moveit_planner_server`; ROS Noetic's interpreter can be
selected for the host with `MHS_SIM_HOST_PYTHON`. The real simulator's initial pose uses unseeded MoveIt sampling, so
no seeded native determinism is advertised. There is no claim of a ROS, Gazebo or hardware run.

Tags: panda, franka, robot-arm, reach, gazebo, ros, reinforcement-learning, simulation, gymnasium
