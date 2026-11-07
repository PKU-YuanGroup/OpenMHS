# Facts and tags for gh.enph353/gym-gazebo-sim

Every fact cites its source at commit `d8df39af7e7c405a6738fe752d51d2e90d5fb814`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same entries are copied into
`facts = [Fact(text, source=..., ref=...)]` in `driver.py`; `reference.json` and `REFERENCE.md` are generated from the
driver, not from this page.

| fact | source | ref |
|---|---|---|
| Gym-Gazebo-Sim is a wrapper and Gazebo plugin that extends the Gymnasium API for Gazebo Sim Harmonic and ROS 2 Jazzy | vendor_doc | README.md:8-10 |
| gym_gazebo registers CartpoleEnv-v0 with entry point gym_gazebo.envs.cartpole_env:CartpoleEnv and max_episode_steps 3000 | upstream_code | src/gym_gazebo/__init__.py:6-10 |
| CartpoleEnv derives from GazeboEnv | upstream_code | src/gym_gazebo/envs/cartpole_env.py:11 |
| GazeboEnv derives from gymnasium.Env | upstream_code | src/gym_gazebo/core/gazebo_env.py:15 |
| GazeboEnv.__init__ starts the simulation with subprocess.Popen of ['ros2', 'launch', launch_pkg, launch_file] and sleeps 4.0 s for it to boot | upstream_code | src/gym_gazebo/core/gazebo_env.py:26-34 |
| The world-control service name is /world/<world_name>/control | upstream_code | src/gym_gazebo/core/gazebo_env.py:41 |
| _pause_sim sends a WorldControl request with the given pause value to the world-control service with the timeout argument 10 and does not inspect the returned result or response | upstream_code | src/gym_gazebo/core/gazebo_env.py:76-89 |
| _step_physics sends WorldControl with pause=True and multi_step=iterations to the world-control service with the timeout argument 10 | upstream_code | src/gym_gazebo/core/gazebo_env.py:91-104 |
| GazeboEnv.__init__ prints a launch message, starts ros2 launch with Popen without a stdout argument, stderr sent to STDOUT and preexec_fn=os.setsid, sleeps 4.0 s and prints 'Simulation ready!' | upstream_code | src/gym_gazebo/core/gazebo_env.py:20-47 |
| CartpoleEnv.__init__ calls rclpy.init(args=None) and passes launch package cartpole_ros, launch file my_cartpole.launch.xml and world name cartpole_world to GazeboEnv | upstream_code | src/gym_gazebo/envs/cartpole_env.py:12-19 |
| The cartpole world is named cartpole_world | upstream_code | ros2_ws/src/cartpole_ros/world/cartpole.sdf:3 |
| The shipped launch starts Gazebo through ros_gz_sim's gz_sim.launch.py with the world file, -r and the GUI configuration file keypublisher.config | upstream_code | ros2_ws/src/cartpole_ros/launch/my_cartpole.launch.xml:3-15 |
| The GUI configuration loads the WorldControl GUI plugin | upstream_code | ros2_ws/src/cartpole_ros/config/keypublisher.config:634 |
| The GUI configuration loads the KeyPublisher GUI plugin | upstream_code | ros2_ws/src/cartpole_ros/config/keypublisher.config:1264 |
| ResetSimPlugin.OnKeyPress sets teleport_requested when the received Int32 is 114 or 82 | upstream_code | ros2_ws/src/custom_plugins/src/ResetSimPlugin.cc:55-63 |
| When a teleport is requested, ResetSimPlugin.PreUpdate sets the WorldPoseCmd of every model stored in initial_poses to its stored pose, sets that model's joint position and velocity resets to 0.0 and clears the request | upstream_code | ros2_ws/src/custom_plugins/src/ResetSimPlugin.cc:134-176 |
| The reset trigger is Int32(data=114) advertised on /keyboard/keypress | upstream_code | src/gym_gazebo/core/gazebo_env.py:40-45 |
| _reset_agents publishes the reset message | upstream_code | src/gym_gazebo/core/gazebo_env.py:106-108 |
| GazeboEnv.close calls user_close and then pkill for gz sim, gz sim server, gzsim gui, ros_gz_bridge and ros2 launch | upstream_code | src/gym_gazebo/core/gazebo_env.py:60-69 |
| CartpoleEnv sets theta_limit_rad to 12 * pi / 180 rad and x_limit to 15 | upstream_code | src/gym_gazebo/envs/cartpole_env.py:28-29 |
| The observation space is gym.spaces.Box with float32 low bounds [-2*theta_limit_rad, -15, -inf, -inf] and high bounds [2*theta_limit_rad, 15, inf, inf] | upstream_code | src/gym_gazebo/envs/cartpole_env.py:31-38 |
| The action space is gym.spaces.Discrete(2) | upstream_code | src/gym_gazebo/envs/cartpole_env.py:39 |
| The ROS 2 interface subscribes to /joint_states (sensor_msgs/JointState) and publishes std_msgs/Float64MultiArray on /cart_velocity_controller/commands | upstream_code | src/gym_gazebo/envs/cartpole_env.py:41-50 |
| The step action increments current_vel by 0.2 when action == 1 and decrements it by 0.2 otherwise | upstream_code | src/gym_gazebo/envs/cartpole_env.py:136-137 |
| The step observation is [x, x_dot, theta, theta_dot], rounded to two decimals, from the concatenated JointState positions and velocities with theta normalized by atan(tan(theta)) | upstream_code | src/gym_gazebo/envs/cartpole_env.py:66-78 |
| The termination condition is \|theta\| > theta_limit_rad or \|x\| > x_limit; the reward is 1.0 while in bounds and 0.0 when terminated | upstream_code | src/gym_gazebo/envs/cartpole_env.py:176-204 |
| step unpauses the simulation, publishes the velocity command, waits for the next observation with rclpy.spin_once, pauses again and returns (state, reward, terminated, False, {}) | upstream_code | src/gym_gazebo/envs/cartpole_env.py:143-171 |
| step loops on rclpy.spin_once(timeout_sec=SPIN_TIME_s) until latest_obs is set, with no limit on the number of iterations | upstream_code | src/gym_gazebo/envs/cartpole_env.py:149-154 |
| process_obs prints a message when the angle or the position limit is exceeded | upstream_code | src/gym_gazebo/envs/cartpole_env.py:192-200 |
| user_close destroys the ROS node and calls rclpy.shutdown() when rclpy.ok() | upstream_code | src/gym_gazebo/envs/cartpole_env.py:220-223 |
| reset zeroes the velocity command, publishes it, calls _reset_agents, waits for an observation, pauses the simulation and returns (state, {}) | upstream_code | src/gym_gazebo/envs/cartpole_env.py:82-124 |
| reset accepts seed and options but does not use them; the returned state comes from the simulator's next /joint_states observation | upstream_code | src/gym_gazebo/envs/cartpole_env.py:82-124 |
| The cartpole world physics has max_step_size 0.005 s, real_time_update_rate 200 and real_time_factor 1.0 | upstream_code | ros2_ws/src/cartpole_ros/world/cartpole.sdf:6-9 |
| The package requires Python >=3.12.3 and depends on gymnasium>=1.3.0, torch>=2.12.0, tensorboard and numpy>=1.26.0 | upstream_code | pyproject.toml:8-14 |
| The README says sourcing ros2_ws/install/setup.bash is required to use the prebuilt environments | vendor_doc | README.md:140-147 |
| LICENSE.md states that the project is released under the MIT License | vendor_doc | LICENSE.md:1 |
| The cartpole_ros package.xml declares the licence 'TODO: License declaration' | upstream_code | ros2_ws/src/cartpole_ros/package.xml:8 |

