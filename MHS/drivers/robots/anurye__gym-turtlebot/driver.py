"""OpenMHS driver for the TurtleBot4 Gymnasium environment (gh.anurye/gym-turtlebot).

DEVIATION FROM THE CARD: the task card names ``helper: RosDriver`` with reason
``family:ros``, but the pinned entry symbol is a Gymnasium environment whose
primary interface is ``reset``/``step``; the ROS 2 nodes and Gazebo services
are internals that the upstream environment constructs itself.  A rosbridge
transport cannot express the environment step, so this package uses the
SDK's configuration-only ``GymnasiumDriver`` and serves
``cap.world.step.v1`` / ``cap.world.reset.v1`` / ``cap.world.seed.v1``.

The real environment needs ROS 2 Jazzy and Gazebo Harmonic and is never
imported by the gate.  The package backend is a ROS-free analytic fake in
``fake.py``; its observations are placeholders and its fidelity is F0.  Every
fact and the derived action-space reference cite the pinned clone at
c1e8b72a1081b92821dc14320fc7105b10423c54.
"""

from mhs.driver import Fact, GymnasiumDriver

_ACTION = "src/tb4_drl_navigation/tb4_drl_navigation/envs/diffdrive/turtlebot4.py"


class GymTurtlebot(GymnasiumDriver):
    """The registered Turtlebot4Env-v0, served through the Gymnasium bridge."""

    device_id = "gym-turtlebot"
    device_kind = "world.sim"
    mode = "simulated"
    # R2, not R0 (grok-4.7, 2026-11-05; REVIEW.md item 12): Turtlebot4Env.step
    # publishes geometry_msgs/TwistStamped on /cmd_vel (ros_gz.py:135-139, 160-165;
    # turtlebot4.py:331-346). docs/Tutorial.md:34 says a differential-drive robot can be
    # used directly when its topics are scan, odom and cmd_vel. No fact cites that only
    # the simulator consumes /cmd_vel. A mobile base is R2 however simulated the
    # deployment. The latch does not publish a zero Twist and does not stop a base on
    # that topic.
    risk = "R2"
    env_id = "Turtlebot4Env-v0"
    native = "tb4_drl_navigation.envs.diffdrive.turtlebot4:Turtlebot4Env"
    backends = {"fake": ".fake:FakeTurtlebot4Env"}
    tags = ["gymnasium", "simulation", "ros2", "gazebo", "turtlebot4", "navigation", "reinforcement-learning"]
    display_name = "TurtleBot4 Gymnasium environment"
    vendor = "anurye"

    # The fake copies the upstream action space exactly; the bridge derives
    # the cap.world.step.v1 per-element bounds from it.
    action_space_ref = f"{_ACTION}:187-191"

    facts = [
        Fact(
            "The package registers Gymnasium environment Turtlebot4Env-v0 with entry point "
            "tb4_drl_navigation.envs.diffdrive.turtlebot4:Turtlebot4Env and max_episode_steps=500.",
            source="upstream_code",
            ref="src/tb4_drl_navigation/tb4_drl_navigation/envs/__init__.py:3-7",
        ),
        Fact(
            "Turtlebot4Env defines a two-element float32 Box action space with low [0.0, -1.0] and high [1.0, 1.0].",
            source="upstream_code",
            ref=f"{_ACTION}:187-191",
        ),
        Fact(
            "Turtlebot4Env defines a Dict observation space with min_ranges and min_ranges_angle shaped by "
            "num_bins and bounded by the scan range and angle, dist_to_goal bounded 0.0 to 100.0, "
            "orient_to_goal bounded -pi to pi, and the last action copied from the action space.",
            source="upstream_code",
            ref=f"{_ACTION}:219-234",
        ),
        Fact(
            "step stores the action, converts action[0] to the linear.x twist component and action[1] to "
            "angular.z, publishes the twist through Publisher, and propagates the state for time_delta seconds.",
            source="upstream_code",
            ref=f"{_ACTION}:331-346",
        ),
        Fact(
            "Sensors creates a sensor_msgs/LaserScan subscription on /scan and a nav_msgs/Odometry subscription "
            "on /odometry/filtered.",
            source="upstream_code",
            ref="src/tb4_drl_navigation/tb4_drl_navigation/envs/utils/ros_gz.py:57-70",
        ),
        Fact(
            "Publisher creates a TwistStamped publisher on /cmd_vel with queue depth 10.",
            source="upstream_code",
            ref="src/tb4_drl_navigation/tb4_drl_navigation/envs/utils/ros_gz.py:135-139",
        ),
        Fact(
            "pub_cmd_vel stamps the TwistStamped with the node clock and the configured base frame and publishes it.",
            source="upstream_code",
            ref="src/tb4_drl_navigation/tb4_drl_navigation/envs/utils/ros_gz.py:160-165",
        ),
        Fact(
            "reset passes seed to Gymnasium's super().reset(seed=seed), calls SimulationControl.reset_world(), "
            "zeroes the last action and republishes it, and reads start_pos/goal_pos from options.",
            source="upstream_code",
            ref=f"{_ACTION}:375-394",
        ),
        Fact(
            "SimulationControl creates a ControlWorld service client on /world/<world_name>/control.",
            source="upstream_code",
            ref="src/tb4_drl_navigation/tb4_drl_navigation/envs/utils/ros_gz.py:400-403",
        ),
        Fact(
            "SimulationControl.reset_world requests a ControlWorld reset with model_only=True, and pause_unpause "
            "sets world_control.pause to the requested value.",
            source="upstream_code",
            ref="src/tb4_drl_navigation/tb4_drl_navigation/envs/utils/ros_gz.py:423-441",
        ),
        Fact(
            "_propagate_state unpauses the world, spins the executor until time_delta elapses, pauses the world, "
            "and then reads the observation from the sensors.",
            source="upstream_code",
            ref=f"{_ACTION}:446-456",
        ),
        Fact(
            "ScenarioGenerator is constructed with seed=None.",
            source="upstream_code",
            ref=f"{_ACTION}:178-185",
        ),
        Fact(
            "When reset options omit start_pos and goal_pos, the start and goal yaws are drawn from "
            "np.random.uniform(-pi, pi), not from the seeded Gymnasium RNG.",
            source="upstream_code",
            ref=f"{_ACTION}:392-404",
        ),
        Fact(
            "The environment terminates when dist_to_goal < goal_threshold or min(min_ranges) < "
            "collision_threshold.",
            source="upstream_code",
            ref=f"{_ACTION}:495-503",
        ),
        Fact(
            "README states that Gazebo Sim does not support model reset and that the robot's odometry and pose "
            "are reset with the SetPose and SetEntityPose services.",
            source="vendor_doc",
            ref="README.md:89-91",
        ),
        Fact(
            "The tutorial says num_bins creates 30 bins by default and can be as high as len(ranges).",
            source="vendor_doc",
            ref="docs/Tutorial.md:42-43",
        ),
    ]

    safe_state = (
        "The simulated environment is held at its last observation: the runtime refuses further world steps "
        "until an operator reset. The latch does not publish a zero Twist on /cmd_vel and does not stop a "
        "mobile base subscribed to that topic."
    )

    # Describes the deployed analytic fake, not the upstream ROS 2/Gazebo timing.
    fidelity = {
        "engine": "analytic:analytic fake (no ROS 2, Gazebo or physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "reset_required",
            "notes": (
                "The analytic fake stores the reset seed and returns fixed placeholder observations; the "
                "seed does not reproduce the upstream ROS 2/Gazebo scenario."
            ),
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free analytic stand-in: it creates no ROS 2 nodes and never contacts /scan, "
            "/odometry/filtered, /cmd_vel or the Gazebo /world/<world_name>/control service",
            "all observation values, rewards and terminal flags are placeholders; the fake applies no "
            "TurtleBot4 dynamics, contacts, lidar, odometry or reward logic",
            "the fake reports 30 lidar bins, the upstream constructor default (docs/Tutorial.md:42); the live "
            "length is the LaserScan ranges length and num_bins is clamped to it (turtlebot4.py:260), so the "
            "real observation array size is not fixed by the clone",
            "the action space is copied from the upstream environment (turtlebot4.py:187-191); the fake does "
            "not publish a TwistStamped on /cmd_vel and does not advance Gazebo for time_delta",
            "the upstream reset samples the scenario with ScenarioGenerator(seed=None) and np.random.uniform; "
            "the fake's seed only selects its placeholder distance",
            "the registered max_episode_steps=500 TimeLimit wrapper is not applied to the fake; only the "
            "bridge's ticks and max_steps bounds apply",
            "rendering, observation images, TF, snapshots and the full LaserScan array are NOT COVERED",
        ],
    }
