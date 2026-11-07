"""OpenMHS driver for gh.engineai-robotics/engineai_legged_gym: the ZqSA01 humanoid MJCF (a MuJoCo family driver).

The card's upstream entry point is ``legged_gym.scripts.sim2sim_zqsa01:run_mujoco`` (line 105): a MuJoCo loop that
takes a TorchScript policy and a ``Sim2simCfg`` defined only under ``__main__``, imports ``legged_gym.envs`` (which
pulls in Isaac Gym) and exposes no reset, step or seed of its own.  This package therefore serves the card's
``models[0]``, ``resources/robots/zq_humanoid/urdf/zq_sa01.xml``, through ``MujocoDriver``: the bridge loads the MJCF,
takes the step action from ``data.ctrl`` (twelve motors, bounded per actuator by the model's ``actuator_ctrlrange`` of
-200 to 200) and derives the world state from the model and data arrays.

The device is simulated (R0, ``world.sim``): there is no hardware backend, no physical stop and no operator-required
limit.  MuJoCo is not installed and cannot be installed where the acceptance gate runs (no network, no pip), so the
``fake`` backend is this package's stand-in ``mujoco`` module (fake.py).  It parses the same MJCF for the joint shape,
the twelve actuators, their explicit control ranges, the free base pose and the 0.002 s option step, but its
integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` say so.  A backend name that ``backends``
does not list (``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  Every Fact cites a line or line range of the clone at commit
1a659aa0aa77445766ecea6d95708a5812e9f290.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "resources/robots/zq_humanoid/urdf/zq_sa01.xml"
SCRIPT = "legged_gym/scripts/sim2sim_zqsa01.py"
README = "README.md"
SETUP = "setup.py"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/engineai-robotics/engineai_legged_gym/" + MODEL


class ZqSa01(MujocoDriver):
    device_id = "zqsa01"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "EngineAI ZqSA01 humanoid (MuJoCo model)"
    vendor, model = "EngineAI Robotics", "ZqSA01 humanoid"
    tags = ["engineai", "zqsa01", "humanoid", "legged", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The repository provides the environments used to train engineai robots to walk on rough terrain with "
             "NVIDIA's Isaac Gym and includes sim2sim and sim2real components", source="vendor_doc",
             ref=f"{README}:2-4"),
        Fact("The package declares mujoco and mujoco-python-viewer in install_requires", source="upstream_code",
             ref=f"{SETUP}:22-23"),
        Fact("run_mujoco loads the model with mujoco.MjModel.from_xml_path(cfg.sim_config.mujoco_model_path)",
             source="upstream_code", ref=f"{SCRIPT}:116"),
        Fact("Sim2simCfg points mujoco_model_path at resources/robots/zq_humanoid/urdf/zq_sa01.xml below the clone "
             "root", source="upstream_code", ref=f"{SCRIPT}:294"),
        Fact("The MJCF root element declares the model zqsa01", source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The model uses radians, resolves its meshes from ../meshes/, and its option element sets timestep "
             "0.002 s, 50 Newton iterations, gravity 0 0 -9.81 and the RK4 integrator", source="upstream_code",
             ref=f"{MODEL}:2-3"),
        Fact("The world contains a plane floor and a base_link body at 0 0 1.5 that carries the free joint root",
             source="upstream_code", ref=f"{MODEL}:38-43"),
        Fact("The left leg has six limited hinge joints from leg_l1_joint to leg_l6_joint, each with its own range",
             source="upstream_code", ref=f"{MODEL}:54-88"),
        Fact("The right leg has six limited hinge joints from leg_r1_joint to leg_r6_joint, each with its own range",
             source="upstream_code", ref=f"{MODEL}:101-135"),
        Fact("The actuator section has twelve motor actuators, one per leg hinge, each with ctrllimited true and "
             "ctrlrange -200 200", source="upstream_code", ref=f"{MODEL}:147-168"),
        Fact("run_mujoco computes PD torques, clips them to cfg.robot_config.tau_limit and writes the result to "
             "data.ctrl", source="upstream_code", ref=f"{SCRIPT}:193-197"),
        Fact("Sim2simCfg sets tau_limit to 200 for all 12 joints", source="upstream_code", ref=f"{SCRIPT}:302"),
        Fact("Sim2simCfg sets dt to 0.001 s and decimation to 10", source="upstream_code", ref=f"{SCRIPT}:296-297"),
        Fact("run_mujoco overwrites model.opt.timestep with cfg.sim_config.dt before creating MjData",
             source="upstream_code", ref=f"{SCRIPT}:118"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed.  The bridge derives the engine, time step, determinism kind and
    #: lockstep clock; the members below make the whole contract readable in one place.
    fidelity = {
        "engine": "mujoco:zqsa01",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates the fixed model deterministically from the model defaults; the bridge accepts "
                     "a seed in cap.world.reset.v1 but a MuJoCo reset restores the model defaults and does not use it, "
                     "so one control sequence repeats a trajectory on the same engine.  The package's stand-in is "
                     "deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the MJCF for the free base, "
            "the twelve hinge joints, the twelve motor actuators, their explicit ctrlranges and the 0.002 s option "
            "step, then gives each actuated hinge a placeholder velocity proportional to its control value and holds "
            "the free base where the model puts it; it computes no inertia, torque, gravity, contact, friction, "
            "constraint, damping or actuator dynamics and produces no MuJoCo trajectory",
            "the stand-in loads no STL mesh or texture and resolves no collision or contact; the model's floor, base "
            "collision geom and armature attributes are not applied",
            "the upstream sim2sim loop overwrites the model time step with its own 0.001 s dt and writes PD torques, "
            "clipped to 200, to data.ctrl; this package loads the MJCF directly, serves its own 0.002 s step and "
            "takes the control vector from the caller",
            "the fake reset restores the parsed model qpos0 and zeros; a real MjData reset also restores the full "
            "integration state, which this package did not inspect",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared with "
            "the real engine",
            "no physical humanoid is modelled and nothing was validated against the ZqSA01 hardware",
        ],
    }
