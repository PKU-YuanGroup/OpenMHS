"""OpenMHS MuJoCo driver for the AgileX PiPER Isaac Sim description package.

The card is ``family:ros`` with ``RosDriver``, but the pinned clone is a robot-description and asset repository,
not a ROS control runtime.  Its README describes an Isaac Sim workflow (install the NVIDIA driver, Omniverse and
Isaac Sim, then open the USD asset and press play); the ``piper_description`` CMakeLists only installs launch,
mesh, rviz, urdf and ``mujoco_model`` directories and defines no executable; and the manifest declares no message,
service or action.  The display launch starts only ``robot_state_publisher``, ``joint_state_publisher`` and
``rviz2``.  The one controller reference is a ``gazebo_ros2_control`` plugin in the xacro whose parameters live in
``piper_gazebo/config/ros2_controllers.yaml``, a package and file that are not part of this clone.  There is
therefore no pinned ROS endpoint or type to bind.

This package follows the card's shipped MJCF instead: a configuration-only ``MujocoDriver`` over
``piper_description/mujoco_model/piper_description.xml`` (``models[0]``).  ``cap.world.step.v1`` writes
``data.ctrl`` after checking each element against the model's ``actuator_ctrlrange`` and runs ``mj_step``;
``cap.world.reset.v1`` runs ``mj_resetData`` + ``mj_forward``.  The model file and its meshes are read in place from
the read-only clone at commit 8e1f88fdb7afca49c40e9a0c1c01cc588e86f0d2; nothing is copied or imported from it.

MuJoCo is not installed where the acceptance gate runs, so ``backends["fake"]`` is this package's pure Python
stand-in ``mujoco`` module (``fake.py``).  It parses the MJCF for the joint dimensions and the eight position
actuators' control ranges, but its integration is a placeholder first-order motion, not MuJoCo physics.  It
publishes its own F0 contract through ``fidelity_by_backend``; the class-level F1 contract describes the real
engine path, which was not run (reviewer change).  The fidelity ``gaps`` list every difference, including that the
model's ctrlranges are wider than several joint ranges.  This package is model-authored and unreviewed: it is
checked on the fake backend only, no hardware or Isaac Sim run is claimed, and the upstream licence is not stated.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "piper_description/mujoco_model/piper_description.xml"
MODEL_PATH = "../../../../robots/agilexrobotics/piper_isaac_sim/" + MODEL
NO_GRIPPER = "piper_description/mujoco_model/piper_no_gripper_description.xml"
README = "README.md"
CMAKE = "piper_description/CMakeLists.txt"
MANIFEST = "piper_description/package.xml"
DISPLAY_LAUNCH = "piper_description/launch/piper_with_gripper/display_urdf.launch.py"
XACRO = "piper_description/urdf/piper_description.xacro"


class PiperIsaacSim(MujocoDriver):
    device_id = "piper-isaac-sim"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "AgileX PiPER Isaac Sim MJCF"
    vendor, model = "AgileX Robotics", "PiPER"
    tags = ["agilex", "piper", "isaac-sim", "mujoco", "robot", "arm", "description", "simulation"]
    facts = [
        Fact("The README describes an Isaac Sim workflow: install the NVIDIA driver, Omniverse and Isaac Sim, open "
             "the USD asset from the content browser, and press play to start the simulation.",
             source="vendor_doc", ref=f"{README}:3-37"),
        Fact("The piper_description CMakeLists is an ament_cmake description build: it installs the launch, meshes, "
             "rviz, urdf and mujoco_model directories and defines no executable target.",
             source="upstream_code", ref=f"{CMAKE}:1-38"),
        Fact("The piper_description manifest declares ament_cmake with runtime dependencies joint_state_publisher, "
             "joint_state_publisher_gui, rviz2 and xacro; it declares no message, service or action definition.",
             source="upstream_code", ref=f"{MANIFEST}:3-24"),
        Fact("The display launch starts robot_state_publisher, joint_state_publisher (or its GUI) and rviz2, and "
             "starts no controller or command node.", source="upstream_code", ref=f"{DISPLAY_LAUNCH}:23-60"),
        Fact("The xacro adds a gazebo_ros2_control plugin that loads its controller parameters from "
             "piper_gazebo/config/ros2_controllers.yaml; the piper_gazebo package and that file are not part of "
             "this clone.", source="upstream_code", ref=f"{XACRO}:531-535"),
        Fact("The MJCF root declares the model name piper_description and the compiler angle in radians.",
             source="upstream_code", ref=f"{MODEL}:1-2"),
        Fact("The MJCF worldbody is a fixed-base chain of six hinge joints (joint1 to joint6) followed by two slide "
             "joints (joint7 and joint8); it declares no free joint.", source="upstream_code", ref=f"{MODEL}:16-50"),
        Fact("The hinge joint ranges are joint1 -2.618 to 2.168 rad, joint2 0 to 3.14 rad, joint3 -2.967 to 0 rad, "
             "joint4 -1.745 to 1.745 rad, joint5 -1.22 to 1.22 rad and joint6 -2.0944 to 2.0944 rad; the slide "
             "joint ranges are joint7 0 to 0.035 and joint8 -0.035 to 0.", source="upstream_code",
             ref=f"{MODEL}:20-50"),
        Fact("The actuator section declares eight position actuators, joint1 to joint8, and every actuator sets "
             "ctrllimited=true with an explicit ctrlrange; it also sets forcelimited=true and a forcerange.",
             source="upstream_code", ref=f"{MODEL}:60-69"),
        Fact("The MJCF asset section names ten mesh files under ../meshes: base_link, link1 to link8 and gripper_base.",
             source="upstream_code", ref=f"{MODEL}:4-15"),
        Fact("The MJCF contains no <option> element and no timestep attribute.",
             source="upstream_code", ref=f"{MODEL}:1-70"),
        Fact("The actuator ctrlranges are wider than the joint ranges for joint1 (ctrlrange -2.618 to 2.618, range "
             "-2.618 to 2.168), joint4 (-1.832 to 1.832 against -1.745 to 1.745), joint6 (-3.14158 to 3.14158 "
             "against -2.0944 to 2.0944), joint7 (0 to 0.0475 against 0 to 0.035) and joint8 (-0.0475 to 0 against "
             "-0.035 to 0); joint2's ctrlrange ends at 3.14158 and its range at 3.14.",
             source="upstream_code", ref=f"{MODEL}:20-68"),
        Fact("The card's second model, piper_no_gripper_description.xml, is a six-joint MJCF with six position "
             "actuators and no gripper; it is not the model this package serves.", source="upstream_code",
             ref=f"{NO_GRIPPER}:1-54"),
        Fact("The piper_description manifest declares its licence as 'TODO: License declaration'.",
             source="upstream_code", ref=f"{MANIFEST}:8"),
        Fact("The vendored realsense2_description manifest declares the Apache License 2.0.",
             source="upstream_code", ref="realsense2_description/package.xml:8"),
    ]
    safe_state = ("the simulated world stops advancing: after an e-stop the server refuses step and reset until "
                  "an operator reset clears the latch; the integration state is kept and stays readable")
    #: The real MuJoCo engine contract, used by the implicit ``sim`` backend.  The gate exercises the package's
    #: stand-in module, whose F0 contract is selected by ``fidelity_by_backend`` below (reviewer change).  The
    #: bridge derives the engine, the timestep and the lockstep clock; the members below are this package's.
    fidelity = {
        "engine": "mujoco:piper_description",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "The bridge reports determinism none: cap.world.reset.v1 restores the model defaults with "
                     "mj_resetData and takes no seed, and a native checkpoint does not establish hidden-state, "
                     "contact, plugin or RNG completeness.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine and no Isaac Sim or USD asset was opened",
            "the MJCF declares no <option timestep>, so the engine runs at MuJoCo's library default (0.002 s, "
            "outside the clone); the 2.0 ms is not a line of the clone",
            "the bridge derives the step envelope from the actuator ctrlranges, which are wider than the joint "
            "ranges for joint1, joint4, joint6, joint7 and joint8 (piper_description.xml:20-50, 61-68): a target "
            "inside the envelope can drive a position servo (joint1 kp 10000, forcerange -20000 to 20000) against "
            "its joint range",
            "the bridge exposes qpos, qvel, ctrl and time, not camera, inertial or sensor arrays",
            "the package serves the card's models[0] only; the no-gripper MJCF (models[1]) is not served",
            "the upstream is a description and asset repository with no controller executable, ROS node, topic, "
            "service or action; the Gazebo plugin in the xacro references a piper_gazebo config that is absent from "
            "this clone, and this package drives the MJCF model, not Isaac Sim, a ROS graph or a physical robot",
            "no physical PiPER robot is modelled or driven; this simulated package has no hardware backend and "
            "nothing was validated against hardware",
        ],
    }
    #: The fake backend is the package's stand-in mujoco module, not MuJoCo: F0, no physics (reviewer change).
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:stand-in mujoco module (no physics)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "none",
                "seed_control": "none",
                "notes": "The stand-in moves each actuated joint by a fixed fraction toward its control value from "
                         "the zero reset state; it has no seed input and its motion is not MuJoCo's physics.",
            },
            "gaps": [
                "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the pinned MJCF for the "
                "joint dimensions and the per-actuator ctrlranges but integrates a placeholder first-order motion of "
                "each actuated joint toward its control value, so trajectories, contacts, actuator dynamics and the "
                "model's inertials are not MuJoCo's",
                "the model's eight <position> actuators are position servos with kp and forcerange; the fake's "
                "first-order step is not a position servo and ignores kp, forcerange, damping, inertia and the joint "
                "ranges, so it follows targets beyond the joint ranges that the wider ctrlranges admit",
                "the MJCF declares no <option timestep>, so the fake uses MuJoCo's library default 0.002 s as a "
                "placeholder; the reported 2.0 ms comes from the fake, not from a line of the clone",
                "the fake has no mj_getState/mj_setState/mj_stateSize, so the bridge uses its basic checkpoint "
                "profile: time, qpos, qvel and ctrl are restored, not MuJoCo's full integration state",
                "no mesh, texture, collision, contact, equality, tendon or sensor is loaded or resolved by the "
                "stand-in; the bridge exposes qpos, qvel, ctrl and time, not camera, inertial or sensor arrays",
                "MuJoCo itself was not importable where the gate ran, so the stand-in was not compared with the real "
                "engine and no Isaac Sim or USD asset was opened",
                "the package serves the card's models[0] only, a description and asset repository's MJCF, and no "
                "physical PiPER robot is modelled or driven",
            ],
        },
    }
