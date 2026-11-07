"""OpenMHS driver for gh.lionlai1989/stalkerdronerl: the QuadcopterTrackingEnv simulation.

The card's static scan guessed a ROS helper because the repository is a ROS 2 + Gazebo
project.  The confirmed entry symbol is a Gymnasium environment
(``src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:50``), so this package uses
``GymnasiumDriver``: a Gymnasium environment does not become a ROS transport driver merely
because its repository also contains ROS nodes.  The ROS topics and services are internal
to the environment's Gazebo/navigator loop; the primary control interface is
``reset()`` / ``step(action)``.

The bridge derives ``cap.world.step.v1`` (``{ticks, action}``), ``cap.world.reset.v1`` and
``cap.world.seed.v1`` from the environment.  The action is the upstream four-element
normalized force/torque Box, and the observation is the upstream eleven-element normalized
Box.  The environment is simulated at R0: it has no hardware backend, no physical stop and
no operator-required limit.

The gate cannot import the upstream environment: it imports ``rclpy``, ``torch``,
``stable_baselines3`` and the clone's own ROS modules (train_sac.py:14-39), and package code
never imports or runs the clone.  The declared ``fake`` backend is therefore this package's
pure Python kinematic stand-in (fake.py), not an upstream simulator run, not a recording and
not a transcript.  It was never compared with the upstream Gazebo model or with a real ROS
graph; the fidelity gaps state that.  No hardware is attached.

Every Fact cites the clone at commit e34db1c6a4926d22b447aa1ef93e9bb0bad4793c.  This package
is model-authored and unreviewed: ``driver.lock.json`` keeps ``reviewed_by: null``.
"""

from mhs.driver import Fact, GymnasiumDriver

TRAIN = "src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py"
OBS_ACTION = "src/sdrl_rl_controller/sdrl_rl_controller/observation_state_action.py"
PARAMS = "src/sdrl_geometric_controller/sdrl_geometric_controller/quadcopter_params.py"
GZ_CLIENT = "src/sdrl_rl_controller/sdrl_rl_controller/gz_client.py"
TRAIN_LAUNCH = "src/sdrl_bringup/launch/train_sac_launch.py"


