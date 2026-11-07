# Facts and tags for gh.ammar-n-abbas/sim2real-ur-gym-gazebo

Every fact cites the pinned clone at commit `c36c625626c21ed44d02729426a1220fde5ec56a` as
`upstream_code` (`path/in/clone.py:LINE`) or `vendor_doc` (a text file of the clone). The same facts are written
into `driver.py` (`facts = [...]`); `REFERENCE.md` is generated from the driver, not from this page.

## Scope

The task card's `family: ros` and `RosDriver` helper come from a scan of the repository, but the confirmed entry
symbols are Python Gymnasium environments; the repository's ROS nodes are the simulation and robot transport used by
those environments, not the primary interface. This package therefore covers one environment,
`ur_openai.task_envs.ur5_task_space:UR5TaskSpaceEnv` (registered as `UR5TaskSpaceEnv-v0`), through the
`GymnasiumDriver` family. The other entry symbols (`UR5JointSpaceEnv`, `UR5GraspEnv`, `UR5PickAndPlaceEnv` and
`UR5PickAndPlaceRealEnv`) are not covered by this one-device package. The `UR5JointSpaceEnv` was not selected because
its `step` falls through to the base `_is_terminated` method while the subclass defines only `_is_done`
(`ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_joint_space.py:203-212` and
`ur_openai_gym/ur_openai/src/ur_openai/robot_env.py:75`).

The driver is a simulated `world.sim` at R2 (REVIEW.md item 12). It exposes `cap.world.step.v1`, `cap.world.reset.v1` and
`cap.world.seed.v1`; it does not publish ROS topics or call ROS services directly. The upstream `step` calls
unpause and pause on its robot connection around the task-space action sent through `set_target_pose_flex`
(`robot_env.py:55-83`), but `UR5TaskSpaceEnv.get_robot_params` sets `param_use_gazebo` to False for every driver
value (`ur5_task_space.py:74-81`), so the connection is always the no-op `RobotConnection`
(`gazebo_connection.py:22-33`): upstream never pauses or resets Gazebo. Its `Arm` commands
`scaled_pos_joint_traj_controller`, the controller name that `ur_gazebo` and the real UR driver share, so the
same class moves a real UR5 when the operator's ROS graph runs the real driver. `UR5PickAndPlaceRealEnv` (the
real-robot entry symbol, configured with `driver: robot`) is not covered either. The action space is the upstream `Box(-1., 1.)` with `n_actions: 3`; the
observation is an unbounded 32-element Box built from 6 joint angles, 7 end-effector pose values, 7 target pose
values, 6 pose-error values and 6 velocity values (`ur5_task_space.py:38-45,136-146`).

## Facts

