"""OpenMHS driver for gh.saqib736/ros2-reinforcement-learning: the RacingBotEnv-v0 Gymnasium environment.

The card classifies this repository as a ROS package, but the concrete entry is a Gymnasium
environment: ``RacingBotEnv-v0`` is registered with entry point ``rl_racing.gazebo_env:GazeboEnv``
(start_learning.py:36-40).  ``GazeboEnv`` inherits ``gazebo_connections.GazeboConnection`` (a
``rclpy`` node) and ``gymnasium.Env``; its public contract is ``reset()``/``step()``, not a ROS
topic or service (gazebo_env.py:11,44-81).  This package therefore uses ``GymnasiumDriver``
instead of the card's ``RosDriver`` (DEVIATION FROM THE CARD in RESULT.json).  The ROS topics
behind the environment are internal to the simulator adapter and are recorded as source facts,
not exposed as a separate transport driver.

The bridge derives ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` from
the environment's spaces.  The action space is the upstream ``Box([-1, -1], [1, 1])``
(gazebo_env.py:25-27); the observation space is ``Box(0, 1, shape=(60,))`` (gazebo_env.py:29).
The served step publishes geometry_msgs/Twist on /cmd_vel (gazebo_env.py:95-103,
gazebo_connections.py:36-39 and 47-51). The model SDF's diff-drive plugin consumes cmd_vel
(td_robot.sdf:727-750) and does not say that only Gazebo does, so the device risk is R2
(REVIEW.md item 12), a mobile base, however simulated the deployment. There is no hardware
backend, no physical e-stop and no operator-required limit.

The gate cannot open the upstream environment: it imports ``rclpy``, ``numpy`` and
``gymnasium`` (gazebo_env.py:3-7), and the clone is never imported or run by package code.  The
checked ``fake`` backend is this package's own pure Python analytic stand-in (fake.py).  It
reproduces the upstream action-to-velocity conversion, the observation scaling, the crash test
and the reward terms, but it is not the Gazebo simulator and no Gazebo, ROS or hardware run was
made.

Every Fact cites the pinned clone at c17f9055076f72d91be6a628a2a5db084dacd7d1.  The package is
model-authored and unreviewed: ``driver.lock.json`` keeps ``reviewed_by: null``.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "rl_racing/rl_racing/gazebo_env.py"
CONNECTIONS = "rl_racing/rl_racing/gazebo_connections.py"
START_LEARNING = "rl_racing/rl_racing/start_learning.py"
URDF = "sim_package/urdf/td_robot.urdf"
WORLD = "sim_package/worlds/racing_track.world"
MODEL_SDF = "sim_package/models/td_robot/td_robot.sdf"


class RacingBotEnv(GymnasiumDriver):
    # R2, not the inherited R0 (grok-4.7, 2026-11-05; REVIEW.md item 12):
    # GazeboEnv.step calls _set_action, which publishes geometry_msgs/Twist linear.x and
    # angular.z on /cmd_vel (gazebo_env.py:44-47, 95-103; gazebo_connections.py:36-39,
    # 47-51). td_robot.sdf:727-750 points libgazebo_ros_diff_drive at command_topic
    # cmd_vel and does not say that only that plugin consumes it. A mobile base is R2
    # however simulated the deployment. The latch does not publish a zero Twist.
    risk = "R2"
    device_id = "racingbot-env"
    env_id = "RacingBotEnv-v0"
    native = "rl_racing.gazebo_env:GazeboEnv"
    backends = {"fake": ".fake:FakeGazeboEnv"}
    action_space_ref = f"{ENV}:25-27"
    display_name = "RacingBotEnv-v0 (ROS 2 Gazebo racing simulation)"
    vendor = "saqib736"
    model = "RacingBotEnv-v0"
    tags = [
        "ros2",
        "gazebo",
        "reinforcement-learning",
        "gymnasium",
        "racing",
        "simulation",
        "laser",
        "pioneer3dx",
    ]
    facts = [
        Fact("This project demonstrates reinforcement learning for robotic tasks using ROS 2 Humble, "
             "Gazebo, Stable-Baselines3 and Gymnasium.", source="vendor_doc", ref="README.md:3"),
        Fact("start_learning registers RacingBotEnv-v0 with entry point rl_racing.gazebo_env:GazeboEnv and "
             "max_episode_steps=1000.", source="upstream_code", ref=f"{START_LEARNING}:36-40"),
        Fact("GazeboEnv subclasses GazeboConnection (from rl_racing.gazebo_connections) and gymnasium's Env.",
             source="upstream_code", ref=f"{ENV}:5-11"),
        Fact("GazeboConnection subclasses rclpy's Node, and its constructor creates the node gazebo_connection.",
             source="upstream_code", ref=f"{CONNECTIONS}:6-32"),
        Fact("The action space is Box(low=[-1, -1], high=[1, 1], dtype=float32).",
             source="upstream_code", ref=f"{ENV}:25-27"),
        Fact("The observation space is Box(low=0, high=1, shape=(60,), dtype=float32).",
             source="upstream_code", ref=f"{ENV}:29"),
        Fact("The environment sets max_linear_vel=1.0, min_linear_vel=0.0, angular_vel=1.0 and "
             "min_obstacle_dist=0.2.", source="upstream_code", ref=f"{ENV}:20-23"),
        Fact("seed() creates a generator with gymnasium.utils.seeding.np_random and returns [seed].",
             source="upstream_code", ref=f"{ENV}:34-36"),
        Fact("spin() clears done_laser_ and done_odom_ and calls rclpy.spin_once(self) in a loop, with no "
             "deadline, until both flags are set.", source="upstream_code", ref=f"{ENV}:38-42"),
        Fact("step() applies the action, spins, reads the observation, evaluates done, computes the reward "
             "and returns (obs, reward, done, False, {}).", source="upstream_code", ref=f"{ENV}:44-60"),
        Fact("reset() optionally seeds, calls resetSim(), updates the episode, spins, reads the observation, "
             "clears last_action and returns (obs, {}).", source="upstream_code", ref=f"{ENV}:62-81"),
        Fact("_set_action computes the linear velocity (max_linear_vel * (action[0] + 1) + min_linear_vel * "
             "(1 - action[0])) / 2 and the angular velocity (angular_vel * (action[1] + 1) - angular_vel * "
             "(1 - action[1])) / 2, then calls publish_velocity.",
             source="upstream_code", ref=f"{ENV}:95-103"),
        Fact("_get_obs returns the laser scan divided by 10.", source="upstream_code", ref=f"{ENV}:105-110"),
        Fact("_is_done is true when any laser distance is below min_obstacle_dist.",
             source="upstream_code", ref=f"{ENV}:112-119"),
        Fact("The reward is 5 * get_current_linear_vel(), plus -(min_obstacle_dist - min(obs)) when the minimum "
             "of the scaled observation is below min_obstacle_dist, minus 20 when done, plus 0.1, and minus 2 "
             "when the action equals last_action.",
             source="upstream_code", ref=f"{ENV}:121-145"),
        Fact("GazeboConnection publishes geometry_msgs/Twist on /cmd_vel and subscribes to nav_msgs/Odometry "
             "on /odom and sensor_msgs/LaserScan on /front_laser/scan.",
             source="upstream_code", ref=f"{CONNECTIONS}:36-39"),
        Fact("publish_velocity puts velocity[0] in linear.x and velocity[1] in angular.z.",
             source="upstream_code", ref=f"{CONNECTIONS}:47-51"),
        Fact("laser_callback copies msg.ranges into a numpy array and replaces infinite readings with 10.",
             source="upstream_code", ref=f"{CONNECTIONS}:53-56"),
        Fact("odom_callback stores msg.twist.twist.linear.x as the current linear velocity.",
             source="upstream_code", ref=f"{CONNECTIONS}:61-66"),
        Fact("resetSim repeats wait_for_service(max_retry_) until /reset_simulation is available, sends an "
             "Empty request, waits with rclpy.spin_until_future_complete without a timeout and sets "
             "resetSim_done_ when the future has a result.", source="upstream_code",
             ref=f"{CONNECTIONS}:68-88"),
        Fact("The GazeboConnection docstring lists /reset_simulation, /reset_world, /pause_physics and "
             "/unpause_physics under 'Services not used'.", source="upstream_code", ref=f"{CONNECTIONS}:24-28"),
        Fact("The documented simulation launch is ros2 launch sim_package start_simulation.launch.py.",
             source="vendor_doc", ref="README.md:78"),
        Fact("The documented training launch is ros2 launch rl_racing start_training.launch.py.",
             source="vendor_doc", ref="README.md:88"),
        Fact("The package declares rclpy, geometry_msgs, sensor_msgs, nav_msgs, std_srvs, gymnasium, numpy "
             "and stable_baselines3 dependencies.", source="upstream_code", ref="rl_racing/package.xml:10-25"),
        Fact("The URDF attaches a front_laser link to the chassis at x=0.125, z=0.25.",
             source="upstream_code", ref=f"{URDF}:383-388"),
        Fact("The racing_track world includes model://td_robot at pose 0 5 0.01.",
             source="upstream_code", ref=f"{WORLD}:31-35"),
        Fact("The td_robot model's laser sensor has 60 horizontal samples from -1.5708 to 1.5708, a range of "
             "0.1 to 10 and an update rate of 100, and its libgazebo_ros_ray_sensor plugin remaps its output to "
             "/front_laser/scan as sensor_msgs/LaserScan.", source="upstream_code", ref=f"{MODEL_SDF}:340-366"),
        Fact("The td_robot model's libgazebo_ros_diff_drive plugin uses command_topic cmd_vel and "
             "odometry_topic odom with max_wheel_torque 20, max_wheel_acceleration 1.8 and update_rate 50.",
             source="upstream_code", ref=f"{MODEL_SDF}:727-750"),
    ]
    safe_state = (
        "Software latch only: after an e-stop the bridge refuses step and reset until mhs.safety.reset clears "
        "the latch, and the fake's state is kept and stays readable. Nothing is sent to the environment: a "
        "live Gazebo is free-running and would keep simulating with the last /cmd_vel Twist in place, because "
        "the upstream publishes velocity only from step and calls no pause service. The latch does not "
        "publish a zero Twist, so a physical base subscribed to /cmd_vel is not stopped."
    )
    #: Fidelity contract of the checked fake backend (spec 05-fidelity).  The fake is an analytic
    #: kinematic stand-in, not the Gazebo simulator.
    fidelity = {
        "engine": "analytic:kinematic scan stand-in (no Gazebo physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": (
                "this package's fake is deterministic for a given seed and action sequence: the seed "
                "selects the placeholder starting clearance.  The upstream reset(seed) only creates "
                "np_random (gazebo_env.py:34-36) and no code consumes that generator, so it does not seed "
                "the Gazebo world; the two implementations do not produce the same trajectory"
            ),
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the checked fake is a pure Python kinematic stand-in for Gazebo: it models no rigid-body "
            "physics, contacts, wheels, motor, laser ray casting, odometry, sensor noise or rendering; its "
            "60-beam scan is a placeholder profile around one scalar clearance and was never compared "
            "with a Gazebo run",
            "the world includes model://td_robot (sim_package/worlds/racing_track.world:31-35), whose SDF "
            "carries the 60-sample, 0.1 to 10 laser that publishes /front_laser/scan and the diff-drive plugin "
            "on cmd_vel and odom (sim_package/models/td_robot/td_robot.sdf:340-366, 727-750); the URDF has "
            "only the front_laser link; the fake models neither plugin",
            "the fake has no physical timestep or wall-clock pacing: fidelity.timestep_ms is 0 and a "
            "cap.world.step.v1 tick is one fake control transition, not one Gazebo physics step",
            "the upstream reset calls the /reset_simulation service and spin() waits for both a laser and "
            "an odometry message (gazebo_env.py:38-42,62-72); the fake returns immediately, does not use "
            "ROS and does not prove that a Gazebo reset completed",
            "the upstream step publishes a Twist and waits for one laser and one odometry message; the "
            "fake instead applies its own placeholder clearance update, so its trajectories are not "
            "comparable with the upstream simulator",
            "the upstream observation space declares 60 beams and the model's laser has 60 samples and a "
            "10 maximum range; the fake always returns 60 placeholder values and does not model readings "
            "below the 0.1 minimum range",
            "the upstream is not lockstep: Gazebo runs freely between steps, and a step publishes one Twist "
            "and then waits, with no deadline, for the next laser and odometry messages (gazebo_env.py:38-60); "
            "a paused or silent simulator blocks it, and reset waits without a timeout for /reset_simulation "
            "(gazebo_connections.py:68-82)",
            "constructing the upstream environment needs a prior global rclpy.init() and creates the node "
            "gazebo_connection; close() destroys that node and never calls rclpy.shutdown; RacingBotEnv-v0 is "
            "registered only inside start_learning.main with max_episode_steps=1000, so gymnasium.make in the "
            "server finds no such environment, and a registered one would be truncated after 1000 steps, "
            "which the fake does not do",
            "the upstream progress reward reads the odometry linear velocity (gazebo_connections.py:61-66); the "
            "fake has no odometry and uses the commanded linear velocity instead",
            "the upstream safety penalty compares the observation scaled by 1/10 with min_obstacle_dist 0.2, "
            "which the crash test applies to unscaled ranges, so the penalty starts at ten times the crash "
            "distance; the fake copies this as written",
            "the README's documented training launch (start_training.launch.py) runs the upstream TD3 trainer, "
            "which builds its own environment and publishes /cmd_vel itself; it must not run beside an MHS "
            "deployment of this environment",
            "no live ROS 2 or Gazebo backend was run and no hardware is declared; the package only serves "
            "the fake backend, and the upstream environment needs ROS 2 Humble, Gazebo and the robot model",
        ],
    }
