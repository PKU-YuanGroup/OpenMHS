"""OpenMHS driver for gh.catachiii/crl-humanoid-ros: the Unitree G1 MuJoCo scene.

The upstream repository is a ROS 2 humanoid simulation and control framework whose simulator
(``crl_humanoid_simulator``) loads MJCF models and steps MuJoCo.  The card's ``models[0]`` is the
G1 scene ``crl_humanoid_commons/data/robots/g1_description/scene_crl.xml``, and the registry
device plan for this package is a ``world.sim`` resource served through ``cap.world.step.v1`` /
``cap.world.reset.v1``.  This package therefore uses the SDK's ``MujocoDriver`` rather than the
card's suggested ``RosDriver``: a rosbridge driver would only expose ROS topics and cannot
express the environment-step or reset contract, while the pinned MJCF model is the upstream
simulation asset itself.  The deviation is recorded in RESULT.json.

A ``MujocoDriver`` is configuration only.  ``model_path`` names the G1 scene; the bridge derives
the contract from the model it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl:
[...]}}`` and writes the control vector, then calls ``mj_step`` for every tick.  The G1 MJCF
declares 29 motor actuators without ``ctrlrange``, so the bridge publishes ``action.ctrl`` as ``operator_required``: the endpoint refuses a step that sets
it (``MHS.SAFETY.LIMITS_UNSET``, before any native call) until the site's ``site-limits.json`` bounds it;
``site-limits.example.json`` is operator example data, not a bound of the model;
this package invents none.  ``cap.world.reset.v1`` restores the model defaults with
``mj_resetData`` + ``mj_forward``.  ``cap.world.seed.v1`` is not served: the MuJoCo bridge has
no seed input, and a reset restores the model defaults rather than sampling a new state.

MuJoCo is not installed where the acceptance gate runs (no network, no pip install), so
``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py).  It reads the same
MJCF file and its include for the model shape (joint dimensions, the free base, the 29 motor
channels and the option timestep) but its integration is a placeholder, not MuJoCo's physics.
A backend name that ``backends`` does not list (for example ``sim``) imports the real
``mujoco`` module and loads the same scene; that path was not run here.

Every fact cites the pinned clone at 31202ed7c73ab6b6735d0416274ee9d256ecdf02.  The model file
is read from the read-only clone in place; it is never copied into this package or imported.
This package is model-authored and unreviewed: ``driver.lock.json`` keeps ``reviewed_by`` null.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/.
MODEL = "crl_humanoid_commons/data/robots/g1_description/scene_crl.xml"
MODEL_PATH = "../../../../robots/catachiii/crl-humanoid-ros/" + MODEL
SCENE = "crl_humanoid_commons/data/robots/g1_description/scene_crl.xml"
G1 = "crl_humanoid_commons/data/robots/g1_description/g1_29dof_crl.xml"
SIM_NODE = "crl_humanoid_simulator/include/crl_humanoid_simulator/G1SimNode.h"
SIM_CONFIG = "crl_humanoid_simulator/config/g1_sim.yaml"
BASE_NODE = "crl_humanoid_commons/include/crl_humanoid_commons/nodes/BaseNode.h"
HW_NODE = "crl_humanoid_hardware/include/crl_humanoid_hardware/G1Node.h"

#: Gaps shared by the real-engine contract and the fake backend.
_PACKAGE_GAPS = [
    "the G1 MJCF sets no option timestep, so a direct load runs at the engine's library default (the "
    "stand-in uses 2 ms); the upstream ROS simulator instead sets the model timestep from its "
    "time_step_size parameter (G1SimNode.h:414, g1_sim.yaml:24), which this direct model load does not "
    "apply",
    "the G1 actuator block sets no ctrlrange, so the bridge publishes action.ctrl operator_required: a step that sets it is refused until the site's site-limits.json bounds it, and site-limits.example.json is operator example data, not a model bound; "
    "the package declares no bound of its own and the joint actuatorfrcrange values are not used as ctrl "
    "limits",
    "cap.world.seed.v1 is not served because the MuJoCo bridge has no seed input and a reset restores "
    "the model defaults; the upstream ROS simulator's command topics, services, elastic band, monitor "
    "stream and FSM state switching are out of scope for this direct model driver",
    "the second and third card models (the Tron1A scene and the G1 robot include) are not separately "
    "served; the card's first scene is the served model",
    "no physical humanoid is modelled and nothing was validated against Unitree G1 hardware; the "
    "repository's crl_humanoid_hardware nodes for the real G1 (Unitree SDK2) and Tron1A (LimX SDK) are "
    "out of scope; only the simulated world state and the derived control vector are exposed",
]
#: The fake backend: a stand-in mujoco module with no dynamics (F0).
_FAKE_GAPS = [
    "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the card's scene and "
    "its include for the free base, the 29 hinge joints, the 29 motor channels and the model option "
    "timestep, then integrates a placeholder torque response and joint motion",
    "the stand-in computes no inertia, mass matrix, gravity, contact, friction, equality, tendon or "
    "actuator dynamics, loads no STL mesh or texture, and does not implement MuJoCo's integration-"
    "state snapshot API; a fake trajectory is not a MuJoCo trajectory",
    "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was "
    "compared with the real engine or with the upstream ROS simulator",
] + _PACKAGE_GAPS
#: The real engine contract of the implicit sim backend, which was not run.
_REAL_GAPS = [
    "the official MuJoCo engine was not run where this package was checked, so its step, contact and "
    "actuator behaviour are not validated by this package's fake evidence",
] + _PACKAGE_GAPS


class CrlHumanoidG1(MujocoDriver):
    """Configuration-only MuJoCo world driver for the Unitree G1 scene."""

    device_id = "crl-humanoid-g1"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "CRL Humanoid ROS Unitree G1 (MuJoCo scene)"
    vendor, model = "Computational Robotics Lab, ETH Zurich", "Unitree G1 (g1_29dof_crl)"
    tags = ["ros2", "humanoid", "unitree", "g1", "mujoco", "simulation", "world"]
    facts = [
        Fact("The repository is a ROS 2 framework for humanoid robot simulation and control that "
             "supports the Unitree G1 and LimX Tron1A platforms.", source="vendor_doc", ref="README.md:5"),
        Fact("The repository lists MuJoCo-based software-in-the-loop testing as its simulation role.",
             source="vendor_doc", ref="README.md:11"),
        Fact("The card's first model is the MJCF scene 'g1 scene crl', which includes g1_29dof_crl.xml.",
             source="upstream_code", ref=f"{SCENE}:1-2"),
        Fact("The robot model compiles angles in radians and resolves its meshes from meshes/.",
             source="upstream_code", ref=f"{G1}:2"),
        Fact("The pelvis body is placed at 0 0 0.793 and carries the free joint floating_base_joint.",
             source="upstream_code", ref=f"{G1}:44-46"),
        Fact("The left hip pitch joint declares range -2.5307 2.8798 and actuatorfrcrange -88 88.",
             source="upstream_code", ref=f"{G1}:53"),
        Fact("The actuator block has 29 motor actuators, one for each leg, waist and arm joint, and none "
             "sets ctrlrange or ctrllimited.", source="upstream_code", ref=f"{G1}:245-275"),
        Fact("The model declares gyro and accelerometer sensors for the torso and pelvis IMUs.",
             source="upstream_code", ref=f"{G1}:277-282"),
        Fact("The scene's worldbody adds a directional light and a plane geom named floor.",
             source="upstream_code", ref=f"{SCENE}:18-21"),
        Fact("The G1 simulator declares robot_xml_file with the default g1_description/scene_crl.xml.",
             source="upstream_code", ref=f"{SIM_NODE}:40"),
        Fact("initializeMuJoCo loads the robot_xml_file model with mj_loadXML and sets the model option "
             "timestep to timeStepSize_.", source="upstream_code", ref=f"{SIM_NODE}:393-414"),
        Fact("BaseNode declares the time_step_size parameter with default 0.01 and stores it in "
             "timeStepSize_.", source="upstream_code", ref=f"{BASE_NODE}:36-37"),
        Fact("The G1 simulator configuration sets the robot node's time_step_size to 0.001667.",
             source="upstream_code", ref=f"{SIM_CONFIG}:22-24"),
        Fact("The repository's crl_humanoid_hardware G1Node names the Unitree SDK2 low-level command and "
             "state topics rt/lowcmd and rt/lowstate for the 29 G1 motors.",
             source="upstream_code", ref=f"{HW_NODE}:17-30"),
        Fact("The README lists MuJoCo 3.3.5 as the simulation dependency.",
             source="vendor_doc", ref="README.md:78"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the MuJoCo integration state is kept and stays readable")
    #: The real MuJoCo engine contract, used by the implicit ``sim`` backend (not run here).  The bridge
    #: derives the time step and the lockstep clock.  The gate exercises the package's stand-in module,
    #: whose F0 contract is selected by ``fidelity_by_backend`` below.
    fidelity = {
        "engine": "mujoco:g1 scene crl",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates the fixed G1 model deterministically from the model defaults; the "
                     "bridge exposes no seed input and cap.world.reset.v1 restores the model defaults, so a "
                     "seed cannot select a different initial state.",
        },
        "gaps": _REAL_GAPS,
    }
    #: The fake backend is not MuJoCo and not a recording: F0, no dynamics.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:stand-in mujoco module (no physics)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "seeded",
                "seed_control": "none",
                "notes": "The stand-in integrates the same placeholder response for the same controls from "
                         "the model defaults; it has no seed input and its motion is not MuJoCo's physics.",
            },
            "gaps": _FAKE_GAPS,
        },
    }
