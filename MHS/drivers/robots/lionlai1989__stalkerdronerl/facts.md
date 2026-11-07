# Facts and tags for gh.lionlai1989/stalkerdronerl

Every fact cites the pinned clone at commit `e34db1c6a4926d22b447aa1ef93e9bb0bad4793c`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the statement spans
adjacent lines. The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| StalkerDroneRL is a fully containerized ROS 2 + Gazebo project that simulates a quadcopter stalking a red ball with a Gymnasium and Stable Baselines3 deep reinforcement learning controller. | vendor_doc | README.md:3-5 |
| The sdrl_rl_controller package implements the Gymnasium environment and trains the drone controller with Stable Baselines3. | vendor_doc | README.md:62-63 |
| The project documentation says it simulates a drone in a physical environment using ROS 2 Humble and Gazebo Harmonic and that the deep RL framework is Gymnasium and Stable Baselines3. | vendor_doc | docs/StalkerDroneRL.md:2-4 |
| QuadcopterTrackingEnv derives from gym.Env. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:50 |
| The QuadcopterTrackingEnv constructor defaults control_freq to 100, max_episode_steps to 2000 and use_sim_time to True, calls rclpy.init() when rclpy is not running and creates a node with that use_sim_time parameter. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:53-72 |
| The action space is a four-element gym.spaces.Box with low -1 and high 1 and dtype float32; the comment names the components fz, tx, ty and tz. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:151-156 |
| The observation space is an eleven-element gym.spaces.Box with low -1 and high 1 and dtype float32. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:158-165 |
| The environment subscribes to /X3/gt_odom, /X3/cmd_odom and /X3/navi_state, publishes motor speeds on /X3/ros/motor_speed and creates Trigger clients for /X3/reset_navigator and /X3/reset_dynamics. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:189-201 |
| The constant WORLD_NAME is ground_plane_world and QUADCOPTER_MODEL is lion_quadcopter, with MAX_POS_DIST 9.0 and MAX_VEL_DIST 5.0. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:41-47 |
| step converts the normalized action to motor speeds, publishes them, calls gz_client.world_control with step_multi=10 and no pause argument, waits for odometry stamped at least one control period after the step began, then computes the tracking error and reward. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:362-443 |
| _wait_for_odom polls the odometry stamp every 0.5 ms and, after 2 s of wall-clock time without a new enough stamp, logs a warning and returns normally. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:219-238 |
| gz_client.world_control sets the WorldControl pause field only when a pause argument is given, sets step and multi_step when step_multi is given, and raises RuntimeError when the request fails. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/gz_client.py:37-47 |
| The step comments state that physics runs at 1000 Hz and control at 100 Hz and that ten physics steps are requested per environment step. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:389-393 |
| The reward configuration is base 0.2, position-distance penalty -0.0388, velocity-distance penalty -0.007, progress reward 1.0, danger-zone tilt pi/6, tilt penalty -0.5, success bonus 2.5 and crash penalty -10.0; the step reward range is documented as [-10, 10]. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:105-115 |
| The reward adds the base term, the distance and velocity penalties, a progress term that is zero when the command position moved more than 0.5 since the last step, the tilt penalty above the danger-zone tilt and the success and crash terms, and clips the result to [-10, 10]. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:240-278 |
| A step terminates only when the navigator state has been CRASHED for at least four consecutive steps, and truncates when step_count reaches max_steps. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:419-474 |
| step returns the normalized observation, reward, terminated, truncated and an info dict with success and crash. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:473-485 |
| reset accepts seed and options, calls super().reset(seed=seed), requests the drone reset, waits for fresh odometry, pauses physics and returns (observation, {}). | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:487-544 |
| After the reset sequence, reset waits for fresh odometry on a 10 Hz node rate, measures its 5 s timeout with the node clock and raises RuntimeError when it expires. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:514-530 |
| The reset sequence pauses physics, calls the navigator reset service, publishes zero motor speeds five times, teleports the drone to random x and y with z=0.05, calls the dynamics reset service and unpauses physics. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:546-614 |
| The reset comment records that the drone is still moving slightly after being put back at the initial position and that residual velocity may need a second reset. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:574-576 |
| close shuts down rclpy when it is running, joins the spin thread and destroys the node. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:620-625 |
| The training entry refuses n_envs other than 1 because the ROS 2/Gazebo simulation exposes a single physical drone instance, and it constructs QuadcopterTrackingEnv directly rather than through gym.make. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:771-806 |
| The normalized observation is eleven float32 values: body-frame position error, body-frame velocity error, roll, pitch and body rates p, q and r. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/observation_state_action.py:25-130 |
| The observation normalization constants are MAX_POS_ERR 5.0, MAX_VEL_ERR 3.0 and MAX_ANG_VEL 6.28. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/observation_state_action.py:20-22 |
| action_to_wrench accepts only an action with shape (4,) and values in [-1, 1], treats action[0] as normalized force z and action[1:4] as normalized torques x, y and z, and maps them through the wrench limits. | upstream_code | src/sdrl_rl_controller/sdrl_rl_controller/observation_state_action.py:133-162 |
| QuadcopterParams defines a 1.5 kg mass and the diagonal inertia [0.0347563, 0.07, 0.0977]. | upstream_code | src/sdrl_geometric_controller/sdrl_geometric_controller/quadcopter_params.py:14-16 |
| QuadcopterParams sets hover_thrust to mass * GRAVITY * 1.1. | upstream_code | src/sdrl_geometric_controller/sdrl_geometric_controller/quadcopter_params.py:86 |
| The project documentation notes that Gazebo shows a large initial velocity after the reset that looks like left-over velocity from the previous episode. | vendor_doc | docs/StalkerDroneRL.md:46-54 |
| The training launch file starts Gazebo with gz sim -r, with the GUI or headless (-s). | upstream_code | src/sdrl_bringup/launch/train_sac_launch.py:94-105 |

