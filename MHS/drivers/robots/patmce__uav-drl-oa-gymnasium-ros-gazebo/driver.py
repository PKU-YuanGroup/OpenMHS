"""OpenMHS driver for gh.patmce/uav-drl-oa-gymnasium-ros-gazebo (DroneGymGazeboEnv-v0).

The pinned repository ships two copies of a Gymnasium environment class around a ROS Noetic,
Gazebo and PX4 SITL drone (``DroneGymGazeboEnv`` in step1/new_drone_gym_gazebo_env.py:33 and
step2/eval_drone_gym_gazebo_env.py:33).  The runtime is a Gymnasium environment, not a ROS
transport endpoint, so this package is a configuration-only :class:`GymnasiumDriver` over the
step1 copy: ``cap.world.step.v1`` takes ``{ticks, action}`` with the ``Discrete(3)`` action of
step1:39, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.
The card named a RosDriver because the repository also contains ROS launch files; that helper
cannot express an environment's step/reset/observation contract.

The upstream class cannot be imported by this package or the gate: it imports rospy, cv_bridge,
OpenCV and the external mavros_px4_vehicle package and constructs ``PX4Vehicle(auto_connect=True)``
(step1:12-24, :36).  The ``fake`` backend is this package's analytic kinematic stand-in
(fake.py), so the gate's evidence is contract-level only.  No ROS, Gazebo, PX4 or hardware is
contacted, and the package has no hardware or live-sim backend.  ``forward`` and
``left_or_right`` send a pose setpoint through ``PX4Vehicle.set_pose2d``
(step1/new_drone_gym_gazebo_env.py:233-249).  README.md:79-83 says the cloned
mavros-px4-vehicle package communicates with the PX4 autopilot through MAVROS, and
no fact cites that only a simulator consumes that setpoint, so the device risk is R2
(a vehicle in flight) however simulated the deployment.  The Jetson notes run the
same environment against a desktop Gazebo (README.md:285-303); that does not show
the setpoint is simulator-only.  The e-stop is the runtime's software latch, after
which no step or reset is accepted until ``mhs.safety.reset`` clears it.  The
upstream's live construction and lifecycle hazards are listed in the fidelity gaps
(model review, 2026-11-05).

Every fact cites the clone at commit 7e72584e02545c782bc15f3a73480a228a9498af.  The fidelity
object describes the fake as deployed (spec 05-fidelity FID-002), not the upstream Gazebo
defaults.  This package is model-authored and unreviewed: ``reviewed_by`` stays null.
"""

from mhs.driver import Fact, GymnasiumDriver

STEP1 = "step1/new_drone_gym_gazebo_env.py"
STEP2 = "step2/eval_drone_gym_gazebo_env.py"


