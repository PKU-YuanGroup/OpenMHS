"""OpenMHS driver for gh.mosesandlily/whip-project-targeting: the 3D whip-targeting MJCF scene (MuJoCo family).

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's 3D whip scene, ``models/3D_model_w_whip_T1.xml``,
and the bridge derives the contract from the model it loads.  ``cap.world.step.v1`` takes ``{ticks, action}`` and
writes ``action.ctrl``, one number per active actuator, to ``data.ctrl`` before running ``mj_step`` once per tick;
``cap.world.reset.v1`` runs ``mj_resetData`` + ``mj_forward`` and returns the model defaults.  The world state is the
bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The scene is the T1 target of the user-facing ``main_whip.py`` path: the script builds the model name as
``"3D_model_w_whip_T" + target_type`` (``main_whip.py:43-44``).  The MJCF declares four arm hinges and a 25-node whip,
and four ``<motor>`` actuators, one per arm joint (``models/3D_model_w_whip_T1.xml:41-52, 220-225``).  The motors state
no ``ctrlrange``, so the bridge publishes ``action.ctrl`` as ``operator_required``: the endpoint refuses a step that
sets it (``MHS.SAFETY.LIMITS_UNSET``, before any native call) until the site's ``site-limits.json`` bounds it;
``site-limits.example.json`` is operator example data, not a bound of the model.

The device is simulated (R0): no physical arm or whip is driven.  MuJoCo and mujoco-py are neither installed nor
installable where the acceptance gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py).  It parses the same MJCF for the joint dimensions, the actuator count and the absent control ranges, but
its integration is a placeholder, not MuJoCo's physics; the fake fidelity contract says so.  A backend name that
``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run
here.  The model file is read from the read-only clone and never copied or imported.  Every fact cites a line of the
clone at commit 8025f9f156bf3cf591afbedca18eaa03e3846d4a.  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's user-facing 3D scene, relative to the read-only clone under robots/ at the pinned commit.
MODEL = "models/3D_model_w_whip_T1.xml"
MODEL_PATH = "../../../../robots/mosesandlily/whip-project-targeting/" + MODEL
SIMULATION = "modules/simulation.py"
MAIN = "main_whip.py"
README = "README.md"


class WhipTargeting(MujocoDriver):
    device_id = "whip-targeting"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Whip targeting 3D scene (MuJoCo, target 1)"
    vendor, model = "mosesandlily", "3D_model_w_whip_T1"
    tags = ["whip", "targeting", "dynamic-primitives", "mujoco", "robot", "simulation"]
    facts = [
        Fact("The README presents the repository as a controller-design study that controls a whip, described as a "
             "complex object with significant dynamics", source="vendor_doc", ref=f"{README}:3"),
        Fact("The README's setup downloads the requirements with pip for the mujoco-py simulation",
             source="vendor_doc", ref=f"{README}:40-42"),
        Fact("The module defines class Simulation, documented as running a single whip simulation",
             source="upstream_code", ref=f"{SIMULATION}:16-19"),
        Fact("The Simulation constructor loads the selected model with mjPy.load_model_from_path from "
             "C.MODEL_DIR + model_name + '.xml' and wraps it in mjPy.MjSim", source="upstream_code",
             ref=f"{SIMULATION}:35-36"),
        Fact("Simulation reads n_act from the model's actuator_names, nq from its joint_names and dt from "
             "model.opt.timestep", source="upstream_code", ref=f"{SIMULATION}:47-57"),
        Fact("Simulation.set_init_posture writes the caller's qpos and qvel into mj_data and calls mj_sim.forward; "
             "it takes no seed", source="upstream_code", ref=f"{SIMULATION}:98-116"),
        Fact("Simulation.reset calls mj_sim.reset and resets each attached controller",
             source="upstream_code", ref=f"{SIMULATION}:125-132"),
        Fact("Simulation.run halts the loop as unstable when max(abs(mj_data.qacc)) exceeds 10 ** 6",
             source="upstream_code", ref=f"{SIMULATION}:250-261"),
        Fact("Simulation.get_state returns the concatenated mj_data.qpos and mj_data.qvel arrays",
             source="upstream_code", ref=f"{SIMULATION}:263-267"),
        Fact("Simulation.stepML writes the action into mj_data.ctrl[:n_act] and calls mj_sim.step",
             source="upstream_code", ref=f"{SIMULATION}:305-313"),
        Fact("The user-facing main_whip.py builds the model name as '3D_model_w_whip_T' + str(target_type)",
             source="upstream_code", ref=f"{MAIN}:43-44"),
        Fact("The model root is '<mujoco model=\"1_3D_model_w_N25\">' and its compiler declares the angle unit "
             "as radian", source="upstream_code", ref=f"{MODEL}:1-2"),
        Fact("The option element sets timestep 0.0001 s, 50 iterations, the PGS solver, the Euler integrator and "
             "gravity 0 0 -9.81", source="upstream_code", ref=f"{MODEL}:3-5"),
        Fact("The arm has four hinge joints named joint_shoulder_flex_ext, joint_shoulder_add_abd, "
             "joint_shoulder_med_lat and joint_elbow", source="upstream_code", ref=f"{MODEL}:41-52"),
        Fact("The whip chain runs from body_whip_node1 to body_whip_node25, and every node carries an X hinge and "
             "a Y hinge", source="upstream_code", ref=f"{MODEL}:61-186"),
        Fact("The target sphere geom has position 1.9950 0.0000 0.0000, size 0.03 and "
             "mass 0", source="upstream_code", ref=f"{MODEL}:216"),
        Fact("The actuator section declares four motor actuators, one per arm joint, and each sets "
             "forcelimited false and states no ctrlrange", source="upstream_code", ref=f"{MODEL}:220-225"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state, including the last controls, is kept "
                  "and stays readable. A later explicit step without action reuses those controls")
    #: The real MuJoCo engine contract (the implicit sim backend); the fake overrides it below with its F0 contract.
    fidelity = {
        "engine": "mujoco:1_3D_model_w_N25",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "MuJoCo integrates a fixed model deterministically from a fixed initial state, but the bridge "
                     "reset restores the model defaults with mj_resetData and takes no working seed, so no seed "
                     "selects a different trajectory; the fake is deterministic too but its motion is not the "
                     "engine's physics.",
        },
        "timestep_ms": 0.1,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the upstream Simulation task interface is NOT COVERED: it builds an argparse Namespace, sets an initial "
            "posture through Simulation.init and make_whip_downwards, runs joint-impedance controllers and an "
            "objective, renders a viewer and can halt on instability; the bridge serves mj_resetData/mj_step and the "
            "model integration state instead",
            "no seed selects a different initial state: cap.world.reset.v1 restores the model defaults and the seed "
            "input only records the endpoint's configured value",
            "the model's four motors state no ctrlrange, so the bridge publishes action.ctrl operator_required; "
            "site-limits.example.json is operator example data (-10.0 to 10.0 per control), not a model bound, and a "
            "deployment must supply its own site-limits.json envelope",
            "only models/3D_model_w_whip_T1.xml is served; the card's 2D_model_w_whip.xml and the N10-N20 and T2-T6 "
            "scenes are not",
            "MuJoCo and mujoco-py are not importable where the gate runs, so the real engine path and its snapshot "
            "behaviour were not exercised and no trajectory of this package was compared with the engine",
        ],
    }
    #: The fake is the package's stand-in mujoco module, not MuJoCo: F0, placeholder motion (fake.py).
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:stand-in mujoco module (no physics)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "none",
                "seed_control": "none",
                "notes": "The stand-in has no seed input and restores all-zero model defaults; it applies a "
                         "deterministic placeholder velocity from each control value, which is not the engine's "
                         "physics.",
            },
            "gaps": [
                "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the MJCF for the 54 "
                "hinge joints, the four motor actuators, their absent ctrlranges and the 0.0001 s option timestep, "
                "then moves each actuated hinge by a placeholder velocity proportional to its control value; it "
                "computes no inertia, gear, torque, gravity, contact, friction, constraint, damping or actuator "
                "dynamics and produces no MuJoCo trajectory",
                "the stand-in loads no mesh or texture and resolves no collision, contact or sensor; the model's "
                "target sphere and whip inertias are not simulated",
                "the fake reports no ctrlrange for the four motors, exactly as the model states; the bridge therefore "
                "publishes action.ctrl operator_required and site-limits.example.json is operator example data, not "
                "a model bound; a step that sets action.ctrl is refused until an operator overlay bounds it",
                "the fake has no mj_getState, mj_setState, mj_stateSize or mjtState, so the bridge uses its basic "
                "checkpoint profile: time, qpos, qvel and ctrl are restored, not MuJoCo's full integration state",
                "the upstream Simulation task interface is NOT COVERED: it applies the caller's qpos and qvel, makes "
                "the whip downwards, runs joint-impedance controllers and an objective, and uses a 10 ** 6 "
                "acceleration instability halt; the bridge serves raw ctrl and the integration state instead",
                "the fake reset restores all-zero model defaults, not the initial posture that main_whip.py writes; "
                "cap.world.reset.v1 accepts a seed but does not use it",
                "only models/3D_model_w_whip_T1.xml is served; the card's 2D_model_w_whip.xml and the N10-N20 and "
                "T2-T6 scenes are not",
                "MuJoCo itself was not importable where the gate ran, so the stand-in was not compared with the real "
                "engine and the sim backend that imports mujoco was not run; no physical arm or whip is modelled",
            ],
        },
    }
