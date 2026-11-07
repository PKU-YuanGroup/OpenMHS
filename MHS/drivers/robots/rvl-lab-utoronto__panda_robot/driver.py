"""OpenMHS driver for gh.rvl-lab-utoronto/panda_robot: the PandaReacherEnv Gym environment.

The upstream repository is a ROS 1 framework for a real Franka Emika Panda arm.  Its concrete
environment ``PandaReacherEnv`` is an old Gym environment (``gym.Env``), not a ROS topic/service
interface: ``step`` builds a ``geometry_msgs/Twist`` and publishes it on
``/franka_control/target_velocity`` through ``PandaClient.set_ee_velocity``, while the observation
comes from ``/franka_state_controller/franka_states``.  This package therefore uses the SDK's
``GymnasiumDriver`` rather than the card's ``RosDriver``: the environment step/reset/seed contract
is the primary interface, and a ROS transport declaration would lose it.  See RESULT.json for the
explicit deviation from the card.

The upstream environment is Python 2 and needs a live ROS graph, MoveIt, franka_ros, a Franka
control computer and a real Panda arm; the clone also has missing modules, so it cannot be built or
imported here.  No upstream simulator or mock exists.  Only the package fake is exposed: an
ROS-free analytic stand-in that preserves the old Gym four-tuple step and the observation/reward
rules of the source, but not the arm, the ROS transport or the real controller.  A live hardware
backend is deliberately absent; such a binding would affect a robot arm (at least R2) and needs a
human-reviewed deployment and an independent physical stop.  The fake is not a recording and no
trajectory was captured from the arm.

Model review (r20): the environment has no hardware-free path (a real Franka Panda only, no simulator
or mock in the clone) and does not load as shipped (``gym_panda_robot.envs`` imports a missing
``panda_reacher_manga`` module), so, as for applied-ai-lab/ramp, the package is blocked
(NO_HARDWARE_FREE_PATH); the device it describes is an arm (R2), while this fake contract stays R0.

Every fact cites the pinned clone at commit 494e9db28a8b38290a3339fea3644379f3d5b9ad.  The package
is model-authored and unreviewed; ``driver.lock.json`` keeps ``reviewed_by: null``.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "src/gym-panda-robot/gym_panda_robot/envs/panda_reacher_env.py"
CLIENT = "src/gym-panda-robot/gym_panda_robot/envs/panda_client.py"
ENVS_INIT = "src/gym-panda-robot/gym_panda_robot/envs/__init__.py"
PKG_INIT = "src/gym-panda-robot/gym_panda_robot/__init__.py"
TOP_INIT = "src/__init__.py"
PEG = "src/gym-panda-robot/gym_panda_robot/envs/panda_peg_in_hole.py"


class PandaReacher(GymnasiumDriver):
    """PandaReacherEnv as served by the package's isolated fake backend."""

    device_id = "panda-reacher"
    env_id = "panda-robot-reacher-v0"
    native = "gym_panda_robot.envs:PandaReacherEnv"
    backends = {"fake": ".fake:FakePandaReacherEnv"}
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    display_name = "RVL panda_robot PandaReacherEnv (ROS-free fake)"
    vendor = "RVL Lab, University of Toronto"
    model = "PandaReacherEnv"
    tags = ["franka", "panda", "ros", "gym", "reinforcement-learning", "simulation", "fake"]
    facts = [
        Fact("The README describes Gym-like interfaces through ROS for the real Franka Emika Panda arm, "
             "for reinforcement-learning prototyping.", source="vendor_doc", ref="README.md:3"),
        Fact("The documented deployment has two Ubuntu 18.04 machines: a real-time Linux NUC connected "
             "directly to the Franka FCI computer and a second ROS machine connected to the NUC.",
             source="vendor_doc", ref="README.md:7"),
        Fact("The installation assumes ROS Melodic, libfranka 0.5 and franka_ros, with franka_ros built "
             "from source on the melodic-devel branch.", source="vendor_doc", ref="README.md:10"),
        Fact("Running the Gym environments is documented as launching panda_robot.launch and "
             "kinect_azure.launch, then running panda_env_test.py; the test should move the robot along "
             "x, y and z in cartesian velocity mode and occasionally reset it to the home configuration.",
             source="vendor_doc", ref="README.md:49-65"),
        Fact("PandaReacherEnv is the concrete reacher environment class and derives from gym.Env.",
             source="upstream_code", ref=f"{ENV}:23"),
        Fact("PandaReacherEnv.__init__ starts a ROS node named panda_robot_reacher_v0, sets dt to 0.1 s "
             "(a 10 Hz rate), and builds PandaClient with the end-effector safety zone "
             "[[0.2, 0.7], [-0.3, 0.05], [0.15, 0.4]] and Kinect enabled.",
             source="upstream_code", ref=f"{ENV}:26-32"),
        Fact("PandaReacherEnv stores hole_goal (0.455, -0.005, 0.25), threshold 0.05, sparse False and "
             "_max_episode_steps 50.", source="upstream_code", ref=f"{ENV}:33-36"),
        Fact("PandaReacherEnv.apply_velocity_action copies action[0], action[1] and action[2] into "
             "Twist.linear.x, .y and .z and calls PandaClient.set_ee_velocity.",
             source="upstream_code", ref=f"{ENV}:38-43"),
        Fact("The dense reward is minus the Euclidean distance to hole_goal; the sparse branch returns "
             "-(distance >= threshold).", source="upstream_code", ref=f"{ENV}:45-58"),
        Fact("PandaReacherEnv.preprocess_action returns the action unchanged.", source="upstream_code",
             ref=f"{ENV}:60-61"),
        Fact("PandaReacherEnv.step applies the action, sleeps one rate period, reads the observation, "
             "computes the reward and done = distance < threshold, and returns a four-tuple "
             "(observation, reward, done, info); it does not test _max_episode_steps.",
             source="upstream_code", ref=f"{ENV}:63-76"),
        Fact("PandaReacherEnv.reset calls PandaClient.go_home() and returns the observation.",
             source="upstream_code", ref=f"{ENV}:78-81"),
        Fact("PandaReacherEnv.get_obs concatenates PandaClient.O_P_EE and O_V_EE, the end-effector "
             "position and velocity, into one observation.", source="upstream_code", ref=f"{ENV}:83-89"),
        Fact("PandaReacherEnv.close publishes a zero linear velocity through set_ee_velocity.",
             source="upstream_code", ref=f"{ENV}:91-96"),
        Fact("PandaReacherEnv imports PandaClient as a top-level module (from panda_client import "
             "PandaClient), not as a package-relative import.", source="upstream_code", ref=f"{ENV}:9"),
        Fact("PandaClient creates actionlib clients for /franka_gripper/homing, /franka_gripper/move and "
             "/franka_gripper/grasp.", source="upstream_code", ref=f"{CLIENT}:98-103"),
        Fact("PandaClient creates an actionlib client for /franka_control/error_recovery.",
             source="upstream_code", ref=f"{CLIENT}:160-161"),
        Fact("PandaClient publishes Twist commands on /franka_control/target_velocity with queue size 1 "
             "and subscribes to /franka_control/current_target_velocity.",
             source="upstream_code", ref=f"{CLIENT}:169-171"),
        Fact("PandaClient subscribes to /franka_state_controller/franka_states with "
             "franka_msgs/FrankaState and stores the message in update_state.",
             source="upstream_code", ref=f"{CLIENT}:173-175"),
        Fact("PandaClient.set_ee_velocity clips only velocity components that would move the end effector "
             "farther outside the configured safety zone, then publishes the Twist on "
             "/franka_control/target_velocity.", source="upstream_code", ref=f"{CLIENT}:320-353"),
        Fact("PandaClient.go_home switches to the position joint trajectory controller when it is not "
             "running, moves to a fixed home joint configuration and switches back to the cartesian "
             "velocity controller.", source="upstream_code", ref=f"{CLIENT}:364-380"),
        Fact("PandaClient contains Python 2 print statements, for example print \"Waiting for gripper "
             "homing server\".", source="upstream_code", ref=f"{CLIENT}:105"),
        Fact("PandaClient uses the Python 2 exception syntax except rospy.ServiceException, e:.",
             source="upstream_code", ref=f"{CLIENT}:396"),
        Fact("The gym package registers panda-robot-reacher-v0 with entry point "
             "gym_panda_robot.envs:PandaReacherEnv and panda-robot-reacher-v1 with entry point "
             "gym_panda_robot.envs:PandaReacherEnv1.", source="upstream_code", ref=f"{PKG_INIT}:3-10"),
        Fact("The envs package imports PandaReacherEnv from panda_reacher_env and PandaReacherEnv1 from "
             "gym_panda_robot.envs.panda_reacher_manga; no panda_reacher_manga module exists in the "
             "clone.", source="upstream_code", ref=f"{ENVS_INIT}:1-2"),
        Fact("The top-level package registers panda-robot-v0 with entry point "
             "gym_panda_robot.envs:PandaPegInHoleEnv.", source="upstream_code", ref=f"{TOP_INIT}:3-6"),
        Fact("PandaPegInHoleEnv imports PandaBaseEnv from panda_base_env; no panda_base_env module exists "
             "in the clone.", source="upstream_code", ref=f"{PEG}:12"),
        Fact("PandaPegInHoleEnv.step is declared with no action parameter and then refers to an undefined "
             "action variable.", source="upstream_code", ref=f"{PEG}:45-47"),
        Fact("The gym package declares only gym as its install dependency.",
             source="upstream_code", ref="src/gym-panda-robot/setup.py:5"),
    ]
    safe_state = ("The simulated fake stops advancing: after an e-stop no step, reset or seed is accepted "
                  "until mhs.safety.reset clears the latch, and the placeholder world state stays readable. "
                  "This is a software latch on an isolated fake, not a robot stop; no hardware or ROS "
                  "backend is served.")
    #: The deployed fake is an analytic kinematic stand-in, not a recording and not the ROS arm.
    fidelity = {
        "engine": "analytic:pure-Python PandaReacherEnv fake (no ROS, no arm, no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake accepts the bridge seed and is deterministic without random sampling; its "
                     "fixed trajectory and placeholders repeat, but this is not the upstream arm or ROS "
                     "behaviour and was not compared with a live run",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a pure-Python analytic stand-in for the old Gym PandaReacherEnv: it does not import "
            "gym, rospy, MoveIt, franka_ros, numpy or the clone, never starts a ROS node, and never publishes "
            "a Twist or calls a controller, gripper or error-recovery action",
            "the upstream environment is hardware-in-the-loop for a real Franka Emika Panda over ROS "
            "(README.md:3,7,49-65; panda_client.py:169-175,320-353); no upstream simulator or mock exists, so "
            "the fake is not a recording and no arm trajectory was captured",
            "the action bounds of Box(-1, 1) with three values are placeholders: upstream preprocess_action "
            "returns the action unchanged and apply_velocity_action writes action[0..2] to Twist.linear with no "
            "value bound, clipping or scale (panda_reacher_env.py:38-43,60-61), so these are not sourced limits",
            "the fake's start position, goal, threshold and velocity gain are placeholders, not calibrated "
            "values; the fake integrates one velocity step per tick and models no arm kinematics, controllers, "
            "contacts, actuators, gripper, camera or sensor noise",
            "the upstream environment is Python 2 (panda_client.py:105,396) and its envs package imports a "
            "missing panda_reacher_manga module (envs/__init__.py:1-2), so the registered old Gym environment "
            "cannot be constructed on Python 3 here",
            "no sim or hardware backend is served: only the fake backend is declared; a live ROS deployment "
            "would need the Python 2/ROS Melodic stack with libfranka, MoveIt, franka_ros and a real arm, and "
            "such a binding would be at least R2 with a human-reviewed independent stop",
            "the fake accepts reset(seed, options) for the bridge while upstream reset() takes no argument and "
            "the seed does not change the fake's fixed trajectory",
            "the fake returns the old Gym four-tuple (observation, reward, done, info) and Python lists; "
            "upstream returns numpy arrays, a one-element reward and a one-element done array, and the bridge "
            "reports done as terminated",
            "the package serves no rendering, snapshot or restore, and the upstream _max_episode_steps=50 is "
            "not enforced by the environment's own step",
            "model review r20: the device is a real Franka Panda (an arm, R2) with no hardware-free path, and "
            "the only stop-like call, close(), publishes an unacknowledged zero Twist; the package is blocked "
            "NO_HARDWARE_FREE_PATH and this fake contract is not a substitute for that missing path",
        ],
    }