class DroneGymGazeboEnv(GymnasiumDriver):
    # R2, not the inherited R0 (grok-4.7, 2026-11-05; REVIEW.md item 12):
    # forward and left_or_right call PX4Vehicle.set_pose2d with a position offset
    # (step1/new_drone_gym_gazebo_env.py:233-249). README.md:79-83 says
    # troiwill/mavros-px4-vehicle communicates with the PX4 autopilot through MAVROS.
    # The setpoint topic name is not in this clone; it is not invented here. No fact
    # cites that only a simulator consumes the setpoint. A vehicle in flight is R2
    # however simulated the deployment. The latch does not disarm the vehicle.
    risk = "R2"
    device_id = "uav-drl-oa-drone-gym-gazebo"
    env_id = "DroneGymGazeboEnv-v0"
    native = "new_drone_gym_gazebo_env:DroneGymGazeboEnv"
    backends = {"fake": ".fake:FakeDroneGymGazeboEnv"}
    #: The fake copies the upstream action space line (Discrete(3) at step1:39).
    action_space_ref = f"{STEP1}:39"
    display_name = "UAV DRL obstacle-avoidance DroneGymGazeboEnv-v0"
    vendor, model = "patmce", "DroneGymGazeboEnv-v0"
    tags = ["uav", "drone", "gazebo", "px4", "mavros", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The repository is connected to the paper 'Towards Latency Efficient DRL Inference: Improving UAV "
             "Obstacle Avoidance at the Edge Through Model Compression'", source="vendor_doc", ref="README.md:3"),
        Fact("The setup clones the external decargroup/ifo_gazebo Gazebo model and PX4-Autopilot workspace",
             source="vendor_doc", ref="README.md:20-24"),
        Fact("The setup clones the external troiwill/mavros-px4-vehicle package, which communicates with the PX4 "
             "autopilot through MAVROS", source="vendor_doc", ref="README.md:79-83"),
        Fact("The README instructs copying six Python scripts by hand into the mavros-px4-vehicle catkin package's "
             "scripts directory", source="vendor_doc", ref="README.md:103-109"),
        Fact("The environment imports rospy, sensor_msgs, geometry_msgs, std_srvs, cv_bridge and cv2, and imports "
             "PX4_MODE_OFFBOARD, SetPositionWithYawCmdBuilder and PX4Vehicle from mavros_px4_vehicle",
             source="upstream_code", ref=f"{STEP1}:5-24"),
        Fact("The constructor creates PX4Vehicle(auto_connect=True)", source="upstream_code", ref=f"{STEP1}:36"),
        Fact("The constructor creates the /gazebo pause and unpause service proxies and subscribes to "
             "/camera/depth/image_raw and /mavros/local_position/pose", source="upstream_code",
             ref=f"{STEP1}:73-80"),
        Fact("The environment registers DroneGymGazeboEnv-v0 with entry point "
             "new_drone_gym_gazebo_env:DroneGymGazeboEnv and max_episode_steps 225", source="upstream_code",
             ref=f"{STEP1}:26-31"),
        Fact("DroneGymGazeboEnv derives from gymnasium.Env", source="upstream_code", ref=f"{STEP1}:33"),
        Fact("The action space is spaces.Discrete(3), commented as three actions forward/left/right",
             source="upstream_code", ref=f"{STEP1}:39"),
        Fact("The observation space is spaces.Box(low=-1.0, high=8.0, shape=(3, 80, 106), dtype=np.float32)",
             source="upstream_code", ref=f"{STEP1}:41-45"),
        Fact("The start point is (0.0, 0.0, 1.5) and the desired point is (7.0, start.y, 1.5)",
             source="upstream_code", ref=f"{STEP1}:47-55"),
        Fact("The workspace bounds are x in (-0.5, 7.5], y in (-1.7, 1.7] relative to start_point.y and z in "
             "(0.5, 3.2]", source="upstream_code", ref=f"{STEP1}:57-63"),
        Fact("The goal reward is 100, speed is 0.5 m/s, action_duration is 0.5 s and the candidate y start/desired "
             "points are 0.0, -5.0, -10.0 and -15.0", source="upstream_code", ref=f"{STEP1}:66-69"),
        Fact("step unpauses Gazebo, applies the action, pauses Gazebo and returns "
             "(observation, reward, terminated, False, {})", source="upstream_code", ref=f"{STEP1}:83-92"),
        Fact("reset takes options then seed and calls random.seed(seed) when a seed is given",
             source="upstream_code", ref=f"{STEP1}:94-104"),
        Fact("When the drone is not armed (commented as the first call of reset) reset unpauses Gazebo, arms the "
             "drone, goes to takeoff height and sets offboard mode; otherwise it draws the start y with "
             "np.random.choice(self.possible_y_start_desired_points)",
             source="upstream_code", ref=f"{STEP1}:106-121"),
        Fact("The other reset branch unpauses Gazebo, sends the drone to x-0.5, then up to work_space_z_max + 1.0, "
             "then to the start point x and y at that height, with rospy.sleep waits of 8, 4 and 8 s, goes to "
             "takeoff height and pauses Gazebo", source="upstream_code", ref=f"{STEP1}:128-150"),
        Fact("reset ends by calling reset_dist_to_desired_point_and_observations and returning _get_obs()",
             source="upstream_code", ref=f"{STEP1}:152-153"),
        Fact("forward and left_or_right read the current pose and send a set_pose2d setpoint offset by "
             "round(self.speed, 2) in x, or by direction * speed in y, at start_point.z",
             source="upstream_code", ref=f"{STEP1}:233-251"),
        Fact("unpause_sim and pause_sim wait for the Gazebo service with rospy.wait_for_service and only print "
             "a failed call", source="upstream_code", ref=f"{STEP1}:166-178"),
        Fact("The constructor's readiness checks retry rospy.wait_for_message with a 5 s timeout until a depth "
             "image and a pose arrive or ROS shuts down", source="upstream_code", ref=f"{STEP1}:180-200"),
        Fact("_set_action maps 0 to forward, 1 to left_or_right(1) and 2 to left_or_right(-1), holding each action "
             "for action_duration seconds", source="upstream_code", ref=f"{STEP1}:253-273"),
        Fact("_get_obs writes desired.x - x and desired.y - y into the position channel and concatenates the "
             "current depth image, the previous depth image and that position map", source="upstream_code",
             ref=f"{STEP1}:294-305"),
        Fact("is_in_desired_position defaults epsilon to 0.5 and tests x and y against desired +/- epsilon",
             source="upstream_code", ref=f"{STEP1}:307-327"),
        Fact("is_inside_workspace tests the absolute x and z bounds and the y bounds offset by start_point.y",
             source="upstream_code", ref=f"{STEP1}:337-348"),
        Fact("drone_has_collided treats roll outside (-0.2, 0.2], pitch outside (-0.2, 0.2] or yaw outside "
             "(-0.05, 0.05] as a collision", source="upstream_code", ref=f"{STEP1}:350-369"),
        Fact("_is_done terminates when the drone leaves the workspace, collides or reaches the desired position",
             source="upstream_code", ref=f"{STEP1}:371-386"),
        Fact("_compute_reward returns -1 plus the reduction in distance while the episode runs, goal_reward when "
             "it ends at the desired position and -goal_reward otherwise", source="upstream_code",
             ref=f"{STEP1}:388-410"),
        Fact("close shuts down the ROS node with rospy.signal_shutdown", source="upstream_code",
             ref=f"{STEP1}:162-164"),
        Fact("The step2 copy registers the same DroneGymGazeboEnv-v0 id with entry point "
             "eval_drone_gym_gazebo_env:DroneGymGazeboEnv", source="upstream_code", ref=f"{STEP2}:26-31"),
        Fact("The step2 reset selects the start y with a counter that cycles through the four candidate points",
             source="upstream_code", ref=f"{STEP2}:120-126"),
        Fact("The step2 goal test defaults epsilon to 0.7", source="upstream_code", ref=f"{STEP2}:312"),
    ]
    safe_state = ("the runtime latches the e-stop and accepts no step or reset until mhs.safety.reset clears it; "
                  "the fake holds its last observation and tick, and the latch does not disarm the vehicle or "
                  "clear the PX4Vehicle.set_pose2d setpoint, so a physical PX4 on that MAVROS link is not "
                  "stopped. A completed step or reset pauses Gazebo only when /gazebo/pause_physics succeeds; "
                  "a failed pause is only printed, and a running step or reset is not interrupted")
    #: The contract of the fake as deployed (spec 05-fidelity FID-002): a discrete kinematic setpoint model,
    #: not Gazebo.  The upstream step waits 0.5 s of wall-clock action_duration (step1:68) while Gazebo is
    #: unpaused, but the fake integrates nothing, so it declares no timestep and no pacing.
    fidelity = {
        "engine": "analytic:DroneGymGazeboEnv-v0 kinematic setpoint stand-in",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds a local random.Random with the reset seed and uses it for the start-y choice "
                     "of resets after the first; that choice is not visible in its observation, which is relative "
                     "to the chosen lane. The upstream reset calls random.seed(seed) but draws the start y with "
                     "np.random.choice (step1:103-104, :120), which that seed does not reach, so the upstream "
                     "reset is not seed-controlled and no trajectory was compared with it",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic kinematic setpoint model: it loads no ROS, Gazebo, PX4 SITL, MAVROS, "
            "ifo_gazebo or mavros_px4_vehicle code, runs no physics, contacts, attitude, depth camera, CvBridge or "
            "OpenCV preprocessing, and holds no actuator, sensor or noise model",
            "the real observation is spaces.Box(low=-1.0, high=8.0, shape=(3, 80, 106), dtype=np.float32) "
            "(step1:41-45); the fake declares and returns a 3 x 8 x 8 placeholder array whose first two channels "
            "are zeros and whose last channel carries only desired.x - x and desired.y - y (step1:294-305) so "
            "receipts stay bounded",
            "one fake step is one discrete setpoint transition of 0.5 m (step1:67-68, :233-251); the upstream "
            "step unpauses Gazebo, holds the command for action_duration 0.5 s and pauses it again (step1:83-92, "
            ":253-273), so the fake models no dynamics over that interval and no wall-clock pacing",
            "collision termination is not modelled: the upstream derives it from the pose quaternion's "
            "roll/pitch/yaw (step1:350-369), while the fake keeps attitude zero and never reports a collision",
            "the upstream reset arms the drone, waits for arming, sets offboard mode and sends several setpoints "
            "with rospy.sleep waits (step1:106-150); the fake performs an instantaneous state jump and models only "
            "the resulting start position",
            "the first reset starts at y=0 and later resets choose from the four candidate y points and start the "
            "drone in that lane (step1:120, :144-149); the step2 copy cycles those candidates with a counter and "
            "defaults the goal epsilon to 0.7 (step2:120-126, :312), while this package serves the step1 copy",
            "the position channel holds desired.y - y, which reaches about -1.7 inside the workspace, below the "
            "declared observation low of -1.0 (step1:45, :57-63, :296-297); the bridge does not check observations "
            "against the Box, and the fake returns such values too",
            "the registration's max_episode_steps 225 is applied by gymnasium.make's TimeLimit wrapper; the "
            "upstream env.step itself always returns truncated=False (step1:92), and the fake implements the "
            "225-step truncation directly because the bridge serves the pre-built fake",
            "no snapshot and restore: DroneGymGazeboEnv defines no get_state or set_state method",
            "no live environment backend is included: the upstream needs ROS Noetic, Gazebo, PX4 SITL and two "
            "external catkin packages, and its scripts are copied by hand rather than installed (README.md:20-24, "
            ":79-83, :103-109), so runtime construction was not attempted",
            "live construction and lifecycle hazards (model review): the class never calls rospy.init_node (its "
            "training script does, step1/train_main_d3qn.py:38); the constructor connects PX4Vehicle "
            "(auto_connect=True) and waits without a bound for the Gazebo services and for a depth image and a "
            "pose (step1:36, :73-80, :166-200); reset arms the drone and switches it to OFFBOARD (step1:106-118); "
            "close calls rospy.signal_shutdown for the whole process (step1:162-164); failed pause/unpause calls "
            "and CvBridge errors are printed to stdout (step1:171, :178, :279), which would corrupt a stdio server",
        ],
    }