Limits: the driver declares none. The only bound is the environment's action space, which the bridge derives from the
served environment. The fake copies the upstream `gym.spaces.Discrete(2)` of
`src/gym_gazebo/envs/cartpole_env.py:39`, so `cap.world.step.v1` bounds `action.index` to 0..1 and the derived limit
carries source `upstream_code` with that ref. The device is simulated R0, so no limit is `operator_required` and no
site-limits overlay is needed.

Observation space: the fake copies the declared `Box` bounds of `src/gym_gazebo/envs/cartpole_env.py:31-38` exactly.
The upstream bounds are ordered as if the state were `[theta, x, ...]`, while the upstream `obs_feed_` returns
`[x, x_dot, theta, theta_dot]` (`src/gym_gazebo/envs/cartpole_env.py:66-78`); the fake preserves both the returned
order and the declared space, and the driver fidelity gaps disclose the mismatch. It is an upstream observation-space
question, not a limit the driver may silently rewrite.

Fidelity contract (`driver.py`, `fidelity = {...}`): the deployed model is the package's own pure-Python kinematic
stand-in, engine `analytic:cartpole-env-v0-fake (no physics)`, level F0, determinism `none` with `seed_control`
`none` (upstream `reset` accepts and ignores seed/options and the state comes from Gazebo), timestep 0 ms
(event-driven; no simulated clock), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot/restore. The
upstream world configures a 0.005 s physics step, 200 Hz update rate and real-time factor 1.0
(`ros2_ws/src/cartpole_ros/world/cartpole.sdf:6-9`); those are recorded as facts and are **not** claims about the
fake. The fake's cart-position increment uses a placeholder 0.01 s bookkeeping interval, not the world physics step.

