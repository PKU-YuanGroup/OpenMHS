"""OpenMHS driver for the gh.tenfoldpaper/multipanda_ros2 dual-arm MuJoCo scene.

The card proposes a ``RosDriver``, but the registry's device plan for this
package is a ``world.sim`` resource backed by the upstream simulation, and the
repository's concrete simulation entry is the MuJoCo scene
``franka_description/mujoco/franka/dual_scene.xml`` (the dual-arm simulator
launch passes that file to the MuJoCo server).  The ROS packages of the pinned
parent tree are a ``ros2_control`` framework, the MuJoCo hardware plugin and
gripper action servers; the MuJoCo server's own world services (pause, reset
and a step action) are in the ``mujoco_ros_pkgs`` git submodule, which the
pinned parent commit records only as a gitlink, so no line of the pinned tree
shows them.  This package therefore uses the SDK's ``MujocoDriver`` over the
same MJCF model: ``cap.world.step.v1`` writes the model's actuator control
vector and ``cap.world.reset.v1`` restores the model defaults.  DEVIATION FROM
THE CARD: helper RosDriver replaced by MujocoDriver for the world.sim device
plan.

The model has 44 actuator channels.  Per arm, the seven torque motors and the
gripper declare a ctrlrange, but the seven position and seven velocity servos
declare none, so MuJoCo compiles them as not ctrl-limited and leaves their
control unclamped.  The MuJoCo bridge publishes one limit per channel: the
model's ctrlrange where it states one, and ``operator_required`` for the 28
servo channels, so the endpoint refuses every step that sets them
(``MHS.SAFETY.LIMITS_UNSET``, before any native call) until the site's
``site-limits.json`` bounds them.  ``site-limits.example.json`` is the operator
example the gate serves (the joint ranges and the Panda joint velocity limits;
operator data, not model bounds).  The fake reports the model's 44 channels in
document order (the author's fake hid the 28 servo channels; until the SDK change
of 2026-11-05 the bridge could not bound them and the package was blocked
SDK_BUG).

The model is read from the pinned read-only clone in place; it is never copied
into this package.  ``fake.py`` is a package-local stand-in for the ``mujoco``
module, not MuJoCo; the driver declares its F0 fidelity and all gaps.  No ROS
graph, MuJoCo engine, simulator or hardware was contacted.  This is a
model-authored, unreviewed package; the lock keeps ``reviewed_by: null``.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's first model, relative to this package directory: the read-only
#: clone under robots/ at the pinned commit.
MODEL = "franka_description/mujoco/franka/dual_scene.xml"
MODEL_PATH = "../../../../robots/tenfoldpaper/multipanda_ros2/" + MODEL

_README_SIM = "README.md:10-11"
_README_MUJOCO = "README.md:94"
_LAUNCH_SCENE = "franka_bringup/launch/sim/dual_franka_sim.launch.py:65-71"
_LAUNCH_MODEL = "franka_bringup/launch/sim/dual_franka_sim.launch.py:144-149"
_BRINGUP_DOC = "docs/chapters/franka_bringup.md:32"
_SCENE = MODEL + ":1-5"
_MJ_DUAL = "franka_description/mujoco/franka/mj_dual.xml"
_OBJECTS = "franka_description/mujoco/franka/objects.xml"

#: The two arm trees are the first body of each arm in mj_dual.xml.
_ARMS_REF = _MJ_DUAL + ":126-277"
#: The seven left and seven right hinge joints, in document order.
_LEFT_JOINTS_REF = _MJ_DUAL + ":145-213"
_RIGHT_JOINTS_REF = _MJ_DUAL + ":296-364"
_FINGER_DEFAULT_REF = _MJ_DUAL + ":13-14"
_FINGER_JOINTS_REF = _MJ_DUAL + ":241-405"
_COUPLING_REF = _MJ_DUAL + ":435-450"
_ACTUATORS_REF = _MJ_DUAL + ":452-506"
_OBJECTS_REF = _OBJECTS + ":4-9"
_HARDWARE_DOC = "docs/chapters/franka_hardware.md:9-12"
_PLUGIN = "franka_hardware/src/sim/franka_mj_hardware_system.cpp"
_PANDA_LIMITS = ("franka_multi_mode_controller/multi_mode_controller/include/multi_mode_controller/utils/"
                 "panda_limits.h:14-16")

_FAKE_GAPS = [
    "the fake is a package-local stand-in for the mujoco Python module, not MuJoCo: it parses the MJCF and "
    "its includes for the actuator control ranges, joint dimensions and option timestep, but its step is a "
    "placeholder first-order motion, not the model's dynamics",
    "the dual scene has 44 actuator channels in document order (per arm seven torque motors, seven position "
    "servos, seven velocity servos and one gripper); the fake reports all 44, the 28 servos as not ctrl-limited "
    "as MuJoCo compiles them, and its placeholder motion applies every channel at once, as the bare MJCF does "
    "without the upstream plugin's gain switching",
    "the fake resolves no mesh, inertia, contact, friction, tendon, equality or gravity compensation; the "
    "free-joint box, the mocap sphere and the two-arm contact geometry are counted in qpos/qvel but are not "
    "simulated",
    "the fake resets qpos to the model's qpos0 (zero arm and finger joints, the free box at its body pose) and "
    "qvel and ctrl to zero, while the upstream simulation sets the arm joints from ros2_control initial_position "
    "parameters; the fake does not read those parameters, and zero lies outside the ranges of joints 4 and 6",
    "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared with "
    "the real engine; the driver's sim backend would import mujoco and load the same file, but it was not run",
    "the fake has no mj_getState, mj_setState or mj_stateSize, so snapshots use the bridge's basic profile "
    "(time, qpos, qvel, ctrl and act), not the full MuJoCo integration state",
    "no viewer, rendering, camera, contact sensor or actuator force is exposed; only the cap.world.step and "
    "cap.world.reset integration state and control vector are served",
    "the upstream ros2_control controller manager, gripper action servers and rosbridge layer are not part of "
    "this world driver; the raw actuator vector is exposed instead of the upstream's joint/controller interface",
    "the free box and the mocap sphere are not externally placed; the fake has no reset scenario or seed "
    "control beyond the bridge's configured seed",
    "no physical robot is modelled and nothing was validated against hardware",
]

_SIM_GAPS = [
    "the sim backend would import the real mujoco module and load the same dual_scene.xml; it was not run here",
    "the driver exposes the raw MuJoCo actuator vector, not the upstream ros2_control controller layer or the "
    "gripper action servers",
    "the model's three actuator sets per arm (torque, position and velocity) are all present in the control "
    "vector and all act at once with their MJCF gains; the upstream plugin turns the unused sets off by gain "
    "switching (franka_mj_hardware_system.cpp:141-146, 508-547), which the bare model does not do",
    "the 28 position and velocity servo channels declare no ctrlrange, so the bridge publishes them "
    "operator_required: a step that sets them is refused until the site's site-limits.json bounds them, and "
    "the example overlay's joint ranges and velocity limits are operator data, not bounds of the model",
    "no viewer, rendering, camera or sensor topic is exposed",
    "no physical robot is modelled and nothing was validated against hardware",
]


class MultipandaRos2World(MujocoDriver):
    device_id = "multipanda-ros2"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    tags = ["ros2", "multipanda", "franka", "panda", "mujoco", "simulation", "robot-arm", "dual-arm"]
    display_name = "multipanda_ros2 dual Panda MuJoCo scene"
    vendor, model = "tenfoldpaper", "dual_scene"
    facts = [
        Fact("The project integrates multi-arm MuJoCo simulation designed as a plugin to mujoco_ros_pkg.",
             source="vendor_doc", ref=_README_SIM),
        Fact("The README's tested configuration lists Ubuntu 22.04, ROS 2 Humble, Panda 4.2.2 and 4.2.1, "
             "libfranka 0.9.2 and MuJoCo 3.2.0.", source="vendor_doc", ref=_README_MUJOCO),
        Fact("The dual-arm simulator launch selects dual_scene.xml when the gripper is loaded and resolves it "
             "below franka_description/mujoco/franka.", source="upstream_code", ref=_LAUNCH_SCENE),
        Fact("The dual-arm simulator launch includes launch_mujoco_ros_server.launch and passes the selected scene "
             "to it as its modelfile argument.", source="upstream_code", ref=_LAUNCH_MODEL),
        Fact("The dual-arm documentation says dual_scene.xml is loaded for the dual-arm simulation.",
             source="vendor_doc", ref=_BRINGUP_DOC),
        Fact("The MuJoCo files are under mujoco/franka, and each robot body carries gravcomp=1 for gravity "
             "compensation.", source="vendor_doc", ref="docs/chapters/franka_description.md:50"),
        Fact("For the multi-arm case the documentation defines all arms in a single XML file, like mj_dual.",
             source="vendor_doc", ref="docs/chapters/franka_description.md:54"),
        Fact("Additional objects can be included in the scene by including a separate file such as "
             "objects.xml.", source="vendor_doc", ref="docs/chapters/franka_description.md:60"),
        Fact("The scene model is named 'panda scene' and includes mj_dual.xml and objects.xml.",
             source="upstream_code", ref=_SCENE),
        Fact("mj_dual sets the option timestep to 0.002 s.", source="upstream_code", ref=_MJ_DUAL + ":4"),
        Fact("The scene has two arm trees rooted at mj_left_link0 and mj_right_link0, at y +0.26 and -0.26.",
             source="upstream_code", ref=_ARMS_REF),
        Fact("The left arm has seven hinge joints with ranges -2.7437 to 2.7437, -1.7837 to 1.7837, -2.9007 "
             "to 2.9007, -3.0421 to -0.1518, -2.8065 to 2.8065, 0.5445 to 4.5169 and -3.0159 to 3.0159.",
             source="upstream_code", ref=_LEFT_JOINTS_REF),
        Fact("The right arm has the same seven hinge-joint ranges as the left arm.", source="upstream_code",
             ref=_RIGHT_JOINTS_REF),
        Fact("The finger default class declares a slide joint with range 0 to 0.04 m.",
             source="upstream_code", ref=_FINGER_DEFAULT_REF),
        Fact("Each hand carries two joints of class finger: mj_left_finger_joint1/2 and "
             "mj_right_finger_joint1/2.", source="upstream_code", ref=_FINGER_JOINTS_REF),
        Fact("The finger joints are coupled by fixed tendons with coefficient 0.5 and by joint equality "
             "constraints.", source="upstream_code", ref=_COUPLING_REF),
        Fact("mj_dual.xml's actuator block has, per arm, seven torque motors with ctrllimited true (ctrlrange "
             "-87 87 for joints 1 to 4 and -12 12 for joints 5 to 7), seven position servos (kp 10) and seven "
             "velocity servos (kv 1) that declare no ctrlrange, and a general gripper channel of class panda with "
             "ctrlrange 0 255: 44 channels in all.",
             source="upstream_code", ref=_ACTUATORS_REF),
        Fact("objects.xml adds a free-joint box (obj_box_01) and a mocap sphere (sphere_01).",
             source="upstream_code", ref=_OBJECTS_REF),
        Fact("The simulation interface handles n >= 1 Panda robots and exposes the same ROS 2 interfaces as "
             "the real robot.", source="vendor_doc", ref=_HARDWARE_DOC),
        Fact("The documentation says the real-robot interface FrankaMultiHardwareInterface wraps libfranka to "
             "connect to the robot, its control callbacks implement no logic of their own, and all safety features "
             "and command calculation must be handled by the controller.", source="vendor_doc",
             ref="docs/chapters/franka_hardware.md:14"),
        Fact(".gitmodules declares mujoco_ros_pkgs as a git submodule from github.com/tenfoldpaper/mujoco_ros_pkgs, "
             "branch wip_ros_control_humble.", source="upstream_code", ref=".gitmodules:1-4"),
        Fact("The MuJoCo hardware plugin initialises every arm's torque, position and velocity actuators to off: "
             "torque flag 0 and servo gains 0.", source="upstream_code", ref=f"{_PLUGIN}:141-146"),
        Fact("When a mode switch is pending, perform_command_mode_switch turns on only the actuator set of the "
             "arm's control mode (torque flag 1, position-servo kp 100 or velocity-servo kv 10) and zeroes the other "
             "two sets; mode None zeroes all three.",
             source="upstream_code", ref=f"{_PLUGIN}:508-547"),
        Fact("write returns an error for a non-finite effort, position or velocity command and writes data.ctrl "
             "only for the actuator set of the arm's control mode, plus the gripper channel when the arm has a "
             "gripper.", source="upstream_code", ref=f"{_PLUGIN}:259-299"),
        Fact("The multi-mode controller's Panda limits give the maximum joint velocity as 2.1750 rad/s for joints "
             "1 to 4 and 2.6100 rad/s for joints 5 to 7.", source="upstream_code", ref=_PANDA_LIMITS),
    ]
    safe_state = (
        "No step or reset is accepted after an e-stop until mhs.safety.reset clears the latch; the last "
        "integration state is kept and remains readable, and the lockstep simulation does not advance between "
        "steps. The latch is software and the simulation has no physical stop."
    )
    #: The common contract describes the real-MuJoCo sim backend; the deployed
    #: fake is an analytic stand-in and overrides it below.
    fidelity = {
        "engine": "mujoco:dual_scene",
        "fidelity_level": "F1",
        "gaps": _SIM_GAPS,
    }
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:fake-mjcf-parser",
            "fidelity_level": "F0",
            "gaps": _FAKE_GAPS,
        },
    }
