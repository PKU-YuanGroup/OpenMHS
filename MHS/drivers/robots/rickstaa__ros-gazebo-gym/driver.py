"""OpenMHS driver for gh.rickstaa/ros-gazebo-gym: the PandaReach-v1 Gazebo environment (a Gymnasium family driver).

The card's entry class is ``ros_gazebo_gym.task_envs.panda.panda_reach:PandaReachEnv``, registered as
``PandaReach-v1`` with 500 steps per episode.  A GymnasiumDriver is configuration only: ``env_id`` names the
environment, ``env_kwargs`` selects the shipped effort control, and the bridge derives the whole contract from the
environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values}`` bounded per
element by ``Box(7)`` (the seven arm efforts), ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.

Both backends run in an isolated simulator host (``process_by_backend``, ``mhs.bridge.sim_host``): a child process
that this endpoint starts and owns builds and drives the environment.  The upstream constructor launches roscore,
Gazebo and MoveIt and its ``close`` (like several failure paths) signals a global ROS shutdown and calls
``sys.exit`` (``core/helpers.py:325-339``): in the host those end a call of that process, never the endpoint.  The
e-stop latches and fences the host, then calls the environment's ``gazebo.pause_proxy`` (the
``/gazebo/pause_physics`` service proxy, ``core/gazebo_connection.py:143``) in the host; a step in flight is waited
for and the pause sent again, because a step unpauses the world before it applies its action
(``robot_gazebo_goal_env.py:158``); the stop counts only when ``gazebo.get_physics_properties()`` returns
``pause`` True (``core/gazebo_connection.py:562-580``).  ``pause_sim`` itself is not used: it retries for seconds
and then exits the interpreter, and it returns without pausing once rospy is shut down (``:328-356``).

The ``fake`` backend is the package's own F0 stand-in (fake.py), run in the same host with the same stop and
read-back; the ``sim`` backend (host.py) builds the upstream environment there and is never run by the gate.  Risk
R2: with the shipped direct control the step publishes the seven joint efforts on the
``panda_arm_joint_effort_controller/command`` topic (``robot_envs/panda_env.py:100``, ``:643-657``;
``panda_reach.yaml:7``), a ros_control command topic that a physical Panda's control stack could also serve
(REVIEW.md item 12); the pause is a simulator-only service.

What the pause and its read-back do in the simulator is cited from a reviewed companion source (``task.json``
``companions``; integrator v4, 2026-11-05): gazebo_ros 2.9.3, the ROS 1 Noetic release the clone's CI image carries,
at its corpus pin cd9cc952 (``companion:gazebo_ros_pkgs/<path>:<LINE>``).  Its API plugin, node ``gazebo``, serves
``pause_physics`` (``World::SetPaused(true)``) and ``get_physics_properties`` (``pause`` is ``IsPaused()``; success
only with the ODE engine, which the shipped config selects) in its private namespace.  What a paused Gazebo world
still runs is Gazebo classic's and is not cited here.

The ``fidelity`` attribute is the complete fidelity contract of the deployed fake (spec 05-fidelity FID-002).  Source-derived
interface claims and action bounds cite the clone at the pinned commit (157981585c26e7d252bc10e4deb527ca450775a0).  The
package is model-authored and unreviewed: it is checked on the fake backend only, and fake evidence establishes no
real ROS or hardware run.
"""

from mhs.driver import Fact, GymnasiumDriver

PANDA = "src/ros_gazebo_gym/task_envs/panda/panda_reach.py"
CONFIG = "src/ros_gazebo_gym/task_envs/panda/config/panda_reach.yaml"
REGISTRY = "src/ros_gazebo_gym/task_envs/task_envs_list.py"
GOAL_ENV = "src/ros_gazebo_gym/robot_gazebo_goal_env.py"
PANDA_ENV = "src/ros_gazebo_gym/robot_envs/panda_env.py"
GAZEBO = "src/ros_gazebo_gym/core/gazebo_connection.py"
HELPERS = "src/ros_gazebo_gym/core/helpers.py"
#: The reviewed companion source (task.json companions; integrator v4, 2026-11-05): gazebo_ros 2.9.3 (ROS 1 Noetic) at
#: cd9cc952, whose API plugin serves the pause and its read-back.
_API = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
LAUNCHER = "src/ros_gazebo_gym/core/ros_launcher.py"

