"""OpenMHS MuJoCo driver for gh.geo-jtao/unitree_robot_sim: the B2 MJCF scene.

The pin is a collection of ROS 1 Gazebo simulation packages and robot
description assets.  Its README describes mapping and navigation for Unitree
quadruped robots in Gazebo, while the B2 MuJoCo subdirectory ships a standalone
MJCF scene and instructs the user to run ``simulate ./xml/scene.xml``.

The card names a ``RosDriver`` (family ``ros``).  The card's own candidate
classes are ``cap.world.reset.v1``, ``cap.world.step.v1`` and
``cap.world.seed.v1``; its models are MJCF scenes and its mock strategy prefers
the upstream simulator.  The ROS 1 side exposes joint command/state topics and
a Gazebo runtime, not world reset/step services owned by this clone, and no
Python environment object exists.  DEVIATION FROM THE CARD: this package serves
the B2 MJCF scene through :class:`MujocoDriver` instead of declaring a ROS
transport.  The production path is the official MuJoCo engine loading the same
read-only file.  The ROS graph, the ``unitree_guide`` controller, mapping,
navigation and SLAM are NOT COVERED by this world-step package.

``cap.world.step.v1`` writes ``data.ctrl`` (checked per actuator against the
model's ``actuator_ctrlrange``) and runs ``mj_step`` for each tick.
``cap.world.reset.v1`` runs ``mj_resetData`` + ``mj_forward`` and restores the
model defaults.  The world state is the bridge's integration state (``time_ms``,
``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed`` and the
native checkpoint).  ``cap.world.seed.v1`` is not served by the MuJoCo bridge;
the reset ``seed`` input is accepted as class metadata but ``mj_resetData``
does not use it.

MuJoCo is not installed where the acceptance gate runs, so ``backends["fake"]``
is this package's stand-in ``mujoco`` module (``fake.py``).  It parses the same
MJCF scene for the joint shape, qpos0, the twelve actuators and their
ctrlranges, and the option timestep; its integration is a torque-like
placeholder joint update, not MuJoCo physics.  It is not a recording and
replays no captured traffic.
The fidelity gaps below state every difference.  A backend name that
``backends`` does not list (``sim``) would import the real ``mujoco`` module and
load the same file; that path was not run here.

The model is read from the read-only clone in place and is never copied,
modified or imported.  Every Fact cites a line or line range of the clone at
commit 49fb7fa50e0c3b65dd2a07ac4df370ba781858b8.  This package is
model-authored and unreviewed: ``driver.lock.json`` keeps ``reviewed_by`` null,
and no MuJoCo, ROS, Gazebo or hardware run is claimed.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's B2 scene, relative to the package directory: the read-only clone.
SCENE = "src/unitree_ros/robots/b2_description_mujoco/xml/scene.xml"
MODEL = "src/unitree_ros/robots/b2_description_mujoco/xml/b2.xml"
MODEL_PATH = "../../../../robots/geo-jtao/unitree_robot_sim/" + SCENE
README = "README.md"
B2_README = "src/unitree_ros/robots/b2_description_mujoco/README.md"
ROS_README = "src/unitree_ros/README.md"
GUIDE_CMAKE = "src/unitree_guide/unitree_guide/CMakeLists.txt"
ROS_LICENSE = "src/unitree_ros/LICENSE"


class UnitreeB2Scene(MujocoDriver):
    device_id = "unitree-b2"
    device_kind = "world.sim"
    mode = "simulated"
    # Direct world stepping is isolated simulated state; the package exposes no
    # physical mobile-base, actuator or sensor command.
    risk = "R0"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    tags = ["unitree", "b2", "quadruped", "mujoco", "mjcf", "simulation", "ros", "gazebo"]
    display_name = "Unitree B2 MuJoCo scene"
    vendor = "Unitree Robotics (geo-jtao mirror)"
    model = "b2 scene"

    def _model_name(self):
        """Name the included file that actually declares the actuator ctrlranges.

        ``model_path`` loads the scene wrapper (floor and light); the
        ``actuator_ctrlrange`` values this package enforces are in b2.xml.
        """
        return MODEL

    facts = [
        Fact("The project provides a mapping and navigation package for Unitree quadruped robots in Gazebo.",
             source="vendor_doc", ref=f"{README}:2"),
        Fact("The B2 MuJoCo README instructs the user to install mujoco, enter the b2_description_mujoco "
             "directory and run 'simulate ./xml/scene.xml' to open the model.",
             source="vendor_doc", ref=f"{B2_README}:4-6"),
        Fact("The unitree_ros README says its ROS simulation packages load robots and joint controllers in "
             "Gazebo for low-level torque, position and angular-velocity control, and that the Gazebo simulation "
             "cannot do high-level walking.",
             source="vendor_doc", ref=f"{ROS_README}:2"),
        Fact("The selected file is an MJCF scene named 'b2 scene' that includes b2.xml.",
             source="upstream_code", ref=f"{SCENE}:1-2"),
        Fact("The scene adds a directional light and a plane floor geom named floor.",
             source="upstream_code", ref=f"{SCENE}:19-22"),
        Fact("The included B2 model root is named b2 and its compiler element declares radian angles, meshdir "
             "../meshes and autolimits true.", source="upstream_code", ref=f"{MODEL}:1-2"),
        Fact("The B2 default class gives joints damping 1 and armature 0.1.",
             source="upstream_code", ref=f"{MODEL}:7"),
        Fact("The base_link body starts at pos 0 0 0.8 and carries the free joint floating_base_joint.",
             source="upstream_code", ref=f"{MODEL}:52-54"),
        Fact("The FL leg has a hip joint range -0.87 to 0.87 rad, a thigh joint range -0.94 to 4.69 rad and a "
             "calf joint range -2.82 to -0.43 rad; the FR, RL and RR legs declare the same ranges.",
             source="upstream_code", ref=f"{MODEL}:73-156"),
        Fact("The actuator block declares twelve motor actuators: the hip and thigh motors have ctrlrange -200 to "
             "200 and the calf motors have ctrlrange -300 to 300.",
             source="upstream_code", ref=f"{MODEL}:170-182"),
        Fact("The model declares joint position and velocity sensors for the twelve leg joints plus body "
             "quaternion, gyro, accelerometer and frame-position sensors.",
             source="upstream_code", ref=f"{MODEL}:185-216"),
        Fact("The keyframe named home sets a 19-value qpos with the base at 0 0 0.5 and the identity "
             "quaternion, and a 12-value ctrl.",
             source="upstream_code", ref=f"{MODEL}:218-220"),
        Fact("unitree_guide's CMakeLists sets ROBOT_TYPE Go1 (Go1 and A1 supported), SIMULATION ON and "
             "REAL_ROBOT OFF.", source="upstream_code", ref=f"{GUIDE_CMAKE}:4-9"),
        Fact("With REAL_ROBOT on, unitree_guide defines COMPILE_WITH_REAL_ROBOT and, for A1, uses the "
             "unitree_legged_sdk_3.2 headers and libraries.", source="upstream_code", ref=f"{GUIDE_CMAKE}:87-95"),
        Fact("The vendored unitree_ros directory carries the BSD 3-Clause License of HangZhou YuShu Technology "
             "(Unitree Robotics).", source="upstream_code", ref=f"{ROS_LICENSE}:1-3"),
    ]
    safe_state = ("The simulation stops advancing: after an e-stop no cap.world.step.v1 or cap.world.reset.v1 call "
                  "is accepted until mhs.safety.reset clears the latch, while the integration state stays readable.")
    #: The deployed real path would be the official MuJoCo engine loading the
    #: same scene.  It was not installed or run here, so the deployment is
    #: described, not validated.
    fidelity = {
        "engine": "mujoco:b2",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "notes": "The bridge does not claim seeded or exact continuation: MuJoCo determinism depends on the "
                     "engine version, model options, contact state and any callbacks or plugins; this package also "
                     "has no seeded control input.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the real sim backend was not run: mujoco is not installed here, so no trajectory was compared with "
            "the official engine",
            "the scene declares no <option> timestep; 2 ms is the stand-in's placeholder step (and the MuJoCo "
            "library default), not a bound sourced from the clone",
            "the package steps the MJCF directly; the upstream ROS 1 Gazebo runtime (unitree_guide, "
            "unitree_controller, unitree_legged_control), the joint-command topics, mapping, navigation and SLAM "
            "are NOT COVERED",
            "contact, friction, inertia, actuator force limits and sensor physics are those of the model file "
            "and are not validated against a physical B2",
            "the scene resolves mesh files from the clone's meshes directory; the package does not copy or "
            "modify those assets",
            "the world-step package does not publish the model's sensors or a rendered image",
            "reset runs mj_resetData, which restores the model's qpos0 (base at 0 0 0.8 with the identity "
            "quaternion); the keyframe home is not applied, so the robot starts above the floor and falls under "
            "gravity with zero torque",
            "the repository's primary runtime, unitree_guide (Go1 or A1 in Gazebo, or a real robot when "
            "REAL_ROBOT is compiled on), and the other vendored robot descriptions are NOT COVERED",
        ],
    }
    #: The deployed fake is a package-local stand-in for the mujoco module.  It
    #: parses the same scene for model shape, actuator names and ctrlranges, but
    #: runs no MuJoCo physics.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:MuJoCo API stand-in (no MuJoCo engine)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "none",
                "notes": "Event-driven placeholder integration with no contact, constraint or force solver; the "
                         "same control input reproduces the same placeholder state hash, but this is a stand-in "
                         "digest, not a MuJoCo trajectory or state-hash replay.",
            },
            "timestep_ms": 2.0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": True,
            "gaps": [
                "the fake is a package-local stand-in for the mujoco module: it parses the MJCF and its includes "
                "for model shape, actuator names and ctrlranges, but it loads no meshes, textures, inertias or "
                "contacts and runs no MuJoCo physics",
                "each motor's control value accelerates its joint through a placeholder gain against a "
                "placeholder damping (a torque stand-in, not the model's inertia); the free base stays at qpos0, "
                "and gravity, contacts, friction, joint limits and sensor physics are not integrated",
                "reset restores qpos0 parsed from the MJCF (base at 0 0 0.8, identity quaternion, hinges at 0), "
                "as mj_resetData does; the stand-in settles nothing by physics",
                "the snapshot uses the bridge's basic profile (time, qpos, qvel, act and ctrl) because the "
                "stand-in exposes no full integration-state API; warm-start and derived quantities are not "
                "preserved",
                "the upstream ROS 1 graph, Gazebo, unitree_guide, the controllers and the model's sensors are NOT "
                "COVERED",
                "the published timestep_ms is the stand-in's placeholder step; the scene declares no option "
                "timestep, so this value is not a sourced model parameter and does not establish MuJoCo timing or "
                "determinism",
            ],
        },
    }