| fact | source | ref |
|---|---|---|
| UR5TaskSpaceEnv subclasses ur5_env.UR5Env in ur_openai.task_envs.ur5_task_space. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py:17 |
| The task-env registry registers UR5TaskSpaceEnv-v0 with entry point ur_openai.task_envs.ur5_task_space:UR5TaskSpaceEnv and a max_episode_steps argument. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/task_envs_list.py:19-25 |
| The simulation task-space configuration sets env_id UR5TaskSpaceEnv-v0 and agent_control_dt 0.005 s. | upstream_code | ur_openai_gym/ur_rl/config/simulation/task_space.yaml:3-7 |
| The same configuration sets n_actions 3 and distance_threshold 5.0. | upstream_code | ur_openai_gym/ur_rl/config/simulation/task_space.yaml:28-32 |
| The action space is Box(-1., 1.) with shape (n_actions,) and dtype float32. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py:38-40 |
| The observation space is an unbounded Box whose shape is the observation built in __init__. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py:42-45 |
| The observation concatenates joint angles, end-effector pose, target pose, pose error and velocity. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py:136-146 |
| The pose error is translation_rotation_error(target_pose, end-effector pose) and the velocity is a finite difference over agent_control_dt. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py:150-166 |
| For n_actions 3, the action is multiplied by 0.001 and applied as a translation-only pose delta with zero rotation delta. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py:187-192 |
| _set_action sends the command with set_target_pose_flex(cmd, t=agent_control_dt) without checking its return value, publishes the current pose and sleeps on the loop rate. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py:206-208 |
| The loop rate is rospy.Rate(1/agent_control_dt). | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py:48 |
| The reward is 100.0 when the episode is done and otherwise the negative end-effector-to-target distance times 1000. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py:169-174 |
| Termination is true when the translational error converted to millimetres is below distance_threshold. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py:211-220 |
| RobotGazeboEnv.step calls _pause_env when the pause flag is set, then unpause, _set_action and pause on the robot connection, reads the observation, computes terminated, truncated (step_count >= 200) and reward, and returns a five-tuple. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/robot_env.py:55-83 |
| RobotGazeboEnv.reset accepts seed and options, updates the episode, initializes per-episode variables, resets the simulation and returns (observation, info). | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/robot_env.py:85-93 |
| RobotGazeboEnv.seed reseeds np_random with gymnasium.utils.seeding.np_random. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/robot_env.py:51-53 |
| With reset_controls false, RobotGazeboEnv._reset_sim calls unpause, _check_all_systems_ready, _set_init_pose, pause, reset, unpause, _check_all_systems_ready and pause on the robot connection. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/robot_env.py:158-167 |
| With random_target_pose and random_initial_pose enabled, _set_init_pose redraws the target around the current pose and samples a new start pose from the workspace. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py:95-126 |
| The simulation task-space configuration enables random_target_pose and random_initial_pose. | upstream_code | ur_openai_gym/ur_rl/config/simulation/task_space.yaml:12-13 |
| The README describes the project as a Universal Robot Environment for Gymnasium and ROS Gazebo. | vendor_doc | README.md:3 |
| get_robot_params loads the ur_gym parameters, reads ur_gym/driver without a default and sets param_use_gazebo to False whatever the driver value is. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py:74-81 |
| UR5Env passes param_use_gazebo as use_gazebo, with reset_controls False, to RobotGazeboEnv, then calls robot_connection.unpause and constructs ur_control's Arm. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/robot_envs/ur5_env.py:52-64 |
| RobotGazeboEnv uses GazeboConnection only when use_gazebo is true; otherwise it uses RobotConnection and subscribes to ur3/pause. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/robot_env.py:24-28 |
| RobotConnection's pause, unpause and reset do nothing. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/gazebo_connection.py:22-33 |
| pause_callback sets the pause flag when a ur3/pause message is true. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/robot_env.py:46-48 |
| UR5Env._pause_env reads the joint angles, blocks on input('Press Enter to continue') and then moves the arm back to those angles with wait=True. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/robot_envs/ur5_env.py:77-80 |
| _set_action calls sys.exit() when the action contains NaN and asserts that every value lies within -1.0001 and 1.0001. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py:178-183 |
| RobotGazeboEnv.close calls rospy.signal_shutdown. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/robot_env.py:95-102 |
| Importing ur5_env inserts an absolute /home/imr workspace path at the front of sys.path. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/robot_envs/ur5_env.py:24-25 |
| Arm publishes its flexible trajectories on the namespace plus '/' plus JOINT_PUBLISHER_ROBOT plus '/command'. | upstream_code | ur_control/src/ur_control/arm.py:116-127 |
| JOINT_PUBLISHER_ROBOT is scaled_pos_joint_traj_controller. | upstream_code | ur_control/src/ur_control/constants.py:4 |
| The ur_gazebo UR5 controller configuration defines a controller named scaled_pos_joint_traj_controller. | upstream_code | ur_gazebo/config/ur5_controllers.yaml:5 |
| set_joint_positions_flex returns SPEED_LIMIT_EXCEEDED without commanding when the required joint speed exceeds max_joint_speed, and set_target_pose_flex returns IK_NOT_FOUND when inverse kinematics finds no solution. | upstream_code | ur_control/src/ur_control/arm.py:395-422 |
| With curriculum_learning enabled, each _set_init_pose call lowers dist_cl by 0.005 and uses it as distance_threshold, never below 5. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py:104-109 |
| The simulation task-space configuration sets driver gazebo, curriculum_learning true and dist_cl 50. | upstream_code | ur_openai_gym/ur_rl/config/simulation/task_space.yaml:4-15 |
| UR5PickAndPlaceRealEnv.get_robot_params sets param_use_gazebo True unless the ur_gym/driver parameter is robot. | upstream_code | ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space_pick_and_place_real.py:203-209 |
| The real-robot configuration sets env_id UR5PickAndPlaceRealEnv-v0 and driver robot. | upstream_code | ur_openai_gym/ur_rl/config/real/task_space_pick_and_place_real.yaml:3-4 |

## Fidelity contract

`driver.py` describes the deployed fake backend, not the upstream simulator: engine `analytic`, level F0,
determinism `seeded` (the fake draws its target jitter from `random.Random(seed)`; upstream `reset(seed)` ignores
the seed and uses the process-global numpy RNG), `timestep_ms: 5.0` from `agent_control_dt: 0.005`, clock
`lockstep`, `realtime_factor: 0`, reset `full`, and no snapshot/restore. The fake models only the end-effector
translation `action * 0.001` m; it has no inverse kinematics, joint limits, dynamics, contacts, collisions,
grasping, Gazebo physics or ROS graph. It keeps the configured 5.0 mm termination threshold, while the shipped
simulation configuration's curriculum makes upstream terminate at `dist_cl` (from 50, never below 5). The full list
of gaps, including the live-construction hazards (`sys.exit()` on a NaN action, `input()` after a `ur3/pause`
message, `rospy.signal_shutdown` on close, a `/home/imr` `sys.path` entry), is in `driver.py`.

## Safety

The device risk is R2, an arm, and only the fake backend is declared. There is no native e-stop method: an e-stop
is the runtime's software latch, which refuses further `cap.world.step.v1` and `cap.world.reset.v1` calls until
`mhs.safety.reset` clears it, while the last observation remains readable. The latch cannot interrupt an in-flight
native `env.step` call and does not send a zero trajectory; no hardware-safety claim is made. Upstream never pauses
Gazebo, so a live simulation would keep running with the trajectory controller holding the last commanded target;
`safe_state` says so. `Arm` publishes `JointTrajectory` on `scaled_pos_joint_traj_controller/command`
(`arm.py:115-127`, `constants.py:4`, `ur5_controllers.yaml:5-25`). The same class drives a real UR5 when the real
driver is running, and the latch does not stop that arm.

## Tags

`ur5`, `universal-robots`, `gazebo`, `ros`, `gymnasium`, `reinforcement-learning`, `simulation`, `robot-arm`,
`task-space`
