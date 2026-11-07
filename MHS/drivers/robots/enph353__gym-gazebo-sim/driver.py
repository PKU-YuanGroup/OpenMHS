"""OpenMHS driver for gh.enph353/gym-gazebo-sim: the registered CartpoleEnv-v0 environment.

The task card names a ``RosDriver``, but the confirmed entry symbol
``gym_gazebo.envs.cartpole_env:CartpoleEnv`` is a Gymnasium environment
(``CartpoleEnv`` derives from ``GazeboEnv``, which derives from ``gymnasium.Env``).
The repository also contains a ROS 2 workspace and a Gazebo reset plugin, but they are the
environment's backend, not its public interface.  A Gymnasium environment does not become a
ROS transport driver because its repository also contains ROS nodes, so this package is a
:class:`GymnasiumDriver` over ``cap.world.step.v1``, ``cap.world.reset.v1`` and
``cap.world.seed.v1`` (DEVIATION FROM THE CARD, recorded in RESULT.json).  The bridge derives
the step action schema and its limits from the environment's ``gym.spaces.Discrete(2)``
action space; the package declares no ``Limit``.

The device is simulated (R0): there is no hardware backend, no physical e-stop and no
operator-required limit.  The upstream constructor calls ``rclpy.init`` for the whole process,
starts ``ros2 launch`` (a Gazebo Harmonic and ROS 2 Jazzy stack) and waits four seconds for it,
so the gate cannot open the real environment.  The ``fake`` backend is this package's
pure-Python kinematic stand-in for the native class (fake.py); this is a fake-only contract:
the implicit ``sim`` path is ``gymnasium.make("CartpoleEnv-v0")``, which would construct the
upstream environment inside the server process with the hazards listed in the fidelity gaps,
and it was not run.  The e-stop is the runtime latch only and sends nothing to Gazebo.  The fake
copies the upstream action space, which ``action_space_ref`` cites.

Every fact cites the pinned clone at d8df39af7e7c405a6738fe752d51d2e90d5fb814.  This package
is model-authored and unreviewed; it is checked on the fake backend only, and no Gazebo, ROS 2,
live simulator or hardware run has happened.
"""

from mhs.driver import Fact, GymnasiumDriver

CARTPOLE = "src/gym_gazebo/envs/cartpole_env.py"
GAZEBO = "src/gym_gazebo/core/gazebo_env.py"
WORLD = "ros2_ws/src/cartpole_ros/world/cartpole.sdf"


