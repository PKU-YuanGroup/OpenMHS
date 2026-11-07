"""OpenMHS driver for gh.elijah-waichong-chan/go2-convex-mpc: the Unitree Go2 MJCF scene as a simulated MuJoCo world.

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's primary model, ``models[0]``
(``models/MJCF/go2/scene.xml``), which includes the robot model ``models/MJCF/go2/go2.xml``.  The bridge loads the
scene with the MuJoCo engine, derives ``cap.world.step.v1``'s ``action.ctrl`` from the model's
``actuator_ctrlrange`` (12 motor actuators: a hip, thigh and calf for each of the four legs), writes ``data.ctrl``,
runs ``mj_step`` for ``ticks``, and serves ``cap.world.reset.v1`` with ``mj_resetData`` + ``mj_forward``.  The world
state is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``,
``seed``).

The device is simulated (R0): there is no hardware backend and no physical Go2 is driven.  The repository's control
stack (convex MPC, gait scheduler, swing-leg controller) is not served; this package is the MuJoCo world, not the
controller.  The model files are read in place from the read-only clone at the pinned commit and are never copied,
imported or installed.

MuJoCo is not installed where the acceptance gate runs, so ``backends["fake"]`` is this package's stand-in
``mujoco`` module (fake.py).  It reads the same scene and included model for the model shape and integrates a
placeholder motion instead of the engine's physics; the fidelity ``gaps`` below state every difference.  Every Fact
cites a line of the clone at commit 1c63c6a762779887ab0431fd60db681dede6cb32.  This package is model-authored and
unreviewed: it is checked on the fake backend only, and nothing here ran the MuJoCo engine or a physical robot.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

SCENE = "models/MJCF/go2/scene.xml"
ROBOT = "models/MJCF/go2/go2.xml"
TERRAIN_SCENE = "models/MJCF/go2/scene_terrain.xml"
LOADER = "src/convex_mpc/mujoco_model.py"
DEMO = "examples/ex00_demo.py"
#: The card's models[0] relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/elijah-waichong-chan/go2-convex-mpc/" + SCENE


class Go2ConvexMPC(MujocoDriver):
    device_id = "go2-convex-mpc"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "Unitree Go2 convex MPC scene (MuJoCo)"
    vendor, model = "elijah-waichong-chan", "Unitree Go2 MJCF scene"
    tags = ["mujoco", "unitree", "go2", "quadruped", "locomotion", "mpc", "simulation", "robot"]
    facts = [
        Fact("The repository implements a convex model predictive controller for the Unitree Go2 quadruped, "
             "including contact-force optimization, centroidal linearized dynamics, Raibert-style foot planning, "
             "swing-leg path generation and MuJoCo simulation", source="vendor_doc", ref="README.md:1-2"),
        Fact("The upstream MuJoCo model class resolves models/MJCF/go2/scene.xml and loads it with "
             "mujoco.MjModel.from_xml_path, then creates its data with mujoco.MjData", source="upstream_code",
             ref=f"{LOADER}:14-21"),
        Fact("The primary scene is the MJCF model 'go2 scene' and includes go2.xml from the same directory",
             source="upstream_code", ref=f"{SCENE}:1-2"),
        Fact("The scene adds a floor plane, two low boxes and a rising row of boxes along the x axis",
             source="upstream_code", ref=f"{SCENE}:19-31"),
        Fact("The robot model is named go2, is compiled in radians with meshdir assets and autolimits, and sets "
             "the elliptic friction cone with impratio 100", source="upstream_code", ref=f"{ROBOT}:1-4"),
        Fact("The quadruped root body base_link is at z=0.445 m and is attached to the world by a freejoint",
             source="upstream_code", ref=f"{ROBOT}:63-68"),
        Fact("The go2 default class gives its motor elements the control range -23.7 to 23.7",
             source="upstream_code", ref=f"{ROBOT}:10"),
        Fact("The knee default class overrides the motor control range to -45.43 to 45.43",
             source="upstream_code", ref=f"{ROBOT}:22-25"),
        Fact("The joint ranges are abduction -1.0472 to 1.0472 rad, front hip -1.5708 to 3.4907 rad, back hip "
             "-0.5236 to 4.5379 rad and knee -2.7227 to -0.83776 rad", source="upstream_code", ref=f"{ROBOT}:9-24"),
        Fact("The actuator block declares 12 motor actuators, one hip, thigh and calf per leg, named in FR, FL, RR "
             "and RL order", source="upstream_code", ref=f"{ROBOT}:222-235"),
        Fact("The model provides a home keyframe with 19 qpos values (a floating base plus 12 joints) and 12 ctrl "
             "values", source="upstream_code", ref=f"{ROBOT}:285-288"),
        Fact("The sensor section declares joint position, velocity and actuator force sensors for all 12 joints, "
             "plus IMU orientation, gyroscope, accelerometer, position and linear velocity at the imu site",
             source="upstream_code", ref=f"{ROBOT}:237-283"),
        Fact("The demos run the simulation at SIM_HZ 1000 with SIM_DT 1/1000 s", source="upstream_code",
             ref=f"{DEMO}:83-85"),
        Fact("The demos assign SIM_DT to model.opt.timestep before the simulation loop", source="upstream_code",
             ref=f"{DEMO}:185-186"),
        Fact("The demo loop advances each physics step with mj_step1, writes the held joint torques through "
             "set_joint_torque, then calls mj_step2", source="upstream_code", ref=f"{DEMO}:311-314"),
        Fact("The model wrapper looks up each leg's hip, thigh and calf actuator ids by name and writes torque[0], "
             "torque[1] and torque[2] to data.ctrl", source="upstream_code", ref=f"{LOADER}:30-39"),
        Fact("set_joint_torque assigns the 12-value torque vector in FL, FR, RL, RR leg order",
             source="upstream_code", ref=f"{LOADER}:41-46"),
        Fact("The second scene, scene_terrain.xml, includes go2.xml and adds two height fields and obstacle "
             "geometry; this package serves the primary scene.xml", source="upstream_code",
             ref=f"{TERRAIN_SCENE}:1-16"),
        Fact("The package requires Python 3.10 or newer below 3.11", source="upstream_code", ref="pyproject.toml:8"),
        Fact("The README recommends Linux for the project and states that other operating systems were not "
             "tested", source="vendor_doc", ref="README.md:67-68"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the determinism kind, the timestep and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:go2 scene",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates one loaded MJCF deterministically from the reset state and the model has no "
                     "random element; the bridge accepts a reset seed for the class contract but mj_resetData does "
                     "not use it.  The package's fake is deterministic too, but its placeholder motion is not the "
                     "engine's physics.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses scene.xml and its "
            "included go2.xml for the 19 qpos and 18 dof coordinates, the 12 motor actuators and their ctrlranges, "
            "then moves each actuated hinge a placeholder fraction toward its control value; it computes no "
            "inertias, contacts, friction, actuator or sensor dynamics and was never compared with the engine",
            "the model file sets no <option timestep>; the published timestep_ms 2.0 is the fake's placeholder for "
            "MuJoCo's library default, while the upstream demos set model.opt.timestep to 1 ms "
            "(examples/ex00_demo.py:83-85,185-186), so the step used by a real bridge load of the raw scene is not "
            "verified here",
            "the bridge's ctrl vector order is the model actuator order FR, FL, RR, RL "
            "(models/MJCF/go2/go2.xml:222-235), while the upstream set_joint_torque maps the 12-value vector in "
            "FL, FR, RL, RR order (src/convex_mpc/mujoco_model.py:41-46); a client must reorder, and the upstream "
            "MPC, gait and leg controllers are not served",
            "the bridge's reset calls mj_resetData and starts from the model defaults; the fake starts every array "
            "at zero, while the model's base_link default is z=0.445 m (models/MJCF/go2/go2.xml:64) and the home "
            "keyframe is not applied",
            "the stand-in loads no mesh or texture (the model's asset section names 16 OBJ files under assets/) and "
            "resolves no contact, friction, sensor or actuator dynamics; a real engine load needs the meshes beside "
            "the model, which the pinned clone provides",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the model step only; the "
            "upstream demo's render pacing and replay viewer are not used",
            "no rendering, cameras or sensor publication: the model's 36 joint sensors and five IMU sensors are "
            "not exposed; the observation is only the bridge's time, qpos, qvel and ctrl state",
            "only the card's primary scene is served; the terrain scene scene_terrain.xml and the URDF description "
            "are not loaded by this package",
            "no physical Go2 is modelled or controlled and nothing was validated against the robot; MuJoCo itself "
            "was not installed where the gate ran, so no trajectory here is an engine result",
        ],
    }
