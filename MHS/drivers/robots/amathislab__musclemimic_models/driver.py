"""OpenMHS driver for gh.amathislab/musclemimic_models: the MyoBimanualArm MuJoCo model.

A MujocoDriver is configuration only: ``model_path`` names the MJCF scene that the card lists as ``models[0]``
(``musclemimic_models/model/arm/myoarm_bimanual.xml``) and the bridge derives the contract from the model it loads.
The step action is ``data.ctrl``, one number per muscle actuator, bounded per actuator by the model's
``actuator_ctrlrange`` (the default classes of the model set ``ctrlrange="-1 1"``); the state is the integration
state of the model (``time``, ``qpos``, ``qvel``, ``ctrl``) plus the tick count; ``cap.world.reset.v1`` restores
the model defaults with ``mj_resetData``.

The device is simulated (R0): there is no hardware backend and no e-stop path to a machine.  MuJoCo is not
installed and cannot be installed where the acceptance gate runs (no network, no pip), so the ``fake`` backend is
this package's stand-in ``mujoco`` module (fake.py).  It reads the same MJCF file (including its ``<include>``
elements) for the actuator count, the per-actuator control ranges, the joint count and the timestep, but its
integration is a placeholder, not MuJoCo's physics; the driver's fidelity ``gaps`` say so.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this
package and never imported).  Every Fact cites a line of the clone at commit
001b723e1be89a055a4cf79d23e2e7aaf968fb40.  The package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "musclemimic_models/model/arm/myoarm_bimanual.xml"
ASSETS = "musclemimic_models/model/arm/assets/myoarm_bimanual_assets.xml"
REGISTRY = "musclemimic_models/__init__.py"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/amathislab/musclemimic_models/" + MODEL


class MyoBimanualArm(MujocoDriver):
    device_id = "myoarm-bimanual"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "MuscleMimic MyoBimanualArm (MuJoCo model)"
    vendor, model = "MuscleMimic Team", "MyoBimanualArm"
    tags = ["biomechanics", "bimanual", "mujoco", "muscle", "musculoskeletal", "simulation"]
    facts = [
        Fact("The card's main model is the MJCF scene myoarm_bimanual.xml, whose root element is "
             "'<mujoco model=\"MuscleMimic MyoBiamanualArm\">'", source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The repository registry maps the name bimanual to arm/myoarm_bimanual.xml and myofullbody to "
             "body/myofullbody.xml", source="upstream_code", ref=f"{REGISTRY}:10-13"),
        Fact("The upstream load() builds the model with mujoco.MjModel.from_xml_path and returns it with "
             "mujoco.MjData(model)", source="upstream_code", ref=f"{REGISTRY}:25-27"),
        Fact("The scene includes the shared scene file ../scene/musclemimic_scene.xml", source="upstream_code",
             ref=f"{MODEL}:19"),
        Fact("The scene includes the arm's asset and default-class definitions from "
             "./assets/myoarm_bimanual_assets.xml", source="upstream_code", ref=f"{MODEL}:20"),
        Fact("The arm is the fixed-base body named Bimanual, attached directly under worldbody at pos "
             "-.025 0.1 1", source="upstream_code", ref=f"{MODEL}:23-24"),
        Fact("The scene includes the kinematic chain ./assets/myoarm_bimanual_body.xml inside the Bimanual body",
             source="upstream_code", ref=f"{MODEL}:25"),
        Fact("The model sets the integration timestep to 0.002 s with <option timestep=\"0.002\"/>",
             source="upstream_code", ref=f"{ASSETS}:21"),
        Fact("The nested default class muscle sets the muscle control range -1 to 1 (ctrllimited true, "
             "ctrlrange \"-1 1\")", source="upstream_code", ref=f"{ASSETS}:37-38"),
        Fact("The default class upperarm_muscle repeats the -1 to 1 control range for the upper-arm muscle "
             "actuators", source="upstream_code", ref=f"{ASSETS}:53-54"),
        Fact("The default class forearm_muscle sets the -1 to 1 control range for the forearm muscle actuators",
             source="upstream_code", ref=f"{ASSETS}:57-58"),
        Fact("The MyoBimanualArm row of the model table lists 76 joints (36 with finger muscles disabled) and "
             "126 muscles (64 with finger muscles disabled)", source="vendor_doc", ref="README.md:127"),
        Fact("The README states that the minimum required MuJoCo version for both models is mujoco==3.2.1",
             source="vendor_doc", ref="README.md:154"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:MuscleMimic MyoBimanualArm",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one fixed model deterministically from one initial state; the bridge has "
                     "no seed input and a reset restores the model defaults, so the same run repeats on the same "
                     "engine but no seed selects a different initial state.  This package's fake was not compared "
                     "with MuJoCo, so its trajectories are not evidence of the engine's.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "fake mujoco stand-in, not MuJoCo",
            "not compared with MuJoCo",
            "the stand-in parses the card's MJCF for the actuator count, the per-actuator control ranges, the joint "
            "count and the timestep, but its integration is a placeholder first-order motion, not the muscular, "
            "tendon, contact, equality, mesh or sensor dynamics of the model",
            "MuJoCo itself was not importable where the gate ran (no network, no pip)",
            "the model file and its assets are read from the read-only upstream clone at runtime; the package "
            "copies none of them and the fake loads no mesh, texture or muscle parameter",
            "only the card's models[0] (the bimanual arm) is served; the card's second model, "
            "musclemimic_models/model/body/myofullbody.xml, is not served by this package",
            "no physical device is modelled and nothing was validated against hardware",
        ],
    }