Scope: the package serves the card's first entry symbol, `CartpoleEnv-v0`
(`src/gym_gazebo/__init__.py:6-10`). The card's second registered environment, `LineFollowerEnv-v0`
(`src/gym_gazebo/__init__.py:12-16`), is a different environment (camera/`Twist` line following) and is not modelled
by this package.

Safety: simulated R0 device. The e-stop is the runtime's software latch; after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the last observation and tick stay readable. The driver exposes no native
stop: it does not send the Gazebo world-control pause command on e-stop, and an e-stop therefore does not claim that
the separate Gazebo process stopped stepping. Upstream `step` and `reset` end with a pause request whose reply
`_pause_sim` does not inspect (`src/gym_gazebo/core/gazebo_env.py:76-89`; timeout argument 10, its unit set by
gz-transport), so a live world stays paused after a completed step only if that request took effect, and a step or
reset in flight keeps the world unpaused until its next `/joint_states` sample arrives, waiting without an overall
timeout (`src/gym_gazebo/envs/cartpole_env.py:149-154`). The shipped launch runs the world (`-r`) with a GUI whose
WorldControl and KeyPublisher plugins let a user unpause it or trigger the reset plugin. There is no hardware
backend and no physical stop.

Live construction (fake-only contract): the package declares only the fake backend. Constructing the upstream
`CartpoleEnv` in the server process (the implicit `gymnasium.make` path) calls `rclpy.init` for the whole process,
starts `ros2 launch` in a new session whose stdout and stderr are the server's stdout, sleeps 4 s and prints status
lines (`src/gym_gazebo/core/gazebo_env.py:20-47`; `process_obs` also prints when a limit is exceeded), which would
corrupt an MHS server talking over stdio. `GazeboEnv.close` runs `pkill -f` / `pkill -9 -f` patterns that match every
`gz sim`, `ros_gz_bridge` and `ros2 launch` process on the host, not only its own, and `user_close` calls
`rclpy.shutdown` (`src/gym_gazebo/core/gazebo_env.py:60-69`, `src/gym_gazebo/envs/cartpole_env.py:220-223`). A live
deployment needs an owned, isolated environment factory.

Licence: `LICENSE.md` and `pyproject.toml` say MIT; the three `ros2_ws` `package.xml` files say
`TODO: License declaration`.

Tags: gymnasium, gazebo, ros2, cartpole, reinforcement-learning, simulation
