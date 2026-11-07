"""OpenMHS driver for gh.geonhee-lee/ur5_ros_gym: the UR5 unscrewing Gym environment.

The card names the ROS family and ``RosDriver``, but the confirmed entry symbol is
``rl_gym.envs:UnscrewingEnv`` (``rl_unscrew/rl-gym/rl_gym/envs/unscrewing_env.py:14``), a legacy
``gym.Env`` subclass registered as ``gym_unscrewing_env-v0``
(``rl_unscrew/rl-gym/rl_gym/__init__.py:3-6``).  Its primary interface is ``reset()`` / ``step(action)``,
not a ROS topic or service surface: the ROS publishers, subscriber waits and ``/reset_robot`` service are
how the environment drives the upstream Gazebo/MoveIt simulator, not a transport this package exposes.
The package is therefore a configuration-only :class:`GymnasiumDriver` (DEVIATION FROM THE CARD:
GymnasiumDriver instead of RosDriver) and serves the derived ``cap.world.step.v1``,
``cap.world.reset.v1`` and ``cap.world.seed.v1`` capabilities.

The ``fake`` backend is the package's own pure-Python analytic stand-in for the legacy Gym methods.  The
upstream environment needs ROS 1 Kinetic, Gazebo, MoveIt and ``gym==0.10.5``
(``rl_unscrew/README.md:14-27``), so the real simulator path was not run; the package is contract-checked
on the fake backend only (a fake-only contract: no sim backend is declared).  An MHS e-stop is a software
latch only and calls nothing upstream; a live Gazebo world keeps running and MoveIt finishes a motion already
requested.  Every source reference is from the pinned clone at bd291129c8a12be28311538822c900d7d0930930.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "rl_unscrew/rl-gym/rl_gym/envs/unscrewing_env.py"
REGISTRY = "rl_unscrew/rl-gym/rl_gym/__init__.py"
MOVEIT = "rl_unscrew/rl_moveit/script/planning_script.py"
SCREW = "rl_unscrew/rl_moveit/script/screw_control.py"
RESET = "rl_unscrew/rl_gazebo_sim/srv/reset_robot.py"
URDF = "rl_unscrew/rl_gazebo_sim/ur5_robot_w_tool/ur5_robot_w_tool.urdf"


class Ur5Unscrewing(GymnasiumDriver):
    device_id = "ur5-unscrewing"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    env_id = "gym_unscrewing_env-v0"
    native = "rl_gym.envs:UnscrewingEnv"
    backends = {"fake": ".fake:FakeUr5RosGym"}
    #: The fake copies the upstream ``spaces.Discrete(7)`` from the environment constructor.
    action_space_ref = f"{ENV}:39"
    display_name = "UR5 unscrewing Gym environment over ROS/Gazebo"
    vendor, model = "geonhee-lee", "ur5_ros_gym (gym_unscrewing_env-v0)"
    tags = ["ur5", "gym", "reinforcement-learning", "unscrewing", "ros", "gazebo", "moveit", "simulation"]
    facts = [
        Fact("The package registers the Gym environment id gym_unscrewing_env-v0 with entry point "
             "rl_gym.envs:UnscrewingEnv", source="upstream_code", ref=f"{REGISTRY}:3-6"),
        Fact("rl_gym.envs imports UnscrewingEnv from rl_gym.envs.unscrewing_env", source="upstream_code",
             ref="rl_unscrew/rl-gym/rl_gym/envs/__init__.py:1"),
        Fact("UnscrewingEnv subclasses gym.Env", source="upstream_code", ref=f"{ENV}:14"),
        Fact("The constructor initializes the anonymous ROS node Env_setup_node, creates a std_msgs/Int8 "
             "publisher on /action_move, and creates a Trigger service proxy for /reset_robot",
             source="upstream_code", ref=f"{ENV}:21-32"),
        Fact("The constructor sets boundaries x_low 0.478915, x_high 0.521085, y_low -0.021225, y_high "
             "0.021225, z_low 0.02 and z_high 0.04", source="upstream_code", ref=f"{ENV}:36"),
        Fact("The action space is spaces.Discrete(7), commented as x+, x-, y+, y-, z+, z-, unscrewing",
             source="upstream_code", ref=f"{ENV}:39"),
        Fact("The constructor calls _seed(), which seeds self.np_random through gym.utils.seeding",
             source="upstream_code", ref=f"{ENV}:44-59"),
        Fact("step waits for a /curr_pose geometry_msgs/PoseStamped message with timeout 10, calling "
             "rospy.sleep(10) and retrying after each failure, publishes the action with action_pub, calls "
             "rospy.sleep(0.25) (the comment says a delay of 0.5s is needed), reads the state with "
             "get_state(current_pose, 0) and passes the pose read before publishing to is_done",
             source="upstream_code", ref=f"{ENV}:72-89"),
        Fact("When the episode is not done, step sets screw_touch_state when state['z'] < 0.0295 and gives "
             "reward 2 when state['force_z'] < 0 and the action is 6, otherwise reward 0",
             source="upstream_code", ref=f"{ENV}:93-101"),
        Fact("When the episode is done, step gives reward -10 if out_of_bounds(current_pose) is True, otherwise "
             "30 + 3000 * z after a screw touch or 10 + 1.5 / z without one", source="upstream_code",
             ref=f"{ENV}:103-113"),
        Fact("step returns the legacy four-tuple (state, reward, done, {})", source="upstream_code",
             ref=f"{ENV}:116"),
        Fact("out_of_bounds returns True when the pose is within 0.0001 of a boundary or beyond it: x above "
             "x_high - 0.0001, x below x_low + 0.0001, and the same margin for y and z",
             source="upstream_code", ref=f"{ENV}:119-148"),
        Fact("get_state reads /curr_pose (when pos_state is 0), /FTsensor_topic (geometry_msgs/WrenchStamped, using "
             "wrench.force.z) and /screw_joint_value (std_msgs/Float32, using data), each with timeout 1 inside "
             "a loop that retries until a message arrives, and discretises the five values",
             source="upstream_code", ref=f"{ENV}:171-224"),
        Fact("discretise_data rounds x, y and z to four decimals, force_z to one decimal and "
             "screw_joint_value to three decimals", source="upstream_code", ref=f"{ENV}:151-168"),
        Fact("is_done is True when force_z is less than -10 or out_of_bounds(current_pose) is True for the "
             "pose it is given", source="upstream_code", ref=f"{ENV}:227-244"),
        Fact("reset clears screw_touch_state, calls the /reset_robot Trigger service until a call raises no "
             "exception (rospy.sleep(10) after each failure) without reading the response's success field, "
             "sleeps 1 s, waits for /curr_pose with timeout 1 and calls rospy.sleep(10000) after each failed "
             "wait, and returns get_state(current_pose, 0)", source="upstream_code", ref=f"{ENV}:247-286"),
        Fact("planning_script's move_action adds or subtracts step_size 0.0005 to the x, y or z of "
             "group.get_current_pose() for actions 0 to 5 (0/1 x, 2/3 y, 4/5 z) and calls move",
             source="upstream_code", ref=f"{MOVEIT}:34-76"),
        Fact("planning_script's move sets the pose target, plans and executes with group.go(wait=True) "
             "without reading its result", source="upstream_code", ref=f"{MOVEIT}:81-100"),
        Fact("planning_script uses the MoveGroupCommander arm and subscribes move_action to action_move "
             "(std_msgs/Int8)", source="upstream_code", ref=f"{MOVEIT}:116-128"),
        Fact("screw_control's move_action adds step_size -0.25 to the first value of "
             "group.get_current_joint_values() for action 6 and calls move", source="upstream_code",
             ref=f"{SCREW}:34-57"),
        Fact("The /curr_pose publisher publishes group.get_current_pose() as geometry_msgs/PoseStamped in a "
             "loop without a sleep, printing each pose", source="upstream_code",
             ref="rl_unscrew/rl_moveit/script/current_pose_publisher.py:28-39"),
        Fact("The /screw_joint_value publisher publishes the first value of group.get_current_joint_values() "
             "as std_msgs/Float32 in a loop without a sleep", source="upstream_code",
             ref="rl_unscrew/rl_moveit/script/current_screw_joint_publisher.py:28-39"),
        Fact("The Gazebo FT sensor plugin publishes on FTsensor_topic at updateRate 100.0 with gaussianNoise "
             "0.0 for the ft_sensor_drill_joint", source="upstream_code", ref=f"{URDF}:357-364"),
        Fact("RobotReset uses the MoveGroupCommander arm, creates service proxies for /gazebo/reset_world, "
             "/gazebo/reset_simulation and /gazebo/unpause_physics, and advertises reset_robot as a Trigger "
             "service", source="upstream_code", ref=f"{RESET}:24-68"),
        Fact("The reset_robot handler sets a fixed joint target, plans, executes with group.go(wait=True) "
             "without reading its result, sleeps 0.1 s, calls reset_world_srv and returns [True, 'succeded "
             "resetting the robot.']", source="upstream_code", ref=f"{RESET}:74-119"),
        Fact("rl_world.launch starts gazebo_ros empty_world.launch with paused defaulting to false, spawns "
             "the arm_controller and screw_controller and starts reset_robot.py",
             source="upstream_code", ref="rl_unscrew/rl_gazebo_sim/launch/rl_world.launch:13-56"),
        Fact("moveit_planning_execution.launch starts current_pose_publisher.py, planning_script.py, "
             "screw_control.py and current_screw_joint_publisher.py", source="upstream_code",
             ref="rl_unscrew/rl_moveit_config/launch/moveit_planning_execution.launch:26-35"),
        Fact("The MoveIt controller list of rl_moveit_config names arm_controller and screw_controller with "
             "action namespace follow_joint_trajectory", source="upstream_code",
             ref="rl_unscrew/rl_moveit_config/config/controllers.yaml:1-18"),
        Fact("The vendored ur_driver package describes itself as a driver for the UR5/10 arm based on the "
             "Polyscope control scheme", source="upstream_code", ref="universal_robot/ur_driver/package.xml:5-7"),
        Fact("ur_driver creates an actionlib ActionServer named follow_joint_trajectory for "
             "FollowJointTrajectoryAction", source="upstream_code",
             ref="universal_robot/ur_driver/src/ur_driver/driver.py:649-651"),
        Fact("Screwdriver.ino subscribes to std_msgs/Int8 on screwdriver and writes 255 to pin 9 for a value "
             "above 1, otherwise 0", source="upstream_code", ref="rl_unscrew/Screwdriver/Screwdriver.ino:34-41"),
        Fact("The README installation instructions target ROS Kinetic and gym ==0.10.5 and launch the Gazebo "
             "world, the MoveIt planning execution and the example script", source="vendor_doc",
             ref="rl_unscrew/README.md:14-43"),
    ]
    safe_state = ("Software latch only: the runtime refuses every step, reset and seed until mhs.safety.reset and "
                  "the fake stops advancing with its last observation readable; nothing upstream is called, so a "
                  "live Gazebo world, which this package never drives and rl_world.launch starts unpaused, keeps "
                  "running, and MoveIt still plans and executes an action already published on /action_move with "
                  "go(wait=True), which nothing cancels")
    #: The fake is an F0 analytic stand-in: one step is one environment transition, with no ROS, Gazebo,
    #: MoveIt, UR5 model, physics, force sensor or wall-clock pacing.  The upstream environment itself is
    #: only a legacy Gym wrapper around a live ROS/Gazebo/MoveIt stack.
    fidelity = {
        "engine": "analytic:legacy-gym UR5 unscrewing stand-in (no Gazebo, MoveIt or ROS)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "the fake's transition is fixed Python arithmetic with no random source; the bridge's "
                     "seed endpoint records a seed for the next reset, but the upstream reset has no seed "
                     "parameter and the environment's seeded np_random generator is never used, so the seed "
                     "has no effect on either the fake or the served environment",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a pure-Python analytic stand-in: it loads no ROS, Gazebo, MoveIt, UR5 model, "
            "controller, force sensor, plugin, contact physics or wall-clock loop, and it models no dynamics",
            "the upstream environment is a ROS client: the constructor calls rospy.init_node and creates the "
            "/action_move publisher and /reset_robot service proxy, step waits on /curr_pose and publishes "
            "the action, get_state waits on /curr_pose, /FTsensor_topic and /screw_joint_value, and reset "
            "calls the Trigger service (rl_unscrew/rl-gym/rl_gym/envs/unscrewing_env.py:21-32, 72-88, "
            "171-224, 247-286); the fake performs none of these ROS operations",
            "the upstream step has unbounded retry loops: /curr_pose is waited for with a 10 s timeout and "
            "then a 10 s sleep, /FTsensor_topic and /screw_joint_value have 1 s timeouts inside while loops, "
            "and reset retries the service forever (rl_unscrew/rl-gym/rl_gym/envs/unscrewing_env.py:74-79, "
            "190-215, 261-283); the fake returns immediately",
            "timestep_ms is 0 because the environment declares no physics timestep: the 0.25 s rospy.sleep "
            "after publishing is a ROS-time wait (simulated time when use_sim_time is set), not a simulated "
            "step, while the upstream comment says MoveIt needs 0.5 s (rl_unscrew/rl-gym/rl_gym/envs/"
            "unscrewing_env.py:84-85) and the MoveIt subscriber executes with go(wait=True), so the next state "
            "can be read before the motion ends; the Gazebo physics period is not declared in the clone",
            "the fake's start pose, force values and screw-joint value are placeholders; the pose increments "
            "copy the MoveIt step sizes 0.0005 m and -0.25 rad as test data, not as limits, and the force "
            "model is a placeholder counter, not a contact or wrench model",
            "the fake follows the upstream terminal rules (force_z < -10 or the previous pose out of bounds, "
            "rl_unscrew/rl-gym/rl_gym/envs/unscrewing_env.py:227-244) and reward rules (:93-113), but the "
            "previous-pose lag and the force-dependent outcome cannot match the unrun Gazebo scene",
            "the real simulator path gym.make('gym_unscrewing_env-v0') was not run: it needs ROS 1 Kinetic, "
            "Gazebo, MoveIt, the workspace packages and gym==0.10.5 (rl_unscrew/README.md:14-43), none of "
            "which exists where the gate runs or is installed by this package",
            "the seed endpoint is accepted and recorded for the next reset but does not change the "
            "deterministic fake or the upstream reset, which always calls the reset service",
            "snapshot and restore are not offered: the environment has no get_state/set_state checkpoint "
            "protocol, and its get_state method only reads ROS topics",
            "no upstream simulator, ROS graph or hardware was contacted; the package is contract-checked on "
            "the fake only and makes no live-run or hardware claim",
            "a reset proves nothing upstream: reset never reads the Trigger response's success, and the "
            "reset_robot handler returns success unconditionally after a go(wait=True) whose result it ignores "
            "(rl_unscrew/rl_gazebo_sim/srv/reset_robot.py:105-119); a failed /curr_pose wait in reset sleeps "
            "10000 s (rl_unscrew/rl-gym/rl_gym/envs/unscrewing_env.py:276-283)",
            "live construction in the server process would call the global rospy.init_node, and step, reset "
            "and get_state print progress and error lines to standard output (rl_unscrew/rl-gym/rl_gym/envs/"
            "unscrewing_env.py:79, 195-215, 257-283), which would corrupt an MHS server speaking over stdio",
            "the clone also ships a real-robot path that this package does not cover: the vendored ROS-Industrial "
            "ur_driver serves follow_joint_trajectory for a real UR arm, visual-pushing-grasping/robot.py drives "
            "a real UR5 over TCP sockets, and Screwdriver.ino switches a real screwdriver on the screwdriver "
            "topic; as shipped the environment's MoveIt configuration sends trajectories to the Gazebo "
            "arm_controller and screw_controller, so only a remap would move a real arm",
        ],
    }
