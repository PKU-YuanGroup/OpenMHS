"""OpenMHS driver for gh.arise-initiative/robosuite_models: the Aloha bimanual MJCF model (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's first model,
``robosuite_models/assets/robots/aloha/robot.xml``: a fixed-base Aloha body with two six-joint arms and twelve
``motor`` actuators.  The bridge loads the model with the MuJoCo engine, derives ``cap.world.step.v1``'s
``action.ctrl`` from each actuator's ``ctrlrange``, writes ``data.ctrl``, runs ``mj_step`` for ``ticks``, and serves
``cap.world.reset.v1`` with ``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration state
(``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): there is no hardware backend and no physical Aloha is driven.  The model is read from
the read-only clone at the pinned commit and is neither copied into this package nor imported.  MuJoCo is not
installed where the acceptance gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py), which reads the model shape from the same file but integrates a placeholder motion instead of the
engine's physics; the fidelity ``gaps`` below state every difference.

Every Fact cites a line of the clone at commit 2d63a6b4319bda772420daf10594ce0de5bd793d.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran the MuJoCo engine or a
physical robot.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

MODEL = "robosuite_models/assets/robots/aloha/robot.xml"
WRAPPER = "robosuite_models/robots/manipulators/aloha_robot.py"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/arise-initiative/robosuite_models/" + MODEL


class Aloha(MujocoDriver):
    device_id = "robosuite-aloha"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "robosuite_models Aloha bimanual arm (MuJoCo model)"
    vendor, model = "ARISE-Initiative", "Aloha"
    tags = ["aloha", "bimanual", "manipulation", "mujoco", "robosuite", "robot", "simulation"]
    facts = [
        Fact("The repository is a collection of robot models tailored to robosuite", source="vendor_doc",
             ref="README.md:3"),
        Fact("The card's first model is the MJCF document whose root element is '<mujoco model=\"aloha\">'",
             source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The Aloha wrapper loads the same file through robosuite_model_path_completion(\"robots/aloha/"
             "robot.xml\")", source="upstream_code", ref=f"{WRAPPER}:20"),
        Fact("The Aloha wrapper describes the robot as bimanual with two arms and lists the arms right and left",
             source="upstream_code", ref=f"{WRAPPER}:11-17"),
        Fact("The right arm is a chain of six hinge joints named right/waist, right/shoulder, right/elbow, "
             "right/forearm_roll, right/wrist_angle and right/wrist_rotate", source="upstream_code",
             ref=f"{MODEL}:92-116"),
        Fact("The left arm is the matching chain of six hinge joints named left/waist, left/shoulder, left/elbow, "
             "left/forearm_roll, left/wrist_angle and left/wrist_rotate", source="upstream_code",
             ref=f"{MODEL}:139-164"),
        Fact("The actuator section declares twelve motor actuators, one per joint; the control ranges are waist -5 "
             "to 5, shoulder -50 to 50, elbow -50 to 50, forearm_roll -5 to 5, wrist_angle -1 to 1 and wrist_rotate "
             "-1 to 1, repeated for the left arm", source="upstream_code", ref=f"{MODEL}:188-201"),
        Fact("The model sets no option timestep: the compiler and option elements are inside an XML comment at "
             "lines 2-4, so no <option timestep> element is active", source="upstream_code", ref=f"{MODEL}:2-4"),
        Fact("The finger default classes, with a slide joint range and a position ctrlrange, are inside an XML "
             "comment at lines 34-43, so those finger defaults are not active in this model", source="upstream_code",
             ref=f"{MODEL}:34-43"),
        Fact("The Aloha wrapper attaches the AlohaGripper to the right and left arms by default; the gripper is not "
             "part of robot.xml", source="upstream_code", ref=f"{WRAPPER}:26-35"),
        Fact("The model declares its six visual meshes as STL files with a 0.001 scale under meshes/",
             source="upstream_code", ref=f"{MODEL}:60-65"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch, and the integration state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the determinism kind, the timestep and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:aloha",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the reset state and the model has no "
                     "random element, so one ctrl sequence and tick count repeat a trajectory; the package's fake "
                     "backend is deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the served robot.xml for "
            "the 12 joints, the 12 actuator ctrlranges and the time step, then moves each actuated joint toward its "
            "control value; it computes no inertia, torque, contact, equality or actuator dynamics, so no "
            "trajectory here is a MuJoCo result",
            "the stand-in loads no mesh or texture and resolves no contact: the six STL meshes of the model are "
            "not read, and the two contact exclusions of the model are not applied",
            "the served robot.xml is the bare two-arm model; the AlohaGripper that the robosuite wrapper attaches "
            "to each arm (aloha_robot.py:26-35) is not part of this MJCF, so no finger joint or gripper actuator is "
            "served",
            "the model sets no option timestep; the stand-in uses a placeholder library default as the step "
            "(fake.py), and the bridge publishes that stand-in value from the stand-in",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "no rendering, cameras or sensor publication: the two wrist cameras of the model are not exposed, and "
            "only the bridge's time, qpos, qvel and ctrl state is published",
            "no physical Aloha robot is modelled and nothing was validated against the hardware",
        ],
    }