class GymGazeboCartpole(GymnasiumDriver):
    device_id = "gym-gazebo-cartpole"
    env_id = "CartpoleEnv-v0"
    native = "gym_gazebo.envs.cartpole_env:CartpoleEnv"
    backends = {"fake": ".fake:FakeCartpoleEnv"}
    # The fake copies the upstream Discrete(2) of CARTPOLE:39.
    action_space_ref = f"{CARTPOLE}:39"
    display_name = "Gym-Gazebo-Sim CartpoleEnv-v0"
    vendor, model = "ENPH353", "CartpoleEnv-v0"
    tags = ["gymnasium", "gazebo", "ros2", "cartpole", "reinforcement-learning", "simulation"]
    facts = [
        Fact("Gym-Gazebo-Sim is a wrapper and Gazebo plugin that extends the Gymnasium API for "
             "Gazebo Sim Harmonic and ROS 2 Jazzy", source="vendor_doc", ref="README.md:8-10"),
        Fact("gym_gazebo registers CartpoleEnv-v0 with entry point "
             "gym_gazebo.envs.cartpole_env:CartpoleEnv and max_episode_steps 3000",
             source="upstream_code", ref="src/gym_gazebo/__init__.py:6-10"),
        Fact("CartpoleEnv derives from GazeboEnv", source="upstream_code", ref=f"{CARTPOLE}:11"),
        Fact("GazeboEnv derives from gymnasium.Env", source="upstream_code", ref=f"{GAZEBO}:15"),
        Fact("GazeboEnv.__init__ starts the simulation with subprocess.Popen of "
             "['ros2', 'launch', launch_pkg, launch_file] and sleeps 4.0 s for it to boot",
             source="upstream_code", ref=f"{GAZEBO}:26-34"),
        Fact("The world-control service name is /world/<world_name>/control",
             source="upstream_code", ref=f"{GAZEBO}:41"),
        Fact("_pause_sim sends a WorldControl request with the given pause value to the world-control "
             "service with the timeout argument 10 and does not inspect the returned result or response",
             source="upstream_code", ref=f"{GAZEBO}:76-89"),
        Fact("_step_physics sends WorldControl with pause=True and multi_step=iterations to the "
             "world-control service with the timeout argument 10", source="upstream_code",
             ref=f"{GAZEBO}:91-104"),
        Fact("GazeboEnv.__init__ prints a launch message, starts ros2 launch with Popen without a stdout "
             "argument, stderr sent to STDOUT and preexec_fn=os.setsid, sleeps 4.0 s and prints "
             "'Simulation ready!'", source="upstream_code", ref=f"{GAZEBO}:20-47"),
        Fact("CartpoleEnv.__init__ calls rclpy.init(args=None) and passes launch package cartpole_ros, "
             "launch file my_cartpole.launch.xml and world name cartpole_world to GazeboEnv",
             source="upstream_code", ref=f"{CARTPOLE}:12-19"),
        Fact("The cartpole world is named cartpole_world", source="upstream_code", ref=f"{WORLD}:3"),
        Fact("The shipped launch starts Gazebo through ros_gz_sim's gz_sim.launch.py with the world file, "
             "-r and the GUI configuration file keypublisher.config",
             source="upstream_code", ref="ros2_ws/src/cartpole_ros/launch/my_cartpole.launch.xml:3-15"),
        Fact("The GUI configuration loads the WorldControl GUI plugin", source="upstream_code",
             ref="ros2_ws/src/cartpole_ros/config/keypublisher.config:634"),
        Fact("The GUI configuration loads the KeyPublisher GUI plugin", source="upstream_code",
             ref="ros2_ws/src/cartpole_ros/config/keypublisher.config:1264"),
        Fact("ResetSimPlugin.OnKeyPress sets teleport_requested when the received Int32 is 114 or 82",
             source="upstream_code", ref="ros2_ws/src/custom_plugins/src/ResetSimPlugin.cc:55-63"),
        Fact("When a teleport is requested, ResetSimPlugin.PreUpdate sets the WorldPoseCmd of every model "
             "stored in initial_poses to its stored pose, sets that model's joint position and velocity "
             "resets to 0.0 and clears the request", source="upstream_code",
             ref="ros2_ws/src/custom_plugins/src/ResetSimPlugin.cc:134-176"),
        Fact("The reset trigger is Int32(data=114) advertised on /keyboard/keypress",
             source="upstream_code", ref=f"{GAZEBO}:40-45"),
        Fact("_reset_agents publishes the reset message", source="upstream_code",
             ref=f"{GAZEBO}:106-108"),
        Fact("GazeboEnv.close calls user_close and then pkill for gz sim, gz sim server, "
             "gzsim gui, ros_gz_bridge and ros2 launch", source="upstream_code",
             ref=f"{GAZEBO}:60-69"),
        Fact("CartpoleEnv sets theta_limit_rad to 12 * pi / 180 rad and x_limit to 15",
             source="upstream_code", ref=f"{CARTPOLE}:28-29"),
        Fact("The observation space is gym.spaces.Box with float32 low bounds "
             "[-2*theta_limit_rad, -15, -inf, -inf] and high bounds "
             "[2*theta_limit_rad, 15, inf, inf]", source="upstream_code",
             ref=f"{CARTPOLE}:31-38"),
        Fact("The action space is gym.spaces.Discrete(2)", source="upstream_code",
             ref=f"{CARTPOLE}:39"),
        Fact("The ROS 2 interface subscribes to /joint_states (sensor_msgs/JointState) and "
             "publishes std_msgs/Float64MultiArray on /cart_velocity_controller/commands",
             source="upstream_code", ref=f"{CARTPOLE}:41-50"),
        Fact("The step action increments current_vel by 0.2 when action == 1 and decrements it "
             "by 0.2 otherwise", source="upstream_code", ref=f"{CARTPOLE}:136-137"),
        Fact("The step observation is [x, x_dot, theta, theta_dot], rounded to two decimals, "
             "from the concatenated JointState positions and velocities with theta normalized "
             "by atan(tan(theta))", source="upstream_code", ref=f"{CARTPOLE}:66-78"),
        Fact("The termination condition is |theta| > theta_limit_rad or |x| > x_limit; the "
             "reward is 1.0 while in bounds and 0.0 when terminated", source="upstream_code",
             ref=f"{CARTPOLE}:176-204"),
        Fact("step unpauses the simulation, publishes the velocity command, waits for the next "
             "observation with rclpy.spin_once, pauses again and returns "
             "(state, reward, terminated, False, {})", source="upstream_code",
             ref=f"{CARTPOLE}:143-171"),
        Fact("step loops on rclpy.spin_once(timeout_sec=SPIN_TIME_s) until latest_obs is set, with no limit "
             "on the number of iterations", source="upstream_code", ref=f"{CARTPOLE}:149-154"),
        Fact("process_obs prints a message when the angle or the position limit is exceeded",
             source="upstream_code", ref=f"{CARTPOLE}:192-200"),
        Fact("user_close destroys the ROS node and calls rclpy.shutdown() when rclpy.ok()",
             source="upstream_code", ref=f"{CARTPOLE}:220-223"),
        Fact("reset zeroes the velocity command, publishes it, calls _reset_agents, waits for "
             "an observation, pauses the simulation and returns (state, {})",
             source="upstream_code", ref=f"{CARTPOLE}:82-124"),
        Fact("reset accepts seed and options but does not use them; the returned state comes "
             "from the simulator's next /joint_states observation", source="upstream_code",
             ref=f"{CARTPOLE}:82-124"),
        Fact("The cartpole world physics has max_step_size 0.005 s, real_time_update_rate 200 "
             "and real_time_factor 1.0", source="upstream_code", ref=f"{WORLD}:6-9"),
        Fact("The package requires Python >=3.12.3 and depends on gymnasium>=1.3.0, "
             "torch>=2.12.0, tensorboard and numpy>=1.26.0", source="upstream_code",
             ref="pyproject.toml:8-14"),
        Fact("The README says sourcing ros2_ws/install/setup.bash is required to use the "
             "prebuilt environments", source="vendor_doc", ref="README.md:140-147"),
        Fact("LICENSE.md states that the project is released under the MIT License",
             source="vendor_doc", ref="LICENSE.md:1"),
        Fact("The cartpole_ros package.xml declares the licence 'TODO: License declaration'",
             source="upstream_code", ref="ros2_ws/src/cartpole_ros/package.xml:8"),
    ]
    safe_state = ("Software latch only: the runtime refuses every step and reset until mhs.safety.reset, the "
                  "last observation and tick stay readable, and the e-stop sends nothing to Gazebo. In a live "
                  "CartpoleEnv-v0 deployment each completed step or reset ends with a WorldControl pause "
                  "request whose reply is not inspected, so the world stays paused only if that request took "
                  "effect; a step or reset in flight keeps the world unpaused, waiting without a timeout, until "
                  "its next /joint_states sample arrives.")
    #: The model as deployed, the package's own event-driven stand-in (spec 05-fidelity FID-002):
    #: no Gazebo physics, no ROS 2 graph and no wall-clock pacing.  The upstream physics
    #: timestep is recorded as a Fact only; it is not the fake's timestep.
    fidelity = {
        "engine": "analytic:cartpole-env-v0-fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "the fake is a deterministic event-driven stand-in, but upstream reset accepts and ignores "
                     "seed/options and the Gazebo state comes from the simulator, so this package makes no replay "
                     "or seed-equality claim",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic stand-in, not the upstream simulator: it loads no Gazebo Harmonic, "
            "ros_gz_bridge, ROS 2 Jazzy, DART physics, cart-pole rigid bodies, joints, controllers, contacts or "
            "sensors, and it models no dynamics; the pole angle and angular velocity stay at their placeholder "
            "zero values",
            "one cap.world.step.v1 tick is one environment step; the fake has no simulated clock, and its cart "
            "position advances by a placeholder 0.01 s bookkeeping interval, not the world's 5 ms physics step or "
            "a measured /joint_states period",
            "the action effect copies the upstream velocity-command rule (0.2 per step) but the fake does not "
            "publish to /cart_velocity_controller/commands, subscribe to /joint_states, pause the world-control "
            "service or launch a simulator",
            "the upstream observation space bounds appear ordered for [theta, x, ...] while the returned state is "
            "[x, x_dot, theta, theta_dot]; the fake preserves the returned order and the declared space unchanged",
            "the fake's start state and its zero pole values are placeholders; the real starting pose comes from "
            "the Gazebo world and the reset plugin",
            "the upstream registered environment is wrapped with a 3000-step TimeLimit by gymnasium.make; the fake "
            "applies the same 3000-step truncation directly",
            "the sim backend calls gymnasium.make('CartpoleEnv-v0'), which needs the upstream package installed, a "
            "sourced ros2_ws, ROS 2 Jazzy and Gazebo Harmonic; that path was not run and was not compared with the "
            "fake",
            "fake-only contract: constructing the upstream CartpoleEnv inside the server process calls rclpy.init "
            "for the whole process, starts ros2 launch in a new session whose stdout and stderr are the server's "
            "stdout, sleeps 4 s and prints status lines, so an MHS server talking over stdio would receive that "
            "output; a live deployment needs an owned, isolated environment factory",
            "GazeboEnv.close runs pkill -f for 'gz sim', 'gz sim server' and 'gzsim gui' and pkill -9 -f for "
            "'ros_gz_bridge' and 'ros2 launch', which match every such process on the host, not only the ones "
            "this environment started; user_close calls rclpy.shutdown for the whole process",
            "upstream step and reset wait on rclpy.spin_once without an overall timeout until a /joint_states "
            "sample arrives, print a line whenever a limit is exceeded, and end with a WorldControl pause request "
            "(timeout argument 10, its unit set by gz-transport) whose reply is not inspected; the shipped launch "
            "starts the world running (-r) with a GUI whose WorldControl and KeyPublisher plugins let a user "
            "unpause the world or trigger the reset plugin",
            "an upstream reset returns the first /joint_states message processed after the reset request; the "
            "subscription keeps up to 10 messages and ResetSimPlugin teleports on a later PreUpdate, so the "
            "returned state may predate the teleport",
            "the upstream environment takes theta from JointState index 0 and x from index 1 without checking "
            "the joint names; the order comes from joint_state_broadcaster, outside the clone",
            "no snapshot or restore: CartpoleEnv exposes no get_state/set_state method",
            "no hardware is modelled and no hardware backend exists; the Gazebo simulation is the system of record",
        ],
    }
