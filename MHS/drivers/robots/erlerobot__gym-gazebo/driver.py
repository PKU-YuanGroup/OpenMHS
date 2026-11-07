"""OpenMHS driver for gh.erlerobot/gym-gazebo: GazeboCircuitTurtlebotLidar-v0.

DEVIATION FROM THE CARD: the card names ``helper: RosDriver`` and
``family: ros``, but the confirmed entry symbol is a legacy ``gym.Env`` whose
public interface is ``reset()`` and ``step(action)``.  The ROS 1 publisher and
the Gazebo pause/reset services are internals that the environment constructs
in its constructor; they are not a rosbridge endpoint surface that a RosDriver
could drive.  This package therefore uses the SDK's configuration-only
``GymnasiumDriver`` and serves ``cap.world.step.v1``, ``cap.world.reset.v1``
and ``cap.world.seed.v1``, preserving the environment step/reset interface.
The bridge has explicit fallbacks for legacy gym's four-value ``step`` result
and argument-less ``reset`` (mhs/bridge/gymnasium.py).

The pinned class launches ROS through ``roslaunch`` and requires ROS Melodic,
Gazebo 9 and the legacy ``gym`` package, so it is never imported here and no
live backend is offered.  The ``fake`` backend is the package's own analytic
stand-in (fake.py); it is not a recording and claims F0 contract evidence only.
Every Fact cites the pinned clone at
ade82b627839f816c1f4be6cea77b56eb21abc81.  This package is model-authored and
unreviewed: ``driver.lock.json`` keeps ``reviewed_by: null``.
"""

from mhs.driver import Fact, GymnasiumDriver

TURTLEBOT = "gym_gazebo/envs/turtlebot/gazebo_circuit_turtlebot_lidar.py"
BASE = "gym_gazebo/envs/gazebo_env.py"
REGISTER = "gym_gazebo/__init__.py"
LAUNCH = "gym_gazebo/envs/assets/launch/GazeboCircuitTurtlebotLidar_v0.launch"


