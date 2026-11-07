"""OpenMHS Gymnasium driver for gh.ammar-n-abbas/sim2real-ur-gym-gazebo.

The card names the ROS family, but the confirmed entry symbols are Python Gymnasium environments, not ROS
topics, services or actions.  This package therefore uses the ``GymnasiumDriver`` family and covers one concrete
environment, ``UR5TaskSpaceEnv-v0`` (``ur_openai.task_envs.ur5_task_space:UR5TaskSpaceEnv``), through the
``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` classes.  The environment itself is a
Gymnasium ``gym.Env`` that commands a UR5 arm through ROS; it is not replaced by a rosbridge transport.  Upstream
it never pauses Gazebo and cannot tell the Gazebo arm from a real one (see the facts and fidelity gaps).

A GymnasiumDriver is configuration only.  ``env_id`` names the upstream registration, ``native`` documents the
upstream class and the bridge derives the whole contract from the environment's spaces.  The action space is
``Box(-1.0, 1.0, shape=(3,))`` (the simulation task-space configuration sets ``n_actions: 3``), and the observation
is an unbounded 32-element ``Box`` built from the upstream concatenation.

The gate cannot import the upstream environment: constructing it needs ROS parameters and a running trajectory
controller and imports ``rospy``, ``ur_control``, ``ur_gazebo`` and ``ur_pykdl``.  The declared ``fake`` backend is therefore the
package's own pure Python analytic stand-in (fake.py); the ``sim`` path would call
``gym.make('UR5TaskSpaceEnv-v0')`` after the upstream registration and was not run.  Every Fact cites the pinned
clone at c36c625626c21ed44d02729426a1220fde5ec56a.  This package is model-authored and unreviewed: it is checked on
the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

TASK_SPACE = "ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space.py"
BASE_ENV = "ur_openai_gym/ur_openai/src/ur_openai/robot_env.py"
REGISTRY = "ur_openai_gym/ur_openai/src/ur_openai/task_envs/task_envs_list.py"
CONFIG = "ur_openai_gym/ur_rl/config/simulation/task_space.yaml"
GAZEBO_CONN = "ur_openai_gym/ur_openai/src/ur_openai/gazebo_connection.py"
UR5_ENV = "ur_openai_gym/ur_openai/src/ur_openai/robot_envs/ur5_env.py"
ARM = "ur_control/src/ur_control/arm.py"
UR_CONSTANTS = "ur_control/src/ur_control/constants.py"
GAZEBO_CONTROLLERS = "ur_gazebo/config/ur5_controllers.yaml"
REAL_ENV = "ur_openai_gym/ur_openai/src/ur_openai/task_envs/ur5_task_space_pick_and_place_real.py"
REAL_CONFIG = "ur_openai_gym/ur_rl/config/real/task_space_pick_and_place_real.yaml"


class UR5TaskSpace(GymnasiumDriver):
    # R2, not the inherited R0 (grok-4.7, 2026-11-05; REVIEW.md item 12):
    # Arm publishes JointTrajectory on <ns>/scaled_pos_joint_traj_controller/command
    # (arm.py:115-127; constants.py:4). ur5_controllers.yaml:5-25 defines that
    # controller as position_controllers/JointTrajectoryController on the six UR
    # joints. get_robot_params leaves param_use_gazebo False for every driver value
    # (ur5_task_space.py:74-81), so the class cannot tell the Gazebo arm from a real
    # one. No fact cites that only Gazebo consumes the trajectory topic. An arm is
    # R2 however simulated the deployment. The latch does not send a zero trajectory.
    risk = "R2"
    device_id = "ur5-task-space"
    env_id = "UR5TaskSpaceEnv-v0"
    native = "ur_openai.task_envs.ur5_task_space:UR5TaskSpaceEnv"
    backends = {"fake": ".fake:FakeUR5TaskSpaceEnv"}
    #: The upstream Box line the fake's action space copies.
    action_space_ref = f"{TASK_SPACE}:38-40"
    display_name = "Sim2Real UR5 task-space environment (ROS Gazebo)"
    vendor, model = "ammar-n-abbas", "UR5TaskSpaceEnv-v0"
    tags = ["ur5", "universal-robots", "gazebo", "ros", "gymnasium", "reinforcement-learning",
            "simulation", "robot-arm", "task-space"]
    facts = [
        Fact("UR5TaskSpaceEnv subclasses ur5_env.UR5Env in ur_openai.task_envs.ur5_task_space.",
             source="upstream_code", ref=f"{TASK_SPACE}:17"),
        Fact("The task-env registry registers UR5TaskSpaceEnv-v0 with entry point "
             "ur_openai.task_envs.ur5_task_space:UR5TaskSpaceEnv and a max_episode_steps argument.",
             source="upstream_code", ref=f"{REGISTRY}:19-25"),
        Fact("The simulation task-space configuration sets env_id UR5TaskSpaceEnv-v0 and agent_control_dt 0.005 s.",
             source="upstream_code", ref=f"{CONFIG}:3-7"),
        Fact("The same configuration sets n_actions 3 and distance_threshold 5.0.",
             source="upstream_code", ref=f"{CONFIG}:28-32"),
        Fact("The action space is Box(-1., 1.) with shape (n_actions,) and dtype float32.",
             source="upstream_code", ref=f"{TASK_SPACE}:38-40"),
        Fact("The observation space is an unbounded Box whose shape is the observation built in __init__.",
             source="upstream_code", ref=f"{TASK_SPACE}:42-45"),
        Fact("The observation concatenates joint angles, end-effector pose, target pose, pose error and velocity.",
             source="upstream_code", ref=f"{TASK_SPACE}:136-146"),
        Fact("The pose error is translation_rotation_error(target_pose, end-effector pose) and the velocity is a "
             "finite difference over agent_control_dt.",
             source="upstream_code", ref=f"{TASK_SPACE}:150-166"),
        Fact("For n_actions 3, the action is multiplied by 0.001 and applied as a translation-only pose delta with "
             "zero rotation delta.", source="upstream_code", ref=f"{TASK_SPACE}:187-192"),
        Fact("_set_action sends the command with set_target_pose_flex(cmd, t=agent_control_dt) without checking its "
             "return value, publishes the current pose and sleeps on the loop rate.",
             source="upstream_code", ref=f"{TASK_SPACE}:206-208"),
        Fact("The loop rate is rospy.Rate(1/agent_control_dt).", source="upstream_code", ref=f"{TASK_SPACE}:48"),
        Fact("The reward is 100.0 when the episode is done and otherwise the negative end-effector-to-target "
             "distance times 1000.", source="upstream_code", ref=f"{TASK_SPACE}:169-174"),
        Fact("Termination is true when the translational error converted to millimetres is below "
             "distance_threshold.", source="upstream_code", ref=f"{TASK_SPACE}:211-220"),
        Fact("RobotGazeboEnv.step calls _pause_env when the pause flag is set, then unpause, _set_action and pause "
             "on the robot connection, reads the observation, computes terminated, truncated (step_count >= 200) "
             "and reward, and returns a five-tuple.",
             source="upstream_code", ref=f"{BASE_ENV}:55-83"),
        Fact("RobotGazeboEnv.reset accepts seed and options, updates the episode, initializes per-episode variables, "
             "resets the simulation and returns (observation, info).", source="upstream_code",
             ref=f"{BASE_ENV}:85-93"),
        Fact("RobotGazeboEnv.seed reseeds np_random with gymnasium.utils.seeding.np_random.",
             source="upstream_code", ref=f"{BASE_ENV}:51-53"),
        Fact("With reset_controls false, RobotGazeboEnv._reset_sim calls unpause, _check_all_systems_ready, "
             "_set_init_pose, pause, reset, unpause, _check_all_systems_ready and pause on the robot connection.",
             source="upstream_code", ref=f"{BASE_ENV}:158-167"),
        Fact("With random_target_pose and random_initial_pose enabled, _set_init_pose redraws the target around the "
             "current pose and samples a new start pose from the workspace.", source="upstream_code",
             ref=f"{TASK_SPACE}:95-126"),
        Fact("The simulation task-space configuration enables random_target_pose and random_initial_pose.",
             source="upstream_code", ref=f"{CONFIG}:12-13"),
        Fact("The README describes the project as a Universal Robot Environment for Gymnasium and ROS Gazebo.",
             source="vendor_doc", ref="README.md:3"),
        Fact("get_robot_params loads the ur_gym parameters, reads ur_gym/driver without a default and sets "
             "param_use_gazebo to False whatever the driver value is.",
             source="upstream_code", ref=f"{TASK_SPACE}:74-81"),
        Fact("UR5Env passes param_use_gazebo as use_gazebo, with reset_controls False, to RobotGazeboEnv, then calls "
             "robot_connection.unpause and constructs ur_control's Arm.",
             source="upstream_code", ref=f"{UR5_ENV}:52-64"),
        Fact("RobotGazeboEnv uses GazeboConnection only when use_gazebo is true; otherwise it uses RobotConnection "
             "and subscribes to ur3/pause.", source="upstream_code", ref=f"{BASE_ENV}:24-28"),
        Fact("RobotConnection's pause, unpause and reset do nothing.",
             source="upstream_code", ref=f"{GAZEBO_CONN}:22-33"),
        Fact("pause_callback sets the pause flag when a ur3/pause message is true.",
             source="upstream_code", ref=f"{BASE_ENV}:46-48"),
        Fact("UR5Env._pause_env reads the joint angles, blocks on input('Press Enter to continue') and then moves "
             "the arm back to those angles with wait=True.", source="upstream_code", ref=f"{UR5_ENV}:77-80"),
        Fact("_set_action calls sys.exit() when the action contains NaN and asserts that every value lies within "
             "-1.0001 and 1.0001.", source="upstream_code", ref=f"{TASK_SPACE}:178-183"),
        Fact("RobotGazeboEnv.close calls rospy.signal_shutdown.", source="upstream_code", ref=f"{BASE_ENV}:95-102"),
        Fact("Importing ur5_env inserts an absolute /home/imr workspace path at the front of sys.path.",
             source="upstream_code", ref=f"{UR5_ENV}:24-25"),
        Fact("Arm publishes its flexible trajectories on the namespace plus '/' plus JOINT_PUBLISHER_ROBOT plus "
             "'/command'.", source="upstream_code", ref=f"{ARM}:116-127"),
        Fact("JOINT_PUBLISHER_ROBOT is scaled_pos_joint_traj_controller.",
             source="upstream_code", ref=f"{UR_CONSTANTS}:4"),
        Fact("The ur_gazebo UR5 controller configuration defines a controller named scaled_pos_joint_traj_controller.",
             source="upstream_code", ref=f"{GAZEBO_CONTROLLERS}:5"),
        Fact("set_joint_positions_flex returns SPEED_LIMIT_EXCEEDED without commanding when the required joint speed "
             "exceeds max_joint_speed, and set_target_pose_flex returns IK_NOT_FOUND when inverse kinematics finds "
             "no solution.", source="upstream_code", ref=f"{ARM}:395-422"),
        Fact("With curriculum_learning enabled, each _set_init_pose call lowers dist_cl by 0.005 and uses it as "
             "distance_threshold, never below 5.", source="upstream_code", ref=f"{TASK_SPACE}:104-109"),
        Fact("The simulation task-space configuration sets driver gazebo, curriculum_learning true and dist_cl 50.",
             source="upstream_code", ref=f"{CONFIG}:4-15"),
        Fact("UR5PickAndPlaceRealEnv.get_robot_params sets param_use_gazebo True unless the ur_gym/driver parameter "
             "is robot.", source="upstream_code", ref=f"{REAL_ENV}:203-209"),
        Fact("The real-robot configuration sets env_id UR5PickAndPlaceRealEnv-v0 and driver robot.",
             source="upstream_code", ref=f"{REAL_CONFIG}:3-4"),
    ]
    safe_state = ("software latch only: after an e-stop no further step or reset is accepted until mhs.safety.reset "
                  "clears the latch, an in-flight native step may finish and the last observation stays readable. "
                  "Upstream UR5TaskSpaceEnv never pauses Gazebo (it always uses the no-op RobotConnection), so a "
                  "live simulation keeps running and the trajectory controller holds the last commanded target. "
                  "The latch sends no zero trajectory and does not stop a UR arm on "
                  "scaled_pos_joint_traj_controller/command")
    #: The fidelity contract of the analytic fake backend that the gate checks.  It is not a claim about the
    #: upstream Gazebo deployment (which was not run).
    fidelity = {
        "engine": "analytic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake draws its target jitter from random.Random(seed) at reset, so one seed repeats; "
                     "upstream reset(seed) ignores the seed and redraws the target and start pose from the "
                     "process-global numpy RNG, so a seed does not reproduce an upstream trajectory",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the checked fake is an analytic kinematic stand-in for the ROS/Gazebo environment: it translates the "
            "end-effector by 0.001 m per unit action in a straight line and models no inverse kinematics, joint "
            "limits, dynamics, contacts, collisions, grasping, Gazebo physics or ROS graph",
            "no ROS or Gazebo run: the upstream environment needs ROS Noetic, Gazebo, a catkin workspace and the "
            "clone's ur_control, ur_gazebo and ur_pykdl packages, none of which were installed where the gate ran",
            "the upstream reset(seed) ignores the seed and redraws the target around the current pose and the start "
            "pose from the workspace with the process-global numpy RNG; the fake uses its own seed-local jitter, so "
            "the two give different episodes",
            "the fake's 32-element observation mirrors the upstream concatenation of 6 joint angles + 7 "
            "end-effector pose + 7 target pose + 6 pose error + 6 velocity, but the joint angles and orientation "
            "are placeholders and no forward kinematics is modelled",
            "the environment cannot be constructed before a ROS node and ROS parameters exist; the implicit sim "
            "backend gym.make('UR5TaskSpaceEnv-v0') was not run and needs the upstream register_environment call",
            "live construction in the server process would read ur_gym/driver without a default, insert an "
            "absolute /home/imr path into sys.path on import, construct ur_control's Arm and create ROS "
            "publishers; a NaN action makes _set_action call sys.exit(), a true ur3/pause message makes the next "
            "step block on input(), and close() calls rospy.signal_shutdown",
            "upstream get_robot_params leaves param_use_gazebo False for every driver value, so UR5TaskSpaceEnv "
            "uses the no-op RobotConnection: it never pauses or resets Gazebo, and its Arm commands "
            "scaled_pos_joint_traj_controller, the controller name that ur_gazebo and the real UR driver share, so "
            "the same class moves a real UR5 when the operator's ROS graph runs the real driver",
            "set_target_pose_flex can return IK_NOT_FOUND or SPEED_LIMIT_EXCEEDED without commanding the arm, and "
            "_set_action ignores the return value, so an upstream step can complete without motion; the fake models "
            "neither",
            "the shipped simulation configuration enables curriculum_learning, so upstream _set_init_pose uses "
            "dist_cl (50, lowered by 0.005 per reset, never below 5) as the termination threshold and draws the "
            "target within n_count * 0.001 m of the current pose; the fake keeps the fixed 5.0 mm threshold and a "
            "placeholder target, so its episode lengths differ",
            "the fake applies the upstream step_count >= 200 truncation itself; the gymnasium TimeLimit wrapper "
            "that gym.make can add was not exercised (the training scripts use .unwrapped)",
            "snapshot and restore are not offered: the upstream environment has no get_state/set_state methods",
            "the runtime latch stops future step/reset calls but cannot interrupt one in-flight native env.step; "
            "this is a simulation latch, not a physical emergency stop",
        ],
    }