#: The stop, the read-back and the reset signature of both backends (isolated_process_v1).
_HOST = {
    "mode": "isolated_process_v1",
    "reset_kwargs": ["seed", "options"],
    "stop": "gazebo.pause_proxy",
    "readback": {"path": "gazebo.get_physics_properties", "field": "pause", "equals": True},
    "source_refs": [f"{GAZEBO}:136-148", f"{GAZEBO}:328-356", f"{GAZEBO}:562-580", f"{GAZEBO}:805-808",
                    f"{GOAL_ENV}:83", f"{GOAL_ENV}:157-163", f"{GOAL_ENV}:200-227"],
}


class PandaReach(GymnasiumDriver):
    device_id = "panda-reach"
    env_id = "PandaReach-v1"
    env_kwargs = {"control_type": "effort"}
    native = "ros_gazebo_gym.task_envs.panda.panda_reach:PandaReachEnv"
    backends = {"fake": ".fake:FakePandaReachEnv", "sim": ".host:make_env"}
    #: The bounds are package choices, not upstream numbers: the live bounds leave room for a Gazebo and MoveIt start,
    #: an effort step that waits for the controllers and a reset that re-plans the initial pose; the fake's are short.
    process_by_backend = {
        "fake": {**_HOST, "start_timeout_s": 60.0, "step_timeout_s": 10.0, "reset_timeout_s": 10.0,
                 "close_timeout_s": 10.0, "stop_timeout_s": 2.0, "settle_timeout_s": 10.0},
        "sim": {**_HOST, "start_timeout_s": 900.0, "step_timeout_s": 60.0, "reset_timeout_s": 300.0,
                "close_timeout_s": 60.0, "stop_timeout_s": 5.0, "settle_timeout_s": 60.0},
    }
    #: A joint-effort command on a ros_control command topic is a limb command (REVIEW.md item 12): R2, although the
    #: environment drives a simulated Panda; the card floor is R0.
    risk = "R2"
    action_space_ref = f"{CONFIG}:211-226"
    display_name = "ROS Gazebo Gym PandaReach-v1 (Franka Panda reach, simulated)"
    vendor, model = "Rick Staa", "PandaReach-v1"
    tags = ["panda", "franka", "robot-arm", "reach", "gazebo", "ros", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("PandaReach-v1 is registered with entry point "
             "ros_gazebo_gym.task_envs.panda.panda_reach:PandaReachEnv and max_steps 500",
             source="upstream_code", ref=f"{REGISTRY}:21-24"),
        Fact("The PandaReachEnv constructor defaults control_type to 'effort'", source="upstream_code",
             ref=f"{PANDA}:198-207"),
        Fact("The shipped panda_reach.yaml sets load_gripper False and lists the seven panda_joint values under "
             "controlled_joints", source="upstream_code", ref=f"{CONFIG}:10-33"),
        Fact("The shipped effort bounds are -87 to 87 for panda_joint1 through panda_joint4 and -12 to 12 for "
             "panda_joint5 through panda_joint7", source="upstream_code", ref=f"{CONFIG}:209-227"),
        Fact("The action space is a Box built from the bounds of the configured control type, ordered by the "
             "action-space joints", source="upstream_code", ref=f"{PANDA}:1157-1232"),
        Fact("The observation space is a Dict of observation, desired_goal and achieved_goal, each an unbounded Box "
             "shaped from a sample observation", source="upstream_code", ref=f"{PANDA}:521-542"),
        Fact("The observation member concatenates the end-effector position with the finger joint positions and "
             "velocities selected by the panda_finger name", source="upstream_code", ref=f"{PANDA}:1345-1379"),
        Fact("The shipped panda_reach.yaml selects the dense reward type", source="upstream_code",
             ref=f"{CONFIG}:159"),
        Fact("The non-sparse reward subtracts the goal distance and any enabled collision penalty, then uses its "
             "absolute value when positive_reward is true", source="upstream_code", ref=f"{PANDA}:1295-1325"),
        Fact("The episode terminates when the goal distance is below distance_threshold, and with target_hold it "
             "requires hold_samples consecutive samples", source="upstream_code", ref=f"{PANDA}:1470-1488"),
        Fact("The shipped config sets target_hold True, hold_samples 2 and distance_threshold 0.05",
             source="upstream_code", ref=f"{CONFIG}:160-162"),
        Fact("A global target is drawn uniformly from the target sampling bounds of the environment's numpy "
             "generator", source="upstream_code", ref=f"{PANDA}:1504-1517"),
        Fact("The shipped global target bounds are x 0.1 to 0.8, y -0.4 to 0.4 and z 0.1 to 1.0",
             source="upstream_code", ref=f"{CONFIG}:139-146"),
        Fact("The info dictionary returns reference, state_of_interest and reference_error", source="upstream_code",
             ref=f"{PANDA}:1381-1398"),
        Fact("reset() calls the parent gymnasium reset with the seed, resets the simulation and then re-initialises "
             "the episode variables", source="upstream_code", ref=f"{GOAL_ENV}:200-227"),
        Fact("The shipped panda_reach.yaml sets random_init_pose True", source="upstream_code",
             ref=f"{CONFIG}:64"),
        Fact("In the random end-effector sampling branch, reset calls _get_random_ee_pose when first-episode "
             "randomization is enabled or episode_num is not zero", source="upstream_code", ref=f"{PANDA}:1602-1637"),
        Fact("The shipped config pauses the simulation after every step", source="upstream_code",
             ref=f"{CONFIG}:169"),
        Fact("The shipped config selects the ODE physics engine", source="upstream_code",
             ref=f"{CONFIG}:232"),
        Fact("The upstream close() calls ros_exit_gracefully with exit code 0", source="upstream_code",
             ref=f"{GOAL_ENV}:229-236"),
        Fact("ros_exit_gracefully signals ROS shutdown and exits the interpreter", source="upstream_code",
             ref=f"{HELPERS}:325-339"),
        Fact("The environment keeps its GazeboConnection as the gazebo attribute", source="upstream_code",
             ref=f"{GOAL_ENV}:83"),
        Fact("GAZEBO_PAUSE_PHYSICS_TOPIC is /gazebo/pause_physics", source="upstream_code", ref=f"{GAZEBO}:50"),
        Fact("GazeboConnection's constructor creates pause_proxy, a rospy ServiceProxy of GAZEBO_PAUSE_PHYSICS_TOPIC "
             "with the std_srvs Empty type", source="upstream_code", ref=f"{GAZEBO}:136-148"),
        Fact("pause_sim() calls pause_proxy in a retry loop that stops once rospy is shut down and calls "
             "ros_exit_gracefully after max_retry failures", source="upstream_code", ref=f"{GAZEBO}:328-356"),
        Fact("get_physics_properties() returns the physics_properties response and raises "
             "GetPhysicsPropertiesError when its success field is false", source="upstream_code",
             ref=f"{GAZEBO}:562-580"),
        Fact("The physics_properties property calls the get_physics_proxy service proxy", source="upstream_code",
             ref=f"{GAZEBO}:805-808"),
        Fact("get_physics_proxy is a rospy ServiceProxy of GAZEBO_GET_PHYSICS_PROPERTIES_TOPIC with the "
             "GetPhysicsProperties type", source="upstream_code", ref=f"{GAZEBO}:286-288"),
        Fact("GAZEBO_GET_PHYSICS_PROPERTIES_TOPIC is /gazebo/get_physics_properties", source="upstream_code",
             ref=f"{GAZEBO}:63"),
        Fact("The environment constructor ends by unpausing the simulation", source="upstream_code",
             ref=f"{GOAL_ENV}:125-128"),
        Fact("step() unpauses the simulation before it applies the action and pauses it after the observation only "
             "when pause_simulation is set", source="upstream_code", ref=f"{GOAL_ENV}:157-163"),
        Fact("reset() pauses the simulation at its end when pause_simulation is set", source="upstream_code",
             ref=f"{GOAL_ENV}:221-223"),
        Fact("PandaEnv passes pause_after_step on as pause_simulation", source="upstream_code",
             ref=f"{PANDA_ENV}:336-344"),
        Fact("The shipped config sets direct_control True: arm commands are published on the controller command "
             "topics", source="upstream_code", ref=f"{CONFIG}:7"),
        Fact("With direct control the arm effort commands are published as Float64MultiArray on the command topic "
             "of ARM_EFFORT_CONTROLLER", source="upstream_code", ref=f"{PANDA_ENV}:643-657"),
        Fact("ARM_EFFORT_CONTROLLER is panda_arm_joint_effort_controller", source="upstream_code",
             ref=f"{PANDA_ENV}:100"),
        Fact("_set_action calls ros_exit_gracefully when the action shape differs from the action space shape",
             source="upstream_code", ref=f"{PANDA}:1406-1413"),
        Fact("The constructor calls ros_exit_gracefully when a Gazebo instance is already running",
             source="upstream_code", ref=f"{PANDA}:280-289"),
        Fact("ROSLauncher.initialize starts roscore in a subprocess when no ROS master is online",
             source="upstream_code", ref=f"{LAUNCHER}:37-43"),
        Fact("The constructor launches the panda_gazebo world launch file with paused set through ROSLauncher.launch",
             source="upstream_code", ref=f"{PANDA}:307-317"),
        Fact("ROSLauncher.launch installs a missing launch package and its dependencies before launching it",
             source="upstream_code", ref=f"{LAUNCHER}:133-139"),
        Fact("The launch command runs in a PopenAutoCleanup subprocess through /bin/bash with shell=True",
             source="upstream_code", ref=f"{LAUNCHER}:176-184"),
        Fact("PopenAutoCleanup registers its process cleanup with atexit", source="upstream_code",
             ref=f"{HELPERS}:74"),
        Fact("The cleanup terminates the launched process's children and then the process", source="upstream_code",
             ref=f"{HELPERS}:88-107"),
        Fact("install_package clones a missing dependency into the workspace from the dependency index",
             source="upstream_code", ref=f"{HELPERS}:550-562"),
        Fact("is_repo_up_to_date fetches the repository's origin remote", source="upstream_code",
             ref=f"{HELPERS}:314"),
        Fact("Rebuilding the workspace asks whether to install the ROS system dependencies and runs sudo rosdep "
             "install only when the answer is yes", source="upstream_code", ref=f"{HELPERS}:358-377"),
        # The companion gazebo_ros 2.9.3 (task.json companions; integrator v4, 2026-11-05).
        Fact("The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet.",
             source="upstream_code", ref=_API + ":125-126"),
        Fact("The API plugin creates its node handle in the private namespace ~ and advertises its topics and services "
             "there.", source="upstream_code", ref=_API + ":145"),
        Fact("The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback "
             "queue gazebo_queue_.", source="upstream_code", ref=_API + ":492-498"),
        Fact("The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties "
             "type on gazebo_queue_.", source="upstream_code", ref=_API + ":383-389"),
        Fact("pausePhysics calls world_->SetPaused(true) and returns true.", source="upstream_code",
             ref=_API + ":1725-1729"),
        Fact("getPhysicsProperties sets res.pause to world_->IsPaused().", source="upstream_code", ref=_API + ":1489"),
        Fact("getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it "
             "sets success false and returns false.", source="upstream_code", ref=_API + ":1496-1528"),
        Fact("The GetPhysicsProperties response field pause is true if the physics engine is paused.",
             source="upstream_code", ref="companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4"),
    ]
    safe_state = ("the Gazebo world paused by /gazebo/pause_physics in the isolated host and confirmed by "
                  "get_physics_properties pause True; the endpoint latch and the host fence refuse every step and "
                  "reset; the controllers keep their last effort command, which acts again when a later step "
                  "unpauses the world; another ROS client or the Gazebo GUI can unpause it. A host that is dead, "
                  "unresponsive or not confirming is SAFE_STATE_UNREACHED")
    #: The fidelity contract of the package fake (the backend the acceptance gate opens).  The bridge derives the
    #: engine, determinism kind and lockstep clock; they are written out so the whole contract reads in one place.
    fidelity_level = "F0"
    fidelity = {
        "engine": "ros_gazebo_gym:PandaReach-v1",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "parameter",
            "notes": "a seed repeats the fake's initial pose and goal, but reset preserves the source-shaped "
                     "target-hold counter, so terminal results can depend on prior history; no whole-episode replay "
                     "equality is claimed. Upstream additionally samples the initial pose through unseeded MoveIt",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "partial",
        "snapshot_restore": False,
        "gaps": [
            "the upstream simulator was not run: it needs ROS, Gazebo, MoveIt, panda_gazebo and "
            "panda_moveit_planner_server in a catkin workspace, and this package's evidence is fake-only",
            "the fake has no physics timestep, actuator model, sensor model or noise model; no native timing or "
            "dynamics contract has been verified; no wall-clock pacing",
            "the initial end-effector pose is sampled through MoveIt and is not controlled by the gymnasium seed",
            "the fake has no arm, controller, contact or sensor dynamics: it moves a 3-D end-effector position by a "
            "placeholder linear map of the first three effort components and ignores the other four",
            "the fake is an analytic stand-in, not a recording of upstream traffic, and was never compared with a "
            "live Gazebo run",
            "the fake draws its initial pose and goal from Python's random.Random with the shipped sampling bounds, "
            "while upstream uses numpy's generator and MoveIt, so one seed gives different episodes on the two",
            "the fake does not model controller waits, collisions, the gripper or rendering; the shipped "
            "collision_penalty is 0.0 and the shipped config loads no gripper",
            "no snapshot/restore is offered and step() declares no fixed simulated duration",
            "the fake models only the pause state of /gazebo/pause_physics and get_physics_properties; that the real "
            "services set and report the world's paused flag is cited from the companion gazebo_ros 2.9.3, while "
            "what a paused Gazebo world still runs is Gazebo classic's and is not shown by the fake",
            "reset retains the target-hold counter, matching panda_reach.py:1793-1800; an interrupted or truncated "
            "episode with one held sample can change the next episode's terminal result despite the same seed",
            "a running step or reset is never interrupted: the e-stop pauses the world, waits for the call and "
            "pauses again; a step that outlives its bound stays owned and blocks safety reset until it answers",
        ],
    }
    #: Per-backend members: the fake's engine, and the live contract a sim-backend instance publishes at deployment.
    fidelity_by_backend = {
        "fake": {
            "engine": "ros_gazebo_gym:PandaReach-v1 (package fake)",
        },
        "sim": {
            "engine": "ros_gazebo_gym:PandaReach-v1 in Gazebo classic with ODE and MoveIt (isolated simulator host)",
            "fidelity_level": "F1",
            "determinism": {"kind": "none", "seed_control": "parameter",
                            "notes": "the seed reaches numpy goal sampling only; MoveIt samples the initial pose "
                                     "unseeded and Gazebo advances on its own clock while a step runs"},
            "timestep_ms": 0,
            "clock": "free_running",
            "reset": "partial",
            "snapshot_restore": False,
            "gaps": [
                "never run by this package: the deployment needs ROS Noetic, Gazebo, MoveIt and the panda_gazebo and "
                "panda_moveit_planner_server packages in a catkin workspace",
                "the physics timestep and the real-time pacing are set by the panda_gazebo world, outside the clone, "
                "so timestep_ms is 0 and no pacing is declared",
                "between a step's unpause and its pause the world runs on Gazebo's clock for as long as the action "
                "and observation take, so one step is not a fixed simulated duration",
                "contact, controller and actuator fidelity are those of the Gazebo Panda model; none was validated",
                "construction may clone missing ROS packages and fetch their remotes (network); its rosdep step "
                "asks on standard input, which is /dev/null in the host",
                "another ROS client or the Gazebo GUI can pause, unpause or step the world outside this endpoint",
                "processes the environment launched outside the host's process group can survive a host that had "
                "to be killed after its close bound",
            ],
        },
    }
