"""OpenMHS driver for gh.jackvice/roboterrain: the RoverEnv Gazebo/Gymnasium environment.

DEVIATION FROM THE CARD: the card lists the ROS family and ``RosDriver``,
but its entry symbols are Gymnasium environments, not rosbridge endpoints.
``sb3.environments.rover_env:RoverEnv`` builds a ROS 2 node with ``rclpy``,
subscribes to Gazebo sensor topics and publishes a ``geometry_msgs/Twist``
on ``/cmd_vel``; the simulator itself is Gazebo Fortress.  The SDK's
``GymnasiumDriver`` matches that runtime and preserves the environment's
primary reset/step interface, so this package uses it instead of a transport
driver.  The package names ``RoverEnv`` (rover_env.py:68) as its upstream
class; the card's other entries are separate environments and are not served.

The acceptance gate cannot import the upstream environment: it needs ROS 2
Humble, Gazebo Fortress, ``rclpy``, ``cv_bridge``, ``transforms3d`` and the
rest of the upstream dependency set.  The ``fake`` backend is therefore a
ROS-free kinematic stand-in in fake.py; it copies the upstream action and
observation spaces and implements only the public Gymnasium surface.
``fidelity`` describes that deployed fake, not the upstream Gazebo defaults.

Every source fact cites the pinned clone at
e56a6642b21746f1c5897b9515ef7ac7d258a550.  The package was checked on the
fake backend only; no ROS graph, Gazebo simulator or hardware was contacted.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "ros2_ws/src/sb3/environments/rover_env.py"


class RoboTerrainRover(GymnasiumDriver):
    device_id = "roboterrain-rover"
    device_kind = "world.sim"
    mode = "simulated"
    # R2, not R0 (grok-4.7, 2026-11-05; REVIEW.md item 12): RoverEnv publishes
    # geometry_msgs/Twist on cmd_vel_topic, default /cmd_vel (rover_env.py:257-265), and
    # step sets linear.x and angular.z from the action (rover_env.py:393-406). The
    # connection check only waits for a LaserScan (rover_env.py:808-816) and, when none
    # arrives, logs "No actual robot detected" and still creates the publisher. README.md:14
    # models the Rover Zero, Clearpath Husky and Leo Rover. No fact cites that only the
    # simulator consumes /cmd_vel. A mobile base is R2 however simulated the deployment.
    risk = "R2"
    native = "sb3.environments.rover_env:RoverEnv"
    backends = {"fake": ".fake:FakeRoverEnv"}
    #: The fake copies the upstream Box([-1.0, -pi], [1.0, pi]) space.
    action_space_ref = f"{ENV}:215-219"
    display_name = "RoboTerrain RoverEnv (Gazebo Fortress point navigation)"
    vendor, model = "jackvice", "RoboTerrain"
    tags = ["ros2", "gazebo", "rover", "point-navigation", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The repository integrates ROS 2 Humble, Gazebo Fortress, PyTorch and Stable Baselines3 with a "
             "Gymnasium interface, and simulates the Rover Zero, Clearpath Husky and Leo Rover platforms.",
             source="vendor_doc", ref="README.md:14"),
        Fact("The README launches the Rover Zero simulation with ros2 launch roverrobotics_gazebo "
             "4wd_rover_gazebo.launch.py.", source="vendor_doc", ref="README.md:82-83"),
        Fact("RoverEnv is a gym.Env subclass documented as a custom environment that follows the Gymnasium "
             "interface.", source="upstream_code", ref=f"{ENV}:68-69"),
        Fact("The RoverEnv constructor defaults length to 2000, scan_topic to /scan, imu_topic to /imu/data, "
             "cmd_vel_topic to /cmd_vel, world_n to inspect, lidar_points to 32 and max_lidar_range to 12.0; these "
             "are constructor defaults, not device limits.", source="upstream_code", ref=f"{ENV}:71-73"),
        Fact("RoverEnv publishes geometry_msgs/Twist on cmd_vel and subscribes to LaserScan on scan_topic, Imu on "
             "imu_topic, PoseArray on /rover/pose_array and Odometry on /odometry/wheels.",
             source="upstream_code", ref=f"{ENV}:262-299"),
        Fact("The action space is a Box with low [-1.0, -pi] and high [1.0, pi], one speed and one relative "
             "heading value.", source="upstream_code", ref=f"{ENV}:215-219"),
        Fact("The observation space is a Dict of lidar (32 values from 0 to 12.0), pose (3 values), imu (3 angle "
             "values from -pi to pi), target (distance 0 to 100 and angle) and velocities (2 values).",
             source="upstream_code", ref=f"{ENV}:226-255"),
        Fact("step reads action[0] as speed and action[1] as a relative heading command, adds it to current_yaw, "
             "passes the result through heading_controller, and publishes linear.x = speed and angular.z = the "
             "controller output.", source="upstream_code", ref=f"{ENV}:393-406"),
        Fact("The constructor sets max_angular_velocity to "
             "7.0.", source="upstream_code", ref=f"{ENV}:128"),
        Fact("heading_controller returns np.clip(control, -self.max_angular_velocity, "
             "self.max_angular_velocity).", source="upstream_code", ref=f"{ENV}:330"),
        Fact("step increments _step, sets done when _step >= _length, and returns (observation, reward, done, "
             "False, info).", source="upstream_code", ref=f"{ENV}:412-443"),
        Fact("get_observation returns the lidar data, rover position, pitch/roll/yaw, target distance and "
             "relative angle, and linear/angular velocities.", source="upstream_code", ref=f"{ENV}:446-455"),
        Fact("reset calls super().reset(seed=seed), draws the start position and target with the module-level "
             "numpy random generator, sends an ign service set_pose command through subprocess, spins the node "
             "100 times, sleeps for 1.0 s and returns (observation, {}).", source="upstream_code",
             ref=f"{ENV}:599-683"),
        Fact("close destroys the ROS node and shuts down rclpy.", source="upstream_code", ref=f"{ENV}:691-694"),
    ]
    safe_state = ("For the declared analytic fake, the software latch fences subsequent step/reset calls. "
                  "It does not pause Gazebo, does not publish a zero Twist on /cmd_vel, and does not stop a "
                  "mobile base subscribed to that topic.")
    fidelity_level = "F0"
    #: The deployed fake is a ROS-free kinematic stand-in: no Gazebo physics,
    #: ROS graph, timestep or wall-clock pacing.
    fidelity = {
        "engine": "analytic:ROS-free kinematic stand-in for Gazebo Fortress",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake's reset(seed=...) creates a local random.Random and its step rule is deterministic; "
                     "the upstream reset calls super().reset(seed=seed) but draws the start pose and target from "
                     "the module-level numpy generator, so the same seed is not known to repeat an upstream run",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free kinematic stand-in: it runs no rclpy node, ROS 2 graph, Gazebo Fortress "
            "physics, contacts, sensors, plugins or wall-clock loop, and no ign service reset",
            "the upstream reset waits for 100 spin_once calls and time.sleep(1.0) after its ign service request; "
            "the fake resets immediately, so it does not model that latency",
            "the upstream step waits for a fresh LaserScan while the fake applies its placeholder kinematic "
            "displacement immediately; one tick is one control transition with timestep_ms 0, not a physics step",
            "the lidar array is a fixed 32-value placeholder; the real length is the constructor's lidar_points "
            "default of 32 and is configurable, and the upstream callback downsamples a LaserScan",
            "the fake's reward is a simple progress term and its done flag only counts steps; it does not model "
            "the upstream collision, flip, stuck, out-of-bounds and goal logic in task_reward()",
            "the fake's start pose, target, lidar reading and per-tick displacement are placeholder test data, not "
            "calibrated values, and its trajectories were not compared with a Gazebo run",
            "the fake returns Python lists and floats; the upstream callbacks produce numpy arrays",
            "no rendering and no snapshot/restore: the upstream class has no get_state()/set_state() pair and "
            "render() is a no-op",
            "the action space is copied from the upstream Box and the observation space from the upstream Dict, but "
            "the dynamics behind them are not",
        ],
    }
