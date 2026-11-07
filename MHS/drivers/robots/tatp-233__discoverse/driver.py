"""OpenMHS driver for gh.tatp-233/discoverse: the MMK2 floor scene as a simulated MuJoCo world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's MJCF scene ``models/mjcf/mmk2_floor.xml``
(the card's ``models[1]``; ``models[0]`` is not well-formed XML at line 37, so it cannot be loaded by a standard XML
parser).  The scene includes ``mobile_chassis/mmk2/mmk2_options.xml`` and ``mmk2_dependencies.xml`` and the mobile
base, lift, head, two six-joint arms and two grippers from ``mobile_chassis/mmk2/mmk2.xml`` and
``mmk2_control.xml``: 28 qpos, 27 dof and 19 actuators.  The bridge loads the scene with the MuJoCo engine, derives
``cap.world.step.v1``'s ``action.ctrl`` from the model's ``actuator_ctrlrange``, writes ``data.ctrl``, runs
``mj_step`` for ``ticks``, and serves ``cap.world.reset.v1`` with ``mj_resetData`` + ``mj_forward``.

The device is simulated (R0): there is no hardware backend and no physical MMK2 is driven.  The scene and its
includes are read in place from the read-only clone at the pinned commit and are not copied into this package.
MuJoCo is not installed where the acceptance gate runs, so ``backends["fake"]`` is this package's stand-in
``mujoco`` module (fake.py), which reads the same scene for the joint dimensions and control ranges and integrates
a placeholder motion instead of the engine's physics; the fidelity ``gaps`` below state every difference.

Every Fact cites a line of the clone at commit d67f47c084aba0e0cf422a8725235f8b9238655a.  The card's five entry
symbols are real-robot policy environments (``AIRBOTMMK2Env`` / ``AIRBOTPlayWithCameraEnv``); they are confirmed in
the clone and are not imported or run.  This family serves the MJCF scene.  This package is model-authored and
unreviewed: it is checked on the fake backend only, and nothing here ran the MuJoCo engine or a physical robot.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

SCENE = "models/mjcf/mmk2_floor.xml"
OPTIONS = "models/mjcf/mobile_chassis/mmk2/mmk2_options.xml"
DEPENDENCIES = "models/mjcf/mobile_chassis/mmk2/mmk2_dependencies.xml"
CONTROL = "models/mjcf/mobile_chassis/mmk2/mmk2_control.xml"
SENSOR = "models/mjcf/mobile_chassis/mmk2/mmk2_sensor.xml"
ARM = "models/mjcf/manipulator/airbot_play/airbot_play_dependencies.xml"
BASE = "discoverse/robots_env/mmk2_base.py"
SIMULATOR = "discoverse/envs/simulator.py"
#: The card's models[1] relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/tatp-233/discoverse/" + SCENE


class MMK2(MujocoDriver):
    device_id = "mmk2-floor"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "MMK2 mobile manipulator floor scene (MuJoCo)"
    vendor, model = "TATP-233 / DISCOVERSE", "MMK2 floor scene"
    tags = ["mujoco", "discoverse", "mmk2", "mobile manipulator", "dual arm", "simulation"]
    facts = [
        Fact("The core installation includes MuJoCo, OpenCV and NumPy", source="vendor_doc", ref="README.md:64"),
        Fact("The project requires Python 3.8 or newer", source="upstream_code", ref="pyproject.toml:10"),
        Fact("The package declares mujoco 3.2.0 or newer as a core dependency", source="upstream_code",
             ref="pyproject.toml:40"),
        Fact("MMK2Cfg names the MJCF scene mjcf/mmk2_floor.xml", source="upstream_code", ref=f"{BASE}:8"),
        Fact("MMK2Cfg sets the timestep to 0.0025 s and the decimation to 4", source="upstream_code",
             ref=f"{BASE}:9-10"),
        Fact("MMK2Base declares 28 qpos and 19 control values for the scene", source="upstream_code",
             ref=f"{BASE}:60-61"),
        Fact("MMK2Cfg's init_state gives the base position and orientation and zero positions for the slide, head, "
             "arm and gripper joints", source="upstream_code", ref=f"{BASE}:18-27"),
        Fact("SimulatorBase copies config.timestep onto model.opt.timestep after loading the model",
             source="upstream_code", ref=f"{SIMULATOR}:220"),
        Fact("SimulatorBase sets delta_t to the model timestep times the decimation", source="upstream_code",
             ref=f"{SIMULATOR}:88-89"),
        Fact("SimulatorBase.step runs updateControl and mj_step decimation times per call", source="upstream_code",
             ref=f"{SIMULATOR}:639-642"),
        Fact("The scene is the MJCF model named mmk2", source="upstream_code", ref=f"{SCENE}:1"),
        Fact("The scene includes mmk2_options.xml and mmk2_dependencies.xml", source="upstream_code",
             ref=f"{SCENE}:3-4"),
        Fact("The scene adds a plane geom named floor", source="upstream_code", ref=f"{SCENE}:22"),
        Fact("The scene attaches a body named mmk2 to the world with an unnamed free joint", source="upstream_code",
             ref=f"{SCENE}:23-24"),
        Fact("The scene includes mobile_chassis/mmk2/mmk2.xml inside that body", source="upstream_code",
             ref=f"{SCENE}:25"),
        Fact("The scene's actuator section includes mmk2_control.xml", source="upstream_code", ref=f"{SCENE}:29-30"),
        Fact("The scene's sensor section includes mmk2_sensor.xml", source="upstream_code", ref=f"{SCENE}:33-34"),
        Fact("The scene has a home keyframe with 28 qpos values", source="upstream_code", ref=f"{SCENE}:37-38"),
        Fact("The included options set the RK4 integrator and the Newton solver and state no timestep",
             source="upstream_code", ref=f"{OPTIONS}:2"),
        Fact("The dependencies include the Airbot Play dependency file", source="upstream_code",
             ref=f"{DEPENDENCIES}:3"),
        Fact("The slide_joint default gives the lift the joint range -0.04 to 0.87 m and the position actuator the "
             "same ctrlrange with kp 50000", source="upstream_code", ref=f"{DEPENDENCIES}:6-8"),
        Fact("The head yaw joint range is -0.5 to 0.5 rad and the head pitch joint range is -1.18 to 0.16 rad, "
             "with matching position ctrlranges", source="upstream_code", ref=f"{DEPENDENCIES}:10-16"),
        Fact("The wheel default gives both wheel motors the ctrlrange and forcerange -35 to 35", source="upstream_code",
             ref=f"{DEPENDENCIES}:18-20"),
        Fact("The control fragment declares two wheel motors, the lift, head yaw and head pitch, and seven position "
             "actuators per arm", source="upstream_code", ref=f"{CONTROL}:3-24"),
        Fact("The two gripper position actuators have the ctrlrange 0 to 1", source="upstream_code",
             ref=f"{CONTROL}:16-24"),
        Fact("The Airbot Play joint ctrlranges are joint1 -3.151 to 2.089, joint2 -2.963 to 0.181, joint3 -0.094 to "
             "3.161, joint4 -3.012 to 3.012, joint5 -1.859 to 1.859 and joint6 -3.017 to 3.017 rad",
             source="upstream_code", ref=f"{ARM}:11-33"),
        Fact("The sensor fragment publishes joint positions, tendon positions, joint velocities and tendon "
             "velocities for the controlled joints", source="upstream_code", ref=f"{SENSOR}:3-40"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the determinism kind, the timestep and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:mmk2",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "the model has no random element and MuJoCo integrates it deterministically from the reset "
                     "state, so the same ctrl sequence and tick count repeat a trajectory; the package's stand-in "
                     "is deterministic too, but its placeholder motion is not the engine's physics",
        },
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the scene and its "
            "includes for the 28 qpos, 27 dof, 19 actuators and their control ranges, then moves each actuated "
            "joint toward its control value; it computes no inertias, contacts, tendons, equalities or actuator "
            "and sensor dynamics, so no trajectory here is a MuJoCo result",
            "the meshes and textures are not loaded by the stand-in; a real engine load needs them beside the "
            "model, which the pinned clone provides",
            "the model file states no <option timestep>; MMK2Cfg sets 0.0025 s and SimulatorBase copies it onto "
            "the model, but this package loads the model file directly and does not apply that configuration.  "
            "The reference's timestep_ms (2.0) is the library default supplied by the stand-in's placeholder "
            "fallback, not a value stated by the model",
            "the bridge's reset calls mj_resetData and starts from the model defaults, not from the upstream "
            "init_state or the home keyframe of mmk2_floor.xml:37-38; a client that wants a pose must send its "
            "ctrl and step",
            "the upstream step applies the action for decimation=4 substeps (mmk2_base.py:10 and "
            "simulator.py:639-642); the bridge applies ctrl at every tick with no decimation, so one bridge tick "
            "is one mj_step, not one upstream step",
            "the upstream updateControl path clips a control to the actuator ctrlrange; the bridge refuses an "
            "out-of-range ctrl before writing it, which is the safer direction but a different contract",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the model's timestep only",
            "no rendering, cameras or sensor publication: the 19 joint sensors are not exposed as an observation, "
            "only the bridge's time, qpos, qvel and ctrl state is",
            "the model is a simulation asset for the MMK2: no physical robot is modelled or controlled and nothing "
            "here was validated against the hardware",
        ],
    }
