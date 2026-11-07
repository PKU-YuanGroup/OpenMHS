"""OpenMHS driver for gh.ikalevatykh/mano_pybullet: the HandLiftEnv-v1 gym environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the
``cap.world.*`` contract from the environment's spaces.  The environment is a PyBullet simulation of a MANO-based
hand that lifts an object (R0, mode simulated): there is no hardware backend and no e-stop path to a machine.

The upstream clone is never imported or run by the package or the gate.  The ``fake`` backend is a pure Python
stand-in for ``mano_pybullet.envs:HandLiftEnv`` because upstream needs gym, pybullet, numpy, chumpy and the
separately downloaded MANO models (README.md:25-29, setup.py:36-43).  The real backend name (``sim``), which the
Gymnasium family maps to ``gym.make(env_id)``, was not run here.

Every Fact cites a line of the clone at the pinned commit 960c257cf465f8966e770562b66150beaa359230.  This package
is model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

LIFT = "mano_pybullet/envs/hand_lift_env.py"
HAND = "mano_pybullet/envs/hand_env.py"
OBJECT = "mano_pybullet/envs/hand_object_env.py"
MODEL = "mano_pybullet/hand_model.py"


class ManoHandLift(GymnasiumDriver):
    device_id = "mano-hand-lift"
    env_id = "HandLiftEnv-v1"
    native = "mano_pybullet.envs:HandLiftEnv"
    backends = {"fake": ".fake:FakeHandLiftEnv"}
    display_name = "mano_pybullet HandLiftEnv-v1 (PyBullet MANO hand lifting an object)"
    vendor, model = "Igor Kalevatykh", "mano_pybullet HandLiftEnv-v1"
    tags = ["mano", "pybullet", "hand", "manipulation", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("HandLiftEnv-v1 is registered as a gym environment with entry point mano_pybullet.envs:HandLiftEnv",
             source="upstream_code", ref="mano_pybullet/envs/__init__.py:9-12"),
        Fact("HandLiftEnv is the object-lifting subclass of HandObjectEnv", source="upstream_code", ref=f"{LIFT}:8"),
        Fact("The default target lift height is 0.25", source="upstream_code", ref=f"{LIFT}:11"),
        Fact("The target height is stored in _target_height at construction", source="upstream_code",
             ref=f"{LIFT}:18"),
        Fact("The reward is the z coordinate of the object's base position", source="upstream_code",
             ref=f"{LIFT}:47-48"),
        Fact("The episode is done when the object's z coordinate is greater than the target height",
             source="upstream_code", ref=f"{LIFT}:56-57"),
        Fact("HandLiftEnv passes itself as the model_path argument of HandObjectEnv", source="upstream_code",
             ref=f"{LIFT}:17"),
        Fact("The default hand side is the right hand (HAND_RIGHT = 1) and the default control mode is joint space "
             "(MODE_JOINT = 1)", source="upstream_code", ref=f"{HAND}:19-26"),
        Fact("The default constructor selects hand_side=HAND_RIGHT and control_mode=MODE_JOINT",
             source="upstream_code", ref=f"{HAND}:38-41"),
        Fact("In joint mode the action per hand is a 3-vector base position bounded by -5.0 to 5.0, a 4-vector base "
             "quaternion bounded by -1.0 to 1.0, and the hand model's joint angles", source="upstream_code",
             ref=f"{HAND}:73-80"),
        Fact("The observation per hand is a 3-vector base position, a 4-vector base quaternion, a 6-vector "
             "constraint force bounded by -10.0 to 10.0, the joint angles, joint velocities bounded by -3.0 to 3.0 "
             "and joint torques bounded by -1.0 to 1.0", source="upstream_code", ref=f"{HAND}:81-89"),
        Fact("HandObjectEnv extends the observation space with the object's 3-vector base position and 4-vector base "
             "quaternion", source="upstream_code", ref=f"{OBJECT}:32-37"),
        Fact("The hand state is the base position, base orientation, constraint forces, joint positions, joint "
             "velocities and joint torques", source="upstream_code", ref="mano_pybullet/hand_body.py:81-94"),
        Fact("HandModel20 is a heuristic rigid model with 20 degrees of freedom", source="upstream_code",
             ref=f"{MODEL}:122-123"),
        Fact("The dofs_limits property returns the lower and upper limit of every model degree of freedom",
             source="upstream_code", ref=f"{MODEL}:58-65"),
        Fact("The metadata declares step_time 1.0 / 60.0 seconds", source="upstream_code", ref=f"{HAND}:32-36"),
        Fact("step() runs int(step_time * 240.0) simulation steps and returns observation, reward, done, info",
             source="upstream_code", ref=f"{HAND}:169-177"),
        Fact("reset() sets gravity (0, 0, -10) and deterministicOverlappingPairs=1", source="upstream_code",
             ref=f"{HAND}:125-128"),
        Fact("The gym extra installs gym>=0.17.3 and imageio, and the package requires numpy, chumpy, transforms3d "
             "and pybullet>=3.0.6", source="upstream_code", ref="setup.py:36-43"),
        Fact("The MANO models must be downloaded separately from the MANO website and pointed to by MANO_MODELS_DIR",
             source="vendor_doc", ref="README.md:25-29"),
        Fact("The README describes HandLiftEnv as the environment whose target is to lift an object",
             source="vendor_doc", ref="README.md:46"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  ``ticks`` count environment
    #: steps, each advancing the PyBullet simulation by a fixed 1/60 s.
    fidelity = {
        "engine": "pybullet:mano_pybullet HandLiftEnv-v1",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the default construction does not randomize the hand shape, reset() enables deterministic "
                     "overlapping pairs, and the bridge records the seed (the environment's own RNG is used only "
                     "when randomize_hand_shape is enabled); the bridge reports exact determinism only when the "
                     "environment exposes get_state/set_state, which this one does not",
        },
        "timestep_ms": 1000.0 / 60.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body PyBullet simulation: contact, friction, damping and actuator parameters are those of the "
            "engine and the hand model, not of a physical hand; the model was not validated against a device",
            "the fake backend is kinematic: the object follows the commanded hand base position and the joint "
            "angles only shape the observation; it runs no PyBullet, contact or gravity solver",
            "the upstream HandLiftEnv constructor passes the environment object as model_path to HandObjectEnv "
            "(mano_pybullet/envs/hand_lift_env.py:17), so the upstream simulator path was not run and is not "
            "reproduced by the fake",
            "no wall-clock pacing: realtime_factor 0; ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
            "the fake models the default right hand with the 20 degrees of freedom of HandModel20, not the "
            "optional HandModel45 or the left/both-hand configurations",
            "the action and observation spaces are gymnasium Tuples, so the bridge derives structure but no "
            "per-element limits from them; the action bounds are documented in the Facts",
            "the MANO model files and the hand-shape randomization are not modelled by the fake; the upstream "
            "package requires MANO_MODELS_DIR (README.md:25-29)",
        ],
    }
