"""OpenMHS MuJoCo driver for the bcr_bot small-warehouse scene (gh.blackcoffeerobotics/bcr_bot).

The pinned upstream is a ROS 2 ament package that ships Gazebo, MuJoCo and
Isaac Sim assets for a differential-drive robot.  Its MuJoCo runtime is the
external ``mujoco_ros2_control`` node configured with this package's
``mjcf/small_warehouse.xml`` (``urdf/mujoco_ros2_control.xacro:7``); the clone
does not contain that node or a ROS-to-MuJoCo bridge.

DEVIATION FROM THE CARD: the card names ``RosDriver``, but every ROS endpoint
in the clone is a launch/bridge configuration for a simulator runtime that is
outside the clone.  The card's own candidate classes are ``cap.world.step.v1``,
``cap.world.reset.v1`` and ``cap.world.seed.v1``, and its mock strategy prefers
the upstream simulator.  This package therefore serves the shipped MJCF scene
directly through :class:`MujocoDriver`: the production path is the upstream
MuJoCo engine loading the same model, not a Python native class and not a ROS
graph.  The ROS command/observation layer (``/bcr_bot/cmd_vel``, odometry,
IMU, LiDAR and cameras) is deliberately NOT COVERED because
``mujoco_ros2_control`` is not in the pinned clone and a topic subscription
would not be the environment-step interface.

The model is read from the read-only clone in place and is never copied into
the package or modified.  The fake backend is a package-local stand-in for the
``mujoco`` module; it parses the same MJCF file for the model shape and its
placeholder integration is not the MuJoCo engine.

Every fact cites the pinned clone at
58b9220f35870bf8543db12f8b457942fa07cac3.  No MuJoCo, ROS graph, simulator or
hardware is contacted by the package.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The configured MuJoCo scene of the ROS 2 control xacro, relative to the pinned clone.
MODEL = "mjcf/small_warehouse.xml"
MODEL_PATH = "../../../../robots/blackcoffeerobotics/bcr_bot/" + MODEL

#: The scene that the package's ROS 2 control hardware plugin is pointed at.
_XACRO_MODEL_REF = "urdf/mujoco_ros2_control.xacro:4-7"

#: The included robot model and its option element.
_ROBOT_REF = "mjcf/bcr_bot.xml:2-5"

#: The base free joint and the two actuated wheel hinges.
_BASE_REF = "mjcf/bcr_bot.xml:26-29"
_WHEEL_JOINTS_REF = "mjcf/bcr_bot.xml:74-88"
_ACTUATORS_REF = "mjcf/bcr_bot.xml:148-153"
_SENSORS_REF = "mjcf/bcr_bot.xml:155-160"

#: The ROS 2 control node and the command remapping, both outside the clone.
_CONTROL_NODE_REF = "launch/mujoco.launch.py:33-54"
_TWIST_STAMPER_REF = "launch/mujoco.launch.py:70-79"
_CONTROLLER_REF = "config/mujoco_controllers.yaml:19-35"


class BcrBotSim(MujocoDriver):
    device_id = "bcr_bot_sim"
    device_kind = "world.sim"
    mode = "simulated"
    # World stepping/reset is isolated simulated state (MHS-004 SAFE-006); no
    # physical mobile-base command is exposed by this package.
    risk = "R0"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    tags = ["mujoco", "mjcf", "simulation", "differential-drive", "mobile-base", "ros2"]
    display_name = "bcr_bot MuJoCo small-warehouse simulation"
    vendor = "blackcoffeerobotics"
    model = "bcr_bot_small_warehouse"
    facts = [
        Fact("The repository contains Gazebo, MuJoCo and Isaac Sim simulations for a differential-drive "
             "robot equipped with an IMU, a depth camera, a stereo camera and a 2D LiDAR.",
             source="vendor_doc", ref="README.md:7"),
        Fact("The MuJoCo launch starts the robot in the MuJoCo warehouse and enables wheel control, odometry, "
             "IMU, 2D LiDAR, the depth camera and stereo cameras.",
             source="vendor_doc", ref="README.md:112-118"),
        Fact("The MuJoCo ROS 2 control xacro declares the MujocoSystem hardware plugin "
             "mujoco_ros2_control/MujocoSystemInterface and sets its mujoco_model parameter to "
             "$(find bcr_bot)/mjcf/small_warehouse.xml.",
             source="upstream_code", ref=_XACRO_MODEL_REF),
        Fact("The configured scene is mjcf/small_warehouse.xml, an MJCF model named bcr_bot_small_warehouse "
             "that includes bcr_bot.xml.",
             source="upstream_code", ref="mjcf/small_warehouse.xml:2-3"),
        Fact("The included bcr_bot.xml model compiles angles in radians, points meshdir and texturedir at "
             "../meshes, and sets option timestep 0.002 s with gravity 0 0 -9.81.",
             source="upstream_code", ref=_ROBOT_REF),
        Fact("The robot model starts with a base_footprint body carrying a freejoint named "
             "base_footprint_joint.",
             source="upstream_code", ref=_BASE_REF),
        Fact("The middle_left_wheel and middle_right_wheel bodies each carry a hinge joint on axis 0 1 0 and "
             "a cylinder collision geom of size 0.1 0.025.",
             source="upstream_code", ref=_WHEEL_JOINTS_REF),
        Fact("The actuator block has two velocity actuators, one for each middle wheel joint, with kv=100 and "
             "a forcerange of -20000 to 20000; neither actuator element declares a ctrlrange.",
             source="upstream_code", ref=_ACTUATORS_REF),
        Fact("The model declares a framequat sensor, a gyro and an accelerometer at imu_site and a rangefinder "
             "at two_d_lidar_ray.",
             source="upstream_code", ref=_SENSORS_REF),
        Fact("The MuJoCo launch starts the mujoco_ros2_control package's ros2_control_node with "
             "config/mujoco_controllers.yaml as its parameter file.",
             source="upstream_code", ref=_CONTROL_NODE_REF),
        Fact("The MuJoCo launch starts the twist_stamper package's twist_stamper as bcr_bot_twist_stamper with "
             "cmd_vel_in remapped to /bcr_bot/cmd_vel and cmd_vel_out to /bcr_bot/cmd_vel_stamped.",
             source="upstream_code", ref=_TWIST_STAMPER_REF),
        Fact("The diff_drive_controller configuration names the two middle wheel joints and sets "
             "wheel_separation 0.64, wheel_radius 0.11, publish_rate 30.0 and cmd_vel_timeout 0.5.",
             source="upstream_code", ref=_CONTROLLER_REF),
        Fact("CMakeLists.txt installs the launch, meshes, models, urdf, worlds, rviz, config and mjcf "
             "directories into the package share.",
             source="upstream_code", ref="CMakeLists.txt:6-7"),
        Fact("The empty_world.xml scene declares the model bcr_bot_empty_world and includes bcr_bot.xml.",
             source="upstream_code", ref="mjcf/empty_world.xml:2-3"),
    ]
    safe_state = (
        "The simulation stops advancing: after an e-stop no cap.world.step.v1 or cap.world.reset.v1 call is "
        "accepted until mhs.safety.reset clears the latch, while the integration state stays readable."
    )
    #: The deployed fake is an analytic stand-in for the mujoco module and runs
    #: no MuJoCo physics.  The real sim backend loads the same MJCF in MuJoCo.
    fidelity = {
        "engine": "mujoco:bcr_bot_small_warehouse",
        "fidelity_level": "F1",
        "gaps": [
            "contact, friction, inertia, tendon, equality and actuator force limits are those of the model "
            "file and are not validated against a physical robot",
            "no camera, LiDAR, IMU or point-cloud stream is exposed by the world-step package",
            "the ROS 2 control layer (mujoco_ros2_control, diff_drive_controller, twist_stamper) is outside "
            "the pinned clone and is not reproduced or validated here",
        ],
    }
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:MuJoCo API stand-in (no MuJoCo engine)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "none",
                "notes": "Event-driven placeholder integration with no contact, constraint or force solver; "
                         "the same control input reproduces the same placeholder state hash, but this "
                         "is a stand-in digest, not a MuJoCo trajectory or state-hash replay",
            },
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": True,
            "gaps": [
                "the fake is a package-local stand-in for the mujoco module: it parses the MJCF and its "
                "includes for model shape, actuator names and option timestep, but it does not load meshes, "
                "textures, inertias or contacts and runs no MuJoCo physics",
                "each velocity actuator is modelled as a placeholder joint-velocity command; the two wheel "
                "hinges turn, but the free base, gravity, contacts, friction and the model's force limits are "
                "not integrated",
                "the snapshot uses the bridge's basic profile (time, qpos, qvel, act and ctrl) because the "
                "stand-in exposes no full integration-state API; warm-start and derived quantities are not "
                "preserved",
                "the published timestep_ms is read from the model's option element, but the fake's state "
                "advance is a placeholder and does not establish MuJoCo timing or determinism",
                "the upstream ROS 2 control graph, sensor streams, camera rendering, Nav2 and SLAM are NOT "
                "COVERED",
            ],
        },
        "sim": {
            "engine": "mujoco:bcr_bot_small_warehouse",
            "fidelity_level": "F1",
            "determinism": {
                "kind": "none",
                "notes": "The bridge does not claim seeded or exact continuation: MuJoCo determinism depends "
                         "on the engine version, model, options and any callbacks or plugins",
            },
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": True,
            "gaps": [
                "the real sim backend was not run: MuJoCo is not installed here, so no trajectory was "
                "compared with the engine",
                "contact, friction, inertia, force limits and sensor physics are those of the model and are "
                "not validated against a physical robot",
                "the ROS 2 control layer, camera rendering, LiDAR, IMU publication, Nav2 and SLAM are outside "
                "this package",
                "the scene was never compiled by MuJoCo here; its rangefinder names the site two_d_lidar_ray, "
                "which sits inside a replicate block (mjcf/bcr_bot.xml:102-106, 159), so loading needs a MuJoCo "
                "release with replicate support and is unverified",
                "the two velocity actuators declare no ctrlrange (mjcf/bcr_bot.xml:148-153), "
                "so the bridge publishes action.ctrl operator_required: a step that sets it is refused until the site's site-limits.json bounds it, and site-limits.example.json is operator example data, not a model bound; the model's forcerange of -20000 to 20000 limits the "
                "applied actuator force",
            ],
        },
    }
