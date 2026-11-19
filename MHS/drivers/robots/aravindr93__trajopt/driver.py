"""OpenMHS MuJoCo driver for gh.aravindr93/trajopt: the 7-DoF reacher model behind the upstream environments.

The pinned clone is a trajectory-optimization repository whose concrete environments are
``trajopt.envs.reacher_env:Reacher7DOFEnv`` and ``ContinualReacher7DOFEnv`` (card entry symbols).  Both wrap the
shipped MJCF ``trajopt/envs/assets/sawyer.xml`` through ``mjrl.envs.mujoco_env.MujocoEnv``; they need gym, mjrl and
mujoco_py, which are not installed where the gate runs (``setup.py`` does not even list mjrl).  This package therefore
serves the model itself through the card's ``MujocoDriver``: ``cap.world.step.v1`` writes ``data.ctrl`` after checking
each element against the model's ``actuator_ctrlrange`` and calls ``mj_step``; ``cap.world.reset.v1`` calls
``mj_resetData`` + ``mj_forward``. ``cap.world.seed.v1`` is not served; reset accepts the class's seed field but
MuJoCo reset does not use it.

The model is read in place from the read-only clone at the pinned commit
``23fbc453af2e980788348e5bde18136ad52378f0``; nothing is copied or imported from it.  MuJoCo is not installed, so
``backends["fake"]`` is this package's pure Python stand-in ``mujoco`` module (``fake.py``): it parses the MJCF for
the joint dimensions, timestep, joint ranges and the seven motors' ctrlranges, and integrates a placeholder torque
model.  The driver publishes the stand-in's F0 contract through ``fidelity_by_backend`` and the real MuJoCo F1
contract at class level; the real path was not run.

The upstream Gym wrapper's reward, its declared observation (26) and its ``done=False`` step are not part of the
MuJoCo family's ``cap.world.*`` contract and are not served; the driver exposes the model's qpos/qvel/ctrl/time.
This package is model-authored and unreviewed, is checked on the fake backend only, and claims no MuJoCo, Gym or
hardware run.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The shipped MJCF named by the card's models[0], relative to the pinned clone root.
MODEL = "trajopt/envs/assets/sawyer.xml"
#: The same file, relative to this package directory.
MODEL_PATH = "../../../../robots/aravindr93/trajopt/" + MODEL
ENV = "trajopt/envs/reacher_env.py"
REGISTRATION = "trajopt/envs/__init__.py"


class TrajoptReacher(MujocoDriver):
    device_id = "trajopt-reacher"
    device_kind = "world.sim"
    mode = "simulated"
    # Direct stepping of isolated simulated state is R0 (MHS-004 SAFE-006, catalog cap.world.step.v1).
    risk = "R0"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "trajopt 7-DoF reacher MuJoCo model"
    vendor, model = "Aravind Rajeswaran", "7dof reacher"
    tags = ["trajopt", "reacher", "mujoco", "mjcf", "simulation", "robot-arm", "reinforcement-learning"]
    facts = [
        Fact("The README describes the package as trajectory optimization algorithms for continuous-control tasks "
             "simulated with MuJoCo.", source="vendor_doc", ref="README.md:2"),
        Fact("The README names MuJoCo and mjrl as the main dependencies and says mujoco_py must be installed before "
             "the package is used.", source="vendor_doc", ref="README.md:5-7"),
        Fact("The concrete environment class Reacher7DOFEnv extends mjrl's MujocoEnv and gym's EzPickle.",
             source="upstream_code", ref=f"{ENV}:8"),
        Fact("The constructor passes the model path curr_dir+'/assets/sawyer.xml' and the number 2 to "
             "MujocoEnv.__init__.", source="upstream_code", ref=f"{ENV}:20-21"),
        Fact("The environment declares observation_dim 26 and action_dim 7.", source="upstream_code",
             ref=f"{ENV}:23-24"),
        Fact("get_obs concatenates qpos, qvel, the finger site position and the finger-minus-target site "
             "difference.", source="upstream_code", ref=f"{ENV}:41-47"),
        Fact("step calls do_simulation(a, frame_skip), computes the reward -l1_dist - 5.0*l2_dist from the finger "
             "and target site positions, and returns False as done.", source="upstream_code", ref=f"{ENV}:29-39"),
        Fact("The target reset draws the target site position uniformly from x -0.3..0.3, y -0.2..0.2 and "
             "z -0.25..0.25.", source="upstream_code", ref=f"{ENV}:56-62"),
        Fact("reset_model resets the robot and the target and returns get_obs.", source="upstream_code",
             ref=f"{ENV}:64-71"),
        Fact("The registration comment says max_episode_steps is not used internally in trajopt; trajopt_reacher-v0 "
             "is registered with 75 and trajopt_continual_reacher-v0 with 250.", source="upstream_code",
             ref=f"{REGISTRATION}:6-19"),
        Fact("The reacher_env module imports gym.utils, mjrl.envs.mujoco_env and mujoco_py.MjViewer.",
             source="upstream_code", ref=f"{ENV}:1-4"),
        Fact("setup.py's install_requires lists click, gym, mujoco_py, termcolor, tqdm and numpy, but not mjrl.",
             source="upstream_code", ref="setup.py:20-27"),
        Fact("The MJCF model is named '7dof reacher', compiles angles in radians and local coordinates, and resolves "
             "inertia from the geoms.", source="upstream_code", ref=f"{MODEL}:1-2"),
        Fact("The model option sets timestep 0.01 s, gravity 0 0 0 and the Euler integrator.",
             source="upstream_code", ref=f"{MODEL}:3"),
        Fact("The default joint class sets armature 0.004, damping 0.8 and limited true.",
             source="upstream_code", ref=f"{MODEL}:5"),
        Fact("The model has seven hinge joints with ranges: r_shoulder_pan -2.2854..1.714602, r_shoulder_lift "
             "-0.5236..1.3963, r_upper_arm_roll -1.5..1.7, r_elbow_flex -2.3213..0, r_forearm_roll -1.5..1.5, "
             "r_wrist_flex -1.094..0 and r_wrist_roll -1.5..1.5, all in radians.", source="upstream_code",
             ref=f"{MODEL}:2-50"),
        Fact("The actuator block declares seven motor actuators, one per hinge joint, each with ctrllimited true and "
             "ctrlrange -1.0..1.0; the shoulder-pan gear is 20 and the other six are 10.",
             source="upstream_code", ref=f"{MODEL}:101-109"),
        Fact("The model declares a target site at position 0.1 0.1 0.1 and a finger site on the wrist-roll body.",
             source="upstream_code", ref=f"{MODEL}:13-59"),
        Fact("The repository LICENSE is the MIT License, copyright 2018 Aravind Rajeswaran.",
             source="vendor_doc", ref="LICENSE:1-3"),
    ]
    safe_state = ("the simulated world stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the integration state stays readable")
    #: The real MuJoCo engine contract.  The bridge derives the engine, timestep and lockstep clock; the members
    #: here are this package's.  The F1 path was not run because MuJoCo is not installed where the gate runs.
    fidelity = {
        "engine": "mujoco:7dof reacher",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "cap.world.reset.v1 restores the model defaults with mj_resetData and does not use a seed; "
                     "a native checkpoint does not establish callback, plugin or RNG completeness, so the bridge "
                     "does not claim seeded or exact determinism.",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "MuJoCo is not installed where the gate ran: the real engine path was never opened, the MJCF was not "
            "compiled by MuJoCo, and no trajectory was compared with the engine",
            "the upstream Gym wrappers Reacher7DOFEnv and ContinualReacher7DOFEnv are not imported: their reward, "
            "26-D observation declaration, done=False step and target randomization are not part of the MuJoCo "
            "family's cap.world.* contract, which serves qpos/qvel/ctrl/time instead",
            "the upstream environments need gym, mjrl.envs.mujoco_env and mujoco_py.MjViewer; setup.py does not "
            "even list mjrl, and this package imports none of those packages",
            "the bridge exposes qpos, qvel, ctrl and time, not the finger and target site positions, camera "
            "frames, contacts or any sensor array; the MJCF declares no sensor",
            "contact, friction, composite inertia, joint force limits and actuator force dynamics are those of the "
            "model file and were not validated against a physical 7-DoF arm",
            "the registered max_episode_steps 75 and 250 are Gym wrapper metadata (the registration says they are "
            "not used internally); the MuJoCo model has no terminal condition",
            "no hardware backend exists: this simulated R0 package drives no arm and no hardware run is claimed",
        ],
    }
    #: The fake backend is this package's stand-in mujoco module, not MuJoCo and not a recorded trajectory.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:stand-in mujoco module (no physics)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "none",
                "seed_control": "none",
                "notes": "The stand-in repeats the same placeholder integration for the same controls, but it is "
                         "not MuJoCo and has no seed input; a matching state hash is not a MuJoCo trajectory.",
            },
            "timestep_ms": 10.0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": True,
            "gaps": [
                "the fake is a stand-in for the mujoco module, not MuJoCo: it parses the MJCF for nq, nv, nu, the "
                "timestep, joint ranges and the seven ctrlranges, but computes no composite inertia, contact, "
                "friction, constraint, tendon or sensor physics",
                "each motor's torque (gear * ctrl) accelerates only its own joint against a placeholder unit "
                "inertia plus the model's armature; the model's zero gravity is omitted, joint limits are clamped, "
                "and this is not MuJoCo's Euler integration",
                "the fake computes no site positions, so the upstream finger/target reward and observation are not "
                "reproduced (the family does not serve them)",
                "the stand-in has no mj_getState/mj_setState, so snapshots use the bridge's basic profile (time, "
                "qpos, qvel, ctrl, tick); warm-start, qacc and derived state are not preserved",
                "no rendering, viewer, contact, sensor or actuator force limit is modelled",
                "the fake was not compared with MuJoCo or with the upstream environment; all integration constants "
                "the model does not state are marked placeholder in fake.py",
            ],
        },
    }