class StalkerDroneRL(GymnasiumDriver):
    device_id = "stalker-drone-rl"
    #: The clone contains no gym.register call; the training entry constructs the class
    #: directly (train_sac.py:795-801).  No registered Gymnasium id exists, so none is invented.
    #: The fake backend is the only backend; a sim backend would need an operator-built factory.
    env_id = None
    native = "sdrl_rl_controller.sdrl_rl_controller.train_sac:QuadcopterTrackingEnv"
    backends = {"fake": ".fake:FakeQuadcopterTrackingEnv"}
    display_name = "StalkerDroneRL QuadcopterTrackingEnv (ROS 2 + Gazebo simulation)"
    vendor = "lionlai1989"
    model = "QuadcopterTrackingEnv"
    tags = ["ros2", "gazebo", "quadcopter", "reinforcement-learning", "simulation", "gymnasium"]
    action_space_ref = f"{TRAIN}:152-156"
    facts = [
        Fact("StalkerDroneRL is a fully containerized ROS 2 + Gazebo project that simulates a quadcopter "
             "stalking a red ball with a Gymnasium and Stable Baselines3 deep reinforcement learning "
             "controller.", source="vendor_doc", ref="README.md:3-5"),
        Fact("The sdrl_rl_controller package implements the Gymnasium environment and trains the drone "
             "controller with Stable Baselines3.", source="vendor_doc", ref="README.md:62-63"),
        Fact("The project documentation says it simulates a drone in a physical environment using ROS 2 "
             "Humble and Gazebo Harmonic and that the deep RL framework is Gymnasium and Stable "
             "Baselines3.", source="vendor_doc", ref="docs/StalkerDroneRL.md:2-4"),
        Fact("QuadcopterTrackingEnv derives from gym.Env.", source="upstream_code", ref=f"{TRAIN}:50"),
        Fact("The QuadcopterTrackingEnv constructor defaults control_freq to 100, max_episode_steps to 2000 "
             "and use_sim_time to True, calls rclpy.init() when rclpy is not running and creates a node with "
             "that use_sim_time parameter.", source="upstream_code", ref=f"{TRAIN}:53-72"),
        Fact("The action space is a four-element gym.spaces.Box with low -1 and high 1 and dtype float32; "
             "the comment names the components fz, tx, ty and tz.", source="upstream_code",
             ref=f"{TRAIN}:151-156"),
        Fact("The observation space is an eleven-element gym.spaces.Box with low -1 and high 1 and dtype "
             "float32.", source="upstream_code", ref=f"{TRAIN}:158-165"),
        Fact("The environment subscribes to /X3/gt_odom, /X3/cmd_odom and /X3/navi_state, publishes motor "
             "speeds on /X3/ros/motor_speed and creates Trigger clients for /X3/reset_navigator and "
             "/X3/reset_dynamics.", source="upstream_code", ref=f"{TRAIN}:189-201"),
        Fact("The constant WORLD_NAME is ground_plane_world and QUADCOPTER_MODEL is lion_quadcopter, with "
             "MAX_POS_DIST 9.0 and MAX_VEL_DIST 5.0.", source="upstream_code", ref=f"{TRAIN}:41-47"),
        Fact("step converts the normalized action to motor speeds, publishes them, calls "
             "gz_client.world_control with step_multi=10 and no pause argument, waits for odometry stamped at "
             "least one control period after the step began, then computes the tracking error and reward.",
             source="upstream_code", ref=f"{TRAIN}:362-443"),
        Fact("_wait_for_odom polls the odometry stamp every 0.5 ms and, after 2 s of wall-clock time without "
             "a new enough stamp, logs a warning and returns normally.", source="upstream_code",
             ref=f"{TRAIN}:219-238"),
        Fact("gz_client.world_control sets the WorldControl pause field only when a pause argument is given, "
             "sets step and multi_step when step_multi is given, and raises RuntimeError when the request "
             "fails.", source="upstream_code", ref=f"{GZ_CLIENT}:37-47"),
        Fact("The step comments state that physics runs at 1000 Hz and control at 100 Hz and that ten "
             "physics steps are requested per environment step.", source="upstream_code",
             ref=f"{TRAIN}:389-393"),
        Fact("The reward configuration is base 0.2, position-distance penalty -0.0388, velocity-distance "
             "penalty -0.007, progress reward 1.0, danger-zone tilt pi/6, tilt penalty -0.5, success "
             "bonus 2.5 and crash penalty -10.0; the step reward range is documented as [-10, 10].",
             source="upstream_code", ref=f"{TRAIN}:105-115"),
        Fact("The reward adds the base term, the distance and velocity penalties, a progress term that is "
             "zero when the command position moved more than 0.5 since the last step, the tilt penalty above "
             "the danger-zone tilt and the success and crash terms, and clips the result to [-10, 10].",
             source="upstream_code", ref=f"{TRAIN}:240-278"),
        Fact("A step terminates only when the navigator state has been CRASHED for at least four "
             "consecutive steps, and truncates when step_count reaches max_steps.", source="upstream_code",
             ref=f"{TRAIN}:419-474"),
        Fact("step returns the normalized observation, reward, terminated, truncated and an info dict "
             "with success and crash.", source="upstream_code", ref=f"{TRAIN}:473-485"),
        Fact("reset accepts seed and options, calls super().reset(seed=seed), requests the drone reset, "
             "waits for fresh odometry, pauses physics and returns (observation, {}).", source="upstream_code",
             ref=f"{TRAIN}:487-544"),
        Fact("After the reset sequence, reset waits for fresh odometry on a 10 Hz node rate, measures its "
             "5 s timeout with the node clock and raises RuntimeError when it expires.",
             source="upstream_code", ref=f"{TRAIN}:514-530"),
        Fact("The reset sequence pauses physics, calls the navigator reset service, publishes zero motor "
             "speeds five times, teleports the drone to random x and y with z=0.05, calls the dynamics "
             "reset service and unpauses physics.", source="upstream_code", ref=f"{TRAIN}:546-614"),
        Fact("The reset comment records that the drone is still moving slightly after being put back at "
             "the initial position and that residual velocity may need a second reset.", source="upstream_code",
             ref=f"{TRAIN}:574-576"),
        Fact("close shuts down rclpy when it is running, joins the spin thread and destroys the node.",
             source="upstream_code", ref=f"{TRAIN}:620-625"),
        Fact("The training entry refuses n_envs other than 1 because the ROS 2/Gazebo simulation exposes a "
             "single physical drone instance, and it constructs QuadcopterTrackingEnv directly rather than "
             "through gym.make.", source="upstream_code", ref=f"{TRAIN}:771-806"),
        Fact("The normalized observation is eleven float32 values: body-frame position error, body-frame "
             "velocity error, roll, pitch and body rates p, q and r.", source="upstream_code",
             ref=f"{OBS_ACTION}:25-130"),
        Fact("The observation normalization constants are MAX_POS_ERR 5.0, MAX_VEL_ERR 3.0 and "
             "MAX_ANG_VEL 6.28.", source="upstream_code", ref=f"{OBS_ACTION}:20-22"),
        Fact("action_to_wrench accepts only an action with shape (4,) and values in [-1, 1], treats "
             "action[0] as normalized force z and action[1:4] as normalized torques x, y and z, and maps "
             "them through the wrench limits.", source="upstream_code", ref=f"{OBS_ACTION}:133-162"),
        Fact("QuadcopterParams defines a 1.5 kg mass and the diagonal inertia [0.0347563, 0.07, 0.0977].",
             source="upstream_code", ref=f"{PARAMS}:14-16"),
        Fact("QuadcopterParams sets hover_thrust to mass * GRAVITY * 1.1.", source="upstream_code",
             ref=f"{PARAMS}:86"),
        Fact("The project documentation notes that Gazebo shows a large initial velocity after the reset "
             "that looks like left-over velocity from the previous episode.",
             source="vendor_doc", ref="docs/StalkerDroneRL.md:46-54"),
        Fact("The training launch file starts Gazebo with gz sim -r, with the GUI or headless (-s).",
             source="upstream_code", ref=f"{TRAIN_LAUNCH}:94-105"),
    ]
    safe_state = ("Software latch only: the runtime refuses every step, reset and seed until mhs.safety.reset, "
                  "so the in-process fake stops advancing and its last observation and tick stay readable; a "
                  "live Gazebo world, which this package never drives, is not paused by the latch, and nothing "
                  "zeroes the motor speeds last published on /X3/ros/motor_speed.")
    fidelity = {
        "engine": "analytic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake draws its placeholder start and target from a per-instance random.Random "
                     "seeded by reset(seed), so one seed and one action sequence repeat in this package; "
                     "the upstream reset also calls super().reset(seed=seed) but draws its x/y jitter from "
                     "the global numpy generator (train_sac.py:582-584), and its documented residual "
                     "velocity is not modelled, so upstream determinism is not claimed or compared",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a pure Python point-mass and attitude stand-in: it loads no Gazebo, ROS 2, "
            "quadcopter SDF, motor mixer, physics engine, contacts, sensors or navigator state machine, and "
            "was never compared with the upstream simulator",
            "the upstream environment imports rclpy, torch, stable_baselines3 and clone modules "
            "(train_sac.py:14-39) and is never imported or run by this package; the fake only mirrors the "
            "Gymnasium methods reset, step and close and the two spaces",
            "the action is interpreted directly as a vertical force and three torques; the upstream path "
            "goes through action_to_wrench, wrench_to_motor_speeds and Gazebo motor models, so the fake's "
            "trajectories and motor commands are not the upstream ones",
            "the observation is a world-frame approximation of the upstream body-frame tracking error; the "
            "eleven-value layout and [-1, 1] bounds match, the values do not",
            "the target position is a local placeholder; upstream the command pose and twist arrive on "
            "/X3/cmd_odom from the navigator and the red-ball tracker",
            "the reward terms are copied from the upstream configuration but applied to the fake state; "
            "crash uses a local four-consecutive-step z<=0 or tilt>pi/4 test instead of the upstream "
            "/X3/navi_state CRASHED count, and success uses the initial 2.5 m curriculum radius rather than "
            "the moving curriculum",
            "reset zeroes velocity and teleports inside the fake; upstream pauses Gazebo, calls "
            "/X3/reset_navigator and /X3/reset_dynamics, publishes zero motor speeds five times, teleports "
            "with gz_client.set_pose and unpauses, and the clone documents residual velocity after reset "
            "(train_sac.py:574-576, docs/StalkerDroneRL.md:46-54)",
            "one environment instance is served; upstream forbids n_envs other than 1 because one Gazebo "
            "drone is shared by all environments (train_sac.py:771-779)",
            "there is no wall-clock pacing: realtime_factor 0 and only cap.world.step.v1 advances time; "
            "one tick is one 10 ms control step, the upstream ten 1 kHz physics steps are not simulated",
            "snapshot and restore are not offered because QuadcopterTrackingEnv defines no get_state or "
            "set_state method",
            "seeded repeats are a property of the fake only: upstream reset(seed) seeds self.np_random through "
            "super().reset, but the start x and y come from the global numpy generator (train_sac.py:582-584) "
            "and the target from the navigator and ball mover, so the seed test cases are fake-only",
            "upstream step swallows a missing observation: _wait_for_odom returns after 2 s of wall-clock time "
            "with only a warning (train_sac.py:219-238), and step then computes reward and observation from "
            "stale odometry and reports a normal step",
            "a live world is not lockstep by construction: the training launch starts Gazebo running "
            "(train_sac_launch.py:94-105), and step requests ten iterations with a WorldControl message whose "
            "pause field it never sets (gz_client.py:37-47, train_sac.py:393), so whether Gazebo stays paused "
            "between steps depends on gz-sim, outside the clone; the latch refuses steps but pauses nothing",
            "the stock constructor is unsafe inside the server process: it calls the global rclpy.init and "
            "starts a daemon rclpy.spin thread, importing gz_client creates a gz-transport node at import, "
            "reset waits up to 5 s for each Trigger service and then for odometry with a timeout measured on "
            "the node clock, which is simulated time by default and never elapses while /clock is silent, and "
            "close() calls the global rclpy.shutdown and joins the spin thread without a timeout; no sim "
            "backend is declared, a live deployment needs an owned, isolated factory",
            "in a live graph the navigator publishes its own /X3/ros/motor_speed commands at 100 Hz unless it "
            "runs in control_mode rl_train (navigator.py:241-243, 303-320, 590-607), which would compete with "
            "every step's motor command",
        ],
    }
