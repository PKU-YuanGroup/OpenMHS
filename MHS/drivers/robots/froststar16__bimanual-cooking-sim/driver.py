"""OpenMHS driver for gh.froststar16/bimanual-cooking-sim: the bimanual kitchen scene as a simulated MuJoCo world.

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's primary scene, ``models/kitchen_scene.xml``
(the stir stage: two seven-joint arms, a pot and a spoon), and the bridge derives the whole contract from that model.
``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [14 numbers]}}``; the bridge checks each control value against the
matching actuator's ``actuator_ctrlrange`` (the ``arm_actuator`` default class gives every motor -80 to 80), writes
``data.ctrl`` and runs ``mj_step`` for ``ticks`` steps.  ``cap.world.reset.v1`` calls ``mj_resetData`` + ``mj_forward``
and returns the model-default state.  The world state is the bridge's integration state (``time_ms``, ``qpos``,
``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): there is no hardware backend and no physical arm is driven.  The scene is read in place
from the read-only clone at the pinned commit and is never copied into this package.  The seven other scenes of the
clone (``pan_flip``, ``pan_pour``, ``bottle``, ``cook`` and the three ``omelette_*`` acts) are not exposed by this
package; the card's ``models[0]`` is the scene served here.  MuJoCo is not installed where the acceptance gate runs,
so ``backends["fake"]`` is this package's stand-in ``mujoco`` module (``fake.py``), which reads the model shape from
the same scene but integrates a placeholder motion instead of the engine's physics; the fidelity ``gaps`` below state
every difference.

Every Fact cites a line of the clone at commit 6ca8f1c83378d1e3fe39a4cc9083eefe6540c5ec.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran the MuJoCo engine or a
physical device.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

SCENE = "models/kitchen_scene.xml"
#: The card's models[0] relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/froststar16/bimanual-cooking-sim/" + SCENE


class BimanualKitchen(MujocoDriver):
    device_id = "bimanual-kitchen"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "Bimanual cooking kitchen (MuJoCo scene)"
    vendor, model = "Froststar16", "Bimanual kitchen MJCF scene"
    tags = ["mujoco", "bimanual", "robot arm", "cooking", "manipulation", "simulation"]
    facts = [
        Fact("The repository is a two-armed robot cooking simulation built in MuJoCo", source="vendor_doc",
             ref="README.md:5-8"),
        Fact("Two 7-DOF arms are driven by the same operational-space impedance controller", source="vendor_doc",
             ref="README.md:10-14"),
        Fact("The README lists kitchen_scene.xml as the stir stage with two arms, a pot and a spoon", source="vendor_doc",
             ref="README.md:178"),
        Fact("The kitchen scene is the MJCF model 'bimanual_kitchen'", source="upstream_code", ref=f"{SCENE}:1"),
        Fact("The scene is self-contained: it is built from primitives, needs no external meshes and carries the two "
             "7-DOF arms and a rigidly attached spoon", source="upstream_code", ref=f"{SCENE}:2-6"),
        Fact("The scene compiles with the radian angle unit and automatic limits", source="upstream_code",
             ref=f"{SCENE}:8"),
        Fact("The scene sets the integration step to 0.002 s with the implicitfast integrator and gravity -9.81 m/s^2",
             source="upstream_code", ref=f"{SCENE}:9"),
        Fact("The arm default class gives every arm joint hinge damping 2.0, armature 0.1 and frictionloss 0.2",
             source="upstream_code", ref=f"{SCENE}:20"),
        Fact("The nested arm_actuator default class sets each motor's control range to -80 to 80 with gear 1",
             source="upstream_code", ref=f"{SCENE}:23-24"),
        Fact("The right arm has seven hinge joints r_j1 to r_j7 with the ranges -2.9 to 2.9, -1.8 to 1.8, -2.5 to 2.5, "
             "-2.9 to 2.9, -2.0 to 2.0, -2.9 to 2.9 and -2.0 to 2.0 rad", source="upstream_code",
             ref=f"{SCENE}:67-85"),
        Fact("The left arm has seven hinge joints l_j1 to l_j7 with the same ranges as the right arm's", source="upstream_code",
             ref=f"{SCENE}:114-132"),
        Fact("The actuator section declares 14 motors, r_m1 to r_m7 and l_m1 to l_m7, one for each arm joint",
             source="upstream_code", ref=f"{SCENE}:145-159"),
        Fact("The stir task loads models/kitchen_scene.xml with mujoco.MjModel.from_xml_path and creates an MjData",
             source="upstream_code", ref="sim/runner.py:117-118"),
        Fact("The runner advances the model with mujoco.mj_step", source="upstream_code", ref="sim/runner.py:414"),
        Fact("The required Python packages are mujoco 3.0 or newer, numpy, imageio and pillow", source="upstream_code",
             ref="requirements.txt:1-4"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the determinism kind, the timestep and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:bimanual_kitchen",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the reset state and the model has no random "
                     "element, so one ctrl sequence and tick count repeat the trajectory.  The package's fake "
                     "backend is deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses models/kitchen_scene.xml "
            "for the 2 ms step, the 14 qpos and 14 dof hinge coordinates and the 14 motor ctrlranges, then moves "
            "each actuated joint toward its control value; it computes no inertias, contacts, friction loss, "
            "armature, gravity or actuator dynamics, so no trajectory here is a MuJoCo result",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "only models/kitchen_scene.xml is served: the clone's pan_flip, pan_pour, bottle, cook and omelette_* "
            "scenes (and their free joints and generated props) are not exposed by this package",
            "the scene has no keyframe; reset calls mj_resetData and starts from the model defaults, not from a "
            "home pose",
            "no rendering, cameras or sensor publication: the scene has no sensor stream and the bridge exposes "
            "only time, qpos, qvel and ctrl",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the model's 2 ms step only",
            "snapshot and restore use the stand-in integration state; the bridge offers them but the CL3 gate does "
            "not exercise them",
            "the scene is a simulation asset: no physical robot or kitchen is modelled or controlled and nothing "
            "here was validated against hardware",
        ],
    }