class GazeboCircuitTurtlebotLidar(GymnasiumDriver):
    """The registered GazeboCircuitTurtlebotLidar-v0 environment."""

    device_id = "gym-gazebo-circuit-turtlebot-lidar"
    device_kind = "world.sim"
    mode = "simulated"
    # R2, not R0 (grok-4.7, 2026-11-05; REVIEW.md item 12): step publishes
    # geometry_msgs/Twist on /mobile_base/commands/velocity (gazebo_circuit_turtlebot_lidar.py:21,
    # 60-74). The launch file defaults the base to kobuki and names create and roomba
    # (GazeboCircuitTurtlebotLidar_v0.launch:3, 19-23). That topic is the TurtleBot base
    # command, not a Gazebo-only service. No fact cites that only the simulator consumes
    # it. A mobile base is R2 however simulated the deployment.
    risk = "R2"
    env_id = "GazeboCircuitTurtlebotLidar-v0"
    native = "gym_gazebo.envs.turtlebot:GazeboCircuitTurtlebotLidarEnv"
    backends = {"fake": ".fake:FakeGazeboCircuitTurtlebotLidarEnv"}
    tags = ["gym", "gazebo", "ros", "ros1", "turtlebot", "lidar", "simulation",
            "reinforcement-learning"]
    display_name = "gym-gazebo GazeboCircuitTurtlebotLidar-v0"
    vendor = "Erle Robotics"
    model = "GazeboCircuitTurtlebotLidar-v0"

    #: The fake copies the upstream Discrete(3) space (#F,L,R), so the bridge
    #: derives action.index 0..2 with this source.
    action_space_ref = f"{TURTLEBOT}:26"

    facts = [
        Fact("The project is an extension of the initial OpenAI gym for robotics using ROS and Gazebo.",
             source="vendor_doc", ref="README.md:10"),
        Fact("The README marks the repository as deprecated in favour of gym-gazebo2.",
             source="vendor_doc", ref="README.md:4"),
        Fact("GazeboCircuitTurtlebotLidar-v0 is registered with entry point "
             "gym_gazebo.envs.turtlebot:GazeboCircuitTurtlebotLidarEnv.",
             source="upstream_code", ref=f"{REGISTER}:15-19"),
        Fact("The documented example constructs the environment with "
             "gym.make('GazeboCircuitTurtlebotLidar-v0').",
             source="upstream_code", ref="examples/turtlebot/circuit_turtlebot_lidar_qlearn.py:24"),
        Fact("GazeboEnv derives from gym.Env and is the superclass of the environment.",
             source="upstream_code", ref=f"{BASE}:13"),
        Fact("GazeboEnv chooses a random ROS master port and a Gazebo master port one higher.",
             source="upstream_code", ref=f"{BASE}:21-25"),
        Fact("GazeboEnv launches the roslaunch process for the environment's launch file.",
             source="upstream_code", ref=f"{BASE}:53"),
        Fact("GazeboEnv writes ROS_MASTER_URI and GAZEBO_MASTER_URI into os.environ and prints both URIs.",
             source="upstream_code", ref=f"{BASE}:27-33"),
        Fact("GazeboEnv calls rospy.init_node('gym', anonymous=True) after starting roslaunch.",
             source="upstream_code", ref=f"{BASE}:59"),
        Fact("GazeboEnv._close counts gzclient, gzserver, roscore and rosmaster in ps -Af and runs killall -9 on "
             "each that appears.", source="upstream_code", ref=f"{BASE}:119-138"),
        Fact("The environment's launch file takes its world from the GYM_GAZEBO_WORLD_CIRCUIT environment variable "
             "and includes the turtlebot_gazebo base launch (kobuki unless TURTLEBOT_BASE is set).",
             source="upstream_code", ref=f"{LAUNCH}:1-23"),
        Fact("GazeboCircuitTurtlebotLidarEnv derives from gazebo_env.GazeboEnv.",
             source="upstream_code", ref=f"{TURTLEBOT}:16"),
        Fact("The constructor creates a rospy Publisher on /mobile_base/commands/velocity and "
             "service proxies for /gazebo/unpause_physics, /gazebo/pause_physics and "
             "/gazebo/reset_simulation.",
             source="upstream_code", ref=f"{TURTLEBOT}:21-24"),
        Fact("The action space is spaces.Discrete(3), commented #F,L,R.",
             source="upstream_code", ref=f"{TURTLEBOT}:26"),
        Fact("discretize_observation samples every len(ranges)/new_ranges beam, maps infinity to 6, "
             "NaN to 0 and any other range to int(range), and sets done when a range is greater "
             "than 0 and below 0.2.",
             source="upstream_code", ref=f"{TURTLEBOT}:31-46"),
        Fact("Action 0 commands linear.x 0.3 and angular.z 0.0, action 1 linear.x 0.05 and "
             "angular.z 0.3, and action 2 linear.x 0.05 and angular.z -0.3.",
             source="upstream_code", ref=f"{TURTLEBOT}:60-74"),
        Fact("A step first calls /gazebo/unpause_physics; a rospy.ServiceException is printed and the step "
             "continues.", source="upstream_code", ref=f"{TURTLEBOT}:54-58"),
        Fact("A step retries rospy.wait_for_message('/scan', LaserScan, timeout=5) inside a bare except until a "
             "message arrives, with no limit on the number of attempts.",
             source="upstream_code", ref=f"{TURTLEBOT}:76-81"),
        Fact("A step calls the /gazebo/pause_physics service after reading the scan; a rospy.ServiceException is "
             "printed and the step continues.", source="upstream_code", ref=f"{TURTLEBOT}:83-88"),
        Fact("step discretizes the scan into five ranges; a non-terminal step rewards 5 for action 0 "
             "and 1 otherwise, a terminal one rewards -200, and it returns "
             "(state, reward, done, {}).",
             source="upstream_code", ref=f"{TURTLEBOT}:90-100"),
        Fact("reset calls the /gazebo/reset_simulation and /gazebo/unpause_physics services, waits "
             "for a scan, calls /gazebo/pause_physics, and returns the result of "
             "discretize_observation(data, 5).",
             source="upstream_code", ref=f"{TURTLEBOT}:102-137"),
        Fact("setup.py declares only gym>=0.2.3 as a runtime dependency.",
             source="upstream_code", ref="setup.py:10"),
        Fact("The installation guide requires ROS Melodic and Gazebo 9.0.0.",
             source="vendor_doc", ref="INSTALL.md:13-15"),
        Fact("The README describes GazeboCircuitTurtlebotLidar-v0 as a more complex maze with high-contrast "
             "floor and walls, in which lidar is the input that trains the robot's navigation.",
             source="vendor_doc", ref="README.md:41"),
    ]

    #: Model review: the latch only refuses new steps and resets.  The fake does not advance; the upstream
    #: environment leaves Gazebo paused only because each step and reset ends with an unchecked pause call.
    safe_state = ("after an e-stop no world step or reset is accepted until mhs.safety.reset clears the latch, "
                  "the fake does not advance and its last observation stays readable; the latch publishes no "
                  "zero Twist on /mobile_base/commands/velocity and does not stop a kobuki, create or roomba "
                  "base on that topic, and Gazebo stays paused only when each step or reset pause call "
                  "succeeds, so after a failed pause or another unpause the last Twist keeps driving the base")
    fidelity = {
        "engine": "analytic:gym-gazebo GazeboCircuitTurtlebotLidar-v0 fake (no Gazebo)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake accepts and stores reset(seed=...) but its fixed start state and its "
                     "deterministic per-tick range update do not use the seed, so a seed is reported "
                     "without changing the trajectory; the upstream reset() takes no seed at all",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake runs no ROS, Gazebo, physics, contact, raycast or wall-clock loop; its five "
            "sector distances are placeholders that shrink by fixed per-tick amounts, so they are "
            "not a simulated LaserScan",
            "the upstream collision rule checks every beam before sampling five; the fake checks and "
            "samples the same five placeholder sectors",
            "the upstream step publishes a Twist and waits for a fresh /scan while the Gazebo world "
            "advances; the fake does not model velocity, pose, collision geometry, the Twist message "
            "or ROS timing",
            "reset(seed=...) is an extension of the fake; the upstream reset() takes no arguments and "
            "uses no seed, so seeded repeatability is not an upstream property",
            "there is no live or sim backend: the class starts ROS through roslaunch and needs ROS "
            "Melodic, Gazebo 9 and legacy gym, which are not available to the gate and are never "
            "imported by package code",
            "fake-only contract: live construction (never run here) would write ROS_MASTER_URI and "
            "GAZEBO_MASTER_URI into the server process's environment, print to standard output (which "
            "corrupts an MHS server that speaks over stdio), start roslaunch as a child process, call "
            "rospy.init_node in the server process and need GYM_GAZEBO_WORLD_CIRCUIT set; the legacy "
            "GazeboEnv._close runs killall -9 on every gzclient, gzserver, rosmaster and roscore of the host",
            "the upstream step and reset wait for each Gazebo service without a timeout, retry the /scan "
            "wait without limit and only print a failed unpause or pause call, so a live step can block "
            "indefinitely or report a transition while Gazebo stayed paused or kept running; the fake models "
            "neither",
            "the upstream reset returns the (ranges, done) pair of discretize_observation; the bridge keeps "
            "the ranges and drops done, so a reset that starts within 0.2 of a wall is not reported as "
            "terminal until the next step",
            "rendering, the Gazebo client, the raw LaserScan array and the ROS pause/unpause/reset "
            "services are not exposed",
        ],
    }