## Scope and shape

The card's static scan proposed a ROS helper because the repository is a ROS 2 + Gazebo project.
The confirmed entry symbol is `QuadcopterTrackingEnv`
(`src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:50`), a Gymnasium environment, so the
package uses `GymnasiumDriver` and records `DEVIATION FROM THE CARD` in `RESULT.json`. The ROS
topics and services are internal to the environment's Gazebo/navigator loop; the primary control
interface is `reset()` and `step(action)`. The clone contains no `gym.register` call, so no
registered Gymnasium id is invented (`env_id = None`); the training entry constructs the class
directly (`train_sac.py:795-801`).

The bridge derives three catalogue classes: `cap.world.step.v1` (`{ticks, action}`),
`cap.world.reset.v1` (`{seed, options}`) and `cap.world.seed.v1` (`{seed}`). The action bounds are
the upstream four-element Box `[-1, 1]`, cited at `train_sac.py:152-156`; the driver declares no
Limit for the action because the Gymnasium bridge derives it from the action space. The
observation is the upstream eleven-element Box `[-1, 1]`. There are no other numeric inputs, so
there is no operator overlay and no `site-limits.example.json`.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic`, level F0, determinism `seeded` with
`seed_control` `parameter`, timestep 10 ms (one 100 Hz control step), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot/restore. The fake is a pure Python point mass with a
three-axis attitude, not the upstream Gazebo model. It mirrors the 11-value observation layout,
the 4-value action layout and the upstream reward terms, but its values, trajectories, target,
reset sequence, crash test and success radius are its own. It was never compared with the
upstream simulator. The upstream reset draws x/y jitter from the global NumPy generator
(`train_sac.py:582-584`) and documents residual velocity after reset
(`train_sac.py:574-576`, `docs/StalkerDroneRL.md:46-54`); the fake uses a per-instance
`random.Random` and zeroes velocity, so upstream determinism is not claimed and the test cases that
assert seeded repeats are fake-only. The upstream `step` also swallows a missing observation:
`_wait_for_odom` returns after 2 s of wall-clock time with only a warning (`train_sac.py:219-238`),
and the step is then computed from stale odometry.

## Safety

The device is simulated at R0. There is no hardware backend, no native stop and no physical
e-stop. The runtime's software latch refuses every step, reset and seed after `mhs.estop` until
`mhs.safety.reset`; the in-process fake stops advancing and its state stays readable. The latch would
not pause a live Gazebo world, which this package never drives: the training launch starts Gazebo
running (`train_sac_launch.py:94-105`), the upstream step requests ten iterations without setting the
WorldControl pause field (`gz_client.py:37-47`, `train_sac.py:393`), and nothing zeroes the motor
speeds last published on `/X3/ros/motor_speed`. The stock constructor calls the global `rclpy.init`,
starts a spin thread and waits on services and on a simulated-time timeout in `reset`, and `close()`
calls the global `rclpy.shutdown`; these are why no sim backend is declared. A model-authored package never runs a
hardware backend, and `driver.lock.json` keeps `reviewed_by: null`.

## Tags

`ros2`, `gazebo`, `quadcopter`, `reinforcement-learning`, `simulation`, `gymnasium`
